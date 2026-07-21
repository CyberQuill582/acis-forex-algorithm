"""MCP audit + idempotency store (ACIS-08 §10).

`request_id` is the PRIMARY KEY: a duplicated tool call cannot double-execute —
the second attempt collides and the first result is returned (C-MCP-3). The
control plane's audit trail is part of the risk audit spine: every halt /
flatten / resume / mode-change / rejection is attributable to a caller and (for
resume/live) a human.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AuditRecord:
    request_id: str
    tool: str
    caller: str
    is_human: bool
    args: dict
    result: str            # "ok" | "ok:<detail>" | "rejected:<reason>"
    session_id: str


class McpAuditStore:
    def __init__(self, db_path: str = ":memory:") -> None:
        self._db = sqlite3.connect(db_path)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS mcp_audit (
                   request_id TEXT PRIMARY KEY,
                   ts TEXT NOT NULL,
                   tool TEXT NOT NULL,
                   caller TEXT NOT NULL,
                   is_human INTEGER NOT NULL,
                   args TEXT NOT NULL,
                   result TEXT NOT NULL,
                   session_id TEXT NOT NULL
               )"""
        )
        self._db.commit()

    def find(self, request_id: str) -> AuditRecord | None:
        row = self._db.execute(
            "SELECT request_id, tool, caller, is_human, args, result, session_id "
            "FROM mcp_audit WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        return AuditRecord(
            request_id=row[0], tool=row[1], caller=row[2], is_human=bool(row[3]),
            args=json.loads(row[4]), result=row[5], session_id=row[6])

    def record(self, rec: AuditRecord) -> None:
        """Insert once. A colliding request_id raises IntegrityError — callers
        that have already checked `find` and want the collision to be fatal use
        this; `record_once` handles the race gracefully instead."""
        self._db.execute(
            "INSERT INTO mcp_audit "
            "(request_id, ts, tool, caller, is_human, args, result, session_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rec.request_id, datetime.now(timezone.utc).isoformat(), rec.tool,
             rec.caller, int(rec.is_human), json.dumps(rec.args, sort_keys=True),
             rec.result, rec.session_id))
        self._db.commit()

    def record_once(self, rec: AuditRecord) -> bool:
        """Insert; return True if this call wrote the row, False if a row with
        the same request_id already existed (a concurrent duplicate lost the
        race). The PK makes double-execution impossible even without a lock
        (GAP-P10E-01) — the caller returns the winner's stored result."""
        try:
            self.record(rec)
            return True
        except sqlite3.IntegrityError:
            return False

    def count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM mcp_audit").fetchone()[0]

    def close(self) -> None:
        self._db.close()
