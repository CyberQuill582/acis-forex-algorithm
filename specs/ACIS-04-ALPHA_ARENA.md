# ACIS-04 — AGON Signal Engine (né Alpha Arena) — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-ALPHA-004` |
| **Version** | 1.5 (LOCKED — master v2.26: the no-trade band is around the TARGET, Carver's code; 2026-10-01) · 1.4 (LOCKED — the R1 audit triage: Carver's no-trade band owned by the Governor, pair families refused while a leg is capped, TSMOM's vote is not the MOP baseline; master v2.22, 2026-09-25) · 1.3 (LOCKED — R-1: the TREND family and forecast netting, master v2.21) |
| **Layer / DIR** | Layer 4 · `[DIR:core/signals]` |
| **Consumes** | `RegimeContext` (ACIS-02) + `ActiveParamSet` (ACIS-03) + `MarketState` + provenance gates (ACIS-11) |
| **Emits** | `Signal` (frozen; linked groups for Pair Divergence) → Capital Governor (ACIS-05) |
| **Depends On** | `../ACIS_SPEC.md` §5.5–5.7, §2, §10 · `ACIS-02`, `ACIS-03`, `ACIS-11`, `ACIS-00` |
| **Blocks** | ACIS-05 |
| **Corrections applied** | C4/F11 (discount-then-discard), conviction 0–1, NaN-guard · **v1.1:** AGON reflex law (v2.8), Pair Divergence (§5.5 v2.2), slow TSMOM required canonical (v2.9), GAP-0009 ruling (owner-ratified 2026-07-15), GAP-0007 budget value, ACIS-11 provenance gate |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Algorithm & config · 7. Core logic · 8. State machine & cadence · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Within the regime NVMA permits and using the params QIEA activated, generate directional `Signal` objects with a conviction score, entry, stop, and target. AGON proposes; it never disposes.

**The reflex law (binding, v2.8):** AGON is a **reflex, not a committee**. Modules fire independently and in parallel; there is no voting, no consensus round, no confidence negotiation, and no deliberation of any kind in the signal path. Conviction is a per-module deterministic formula; conflicts resolve instantly via the fixed §2 table (opposite directions ⇒ discard both); every act/skip decision closes within the §6 decision-latency budget. Deliberation is design-time (§5.6/§12, out-of-band); execution is reflex.

**v1.3 (owner-ratified 2026-09-25, R-1: "i ratify all your recommendations for R1-D1 to D14"; master v2.21 §5.5–5.6, A3 + A7):**
- Rule families emit **forecasts**. Per instrument they are combined with fixed pre-registered weights × FDM (capped at 2.5), capped at ±20, into **one target position**.
- The no-trade buffer is Carver's: a band of ±10% of the average position around the TARGET position (a current position outside it trades to the band's nearest edge), owned by the Governor (v1.4; wording v1.5, master v2.26, GAP-P12D-118).
- A pair family is refused while either leg is capped (GAP-P12D-123).
- Regimes no longer gate families, and the NVMA `tradeable=False` veto is unchanged.
- The v1 required canonical family is **TREND** (master §5.6). §6.6's TSMOM is one registered member of it.
- The forecast/target-position interface (the `Signal` successor, and what the Governor consumes) is specified HERE, as a versioned amendment, before R1.6 builds it (spec first).
- Until then the as-built modules and the §7 pipeline below stand. They are the as-built v2.20 path, not a uniformly stricter one (GAP-P12D-123), and no R1.x phase lands before the rules it assumes.

**IS (as built, legacy until R1.6):** six concurrent, regime-gated strategy modules (Trend Following, Breakout, Mean Reversion, Momentum Scalp, Pair Divergence, Slow TSMOM); per-module deterministic conviction; signal expiry (`valid_for_seconds`); the conviction discount + discard pipeline (C4); linked signal groups for pair legs; the ACIS-11 provenance/entry gate per module.

**IS NOT (hard walls):** it does not know capital, portfolio state, or execution; it cannot size or route; it cannot override the NVMA veto; it never reads the Governor/Execution/Risk layers. A signal generated in a vetoed regime is invalid by definition (master §17) — the layer must not even run its modules when `tradeable=False`.

