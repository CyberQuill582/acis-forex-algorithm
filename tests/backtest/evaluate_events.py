"""THE entry point of an event-simulator grade (GAP-P12D-154; ACIS-09 C-BT-11 v2 step 1, v1.12): the
twin of `evaluate()` for scheduled-window rules, such as D3.

    look, result = evaluate_events(register=..., cfg=..., source=..., family=..., claim=..., account=...,
                                   hourly=..., costs=..., start=..., graded_from=..., end=...)

Mental model:
  * Register first: the look line is written (its claim names the "event" simulator), `begin_grade`
    re-checks and CONSUMES it, and only then does `event_sim.simulate` run. Every refusal happens
    before any compute.
  * KILL-ONLY: no event verdict exists for a pass, so a look whose graded window ends after its claim's
    certifying boundary (master §5.6; `look_cycles.is_kill_only`) is refused before its line. Its
    verdict is `verdict.kill_verdict`, killed at HAC t < -0.5 (owner rulings 2026-10-03).
  * One fold: warm-up [start, graded_from) for the legs' volatility, test [graded_from, end]; the test
    window decides the data tier. The outcome and the daily portfolio vector are chained against the
    line, with the context vectors (the passive long, the book at 2x cost) stored by their hashes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping

import numpy as np

from config.schemas import AcisConfig
from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.evaluate import OneSource
from tests.backtest.event_sim import EventResult, passive_long, per_index, simulate
from tests.backtest.hac import hac_t
from tests.backtest.look_claims import Claim, store_vector
from tests.backtest.look_cycles import is_kill_only
from tests.backtest.look_gate import begin_grade
from tests.backtest.look_register import Look, LookRefused, LookRegister
from tests.backtest.rsim import annual_sharpe
from tests.backtest.walk_forward import Fold

SIMULATOR = "event"


def _utc(d: date) -> datetime:
    return datetime.combine(d, time(), tzinfo=timezone.utc)


def evaluate_events(*, register: LookRegister, cfg: AcisConfig, source: object, family: str, claim: Claim,
                    account: str, hourly: Mapping[str, Hourly], costs: Mapping[str, CostModel], start: date,
                    graded_from: date, end: date, changed: str = "") -> tuple[Look, EventResult]:
    instruments = tuple(sorted(hourly))
    if not isinstance(claim, Claim) or claim.simulator != SIMULATOR:
        raise LookRefused(f"an event grade carries a claim naming the {SIMULATOR!r} simulator")
    stresses = {(cm.stress, cm.spread_floor) for cm in costs.values()}
    if len(stresses) != 1:
        raise LookRefused("one grade, one cost stress: the book's cost models disagree")
    (cost_stress, spread_floor), = stresses
    if set(costs) != set(instruments):
        raise LookRefused("the book prices other instruments than the market holds")
    if not start < graded_from <= end:
        raise LookRefused(f"the graded window must start inside the marks ({start}..{end})")
    test_end = _utc(end) + timedelta(days=1)
    if not is_kill_only(claim.origin.boundary(), test_end.date()):
        raise LookRefused("an event look can only kill: its graded window must end by the claim's certifying "
                          f"boundary ({claim.origin.boundary()}), since no event verdict exists for a pass")
    fold = Fold(0, _utc(start), _utc(graded_from), _utc(graded_from), test_end)
    look = register.register(cfg=cfg, source=source, instruments=instruments, folds=[fold], family=family,
                             account=account, changed=changed, cost_stress=cost_stress,
                             spread_floor=spread_floor, claim=claim)
    begin_grade(look, cfg=cfg, loader=OneSource(source), source=source.name, instruments=instruments,
                folds=[fold], account=account, cost_stress=cost_stress, spread_floor=spread_floor,
                simulator=SIMULATOR)
    result = simulate(hourly, costs, start, graded_from, end)
    keep = [t for t, d in enumerate(result.days) if d >= graded_from]
    dates, daily = [result.days[t] for t in keep], result.daily[keep]
    doubled = {n: replace(cm, stress=cm.stress * 2.0) for n, cm in costs.items()}
    stored = lambda v: store_vector(register.root, dates, np.asarray(v)[keep].tolist())   # noqa: E731
    outcome = {"simulator": SIMULATOR, "annual_sharpe": annual_sharpe(daily), "hac_t": hac_t(daily),
               "graded_days": len(keep), "events": len(result.events), "skipped": len(result.skipped),
               "per_index": per_index(result.events, result.skipped),
               "context": {"benchmark": claim.declaration.benchmark,
                           "benchmark_vector": stored(passive_long(hourly, start, end)),
                           "cost2x_vector": stored(simulate(hourly, doubled, start, graded_from, end).daily)}}
    register.record_outcome(look, outcome, daily=(dates, daily.tolist()))
    return look, result
