"""T7: the leakage guard must BITE (GAP-P12D-65; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md §7.3).

A check that finds nothing proves nothing until it has been shown to find something. Each
control plants the look-ahead the research names — a decision that reads the NEXT bar's
return — into a real component or through the real harness. T1 and T2 must both catch it, on
the same exhaustive grid the honest sweeps use (test_leakage_components.py), while the honest
configuration raises no alarm. Statistics cannot remove such a leak (Gençay, arXiv 2608.27734
§6.1: a leaky oracle keeps DSR = 1.00); T1/T2 are empirical detectors that exhibit the leaks
they trigger and certify nothing by their silence (Fonseca, arXiv 2607.04958 §8.3), which is
why every control must bite and why a silent sweep is never called clean.
"""

from __future__ import annotations

import inspect
import math
import random
import textwrap
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import core.optimizer.fitness as fitness
from core.data.bars import BarAggregator
from core.optimizer.param_types import LabelledBar
from core.regime.regime_types import RegimeType
from tests.backtest.leakage import Decision, future_perturbation, perturb_path, perturb_returns, truncation
from tests.backtest.leakage_engine import NullLogger
from tests.backtest.leakage_markets import (PerturbedMarket, decision_cuts, oracle_decisions,
                                            ticks_before)
from tests.backtest.leakage_tapes import bar_cuts, bar_tape, bar_tape_variant, trade_path_decisions
from tests.backtest.regime_labels import label_bars
from tests.backtest.synthetic_grade import START, plan
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket
from tests.backtest.test_evolve_step import _cfg
from tests.backtest.test_leakage_components import (AGON_START, EVO_TRAIN_END, LABEL_START, LABEL_TICKS, _agon,
                                                    _bars, _labels, _small_regime, agon_tapes, evolution_run,
                                                    evolution_tape, evolution_variant)
from tests.backtest.leakage_tapes import tick_tape, tick_tape_variant
from tests.optimizer_fixtures import TEST_COSTS, make_paramset

UTC = timezone.utc
PS = make_paramset(max_holding_periods=12)
REAL_EMA = fitness.ema_series


# -- the instrument itself ------------------------------------------------------------------ #

def test_the_perturbation_moves_every_later_price_and_its_scale_and_nothing_earlier() -> None:
    rng = random.Random(4)
    prices = [1.1]
    for _ in range(199):
        prices.append(prices[-1] * math.exp(rng.gauss(0, 1e-3)))
    for cut in (1, 57, 199):
        out = perturb_path(prices, cut)
        assert out[:cut] == prices[:cut] and len(out) == len(prices)
        assert all(a != b for a, b in zip(out[cut:], prices[cut:]))
    moves = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    tail = perturb_returns(moves, 100)[100:]
    assert sum(r * r for r in tail) == pytest.approx(4 * sum(r * r for r in moves[100:]))


def test_the_market_variants_leave_the_past_bit_identical_and_change_every_later_tick() -> None:
    spec = MarketSpec("planted", START, 3, (("EUR_USD", 1.10),), tick_seconds=300)
    cut = START + timedelta(days=1, hours=5, minutes=2)                  # between two ticks
    full = list(SyntheticMarket(spec).load("EUR_USD", spec.start, spec.end))
    pert = list(PerturbedMarket(spec, cut, "perturb").load("EUR_USD", spec.start, spec.end))
    trunc = list(PerturbedMarket(spec, cut, "truncate").load("EUR_USD", spec.start, spec.end))
    k = ticks_before(spec, cut)
    assert k == sum(t.event_time < cut for t in full) == len(trunc)
    assert [(t.event_time, t.bid, t.ask) for t in pert[:k]] == [(t.event_time, t.bid, t.ask) for t in full[:k]]
    data = lambda ticks: [(t.event_time, t.instrument, t.bid, t.ask, t.volume) for t in ticks]  # noqa: E731
    assert data(trunc) == data(full[:k]) and all(a.bid != b.bid for a, b in zip(pert[k:], full[k:]))
    names = {SyntheticMarket(spec).name, PerturbedMarket(spec, cut, "perturb").name,
             PerturbedMarket(spec, cut, "truncate").name, PerturbedMarket(spec, cut + timedelta(hours=1), "perturb").name}
    assert len(names) == 4 and {t.provider for t in trunc} == {PerturbedMarket(spec, cut, "truncate").name}
    assert len(PerturbedMarket(spec, cut, "truncate").returns("EUR_USD")) == k   # side channels cut too


def test_a_decision_cannot_claim_it_was_emitted_before_its_own_horizon() -> None:
    with pytest.raises(ValueError, match="before its horizon"):
        Decision(2.0, 1.0, "signal", ())


