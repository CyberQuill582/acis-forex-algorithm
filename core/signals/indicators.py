"""Shared TA for AGON (ACIS-04 §3) — NaN-safe, stdlib, deterministic.

v2.11 time base: AGON indicators run on completed OHLC BARS (core/data/bars.py),
never bare tick deques. `wilder_atr` is REAL true-range ATR (reusing the
phase-4-tested fitness.atr_series); `adx_proxy` is the regime layer's
close-only directional proxy, consumed here ONLY as the trend-conviction
score and named for what it is (declared deviation, ACIS-04 §6.1).
"""

from __future__ import annotations

import math
import operator
from typing import Sequence

from core.data.bars import Bar
from core.optimizer.fitness import atr_series, ema_series, rsi_series  # noqa: F401
from core.regime.nvma import adx_proxy  # noqa: F401  (re-exported, proxy by name)


def wilder_atr(bars: Sequence[Bar], period: int) -> float:
    """True-range ATR over completed bars (Wilder smoothing). NaN if unwarmed."""
    if len(bars) <= period:
        return float("nan")
    value = atr_series(bars, period)[-1]
    return value if value > 0 else float("nan")


class AtrMemo:
    """`wilder_atr` memoised on the exact bar sequence (GAP-P12D-15).

    Invariant: a cached value is returned only when the window holds the very same Bar
    objects, in the same order, as the call that computed it. Bars are frozen and
    `wilder_atr` is pure, so the memo can never change a result; it only skips the
    recomputation. Signal-bar ATR changes only when a bar completes, so every call
    between two bars is a hit. The key only groups windows: a wrong key costs a
    recomputation, never a wrong value.
    """

    def __init__(self, period: int) -> None:
        self.period = period
        self._cache: dict[str, tuple[tuple[Bar, ...], float]] = {}

    def __call__(self, key: str, bars: Sequence[Bar]) -> float:
        hit = self._cache.get(key)
        if (hit is not None and bars and len(hit[0]) == len(bars) and hit[0][-1] is bars[-1]
                and all(map(operator.is_, hit[0], bars))):
            return hit[1]
        value = wilder_atr(bars, self.period)
        self._cache[key] = (tuple(bars), value)
        return value


def bollinger_z(mids: Sequence[float], window: int = 20) -> float:
    """Z-score of the last mid against the trailing window. NaN if unwarmed/flat."""
    if len(mids) < window:
        return float("nan")
    tail = list(mids[-window:])
    mean = sum(tail) / window
    var = sum((m - mean) ** 2 for m in tail) / window
    if var == 0.0:
        return float("nan")
    return (tail[-1] - mean) / math.sqrt(var)


def log_returns(series: Sequence[float]) -> list[float]:
    out = []
    for a, b in zip(series, list(series)[1:]):
        if a <= 0 or b <= 0:
            return []
        out.append(math.log(b / a))
    return out


def rolling_correlation(a: Sequence[float], b: Sequence[float], window: int) -> float:
    """Pearson correlation of log returns over the trailing window (§5.5:
    method = pearson_log_returns). NaN if unwarmed or degenerate."""
    if len(a) < window + 1 or len(b) < window + 1:
        return float("nan")
    ra = log_returns(list(a)[-(window + 1):])
    rb = log_returns(list(b)[-(window + 1):])
    if len(ra) != window or len(rb) != window:
        return float("nan")
    ma, mb = sum(ra) / window, sum(rb) / window
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / window
    va = sum((x - ma) ** 2 for x in ra) / window
    vb = sum((y - mb) ** 2 for y in rb) / window
    if va == 0.0 or vb == 0.0:
        return float("nan")
    return cov / math.sqrt(va * vb)


def pair_spread_z(
    a: Sequence[float], b: Sequence[float], expected_sign: int, window: int
) -> float:
    """Z-score of the pair spread s = log(A) - expected_sign*log(B) over the
    trailing window. NaN if unwarmed, non-positive prices, or flat."""
    n = min(len(a), len(b))
    if n < window:
        return float("nan")
    sa, sb = list(a)[-window:], list(b)[-window:]
    if any(x <= 0 for x in sa) or any(x <= 0 for x in sb):
        return float("nan")
    spread = [math.log(x) - expected_sign * math.log(y) for x, y in zip(sa, sb)]
    mean = sum(spread) / window
    var = sum((s - mean) ** 2 for s in spread) / window
    if var == 0.0:
        return float("nan")
    return (spread[-1] - mean) / math.sqrt(var)


def clamp01(x: float) -> float:
    if math.isnan(x):
        return float("nan")  # NaN stays NaN — the caller's NaN guard must see it
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
