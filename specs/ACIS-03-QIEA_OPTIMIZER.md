# ACIS-03 — QIEA Optimizer & Parameter Library — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-QIEA-003` |
| **Version** | 1.3 (LOCKED — master v2.14 local-time boundaries, 2026-09-11) |
| **Layer / DIR** | Layer 3 · `[DIR:core/optimizer]` |
| **Consumes** | `RegimeContext` (ACIS-02) + regime-labelled **historical** data only |
| **Emits** | `ActiveParamSet` (frozen) → AGON (ACIS-04, né Alpha Arena) via `param_library` |
| **Depends On** | `../ACIS_SPEC.md` §5, §10, §2 · `ACIS-02`, `ACIS-00` |
| **Blocks** | ACIS-04 |
| **Corrections applied** | C1 (session-boundary definition), C2 (promotion liveness/staleness), F3 (promotion trigger), F6/F8 · **v1.1:** C8 (net-of-costs fitness), C9 (expectancy gate, exact fn — closes GAP-0006), GAP-0008 (window minimum + holdout OOS), GAP-0025/0033 C1 ruling |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Algorithm & config · 7. Core logic · 8. State machine & staging rule · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Evolve, per regime, the best strategy `ParamSet` using a Quantum-Inspired Evolutionary Algorithm, and maintain a **regime-indexed parameter library** the fast loop reads. The defining constraint is *when* it is allowed to change live behaviour: **never during a session, never with open positions.**

**IS:** quantum-bit chromosome evolution; per-regime fitness evaluation on regime-labelled history, **net of costs (C8)** and gated on **positive net expectancy (C9)** with a chronological held-out split (GAP-0008); staging evolved params to `PendingParamStore`; promotion to `ActiveParamSet` only at a valid session boundary with `open_positions == 0`; staleness observability.

**IS NOT:** it never reads live portfolio state (isolation, master §10 — Loop 1 cannot read live portfolio); it never modifies active params mid-session; it never trades, signals, or sizes; it never overrides NVMA or Risk. Evolution consumes **historical data only** — never the live feed's future. It never optimises on gross (frictionless) returns — forbidden by C8.

**Done-when:** QIEA evolves valid `ParamSet`s per regime; the session-boundary staging rule is enforced (a mid-session promotion attempt **raises**); staged→active promotion happens only when flat at a boundary; a champion that fails the C9 gate on the held-out split is never staged; staleness is observable; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/optimizer/qiea.py::QIEA.evolve(regime: RegimeType, history: RegimeLabelledHistory) -> ParamSet | None` and `param_library.py::ParamLibrary.{stage,promote,get_active,get_pending,has_active,on_boundary}`.

**Inputs:** `RegimeContext.regime` (which regime needs params); regime-labelled historical bars (last `fitness_bars` of the target regime, master §5); config `optimizer:`. **No live inputs.** The clock (session boundary + `open_positions == 0`) is read from the shared state via a read-only guard (see §7) — QIEA does not read positions to *use* them, only to check the flat/boundary gate. All gate-relevant methods take an explicit `now: datetime` (UTC) — no hidden clock reads; deterministic and testable.

**Precondition to run:** `is_session_closed() OR (is_session_boundary() AND open_positions == 0)` (master §5). Otherwise `evolve()` may compute in the background but `promote()` is refused.

## 3. Architecture & responsibility

Five units (lean, each names its spec requirement): `param_types.py` (the §4/§5 frozen boundary dataclasses), `costs.py` (the **C8 shared cost model** — `ACIS-09`'s backtest harness MUST import this same module, which is how "unit-tested identical in both places" is achieved: one module, one pinned-semantics test), `fitness.py` (fitness function + C9 gate), `qiea.py` (evolution), `param_library.py` (active + `PendingParamStore`, staging/promotion). Single responsibility: **offline parameter optimisation + safe staged deployment.** Downward-only: it may read `RegimeContext`/`RegimeType` (from the layer above) and historical stores; it must not import AGON/Governor/Execution/Risk (import allowlist: `optimizer → {regime, data}`). It is the SLOW loop (master §10).

**Determinism scope (recorded honestly):** QIEA is stochastic by construction (observation collapse). It runs in the SLOW loop, outside the fast-loop determinism law. The binding requirement is **reproducibility**: every run's RNG seed is logged in `EVOLUTION_RUN`; identical seed + identical history ⇒ identical champion (property-tested). Stdlib `random.Random(seed)` only — no new dependency (§18 lean-build; phases 1–3 precedent).

**F17 scoping note:** the fitness mini-backtest's PnL quantities are *statistical scores* used for relative ranking, not account accounting — they are float by design. The F17 Decimal boundary applies to live accounting quantities (size, PnL, NAV, equity) and lands with the first real PnL aggregate (phase 9, per TODO ledger). This is a declared scoping, not an omission.

## 4. Output contract

```python
@dataclass(frozen=True)
class ParamSet:
    # entry/exit
    ema_fast: int          # 5..50
    ema_slow: int          # 20..200   (invariant: ema_slow > ema_fast)
    rsi_period: int        # 7..21
    rsi_overbought: float  # 65..80
    rsi_oversold: float    # 20..35    (invariant: rsi_oversold < rsi_overbought)
    atr_multiplier_sl: float  # 1.0..3.5
    atr_multiplier_tp: float  # 1.5..5.0 (invariant: tp_mult > sl_mult)
    momentum_lookback: int    # 5..50
    breakout_atr_threshold: float  # 0.5..2.0
    mean_rev_zscore_entry: float   # 1.5..2.5
    max_holding_periods: int       # 1..48 (loop cycles)
    # identity/validity
    regime: RegimeType
    param_set_id: str      # UUID; referenced by Signal.param_set_id (ACIS-04)
    fitness_score: float
    evolved_at: datetime

