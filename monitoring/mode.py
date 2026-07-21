"""Mode controller with the dual-hash live gate (ACIS-08 §4/§7, master §12).

`acis_set_mode(live)` requires a human token (checked in tools.py) AND
acknowledgment of BOTH:
  1. the guardrail hash (the exact hard limits in force), and
  2. the active-account rulebook hash (§9.5 — the platform's own rules, news
     restrictions included),
AND that §14 minimums were met (a validation record). Nobody takes an account
live without attesting to both hashes (v2.7 carry-forward, C-MCP-8).

This controller does NOT check the human token — that is the tools layer's
auth gate (§7 step 4). It owns only the hash/validation asymmetry and the mode
state. It never widens risk on its own: going live is human-gated end to end.
"""

from __future__ import annotations

from typing import Callable, Literal

Mode = Literal["backtest", "paper", "live"]


class ModeChangeRejected(Exception):
    """A mode change failed a precondition (hash mismatch or unmet §14)."""


class ModeController:
    def __init__(self, *, initial_mode: Mode, guardrail_hash: str,
                 rulebook_hash: str, validation_record_ok: Callable[[], bool],
                 logger) -> None:
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
        self._log = logger

    @property
    def mode(self) -> Mode:
        return self._mode

    def set_mode(self, mode: Mode, *, guardrail_hash: str | None = None,
                 rulebook_hash: str | None = None) -> None:
        if mode == "live":
            # Each precondition rejected INDEPENDENTLY (C-MCP-8), most-restrictive
            # framing: any missing/mismatched attestation blocks live.
            if guardrail_hash != self._guardrail_hash:
                self._log.event("MODE_CHANGE_REJECT", to=mode, reason="guardrail_hash")
                raise ModeChangeRejected("guardrail_hash mismatch/absent")
            if rulebook_hash != self._rulebook_hash:
                self._log.event("MODE_CHANGE_REJECT", to=mode, reason="rulebook_hash")
                raise ModeChangeRejected("rulebook_hash mismatch/absent")
            if not self._validation_ok():
                self._log.event("MODE_CHANGE_REJECT", to=mode, reason="validation_record")
                raise ModeChangeRejected("§14 minimums not met (no validation record)")
        prev = self._mode
        self._mode = mode
        self._log.event("MODE_CHANGE", **{"from": prev, "to": mode})
