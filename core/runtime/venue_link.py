"""The attached venue, as the runtime holds it (ACIS-13 §7.5, §6.5): its execution face, its
orchestrator, the budgeted account poll and the periodic reconciliation.

Invariants:
  * The account is polled every `equity_poll_s`, the cadence ACIS-13 §6.5's feasibility check
    budgets (two requests a poll). Risk's other evaluations read the last poll, so equity may
    lag by up to one poll interval (declared, GAP-0091b); a failed poll keeps the old account,
    whose age makes the Governor's portfolio stale and zeroes entries.
  * Every `reconcile_interval_s`, with nothing in flight, venue positions are compared with
    Risk's. Venue truth wins: any drift is adopted and halts everything for a human (the
    restart rule, ACIS-07 C-RSK-5), because a drift no fill explains is never benign.
  * A lost link comes back through the reconnector (ACIS-13 §6.6, GAP-0020); if the account
    detaches, the reconnector ends, and the runtime treats that as a stalled loop.
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
                 logger, reconnector=None) -> None:
        self.face, self.orchestrator, self.attached = face, orchestrator, attached
        self.reconnector = reconnector            # ACIS-13 §6.6 (GAP-0020); its end is a stall
        self._poll_s, self._reconcile_s, self._now, self._log = poll_s, reconcile_s, now_fn, logger
        self.account: BrokerAccount | None = None
        self.account_at: datetime | None = None

    @property
    def practice_eligible(self) -> bool:
        return self.attached.report.practice_eligible

    def min_units(self, instrument: str):
        spec = self.attached.specs.get(instrument)
        return spec.min_units if spec is not None else None

    async def poll_once(self) -> None:
        try:
            self.account, self.account_at = await self.face.account_snapshot(), self._now()
        except Exception as exc:                  # the old account ages; entries go stale
            self._log.event("ACCOUNT_POLL_FAILED", error=repr(exc))

    async def poll(self) -> None:
        while True:
            await asyncio.sleep(self._poll_s)
            await self.poll_once()

    async def reconcile(self, risk, executor) -> None:
        while True:
            await asyncio.sleep(self._reconcile_s)
            if executor.busy or not executor.queue.empty():
                continue                          # a fill in flight is not a drift
            try:
                broker = await self.face.open_positions()
            except Exception as exc:
                self._log.event("RECONCILE_FAILED", error=repr(exc))
                continue
            self._log.event("RECONCILE", venue_positions=len(broker))
            risk.reconcile_on_restart(broker, self._now())     # drift ⇒ adopt + halt all
