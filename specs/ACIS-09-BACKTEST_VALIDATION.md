# ACIS-09 — Backtesting Harness & Performance Validation — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-BT-009` |
| **Version** | 1.14 (**LOCKED** 2026-10-04 — stage D for many families at once: the multiplicity clause, E2's daily units, σ* for unscaled books, per-family tripwires, three forward looks per variant; master v2.36, GAP-P12D-158) · 1.13 (**LOCKED** 2026-10-03 — the tick-window and minute-candle event books named; stage C admits an LLM variant's one holdout look; master v2.35, GAP-P12D-159 X-2) · 1.12 (**LOCKED** 2026-10-03 — the event simulator opens for kill-only looks; D3 v1's window; master v2.34, GAP-P12D-154) · 1.11 (**LOCKED** 2026-10-03 — real looks open, scoped; kill-only looks; the certifying boundary in the verdict; master v2.32) · 1.10 (**LOCKED** 2026-09-29 — the R1.2 audit's owner decisions: the origin records the training-data cutoff, proposal date and exposure; the register's chain head is anchored on GitHub before real looks open; master v2.24, GAP-P12D-127) · 1.9 (**LOCKED** 2026-09-29 — the R1.1 audit's two owner decisions: B0's planted criterion becomes an equivalence test in Sharpe units (D-R11-1) and C-BT-12's horizon wording is made satisfiable (D-R11-2); GAP-P12D-125) · 1.8 (**LOCKED** 2026-09-25 — the R1 audit triage: `passed` keeps its gates, B0, serial gatekeeping with α-spending, a raw stage C, consistent stage-D units, C-BT-12 corrected; master v2.22) · 1.7 (**LOCKED** 2026-09-25 — R-1: expanding walk-forward, the register-aware verdict C-BT-11 v2, the synthetic-lab law C-BT-12; master v2.21) · 1.6 (**LOCKED** 2026-07-18, phase-11 start; v1.2 2026-09-11 owner-ratified: cross-check source HistData replaces TrueFX — master v2.13; v1.3 2026-09-13 owner-approved: independent validation set — master v2.17; v1.4 2026-09-15: walk-forward honesty C-BT-11 — embargo, Deflated Sharpe gate ≥ 0.95, date-joined SPX; v1.5 2026-09-15: mutation-gate targets; v1.6 2026-09-16: per-regime + per-strategy attribution, GAP-P12D-31) |
| **Layer / DIR** | Validation · `[DIR:tests/backtest]` (+ `scripts/`) |
| **Consumes** | the full engine (ACIS-01…07) run in backtest mode over historical data |
| **Emits** | a per-account validation report vs `../ACIS_SPEC.md` §14 targets (out-of-sample) |
| **Depends On** | `../ACIS_SPEC.md` §13, §14, §15, §9.5, §3.7, §8.5, §16 · all layer specs · `ACIS-00` |
| **Blocks** | **phase 12 (live)** — live is forbidden until §14 minimums are met out-of-sample per account + human sign-off |
| **Corrections applied** | in/out-of-sample discipline, walk-forward, never-report-in-sample, backtest-fidelity gap (GAP-0001); **v1.1: per-account §14 evaluation with §9.5 platform limits active (F26/F31); the TSMOM (GAP-0055) + MOMENTUM_SCALP (GAP-0009) avg-duration carve-outs; Dukascopy/TrueFX data provenance + loader + cross-source drift check + OANDA C8 cost calibration (v2.9); the nine futures/account glitch classes (F31, §13); targeted mutation testing of fitness/cost/backtest code (v2.10 item d, §16 dependency); the GAP-0103 VaR-breach-frequency report; the GAP-0108 outage-allowance-source refinement; the §15 phase renumber (ACIS-09 = phase 11, live = phase 12)** |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract (the report) · 5. Data & split schemas · 6. Methodology & config · 7. Core logic · 8. Run modes · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Prove — honestly, out-of-sample, **per attached account** — whether ACIS meets the §14 performance targets, and be the gate that stands between paper and live. It runs the *real* engine (not a re-implementation) against historical data with a strict in-sample/out-of-sample split and walk-forward evaluation.

**IS:** a deterministic historical replay driving the actual ACIS layers in `backtest` mode; strict train/test separation; walk-forward windows; equity/drawdown/regime-labelled reporting; the §14 pass/fail gate computed **only** on out-of-sample data, **per account on that account's enabled universe with the account's §9.5 platform rules active during the run**.

**IS NOT:** it is not a separate strategy engine (it must exercise ACIS-01…07, or the result is meaningless); it never tunes params on the test set; it never reports in-sample numbers against §14 (master §13, hard rule); it is not a live-trading path. It cannot mark the system "validated" on in-sample, single-split, single-account, or rule-violating results.

**Done-when:** the harness replays ≥2 years of provenance-declared tick data per instrument through the real engine; QIEA evolves only on in-sample/train folds; the report presents out-of-sample metrics against §14 with equity/drawdown/regime distributions **per account**; walk-forward is used; the honesty guards (§13) are enforced in code; the nine §13 futures/account glitch classes have backtest-level tests.

## 2. Entry contract

**Entry point:** `scripts/backtest_runner.py` → `tests/backtest/harness.py::Backtest.run(config, account) -> ValidationReport`. It instantiates the real ACIS layers with a historical tick replay as the data source (ACIS-01 interface), runs the loops in accelerated time, and collects `FillReport`s/`RiskSnapshot`s. **The run is scoped to ONE account** (its enabled universe + its rulebook); a multi-account validation is a set of per-account reports, each graded on its own.

