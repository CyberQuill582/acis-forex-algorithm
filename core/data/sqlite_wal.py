"""Open the engine's small SQLite stores in WAL journal mode (GAP-P12D-15).

The fast loop reads the parameter library and the provenance store on every tick. Under
SQLite's default rollback journal each statement takes and releases a file lock; on the
Windows dev laptop that measured ~150-220 us per keyed SELECT. In WAL mode the same read
measured ~5-20 us, because readers use the shared-memory index instead of file locks.

Invariant: WAL changes only locking and journaling, not what a read returns. Every read
still goes to the database, so a promotion or a freeze committed through ANY connection is
visible on the very next call — no in-memory copy of store state can go stale. Commits
stay durable (the default synchronous=FULL is unchanged). WAL needs the -wal/-shm files on
a local filesystem shared by every process that opens the store (not a network share).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_store(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.execute("PRAGMA journal_mode=WAL")
    return db
