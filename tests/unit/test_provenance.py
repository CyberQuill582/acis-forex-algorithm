"""ACIS-11 provenance/lifecycle scaffolding (§14, postcondition style)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.data.errors import DataQualityError
from core.optimizer.param_library import PromotionForbiddenError
from core.signals.provenance import ProvenanceRecord, ProvenanceStore, Rung
from tests.optimizer_fixtures import CapturingLogger
from tests.signals_fixtures import T0


def mk_record(sid="strat_v1", **overrides) -> ProvenanceRecord:
    base = dict(strategy_id=sid, citation="Author, Work (2020)",
                claimed_inefficiency="an inefficiency", why_it_persists="a reason",
                falsifier="12m net expectancy < 0", registered_at=T0)
    base.update(overrides)
    return ProvenanceRecord(**base)


def mk_store(tmp_path) -> tuple[ProvenanceStore, CapturingLogger]:
    log = CapturingLogger()
    return ProvenanceStore(tmp_path / "prov.db", 90, log), log


# -------------------- registration gate (C-PRV-1) -------------------- #

@pytest.mark.parametrize("field", ["citation", "claimed_inefficiency",
                                   "why_it_persists", "falsifier", "strategy_id"])
def test_blank_provenance_field_refused(field: str) -> None:
    with pytest.raises(DataQualityError):
        mk_record(**{field: "   "})


def test_registration_and_duplicate_refused(tmp_path) -> None:
    store, log = mk_store(tmp_path)
    store.register(mk_record())
    assert store.is_registered("strat_v1")
    assert store.rung_of("strat_v1") is Rung.INCUBATION
    with pytest.raises(DataQualityError):
        store.register(mk_record())
    assert len(log.events("STRATEGY_REGISTERED")) == 1


def test_unregistered_strategy_raises(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    with pytest.raises(DataQualityError):
        store.rung_of("ghost_v1")
    with pytest.raises(DataQualityError):
        store.entry_allowed("ghost_v1", T0)


# -------------------- rung ladder (§8 exhaustive) -------------------- #

def test_promotion_path_and_human_token_gate(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    store.promote_one_rung("strat_v1", "backtest evidence", T0)
    assert store.rung_of("strat_v1") is Rung.PAPER
    with pytest.raises(PromotionForbiddenError):     # C-PRV-3: no self-promotion
        store.promote_one_rung("strat_v1", "paper evidence", T0)
    store.promote_one_rung("strat_v1", "paper evidence", T0, human_token="OWNER-SIGNED")
    assert store.rung_of("strat_v1") is Rung.LIVE


def test_promotion_requires_evidence(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    with pytest.raises(DataQualityError):
        store.promote_one_rung("strat_v1", "   ", T0)


def test_illegal_edge_raises(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    with pytest.raises(DataQualityError):            # INCUBATION -> LIVE skips PAPER
        store._transition("strat_v1", Rung.LIVE, "cheat", T0)
    # (INCUBATION -> RETIRED became a LEGAL disposal edge at the GAP-0045 triage.)
    store.promote_one_rung("strat_v1", "evidence", T0)
    with pytest.raises(DataQualityError):            # PAPER -> RETIRED skips DECAYED
        store.retire("strat_v1", "regime X returns", {}, T0)


# -------------------- re-validation + GAP-0019 (C-PRV-2) -------------------- #

def test_revalidation_pass_rearms_due_date(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    later = T0 + timedelta(days=40)
    store.apply_revalidation("strat_v1", "PASS", later)
    row = store._db.execute("SELECT revalidation_due FROM rung_state").fetchone()
    assert row[0] == (later + timedelta(days=90)).isoformat()


def test_gap0019_demotion_transition(tmp_path) -> None:
    store, log = mk_store(tmp_path)
    store.register(mk_record())
    store.promote_one_rung("strat_v1", "evidence", T0)          # PAPER
    store.apply_revalidation("strat_v1", "FAIL", T0)            # demote path
    assert store.entry_allowed("strat_v1", T0) is False         # frozen INSTANTLY
    assert store.rung_of("strat_v1") is Rung.PAPER              # rung not yet moved
    for n in range(1, 4):                                       # positions still open
        assert store.on_boundary("strat_v1", open_positions=2,
                                 now=T0 + timedelta(days=n)) is False
    stalls = log.events("STRATEGY_REMOVAL_STALLED")
    assert [e["data"]["boundaries_skipped"] for e in stalls] == [1, 2, 3]
    assert store.on_boundary("strat_v1", open_positions=0,      # flat boundary
                             now=T0 + timedelta(days=4)) is True
    assert store.rung_of("strat_v1") is Rung.DECAYED


def test_invalid_verdict_raises(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    with pytest.raises(DataQualityError):
        store.apply_revalidation("strat_v1", "MAYBE", T0)


# -------------------- graveyard (C-PRV-5) -------------------- #

def test_graveyard_requires_revival_condition_and_revives_at_bottom(tmp_path) -> None:
    store, log = mk_store(tmp_path)
    store.register(mk_record())
    store.promote_one_rung("strat_v1", "evidence", T0)
    store.apply_revalidation("strat_v1", "FAIL", T0)
    store.on_boundary("strat_v1", open_positions=0, now=T0)     # -> DECAYED
    with pytest.raises(DataQualityError):
        store.retire("strat_v1", "  ", {}, T0)
    store.retire("strat_v1", "revive when ranging regimes exceed 40% share", {"pf": 0.9}, T0)
    assert store.rung_of("strat_v1") is Rung.RETIRED
    store.flag_revival("strat_v1", "regime stats matched", T0)
    assert store.snapshot()["graveyard"][0]["revival_flagged"] is True
    store.revive("strat_v1", T0)
    assert store.rung_of("strat_v1") is Rung.INCUBATION          # the BOTTOM rung


# -------------------- attempts (C-PRV-4) + challengers + reading list -------------------- #

def test_attempt_registry_append_only_and_monotone(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    assert store.attempts("trend_following") == 0
    store.record_attempt("trend_following", "ema 5/20 variant", now=T0)
    store.record_attempt("trend_following", "ema 8/34 variant", now=T0)
    assert store.attempts("trend_following") == 2
    assert not hasattr(store, "delete_attempt")      # no deletion API exists


def test_challenger_lane_never_touches_champion_rung(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record("champion_v1"))
    store.promote_one_rung("champion_v1", "evidence", T0)
    store.add_challenger("challenger_v1", "champion_v1", 60, T0)
    assert store.challengers_of("champion_v1") == ["challenger_v1"]
    assert store.rung_of("champion_v1") is Rung.PAPER  # unchanged (C-PRV-6)


def test_reading_list_rejection_requires_reason(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    with pytest.raises(DataQualityError):
        store.record_source_disposition("Some EA marketing thread", "rejected_with_reason",
                                        "  ", T0)
    store.record_source_disposition("Moskowitz-Ooi-Pedersen 2012", "implemented", "", T0)
    assert store.snapshot()["reading_list"][0]["disposition"] == "implemented"


# -------------------- restart safety -------------------- #

def test_restart_resumes_rungs_freezes_and_counters(tmp_path) -> None:
    store, log = mk_store(tmp_path)
    store.register(mk_record())
    store.promote_one_rung("strat_v1", "evidence", T0)
    store.apply_revalidation("strat_v1", "FAIL", T0)
    store.on_boundary("strat_v1", open_positions=1, now=T0)
    store.close()
    store2 = ProvenanceStore(tmp_path / "prov.db", 90, log)
    assert store2.rung_of("strat_v1") is Rung.PAPER
    assert store2.entry_allowed("strat_v1", T0) is False
    row = store2._db.execute("SELECT boundaries_skipped FROM rung_state").fetchone()
    assert row[0] == 1


# ---------------- phase-5 audit triage regressions (GAP-0045/48) ---------------- #

def test_gap0045_frozen_incubation_cannot_promote_out(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    store.apply_revalidation("strat_v1", "FAIL", T0)        # frozen at INCUBATION
    assert store.entry_allowed("strat_v1", T0) is False
    with pytest.raises(PromotionForbiddenError):            # no escape via promotion
        store.promote_one_rung("strat_v1", "shiny backtest", T0)
    # the two legitimate exits: PASS re-validation unfreezes...
    store.apply_revalidation("strat_v1", "PASS", T0 + timedelta(days=1))
    assert store.entry_allowed("strat_v1", T0 + timedelta(days=1)) is True
    store.promote_one_rung("strat_v1", "evidence", T0 + timedelta(days=2))
    assert store.rung_of("strat_v1") is Rung.PAPER


def test_gap0045_failed_incubation_can_be_retired(tmp_path) -> None:
    store, _ = mk_store(tmp_path)
    store.register(mk_record())
    store.apply_revalidation("strat_v1", "FAIL", T0)
    store.retire("strat_v1", "revive when its regime share recovers", {"n": 0}, T0)
    assert store.rung_of("strat_v1") is Rung.RETIRED        # disposal path exists


def test_gap0048_attempt_registry_append_only_in_store(tmp_path) -> None:
    import sqlite3
    store, _ = mk_store(tmp_path)
    store.record_attempt("trend_following", "variant", now=T0)
    with pytest.raises(sqlite3.IntegrityError):
        store._db.execute("DELETE FROM attempts")
    with pytest.raises(sqlite3.IntegrityError):
        store._db.execute("UPDATE attempts SET family='x'")
    assert store.attempts("trend_following") == 1           # untouched


# -------------- a correction is a lineage successor, never a rewrite (ACIS-11 §6; GAP-P12D-116) -------------- #

def test_a_corrected_record_is_a_lineage_successor_and_the_parent_stays_as_written(tmp_path) -> None:
    from core.signals.canonical import STRATEGY_IDS, register_canonical
    from core.signals.signal_types import StrategyType

    store, _ = mk_store(tmp_path)
    store.register(mk_record("tsmom_slow_v1", citation="MOP 2012 (old text)",
                             declared_deviations=("spot vs excess: immaterial (GAP-0073)",)))
    register_canonical(store, T0)
    assert STRATEGY_IDS[StrategyType.TSMOM] == "tsmom_slow_v2"
    snap = {s["strategy_id"]: s for s in store.snapshot()["strategies"]}
    assert snap["tsmom_slow_v1"]["citation"] == "MOP 2012 (old text)"          # the parent, untouched
    assert snap["tsmom_slow_v1"]["declared_deviations"] == ["spot vs excess: immaterial (GAP-0073)"]
    v2 = snap["tsmom_slow_v2"]
    assert "lineage:tsmom_slow_v1" in v2["citation"]
    assert any("NOT immaterially" in d for d in v2["declared_deviations"])
    registered = store._db.execute("SELECT registered_at FROM provenance WHERE strategy_id = 'tsmom_slow_v2'").fetchone()[0]
    assert registered.startswith("2026-10-01")                                  # the correction's date, not the boot's


def test_a_fresh_store_registers_only_the_corrected_record(tmp_path) -> None:
    from core.signals.canonical import register_canonical

    store, _ = mk_store(tmp_path)
    register_canonical(store, T0)
    assert store.is_registered("tsmom_slow_v2") and not store.is_registered("tsmom_slow_v1")
