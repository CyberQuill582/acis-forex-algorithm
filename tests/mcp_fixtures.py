"""Shared fixtures for the phase-10 MCP control-plane tests (ACIS-08 §14)."""

from __future__ import annotations

import io

from core.data.jsonl_logging import JsonlEventLogger
from monitoring.auth import HumanTokenVerifier
from monitoring.mode import ModeController
from monitoring.server import ControlPlane
from monitoring.store import McpAuditStore

HUMAN_SECRET = "human-only-secret-token"
GUARDRAIL_HASH = "GHASH"
RULEBOOK_HASH = "RHASH"


class RecordingControl:
    """A narrow ControlTarget test double (records restrictive calls)."""

    def __init__(self) -> None:
        self.halts: list[tuple[str, str]] = []
        self.flattens: list[tuple[str, str]] = []
        self.resumes: list[str] = []

    def apply_halt(self, scope: str, reason: str) -> None:
        self.halts.append((scope, reason))

    def flatten(self, scope: str, reason: str) -> None:
        self.flattens.append((scope, reason))

    def resume(self, human_token: str) -> None:
        self.resumes.append(human_token)


class RecordingStager:
    def __init__(self) -> None:
        self.staged: list[tuple[dict, str]] = []

    def stage_config(self, patch: dict, rationale: str) -> str:
        self.staged.append((patch, rationale))
        return f"stage-{len(self.staged)}"


def mk_logger():
    return JsonlEventLogger(io.StringIO(), "monitoring", "mcp-test")


_DEFAULT_BOUNDS = {
    "signals.conviction_discard": (0.45, 0.95),
    "governor.marginal_alpha_window": (10.0, 500.0),
}


def mk_plane(*, providers=None, tunable_bounds=None, validation_ok=True,
             control=None, stager=None, initial_mode="paper",
             guardrail_hash=GUARDRAIL_HASH, rulebook_hash=RULEBOOK_HASH,
             heartbeat_monitor=None, heartbeat_getter=None, now_fn=None):
    """Assemble a ControlPlane over test doubles. Returns (plane, control,
    stager, mode_controller)."""
    control = control or RecordingControl()
    stager = stager or RecordingStager()
    logger = mk_logger()
    mode = ModeController(
        initial_mode=initial_mode, guardrail_hash=guardrail_hash,
        rulebook_hash=rulebook_hash, validation_record_ok=lambda: validation_ok,
        logger=logger)
    plane = ControlPlane(
        control=control, auth=HumanTokenVerifier.from_secret(HUMAN_SECRET),
        mode_controller=mode, stager=stager,
        providers=providers or {},
        guardrail_view={"var_cap_pct": 3.0, "equity_floor_usd": 9000.0},
        guardrail_hash=guardrail_hash, rulebook_hash=rulebook_hash,
        tunable_bounds=tunable_bounds or dict(_DEFAULT_BOUNDS),
        log_tail_max=100, logger=logger, session_id="mcp-test",
        audit=McpAuditStore(), heartbeat_monitor=heartbeat_monitor,
        heartbeat_getter=heartbeat_getter, now_fn=now_fn)
    return plane, control, stager, mode
