"""The REAL decision path under the leakage checks (GAP-P12D-65): the labeller, evolution,
NVMA, AGON, the Governor and the book, exactly as `oos_runner.run_walk_forward` composes them.

Mental model:
  * One variant = one fresh directory. The labeller writes its own cache, evolution reads
    it, the engine replays; nothing is shared between variants. A shared label cache would
    carry one tape's labels into another: that is the whole-file cache channel T2 targets.
  * Decisions recorded, each with its horizon and emission stamp (leakage.py):
      label      every cached labelled bar: horizon its own close, emitted by the tick that
                 completes it (TickClock: the ticks the loader really delivers);
      evolution  each fold's record: horizon its train end, emitted by the first tick at or
                 after it on every instrument (the last training bar needs its completing tick);
      regime     the context the loop holds after each replayed tick, warm-up included;
      signal     every AGON signal (random ids stripped, group ordinal kept);
      order      every Governor order; trade: every closed trade (the book's fill model).
  * The tap wraps `build_paper_loop` for ONE run (unittest.mock.patch), so the runner under
    test is the production composition, unmodified, and nothing outlives the run.
  * `leak_config` may shrink the optimizer (population, generations, the minimum bar and
    trade counts) so a short tape stages champions at all. Causality does not depend on a
    population size; a sweep whose reference run staged nothing or ordered nothing has
    compared nothing that matters, and the script refuses it a verdict.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence
from unittest import mock

import tests.backtest.oos_runner as oos_runner
from config.schemas import AcisConfig, load_config
from tests.legacy_universe import legacy_view
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.leakage import Decision
from tests.backtest.leakage_markets import PerturbedMarket, TickClock, order_decisions, trade_decisions
from tests.backtest.look_register import LookRegister
from tests.backtest.oos_runner import RunInputs, run_walk_forward, train_years
from tests.backtest.regime_labels import label_instrument_year
from tests.backtest.synthetic_grade import market_cache
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, synthetic_spx
from tests.backtest.walk_forward import Fold

_US = timedelta(microseconds=1)


class NullLogger:
    """The leakage runs replay the same tape many times; their event lines are not decisions."""

    def event(self, event_type: str, **data) -> None:
        return None

    def close(self) -> None:
        return None


def leak_config(root: Path, *, small_optimizer: bool) -> AcisConfig:
    cfg = legacy_view(load_config(root / "config"))       # the legacy engine's synthetic pairs
    if not small_optimizer:
        return cfg
    small = cfg.system.optimizer.model_copy(update={
        "population_size": 8, "generations": 8, "fitness_min_bars": 100, "fitness_min_trades": 5,
        "holdout_min_trades": 2})
    return cfg.model_copy(update={"system": cfg.system.model_copy(update={"optimizer": small})})


def signal_decisions(ts: datetime, signals: Sequence) -> list[Decision]:
    groups: dict[str, int] = {}
    return [Decision(ts, ts, "signal", (
        s.instrument, s.direction, s.conviction, s.entry_price, s.stop_loss, s.take_profit,
        s.strategy_type.value, s.regime_at_generation.value, s.param_set_id, s.generated_at,
        s.valid_for_seconds, None if s.group_id is None else groups.setdefault(s.group_id, len(groups))))
        for s in signals]


class _Tap:
    """Records the loop's decisions as the harness drives it; changes nothing it wraps."""

    def __init__(self, build) -> None:
        self._build = build
        self.decisions: list[Decision] = []
        self.backtest = None

    def build(self, *args, **kw):
        loop = self._build(*args, **kw)
        self.backtest = kw.get("position_gate")
        on_state, observe_only, generate = loop.on_state, loop.observe_only, loop.agon.generate

        def tapped_generate(state, regime, params, now):
            signals = generate(state, regime, params, now)
            self.decisions += signal_decisions(state.timestamp, signals)
            return signals

        def held_regime(st) -> None:
            c = loop.last_context
            self.decisions.append(Decision(st.timestamp, st.timestamp, "regime", (
                st.instrument, c.timestamp, c.regime.value, c.trend_direction, c.volatility_class.value,
                c.liquidity_state.value, c.tradeable, c.confidence, c.regime_stability_score,
                c.estimated_half_life_seconds)))

        def tapped_on_state(st) -> None:
            n = len(loop.book.orders)
            on_state(st)
            held_regime(st)
            self.decisions += order_decisions(loop.book.orders[n:], loop.book.strategy_of,
                                              loop.book.regime_of)

        def tapped_observe_only(st) -> None:
            observe_only(st)
            held_regime(st)

        loop.agon.generate, loop.on_state, loop.observe_only = tapped_generate, tapped_on_state, tapped_observe_only
        return loop


