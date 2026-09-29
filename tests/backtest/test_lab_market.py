"""The daily lab carries exactly the answer it claims (R1.1 C-3/C-5; ACIS-09 C-BT-12). Every
statistical test also runs the DEFECT it guards against, so it is shown to have the power to catch it."""

from __future__ import annotations

import math

import numpy as np
import pytest

from dataclasses import replace

from tests.backtest.lab_intraday import intraday
from tests.backtest.lab_market import Effect, LabSpec, calendar, generate, permuted
from tests.backtest.lab_theory import (YEAR, ar_phi, drift_variance_for, ewmac_sharpe,
                                       ewmac_weights, oracle_sharpe)

BURN = 300


def _t(values) -> float:
    v = np.asarray(values, float)
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(v.size)))


def _sharpe(pnl: np.ndarray) -> np.ndarray:
    """Annual Sharpe per instrument after the burn-in."""
    p = pnl[BURN:]
    return p.mean(axis=0) / p.std(axis=0, ddof=1) * math.sqrt(YEAR)


def _momentum(y: np.ndarray, lookback: int) -> np.ndarray:
    """Per-instrument mean of sign(sum of the past `lookback` days)·y_t."""
    c = np.vstack([np.zeros(y.shape[1]), np.cumsum(y, axis=0)])
    past = c[lookback:-1] - c[:-lookback - 1]
    return (np.sign(past) * y[lookback:]).mean(axis=0)


def _ewmac(y: np.ndarray, fast: int, slow: int) -> np.ndarray:
    """sign(EWMA_fast - EWMA_slow) of the cumulative y, decided from days up to t-1."""
    p, af, a_s = np.cumsum(y, axis=0), 2 / (fast + 1), 2 / (slow + 1)
    ef, es, pos = np.zeros(y.shape[1]), np.zeros(y.shape[1]), np.zeros_like(y)
    for t in range(len(y)):
        pos[t] = np.sign(ef - es)
        ef += af * (p[t] - ef)
        es += a_s * (p[t] - es)
    return pos


def test_generation_is_deterministic_read_only_and_weekday_only() -> None:
    a, b = generate(LabSpec(seed=3, days=400)), generate(LabSpec(seed=3, days=400))
    assert np.array_equal(a.r, b.r) and a.kind == "null" and a.scale == 1.0
    assert not a.r.flags.writeable
    dates, tom, monday = calendar(LabSpec(days=400))
    assert all(d.astype(object).weekday() < 5 for d in dates) and monday[0] and tom[0]
    assert dates[0] == np.datetime64("2012-01-02") and len(dates) == 400


def test_planted_is_the_nulls_noise_plus_the_drift_times_one_exact_scale() -> None:
    """Common random numbers plus an exact rescale (GAP-P12D-90): the model variance of y over
    the decision horizon (one weekday) is the null's, scale² · (Var m + other) = other."""
    spec = LabSpec(seed=5, days=500, effect=Effect(trend_sharpe=0.5, trend_halflife=60))
    null, planted = generate(LabSpec(seed=5, days=500)), generate(spec)
    v_m = drift_variance_for(0.5, spec.other)
    assert planted.kind == "planted"
    assert planted.scale ** 2 * (v_m + spec.other) == pytest.approx(spec.other, rel=1e-12)
    assert np.allclose(planted.y / planted.scale - planted.m, null.y, rtol=0, atol=1e-12)
    unapplied = generate(spec, null=True)                        # the tick generator's contract (R11I-05)
    assert unapplied.kind == "null" and unapplied.scale == 1.0 and not unapplied.m.any()
    assert np.array_equal(unapplied.y, null.y) and np.array_equal(unapplied.truth, planted.truth)
    assert np.array_equal(planted.truth, planted.m) and planted.truth.any()


def test_the_null_is_a_martingale_and_the_old_bridge_is_caught() -> None:
    """sign(past 126 days)·y_t averages 0 on the null over 400 paths; the SAME draws demeaned
    per path (a Brownian bridge, GAP-P12D-91) lose at t < -3."""
    fair, bridge = [], []
    for seed in range(20):
        y = generate(LabSpec(seed=seed, days=705)).y
        fair.extend(_momentum(y, 126))
        bridge.extend(_momentum(y - y.mean(axis=0), 126))
    assert abs(_t(fair)) < 3.0 and _t(bridge) < -3.0, (_t(fair), _t(bridge))


def test_a_long_bias_earns_nothing_in_price_units_on_either_null() -> None:
    """A financed buy-and-hold compounds (1 + r): its wealth centres on 1 over 400 instrument
    paths. The same draws built as exp(sum r), the prototype's law, earn the convexity on top."""
    wealth, convexity = [], []
    for seed in range(20):
        base = generate(LabSpec(seed=seed, days=1260))
        for path in (base, permuted(base)):
            w = np.prod(1.0 + path.r, axis=0)
            wealth.extend(w - 1.0)
            convexity.extend(np.exp(path.r.sum(axis=0)) - w)
    assert abs(_t(wealth)) < 3.0 and _t(convexity) > 10.0, (_t(wealth), _t(convexity))
    path = generate(LabSpec(seed=1, days=400))
    assert np.allclose(path.mids(1.1)[1:], path.mids(1.1)[:-1] * (1.0 + path.spot[1:]), rtol=1e-13)


