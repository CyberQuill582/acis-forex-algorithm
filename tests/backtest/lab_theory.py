"""Closed forms for the daily lab (R1.1 C-3/C-5, ACIS-09 C-BT-12): the annual Sharpe of each
plantable effect's oracle, and of an EWMA crossover, so a detection rate is always graded against
a stated power. The design is R1-C's (CLOUD_AUDIT/reports/r1/R1C_SYNTH_LAB.md §2.4); this is its
production form.

Mental model:
  * Everything is per weekday in VOLATILITY UNITS: y_t = m_t + e_t, where Var(e_t) = `other`
    (the unit diffusive variance plus the Monday gap, averaged over weekdays) and the planted
    drift m_t is independent of e.
  * THE ORACLE knows the drift in force on day t at the start of day t (the state in force now,
    never the next one, as in the tick generator) and holds sign(m_t) over day t. Its daily
    mean is E|m_t| = sqrt(2/pi)·sd(m), so annual Sharpe = sqrt(2/pi)·sd(m) / sd(sign·y) · sqrt(252).
  * A RULE decides day t from y up to t-1. Under joint Gaussianity
    E[sign(X)·y'] = sqrt(2/pi)·Cov(X, y')/sd(X), which gives every linear sign rule's Sharpe.
  * Each strength is solved from its target Sharpe by bisection: every Sharpe here is monotone
    in its strength, so no root-finding library is needed (the §16 stack has none named).
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Callable

import numpy as np

YEAR = 252
SQ2PI = math.sqrt(2.0 / math.pi)


def ar_phi(halflife: float) -> float:
    """The AR(1) coefficient whose impulse response halves in `halflife` weekdays."""
    return 0.5 ** (1.0 / halflife)


def solve_increasing(f: Callable[[float], float], target: float, lo: float, hi: float) -> float:
    """x in [lo, hi] with f(x) = target, for f increasing: bisection to machine precision."""
    if not f(lo) <= target <= f(hi):
        raise ValueError(f"target {target} outside [{f(lo)}, {f(hi)}]")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
        if hi - lo <= 1e-15 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


def sign_rule_sharpe(mean: float, second_moment: float) -> float:
    """Annual Sharpe of a ±1 position whose daily P&L has this mean and E[y²]: the P&L's
    second moment is E[y²] whatever the sign, so its variance is E[y²] - mean²."""
    return mean / math.sqrt(second_moment - mean * mean) * math.sqrt(YEAR)


def oracle_sharpe(v_m: float, other: float) -> float:
    """The oracle holding sign(m_t) over day t, with Var(m) = v_m (Gaussian m)."""
    return sign_rule_sharpe(SQ2PI * math.sqrt(v_m), v_m + other)


def drift_variance_for(sharpe: float, other: float) -> float:
    """The Var(m) at which the oracle earns `sharpe` a year (0 for 0)."""
    if sharpe == 0.0:
        return 0.0
    return solve_increasing(lambda v: oracle_sharpe(v, other), sharpe, 1e-14, 50.0)


def ewmac_weights(fast: int, slow: int, n: int) -> np.ndarray:
    """EWMA_fast(p) - EWMA_slow(p) of the cumulative return p is sum_k w_k·y_(t-k), with
    w_k = (1 - a_slow)^(k+1) - (1 - a_fast)^(k+1), a = 2/(span + 1)."""
    a_fast, a_slow = 2.0 / (fast + 1), 2.0 / (slow + 1)
    k = np.arange(n)
    return (1 - a_slow) ** (k + 1) - (1 - a_fast) ** (k + 1)


def ewmac_sharpe(v_m: float, phi: float, other: float, fast: int, slow: int) -> float:
    """Annual Sharpe of sign(EWMA_fast - EWMA_slow) of y up to t-1, held over day t, when m is an
    AR(1) with coefficient phi and stationary variance v_m. X = sum_k w_k y_(t-1-k), so
    Cov(X, y_t) = v_m·sum_k w_k·phi^(k+1) and Var(X) = other·sum w² + v_m·sum_j sum_k w_j w_k
    phi^|j-k| (the double sum by an O(n) recursion)."""
    n = int(12 * slow) + 50
    w = ewmac_weights(fast, slow, n)
    cov = v_m * float(np.sum(w * phi ** (np.arange(n) + 1)))
    double, acc = 0.0, 0.0
    for j in range(n):                          # acc_j = sum_(k<j) w_k·phi^(j-k)
        acc = phi * (acc + (w[j - 1] if j else 0.0))
        double += w[j] * (w[j] + 2.0 * acc)
    var_x = other * float(np.sum(w * w)) + v_m * double
    return sign_rule_sharpe(SQ2PI * cov / math.sqrt(var_x), v_m + other)


def detection_power(sharpe: float, years: float, alpha: float = 0.05) -> float:
    """The power statement (C-5): the chance a one-sided t-test at `alpha` detects a true annual
    Sharpe over `years` of daily returns, Phi(SR·sqrt(years) - z_alpha)."""
    unit = NormalDist()
    return unit.cdf(sharpe * math.sqrt(years) - unit.inv_cdf(1.0 - alpha))


def carry_kappa_for(sharpe: float, other: float) -> float:
    """m = kappa·z with z the standardised rate differential (unit variance), known at the day's
    start; the rule sign(z) earns kappa·sqrt(2/pi) a day."""
    if sharpe == 0.0:
        return 0.0
    return solve_increasing(lambda k: sign_rule_sharpe(k * SQ2PI, k * k + other), sharpe, 1e-12, 5.0)


def season_size_for(sharpe: float, flagged: float, other: float) -> float:
    """The turn-of-month rule holds dir_i on the flagged share of days and is flat otherwise:
    daily mean s·f, second moment f·(other + s²)."""
    if sharpe == 0.0:
        return 0.0
    return solve_increasing(lambda s: sign_rule_sharpe(s * flagged, flagged * (other + s * s)),
                            sharpe, 1e-12, 5.0)
