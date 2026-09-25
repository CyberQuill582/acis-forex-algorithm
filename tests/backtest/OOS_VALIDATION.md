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
train fold; the validation design is not an optimisation target. **Amended 2026-09-25 (R-1, owner-ratified; ACIS-09 v1.7):** the only legitimate selection is among the members of a declared search space, hashed and registered before the first look; the validation design is still not an optimisation target.

- **AMENDED 2026-09-25 (R-1 A5, R1-D5, owner-ratified): the research universe is 30 instruments.**
  - FX 16: EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF, EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/CHF, EUR/AUD, CHF/JPY, AUD/NZD, NZD/USD, CAD/JPY.
  - Metals: XAU, XAG, XCU. Indices: US500, US30, UK100, JP225, EU50, AUS200, GER40, US100. Energy: UKOIL, NATGAS, USOIL.
  - All are quoted by FTMO, with Dukascopy history from ≤ 2013; the owner confirms availability with `scripts/download_dukascopy_s3.py check` before onboarding.
  - **Held out and LOCKED (the salt is frozen now; re-salting after any real-data look is forbidden):** AUD/NZD, NZD/USD, CAD/JPY, XCU/USD, GER40, US100 and USOIL. They were drawn by sorting each class by `sha256("ACIS-R1-holdout-2026-09-25|" + symbol)` and holding out the first k (FX 3, metal 1, index 2, energy 1), with the 8 on-disk instruments forced into the explored set. They are never explored, graded once per assembled portfolio, residualised and kill-only. They are clean of the project's looks, not of the LLM's memory.
  - **Live eligibility per account:** an instrument is live-eligible on an account only if one minimum lot is ≤ its risk budget at |forecast| = 10 on that account (GAP-P12D-101). The rest stay research-only there.
  - **Breadth** is measured as effective breadth, IDM = √(N/(1+(N−1)ρ_P&L)), not as a count.
  - The 8-instrument universe below stays the on-disk tick set, forced explored.
