"""ParamLibrary — active + PendingParamStore, staging/promotion (ACIS-03 §7–§10).

The non-overridable invariant (master §5): params are NEVER promoted mid-session
or with open positions. `promote()` off the gate raises PromotionForbiddenError —
the testable teeth (C-QIEA-1). Staleness is observable, never force-resolved
(C-QIEA-2); position-close is not a trigger (C-QIEA-3): nothing here subscribes
to position events — only explicit boundary calls move state. The flat check
reaches positions ONLY via PositionGate.open_position_count() (C-QIEA-4).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from config.schemas import ZonedTime
from core.data.errors import DataQualityError
from core.data.fx_clock import at_local_minute
from core.optimizer.param_types import ActiveParamSet, ParamSet, PendingEntry
from core.regime.regime_types import RegimeType


class PromotionForbiddenError(Exception):
    """promote() called off a session boundary or with open positions — caller bug."""


class PositionGate(Protocol):
    """Narrow read-only flat gate (§7): a count, never sizes/PnL/instruments."""

    def open_position_count(self) -> int: ...


def is_session_boundary(now: datetime, boundaries: list[ZonedTime]) -> bool:
    """C1 + the GAP-0025 ruling: a discrete instant, minute-granularity, matched
    ONLY against the declared session_boundaries list — each a local wall time in
    its centre, so the UTC instant follows DST (GAP-P12D-10)."""
    if now.tzinfo is None:
        raise ValueError("boundary check requires a tz-aware datetime")
    return any(at_local_minute(now, b.zone, b.at) for b in boundaries)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS param_active (
    regime            TEXT PRIMARY KEY,
    param_set_id      TEXT NOT NULL,
    params            TEXT NOT NULL,
    fitness_score     REAL NOT NULL,
    evolved_at        TEXT NOT NULL,
    promoted_at       TEXT NOT NULL,
    source_pending_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS param_pending (
    pending_id         TEXT PRIMARY KEY,
    regime             TEXT NOT NULL UNIQUE,
    params             TEXT NOT NULL,
    fitness_score      REAL NOT NULL,
    staged_at          TEXT NOT NULL,
    boundaries_skipped INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS param_history (
    param_set_id TEXT NOT NULL, regime TEXT NOT NULL, params TEXT NOT NULL,
    fitness_score REAL NOT NULL, promoted_at TEXT NOT NULL,
    PRIMARY KEY (param_set_id, promoted_at)
);
"""


def _params_to_json(p: ParamSet) -> str:
    d = p.gene_values()
    d["regime"] = p.regime.value
    d["param_set_id"] = p.param_set_id
    d["fitness_score"] = p.fitness_score
    d["evolved_at"] = p.evolved_at.isoformat()
    return json.dumps(d, sort_keys=True)


def _params_from_json(raw: str) -> ParamSet:
    d = json.loads(raw)
    d["regime"] = RegimeType(d["regime"])
    d["evolved_at"] = datetime.fromisoformat(d["evolved_at"])
    return ParamSet(**d)


