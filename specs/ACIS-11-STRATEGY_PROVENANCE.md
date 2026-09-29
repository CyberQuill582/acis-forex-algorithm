# ACIS-11 — Strategy Provenance, Lifecycle & the Literature Law — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-PROVENANCE-011` |
| **Version** | 1.2 (LOCKED — the look register is authoritative for graded numbers, 2026-09-25) · 1.1 (LOCKED — v2.11 declared-deviations law, 2026-07-16) |
| **Layer / DIR** | Layer 4 · `[DIR:core/signals]` (provenance/lifecycle scaffolding lives with AGON) |
| **Consumes** | Module registrations (design-time), re-validation verdicts (phase-11 harness / Phronesis via §12) |
| **Emits** | Provenance + lifecycle state → `acis://strategies/provenance` (ACIS-08); rung gates consumed by AGON (ACIS-04) |
| **Depends On** | `../ACIS_SPEC.md` §5.6, §5.7, §12, §18 · `ACIS-04`, `ACIS-00` |
| **Blocks** | ACIS-04 v1.1 (phase 5) |
| **Corrections applied** | F29 (literature cadence), GAP-0019 (demotion transition), C9 (expectancy at every rung), C14 (evolution law) |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Algorithm & config · 7. Core logic · 8. State machine · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Make §5.6/§5.7 executable: no strategy module exists without a provenance record and a falsifier; every module lives on the rung ladder its whole life with a re-validation due date; demotion is automatic and risk-reducing; retirement is a graveyard with declared revival conditions, never deletion. This layer is the **anti-self-deception bookkeeping** — it never generates signals and never sizes.

**IS (phase-5 scaffolding):** the `ProvenanceRecord` contract and registration gate (no falsifier ⇒ no Arena entry); the attempt registry; rung-ladder state machine with due dates; the GAP-0019 demotion transition (immediate new-entry freeze → staged Arena removal at a flat boundary); the graveyard with revival conditions; the challenger-lane and reading-list *records*; SQLite store + MCP snapshot sources.

**IS NOT:** it does not run walk-forwards (phase-11 harness executes re-validation and reports a verdict); it does not do LLM research (the §5.6 research loop is Phronesis-side, out-of-band, landing only as staged code/config); it never promotes to live (human sign-off, §5.6); it holds no market data and emits no orders.

**Done-when:** a module without a complete provenance record cannot register; rung transitions follow §8 exactly (demote = one rung, automatic, logged; promote = one rung, gated, never by backtest numbers alone); a failed re-validation freezes new entries instantly and stages removal to a flat boundary with staleness observable; graveyard entries surface when their revival condition is declared matched; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/signals/provenance.py::ProvenanceStore` — `register(record) -> None` (raises on incomplete provenance), `record_attempt(family, variant_descriptor)`, `rung_of(strategy_id) -> Rung`, `entry_allowed(strategy_id, now) -> bool` (the gate AGON checks before a module may emit), `apply_revalidation(strategy_id, verdict, now)`, `demote(strategy_id, reason, now)`, `retire(strategy_id, revival_condition, now)`, `promote_one_rung(strategy_id, evidence, now)` (paper→live additionally requires `human_token` — refused otherwise), `challengers_of(champion_id)`, `reading_list()` / `record_source_disposition(...)`, `snapshot()`.

**Inputs are declarations and verdicts, never market data.** All state-changing methods take explicit `now: datetime` (UTC, tz-aware) — no hidden clock.

## 3. Architecture & responsibility

One unit: `provenance.py` (records + registry + rung ladder + graveyard + reading list, SQLite-backed). Single responsibility: **strategy bookkeeping and gating.** It imports nothing from other core layers (leaf module; AGON imports it, not vice versa). The phase-11 harness and Phronesis reach it only through declared methods (and §12 read surfaces) — a verdict is data, not code.

## 4. Output contract

```python
class Rung(str, Enum):
    INCUBATION = "INCUBATION"   # backtest only
    PAPER      = "PAPER"        # live data, no real-money orders (practice-mode demo orders count: master v2.23)
    LIVE       = "LIVE"         # real orders (human sign-off to enter)
    DECAYED    = "DECAYED"      # failed re-validation from LIVE/PAPER; exits managed, no new entries
    RETIRED    = "RETIRED"      # graveyard, revival condition declared