**Inputs:** ≥2 years of provenance-declared tick data per instrument (§13, Dukascopy primary / TrueFX cross-check); a train/test split spec; walk-forward window config; the account's `platform_rules.yaml` rulebook; the same `system_config.yaml`/`instruments.yaml`/`guardrail_limits.yaml` used in paper/live (guardrails identical — backtests do not run with relaxed limits, and the account's §9.5 platform limits apply *during* the run, not just live).

## 3. Architecture & responsibility

Units: `harness.py` (replay + loop driver in accelerated time), `walk_forward.py` (fold generation), `metrics.py` (Sharpe, PF, drawdown, win-rate, positive-months, SPX correlation, avg duration — NaN-safe, Decimal PnL, with the TSMOM/scalp duration carve-outs), `report.py` (`ValidationReport` + curves), `data_loader.py` + `sources.py` (Dukascopy/HistData loaders + §3 validation + cross-source drift check + OANDA C8 calibration hook). It drives the engine; it does not reimplement any layer's logic. Single responsibility: **honest, per-account validation.**

## 4. Output contract — `ValidationReport`

```python
@dataclass(frozen=True)
class ValidationReport:
    account: str                      # the account this report grades (its universe + rulebook)
    period: tuple[datetime, datetime]
    split: str                        # e.g. "walk_forward" with fold boundaries
    in_sample: MetricBlock            # reported for transparency, NEVER graded vs §14
    out_of_sample: MetricBlock        # the ONLY block graded vs §14
    per_regime: Mapping[str, SliceStats]      # v1.6 (GAP-P12D-31): trade-level attribution
    per_strategy: Mapping[str, SliceStats]   # v1.6: which AGON module made or lost the money
    equity_curve_ref: str             # artifact path
    drawdown_curve_ref: str
    targets_met: Mapping[str, bool]   # per §14 metric, computed on out_of_sample ONLY
    passed: bool                      # all §14 minimums met out-of-sample on this account
    fidelity_caveats: tuple[str, ...] # GAP-0001 caveats surfaced in the report itself
    var_breach_frequency: float       # GAP-0103: observed 1-day 1% VaR breach rate vs the 3% cap
    rule_violations: tuple[str, ...]  # §9.5: any platform-rule breach during the run (a pass that
    #                                   needed a violation is NOT a pass — non-empty ⇒ passed=False)
    trial_count: int                  # v1.4 (GAP-SP12E-03): trial Sharpe ratios behind the selection
    deflated_sharpe: float            # v1.4: Bailey & López de Prado (2014) DSR of the OOS returns;
    #                                   `passed` requires ≥ 0.95 over ≥ 2 trials (owner-ratified, GAP-P12D-16)
```

