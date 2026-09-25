# ACIS-02 — NVMA Regime Engine — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-REGIME-002` |
| **Version** | 1.4 (LOCKED, 2026-09-25 — master v2.21/v2.22: the no-params trigger is replaced by "no registered, validated rule set", and regimes no longer gate families) · 1.3 (LOCKED, 2026-07-17 — v2.12 Hurst correction) |
| **Layer / DIR** | Layer 2 · `[DIR:core/regime]` · **the sovereign gatekeeper** |
| **Consumes** | `MarketState` (ACIS-01) + `session_median_cache` |
| **Emits** | `RegimeContext` (frozen) → QIEA (ACIS-03) & AGON (ACIS-04) via `regime_store` |
| **Depends On** | `../ACIS_SPEC.md` §4, §10, §2 (conflict priority #2) · `ACIS-01`, `ACIS-00` |
| **Blocks** | ACIS-03, ACIS-04 |
| **Corrections applied** | F1 (cadence lock), F18 (session-median estimator + cold-start), C3/F7 (half-life advisory), veto provability |


> **v1.2 honesty note (v2.11 naming law, GAP-0062):** every "ATR"/"ADX" in this document denotes the regime layer’s DECLARED tick-window proxies — `mean_abs_delta` (mean |Δmid| over the trailing window; not Wilder’s true-range ATR) and `adx_proxy` (close-only directional index). The thresholds in `regime:` config were empirically tuned against THESE proxies (phase 3) and are self-consistent; nothing outside the regime layer may treat them as the canonical indicators. Real true-range ATR lives on bars (core/data/bars.py + indicators.wilder_atr, v2.11).

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract · 5. Data schemas · 6. Algorithm & config · 7. Core logic · 8. State machine & cadence · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Read `MarketState` and decide *what kind of market this is* and *whether it may be traded at all*. NVMA is the **sovereign gatekeeper**: its `tradeable` flag is conflict-priority #2 (master §2), below only the Risk Monitor HALT. Nothing below NVMA can manufacture a trade in a regime NVMA has vetoed.

**IS:** classify into exactly one of 12 regimes; compute volatility class, liquidity state, trend direction, stability score, estimated half-life, and confidence; apply the veto rules; detect regime shifts and notify the param library; write `RegimeContext` to `regime_store`.

**IS NOT:** it does not generate signals, size, execute, or optimise; it does not trigger execution (master §10 isolation); it does not import any lower layer. It never mutates `MarketState`. Classification is deterministic — no LLM, no learned model at runtime beyond the fixed statistical rules in §6 (a learned classifier, if ever introduced, is trained offline and shipped as fixed weights via the QIEA-style staged path, never trained in the loop).

**Done-when:** all 12 regimes are classifiable from synthetic fixtures; every veto rule is individually provable; regime-shift handling notifies the param library and sets `tradeable=False` when no evolved params exist for the new regime; cadence + cold-start behave per §6/§8; §14 tests pass.

## 2. Entry contract

**Entry point:** `core/regime/nvma.py::NVMA.classify(state: MarketState, history: RegimeInputWindow) -> RegimeContext`.

**Inputs:** the latest `MarketState`; a rolling price/spread/volume window (`RegimeInputWindow`, length ≥ 200 bars to satisfy ATR-200 and Hurst-200); the `session_median_cache` from ACIS-01 (F18). Config from `system_config.yaml → regime:`. NVMA reads only the data path — never portfolio, signal, or optimizer state.

**Preconditions:** window has enough bars for the longest indicator (200) — until then NVMA returns `UNCLASSIFIED` (`tradeable=False`), never a guessed regime (cold-start safety, F18).

## 3. Architecture & responsibility

Three units (master §1): `nvma.py` (classifier + veto), `regime_types.py` (enums + `RegimeContext` + `RegimeType`), `stability.py` (stability score + half-life estimator). Single responsibility: **classification + veto**. It writes only to `regime_store`; it emits no commands. Downward-only imports enforced by the contract test.

## 4. Output contract — `RegimeContext` (locked)

```python
@dataclass(frozen=True)
class RegimeContext:
    regime: RegimeType
    trend_direction: int              # -1 | 0 | +1
    volatility_class: VolClass        # LOW | MEDIUM | HIGH | EXTREME
    liquidity_state: LiqState         # DEEP | NORMAL | THIN | ILLIQUID
    tradeable: bool                   # master veto flag (priority #2)
    regime_stability_score: float     # 0..1
    estimated_half_life_seconds: int  # advisory (C3) — logged/exposed, not a sizing factor
    confidence: float                 # 0..1
    timestamp: datetime
    instrument: str
    inputs_snapshot: Mapping          # the indicator values that produced this classification (audit)
```

`RegimeType` (12): `STRONG_TREND_UP`, `STRONG_TREND_DOWN`, `WEAK_TREND_UP`, `WEAK_TREND_DOWN`, `RANGING_TIGHT`, `RANGING_WIDE`, `BREAKOUT_IMMINENT`, `POST_BREAKOUT`, `MEAN_REVERTING`, `MACRO_EVENT`†, `ILLIQUID`†, `UNCLASSIFIED`† (†always `tradeable=False`). `inputs_snapshot` makes every classification auditable/reproducible — required, not optional.

## 5. Data schemas

- **`RegimeInputWindow`:** rolling arrays of `mid`, `spread`, `volume`, `tick_velocity`, `timestamp`, per instrument, length = `max_indicator_lookback` (≥200). Backed by a ring buffer; NaN-free (guaranteed by ACIS-01).
- **Enums:** `VolClass`, `LiqState` as above. `trend_direction` ∈ {-1,0,+1}.
- **Config (`regime:`):** `cycle_seconds` (60–300, F1), `atr_periods:[14,50,200]`, `adx_period:14`, `adx_strong`, `adx_weak`, `bb_window:100`, `hurst_window:200`, `hurst_meanrev:0.35` (re-derived v2.12; `hurst_trend` DELETED — see §6), `confidence_veto:0.55`, `spread_veto_mult:3.0`, `velocity_veto_mult:0.5`, `macro_lookahead_min:30` (shared with data), `session_median_window`, `session_median_min_samples`. All required.

## 6. Algorithm & config set

**Classification inputs (master §4):**
- Volatility class ← ATR(14)/ATR(50)/ATR(200) ratios: expanding short/long ratio ⇒ higher class; thresholds config-driven; `EXTREME` above the top band.
- Trend strength ← ADX(14): ≥ `adx_strong` ⇒ STRONG, between weak/strong ⇒ WEAK, < `adx_weak` ⇒ not-trending. Direction ← sign of DI+ − DI− (or EMA slope).
- Ranging ← Bollinger-band width percentile over `bb_window`: low percentile + low ADX ⇒ `RANGING_TIGHT`; high width + low ADX ⇒ `RANGING_WIDE`.
- Anti-persistence ← Hurst(200), Anis–Lloyd-corrected multi-window R/S (v2.12 repair): **H < 0.35 gates MEAN_REVERTING — its ONLY role.** R/S Hurst is drift-invariant (a trend and a random walk read identically), so it carries no trend meaning; ADX alone carries trend strength and trend confidence. Threshold re-derived against the repaired estimator at window 201: random-walk false-positive 7.5%, OU κ≥0.2 detection 95–100% (probe recorded in the v2.12 pass).
- Breakout ← BB squeeze release / channel proximity ⇒ `BREAKOUT_IMMINENT`; confirmed break + elevated vol ⇒ `POST_BREAKOUT`.
- `MACRO_EVENT` ← `macro_events_imminent` (from `MarketState`) OR a §3.6 Tier-G shock flag on the instrument (master v2.4+: a headline can only ever make ACIS more conservative — the shock feeds classification as MACRO_EVENT, never a direction).
- `ILLIQUID` ← spread deviation > `spread_illiquid_sigma` × σ(window spreads) above the **session median** (master §4 — one baseline, shared with the veto rules; a window-median centre would self-track a widening spread and mask sustained illiquidity — GAP-0028), `session == "closed"` (the market is not open — ACIS-01 §4), and exchange halt / limit-lock states (master §3.7). Dead tick-velocity is a **veto** (master §4), not an ILLIQUID classification.

**Veto rules (`tradeable=False`) — each individually testable (master §4):** regime ∈ {MACRO_EVENT, ILLIQUID, UNCLASSIFIED}; OR `confidence < confidence_veto` (0.55); OR `spread > spread_veto_mult × session_median_spread`; OR `tick_velocity < velocity_veto_mult × session_median_velocity` (dead market); OR `MarketState.is_stale`. Vetoes are **OR-combined** — any one forces `tradeable=False`. The veto is a structural gate, not advice (master §2; S2 guardrail card).

**Session-median estimator (F18):** median spread and median tick-velocity over a rolling `session_median_window` *within the current session*, requiring ≥ `session_median_min_samples`. Below the minimum (session cold-start): the median-dependent vetoes cannot be evaluated → NVMA returns `tradeable=False` with `regime=UNCLASSIFIED` and `confidence` reflecting warm-up, until enough samples exist. It never uses a fabricated median.

**Stability score & half-life (`stability.py`):** `regime_stability_score` = fraction of the last `stability_window` classifications equal to the current regime (0..1), optionally weighted by confidence. `estimated_half_life_seconds` = expected dwell time of the current regime, estimated from historical transition rates (exponential-dwell MLE over labelled history). **C3:** half-life is advisory — logged + exposed on `acis://regime/current`, consumed by no sizing formula.

**Confidence:** a bounded aggregate of indicator agreement (ADX-derived for the trend regimes — Hurst contributes NO trend term, v2.12; Hurst-distance + ADX-absence for MEAN_REVERTING; BB-based for the ranging/breakout family); 0..1; low agreement ⇒ low confidence ⇒ veto.

## 7. Core logic (step by step)

1. On each medium-loop tick, pull the latest `MarketState` + window.
2. If window not full (< 200 bars) or session-median not warm → emit `UNCLASSIFIED`, `tradeable=False`, log `REGIME_WARMING`. Return.
3. Compute indicators (ATR ratios, ADX, BB width pct, Hurst) — all NaN-checked; a NaN indicator ⇒ `UNCLASSIFIED` + veto + `INDICATOR_NAN` log (never leak NaN downstream, glitch class; this is where NaN would otherwise reach conviction in ACIS-04).
4. Resolve the single regime via the precedence: MACRO_EVENT > ILLIQUID > (trend/range/breakout/mean-revert by indicators) > UNCLASSIFIED. Exactly one regime; ties broken deterministically by the fixed precedence (ambiguity never yields two regimes).
5. Compute stability, half-life, confidence.
6. Apply veto rules (OR). Set `tradeable`.
7. Build `RegimeContext` (with `inputs_snapshot`), write to `regime_store` (last-writer per instrument).
8. **Shift handling:** if `regime != previous_regime` for the instrument → log `REGIME_SHIFT{from,to,inputs}`; notify `param_library` to load matching `ActiveParamSet`; **if none exists for the new regime → force `tradeable=False` until QIEA evolution completes** (master §4, conflict-table row). *(v1.4, master v2.21/v2.22: once QIEA retires, this trigger is REPLACED by the master §2 row "instrument has no registered, validated rule set → `tradeable=False`", evaluated per instrument, not per regime. Every organic veto trigger stays unchanged.)* The shift never swaps params for *open positions* — that is QIEA's session-boundary rule (ACIS-03); NVMA only gates new entries.

## 8. State machine & cadence

**Loop 2 MEDIUM, `cycle_seconds` ∈ [60,300] (F1).** Per-instrument regime state: `WARMING → CLASSIFIED(tradeable) → CLASSIFIED(vetoed) → …`, with `REGIME_SHIFT` transitions logged. Heartbeat to `acis://status` every ≤60 s (medium-loop SLA, master §12); a stalled medium loop is a reportable health event. NVMA cannot trigger execution (isolation). **Determinism scope (GAP-0032):** the regime label, `trend_direction`, `volatility_class`, `liquidity_state`, `confidence`, `tradeable`, and `inputs_snapshot` are pure functions of (state, window, config) — same inputs ⇒ same values, testable on one classifier called twice. `regime_stability_score` and `estimated_half_life_seconds` are **declared historical aggregates** over the classifier's recorded *classifiable* history (gate-states — UNCLASSIFIED/MACRO_EVENT/ILLIQUID — are never recorded, GAP-0031): path-dependent by design, and documented as such rather than pretended pure.

## 9. Persistence & logging

`regime_log` (JSONL, master §11): every classification (or every shift + periodic heartbeat classification, per `regime.log_mode` to bound volume) with the standard envelope + `inputs_snapshot`. Events: `REGIME_SHIFT`, `REGIME_WARMING`, `INDICATOR_NAN`, `VETO_APPLIED{reason}`. `regime_store` (in-memory + persisted table §10) holds the current `RegimeContext` per instrument for the fast loop to read.

## 10. Store schema (DDL)

```sql
CREATE TABLE regime_context (
    ts             TIMESTAMPTZ NOT NULL,
    instrument     TEXT NOT NULL,
    regime         TEXT NOT NULL,
    trend_direction SMALLINT NOT NULL,
    volatility_class TEXT NOT NULL,
    liquidity_state  TEXT NOT NULL,
    tradeable      BOOLEAN NOT NULL,
    stability_score DOUBLE PRECISION NOT NULL,
    half_life_s    INTEGER NOT NULL,
    confidence     DOUBLE PRECISION NOT NULL,
    inputs         JSONB NOT NULL,
    session_id     TEXT NOT NULL,
    PRIMARY KEY (instrument, ts)
);
SELECT create_hypertable('regime_context','ts', chunk_time_interval => INTERVAL '1 day');
```
The fast loop reads current regime from the in-memory `regime_store`; the table is the audit/replay copy.

## 11. MCP contract

Exposes no control tools. Surfaces (via ACIS-08) `acis://regime/current` (latest `RegimeContext` per instrument, incl. advisory half-life) and shift/veto events on `acis://logs/tail/regime`. Consumes nothing controllable.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| window not full / median cold | `UNCLASSIFIED` + veto + `REGIME_WARMING` |
| NaN indicator | `UNCLASSIFIED` + veto + `INDICATOR_NAN` |
| ambiguous regime | deterministic precedence resolves to one; never two |
| `regime_store` write failure | retry/log `SYSTEM`; keep last good context (fail-safe = stale-but-vetoed via `is_stale`) |
| macro calendar unavailable | treat window as potentially MACRO_EVENT? No — missing calendar = config/feed error, logged; do **not** silently assume no event; conservative veto if calendar staleness exceeds tolerance |

## 13. Logic-flaw registry
- **C-REG-1 (F1):** cadence bound to `cycle_seconds` ∈ [60,300]; test rejects out-of-range config at boot.
- **C-REG-2 (F18):** session-median estimator with `session_median_min_samples`; cold-start ⇒ veto, never fabricated median; tested at session open.
- **C-REG-3 (C3/F7):** half-life advisory only; a test asserts no downstream sizing path reads it (Governor spec ACIS-05 mirrors this).
- **C-REG-4 (NaN leakage):** any NaN indicator vetoes and logs; a test injects NaN and asserts no `RegimeContext` with `tradeable=True` is emitted and no NaN reaches `regime_store`.
- **C-REG-5 (determinism, scoped per GAP-0032):** identical (state,window) ⇒ identical *pure fields* (label, direction, classes, confidence, tradeable, snapshot) on the same classifier; stability/half-life are declared historical aggregates over classifiable labels only (GAP-0031); property test asserts both halves.
- **C-REG-6 (shift/params):** regime shift with no params for the new regime ⇒ `tradeable=False`; owns conflict-table row "regime shift + no evolved params". *(v1.4: that row is now "no registered, validated rule set" (master v2.21 A4). This invariant holds for the legacy QIEA path until it retires, then becomes the per-instrument check.)*

## 14. Test contract (postcondition-style)

**Unit:** synthetic fixture generator per regime (12) → NVMA returns that regime (assert the enum + `inputs_snapshot`); each veto rule has a fixture that flips `tradeable=False` and one that leaves it True (individually provable, master §13); confidence-veto boundary at exactly 0.55; spread-veto at exactly `3× median`; velocity-veto at exactly `0.5× median`; stale `MarketState` ⇒ veto; NaN indicator ⇒ `UNCLASSIFIED`+veto; cold-start window ⇒ `UNCLASSIFIED`; determinism property test.

**Integration:** stream that crosses a regime boundary → exactly one `REGIME_SHIFT`, param-library notified, and if no params ⇒ `tradeable=False` (assert zero signals reach the Governor in that window — cross-checked in ACIS-04/05 integration); mid-session shift with open positions ⇒ NVMA gates new entries but does **not** cause a param swap (that invariant is owned by ACIS-03, tested jointly); DST/session-open cold-start ⇒ veto then classify once warm.

## 15. Integration gate

**What QIEA (ACIS-03) & AGON (ACIS-04) consume:** `RegimeContext` from `regime_store`. QIEA keys its param library by `regime`, and AGON gates its strategy modules by `regime` + `volatility_class` *(both legacy; v1.4: rule families are not regime-gated, and the Governor's §6 regime sizing factor stays, decision D-b)* and reads `tradeable`, `regime_stability_score`, `confidence`. **Owns conflict-table rows:** "NVMA no-trade + high-conviction signal → discard" and "regime shift + no evolved params → tradeable=False". **Done-when (phase 2, master §15):** all §14 tests green; import-linter contract still passing after this layer is added.

## Changelog
- **1.4 (LOCKED, 2026-09-25)** — Master v2.21/v2.22 (owner-ratified). The no-params veto trigger is replaced by "no registered, validated rule set" once QIEA retires, and regimes stop gating rule families. The organic triggers and the §6 regime sizing factor are unchanged (D-b). No threshold changes.
- **1.3 (LOCKED, 2026-07-17 — master v2.12, GAP-0066/0070 closure)** — Hurst repaired (Anis–Lloyd-corrected multi-window R/S, ≥8 geometric sizes with subseries averaging; an iid walk centres at ≈0.5) and narrowed to its ONLY defensible role: the anti-persistence gate into MEAN_REVERTING at the re-derived `hurst_meanrev = 0.35` (RW false-positive 7.5%, OU κ≥0.2 detection 95–100% at window 201). `hurst_trend` deleted from config/schema — R/S is drift-invariant and carries no trend meaning; trend confidence rides on ADX alone. Ranging fixture generators re-tuned to walk-dominated series (the old zigzag fixtures were themselves anti-persistent — tuned to the broken estimator).
- **1.2 (LOCKED, 2026-07-15)** — Phases 2–3 subordinate-audit triage: ILLIQUID baseline fixed to session median (GAP-0028); §8/C-REG-5 determinism honestly scoped — pure fields vs declared historical aggregates (GAP-0032); gate-states excluded from stability history (GAP-0031); remaining "Alpha Arena" consumer references renamed AGON (GAP-0029).
- **1.1 (LOCKED, 2026-07-15)** — v2.8 master consistency pass for the phase-3 build: Tier-G shock (§3.6) added as a MACRO_EVENT input (conservative-only); `session == "closed"` and exchange halt/limit-lock (§3.7) classify ILLIQUID; consumer naming updated (Alpha Arena → AGON, §5.5 reflex law); master-§15 phase renumbering (this layer is build phase 3). Status → LOCKED.
- **1.0 (DRAFT)** — From master §4 + `ACIS_Agent_Prompt.md` §3.2 + S2 layer-2 card; corrections C-REG-1..6 from `SPEC_AUDIT.md`.
