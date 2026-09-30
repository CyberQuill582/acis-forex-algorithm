"""The attached venue, as the runtime holds it (ACIS-13 §7.5, §6.5, §6.6, §6.7; GAP-P12D-132).

Invariants:
  * The account is polled every `equity_poll_s`, the cadence ACIS-13 §6.5's feasibility check
    budgets (two requests a poll). Risk's other evaluations read the last poll, so equity may
    lag by up to one poll interval (declared, GAP-P12D-131 a); a failed poll keeps the old
    account, whose age makes the Governor's portfolio stale and zeroes entries.
  * Every `reconcile_interval_s`, in PRACTICE only (paper's Risk describes the paper venue, not
    this account: TAI-06), with nothing in flight and the budget outside its close reserve (the
    reserve is kept for closes: TAI-01), venue positions are compared with Risk's. Venue truth
    wins: a drift is adopted and halts everything for a human (ACIS-07 C-RSK-5). An ACIS position
    the venue shows WITHOUT a stop is flattened over the edge (C-VEN-2, TAI-04). The token is
    refreshed there, at that quiet moment (§6.7, TAI-17).
  * At a restart, Risk is built from venue truth, so the fills SYNCING recovered from the downtime
    are already in it and are discarded, never replayed on top (A7, TAI-05); mid-run reconnects
    keep them, because there Risk still holds its book.
  * A lost link comes back through the reconnector (§6.6, GAP-0020). The reconnector and the face's
    event consumer are the runtime's to supervise: either ending is a stalled loop (TAE-08).
  * Nothing here sends an order. Orders reach the venue only through the executor.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable

from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import BrokerAccount, ExecutionFace


class VenueLink:
    def __init__(self, *, face: ExecutionFace, orchestrator: ExecutionOrchestrator, attached,
                 poll_s: float, reconcile_s: float, now_fn: Callable[[], datetime],
                 logger, session=None, events: asyncio.Task | None = None, reconnector=None) -> None:
        self.face, self.orchestrator, self.attached = face, orchestrator, attached
        self.session, self.events, self.reconnector = session, events, reconnector
        self._poll_s, self._reconcile_s, self._now, self._log = poll_s, reconcile_s, now_fn, logger
        self.account: BrokerAccount | None = None
        self.account_at: datetime | None = None

    @property
    def practice_eligible(self) -> bool:
        return self.attached.report.practice_eligible

    def min_units(self, instrument: str):
        spec = self.attached.specs.get(instrument)
        return spec.min_units if spec is not None else None

    def discard_recovered(self) -> int:
        """At a restart: the SYNCING reports venue truth already reflects (TAI-05)."""
        queue = getattr(getattr(self.face, "router", None), "unsolicited", None)
        n = 0
        while queue is not None and not queue.empty():
            report = queue.get_nowait()
            n += 1
            self._log.event("BOOT_FILL_IN_VENUE_TRUTH", fill_id=report.fill_id, instrument=report.instrument)
        return n

    async def watch_events(self) -> None:
        if self.events is not None:
            await self.events                         # its end, clean or not, is a stall

    async def poll_once(self) -> None:
        try:
            self.account, self.account_at = await self.face.account_snapshot(), self._now()
        except Exception as exc:                  # the old account ages; entries go stale
            self._log.event("ACCOUNT_POLL_FAILED", error=repr(exc))

    async def poll(self) -> None:
        while True:
            await asyncio.sleep(self._poll_s)
            await self.poll_once()

    def _in_reserve(self) -> bool:
        if self.session is None:
            return False
        b = self.session.budget()
        return b["used_24h"] >= b["cap"] - b["close_reserve"]

    async def reconcile(self, risk, executor, *, active: Callable[[], bool],
                        flatten: Callable[[str, str], None]) -> None:
        while True:
            await asyncio.sleep(self._reconcile_s)
            if not active() or executor.busy or not executor.queue.empty() or self._in_reserve():
                continue                          # paper, a fill in flight, or the close reserve
            try:
                if self.session is not None:
                    await self.session.refresh_if_due()
                broker = await self.face.open_positions()
            except Exception as exc:
                self._log.event("RECONCILE_FAILED", error=repr(exc))
                continue
            self._log.event("RECONCILE", venue_positions=len(broker))
            for p in broker:
                if p.stop_loss is None:
                    self._log.event("VENUE_STOP_MISSING", instrument=p.instrument, severity="critical")
                    flatten(p.instrument, "venue_stop_missing")
            risk.reconcile_on_restart(broker, self._now())     # drift ⇒ adopt + halt all
