"""ParamLibrary staging/promotion teeth (ACIS-03 §7/§10/§13, C-QIEA-1..5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.optimizer.param_library import (
    ParamLibrary,
    PromotionForbiddenError,
    is_session_boundary,
)
from core.optimizer.param_types import ParamSet
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import CapturingLogger, make_paramset

BOUNDARIES = ["22:00", "00:00", "07:00", "12:00"]
AT_BOUNDARY = datetime(2026, 7, 6, 22, 0, tzinfo=timezone.utc)
MID_SESSION = datetime(2026, 7, 6, 21, 59, tzinfo=timezone.utc)  # C-QIEA-1: close-looking


class FakeGate:
    def __init__(self, count: int = 0) -> None:
        self.count = count

    def open_position_count(self) -> int:
        return self.count


class StrictGate(FakeGate):
    """C-QIEA-4: any attribute beyond the flat count is a violation."""

    def __getattr__(self, name: str):
        raise AssertionError(f"ParamLibrary touched forbidden gate attribute {name!r}")


def make_lib(tmp_path, gate: FakeGate) -> tuple[ParamLibrary, CapturingLogger]:
    log = CapturingLogger()
    lib = ParamLibrary(tmp_path / "params.db", BOUNDARIES, 3, gate, log)
    return lib, log


# ---------------------------- boundary definition (C1) ------------------------ #

def test_boundary_is_minute_exact_against_the_declared_list() -> None:
    assert is_session_boundary(AT_BOUNDARY, BOUNDARIES)
    assert not is_session_boundary(MID_SESSION, BOUNDARIES)


def test_boundary_check_is_utc_aware() -> None:
    plus_one = datetime(2026, 7, 6, 23, 0, tzinfo=timezone(timedelta(hours=1)))
    assert is_session_boundary(plus_one, BOUNDARIES)  # 23:00+01:00 == 22:00 UTC
    with pytest.raises(ValueError):
        is_session_boundary(datetime(2026, 7, 6, 22, 0), BOUNDARIES)


# ---------------------------- promotion guard (C-QIEA-1) ---------------------- #

def test_promote_mid_session_raises_even_close_looking(tmp_path) -> None:
    lib, log = make_lib(tmp_path, FakeGate(0))
    lib.stage(make_paramset())
    with pytest.raises(PromotionForbiddenError):
        lib.promote(MID_SESSION)
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None  # store untouched
    assert len(lib.get_pending()) == 1
    assert log.events("PROMOTION_FORBIDDEN")[0]["data"]["reason"] == "not_session_boundary"


def test_promote_with_open_positions_raises(tmp_path) -> None:
    lib, log = make_lib(tmp_path, FakeGate(2))
    lib.stage(make_paramset())
    with pytest.raises(PromotionForbiddenError):
        lib.promote(AT_BOUNDARY)
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None
    assert log.events("PROMOTION_FORBIDDEN")[0]["data"]["open_positions"] == 2


def test_boundary_flat_promotion_postconditions(tmp_path) -> None:
    """Assert the store, not return codes (§14): active + history + cleared pending."""
    lib, log = make_lib(tmp_path, FakeGate(0))
    ps = make_paramset()
    pending_id = lib.stage(ps)
    lib.promote(AT_BOUNDARY)
    active = lib.get_active(ps.regime)
    assert active is not None
    assert active.params == ps
    assert active.source_pending_id == pending_id
    assert active.promoted_at == AT_BOUNDARY
    assert lib.get_pending() == []
    history = lib._db.execute("SELECT param_set_id, regime FROM param_history").fetchall()
    assert history == [(ps.param_set_id, ps.regime.value)]
    assert len(log.events("PARAM_PROMOTED")) == 1


# ---------------------------- staleness (C-QIEA-2) ---------------------------- #

def test_stall_counts_and_surfaces_without_promoting(tmp_path) -> None:
    lib, log = make_lib(tmp_path, FakeGate(1))
    lib.stage(make_paramset())
    for day in range(3):
        lib.on_boundary(AT_BOUNDARY + timedelta(days=day))
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None      # never promoted
    entry = lib.get_pending()[0]
    assert entry.boundaries_skipped == 3
    snap = lib.pending_snapshot()[0]
    assert snap["stalled"] is True                                  # surfaced at threshold 3
    stalls = log.events("PARAM_PROMOTION_STALLED")
    assert [e["data"]["boundaries_skipped"] for e in stalls] == [1, 2, 3]


def test_flatten_at_next_boundary_promotes_exactly_once(tmp_path) -> None:
    gate = FakeGate(1)
    lib, log = make_lib(tmp_path, gate)
    lib.stage(make_paramset())
    for day in range(3):
        lib.on_boundary(AT_BOUNDARY + timedelta(days=day))
    gate.count = 0
    promoted = lib.on_boundary(AT_BOUNDARY + timedelta(days=3))
    assert promoted == [RegimeType.STRONG_TREND_UP.value]
    assert lib.has_active(RegimeType.STRONG_TREND_UP)
    assert lib.get_pending() == []
    assert len(log.events("PARAM_PROMOTED")) == 1


# ---------------------------- no close-trigger (C-QIEA-3) --------------------- #

def test_position_close_is_not_a_promotion_trigger(tmp_path) -> None:
    """Nothing subscribes to position events: going flat mid-session changes no state,
    and even an explicit promote() while flat mid-session still raises."""
    gate = FakeGate(1)
    lib, _ = make_lib(tmp_path, gate)
    lib.stage(make_paramset())
    gate.count = 0  # position closed mid-session
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None
    with pytest.raises(PromotionForbiddenError):
        lib.promote(MID_SESSION)
    assert len(lib.get_pending()) == 1


# ---------------------------- isolation (C-QIEA-4) ---------------------------- #

def test_gate_surface_is_only_open_position_count(tmp_path) -> None:
    lib, _ = make_lib(tmp_path, StrictGate(0))
    lib.stage(make_paramset())
    lib.promote(AT_BOUNDARY)  # full cycle without touching any other gate attribute
    assert lib.has_active(RegimeType.STRONG_TREND_UP)


# ---------------------------- immutability (C-QIEA-5) ------------------------- #

def test_active_params_byte_stable_while_successor_stalls(tmp_path) -> None:
    gate = FakeGate(0)
    lib, _ = make_lib(tmp_path, gate)
    first = make_paramset(param_set_id="ps-first")
    lib.stage(first)
    lib.promote(AT_BOUNDARY)
    before = lib._db.execute("SELECT params FROM param_active").fetchone()[0]
    successor = make_paramset(param_set_id="ps-second", ema_fast=8)
    lib.stage(successor, now=AT_BOUNDARY + timedelta(hours=1))
    gate.count = 1
    lib.on_boundary(AT_BOUNDARY + timedelta(days=1))               # stall, not promote
    after = lib._db.execute("SELECT params FROM param_active").fetchone()[0]
    assert after == before                                          # byte-identical
    assert lib.get_active(first.regime).params == first
    assert isinstance(lib.get_active(first.regime).params, ParamSet)  # frozen type out


def test_staging_replaces_prior_pending_for_regime(tmp_path) -> None:
    lib, log = make_lib(tmp_path, FakeGate(0))
    lib.stage(make_paramset(param_set_id="ps-old"))
    lib.stage(make_paramset(param_set_id="ps-new", ema_fast=9))
    pending = lib.get_pending()
    assert len(pending) == 1 and pending[0].params.param_set_id == "ps-new"
    assert log.events("PARAM_STAGED")[1]["data"]["replaced_previous"] is True


# ---------------- phase-4 audit triage regression (GAP-0036) ---------------- #

def test_gap0036_promotion_sweep_is_all_or_nothing(tmp_path) -> None:
    """A failure on ANY pending entry rolls back the WHOLE sweep: no regime is
    promoted, all pending survive, and the error is taxonomy (DataQualityError),
    never a raw sqlite exception with a partial write behind it."""
    from core.data.errors import DataQualityError

    lib, _ = make_lib(tmp_path, FakeGate(0))
    lib.stage(make_paramset(regime=RegimeType.STRONG_TREND_UP, param_set_id="dup-id"))
    lib.stage(make_paramset(regime=RegimeType.RANGING_TIGHT, param_set_id="dup-id"))
    with pytest.raises(DataQualityError):
        lib.promote(AT_BOUNDARY)  # duplicate audit id => history PK violation
    assert lib.get_active(RegimeType.STRONG_TREND_UP) is None   # nothing promoted
    assert lib.get_active(RegimeType.RANGING_TIGHT) is None
    assert len(lib.get_pending()) == 2                          # nothing stranded/lost
    assert lib._db.execute("SELECT COUNT(*) FROM param_history").fetchone()[0] == 0
