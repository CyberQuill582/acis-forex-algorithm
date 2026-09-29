"""The cTrader session's small value types (ACIS-13 §8.1, §2.2, §5.3, §6.6), split out of session.py
(A12). Invariants: credentials come from the environment and never print (C-VEN-8); DETACHED is
terminal until a human re-grants (§7.2); backoff is full-jitter on an injected RNG (§6.6).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field as dc_field
from enum import Enum

from core.data.errors import DataQualityError


class LinkState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    APP_AUTH = "APP_AUTH"
    ACCOUNT_AUTH = "ACCOUNT_AUTH"
    SYNCING = "SYNCING"
    READY = "READY"
    REAUTH = "REAUTH"
    DETACHED = "DETACHED"          # terminal: a human re-grant and re-attach (§7.2)


class AuthRefused(Exception):
    """Attach refused at authorisation; `verdict` is the §9 event name."""

    def __init__(self, verdict: str, detail: str = "") -> None:
        super().__init__(f"{verdict}: {detail}" if detail else verdict)
        self.verdict = verdict


@dataclass(frozen=True)
class Credentials:
    client_id: str = dc_field(repr=False)
    client_secret: str = dc_field(repr=False)

    @classmethod
    def from_env(cls) -> "Credentials":
        cid, secret = os.environ.get("ACIS_CTRADER_CLIENT_ID"), os.environ.get("ACIS_CTRADER_CLIENT_SECRET")
        if not cid or not secret:
            raise DataQualityError("credentials", None, "ACIS_CTRADER_CLIENT_ID/SECRET not set")
        return cls(cid, secret)


@dataclass(frozen=True)
class Grant:
    """What the venue's grant says about the bound binding (for the AttachReport, §5.3)."""
    is_live: bool
    trader_login: int | None
    broker: str | None


def backoff_delay(attempt: int, rng, *, base_s: float, factor: float, cap_s: float) -> float:
    """Exponential backoff with full jitter (§6.6): uniform(0, min(cap, base·factor^attempt))."""
    return rng.uniform(0.0, min(cap_s, base_s * factor ** attempt))