@dataclass(frozen=True)
class ProvenanceRecord:
    strategy_id: str            # stable id, e.g. "trend_following_v1"
    citation: str               # author/work/edition-or-section, or "lineage:<strategy_id>"
    claimed_inefficiency: str   # the market inefficiency it exploits
    why_it_persists: str        # why that inefficiency should exist in current markets
    falsifier: str              # the live-performance bound that kills it — MANDATORY
    registered_at: datetime
```

Every field non-empty (whitespace-only = empty ⇒ `DataQualityError`). **A strategy that cannot state its falsifier does not enter the Arena** (§5.6) — `register()` is the enforcement point, and AGON refuses to construct a module whose `strategy_id` is unregistered.

## 5. Data schemas

- **`RungState`:** `strategy_id`, `rung`, `revalidation_due` (date), `entries_frozen: bool`, `freeze_reason`, `removal_staged: bool`, `boundaries_skipped` (GAP-0019 mirrors the QIEA C2 pattern), `updated_at`.
- **`AttemptRecord`:** `family` (e.g. "trend_following"), `variant_descriptor` (free text of what was varied), `recorded_at`. The count per family is THE multiple-testing denominator — you cannot un-try a variant; there is no delete API.
- **`GraveyardEntry`:** `strategy_id`, `final_rung`, `final_metrics_json`, `revival_condition` (non-empty text tied to regime/inefficiency conditions), `retired_at`, `revival_flagged: bool`.
- **`ChallengerRecord`:** `challenger_id`, `champion_id`, `comparison_window_days`, `started_at` — paper-only by construction (a challenger row never changes the champion's rung; promotion goes through the full ladder).
- **`SourceDisposition`:** `source` (book/paper/URL citation), `disposition ∈ {implemented, rejected_with_reason, queued}`, `reason`, `recorded_at` — the reading-list ledger (F29).
- **Config (`provenance:`):** `revalidation_cadence_days: 90` (default quarterly, §5.7), `challenger_comparison_window_days: 60`. Required.

## 6. Algorithm & config set

- **Registration gate:** `register()` validates completeness; duplicate `strategy_id` re-registration is an error (provenance is written once; lineage variants get new ids citing `lineage:<parent>`).
- **Due dates:** on entering any active rung (INCUBATION/PAPER/LIVE), `revalidation_due = now + revalidation_cadence_days`. `apply_revalidation(PASS)` re-arms the date; `apply_revalidation(FAIL)` ⇒ automatic `demote()` (no debate, logged).
- **The C9 tie-in:** a re-validation verdict is only ever computed by the phase-11 harness under the strategy's own falsifier AND the C9 expectancy gate; this store records verdicts, it does not compute them (separation: bookkeeping vs measurement).
- **Attempt registry:** metrics reported anywhere must quote `attempts(family)` beside them; `snapshot()` always includes the count (the §5.6 anti-overfitting law's denominator).

## 7. Core logic — the GAP-0019 demotion transition (mirrors QIEA C2)

On demotion from PAPER/LIVE (re-validation failure or explicit `demote`):
1. **Instantly** (same call): `entries_frozen = True` — AGON's `entry_allowed()` returns False from this moment; freezing new entries is risk-reducing and needs no boundary.
2. Open positions are NOT touched — they remain managed by the strategy's own exit logic until flat (a live position is never orphaned, §5.7).
3. Arena **removal is staged**: `removal_staged = True`; at each session boundary where the strategy still holds open positions, `boundaries_skipped += 1` and `STRATEGY_REMOVAL_STALLED` is logged + surfaced (exactly like a stalled param promotion). At the first flat boundary, the rung transition completes (`DECAYED`, or one rung down per §8).
4. Demotion is agent-executable (risk-reducing). **Promotion is not:** `promote_one_rung` refuses PAPER→LIVE without `human_token` (§5.6 — live behaviour is the only definition of "works", and a human signs it).

**Graveyard & revival:** `retire()` requires a non-empty revival condition. `flag_revival(strategy_id, evidence, now)` marks `revival_flagged` for surfacing on `acis://strategies/provenance` — re-incubation re-enters at INCUBATION (the *bottom* rung) with its attempt history intact; the flag never auto-promotes.

