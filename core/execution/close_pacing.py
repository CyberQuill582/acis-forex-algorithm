"""Pacing for closes the venue keeps refusing (audits X6 / F5). Invariants:
  * A de-risking close is never BLOCKED — it is PACED, and every paced attempt is logged
    (EXEC_CLOSE_PACED, a REJECTED report), so the weekend flatten's every-tick re-emission
    cannot turn a venue that refuses closes into a request flood past a firm's daily cap.
  * After n consecutive failed closes of one (venue, instrument) the next may go no sooner
    than min(BASE_S · 2^(n−1), MAX_S) after the last one; a close that fills resets n.
  * Once CEILING close attempts have gone to that (venue, instrument) in a rolling 24 h,
    every further attempt waits the full MAX_S after the last: slower, never stopped.
  * Attempts are persisted in the fill log and re-read at boot: a restart keeps the pace.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.execution.fill_store import FillReportStore

BASE_S = 2.0
MAX_S = 300.0
CEILING = 100
WINDOW = timedelta(hours=24)


class ClosePacer:
    def __init__(self, store: FillReportStore, now: datetime) -> None:
        self._store = store
        self._attempts: dict[tuple[str, str], list[tuple[datetime, bool]]] = {}
        for venue, instrument, at, ok in store.close_attempts(now - WINDOW):
            self._attempts.setdefault((venue, instrument), []).append((at, ok))

    def wait_s(self, venue: str, instrument: str, now: datetime) -> float:
        """Seconds before a close of (venue, instrument) may go; 0 when it may go now."""
        rows = [r for r in self._attempts.get((venue, instrument), []) if r[0] > now - WINDOW]
        self._attempts[(venue, instrument)] = rows
        if not rows:
            return 0.0
        failures = 0
        for _, ok in reversed(rows):
            if ok:
                break
            failures += 1
        delay = min(BASE_S * 2 ** (failures - 1), MAX_S) if failures else 0.0
        if len(rows) >= CEILING:
            delay = MAX_S
        return max(0.0, (rows[-1][0] + timedelta(seconds=delay) - now).total_seconds())

    def record(self, venue: str, instrument: str, at: datetime, ok: bool) -> None:
        self._attempts.setdefault((venue, instrument), []).append((at, ok))
        self._store.record_close_attempt(venue, instrument, at, ok, keep_since=at - WINDOW)