# -- controls that bite where the honest sweeps could only be silent (MEDIUM-3 / MEDIUM-4) ---- #
# Each goes RED if the perturbation is switched off (falsify.cases.json "perturbation off").

def test_evolution_that_peeks_past_its_train_end_is_caught_by_t2_alone(tmp_path, acis_config) -> None:
    """MEDIUM-3: before, T2 had never caught an evolution leak (the honest record was saturated
    and every leaky reference staged nothing). Here the peeking reference still stages a
    champion, and T2 on its own sees the record move with the perturbed future."""
    cfg, bars = _cfg(acis_config), evolution_tape()
    peek = timedelta(minutes=30)
    ref, record = evolution_run(tmp_path, cfg, bars, peek=peek)
    assert record["champions"] >= 1                                       # a real record to compare
    t2 = future_perturbation(ref, lambda t: evolution_run(tmp_path, cfg, evolution_variant(bars, t, "perturb"),
                                                          peek=peek)[0], [EVO_TRAIN_END])
    assert t2.violations, t2.summary()


class _ClosingTickAggregator(BarAggregator):
    """A completed bar whose close is the tick that COMPLETED it: one tick of the future."""

    def add(self, ts, mid, spread):
        bar = super().add(ts, mid, spread)
        return None if bar is None else replace(bar, close=mid, high=max(bar.high, mid), low=min(bar.low, mid))


def test_a_bar_builder_that_closes_on_the_completing_tick_is_caught_by_t2() -> None:
    tape = tick_tape(datetime(2026, 7, 6, 19, 0, tzinfo=UTC), 160, seed=5, gap_s=(5, 40))

    def make():
        return _ClosingTickAggregator(60)
    t2 = future_perturbation(_bars(tape, make), lambda t: _bars(tick_tape_variant(tape, t, "perturb"), make),
                             tape.ts[1:])
    assert t2.violations, t2.summary()


