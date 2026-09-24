# ACIS Deep-Spec Set — Index & Constitution Map
**Document ID:** `ACIS-SPEC-INDEX-000` · **Version:** 1.3 · **Status:** ACTIVE
**Depends On:** `../ACIS_SPEC.md` (master), `../_SPEC_AUTHORING_GUIDE.md` (template), `../SPEC_AUDIT.md` (findings)
**Blocks:** every layer spec below

---

## 1. What this set is
`../ACIS_SPEC.md` is the **constitution** — layer law, guardrails, `[DIR:]` tags, conflict table, performance targets. It governs. This `specs/` set is the **buildable detail**: one deep document per layer, authored to the mandatory 15-section template in `../_SPEC_AUTHORING_GUIDE.md` §6, in the `../ACIS_SPEC.md` §15 implementation order.

**Precedence (binding):** master spec > this index > a layer spec. A layer spec may *add* detail; it may never *contradict* a rule in the master. If a layer spec needs to deviate, stop and amend the master first (CLAUDE.md rule).

## 2. The downward-only dependency law applied to the docs
Data flows down one layer at a time; the single upward edge is Risk Monitor → Governor HALT (master §2). The **spec dependencies mirror the data flow** — a layer spec `Depends On` only the layer directly above it (whose output object it consumes) and `Blocks` only the layer directly below it. No layer spec may reference the internals of a layer above it.

```
ACIS-01 Data Ingestion      ──emits MarketState──────────►
ACIS-02 NVMA Regime         ──emits RegimeContext────────►
ACIS-03 QIEA Optimizer      ──emits ActiveParamSet───────►
ACIS-04 Alpha Arena         ──emits Signal───────────────►
ACIS-05 Capital Governor    ──emits SizedOrder───────────►
ACIS-06 Execution Orch.     ──emits FillReport───────────►
ACIS-07 Risk Monitor        ──HALT ↑ to Governor ONLY────►
ACIS-08 Monitoring/MCP      ──observes all; controls via §12 contract (out-of-band)
ACIS-09 Backtest/Validation ──exercises 01–07 end-to-end; owns §14 gate
```

