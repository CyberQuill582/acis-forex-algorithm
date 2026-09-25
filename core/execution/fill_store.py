"""The persisted fill log (ACIS-06 §10). Moved out of core/execution/venue.py, which
re-exports it (legibility budget, GAP-P12M-01).

Invariants:
  * `fill_id` is the primary key, so ingestion is idempotent — a reconnect or restart
    can never double-count a fill.
  * Every venue hit leaves a row under that venue's name; boundary refusals that never
    reached a venue are written under venue "none". So the rows under a venue's name
    are a restart-proof lower bound on the requests sent to it (`request_times`,
    GAP-P12D-57) — a restart cannot hand the engine a fresh request budget.
  * Every close sent to a venue leaves a `close_attempt` row (filled or not), kept for
    24 h, so the close pace (close_pacing.py, audit X6/F5) survives a restart too. The
    table is additive: `fill_report` is unchanged.
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
    CREATE INDEX IF NOT EXISTS ix_fill_order ON fill_report (order_id);
    CREATE TABLE IF NOT EXISTS close_attempt (
        venue TEXT NOT NULL, instrument TEXT NOT NULL, at TEXT NOT NULL, ok INTEGER NOT NULL
    );"""

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

    def record_close_attempt(self, venue: str, instrument: str, at: datetime, ok: bool,
                             keep_since: datetime) -> None:
        self._conn.execute("DELETE FROM close_attempt WHERE at < ?", (keep_since.isoformat(),))
        self._conn.execute("INSERT INTO close_attempt VALUES (?,?,?,?)",
                           (venue, instrument, at.isoformat(), int(ok)))
        self._conn.commit()

    def close_attempts(self, since: datetime) -> list[tuple[str, str, datetime, bool]]:
        rows = self._conn.execute("SELECT venue, instrument, at, ok FROM close_attempt "
                                  "WHERE at >= ? ORDER BY at", (since.isoformat(),)).fetchall()
        return [(v, i, datetime.fromisoformat(at), bool(ok)) for v, i, at, ok in rows]

    def row_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM fill_report").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
