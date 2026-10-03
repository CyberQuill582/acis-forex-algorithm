"""THE entry point of an event-simulator grade (GAP-P12D-154/157; ACIS-09 C-BT-11 v2 step 1, v1.12): the
twin of `evaluate()` for scheduled-window rules (D3's windows, REBAL's close-to-close days).

    look, fold = register_event_look(...)          # every refusal, then the line
    result = grade_event_look(look, fold, ...)     # consume the line, grade, chain the outcome
    look, result = evaluate_events(...)            # both, for D3's book

Mental model:
  * Register first: the look line is written (its claim names the "event" simulator), `begin_grade`
    re-checks and CONSUMES it, and only then does the book run. Every refusal happens before any
    compute. Splitting the two lets a family register several versions before grading any (REBAL).
  * KILL-ONLY: no event verdict exists for a pass, so a look whose graded window ends after its claim's
    certifying boundary (master §5.6; `look_cycles.is_kill_only`) is refused before its line. Its
    verdict is `verdict.kill_verdict`, killed at HAC t < -0.5 (owner rulings 2026-10-03).
  * One fold: warm-up [start, graded_from), test [graded_from, end]; the test window decides the data
    tier. `run(stress)` is the book at a cost multiple: 1x is graded, 2x is context, as is the passive
    benchmark; each vector is stored by its hash and the outcome is chained against the line.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Mapping, Sequence

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


def _stress(costs: Mapping[str, CostModel]) -> tuple[float, float]:
    stresses = {(cm.stress, cm.spread_floor) for cm in costs.values()}
    if len(stresses) != 1:
        raise LookRefused("one grade, one cost stress: the book's cost models disagree")
    return stresses.pop()


def register_event_look(*, register: LookRegister, cfg: AcisConfig, source: object, claim: Claim, account: str,
                        instruments: Sequence[str], costs: Mapping[str, CostModel], start: date,
                        graded_from: date, end: date, changed: str = "") -> tuple[Look, Fold]:
    instruments = tuple(sorted(instruments))
    if not isinstance(claim, Claim) or claim.simulator != SIMULATOR:
        raise LookRefused(f"an event grade carries a claim naming the {SIMULATOR!r} simulator")
    cost_stress, spread_floor = _stress(costs)
    if set(costs) != set(instruments):
        raise LookRefused("the book prices other instruments than the market holds")
    if not start < graded_from <= end:
        raise LookRefused(f"the graded window must start inside the marks ({start}..{end})")
    test_end = _utc(end) + timedelta(days=1)
    if not is_kill_only(claim.origin.boundary(), test_end.date()):
        raise LookRefused("an event look can only kill: its graded window must end by the claim's certifying "
                          f"boundary ({claim.origin.boundary()}), since no event verdict exists for a pass")
    fold = Fold(0, _utc(start), _utc(graded_from), _utc(graded_from), test_end)
    look = register.register(cfg=cfg, source=source, instruments=instruments, folds=[fold], family=claim.family,
                             account=account, changed=changed, cost_stress=cost_stress,
                             spread_floor=spread_floor, claim=claim)
    return look, fold


def grade_event_look(look: Look, fold: Fold, *, register: LookRegister, cfg: AcisConfig, source: object,
                     costs: Mapping[str, CostModel], graded_from: date, run: Callable[[float], EventResult],
                     benchmark: Callable[[], np.ndarray], summary: Callable[[EventResult], dict]) -> EventResult:
    cost_stress, spread_floor = _stress(costs)
    begin_grade(look, cfg=cfg, loader=OneSource(source), source=source.name, instruments=look.instruments,
                folds=[fold], account=look.account, cost_stress=cost_stress, spread_floor=spread_floor,
                simulator=SIMULATOR)
    result = run(1.0)
    keep = [t for t, d in enumerate(result.days) if d >= graded_from]
    dates, daily = [result.days[t] for t in keep], result.daily[keep]
    stored = lambda v: store_vector(register.root, dates, np.asarray(v)[keep].tolist())   # noqa: E731
    outcome = {"simulator": SIMULATOR, "annual_sharpe": annual_sharpe(daily), "hac_t": hac_t(daily),
               "graded_days": len(keep), **summary(result),
               "context": {"benchmark": look.claim["declaration"]["benchmark"],
                           "benchmark_vector": stored(benchmark()), "cost2x_vector": stored(run(2.0).daily)}}
    register.record_outcome(look, outcome, daily=(dates, daily.tolist()))
    return result


def evaluate_events(*, register: LookRegister, cfg: AcisConfig, source: object, family: str, claim: Claim,
                    account: str, hourly: Mapping[str, Hourly], costs: Mapping[str, CostModel], start: date,
                    graded_from: date, end: date, changed: str = "") -> tuple[Look, EventResult]:
    """D3's book: the windows of `event_sim.simulate` on every index of `hourly`."""
    if claim.family != family:
        raise LookRefused(f"the claim is family {claim.family!r}'s, not {family!r}'s")
    look, fold = register_event_look(register=register, cfg=cfg, source=source, claim=claim, account=account,
                                     instruments=tuple(hourly), costs=costs, start=start,
                                     graded_from=graded_from, end=end, changed=changed)
    scaled = lambda s: {n: replace(cm, stress=cm.stress * s) for n, cm in costs.items()}   # noqa: E731
    result = grade_event_look(
        look, fold, register=register, cfg=cfg, source=source, costs=costs, graded_from=graded_from,
        run=lambda s: simulate(hourly, scaled(s), start, graded_from, end),
        benchmark=lambda: passive_long(hourly, start, end),
        summary=lambda r: {"events": len(r.events), "skipped": len(r.skipped),
                           "per_index": per_index(r.events, r.skipped)})
    return look, result