def _whole_tape_median(tapes):
    """AGON's session-median channel answered from the WHOLE tape (the F3 class at AGON's input:
    a median computed on a materialised stream)."""
    med = {i: sorted(tp.velocity)[len(tp.velocity) // 2] for i, tp in tapes.items()}
    return lambda instrument, session, kind: med[instrument]


def test_a_whole_tape_median_on_agons_channel_is_caught_by_t2(tmp_path) -> None:
    """MEDIUM-4: AGON is fed one tick at a time, so its own code has no path to a later datum;
    its only channels are its callbacks. A future-reading median there moves the scalp's surge
    ratio and conviction on EARLIER ticks, and T2 must see it. (T1 need not: a median of the
    truncated sample flips no earlier decision at these cuts, so it is reported, not asserted.)"""
    from core.signals.canonical import register_canonical
    from core.signals.provenance import ProvenanceStore
    store = ProvenanceStore(tmp_path / "provenance.db", 90, NullLogger())
    register_canonical(store, AGON_START)
    tapes = agon_tapes()

    def run(t, mode):
        variant = {i: tick_tape_variant(tp, t, mode) for i, tp in tapes.items()}
        return _agon(store, variant, t if mode == "perturb" else None, median=_whole_tape_median(variant))
    ref = _agon(store, tapes, median=_whole_tape_median(tapes))
    t2 = future_perturbation(ref, lambda t: run(t, "perturb"), tapes["EUR_USD"].ts[4::6])
    assert t2.violations, t2.summary()


# -- a centered indicator inside the real fitness simulator --------------------------------- #

def _sweep_fitness():
    bars = bar_tape(240, seed=21)

    def run(k, mode):
        return trade_path_decisions(fitness.trade_path(PS, bar_tape_variant(bars, k, mode), TEST_COSTS,
                                                       atr_period=14))
    ref = run(len(bars), "truncate")
    cuts = bar_cuts(len(bars))
    return (future_perturbation(ref, lambda t: run(t, "perturb"), cuts),
            truncation(ref, lambda t: run(t, "truncate"), cuts))


def test_an_ema_that_reads_the_next_close_is_caught_by_t1_and_t2(monkeypatch) -> None:
    monkeypatch.setattr(fitness, "ema_series", lambda c, p: REAL_EMA(list(c[1:]) + list(c[-1:]), p))
    t2, t1 = _sweep_fitness()
    assert t2.violations and t1.violations, (t2.summary(), t1.summary())


def test_a_five_percent_peek_is_caught_only_because_the_sweep_is_exhaustive(monkeypatch) -> None:
    """One bar in twenty, the fast EMA jumps by three times the NEXT bar's return. The sweep
    over every data point catches it; the fraction of cuts that do shows why a sample would
    not (the VALIDATOR measured 15-67% for sampled sweeps)."""
    def peek(c, p):
        out = REAL_EMA(c, p)
        if p != PS.ema_fast:
            return out
        return [e + (3 * (c[i + 1] - c[i]) if i % 20 == 7 and i + 1 < len(c) else 0.0) for i, e in enumerate(out)]
    monkeypatch.setattr(fitness, "ema_series", peek)
    t2, t1 = _sweep_fitness()
    assert t2.violations and t1.violations, (t2.summary(), t1.summary())
    assert len(t2.violations) / t2.cuts < 0.05 and len(t1.violations) / t1.cuts < 0.05


# -- a gap exit that reads its own bar's close (MEDIUM-2 / X2) ------------------------------- #

CLOSE_PEEK = (('exit_mid, kind = (bar.open, "gap") if bar.open < sl else (sl, "stop")',
               'exit_mid, kind = (min(max(bar.open, bar.close), sl), "gap") if bar.open < sl else (sl, "stop")'),
              ('exit_mid, kind = (bar.open, "gap") if bar.open > sl else (sl, "stop")',
               'exit_mid, kind = (max(min(bar.open, bar.close), sl), "gap") if bar.open > sl else (sl, "stop")'))


def _planted_trade_path(replacements):
    """The REAL trade_path with the audit's exact mutation planted in a copy of its source."""
    src = textwrap.dedent(inspect.getsource(fitness.trade_path))
    for old, new in replacements:
        assert src.count(old) == 1, "the planted anchor moved: re-point this control"
        src = src.replace(old, new)
    namespace = dict(vars(fitness))
    exec(compile(src, "<planted trade_path>", "exec"), namespace)
    return namespace["trade_path"]


def test_a_gap_exit_that_reads_its_own_close_is_caught_by_t1_and_t2() -> None:
    """The audit's leak: a gap exit that fills at the stop when its bar's CLOSE recovers above
    it. With every exit stamped at its bar's close, 479 cuts found nothing (MEDIUM-2 / X2)."""
    leaky = _planted_trade_path(CLOSE_PEEK)
    bars = bar_tape(240, seed=21, gap=3.0)

    def run(k, mode):
        return trade_path_decisions(leaky(PS, bar_tape_variant(bars, k, mode), TEST_COSTS, atr_period=14))
    ref, cuts = run(len(bars), "truncate"), bar_cuts(len(bars))
    t2 = future_perturbation(ref, lambda t: run(t, "perturb"), cuts)
    t1 = truncation(ref, lambda t: run(t, "truncate"), cuts)
    assert t2.violations and t1.violations, (t2.summary(), t1.summary())


# -- a labeller that labels a bar with the regime AFTER its completing tick ----------------- #

def _peeking_label_bars(states, engine, *, cycle_s, bar_seconds):
    """`regime_labels.label_bars` with ONE change: the completing tick is observed and
    classified BEFORE the bar is labelled, so a label knows the next bar's first price."""
    aggregators, classified_at = {}, {}
    for st in states:
        bar = aggregators.setdefault(st.instrument, BarAggregator(bar_seconds)).add(st.timestamp, st.mid, st.spread)
        engine.observe(st)
        last = classified_at.get(st.instrument)
        if last is None or (st.timestamp - last).total_seconds() >= cycle_s:
            classified_at[st.instrument] = st.timestamp
            engine.classify(st)
        ctx = engine.regime_store.get(st.instrument)
        if bar is not None and ctx is not None:
            yield st.instrument, LabelledBar(ts=bar.ts_open, open=bar.open, high=bar.high, low=bar.low,
                                             close=bar.close, spread=bar.spread, regime=ctx.regime)


def test_a_one_tick_label_peek_is_caught_by_t2_and_is_invisible_to_t1(acis_config) -> None:
    """Why both tests exist. The peeking label is emitted by its completing tick, so T1 (which
    compares what was EMITTED before the cut) cannot see it; T2 compares by horizon and does.
    The honest labeller at the same every-tick cadence raises nothing."""
    cfg = _small_regime(acis_config)
    spec = MarketSpec("planted", datetime(2014, 1, 6, tzinfo=UTC), 1, (("EUR_USD", 1.10),), tick_seconds=60)
    cuts = [LABEL_START + timedelta(minutes=k) for k in range(LABEL_TICKS - 15, LABEL_TICKS)]   # classified
    results = {}
    for name, labeller in (("honest", None), ("peek", _peeking_label_bars)):
        kw = {"cycle_s": 60.0} | ({"labeller": labeller} if labeller else {})
        ref = _labels(cfg, SyntheticMarket(spec), **kw)
        results[name] = (future_perturbation(ref, lambda t: _labels(cfg, PerturbedMarket(spec, t, "perturb"), **kw), cuts),
                         truncation(ref, lambda t: _labels(cfg, PerturbedMarket(spec, t, "truncate"), **kw), cuts))
    (h2, h1), (p2, p1) = results["honest"], results["peek"]
    assert h2.silent and h1.silent, (h2.summary(), h1.summary())
    assert p2.violations and p1.silent, (p2.summary(), p1.summary())
    assert {v.missing[0].kind for v in p2.violations} == {"label"}


# -- a whole-file statistic memoised on the source name (MEDIUM-1) --------------------------- #

def _memo_labeller(market, memo: dict):
    """Labels normalised by the WHOLE file's median mid, memoised on the source name: the
    \"cache keyed on a whole file\" channel T2 exists for (VALIDATOR §7.3)."""
    def labeller(states, engine, **kw):
        if market.name not in memo:
            end = LABEL_START + timedelta(minutes=LABEL_TICKS)
            mids = sorted((t.bid + t.ask) / 2 for t in market.load("EUR_USD", LABEL_START, end))
            memo[market.name] = mids[len(mids) // 2]
        for inst, b in label_bars(states, engine, **kw):
            yield inst, replace(b, regime=RegimeType.RANGING_WIDE) if b.close > memo[market.name] else b
    return labeller


def test_a_whole_file_statistic_memoised_on_the_source_name_is_caught(acis_config) -> None:
    """Every variant carries its own source name, so a name-keyed memo recomputes on the
    perturbed or truncated file and the leak shows. Were the names shared, every variant would
    reuse the reference's statistic, computed on the TRUE future, and both tests would stay
    silent (the audit measured 0/129 cuts)."""
    cfg = _small_regime(acis_config)
    spec = MarketSpec("planted", datetime(2014, 1, 6, tzinfo=UTC), 1, (("EUR_USD", 1.10),), tick_seconds=60)
    memo: dict = {}

    def run(market):
        return _labels(cfg, market, labeller=_memo_labeller(market, memo))
    ref = run(SyntheticMarket(spec))
    cuts = [LABEL_START + timedelta(minutes=k) for k in range(5, LABEL_TICKS, 5)]
    t2 = future_perturbation(ref, lambda t: run(PerturbedMarket(spec, t, "perturb")), cuts)
    t1 = truncation(ref, lambda t: run(PerturbedMarket(spec, t, "truncate")), cuts)
    assert t2.violations and t1.violations, (t2.summary(), t1.summary())
    assert len(memo) == 2 * len(cuts) + 1                           # one statistic per variant


# -- a next-tick peek through the REAL harness (Backtest, book, C8 costs) ------------------- #

ORACLE_FOLDS = plan(1, 2, 2, embargo=timedelta(days=2))
ORACLE_SPEC = MarketSpec("planted", START, (ORACLE_FOLDS[-1].test_end - START).days, (("EUR_USD", 1.10),),
                         tick_seconds=300)


def _oracle_sweeps(cfg, leak_every: int):
    kw = dict(instruments=["EUR_USD"], leak_every=leak_every)

    def run(t=None, mode="perturb"):
        return oracle_decisions(ORACLE_SPEC, cfg, cfg.system.active_account, ORACLE_FOLDS, NullLogger(),
                                cut=t, mode=mode, **kw)
    ref, cuts = run(), decision_cuts(ORACLE_SPEC)
    return ref, future_perturbation(ref, run, cuts), truncation(ref, lambda t: run(t, "truncate"), cuts)


def test_the_harness_level_controls_honest_oracle_silent_and_next_tick_peek_caught(acis_config) -> None:
    ref, h2, h1 = _oracle_sweeps(acis_config, 0)
    assert h2.silent and h1.silent and h2.compared > 30, (h2.summary(), h1.summary())
    assert {d.kind for d in ref} == {"order", "trade"}
    _, p2, p1 = _oracle_sweeps(acis_config, 1)
    assert p2.violations and p1.violations, (p2.summary(), p1.summary())


def test_a_daily_grid_cannot_see_a_sparse_intraday_peek(acis_config) -> None:
    """The engine-level sweep (scripts/leakage_suite.py) cuts once per decision DAY. A peek on
    one tick in twenty only crosses a daily cut if it falls on the last tick before midnight,
    so this sweep stays silent — pinned, because it is why the components are swept at every
    decision point and the engine only at its day grid."""
    _, s2, s1 = _oracle_sweeps(acis_config, 20)
    assert s2.silent and s1.silent
