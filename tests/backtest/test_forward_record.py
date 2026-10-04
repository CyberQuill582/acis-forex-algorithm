"""The tournament's forward record (TOURNAMENT): append-only, hash-chained, no day before a strategy's forward
start, no day twice, no unsettled day, no entry whose first exposure has passed, the alpha budget and the
capacity enforced, and the head anchored on its own branch. Runs on temporary directories and repositories."""

from __future__ import annotations

import subprocess
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.backtest.forward_record import BRANCH, FILE, ForwardRecord, RecordRefused
from tests.backtest.look_claims import canonical_hash
from tests.backtest.tournament_rule import PARAMS, rule_line

T0 = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
H = "ab" * 32


def _entry(sid: str, start: date = date(2026, 10, 5), alpha: float = 0.0025, boundary: str | None = "2026-10-01",
           exposure: datetime | None = None) -> dict:
    return {"kind": "entry", "strategy": sid, "family": f"fam_{sid}", "variant_hash": H, "clock": "rsim_17ny",
            "instruments": ["EUR_USD"], "formula": "f", "origin": {"kind": "literature"}, "certifying_boundary": boundary,
            "forward_start": start.isoformat(),
            "first_exposure_utc": (exposure or datetime.combine(start, datetime.min.time(), timezone.utc)
                                   + timedelta(hours=21)).isoformat(),
            "sigma_daily": 0.01, "sharpe_dev": 0.5, "alpha": alpha, "spec_hash": H}


def _days(sid: str, rows, horizon: str) -> dict:
    return {"kind": "days", "strategy": sid, "rows": rows, "horizon": horizon, "inputs": H}


@pytest.fixture
def rec(tmp_path) -> ForwardRecord:
    r = ForwardRecord(tmp_path / "record")
    r.append(rule_line(), T0)
    r.append(_entry("A"), T0)
    return r


def test_a_day_before_the_forward_start_or_recorded_twice_or_unsettled_is_refused(rec) -> None:
    later = T0 + timedelta(days=5)
    with pytest.raises(RecordRefused, match="precedes its forward start"):
        rec.append(_days("A", [["2026-10-02", 0.001]], "2026-10-06"), later)
    rec.append(_days("A", [["2026-10-05", -0.0002], ["2026-10-06", 0.001]], "2026-10-06"), later)
    with pytest.raises(RecordRefused, match="no day twice"):
        rec.append(_days("A", [["2026-10-06", 0.002]], "2026-10-07"), later)
    with pytest.raises(RecordRefused, match="beyond the settled horizon"):
        rec.append(_days("A", [["2026-10-08", 0.002]], "2026-10-07"), later)
    with pytest.raises(RecordRefused, match="not before the day the line is written"):
        rec.append(_days("A", [["2026-10-09", 0.002]], "2026-10-09"), later)      # later's own date
    with pytest.raises(RecordRefused, match="finite"):
        rec.append(_days("A", [["2026-10-07", float("nan")]], "2026-10-07"), later)
    assert rec.state().days["A"] == [(date(2026, 10, 5), -0.0002), (date(2026, 10, 6), 0.001)]


def test_an_entry_registered_after_its_first_exposure_or_before_its_boundary_is_refused(rec) -> None:
    with pytest.raises(RecordRefused, match="never starts in the past"):
        rec.append(_entry("B", exposure=T0 - timedelta(minutes=1)), T0)
    with pytest.raises(RecordRefused, match="certifying boundary"):
        rec.append(_entry("C", start=date(2026, 10, 5), boundary="2026-10-07"), T0)
    with pytest.raises(RecordRefused, match="never re-declared"):
        rec.append(_entry("A"), T0)
    with pytest.raises(RecordRefused, match="active strategy"):
        rec.append(_days("Z", [["2026-10-05", 0.0]], "2026-10-05"), T0 + timedelta(days=3))


