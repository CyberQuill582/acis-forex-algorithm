"""Float statistics for the regime layer's hot loops (GAP-P12D-12).

`statistics.pstdev` computes in exact rational arithmetic (Fraction + gcd per value). NVMA
called it ~142 times per tick, and it was 82% of replay time on real Dukascopy ticks.
`pstdev` here is the same population standard deviation in floats — correctly rounded
sums (`math.fsum`) taken around the fsum mean. Guarantees, pinned by
tests/unit/test_fast_stats.py:

  * a constant series gives EXACTLY 0.0, like the exact version (the GAP-0076 hazard:
    float dust in a spread sigma would flip the ILLIQUID comparison);
  * the result does not depend on input order (fsum is exact up to one final rounding),
    so chunks holding the same values give bit-identical widths and percentile ties hold;
  * on price-like data it agrees with `statistics.pstdev` to a relative 1e-12.
"""

from __future__ import annotations

import math
import statistics
from typing import Sequence


def pstdev(xs: Sequence[float]) -> float:
    """Population standard deviation of `xs` in floats (see module docstring)."""
    n = len(xs)
    if n < 1:
        raise statistics.StatisticsError("pstdev requires at least one data point")
    first = xs[0]
    if all(x == first for x in xs):
        return 0.0
    mean = math.fsum(xs) / n
    return math.sqrt(math.fsum((x - mean) * (x - mean) for x in xs) / n)
