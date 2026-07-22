# SPEC_AUDIT_EXTERNAL_PENDING.md — Lens 2 (external-referent) findings, phase-12 SPEC audit

**Auditor:** adversarial external-referent lens (Opus 4.8), launched cold per
`SPEC_AUDIT_BRIEF.md` v1.0 and `SPEC_CONSTITUTION.md` v0.3 (Tier 1).
**Date:** 2026-07-21. **Target:** `ACIS_SPEC.md` master v2.12 + LOCKED `specs/`
(esp. ACIS-07, ACIS-09, ACIS-12) + the guard-2 runbook `tests/backtest/OOS_VALIDATION.md`
and the code that realises the graded claims (`tests/backtest/metrics.py`,
`report.py`, `walk_forward.py`, `core/risk/monitor.py`).

## ATTESTATION (A4)
- **Fresh/cold context:** I was launched with no prior session state. I read the
  brief and constitution FIRST, then formed each attack from the spec's *claims +
  the code's observed behaviour*, treating the spec's justificatory prose and
  changelog rationales as untrusted framing (A9). I did not audit against the
  repo's own approving documents.
- I am a **finder, not a clearer** (A5). A clean line below is a recorded negative,
  never a sign-off. Every binding finding quotes a retrievable external passage (A6);
  anything weaker is marked `unconfirmed`.

### External sources consulted (URLs)
- Lo, A. (2002), *The Statistics of Sharpe Ratios*, Financial Analysts Journal —
  https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
  (also PDF: https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf)
- Moskowitz, Ooi, Pedersen (2012), *Time Series Momentum* — summary:
  https://foxholm.com/q/research/moskowitz-ooi-pedersen-time-series-momentum/ ;
  paper: https://www.sciencedirect.com/science/article/pii/S0304405X11002613
- Kupiec POF test — https://www.mathworks.com/help/risk/overview-of-var-backtesting.html
  and https://www.mathworks.com/help/risk/varbacktest.pof.html
- 2015 SNB de-peg magnitudes — https://www.nasdaq.com/articles/forex-usdchf-eurchf-plunge-after-shock-snb-move-2015-01-15 ,
  https://www.forex.com/en/news-and-analysis/happy-5-year-anniversary-to-snb-peg-removal/ ,
  https://www.forex.in.rs/usd-chf-15-january-2015/
- López de Prado, *Advances in Financial Machine Learning* (purged/embargo CV,
  Deflated Sharpe) — referent named by the runbook itself (`OOS_VALIDATION.md` ll.14–39).

---

## FINDINGS

### GAP-SP12E-01 — §14 Sharpe>1.5 bar exceeds the very literature the spec cites
- **Severity:** Medium · **Likelihood:** High · **Area:** master §14 / §5.6 / ACIS-09 / OOS_VALIDATION.md
- **Spec says:** the live gate requires **annual Sharpe > 1.5** out-of-sample
  (`ACIS_SPEC.md` §14 table; `report.py` `SHARPE_MIN = 1.5`), evaluated per account
  on its enabled universe. The ratified OOS plan sets that enabled universe to
  **two FX pairs, EUR/USD + USD/JPY** (`OOS_VALIDATION.md` l.22).
