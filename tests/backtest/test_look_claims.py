"""Register v2 (R1.2; ACIS-09 C-BT-11 v2 step 1; GAP-P12D-98/89/66/127): a real-data look carries its
claim, a cycle's order is a chain line, and a grade stores its daily vector by hash. Each dual-audit
finding fixed in-session has its test here (GAP-P12D-127)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import tests.backtest.look_claims as lc
import tests.backtest.look_register as lr
from tests.backtest.look_claims import (Claim, Origin, canonical_hash, canonical_space, cost_map_hash,
                                        load_vector, spending_alpha, store_vector)
from tests.backtest.look_register import LookRefused, LookRegister
from tests.backtest.oos_plan import plan_folds
from tests.backtest.sources import DukascopyTickSource

GIT = ("c0ffee", False)
FOLDS = plan_folds(2014, 2015)
SPACE = {"grid": {"fast": [8, 16, 32]}, "formula": "sign(ewmac fast/4fast)", "instruments": ["EUR_USD", "USD_JPY"]}
LLM = Origin("llm", model_id="claude-opus-5-5", model_cutoff="2026-06-01", proposed="2026-09-29", exposure="web")


class _Real(DukascopyTickSource):
    def __init__(self) -> None:
        pass


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    root = tmp_path / "data" / "validation" / "looks"
    monkeypatch.setattr(lr, "CANONICAL", root)
    monkeypatch.setattr(lr, "git_state", lambda repo=None: GIT)
    monkeypatch.setattr(lc, "REAL_LOOKS_OPEN", True)      # opened here; closed in the repo until R1.4
    return LookRegister(root)


def _claim(family="trend-v1", origin=Origin("human"), **kw) -> Claim:
    base = dict(family=family, variant="fixed", declared_space=SPACE, universe_id="R1-23",
                origin=origin, simulator="rsim", recon_commit="c0ffee")
    return Claim(**{**base, **kw})


def _look(reg, cfg, claim=None, family="trend-v1", **kw):
    return reg.register(cfg=cfg, source=_Real(), instruments=sorted(cfg.instruments.enabled), folds=FOLDS,
                        family=family, account="dev_paper", git=GIT, claim=claim, **kw)


def test_real_data_looks_and_cycle_rows_are_closed_until_r1_4(tmp_path, monkeypatch, acis_config) -> None:
    """GAP-P12D-127: R-1 allows no real-data look before R1.1-R1.4 are green; the register's
    recording fixes land first, because an append-only line cannot gain a declaration later."""
    assert lc.REAL_LOOKS_OPEN is False
    root = tmp_path / "data" / "validation" / "looks"
    monkeypatch.setattr(lr, "CANONICAL", root)
    with pytest.raises(LookRefused, match="closed until R1.4"):
        _look(LookRegister(root), acis_config, claim=_claim())
    with pytest.raises(LookRefused, match="open with real-data looks"):
        LookRegister(root).register_cycle(cycle_id="c1", order=[_claim().variant_hash])


def test_a_real_look_must_carry_its_own_familys_claim_and_the_line_records_it(canonical, acis_config) -> None:
    with pytest.raises(LookRefused, match="carries its claim"):
        _look(canonical, acis_config)
    with pytest.raises(LookRefused, match="not 'trend-v1'"):
        _look(canonical, acis_config, claim=_claim(family="carry-v1"))
    with pytest.raises(LookRefused, match="not the instruments this look grades"):      # R12I-03
        _look(canonical, acis_config, claim=_claim(declared_space={**SPACE, "instruments": ["EUR_USD"]}))
    look = _look(canonical, acis_config, claim=_claim(origin=LLM))
    line = json.loads(Path(look.path).read_text(encoding="utf-8"))["claim"]
    assert line["declared_space_hash"] == canonical_hash(canonical_space(SPACE)) and line["universe_id"] == "R1-23"
    assert line["origin"] == {"kind": "llm", "model_id": "claude-opus-5-5", "model_cutoff": "2026-06-01",
                              "proposed": "2026-09-29", "exposure": "web", "reference": "",
                              "published": ""}                                           # R12I-10 mutant 6
    assert line["certifying_boundary"] == "2026-09-29"                                # v2.24: the later date
    assert line["simulator"] == "rsim" and line["recon_commit"] == "c0ffee"
    assert line["cost_map_hash"] == cost_map_hash(acis_config, sorted(acis_config.instruments.enabled), 1.0, 0.0)


def test_the_declared_space_is_hashed_and_any_change_to_it_changes_the_hash() -> None:
    """GAP-P12D-89: the grid, the formula and the instrument list are declared before the first look."""
    for key, value in (("grid", {"fast": [8, 16]}), ("formula", "sign(ewmac fast/2fast)"), ("instruments", ["EUR_USD"])):
        assert _claim(declared_space={**SPACE, key: value}).declared_space_hash != _claim().declared_space_hash
    assert _claim(variant="fast=16").variant_hash != _claim().variant_hash
    for bad in ({"grid": {}, "formula": "x"}, {**SPACE, "note": "v2"}):
        with pytest.raises(ValueError, match="exactly the keys"):
            _claim(declared_space=bad)


@pytest.mark.parametrize("respelled", [                    # R12I-01 / E-R12-08: one plan, one hash
    {**SPACE, "instruments": ["USD_JPY", "EUR_USD"]},
    {**SPACE, "grid": {"fast": [32, 16, 8]}},
    {**SPACE, "grid": {"fast": [8.0, 16.0, 32.0]}},
    {**SPACE, "formula": "sign(ewmac  fast/4fast) "},
    {**SPACE, "formula": "SIGN(EWMAC FAST/4FAST)"},
])
def test_the_same_plan_respelled_is_the_same_variant(respelled) -> None:
    assert _claim(declared_space=respelled).variant_hash == _claim().variant_hash
    assert _claim(universe_id="r1-23-bis", variant="Fixed").variant_hash == _claim().variant_hash


def test_an_origin_records_what_the_contamination_law_needs() -> None:
    """Master v2.24 §5.6: an LLM origin names its model, training-data cutoff, proposal date and
    exposure; a literature origin its dated reference; no origin carries another kind's fields."""
    model = dict(model_id="claude-opus-5-5", model_cutoff="2026-06-01", proposed="2026-09-29", exposure="web")
    for bad, why in (({"kind": "llm", "model_id": "claude-opus-5-5"}, "training-data cutoff"),
                     ({"kind": "llm", **model, "exposure": "telepathy"}, "exposure"),
                     ({"kind": "literature", "reference": "Moskowitz, Ooi, Pedersen (2012)"}, "dated reference"),
                     ({"kind": "oracle"}, "origin must be"),
                     ({"kind": "human", **model}, "say llm"),
                     ({"kind": "llm", **model, "model_id": " "}, "model")):
        with pytest.raises(ValueError, match=why):
            Origin(**bad)
    assert Origin("llm", **{**model, "model_cutoff": "20260601"}).model_cutoff == "2026-06-01"