@dataclass(frozen=True)
class ActiveParamSet:
    regime: RegimeType
    params: ParamSet
    promoted_at: datetime
    source_pending_id: str
```

`ParamSet` validates every field range **and** the cross-field invariants on construction (raise `DataQualityError` on violation) — an out-of-range gene decoded by QIEA is clamped during decoding, never emitted invalid. `param_set_id` is the audit link the Signal and every downstream log carries, so any trade is traceable to the exact params (and their fitness/evolution time) that produced it.

## 5. Data schemas

- **`Individual`:** observed bits + decoded genes + train fitness. The population state is a vector of **qubit angles** `theta` per bit with `P(observe 1) = sin²(theta)`, initialised at π/4 (unbiased superposition) — genuine angle encoding, stdlib math (v1.2, GAP-0037).
- **`PendingParamStore` entry:** `ParamSet` + `staged_at` + `boundaries_skipped: int` + `pending_id`.
- **Time base (v2.11):** the fitness bar and the AGON signal bar are THE SAME declared unit (`signal_bar_seconds`) — genes are calibrated and spent in one time base (closes the ext-review A4 unit mismatch); phase 7/11 builds `RegimeLabelledHistory` from the same `core/data/bars.py` aggregator.
- **`LabelledBar` / `RegimeLabelledHistory`:** OHLC bars + per-bar `spread` (for C8) tagged with the regime that was active (produced by replaying NVMA over history offline). `evolve()` validates every bar carries the target regime (`DataQualityError` otherwise) and uses the last `fitness_bars` of them.
- **`CostModel` (C8):** per-instrument `commission_per_side` + `slippage_per_side` (price units), declared in `instruments.yaml` under `costs:` — **required for every enabled instrument; missing = fatal at startup** (no silent zero-cost optimisation). Spread cost comes from each bar's own `spread`. Phase 11 calibrates these against OANDA practice-feed spreads (master §13, v2.9).
- **Config (`optimizer:`, all required, schema-gated):** `population_size`, `generations`, `qbit_resolution` (bits per gene), `rotation_angle_rad` (Q-gate), `qiea_cycle_seconds` (4h–24h), `fitness_bars: 500`, `fitness_min_bars` (default 300 — GAP-0008 window minimum), `fitness_min_trades` (default 10), `holdout_fraction` (default 0.20, chronological tail), `holdout_min_trades` (default 5), `expectancy_min_r` (default 0.0, **schema-enforced ≥ 0** — the C9 floor may be raised, never lowered below zero). `session_boundaries` and `param_stall_alert_boundaries: 3` stay top-level in `system_config.yaml` (the shared C1 list).

## 6. Algorithm & config set

**QIEA loop (per regime needing evolution):**
1. Initialise the qubit-angle vector (`theta = π/4` per bit, `P(1) = sin²θ`), seeded RNG (§3 determinism scope).
2. Observe (collapse) each individual to a binary string; decode to a `ParamSet` (fixed-point decode into each gene's range; clamp to range; enforce cross-field invariants by repair, not by emitting invalid).
3. Evaluate fitness on the **training split** of the regime-labelled bars for **this regime only** (never full history — master §5).
4. Apply the rotation gate: turn each `theta` toward the best observed individual's bit by `rotation_angle_rad` (Han–Kim-style **simplified** rotation — comparison is always against the generation best, so the canonical Δθ lookup table reduces to a fixed signed step; angles clamped off saturation so no bit becomes unrecoverable). *(v1.2 honesty note, GAP-0037: v1.1's "canonical Han & Kim" overclaimed — the shipped gate is the reduced best-only form, now with true angle encoding.)*
5. Repeat for `generations`; keep the best `ParamSet`. **The champion must itself have cleared the C9 gate on train** (`fitness > WORST_FITNESS`; otherwise `EVOLUTION_REJECTED_TRAIN`, nothing staged — GAP-0038), then pass the §6.3 holdout gate before it may be staged.

**`param_set_id` (§4 audit link, v1.2 — GAP-0036):** derived deterministically from the param **content** (genes + regime + seed + `evolved_at`, uuid5) — distinct param sets always carry distinct ids, and same seed + same history + same clock reproduces the same id.

**Session boundary (C1, with the GAP-0025/0033 ruling — RESOLVED here, phase 4):** `is_session_boundary(t)` is true iff, for some declared `{zone, at}` in `session_boundaries`, `t`'s local `HH:MM` in `zone` equals `at` — a discrete-instant, minute-granularity match against the declared list, exactly C1's letter (v2.14: local, so the UTC instant follows DST). **Ruling: the declared, human-committed list stays authoritative; deriving boundaries from the session calendars is REJECTED** — C1 names the explicit list as the single source, an explicit list is more auditable than a derivation, and the bidirectional boot cross-check (boundaries ⊆ session edges ∧ every fx session start ∈ boundaries, both fatal — GAP-0033 fix) already makes silent divergence impossible. QIEA consumes **only** `session_boundaries`; it never reads session windows. `is_session_closed()` = outside all sessions (delegates to the phase-1 `MarketCalendar`, import allowed).

### 6.1 Fitness — exact contract (C8 net-of-costs, master §5)

Fitness is computed by a deterministic mini-backtest of the decoded params over the split's bars — **v1 evaluation harness (declared):** the canonical dual-EMA core. Long when EMA(fast) crosses above EMA(slow) with RSI < `rsi_overbought`; short on the mirror cross with RSI > `rsi_oversold`; entry at next bar's open; one position at a time; exit intrabar at ATR-multiple SL/TP (SL checked before TP on the same bar — conservative), else at close after `max_holding_periods` bars; **a position still open at the window end is closed at the final bar's close, net of costs (mark-to-close, v1.2 — GAP-0039: every entered trade is accounted; end-of-window losers cannot silently vanish from the fitness or E_R series).** **Every fill pays C8 costs per side: `half_spread(bar) + commission_per_side + slippage_per_side`.** Genes the v1 harness does not exercise (`momentum_lookback`, `breakout_atr_threshold`, `mean_rev_zscore_entry`) are decoded, validated, and carried but not selected-for until the phase-5 AGON module-specific evaluation — recorded as a KNOWN_GAPS limitation, not hidden.

`fitness = 0.40·mean_sigma_c + 0.20·win_rate + 0.20·pf_c − 0.20·mdd_pen` over closed trades' **net** PnL, components normalised (each ∈ [0,1], unit-tested):
- `mean_sigma_c = clamp01((s + 3) / 6)` where `s = mean(pnl)/std(pnl)` per-trade (std == 0 ⇒ s = ±3 by sign of mean, 0 if mean 0) — monotone in s on [−3, 3]. *(Renamed from `sharpe_c` per the §16 naming law, GAP-0091: it is a per-trade mean/σ transform — no time base, no risk-free rate — and may not wear the canonical name "Sharpe".)*
- `win_rate` = wins / closed trades (natural [0,1]).
- `pf_c = clamp01(PF / 3)`; `PF = gross_win / gross_loss`; `gross_loss == 0` ⇒ 1.0 if `gross_win > 0` else 0.0.
- `mdd_pen = clamp01(max_drawdown / gross_win)` on the cumulative-net-PnL curve (peak-to-trough); `gross_win == 0` ⇒ 1.0.

Range: fitness ∈ [−0.2, 0.8]. **`WORST_FITNESS = −1.0`** — strictly below the formula floor; a gated-out individual can never win (C9's "cannot win evolution" is arithmetic, not procedural). NaN anywhere in a trade series ⇒ `WORST_FITNESS` (never a spuriously high score).

### 6.2 C9 expectancy gate — exact function (closes GAP-0006)

Over the split's closed trades (net of C8 costs): `E = mean(net_pnl_per_trade)` — identically `winRate·avgWin − lossRate·avgLoss` with breakeven trades counted in the denominator. **Normalisation (the GAP-0006 contract): `E_R = E / avgLoss`** (expectancy in R-multiples of the average loss — scale-free, comparable across instruments and regimes). Degenerate cases: no losing trades ∧ `E > 0` ⇒ gate passes (`E_R` reported capped at 10.0 for logs); no losing trades ∧ `E ≤ 0` ⇒ fails; any NaN ⇒ fails.

**The gate (applied to every fitness evaluation):** `closed_trades < fitness_min_trades` ∨ `E_R ≤ expectancy_min_r` ⇒ `WORST_FITNESS`. With `expectancy_min_r = 0.0` this is exactly master C9's binding floor ("E ≤ 0 cannot win"); the config may only tighten it (schema ≥ 0).

### 6.3 Window minimum + held-out OOS (closes GAP-0008 at the optimizer)

- **Window minimum:** fewer than `fitness_min_bars` regime-labelled bars ⇒ no evolution for that regime (`EVOLUTION_INSUFFICIENT_DATA` logged; the regime simply stays param-less ⇒ NVMA holds `tradeable=False` — safe default, no thin fit).
- **Holdout:** the window splits chronologically — train = first `1 − holdout_fraction`, holdout = last `holdout_fraction`. Evolution selects on train only. The champion is then evaluated on the holdout — **indicators warm up on the preceding train bars, but only trades *entered* within the holdout tail count** (no lookahead; no artificial indicator starvation of long-lookback params in a short tail) — and **must pass the C9 gate there with ≥ `holdout_min_trades` closed trades; otherwise it is not staged** (`EVOLUTION_REJECTED_OOS` logged). An in-window overfit that cannot carry positive expectancy forward dies here, not at the phase-11 gate.
- **Cross-regime OOS before live** remains with `ACIS-09` (phase 11 walk-forward, per GAP-0008) — this section is the optimizer-side half.

## 7. Core logic — the staging rule (the heart of this layer)

**Invariant (non-overridable, master §5):** QIEA never mutates an `ActiveParamSet` in place, and never promotes while a session is live or any position is open.

1. **Evolve** (SLOW loop): only when `is_session_closed() OR (is_session_boundary() AND open_positions == 0)`. Evolution may *compute* in the background at other times, but its result goes only to `PendingParamStore` — it can never touch active.
2. **Stage:** `param_library.stage(regime, paramset)` writes to `PendingParamStore` with `staged_at`, `boundaries_skipped=0`. Logs `PARAM_STAGED`.
3. **Promote:** `param_library.promote(now)` runs a guard: `is_session_boundary(now) and open_positions == 0` — **if called otherwise it raises `PromotionForbiddenError`** (this is the testable teeth of the rule, master §13). On success it copies pending→active atomically, logs `PARAM_PROMOTED{regime, pending_id}`, clears the pending entry.
4. **C2 liveness / staleness:** at every session boundary (`on_boundary(now)` sweep), for each pending entry, if `open_positions != 0` → do **not** promote; increment `boundaries_skipped`; log `PARAM_PROMOTION_STALLED{regime, boundaries_skipped, staged_at}`. When `boundaries_skipped ≥ param_stall_alert_boundaries` (default 3) → surface on `acis://params/pending` for orchestrator/human attention. **The system waits — it never force-promotes and position-close is not a trigger (F3).**
5. **Regime with no params:** if NVMA reports a regime for which `param_library.has_active(regime)` is false → NVMA holds `tradeable=False` (ACIS-02, wired via its `has_params_for` callable) until QIEA stages+promotes params for it at the next valid boundary. QIEA does not trade or rush; it evolves offline and waits for the gate.