- **The world says:** the strongest, most-cited systematic-FX/futures edge — the
  one the spec itself adopts as its canon (§5.6 verified-benchmark law, "Moskowitz–
  Ooi–Pedersen 2012") — reaches ~1.0 Sharpe **only after diversifying across 58
  markets**. Quote: *"Combining the strategy across all 58 markets produced a
  portfolio with a Sharpe ratio (return per unit of risk) of about 1.0"*; *"Individual
  market strategies had Sharpe ratios around 0.3 to 0.5"*; *"the long-run Sharpe ratio
  of the U.S. stock market is roughly 0.4."*
  (https://foxholm.com/q/research/moskowitz-ooi-pedersen-time-series-momentum/).
- **Why this is a finding:** the §14 minimum (1.5) is **~50% above the diversified,
  58-market benchmark (~1.0)** the spec leans on, demanded on a **2-instrument,
  highly-correlated FX book** (EUR/USD and USD/JPY share the USD leg) net of the C8
  cost model. A bar set above what the cited literature achieves *with* broad
  breadth, on a book with almost none, is realistically clearable in-sample **only
  by overfitting** — precisely the §5.6 self-deception the honesty gates then reject
  out-of-sample. The likely real outcome is either (a) the system never clears the
  gate and never goes live, or (b) a "passing" OOS run is an overfit that slipped the
  ≥30-trade / >1-fold floors. This is not an argument to lower the guardrail — it is
  a warning that the *target* is out of calibration with the spec's own evidence base,
  and that a pass should be treated with extra suspicion (Deflated-Sharpe territory —
  see GAP-SP12E-03).
- **Justification:** the brief asks explicitly whether §14 levels are "realistic, or
  a number that only an overfit clears." The cited-literature ceiling (~1.0 with 58
  markets; 0.3–0.5 per market) answers it: 1.5 on 2 pairs is top-decile-of-industry
  and should be owner-reviewed as a *stretch* rather than a *minimum*, or the §14
  pass explicitly paired with a multiple-testing deflation before it can gate live.

### GAP-SP12E-02 — Sharpe annualised by the naïve iid √T rule; no autocorrelation correction
- **Severity:** Medium · **Likelihood:** High · **Area:** ACIS-09 `metrics.py::annual_sharpe`
- **Code does:** `annual_sharpe = (mean/sd) * math.sqrt(periods_per_year)` on daily
  equity returns with `periods_per_year = 252` (`metrics.py` l.81; `harness.py` l.89).
  This is the textbook **iid** square-root-of-time annualisation, applied with no
  serial-correlation adjustment.
- **The world says (Lo 2002, the standard reference on exactly this):**
  *"monthly Sharpe ratios cannot be annualized by multiplying by √12 except under
  very special circumstances"* and *"the annual Sharpe ratio for a hedge fund can be
  overstated by as much as 65 percent because of the presence of serial correlation
  in monthly returns"*
  (https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios).
- **Why this bites HERE specifically:** ACIS's flagship modules are **trend/momentum**
  (TSMOM, dual-EMA trend following) plus multi-bar holds up to 48 h. Trend returns
  are positively autocorrelated at the daily scale *within* trends, which is the sign
  of serial correlation that makes √252 **overstate** the annualised Sharpe. The bias
  lands directly on the §14 Sharpe>1.5 gate (GAP-SP12E-01), so the one metric most
  likely to be overstated is the one that decides live-enablement. The function's
  declared deviation (`metrics.py` ll.67–74) covers only the rf=0 choice — it does
  **not** declare the iid-annualisation assumption, which is the material one.
- **Justification:** an undeclared deviation from the standard method on a
  live-gating statistic. Fix path: either compute the Lo autocorrelation-corrected
  annualisation, or (minimum) add it to `declared_deviations` and surface the caveat
  in the report next to the Sharpe figure, so the grade is honest about the bias.

### GAP-SP12E-03 — The guard-2 runbook cites purged/embargo CV + Deflated Sharpe but neither is built
- **Severity:** Medium · **Likelihood:** High · **Area:** `OOS_VALIDATION.md` vs `walk_forward.py` / `report.py`
- **The runbook says (in the orienting read path — CLAUDE.md guard 2):** the plan is
  *"Grounded in the walk-forward / backtest-overfitting literature (López de Prado
  purged-CV & Deflated Sharpe…)"* and lists **"Adopted honesty enhancements (small
  ACIS-09 additions): (1) an embargo gap in `generate_folds`; (2) Deflated Sharpe +
  a logged trial-count in the report"** (`OOS_VALIDATION.md` ll.14–37). Its component
  table marks `walk_forward.py` and `report.py` **"✅ built + tested."**
- **The code says otherwise:**
  - `walk_forward.py::generate_folds` sets `test_start = train_end` with **zero gap**
    (l.43). There is **no embargo and no purge** anywhere in the file. Train and test
    are directly adjacent, so serial-correlation leakage across the boundary — the
    exact defect purge/embargo exists to remove — is **not** removed.
  - **Deflated Sharpe / trial-count exist nowhere in code.** A repo-wide search for
    `deflat|trial|DSR|PSR` returns only the docs (`OOS_VALIDATION.md`,
    `SPEC_AUDIT_BRIEF.md`, `TODO.md`) — never `report.py`. The `ValidationReport`
    dataclass has no `trial_count`/`deflated_sharpe` field; `grade_out_of_sample`
    applies **raw** `annual_sharpe > 1.5` with no multiple-testing deflation.
- **The world says (López de Prado, the cited referent):** purged K-fold + an embargo
  after each test set is required precisely because adjacent train/test folds leak
  through overlapping/serially-correlated observations, and the Deflated Sharpe Ratio
  discounts an observed Sharpe for the number of trials to defeat backtest selection
  bias. Citing these methods while shipping neither means the multiple-testing and
  boundary-leakage defences the citation promises are **absent at the gate.**
