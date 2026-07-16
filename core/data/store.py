"""Persistence: SQLite (dev) mirror of the ACIS-01 §10 schema + async writer.

The writer is out-of-band and bounded: a slow DB NEVER blocks the fast loop —
queue overflow applies drop_oldest and logs DATA_BACKPRESSURE (SPEC §3).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from core.data.jsonl_logging import JsonlEventLogger
from core.data.normaliser import MarketState, thaw

_DDL = """
CREATE TABLE IF NOT EXISTS market_state (
    ts             TEXT    NOT NULL,
    ingest_ts      TEXT    NOT NULL,
    instrument     TEXT    NOT NULL,
    bid            REAL    NOT NULL,
    ask            REAL    NOT NULL,
    spread         REAL    NOT NULL,
    mid            REAL    NOT NULL,
    volume         REAL    NOT NULL,
    tick_velocity  REAL    NOT NULL,
    session        TEXT    NOT NULL,
    macro_imminent INTEGER NOT NULL,
    is_stale       INTEGER NOT NULL,
    book           TEXT,
    raw            TEXT,
    session_id     TEXT    NOT NULL,
    PRIMARY KEY (instrument, ts, ingest_ts)
);
CREATE INDEX IF NOT EXISTS ix_market_state ON market_state (instrument, ts DESC);
"""


class MarketStateStore:
    """Idempotent writes: the (instrument, ts, ingest_ts) PK makes restart/replay safe."""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(_DDL)
        self._conn.commit()

    def write(self, ms: MarketState, session_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO market_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ms.timestamp.isoformat(),
                ms.ingest_ts.isoformat(),
                ms.instrument,
                ms.bid,
                ms.ask,
                ms.spread,
                ms.mid,
                ms.volume,
                ms.tick_velocity,
                ms.session,
                int(ms.macro_events_imminent),
                int(ms.is_stale),
                json.dumps(thaw(ms.order_book_depth)),
                json.dumps(thaw(ms.raw)),
                session_id,
            ),
        )
        self._conn.commit()

    def row_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM market_state").fetchone()[0]

    def close(self) -> None:
        self._conn.close()


class AsyncBoundedWriter:
    """Drains a bounded queue into the store; overflow = drop_oldest + log."""

    _SENTINEL = object()

    def __init__(
        self,
        store: MarketStateStore,
        queue_max: int,
        session_id: str,
        logger: JsonlEventLogger,
    ) -> None:
        self._store = store
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_max)
        self._queue_max = queue_max
        self._session_id = session_id
        self._log = logger
        self.dropped = 0

    def enqueue(self, ms: MarketState) -> None:
        """Non-blocking by contract — called from the fast loop."""
        try:
            self._queue.put_nowait(ms)
        except asyncio.QueueFull:
            self._queue.get_nowait()  # drop_oldest
            self.dropped += 1
            self._log.event("DATA_BACKPRESSURE", dropped=1, queue_max=self._queue_max)
            self._queue.put_nowait(ms)

    async def stop(self) -> None:
        await self._queue.put(self._SENTINEL)

    async def run(self) -> None:
        while True:
            item = await self._queue.get()
            if item is self._SENTINEL:
                return
            self._store.write(item, self._session_id)
