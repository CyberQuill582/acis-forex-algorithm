"""Mode controller with the dual-hash gates (ACIS-08 §4/§7, master §12).

`acis_set_mode(practice|live)` requires a human token (checked in tools.py) AND
acknowledgment of BOTH:
  1. the guardrail hash (the exact hard limits in force), and
  2. the active-account rulebook hash (§9.5 — the platform's own rules, news
     restrictions included).
Live additionally requires that §14 minimums were met (a validation record).
Practice (master v2.23, ACIS-13 §7.1 A2) instead requires that the attached
venue is practice-eligible: the venue reports a demo account AND its rulebook
declares `account_class: practice`, so practice orders never reach money.

This controller does NOT check the human token — that is the tools layer's
auth gate (§7 step 4). It owns only the hash/validation/eligibility asymmetry
and the mode state. It never widens risk on its own: every order-sending mode
is human-gated end to end.
"""

from __future__ import annotations

from typing import Callable, Literal

Mode = Literal["backtest", "paper", "practice", "live"]
MODES: tuple[Mode, ...] = ("backtest", "paper", "practice", "live")


class ModeChangeRejected(Exception):
    """A mode change failed a precondition (hash mismatch, unmet §14, or a venue
    that is not practice-eligible)."""


def _no_practice_venue() -> bool:
    return False       # nothing attached: practice is refused


class ModeController:
    def __init__(self, *, initial_mode: Mode, guardrail_hash: str,
                 rulebook_hash: str, validation_record_ok: Callable[[], bool],
                 logger, practice_eligible: Callable[[], bool] = _no_practice_venue) -> None:
        # Safe by construction (GAP-P10I-03): the REFERENCE hashes must be
        # non-empty strings, so a `None`/absent acknowledgment arg can never
        # coincide with the reference (`None != <hash>`). Without this a
        # controller wired with `None` references would clear the live gate on a
        # `None` ack (`None == None`) — zero acknowledgment.
        if not isinstance(guardrail_hash, str) or not guardrail_hash.strip():
            raise ValueError("ModeController requires a non-empty guardrail_hash")
        if not isinstance(rulebook_hash, str) or not rulebook_hash.strip():
            raise ValueError("ModeController requires a non-empty rulebook_hash")
        self._mode: Mode = initial_mode
        self._guardrail_hash = guardrail_hash
        self._rulebook_hash = rulebook_hash
        self._validation_ok = validation_record_ok
        self._practice_eligible = practice_eligible
        self._log = logger

    @property
    def mode(self) -> Mode:
        return self._mode

    def _reject(self, mode: Mode, reason: str, message: str) -> None:
        self._log.event("MODE_CHANGE_REJECT", to=mode, reason=reason)
        raise ModeChangeRejected(message)

    def set_mode(self, mode: Mode, *, guardrail_hash: str | None = None,
                 rulebook_hash: str | None = None) -> None:
        if mode in ("practice", "live"):
            # Each precondition rejected INDEPENDENTLY (C-MCP-8), most-restrictive
            # framing: any missing/mismatched attestation blocks the mode.
            if guardrail_hash != self._guardrail_hash:
                self._reject(mode, "guardrail_hash", "guardrail_hash mismatch/absent")
            if rulebook_hash != self._rulebook_hash:
                self._reject(mode, "rulebook_hash", "rulebook_hash mismatch/absent")
        if mode == "practice" and not self._practice_eligible():
            self._reject(mode, "practice_venue",
                         "the attached venue is not a demo account with a practice rulebook")
        if mode == "live" and not self._validation_ok():
            self._reject(mode, "validation_record",
                         "§14 minimums not met (no validation record)")
        prev = self._mode
        self._mode = mode
        self._log.event("MODE_CHANGE", **{"from": prev, "to": mode})
