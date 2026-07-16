# ACIS — Spec Authoring Guide (for a future session)

> **STATUS UPDATE (2026-07-05):** the deep per-layer spec set described below **has now been authored** — see `specs/ACIS-00-INDEX.md` and `specs/ACIS-01…09` (all DRAFT). The master `ACIS_SPEC.md` is at **v2.1** with cross-source corrections C1–C7 applied (`SPEC_AUDIT.md`). This guide is retained as the **authoring template/record**. If you are the next session, you most likely want the **verification pass** in `_SPEC_REVIEW_PASS.md`, not a rewrite. Only author fresh specs here for a *new* layer added via a master-spec edit.

**Read this, then STOP. Do not rewrite the existing specs.** This guide tells how the ACIS deep specs were brought to depth (template in §6). Work **only** on ACIS — do not touch AXIS, Skopos, or Phronesis (keep the four un-muddled).

---

## 1. What ACIS is
The **Adaptive Capital Intelligence System** — a production-grade, deterministic (no-LLM-in-execution-path) autonomous forex engine: QIEA optimizer + NVMA regime engine + Alpha Arena signals + Capital Governor + Execution Orchestrator + Risk Monitor, over a 7-layer downward-only architecture with an MCP monitoring plane.

## 2. Depth target (the benchmark)
Match the Drive AXIS phase docs (ACIS has no per-phase docx of its own, so the AXIS docx are the **format/depth template**): **~9,000–10,000 words per document, ~15 binding sections**, full DDL, complete dataclasses, state tables, error taxonomy, Logic Flaw Registry (C1…Cn), Test Contract, Integration Gate. One deep doc **per layer**, not one big file.

## 3. Refine vs. rewrite — the decision
- **Refine** `acis/ACIS_SPEC.md` into the **master index / constitution** (it already fixes the layer law, guardrails, `[DIR]` tags, targets). Keep it as top-level authority.
- **Write fresh** a deep spec **per layer/module** (SPEC §1 `core/*` + monitoring), each expanding the corresponding section of `ACIS_Agent_Prompt.md` to benchmark depth (that md already carries dataclasses, fitness functions, guardrail YAML, conflict tables — mine them, don't re-derive).

## 4. Reference material
Content source (rich — primary):
- **ACIS_Agent_Prompt.md** — id `1L6pYHwav7pyXGrk6LEXaLL-sRrcYpgdo` (the 27KB master build prompt: layers, dataclasses, fitness fn, guardrail limits, conflict-resolution table, instrument universe, perf targets)
- Super_Forex_Agent.html — id `1I3gh3Sn39pWtHQXK1LgYRDyaIWhhncOa`
- Master doc: "System Engineering Specs & Architecture: Phronesis, AXIS, ACIS" `1ExKEKYcVRXJJ9qP1ETrrlrpNayX81Lsfrs4RwKXoxa4`
Format/depth template (structure only): the AXIS phase docx set — Phase0 `186FPjDZ0UbYMwL9wN79BPVdCn__qCI9K` (and Phase1–6, see the AXIS guide for the full id list).
Local authority already written: `acis/ACIS_SPEC.md`, `acis/CLAUDE.md`, `acis/KNOWN_GAPS.md`.

## 5. The document set to produce (one deep spec per layer)
`acis/specs/ACIS-<LAYER>_Specification.md`, in the SPEC §15 implementation order:
1. Data Ingestion & Normalisation (`core/data`) — MarketState factory, feeds, TimescaleDB writer
2. NVMA Regime Engine (`core/regime`) — 12 regimes, veto rules, RegimeContext
3. QIEA Optimizer (`core/optimizer`) — chromosome, ParamSet, fitness, session-boundary staging
4. Alpha Arena (`core/signals`) — 4 strategy modules, Signal, conviction scoring
5. Capital Governor (`core/governor`) — sizing formula, marginal-alpha, correlation clusters, hard overrides
6. Execution Orchestrator (`core/execution`) — fragmentation, VWAP, venue routing, signature randomisation
7. Risk Monitor (`core/risk`) — RiskSnapshot, HALT conditions, equity breaker, alpha-decay
8. Monitoring / MCP plane (`monitoring`) — resources, tools, control-plane
9. Backtesting harness & §14 performance validation (`tests/backtest`)
Each metadata header: Document ID (e.g. `ACIS-SPEC-GOVERNOR-001`), Depends On, Blocks (respect the downward-only layer law — a layer spec depends only on the layer above).

## 6. Mandatory per-document template (copy this structure)
Metadata table (Document ID · Version · Status · Depends On · Blocks · Corrections Applied) → Table of Contents → binding sections:
1. Executive Purpose & Scope (IS / IS NOT / Done-when)
2. Boot/Entry Contract & the layer's inputs (which upstream object it consumes)
3. Layer Architecture & responsibility (single responsibility; what it must NOT do)
4. Output Contract (the exact frozen dataclass it emits — locked first)
5. Complete Data Schemas (every field, type, range/units)
6. Algorithm/Config Set — formulas, thresholds, YAML config with defaults
7. Core Logic — classification/sizing/execution/etc., step by step
8. State Machine & loop cadence (which of the 3 speed loops; transitions)
9. Persistence / logging (JSONL streams, TimescaleDB tables)
10. Store/DB Schema — all tables & DDL
11. Interface/MCP Contract — resources, tools, prompts consumed/exposed
12. Error Taxonomy (incl. DataQualityError, halts)
13. Logic Flaw Registry — corrections C1…Cn (guard against the SPEC §17 non-goals)
14. Test Contract — unit + integration + the non-obvious glitch classes (clock skew, DST, out-of-order ticks, NaN, float drift, partial fills, reconnect, weekend gap, racing HALTs, restart reconciliation) — postcondition-style
15. Integration Gate — what the next layer consumes; done-when + conflict-table rows this layer owns
+ Changelog.

## 7. Rules (binding)
- No LLM in the execution path — the specs must make that structurally impossible (SPEC §0).
- Guardrail limits, equity floor, HALT/veto semantics are human-only; never a config flag or "temporary" hook.
- Obey `acis/CLAUDE.md` and `ACIS_SPEC.md`. Anti-overengineering, postcondition gates, never present in-sample numbers against §14 targets.
- No project code. Write nothing until the human says go. Stay in ACIS only. Log gaps to `acis/KNOWN_GAPS.md`.