**Read-only position guard (`PositionGate`):** the flat check reaches positions only through a narrow protocol exposing exactly one method — `open_position_count() -> int`. No sizes, no PnL, no instruments — QIEA still may not *read live portfolio state* for optimisation (isolation); it may only test the flat gate. Enforced by the import contract + a test that the library touches nothing but `open_position_count` on the gate object.

## 8. State machine & staging rule

**Loop 1 SLOW, `qiea_cycle_seconds` ∈ [4h,24h].** Per-regime param lifecycle: `NONE → PENDING(staged) → (skipped×n, stalled) → ACTIVE`. Transitions logged. The only path to `ACTIVE` is `promote()` through the guard. Heartbeat to `acis://status` every ≤60 s (slow-loop SLA still emits liveness; the resource itself is wired at phase 10 — the library exposes the snapshot). QIEA can run genuinely concurrently with trading because it writes only to pending — this is why the three-speed isolation is safe (S2 conflict #02/#03).

## 9. Persistence & logging

Dedicated `optimizer_log` (JSONL, phase-1 envelope): `PARAM_STAGED`, `PARAM_PROMOTED` (logged only after the sweep transaction commits — committed facts only), `PARAM_PROMOTION_STALLED`, `EVOLUTION_RUN{regime, best_fitness, generations, seed, train_bars, holdout_bars}`, `EVOLUTION_INSUFFICIENT_DATA`, `EVOLUTION_REJECTED_TRAIN{regime, generations, seed}` (v1.2, GAP-0038), `EVOLUTION_REJECTED_OOS{regime, holdout_trades, holdout_e_r}`, `PROMOTION_FORBIDDEN` (if the guard fires — indicates a caller bug). Every promoted `ParamSet` persists with its `fitness_score` and `evolved_at` so any live trade's params are auditable.

## 10. Store schema (SQLite, phase-1 store discipline)

```sql
CREATE TABLE param_active (
    regime            TEXT PRIMARY KEY,
    param_set_id      TEXT NOT NULL,
    params            TEXT NOT NULL,      -- JSON
    fitness_score     REAL NOT NULL,
    evolved_at        TEXT NOT NULL,      -- ISO-8601 UTC
    promoted_at       TEXT NOT NULL,
    source_pending_id TEXT NOT NULL       -- audit link back to the staged entry
);
CREATE TABLE param_pending (
    pending_id         TEXT PRIMARY KEY,
    regime             TEXT NOT NULL UNIQUE,   -- one staged set per regime
    params             TEXT NOT NULL,
    fitness_score      REAL NOT NULL,
    staged_at          TEXT NOT NULL,
    boundaries_skipped INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE param_history (   -- append-only audit of every promotion
    param_set_id TEXT NOT NULL, regime TEXT NOT NULL, params TEXT NOT NULL,
    fitness_score REAL NOT NULL, promoted_at TEXT NOT NULL,
    PRIMARY KEY (param_set_id, promoted_at)
);
```
`param_active` is keyed by regime (one active set per regime). **The whole boundary sweep is ONE SQLite transaction** (v1.2, GAP-0036): every pending entry's history-insert + active-upsert + pending-delete commits together or rolls back together — a failure on any entry promotes nothing and strands nothing, and a constraint violation surfaces as `DataQualityError` (taxonomy), never a raw sqlite exception over a partial write. Restart-safe: a `ParamLibrary` re-opened on the same DB resumes pending entries with their counters intact. *(v1.0's JSONB/TIMESTAMPTZ DDL was postgres-flavoured; phase 1 established SQLite-dev — §16 stack.)*