def test_the_alpha_budget_and_the_capacity_hold_and_a_retired_entry_keeps_its_alpha(rec) -> None:
    rec.append({"kind": "retire", "strategy": "A", "reason": "owner"}, T0)
    for k in range(PARAMS["capacity"] - 2):
        rec.append(_entry(f"S{k}"), T0)
    with pytest.raises(RecordRefused, match="does not fit"):                    # A's alpha is not recycled
        rec.append(_entry("big", alpha=0.0026), T0)
    rec.append(_entry("last"), T0)
    with pytest.raises(RecordRefused, match="capacity"):
        rec.append(_entry("one_more", alpha=1e-9), T0)
    with pytest.raises(RecordRefused, match="active strategy"):
        rec.append(_days("A", [["2026-10-05", 0.0]], "2026-10-05"), T0 + timedelta(days=3))


def test_an_edited_or_deleted_line_breaks_the_chain_and_refuses_every_append(rec, tmp_path) -> None:
    rec.append(_days("A", [["2026-10-05", 0.001]], "2026-10-05"), T0 + timedelta(days=3))
    rec.append(_entry("B", start=date(2026, 10, 9)), T0 + timedelta(days=3))
    p = rec.root / "000003.json"                                     # a middle line: the next one chains to it
    p.write_bytes(p.read_bytes().replace(b"0.001", b"0.009"))
    assert rec.scan().broken
    with pytest.raises(RecordRefused, match="broken"):
        rec.append(_days("A", [["2026-10-06", 0.001]], "2026-10-06"), T0 + timedelta(days=3))
    other = ForwardRecord(tmp_path / "other")
    other.append(rule_line(), T0)
    other.append(_entry("A"), T0)
    (other.root / "000001.json").unlink()
    assert any("deleted" in b for b in other.scan().broken)


def test_the_rule_is_replaceable_only_before_the_first_day_and_must_hash_to_its_params(rec) -> None:
    with pytest.raises(RecordRefused, match="hash"):
        rec.append({"kind": "rule", "params": {**PARAMS, "min_sharpe": 0.1}, "rule_hash": canonical_hash(PARAMS)}, T0)
    rec.append(rule_line(), T0)                                                    # no day yet: allowed
    rec.append(_days("A", [["2026-10-05", 0.001]], "2026-10-05"), T0 + timedelta(days=3))
    with pytest.raises(RecordRefused, match="frozen"):
        rec.append(rule_line(), T0 + timedelta(days=3))


def test_a_revision_names_a_recorded_value_or_a_skipped_day_and_never_changes_the_record(rec) -> None:
    t = T0 + timedelta(days=5)
    rec.append(_days("A", [["2026-10-05", 0.001], ["2026-10-07", 0.002]], "2026-10-07"), t)
    with pytest.raises(RecordRefused, match="revision"):
        rec.append({"kind": "revision", "strategy": "A", "date": "2026-10-05", "recorded": 0.5, "recomputed": 0.0,
                    "reason": "differs"}, t)
    rec.append({"kind": "revision", "strategy": "A", "date": "2026-10-05", "recorded": 0.001, "recomputed": 0.0011,
                "reason": "differs"}, t)
    rec.append({"kind": "revision", "strategy": "A", "date": "2026-10-06", "recorded": None, "recomputed": 0.0,
                "reason": "skipped by the record"}, t)
    assert rec.state().days["A"] == [(date(2026, 10, 5), 0.001), (date(2026, 10, 7), 0.002)]


def test_a_backwards_clock_is_refused(rec) -> None:
    with pytest.raises(RecordRefused, match="clock"):
        rec.append(_entry("B"), T0 - timedelta(hours=1))


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def test_the_head_is_anchored_on_its_own_branch_and_the_look_anchor_is_untouched(rec, tmp_path) -> None:
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    _git(work, "remote", "add", "origin", str(origin))
    assert not rec.anchored(work)
    rec.anchor(work)
    assert rec.anchored(work)
    rows = _git(work, "show", f"origin/{BRANCH}:{FILE}").splitlines()
    assert rows[-1].split()[1] == rec.scan().head
    assert "look-anchor" not in _git(origin, "branch", "--list")
    rec.append(_entry("B"), T0)
    assert not rec.anchored(work)                                                  # a new line is unanchored until pushed
    rec.anchor(work)
    last = rec.root / "000003.json"                                  # the last line: only the anchor can see an edit
    last.write_bytes(last.read_bytes().replace(b'"B"', b'"X"'))
    assert not rec.scan().broken and not rec.anchored(work)
