"""Practice mode (master v2.23 §7.5/§12, ACIS-08 v1.4, ACIS-13 §7.1 A2, GAP-P12D-69): the
one mode that may order before §14, and only where nothing of value is at stake."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.rulebook import AccountRulebook
from config.schemas import SystemConfig
from monitoring.mode import ModeChangeRejected, ModeController
from tests.mcp_fixtures import (GUARDRAIL_HASH, HUMAN_SECRET, RULEBOOK_HASH, mk_logger,
                                mk_plane)


def _ctl(*, eligible: bool, validation_ok: bool = False) -> ModeController:
    return ModeController(initial_mode="paper", guardrail_hash=GUARDRAIL_HASH,
                          rulebook_hash=RULEBOOK_HASH, validation_record_ok=lambda: validation_ok,
                          logger=mk_logger(), practice_eligible=lambda: eligible)


def test_practice_needs_both_hashes_and_a_practice_venue_but_no_validation_record() -> None:
    ctl = _ctl(eligible=True, validation_ok=False)
    ctl.set_mode("practice", guardrail_hash=GUARDRAIL_HASH, rulebook_hash=RULEBOOK_HASH)
    assert ctl.mode == "practice"


@pytest.mark.parametrize("hashes", [
    {"rulebook_hash": RULEBOOK_HASH},                                 # no guardrail ack
    {"guardrail_hash": GUARDRAIL_HASH},                               # no rulebook ack
    {"guardrail_hash": "TAMPERED", "rulebook_hash": RULEBOOK_HASH},
])
def test_practice_refuses_a_missing_or_wrong_attestation(hashes) -> None:
    ctl = _ctl(eligible=True)
    with pytest.raises(ModeChangeRejected):
        ctl.set_mode("practice", **hashes)
    assert ctl.mode == "paper"


def test_practice_refuses_a_venue_that_is_not_a_practice_account() -> None:
    ctl = _ctl(eligible=False)
    with pytest.raises(ModeChangeRejected, match="practice rulebook"):
        ctl.set_mode("practice", guardrail_hash=GUARDRAIL_HASH, rulebook_hash=RULEBOOK_HASH)
    assert ctl.mode == "paper"


def test_nothing_attached_means_no_practice() -> None:
    ctl = ModeController(initial_mode="paper", guardrail_hash=GUARDRAIL_HASH,
                         rulebook_hash=RULEBOOK_HASH, validation_record_ok=lambda: True,
                         logger=mk_logger())
    with pytest.raises(ModeChangeRejected):
        ctl.set_mode("practice", guardrail_hash=GUARDRAIL_HASH, rulebook_hash=RULEBOOK_HASH)
    assert ctl.mode == "paper"


def test_a_practice_venue_does_not_open_the_live_gate() -> None:
    ctl = _ctl(eligible=True, validation_ok=False)
    with pytest.raises(ModeChangeRejected, match="§14"):
        ctl.set_mode("live", guardrail_hash=GUARDRAIL_HASH, rulebook_hash=RULEBOOK_HASH)
    assert ctl.mode == "paper"


def _call(plane, token, **args):
    return plane.call_tool("acis_set_mode", {"args": args, "human_token": token,
                                             "request_id": "r-practice"})


def test_the_tool_refuses_practice_without_the_human_token() -> None:
    plane, _, _, mode = mk_plane(practice_ok=True)
    out = _call(plane, "agent-guess", mode="practice", guardrail_hash=GUARDRAIL_HASH,
                rulebook_hash=RULEBOOK_HASH)
    assert out["status"] == "rejected" and mode.mode == "paper"


def test_the_tool_sets_practice_for_a_human_on_a_practice_venue() -> None:
    plane, _, _, mode = mk_plane(practice_ok=True)
    out = _call(plane, HUMAN_SECRET, mode="practice", guardrail_hash=GUARDRAIL_HASH,
                rulebook_hash=RULEBOOK_HASH)
    assert out["status"] == "ok" and mode.mode == "practice"


def test_practice_is_never_a_boot_mode(acis_config) -> None:
    """Master §7.5: every attach starts in paper; only a human token reaches practice."""
    raw = acis_config.system.model_dump()
    with pytest.raises(ValidationError):
        SystemConfig.model_validate({**raw, "mode": "practice"})


def test_a_rulebook_may_declare_only_the_practice_class() -> None:
    base = {"platform": "ctrader", "news": {"restricted": False}, "min_hold_seconds": 0,
            "weekend_holding_allowed": True, "drawdown_rules": []}
    assert AccountRulebook.model_validate({**base, "account_class": "practice"}).account_class \
        == "practice"
    assert AccountRulebook.model_validate(base).account_class is None     # absent: not practice
    with pytest.raises(ValidationError):
        AccountRulebook.model_validate({**base, "account_class": "funded"})
