"""The look register (GAP-P12D-64): every grade writes its line FIRST, and the line counts.

Re-scoring revisions against the same history is the false-positive channel (the best of 20
uncounted revisions passes pure noise 21-37% of the time, VALIDATOR §5.2). The register counts
looks; it changes no threshold and no gate.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from config.schemas import load_config
from tests.backtest.harness import NOT_REPLAYED
from tests.backtest.look_register import LookRefused, LookRegister, config_hash, data_tier
from tests.backtest.oos_plan import plan_folds
from tests.backtest.oos_runner import RunInputs, run_walk_forward
from tests.backtest.report import build_report
from tests.backtest.test_oos_runner import _folds
from tests.backtest.walk_forward import Fold

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]
GIT = ("c0ffee", False)


def _look(reg, cfg, source="synthetic", folds=None, family="f", **kw):
    return reg.register(cfg=cfg, source=source, instruments=sorted(cfg.instruments.enabled),
                        folds=folds if folds is not None else _folds(), family=family, git=GIT, **kw)


def _fold(test_start: datetime, test_end: datetime) -> Fold:
    return Fold(0, test_start - timedelta(days=730), test_start, test_start + timedelta(days=7), test_end)


def test_each_look_is_one_exclusively_created_file_and_nothing_is_overwritten(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    first = _look(reg, acis_config)
    squatter = tmp_path / "looks" / "000003.json"          # a number another run already claimed
    squatter.write_text(json.dumps({"family": "other", "tier_name": "synthetic"}), encoding="utf-8")
    before = squatter.read_bytes()
    second = _look(reg, acis_config)
    assert (first.look_id, second.look_id) == ("000001", "000004")
    assert squatter.read_bytes() == before                 # claimed numbers are never overwritten
    line = json.loads(Path(second.path).read_text(encoding="utf-8"))
    assert line["git_commit"] == "c0ffee" and line["config_hash"] == config_hash(acis_config)
    assert line["previous"] == ["000001", "c0ffee", config_hash(acis_config)]
    assert set(line) >= {"registered_utc", "family", "tier_name", "instruments", "start", "end", "changed", "operator"}
    assert reg.family_counts() == {"f": {"synthetic": 2}, "other": {"synthetic": 1}}


def test_the_tier_is_derived_from_the_data_never_claimed() -> None:
    assert data_tier("synthetic-planted", plan_folds(2014, 2015)) == 0
    assert data_tier("dukascopy", plan_folds(2014, 2023)) == 2
    assert data_tier("histdata", plan_folds(2024, 2025)) == 3
    assert data_tier("dukascopy", [_fold(datetime(2010, 1, 1, tzinfo=UTC), datetime(2011, 1, 1, tzinfo=UTC))]) == 1
    assert data_tier("dukascopy", [_fold(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))]) == 4
    with pytest.raises(LookRefused, match="straddles"):
        data_tier("dukascopy", [_fold(datetime(2023, 6, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC))])
    with pytest.raises(LookRefused, match="one data tier"):
        data_tier("dukascopy", plan_folds(2023, 2023) + plan_folds(2024, 2024))


def test_a_real_family_that_looked_before_must_say_what_changed(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    first = _look(reg, acis_config, source="dukascopy", folds=plan_folds(2014, 2015), family="trend-v1")
    assert first.tier_name == "validation" and first.changed == "first look" and first.previous is None
    with pytest.raises(LookRefused, match="say what changed"):
        _look(reg, acis_config, source="dukascopy", folds=plan_folds(2014, 2015), family="trend-v1")
    second = _look(reg, acis_config, source="dukascopy", folds=plan_folds(2014, 2015), family="trend-v1",
                   changed="gene ranges narrowed")
    assert second.previous == ("000001", "c0ffee", config_hash(acis_config))
    _look(reg, acis_config, family="synthetic-again")
    _look(reg, acis_config, family="synthetic-again")        # tier 0 re-looks need no account
    with pytest.raises(LookRefused, match="name its hypothesis family"):
        _look(reg, acis_config, family="  ")


def _inputs(tmp_path, cfg, look, folds=None):
    return RunInputs(cfg=cfg, account="dev_paper", source="synthetic", loader=None, cache=None,
                     folds=folds if folds is not None else _folds(), spx_closes={}, financing=None,
                     work_dir=tmp_path / "engine", logger=None, look=look)


def test_the_grade_refuses_before_any_compute_without_its_own_line(tmp_path, acis_config) -> None:
    reg = LookRegister(tmp_path / "looks")
    good = _look(reg, acis_config)
    other_folds = _look(reg, acis_config, folds=_folds()[:1])
    other_source = _look(reg, acis_config, source="synthetic-null")
    handmade = replace(good, look_id="999999", path=str(tmp_path / "looks" / "999999.json"))
    cases = {None: "no registered look", handmade: "not on disk", other_folds: "another run",
             other_source: "another run"}
    for look, why in cases.items():
        with pytest.raises(LookRefused, match=why):
            run_walk_forward(_inputs(tmp_path, acis_config, look))
    Path(good.path).write_text(Path(good.path).read_text(encoding="utf-8").replace("f", "g", 1), encoding="utf-8")
    with pytest.raises(LookRefused, match="not on disk as registered"):
        run_walk_forward(_inputs(tmp_path, acis_config, good))
    assert not (tmp_path / "engine").exists()               # refused before the engine was built


def test_the_real_data_script_writes_its_line_before_it_grades(monkeypatch, tmp_path) -> None:
    spec = importlib.util.spec_from_file_location("run_oos_validation", ROOT / "scripts" / "run_oos_validation.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = load_config(ROOT / "config")
    seen: list = []

    def grade(inp):
        line = json.loads(Path(inp.look.path).read_text(encoding="utf-8"))    # on disk BEFORE the grade
        seen.append(line)
        report = build_report(account=inp.account, period=(datetime(2014, 1, 8, tzinfo=UTC),) * 2, n_folds=2,
                              in_sample=NOT_REPLAYED, out_of_sample=NOT_REPLAYED, per_regime={},
                              guardrail_hash="h", expected_guardrail_hash="h", var_breach_frequency=math.nan,
                              rule_violations=(), fidelity_caveats=())
        return replace(report, look={"look_id": inp.look.look_id, "family_looks": {line["family"]: {"validation": 1}}})
    for name, fn in (("ROOT", tmp_path), ("load_config", lambda p: cfg), ("missing_labels", lambda *a: []),
                     ("load_spx_closes", lambda p: {}), ("load_rate_table", lambda p: None),
                     ("make_financing", lambda t: None), ("run_walk_forward", grade)):
        monkeypatch.setattr(mod, name, fn)
    monkeypatch.setattr(sys, "argv", ["run_oos_validation.py", "--first-test-year", "2014", "--last-test-year", "2015"])
    with pytest.raises(SystemExit):                          # no family, no look, no grade
        mod.main()
    assert seen == [] and not (tmp_path / "data" / "validation" / "looks").exists()
    monkeypatch.setattr(sys, "argv", sys.argv + ["--family", "trend-v1", "--operator", "owner"])
    assert mod.main() == 0
    assert seen[0]["family"] == "trend-v1" and seen[0]["tier_name"] == "validation" and seen[0]["operator"] == "owner"
    assert mod.main() == 2 and len(seen) == 1                # a second look must say what changed
