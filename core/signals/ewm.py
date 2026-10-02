"""Carver's estimators in stdlib (master §5.6 v2.22, §16 stdlib decision path; GAP-P12D-122).

The TREND family's scalars are Carver's published 3.75 / 2.65 / 1.87, so its normaliser and EWMA
convention must be HIS: pysystemtrade master `a62269d27707806ba61f516791b71a9cd14cf268` (2026-09-29),
`sysquant/estimators/vol.py` and `defaults.yaml` `volatility_calculation` (pandas `ewm(span=...,
adjust=True)` and `rolling(...)`). Reproduced exactly, NaN handling included (ignore_na=False);
`tests/unit/test_carver_reference.py` pins every function to Carver's own code's values.

Mental model:
  * A series is a list of floats; NaN means "no observation". Outputs have the input's length.
  * `ewm_mean`/`ewm_std` are pandas' adjusted EWMA (alpha = 2/(span+1)): after a NaN the
    weights still decay (ignore_na=False), and an output is NaN until `min_periods`
    observations exist. `ewm_std` is the bias-corrected one (`bias=False`).
  * `mixed_vol` is Carver's default normaliser, the daily price-unit volatility:
    70% of the 35-day EWMA standard deviation of daily price changes plus 30% of that series'
    own 10-year (2,560-business-day) EWMA, floored at 1e-10.
  * `rolling_max`/`rolling_min` are pandas' trailing windows that include the current point.
"""

from __future__ import annotations

import math
from typing import Sequence

NAN = float("nan")
BUSINESS_DAYS_IN_YEAR = 256        # syscore/dateutils.py at the pinned commit
CARVER_COMMIT = "a62269d27707806ba61f516791b71a9cd14cf268"


def _alpha(span: float) -> float:
    if span < 1:
        raise ValueError(f"span must be >= 1, got {span}")
    return 2.0 / (span + 1.0)


def ewm_mean(xs: Sequence[float], span: float, min_periods: int = 0) -> list[float]:
    """pandas `Series.ewm(span, min_periods, adjust=True).mean()`."""
    decay, minp = 1.0 - _alpha(span), max(min_periods, 1)
    out: list[float] = []
    weighted, old_wt, nobs = NAN, 1.0, 0
    for i, cur in enumerate(xs):
        obs = cur == cur
        nobs += obs
        if i == 0:
            weighted = cur
        elif weighted == weighted:
            old_wt *= decay
            if obs:
                if weighted != cur:
                    weighted = (old_wt * weighted + cur) / (old_wt + 1.0)
                old_wt += 1.0
        elif obs:
            weighted = cur
        out.append(weighted if nobs >= minp else NAN)
    return out


def ewm_std(xs: Sequence[float], span: float, min_periods: int = 0) -> list[float]:
    """pandas `Series.ewm(span, min_periods, adjust=True).std()` (bias=False)."""
    decay, minp = 1.0 - _alpha(span), max(min_periods, 1)
    out: list[float] = []
    mean, cov, sum_wt, sum_wt2, old_wt, nobs = NAN, 0.0, 1.0, 1.0, 1.0, 0
    for i, cur in enumerate(xs):
        obs = cur == cur
        nobs += obs
        if i == 0:
            mean = cur if obs else NAN
        elif mean == mean:
            sum_wt *= decay
            sum_wt2 *= decay * decay
            old_wt *= decay
            if obs:
                old_mean = mean
                if mean != cur:
                    mean = (old_wt * old_mean + cur) / (old_wt + 1.0)
                cov = (old_wt * (cov + (old_mean - mean) ** 2) + (cur - mean) ** 2) / (old_wt + 1.0)
                sum_wt += 1.0
                sum_wt2 += 1.0
                old_wt += 1.0
        elif obs:
            mean = cur
        if i > 0 and nobs >= minp:                       # pandas: the first output is NaN
            denominator = sum_wt * sum_wt - sum_wt2
            var = sum_wt * sum_wt / denominator * cov if denominator > 0 else NAN
            out.append(math.sqrt(var) if var == var and var > 0 else (0.0 if var == var else NAN))
        else:
            out.append(NAN)
    return out


def mixed_vol(daily_changes: Sequence[float], days: int = 35, min_periods: int = 10,
              slow_vol_years: int = 10, proportion_of_slow_vol: float = 0.3,
              vol_abs_min: float = 1e-10) -> list[float]:
    """`mixed_vol_calc` with `defaults.yaml`'s `volatility_calculation` (backfill off)."""
    vol = ewm_std(daily_changes, days, min_periods)
    long_vol = ewm_mean(vol, slow_vol_years * BUSINESS_DAYS_IN_YEAR)
    mixed = [lv * proportion_of_slow_vol + v * (1.0 - proportion_of_slow_vol)
             for lv, v in zip(long_vol, vol)]
    return [vol_abs_min if m < vol_abs_min else m for m in mixed]      # NaN stays NaN


def ffill(xs: Sequence[float]) -> list[float]:
    out, last = [], NAN
    for x in xs:
        last = x if x == x else last
        out.append(last)
    return out


def diff(xs: Sequence[float]) -> list[float]:
    """pandas `Series.diff()`: the first element is NaN."""
    return [NAN] + [b - a for a, b in zip(xs, xs[1:])]


def _rolling(xs: Sequence[float], window: int, min_periods: int, pick) -> list[float]:
    out = []
    for i in range(len(xs)):
        seen = [x for x in xs[max(0, i - window + 1):i + 1] if x == x]
        out.append(pick(seen) if len(seen) >= max(min_periods, 1) else NAN)
    return out


def rolling_max(xs: Sequence[float], window: int, min_periods: int) -> list[float]:
    return _rolling(xs, window, min_periods, max)


def rolling_min(xs: Sequence[float], window: int, min_periods: int) -> list[float]:
    return _rolling(xs, window, min_periods, min)