def test_permuting_keeps_every_day_and_its_cross_section_and_is_a_martingale() -> None:
    base = generate(LabSpec(seed=2, days=705))
    perm = permuted(base)
    rows = lambda a: sorted(map(tuple, np.round(np.abs(a), 15)))
    assert rows(perm.r) == rows(base.r) and not np.array_equal(perm.r, base.r)
    assert np.array_equal(perm.accrual, base.accrual) and np.array_equal(perm.dates, base.dates)
    assert np.array_equal(perm.truth, base.truth)                # planted's schedule, unapplied
    moves = []
    for seed in range(20):
        moves.extend(_momentum(permuted(generate(LabSpec(seed=seed, days=705))).y, 126))
    assert abs(_t(moves)) < 3.0, _t(moves)


CASES = {"null": Effect(), "trend": Effect(trend_sharpe=0.5, trend_halflife=60),
         "carry": Effect(carry_sharpe=0.5), "xsmom": Effect(xsmom_sharpe=0.5, xsmom_halflife=60),
         "season": Effect(season_sharpe=0.5)}


@pytest.mark.parametrize("name", list(CASES))
def test_each_effect_delivers_its_stated_sharpe(name) -> None:
    """R1-C C-3's falsifier: over 20 seeds x 20 instruments the oracle of each planted effect
    earns its stated 0.5 within 3 se, EWMAC 16/64 earns its closed form on the trend, and on the
    null every rule is within 3 se of 0 (C-5: a detection rate is graded against a stated power)."""
    other = LabSpec().other
    expected = {"null": {"ewmac": 0.0, "carry": 0.0, "season": 0.0},
                "trend": {"oracle": 0.5,
                          "ewmac": ewmac_sharpe(drift_variance_for(0.5, other), ar_phi(60), other, 16, 64)},
                "carry": {"carry": 0.5}, "xsmom": {"oracle": 0.5}, "season": {"season": 0.5}}[name]
    rules = {"oracle": lambda p: np.sign(p.truth), "ewmac": lambda p: _ewmac(p.y, 16, 64),
             "carry": lambda p: np.sign(p.rate),
             "season": lambda p: p.tom[:, None] * p.season_dir * np.ones_like(p.y)}
    realised: dict[str, list[float]] = {}
    for seed in range(1, 21):
        p = generate(LabSpec(seed=seed, effect=CASES[name]))
        for rule in expected:
            realised.setdefault(rule, []).append(float(_sharpe(rules[rule](p) * p.y).mean()))
    for rule, target in expected.items():
        v = np.asarray(realised[rule])
        se = v.std(ddof=1) / math.sqrt(v.size)
        assert abs(v.mean() - target) < 3 * se + 1e-9, (name, rule, v.mean(), target, se)


def test_the_closed_forms_invert_and_the_ewmac_weights_are_the_standard_identity() -> None:
    other = LabSpec().other
    for sr in (0.2, 0.5, 1.0):
        assert oracle_sharpe(drift_variance_for(sr, other), other) == pytest.approx(sr, rel=1e-9)
    y = np.random.default_rng(0).standard_normal(400)
    p, af, a_s = np.cumsum(y), 2 / 17, 2 / 65
    ef = es = 0.0
    for v in p:
        ef, es = ef + af * (v - ef), es + a_s * (v - es)
    w = ewmac_weights(16, 64, 400)
    assert ef - es == pytest.approx(float(np.dot(w, y[::-1])), abs=1e-9)


def test_a_bad_spec_is_refused() -> None:
    with pytest.raises(ValueError, match="carry"):
        LabSpec(financing=False, effect=Effect(carry_sharpe=0.5))
    with pytest.raises(ValueError, match="Monday"):
        LabSpec(start="2012-01-03")
    with pytest.raises(ValueError, match="stationary"):
        LabSpec(garch=(0.2, 0.85))
    with pytest.raises(ValueError, match="trend_scope"):
        Effect(trend_scope="sector")
    for bad in (dict(ann_vol=(0.0, 0.1)), dict(ann_vol=(0.1, 1.6)), dict(rate_sd=0.6)):
        with pytest.raises(ValueError, match="FX-like"):
            LabSpec(**bad)
    assert not generate(LabSpec(seed=1, days=400, financing=False)).rate.any()


def test_a_spot_return_at_or_below_minus_one_is_refused_daily_and_intraday() -> None:
    """R11I-11: prices compound SPOT, so spot is what is checked, and so is the intraday level."""
    with pytest.raises(ValueError, match="spot return <= -1"):
        generate(LabSpec(seed=1, ann_vol=(0.99, 0.99), jumps_per_year=1.0, jump_sd=10.0))
    path = generate(LabSpec(seed=1, days=400))
    wild = replace(path, sigma=path.sigma * 400.0)
    with pytest.raises(ValueError, match="reach zero"):
        for t in range(400):
            intraday(wild, t)
