"""The halt ledger, the anchors and the fill log survive a power loss (audit X4).

SQLite's own documentation: FULL "is not necessarily durable across a power loss in
rollback mode", while "FULL is atomic, consistent, isolated, and durable (ACID) in WAL
mode". Both stores that carry restart-critical state open in WAL with synchronous=FULL
through core/data/sqlite_wal.open_store."""

from __future__ import annotations

from core.execution.fill_store import FillReportStore
from core.risk.store import RiskStore

FULL = 2


def _mode(conn) -> tuple[str, int]:
    return (conn.execute("PRAGMA journal_mode").fetchone()[0],
            conn.execute("PRAGMA synchronous").fetchone()[0])


def test_the_risk_store_is_wal_with_full_sync(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    assert _mode(store._conn) == ("wal", FULL)
    store.close()


def test_the_fill_log_is_wal_with_full_sync(tmp_path) -> None:
    store = FillReportStore(tmp_path / "fills.db")
    assert _mode(store._conn) == ("wal", FULL)
    store.close()