## 3. Document map & status
| ID | File | Layer / DIR | Consumes | Emits | Status |
|---|---|---|---|---|---|
| `ACIS-SPEC-DATA-001` | `ACIS-01-DATA_INGESTION.md` | Data `[DIR:core/data]` | raw feed | `MarketState` | v1.1 LOCKED (built, phase 1) |
| `ACIS-SPEC-REGIME-002` | `ACIS-02-NVMA_REGIME.md` | NVMA `[DIR:core/regime]` | `MarketState` | `RegimeContext` | v1.2 LOCKED (built, phase 3) |
| `ACIS-SPEC-QIEA-003` | `ACIS-03-QIEA_OPTIMIZER.md` | QIEA `[DIR:core/optimizer]` | `RegimeContext` + history | `ActiveParamSet` | v1.4 LOCKED (built, phase 4; v1.4 fitness window = time span) |
| `ACIS-SPEC-ALPHA-004` | `ACIS-04-ALPHA_ARENA.md` | Alpha Arena `[DIR:core/signals]` | `RegimeContext` + `ActiveParamSet` | `Signal` | v1.2 LOCKED (built, phase 5; AGON) |
| `ACIS-SPEC-GOV-005` | `ACIS-05-CAPITAL_GOVERNOR.md` | Governor `[DIR:core/governor]` | `Signal` + portfolio | `SizedOrder` | v1.2 LOCKED (built, phase 6) |
| `ACIS-SPEC-EXEC-006` | `ACIS-06-EXECUTION_ORCHESTRATOR.md` | Execution `[DIR:core/execution]` | `SizedOrder` | `FillReport` | v1.1 LOCKED (phase-8 build started 2026-07-17) |
| `ACIS-SPEC-RISK-007` | `ACIS-07-RISK_MONITOR.md` | Risk `[DIR:core/risk]` | `FillReport` + broker account state + all stores | `RiskSnapshot`, `HALT`/taper/decay (upward edge), heartbeat | v1.1 LOCKED (phase-9 gate cleared 2026-07-17) |
| `ACIS-SPEC-MCP-008` | `ACIS-08-MONITORING_MCP.md` | Monitoring `[DIR:monitoring]` | all resources | MCP resources/tools | v1.2 LOCKED (phase-10 BUILT + dual audits triaged 2026-07-18) |
| `ACIS-SPEC-BT-009` | `ACIS-09-BACKTEST_VALIDATION.md` | Backtest `[DIR:tests/backtest]` | 01–07 | §14 validation report | v1.6 LOCKED (phase 11 ✅ 2026-07-18; v1.2–1.3 phase-12 data layer; v1.4 embargo + Deflated Sharpe + date-joined SPX; v1.5 mutation targets; v1.6 per-regime + per-strategy attribution, 2026-09-16) |
| `ACIS-SPEC-EVENTS-010` | `ACIS-10-EVENTS_NEWS.md` | Events `[DIR:core/data]` (master §3.5–3.6) | calendar/news feeds + `platform_rules.yaml` | `EventPicture`, blackout windows, Tier-G flags | LOCKED (built, phase 2) |
| `ACIS-SPEC-PROV-011` | `ACIS-11-STRATEGY_PROVENANCE.md` | Provenance & literature law `[DIR:core/signals]` (master §5.5 Pair Divergence, §5.6) | literature citations, eval history | provenance records, attempt registry, rung ladder | TO AUTHOR |
| `ACIS-SPEC-SWAN-012` | `ACIS-12-SCENARIO_BOOK.md` | Black-swan replay + §8.6 watchdog `[DIR:core/risk + tests/backtest + scripts]` (master §8.5–8.6) | `scenario_book.yaml`, guardrails, heartbeat | gap-law replay verdicts (release gate), watchdog flatten | v1.0 LOCKED (authored 2026-07-17, phase-9 gate) |
| `ACIS-SPEC-VENUE-013` | `ACIS-13-VENUE_ADAPTERS.md` | Platform adapters + attach protocol `[DIR:core/data + core/execution]` (master §7.5, §9.5 rulebook load) | platform APIs, `platform_rules.yaml`, `instruments.yaml` | feed/execution adapter pairs, capability descriptors, conformance verdicts | DRAFT v0.1 (2026-09-25, cTrader Open API first; NOT LOCKED — review pass pending: OQ-01/02/03a, ACIS-06 amendments; GAP-P12D-69/70) |

Status ladder: `DRAFT` → `REVIEWED` (passed `_SPEC_REVIEW_PASS.md`) → `LOCKED` (ready to build) → `BUILT` (phase complete, tests green).

## 4. Shared vocabulary (defined once, referenced everywhere)
These are defined authoritatively in the master spec and the layer that owns them; every other doc references, never redefines:
- **Frozen boundary objects** — `MarketState` (01), `RegimeContext` (02), `ActiveParamSet`/`ParamSet` (03), `Signal` (04), `SizedOrder` (05), `FillReport` (06), `RiskSnapshot` (07). All `@dataclass(frozen=True)`, validated on construction, deep-immutable (see `SPEC_AUDIT.md` F16).
- **Session boundary** — the `system_config.yaml` `session_boundaries` list of `{zone, at}` local wall times (master §5 / C1; resolved to UTC per date by `core/data/fx_clock.py`, master §3.7 v2.14). Single source of truth for QIEA staging + `MarketState.session`.
- **Stores** (read-shared across the three loops, master §10) — `data_store`, `regime_store`, `param_library` (active + `PendingParamStore`), `portfolio_state`, `risk_store`. Ownership: a store is *written* by exactly one layer and *read* by others; the writer is named in that layer's spec §9/§10.
- **The three loops** — SLOW (QIEA, 03), MEDIUM (NVMA, 02), FAST (Data→Alpha→Governor→Execution, 01/04/05/06). Isolation rules in master §10.
- **Error base** — `DataQualityError` (01) and the per-layer error taxonomy; halts are structured events, never exceptions that escape the loop.

