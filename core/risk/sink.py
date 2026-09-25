"""The upward edge as a narrow injected sink (ACIS-07 §3, GAP-0014).

Risk does not import the Governor's internals; it holds a `HaltSink`. The
sink's SCHEMA cannot express a size increase — every method is
risk-restrictive: halt, session-halt, taper/decay-cut, flatten. This is the
single upward channel in the whole system (master §2/§8), realised at wiring
time by an adapter over the Governor's phase-6 surface plus the flatten path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class HaltSink(ABC):
    """Restrictive-only. There is deliberately no `resume`, no `set_size`, no
    `raise_limit` — a resume is a human action on the Governor/MCP layer, never
    something Risk can reach (master §12 asymmetry)."""

    @abstractmethod
    def apply_halt(self, scope: str, reason: str) -> None:
        """Halt a scope ("all" | instrument) until human resume."""

    @abstractmethod
    def apply_session_halt(self, now: datetime, reason: str) -> None:
        """Session-scoped halt that auto-clears at the next boundary (master §8)."""

    @abstractmethod
    def apply_risk_state(self, *, taper_factor: float | None = None,
                         alpha_decay: bool | None = None) -> None:
        """GAP-0050: None = unchanged. taper ∈ [0,1] (cut only); alpha_decay
        True arms the 25% throttle, False is the explicit recovery clear."""

    @abstractmethod
    def flatten(self, scope: str, reason: str) -> None:
        """Close positions on a scope ("all" | instrument) and halt it."""

    def flush(self) -> None:
        """Record any halt the edge could not persist yet (audit F0/X2). A no-op for an
        edge without a ledger; never a way to lift, shorten or skip a halt."""
