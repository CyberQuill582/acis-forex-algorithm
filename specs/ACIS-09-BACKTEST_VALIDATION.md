# ACIS-09 — Backtesting Harness & Performance Validation — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-BT-009` |
| **Version** | 1.0 (DRAFT) |
| **Layer / DIR** | Validation · `[DIR:tests/backtest]` (+ `scripts/`) |
| **Consumes** | the full engine (ACIS-01…07) run in backtest mode over historical data |
| **Emits** | a validation report vs `../ACIS_SPEC.md` §14 targets (out-of-sample) |
| **Depends On** | `../ACIS_SPEC.md` §13, §14, §15 · all layer specs · `ACIS-00` |
| **Blocks** | phase 11 (live) — live is forbidden until §14 minimums are met out-of-sample + human sign-off |
| **Corrections applied** | in/out-of-sample discipline, walk-forward, never-report-in-sample, backtest-fidelity gap (GAP-0001) |

## Table of contents
1. Purpose & scope · 2. Entry contract · 3. Architecture & responsibility · 4. Output contract (the report) · 5. Data & split schemas · 6. Methodology & config · 7. Core logic · 8. Run modes · 9. Persistence & logging · 10. Store schema · 11. MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Purpose & scope

**Purpose.** Prove — honestly, out-of-sample — whether ACIS meets the §14 performance targets, and be the gate that stands between paper and live. It runs the *real* engine (not a re-implementation) against historical data with a strict in-sample/out-of-sample split and walk-forward evaluation.

**IS:** a deterministic historical replay driving the actual ACIS layers in `backtest` mode; strict train/test separation; walk-forward windows; equity/drawdown/regime-labelled reporting; the §14 pass/fail gate computed **only** on out-of-sample data.

**IS NOT:** it is not a separate strategy engine (it must exercise ACIS-01…07, or the result is meaningless); it never tunes params on the test set; it never reports in-sample numbers against §14 (master §13, hard rule); it is not a live-trading path. It cannot mark the system "validated" on in-sample or single-split results.

**Done-when:** the harness replays ≥2 years of tick data per instrument through the real engine; QIEA evolves only on in-sample/train folds; the report presents out-of-sample metrics against §14 with equity/drawdown/regime distributions; walk-forward is used; the honesty guards (§13) are enforced in code.

## 2. Entry contract

**Entry point:** `scripts/backtest_runner.py` → `tests/backtest/harness.py::Backtest.run(config) -> ValidationReport`. It instantiates the real ACIS layers with a `MockPaperFeed`/historical replay as the data source (ACIS-01 interface), runs the three loops in accelerated time, and collects `FillReport`s/`RiskSnapshot`s.

**Inputs:** ≥2 years of tick data per instrument (master §13); a train/test split spec; walk-forward window config; the same `system_config.yaml`/`instruments.yaml`/`guardrail_limits.yaml` used in paper/live (guardrails identical — backtests do not run with relaxed limits).

## 3. Architecture & responsibility

Units: `harness.py` (replay + loop driver in accelerated time), `walk_forward.py` (fold generation), `metrics.py` (Sharpe, PF, drawdown, win-rate, positive-months, SPX correlation, avg duration — NaN-safe, Decimal PnL), `report.py` (`ValidationReport` + curves). It drives the engine; it does not reimplement any layer's logic. Single responsibility: **honest validation.**

## 4. Output contract — `ValidationReport`

```python
@dataclass(frozen=True)
class ValidationReport:
    period: tuple[datetime, datetime]
    split: str                        # e.g. "walk_forward" with fold boundaries
    in_sample: MetricBlock            # reported for transparency, NEVER graded vs §14
    out_of_sample: MetricBlock        # the ONLY block graded vs §14
    per_regime: Mapping[RegimeType, MetricBlock]
    equity_curve_ref: str             # artifact path
    drawdown_curve_ref: str
    targets_met: Mapping[str, bool]   # per §14 metric, computed on out_of_sample ONLY
    passed: bool                      # all §14 minimums met out-of-sample
    fidelity_caveats: tuple[str, ...] # GAP-0001 caveats surfaced in the report itself
```

`MetricBlock`: annual Sharpe, max drawdown, win rate, profit factor, positive-months %, SPX correlation, avg trade duration. **`targets_met`/`passed` are computed from `out_of_sample` only** — the report cannot grade itself on in-sample (enforced in code, §13). The §14 table minimums: Sharpe > 1.5, max DD < 15%, win rate > 48%, PF > 1.4, positive months > 70%, SPX corr < 0.25, avg duration 30min–48h.

## 5. Data & split schemas

- **Tick dataset:** per-instrument historical ticks (≥2 yr), stored/read the same shape as `MarketState` inputs; regime-labelled offline (replay NVMA over history) for QIEA fitness and per-regime reporting.
- **Split:** `train` (in-sample — QIEA may evolve here) vs `test` (out-of-sample — evolution frozen, params only promoted at simulated session boundaries as in production). Walk-forward: rolling `(train_window, test_window)` folds; test folds are concatenated for the out-of-sample block.
- **Config (`backtest:`):** `data_years:2`, `train_window`, `test_window`, `walk_forward_step`, `accel_clock`, `spx_series_ref`, `slippage_model`, `spread_model`. Required.

## 6. Methodology & config

