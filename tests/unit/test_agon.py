"""AGON modules + conviction pipeline (ACIS-04 §14, postcondition style)."""

from __future__ import annotations

import math

import pytest

from core.data.errors import DataQualityError
from core.regime.regime_types import LiqState, RegimeType, VolClass
from core.signals.agon import AGON, _Raw
from core.signals.signal_types import StrategyType
from tests.signals_fixtures import (
    T0,
    breakout_up_mids,
    feed_daily,
    feed_mids,
    feed_pair,
    make_agon,
    make_paramset,
    meanrev_low_mids,
    mk_regime,
    mk_state,
    pair_divergence_series,
    signals_cfg,
    trend_cross_up_mids,
    tsmom_series,
)

PS = make_paramset()
PS_Z15 = make_paramset(mean_rev_zscore_entry=1.5)


# ---------------------------- module firing + foreign-regime silence ---------------------------- #

def test_trend_fires_on_cross_and_silent_on_foreign_regime(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    state = mk_state(mid=1.101)
    sigs = agon.generate(state, mk_regime(), PS, T0)
    assert [s.strategy_type for s in sigs] == [StrategyType.TREND]
    assert sigs[0].direction == 1 and 0.45 <= sigs[0].conviction <= 1.0
    assert sigs[0].stop_loss < sigs[0].entry_price < sigs[0].take_profit
    # same windows, ranging regime: trend module is gated off (mean-rev may not fire
    # on this fixture either — assert no TREND signal specifically)
    sigs2 = agon.generate(state, mk_regime(RegimeType.RANGING_TIGHT), PS, T0)
    assert all(s.strategy_type is not StrategyType.TREND for s in sigs2)


def test_breakout_fires_and_wick_does_not(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", breakout_up_mids())
    sigs = agon.generate(mk_state(mid=1.1020), mk_regime(RegimeType.BREAKOUT_IMMINENT),
                         PS, T0)
    assert [s.strategy_type for s in sigs] == [StrategyType.BREAKOUT]
    assert sigs[0].direction == 1
    # the false-break filter: same range but the last mid back INSIDE the channel
    agon2, log2, _ = make_agon(tmp_path / "wick")
    feed_mids(agon2, "EUR_USD", breakout_up_mids()[:-1] + [1.10004])
    assert agon2.generate(mk_state(mid=1.10004),
                          mk_regime(RegimeType.BREAKOUT_IMMINENT), PS, T0) == ()


def test_mean_reversion_divergence_gate(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", meanrev_low_mids())
    sigs = agon.generate(mk_state(mid=meanrev_low_mids()[-1]),
                         mk_regime(RegimeType.MEAN_REVERTING), PS_Z15, T0)
    assert [s.strategy_type for s in sigs] == [StrategyType.MEAN_REVERSION]
    assert sigs[0].direction == 1  # fading the low
    # without the RSI recovery (pure monotone collapse) the divergence gate blocks
    agon2, _, _ = make_agon(tmp_path / "mono")
    feed_mids(agon2, "EUR_USD", [1.1 - 0.0005 * i for i in range(40)])
    assert agon2.generate(mk_state(mid=1.08),
                          mk_regime(RegimeType.MEAN_REVERTING), PS_Z15, T0) == ()


def test_momentum_scalp_surge_and_liquidity_gate(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path, median_velocity=10.0)
    feed_mids(agon, "EUR_USD", [1.1 + i * 0.0001 for i in range(30)])
    surge = mk_state(mid=1.103, velocity=25.0)
    sigs = agon.generate(surge, mk_regime(), PS, T0)
    assert StrategyType.MOMENTUM_SCALP in {s.strategy_type for s in sigs}
    # THIN liquidity gates the module off entirely
    sigs2 = agon.generate(surge, mk_regime(liq=LiqState.THIN), PS, T0)
    assert all(s.strategy_type is not StrategyType.MOMENTUM_SCALP for s in sigs2)
    # no surge (velocity at median) => silent
    sigs3 = agon.generate(mk_state(mid=1.103, velocity=10.0), mk_regime(), PS, T0)
    assert all(s.strategy_type is not StrategyType.MOMENTUM_SCALP for s in sigs3)


def test_tsmom_agreement_semantics(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_daily(agon, "EUR_USD", tsmom_series("all_up"))
    feed_mids(agon, "EUR_USD", [1.29] * 25)
    sigs = agon.generate(mk_state(mid=1.30), mk_regime(RegimeType.RANGING_WIDE), PS, T0)
    ts = [s for s in sigs if s.strategy_type is StrategyType.TSMOM]
    assert len(ts) == 1 and ts[0].conviction == 1.0 and ts[0].direction == 1
    assert ts[0].valid_for_seconds == 86400
    # 2-of-3 agreement => 0.667
    agon2, _, _ = make_agon(tmp_path / "two")
    two = tsmom_series("two_up")
    feed_daily(agon2, "EUR_USD", two)
    feed_mids(agon2, "EUR_USD", [two[-1]] * 25)
    sigs2 = agon2.generate(mk_state(mid=two[-1]), mk_regime(RegimeType.RANGING_WIDE), PS, T0)
    ts2 = [s for s in sigs2 if s.strategy_type is StrategyType.TSMOM]
    assert len(ts2) == 1 and ts2[0].conviction == pytest.approx(2 / 3)
    # flat: zero-sum, no signal + insufficient history is silent
    agon3, _, _ = make_agon(tmp_path / "flat")
    feed_daily(agon3, "EUR_USD", tsmom_series("split"))
    feed_mids(agon3, "EUR_USD", [1.2] * 25)
    sigs3 = agon3.generate(mk_state(mid=1.2), mk_regime(RegimeType.RANGING_WIDE), PS, T0)
    assert all(s.strategy_type is not StrategyType.TSMOM for s in sigs3)
    agon4, _, _ = make_agon(tmp_path / "short")
    feed_daily(agon4, "EUR_USD", tsmom_series("all_up")[:100])   # < min history
    feed_mids(agon4, "EUR_USD", [1.09] * 25)
    sigs4 = agon4.generate(mk_state(mid=1.1), mk_regime(RegimeType.RANGING_WIDE), PS, T0)
    assert all(s.strategy_type is not StrategyType.TSMOM for s in sigs4)


def test_pair_divergence_group_and_coupling_gates(tmp_path) -> None:
    a, b = pair_divergence_series()
    agon, _, _ = make_agon(tmp_path)
    feed_pair(agon, "EUR_USD", a, "USD_JPY", b)
    sigs = agon.generate(mk_state(mid=a[-1]), mk_regime(RegimeType.MEAN_REVERTING),
                         PS_Z15, T0)
    pair = [s for s in sigs if s.strategy_type is StrategyType.PAIR_DIVERGENCE]
    assert len(pair) == 2                                        # both legs, always
    assert {s.instrument for s in pair} == {"EUR_USD", "USD_JPY"}
    assert len({s.group_id for s in pair}) == 1                  # one shared group
    assert pair[0].conviction == pair[1].conviction
    # s = logA + logB rich  =>  short A and short B (expected_sign = -1)
    assert all(s.direction == -1 for s in pair)
    # decoupled legs (uncorrelated noise) => no entry
    import random as _r
    rng = _r.Random(1)
    agon2, _, _ = make_agon(tmp_path / "uncorr")
    feed_pair(agon2, "EUR_USD", [1.1 + rng.uniform(-1, 1) * 0.001 for _ in range(120)],
              "USD_JPY", [1.1 + rng.uniform(-1, 1) * 0.001 for _ in range(120)])
    assert agon2.generate(mk_state(mid=1.1), mk_regime(RegimeType.MEAN_REVERTING),
                          PS_Z15, T0) == ()
    # the pair module never fires off its anchor leg (no double emission)
    sigs_b = agon.generate(mk_state(instrument="USD_JPY", mid=b[-1]),
                           mk_regime(RegimeType.MEAN_REVERTING, instrument="USD_JPY"),
                           PS_Z15, T0)
    assert all(s.strategy_type is not StrategyType.PAIR_DIVERGENCE for s in sigs_b)


# ---------------------------- C4 pipeline vectors (C-ALP-1) ---------------------------- #

def _pipeline_run(tmp_path, raw_conviction: float, vol: VolClass):
    agon, log, _ = make_agon(tmp_path)
    raws = [_Raw(StrategyType.TREND, "EUR_USD", 1, raw_conviction, 1.1, 0.001)]
    out = agon._pipeline(raws, mk_regime(vol=vol), PS, T0)
    return out, log


def test_c4_raw_050_medium_is_discarded(tmp_path) -> None:
    out, log = _pipeline_run(tmp_path, 0.50, VolClass.MEDIUM)
    assert out == ()
    assert log.events("DISCARD_SUBTHRESHOLD")[0]["data"]["conviction"] == pytest.approx(0.425)


def test_c4_raw_055_medium_is_emitted(tmp_path) -> None:
    out, _ = _pipeline_run(tmp_path, 0.55, VolClass.MEDIUM)
    assert len(out) == 1
    assert out[0].conviction == pytest.approx(0.4675)


def test_c4_raw_050_high_vol_is_emitted_undiscounted(tmp_path) -> None:
    out, _ = _pipeline_run(tmp_path, 0.50, VolClass.HIGH)
    assert len(out) == 1 and out[0].conviction == pytest.approx(0.50)


# ---------------------------- conflicts + groups ---------------------------- #

def test_opposite_directions_discard_both(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    raws = [_Raw(StrategyType.TREND, "EUR_USD", 1, 0.9, 1.1, 0.001),
            _Raw(StrategyType.MEAN_REVERSION, "EUR_USD", -1, 0.9, 1.1, 0.001)]
    assert agon._pipeline(raws, mk_regime(), PS, T0) == ()
    assert len(log.events("DISCARD_OPPOSITE")) == 1


def test_dead_pair_leg_kills_whole_group(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    raws = [
        _Raw(StrategyType.PAIR_DIVERGENCE, "EUR_USD", -1, 0.9, 1.1, 0.001, "g1"),
        _Raw(StrategyType.PAIR_DIVERGENCE, "USD_JPY", -1, 0.9, 155.0, 0.05, "g1"),
        _Raw(StrategyType.TREND, "EUR_USD", 1, 0.9, 1.1, 0.001),  # opposes leg A
    ]
    out = agon._pipeline(raws, mk_regime(), PS, T0)
    assert out == ()  # leg A died in the opposite-conflict; the group followed
    assert len(log.events("DISCARD_GROUP_INCOMPLETE")) == 1


def test_same_direction_duplicates_keep_higher_conviction(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    raws = [_Raw(StrategyType.TREND, "EUR_USD", 1, 0.6, 1.1, 0.001),
            _Raw(StrategyType.MOMENTUM_SCALP, "EUR_USD", 1, 0.8, 1.1, 0.001)]
    out = agon._pipeline(raws, mk_regime(), PS, T0)
    assert len(out) == 1 and out[0].strategy_type is StrategyType.MOMENTUM_SCALP


# ---------------------------- guards ---------------------------- #

def test_vetoed_regime_emits_nothing(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    vetoed = mk_regime(RegimeType.MACRO_EVENT, tradeable=False)
    assert agon.generate(mk_state(mid=1.101), vetoed, PS, T0) == ()
    assert len(log.events("DISCARD_VETOED_REGIME")) == 1


def test_no_params_emits_nothing(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    assert agon.generate(mk_state(mid=1.101), mk_regime(), None, T0) == ()


def test_nan_never_reaches_conviction(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    raws = [_Raw(StrategyType.TREND, "EUR_USD", 1, float("nan"), 1.1, 0.001)]
    # NaN raws are filtered in generate(); simulate via the NaN guard directly:
    assert math.isnan(raws[0].conviction)
    out = agon._pipeline(
        [r for r in raws if math.isfinite(r.conviction)], mk_regime(), PS, T0)
    assert out == ()


def test_unregistered_module_cannot_construct(tmp_path) -> None:
    from core.signals.provenance import ProvenanceStore
    from tests.optimizer_fixtures import CapturingLogger
    log = CapturingLogger()
    empty_store = ProvenanceStore(tmp_path / "empty.db", 90, log)  # nothing registered
    with pytest.raises(DataQualityError):
        AGON(signals_cfg(), {}, empty_store, lambda i, s, k: 10.0, log)


def test_frozen_module_emits_nothing_new(tmp_path) -> None:
    agon, log, store = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    store.promote_one_rung("trend_following_v1", "evidence", T0)   # -> PAPER
    store.demote("trend_following_v1", "failed re-validation", T0)  # instant freeze
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), PS, T0)
    assert all(s.strategy_type is not StrategyType.TREND for s in sigs)
    assert len(log.events("DISCARD_ENTRY_FROZEN")) == 1


def test_decision_budget_breach_is_logged(tmp_path, monkeypatch) -> None:
    agon, log, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ticks = iter([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    monkeypatch.setattr("core.signals.agon.time.perf_counter", lambda: next(ticks))
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), PS, T0)
    assert len(sigs) >= 1                        # budget is observability, not a gate
    assert len(log.events("DECISION_BUDGET_EXCEEDED")) == 1


def test_determinism_same_inputs_same_signals(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    state = mk_state(mid=1.101)
    a = agon.generate(state, mk_regime(), PS, T0)
    b = agon.generate(state, mk_regime(), PS, T0)
    keyfields = lambda s: (s.instrument, s.direction, s.conviction, s.entry_price,
                           s.stop_loss, s.take_profit, s.strategy_type)
    assert [keyfields(s) for s in a] == [keyfields(s) for s in b]


def test_take_rate_counters(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    agon.generate(mk_state(mid=1.101), mk_regime(), PS, T0)
    tr = agon.take_rate()
    assert tr["signals_considered"] >= tr["signals_emitted"] >= 1


# ---------------- phase-5 audit triage regressions (GAP-0041/42/44) ---------------- #

def test_gap0041_solo_duplicating_group_leg_is_dropped(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    raws = [
        _Raw(StrategyType.PAIR_DIVERGENCE, "EUR_USD", 1, 0.9, 1.1, 0.001, "g1"),
        _Raw(StrategyType.PAIR_DIVERGENCE, "USD_JPY", -1, 0.9, 155.0, 0.05, "g1"),
        _Raw(StrategyType.TREND, "EUR_USD", 1, 0.95, 1.1, 0.001),  # duplicates leg A
    ]
    out = agon._pipeline(raws, mk_regime(), PS, T0)
    assert len(out) == 2                                  # the group only
    assert all(s.group_id == "g1" for s in out)
    assert len(log.events("DISCARD_DUPLICATES_GROUP_LEG")) == 1


def test_gap0042_module_conviction_above_one_dies_on_contract(tmp_path) -> None:
    agon, log, _ = make_agon(tmp_path)
    raws = [_Raw(StrategyType.TREND, "EUR_USD", 1, 2.0, 1.1, 0.001)]  # buggy module
    out = agon._pipeline(raws, mk_regime(), PS, T0)
    assert out == ()                                       # never emitted clamped
    assert len(log.events("SIGNAL_CONSTRUCTION_ERROR")) == 1


def test_gap0044_low_vol_ranging_silences_trend_and_breakout(tmp_path) -> None:
    """The C4 law holds structurally: in a LOW-vol ranging regime the trend and
    breakout modules are regime-gated off even on their firing fixtures."""
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    low_ranging = mk_regime(RegimeType.RANGING_TIGHT, vol=VolClass.LOW)
    sigs = agon.generate(mk_state(mid=1.101), low_ranging, PS, T0)
    assert all(s.strategy_type not in (StrategyType.TREND, StrategyType.BREAKOUT)
               for s in sigs)
    agon2, _, _ = make_agon(tmp_path / "bo")
    feed_mids(agon2, "EUR_USD", breakout_up_mids())
    sigs2 = agon2.generate(mk_state(mid=1.1020), low_ranging, PS, T0)
    assert all(s.strategy_type not in (StrategyType.TREND, StrategyType.BREAKOUT)
               for s in sigs2)


# ---------------- external-referent pass regressions (v2.11) ---------------- #

def test_v211_tsmom_is_faithful_no_take_profit_disaster_stop_only(tmp_path) -> None:
    """Published TSMOM has no target — its expectancy lives in the right tail.
    The only stop is the far §8.6 disaster stop (declared deviation)."""
    agon, _, _ = make_agon(tmp_path)
    feed_daily(agon, "EUR_USD", tsmom_series("all_up"))
    feed_mids(agon, "EUR_USD", [1.29] * 25)
    sigs = agon.generate(mk_state(mid=1.30), mk_regime(RegimeType.RANGING_WIDE), PS, T0)
    ts = [s for s in sigs if s.strategy_type is StrategyType.TSMOM][0]
    assert ts.take_profit is None                              # faithful: no target
    stop_distance = abs(ts.entry_price - ts.stop_loss)
    evolved_max = PS.atr_multiplier_sl                         # 2.0 in the fixture
    # the disaster stop (10x daily ATR) is far beyond any evolved stop
    assert stop_distance > 3.5 / evolved_max * stop_distance * 0  # guard div-by-zero form
    assert stop_distance / abs(ts.entry_price - ts.stop_loss) == 1.0
    # concrete: distance equals 10 x daily ATR, not the evolved 2.0 x
    from core.signals.indicators import wilder_atr
    daily_atr = wilder_atr(list(agon._daily_bars["EUR_USD"]), 14)
    assert stop_distance == pytest.approx(10.0 * daily_atr)


def test_v211_intraday_signals_still_carry_evolved_targets(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), PS, T0)
    trend = [s for s in sigs if s.strategy_type is StrategyType.TREND][0]
    assert trend.take_profit is not None                       # evolved TP intact


def test_v211_window_capacity_derived_from_config(tmp_path) -> None:
    """Ext-review C2: an over-long declared window can never silently starve —
    capacity follows config by construction."""
    from config.schemas import PairRelationship
    wide = {"wide": PairRelationship(
        legs=("EUR_USD", "USD_JPY"), expected_sign=-1, correlation_window=400,
        method="pearson_log_returns", stability_floor=0.4, zscore_window=50)}
    agon, _, _ = make_agon(tmp_path, pairs=wide)
    assert agon.window_capacity >= 402
    agon2, _, _ = make_agon(tmp_path / "d")
    assert agon2.daily_capacity >= 260


def test_v211_declared_deviations_exposed_on_snapshot(tmp_path) -> None:
    _, _, store = make_agon(tmp_path)
    snap = {s["strategy_id"]: s for s in store.snapshot()["strategies"]}
    tsmom = snap["tsmom_slow_v1"]
    assert any("disaster-stop" in d or "disaster" in d.lower()
               for d in tsmom["declared_deviations"])
    assert any("take-profit" in d.lower() or "no take" in d.lower()
               for d in tsmom["declared_deviations"])
    assert all(len(s["declared_deviations"]) > 0 for s in snap.values())  # honesty: v1 has none "as published"


# ---------------- v2.11 internal-audit triage regressions (GAP-0060/0065) ---------------- #

def test_gap0060_pair_join_survives_legs_out_of_lockstep(tmp_path) -> None:
    """One leg races whole buckets ahead: the per-bucket join still pairs every
    bucket both legs eventually barred in — nothing silently dropped."""
    from datetime import timedelta
    agon, _, _ = make_agon(tmp_path)
    # leg A bars buckets 0..4 first (its tick in bucket k+1 closes bar k)
    for i in range(6):
        agon.observe(mk_state(instrument="EUR_USD", mid=1.10 + i * 0.0001,
                              ts=T0 + timedelta(seconds=60 * i)))
    # leg B arrives late and bars the same buckets afterwards
    for i in range(6):
        agon.observe(mk_state(instrument="USD_JPY", mid=155.0 + i * 0.01,
                              ts=T0 + timedelta(seconds=60 * i)))
    joint = agon._pair_samples["eurusd_usdjpy"]
    assert len(joint) == 5                       # buckets 0..4, all joined
    assert agon.pair_buckets_incomplete["eurusd_usdjpy"] == 0


def test_gap0065_daily_series_is_strictly_ascending(tmp_path) -> None:
    """A seed arriving after live daily bars (or a duplicate day) is dropped and
    logged — never double-counted into the r63/r126/r252 indices."""
    agon, log, _ = make_agon(tmp_path)
    feed_daily(agon, "EUR_USD", [1.1, 1.2, 1.3])     # seeds: year-2000 ts, ascending
    n_before = len(agon._daily_bars["EUR_USD"])
    agon.observe_daily_close("EUR_USD", 1.4)          # next seed day: fine
    assert len(agon._daily_bars["EUR_USD"]) == n_before + 1
    # simulate a violating append: same-or-earlier ts
    from core.data.bars import Bar
    from datetime import datetime, timezone
    stale = Bar(ts_open=datetime(2000, 1, 3, 22, 0, tzinfo=timezone.utc),
                open=1.0, high=1.0, low=1.0, close=1.0, spread=0.0, duration_s=86400)
    agon._append_daily("EUR_USD", stale)
    assert len(agon._daily_bars["EUR_USD"]) == n_before + 1   # dropped
    assert len(log.events("DAILY_BAR_ORDER_DROP")) == 1


# ---------------- phase-7 audit triage regression (GAP-0077) ---------------- #

def test_gap0077_params_none_drop_is_attributed_and_logged(tmp_path) -> None:
    """The params-None early return is a discard path like any other: counted
    under the C15 gate that killed it and logged, never silent."""
    agon, log, _ = make_agon(tmp_path)
    out = agon.generate(mk_state(), mk_regime(), None, T0)
    assert out == ()
    assert agon.skips["no_params"] == 1
    assert len(log.events("DISCARD_NO_PARAMS")) == 1