def test_the_certifying_boundary_is_the_later_of_the_cutoff_and_an_exposed_proposal() -> None:
    """E-R12-02 (owner-ratified): a web-using proposer's horizon is the day it proposed the plan."""
    model = dict(model_id="m", model_cutoff="2026-06-01", proposed="2026-09-29")
    assert Origin("llm", **model, exposure="web").boundary() == date(2026, 9, 29)
    assert Origin("llm", **model, exposure="none").boundary() == date(2026, 6, 1)
    paper = dict(reference="Moskowitz, Ooi, Pedersen (2012), JFE 104(2)", published="2012-05-01")
    assert Origin("literature", **paper).boundary() == date(2012, 5, 1)
    picked = Origin("literature", **paper, **model, exposure="repository")          # an LLM selected it
    assert picked.llm_touched and picked.boundary() == date(2026, 9, 29)
    assert Origin("human").boundary() is None


def test_an_llm_variant_is_refused_again_under_any_origin(canonical, acis_config) -> None:
    """R1-D13 + E-R12-01: an LLM plan may not repeat, and relabelling it human or literature does not
    remove the model's memory."""
    _look(canonical, acis_config, claim=_claim(origin=LLM))
    with pytest.raises(LookRefused, match="repeats registered variant"):
        _look(canonical, acis_config, claim=_claim(family="trend-v2", origin=LLM), family="trend-v2")
    for origin in (Origin("human"), Origin("literature", reference="MOP (2012)", published="2012-05-01")):   # E-R12-01
        with pytest.raises(LookRefused, match="registered as an LLM plan"):
            _look(canonical, acis_config, claim=_claim(origin=origin), changed="relabelled")
    _look(canonical, acis_config, claim=_claim(variant="fast=16"), changed="a different, human plan")


def test_the_cost_map_hash_separates_grades_priced_differently(acis_config) -> None:
    inst = sorted(acis_config.instruments.enabled)
    variants = [cost_map_hash(acis_config, inst, 1.0, 0.0), cost_map_hash(acis_config, inst, 2.0, 0.0),
                cost_map_hash(acis_config, inst, 1.0, 0.0001), cost_map_hash(acis_config, inst[:1], 1.0, 0.0)]
    assert variants[0] == cost_map_hash(acis_config, inst, 1.0, 0.0)
    assert len(set(variants)) == len(variants)                                    # pairwise (R12I-10)
    eur = acis_config.instruments.instruments["EUR_USD"]
    for change in ({"costs": eur.costs.model_copy(update={"slippage_per_side": 0.00003})},
                   {"max_plausible_spread": 0.0006}, {"swap_convention": "t_plus_2"}):
        priced = acis_config.instruments.model_copy(update={"instruments": {
            **acis_config.instruments.instruments, "EUR_USD": eur.model_copy(update=change)}})
        assert cost_map_hash(acis_config.model_copy(update={"instruments": priced}), inst, 1.0, 0.0) != variants[0]