`MetricBlock`: annual Sharpe, max drawdown, win rate, profit factor, positive-months %, SPX correlation, **avg trade duration (excluding TSMOM + MOMENTUM_SCALP, GAP-0055/0009)**, plus `tsmom_avg_duration` and `scalp_avg_duration` reported SEPARATELY (never folded into the §14 avg-duration metric). **`targets_met`/`passed` are computed from `out_of_sample` only** and require an empty `rule_violations` (a strategy mix that clears §14 only by violating the account's own rules has NOT cleared §14, master §14). The §14 minimums: Sharpe > 1.5, max DD < 15%, win rate > 48%, PF > 1.4, positive months > 70%, SPX corr < 0.25, avg duration 30min–48h.

## 5. Data & split schemas

- **Tick dataset (§13 provenance):** per-instrument historical ticks (≥2 yr) from a **declared, reproducible source named in config** — **Dukascopy** primary (institutional tick, bid/ask; acquired via its official S3 archive), **HistData** cross-check (validator, not primary; v1.2 — replaces TrueFX, whose free history was withdrawn). Ingested data passes the SAME §3 validation as live ticks (NaN/gap/weekend filtering, bad-tick rejection logged); OANDA is NOT a backtest tick source (its historical API is candle-grade) but its practice-feed spreads calibrate the C8 cost model so backtest friction matches the paper/live venue. `data_loader.py` owns the loader + a **cross-source sanity check** (Dukascopy vs HistData drift on overlapping windows ⇒ investigate/flag, NEVER average silently). Ticks are regime-labelled offline (replay NVMA over history) for QIEA fitness and per-regime reporting.
- **Split:** `train` (in-sample — legacy QIEA may evolve here until it retires; nothing is fitted for a fixed family) vs `test` (out-of-sample — evolution frozen, params only promoted at simulated session boundaries as in production). Walk-forward (v1.7, A1): **EXPANDING** train / 1-yr test / 1-yr step. Each fold trains on every validated day from the instrument's first validated day (never before `DATA_START`) up to the test year. A family with a training step needs ≥ 2 years first; a fixed family has none, so its first test year opens once its longest lookback is warm. *(Legacy text:* rolling `(train_window, test_window)` folds;*)* test folds are concatenated for the out-of-sample block. **Cross-regime OOS (GAP-0008):** the concatenated test folds must span multiple regimes; a promoted param set is graded across regimes it did not evolve in. **Embargo (v1.4, GAP-SP12E-03):** each test window starts `embargo` after its training window ends, and the harness refuses a fold whose real train→test data gap is shorter than the maximum hold.
- **Config (`backtest:`):** *(v1.8: `train_window` applies to explored families only; a fixed family's plan is expanding with its lookback warm-up, GAP-P12D-123)* `data_years:2`, `train_window`, `test_window`, `walk_forward_step`, `accel_clock`, `spx_series_ref`, `tick_source` (declared provenance), `cross_source_drift_bps` (threshold), `slippage_model`, `spread_model`. Required (schema-fatal if missing).

## 6. Methodology & config

- **Walk-forward:** for each fold, QIEA evolves on `train`, params freeze, engine trades `test` with the production session-boundary promotion rule; metrics come from the `test` fold only. Concatenated test folds = the graded out-of-sample record.
- **Per-account evaluation (§9.5/§3.7):** the run uses the account's enabled universe and loads its rulebook; the §9.5 platform limits (drawdown series, news windows, min-hold, lot caps, weekend/overnight bans) are ACTIVE during the run exactly as live. Any rule breach is recorded in `rule_violations` and forces `passed=False`.
- **Duration carve-outs (GAP-0055/0009):** the §14 avg-duration metric EXCLUDES TSMOM (multi-month by design) and MOMENTUM_SCALP (5–15-bar by design); both are reported separately so neither drags the 30min–48h band. This is an owner-ratified §14 metric carve-out, not an indulgence on any other metric.
- **VaR-breach frequency (GAP-0103):** the run records how often the realised 1-day loss exceeds the 1% VaR the Risk Monitor computed, and reports the empirical breach rate against the 3% cap — the phase-11 delivery of "report the binding frequency" the owner's ratification deferred here.
- **Outage-allowance-source refinement (GAP-0108):** the scenario-replay outage allowance is refined to source the worst gap from the worst ENABLED-instrument gap for this account's universe, rather than any book scenario (the disabled-extension −35% CHF over-states an all-majors account); the refined value is used in the per-account release gate.
- **Fidelity modelling (GAP-0001):** spread + slippage models are applied so backtest fills are not naively at mid; the report lists the models used and surfaces `fidelity_caveats` (tick backtests cannot fully reproduce live microstructure — stated *in the report*, not hidden). This is why live also requires the paper phase + OANDA practice account (master §15).
- **Guardrails identical:** the equity floor and all HALT limits are the production `guardrail_limits.yaml` — a backtest never relaxes them (a "passing" backtest under relaxed limits is invalid; the report carries the `guardrail_hash`, ACIS-08 §5).

## 7. Core logic

1. Load ticks via `data_loader` (declared source, §3 validation, cross-source drift check); build walk-forward folds.
2. For each fold: (a) QIEA evolves on `train` only; (b) freeze; (c) replay `test` through the real ACIS loops in accelerated time, honouring session-boundary promotion, NVMA veto, Governor sizing, Execution fill modelling, Risk HALTs/equity breaker, AND the account's §9.5 platform rules exactly as production; (d) collect FillReports/RiskSnapshots + any rule breach.
3. Compute per-fold `test` metrics (with the duration carve-outs); aggregate into `out_of_sample`; compute `in_sample` separately (transparency only); tally `var_breach_frequency` + `rule_violations`.
4. Grade `out_of_sample` vs §14 → `targets_met`, `passed` (passed also requires empty `rule_violations`).
5. Emit `ValidationReport` + equity/drawdown/regime-distribution artifacts.

**Honesty guards (enforced in code, §13):** the grader takes only the `out_of_sample` block; a unit test asserts that in-sample metrics never drive the grade — a FLOW guarantee (`build_report` is the sole grade path and it routes only `out_of_sample` in), not a type barrier (both blocks are the same `MetricBlock`; GAP-P11I-06); `passed` additionally requires ≥2 years, >1 walk-forward fold, a minimum trade count (GAP-P11I-07), an empty `rule_violations`, and a matching `guardrail_hash` (a single split, a thin sample, an in-sample grade, a rule-violating run, or a relaxed-limit run cannot pass). The graded `period` and drawdown are DERIVED from the realised out-of-sample record — the ≥2-year gate binds the data span, not a caller claim (GAP-P11I-01), and max-drawdown is measured off the intraday high-water, never an EOD approximation (GAP-P11I-04).

## 8. Run modes

`backtest` mode is one of the three `acis_set_mode` values (ACIS-08); it is the only mode the harness uses. The harness never sets `live`. Reports feed `acis_report`/`daily-performance-brief` (ACIS-08) for out-of-band human/LLM review. Live enablement (**phase 12**) reads the persisted per-account `ValidationReport.passed` + a human sign-off record; the engine refuses `set_mode(live)` without both (ACIS-08 §7 + this gate).

## 9. Persistence & logging

Reports + curves persist to `logs/`/artifacts with the run's config hash and data range (reproducibility). Every run logs `BACKTEST_RUN{account, period, folds, passed}`; a run that would grade on in-sample is a hard error (`BACKTEST_INSAMPLE_GRADE_BLOCKED`) — it cannot happen silently. Cross-source drift beyond `cross_source_drift_bps` logs `BACKTEST_SOURCE_DRIFT{window, bps}` (investigate, never silently average). Loader writes are **batched** (GAP-0067: no per-row commit; the ≥2-yr ingest uses transaction batching / the prod store, not the dev SQLite per-row path).

## 10. Store schema (DDL)

```sql
CREATE TABLE validation_report (
    report_id     TEXT PRIMARY KEY,
    account       TEXT NOT NULL,        -- the account this report grades
    created_at    TIMESTAMPTZ NOT NULL,
    period_start  TIMESTAMPTZ NOT NULL,
    period_end    TIMESTAMPTZ NOT NULL,
    config_hash   TEXT NOT NULL,
    guardrail_hash TEXT NOT NULL,       -- proves production limits were used
    out_of_sample JSONB NOT NULL,
    in_sample     JSONB NOT NULL,
    per_regime    JSONB NOT NULL,
    targets_met   JSONB NOT NULL,
    passed        BOOLEAN NOT NULL,
    var_breach_frequency REAL NOT NULL,
    rule_violations JSONB NOT NULL,
    fidelity_caveats JSONB NOT NULL
);
```
`guardrail_hash` in the report proves the run used the real limits — a report with a mismatched hash cannot gate live.

## 11. MCP contract

`acis_run_backtest(params)` (ACIS-08) triggers a run out-of-band; `acis_report(period)` returns a persisted `ValidationReport`. Neither can set live; live is gated on a `passed` per-account report + human sign-off. Reports are read-only resources; the harness exposes no control over the live engine.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| < 2 years data | run refused / `passed=False` with reason |
| single split (no walk-forward) | cannot pass; graded blocked |
| attempt to grade on in-sample | hard error `BACKTEST_INSAMPLE_GRADE_BLOCKED` |
| relaxed guardrails detected (hash mismatch) | report invalid; cannot gate live |
| platform-rule breach during the run | recorded in `rule_violations`; forces `passed=False` |
| cross-source drift > threshold | `BACKTEST_SOURCE_DRIFT`; flag for investigation, never silent-average |
| undeclared/unknown tick source | run refused (provenance is mandatory, §13) |
| NaN metric | NaN-safe; degenerate runs report worst-case, never a spurious pass |

## 13. Logic-flaw registry
- **C-BT-1 (no in-sample grading):** grader consumes only `out_of_sample`; a FLOW test asserts in-sample metrics never drive the grade (`build_report` is the sole grade path — GAP-P11I-06; the two blocks share the `MetricBlock` type, so the guarantee is the routing, proven by test, not a type barrier) (master §13 hard rule).
- **C-BT-2 (walk-forward required):** `passed` requires ≥2 yr + >1 fold; test asserts a single-split run cannot pass.
- **C-BT-3 (real engine):** the harness drives ACIS-01…07 (not a reimplementation); test asserts the same layer classes are instantiated (a change in NVMA behaviour changes backtest results).
- **C-BT-4 (production guardrails):** `guardrail_hash` recorded + checked; a relaxed-limit run cannot gate live.
- **C-BT-5 (fidelity honesty, GAP-0001):** `fidelity_caveats` surfaced in the report; slippage/spread models documented; live still requires paper + practice account.
- **C-BT-6 (Decimal PnL):** metrics computed on Decimal PnL at accounting boundaries (F17); no float drift in the equity curve.
- **C-BT-7 (per-account + rules-active, §9.5/§14):** grading is per account on its enabled universe with its §9.5 rules active during the run; a rule breach forces `passed=False`; test asserts a rule-violating "passing" run does not pass.
- **C-BT-8 (duration carve-outs, GAP-0055/0009)** *(legacy: since master v2.21 §14 duration is reported, never gated)*: the §14 avg-duration metric excludes TSMOM + MOMENTUM_SCALP; both reported separately; test asserts a TSMOM-heavy run does not fail avg-duration and that the carve-out figures are surfaced.
- **C-BT-9 (data provenance + drift, §13/v2.9, v2.17):** the tick source is declared/validated; a cross-source drift beyond threshold flags, never averages, and too little overlap is itself a flag (GAP-P12D-13); an undeclared source is refused; the primary passes an independent validation of the primary tick source (v2.17, GAP-P12D-14): ECB euro reference rates vs the primary's mid at the 14:15-Frankfurt fixing on every business day, the EUR/GBP ≈ EUR/USD ÷ GBP/USD triangle, the market's own clock marks (no ticks in the FX weekend; the spread spike at the real 17:00-New-York rollover, gold's 17:00–18:00 New-York break and the 08:30-New-York US jobs-report burst — each against one hour early/late, so a shifted clock fails), and a sampled gold comparison against HistData; every disagreement FLAGS for investigation, never averages silently. HistData's FX ticks carry the primary's own prices (GAP-P12D-13), so a Dukascopy-vs-HistData FX drift is a decoding/clock check, not a price check (`scripts/run_data_validation.py`, zero unexplained flags before any §14 pass is presented).
- **C-BT-10 (futures/account glitch classes, F31):** the §13 classes have backtest-level tests. SEVEN forex/account classes are tested at phase 11 (`tests/backtest/test_glitch_classes.py`): triple-swap Wednesday carry, holiday half-day session, trailing-drawdown anchor (an EOD approximation must fail), symbol suffix mismatch, limit-lock/exchange halt (ties to §8.5 gap law), weekend-ban fencepost, Tier-G shock during blackout (stricter wins, no double-count). The TWO futures-lifecycle classes — contract roll gap and expiry-with-open-position (structurally unreachable given the roll policy) — require the futures roll-or-flatten policy and are tested WITH futures enablement at phase 12 (master §3.7: futures live only on futures-specific gates + a separate human sign-off; no futures instrument is enabled, so these paths are inert in phase-11 forex validation). Recorded as GAP-0109, not silently skipped.
- **C-BT-11 v2 — the register-aware verdict (v1.8; R-1 ratified 2026-09-25, then the audit triage, owner-ratified 2026-09-25, the R1 audit triage: "Ratify all"; A1 + A2; master v2.22 §14).**
  - It supersedes ONLY the v1.4 DSR ≥ 0.95 clause of `passed` (GAP-P12D-16), which passed nothing (GAP-P12D-33/37). Every other `passed` condition stands: C-BT-2, C-BT-4, C-BT-7 and the §14 gates.
  - Until the verdict module is built (R1.4), the as-built v2.20 `passed` stands. It is the as-built path, not a uniformly stricter one (GAP-P12D-123).

  0. **Precondition B0 — machinery proven first (GAP-P12D-105).** No real-data verdict is issued unless, at the same `recon_commit`, the lab (C-BT-12) shows all of:
     - a planted effect detected at its theory Sharpe, by EQUIVALENCE (v1.9, owner-ratified 2026-09-29, D-R11-1; GAP-P12D-125): the planted detection rate, read back as a Sharpe through the same sampling law, lies within ±10% of the closed-form theory Sharpe, at a declared n ≥ 2,000 paths and a declared lab configuration. The closed form is the sanity bound. (It was "within 2 se of its theory power", which refuses a correct lab once n is large, because the closed form is itself approximate, and which cannot see a ±9% error at small n.);
     - the null's false-detect rate ≤ 5% + 2 se;
     - a leaky oracle refused by structure;
     - the research simulator ≡ the engine on lab tapes;
     - positive controls variance-matched to their nulls.
  1. **Registration.** A graded number exists only if the look register (`data/validation/looks`, GAP-P12D-64) wrote its line first.
     - The line records the declared search space's hash, the origin (human / literature / LLM with its model, training-data cutoff, proposal date and tool exposure — master v2.24 §5.6), the certifying boundary that follows from it, the cost-map hash and the universe id.
     - **Open, scoped (v1.11, owner ruling 2026-10-03; v1.12).** Real-data looks are open for human- or literature-origin claims graded by RSIM through `evaluate()`, or by the event simulator through `evaluate_events()` (v1.12, owner ruling "Faithful event harness", GAP-P12D-154: scheduled-window rules on hourly candles (D3's month-turn windows; REBAL's close-to-close days, `event_daily.py`), and (v1.13) intraday windows priced from 1-minute candles (IMOM, `event_intraday.py`) or from ticks at local wall times (GOTOBI, `event_window.py`, with its weekday contrast), marked on RSIM's 17:00 New York clock; an event look is kill-only, refused unless its graded window ends by its claim's certifying boundary; several versions of one family may all be registered before any is graded, `register_event_look` then `grade_event_look`); LLM plans wait for the motif veto and plan schema (R12I-11), engine looks for `Backtest.run`'s consumed-look token (R12I-12). The anchor's push per register line has the owner's standing approval.
     - **The anchor (v1.10, owner-ratified 2026-09-29, E-R12-07).** Before real-data looks open, every appended line's chain head is committed to a tracked file and pushed to the project's GitHub remote; its server timestamps are the external record against rollback or rewrite. A register whose head is not anchored refuses a real-data grade (GAP-P12D-86).
     - The grade stores the family's **daily portfolio net-return vector** (GAP-P12D-98). A verdict is a pure function of the register.
     - Each cycle's testing order is itself a register row, written before any stage-A look of that cycle.
     - A graded number without a register row voids its family's results since its last clean row.
  2. **Unit of test.** A registered **family-version**: a fixed pooled combination of its members, with no argmax inside, graded on its **portfolio** daily series, never on the stacked instrument × day panel (GAP-P12D-100).
  3. **Stage A — development (2012–2023; one tier for fixed families, an E/V split only for explored ones).** Serial gatekeeping within a registered cycle (GAP-P12D-102/111; FDA *Multiple Endpoints in Clinical Trials*, 2022, §§5 and 7):
     - **The α budget (decision D-d).** A cycle is the set of ≤ 5 family-versions whose order is registered together, at most one cycle a quarter. Cycle 1 spends α = 0.03. Every later cycle spends half of the lifetime budget still unspent (0.01, 0.005, …), so lifetime family-wise error stays ≤ 0.05.
     - **The chain.** The cycle's families are tested in their registered order, each at the cycle's α; testing stops at the first failure. Families outside the chain are tested only if the whole chain passed, Holm-adjusted among themselves at the cycle's α.
     - **Looks.** Each family declares a look budget k ∈ {1, 2, 3} at registration. Each of its looks is tested at α/k.
     - **The certifying boundary (v1.11; master §5.6).** A look's HAC p counts toward a pass only over its days on or after its claim's certifying boundary. A look whose whole window lies before the boundary is KILL-ONLY (owner rulings 2026-10-03): it names no cycle, spends no α, and is killed at a HAC t below −0.5 on its net daily portfolio series (stage C's rule); a survival credits nothing.
     - **A family passes when all of these hold:**
       - the one-sided lower bound of its expanding-WF OOS annual Sharpe is > 0, using a HAC (Newey–West) or Lo (2002) standard error on the daily portfolio series (GAP-P12D-121);
       - its paired excess over the registered passive benchmark is > 0;
       - it is net > 0 at 2× modelled cost including swap;
       - no ±10% plateau neighbour fails C9 (kill-only; the conventions are in master §5).
     - The cost filters are master §5.6's: fixed expectations, never a realised per-instrument Sharpe (GAP-P12D-115).
     - **Explored families** instead use max-t over the declared grid, plus PBO ≤ 0.20 with S = 16.
       - Max-t's null comes from a stationary bootstrap of the members' daily series jointly, recentred, with the block length pre-registered (White 2000; Romano–Wolf step-down; GAP-P12D-120).
       - PBO ≤ 0.20 is a declared deviation from the paper's customary 0.05: max-t carries the α, and PBO is a secondary kill (GAP-P12D-119).
  4. **Stage B — engine confirmation.** One frozen expanding-WF run through the real engine on hourly bars as ticks, graded on daily OOS net returns, with Bonferroni over ≤ 3 registered engine looks. The engine's OOS Sharpe must not be significantly below the research simulator's (one-sided 5%).
  5. **Per-account re-grade (GAP-P12D-112).** A family that passed A and B is re-graded on each account's live-eligible universe with that account's §9.5 rules active. The §14 gates and C-BT-7 apply there.
  6. **Stage C — kill-only, once (decision D-e; GAP-P12D-114).**
     - The held-out instruments are graded RAW, with no residualisation. Stage C can only kill, so a factor leak can only weaken a kill, never credit.
     - The 2024–25 holdout is graded once. An LLM-origin variant takes that one look too, kill-only: master v2.35's amendment of §5.6 R1-D13, enforced by `look_claims.admit_claim` (v1.13, GAP-P12D-159).
     - Each kills at t < −0.5 (GAP-P12D-97).
  7. **Stage D — forward (GAP-P12D-110).** Three betting e-processes on the forward record, valid under daily looks (Waudby-Smith & Ramdas 2022; Ville).
     - **Units.** σ* is the declared DAILY volatility target, σ*_ann/√252, declared before the forward record starts; a book with no target declares its development look's realised daily volatility instead (v1.14, P-3). r is the book's daily net P&L as a fraction of equity.
     - **E1 (edge):** W = the mean over λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8} of Π(1 + λ·max(r/(6σ*), −1)).
       - The floor at −1 keeps each factor ≥ 1 − λ > 0, a property of the bet. It binds only on a day beyond −6σ*, which the tripwire handles.
       - W ≥ 20 is "edge shown" and W ≥ 100 is "strong"; otherwise "not yet", never "failed".
     - **E2 (kill):** the same bettor on (μ_claim − r)/(6σ*), with μ_claim = (SR̂_dev/2)·σ*, a daily return; SR̂_dev is the development look's DAILY Sharpe, SR_ann/√252 (v1.14, P-2).
       - W ≥ 5 freezes scaling: the family's risk allocation may not increase, and reductions stay allowed.
       - W ≥ 20 kills.
       - E2 is slow: a dead strategy is killed by year 1 only ~1–4% of the time, so "E2 silent" certifies little by itself. PLAN_R1's "25% by 1 year" is the freeze figure.
     - **E3 (cost):** paired per fill; realised − modelled cost in modelled-cost units, against a ±25% band. It breaches at W ≥ 20 and certifies when both one-sided nulls reach W ≥ 20.
     - **Tripwires.** A day beyond −kσ*, or a fill beyond 5 modelled costs, VOIDS the family-version's running certification: its W := 0 permanently, and a new family-version must be registered. A tripwire is never clipped away. k = max(6, 1.5 × the family's worst registered-history day in σ* units), declared before its first forward day (v1.14, P-5: a fixed 6 would have fired in history). The bettors' 6σ* scale is unchanged.
     - **Many families at once (v1.14, P-1a).** A forward tournament fixes its capacity (20) in advance. Each family takes α_i = 0.05/capacity, never recycled. It is "eligible for owner review" only on the milestone-D screen (≥ 126 days, net Sharpe ≥ 0.5, not killed, no tripwire; a spending gate, never evidence, reported beside its luck odds), plus significance (a weighted Holm test over the capacity at the pre-registered looks of 126, 252 and 504 days, one-sided HAC p, Bonferroni over the looks; or E1 ≥ 1/α_i), plus an intact record. Each registered variant may take those three forward looks on tier 4 (master v2.36's §5.6 amendment, `look_claims.admit_claim`). `tests/backtest/tournament_rule.py` and `forward_record.py`.
     - Live and replay decisions must be identical on the same feed; a difference halts the family.
     - For an LLM-originated family (master §5.6), stage D is the only stage that can credit a pass.

  **`passed` (GAP-P12D-104)** = all of:
  - B0 holds;
  - stages A and B passed;
  - stage C did not kill;
  - the §14 gates (Max DD < 15%, SPX correlation < 0.25) hold on the per-account re-grade;
  - C-BT-2 (≥ 2 yr, > 1 fold, ≥ 30 trades), C-BT-4 (the guardrail hash) and C-BT-7 (no §9.5 rule violation) hold.

  The Deflated Sharpe stays as an informational column.

  **Embargo (GAP-P12D-123).** A fixed family has no training step, so it carries no per-fold embargo, only its lookback warm-up. An explored family's embargo is ≥ max(7 days, its longest lookback), and any CPCV stage also purges the longest lookback.
- **C-BT-12 — the synthetic-lab law (v1.8, R1-D12; corrected per GAP-P12D-117).**
  - Synthetic markets grade MACHINERY, never edge.
  - A generator demeans nothing: a demeaned path is a bridge (GAP-P12D-91).
  - The permuted null randomises the sign of each ARITHMETIC price increment, or pairs every path with its antithetic, sign-flipped twin. So a long-biased rule earns nothing in PRICE units, not only in log units, and a price-unit null test pins it.
  - A planted market is variance-matched to its null EXACTLY at each graded rule's decision (holding) horizon (daily for TREND). Planted and null differ at longer horizons by construction, because a persistent effect's excess variance there IS the effect (v1.9, owner-ratified 2026-09-29, D-R11-2; it read "every horizon the lab's rules use", which no single scale can meet). The match is made by construction (common random numbers plus an exact rescale), never by a sampled tolerance (GAP-P12D-90).
  - Intraday refinement of correlated daily bars bridges the common factor jointly (GAP-P12D-92).
  - Every synthetic verdict recorded before these fixes is re-stated after them (GAP-P12D-49 included).
  - Synthetic runs never enter a real-data verdict.
- *(v1.4 text, superseded by C-BT-11 v2 for `passed`; its embargo, SPX-join and constant-series clauses stand):* **C-BT-11 (walk-forward honesty, v1.4):** folds carry an embargo at least as long as the max hold, enforced on the real data (GAP-SP12E-03). The report carries `trial_count` and the Deflated Sharpe (Bailey & López de Prado 2014, pinned by test to the paper's numerical example), and `passed` requires a Deflated Sharpe ≥ 0.95 over at least 2 trials, so a report that does not record its trials cannot pass (owner-ratified 2026-09-15, GAP-P12D-16). The trials are the candidate champions at each fold's selection — every instrument × regime QIEA evolved — each contributing its holdout per-trade Sharpe; N adds the ACIS-11 attempt-registry entries; the graded series is the out-of-sample per-trade return (pnl / USD notional) (owner ruling GAP-P12D-25, which replaced the per-fold-Sharpe trial set; declared deviations: per-trade basis, and candidates scored by the QIEA fitness harness rather than the full engine). The SPX correlation joins strategy equity, marked at the 17:00-New-York rollover, to SPX closes BY DATE; too little overlap is NaN, which fails the gate (GAP-SP12E-06). A constant return series has a Sharpe of 0, never a float-dust infinity (GAP-P12D-17).

## 14. Test contract (postcondition-style)

**Unit:** metrics correct on synthetic PnL series (Sharpe/PF/drawdown/win-rate/positive-months/SPX-corr/avg-duration), NaN-safe (C-BT-6); grader uses out-of-sample only (C-BT-1); single-split cannot pass (C-BT-2); guardrail-hash mismatch invalidates (C-BT-4); a rule-violating run does not pass (C-BT-7); the duration carve-outs hold and the carve-out figures surface (C-BT-8); the loader validates + flags cross-source drift and refuses an undeclared source (C-BT-9); the nine glitch classes each have a test (C-BT-10); the VaR-breach frequency is tallied (GAP-0103).

**Integration:** a full walk-forward run over a synthetic ≥2-yr fixture drives the real engine end-to-end and produces a per-account `ValidationReport` with populated out-of-sample + per-regime blocks and equity/drawdown artifacts; a deliberate NVMA change shifts backtest output (proving the real engine is exercised, C-BT-3); a run under relaxed limits is flagged invalid; a second account (e.g. an XAUUSD-only prop rulebook) is graded independently on its own universe/rules.

**Quality gate (v2.10 item d, §16):** targeted **mutation testing** of the fitness/cost/backtest code (`core/optimizer/fitness.py`, `core/optimizer/costs.py`, `tests/backtest/metrics.py`, and since v1.5 `tests/backtest/deflated_sharpe.py`, which the pass verdict gates on) — the code whose silent lies are most expensive — via a declared tool dependency (mutmut/cosmic-ray; the §16 stdlib-only rule gets its adapter-package exception edit at this phase). A surviving mutant in a graded metric or the cost model is a finding. A mutant that makes the tests fail in ANY way, including an import or collection error, is killed: a runner that counts only one failure code as a kill reports false survivors (GAP-P12D-28). Not a substitute for the per-phase adversarial audits.

## 15. Integration gate

**The live gate:** **phase 12** (live broker) is permitted only when a persisted per-account **rung-2 record** (master §14, v2.22) exists — which contains `ValidationReport.passed == True` per C-BT-11 v2 (the §14 gates and C-BT-2/4/7 included) on ≥2-yr out-of-sample walk-forward with the account's §9.5 rules active, plus rung 2's practice-mode forward evidence (GAP-P12D-69) — **and** a human sign-off record exists; ACIS-08's `acis_set_mode(live)` checks both (plus the dual-hash ack). This spec is the wall between paper and live (master §15). **Pre-phase-12 VPS deployment-readiness gate (v2.10)** runs alongside: CI running the full suite as the merge gate, the Docker scaffold, process supervision + the §8.6 watchdog deployed, and per-adapter server-side-stop verification in the §7.5 conformance suite. **Done-when (phase 11, master §15):** §14 harness green; the honesty guards are enforced in code, not just documented; never-report-in-sample proven by test; per-account grading with rules-active proven; the nine glitch classes covered; the mutation-testing quality gate configured.

## Changelog
- **1.11 (LOCKED, 2026-10-03)** — C-BT-11 v2 steps 1 and 3, owner rulings 2026-10-03: real-data looks open, scoped to human- and literature-origin RSIM claims; the anchor's push per register line approved; a look's pass counts only days after its certifying boundary, and a look wholly before it is kill-only (no cycle, no α, killed at HAC t < −0.5). D1 (Carver's rule, selected by the cloud lead's plan) is graded that way. Master v2.32.
- **1.10 (LOCKED, 2026-09-29)** — The R1.2 dual audit's two owner decisions (GAP-P12D-127), ratified in chat: "The stricter boundary (Recommended)" (E-R12-02) and "Push the chain head to GitHub (Recommended)" (E-R12-07). C-BT-11 v2 step 1: the look line records the origin's training-data cutoff, proposal date and tool exposure and the certifying boundary that follows (master v2.24 §5.6), and the register's chain head is anchored on the project's GitHub remote before real-data looks open. Tightening only.
- **1.9 (LOCKED, 2026-09-29)** — The R1.1 dual audit (GAP-P12D-125); the owner ratified both recommendations in chat on 2026-09-29 ("Equivalence in Sharpe (Recommended)", "Reword (Recommended)").
  - **C-BT-11 v2 step 0, B0 (a):** "within 2 se of its theory power" becomes an equivalence test: the detection rate read back as a Sharpe lies within ±10% of the closed-form theory Sharpe, at a declared n ≥ 2,000 paths and a declared configuration (D-R11-1). The closed form is approximate: √(2/π) under non-Gaussian returns, the arcsine law, t's dispersion. So a fixed binomial band refused a correct lab once n grew, and could not see a ±9% error at n = 400 (audits R11I-03, E-R11-01).
  - **C-BT-12:** the variance match is exact at each graded rule's decision (holding) horizon; planted and null differ at longer horizons by construction (D-R11-2; audits R11I-06, E-R11-07).
  - No guardrail, HALT, veto or `passed` semantic changes.
- **1.8 (LOCKED, 2026-09-25)** — The R1 dual audit (GAP-P12D-103) triaged; owner-ratified 2026-09-25, the R1 audit triage: "Ratify all". C-BT-11 v2 is corrected:
  - `passed` keeps the §14 gates and C-BT-2/4/7 (GAP-P12D-104), and B0 is a precondition (GAP-P12D-105);
  - stage A is serial gatekeeping with α-spending (D-d), look budgets and a HAC standard error (GAP-P12D-111/121); explored families get a named bootstrap and a declared PBO (GAP-P12D-119/120);
  - the per-account re-grade is added (GAP-P12D-112);
  - stage C grades the held-out set RAW, kill-only (D-e);
  - stage D's units are consistent, and a tripwire sets W := 0 (GAP-P12D-110).

  C-BT-12 is corrected: the decision-horizon variance match and the price-unit null (GAP-P12D-117). The live gate reads the rung-2 record. No guardrail, HALT or veto semantic changes.
- **1.7 (LOCKED, 2026-09-25)** — Master v2.21 (R-1, owner-ratified 2026-09-25, R-1: "i ratify all your recommendations for R1-D1 to D14"; drafts in R1_LEAD_REVIEW_2026-09-25.md).
  - The walk-forward is expanding (A1, GAP-P12D-67).
  - C-BT-11 v2, the register-aware verdict (A2): fixed pooled family-versions on portfolio series; a fixed-sequence stage A with the passive-benchmark, 2×-cost, ⅓-cost and plateau kill-only conditions; engine confirmation; kill-only held-out and holdout at t < −0.5; forward e-process bettors E1/E2/E3. It supersedes the DSR ≥ 0.95 `passed` gate (GAP-P12D-16), which the as-built code keeps until the verdict module lands (R1.4).
  - C-BT-12, the synthetic-lab law (R1-D12).
  - No guardrail, HALT or veto semantic changes.
- **1.6 (2026-09-16)** — Attribution (GAP-P12D-31, after the engine-level falsification failed and the run could not say WHICH regime or module lost the money): every closed trade now carries the regime active at entry, and the report gains `per_strategy` beside `per_regime`. Both are `SliceStats` (trade count, net PnL, win rate, profit factor, average duration, gross win/loss), **not** `MetricBlock`s: a subset of trades has no continuous equity curve, so Sharpe, max drawdown and positive-months are undefined on it — inventing a per-slice curve is the fabrication GAP-P11E-02 forbids. A trade with no regime groups under `UNATTRIBUTED`, so a hole in attribution is visible instead of silently dropping trades. `per_regime` was previously declared but always emitted `{}`. No §14 target value, gate or guardrail changed.
- **1.5 (2026-09-15)** — Quality gate: `deflated_sharpe.py` joins the mutation targets (the pass verdict gates on it since v1.4), and any failing test run kills a mutant — mutmut 2 counts only exit code 1, so a mutant that broke an import (pytest exit 2) was recorded as a survivor (GAP-P12D-28). No §14 target value changed.
- **1.4 (2026-09-15)** — C-BT-11: the walk-forward embargo enforced on real fold data, and `trial_count` + `deflated_sharpe` added to `ValidationReport` (GAP-SP12E-03), with `passed` gated at a Deflated Sharpe ≥ 0.95 over ≥ 2 trials (owner-ratified, GAP-P12D-16); the date-joined SPX correlation off rollover marks, where missing overlap fails instead of passing (GAP-SP12E-06); the float-dust Sharpe fix (GAP-P12D-17). No §14 target value changed.
- **1.3 (2026-09-13)** — Master v2.17: C-BT-9 extended with the owner-approved independent validation set (GAP-P12D-14) and the low-overlap flag (GAP-P12D-13).
- **1.1 (LOCKED, 2026-07-18 — phase-11 start consistency update, master v2.5→v2.12)** — per-account §14 evaluation on the account's enabled universe with §9.5 platform rules ACTIVE during the run (a rule-violating pass is not a pass; `rule_violations` forces `passed=False`; C-BT-7); the TSMOM (GAP-0055) + MOMENTUM_SCALP (GAP-0009) avg-duration carve-outs, reported separately (C-BT-8); Dukascopy-primary/HistData-cross-check data provenance (v1.2; TrueFX until 2026-09-11) + `data_loader.py` (loader, §3 validation, cross-source drift check that never silently averages, OANDA C8 calibration hook) with an undeclared-source refusal (C-BT-9, v2.9); the nine §13 futures/account glitch classes as backtest-level tests (C-BT-10, F31); the v2.10-item-d targeted mutation-testing quality gate on the fitness/cost/backtest code (§16 dependency edit at this phase); the GAP-0103 VaR-breach-frequency report field + tally; the GAP-0108 outage-allowance-source refinement to the worst ENABLED-instrument gap per account; cross-regime OOS grading (GAP-0008); batched loader writes (GAP-0067); the `ValidationReport` gained `account`/`var_breach_frequency`/`rule_violations`; the §15 phase renumber corrected throughout (ACIS-09 = phase 11; live = phase 12; the DRAFT's "phase 10/11" done-when/blocks were stale). New registry entries C-BT-7..10. No §14 target VALUE changed — the carve-outs are owner-ratified metric-scope exclusions, and per-account/rules-active grading only makes the bar STRICTER.
- **1.0 (DRAFT)** — From master §13/§14/§15 + `ACIS_Agent_Prompt.md` §6/§9 + `KNOWN_GAPS.md` GAP-0001; the "never report in-sample" and "live needs out-of-sample pass + human sign-off" rules made code-enforced gates.