class ParamLibrary:
    """Regime-indexed parameter library: active sets + PendingParamStore (SQLite)."""

    def __init__(
        self,
        db_path: str | Path,
        boundaries: list[ZonedTime],
        stall_alert_boundaries: int,
        gate: PositionGate,
        logger,
    ) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.executescript(_SCHEMA)
        self._db.commit()
        self._boundaries = boundaries
        self._stall_threshold = stall_alert_boundaries
        self._gate = gate
        self._log = logger

    # -- staging (§7.2) ------------------------------------------------------ #

    def stage(self, params: ParamSet, *, now: datetime | None = None) -> str:
        pending_id = str(uuid.uuid4())
        staged_at = (now or datetime.now(timezone.utc)).isoformat()
        with self._db:  # a newer evolution for the regime supersedes its pending set
            replaced = self._db.execute(
                "DELETE FROM param_pending WHERE regime = ?", (params.regime.value,)
            ).rowcount
            self._db.execute(
                "INSERT INTO param_pending VALUES (?, ?, ?, ?, ?, 0)",
                (pending_id, params.regime.value, _params_to_json(params),
                 params.fitness_score, staged_at),
            )
        self._log.event(
            "PARAM_STAGED",
            regime=params.regime.value, pending_id=pending_id,
            param_set_id=params.param_set_id, replaced_previous=bool(replaced),
        )
        return pending_id

    # -- promotion (§7.3, the teeth) ------------------------------------------ #

    def promote(self, now: datetime) -> list[str]:
        """Promote every pending entry. Off-gate calls raise (C-QIEA-1)."""
        if not is_session_boundary(now, self._boundaries):
            self._log.event("PROMOTION_FORBIDDEN", reason="not_session_boundary",
                            at=now.isoformat())
            raise PromotionForbiddenError(f"{now.isoformat()} is not a session boundary")
        open_count = self._gate.open_position_count()
        if open_count != 0:
            self._log.event("PROMOTION_FORBIDDEN", reason="open_positions",
                            open_positions=open_count, at=now.isoformat())
            raise PromotionForbiddenError(f"open_positions == {open_count}, must be 0")
        promoted: list[tuple[str, str, str]] = []
        promoted_at = now.isoformat()
        rows = self._db.execute(
            "SELECT pending_id, regime, params, fitness_score FROM param_pending"
        ).fetchall()
        # GAP-0036: ONE transaction over the whole sweep — a failure on any entry
        # rolls back every entry, so a boundary sweep can never leave a partial
        # promotion (some regimes active, others stranded).
        try:
            with self._db:
                for pending_id, regime, params_json, fitness in rows:
                    params = _params_from_json(params_json)
                    self._db.execute(
                        "INSERT INTO param_history VALUES (?, ?, ?, ?, ?)",
                        (params.param_set_id, regime, params_json, fitness, promoted_at),
                    )
                    self._db.execute(
                        "INSERT INTO param_active VALUES (?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(regime) DO UPDATE SET param_set_id=excluded.param_set_id, "
                        "params=excluded.params, fitness_score=excluded.fitness_score, "
                        "evolved_at=excluded.evolved_at, promoted_at=excluded.promoted_at, "
                        "source_pending_id=excluded.source_pending_id",
                        (regime, params.param_set_id, params_json, fitness,
                         params.evolved_at.isoformat(), promoted_at, pending_id),
                    )
                    self._db.execute(
                        "DELETE FROM param_pending WHERE pending_id = ?", (pending_id,)
                    )
                    promoted.append((regime, pending_id, params.param_set_id))
        except sqlite3.IntegrityError as exc:
            # GAP-0036: the whole sweep rolled back — surface a taxonomy error,
            # never a raw sqlite exception, and never a partial promotion.
            raise DataQualityError("param_set_id", str(exc),
                                   "duplicate audit id in promotion sweep") from exc
        for regime, pending_id, param_set_id in promoted:  # log only committed facts
            self._log.event("PARAM_PROMOTED", regime=regime, pending_id=pending_id,
                            param_set_id=param_set_id)
        return [regime for regime, _, _ in promoted]

    def on_boundary(self, now: datetime) -> list[str]:
        """The C2 boundary sweep: promote when flat, otherwise count + surface the stall."""
        if not is_session_boundary(now, self._boundaries):
            raise PromotionForbiddenError(f"{now.isoformat()} is not a session boundary")
        if self._gate.open_position_count() == 0:
            return self.promote(now)
        with self._db:
            self._db.execute(
                "UPDATE param_pending SET boundaries_skipped = boundaries_skipped + 1"
            )
        for e in self.get_pending():
            self._log.event(
                "PARAM_PROMOTION_STALLED",
                regime=e.regime.value, boundaries_skipped=e.boundaries_skipped,
                staged_at=e.staged_at.isoformat(),
                stalled=e.boundaries_skipped >= self._stall_threshold,
            )
        return []

    # -- reads ----------------------------------------------------------------- #

    def get_active(self, regime: RegimeType) -> ActiveParamSet | None:
        row = self._db.execute(
            "SELECT params, promoted_at, source_pending_id FROM param_active WHERE regime = ?",
            (regime.value,),
        ).fetchone()
        if row is None:
            return None
        return ActiveParamSet(
            regime=regime, params=_params_from_json(row[0]),
            promoted_at=datetime.fromisoformat(row[1]),
            source_pending_id=row[2],
        )

    def has_active(self, regime: RegimeType) -> bool:
        return self.get_active(regime) is not None

    def get_pending(self, regime: RegimeType | None = None) -> list[PendingEntry]:
        sql = ("SELECT pending_id, regime, params, staged_at, boundaries_skipped "
               "FROM param_pending")
        args: tuple = ()
        if regime is not None:
            sql += " WHERE regime = ?"
            args = (regime.value,)
        return [
            PendingEntry(
                pending_id=r[0], regime=RegimeType(r[1]),
                params=_params_from_json(r[2]),
                staged_at=datetime.fromisoformat(r[3]), boundaries_skipped=r[4],
            )
            for r in self._db.execute(sql, args).fetchall()
        ]

    # -- MCP snapshot sources (§11; the resource itself is wired at phase 10) --- #

    def pending_snapshot(self) -> list[dict]:
        return [
            {
                "regime": e.regime.value,
                "pending_id": e.pending_id,
                "param_set_id": e.params.param_set_id,
                "staged_at": e.staged_at.isoformat(),
                "boundaries_skipped": e.boundaries_skipped,
                "stalled": e.boundaries_skipped >= self._stall_threshold,
            }
            for e in self.get_pending()
        ]

    def active_snapshot(self) -> list[dict]:
        rows = self._db.execute(
            "SELECT regime, param_set_id, fitness_score, promoted_at FROM param_active"
        ).fetchall()
        return [
            {"regime": r[0], "param_set_id": r[1], "fitness_score": r[2], "promoted_at": r[3]}
            for r in rows
        ]

    def close(self) -> None:
        self._db.close()
