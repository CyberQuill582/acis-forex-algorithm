"""Ledger closure law (CLAUDE.md; SPEC_CONSTITUTION A15) — the machine check that makes
forgetting structurally detectable. Runs in CI with the rest of the suite: a finding,
decision or suggestion that is not closed under reference fails the build.

The rules themselves live in scripts/ledger_check.py (also the session-start digest).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ledger_check as lc  # noqa: E402


def test_ledgers_are_closed_under_reference() -> None:
    violations, entries = lc.check()
    assert entries, "no ledger entries parsed — the parser or the ledger path is broken"
    assert not violations, "ledger-closure violations:\n" + "\n".join(violations)


def test_checker_detects_each_failure_class(tmp_path, monkeypatch) -> None:
    """The check must actually bite: a synthetic repo with one violation per rule."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_real.py").write_text("def test_real_proof():\n    pass\n")
    (tmp_path / "core").mkdir()
    dangling = "GAP-" + "9999"          # built at runtime: a literal would be a real dangling ref
    (tmp_path / "core" / "mod.py").write_text(f"# see {dangling} for why\n")
    (tmp_path / "KNOWN_GAPS.md").write_text(
        "## GAP-0001: open item nobody put on the worklist\n- Status: open\n\n"
        "## GAP-0002: fixed but its proof test was renamed\n- Status: fixed\n"
        "- Proof: `test_renamed_away`\n- Residual: none — complete fix.\n\n"
        "## GAP-0003: fixed with a dangling residual\n- Status: fixed\n"
        "- Proof: `test_real_proof`\n\n"
        "## GAP-0004: parked without a reason\n- Status: accepted-risk\n\n"
        "## GAP-0005: no status at all\n- Area: x\n", encoding="utf-8")
    (tmp_path / "KNOWN_GAPS_CLOSED.md").write_text(
        "## GAP-0006: live item buried in the archive\n- Status: open\n", encoding="utf-8")
    (tmp_path / "TODO.md").write_text("- [ ] something about GAP-0006\n", encoding="utf-8")
    monkeypatch.setattr(lc, "ROOT", tmp_path)
    monkeypatch.setattr(lc, "_NAME_INDEX", None)
    violations, _ = lc.check()
    joined = "\n".join(violations)
    for rule, needle in [("L2", dangling), ("L3", "GAP-0005"), ("L4", "test_renamed_away"),
                         ("L5", "GAP-0003"), ("L6", "GAP-0001"), ("L7", "GAP-0006"),
                         ("L8", "GAP-0004")]:
        assert any(v.startswith(rule) and needle in v for v in violations), (rule, joined)