## 8. State machine (the rung ladder, transitions exhaustive)

`INCUBATION → PAPER` (promote: evidence recorded) · `PAPER → LIVE` (promote: evidence + human token) · `LIVE → DECAYED` / `PAPER → DECAYED` (failed re-validation; via the §7 transition) · `DECAYED → RETIRED` (retire, revival condition mandatory) · `DECAYED → PAPER` (re-proves through re-validation) · `RETIRED → INCUBATION` (revival, bottom rung). **No other edges exist** — in particular there is no path to LIVE that skips PAPER, no backtest-number promotion, and no un-retire that keeps prior rung. Every transition logs `RUNG_TRANSITION{strategy_id, from, to, reason}`.

## 9. Persistence & logging

`provenance_log` (JSONL, standard envelope): `STRATEGY_REGISTERED`, `ATTEMPT_RECORDED`, `RUNG_TRANSITION`, `ENTRIES_FROZEN`, `STRATEGY_REMOVAL_STALLED{strategy_id, boundaries_skipped}`, `STRATEGY_RETIRED`, `REVIVAL_FLAGGED`, `REVALIDATION_APPLIED{verdict}`, `SOURCE_DISPOSITION`. All state also in SQLite (restart-safe; a reopened store resumes rungs, freezes, and counters).

## 10. Store schema (SQLite)

```sql
CREATE TABLE provenance (
    strategy_id TEXT PRIMARY KEY, citation TEXT NOT NULL,
    claimed_inefficiency TEXT NOT NULL, why_it_persists TEXT NOT NULL,
    falsifier TEXT NOT NULL, registered_at TEXT NOT NULL
);
CREATE TABLE rung_state (
    strategy_id TEXT PRIMARY KEY REFERENCES provenance(strategy_id),
    rung TEXT NOT NULL, revalidation_due TEXT,
    entries_frozen INTEGER NOT NULL DEFAULT 0, freeze_reason TEXT,
    removal_staged INTEGER NOT NULL DEFAULT 0,
    boundaries_skipped INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, family TEXT NOT NULL,
    variant_descriptor TEXT NOT NULL, recorded_at TEXT NOT NULL
);                                            -- append-only: no UPDATE/DELETE path exists
CREATE TABLE graveyard (
    strategy_id TEXT PRIMARY KEY, final_rung TEXT NOT NULL,
    final_metrics_json TEXT NOT NULL, revival_condition TEXT NOT NULL,
    retired_at TEXT NOT NULL, revival_flagged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE challengers (
    challenger_id TEXT PRIMARY KEY, champion_id TEXT NOT NULL,
    comparison_window_days INTEGER NOT NULL, started_at TEXT NOT NULL
);
CREATE TABLE reading_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
    disposition TEXT NOT NULL, reason TEXT, recorded_at TEXT NOT NULL
);
```

## 11. MCP contract

`acis://strategies/provenance` (ACIS-08) serves `ProvenanceStore.snapshot()`: per strategy — citation, lineage, falsifier, attempt count (family), current rung, revalidation due, freeze/stall state, graveyard revival flags, reading-list ledger. Read-only. The `strategy-provenance-audit` prompt (§12) walks this surface before any live-promotion proposal. **No MCP tool mutates provenance**; verdicts arrive via the phase-11 harness in-process, and human sign-off is a token on `promote_one_rung`, not an MCP write.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| incomplete/blank provenance field | `DataQualityError` — registration refused |
| unregistered strategy referenced | `DataQualityError` (AGON must not construct the module) |
| duplicate registration | `DataQualityError` (provenance is written once) |
| PAPER→LIVE without human token | `PromotionForbiddenError` (same teeth-class as QIEA staging) |
| retire without revival condition | `DataQualityError` |
| invalid rung edge (e.g. INCUBATION→LIVE) | `DataQualityError` — the §8 edge set is exhaustive |
| attempt deletion attempted | no such API — structurally impossible |

