"""`evaluate_events`, the one producer of an event-simulator grade (GAP-P12D-154): the line first, one line
one grade, kill-only, the outcome and its vectors chained, and every refusal before any line."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

import tests.backtest.look_register as lr
from core.optimizer.costs import CostModel
from tests.backtest.evaluate_events import evaluate_events
from tests.backtest.look_claims import Claim, Origin, load_vector
from tests.backtest.look_declarations import Declaration
from tests.backtest.look_register import LookRefused, LookRegister
from tests.backtest.test_event_sim import _planted
from tests.backtest.verdict import kill_verdict

SELECTED = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-09-25",
                  exposure="web", reference="McConnell & Xu (2008)", published="2008-03-01")
CLAIM = Claim(family="tom_d3_v1", variant="fixed", universe_id="D3-LAB", origin=SELECTED, simulator="event",
              declared_space={"grid": {}, "formula": "long t-2 close -> t+3 close", "instruments": ["US500"]},
              recon_commit="c0ffee", declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
WINDOW = dict(start=date(2014, 1, 2), graded_from=date(2014, 4, 1), end=date(2019, 12, 31))


class LabEvents:
    name, provenance = "lab-events", "synthetic"


@pytest.fixture
def reg(tmp_path, monkeypatch) -> LookRegister:
    monkeypatch.setattr(lr, "git_state", lambda repo=None: ("c0ffee", False))
    return LookRegister(tmp_path / "looks")


def _grade(reg, cfg, claim=CLAIM, costs=None, **window):
    return evaluate_events(register=reg, cfg=cfg, source=LabEvents(), family=claim.family, claim=claim,
                           account="lab", hourly={"US500": _planted(0.0001, seed=11)},
                           costs=costs or {"US500": CostModel(0.0, 0.05)}, **{**WINDOW, **window})


def test_an_event_grade_writes_its_line_first_then_chains_its_outcome_and_vectors(reg, shipped_config) -> None:
    look, result = _grade(reg, shipped_config)
    assert look.tier == 0 and look.cycle is None and look.claim["simulator"] == "event"
    with pytest.raises(LookRefused, match="already graded"):
        reg.consume(look)                                                    # one line, one grade
    outcome = reg.outcome(look.look_id)
    dates, daily = load_vector(reg.root, outcome["daily_vector"])
    assert dates[0] >= WINDOW["graded_from"] and len(daily) == outcome["graded_days"]
    assert sum(daily) == pytest.approx(sum(e["weight"] * e["net"] for e in result.events))
    assert outcome["events"] == outcome["per_index"]["US500"]["events"] == len(result.events) == 68
    for name in ("benchmark_vector", "cost2x_vector"):
        assert load_vector(reg.root, outcome["context"][name])[0] == dates
    assert np.mean(load_vector(reg.root, outcome["context"]["cost2x_vector"])[1]) < np.mean(daily)
    verdict = kill_verdict(reg.root, look.look_id)
    assert verdict.hac_t == pytest.approx(outcome["hac_t"]) and not verdict.killed


@pytest.mark.parametrize("claim, costs, window, match", [
    (replace(CLAIM, simulator="rsim"), None, {}, "'event' simulator"),
    (replace(CLAIM, origin=Origin("human")), None, {}, "can only kill"),
    (replace(CLAIM, origin=Origin("literature", reference="McConnell & Xu (2008)", published="2008-03-01")),
     None, {}, "can only kill"),                                             # a pass would need a verdict
    (CLAIM, {"US500": CostModel(0.0, 0.05, stress=2.0), "US30": CostModel(0.0, 0.05)}, {}, "cost stress"),
    (CLAIM, None, {"graded_from": date(2014, 1, 2)}, "graded window"),
])
def test_a_grade_that_cannot_honestly_run_is_refused_before_any_line(reg, shipped_config, claim, costs, window,
                                                                     match) -> None:
    with pytest.raises(LookRefused, match=match):
        _grade(reg, shipped_config, claim=claim, costs=costs, **window)
    assert not reg.scan().lines
