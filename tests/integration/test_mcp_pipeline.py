"""Phase-10 integration: the MCP control plane drives the REAL Capital Governor
(ACIS-08 §14/§15, master §12/§15).

Proves through the real Governor — not a mock of it — that:
  · `acis_halt` makes the Governor size new orders to zero (Risk HALT semantics);
  · `acis_flatten` closes the book and freezes new opens;
  · a non-human `acis_resume` is rejected and the halt PERSISTS (halts are cheap,
    resumes are human-only — the equity/global-HALT rule, jointly with ACIS-07);
  · a human-token `acis_resume` clears the halt and sizing returns;
  · NO tool mutates `guardrail_limits.yaml` (byte-identical after a full sweep).

The control adapter lives test-side by design (§18 lean-build: the production
three-loop runtime that owns this wiring lands with the live connection, exactly
as paper_loop.py / test_risk_pipeline.py compose the layers test-side).
"""

from __future__ import annotations

from pathlib import Path

from config.account_doctrine import guardrail_hash, rulebook_hash
from config.schemas import load_config
from tests.mcp_fixtures import (GUARDRAIL_HASH, HUMAN_SECRET, RULEBOOK_HASH,
                                mk_plane)
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
GUARDRAIL_FILE = CONFIG_DIR / "guardrail_limits.yaml"
SYSTEM_FILE = CONFIG_DIR / "system_config.yaml"


class PaperBook:
    def __init__(self) -> None:
        self.open: list = ["EUR_USD_pos"]
        self.closed: list = []

    def flatten(self, scope: str) -> None:
        self.closed.extend(self.open)
        self.open = []


class GovernorControl:
    """The MCP ControlTarget realised over the real Governor + book + freeze."""

    def __init__(self, gov, book: PaperBook) -> None:
        self._gov = gov
        self._book = book
        self.freezes: list[str] = []

    def apply_halt(self, scope: str, reason: str) -> None:
        self._gov.apply_halt(scope, reason)

    def flatten(self, scope: str, reason: str) -> None:
        self.freezes.append(reason)               # block new opens (execution freeze)
        self._book.flatten(scope)                 # close positions (paper book)

    def resume(self, human_token: str) -> None:
        self._gov.resume(human_token)


def _wire():
    gov, _ = mk_governor()
    book = PaperBook()
    control = GovernorControl(gov, book)
    plane, _, _, _ = mk_plane(control=control)
    return plane, gov, book, control


def _reason():
    return None


def test_mcp_halt_zeroes_governor_sizing() -> None:
    plane, gov, _, _ = _wire()
    # baseline: the Governor sizes a normal order
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "formula"
    out = plane.call_tool("acis_halt", {"request_id": "h1", "args": {"scope": "all", "reason": "mcp"}})
    assert out["status"] == "ok"
    # through the real Governor: new sizing is now zeroed by the halt
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "halt"


def test_mcp_flatten_closes_book_and_freezes() -> None:
    plane, _, book, control = _wire()
    out = plane.call_tool("acis_flatten", {"request_id": "f1", "args": {"reason": "mcp"}})
    assert out["status"] == "ok"
    assert book.open == [] and book.closed == ["EUR_USD_pos"]
    assert control.freezes == ["mcp"]


def test_non_human_resume_rejected_and_halt_persists() -> None:
    plane, gov, _, _ = _wire()
    plane.call_tool("acis_halt", {"request_id": "h2", "args": {"scope": "all"}})
    # agent (no token) attempt to resume → rejected; the halt survives
    bad = plane.call_tool("acis_resume", {"request_id": "r_bad", "args": {"scope": "all"}})
    assert bad["status"] == "rejected"
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "halt"
    # non-empty-but-wrong token → still rejected, still halted
    wrong = plane.call_tool("acis_resume",
                            {"request_id": "r_wrong", "human_token": "nope", "args": {}})
    assert wrong["status"] == "rejected"
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "halt"


