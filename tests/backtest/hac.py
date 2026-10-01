"""Stage A's standard error (ACIS-09 C-BT-11 v2 step 3; GAP-P12D-121): Newey-West HAC.

A daily portfolio series of a trend book is autocorrelated, so an iid standard error makes the
one-sided bound too narrow and the test too loose: at lag-1 rho of 0.05-0.10 a nominal 5% test
rejects 6.3-7.2% of the time (Lo 2002). Stage A's bound uses this one instead.

Mental model:
  * The bound on the annual Sharpe is > 0 exactly when the HAC t-statistic of the MEAN daily
    return exceeds z(1 - alpha): the Sharpe's sign is the mean's.
  * Newey & West (1987) Bartlett weights 1 - l/(L+1); the lag L is Newey & West (1994)'s plug-in
    rule floor(4·(T/100)^(2/9)), fixed in advance, never chosen on the data (declared).
  * Calibrated on the lab before it binds: B0 holds with this detector at the declared n
    (`test_b0_holds_with_the_hac_detector`), and on an AR(1) null it keeps its size where the
    iid test does not (`test_hac_keeps_its_size_on_an_autocorrelated_null`).
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np


def nw_lags(n: int) -> int:
    """Newey & West (1994): floor(4·(n/100)^(2/9))."""
    return int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def hac_t(x: np.ndarray, lags: int | None = None) -> float:
    """The Newey-West t-statistic of the mean of `x` (Bartlett kernel)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        raise ValueError("need at least 3 observations")
    lags = nw_lags(n) if lags is None else lags
    d = x - x.mean()
    lrv = float(d @ d) / n
    for l in range(1, lags + 1):
        lrv += 2.0 * (1.0 - l / (lags + 1.0)) * float(d[l:] @ d[:-l]) / n
    if lrv <= 0:
        return 0.0
    return float(x.mean() / math.sqrt(lrv / n))


def hac_detector(alpha: float = 0.05):
    """Stage A's one-sided test: the HAC lower bound of the annual Sharpe is above zero."""
    crit = NormalDist().inv_cdf(1.0 - alpha)
    return lambda pnl: hac_t(pnl) > crit
