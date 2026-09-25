"""T1 + T2 at every decision point of each decision-making component (GAP-P12D-65).

Each component reruns on a short tape once per cut, and the cuts are EVERY decision point of
that component (every tick, or every bar), never a sample: a sampled sweep catches a 5% one-bar
peek 15-67% of the time (VALIDATOR §7.2). Each sweep also asserts it compared real decisions,
so a green result can never come from an empty run. The guard's bite is proven separately
(test_leakage_controls.py, T7).
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from config.schemas import PairRelationship
from core.data.bars import BarAggregator, DailyBarAggregator
from core.optimizer.fitness import trade_path
from core.regime.regime_types import LiqState, RegimeContext, RegimeType, VolClass
from core.signals.agon import AGON
from core.signals.canonical import register_canonical
from core.signals.provenance import ProvenanceStore
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.evolve_step import cost_model, evolve_fold
from tests.backtest.harness import FoldData
from tests.backtest.leakage import Decision, future_perturbation, truncation
from tests.backtest.leakage_engine import NullLogger, signal_decisions
from tests.backtest.leakage_markets import PerturbedMarket
from tests.backtest.leakage_tapes import (bar_cuts, bar_tape, bar_tape_variant, tick_tape,
                                          tick_tape_variant, trade_path_decisions)
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec, build_nvma, label_bars
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket
from tests.backtest.test_evolve_step import _cfg
from tests.backtest.tick_stream import build_factory, market_states
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import T0, TEST_COSTS, bars_from_closes, make_paramset, zigzag_closes
from tests.signals_fixtures import mk_state, signals_cfg

UTC = timezone.utc
US = timedelta(microseconds=1)


def _both(reference, run, cuts, min_compared: int):
    t2 = future_perturbation(reference, lambda t: run(t, "perturb"), cuts)
    t1 = truncation(reference, lambda t: run(t, "truncate"), cuts)
    assert t2.clean and t1.clean, (t2.summary(), t1.summary())
    assert t2.compared >= min_compared and t1.compared >= min_compared, (t2.summary(), t1.summary())


# -- the bar builder: every tick is a cut ------------------------------------------------- #

def _bars(tape, make) -> list[Decision]:
    """A completed bar may use every tick before the one that completes it."""
    agg, out = make(), []
    for i, (ts, mid, spread) in enumerate(zip(tape.ts, tape.mid, tape.spread)):
        bar = agg.add(ts, mid, spread)
        if bar is not None:
            out.append(Decision(tape.ts[i - 1], ts, "bar", (bar.ts_open, bar.open, bar.high, bar.low,
                                                            bar.close, bar.spread, bar.duration_s)))
    return out


@pytest.mark.parametrize("make,gap_s,n", [(lambda: BarAggregator(60), (5, 40), 160),
                                          (DailyBarAggregator, (2400, 10800), 150)])
def test_the_bar_builder_decides_nothing_from_later_ticks(make, gap_s, n) -> None:
    tape = tick_tape(datetime(2026, 7, 6, 19, 0, tzinfo=UTC), n, seed=5, gap_s=gap_s)
    ref = _bars(tape, make)
    assert len(ref) >= 8
    _both(ref, lambda t, mode: _bars(tick_tape_variant(tape, t, mode), make), tape.ts[1:], 200)


# -- the regime labeller: the real factory and NVMA, every tick is a cut ------------------- #

LABEL_START = datetime(2014, 1, 6, 8, 0, tzinfo=UTC)       # a Monday, London open: one session throughout
LABEL_TICKS = 130


def _small_regime(acis_config):
    """Production regime logic on the smallest windows the schema allows (hurst >= 100), so a
    150-tick tape classifies; window LENGTHS do not change what is causal."""
    regime = acis_config.system.regime.model_copy(update={"hurst_window": 100, "bb_window": 20,
                                                          "atr_periods": (5, 10, 20)})
    return acis_config.model_copy(update={"system": acis_config.system.model_copy(update={"regime": regime})})


def _labels(cfg, market, *, cycle_s: float = 300.0, labeller=label_bars) -> list[Decision]:
    factory = build_factory(cfg, ["EUR_USD"])
    engine = build_nvma(cfg, factory, NullLogger())
    out: list[Decision] = []
    classify = engine.classify

    def tapped(st):
        c = classify(st)
        out.append(Decision(st.timestamp, st.timestamp, "regime", (c.regime.value, c.trend_direction,
                   c.volatility_class.value, c.liquidity_state.value, c.tradeable, c.confidence)))
        return c
    engine.classify = tapped
    pulled: list[datetime] = []

    def states():                                   # the factory is built LAZILY, tick by tick
        for st in market_states(cfg=cfg, loader=BacktestDataLoader({market.name: market}, NullLogger()),
                                factory=factory, source=market.name, instruments=["EUR_USD"],
                                start=LABEL_START, end=LABEL_START + timedelta(minutes=LABEL_TICKS)):
            pulled.append(st.timestamp)
            yield st
    for _, b in labeller(states(), engine, cycle_s=cycle_s, bar_seconds=60):
        out.append(Decision(b.ts + timedelta(seconds=60) - US, pulled[-1], "label",
                            (b.ts, b.open, b.high, b.low, b.close, b.spread, b.regime.value)))
    return out


def test_the_regime_labeller_decides_nothing_from_later_ticks(acis_config) -> None:
    cfg = _small_regime(acis_config)
    spec = MarketSpec("planted", datetime(2014, 1, 6, tzinfo=UTC), 1, (("EUR_USD", 1.10),), tick_seconds=60)
    ref = _labels(cfg, SyntheticMarket(spec))
    classified = {d.payload[-1] for d in ref if d.kind == "label"} - {"UNCLASSIFIED"}
    assert len(classified) >= 2, classified                  # real regimes, not only warm-up
    cuts = [LABEL_START + timedelta(minutes=k) for k in range(1, LABEL_TICKS)]
    _both(ref, lambda t, mode: _labels(cfg, PerturbedMarket(spec, t, mode)), cuts, 5000)


# -- AGON: every tick is a cut; the regime and the tick rate are future data too ----------- #

AGON_START = datetime(2026, 7, 6, 20, 30, tzinfo=UTC)      # crosses the 17:00 New York rollover (21:00 UTC)
SCHEDULE = (RegimeType.STRONG_TREND_UP, RegimeType.BREAKOUT_IMMINENT, RegimeType.RANGING_TIGHT,
            RegimeType.WEAK_TREND_DOWN, RegimeType.MEAN_REVERTING, RegimeType.POST_BREAKOUT,
            RegimeType.RANGING_WIDE, RegimeType.STRONG_TREND_DOWN)
PAIR = {"eu_uj": PairRelationship(legs=("EUR_USD", "USD_JPY"), expected_sign=-1, correlation_window=10,
                                  method="pearson_log_returns", stability_floor=0.2, zscore_window=10)}


def _regime(k: int, ts: datetime, instrument: str, shift: int) -> RegimeContext:
    return RegimeContext(regime=SCHEDULE[(k // 4 + shift) % len(SCHEDULE)], trend_direction=1,
                         volatility_class=(VolClass.HIGH, VolClass.MEDIUM)[k % 2],
                         liquidity_state=(LiqState.DEEP, LiqState.NORMAL)[k // 3 % 2], tradeable=True,
                         regime_stability_score=0.9, estimated_half_life_seconds=600, confidence=0.9,
                         timestamp=ts, instrument=instrument, inputs_snapshot=MappingProxyType({}))


def agon_tapes() -> dict:
    base = tick_tape(AGON_START, 64, seed=11, gap_s=(60, 60))
    jpy = tick_tape(AGON_START, 64, seed=12, gap_s=(60, 60))
    jpy.mid = [100.0 * m for m in jpy.mid]
    jpy.spread = [100.0 * s for s in jpy.spread]
    return {"EUR_USD": base, "USD_JPY": jpy}


def _agon(store, tapes, cut=None, median=None) -> list[Decision]:
    """`median` is AGON's session-median channel (production: the live factory's medians);
    by default a constant, so nothing reaches AGON but the ticks it is fed."""
    agon = AGON(signals_cfg(), PAIR, store, median or (lambda inst, sess, kind: 10.0), NullLogger())
    for inst in tapes:
        for i in range(262):                               # >= the 252-day lookback + 1, >= min history 260
            agon.observe_daily_close(inst, (1.0 if inst == "EUR_USD" else 100.0) * (1 + 0.001 * i))
    params = make_paramset(mean_rev_zscore_entry=1.5)
    out = []
    eu, uj = tapes["EUR_USD"], tapes["USD_JPY"]
    for k in range(len(eu)):
        for inst, tape in (("EUR_USD", eu), ("USD_JPY", uj)):
            ts = tape.ts[k]
            st = mk_state(instrument=inst, mid=tape.mid[k], spread=tape.spread[k],
                          velocity=tape.velocity[k], ts=ts)
            agon.observe(st)
            future = cut is not None and ts >= cut           # the regime feed's future changes too
            sigs = agon.generate(st, _regime(k, ts, inst, 3 if future else 0), params, ts)
            out += signal_decisions(ts, sigs)
    return out


def test_agon_decides_nothing_from_later_ticks(tmp_path) -> None:
    store = ProvenanceStore(tmp_path / "provenance.db", 90, NullLogger())
    register_canonical(store, AGON_START)
    tapes = agon_tapes()
    base = tapes["EUR_USD"]
    ref = _agon(store, tapes)
    strategies = {d.payload[6] for d in ref}
    assert len(ref) >= 60 and len(strategies) >= 3, strategies

    def run(t, mode):
        variant = {i: tick_tape_variant(tp, t, mode) for i, tp in tapes.items()}
        return _agon(store, variant, t if mode == "perturb" else None)
    _both(ref, run, base.ts[1:], 1500)


# -- the fitness simulator: every open and every close is a cut --------------------------- #

def test_the_fitness_simulator_decides_nothing_from_later_bars() -> None:
    bars = bar_tape(240, seed=21)
    params = make_paramset(max_holding_periods=12)

    def run(k, mode):
        return trade_path_decisions(trade_path(params, bar_tape_variant(bars, k, mode), TEST_COSTS, atr_period=14))
    ref = run(len(bars), "truncate")
    assert sum(d.kind == "exit" for d in ref) >= 8
    _both(ref, run, bar_cuts(len(bars)), 3000)


def test_no_gap_exit_is_decided_from_its_own_bars_later_data() -> None:
    """MEDIUM-2 / X2: on a gappy tape a gap exit is stamped at its bar's OPEN, so its price and
    PnL are compared at the cut between that open and the bar's close."""
    bars = bar_tape(240, seed=21, gap=3.0)
    params = make_paramset(max_holding_periods=12)

    def run(k, mode):
        return trade_path_decisions(trade_path(params, bar_tape_variant(bars, k, mode), TEST_COSTS, atr_period=14))
    ref = run(len(bars), "truncate")
    assert sum(t.exit_kind == "gap" for t in trade_path(params, bars, TEST_COSTS, atr_period=14)) >= 4
    _both(ref, run, bar_cuts(len(bars)), 3000)