def engine_decisions(spec: MarketSpec, cfg: AcisConfig, account: str, folds: Sequence[Fold], work: Path,
                     *, cut: datetime | None = None, mode: str = "perturb") -> list[Decision]:
    """Label, evolve and replay `spec` (or its variant at `cut`) through the production path."""
    log = NullLogger()
    market = SyntheticMarket(spec) if cut is None else PerturbedMarket(spec, cut, mode)
    loader = BacktestDataLoader({market.name: market}, log)
    instruments = sorted(cfg.instruments.enabled)
    cache = market_cache(cfg, work, market.name, spec.start)
    for instrument in instruments:
        for year in train_years(folds):
            label_instrument_year(cfg=cfg, loader=loader, source=market.name, instrument=instrument,
                                  year=year, cache=cache, logger=log, data_start=spec.start)
    look = LookRegister(work / "looks").register(cfg=cfg, source=market, instruments=instruments, folds=folds,
                                                 family="synthetic:leakage", account=account, git=("n/a", False))
    tap = _Tap(oos_runner.build_paper_loop)
    with mock.patch.object(oos_runner, "build_paper_loop", tap.build):
        report = run_walk_forward(RunInputs(
            cfg=cfg, account=account, source=market.name, loader=loader, cache=cache, folds=folds,
            spx_closes=synthetic_spx(spec.start, spec.days), financing=None, work_dir=work / "engine",
            logger=log, look=look))

    full = SyntheticMarket(spec)                   # emission stamps come from the FULL tape
    clocks = {i: TickClock(BacktestDataLoader({full.name: full}, log), full.name, i, spec.start, spec.end)
              for i in instruments}
    bar = timedelta(seconds=cfg.system.signals.signal_bar_seconds)
    out = list(tap.decisions)
    for i in instruments:
        for year in cache.years(i):
            out += [Decision(b.ts + bar - _US, clocks[i].after(b.ts + bar), "label",
                             (i, b.ts, b.open, b.high, b.low, b.close, b.spread, b.regime.value))
                    for b in cache.read(i, year)]
    for record in report.in_sample_evolution:
        end = folds[record["fold"]].train_end
        out.append(Decision(end - _US, max(clocks[i].after(end) for i in instruments), "evolution",
                            (json.dumps(record, sort_keys=True, default=str),)))
    return out + trade_decisions(tap.backtest.graded_trades())


def variant_decisions(spec: MarketSpec, account: str, folds: Sequence[Fold], work: Path, root: Path,
                      small_optimizer: bool, cut: datetime | None, mode: str) -> tuple[datetime | None, str, list[Decision]]:
    """One variant in a worker process: it reloads the config rather than inheriting it."""
    cfg = leak_config(root, small_optimizer=small_optimizer)
    return cut, mode, engine_decisions(spec, cfg, account, folds, work, cut=cut, mode=mode)


def vacuity(reference: Sequence[Decision]) -> list[str]:
    """Why a reference run cannot support a verdict: it staged no champion, or ordered nothing."""
    out = []
    records = [json.loads(d.payload[0]) for d in reference if d.kind == "evolution"]
    if not any(r.get("champions") for r in records):
        out.append("no fold staged a champion")
    if not any(d.kind == "order" for d in reference):
        out.append("the engine placed no order")
    return out