## 13. Logic-flaw registry
- **C-PRV-1 (falsifier gate):** no falsifier ⇒ no registration ⇒ no module; test proves a blank falsifier is refused and AGON refuses an unregistered module id.
- **C-PRV-2 (GAP-0019):** demotion freezes new entries in the same call, never touches open-position management, and stages removal with observable staleness; test walks freeze→stall×N→flat-boundary completion.
- **C-PRV-3 (no self-promotion):** PAPER→LIVE requires the human token; test proves refusal without it; no MCP tool can mutate rungs.
- **C-PRV-4 (attempt registry is append-only):** attempts only grow; snapshot always carries the count; test asserts no deletion path and count monotonicity. *(v1.2, master v2.21/v2.22: for GRADED numbers the authoritative registry is the look register (ACIS-09 C-BT-11 v2). This registry keeps the provenance attempts, i.e. literature variants tried; each graded one must ALSO have its look-register line.)*
- **C-PRV-5 (graveyard is a library):** retirement without a revival condition is refused; revival re-enters at INCUBATION with attempts intact.
- **C-PRV-6 (challenger lane is paper-only):** a challenger record never alters the champion's rung; promotion candidates go through the full ladder.

## 14. Test contract (postcondition-style)

**Unit:** registration completeness gate (each blank field refused); duplicate id refused; rung ladder — every legal edge transitions + every illegal edge raises (exhaustive matrix); re-validation PASS re-arms the due date, FAIL demotes exactly one rung with `ENTRIES_FROZEN` logged; GAP-0019 sequence: fail → `entry_allowed()` False immediately → N boundaries with positions ⇒ `boundaries_skipped == N` + stall logged/surfaced → flat boundary completes the transition; PAPER→LIVE without token raises, with token transitions; retire without revival condition raises; revival flag surfaces and re-incubation lands at INCUBATION; attempt count monotone; reading-list dispositions recorded; restart: reopened store resumes rungs/freezes/counters (assert store, not return codes).

**Integration (with ACIS-04):** AGON refuses to construct a module whose id is unregistered (C-PRV-1); a frozen strategy emits no NEW entry signals while its exit logic still can (jointly with ACIS-04 §7).

## 15. Integration gate

**What AGON (ACIS-04) consumes:** `entry_allowed(strategy_id, now)` as a per-module emission gate, and the registration requirement at module construction. **What ACIS-08 consumes:** `snapshot()` for `acis://strategies/provenance`. **Done-when (phase 5 scaffolding):** §14 tests green in a full run; no walk-forward execution (phase 11), no LLM research loop (Phronesis-side), no live promotion path exercised.

## Changelog
- **1.2 (LOCKED, 2026-09-25)** — Master v2.21/v2.22: the look register (ACIS-09) is the authoritative registry for graded numbers, and this attempt registry keeps provenance attempts (GAP-P12D-123).
- **1.1 (LOCKED, 2026-07-16)** — v2.11 declared-deviations law (owner-directed, external-referent pass): `ProvenanceRecord.declared_deviations: tuple[str, ...]` — every departure from the cited source's ACTUAL method, exhaustively; an EMPTY tuple is the positive assertion "implemented as published"; persisted, exposed on `snapshot()`/`acis://strategies/provenance`, and audited by the new external-referent per-phase audit (CLAUDE.md). All six v1 modules now carry honest deviation lists (none is "as published"). Blank deviations refused.
- **1.0 (LOCKED, 2026-07-15)** — Authored at phase-5 start per the deep-spec queue. Makes §5.6/§5.7 executable as scaffolding: falsifier-gated registration, append-only attempt registry, exhaustive rung ladder with quarterly re-validation due dates, the GAP-0019 demotion transition on the QIEA C2 pattern, graveyard with mandatory revival conditions, paper-only challenger lane, F29 reading-list ledger. Verdict *computation* stays with ACIS-09 (phase 11); research stays out-of-band (§0/§12). Human token required for PAPER→LIVE — no agent self-promotion, mirroring the family audit-firewall.
