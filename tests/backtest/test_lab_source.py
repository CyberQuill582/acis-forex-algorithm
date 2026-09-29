"""The lab as a harness tick source: one path, one clock, one financing model, one cost model
(R1.1 C-4/C-5/C-6/C-7)."""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from config.schemas import load_config
from core.data.fx_clock import in_weekend
from tests.backtest.carry import financing_charge
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.financing import make_financing
from tests.backtest.lab_intraday import day_bounds
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.lab_source import LabTickSource, lab_config, lab_names
from tests.backtest.lab_theory import detection_power
from tests.optimizer_fixtures import CapturingLogger

ROOT = Path(__file__).resolve().parents[2]


def _source(**kw) -> LabTickSource:
    return LabTickSource(generate(LabSpec(seed=2, days=400, n_inst=4, **kw)), first_mids=1.1)


def test_ticks_are_quotes_on_the_fx_clock_and_close_on_the_daily_bar() -> None:
    src = _source()
    name = lab_names(4)[1]
    start, end = day_bounds(src.path.dates[3].astype(object))
    ticks = list(src.load(name, start, end))
    assert ticks and all(t.bid < t.ask and not in_weekend(t.event_time) for t in ticks)
    assert all(start <= t.event_time < end for t in ticks) and src.provenance == "synthetic"
    day = src._day(3)                                   # the last grid mid is the daily close
    prev = src.path.mids(1.1)[2, 1]
    assert prev * (1.0 + day.inc[1].sum()) == pytest.approx(src.path.mids(1.1)[3, 1], rel=1e-12)


def test_loading_is_windowed_and_split_invariant() -> None:
    src, name = _source(), lab_names(4)[0]
    start = day_bounds(src.path.dates[5].astype(object))[0]
    end, cut = start + timedelta(days=4), start + timedelta(days=1, hours=7, seconds=13)
    whole = [(t.event_time, t.bid) for t in src.load(name, start, end)]
    split = [(t.event_time, t.bid) for t in src.load(name, start, cut)] + \
            [(t.event_time, t.bid) for t in src.load(name, cut, end)]
    assert whole == split and len(whole) > 1000


def test_the_real_loader_takes_the_lab_and_rejects_its_spread_spikes() -> None:
    """The spikes above the template's max_plausible_spread exercise the rejection path on purpose."""
    src, name = _source(), lab_names(4)[2]
    start, end = day_bounds(src.path.dates[1].astype(object))[0], day_bounds(src.path.dates[20].astype(object))[1]
    loader = BacktestDataLoader({"lab": src}, CapturingLogger())
    got = loader.load(source="lab", instrument=name, start=start, end=end, max_plausible_spread=0.0005)
    assert got.ticks and got.rejected > 0 and got.weekend_dropped == 0


def test_truth_is_the_drift_in_force_now_never_the_next_days() -> None:
    src = LabTickSource(generate(LabSpec(seed=2, days=400, n_inst=4, effect=Effect(trend_sharpe=0.5))))
    name = lab_names(4)[3]
    for t in (10, 11, 250):
        open_, close = day_bounds(src.path.dates[t].astype(object))
        assert src.truth(name, open_) == src.path.m[t, 3]
        assert src.truth(name, close - timedelta(seconds=1)) == src.path.m[t, 3]
    with pytest.raises(ValueError, match="not inside"):
        src.truth(name, day_bounds(src.path.dates[4].astype(object))[1] + timedelta(hours=10))  # a Saturday
    assert _source().truth(name, day_bounds(src.path.dates[7].astype(object))[0]) == 0.0


def test_the_harness_books_exactly_the_labs_financing() -> None:
    """C-6: make_financing over the lab's own rate table charges value x accrual on every
    rollover, so a financed long earns r and nothing more (the broker fee aside)."""
    src = _source()
    hook = make_financing(src.rate_table(), broker_fee_pct=Decimal("0"))
    for t in (0, 2, 3, 9):                                     # a Wednesday (x3) among them
        night = src.path.dates[t].astype(object)
        for i, name in enumerate(lab_names(4)):
            charge = financing_charge(instrument=name, direction=1, value=Decimal("1000"),
                                      nights=[night], rate=hook)
            assert float(charge) == pytest.approx(1000 * src.path.accrual[t, i], rel=1e-9, abs=1e-12)


def test_a_spot_only_grader_would_see_a_carry_edge_the_financed_one_does_not() -> None:
    """C-6's falsifier: anti-carry earns the accrual in spot units alone (t > 3); with the
    financing the harness books, it earns r, which is 0 on the null."""
    spot_only, financed = [], []
    for seed in range(8):
        p = generate(LabSpec(seed=seed, days=1260))
        pos = -np.sign(p.rate)
        spot_only.extend((pos * p.spot).mean(axis=0))
        financed.extend((pos * (p.spot + p.accrual)).mean(axis=0))
    t = lambda v: np.mean(v) / (np.std(v, ddof=1) / math.sqrt(len(v)))
    assert t(spot_only) > 3.0 and abs(t(financed)) < 3.0, (t(spot_only), t(financed))


def test_the_lab_config_copies_a_declared_cost_block_and_touches_no_real_file() -> None:
    """C-7: no friction constant exists in a lab module; the lab instruments carry EUR_USD's."""
    cfg = load_config(ROOT / "config")
    names = lab_names(3)
    lab = lab_config(cfg, names)
    assert set(lab.instruments.enabled) == set(names)
    tpl = cfg.instruments.instruments["EUR_USD"]
    for n in names:
        spec = lab.instruments.instruments[n]
        assert spec.costs == tpl.costs and spec.max_plausible_spread == tpl.max_plausible_spread
        assert (spec.base_ccy, spec.quote_ccy) == (n[:3], "USD")
    assert not set(names) & set(load_config(ROOT / "config").instruments.instruments)


def test_the_power_statement_matches_r1cs_calibration_table() -> None:
    """C-5: R1-C §2.8's pooled theory 0.828 over 2.8 years has power 39.8%, over 13.3 years 91.5%."""
    assert detection_power(0.828, 2.8) == pytest.approx(0.398, abs=0.01)
    assert detection_power(0.828, 13.3) == pytest.approx(0.915, abs=0.01)
    assert detection_power(0.0, 5.0) == pytest.approx(0.05)
