"""The cTrader face's persisted state (ACIS-13 §10): fragment ⇄ venue order, and the per-binding deal
cursor and first-attach record. SQLite in WAL + synchronous=FULL (power-loss durable).

Invariants:
  * A fragment is recorded SENT BEFORE its frame leaves, so after any crash the face knows it may
    have reached the venue and searches before it resends (C-VEN-1). A fragment is recorded once.
  * Everything is keyed by `account_key`, so nothing leaks from a dead account into its successor
    (§5.4, §7.2, C-VEN-5).
  * The deal cursor only moves forward: ingestion is idempotent and a restart never re-reads the
    past as new.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.data.sqlite_wal import open_store


class VenueStore:
    _DDL = ("CREATE TABLE IF NOT EXISTS venue_order_map (fragment_id TEXT PRIMARY KEY, "
            "account_key TEXT NOT NULL, order_id TEXT NOT NULL, venue_order_id INTEGER, "
            "position_id INTEGER, state TEXT NOT NULL CHECK (state IN ('SENT','TERMINAL','NOT_SENT')), "
            "sent_ts TEXT NOT NULL, terminal_ts TEXT);"
            "CREATE TABLE IF NOT EXISTS venue_binding (account_key TEXT PRIMARY KEY, "
            "first_attached_ts TEXT NOT NULL, initial_balance TEXT NOT NULL, "
            "deal_cursor_ms INTEGER NOT NULL, last_report TEXT NOT NULL);")

    def __init__(self, db_path: str | Path, account_key: str) -> None:
        self.account_key = account_key
        self._db = open_store(db_path)
        self._db.executescript(self._DDL)
        self._db.commit()

    # -- fragments ------------------------------------------------------------------------ #

    def sent(self, fragment_id: str, order_id: str, at: datetime, position_id: int | None = None) -> None:
        """Recorded once; a fragment already known NOT_SENT may be sent again (it never arrived)."""
        prior = self.lookup(fragment_id)
        if prior is not None and prior[0] != "NOT_SENT":
            raise ValueError(f"{fragment_id} is already {prior[0]}: search, never resend")
        self._db.execute("INSERT OR REPLACE INTO venue_order_map (fragment_id, account_key, order_id, "
                         "position_id, state, sent_ts) VALUES (?,?,?,?,'SENT',?)",
                         (fragment_id, self.account_key, order_id, position_id, at.isoformat()))
        self._db.commit()

    def terminal(self, fragment_id: str, venue_order_id: int | None, position_id: int | None,
                 at: datetime) -> None:
        self._db.execute("UPDATE venue_order_map SET state='TERMINAL', venue_order_id=?, "
                         "position_id=?, terminal_ts=? WHERE fragment_id=?",
                         (venue_order_id, position_id, at.isoformat(), fragment_id))
        self._db.commit()

    def not_sent(self, fragment_id: str, at: datetime) -> None:
        self._db.execute("UPDATE venue_order_map SET state='NOT_SENT', terminal_ts=? "
                         "WHERE fragment_id=?", (at.isoformat(), fragment_id))
        self._db.commit()

    def lookup(self, fragment_id: str) -> tuple[str, int | None, datetime] | None:
        row = self._db.execute("SELECT state, venue_order_id, sent_ts FROM venue_order_map "
                               "WHERE fragment_id=? AND account_key=?",
                               (fragment_id, self.account_key)).fetchone()
        return None if row is None else (row[0], row[1], datetime.fromisoformat(row[2]))

    def parts(self, fragment_id: str) -> list[tuple[str, str, int, int | None, datetime]]:
        """A close's per-position rows `<fragment>#<positionId>`: (id, state, position, order, sent)."""
        rows = self._db.execute("SELECT fragment_id, state, position_id, venue_order_id, sent_ts FROM "
                                "venue_order_map WHERE account_key=? AND fragment_id LIKE ?",
                                (self.account_key, fragment_id + "#%")).fetchall()
        return [(f, st, int(pid), vo, datetime.fromisoformat(t)) for f, st, pid, vo, t in rows]

    def ours(self) -> tuple[set[int], set[int]]:
        """(venue order ids, venue position ids) of every order ACIS sent on this binding: a deal on
        one of these orders is ACIS's own; a deal on one of these positions is on an ACIS position."""
        rows = self._db.execute("SELECT venue_order_id, position_id FROM venue_order_map WHERE "
                                "account_key=?", (self.account_key,)).fetchall()
        return ({int(o) for o, _ in rows if o is not None}, {int(p) for _, p in rows if p is not None})

    def in_flight(self) -> list[tuple[str, str, datetime]]:
        """Fragments SENT with no terminal outcome: resolved by search at every SYNCING (§7.8)."""
        rows = self._db.execute("SELECT fragment_id, order_id, sent_ts FROM venue_order_map "
                                "WHERE account_key=? AND state='SENT'", (self.account_key,)).fetchall()
        return [(f, o, datetime.fromisoformat(t)) for f, o, t in rows]

    # -- the binding ---------------------------------------------------------------------- #

    def binding(self) -> tuple[datetime, str, int] | None:
        row = self._db.execute("SELECT first_attached_ts, initial_balance, deal_cursor_ms FROM "
                               "venue_binding WHERE account_key=?", (self.account_key,)).fetchone()
        return None if row is None else (datetime.fromisoformat(row[0]), row[1], int(row[2]))

    def bind(self, at: datetime, initial_balance: str, cursor_ms: int, report_json: str) -> None:
        self._db.execute("INSERT INTO venue_binding VALUES (?,?,?,?,?)",
                         (self.account_key, at.isoformat(), initial_balance, cursor_ms, report_json))
        self._db.commit()

    def advance(self, cursor_ms: int) -> None:
        self._db.execute("UPDATE venue_binding SET deal_cursor_ms=MAX(deal_cursor_ms, ?) "
                         "WHERE account_key=?", (cursor_ms, self.account_key))
        self._db.commit()

    def save_report(self, report_json: str) -> None:
        self._db.execute("UPDATE venue_binding SET last_report=? WHERE account_key=?",
                         (report_json, self.account_key))
        self._db.commit()

    def close(self) -> None:
        self._db.close()
