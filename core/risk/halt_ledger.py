"""The persisted HALT ledger on the upward edge (ACIS-07 §7 "active halts", §10).

A restart is never a relaxation (GAP-0050), and the ledger never gates a guard. Invariants:
  * `PersistentHaltSink` wraps the single upward edge. Every halt, session halt and
    flatten is FORWARDED FIRST — the Governor and execution act before any disk write —
    then recorded in `halt_event` (audit F0/X2). The MCP control target must route its
    halts and flattens through it too.
  * A failed write is retried, raised as a `HALT_LEDGER_WRITE_FAILED` alarm, and kept
    pending in memory; the halt itself is already in force. Every `flush()` (each check)
    writes the pending rows again until they land.
  * Boot re-applies every uncleared row through the same edge, same scope and reason,
    before the first evaluate (`Guardrails.restore_state`).
  * Re-applying writes nothing new: an open row with the same kind, scope and reason
    (and, for a session halt, instant) is not written twice. Every row id is unique, so a
    halt re-issued at the instant of a CLEARED row is still written (audit F9).
  * The sink has no clearing verb. Only the human resume clears rows, so an agent that
    reaches the sink can halt, never unhalt, and never make a restart forget a halt.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import Callable

from core.risk.sink import HaltSink
from core.risk.store import RiskStore

WRITE_ATTEMPTS = 3


class PersistentHaltSink(HaltSink):
    def __init__(self, inner: HaltSink, store: RiskStore,
                 now_fn: Callable[[], datetime], logger) -> None:
        self._inner = inner
        self._store = store
        self._now = now_fn
        self._log = logger
        self._pending: list[tuple[str, str, str, datetime]] = []

    def _record(self, kind: str, scope: str, reason: str, at: datetime) -> None:
        self._pending.append((kind, scope, reason, at))
        self.flush()

    def flush(self) -> None:
        while self._pending:
            kind, scope, reason, at = self._pending[0]
            error = None
            for _ in range(WRITE_ATTEMPTS):
                try:
                    self._write(kind, scope, reason, at)
                    break
                except (sqlite3.Error, OSError) as exc:      # bookkeeping, never the guard
                    error = exc
            else:
                self._log.event("HALT_LEDGER_WRITE_FAILED", kind=kind, scope=scope,
                                reason=reason, error=str(error), pending=len(self._pending))
                return
            self._pending.pop(0)

    def _write(self, kind: str, scope: str, reason: str, at: datetime) -> None:
        for row in self._store.open_halts():
            same = (row.kind, row.scope, row.reason) == (kind, scope, reason)
            if same and (kind != "session" or row.at == at):
                return
        self._store.record_halt(f"{kind}|{at.isoformat()}|{scope}|{reason}|{uuid.uuid4().hex}",
                                at.isoformat(), scope, reason)

    def apply_halt(self, scope: str, reason: str) -> None:
        self._inner.apply_halt(scope, reason)
        self._record("halt", scope, reason, self._now())

    def apply_session_halt(self, now: datetime, reason: str) -> None:
        self._inner.apply_session_halt(now, reason)
        self._record("session", "session", reason, now)

    def apply_risk_state(self, *, taper_factor: float | None = None,
                         alpha_decay: bool | None = None) -> None:
        # persisted with the restrictive state after every evaluate (GAP-P12D-55)
        self._inner.apply_risk_state(taper_factor=taper_factor, alpha_decay=alpha_decay)

    def flatten(self, scope: str, reason: str) -> None:
        self._inner.flatten(scope, reason)
        self._record("flatten", scope, reason, self._now())
