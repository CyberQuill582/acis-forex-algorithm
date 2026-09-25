"""The persisted fill log (ACIS-06 §10). Moved out of core/execution/venue.py, which
re-exports it (legibility budget, GAP-P12M-01).

Invariants:
  * `fill_id` is the primary key, so ingestion is idempotent — a reconnect or restart
    can never double-count a fill.
  * Every venue hit leaves a row under that venue's name; boundary refusals that never
    reached a venue are written under venue "none". So the rows under a venue's name
    are a restart-proof lower bound on the requests sent to it (`request_times`,
    GAP-P12D-57) — a restart cannot hand the engine a fresh request budget.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from core.data.sqlite_wal import open_store

if TYPE_CHECKING:
    from core.execution.venue import FillReport


class FillReportStore:
    _DDL = """
    CREATE TABLE IF NOT EXISTS fill_report (
        fill_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
        fragment_id TEXT NOT NULL, ts TEXT NOT NULL,
        instrument TEXT NOT NULL, direction INTEGER NOT NULL,
        requested_px REAL NOT NULL, fill_px REAL NOT NULL,
        filled_units TEXT NOT NULL, slippage_bps REAL NOT NULL,
        venue TEXT NOT NULL, status TEXT NOT NULL,
        remaining_units TEXT NOT NULL, session_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_fill_order ON fill_report (order_id);"""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = open_store(db_path)     # WAL + synchronous=FULL: power-loss durable (X4)
        self._conn.executescript(self._DDL)
        self._conn.commit()

    def write(self, r: "FillReport") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO fill_report VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r.fill_id, r.order_id, r.fragment_id, r.fill_time.isoformat(),
             r.instrument, r.direction, r.requested_price, r.fill_price,
             str(r.filled_units), r.slippage_bps, r.venue, r.status.value,
             str(r.remaining_units), r.session_id))
        self._conn.commit()

    def request_times(self, venue: str, since: datetime) -> list[datetime]:
        """When each logged request to `venue` at or after `since` was made."""
        rows = self._conn.execute("SELECT ts FROM fill_report WHERE venue = ?",
                                  (venue,)).fetchall()
        stamps = (datetime.fromisoformat(ts) for (ts,) in rows)
        return sorted(t for t in stamps if t >= since)

    def row_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM fill_report").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