- *(Superseded as the research universe:)* **Data:** `2012-01-01 → 2026-01-01` (14 yr). **Enabled universe RATIFIED
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
- **AMENDED 2026-09-25 (R-1 A1, R1-D1/D6, owner-ratified; ACIS-09 v1.7 C-BT-11 v2).**
  - **Walk-forward (development): EXPANDING train / 1-yr test / 1-yr step.** A fixed family (no training step) needs only its longest lookback warm; a family with a training step needs ≥ 2 years first.
  - **The embargo** is ≥ max(7 days, the 95th percentile of the rule set's holding period, measured on the lab).
  - **Development is ONE tier (2012–2023) for fixed families.** The E (2012–19) / V (2020–23) split is used only for explored families.
  - The rolling plan below is superseded, kept for the record.
- *(Superseded:)* **Walk-forward (development):** **2-yr train / 1-yr test / 1-yr step**, with a
  **~1-week embargo** between train and test (purge boundary leakage; embargo ≥ the
  48 h max-hold). Over 2012→2024 this is **~10 rolling folds, ~10 yr concatenated
  OOS** — far above the §14 ≥2-yr / >1-fold / ≥30-trade floors.
- **Locked final holdout:** **2024-01-01 → 2026-01-01 (2 yr), UNTOUCHED** by any
  fold, tuning, or design decision until the design is frozen — then graded **once**
  as the meta-overfit confirmation (a "double out-of-sample" check). The driver
  physically guards it (a holdout guard) until that single final grade.
- **Honesty enhancements — BUILT 2026-09-15** (spec audit GAP-SP12E-03, ACIS-09 C-BT-11):
  (1) `generate_folds(embargo=…)` leaves the gap, and `Backtest.run` refuses a fold whose
  real train→test data gap is shorter than the max hold; (2) every report carries
  `trial_count` and the **Deflated Sharpe** (`deflated_sharpe.py`, pinned to Bailey & López
  de Prado's own numerical example) — pass the per-period Sharpe ratio of every
  configuration tried as `trial_sharpes`. **Gate (owner-ratified 2026-09-15, GAP-P12D-16):**
  `passed` requires DSR ≥ 0.95 over ≥ 2 trials; the trials are the ACIS-11 attempt-registry
  configurations for the strategy family plus each fold's champion. **Deferred:**
  Combinatorial Purged CV (the spec mandates walk-forward; CPCV is a bigger §13
  change — documented future option, not built now).

### Data acquisition (master §13 v2.13 — built + tested 2026-09-11, downloads await the owner)

**Primary = Dukascopy tick, via its official S3 archive** (owner decision 2026-09-11). The
anonymous public feed is per-IP rate-limited (≈ one instrument-day before a >40-min
penalty) and bans datacenter IPs, so it is retired (`archive/download_dukascopy_publicfeed.js`).
**Cross-check = HistData** (replaced TrueFX, whose free history was withdrawn — GAP-P12D-02).
Tick resolution with bid + ask throughout.

- **Primary downloader** [`scripts/download_dukascopy_s3.py`](../../scripts/download_dukascopy_s3.py):
  `aws s3 sync` does the transfer (credentials, retries, resume); the script runs newest year
  first across all 8 instruments and **verifies every day file** with
  [`bi5.py`](bi5.py) — LZMA, whole 20-byte records, ticks inside their day, and a price
  envelope that turns Dukascopy's "wrong scale fails silently" into an error. A verified
  instrument-year gets a `SYNCED` marker: the reader treats a missing day inside a SYNCED
  year as a holiday and an unmarked year as not downloaded. `coverage.json` lists missing
  weekdays for review. The decoder is pinned to real Dukascopy bytes (`test_bi5.py`).
  **Owner setup, once:** AWS account + an access key + AWS CLI v2 + `aws configure` (the agent
  never sees keys); then `python scripts\download_dukascopy_s3.py check` prints the identity,
  confirms all 8 symbols exist, prices the download, and probes the XAU scale.
- **Cross-check downloader** [`scripts/download_histdata.py`](../../scripts/download_histdata.py):
  1,344 month zips, each fully verified (`testzip()`, every row parsed, ticks inside the
  month; sha256 + anomaly counts + HistData's gap report in `manifest.jsonl`); stored as
  published; HistData-clock timestamps (Frankfurt − 6 h — NOT the documented fixed EST, GAP-P12D-13) converted by the reader. Tested: `test_download_histdata.py`.
- **Supervisor** [`scripts/dl_supervisor.ps1`](../../scripts/dl_supervisor.ps1) `-Job s3|histdata`:
  single instance per job, keeps the PC awake while running, restarts on any exit; a
  scheduled task (at logon + every 30 min) resumes after reboots. Shared plumbing:
  [`scripts/dl_common.py`](../../scripts/dl_common.py).
- **Watch:** `data/<dukascopy|histdata>/status.json`, `download.log`, `supervisor.log`; done
  when that folder's `COMPLETE` exists.
- **Macro inputs** (done): `scripts/download_macro.py` → SPX + overnight rates from the issuing
  banks → `financing.py`. **Still to build:** the historical event calendar (GAP-P12D-03).

Before any §14 pass is presented: `scripts/run_data_validation.py` — ECB reference rates, the EUR/GBP triangle,
the market's clock marks and sampled gold vs HistData (C-BT-9, GAP-P12D-14) — with every flag explained. Then: streaming evolve-driver (per-fold, never the full history in RAM) feeding the embargoed
folds, `trial_sharpes` and the downloaded SPX closes as `spx_closes` (date-joined — GAP-SP12E-06) → holdout guard.
`data/` is git-ignored.

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
**≥30 trades** (P11I-07), a **Deflated Sharpe ≥ 0.95 over ≥ 2 recorded trials**
(C-BT-11, GAP-P12D-16), **empty `rule_violations`** (§9.5, C-BT-7), and a
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