- **Justification:** dual-nature finding — (a) external: the cited method is not
  faithfully applied (an undeclared deviation from the referent the runbook names as
  its ground truth), and (b) read-path truth: a doc in the go-live evidence path
  asserts "built + tested" for machinery that does not exist. Either build the embargo
  + DSR, or correct the runbook to mark them TO-BUILD (they must exist before a §14
  pass can honestly gate live, given GAP-SP12E-01/02).

### GAP-SP12E-04 — `rolling_var_breach_rate` is named a "Kupiec POF backtest" but computes only the breach rate
- **Severity:** Low–Medium · **Likelihood:** High · **Area:** ACIS-09 `metrics.py` / master §16 naming law
- **Code does:** `rolling_var_breach_rate(...)` returns `breaches / days` — the
  observed exceedance fraction — and its docstring calls it *"(Kupiec POF backtest)"*
  (`metrics.py` ll.168–192). `var_breach_frequency` is likewise a bare fraction.
- **The world says:** Kupiec's POF is a **likelihood-ratio hypothesis test**, not a
  rate. *"The POF test is a likelihood ratio test proposed by Kupiec (1995)…"*; the
  statistic is `LR_POF = -2 log( ((1-α)^(T-n_f) α^(n_f)) / ((1-n_f/T)^(T-n_f)(n_f/T)^(n_f)) )`,
  *"asymptotically distributed as a chi-square distribution with 1 degree of freedom,"*
  and rejection follows from exceeding the χ²₁ critical value
  (https://www.mathworks.com/help/risk/overview-of-var-backtesting.html).
- **Why this is a finding:** the breach fraction is the *input* to Kupiec, not the
  Kupiec *test* — there is no LR statistic, no χ²₁ comparison, and no accept/reject.
  Labelling the fraction a "Kupiec POF backtest" is exactly the "a function wearing a
  canonical name it does not implement" defect the spec's own v2.11 time-base pass
  outlawed (`ACIS_SPEC.md` §16: *"no function may wear a canonical name it does not
  implement"*). A well-known trap: with a short OOS record even a badly-miscalibrated
  VaR can show a breach fraction "near 1%" by luck — only the LR test tells you whether
  the deviation is significant, which a bare rate cannot.
- **Justification:** rename to what it is (`var_breach_rate`) OR implement the actual
  LR_POF statistic + χ²₁ decision. Lower severity because VaR is not wired in-loop
  (GAP-0091b) and this is a report metric, but the naming law is binding.

### GAP-SP12E-05 — delta-normal + √t VaR is structurally blind to the fat tails the 3% cap implicitly bounds
- **Severity:** Low · **Likelihood:** Medium · **Area:** ACIS-07 `monitor.py::_var_pct`, guardrail `var_cap_pct 3.0`
- **Code does:** per-position **delta-normal** VaR, `z(0.99)·σ`, with σ scaled by
  `√(var_horizon_seconds / eval_cadence_s)` to a 1-day horizon (`monitor.py` ll.271–294).
  Both the Gaussian quantile and the √t scaling assume **iid normal** returns.
- **The world says:** FX daily returns are leptokurtic and jump-prone; a delta-normal
  1-day VaR cannot represent a gap. The 2015 SNB event is the canonical proof: USD/CHF
  fell **~14% on the day and ~27% intraday** (low 0.7462), *"a drop of 13.95% for the
  day"* (https://www.nasdaq.com/articles/forex-usdchf-eurchf-plunge-after-shock-snb-move-2015-01-15) —
  a >10-sigma Gaussian day, i.e. one a normal 1-day VaR assigns ≈0 probability. √t
  scaling further understates multi-period tail risk when jumps dominate.
- **Why only Low:** the spec does **not** rely on VaR for tail bounding — the scenario
  book + gap law (§8.5, ACIS-12) carry that load, and the VaR is explicitly labelled
  delta-normal and "not yet wired in-loop." The residual finding is narrower: (a) the
  **3% cap's calibration to a Gaussian 1-day horizon is unverified** against real FX
  kurtosis, and (b) the only empirical check of that calibration
  (`var_breach_frequency`, GAP-0103) lives in the backtest and is a bare rate, not a
  significance test (GAP-SP12E-04) — so a mis-calibrated cap could pass unremarked.
- **Justification:** record the Gaussian/√t assumption as a declared limitation of the
  VaR line and ensure the operational-referent audit (CLAUDE.md guard, live VaR-breach
  frequency vs the 1% level) uses the Kupiec LR test, not a bare rate, once live.

### GAP-SP12E-06 (unconfirmed) — SPX correlation aligns returns by index position, not by date
- **Severity:** Low · **Likelihood:** unknown · **Area:** ACIS-09 `metrics.py::spx_correlation`
- **Code does:** `spx_correlation` zips `returns` and `spx_returns` by **position**
  (`metrics.py` ll.125–139), truncating to the shorter. The §14 gate is SPX-corr < 0.25.
- **Concern:** if the strategy's daily-return series and the SPX daily-return series
  are not guaranteed date-aligned before the call (e.g. FX trades days SPX is closed,
  or vice-versa), positional zipping silently correlates mismatched dates and yields a
  meaningless (usually near-zero, thus *passing*) correlation — a false clear of the
  hard §14 diversification target.
- **Why unconfirmed:** I did not trace the construction of `spx_returns` at the call
  site, so I cannot show the misalignment is real (A6). Flagged for the author to
  verify the SPX series is date-joined to the equity series before correlation, and to
  add a fixture with an FX/SPX holiday mismatch. Not actioned as fact.

---

## HONEST NEGATIVES (referents checked, found faithful — first-class results, A6/A10)

- **VaR z-score is correct.** `_Z_99 = NormalDist().inv_cdf(0.99) ≈ 2.326`
  (`monitor.py` l.35) is the right one-tailed 1% quantile; matches the brief's
  z(0.99)=2.326. Faithful.
- **2015 CHF de-peg magnitude is defensible / conservative.** The scenario models
  `USD_CHF gap_pct: -35.0` as the worst-fill (`scenario_book.yaml` ll.19–31). Real
  event: USD/CHF closed **~-14%** on 2015-01-15 with an intraday low of **0.7462
  (~-27% from the ~1.02 open)**, and retail brokers filled stops materially worse in
  the vacuum (EUR/CHF, the actually-pegged pair, printed **-30% to -41%** across
  brokers). -35% sits inside the observed worst-fill band and is **conservative**
  relative to the daily close — the correct posture for a max-loss ceiling. The choice
  of USD/CHF (not EUR/CHF) is right: USD/CHF is in the enabled majors universe, EUR/CHF
  is not. The 7.5% ceiling arithmetic checks (20% clustered book × 35% = 7.0% NAV +
  headroom). Sources:
  https://www.nasdaq.com/articles/forex-usdchf-eurchf-plunge-after-shock-snb-move-2015-01-15 ,
  https://www.forex.com/en/news-and-analysis/happy-5-year-anniversary-to-snb-peg-removal/ .
  Faithful.
- **Hurst drift-invariance correction (v2.12) is correct about the world.** The spec
  retired "H>0.55 → trending" as a category error because R/S Hurst is drift-invariant
  (`ACIS_SPEC.md` §4 + changelog). This matches the statistic's real behaviour and
  narrows Hurst to the anti-persistence (mean-reversion) gate it can actually support.
  Faithful — the earlier external-referent catch was correctly internalised.
- **Standard metric definitions faithful:** `max_drawdown_pct` (peak-to-trough off
  the running peak, positive %), `profit_factor` (gross win / gross loss),
  `win_rate` (wins / trades, fraction), `positive_months_pct` (month-end > prior
  month-end, ×100 — units consistent with the >70.0 grader), `spx_correlation`
  (textbook Pearson). All NaN/degenerate-variance-safe toward 0.0 (never a spurious
  ∞/pass). Definitions match their names. (Alignment caveat separately: GAP-SP12E-06.)
- **Non-overlapping OOS folds enforced.** `generate_folds` rejects `step < test_window`
  (`walk_forward.py` ll.35–37), correctly preventing double-counting of overlapping
  OOS windows in the concatenated record — the right guard, faithfully implemented.
- **Duration carve-outs are honest, not indulgent.** Excluding TSMOM (multi-month by
  design) and MOMENTUM_SCALP (5–15 bars) from the 30min–48h band, reported separately
  (`metrics.py` ll.142–219, ACIS-09 C-BT-8), is a defensible metric-scope choice — a
  multi-month TSMOM genuinely should not be graded against a 48h ceiling. Faithful.

## Residual-risk note (A10)
The two structural risks this lens surfaces are (1) a **§14 Sharpe target above the
spec's own cited evidence base**, which turns any in-sample pass into a
multiple-testing suspect, and (2) the **defences against that exact suspicion
(embargo purge, Deflated Sharpe, a real Kupiec test) being cited but not built.**
Together they mean a future "PASSED" `ValidationReport` could be an overfit that the
present pipeline is not yet equipped to catch. None of this weakens a guardrail; all
of it concerns the *honesty of the live-enablement grade* — which is the one thing
guard 2 exists to protect. Findings bind only after author refutation per A6; the
`unconfirmed` item (SP12E-06) is not to be actioned as fact until reproduced.
