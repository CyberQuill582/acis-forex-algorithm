"""Risk persistence (ACIS-07 §10): risk_snapshot + halt_event + the persisted
risk-restrictive state a restart must restore before the first evaluate
(GAP-0050 — a restart is never a relaxation).

`halt_event.cleared_by` is 'human:<token>' for equity/global scope — a machine
can never populate it (enforced at the MCP layer, ACIS-08 phase 10). Snapshot
writes are idempotent on the timestamp PK.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.risk.risk_types import RiskSnapshot


class RiskStore:
    _DDL = """
    CREATE TABLE IF NOT EXISTS risk_snapshot (
        ts TEXT PRIMARY KEY, daily_pnl TEXT NOT NULL, daily_dd_pct REAL NOT NULL,
        open_dd_pct REAL NOT NULL, total_dd_pct REAL NOT NULL,
        var_1pct REAL NOT NULL, max_cluster_pct REAL NOT NULL,
        sharpe_50t REAL NOT NULL, win_rate_50t REAL NOT NULL,
        alpha_decay_flag INTEGER NOT NULL, alpha_decay_state TEXT NOT NULL,
        slippage_alert INTEGER NOT NULL, equity TEXT NOT NULL,
        equity_floor_breached INTEGER NOT NULL, instruments_halted TEXT NOT NULL,
        taper_factor REAL NOT NULL, session_id TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS halt_event (
        halt_id TEXT PRIMARY KEY, ts TEXT NOT NULL, scope TEXT NOT NULL,
        reason TEXT NOT NULL, cleared_at TEXT, cleared_by TEXT
    );
    CREATE TABLE IF NOT EXISTS restrictive_state (
        k TEXT PRIMARY KEY, v TEXT NOT NULL
    );
    """

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(self._DDL)
        self._conn.commit()

    def write_snapshot(self, s: RiskSnapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO risk_snapshot VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s.timestamp.isoformat(), str(s.daily_pnl), s.daily_drawdown_pct,
             s.open_drawdown_pct, s.total_drawdown_pct, s.portfolio_var_1pct,
             s.max_correlated_cluster_pct, s.rolling_sharpe_50t, s.rolling_win_rate_50t,
             int(s.alpha_decay_flag), s.alpha_decay_state, int(s.slippage_slope_alert),
             str(s.equity), int(s.equity_floor_breached),
             json.dumps(list(s.instruments_halted)), s.taper_factor, s.session_id))
        self._conn.commit()

    def record_halt(self, halt_id: str, ts: str, scope: str, reason: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO halt_event (halt_id, ts, scope, reason) "
            "VALUES (?,?,?,?)", (halt_id, ts, scope, reason))
        self._conn.commit()

    def clear_halt(self, halt_id: str, cleared_at: str, cleared_by: str) -> None:
        self._conn.execute(
            "UPDATE halt_event SET cleared_at=?, cleared_by=? WHERE halt_id=?",
            (cleared_at, cleared_by, halt_id))
        self._conn.commit()

    def save_restrictive_state(self, *, alpha_armed: bool, taper_factor: float) -> None:
        for k, v in (("alpha_armed", json.dumps(alpha_armed)),
                     ("taper_factor", json.dumps(taper_factor))):
            self._conn.execute(
                "INSERT OR REPLACE INTO restrictive_state (k, v) VALUES (?,?)", (k, v))
        self._conn.commit()

    def load_restrictive_state(self) -> dict:
        rows = self._conn.execute("SELECT k, v FROM restrictive_state").fetchall()
        return {k: json.loads(v) for k, v in rows}

    def snapshot_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM risk_snapshot").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
