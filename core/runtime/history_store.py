"""The target path's local cache of the venue's hourly bars, and its promotion state (ACIS-04 v1.6 §4b
"cached and appended at every decision"; ACIS-03 v2.2 flatten-then-promote).

Invariants:
  * One row per (instrument, hour): a re-fetched hour REPLACES the stored one, so a fetch is
    idempotent and the cache never holds two closes for one hour.
  * Bars come back oldest first, as the engine's `Bar`. The cache is append-mostly and never
    trimmed (~6,240 rows a year per FX instrument).
  * `meta` holds the target path's ACTIVE family-version and any STAGED one, so a promotion staged
    before a restart is still owed after it (flatten-then-promote survives the process).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from core.data.bars import Bar
from core.data.sqlite_wal import open_store


class HistoryStore:
    _DDL = """CREATE TABLE IF NOT EXISTS h1_bar (
        instrument TEXT NOT NULL, ts_open INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
        low REAL NOT NULL, close REAL NOT NULL, PRIMARY KEY (instrument, ts_open));
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"""

    def __init__(self, path: str | Path) -> None:
        self._db = open_store(path)
        self._db.executescript(self._DDL)

    def add(self, instrument: str, bars: Iterable[Bar]) -> int:
        rows = [(instrument, int(b.ts_open.timestamp()), b.open, b.high, b.low, b.close) for b in bars]
        self._db.executemany("INSERT OR REPLACE INTO h1_bar VALUES (?,?,?,?,?,?)", rows)
        self._db.commit()
        return len(rows)

    def bars(self, instrument: str) -> list[Bar]:
        rows = self._db.execute("SELECT ts_open, open, high, low, close FROM h1_bar WHERE instrument = ? "
                                "ORDER BY ts_open", (instrument,)).fetchall()
        return [Bar(ts_open=datetime.fromtimestamp(t, timezone.utc), open=o, high=h, low=lo, close=c,
                    spread=0.0, duration_s=3600) for t, o, h, lo, c in rows]

    def last_end(self, instrument: str) -> datetime | None:
        (t,) = self._db.execute("SELECT MAX(ts_open) FROM h1_bar WHERE instrument = ?", (instrument,)).fetchone()
        return None if t is None else datetime.fromtimestamp(t, timezone.utc) + timedelta(hours=1)

    def get(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: str | None) -> None:
        if value is None:
            self._db.execute("DELETE FROM meta WHERE key = ?", (key,))
        else:
            self._db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self._db.commit()

    def close(self) -> None:
        self._db.close()
