"""Deflated Sharpe Ratio (GAP-SP12E-03) pinned to its external referent.

Bailey & López de Prado (2014), "The Deflated Sharpe Ratio", numerical example: an
annualised SR of 2.5 over 5 years of daily returns (T = 1250, 250 per year), N = 100
independent trials whose annualised Sharpe ratios have variance 1/2, skewness -3 and
kurtosis 10 give SR0 = 0.1132 (non-annualised) and DSR = 0.9004; with N = 46 the DSR is
0.9505; with normal returns (skew 0, kurtosis 3) it reaches 0.95 only after N = 88.
"""

from __future__ import annotations

import math

import pytest

from tests.backtest.deflated_sharpe import (ReturnMoments, deflated_sharpe,
                                            expected_max_sharpe, moments,
                                            probabilistic_sharpe, sharpe_threshold)

PPY = 250
SR = 2.5 / math.sqrt(PPY)             # per period
VAR = 0.5 / PPY                       # per-period variance of the trial Sharpe ratios


def test_reproduces_the_papers_numerical_example() -> None:
    skewed = ReturnMoments(n=1250, sharpe=SR, skew=-3.0, kurtosis=10.0)
    sr0 = expected_max_sharpe(VAR, 100)
    assert sr0 == pytest.approx(0.1132, abs=5e-5)
    assert probabilistic_sharpe(skewed, sr0) == pytest.approx(0.9004, abs=5e-5)
    assert probabilistic_sharpe(skewed, expected_max_sharpe(VAR, 46)) == pytest.approx(0.9505, abs=5e-5)
    normal = ReturnMoments(n=1250, sharpe=SR, skew=0.0, kurtosis=3.0)
    assert probabilistic_sharpe(normal, expected_max_sharpe(VAR, 88)) == pytest.approx(0.9505, abs=5e-4)


def test_more_trials_deflate_more() -> None:
    m = ReturnMoments(n=1250, sharpe=SR, skew=-3.0, kurtosis=10.0)
    dsr = [probabilistic_sharpe(m, expected_max_sharpe(VAR, n)) for n in (2, 10, 100, 1000)]
    assert dsr == sorted(dsr, reverse=True) and dsr[0] > dsr[-1]


def test_no_selection_means_a_zero_threshold() -> None:
    assert sharpe_threshold([]) == 0.0 and sharpe_threshold([0.3]) == 0.0
    assert expected_max_sharpe(VAR, 1) == 0.0


def test_moments_of_a_known_series() -> None:
    r = [0.02, -0.01] * 50                      # mean 0.005, deviations ±0.015
    m = moments(r)
    assert m.n == 100 and m.skew == pytest.approx(0.0, abs=1e-12)
    assert m.kurtosis == pytest.approx(1.0)
    assert m.sharpe == pytest.approx(0.005 / (0.015 * math.sqrt(100 / 99)))


def test_no_sharpe_means_nan() -> None:
    assert math.isnan(deflated_sharpe([0.01] * 50, []))    # zero variance
    assert math.isnan(deflated_sharpe([0.01, 0.02], []))   # too short
    assert moments([math.nan, 0.01]) is None