def test_human_resume_clears_halt_and_sizing_returns() -> None:
    plane, gov, _, _ = _wire()
    plane.call_tool("acis_halt", {"request_id": "h3", "args": {"scope": "all"}})
    ok = plane.call_tool("acis_resume",
                         {"request_id": "r_ok", "human_token": HUMAN_SECRET, "args": {}})
    assert ok["status"] == "ok"
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "formula"


def test_no_tool_mutates_the_guardrail_file() -> None:
    """Byte-identical guardrail file after a full sweep of every tool, including
    a stage_config attempt on a guardrail path."""
    before = GUARDRAIL_FILE.read_bytes()
    plane, _, _, _ = _wire()
    plane.call_tool("acis_halt", {"request_id": "s1", "args": {"scope": "all"}})
    plane.call_tool("acis_flatten", {"request_id": "s2", "args": {}})
    plane.call_tool("acis_resume", {"request_id": "s3", "human_token": HUMAN_SECRET, "args": {}})
    plane.call_tool("acis_set_mode", {"request_id": "s4", "human_token": HUMAN_SECRET,
                                      "args": {"mode": "live", "guardrail_hash": GUARDRAIL_HASH,
                                               "rulebook_hash": RULEBOOK_HASH}})
    plane.call_tool("acis_stage_config", {"request_id": "s5",
                                          "args": {"patch": {"guardrail_limits.var_cap_pct": 1.0}}})
    assert GUARDRAIL_FILE.read_bytes() == before


# -- GAP-P10I-06: the live gate is proven against the REAL config hashes ------- #

def test_live_gate_uses_real_config_hashes() -> None:
    """The dual-hash live ack tied to the REAL guardrail + rulebook hashes (not
    mock strings): the exact hashes pass; a tampered hash rejects (C-MCP-8)."""
    cfg = load_config(CONFIG_DIR)
    gh = guardrail_hash(cfg.guardrails)
    rb = rulebook_hash(cfg.platform_rules.accounts[cfg.system.active_account])
    plane, _, _, mode = mk_plane(guardrail_hash=gh, rulebook_hash=rb)
    # real hashes → live
    ok = plane.call_tool("acis_set_mode", {"request_id": "L1", "human_token": HUMAN_SECRET,
                                           "args": {"mode": "live", "guardrail_hash": gh,
                                                    "rulebook_hash": rb}})
    assert ok["status"] == "ok" and mode.mode == "live"
    # a tampered guardrail hash → reject
    plane2, _, _, mode2 = mk_plane(guardrail_hash=gh, rulebook_hash=rb)
    bad = plane2.call_tool("acis_set_mode", {"request_id": "L2", "human_token": HUMAN_SECRET,
                                             "args": {"mode": "live", "guardrail_hash": gh[:-1] + "0",
                                                      "rulebook_hash": rb}})
    assert bad["status"] == "rejected" and mode2.mode == "paper"


def test_stage_config_does_not_mutate_live_config_files() -> None:
    """A staged tunable is recorded for the next boundary (ACIS-03 discipline) —
    it never mutates a live config file mid-session."""
    before_sys = SYSTEM_FILE.read_bytes()
    plane, _, stager, _ = mk_plane()
    out = plane.call_tool("acis_stage_config", {
        "request_id": "sc1", "args": {"patch": {"signals.conviction_discard": 0.5}}})
    assert out["status"] == "ok" and len(stager.staged) == 1     # staged, not applied
    assert SYSTEM_FILE.read_bytes() == before_sys                # live file untouched


def test_blackout_override_enforced_surfaced_on_status() -> None:
    """A Governor BLACKOUT_OVERRIDE_ENFORCED near-miss is visible on
    acis://status for the harness to alert on (master §12)."""
    plane, _, _, _ = mk_plane(providers={"status": lambda: {
        "take_rate": 0.2, "blackout_override_enforced": [
            {"instrument": "EUR_USD", "ts": "2026-07-18T12:00:00Z"}]}})
    view = plane.read_resource("acis://status")
    assert view["blackout_override_enforced"][0]["instrument"] == "EUR_USD"
