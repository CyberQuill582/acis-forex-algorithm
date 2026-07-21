# ACIS-06 — Execution Orchestrator — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-EXEC-006` |
| **Version** | 1.1 (**LOCKED** 2026-07-17, phase-8 start) |
| **Layer / DIR** | Layer 6 · `[DIR:core/execution]` |
| **Consumes** | `SizedOrder` (ACIS-05) |
| **Emits** | `FillReport` (frozen) → Risk Monitor (ACIS-07); order flow → broker/venue |
| **Depends On** | `../ACIS_SPEC.md` §7, §7.5, §2 · `ACIS-05`, `ACIS-00` |
| **Blocks** | ACIS-07 |
| **Corrections applied** | F10 (slippage auto-throttle — raised to human; dark-pool dropped), fragment/jitter bounds, partial-fill/reject handling · v1.1: v2.10(c) dispatch-latency observability value, §7.5 execution-face contract + capability descriptor + conformance + flat-or-decide attach (GAP-0013/GAP-0018), v2.11 VWAP time-base honesty, injectable RNG/clock · v1.2 (phase-12 deployment gate): master §279 server-side-stop capability + placement conformance (`server_side_stops`, `submit_order(stop_loss=)`, `resting_stops()`, `BrokerPosition.stop_loss`) |

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
- **Config (`execution:`):** `fragment_threshold_lots`, `fragment_size_jitter:[0.85,1.15]`, `fragment_time_jitter_s:[0.5,3.0]`, `min_fragment_lots`, `vwap_threshold_lots`, `vwap_window_s:300`, `fast_decay_seconds:30`, `signature_lot_variance:0.15`, `dispatch_budget_ms:100` (v2.10 item c, below), `slippage_alert_bps:8.0` (mirrors guardrail), optional `slippage_throttle` (see F10, default **off**). Required block; schema-fatal if missing.
- **Randomness & time are injected (v1.1):** the orchestrator takes an RNG (`random.Random` seeded in tests; `random.SystemRandom` in production — signature randomisation must not be replayable from logs) and a clock/sleep pair (`now_fn`/`sleep_fn`) so the C-EXE-2 statistical tests are seeded and instant. No wall-clock or module-level RNG inside logic.
- **Dispatch-latency observability (v2.10 item c — the value is set HERE, mirroring GAP-0007):** `dispatch_budget_ms = 100` covers `submit()` entry → every fragment dispatched or scheduled (ACIS-side processing only; venue round-trip is measured separately as `venue_rtt_ms` on each fill log record). Exceeding the budget logs `EXEC_BUDGET_EXCEEDED{elapsed_ms, budget_ms}` and increments a counter surfaced with the §10 loop-health numbers on `acis://status`. **Observability + tuning only — never a guardrail; no veto, HALT, or freeze weakens or waits on it.**

## 6. Fragmentation & routing config

