"""Execution Orchestrator (ACIS-06 v1.1, master §7). How and where — never
how much.

Hard walls: never sends more than `size_units` (C-EXE-6); never opens what the
Governor sized to zero; the execution-freeze (Risk flatten path, phase 9) blocks
opens while allowing reduce-only closes; slippage is REPORTED, never acted on (F10:
no throttle knob). Randomness and time are injected. `dispatch_budget_ms` is
observability only (v2.10 item c). The venue's own limits DO gate (GAP-P12D-57,
venue_limits.py): whole lot steps rounded DOWN, below the minimum lot refused, a spent
request budget refuses opens. A close is REDUCE-ONLY (GAP-0040 exits, ACIS-06 §7): it
names its position's side, trades the opposite side, and is capped at — or refused
without — the venue's holding on that side. Every refusal of an order that reaches
dispatch is a FillReport; a frozen OPEN is refused before dispatch, logged only (F12).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncIterator

from config.schemas import ExecutionConfig
from core.data.errors import DataQualityError
from core.execution.boundary import paced_at, quantity_at, reduce_only_at, side
from core.execution.close_pacing import ClosePacer
from core.execution.fragmenter import Fragment, FragmentPlan, plan
from core.execution.reports import ReportBook
from core.execution.venue import (ExecutionFace, FillReport, FillReportStore, FillStatus,
                                  UNITS_PER_LOT)
from core.execution.venue_quality import VenueQuality
from core.execution.venue_limits import (WINDOW, RequestBudget, capable_venues, lot_units,
                                         venue_quantity)
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
        self._rng = rng
        self._log = logger
        self._session = session_id
        self._now = now_fn
        if sleep_fn is None:
            import asyncio
            sleep_fn = asyncio.sleep
        self._sleep = sleep_fn
        self._reports = ReportBook(quality, store, logger, slippage_alert_bps, session_id,
                                   now_fn)
        self._frozen: str | None = None
        self.budget_exceeded_count = 0      # §10 loop-health surface
        since = self._now() - WINDOW        # a restart re-seeds, never resets (GAP-P12D-57)
        self._requests = {name: RequestBudget(name, cfg.max_venue_requests_per_day,
                                              store.request_times(name, since))
                          for name in faces}
        self._pacer = ClosePacer(store, self._now())   # re-read at boot, like the budget

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
        Returns every FillReport (fills, partials, rejects) — Risk's input. An OPEN
        pair leg is refused here: a pair opens only through `submit_group`."""
        if order.group_id is not None and order.action == "open" and order.size_units > 0:
            self._log.event("EXEC_GROUP_LEG_ALONE", order_id=order.order_id,
                            group_id=order.group_id)
            report = self._reports.reject(order, side(order), fragment_id="group")
            self._reports.record(report)
            return (report,)
        return await self._submit(order, valid_for_seconds)

    async def submit_group(self, legs: tuple[SizedOrder, ...], *,
                           valid_for_seconds: int) -> tuple[FillReport, ...]:
        """§5.5 "both legs or neither", held in execution (audit F11): every open leg's
        quantity (lot step, minimum lot) and the request budget are checked FIRST; if any
        leg would be refused or round to zero, the WHOLE group is refused, nothing sent."""
        now = self._now()
        short = [leg.order_id for leg in legs if leg.action == "open"
                 and self._sendable(leg, valid_for_seconds, len(legs), now) == 0]
        if short:
            self._log.event("EXEC_GROUP_REFUSED", group_id=legs[0].group_id, legs=short)
            reports = tuple(self._reports.reject(leg, side(leg), fragment_id="group")
                            for leg in legs)
            for report in reports:
                self._reports.record(report)
            return reports
        out: list[FillReport] = []
        for leg in legs:
            out.extend(await self._submit(leg, valid_for_seconds))
        return tuple(out)

    async def venue_fills(self, venue: str) -> AsyncIterator[FillReport]:
        """ACIS-06 v1.4: `venue`'s unsolicited fills, each recorded once, yielded for Risk."""
        async for report in self._faces[venue].venue_fills():
            if self._reports.record_unsolicited(report):
                yield report

    def _sendable(self, leg: SizedOrder, valid_for_seconds: int, requests: int,
                  now: datetime) -> Decimal:
        """What a leg's planning venue would take, or 0 (no venue, below its minimum lot,
        or too little request budget left for the whole group)."""
        venues = capable_venues(self._faces, self._quality, leg,
                                float(leg.size_units / UNITS_PER_LOT),
                                need_ioc=valid_for_seconds < self._cfg.fast_decay_seconds)
        if not venues:
            return Decimal("0")
        budget = self._requests[venues[0]]
        if budget.used(now) + requests > budget.limit:
            return Decimal("0")
        return venue_quantity(leg.size_units, self._faces[venues[0]].descriptor)[0]

    async def _submit(self, order: SizedOrder,
                      valid_for_seconds: int) -> tuple[FillReport, ...]:
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
        venues = capable_venues(self._faces, self._quality, order, total_lots,
                                need_ioc=fast_decay)
        if not venues:
            self._log.event("EXEC_CAPABILITY_REJECT", order_id=order.order_id,
                            instrument=order.instrument, lots=total_lots,
                            ioc=fast_decay)
            report = self._reports.reject(order, side(order))
            self._reports.record(report)
            return (report,)

        units, reports = quantity_at(self._faces[venues[0]], venues[0], order, order.size_units,
                                     order.order_id, self._reports, self._log)
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
            if order.action == "close":               # paced, then reduce-only, at THIS venue
                refused = paced_at(self._pacer, venue, order, units, fragment_id,
                                   self._reports, self._log, self._now())
                if refused:
                    return reports + refused
                units, refused = await reduce_only_at(self._faces[venue], venue, order, units,
                                                      fragment_id, self._reports, self._log)
                reports.extend(refused)
                if units == 0:
                    return reports
            units, boundary = quantity_at(self._faces[venue], venue, order, units, fragment_id,
                                          self._reports, self._log)
            reports.extend(boundary)
            if units == 0:
                return reports
            report = await self._submit_once(order, fragment_id, venue, units,
                                             fragment_plan.path == "ioc")
            if order.action == "close":
                self._pacer.record(venue, order.instrument, self._now(),
                                   report is not None and report.filled_units > 0)
            if report is None:                        # gave up mid-reconcile
                report = self._reports.reject(order, side(order),
                                              fragment_id=fragment_id, venue=venue)
                self._reports.record(report)
                reports.append(report)
                return reports
            self._reports.record(report)
            reports.append(report)
            if report.status is FillStatus.REJECTED:
                nxt = [v for v in capable_venues(
                    self._faces, self._quality, order, float(units / UNITS_PER_LOT),
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
        for attempt in (1, 2):      # a close here was checked reduce-only at this venue
            if not budget.admit(self._now(), closing=order.action == "close",
                                order_id=order.order_id, log=self._log):
                return self._reports.reject(order, side(order), units=units,
                                            fragment_id=f"{fragment_id}:budget")
            common = dict(fragment_id=fragment_id, order_id=order.order_id,
                          instrument=order.instrument, units=units,
                          requested_price=order.entry_price, now=self._now(),
                          session_id=self._session)
            try:
                if order.action == "close":        # the venue's own atomic reduce (X3)
                    return await face.close_position(direction=order.direction, **common)
                # §279: an open rests the order's own stop at the venue (GAP-P12D-130)
                return await face.submit_order(direction=order.direction, ioc=ioc,
                                               stop_loss=order.stop_loss, **common)
            except ConnectionError:
                positions = await face.open_positions()
                self._log.event(
                    "EXEC_RECONCILE", venue=venue, fragment_id=fragment_id,
                    attempt=attempt, broker_positions=[
                        {"instrument": p.instrument, "direction": p.direction,
                         "units": str(p.size_units)} for p in positions])
                if attempt == 2:
                    return None