## 11. MCP contract

Read: `acis://params/active` and `acis://params/pending` (incl. `boundaries_skipped` and stall alerts) surfaced by ACIS-08 from `ParamLibrary.{active,pending}_snapshot()`. The MCP `acis_stage_config` tool (ACIS-08) stages *tunable config* through this same session-boundary discipline — it may **not** stage guardrail paths (schema-rejected). QIEA exposes no tool that promotes; promotion is internal + gated, never externally forced.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| `PromotionForbiddenError` | raised if `promote()` called off-boundary or with open positions — this is the safety teeth; caller bug |
| out-of-range decoded gene | clamped/repaired during decode; never emitted invalid |
| cross-field invariant violation | repaired in decode; `ParamSet` construction still validates (defense in depth) |
| zero-trade / thin-sample / NaN / non-positive-expectancy fitness | `WORST_FITNESS` (C9 gate) — never a high score |
| champion fails holdout gate | not staged; `EVOLUTION_REJECTED_OOS`; regime stays param-less (safe) |
| < `fitness_min_bars` labelled bars | no evolution; `EVOLUTION_INSUFFICIENT_DATA` |
| bar regime ≠ target regime | `DataQualityError` (mislabelled history is a caller bug, not repairable) |
| pending stall ≥ threshold | `PARAM_PROMOTION_STALLED` + MCP surfacing; **no** force-promote |
| attempt to read live portfolio | blocked by import contract + `PositionGate` surface test |