# -- evolution: the fold's train end is the cut that matters ------------------------------- #

EVO_TRAIN_END = T0 + timedelta(minutes=500)


def evolution_tape() -> list:
    """A zigzag edge under noise: evolution stages a champion whose fitness sits BELOW the formula
    cap (0.754 < 0.8), and a champion survives a peek past the train end (MEDIUM-3: a saturated
    record, or a leaky run that stages nothing, gives T2 nothing to compare)."""
    rng = random.Random(4)
    return list(bars_from_closes([c + rng.gauss(0, 0.0009) for c in zigzag_closes(700)]))


def evolution_run(tmp_path, cfg, bars, *, peek: timedelta = timedelta(0)) -> tuple[list[Decision], dict]:
    """The real evolve_fold over a cache that DOES hold later bars (as a leaky cache would serve);
    `peek` > 0 plants the look-ahead: the cache serves bars up to `peek` past the requested end."""
    spec = LabelSpec(source="test", bar_seconds=60, cycle_s=120.0, regime_config="{}")
    fold = Fold(1, T0, EVO_TRAIN_END, EVO_TRAIN_END + timedelta(days=7), EVO_TRAIN_END + timedelta(days=365))
    costs = {i: cost_model(cfg, i) for i in ("EUR_USD", "USD_JPY")}

    class _Cache(LabelledBarCache):
        def history(self, instrument, regime, start, end, n):
            return super().history(instrument, regime, start, end + peek, n)
    cache = _Cache(tmp_path / f"evo-{uuid.uuid4().hex[:8]}", spec)
    for instrument in costs:
        cache.write(instrument, T0.year, bars)
    stager = SimpleNamespace(staged=[], stage=lambda p, now: stager.staged.append((p, now)))
    record = evolve_fold(SimpleNamespace(params=stager), FoldData(fold, ()), cfg=cfg, costs=costs,
                         cache=cache, instruments=list(costs), logger=NullLogger())
    return [Decision(EVO_TRAIN_END - US, EVO_TRAIN_END - US, "evolution",
                     (repr(sorted(record.items())), repr(stager.staged)))], record


def evolution_variant(bars, t: datetime, mode: str) -> list:
    return bar_tape_variant(bars, sum(1 for b in bars if b.ts < t), mode)


def test_evolution_decides_nothing_from_bars_after_its_train_end(tmp_path, acis_config) -> None:
    cfg, bars = _cfg(acis_config), evolution_tape()
    ref, record = evolution_run(tmp_path, cfg, bars)
    staged = record["regimes"]["STRONG_TREND_UP"]["candidates"][0]
    assert record["champions"] >= 1 and staged["fitness"] < 0.8          # not vacuous, not saturated
    _both(ref, lambda t, mode: evolution_run(tmp_path, cfg, evolution_variant(bars, t, mode))[0],
          [EVO_TRAIN_END, EVO_TRAIN_END + timedelta(hours=1)], 2)
