"""The persisted HALT ledger on the upward edge (ACIS-07 §7 "active halts", §10).

A restart is never a relaxation (GAP-0050). Invariants:
  * `PersistentHaltSink` wraps the single upward edge. Every halt, session halt and
    flatten is written to `halt_event` BEFORE it is forwarded, so a crash between the
    two can only leave a recorded halt not yet applied (restored at boot), never the
    reverse. The MCP control target must route its halts and flattens through it too.
  * Boot re-applies every uncleared row through the same edge, same scope and reason,
    before the first evaluate (`Guardrails.restore_state`). A session halt is re-applied
    with its ORIGINAL instant, so it lifts at the boundary it would have lifted at.
  * Re-applying writes nothing new: an open row with the same kind, scope and reason
    (and, for a session halt, instant) is not written twice.
  * The sink has no clearing verb. Only a human resume clears rows
    (`RiskMonitor.on_human_resume`), so an agent that reaches the sink can halt, never
    unhalt, and never make a restart forget a halt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from core.risk.sink import HaltSink
from core.risk.store import RiskStore


class PersistentHaltSink(HaltSink):
    def __init__(self, inner: HaltSink, store: RiskStore,
                 now_fn: Callable[[], datetime]) -> None:
        self._inner = inner
        self._store = store
        self._now = now_fn

    def _record(self, kind: str, scope: str, reason: str, at: datetime) -> None:
        for k, s, r, t in self._store.open_halts():
            if (k, s, r) == (kind, scope, reason) and (kind != "session" or t == at):
                return
        self._store.record_halt(f"{kind}|{at.isoformat()}|{scope}|{reason}",
                                at.isoformat(), scope, reason)

    def apply_halt(self, scope: str, reason: str) -> None:
        self._record("halt", scope, reason, self._now())
        self._inner.apply_halt(scope, reason)

    def apply_session_halt(self, now: datetime, reason: str) -> None:
        self._record("session", "session", reason, now)
        self._inner.apply_session_halt(now, reason)

    def apply_risk_state(self, *, taper_factor: float | None = None,
                         alpha_decay: bool | None = None) -> None:
        # persisted with the restrictive state after every evaluate (GAP-P12D-55)
        self._inner.apply_risk_state(taper_factor=taper_factor, alpha_decay=alpha_decay)

    def flatten(self, scope: str, reason: str) -> None:
        self._record("flatten", scope, reason, self._now())
        self._inner.flatten(scope, reason)