## 13. Logic-flaw registry
- **C-QIEA-1 (C1/F6):** session boundary defined solely by `session_boundaries`; a test asserts `promote()` off the list raises even at a "close-looking" time (20:59 vs the 21:00 UTC summer rollover), and that the rollover boundary is 21:00 UTC in July and 22:00 UTC in January.
- **C-QIEA-2 (C2/F8):** staleness observable (`boundaries_skipped`, stall log, MCP surfacing); test: hold a position across N boundaries → pending never promotes, `boundaries_skipped == N`, stall surfaced, safety intact.
- **C-QIEA-3 (F3):** position-close is NOT a promotion trigger — test: close a position mid-session → no promotion occurs.
- **C-QIEA-4 (isolation):** QIEA cannot access live position sizes/PnL — import contract + a test that only `open_position_count` is touched on the gate.
- **C-QIEA-5 (mid-session immutability):** active params are never mutated in place; test asserts the active set is byte-stable across staging a successor + a regime shift (jointly with ACIS-02).
- **C-QIEA-6 (C8):** a param set profitable on mid-prices but losing net of spread+commission+slippage scores `WORST_FITNESS` — the frictionless mirage cannot win. The cost model is one shared module (`costs.py`) with a pinned-semantics unit test; ACIS-09 imports it, never re-implements it.
- **C-QIEA-7 (C9/GAP-0006):** exact `E_R = E/avgLoss` values asserted on hand-computed trade series; `E_R ≤ 0` ⇒ can never win regardless of Sharpe/win-rate (arithmetic: `WORST_FITNESS < formula floor`); a high-win-rate/negative-expectancy series is gated out.
- **C-QIEA-8 (GAP-0008):** train/holdout split is chronological (no shuffle — lookahead is the classic sin); a champion with no holdout trades or failing the holdout C9 gate is never staged.

