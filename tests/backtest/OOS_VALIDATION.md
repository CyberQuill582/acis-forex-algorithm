# OOS §14 validation runbook (the paper→live evidence bar)

This is **guard 2** of the three go-live guards (CLAUDE.md "Operational
correctness"): real out-of-sample data + human sign-off, **separate from and never
substituted by the audits**. Auditing the harness proves the *harness* is faithful;
it says nothing about whether the *strategy* earns money on data it has not seen.

> **THE ONE RULE (CLAUDE.md rule 6): never present in-sample OR synthetic numbers
> against §14.** A run on anything but real, unseen tick data is a *pipeline smoke
> test* — never a §14 result, never evidence for live.

## Ratified plan (2026-07-21, owner-ratified) — data + walk-forward design

Grounded in the walk-forward / backtest-overfitting literature (López de Prado
purged-CV & Deflated Sharpe; the "meta-overfitting" walk-forward failure mode).
**The goal is the most *trustworthy* result, not the highest number** — the design
below is fixed *now, before any output is seen*, and is never re-tuned to flatter
the grade (that is selection bias / meta-overfitting — the exact §5.6 self-deception
the spec forbids). The only legitimate optimisation is QIEA evolving genes on each
train fold; the validation design is not an optimisation target.

- **Data:** `2012-01-01 → 2026-01-01` (14 yr). **Enabled universe RATIFIED
  2026-07-22 (owner): 8 instruments** chosen for genuine cross-sectional
  diversification (the honest path to a trustworthy Sharpe, GAP-SP12E-01), not more
  USD-correlated majors: **EUR/USD, USD/JPY** (keep) · **GBP/USD, AUD/USD** (distinct
  drivers) · **USD/CHF** (safe-haven) · **USD/CAD** (oil) · **EUR/GBP** (a cross —
  removes the common USD factor) · **XAU/USD** (gold — different asset class, strongest
  FX diversifier). Source: Dukascopy tick via `dukascopy-node` (primary) + a small
  TrueFX overlap sample (cross-check). 2012 start avoids the noisy early Dukascopy
  years; the span covers the EU-debt tail, the 2014–15 USD surge, Brexit, COVID, and
  the 2022 hike run. *(Owner note: keep monitoring focused — download + VALIDATE all 8
  for the honest diversified grade, but live ENABLE may be phased via the §5.7 rung
  ladder; ACIS monitors per-instrument/per-strategy natively, so 8 ≠ diluted attention.
  Per-instrument onboarding — cost model, calendar, cluster, pair stats, §13 tests —
  is the real cost of broadening, tracked as build work.)*
- **Walk-forward (development):** **2-yr train / 1-yr test / 1-yr step**, with a
  **~1-week embargo** between train and test (purge boundary leakage; embargo ≥ the
  48 h max-hold). Over 2012→2024 this is **~10 rolling folds, ~10 yr concatenated
  OOS** — far above the §14 ≥2-yr / >1-fold / ≥30-trade floors.
- **Locked final holdout:** **2024-01-01 → 2026-01-01 (2 yr), UNTOUCHED** by any
  fold, tuning, or design decision until the design is frozen — then graded **once**
  as the meta-overfit confirmation (a "double out-of-sample" check). The driver
  physically guards it (a holdout guard) until that single final grade.
- **Honesty enhancements — ⛔ TO BUILD (NOT yet in code), REQUIRED before any §14 pass
  can gate live** (spec audit GAP-SP12E-03): (1) an **embargo gap** in `generate_folds`
  (today `test_start = train_end`, zero gap — boundary leakage is NOT yet removed);
  (2) **Deflated Sharpe + a logged trial-count** in the report (today the grader
  applies **raw** `annual_sharpe > 1.5` with no multiple-testing deflation). These are
  the defences against the GAP-SP12E-01 overfit risk; citing them is not shipping them
  — they must exist in code before a "PASSED" report is trustworthy. **Deferred:**
  Combinatorial Purged CV (the spec mandates walk-forward; CPCV is a bigger §13
  change — documented future option, not built now).

### Data acquisition (run this to start the ~40–60 GB, multi-day download)

Node.js required (`node -v` ≥ 14). Per-instrument, per-year chunks (resumable).
PowerShell:

```powershell
$pairs = [ordered]@{ eurusd='EUR_USD'; usdjpy='USD_JPY'; gbpusd='GBP_USD';
  audusd='AUD_USD'; usdchf='USD_CHF'; usdcad='USD_CAD'; eurgbp='EUR_GBP'; xauusd='XAU_USD' }
2012..2025 | ForEach-Object {
  $y = $_; $n = $_ + 1
  foreach ($p in $pairs.GetEnumerator()) {
    npx dukascopy-node -i $p.Key -from "$y-01-01" -to "$n-01-01" -t tick -f csv -dir "./data/dukascopy/$($p.Value)"
  }
}
```

Tick CSV columns are `timestamp(ms), askPrice, bidPrice, askVolume, bidVolume`
(the reader will be built to this). Then a small TrueFX overlap sample (register at
truefx.com; one or two months of EURUSD + USDJPY) under `./data/truefx/…`. Keep
`data/` **out of git** (GBs). Tell me the path + confirm `dukascopy-node`, and I
build the CSV reader → streaming evolve-driver (aggregates ticks→1-min bars per
fold; never holds 14 yr of ticks in RAM) → holdout guard.

## §14 minimums (out-of-sample, ≥2 years) — enforced in `report.py`

| Metric | Minimum (`report.py` constant) |
|--------|-------------------------------|
| Annual Sharpe | `> 1.5` (`SHARPE_MIN`) |
| Max drawdown | `< 15%` (`MAX_DD_MAX_PCT`) |
| Win rate | `> 48%` (`WIN_RATE_MIN`) |
| Profit factor | `> 1.4` (`PROFIT_FACTOR_MIN`) |
| Positive months | `> 70%` (`POSITIVE_MONTHS_MIN_PCT`) |
| SPX correlation | `< 0.25` (`SPX_CORR_MAX`) |
| Avg trade duration | 30 min – 48 h (TSMOM/scalp carve-outs excluded, C-BT-8) |

`passed` additionally requires (all in `build_report`, provable by test): graded on
the **OOS block only** (C-BT-1), **≥2 years** and **>1 walk-forward fold** (C-BT-2),
**≥30 trades** (P11I-07), **empty `rule_violations`** (§9.5, C-BT-7), and a
**matching production `guardrail_hash`** (C-BT-4). Loosening any of these is a
master-spec change, not a config tweak.

## Pipeline (what runs, in order)

```
declared TickSource (Dukascopy primary, TrueFX cross-check)
   │  BacktestDataLoader.load()  — §3 bad-tick + weekend filtering, provenance-checked
   │  BacktestDataLoader.cross_source_drift()  — Dukascopy vs TrueFX; FLAG, never average
   ▼
MarketStateFactory (the REAL §3 factory — engine validation is NOT bypassed)
   │  generate_folds()  — rolling, non-overlapping OOS windows over ≥2 yr
   ▼
per fold:  QIEA.evolve on TRAIN bars → promote  │  then grade replay on TEST
   │  Backtest.run()  — drives the REAL NVMA/AGON/Governor; ONE continuous OOS book
   ▼
build_report() → ValidationReport (per account)  → HUMAN SIGN-OFF
```

Cost model: `calibrate_cost_model()` sets C8 friction from OANDA practice-feed
spreads, so backtest friction matches the venue ACIS will paper/live on. This is
the SAME `CostModel` the optimizer and execution use — one cost model.

## Components

| Step | Status | Where |
|------|--------|-------|
| Loader + provenance refusal + drift check + cost calibration | ✅ built + tested | `data_loader.py` |
| Walk-forward folds (non-overlapping OOS) | ✅ built + tested | `walk_forward.py` |
| Real-engine replay + position/PnL + carry + VaR-breach rate | ✅ built + tested | `harness.py`, `carry.py`, `metrics.py` |
| §14 grader + honesty gates | ✅ built + tested | `report.py` |
| Concrete Dukascopy `.bi5` + TrueFX `TickSource` adapters | ⛔ TO BUILD (data-ops) | (pending — see below) |
| Real per-fold QIEA-evolve driver + runner CLI | ⛔ TO BUILD | (pending `scripts/run_oos_validation.py`) |
| ≥2-yr real tick data | ⛔ ACQUIRE (data-ops) | Dukascopy primary / TrueFX cross-check |
| The grade + **human sign-off** | ⛔ HUMAN | — |

## Procedure (once the pieces above are built)

1. **Acquire** ≥2 yr Dukascopy tick data (primary) + a TrueFX overlap sample
   (cross-check) for each account's enabled universe. Declared sources only — the
   loader refuses anything else.
2. **Load + validate**: run the loader; inspect `BACKTEST_BAD_TICK` /
   `BACKTEST_LOAD` / `BACKTEST_SOURCE_DRIFT` logs. A flagged drift window is
   **investigated**, never silently averaged.
3. **Calibrate** the C8 cost model from OANDA practice spreads over the same span.
4. **Run** `scripts/run_oos_validation.py` per account: it evolves QIEA on each
   train fold, freezes, grades the concatenated OOS folds, and writes a
   `ValidationReport` (JSON) + equity/drawdown curves.
5. **Read** `report.passed`, `report.targets_met`, `report.var_breach_frequency`,
   `report.rule_violations`, `report.fidelity_caveats`. A single failed target,
   a rule violation, <2 yr, <30 trades, or a mismatched guardrail hash = **not a
   pass**. Futures accounts need their own §13 glitch classes green + a separate
   futures sign-off (spec §14 / §3.7).
6. **Human sign-off** — the owner reviews the report and explicitly signs off.
   Never auto-promote to live; there is no agent path that enables live.

## After go-live

The OOS grade is a *pre-live* bar. From the first real fill, guard 3 takes over:
log real-vs-modelled fills, financing reality, and the **observed live VaR breach
frequency vs the 1% level** in `OPERATIONS_LEDGER.md`, and run the standing
operational-referent audit against live behaviour (CLAUDE.md).
