# ACIS-06 — Execution Orchestrator — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-EXEC-006` |
| **Version** | 1.0 (DRAFT) |
| **Layer / DIR** | Layer 6 · `[DIR:core/execution]` |
| **Consumes** | `SizedOrder` (ACIS-05) |
| **Emits** | `FillReport` (frozen) → Risk Monitor (ACIS-07); order flow → broker/venue |
| **Depends On** | `../ACIS_SPEC.md` §7, §2 · `ACIS-05`, `ACIS-00` |
| **Blocks** | ACIS-07 |
| **Corrections applied** | F10 (slippage auto-throttle — raised to human; dark-pool dropped), fragment/jitter bounds, partial-fill/reject handling |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Fragmentation & routing config · 7. Core logic · 8. State machine · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Given a `SizedOrder`, decide **how and where** to execute — fragment, schedule, route, randomise signature — and report every fill to the Risk Monitor. Execution never decides *how much*.

**IS:** order fragmentation (size + timing); VWAP scheduling for large orders; aggressive IOC for fast-decay signals; venue selection by live quality score; execution-signature randomisation; partial-fill / rejection / reconnect handling; `FillReport` emission.

**IS NOT (hard wall):** it never changes `size_units` (the Governor's decision is final on quantity); it never opens a position the Governor sized to 0; it never overrides a HALT (a HALT reaches it via the Governor sizing to 0 and via a direct execution freeze); it does not compute risk metrics (that is ACIS-07). It has **no** upward data path except `FillReport` → Risk (master §2, S2 "No Upstream Feedback": execution results go only to the Risk Monitor).

**Done-when:** fragmentation distribution + jitter are within the specified bounds (statistical, seeded test); fast-decay signals use IOC; venue routing logs a reason per order; partial fills, rejections, and reconnects are handled without double-submission; every fill emits a `FillReport`; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/execution/orchestrator.py::ExecutionOrchestrator.submit(order: SizedOrder) -> tuple[FillReport, ...]`.

**Inputs:** a `SizedOrder` (size > 0; size == 0 is a no-op that emits nothing); live venue quality scores; broker connectors (reused from ACIS-01's feed layer where applicable, but order entry is a distinct authenticated channel). Config `execution:`. A global execution-freeze flag settable by the Risk Monitor's flatten path.

**Guard:** `size_units == 0` → return `()` (no-op, logged `EXEC_NOOP`); execution-freeze active (post-flatten) → reject new opens, allow only position-closing/managing orders.

## 3. Architecture & responsibility

Units: `orchestrator.py` (submit + lifecycle), `fragmenter.py` (TWAP/VWAP split + signature randomisation), `venue.py` (multi-venue routing + quality score). Single responsibility: **execution mechanics.** Downward-only imports (it is the lowest data-producing layer before Risk); its only output edge is `FillReport` to Risk. FAST loop.

## 4. Output contract — `FillReport` (locked)

```python
@dataclass(frozen=True)
class FillReport:
    fill_id: str
    order_id: str            # → SizedOrder
    fragment_id: str         # which fragment of a fragmented order
    instrument: str
    direction: int
    requested_price: float
    fill_price: float
    filled_units: Decimal    # Decimal (accounting boundary)
    slippage_bps: float      # (fill_price − requested_price)/requested_price ·1e4 ·sign
    fill_time: datetime
    venue: str
    status: FillStatus       # FILLED | PARTIAL | REJECTED | CANCELLED
    remaining_units: Decimal # for PARTIAL
    session_id: str
```

Every fill (including partials and rejections) produces a `FillReport` — the Risk Monitor and portfolio accounting reconstruct positions and PnL from these (Decimal quantities/prices at the accounting boundary, F17). A rejection is a `FillReport` with `status=REJECTED`, not a silent drop.

## 5. Data schemas

- **`FillStatus`** enum as above.
- **`VenueQuality`:** per-instrument rolling `spread`, `fill_rate`, `avg_slippage_bps`, `reject_rate` → a scalar `quality_score`. Updated from `FillReport`s (this layer's own feedback, internal — not upstream to signals).
- **`Fragment`:** `fragment_id`, `parent_order_id`, `units`, `scheduled_at`, `venue`.
- **Config (`execution:`):** `fragment_threshold_lots`, `fragment_size_jitter:[0.85,1.15]`, `fragment_time_jitter_s:[0.5,3.0]`, `min_fragment_lots`, `vwap_threshold`, `vwap_window_min:5`, `fast_decay_seconds:30`, `signature_lot_variance:0.15`, `random_seed` (test-only; production uses a CSPRNG), `slippage_alert_bps:8.0` (mirrors guardrail), optional `slippage_throttle` (see F10, default **off**).

## 6. Fragmentation & routing config

- **Fragmentation:** orders > `fragment_threshold_lots` split into `n` sub-orders each sized `uniform(0.85,1.15) × (total/n)`, renormalised so the fragments sum **exactly** to the total (no size created/destroyed — a critical invariant; the Governor's quantity is preserved to the unit); inter-fragment delay `uniform(0.5s,3.0s)`; no fragment below `min_fragment_lots` (merge dust).
- **VWAP:** orders > `vwap_threshold` scheduled over a rolling `vwap_window_min` (5 min).
- **Fast-decay:** `SizedOrder` whose originating signal had `valid_for_seconds < fast_decay_seconds` (30) → aggressive **IOC** market order, no fragmentation (speed over stealth).
- **Venue routing:** route fragments proportional to live `quality_score`; log the routing reason per order; rotate venue order across fragments (signature randomisation).
- **Signature randomisation:** ±15% lot micro-variance (within the summing invariant), randomised timing, rotated venue order, never identical consecutive patterns. Randomness uses a CSPRNG in production; tests seed it for reproducible distribution checks.

## 7. Core logic (step by step)

1. `submit(order)`; if `size_units == 0` or execution-frozen-for-opens → no-op/guard.
2. Classify: fast-decay → IOC path; else large → VWAP/fragment path; else single order.
3. Build fragments (size + schedule + venue), enforcing the **exact-sum invariant** and `min_fragment_lots`.
4. Dispatch fragments to venues; await fills.
5. **Partial fill:** emit a `PARTIAL` `FillReport` with `remaining_units`; decide per policy whether to re-submit the remainder (bounded retries) or cancel; never exceed the parent total; never double-count (idempotent by `fragment_id`).
6. **Rejection:** emit `REJECTED` `FillReport`; update `VenueQuality`; optionally reroute the remainder to the next-best venue (bounded); a persistent reject → stop, log `EXEC_REJECT_GIVEUP`, do not spin.
7. **Reconnect mid-order:** on broker disconnect, freeze new dispatch; on reconnect, **reconcile open/working orders against the broker (broker is authoritative)** before any new submission — this prevents duplicate fills on restart (glitch class; ties to ACIS-07 restart reconciliation).
8. Emit all `FillReport`s to the Risk Monitor.

**F10 (slippage) — raised, not silently added:** each fill computes `slippage_bps`; if `> slippage_alert_bps (8)` → emit `SLIPPAGE_ALERT` (this is the *alert* the master spec already mandates). An **automatic per-instrument allocation throttle** on repeated slippage breaches is **config-gated and OFF by default** pending human ratification (`SPEC_AUDIT.md` F10) — because an auto-throttle is a sizing/guardrail action owned by the Governor + a human, not something Execution may impose unilaterally. Dark-pool routing from the v1.0 brief is **dropped** (not meaningful in retail forex). Execution *reports* slippage; it does not resize.

## 8. State machine

Order lifecycle: `RECEIVED → FRAGMENTED → DISPATCHING → (PARTIAL ↺) → FILLED | REJECTED | CANCELLED`. Connector: `CONNECTED → DISCONNECTED → RECONCILING → CONNECTED`. During `RECONCILING`, no new opens are dispatched. The execution-freeze (from Risk flatten) transitions the layer to opens-blocked while still allowing position-closing orders (so a flatten can actually close). FAST loop; heartbeats via the loop owner.

## 9. Persistence & logging

`trade_log` (JSONL, master §11): every submission, fragment schedule (with venue + reason), and `FillReport` (`SUBMIT`, `FRAGMENT_PLAN`, `FILL`, `PARTIAL`, `REJECT`, `SLIPPAGE_ALERT`, `EXEC_RECONCILE`, `EXEC_FREEZE`). The fragment plan is logged *before* dispatch so a crash mid-dispatch is reconcilable. Decimal for filled quantities/prices at the accounting boundary.

## 10. Store schema (DDL)

```sql
CREATE TABLE fill_report (
    fill_id       TEXT PRIMARY KEY,
    order_id      TEXT NOT NULL,
    fragment_id   TEXT NOT NULL,
    ts            TIMESTAMPTZ NOT NULL,
    instrument    TEXT NOT NULL,
    direction     SMALLINT NOT NULL,
    requested_px  DOUBLE PRECISION NOT NULL,
    fill_px       DOUBLE PRECISION NOT NULL,
    filled_units  NUMERIC NOT NULL,     -- Decimal
    slippage_bps  DOUBLE PRECISION NOT NULL,
    venue         TEXT NOT NULL,
    status        TEXT NOT NULL,
    remaining_units NUMERIC NOT NULL DEFAULT 0,
    session_id    TEXT NOT NULL
);
CREATE INDEX ON fill_report (order_id);
```
`fill_id`/`fragment_id` PK/uniqueness makes fill ingestion idempotent (reconnect/restart safe — no double count).

## 11. MCP contract

No independent control tools; execution obeys the Governor + Risk. `acis_flatten` (ACIS-08) triggers the flatten path: close all positions then set execution-freeze (opens blocked) + Governor halt. Fill/slippage/venue stats surface on `acis://logs/tail/trade` and `acis://risk/snapshot`. Execution exposes no tool that resizes or resumes.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| `size_units == 0` | no-op, `EXEC_NOOP` |
| partial fill | `PARTIAL` FillReport + bounded remainder policy; never exceed parent total |
| rejection | `REJECTED` FillReport; venue quality update; bounded reroute; giveup logged |
| broker disconnect mid-order | freeze dispatch → reconcile vs broker (authoritative) → resume; no duplicate fills |
| slippage > alert | `SLIPPAGE_ALERT`; auto-throttle only if human-enabled (F10) |
| fragment sum ≠ total | impossible by construction; asserted (would create/destroy size) |
| execution-freeze active | block opens, allow closes |

## 13. Logic-flaw registry
- **C-EXE-1 (fragment invariant):** fragments sum exactly to the parent total; property test over random splits — no unit created or destroyed.
- **C-EXE-2 (distribution bounds):** size jitter ∈ [0.85,1.15], time jitter ∈ [0.5,3.0]s; seeded statistical test asserts the empirical distribution stays in bounds and is not degenerate.
- **C-EXE-3 (F10):** slippage alert always; auto-throttle OFF by default and only en-/disabled via human-ratified config; dark-pool language absent; test asserts no autonomous resize on slippage.
- **C-EXE-4 (partial/reject):** partials and rejects each emit a FillReport and never double-fill; idempotent by fragment_id.
- **C-EXE-5 (reconnect/restart):** post-reconnect reconciliation treats the broker as authoritative before new submits; test simulates disconnect with a working order and asserts no duplicate fill.
- **C-EXE-6 (no resize):** Execution never changes `size_units`; test feeds a SizedOrder and asserts total filled ≤ sized total (and == on full fill).

## 14. Test contract (postcondition-style)

**Unit:** fragmentation of a large order → n fragments summing exactly to total, each ≥ min, jitter in bounds (seeded); fast-decay signal → single IOC, no fragmentation; venue routing picks the higher quality score and logs a reason; signature randomisation → consecutive orders are not identical (statistical); slippage computation sign/magnitude correct; `size_units==0` → no order.

**Integration (with ACIS-05/07):** partial fill then remainder → position reconstructed correctly from FillReports (jointly with portfolio accounting); rejection → REJECTED report + reroute within bounds; broker disconnect mid-position → reconcile, no duplicate (glitch class); flatten command → all positions closed, opens frozen; weekend-gap through a stop → the stop fill is reported at the gap price, not the requested price, with correct slippage (jointly with ACIS-07).

## 15. Integration gate

**What Risk (ACIS-07) consumes:** a stream of `FillReport`s (fills, partials, rejects) from which it maintains `PortfolioState`, PnL, drawdown, and its risk metrics, and against which it evaluates HALT conditions. **Owns conflict-table rows:** none directly (it never sizes), but it *executes* the flatten that a HALT/equity-breaker demands. **Done-when (phase 7, master §15):** §14 green; import contract passing; reconnect/partial/reject/weekend-gap glitch tests present.

## Changelog
- **1.0 (DRAFT)** — From master §7 + `ACIS_Agent_Prompt.md` §3.6 + S2 layer-6 card; F10 slippage auto-throttle deliberately raised-not-applied; fragment exact-sum invariant made explicit; dark-pool dropped for forex.