**Done-when:** each module produces valid `Signal`s in its regime and stays silent outside it; the discount-then-discard order is enforced (C4); expired signals are marked so the Governor drops them; opposite-direction same-instrument signals are discarded (ambiguity = no trade); pair legs always emit as a complete group or not at all; an unregistered or entry-frozen module emits nothing; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/signals/agon.py::AGON` — `observe(state: MarketState)` (maintains per-instrument windows) and `generate(state: MarketState, regime: RegimeContext, params: ActiveParamSet, now: datetime) -> tuple[Signal, ...]`.

**Inputs:** current `MarketState`, current `RegimeContext`, `ActiveParamSet` (from `param_library.get_active(regime.regime)`), config `signals:`, the ACIS-11 `ProvenanceStore` gate, and declared pair relationships from `instruments.yaml`. **Guard:** if `not regime.tradeable` → return `()` immediately (no module runs; `DISCARD_VETOED_REGIME` logged if a module was about to fire). If no active params for the regime → return `()` (defense in depth; NVMA would have vetoed). All clock reads are the explicit `now` parameter.

## 3. Architecture & responsibility

Units: `agon.py` (module orchestration + conflict resolution + budget measurement), `signal_types.py` (`Signal`, `StrategyType`), `indicators.py` (shared TA: reuses the phase-3/phase-4 proven code — ADX from `core.regime.nvma`, EMA/RSI/ATR from `core.optimizer.fitness` (allowed imports: signals → {optimizer, regime}); adds Bollinger bands, rolling correlation, spread z-score, velocity surge — all NaN-safe), `provenance.py` (ACIS-11). Single responsibility: **signal generation.** Downward-only; imports nothing below layer 4. FAST loop (tick–5s).

## 4. Output contract — `Signal` (locked)

```python
class StrategyType(str, Enum):
    TREND = "TREND"; BREAKOUT = "BREAKOUT"; MEAN_REVERSION = "MEAN_REVERSION"
    MOMENTUM_SCALP = "MOMENTUM_SCALP"; PAIR_DIVERGENCE = "PAIR_DIVERGENCE"; TSMOM = "TSMOM"

@dataclass(frozen=True)
class Signal:
    signal_id: str                 # UUID
    instrument: str
    direction: int                 # +1 long | -1 short
    conviction: float              # [0.45, 1] for any EMITTED signal (post-discount)
    entry_price: float
    stop_loss: float
    take_profit: float | None     # None = no target (faithful TSMOM, v1.2/v2.11)
    strategy_type: StrategyType
    regime_at_generation: RegimeType
    param_set_id: str              # links to the ActiveParamSet used (traceability)
    generated_at: datetime
    valid_for_seconds: int
    group_id: str | None = None    # §5.5 linked pair group — both legs share it
