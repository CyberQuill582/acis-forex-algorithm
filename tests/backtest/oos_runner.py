"""The walk-forward validation, wired end to end for one account (ACIS-09 §7; GAP-P12D-23).

`run_walk_forward` composes every built piece; `scripts/run_oos_validation.py` is only the
command line around it (paths, holdout guard, report file). Invariants:

  * The account's enabled universe, rulebook, C8 cost models, swap conventions, clusters and
    session boundaries come from the production config; the guardrail hash is the
    production limits' hash (C-BT-4).
  * The Governor sizes against the backtest book's real portfolio snapshot (GAP-P12D-21), and
    params promote only when that book is flat (the harness is the PositionGate).
  * Before the first graded tick, TSMOM's daily history is seeded from labelled bars that
    close by fold 0's train end; each fold replays observe-only ticks from its train end to
    its test start (GAP-P12D-24), then its graded test ticks.
  * Evolution reads only labelled bars inside each fold's train window (evolve_step.py).
  * N for the Deflated Sharpe adds the ACIS-11 attempt-registry entries of the enabled
    strategy families (GAP-P12D-25).
  * With no historical event calendar, MACRO_EVENT never fires and news blackouts never
    apply; the report says so (GAP-P12D-03).
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from config.account_doctrine import guardrail_hash
from config.schemas import AcisConfig
from core.signals.canonical import STRATEGY_IDS
from core.signals.signal_types import StrategyType
from tests.backtest.carry import FinancingRate
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.evolve_step import cost_model, evolve_fold
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.metrics import MetricBlock
from tests.backtest.regime_labels import LabelledBarCache
from tests.backtest.report import ValidationReport
from tests.backtest.tick_stream import build_factory, market_states
from tests.backtest.walk_forward import Fold
from tests.backtest.warmup import daily_closes, seed_tsmom
from tests.integration.paper_loop import build_paper_loop

NO_CALENDAR = ("NO historical event calendar: MACRO_EVENT never fires and news blackouts never "
               "apply, so event risk is traded through (GAP-P12D-03)")


@dataclass(frozen=True)
class RunInputs:
    cfg: AcisConfig
    account: str
    source: str
    loader: BacktestDataLoader
    cache: LabelledBarCache
    folds: Sequence[Fold]
    spx_closes: Mapping[date, float]
    financing: FinancingRate | None
    work_dir: Path
    logger: object


def train_years(folds: Sequence[Fold]) -> list[int]:
    years: set[int] = set()
    for f in folds:
        years.update(range(f.train_start.year, (f.train_end - timedelta(microseconds=1)).year + 1))
    return sorted(years)


def missing_labels(cache: LabelledBarCache, instruments: Sequence[str],
                   folds: Sequence[Fold]) -> list[tuple[str, int]]:
    return [(i, y) for i in instruments for y in train_years(folds) if not cache.has(i, y)]


def load_spx_closes(path: Path) -> dict[date, float]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return {date.fromisoformat(r["date"]): float(r["value"]) for r in csv.DictReader(f)}


def run_walk_forward(inp: RunInputs) -> ValidationReport:
    cfg = inp.cfg
    instruments = sorted(cfg.instruments.enabled)
    specs = cfg.instruments.instruments
    bt = Backtest(account=inp.account, cost_models={i: cost_model(cfg, i) for i in instruments},
                  rulebook=cfg.platform_rules.accounts[inp.account], financing=inp.financing,
                  swap_conventions={i: specs[i].swap_convention for i in instruments},
                  session_boundaries=cfg.system.session_boundaries, clusters=cfg.instruments.clusters)
    factory = build_factory(cfg, instruments)
    inp.work_dir.mkdir(parents=True, exist_ok=True)
    loop = build_paper_loop(inp.work_dir, cfg, factory, bt.portfolio_state, account=inp.account,
                            logger=inp.logger, regime_cycle_s=cfg.system.regime.cycle_seconds,
                            position_gate=bt)
    first = inp.folds[0]
    bar_s = cfg.system.signals.signal_bar_seconds
    for instrument in instruments:
        bars = (b for y in range(first.train_start.year, first.train_end.year + 1)
                if inp.cache.has(instrument, y) for b in inp.cache.read(instrument, y))
        seed_tsmom(loop.agon, instrument, daily_closes(bars, first.train_end, bar_s))
    loop.boot(bt.portfolio_state())

    def stream(start: datetime, end: datetime):
        return market_states(cfg=cfg, loader=inp.loader, factory=factory, source=inp.source,
                             instruments=instruments, start=start, end=end)

    folds = [FoldData(f, stream(f.test_start, f.test_end), warmup_states=stream(f.train_end, f.test_start))
             for f in inp.folds]
    families = {STRATEGY_IDS[StrategyType(s)].rsplit("_v", 1)[0]
                for s, on in cfg.system.signals.modules_enabled.items() if on}
    limits_hash = guardrail_hash(cfg.guardrails)
    report = bt.run(
        loop=loop, folds=folds,
        evolve_fn=lambda lp, fd: evolve_fold(lp, fd, cfg=cfg, cache=inp.cache,
                                             instruments=instruments, logger=inp.logger),
        spx_closes=inp.spx_closes, guardrail_hash=limits_hash, expected_guardrail_hash=limits_hash,
        extra_caveats=(NO_CALENDAR,), min_trials=sum(loop.provenance.attempts(f) for f in families))
    inp.logger.event("BACKTEST_RUN", account=inp.account, folds=len(inp.folds), passed=report.passed,
                     period=[report.period[0].isoformat(), report.period[1].isoformat()])
    return report


def _plain(v):
    if isinstance(v, MetricBlock):
        return v.as_dict()
    if is_dataclass(v):
        return {f.name: _plain(getattr(v, f.name)) for f in fields(v)}
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, Mapping):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def report_json(report: ValidationReport) -> str:
    return json.dumps(_plain(report), indent=1, sort_keys=True)
