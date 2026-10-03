"""The look register's outside anchor (GAP-P12D-86; ACIS-09 C-BT-11 v2 step 1 v1.10): every head is
pushed on a side branch without moving HEAD, and a real-data grade refuses an unpushed head. Runs
against a temporary repository and a bare temporary remote, never the project's."""

from __future__ import annotations

import subprocess

import pytest

import tests.backtest.look_anchor as la
import tests.backtest.look_register as lr
from tests.backtest.look_anchor import AnchorError, anchor, anchored    # the real functions (conftest stubs the module's)
from tests.backtest.look_gate import begin_grade
from tests.backtest.look_register import LookRefused, LookRegister
from tests.backtest.test_look_register import _grade_args, _real, _StandInMirror, canonical  # noqa: F401 (fixture)


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    (work / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(work, "add", "code.py")
    _git(work, "commit", "-q", "-m", "code")
    _git(work, "remote", "add", "origin", str(origin))
    return work


def _line(reg: LookRegister, name: str) -> None:
    reg._append(lambda scan, path: {"kind": "cycle", "cycle_id": name, "order": [], "holm": [], "alpha": 0.03,
                                    "prev_hash": scan.head})


def test_every_head_is_pushed_on_the_side_branch_and_head_never_moves(repo, tmp_path) -> None:
    reg = LookRegister(tmp_path / "looks")
    _line(reg, "c1")
    head_before, tree_before = _git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain")
    assert not anchored(reg, repo)
    anchor(reg, repo)
    assert anchored(reg, repo)
    assert _git(repo, "rev-parse", "HEAD") == head_before and _git(repo, "status", "--porcelain") == tree_before
    _line(reg, "c2")
    assert not anchored(reg, repo)                               # a new line is unanchored until pushed
    anchor(reg, repo)
    text = _git(repo, "show", f"origin/{la.BRANCH}:{la.FILE}").splitlines()
    assert [t.split()[0] for t in text] == ["000001", "000002"] and text[-1].split()[1] == reg.scan().head
    assert anchor(reg, repo) == _git(repo, "rev-parse", f"refs/heads/{la.BRANCH}")   # idempotent: no new commit


def test_a_failed_push_leaves_the_head_unanchored(repo, tmp_path) -> None:
    reg = LookRegister(tmp_path / "looks")
    _line(reg, "c1")
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "no-such-remote.git"))
    with pytest.raises(AnchorError, match="push"):
        anchor(reg, repo)
    assert not anchored(reg, repo)                               # committed locally, never seen outside


def test_a_broken_register_is_never_anchored(repo, tmp_path) -> None:
    reg = LookRegister(tmp_path / "looks")
    _line(reg, "c1")
    _line(reg, "c2")
    (reg.root / "000001.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AnchorError, match="broken"):
        anchor(reg, repo)


def test_a_real_data_grade_refuses_an_unanchored_head(canonical, acis_config, repo, monkeypatch) -> None:
    look = _real(canonical, acis_config)
    monkeypatch.setattr(la, "anchored", anchored)               # the real check, against the temporary repo
    monkeypatch.setattr(lr, "REPO", repo)
    with pytest.raises(LookRefused, match="not anchored"):
        begin_grade(look, **_grade_args(acis_config, _StandInMirror()))
    assert not (canonical.root / f"{look.look_id}.graded.json").exists()
    anchor(canonical, repo)
    begin_grade(look, **_grade_args(acis_config, _StandInMirror()))