def test_a_cycle_orders_unlooked_variants_at_the_spending_alpha_one_a_utc_quarter(canonical, acis_config) -> None:
    looked = _look(canonical, acis_config, claim=_claim())                           # variant a, graded
    first = datetime.now(timezone.utc) + timedelta(days=10)
    order = [_claim(variant="b").variant_hash, _claim(variant="c").variant_hash]
    row = canonical.register_cycle(cycle_id="c1", order=order, now_fn=lambda: first)
    assert row["kind"] == "cycle" and row["alpha"] == 0.03                         # D-d: cycle 1 spends 0.03
    assert not canonical.scan().broken and canonical.scan().lines[1]["order"] == order
    assert canonical.summary()["cycles"] == ["c1"] and sum(canonical.summary()["tier_totals"].values()) == 1
    assert [x["look_id"] for x in canonical.looks()] == [looked.look_id]
    later, second = [_claim(variant=f"v{k}").variant_hash for k in range(3)], first + timedelta(days=100)
    for bad, why in ((dict(cycle_id="c1"), "already registered"),
                     (dict(now_fn=lambda: first), "this quarter"),
                     (dict(order=[_claim().variant_hash]), "before any real look"),   # R12I-04: post hoc
                     (dict(alpha=0.05), "spending schedule"),                         # R12I-05
                     (dict(order=["best one", "whatever"]), "64 lower-case hex"),
                     (dict(order="abc"), "64 lower-case hex"),
                     (dict(order=[later[0], later[0]]), "distinct family-versions"),
                     (dict(order=[_claim(variant=f"w{k}").variant_hash for k in range(6)]), "distinct family-versions"),
                     (dict(now_fn=lambda: first - timedelta(days=1)), "fix the clock")):   # R12I-06
        with pytest.raises(LookRefused, match=why):
            canonical.register_cycle(**{"cycle_id": "c2", "order": later, "now_fn": lambda: second, **bad})
    assert canonical.register_cycle(cycle_id="c2", order=later, now_fn=lambda: second)["alpha"] == 0.01
    assert [spending_alpha(k) for k in range(4)] == [0.03, 0.01, 0.005, 0.0025]      # lifetime <= 0.05


def test_a_line_of_a_kind_the_register_cannot_read_fails_it_closed(canonical, acis_config) -> None:
    look = _look(canonical, acis_config, claim=_claim())
    (canonical.root / "000002.json").write_text(json.dumps(
        {"kind": "evaluate", "prev_hash": lr._sha(Path(look.path).read_bytes())}), encoding="utf-8")
    assert any("cannot read" in b for b in canonical.scan().broken)                   # R12I-13
    assert canonical.family_counts() == {"trend-v1": {"validation": 1}}               # and counting survives


def test_the_daily_vector_is_stored_once_by_its_hash_and_an_edit_is_caught(canonical, tmp_path, acis_config) -> None:
    look = _look(canonical, acis_config, claim=_claim())
    days = [date(2024, 1, 1) + timedelta(days=k) for k in range(5)]
    returns = [0.001, -0.002, 0.0, 0.0015, -0.0005]
    with pytest.raises(LookRefused, match="not a graded look"):                       # R12I-08
        canonical.record_outcome(look, {"sharpe": 0.1}, daily=(days, returns))
    canonical.consume(look)
    canonical.record_outcome(look, {"sharpe": 0.1}, daily=(days, returns))
    outcome = json.loads((canonical.root / f"{look.look_id}.outcome.json").read_text(encoding="utf-8"))
    assert load_vector(canonical.root, outcome["daily_vector"]) == (days, returns)
    assert store_vector(canonical.root, days, returns) == outcome["daily_vector"]      # stored once
    path = canonical.root / "vectors" / f"{outcome['daily_vector']}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("0.001", "0.002", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="edited"):
        load_vector(canonical.root, outcome["daily_vector"])
    for dates, rets, why in (([days[1], days[0]], [0.0, 0.0], "increasing"), (days[:1], [float("nan")], "finite"),
                             ([datetime(2024, 1, 2, 9), datetime(2024, 1, 2, 17)], [0.0, 0.0], "never datetimes")):
        with pytest.raises(ValueError, match=why):                                    # R12I-09 / E-R12-09
            store_vector(tmp_path, dates, rets)