## 14. Test contract (postcondition-style)

**Unit:** `evolve()` returns a `ParamSet` with all ranges + invariants satisfied; same seed + same history ⇒ identical champion (reproducibility property); decode clamps out-of-range genes and repairs cross-field invariants; fitness monotone in Sharpe (constructed trade series); C8: gross-profitable/net-losing set → `WORST_FITNESS` (C-QIEA-6); C9 exact `E_R` values + gate arithmetic (C-QIEA-7); degenerate fitness (zero trades, < min trades, NaN) maps to `WORST_FITNESS`; component normalisations each ∈ [0,1]; `< fitness_min_bars` ⇒ no evolution + log; holdout rejection: train segment trades, flat holdout segment ⇒ champion rejected, `EVOLUTION_REJECTED_OOS` (C-QIEA-8); mid-session `promote()` → `PromotionForbiddenError` (master §13 explicit; 21:59 close-looking raises); boundary+flat `promote()` → `param_active` updated + `param_history` row + `param_pending` cleared (assert store, not return code); mislabelled bar ⇒ `DataQualityError`.

**Integration:** stage at T, hold an open position across 3 boundaries → 0 promotions, `boundaries_skipped==3`, stall surfaced on the pending snapshot; then flatten at the 4th boundary → exactly one promotion; position-close mid-session between boundaries → no promotion (C-QIEA-3); regime shift to a regime with no active params → NVMA `tradeable=False` until QIEA promotes (wired via `has_params_for`, jointly with ACIS-02); restart mid-pending → pending survives with correct `boundaries_skipped` (transaction/restart safety).

