"""Strategy provenance, lifecycle & the literature law (ACIS-11).

Anti-self-deception bookkeeping: falsifier-gated registration, append-only
attempt registry, the exhaustive rung ladder with re-validation due dates,
the GAP-0019 demotion transition (instant entry freeze -> staged removal at a
flat boundary), the graveyard with mandatory revival conditions, the paper-only
challenger lane, and the F29 reading-list ledger. It never generates signals,
never sizes, never computes verdicts (phase-11 harness does), and PAPER->LIVE
promotion requires a human token (C-PRV-3 — no agent self-promotion).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from core.data.errors import DataQualityError
from core.optimizer.param_library import PromotionForbiddenError


class Rung(str, Enum):
    INCUBATION = "INCUBATION"
    PAPER = "PAPER"
    LIVE = "LIVE"
    DECAYED = "DECAYED"
    RETIRED = "RETIRED"


# ACIS-11 §8: the exhaustive edge set — no other transition exists.
# (INCUBATION -> RETIRED added at the phase-5 audit triage, GAP-0045: the
# disposal path for a failed incubation; revival condition stays mandatory.)
_LEGAL_EDGES: frozenset[tuple[Rung, Rung]] = frozenset({
    (Rung.INCUBATION, Rung.PAPER),
    (Rung.PAPER, Rung.LIVE),
    (Rung.LIVE, Rung.DECAYED),
    (Rung.PAPER, Rung.DECAYED),
    (Rung.INCUBATION, Rung.RETIRED),
    (Rung.DECAYED, Rung.RETIRED),
    (Rung.DECAYED, Rung.PAPER),
    (Rung.RETIRED, Rung.INCUBATION),
})

_ACTIVE_RUNGS = frozenset({Rung.INCUBATION, Rung.PAPER, Rung.LIVE})


@dataclass(frozen=True)
class ProvenanceRecord:
    strategy_id: str
    citation: str
    claimed_inefficiency: str
    why_it_persists: str
    falsifier: str
    registered_at: datetime

    def __post_init__(self) -> None:
        for name in ("strategy_id", "citation", "claimed_inefficiency",
                     "why_it_persists", "falsifier"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v.strip():
                raise DataQualityError(name, v, "provenance field must be non-empty (§5.6)")
        if self.registered_at.tzinfo is None:
            raise DataQualityError("registered_at", self.registered_at, "must be tz-aware")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS provenance (
    strategy_id TEXT PRIMARY KEY, citation TEXT NOT NULL,
    claimed_inefficiency TEXT NOT NULL, why_it_persists TEXT NOT NULL,
    falsifier TEXT NOT NULL, registered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rung_state (
    strategy_id TEXT PRIMARY KEY REFERENCES provenance(strategy_id),
    rung TEXT NOT NULL, revalidation_due TEXT,
    entries_frozen INTEGER NOT NULL DEFAULT 0, freeze_reason TEXT,
    removal_staged INTEGER NOT NULL DEFAULT 0,
    boundaries_skipped INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, family TEXT NOT NULL,
    variant_descriptor TEXT NOT NULL, recorded_at TEXT NOT NULL
);
-- GAP-0048: append-only enforced IN the store, not by API omission
CREATE TRIGGER IF NOT EXISTS attempts_no_delete BEFORE DELETE ON attempts
BEGIN SELECT RAISE(ABORT, 'attempt registry is append-only (ACIS-11 C-PRV-4)'); END;
CREATE TRIGGER IF NOT EXISTS attempts_no_update BEFORE UPDATE ON attempts
BEGIN SELECT RAISE(ABORT, 'attempt registry is append-only (ACIS-11 C-PRV-4)'); END;
CREATE TABLE IF NOT EXISTS graveyard (
    strategy_id TEXT PRIMARY KEY, final_rung TEXT NOT NULL,
    final_metrics_json TEXT NOT NULL, revival_condition TEXT NOT NULL,
    retired_at TEXT NOT NULL, revival_flagged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS challengers (
    challenger_id TEXT PRIMARY KEY, champion_id TEXT NOT NULL,
    comparison_window_days INTEGER NOT NULL, started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reading_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
    disposition TEXT NOT NULL, reason TEXT, recorded_at TEXT NOT NULL
);
"""


