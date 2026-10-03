"""A close-to-close book over several index CFDs, each traded at its own cash close (FACTORY 2026-10-04,
GAP-P12D-158): `event_daily.simulate_daily` generalised from US500 to every explored home exchange.

Mental model:
  * SESSIONS of an index are the weekdays (in its exchange's own date) with an ANCHOR: the close mid of
    the last quoted hour ending by the cash close and starting inside the session (`event_sim.Leg`).
    A QUOTED hour traded or moved (`event_daily.quoted`, owner ruling 2026-10-03, GAP-P12D-156). The
    CFDs trade through some exchange holidays, so such a day counts as a session (declared); a feed
    hole is not a session, and the next anchor books the move.
  * TARGET[s] is the fraction of capital held from session s's anchor to session s+1's. Each change
    pays THE C8 model's `per_side_cost` at the anchor hour's spread; swap-free (R1-D9): no financing.
    Before `graded_from` the book is flat; the signal may read earlier sessions.
  * Each session's P&L lands on the 17:00 New York mark of its own date (`event_sim.marks`); every home
    close is earlier than that mark, so the vector is RSIM's kind and reads nothing late.
  * `trailing_vol(r)[s]` is the sample sd of the VOL_SESSIONS returns ending at s (None before half of
    them exist): equal-risk sizing reads nothing after the session it sizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.event_daily import quoted
from tests.backtest.event_sim import HOME, EventResult, Leg, marks

VOL_SESSIONS, LEG_RISK = 60, 0.01


@dataclass(frozen=True)
class Sessions:
    name: str
    exchange: str
    days: tuple[date, ...]
    closes: np.ndarray               # the anchor's close mid
    spreads: np.ndarray              # the anchor hour's open spread

    @property
    def returns(self) -> np.ndarray:
        """Log return from the previous anchor; NaN at the first session."""
        return np.concatenate([[np.nan], np.diff(np.log(self.closes))])


def sessions(h: Hourly, name: str, start: date, end: date) -> Sessions:
    exchange, leg = HOME[name], Leg(quoted(h), np.zeros(1, np.int64))
    days, js, d = [], [], start
    while d <= end:
        if d.weekday() < 5 and (j := leg.anchor(exchange, d)) is not None:
            days.append(d)
            js.append(j)
        d += timedelta(days=1)
    idx = np.asarray(js, np.int64)
    return Sessions(name, exchange, tuple(days), leg.closes[idx].astype(float), leg.spreads[idx].astype(float))


def trailing_vol(r: np.ndarray) -> np.ndarray:
    out = np.full(len(r), np.nan)
    for s in range(len(r)):
        past = r[max(0, s - VOL_SESSIONS + 1):s + 1]
        past = past[np.isfinite(past)]
        if len(past) >= VOL_SESSIONS // 2:
            out[s] = float(np.std(past, ddof=1))
    return out


def book(legs: Mapping[str, Sessions], targets: Mapping[str, np.ndarray], costs: Mapping[str, CostModel] | None,
         start: date, graded_from: date, end: date) -> EventResult:
    """`costs` None prices nothing (the passive benchmark); a NaN target holds flat."""
    grid = marks(start, end)
    at = {d: k for k, (d, _) in enumerate(grid)}
    daily = np.zeros(len(grid))
    for name in sorted(legs):
        s, target, held = legs[name], np.nan_to_num(np.asarray(targets[name], float)), 0.0
        for k, d in enumerate(s.days):
            if not start <= d <= end:
                continue
            p = float(s.closes[k])
            if k and held:
                daily[at[d]] += held * (p / float(s.closes[k - 1]) - 1.0)
            new = float(target[k]) if d >= graded_from else 0.0
            if costs is not None and new != held:
                daily[at[d]] -= abs(new - held) * costs[name].per_side_cost(float(s.spreads[k])) / p
            held = new
    return EventResult(tuple(d for d, _ in grid), daily, (), ())


def passive_targets(legs: Mapping[str, Sessions]) -> dict[str, np.ndarray]:
    """Every index long at LEG_RISK over its trailing vol: the PASSIVE_LONG context arm."""
    return {n: LEG_RISK / trailing_vol(s.returns) for n, s in legs.items()}
