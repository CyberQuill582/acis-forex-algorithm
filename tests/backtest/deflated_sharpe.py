"""Probabilistic and Deflated Sharpe Ratio (GAP-SP12E-03).

Referent: Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection
Bias, Backtest Overfitting and Non-Normality", Journal of Portfolio Management 40(5), 2014,
Eq. (2):

    DSR = Z[ (SR - SR0) * sqrt(T - 1) / sqrt(1 - g3 * SR + (g4 - 1) / 4 * SR^2) ]
    SR0 = sqrt(V[{SR_n}]) * ((1 - gamma) * Zinv[1 - 1/N] + gamma * Zinv[1 - 1/(N e)])

with Z the standard normal CDF, gamma the Euler-Mascheroni constant, T the number of
returns, g3 the skewness and g4 the RAW kurtosis (3 for a normal distribution, not excess
kurtosis) of the selected strategy's returns, and N independent trials whose Sharpe ratios
have variance V. Every Sharpe ratio here is PER PERIOD, never annualised — mixing the two
is the usual mistake. `test_reproduces_the_papers_numerical_example` pins the paper's own
numbers (SR0 0.1132 and DSR 0.9004 at N=100; DSR 0.9505 at N=46).

DECLARED DEVIATIONS (§5.6): (1) N is the number of trial Sharpe ratios supplied, treated as
independent; the paper clusters correlated trials first (its Appendix 3). Over-counting N
raises SR0 and lowers DSR, so the error is conservative. (2) The Sharpe estimator is the
engine's own rf=0 mean / sample-sd form (`metrics.annual_sharpe`, GAP-P11E-05), de-annualised.
N < 2 means no selection was made: SR0 = 0 and DSR is the plain PSR against zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Sequence

EULER_GAMMA = 0.5772156649015329
_Z = NormalDist()


@dataclass(frozen=True)
class ReturnMoments:
    n: int              # number of returns (T)
    sharpe: float       # per-period mean / sample sd
    skew: float
    kurtosis: float     # raw (normal = 3)


def moments(returns: Sequence[float]) -> ReturnMoments | None:
    """None when fewer than 3 finite returns or zero variance (no Sharpe exists). `fsum` keeps
    a constant series exactly constant: a plain `sum` of 50 × 0.01 leaves float dust, a tiny
    non-zero variance and a huge spurious Sharpe (the GAP-0076 hazard)."""
    r = [x for x in returns if math.isfinite(x)]
    n = len(r)
    if n < 3:
        return None
    mean = math.fsum(r) / n
    m2 = math.fsum((x - mean) ** 2 for x in r) / n
    if m2 == 0.0:
        return None
    m3 = math.fsum((x - mean) ** 3 for x in r) / n
    m4 = math.fsum((x - mean) ** 4 for x in r) / n
    return ReturnMoments(n=n, sharpe=mean / math.sqrt(m2 * n / (n - 1)),
                         skew=m3 / m2 ** 1.5, kurtosis=m4 / m2 ** 2)


def expected_max_sharpe(trial_variance: float, n_trials: int) -> float:
    """SR0: the expected maximum of N trial Sharpe ratios when every true Sharpe is zero."""
    if n_trials < 2 or trial_variance <= 0.0:
        return 0.0
    return math.sqrt(trial_variance) * ((1 - EULER_GAMMA) * _Z.inv_cdf(1 - 1 / n_trials)
                                        + EULER_GAMMA * _Z.inv_cdf(1 - 1 / (n_trials * math.e)))


def sharpe_threshold(trial_sharpes: Sequence[float]) -> float:
    t = [x for x in trial_sharpes if math.isfinite(x)]
    if len(t) < 2:
        return 0.0
    mean = sum(t) / len(t)
    return expected_max_sharpe(sum((x - mean) ** 2 for x in t) / (len(t) - 1), len(t))


def probabilistic_sharpe(m: ReturnMoments, threshold: float) -> float:
    """P(true Sharpe > threshold). NaN when the non-normality term is not positive."""
    denom = 1 - m.skew * m.sharpe + (m.kurtosis - 1) / 4 * m.sharpe ** 2
    if denom <= 0.0:
        return math.nan
    return _Z.cdf((m.sharpe - threshold) * math.sqrt(m.n - 1) / math.sqrt(denom))


def deflated_sharpe(returns: Sequence[float], trial_sharpes: Sequence[float]) -> float:
    """DSR of the selected strategy's per-period `returns`, deflated by the trials. NaN when
    the returns carry no Sharpe ratio."""
    m = moments(returns)
    return math.nan if m is None else probabilistic_sharpe(m, sharpe_threshold(trial_sharpes))
