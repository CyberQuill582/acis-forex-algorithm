"""Hand-worked values for the Deflated Sharpe paths the paper's example does not reach
(GAP-P12D-28 mutation-gate triage): the skew and kurtosis formulas, the trials' SAMPLE
variance, the NaN branch of the non-normality term, and the N < 2 boundaries."""

from __future__ import annotations

import math
from statistics import NormalDist

import pytest

from tests.backtest.deflated_sharpe import (EULER_GAMMA, ReturnMoments, deflated_sharpe,
                                            expected_max_sharpe, moments, probabilistic_sharpe,
                                            sharpe_threshold)


def test_moments_of_a_skewed_three_point_series() -> None:
    # [0, 0, 3]: mean 1, deviations -1 -1 2 -> m2 = 6/3 = 2, m3 = 6/3 = 2, m4 = 18/3 = 6
    # skew 2 / 2^1.5 = 0.70711; raw kurtosis 6 / 4 = 1.5; Sharpe 1 / sqrt(2·3/2) = 1/sqrt(3)
    m = moments([0.0, 0.0, 3.0])
    assert m.n == 3
    assert m.skew == pytest.approx(2 / 2 ** 1.5)
    assert m.kurtosis == pytest.approx(1.5)
    assert m.sharpe == pytest.approx(1 / math.sqrt(3))


def test_moments_are_frozen() -> None:
    with pytest.raises(AttributeError):
        moments([0.0, 0.0, 3.0]).n = 4


def test_non_finite_returns_are_dropped_before_counting() -> None:
    assert moments([0.0, math.nan, 0.0, math.inf, 3.0]) == moments([0.0, 0.0, 3.0])


def test_the_trial_variance_is_the_sample_variance() -> None:
    # [0, 0.2]: mean 0.1, sample variance (0.01 + 0.01) / 1 = 0.02 (the population form gives 0.01)
    # N = 2: Zinv(1 - 1/2) = 0, so SR0 = sqrt(0.02) · gamma · Zinv(1 - 1/(2e))
    expected = math.sqrt(0.02) * EULER_GAMMA * NormalDist().inv_cdf(1 - 1 / (2 * math.e))
    assert sharpe_threshold([0.0, 0.2]) == pytest.approx(expected)
    assert expected == pytest.approx(0.07352, abs=5e-5)
    assert sharpe_threshold([0.0, math.nan, 0.2]) == sharpe_threshold([0.0, 0.2])
    assert sharpe_threshold([0.0, 0.2], n_trials=3) == pytest.approx(expected_max_sharpe(0.02, 3))


def test_three_trials_use_the_n_minus_one_divisor() -> None:
    # [0, 0.1, 0.2]: squared deviations sum to 0.02; sample variance 0.02 / 2 = 0.01
    assert sharpe_threshold([0.0, 0.1, 0.2]) == pytest.approx(expected_max_sharpe(0.01, 3))


def test_two_trials_is_already_a_selection() -> None:
    assert expected_max_sharpe(0.02, 2) > 0.0
    assert expected_max_sharpe(0.0, 10) == 0.0 and expected_max_sharpe(-0.01, 10) == 0.0


def test_probabilistic_sharpe_hand_worked() -> None:
    # T 101, SR 0.1, normal: z = 0.1 · sqrt(100) / sqrt(1 + (3-1)/4 · 0.01) = 1 / sqrt(1.005) = 0.997509
    # Phi(0.997509) = Phi(1) - 0.002491 · phi(1) = 0.841345 - 0.000603 = 0.840742
    m = ReturnMoments(n=101, sharpe=0.1, skew=0.0, kurtosis=3.0)
    assert probabilistic_sharpe(m, 0.0) == pytest.approx(0.84074, abs=2e-5)
    # a threshold equal to the Sharpe is a coin flip
    assert probabilistic_sharpe(m, 0.1) == pytest.approx(0.5)


def test_a_non_positive_non_normality_term_is_nan() -> None:
    # 1 - 3·1 + (3-1)/4 · 1 = -1.5 ; 1 - 1.5·1 + 0.5 = 0 exactly
    assert math.isnan(probabilistic_sharpe(ReturnMoments(n=50, sharpe=1.0, skew=3.0, kurtosis=3.0), 0.0))
    assert math.isnan(probabilistic_sharpe(ReturnMoments(n=50, sharpe=1.0, skew=1.5, kurtosis=3.0), 0.0))


def test_deflated_sharpe_is_the_psr_at_the_trials_threshold() -> None:
    r, trials = [0.0, 0.0, 3.0], [0.0, 0.2]
    assert deflated_sharpe(r, trials) == pytest.approx(
        probabilistic_sharpe(moments(r), sharpe_threshold(trials)))
    assert deflated_sharpe(r, trials, n_trials=50) == pytest.approx(
        probabilistic_sharpe(moments(r), sharpe_threshold(trials, 50)))
    assert deflated_sharpe(r, trials, n_trials=50) < deflated_sharpe(r, trials)
