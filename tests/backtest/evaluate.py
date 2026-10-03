"""THE entry point of an RSIM grade (R1.2's residual; GAP-P12D-136 item 6; ACIS-09 C-BT-11 v2 step 1).

    look, result = evaluate(register=..., cfg=..., source=..., family=..., claim=..., account=...,
                            market=..., forecast=..., pct_vol=..., spec=..., graded_from=...)

Mental model:
  * A graded number exists only if its look-register line was written FIRST. `evaluate` registers
    the look (real data refused while `look_claims.REAL_LOOKS_OPEN` is False, a claim required for
    real data), then `look_gate.begin_grade` re-checks and CONSUMES the line (one line, one grade),
    and only then does RSIM run. The outcome and the daily portfolio vector are stored against the
    line (GAP-P12D-98). A refusal happens before any compute.
  * `evaluate` calls RSIM itself: the market, forecasts and book spec are its inputs, so no caller
    can grade one run and register another. The market must hold exactly the registered
    instruments, and every cost model the registered cost stress and floor.
  * A fixed family has no training step, so its one fold is warm-up [first day, graded_from) and
    test [graded_from, last day]: the test window decides the data tier (look_tiers).
  * A STAGE-A grade (`arms` given) runs, inside the same consumed look, every series stage A reads:
    the declared passive benchmark on the family's own book, the family at 2x modelled cost (the
    C8 stress and the swap markup both doubled), and each kill-only arm (C9 members, plateau
    neighbours). Each graded span is stored by its hash, so the verdict is a pure function of the
    register (`stage_a.from_register`), and no arm can be graded outside its family's look.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Mapping

import numpy as np

from config.schemas import AcisConfig
from tests.backtest.hac import hac_t
from tests.backtest.look_claims import Claim, store_vector
from tests.backtest.look_declarations import BENCHMARKS
from tests.backtest.look_gate import begin_grade
from tests.backtest.look_register import Look, LookRefused, LookRegister
from tests.backtest.rsim import BookResult, BookSpec, Market, annual_sharpe, run
from tests.backtest.walk_forward import Fold


@dataclass(frozen=True)
class StageArms:
    """The series stage A reads besides the family's own (C-BT-11 v2 step 3)."""
    benchmark: str                                   # the declared passive arm (look_declarations.BENCHMARKS)
    benchmark_forecast: np.ndarray
    kill_only: Mapping[str, np.ndarray] = field(default_factory=dict)   # name -> forecasts


@dataclass(frozen=True)
class OneSource:
    """`begin_grade` reads the source through a loader; RSIM has exactly one."""
    src: object

    def source_object(self, name: str) -> object:
        return self.src if getattr(self.src, "name", None) == name else None


def _utc(d: date) -> datetime:
    return datetime.combine(d, time(), tzinfo=timezone.utc)


def evaluate(*, register: LookRegister, cfg: AcisConfig, source: object, family: str, claim: Claim | None,
             account: str, market: Market, forecast: np.ndarray, pct_vol: np.ndarray, spec: BookSpec,
             graded_from: date, changed: str = "", arms: StageArms | None = None) -> tuple[Look, BookResult]:
    instruments = tuple(sorted(market.names))
    if arms is not None:
        _admit_arms(arms, claim, forecast.shape)
    stresses = {(cm.stress, cm.spread_floor) for cm in spec.costs.values()}
    if len(stresses) != 1:
        raise LookRefused("one grade, one cost stress: the book's cost models disagree")
    (cost_stress, spread_floor), = stresses
    if set(spec.costs) != set(instruments):
        raise LookRefused("the book prices other instruments than the market holds")
    days = market.days
    if not (days[0] < graded_from <= days[-1]):
        raise LookRefused(f"the graded window must start inside the market's days ({days[0]}..{days[-1]})")
    fold = Fold(0, _utc(days[0]), _utc(graded_from), _utc(graded_from), _utc(days[-1]) + timedelta(days=1))
    look = register.register(cfg=cfg, source=source, instruments=instruments, folds=[fold], family=family,
                             account=account, changed=changed, cost_stress=cost_stress,
                             spread_floor=spread_floor, claim=claim)
    begin_grade(look, cfg=cfg, loader=OneSource(source), source=source.name, instruments=instruments,
                folds=[fold], account=account, cost_stress=cost_stress, spread_floor=spread_floor, simulator="rsim")
    result = run(market, forecast, pct_vol, spec)
    keep = [t for t, d in enumerate(days) if d >= graded_from]
    daily = result.daily[keep]
    outcome = {"annual_sharpe": annual_sharpe(daily), "hac_t": hac_t(daily),
               "graded_days": len(keep), "fills": result.fills, "world": result.world}
    if arms is not None:
        outcome["stage_a"] = _stage_a_vectors(register, market, forecast, pct_vol, spec, arms, keep)
    register.record_outcome(look, outcome, daily=([days[t] for t in keep], daily.tolist()))
    return look, result


def _admit_arms(arms: StageArms, claim: Claim | None, shape: tuple[int, ...]) -> None:
    """Refused before any line: an undeclared benchmark, or an arm on another market's shape."""
    if arms.benchmark not in BENCHMARKS:
        raise LookRefused(f"the benchmark is a registered passive arm, one of {BENCHMARKS}")
    if claim is not None and claim.declaration.benchmark != arms.benchmark:
        raise LookRefused(f"the claim declared {claim.declaration.benchmark!r}, not {arms.benchmark!r}")
    if any(f.shape != shape for f in (arms.benchmark_forecast, *arms.kill_only.values())):
        raise LookRefused("every stage-A arm forecasts the family's own market")


def _doubled(spec: BookSpec) -> BookSpec:
    """2x modelled cost including swap: the whole C8 per-side cost and the venue's markup."""
    return replace(spec, costs={n: replace(cm, stress=cm.stress * 2.0) for n, cm in spec.costs.items()},
                   markup={n: (lo * 2.0, sh * 2.0) for n, (lo, sh) in spec.markup.items()})


def _stage_a_vectors(register: LookRegister, market: Market, forecast: np.ndarray, pct_vol: np.ndarray,
                     spec: BookSpec, arms: StageArms, keep: list[int]) -> dict:
    dates = [market.days[t] for t in keep]
    stored = lambda f, s=spec: store_vector(register.root, dates, run(market, f, pct_vol, s).daily[keep].tolist())  # noqa: E731
    return {"benchmark": arms.benchmark, "benchmark_vector": stored(arms.benchmark_forecast),
            "cost2x_vector": stored(forecast, _doubled(spec)),
            "kill_only_vectors": {name: stored(f) for name, f in sorted(arms.kill_only.items())}}
