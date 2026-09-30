"""The venue request budget (ACIS-13 §6.5, C-VEN-4; GAP-P12D-57): every outbound request to one
bound account over any rolling 24 hours, persisted. Transport metering only: it holds no market,
account or position state (GAP-0013), just counts and timestamps.

Invariants:
  * The window is a rolling 24 h, so a cap of N holds in every calendar day in every time zone.
  * A restart is never a relaxation, and two processes on one account never see half each: the
    count is read from the persisted log at every check (GAP-P12D-132 TAI-11).
  * Heartbeats are events, not requests, and are never metered.
  * Exits are never starved. Below `budget − reserve` everything passes. In the reserve, opens,
    queries and subscriptions are refused and only closes, stop repair and the authorisation
    they need pass. At or over the budget closes and stop repair still pass (they are paced
    upstream, ACIS-06 v1.3 C-EXE-8); everything else, authorisation included, is refused — the
    budget is hard (C-VEN-4), so no reconnect or restart loop can spend past it (TAI-02, TAE-01).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from core.data.errors import DataQualityError
from core.data.sqlite_wal import open_store

WINDOW = timedelta(hours=24)
BUDGET_MAX = 1000                                  # half the FTMO / E8 cap of 2,000 (GAP-P12D-57)
CLASSES = ("open", "close", "protect", "query", "auth", "subscribe")
EXIT_CLASSES = frozenset({"close", "protect", "auth"})


class BudgetRefused(Exception):
    """A request the budget refuses; nothing was sent."""

    def __init__(self, req_class: str, used: int, cap: int, reason: str) -> None:
        super().__init__(f"{reason}: {req_class} with {used}/{cap} used")
        self.req_class = req_class
        self.reason = reason


class RequestMeter:
    _DDL = """CREATE TABLE IF NOT EXISTS venue_request_log (
        ts TEXT NOT NULL, account_key TEXT NOT NULL, payload_type INTEGER NOT NULL,
        req_class TEXT NOT NULL, client_msg_id TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_vrl ON venue_request_log (account_key, ts);"""

    def __init__(self, db_path: str | Path, account_key: str, *, budget: int, reserve: int,
                 now: datetime) -> None:
        if not 0 < budget <= BUDGET_MAX:
            raise DataQualityError("daily_request_budget", budget, f"must be in (0, {BUDGET_MAX}]")
        if not 0 < reserve < budget:
            raise DataQualityError("close_reserve", reserve, "must be in (0, budget)")
        self.account_key = account_key
        self.budget = budget
        self.reserve = reserve
        self._db = open_store(db_path)
        self._db.executescript(self._DDL)

    def used(self, now: datetime) -> int:
        (n,) = self._db.execute("SELECT COUNT(*) FROM venue_request_log WHERE account_key = ? AND ts > ?",
                                (self.account_key, (now - WINDOW).isoformat())).fetchone()
        return int(n)

    def admit(self, req_class: str, now: datetime) -> None:
        """Raise BudgetRefused if this request may not be sent now."""
        if req_class not in CLASSES:
            raise DataQualityError("req_class", req_class, f"one of {CLASSES}")
        used = self.used(now)
        if req_class in EXIT_CLASSES and (req_class != "auth" or used < self.budget):
            return
        if used >= self.budget:
            raise BudgetRefused(req_class, used, self.budget, "VENUE_BUDGET_EXHAUSTED")
        if used >= self.budget - self.reserve:
            raise BudgetRefused(req_class, used, self.budget, "VENUE_BUDGET_OPEN_EXHAUSTED")

    def record(self, payload_type: int, req_class: str, client_msg_id: str, now: datetime) -> None:
        """Count one request, persisted BEFORE the frame leaves (a crash can overcount, never under)."""
        self._db.execute("INSERT INTO venue_request_log VALUES (?,?,?,?,?)",
                         (now.isoformat(), self.account_key, payload_type, req_class, client_msg_id))
        self._db.commit()

    def state(self, now: datetime) -> dict:
        return {"used_24h": self.used(now), "cap": self.budget, "close_reserve": self.reserve}

    def close(self) -> None:
        self._db.close()