- **Fragmentation:** orders > `fragment_threshold_lots` split into `n` sub-orders each sized `uniform(0.85,1.15) × (total/n)`, renormalised so the fragments sum **exactly** to the total (no size created/destroyed — a critical invariant; the Governor's quantity is preserved to the unit); inter-fragment delay `uniform(0.5s,3.0s)`; no fragment below `min_fragment_lots` (merge dust).
- **VWAP (v2.11 time-base honesty):** orders > `vwap_threshold_lots` are scheduled across a rolling `vwap_window_s` (300 s = 5 signal bars). **Declared deviation from exchange-VWAP semantics:** v1's venue set (retail FX, one venue per account) has no consolidated volume tape, so the schedule is time-sliced across the window, volume-weighted only when the feed supplies per-tick volume (the mock does). No function or log field may call the unweighted form "VWAP" — the path is named `scheduled` with `weighting: "volume" | "time"` recorded per plan (§16 naming law).
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

## 7.5 Execution-face adapter contract (master §7.5 — the CONTRACT is phase 8; platform adapters beyond mock are ACIS-13/phase 12)

- **`ExecutionFace` (ABC in `venue.py`):** `submit_order(fragment) -> FillReport` · `cancel(fragment_id)` · `open_positions() -> tuple[BrokerPosition, ...]` · `account_snapshot() -> BrokerAccount` (equity/balance/margin — read downstream by Risk for reconciliation, never by any layer above). Async; every method idempotent by `fragment_id`/request id.
- **`CapabilityDescriptor` (data, mandatory):** order types (market/limit/stop, IOC), netting-vs-hedging model, partial-close support, min lot / lot step / max order size, symbol map (the §13 suffix problem solved here, once), quote-depth availability, served asset classes, **`server_side_stops` (v1.2, phase-12 gate)**. The orchestrator rejects loudly (`EXEC_CAPABILITY_REJECT`) any order needing a capability the descriptor lacks — never silent emulation.
- **Server-side stop placement (master §279 — "already law"; v1.2 phase-12 deployment gate):** `submit_order(..., stop_loss=None)` places, atomically with the fill, a protective stop **RESTING AT THE VENUE** — position risk stays bounded even if ACIS/the VPS vanishes. `resting_stops() -> {instrument: price}` and `BrokerPosition.stop_loss` expose the broker-held stop so the conformance gate can prove it lives on the server, not in engine memory. A face that declares `server_side_stops=False` MUST reject a stop-bearing order (never accept it unprotected); such a face is not live-attachable. (The in-loop wiring that threads each `SizedOrder.stop_loss` through the orchestrator to this parameter lands with the phase-12 three-loop runtime; phase 8 established the contract, phase 12 asserts placement per adapter.)
- **GAP-0013 split (structural):** the feed face (ACIS-01 `feeds.py`) exposes no account/position surface; the execution face exposes them only downward to Risk. A shared session object carries transport+auth only. The conformance suite asserts both structurally.
- **Conformance suite (release gate per adapter):** one shared `tests/integration` suite every adapter must pass — round-trip lifecycle, partial fill, reject, cancel, reconnect-mid-order reconciliation (broker authoritative), idempotent duplicate-submit, symbol-map completeness for the enabled universe, capability-descriptor honesty (a declared capability must work; an undeclared one must be rejected), **server-side-stop placement (§279: the stop rests at the venue, is exposed by `resting_stops()`/`BrokerPosition.stop_loss`, retires when flat, and a non-supporting face refuses a stop-bearing order — `test_server_side_stop_*`)**. **v1: the mock adapter passes conformance in phase 8; the §279 stop-placement assertions were added at the phase-12 deployment gate.** OANDA/MT5 faces run the same suite at phase 12 attach (ACIS-13).
- **Attach protocol incl. flat-or-decide (GAP-0018):** select adapter → verify symbol map/contract metadata vs `instruments.yaml` → load rulebook (missing = fatal) → **if the account holds open positions, attach HALTS and requires an explicit human decision (flatten via platform, or manage manually until flat)** → start paper-always. Paper mode never gains a real-order path.

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

**What Risk (ACIS-07) consumes:** a stream of `FillReport`s (fills, partials, rejects) from which it maintains `PortfolioState`, PnL, drawdown, and its risk metrics, and against which it evaluates HALT conditions. **Owns conflict-table rows:** none directly (it never sizes), but it *executes* the flatten that a HALT/equity-breaker demands. **Done-when (phase 8, master §15):** §14 green; import contract passing; reconnect/partial/reject glitch tests present (the weekend-gap-through-stop joint test lands with ACIS-07's accounting at phase 9); mock adapter conformant.

## Changelog
- **1.1 (LOCKED, 2026-07-17 — phase-8 start consistency update)** — v2.10 item (c) applied: `dispatch_budget_ms = 100` set as the execution-layer latency observability value (GAP-0007 pattern — measured, logged `EXEC_BUDGET_EXCEEDED`, surfaced, never a guardrail; venue RTT observed separately). Master §7.5 execution-side contract concretised for phase 8 (new §7.5): `ExecutionFace` ABC, mandatory `CapabilityDescriptor` with loud `EXEC_CAPABILITY_REJECT`, GAP-0013 transport-only session split restated structurally, per-adapter conformance suite as the release gate (mock conformant in phase 8; platform adapters are ACIS-13/phase 12), flat-or-decide attach (GAP-0018). v2.11 time-base honesty: the "VWAP" path renamed `scheduled` with declared `weighting` (no consolidated volume tape in v1 retail FX — §16 naming law). RNG (`SystemRandom` prod / seeded tests) and clock/sleep made injected dependencies. Config keys normalised (`vwap_threshold_lots`, `vwap_window_s`), block schema-fatal if missing. Done-when moved to the renumbered phase 8; weekend-gap joint test explicitly deferred to phase 9 with ACIS-07. No guardrail, HALT, veto, or sizing semantics changed.
- **1.0 (DRAFT)** — From master §7 + `ACIS_Agent_Prompt.md` §3.6 + S2 layer-6 card; F10 slippage auto-throttle deliberately raised-not-applied; fragment exact-sum invariant made explicit; dark-pool dropped for forex.
