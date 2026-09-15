"""Equity marked at the FX day boundary, for the date-joined SPX correlation (GAP-SP12E-06).

Invariant: one mark per 17:00-New-York rollover that the replay crosses, labelled with its
New York date and carrying the equity of the LAST tick before the rollover. The rollover
instant follows US daylight time (`core/data/fx_clock.py`). A weekend yields only
Friday's mark: the first tick after the weekend crosses Friday's rollover, and the next
boundary is then computed from that tick, so Sunday's re-open is not a trading-day mark.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from core.data.fx_clock import ROLLOVER, next_local, to_local


class RolloverMarker:
    def __init__(self) -> None:
        self.marks: list[tuple[date, Decimal]] = []
        self._next: datetime | None = None
        self._last: Decimal | None = None

    def observe(self, ts: datetime, equity: Decimal) -> bool:
        """Call once per tick, after the tick's equity is known. True when this tick is the
        first of a new FX trading day (it crossed a rollover)."""
        crossed = False
        if self._next is not None and ts >= self._next:
            if self._last is not None:
                self.marks.append((to_local(self._next, ROLLOVER[0]).date(), self._last))
            self._next = None
            crossed = True
        if self._next is None:
            self._next = next_local(ts, ROLLOVER[0], ROLLOVER[1])
        self._last = equity
        return crossed