```

**Contract rules:** frozen; `direction ∈ {+1,-1}` (never 0); `conviction ∈ [0.45, 1]` for any *emitted* signal; `stop_loss`/`take_profit` on the correct side of `entry_price` for the direction (validated on construction, else `DataQualityError`); prices finite; `generated_at` tz-aware; `param_set_id` present (audit link). `group_id` is set iff `strategy_type == PAIR_DIVERGENCE` — the Governor sizes a group atomically (both legs or neither, §5.5). *(v1.1: `group_id` added — required by the §5.5 linked-group law; the master's Signal field list is extended by exactly this field, recorded here.)*

## 5. Data schemas

- **Module→regime gate table (fixed):**
  | Module | Active regimes | Additional gate | Disabled when |
  |---|---|---|---|
  | Trend Following | STRONG_TREND_*, WEAK_TREND_* | — | LOW-vol ranging (C4) |
  | Breakout | BREAKOUT_IMMINENT, POST_BREAKOUT | — | LOW-vol ranging (C4) |
  | Mean Reversion | RANGING_TIGHT/WIDE, MEAN_REVERTING | — | — |
  | Momentum Scalp | any trend regime | `liquidity_state ∈ {DEEP, NORMAL}` | THIN/ILLIQUID |
  | Pair Divergence | RANGING_TIGHT/WIDE, MEAN_REVERTING | instrument is a declared pair leg; both legs' windows warm | coupling break |
  | Slow TSMOM | **every tradeable regime** (canonical unconditional — the century evidence is regime-blind; the NVMA veto stays sovereign via `tradeable`) | ≥ `tsmom_min_history_days` daily closes | — |
- **Pair relationships (`instruments.yaml`, §5.5):** `pair_relationships:` — each entry declares `legs: [A, B]`, `expected_sign: -1|+1`, `correlation_window: N` and `method: pearson_log_returns` (**a correlation without its declared window+method is a config error**), `stability_floor` (|corr| below it = coupling break), `zscore_window`. Schema-gated, required fields all.
- **Config (`signals:`):** `conviction_discard: 0.45`, `medium_vol_discount: 0.85`, per-module `valid_for_seconds` map, `momentum_scalp_horizon_bars: [5,15]`, `momentum_scalp_bar_seconds: 60` (GAP-0009 ruling), `momentum_scalp_surge_ratio: 1.5`, `fast_loop_decision_budget_ms: 250` (GAP-0007 value), `tsmom_lookback_days: [63, 126, 252]`, `tsmom_min_history_days: 260`, module enable flags. Required.

## 6. Algorithm & config set (the six modules — conviction formulas are exact contracts)

1. **Trend Following** — dual-EMA cross (`ema_fast`/`ema_slow` from params) + RSI filter (long only if RSI < `rsi_overbought`; short only if RSI > `rsi_oversold`). SL/TP = `atr_multiplier_sl`/`atr_multiplier_tp` × ATR(14). **Conviction = clamp01(ADX/50)** — *where "ADX" is the close-only `adx_proxy` (declared deviation, GAP-0072: directionally faithful to Wilder's construction but |Δclose| stands in for the high/low true range; declared in TREND's `declared_deviations`)*.
2. **Breakout** — price-channel break (highest-high/lowest-low over `momentum_lookback`) with the **false-break filter: the mid must *close* beyond the level, not merely wick**, by at least `breakout_atr_threshold × ATR`. SL/TP from ATR multiples. **Conviction = clamp01((break magnitude / ATR) / 2)**.
3. **Mean Reversion** — Bollinger-extreme touch (20-period z) + classic RSI divergence; entry when `|z| ≥ mean_rev_zscore_entry` (params). Direction against the extreme. **Divergence is a gate, magnitude comes from z: conviction = clamp01(|z|/2), emitted only when RSI(params) has moved ≥ 5 RSI points off its 20-window trough (longs) / peak (shorts)** — price holding the extreme while RSI walks away from it is the classic divergence; a low that RSI still confirms (no recovery) is not faded. *(v1.1 note: the earlier `|z|/3 × strength` product was arithmetically unable to clear the 0.45 discard in realistic divergence geometry — RSI near 50 and a fresh 2σ extreme exclude each other; the gate-plus-magnitude form is the classic definition and testable with hand-computed vectors.)*
4. **Momentum Scalp** — tick-velocity surge (`tick_velocity ≥ momentum_scalp_surge_ratio ×` session median velocity) + directional alignment with the short EMA slope; horizon 5–15 bars. **Conviction = clamp01(surge_ratio / 3)**. Only in high-liquidity trend regimes. **GAP-0009 ruling (owner-ratified 2026-07-15, in-chat clearance):** the scalp bar is the **1-minute bar** (`momentum_scalp_bar_seconds: 60`), so the 5–15-bar horizon means **5–15-minute expected duration**. Scalp trades are **excluded from the §14 average-trade-duration metric** (that target was written for the swing modules) and reported as a separate `scalp_avg_duration` beside it — never silently blended. The module gets no expectancy indulgence: it must clear the C9 net-of-costs gate at its own horizon in phase-11 raw evaluation or it is demoted/dropped by the ordinary §5.7 machinery (scalps are the most cost-sensitive strategy — C8 makes that visible, not hidden).
5. **Pair Divergence** (§5.5) — for each declared relationship where this instrument is a leg: rolling correlation over the declared window/method confirms coupling (`|corr| ≥ stability_floor`); spread z-score over `zscore_window` beyond the evolved `mean_rev_zscore_entry` ⇒ **both legs emitted as one linked group** (shared `group_id`): the rich leg faded, the cheap leg bought, per `expected_sign`. Exit signal for the whole group on reconvergence (|z| < 0.5) or coupling break — never one leg alone. **Conviction (both legs) = clamp01(|z|/3) × |corr|**. Groups count once against clusters and net currency delta (Governor side, §6). Active in ranging/mean-reverting regimes on both legs' instruments.
6. **Slow TSMOM** — **v1.3 (R-1 A3): no longer the required canonical module.** It is one registered member of the TREND family (master §5.6). It is NOT the MOP-2012 baseline variant, which is MOP's own 12-month excess-return sign (v1.4, GAP-P12D-116). This vote's spot basis is a declared deviation. Its changes are: exit by target-position change; the §8.6 disaster stop as a broker-side stop; and no harness-only `max_hold`. The "every tradeable regime" row stands. *As built:* (v2.9 required canonical; Moskowitz–Ooi–Pedersen 2012, implemented faithfully-simple, tested raw first per §5.6) — on **daily closes**: trailing simple returns over 63/126/252 trading days; `total = sign(r63) + sign(r126) + sign(r252)`; **direction = sign(total)**, no signal when `total == 0`. **Conviction = agreement/3**, where agreement = the count of horizons whose sign equals the direction (2-of-3 ⇒ 0.667, 3-of-3 ⇒ 1.0; a zero-return horizon counts to neither side — so an emitted TSMOM signal always has ≥ 2 horizons agreeing, since 0.333 dies at the 0.45 discard). A fixed formula, not vote-as-deliberation: the reflex law forbids negotiation, not arithmetic. **Faithful form (v2.11): NO take-profit** — the published expectancy lives in the right tail a target truncates; the ONLY stop is the far disaster stop (`tsmom_disaster_stop_atr` × daily true-range ATR — the §8.6 safety law requires a broker-side stop on every order; a DECLARED deviation); exit = vote flip / re-evaluation. Daily bars aggregate live from ticks (rollover-anchored); `valid_for_seconds` 86400. **§14 duration ruling (GAP-0055, OWNER-RATIFIED 2026-07-16):** TSMOM trades are EXCLUDED from the §14 average-trade-duration metric (that target was written for the intraday/swing modules) and reported separately as `tsmom_avg_duration` beside it — the GAP-0009 pattern, never blended, never silently resolved by a stop. The module gets no expectancy indulgence: C9 net-of-costs at its own multi-month horizon in phase-11 raw evaluation, judged by its declared falsifier. Lookbacks are **canonical constants, not evolved genes** (§5.6 faithful-first; deliberately outside QIEA — no new GAP-0035 surface).

All indicator inputs are NaN-checked; a NaN in any module's computation ⇒ that module emits no signal + logs `SIGNAL_NAN_SKIP` (NaN never reaches conviction).

**Decision-latency budget (GAP-0007, value set here):** `fast_loop_decision_budget_ms = 250`. `generate()` measures wall time; exceeding the budget logs `DECISION_BUDGET_EXCEEDED{elapsed_ms}` and the signals-considered vs emitted **take-rate** is surfaced (via `acis://status`, §10 starvation observability). The budget is observability + tuning, never a guardrail: vetoes, HALTs, and ambiguity=no-trade remain sovereign regardless of elapsed time.

