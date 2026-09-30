"""The upward edge and the MCP control target, wired (ACIS-07 §3, ACIS-08 §4; GAP-0014).

Invariants:
  * `RuntimeHaltSink` is the edge Risk holds, wrapped by `PersistentHaltSink`, which forwards
    first and records second. Every verb restricts: halts go to the Governor, and a flatten
    freezes new opens at EVERY orchestrator (paper and venue: a flatten is never mode-local)
    and queues a reduce-only close of each held position in its scope. No verb lifts anything.
  * `RuntimeControl` is ACIS-08's `ControlTarget`. Halt and flatten go through the persisted
    edge, so an agent's halt survives a restart exactly as Risk's does. `resume` is the ONE
    human path — the Governor's, which clears the halt ledger first or lifts nothing — and only
    then is the execution freeze lifted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Sequence

from core.execution.orchestrator import ExecutionOrchestrator
from core.governor.capital_governor import CapitalGovernor
from core.risk.sink import HaltSink


class RuntimeHaltSink(HaltSink):
    def __init__(self, governor: CapitalGovernor, orchestrators: Sequence[ExecutionOrchestrator],
                 request_flatten: Callable[[str, str], None]) -> None:
        self._gov = governor
        self._orchs = tuple(orchestrators)
        self._flatten = request_flatten

    def apply_halt(self, scope: str, reason: str) -> None:
        self._gov.apply_halt(scope, reason)

    def apply_session_halt(self, now: datetime, reason: str) -> None:
        self._gov.apply_session_halt(now, reason)

    def apply_risk_state(self, *, taper_factor: float | None = None,
                         alpha_decay: bool | None = None) -> None:
        self._gov.apply_risk_state(taper_factor=taper_factor, alpha_decay=alpha_decay)

    def flatten(self, scope: str, reason: str) -> None:
        for orch in self._orchs:
            orch.set_freeze(True, reason)             # opens refused; closes still go through
        self._flatten(scope, reason)


class RuntimeControl:
    """ACIS-08's ControlTarget over the persisted edge and the Governor's one resume path."""

    def __init__(self, edge: HaltSink, governor: CapitalGovernor,
                 orchestrators: Sequence[ExecutionOrchestrator]) -> None:
        self._edge = edge
        self._gov = governor
        self._orchs = tuple(orchestrators)

    def apply_halt(self, scope: str, reason: str) -> None:
        self._edge.apply_halt(scope, reason)

    def flatten(self, scope: str, reason: str) -> None:
        self._edge.flatten(scope, reason)

    def resume(self, human_token: str) -> None:
        self._gov.resume(human_token)                 # raises before anything lifts (F8)
        for orch in self._orchs:
            orch.set_freeze(False, "human_resume")
