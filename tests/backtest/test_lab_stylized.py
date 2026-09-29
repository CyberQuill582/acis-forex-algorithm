"""The lab's own gate (R1.1 C-8): at default knobs the null lab shows Cont (2001)'s stylized facts,
so a rule cannot pass the lab by exploiting an iid-Gaussian world (the tick generator's is one).

Targets are quoted in R1-C §2.5 from Cont, "Empirical properties of asset returns: stylized facts
and statistical issues", Quantitative Finance 1 (2001) 223-236. A tolerance marked "lab" is R1-C's
operationalisation of a qualitative fact, never a value fitted to market data. Not asserted: 5
intermittency, 9 leverage (an equity fact), 10 volume, 11 time-scale asymmetry. Four seeds of 20
instruments x 3,640 weekdays.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tests.backtest.lab_market import LabSpec, generate

LAGS, ABS_LAGS = np.arange(1, 21), np.arange(1, 101)


def _acf(x: np.ndarray, lags: np.ndarray) -> np.ndarray:
    x = x - x.mean()
    d = float(x @ x)
    return np.array([float(x[:-k] @ x[k:]) / d for k in lags])


def _moment_ratio(x: np.ndarray, k: int) -> float:
    c = x - x.mean()
    return float(np.mean(c ** k) / np.mean(c ** 2) ** (k / 2))


def _hill(abs_z: np.ndarray, frac: float = 0.025) -> float:
    s = np.sort(abs_z)[::-1]
    k = max(10, int(frac * len(s)))
    return float(1.0 / np.mean(np.log(s[:k] / s[k])))


def _r2(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(slope, R²) of the least-squares line y ~ x."""
    slope, icpt = np.polyfit(x, y, 1)
    resid = y - (slope * x + icpt)
    return float(slope), float(1.0 - resid @ resid / ((y - y.mean()) @ (y - y.mean())))


@pytest.fixture(scope="module")
def facts() -> dict[str, float]:
    out: dict[str, list[float]] = {}
    add = lambda k, v: out.setdefault(k, []).append(float(v))
    for seed in range(1, 5):
        p = generate(LabSpec(seed=seed))
        r, (T, N) = p.r, p.r.shape
        mean_abs_acf = np.zeros(len(ABS_LAGS))
        for i in range(N):
            x = r[:, i]
            xc = x - x.mean()
            d = float(xc @ xc)
            robust_se = np.array([math.sqrt(float(xc[:-k] ** 2 @ xc[k:] ** 2)) / d for k in LAGS])
            add("acf_share", np.mean(np.abs(_acf(x, LAGS)) > 1.96 * robust_se))
            add("hill", _hill(np.abs(x / x.std())))
            add("kurt1", _moment_ratio(x, 4) - 3)
            add("kurt5", _moment_ratio(x[: T // 5 * 5].reshape(-1, 5).sum(1), 4) - 3)
            add("kurt20", _moment_ratio(x[: T // 20 * 20].reshape(-1, 20).sum(1), 4) - 3)
            add("skew", _moment_ratio(x, 3))
            absacf = _acf(np.abs(x), ABS_LAGS)
            mean_abs_acf += absacf / N
            add("absacf1_5", absacf[:5].mean())
            add("kurt_conditional", _moment_ratio(x / p.sigma[:, i], 4))
            add("kurt_unconditional", _moment_ratio(x, 4))
        ok = mean_abs_acf > 0
        slope, r2_power = _r2(np.log(ABS_LAGS[ok]), np.log(mean_abs_acf[ok]))
        _, r2_exp = _r2(ABS_LAGS[ok].astype(float), np.log(mean_abs_acf[ok]))
        add("beta", -slope)
        add("r2_power", r2_power)
        add("r2_exp", r2_exp)
    return {k: float(np.mean(v)) for k, v in out.items()}


def test_1_linear_autocorrelations_are_insignificant(facts) -> None:
    """Cont 1, against a heteroskedasticity-robust band (the iid band is invalid under clustering)."""
    assert facts["acf_share"] <= 0.10, facts["acf_share"]          # lab tolerance; 0.05 nominal


def test_2_tails_are_heavy_with_a_tail_index_between_two_and_five(facts) -> None:
    assert 2.0 < facts["hill"] < 5.0, facts["hill"]


def test_3_fx_shows_no_gain_loss_asymmetry(facts) -> None:
    """Cont's footnote: not true for exchange rates, which are more symmetric."""
    assert abs(facts["skew"]) < 0.2, facts["skew"]                 # lab tolerance


def test_4_aggregation_brings_returns_toward_gaussian(facts) -> None:
    assert facts["kurt1"] > facts["kurt5"] > facts["kurt20"], facts
    assert facts["kurt20"] < 0.5 * facts["kurt1"], facts           # lab tolerance


def test_6_volatility_clusters(facts) -> None:
    assert facts["absacf1_5"] > 0.05, facts["absacf1_5"]           # lab tolerance


def test_7_tails_stay_heavy_after_correcting_for_volatility(facts) -> None:
    assert 3.0 < facts["kurt_conditional"] < facts["kurt_unconditional"], facts


def test_8_absolute_return_autocorrelation_decays_as_a_power_law(facts) -> None:
    """Cont: beta in [0.2, 0.4], and a power law must fit better than an exponential (the shape
    test GARCH(1,1) alone fails)."""
    assert 0.2 <= facts["beta"] <= 0.4 and facts["r2_power"] > facts["r2_exp"], facts