## 15. Integration gate

**What AGON (ACIS-04) consumes:** `ActiveParamSet` via `param_library.get_active(regime)` — a frozen, validated param set keyed by the current regime, carrying `param_set_id` for signal traceability. **Owns conflict-table row:** "QIEA new params ready + open positions → stage, deploy at next session boundary only." **Done-when (phase 4, master §15, paper mode):** all §14 tests green in a full run; import contract passing; no live trading (paper only until phase 12).

## Changelog
- **1.3 (2026-09-11)** — Master v2.14 (GAP-P12D-10): `session_boundaries_utc` → `session_boundaries` (local `{zone, at}` pairs); the boundary match is the local minute in the declared zone. The GAP-0025/0033 ruling is unchanged — the declared list stays authoritative; the cross-check now compares `(zone, local time)` pairs.
- **1.2 (LOCKED, 2026-07-15)** — Phase-4 subordinate-audit triage (GAP-0036..0039, all fixed same-day with regression tests; suite 159 green): **GAP-0036** `param_set_id` now content-derived (uuid5 of genes+regime+seed+evolved_at — §4 traceability genuinely unique) and the promotion boundary sweep is one all-or-nothing transaction surfacing `DataQualityError`, never a partial write; **GAP-0037** genuine qubit-angle encoding (`P(1)=sin²θ`, rotation gate turns θ by `rotation_angle_rad` — dimensionally honest) and the "canonical Han & Kim" claim corrected to the reduced best-only rotation actually shipped; **GAP-0038** champion must clear the C9 gate on TRAIN (`EVOLUTION_REJECTED_TRAIN`) before the holdout gate — an all-gated generation stages nothing; **GAP-0039** mark-to-close at window end — no silent discard of open positions from the fitness/E_R series. Selection tightened or honesty corrected in every case; no guardrail/staging semantics weakened.
- **1.1 (LOCKED, 2026-07-15)** — v2.5–v2.9 consistency pass at phase-4 start (per TODO standing rule): **C8** exact cost-model contract (`costs.py` shared with ACIS-09 as one module; per-instrument `costs:` block required for enabled instruments, fatal if missing; v2.9 OANDA calibration pointer). **C9** exact expectancy normalisation `E_R = E/avgLoss` with `expectancy_min_r ≥ 0` schema floor — **closes GAP-0006**. **GAP-0008** optimizer-side: `fitness_min_bars`, `fitness_min_trades`, chronological holdout with C9 gate on the holdout; cross-regime OOS stays with ACIS-09. **GAP-0025/0033 C1 ruling:** declared list stays authoritative, derivation rejected, QIEA consumes only `session_boundaries_utc`; minute-granularity boundary match defined. v1 fitness evaluation harness declared (dual-EMA core; unexercised genes recorded as a gap for phase 5). AGON rename (v2.8). SQLite DDL (phase-1 store discipline) + one-pending-per-regime UNIQUE. Determinism/seed reproducibility scope + F17 float-score scoping note. Explicit `now` injection; `PositionGate` narrow protocol named. Component normalisations made exact. No guardrail, HALT, veto, or staging semantics changed — every delta tightens selection or records an honest scoping.
- **1.0 (DRAFT)** — From master §5 + `ACIS_Agent_Prompt.md` §3.3 + S2 conflict #02; corrections C-QIEA-1..5 encode the C1/C2/F3/F8 audit fixes as testable guards.