class ProvenanceStore:
    def __init__(self, db_path: str | Path, revalidation_cadence_days: int, logger) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.executescript(_SCHEMA)
        self._db.commit()
        self._cadence = revalidation_cadence_days
        self._log = logger

    # -- registration (C-PRV-1) --------------------------------------------- #

    def register(self, record: ProvenanceRecord) -> None:
        if self.is_registered(record.strategy_id):
            raise DataQualityError("strategy_id", record.strategy_id,
                                   "provenance is written once (ACIS-11 §6)")
        due = (record.registered_at + timedelta(days=self._cadence)).isoformat()
        with self._db:
            self._db.execute(
                "INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?)",
                (record.strategy_id, record.citation, record.claimed_inefficiency,
                 record.why_it_persists, record.falsifier, record.registered_at.isoformat()),
            )
            self._db.execute(
                "INSERT INTO rung_state VALUES (?, ?, ?, 0, NULL, 0, 0, ?)",
                (record.strategy_id, Rung.INCUBATION.value, due,
                 record.registered_at.isoformat()),
            )
        self._log.event("STRATEGY_REGISTERED", strategy_id=record.strategy_id,
                        citation=record.citation, falsifier=record.falsifier)

    def is_registered(self, strategy_id: str) -> bool:
        return self._db.execute(
            "SELECT 1 FROM provenance WHERE strategy_id = ?", (strategy_id,)
        ).fetchone() is not None

    # -- attempt registry (C-PRV-4: append-only, no delete API) --------------- #

    def record_attempt(self, family: str, variant_descriptor: str, *, now: datetime) -> None:
        with self._db:
            self._db.execute("INSERT INTO attempts (family, variant_descriptor, recorded_at) "
                             "VALUES (?, ?, ?)", (family, variant_descriptor, now.isoformat()))
        self._log.event("ATTEMPT_RECORDED", family=family, variant=variant_descriptor,
                        attempts=self.attempts(family))

    def attempts(self, family: str) -> int:
        return self._db.execute(
            "SELECT COUNT(*) FROM attempts WHERE family = ?", (family,)
        ).fetchone()[0]

    # -- rung ladder (ACIS-11 §8) --------------------------------------------- #

    def rung_of(self, strategy_id: str) -> Rung:
        row = self._db.execute(
            "SELECT rung FROM rung_state WHERE strategy_id = ?", (strategy_id,)
        ).fetchone()
        if row is None:
            raise DataQualityError("strategy_id", strategy_id, "unregistered strategy")
        return Rung(row[0])

    def entry_allowed(self, strategy_id: str, now: datetime) -> bool:
        row = self._db.execute(
            "SELECT rung, entries_frozen FROM rung_state WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchone()
        if row is None:
            raise DataQualityError("strategy_id", strategy_id, "unregistered strategy")
        return Rung(row[0]) in _ACTIVE_RUNGS and not row[1]

    def _transition(self, strategy_id: str, to: Rung, reason: str, now: datetime,
                    *, freeze: bool | None = None) -> None:
        frm = self.rung_of(strategy_id)
        if (frm, to) not in _LEGAL_EDGES:
            raise DataQualityError("rung", f"{frm.value}->{to.value}",
                                   "illegal rung edge (ACIS-11 §8 is exhaustive)")
        due = ((now + timedelta(days=self._cadence)).isoformat()
               if to in _ACTIVE_RUNGS else None)
        with self._db:
            self._db.execute(
                "UPDATE rung_state SET rung=?, revalidation_due=?, updated_at=?, "
                "entries_frozen=COALESCE(?, entries_frozen), "
                "removal_staged=0, boundaries_skipped=0 WHERE strategy_id=?",
                (to.value, due, now.isoformat(),
                 None if freeze is None else int(freeze), strategy_id),
            )
        self._log.event("RUNG_TRANSITION", strategy_id=strategy_id,
                        from_rung=frm.value, to_rung=to.value, reason=reason)

    def promote_one_rung(self, strategy_id: str, evidence: str, now: datetime,
                         human_token: str | None = None) -> None:
        frm = self.rung_of(strategy_id)
        # GAP-0045: a frozen strategy cannot promote its way out — only a PASS
        # re-validation (which unfreezes) or retirement is an exit from a freeze.
        row = self._db.execute(
            "SELECT entries_frozen FROM rung_state WHERE strategy_id=?",
            (strategy_id,),
        ).fetchone()
        if row and row[0]:
            raise PromotionForbiddenError(
                f"{strategy_id} is entry-frozen (failed re-validation); promotion "
                "requires a PASS re-validation first (ACIS-11 §7/GAP-0045)"
            )
        to = {Rung.INCUBATION: Rung.PAPER, Rung.PAPER: Rung.LIVE,
              Rung.DECAYED: Rung.PAPER}.get(frm)
        if to is None:
            raise DataQualityError("rung", frm.value, "no promotion edge from this rung")
        if to is Rung.LIVE and not human_token:
            raise PromotionForbiddenError(
                "PAPER->LIVE requires a human token (§5.6 — live behaviour is the "
                "only definition of 'works', and a human signs it)"
            )
        if not evidence.strip():
            raise DataQualityError("evidence", evidence, "promotion evidence required")
        self._transition(strategy_id, to, f"promoted: {evidence}", now, freeze=False)

    # -- GAP-0019 demotion transition (ACIS-11 §7) ----------------------------- #

    def demote(self, strategy_id: str, reason: str, now: datetime) -> None:
        frm = self.rung_of(strategy_id)
        if frm not in (Rung.PAPER, Rung.LIVE):
            raise DataQualityError("rung", frm.value, "demotion applies to PAPER/LIVE")
        with self._db:  # instant, same call: new entries freeze (risk-reducing)
            self._db.execute(
                "UPDATE rung_state SET entries_frozen=1, freeze_reason=?, "
                "removal_staged=1, updated_at=? WHERE strategy_id=?",
                (reason, now.isoformat(), strategy_id),
            )
        self._log.event("ENTRIES_FROZEN", strategy_id=strategy_id, reason=reason)

    def on_boundary(self, strategy_id: str, open_positions: int, now: datetime) -> bool:
        """Complete a staged removal at a flat boundary; count the stall otherwise.
        Returns True when the DECAYED transition completed."""
        row = self._db.execute(
            "SELECT removal_staged, boundaries_skipped FROM rung_state WHERE strategy_id=?",
            (strategy_id,),
        ).fetchone()
        if row is None:
            raise DataQualityError("strategy_id", strategy_id, "unregistered strategy")
        if not row[0]:
            return False
        if open_positions != 0:
            skipped = row[1] + 1
            with self._db:
                self._db.execute(
                    "UPDATE rung_state SET boundaries_skipped=?, updated_at=? "
                    "WHERE strategy_id=?", (skipped, now.isoformat(), strategy_id),
                )
            self._log.event("STRATEGY_REMOVAL_STALLED", strategy_id=strategy_id,
                            boundaries_skipped=skipped)
            return False
        self._transition(strategy_id, Rung.DECAYED, "staged removal completed (flat)",
                         now, freeze=True)
        return True

    def apply_revalidation(self, strategy_id: str, verdict: str, now: datetime) -> None:
        if verdict not in ("PASS", "FAIL"):
            raise DataQualityError("verdict", verdict, "must be PASS or FAIL")
        self._log.event("REVALIDATION_APPLIED", strategy_id=strategy_id, verdict=verdict)
        if verdict == "PASS":
            due = (now + timedelta(days=self._cadence)).isoformat()
            with self._db:  # GAP-0045: a PASS re-proves the strategy — unfreeze
                self._db.execute(
                    "UPDATE rung_state SET revalidation_due=?, updated_at=?, "
                    "entries_frozen=0, freeze_reason=NULL, removal_staged=0, "
                    "boundaries_skipped=0 WHERE strategy_id=?",
                    (due, now.isoformat(), strategy_id),
                )
            return
        rung = self.rung_of(strategy_id)
        if rung in (Rung.PAPER, Rung.LIVE):
            self.demote(strategy_id, "failed re-validation", now)
        elif rung is Rung.INCUBATION:
            # bottom active rung: a failed incubation dies straight to the graveyard
            # path via DECAYED semantics — freeze; retirement needs its condition.
            with self._db:
                self._db.execute(
                    "UPDATE rung_state SET entries_frozen=1, freeze_reason=?, updated_at=? "
                    "WHERE strategy_id=?",
                    ("failed incubation re-validation", now.isoformat(), strategy_id),
                )
            self._log.event("ENTRIES_FROZEN", strategy_id=strategy_id,
                            reason="failed incubation re-validation")

    # -- graveyard (C-PRV-5) ---------------------------------------------------- #

    def retire(self, strategy_id: str, revival_condition: str, final_metrics: dict,
               now: datetime) -> None:
        if not revival_condition.strip():
            raise DataQualityError("revival_condition", revival_condition,
                                   "the graveyard is a library, not a landfill (§5.7)")
        frm = self.rung_of(strategy_id)
        self._transition(strategy_id, Rung.RETIRED, "retired", now, freeze=True)
        with self._db:
            self._db.execute(
                "INSERT INTO graveyard VALUES (?, ?, ?, ?, ?, 0)",
                (strategy_id, frm.value, json.dumps(final_metrics, sort_keys=True),
                 revival_condition, now.isoformat()),
            )
        self._log.event("STRATEGY_RETIRED", strategy_id=strategy_id,
                        revival_condition=revival_condition)

    def flag_revival(self, strategy_id: str, evidence: str, now: datetime) -> None:
        row = self._db.execute(
            "SELECT 1 FROM graveyard WHERE strategy_id = ?", (strategy_id,)
        ).fetchone()
        if row is None:
            raise DataQualityError("strategy_id", strategy_id, "not in the graveyard")
        with self._db:
            self._db.execute(
                "UPDATE graveyard SET revival_flagged=1 WHERE strategy_id=?", (strategy_id,)
            )
        self._log.event("REVIVAL_FLAGGED", strategy_id=strategy_id, evidence=evidence)

    def revive(self, strategy_id: str, now: datetime) -> None:
        """Re-incubation from the graveyard — the BOTTOM rung, attempts intact."""
        self._transition(strategy_id, Rung.INCUBATION, "revived from graveyard",
                         now, freeze=False)

    # -- challenger lane (C-PRV-6) + reading list (F29) --------------------------- #

    def add_challenger(self, challenger_id: str, champion_id: str,
                       comparison_window_days: int, now: datetime) -> None:
        with self._db:
            self._db.execute("INSERT INTO challengers VALUES (?, ?, ?, ?)",
                             (challenger_id, champion_id, comparison_window_days,
                              now.isoformat()))

    def challengers_of(self, champion_id: str) -> list[str]:
        return [r[0] for r in self._db.execute(
            "SELECT challenger_id FROM challengers WHERE champion_id = ?", (champion_id,)
        ).fetchall()]

    def record_source_disposition(self, source: str, disposition: str, reason: str,
                                  now: datetime) -> None:
        if disposition not in ("implemented", "rejected_with_reason", "queued"):
            raise DataQualityError("disposition", disposition, "unknown disposition")
        if disposition == "rejected_with_reason" and not reason.strip():
            raise DataQualityError("reason", reason, "rejection requires a reason")
        with self._db:
            self._db.execute(
                "INSERT INTO reading_list (source, disposition, reason, recorded_at) "
                "VALUES (?, ?, ?, ?)", (source, disposition, reason, now.isoformat()),
            )
        self._log.event("SOURCE_DISPOSITION", source=source, disposition=disposition)

    # -- MCP snapshot source (ACIS-11 §11) ----------------------------------------- #

    def snapshot(self) -> dict:
        strategies = []
        for row in self._db.execute(
            "SELECT p.strategy_id, p.citation, p.falsifier, r.rung, r.revalidation_due, "
            "r.entries_frozen, r.removal_staged, r.boundaries_skipped "
            "FROM provenance p JOIN rung_state r USING (strategy_id)"
        ).fetchall():
            family = row[0].rsplit("_v", 1)[0]
            strategies.append({
                "strategy_id": row[0], "citation": row[1], "falsifier": row[2],
                "rung": row[3], "revalidation_due": row[4],
                "entries_frozen": bool(row[5]), "removal_staged": bool(row[6]),
                "boundaries_skipped": row[7], "attempts": self.attempts(family),
            })
        graveyard = [
            {"strategy_id": r[0], "revival_condition": r[3], "revival_flagged": bool(r[5])}
            for r in self._db.execute("SELECT * FROM graveyard").fetchall()
        ]
        reading = [
            {"source": r[1], "disposition": r[2], "reason": r[3]}
            for r in self._db.execute("SELECT * FROM reading_list").fetchall()
        ]
        return {"strategies": strategies, "graveyard": graveyard, "reading_list": reading}

    def close(self) -> None:
        self._db.close()