- **Walk-forward:** for each fold, QIEA evolves on `train`, params freeze, engine trades `test` with the production session-boundary promotion rule; metrics come from the `test` fold only. Concatenated test folds = the graded out-of-sample record.
- **Fidelity modelling (GAP-0001):** spread + slippage models are applied so backtest fills are not naively at mid; the report lists the models used and surfaces `fidelity_caveats` (tick backtests cannot fully reproduce live microstructure — this is stated *in the report*, not hidden). This is why live also requires the paper phase + OANDA practice account (master §15).
- **Guardrails identical:** the equity floor and all HALT limits are the production `guardrail_limits.yaml` — a backtest never relaxes them (a "passing" backtest under relaxed limits is invalid).

## 7. Core logic

1. Load ticks; build walk-forward folds.
2. For each fold: (a) QIEA evolves on `train` only; (b) freeze; (c) replay `test` through the real ACIS loops in accelerated time, honouring session-boundary promotion, NVMA veto, Governor sizing, Execution fill modelling, Risk HALTs/equity breaker exactly as production; (d) collect FillReports/RiskSnapshots.
3. Compute per-fold `test` metrics; aggregate into `out_of_sample`; compute `in_sample` separately (transparency only).
4. Grade `out_of_sample` vs §14 → `targets_met`, `passed`.
5. Emit `ValidationReport` + equity/drawdown/regime-distribution artifacts.

**Honesty guards (enforced in code, §13):** the grader takes only the `out_of_sample` block; a unit test asserts that feeding in-sample metrics to the grader is impossible by type/flow; `passed` requires ≥2 years and >1 walk-forward fold (a single split cannot pass).

## 8. Run modes

`backtest` mode is one of the three `acis_set_mode` values (ACIS-08); it is the only mode the harness uses. The harness never sets `live`. Reports feed `acis_report`/`daily-performance-brief` (ACIS-08) for out-of-band human/LLM review. Live enablement (phase 11) reads the persisted `ValidationReport.passed` + a human sign-off record; the engine refuses `set_mode(live)` without both (ACIS-08 §7 + this gate).

## 9. Persistence & logging

Reports + curves persist to `logs/`/artifacts with the run's config hash and data range (reproducibility). Every run logs `BACKTEST_RUN{period, folds, passed}`; a run that would grade on in-sample is a hard error (`BACKTEST_INSAMPLE_GRADE_BLOCKED`) — it cannot happen silently.

## 10. Store schema (DDL)

```sql
CREATE TABLE validation_report (
    report_id     TEXT PRIMARY KEY,
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
    fidelity_caveats JSONB NOT NULL
);
```
`guardrail_hash` in the report proves the run used the real limits — a report with a mismatched hash cannot gate live.

## 11. MCP contract

`acis_run_backtest(params)` (ACIS-08) triggers a run out-of-band; `acis_report(period)` returns a persisted `ValidationReport`. Neither can set live; live is gated on a `passed` report + human sign-off. Reports are read-only resources; the harness exposes no control over the live engine.

## 12. Error taxonomy

| Event | Handling |
|---|---|
| < 2 years data | run refused / `passed=False` with reason |
| single split (no walk-forward) | cannot pass; graded blocked |
| attempt to grade on in-sample | hard error `BACKTEST_INSAMPLE_GRADE_BLOCKED` |
| relaxed guardrails detected (hash mismatch) | report invalid; cannot gate live |
| NaN metric | NaN-safe; degenerate runs report worst-case, never a spurious pass |

## 13. Logic-flaw registry
- **C-BT-1 (no in-sample grading):** grader consumes only `out_of_sample`; type/flow test asserts in-sample metrics cannot reach the grader (master §13 hard rule).
- **C-BT-2 (walk-forward required):** `passed` requires ≥2 yr + >1 fold; test asserts a single-split run cannot pass.
- **C-BT-3 (real engine):** the harness drives ACIS-01…07 (not a reimplementation); test asserts the same layer classes are instantiated (e.g. a change in NVMA behaviour changes backtest results).
- **C-BT-4 (production guardrails):** `guardrail_hash` recorded + checked; a relaxed-limit run cannot gate live.
- **C-BT-5 (fidelity honesty, GAP-0001):** `fidelity_caveats` surfaced in the report; slippage/spread models documented; live still requires paper + practice account.
- **C-BT-6 (Decimal PnL):** metrics computed on Decimal PnL at accounting boundaries (F17); no float drift in the equity curve.

## 14. Test contract (postcondition-style)

**Unit:** metrics correct on synthetic PnL series (Sharpe/PF/drawdown/win-rate/positive-months/SPX-corr/avg-duration), NaN-safe; grader uses out-of-sample only (C-BT-1); single-split cannot pass (C-BT-2); guardrail-hash mismatch invalidates (C-BT-4).

**Integration:** a full walk-forward run over a synthetic ≥2-yr fixture drives the real engine end-to-end and produces a `ValidationReport` with populated out-of-sample + per-regime blocks and equity/drawdown artifacts; a deliberate NVMA change shifts backtest output (proving the real engine is exercised, C-BT-3); a run under relaxed limits is flagged invalid.

## 15. Integration gate

**The live gate:** phase 11 (live broker) is permitted only when a persisted `ValidationReport.passed == True` on ≥2-yr out-of-sample walk-forward **and** a human sign-off record exist; ACIS-08's `acis_set_mode(live)` checks both. This spec is the wall between paper and live (master §15). **Done-when (phase 10, master §15):** §14 harness green; the honesty guards are enforced in code, not just documented; never-report-in-sample proven by test.

## Changelog
- **1.0 (DRAFT)** — From master §13/§14/§15 + `ACIS_Agent_Prompt.md` §6/§9 + `KNOWN_GAPS.md` GAP-0001; the "never report in-sample" and "live needs out-of-sample pass + human sign-off" rules made code-enforced gates.
