"""OPEX's position: US500 over the option-expiration week (GAP-P12D-158; Stivers & Sun, "Returns and option
activity over the option-expiration week for S&P 100 stocks", JBF 37(11) (2013); the S&P 500 index 1983-2008).

Mental model:
  * The OE WEEK is the Monday-to-Friday week holding the month's third Friday, the standard monthly
    expiration (a holiday Friday moves the expiration to Thursday; the week is the same).
  * The paper's weekly returns are close to close, so the book is long from the last S&P close BEFORE the
    OE week to the close of its last session. On the S&P's business days `days`, target[s] is the position
    held from close s to close s+1: 1 when session s+1 falls in an OE week, else `other`.
  * `other` is 0 for the plain book. For the CONTRAST it is minus (OE holds / other holds), counted on the
    calendar alone, never on a return: a drift that is the same every day nets to zero, so only an OE-week
    excess over the other weeks can earn.
  * The book is REBAL's (`event_daily.simulate_daily`): marks at the anchored US cash close, C8 costs on
    each change of units, swap-free. `segments` reports a result's annual Sharpe between pre-declared cuts.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import numpy as np

from tests.backtest.event_sim import EventResult
from tests.backtest.rsim import annual_sharpe


def third_friday(y: int, m: int) -> date:
    first = date(y, m, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def oe_week(d: date) -> bool:
    friday = third_friday(d.year, d.month)
    return friday - timedelta(days=4) <= d <= friday


def target(days: Sequence[date], contrast: bool = False) -> np.ndarray:
    into = np.array([oe_week(days[s + 1]) for s in range(len(days) - 1)] + [False])
    held = into[:-1]
    other = -held.sum() / (~held).sum() if contrast else 0.0
    out = np.where(into, 1.0, other)
    out[-1] = 0.0                                   # the last close holds nothing: no next session
    return out


def segments(r: EventResult, cuts: Sequence[date], graded_from: date) -> dict[str, float | None]:
    """The annual Sharpe of `r.daily` on [graded_from, cut1), [cut1, cut2), ... , [last cut, end]."""
    days, edges, out = np.array(r.days), [graded_from, *cuts, None], {}
    for a, b in zip(edges[:-1], edges[1:]):
        m = (days >= a) & (days < b) if b else days >= a
        out[f"{a.isoformat()}..{(b - timedelta(days=1)).isoformat() if b else 'end'}"] = (
            annual_sharpe(r.daily[m]) if m.sum() > 1 else None)
    return out
