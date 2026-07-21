"""Phase-10 dual-audit triage regressions (ACIS-08; GAP-P10I-* / GAP-P10E-*).

Each test pins a fix for a finding from the two adversarial audits so it cannot
silently regress.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from monitoring.heartbeat import HeartbeatMonitor
from monitoring.mode import ModeController
from tests.mcp_fixtures import (GUARDRAIL_HASH, HUMAN_SECRET, RULEBOOK_HASH,
                                RecordingControl, mk_logger, mk_plane)

T0 = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


# -- GAP-P10I-03: ModeController must reject empty/None reference hashes ------- #

def test_mode_controller_rejects_empty_reference_hashes() -> None:
    log = mk_logger()
    for bad in (None, "", "   "):
        with pytest.raises(ValueError):
            ModeController(initial_mode="paper", guardrail_hash=bad,
                           rulebook_hash=RULEBOOK_HASH,
                           validation_record_ok=lambda: True, logger=log)
        with pytest.raises(ValueError):
            ModeController(initial_mode="paper", guardrail_hash=GUARDRAIL_HASH,
                           rulebook_hash=bad, validation_record_ok=lambda: True,
                           logger=log)


def test_live_with_none_acks_cannot_pass_even_conceptually() -> None:
    """The None==None coincidence is structurally impossible: refs are non-empty,
    so an absent ack never matches."""
    plane, _, _, mode = mk_plane()
    out = plane.call_tool("acis_set_mode", {
        "request_id": "x", "human_token": HUMAN_SECRET,
        "args": {"mode": "live"}})           # no hashes supplied
    assert out["status"] == "rejected" and mode.mode == "paper"


# -- GAP-P10I-04 / GAP-P10E-01: idempotency is crash-safe (exactly-once) ------- #

class _RaisingControl(RecordingControl):
    def flatten(self, scope: str, reason: str) -> None:
        super().flatten(scope, reason)           # record the (partial) side effect
        raise RuntimeError("venue dropped mid-flatten")


def test_crash_mid_dispatch_is_recorded_and_never_re_executes() -> None:
    control = _RaisingControl()
    plane, _, _, _ = mk_plane(control=control)
    first = plane.call_tool("acis_flatten", {"request_id": "crash", "args": {}})
    assert first["status"] == "rejected" and first["result"].startswith("error:")
    # the replay returns the recorded error and does NOT call flatten again
    second = plane.call_tool("acis_flatten", {"request_id": "crash", "args": {}})
    assert second["status"] == "idempotent_replay"
    assert len(control.flattens) == 1            # exactly once despite the crash


# -- GAP-P10I-09: a pure rejection is not cached — a legit retry is allowed ---- #

def test_pure_rejection_is_not_cached_and_retry_is_allowed() -> None:
    plane, control, _, _ = mk_plane()
    rid = "retry-me"
    # first attempt: no token → rejected (no side effect, not persisted)
    bad = plane.call_tool("acis_resume", {"request_id": rid, "args": {}})
    assert bad["status"] == "rejected"
    assert plane.tools._audit.count() == 0       # nothing persisted
    # a genuine retry with the SAME id + a valid token now succeeds (not swallowed)
    ok = plane.call_tool("acis_resume",
                         {"request_id": rid, "human_token": HUMAN_SECRET, "args": {}})
    assert ok["status"] == "ok" and control.resumes == [HUMAN_SECRET]


# -- GAP-P10I-07: guardrails resource is observably read-only (deep copy) ------ #

def test_guardrails_resource_mutation_does_not_leak() -> None:
    plane, _, _, _ = mk_plane()
    v1 = plane.read_resource("acis://config/guardrails")
    v1["limits"]["var_cap_pct"] = 999.0          # caller mutates the returned view
    v2 = plane.read_resource("acis://config/guardrails")
    assert v2["limits"]["var_cap_pct"] == 3.0    # next reader is unaffected


# -- GAP-P10I-05 / GAP-P10E-05: C-MCP-6 heartbeat / missed-beat rule ----------- #

def _hb_plane(*, last_beat, open_positions, now):
    monitor = HeartbeatMonitor(heartbeat_fast_s=10.0, missed_beats_flatten=3)
    return mk_plane(heartbeat_monitor=monitor,
                    heartbeat_getter=lambda: (last_beat, open_positions),
                    now_fn=lambda: now)[0]


def test_fresh_heartbeat_is_healthy_no_flatten() -> None:
    plane = _hb_plane(last_beat=T0, open_positions=2, now=T0 + timedelta(seconds=5))
    hb = plane.read_resource("acis://status")["heartbeat"]
    assert hb["healthy"] and not hb["flatten_recommended"]


def test_three_missed_beats_with_positions_recommends_flatten() -> None:
    plane = _hb_plane(last_beat=T0, open_positions=2, now=T0 + timedelta(seconds=35))
    hb = plane.read_resource("acis://status")["heartbeat"]
    assert hb["missed_beats"] >= 3 and hb["flatten_recommended"]
    assert hb["reason"] == "missed_beats_with_positions"


def test_missed_beats_but_flat_is_alert_only() -> None:
    plane = _hb_plane(last_beat=T0, open_positions=0, now=T0 + timedelta(seconds=35))
    hb = plane.read_resource("acis://status")["heartbeat"]
    assert hb["missed_beats"] >= 3 and not hb["flatten_recommended"]
    assert hb["reason"] == "missed_beats_but_flat"


def test_never_synced_with_positions_recommends_flatten() -> None:
    plane = _hb_plane(last_beat=None, open_positions=1, now=T0)
    hb = plane.read_resource("acis://status")["heartbeat"]
    assert not hb["healthy"] and hb["flatten_recommended"]
