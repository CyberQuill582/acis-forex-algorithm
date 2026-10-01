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
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import numpy as np

from config.schemas import AcisConfig
from tests.backtest.hac import hac_t
from tests.backtest.look_claims import Claim
from tests.backtest.look_gate import begin_grade
from tests.backtest.look_register import Look, LookRefused, LookRegister
from tests.backtest.rsim import BookResult, BookSpec, Market, annual_sharpe, run
from tests.backtest.walk_forward import Fold


@dataclass(frozen=True)
class _OneSource:
    """`begin_grade` reads the source through a loader; RSIM has exactly one."""
    src: object

    def source_object(self, name: str) -> object:
        return self.src if getattr(self.src, "name", None) == name else None


def _utc(d: date) -> datetime:
    return datetime.combine(d, time(), tzinfo=timezone.utc)


def evaluate(*, register: LookRegister, cfg: AcisConfig, source: object, family: str, claim: Claim | None,
             account: str, market: Market, forecast: np.ndarray, pct_vol: np.ndarray, spec: BookSpec,
             graded_from: date, changed: str = "") -> tuple[Look, BookResult]:
    instruments = tuple(sorted(market.names))
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
    begin_grade(look, cfg=cfg, loader=_OneSource(source), source=source.name, instruments=instruments,
                folds=[fold], account=account, cost_stress=cost_stress, spread_floor=spread_floor)
    result = run(market, forecast, pct_vol, spec)
    keep = [t for t, d in enumerate(days) if d >= graded_from]
    daily = result.daily[keep]
    register.record_outcome(look, {"annual_sharpe": annual_sharpe(daily), "hac_t": hac_t(daily),
                                   "graded_days": len(keep), "fills": result.fills, "world": result.world},
                            daily=([days[t] for t in keep], daily.tolist()))
    return look, result
