"""Calendar gates the Governor applies (ACIS-05 §7 step 1; GAP-0053, GAP-P12D-10).

Moved unchanged out of capital_governor.py (module legibility, GAP-P12M-01). Invariants:
  * The weekend entry ban covers the buffer BEFORE the Friday close AND the whole closed
    window through the Sunday open — there is no post-close bypass. It binds EVERY
    account, weekend holding allowed or not (GAP-P12D-58: FTMO forbids opening a trade
    two hours or less before a market closes for two hours or more, on every account).
  * The weekend FLATTEN (master §9.5, no-weekend-holding accounts) starts with that same
    window, so no entry can open after it starts: every open position gets a reduce-only
    close naming it — its own side and size (the close convention, venue_limits.py).
  * Every time is the declared centre's local wall clock, so it follows DST.
  * The next boundary is the earliest declared session boundary strictly after `now`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from types import MappingProxyType
from typing import Sequence

from config.schemas import ZonedTime
from core.data.fx_clock import local_to_utc, next_local, to_local
from core.governor.portfolio_types import PortfolioState, SizedOrder


def within_weekend_buffer(now: datetime, week_close: ZonedTime, week_open: ZonedTime,
                          buffer_s: float) -> bool:
    local = to_local(now, week_close.zone)
    wd = local.weekday()
    if wd == 5:                                       # Saturday
        return True
    if wd == 6:                                       # Sunday, before the open
        return to_local(now, week_open.zone).strftime("%H:%M") < week_open.at
    if wd != 4:                                       # Mon–Thu
        return False
    gap = (local_to_utc(local.date(), week_close.at, week_close.zone) - now).total_seconds()
    return gap <= buffer_s                            # buffer window OR past close


def next_boundary(now: datetime, boundaries: Sequence[ZonedTime]) -> datetime:
    return min(next_local(now, b.zone, b.at) for b in boundaries)


def weekend_flatten_orders(portfolio: PortfolioState, now: datetime, week_close: ZonedTime,
                           week_open: ZonedTime, buffer_s: float) -> tuple[SizedOrder, ...]:
    """A close for every open position once the weekend window has begun, else ()."""
    if not within_weekend_buffer(now, week_close, week_open, buffer_s):
        return ()
    return tuple(SizedOrder(
        order_id=str(uuid.uuid4()), signal_id=f"weekend_flatten:{p.instrument}",
        instrument=p.instrument, direction=p.direction, size_units=p.size_units,
        entry_price=p.entry_price, stop_loss=p.stop_loss, take_profit=p.take_profit,
        reason="weekend_flatten", factors_snapshot=MappingProxyType({"weekend_flatten": True}),
        sized_at=now, param_set_id=p.param_set_id, group_id=p.group_id, action="close",
    ) for p in portfolio.open_positions)
