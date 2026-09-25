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
  * No grade without its look (GAP-P12D-64): `look_register.begin_grade` proves, BEFORE any
    compute, that `inp.look` is an unconsumed line of an intact register (the canonical one for
    real data) for exactly this run, then consumes it; the outcome is recorded against it after
    the grade, and the report carries the look and the register's counts.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, fields, is_dataclass, replace
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
from tests.backtest.look_register import LookRegister, begin_grade
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
    look: object                  # a look_register.Look written for THIS run (GAP-P12D-64)
    # GAP-P12D-46 cost-stress ladder — RUN properties, never instrument properties. 1.0 / 0.0
    # is the declared world; anything else is recorded as a fidelity caveat so a stressed
    # number can never be read as a declared-cost one.
    cost_stress: float = 1.0
    spread_floor: float = 0.0


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


def stress_caveat(inp: RunInputs) -> tuple[str, ...]:
    """A stressed run must SAY it is stressed (GAP-P12D-46): its §14 numbers are priced in a
    world harsher than the declared one, and the ladder is a stress test, never a calibration."""
    if inp.cost_stress == 1.0 and inp.spread_floor == 0.0:
        return ()
    return (f"COST-STRESS RUN: every C8 per-side cost multiplied by {inp.cost_stress}"
            + (f" over a {inp.spread_floor} spread floor" if inp.spread_floor else "")
            + " — a flat stress ladder, NOT a venue calibration (GAP-P12D-46)",)


def run_walk_forward(inp: RunInputs) -> ValidationReport:
    cfg = inp.cfg
    instruments = sorted(cfg.instruments.enabled)
    begin_grade(inp.look, cfg=cfg, loader=inp.loader, source=inp.source, instruments=instruments,
                folds=inp.folds, account=inp.account, cost_stress=inp.cost_stress,
                spread_floor=inp.spread_floor)     # GAP-P12D-64: the line exists and is consumed first
    specs = cfg.instruments.instruments
    # ONE cost map, both places (master §5 C8): selection (QIEA, via evolve_fold) and the
    # graded book charge the same instances, so a stressed run cannot select cheap and grade
    # expensive — the GAP-P12D-36 defect class, now structurally excluded.
    costs = {i: cost_model(cfg, i, stress=inp.cost_stress, spread_floor=inp.spread_floor)
             for i in instruments}
    bt = Backtest(account=inp.account, cost_models=costs,
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
        evolve_fn=lambda lp, fd: evolve_fold(lp, fd, cfg=cfg, costs=costs, cache=inp.cache,
                                             instruments=instruments, logger=inp.logger),
        spx_closes=inp.spx_closes, guardrail_hash=limits_hash, expected_guardrail_hash=limits_hash,
        extra_caveats=(NO_CALENDAR, *stress_caveat(inp)),
        min_trials=sum(loop.provenance.attempts(f) for f in families))
    inp.logger.event("BACKTEST_RUN", account=inp.account, folds=len(inp.folds), passed=report.passed,
                     period=[report.period[0].isoformat(), report.period[1].isoformat()],
                     look=inp.look.look_id, family=inp.look.family)
    register = LookRegister(Path(inp.look.path).parent)
    register.record_outcome(inp.look, _plain({
        "passed": report.passed, "targets_met": report.targets_met, "period": report.period,
        "annual_sharpe": report.out_of_sample.annual_sharpe, "n_trades": report.out_of_sample.n_trades,
        "deflated_sharpe": report.deflated_sharpe, "trial_count": report.trial_count,
        "trade_returns": [float(t.pnl / t.notional_usd) for t in bt.graded_trades() if t.notional_usd]}))
    return replace(report, look={"look_id": inp.look.look_id, "family": inp.look.family,
                                 "tier": inp.look.tier_name, **register.summary()})


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


def strict_json(value, *, sort_keys: bool = False) -> str:
    """RFC 8259 JSON (audits F6/E7: "NaN and Infinity are not permitted"): `_plain` maps every
    non-finite float to null, and `allow_nan=False` makes any that slips past RAISE rather than
    write a bare NaN a strict parser rejects."""
    return json.dumps(_plain(value), indent=1, sort_keys=sort_keys, allow_nan=False)


def report_json(report: ValidationReport) -> str:
    return strict_json(report, sort_keys=True)
