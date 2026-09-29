"""Intraday ticks from the daily lab are exact, on the FX clock, and plant no edge (R1.1 C-4;
ACIS-09 C-BT-12, GAP-P12D-92). The power checks rerun R1-C's receipts (evidence/R1C/probe_intraday.py):
independent per-instrument bridges must show the spurious lead-lag edge the joint bridge removes."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

from core.data.fx_clock import in_weekend, rollover_utc
from tests.backtest.lab_intraday import HOUR_VAR, bridge, day_bounds, intraday
from tests.backtest.lab_market import Effect, LabSpec, generate, permuted

MID = 12 * 60                                   # the 12th hour of the FX day on a 1-minute grid


def _t(values) -> float:
    v = np.asarray(values, float)
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(v.size)))


def test_each_days_ticks_sum_to_its_spot_return_on_every_kind() -> None:
    base = generate(LabSpec(seed=4, days=400, effect=Effect(trend_sharpe=0.5)))
    for path in (base, permuted(base), generate(LabSpec(seed=4, days=400))):
        for t in (0, 1, 57, 399):
            day = intraday(path, t)
            assert np.allclose(day.inc.sum(axis=1), path.spot[t], rtol=0, atol=1e-15), (path.kind, t)


def test_the_day_runs_rollover_to_rollover_and_never_touches_the_weekend() -> None:
    monday = date(2012, 1, 2)
    assert day_bounds(monday)[0] == rollover_utc(monday - timedelta(days=1))   # opens Sunday 17:00 NY
    path = generate(LabSpec(seed=1, days=400))
    lengths = set()
    for t in range(0, 400, 7):
        day = intraday(path, t)
        lengths.add(day.inc.shape[1])
        assert not any(in_weekend(day.time(k)) for k in (0, day.inc.shape[1] - 1))
    assert lengths >= {1440} and lengths <= {1380, 1440, 1500}          # DST days are 23 or 25 hours


def test_the_bridge_is_exact_and_a_zero_pinned_day_is_the_old_defect() -> None:
    """R1-C (2): 'go with the day so far to the close' averages 0 on the lab null (per-day means,
    so the cross-section's correlation is not counted as independent samples); the same rule on
    days pinned to zero, GAP-P12D-91's defect at day scale, loses at t < -30."""
    path, rng = generate(LabSpec(seed=3, days=1500, rho=0.5)), np.random.default_rng(99)
    fair, pinned = [], []
    for t in range(1500):
        y = intraday(path, t).inc / path.sigma[t][:, None]
        fair.append(np.mean(np.sign(y[:, :MID].sum(axis=1)) * y[:, MID:].sum(axis=1)))
        w = np.full(y.shape[1], 1.0 / y.shape[1])
        z = bridge(rng, w, np.ones((y.shape[0], 1)), np.zeros((y.shape[0], 1)), y.shape)
        pinned.append(np.mean(np.sign(z[:, :MID].sum(axis=1)) * z[:, MID:].sum(axis=1)))
    assert abs(_t(fair)) < 3.0 and _t(pinned) < -30.0, (_t(fair), _t(pinned))


def test_joint_bridges_plant_no_lead_lag_edge_and_independent_ones_would() -> None:
    """R1-C (3), the pairs trap: 'long i when its positively correlated j led it so far'."""
    path = generate(LabSpec(seed=3, days=1500, rho=0.5))
    same = np.flatnonzero(np.sign(path.loadings) == np.sign(path.loadings[0]))
    i, j = same[0], same[1]
    edge = {True: [], False: []}
    for t in range(1500):
        for joint in (True, False):
            y = intraday(path, t, joint=joint).inc / path.sigma[t][:, None]
            edge[joint].append(np.sign(y[j, :MID].sum() - y[i, :MID].sum()) * y[i, MID:].sum())
    assert abs(_t(edge[True])) < 3.0 and _t(edge[False]) > 4.0, (_t(edge[True]), _t(edge[False]))


def test_session_shape_and_the_rollover_spread_spike_are_what_the_knobs_declare() -> None:
    """Self-consistency, not a calibration: |move| by UTC hour follows sqrt(the hour profile),
    and the spread in the first minutes after the 17:00 open is well above an hour later."""
    path = generate(LabSpec(seed=1, days=400))
    by_hour, first, later = np.zeros(24), [], []
    for t in range(200):
        day = intraday(path, t)
        hours = (day.open.hour * 3600 + day.open.minute * 60 + np.arange(day.inc.shape[1]) * 60) // 3600 % 24
        by_hour += np.bincount(hours, weights=np.abs(day.inc / path.sigma[t][:, None]).mean(axis=0), minlength=24)
        first.append(day.spread[:, :5].mean())
        later.append(day.spread[:, 60:65].mean())
    assert np.corrcoef(by_hour, np.sqrt(HOUR_VAR))[0, 1] > 0.9
    assert np.mean(first) / np.mean(later) > 3.0
