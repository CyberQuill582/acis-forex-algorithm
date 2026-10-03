"""A conservative passive-first fill model: what a resting limit order saves against a market order.

Mental model:
  * QUOTES are time-ordered (t, bid, ask, ask_low, bid_high) rows. A tick is its own low and high; a
    1-minute candle row is stamped at the minute's END with its closes and its extremes. The quote at T
    is the last row at or before T, if it is at most STALE_S old.
  * A buy (side +1) arriving at t0 rests a limit at the bid ("touch") or the mid, on the venue's tick
    grid and rounded away from the market. It FILLS at its limit, never better, at the first row in
    (t0, t0 + window] whose ask_low is `through` ticks or more BELOW the limit. cTrader fills a buy
    limit when the ASK reaches it, so through = 0 is the venue's rule and 1 the conservative proxy.
    A sell mirrors it on the bid. A CFD limit never joins a queue: it cannot earn the spread.
  * Unfilled at the deadline, it falls back to a MARKET order there. "chase" (Carver's rule) crosses as
    soon as the near quote moves away; the "delay" control rests nothing: the deadline's market order alone.
  * SAVING (bp of the arrival mid) = side x (market price - price paid) = the P&L gap at any common
    mark after the deadline. The market price is the arrival quote's (an entry decided at t0) or the
    deadline's (an exit due at the deadline that starts resting a window early).
  * DRIFT after execution (bp, signed by side) is the adverse-selection read: negative means the
    market kept moving against the order once it filled.
  * Every arrival is run as a buy AND a sell, so a summary reads no signal (direction-blind).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

STALE_S = 300
LEVELS = ("touch", "chase", "mid", "delay")


@dataclass(frozen=True)
class Quotes:
    t: np.ndarray          # epoch ms, non-decreasing
    bid: np.ndarray
    ask: np.ndarray
    ask_low: np.ndarray    # the lowest ask in the row (a tick: its ask)
    bid_high: np.ndarray   # the highest bid in the row (a tick: its bid)

    @classmethod
    def from_ticks(cls, t: np.ndarray, bid: np.ndarray, ask: np.ndarray) -> "Quotes":
        return cls(np.asarray(t, "i8"), np.asarray(bid, float), np.asarray(ask, float),
                   np.asarray(ask, float), np.asarray(bid, float))

    def at(self, ms: int) -> int | None:
        k = int(np.searchsorted(self.t, ms, side="right")) - 1
        return k if k >= 0 and ms - self.t[k] <= STALE_S * 1000 else None


@dataclass(frozen=True)
class Policy:
    level: str             # "touch", "chase", "mid" or "delay"
    window_s: int
    through: int = 1       # ticks the opposite quote must pass the limit by
    react_ms: int = 0      # chase only: the round trip before its market order lands (the demo's is ~0.3-0.55 s)

    def __post_init__(self) -> None:
        if self.level not in LEVELS or self.window_s <= 0 or self.through < 0 or self.react_ms < 0:
            raise ValueError(f"bad policy {self}")


@dataclass(frozen=True)
class Outcome:
    filled: bool
    wait_s: float
    saving_bp: float
    arrival_spread_bp: float
    drift_bp: tuple[float, ...]    # per horizon; NaN when no quote
    arrival_mid: float = math.nan


def limit_price(bid: float, ask: float, side: int, level: str, tick: float) -> float:
    """The resting price: the near touch, or the mid rounded onto the tick grid away from the market."""
    if level in ("touch", "chase"):
        return bid if side > 0 else ask
    n = (bid + ask) / 2 / tick
    return (math.floor(n + 1e-6) if side > 0 else math.ceil(n - 1e-6)) * tick


def simulate(q: Quotes, rest_ms: int, side: int, policy: Policy, tick: float, benchmark: str = "arrival",
             horizons_s: Sequence[int] = (60, 300, 1800)) -> Outcome | None:
    """One order resting from `rest_ms` for `policy.window_s`; None if the arrival or deadline is unquoted."""
    end_ms = rest_ms + policy.window_s * 1000
    a, d = q.at(rest_ms), q.at(end_ms)
    if a is None or d is None or benchmark not in ("arrival", "deadline"):
        return None
    bid0, ask0 = float(q.bid[a]), float(q.ask[a])
    mid0 = (bid0 + ask0) / 2
    limit = limit_price(bid0, ask0, side, policy.level, tick)
    lo, hi = a + 1, int(np.searchsorted(q.t, end_ms, side="right"))
    eps = tick * 1e-3
    if policy.level == "delay":
        hit = np.zeros(0, bool)
    elif side > 0:
        hit = q.ask_low[lo:hi] <= limit - policy.through * tick + eps
    else:
        hit = q.bid_high[lo:hi] >= limit + policy.through * tick - eps
    k_fill = lo + int(np.argmax(hit)) if hit.any() else None
    k_away = None
    if policy.level == "chase":                    # the near quote moved away; a tie in one row counts as away
        away = q.bid_high[lo:hi] > bid0 + eps if side > 0 else q.ask_low[lo:hi] < ask0 - eps
        k_away = lo + int(np.argmax(away)) if away.any() else None
    filled = k_fill is not None and (k_away is None or k_fill < k_away)
    if filled:
        paid, exec_ms, exec_row = limit, int(q.t[k_fill]), k_fill
    elif k_away is None:
        exec_row, exec_ms = d, end_ms
    else:                                          # the chase lands `react_ms` late, at that moment's quote
        exec_ms = int(q.t[k_away]) + policy.react_ms
        j = q.at(exec_ms)
        exec_row = k_away if j is None else j
    if not filled:
        paid = float(q.ask[exec_row] if side > 0 else q.bid[exec_row])
    ref = a if benchmark == "arrival" else d
    market = float(q.ask[ref] if side > 0 else q.bid[ref])
    mid_exec = (q.bid[exec_row] + q.ask[exec_row]) / 2
    drift = []
    for h in horizons_s:
        j = q.at(exec_ms + h * 1000)
        drift.append(float(side * ((q.bid[j] + q.ask[j]) / 2 - mid_exec) / mid0 * 1e4) if j is not None else math.nan)
    return Outcome(filled, (exec_ms - rest_ms) / 1000, side * (market - paid) / mid0 * 1e4,
                   (ask0 - bid0) / mid0 * 1e4, tuple(drift), mid0)


@dataclass(frozen=True)
class Summary:
    days: int
    fill_rate: float
    saving_bp: float          # mean over days of the day's buy-and-sell mean
    saving_se: float          # standard error across days
    wait_s: float             # mean time to fill or deadline
    fill_drift_bp: tuple[float, ...]   # mean drift after FILLED orders, per horizon
    spread_bp: float          # median arrival spread


def summarise(per_day: Iterable[Sequence[Outcome]]) -> Summary | None:
    """`per_day`: each day's outcomes (its buy and its sell); days are the independent unit."""
    days = [list(o) for o in per_day if o]
    if not days:
        return None
    flat = [o for day in days for o in day]
    daily = np.array([np.mean([o.saving_bp for o in day]) for day in days])
    se = float(daily.std(ddof=1) / math.sqrt(len(daily))) if len(daily) > 1 else math.nan
    fills = [o for o in flat if o.filled]
    drift = tuple(float(np.nanmean([o.drift_bp[i] for o in fills])) if fills else math.nan
                  for i in range(len(flat[0].drift_bp)))
    return Summary(len(days), len(fills) / len(flat), float(daily.mean()), se,
                   float(np.mean([o.wait_s for o in flat])), drift,
                   float(np.median([o.arrival_spread_bp for o in flat])))