## 5. Cross-cutting invariants every layer spec must restate in its §3 and honour
1. **No LLM / network reasoning / human prompt in the fast loop.** Deterministic Python only (master §0). LLM/orchestrator influence is out-of-band via §12 staged config only.
2. **Downward-only imports**, enforced by the import-linter contract test in `tests/unit/` (must exist before ACIS-02 is built; master §2).
3. **Frozen dataclasses across boundaries; validate on construction; raise `DataQualityError` on bad input** — no silent coercion, no defensive fallback for a state the type excludes (CLAUDE.md).
4. **Structured JSONL logging** `{timestamp, event_type, layer, data, session_id}` for every module; no `print` (master §11).
5. **Guardrail limits, equity floor, HALT/veto semantics are human-only.** No config flag, MCP tool, or test hook may weaken them. There is no force flag (CLAUDE.md).
6. **Postcondition test discipline** — assert observable outcomes, never exit codes alone (master §13).
7. **QIEA staging rule** — never modify live params, never promote mid-session (master §5).

## 6. Correction IDs carried from the audit
Each layer spec has a **Logic Flaw Registry** (§13 of the template) that must address its assigned corrections from `../SPEC_AUDIT.md`:
- `ACIS-01`: F16 (deep-immutable `raw`), F17 (Decimal boundaries), F6/C1 (session tagging vs the boundary list).
- `ACIS-02`: F1 (cadence lock), F18 (session-median estimator/cold-start), C3/F7 (half-life advisory), veto provability.
- `ACIS-03`: C1/C2/F3/F6/F8 (session-boundary def, promotion liveness, staleness observability, never-mid-session).
- `ACIS-04`: C4/F11 (discount-then-discard ordering), conviction 0–1, regime-gating of the four modules.
- `ACIS-05`: C6/F14 + F15 (marginal-alpha normalisation contract, cold-start, size-bucketing), F5.1/F7 (half-life factor decision), cluster caps, hard overrides.
- `ACIS-06`: F10 (slippage auto-throttle decision; drop dark-pool), fragment distribution/jitter bounds, partial-fill/reject handling.
- `ACIS-07`: C5/F13 (alpha-decay baseline validity, NaN-safe Sharpe), F9 (drawdown buffer decision), equity breaker, racing HALTs, restart reconciliation.
- `ACIS-08`: human-token gate, `acis_stage_config` guardrail-path rejection, heartbeat SLAs, safety asymmetry.
- `ACIS-09`: in/out-of-sample discipline, walk-forward, never report in-sample vs §14.

## 7. How to use this set
- **Building a layer:** read the master spec section, then this index row, then the layer's deep spec. Build only into the `[DIR:]` tag. Do not start a layer until the previous phase's tests pass (master §15).
- **Reviewing:** run `../_SPEC_REVIEW_PASS.md` — it walks the master, every `.md`, this set, and the skeleton, and re-verifies every `SPEC_AUDIT.md` OPEN/FIXED item.

## Changelog
- **1.3 (2026-09-11)** — Master v2.14 (GAP-P12D-10): the *session boundary* term is now a list of local `{zone, at}` wall times, not fixed UTC instants. (Header version corrected from a stale 1.0.)
- **1.2** — Master v2.4 registered: new `ACIS-13` (platform adapter contract + attach protocol, master §7.5), TO AUTHOR. Coverage additions to existing docs: `ACIS-01` gains master §3.7 asset-class law (contract metadata, per-calendar session boundaries — C1 generalised, futures lifecycle) and C10; `ACIS-10` gains §3.6 Tier-G taxonomy + shock-asymmetry law (C12, F27); `ACIS-11` gains §5.7 evolution law (lifecycle, re-validation due dates, graveyard/revival, challenger lane, C14); `ACIS-05`/`ACIS-07` gain §9.5 account doctrine (stricter-of, platform-measured drawdown series, C11, F26 + GAP-0010); `ACIS-04`/`ACIS-08` gain §10 per-gate skip attribution (C15); `ACIS-09` gains the nine F31 glitch classes and per-account §14 evaluation.
- **1.1** — Master v2.2 additions registered: ACIS-10 (events/news + platform-rules law), ACIS-11 (strategy provenance + literature law + Pair Divergence detail), ACIS-12 (scenario book + gap law), all TO AUTHOR. ACIS-04 must additionally cover the Pair Divergence module's linked signal groups; ACIS-05 the blackout hard override + atomic group sizing.
- **1.0** — Index created; nine layer specs registered in implementation order with dependency law, shared vocabulary, and audit-correction assignments.