## 7. Core logic — conviction pipeline (C4 order is fixed)

Per evaluation, for each module active in the current regime **and provenance-cleared** (`ProvenanceStore.entry_allowed(strategy_id, now)` — an unregistered module cannot even be constructed, C-PRV-1; a frozen one emits nothing new while its exits stay managed, GAP-0019):
1. Compute the raw signal (direction, entry, SL, TP, raw conviction ∈ [0,1]).
2. **Apply the MEDIUM-volatility discount first:** if `regime.volatility_class == MEDIUM` → `conviction *= 0.85`.
3. **Then the discard threshold:** if `conviction < 0.45` → discard (`DISCARD_SUBTHRESHOLD`). *(Raw 0.50 MEDIUM → 0.425 → discarded; raw 0.55 MEDIUM → 0.4675 → emitted. Order is load-bearing; F11.)*
4. Validate SL/TP sides; construct the frozen `Signal` (+ shared `group_id` for pair legs).
5. **Cross-module conflict (reflex, not debate):** *(v1.3, A7: superseded at R1.6 by forecast netting — master §2 / §5.5; until then this stricter rule stands)* opposite `direction` on the same instrument this evaluation → **discard both** (`DISCARD_OPPOSITE`; ambiguity = no trade, §2 table). Same-direction duplicates → keep the higher conviction. **Pair-group integrity:** if either leg of a group is discarded by any rule, the whole group is discarded (`DISCARD_GROUP_INCOMPLETE`) — a half-group is never emitted.
6. Emit the surviving tuple. AGON does not track whether the Governor acts — no upward feedback (master §8).

