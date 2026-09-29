"""Register v2 (R1.2; ACIS-09 C-BT-11 v2 step 1; GAP-P12D-98/89/66): a real-data look carries its
claim, a cycle's order is a chain line, and a grade stores its daily vector by hash."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import tests.backtest.look_register as lr
from tests.backtest.look_claims import (Claim, Origin, canonical_hash, cost_map_hash, load_vector,
                                        store_vector)
from tests.backtest.look_register import LookRefused, LookRegister
from tests.backtest.oos_plan import plan_folds
from tests.backtest.sources import DukascopyTickSource

GIT = ("c0ffee", False)
FOLDS = plan_folds(2014, 2015)
SPACE = {"grid": {"fast": [8, 16, 32]}, "formula": "sign(ewmac fast/4fast)", "instruments": ["EUR_USD", "USD_JPY"]}


class _Real(DukascopyTickSource):
    def __init__(self) -> None:
        pass


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    root = tmp_path / "data" / "validation" / "looks"
    monkeypatch.setattr(lr, "CANONICAL", root)
    monkeypatch.setattr(lr, "git_state", lambda repo=None: GIT)
    return LookRegister(root)


def _claim(family="trend-v1", origin=Origin("human"), **kw) -> Claim:
    base = dict(family=family, variant="fixed", declared_space=SPACE, universe_id="R1-23",
                origin=origin, simulator="rsim", recon_commit="c0ffee")
    return Claim(**{**base, **kw})


def _look(reg, cfg, claim=None, family="trend-v1", **kw):
    return reg.register(cfg=cfg, source=_Real(), instruments=sorted(cfg.instruments.enabled), folds=FOLDS,
                        family=family, account="dev_paper", git=GIT, claim=claim, **kw)


def test_a_real_look_must_carry_its_own_familys_claim_and_the_line_records_it(canonical, acis_config) -> None:
    with pytest.raises(LookRefused, match="carries its claim"):
        _look(canonical, acis_config)
    with pytest.raises(LookRefused, match="not 'trend-v1'"):
        _look(canonical, acis_config, claim=_claim(family="carry-v1"))
    look = _look(canonical, acis_config, claim=_claim())
    line = json.loads(Path(look.path).read_text(encoding="utf-8"))["claim"]
    assert line["declared_space_hash"] == canonical_hash(SPACE) and line["universe_id"] == "R1-23"
    assert line["origin"]["kind"] == "human" and line["simulator"] == "rsim" and line["recon_commit"] == "c0ffee"
    assert line["cost_map_hash"] == cost_map_hash(acis_config, sorted(acis_config.instruments.enabled), 1.0, 0.0)


def test_the_declared_space_is_hashed_and_any_change_to_it_changes_the_hash() -> None:
    """GAP-P12D-89: the grid, the formula and the instrument list are declared before the first look."""
    same = _claim(declared_space=json.loads(json.dumps(SPACE)))
    assert same.declared_space_hash == _claim().declared_space_hash and same.variant_hash == _claim().variant_hash
    for key, value in (("grid", {"fast": [8, 16]}), ("formula", "sign(ewmac fast/2fast)"), ("instruments", ["EUR_USD"])):
        assert _claim(declared_space={**SPACE, key: value}).declared_space_hash != _claim().declared_space_hash
    assert _claim(variant="fast=16").variant_hash != _claim().variant_hash
    with pytest.raises(ValueError, match="lacks"):
        _claim(declared_space={"grid": {}, "formula": "x"})


def test_an_origin_records_what_the_contamination_law_needs() -> None:
    """Master §5.6: an LLM origin names its model and cutoff; a literature origin its dated reference."""
    with pytest.raises(ValueError, match="model"):
        Origin("llm", model_id="claude-opus-5-5")
    with pytest.raises(ValueError, match="dated reference"):
        Origin("literature", reference="Moskowitz, Ooi, Pedersen (2012)")
    with pytest.raises(ValueError, match="origin must be"):
        Origin("oracle")
    Origin("llm", model_id="claude-opus-5-5", model_cutoff="2026-06-01")
    Origin("literature", reference="Moskowitz, Ooi, Pedersen (2012), JFE 104(2)", published="2012-05-01")


def test_an_llm_plan_that_repeats_a_registered_variant_is_refused(canonical, acis_config) -> None:
    llm = Origin("llm", model_id="claude-opus-5-5", model_cutoff="2026-06-01")
    _look(canonical, acis_config, claim=_claim(origin=llm))
    with pytest.raises(LookRefused, match="repeats registered variant"):
        _look(canonical, acis_config, claim=_claim(family="trend-v2", origin=llm), family="trend-v2")
    _look(canonical, acis_config, claim=_claim(), changed="a human re-look that says what changed")


def test_the_cost_map_hash_separates_grades_priced_differently(acis_config) -> None:
    inst = sorted(acis_config.instruments.enabled)
    base = cost_map_hash(acis_config, inst, 1.0, 0.0)
    assert base == cost_map_hash(acis_config, inst, 1.0, 0.0)
    assert base != cost_map_hash(acis_config, inst, 2.0, 0.0) != cost_map_hash(acis_config, inst, 1.0, 0.0001)
    assert base != cost_map_hash(acis_config, inst[:1], 1.0, 0.0)


def test_a_cycle_row_is_a_chain_line_that_counting_skips_and_that_obeys_its_rules(canonical, acis_config) -> None:
    look = _look(canonical, acis_config, claim=_claim())
    order = [_claim().variant_hash, _claim(variant="b").variant_hash]
    row = canonical.register_cycle(cycle_id="2026Q4", order=order, alpha=0.03)
    assert row["kind"] == "cycle" and row["prev_hash"] == lr._sha(Path(look.path).read_bytes())
    scan = canonical.scan()
    assert not scan.broken and scan.lines[1]["kind"] == "cycle" and scan.lines[1]["order"] == order
    assert canonical.summary()["cycles"] == ["2026Q4"] and sum(canonical.summary()["tier_totals"].values()) == 1
    assert [x["look_id"] for x in canonical.looks()] == [look.look_id]
    with pytest.raises(LookRefused, match="already registered"):
        canonical.register_cycle(cycle_id="2026Q4", order=order, alpha=0.03)
    with pytest.raises(LookRefused, match="this quarter"):
        canonical.register_cycle(cycle_id="2026Q4-b", order=order, alpha=0.03)
    for bad, why in ((dict(order=order * 3), "distinct family-versions"),
                     (dict(order=[order[0], order[0]]), "distinct family-versions"),
                     (dict(order=[]), "distinct family-versions"), (dict(alpha=0.2), r"alpha lies in")):
        with pytest.raises(LookRefused, match=why):
            canonical.register_cycle(cycle_id="x", **{"order": order, "alpha": 0.03, **bad})
    _look(canonical, acis_config, claim=_claim(), changed="after the cycle row")
    assert not canonical.scan().broken


def test_the_daily_vector_is_stored_once_by_its_hash_and_an_edit_is_caught(canonical, tmp_path, acis_config) -> None:
    look = _look(canonical, acis_config, claim=_claim())
    days = [date(2024, 1, 1) + timedelta(days=k) for k in range(5)]
    returns = [0.001, -0.002, 0.0, 0.0015, -0.0005]
    canonical.record_outcome(look, {"sharpe": 0.1}, daily=(days, returns))
    outcome = json.loads((canonical.root / f"{look.look_id}.outcome.json").read_text(encoding="utf-8"))
    assert load_vector(canonical.root, outcome["daily_vector"]) == (days, returns)
    assert store_vector(canonical.root, days, returns) == outcome["daily_vector"]      # stored once
    path = canonical.root / "vectors" / f"{outcome['daily_vector']}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("0.001", "0.002", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="edited"):
        load_vector(canonical.root, outcome["daily_vector"])
    with pytest.raises(ValueError, match="increasing"):
        store_vector(tmp_path, [days[1], days[0]], [0.0, 0.0])
    with pytest.raises(ValueError, match="finite"):
        store_vector(tmp_path, days[:1], [float("nan")])
