"""Execution Orchestrator (ACIS-06 v1.1, master §7). How and where — never
how much.

Hard walls: never sends more than `size_units` (C-EXE-6); never opens what the
Governor sized to zero; the execution-freeze (Risk flatten path, phase 9) blocks
opens while allowing closes; slippage is REPORTED, never acted on (F10: no throttle
knob). Randomness and time are injected. `dispatch_budget_ms` is observability only
(v2.10 item c). The venue's own limits DO gate (GAP-P12D-57, venue_limits.py): whole
lot steps rounded DOWN, below the minimum lot refused, and a spent request budget
refuses opens but never a close that truly shrinks the position — each a FillReport.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

from config.schemas import ExecutionConfig
from core.data.errors import DataQualityError
from core.execution.fragmenter import Fragment, FragmentPlan, plan
from core.execution.venue import (
    ExecutionFace,
    FillReport,
    FillReportStore,
    FillStatus,
    UNITS_PER_LOT,
    VenueQuality,
)
from core.execution.venue_limits import WINDOW, RequestBudget, lot_units, venue_quantity
from core.governor.portfolio_types import SizedOrder

# §7 steps 5–6: "bounded" remainder/reroute policy — the bounds, as constants.
MAX_REMAINDER_RETRIES = 2      # partial-fill remainder resubmissions per fragment
MAX_REROUTES = 1               # venue reroutes after a rejection per fragment


class ExecutionOrchestrator:
    def __init__(
        self,
        cfg: ExecutionConfig,
        faces: dict[str, ExecutionFace],
        quality: VenueQuality,
        store: FillReportStore,
        slippage_alert_bps: float,          # from guardrails — single source
        rng,                                # SystemRandom prod / seeded tests
        logger,
        session_id: str,
        now_fn=lambda: datetime.now(timezone.utc),
        sleep_fn=None,
    ) -> None:
        if not faces:
            raise DataQualityError("faces", faces, "needs >= 1 execution face")
        self._cfg = cfg
        self._faces = faces
        self._quality = quality
        self._store = store
        self._alert_bps = slippage_alert_bps
        self._rng = rng
        self._log = logger
        self._session = session_id
        self._now = now_fn
        if sleep_fn is None:
            import asyncio
            sleep_fn = asyncio.sleep
        self._sleep = sleep_fn
        self._frozen: str | None = None
        self.budget_exceeded_count = 0      # §10 loop-health surface
        since = self._now() - WINDOW        # a restart re-seeds, never resets (GAP-P12D-57)
        self._requests = {name: RequestBudget(name, cfg.max_venue_requests_per_day,
                                              store.request_times(name, since))
                          for name in faces}

    # -- freeze (Risk flatten path lands here at phase 9) ---------------------- #

    def set_freeze(self, active: bool, reason: str) -> None:
        self._frozen = reason if active else None
        self._log.event("EXEC_FREEZE", active=active, reason=reason)

    @property
    def frozen(self) -> bool:
        return self._frozen is not None

    # -- §7 core logic ---------------------------------------------------------- #

    async def submit(self, order: SizedOrder, *,
                     valid_for_seconds: int) -> tuple[FillReport, ...]:
        """Execute one SizedOrder. `valid_for_seconds` is the originating
        signal's validity (the loop owner carries it across; SizedOrder does
        not — ACIS-05 locked shape): < cfg.fast_decay_seconds ⇒ aggressive IOC.
        Returns every FillReport (fills, partials, rejects) — Risk's input."""
        t0 = time.perf_counter()
        if order.size_units == 0:
            self._log.event("EXEC_NOOP", order_id=order.order_id)
            return ()
        if self._frozen is not None and order.action == "open":
            self._log.event("EXEC_FROZEN_REJECT", order_id=order.order_id,
                            reason=self._frozen)
            return ()
        self._log.event("SUBMIT", order_id=order.order_id,
                        instrument=order.instrument, action=order.action,
                        size_units=str(order.size_units))

        fast_decay = valid_for_seconds < self._cfg.fast_decay_seconds
        total_lots = float(order.size_units / UNITS_PER_LOT)
        venues = self._capable_venues(order, total_lots, need_ioc=fast_decay)
        if not venues:
            self._log.event("EXEC_CAPABILITY_REJECT", order_id=order.order_id,
                            instrument=order.instrument, lots=total_lots,
                            ioc=fast_decay)
            report = self._synthetic_reject(order, "no_capable_venue")
            self._record(report)
            return (report,)

        units, reports = self._venue_quantity(order, order.size_units, venues[0],
                                              order.order_id)
        if units == 0:
            return tuple(reports)
        fragment_plan = plan(order.order_id, units, fast_decay=fast_decay, cfg=self._cfg,
                             venues=venues, now=self._now(), rng=self._rng,
                             quantum=lot_units(self._faces[venues[0]].descriptor.lot_step))
        self._log.event(          # logged BEFORE dispatch: crash-reconcilable (§9)
            "FRAGMENT_PLAN", order_id=order.order_id, path=fragment_plan.path,
            weighting=fragment_plan.weighting, n=len(fragment_plan.fragments),
            fragments=[{"id": f.fragment_id, "units": str(f.units),
                        "venue": f.venue, "at": f.scheduled_at.isoformat()}
                       for f in fragment_plan.fragments])
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if elapsed_ms > self._cfg.dispatch_budget_ms:   # v2.10(c): observe, never gate
            self.budget_exceeded_count += 1
            self._log.event("EXEC_BUDGET_EXCEEDED", order_id=order.order_id,
                            elapsed_ms=round(elapsed_ms, 3),
                            budget_ms=self._cfg.dispatch_budget_ms)

        for fragment in fragment_plan.fragments:
            reports.extend(await self._dispatch(order, fragment, fragment_plan))
        filled = sum((r.filled_units for r in reports), Decimal("0"))
        if filled > order.size_units:   # GAP-0079 pattern: alive under -O
            raise DataQualityError("filled_units", str(filled),
                                   "C-EXE-6 violated: filled > sized")
        return tuple(reports)

    # -- internals --------------------------------------------------------------- #

    def _capable_venues(self, order: SizedOrder, total_lots: float,
                        *, need_ioc: bool) -> list[str]:
        """Venues whose descriptor covers this order, best quality first.
        A missing capability excludes the venue — never silent emulation."""
        capable = []
        for name, face in self._faces.items():
            d = face.descriptor
            if order.instrument not in d.symbol_map:
                continue
            if total_lots > d.max_order_lots:
                continue
            if need_ioc and not d.supports_ioc:
                continue
            capable.append(name)
        capable.sort(key=lambda n: self._quality.score(n, order.instrument),
                     reverse=True)
        return capable

    async def _dispatch(self, order: SizedOrder, fragment: Fragment,
                        fragment_plan: FragmentPlan) -> list[FillReport]:
        delay = (fragment.scheduled_at - self._now()).total_seconds()
        if delay > 0:
            await self._sleep(delay)
        reports: list[FillReport] = []
        venue = fragment.venue
        fragment_id = fragment.fragment_id
        units = fragment.units
        reroutes = 0
        retries = 0
        while True:
            units, boundary = self._venue_quantity(order, units, venue, fragment_id)
            reports.extend(boundary)
            if units == 0:
                return reports
            report = await self._submit_once(order, fragment_id, venue, units,
                                             fragment_plan.path == "ioc")
            if report is None:                        # gave up mid-reconcile
                report = self._synthetic_reject(order, "venue_unreachable",
                                                fragment_id=fragment_id, venue=venue)
                self._record(report)
                reports.append(report)
                return reports
            self._record(report)
            reports.append(report)
            if report.status is FillStatus.REJECTED:
                nxt = [v for v in self._capable_venues(
                    order, float(units / UNITS_PER_LOT),
                    need_ioc=fragment_plan.path == "ioc") if v != venue]
                if reroutes < MAX_REROUTES and nxt:
                    reroutes += 1
                    venue = nxt[0]
                    fragment_id = f"{fragment.fragment_id}:x{reroutes}"
                    self._log.event("EXEC_REROUTE", order_id=order.order_id,
                                    fragment_id=fragment_id, venue=venue)
                    continue
                self._log.event("EXEC_REJECT_GIVEUP", order_id=order.order_id,
                                fragment_id=fragment_id)
                return reports
            if report.status is FillStatus.PARTIAL and report.remaining_units > 0:
                if retries < MAX_REMAINDER_RETRIES:
                    retries += 1
                    units = report.remaining_units    # never exceeds parent
                    fragment_id = f"{fragment.fragment_id}:p{retries}"
                    continue
                self._log.event("EXEC_PARTIAL_GIVEUP", order_id=order.order_id,
                                fragment_id=fragment_id,
                                remaining=str(report.remaining_units))
                return reports
            return reports

    async def _submit_once(self, order: SizedOrder, fragment_id: str, venue: str,
                           units: Decimal, ioc: bool) -> FillReport | None:
        """One venue hit with the §7-step-7 reconnect rule: on ConnectionError,
        reconcile against the broker (authoritative) BEFORE any resubmission;
        idempotent fragment_ids make the retry double-fill-safe. Two failures
        ⇒ give up (None)."""
        face, budget = self._faces[venue], self._requests[venue]
        for attempt in (1, 2):
            now = self._now()
            derisk = (order.action == "close" and budget.used(now) >= budget.limit
                      and await self._shrinks(face, order, units))       # no read for opens
            if not budget.admit(now, closing=derisk, order_id=order.order_id, log=self._log):
                return self._synthetic_reject(order, "request_budget", units=units,
                                              fragment_id=f"{fragment_id}:budget")
            try:
                return await face.submit_order(
                    fragment_id=fragment_id, order_id=order.order_id,
                    instrument=order.instrument, direction=order.direction,
                    units=units, requested_price=order.entry_price,
                    ioc=ioc, now=self._now(), session_id=self._session)
            except ConnectionError:
                positions = await face.open_positions()
                self._log.event(
                    "EXEC_RECONCILE", venue=venue, fragment_id=fragment_id,
                    attempt=attempt, broker_positions=[
                        {"instrument": p.instrument, "direction": p.direction,
                         "units": str(p.size_units)} for p in positions])
                if attempt == 2:
                    return None

    @staticmethod
    async def _shrinks(face: ExecutionFace, order: SizedOrder, units: Decimal) -> bool:
        """A spent budget exempts only a close that really shrinks the venue position:
        the `close` label is no proof while the close-direction contract is open."""
        held = [p for p in await face.open_positions() if p.instrument == order.instrument]
        return (len(held) == 1 and held[0].direction == -order.direction
                and units <= held[0].size_units)

    def _venue_quantity(self, order: SizedOrder, units: Decimal, venue: str,
                        tag: str) -> tuple[Decimal, list[FillReport]]:
        """GAP-P12D-57: `units` rounded DOWN to `venue`'s lot step, or 0 if that falls
        below its minimum lot. What is not sent is recorded as a REJECTED report."""
        sendable, rest = venue_quantity(units, self._faces[venue].descriptor)
        if rest == 0:
            return sendable, []
        kind = "EXEC_MIN_LOT_REFUSED" if sendable == 0 else "EXEC_LOT_STEP_ROUNDED"
        self._log.event(kind, order_id=order.order_id, venue=venue, action=order.action,
                        units=str(units), sent=str(sendable), unsent=str(rest))
        report = self._synthetic_reject(order, kind, units=rest,
                                        fragment_id=f"{tag}:{'minlot' if sendable == 0 else 'step'}")
        self._record(report)
        return sendable, [report]

    def _record(self, report: FillReport) -> None:
        self._quality.update(report)
        self._store.write(report)
        event = {FillStatus.FILLED: "FILL", FillStatus.PARTIAL: "PARTIAL",
                 FillStatus.REJECTED: "REJECT",
                 FillStatus.CANCELLED: "CANCEL"}[report.status]
        self._log.event(event, fill_id=report.fill_id, order_id=report.order_id,
                        fragment_id=report.fragment_id, venue=report.venue,
                        filled_units=str(report.filled_units),
                        fill_px=report.fill_price,
                        slippage_bps=round(report.slippage_bps, 4),
                        remaining=str(report.remaining_units))
        if (report.status in (FillStatus.FILLED, FillStatus.PARTIAL)
                and report.slippage_bps > self._alert_bps):
            self._log.event("SLIPPAGE_ALERT", fill_id=report.fill_id,
                            instrument=report.instrument,
                            slippage_bps=round(report.slippage_bps, 4),
                            alert_bps=self._alert_bps)

    def _synthetic_reject(self, order: SizedOrder, reason: str, *, fragment_id: str = "",
                          venue: str = "none", units: Decimal | None = None) -> FillReport:
        """A boundary rejection is still a FillReport — never a silent drop (§4);
        `units` is what went unsent (default: the whole order)."""
        return FillReport(
            fill_id=f"{order.order_id}:{fragment_id or 'cap'}:rej",
            order_id=order.order_id, fragment_id=fragment_id or "none",
            instrument=order.instrument, direction=order.direction,
            requested_price=order.entry_price, fill_price=0.0,
            filled_units=Decimal("0"), slippage_bps=0.0, fill_time=self._now(),
            venue=venue, status=FillStatus.REJECTED,
            remaining_units=order.size_units if units is None else units,
            session_id=self._session)