**Expiry:** `valid_for_seconds` set at generation; the **Governor** discards expired signals (`generated_at + valid_for_seconds < now`). The producer stays stateless.

## 8. State machine & cadence

FAST loop (tick–5s). Stateless per evaluation except the per-instrument indicator windows maintained by `observe()` (intraday mids/spreads/velocities + daily closes for TSMOM + the GAP-0047 time-aligned joint pair windows — per-BUCKET join: each leg’s completed bar fills its side of the bucket’s slot; the sample appends when both sides are present, and buckets abandoned by a later completion are counted + logged `PAIR_BUCKET_INCOMPLETE`, never silently dropped (GAP-0060/0064 exact algorithm)). Deterministic: same (windows, state, regime, params) ⇒ same signal **content** — direction, conviction, prices, strategy, expiry are all pure functions of the inputs; the only non-derived values are the `signal_id`/`group_id` identifiers (uuid4 — uniqueness, not decisions; GAP-0046 honesty note). No randomness influences any decision in this layer (decision randomness lives only in Execution, ACIS-06).

## 9. Persistence & logging

`signal_log` (JSONL, standard envelope): every emitted `Signal` (full object) and every discard with reason (`DISCARD_SUBTHRESHOLD`, `DISCARD_OPPOSITE`, `DISCARD_GROUP_INCOMPLETE`, `SIGNAL_NAN_SKIP`, `DISCARD_VETOED_REGIME`, `DISCARD_ENTRY_FROZEN`), plus `DECISION_BUDGET_EXCEEDED`. Discards are logged — silent suppression is not allowed; the audit must show why a signal did not become an order.

## 10. Store schema (SQLite, phase-1 store discipline)

