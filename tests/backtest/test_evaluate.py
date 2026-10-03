"""`evaluate`, the one producer of an RSIM grade (GAP-P12D-136 item 6): the line first, one line one
grade, the outcome and daily vector stored, and every mismatch refused before any compute."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from core.signals import rules
from tests.backtest.evaluate import StageArms, evaluate
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.look_claims import load_vector
from tests.backtest.look_register import LookRefused, LookRegister
from tests.backtest.rsim import BookSpec, panel, run
from tests.backtest.rsim_lab import carver_pct_vol, lab_market
from tests.backtest.stage_a import from_register, stage_a


class LabRsim:
    name, provenance = "lab-rsim", "synthetic"


class RealRsim:
    name, provenance = "dukascopy-candles", "real"


def _inputs(stress: float = 1.0):
    m = lab_market(generate(LabSpec(n_inst=3, days=700, seed=2, effect=Effect(trend_sharpe=1.0))))
    spec = BookSpec(costs={n: CostModel(0.0, 0.00002, stress=stress) for n in m.names})
    return m, panel(m, rules.d1), carver_pct_vol(m), spec


def test_a_synthetic_grade_writes_its_line_first_then_its_outcome_and_vector(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    m, f, v, spec = _inputs()
    look, result = evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="trend_d1_v1", claim=None,
                            account="lab", market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[300])
    assert look.tier == 0 and (tmp_path / "looks" / f"{look.look_id}.graded.json").exists()
    outcome = reg.outcome(look.look_id)                                     # a chained line (R12I-08)
    dates, returns = load_vector(tmp_path / "looks", outcome["daily_vector"])
    assert dates[0] == m.days[300] and len(returns) == outcome["graded_days"] == len(m.days) - 300
    assert returns == pytest.approx(result.daily[300:].tolist())
    with pytest.raises(LookRefused, match="already graded"):
        reg.consume(look)                                                     # one line, one grade


def test_a_real_data_grade_is_refused_while_real_looks_are_closed(tmp_path, acis_config) -> None:
    m, f, v, spec = _inputs()
    with pytest.raises(LookRefused):
        evaluate(register=LookRegister(tmp_path / "looks"), cfg=acis_config, source=RealRsim(), family="trend_d1_v1",
                 claim=None, account="ftmo", market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[300])
    assert not (tmp_path / "looks").exists() or not LookRegister(tmp_path / "looks").looks()


def test_mismatched_costs_or_window_are_refused_before_any_line(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    m, f, v, spec = _inputs()
    mixed = replace(spec, costs={**spec.costs, m.names[0]: CostModel(0.0, 0.00002, stress=2.0)})
    with pytest.raises(LookRefused, match="cost stress"):
        evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="f", claim=None, account="lab",
                 market=m, forecast=f, pct_vol=v, spec=mixed, graded_from=m.days[300])
    with pytest.raises(LookRefused, match="graded window"):
        evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="f", claim=None, account="lab",
                 market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[0])
    assert not reg.scan().lines                                               # nothing was registered


def _arms(m) -> StageArms:
    return StageArms(benchmark="PASSIVE_LONG", benchmark_forecast=np.full((len(m.days), len(m.names)), 10.0),
                     kill_only={"EWMAC16_64": panel(m, lambda p: rules.ewmac(p, 16, 64)),
                                "BREAKOUT80": panel(m, lambda p: rules.breakout(p, 80))})


def test_a_stage_a_grade_stores_every_series_its_verdict_reads(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    m, f, v, spec = _inputs()
    look, result = evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="trend_d1_v1", claim=None,
                            account="lab", market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[300],
                            arms=_arms(m))
    stored = reg.outcome(look.look_id)["stage_a"]
    assert stored["benchmark"] == "PASSIVE_LONG" and sorted(stored["kill_only_vectors"]) == ["BREAKOUT80", "EWMAC16_64"]
    doubled = BookSpec(costs={n: CostModel(0.0, 0.00002, stress=2.0) for n in m.names})
    _, x2 = load_vector(tmp_path / "looks", stored["cost2x_vector"])
    assert x2 == pytest.approx(run(m, f, v, doubled).daily[300:].tolist())          # the WHOLE cost doubled
    assert np.mean(x2) < np.mean(result.daily[300:])
    direct = stage_a(result.daily[300:], run(m, _arms(m).benchmark_forecast, v, spec).daily[300:],
                     run(m, f, v, doubled).daily[300:],
                     {k: float(run(m, fk, v, spec).daily[300:].mean()) for k, fk in _arms(m).kill_only.items()}, 0.03)
    assert from_register(tmp_path / "looks", look.look_id, 0.03) == direct          # a pure function of the register


def test_a_stage_a_arm_that_is_undeclared_or_off_the_market_is_refused_before_any_line(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    m, f, v, spec = _inputs()
    bad_name = StageArms(benchmark="BEST_OF_THREE", benchmark_forecast=_arms(m).benchmark_forecast)
    bad_shape = StageArms(benchmark="PASSIVE_LONG", benchmark_forecast=np.full((5, len(m.names)), 10.0))
    for arms, why in ((bad_name, "registered passive arm"), (bad_shape, "own market")):
        with pytest.raises(LookRefused, match=why):
            evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="f", claim=None, account="lab",
                     market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[300], arms=arms)
    assert not reg.scan().lines
    plain, _ = evaluate(register=reg, cfg=acis_config, source=LabRsim(), family="f", claim=None, account="lab",
                        market=m, forecast=f, pct_vol=v, spec=spec, graded_from=m.days[300])
    with pytest.raises(ValueError, match="not a stage-A grade"):
        from_register(tmp_path / "looks", plain.look_id, 0.03)
