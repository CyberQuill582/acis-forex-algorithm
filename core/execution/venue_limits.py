"""A venue's quantity and request limits, enforced in the execution path (GAP-P12D-57).
Master §7.5: an order needing a capability the venue lacks is refused, never emulated.

Invariants:
  * A quantity reaches a venue only as a whole number of its `lot_step`, rounded DOWN.
    Execution never rounds up: that would add size the Governor did not size (it only
    ever clamps downward). The unsendable remainder is reported, never dropped.
  * A quantity below the venue's `min_lot` is refused with a REJECTED FillReport.
  * Each venue has a hard budget of trading requests (every submit attempt) over ANY
    rolling 24 hours, which is stricter than a firm's "per day" cap whatever its day
    boundary. Once spent, opens are refused; a close is never blocked (de-risking is
    never throttled) and every such exception is logged.
  * A restart does not reset the budget: it is seeded from the persisted fill log.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Iterable

from core.execution.venue import UNITS_PER_LOT, CapabilityDescriptor

WINDOW = timedelta(hours=24)


def lot_units(lots: float) -> Decimal:
    return Decimal(str(lots)) * UNITS_PER_LOT


def venue_quantity(units: Decimal, d: CapabilityDescriptor) -> tuple[Decimal, Decimal]:
    """(sendable, remainder): `units` rounded DOWN to whole lot steps. The sendable part
    is 0 when it would fall below the venue's minimum lot — the whole quantity is refused."""
    step = lot_units(d.lot_step)
    sendable = (units / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if sendable < lot_units(d.min_lot):
        return Decimal("0"), units
    return sendable, units - sendable


class RequestBudget:
    """One venue's trading-request budget over a rolling 24-hour window."""

    def __init__(self, venue: str, limit: int, seed: Iterable[datetime] = ()) -> None:
        self.venue = venue
        self.limit = limit
        self._stamps: deque[datetime] = deque(sorted(seed))

    def used(self, now: datetime) -> int:
        while self._stamps and self._stamps[0] <= now - WINDOW:
            self._stamps.popleft()
        return len(self._stamps)

    def admit(self, now: datetime, *, closing: bool, order_id: str, log) -> bool:
        """Count one request. False means refuse it: an open, with the budget spent."""
        used = self.used(now)
        if used >= self.limit:
            event = "EXEC_REQUEST_BUDGET_DERISK" if closing else "EXEC_REQUEST_BUDGET_REFUSED"
            log.event(event, venue=self.venue, order_id=order_id, used=used, limit=self.limit)
            if not closing:
                return False
        self._stamps.append(now)
        return True