```sql
CREATE TABLE signal_log (
    signal_id     TEXT PRIMARY KEY,
    ts            TEXT NOT NULL,
    instrument    TEXT NOT NULL,
    direction     INTEGER NOT NULL,
    conviction    REAL NOT NULL,
    entry_price   REAL NOT NULL,
    stop_loss     REAL NOT NULL,
    take_profit   REAL,                -- NULL = no target (faithful TSMOM, v1.2)
    strategy_type TEXT NOT NULL,
    regime        TEXT NOT NULL,
    param_set_id  TEXT NOT NULL,
    valid_for_s   INTEGER NOT NULL,
    group_id      TEXT,
    outcome       TEXT NOT NULL,   -- emitted | discarded:<reason>
    session_id    TEXT NOT NULL
);
```
Append-only audit; the Governor gets signals in-process. *(v1.0's postgres-flavoured DDL replaced with SQLite per the phase-1 precedent.)*

## 11. MCP contract

No control tools. Signal rate, discard-reason counts, and the §6 take-rate surface via `acis://logs/tail/trade` and `acis://status`; provenance state via `acis://strategies/provenance` (ACIS-11). An LLM can never inject a signal (fast-loop determinism, master §0).

## 12. Error taxonomy

| Event | Handling |
|---|---|
| `not regime.tradeable` | return `()`; no module runs; `DISCARD_VETOED_REGIME` |
| no active params | return `()` (defense in depth) |
| unregistered module id | `DataQualityError` at construction (C-PRV-1) |
| entry-frozen strategy (GAP-0019) | module skipped; `DISCARD_ENTRY_FROZEN` |
| NaN in module compute | module emits nothing; `SIGNAL_NAN_SKIP` |
| SL/TP wrong side / non-finite price | `DataQualityError` on `Signal` construction (module bug); log + drop |
| opposite-direction same instrument | discard both; `DISCARD_OPPOSITE` |
| half of a pair group discarded | discard the group; `DISCARD_GROUP_INCOMPLETE` |
| sub-threshold conviction | discard; `DISCARD_SUBTHRESHOLD` |
| pair relationship without window+method | fatal at config load (schema) |
| budget exceeded | `DECISION_BUDGET_EXCEEDED` log; signals still emitted/discarded normally |

## 13. Logic-flaw registry
- **C-ALP-1 (C4/F11):** discount-then-discard order fixed; explicit vectors: raw 0.50 MEDIUM → discarded (0.425); raw 0.55 MEDIUM → emitted (0.4675).
- **C-ALP-2:** conviction is 0–1 only; a module returning >1 or <0 is a bug caught by the Signal contract + a property test.
- **C-ALP-3 (veto respect):** no signal is ever emitted when `tradeable=False`; owns the producer half of the "NVMA no-trade + high-conviction" conflict row.
- **C-ALP-4 (ambiguity):** opposite same-instrument signals both discarded; owns the "two strategies opposite directions" conflict row. *(v1.4, A7 as corrected: at R1.6 it becomes "a target inside the Governor's no-trade band around the current position places no order"; ambiguity = no trade survives as the band.)*
- **C-ALP-5 (no upward feedback):** AGON reads nothing from Governor/Execution/Risk; import-contract test (`signals → {optimizer, regime}` allowlist).
- **C-ALP-6 (NaN boundary):** NaN never reaches `conviction`; injected-NaN test asserts no emission.
- **C-ALP-7 (group integrity, §5.5):** a pair group emits both legs or neither; a discarded leg kills the group; a coupling break exits the group, never one leg.
- **C-ALP-8 (reflex law, v2.8):** no module reads another module's output; conflict resolution is the only cross-module step and is table-driven; test asserts module isolation structurally (each module is a pure function of (window, state, regime, params)).
- **C-ALP-9 (provenance gate, ACIS-11):** an unregistered module cannot be constructed; a frozen one emits no new entries.
- **C-ALP-10 (GAP-0009):** scalp signals carry the 1-minute-bar horizon semantics; the §14 duration metric exclusion is recorded where the metric is computed (phase 11) — the ruling lives here.

## 14. Test contract (postcondition-style)

**Unit:** each of the six modules emits a valid `Signal` on its regime fixture and emits nothing on a foreign-regime fixture; LOW-vol ranging disables Trend + Breakout entirely; Momentum Scalp silent in THIN/ILLIQUID; TSMOM: 2-of-3 horizons agreeing ⇒ conviction 2/3, all three ⇒ 1.0, split vote ⇒ no signal, < min history ⇒ no signal; Pair Divergence: divergence beyond z ⇒ both legs share `group_id` with correct opposing directions per `expected_sign`, coupling below `stability_floor` ⇒ no entry + group exit while open, reconvergence ⇒ group exit; discount-then-discard boundary vectors (C-ALP-1); SL/TP side validation raises on a wrong-sided construction; opposite-direction discard kills both incl. a pair leg (⇒ whole group dies, C-ALP-7); sub-threshold discard logged; NaN-injection → no emission; unregistered module ⇒ `DataQualityError`; frozen module ⇒ `DISCARD_ENTRY_FROZEN` and zero new signals; budget: an artificially slow module logs `DECISION_BUDGET_EXCEEDED`; determinism property (same inputs ⇒ same signals, run twice).

**Integration (with ACIS-02/03/11):** NVMA veto ⇒ zero signals across the vetoed window; regime shift ⇒ module set switches, params switch only at boundaries (jointly with ACIS-03); provenance demotion mid-stream freezes new entries while a later flat boundary completes removal (jointly with ACIS-11); every emitted signal's `param_set_id` matches the promoted active set end-to-end.

## 15. Integration gate

**What the Governor (ACIS-05) consumes:** a tuple of frozen `Signal`s with conviction ∈ [0.45,1], validated SL/TP, `param_set_id`, `valid_for_seconds`, and group-complete pair legs. The Governor applies expiry, sizing, atomic group sizing, clusters, and hard overrides. **Owns conflict-table rows:** "two strategies opposite directions → discard both"; producer side of "NVMA no-trade → discard signal." **Done-when (phase 5, master §15, paper signals only):** §14 tests green in a full run; import contract passing; ACIS-11 scaffolding live and gating.

## Changelog
- **1.5 (LOCKED, 2026-10-01)** — Master v2.26 (owner-ratified in chat, "Ratify Carver's (Recommended)", GAP-P12D-118): the no-trade band is around the TARGET, as Carver's code builds it; the no-trade condition is unchanged.
- **1.4 (LOCKED, 2026-09-25)** — The R1 dual audit, triaged, owner-ratified 2026-09-25, the R1 audit triage: "Ratify all":
  - Carver's no-trade band around the current position, owned by the Governor (GAP-P12D-118);
  - the FDM capped at 2.5;
  - a pair family is refused while a leg is capped;
  - TSMOM's 3-horizon vote is not the MOP baseline (GAP-P12D-116);
  - "stricter" is corrected to "as-built".
- **1.3 (LOCKED, 2026-09-25)** — Master v2.21 (R-1 A3 + A7, owner-ratified 2026-09-25, R-1: "i ratify all your recommendations for R1-D1 to D14"). The TREND family (EWMAC 16/64, 32/128, 64/256, with breakout and the MOP-12m sign as members) replaces required-canonical TSMOM, and TSMOM stays as a registered member. Families emit forecasts that net into one target position, which supersedes DISCARD_OPPOSITE at R1.6. Regimes stop gating families, and the NVMA veto is unchanged. The interface amendment lands here before R1.6. No guardrail, HALT or veto semantic changes.
- **1.2 (LOCKED, 2026-07-16)** — v2.11 external-referent corrections (owner review; GAP-0054..0057): **time base = BARS** — AGON windows hold completed OHLC bars of `signal_bar_seconds` (60 s, = the GAP-0009 scalp bar) from `core/data/bars.py`; indicator periods mean bars, never ticks; stops/targets use REAL true-range ATR (`indicators.wilder_atr`, period = config `atr_period`); trend conviction's close-only directional score renamed `adx_proxy` (declared deviation); pair statistics resample onto the shared bar clock — one joint sample per bucket both legs barred in (GAP-0047 strong form). **TSMOM made faithful** (§6.6): `Signal.take_profit` Optional and TSMOM emits None; only the far §8.6 disaster stop (`tsmom_disaster_stop_atr`, declared deviation); exit on vote flip; live daily bars aggregate from ticks with `observe_daily_close` as the seeding API; **§14 average-duration ruling RAISED (GAP-0055), never silently resolved by a stop.** `atr_period` + derived window capacities close GAP-0056. Module `declared_deviations` (ACIS-11 v1.1) registration-visible. Suite 283 green.
- **1.1 (LOCKED, 2026-07-15)** — v2.5–v2.9 consistency pass at phase-5 start: renamed **AGON** with the v2.8 reflex law made §1-binding; **Pair Divergence** added as the fifth module (§5.5: declared relationships with mandatory window+method, linked `group_id` emission, group-integrity law C-ALP-7); **Slow TSMOM** added as the sixth, v2.9-required canonical module (63/126/252-day trailing-return agreement formula, canonical constants not evolved genes, regime-blind but veto-subordinate); **GAP-0009 RESOLVED (owner-ratified 2026-07-15):** scalp bar = 1-minute, 5–15-minute horizon, excluded from the §14 avg-duration metric and reported separately, no expectancy indulgence — C9 at its own horizon or demoted; **GAP-0007 value set:** `fast_loop_decision_budget_ms = 250`, measured + logged + take-rate surfaced, never a guardrail; **ACIS-11 provenance gate** wired into §7 (construction requires registration; frozen strategies emit nothing new); `group_id` field added to `Signal` (required by the §5.5 linked-group law — recorded as the one master-schema extension); SQLite DDL per phase-1 precedent; explicit `now` injection. No guardrail, veto, or conflict-table semantics changed.
- **1.0 (DRAFT)** — From master §5.5 + `ACIS_Agent_Prompt.md` §3.4 + S2 layer-4 card; C4/F11 ordering encoded as explicit test vectors.
