"""Marginal-alpha estimator + the exact GAP-0005 normalisation (ACIS-05 §6.1).

g(x), x = m/b: 0.25 for x <= 0 (anti-greed floor), 0.25 + 0.75x on (0,1)
(continuous ramp), 1.0 at neutral, min(1.5, 1 + 0.5(x-1)) above — capped at 1.5.
Cold start pins to 1.0 (F15): never guess an edge you cannot yet measure.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from core.data.errors import DataQualityError

FLOOR, NEUTRAL, CAP = 0.25, 1.0, 1.5


def g(x: float) -> float:
    """The GAP-0005 normalisation. Input x = marginal/baseline; NaN/inf-safe."""
    if not math.isfinite(x):
        raise DataQualityError("x", x, "g() is defined for finite inputs only")
    if x <= 0.0:
        return FLOOR
    if x < 1.0:
        return FLOOR + 0.75 * x
    return min(CAP, NEUTRAL + 0.5 * (x - 1.0))


@dataclass(frozen=True)
class MarginalAlphaResult:
    factor: float
    pinned: bool
    detail: str


class MarginalAlphaEstimator:
    """Rolling closed-trade window, bucketed at the median executed size."""

    def __init__(self, window: int, min_trades: int, min_bucket: int) -> None:
        self._trades: deque[tuple[Decimal, Decimal]] = deque(maxlen=window)
        self._min_trades = min_trades
        self._min_bucket = min_bucket

    def record_trade(self, size_units: Decimal, pnl: Decimal) -> None:
        if not isinstance(size_units, Decimal) or not isinstance(pnl, Decimal):
            raise DataQualityError("trade", (size_units, pnl), "Decimal required (F17)")
        if size_units <= 0:
            raise DataQualityError("size_units", size_units, "must be > 0")
        self._trades.append((size_units, pnl))

    def factor(self) -> MarginalAlphaResult:
        n = len(self._trades)
        if n < self._min_trades:
            return MarginalAlphaResult(NEUTRAL, True, f"cold_start:{n}<{self._min_trades}")
        sizes = sorted(float(s) for s, _ in self._trades)
        median = sizes[n // 2] if n % 2 else (sizes[n // 2 - 1] + sizes[n // 2]) / 2.0
        small = [(float(s), float(p)) for s, p in self._trades if float(s) <= median]
        large = [(float(s), float(p)) for s, p in self._trades if float(s) > median]
        if len(small) < self._min_bucket or len(large) < self._min_bucket:
            return MarginalAlphaResult(NEUTRAL, True, "bucket_underpopulated")
        mean_size_s = sum(s for s, _ in small) / len(small)
        mean_size_l = sum(s for s, _ in large) / len(large)
        if mean_size_l == mean_size_s:
            return MarginalAlphaResult(NEUTRAL, True, "degenerate_buckets")
        mean_pnl_s = sum(p for _, p in small) / len(small)
        mean_pnl_l = sum(p for _, p in large) / len(large)
        m = (mean_pnl_l - mean_pnl_s) / (mean_size_l - mean_size_s)
        b = sum(p / s for s, p in small + large) / n   # baseline: mean pnl per unit
        if b <= 0.0:
            return MarginalAlphaResult(FLOOR, False, "baseline_nonpositive")
        return MarginalAlphaResult(g(m / b), False, f"m={m:.6g},b={b:.6g}")
