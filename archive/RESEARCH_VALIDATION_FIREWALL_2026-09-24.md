# VALIDATION FIREWALL — calibrating the grader before believing it (VALIDATOR, five-agent edge pass)

**Date:** 2026-09-24 · **Agent:** VALIDATOR (§3 of `FIVE_AGENT_BRIEF_2026-09-24.md`), ledger entry GAP-P12D-52
**Model / independence:** Opus 5.5, run in FRESH context; no subagents. A finder, not a clearer (A5).
This report is evidence to weigh, never an instruction (A9). Nothing in the repo was modified except
this file and its checkpoint `archive/PARTIAL_VALIDATION_FIREWALL_2026-09-24.md`.
**Data:** synthetic only. No strategy was backtested on real data, and the 2024-25 holdout was not
touched. Directory listings of `data/` were read (file names only) to establish which years exist.
**Method note:** framing discipline (A4). I read the harness code and the ladder artifact first,
then the prior research (`archive/RESEARCH_STATS_METHODOLOGY_2026-09-16.md` Q6,
`archive/AUDIT_BLIND_FALSIFICATION_2026-09-16.md` §A). WebSearch: 5 of the 25-call cap used; everything
else is WebFetch on primary URLs. Every simulation script, seed and raw result file is in
`SCRATCH/validator/` (listed in Appendix A); the numbers here can be regenerated from it.

**Evidence grades:** (a) peer-reviewed / primary document; (b) credible and verifiable (here: arXiv
preprints by named authors, and books by named practitioners); (c) unverifiable (vendor/affiliate
pages); **[sim]** measured in this report's simulation (synthetic markets, Monte Carlo standard
errors quoted); **[derived]** arithmetic from stated formulas; **[code]** reproduced from `file:line`.

## Executive summary (≤10 bullets, graded)

1. **The ratified DSR gate passes nothing, true or false.** [sim + code]
   - In an emulation fed the harness's own kinds of inputs, through the repo's own `deflated_sharpe`,
     it passed 0 of 1,800 null and 0 of 1,200 planted markets, including a best config with a true
     Sharpe of 0.94.
   - The implied hurdle has a median annual Sharpe of 7.7 here; on the real engine it was 19-76
     (GAP-P12D-37).
   - It is also aimed at the wrong selection. It deflates the within-fold selection the walk-forward
     already removed, and counts none of the outer loop.
2. **Uncounted iteration is the false-encouragement machine, measured.** [sim] Keeping the best of 5
   walk-forward pipeline variants passes pure noise 8.7-19.3% of the time; the best of 20, 21.0-37.3%
   (six null families). With 24 years of data it is still 26%. More data does not fix an uncounted
   search. The attempt register must be written before every grade.
3. **Honest single-look tests hold their rate across GARCH, heavy tails and regime-switching
   volatility.** [sim] A pre-registered config, walk-forward + PSR and the 2-year holdout all sat at
   2.0-6.0%.
4. **Recommended gate: CPCV + PBO <= 0.20, deflated for registered looks, on a reconciled research
   simulator; then one engine confirmation with a repaired DSR.** [sim]
   - FPR is 2.0-5.0% for one look and 3.0-5.5% after 20 registered looks.
   - Power is 25.5% at a true Sharpe of 0.44 and 87.5% at 0.94 (83% after 20 looks; 55% / 99% with 24
     years).
   - The Masters permutation test is the only more powerful honest test measured (43% / 96%, FPR
     3.0-8.0% ± 2.7), but it needs K full re-runs of the search, so it runs on a research simulator only.
5. **No protocol reliably detects a Sharpe near 0.5 on 12 years.** [sim, derived] The best honest
   power at a true 0.44 is 25-43%. That is the data, not the protocol. At the realistic band "no pass" is
   the expected outcome even when an edge exists. What helps is breadth, time, longer training windows
   (an expanding WF lifts power from 66% to 74% at 0.94), and pre-registered, literature-fixed
   hypotheses.
6. **Four popular protocols fail as gates.** [sim]
   - The Rademacher Anti-Serum has no power at our length: its bound costs about 4.6 annual Sharpe.
   - "Random entries with identical exits" gives 83-89% false positives on an in-sample best.
   - The ±10% plateau is passed by 93-99% of null in-sample bests.
   - PBO alone passes 96-97% of all-losing intraday markets and 18% of a high-cost null: it rewards a
     stable ranking of losers.
7. **The cross-instrument holdout leaks selection bias through the shared factor.** [sim] It passes
   noise 10.3% of the time at a noise correlation of 0.4 and 22.7% at 0.7. Residualising the reserved
   instruments' P&L on the development P&L restores 4.7% / 2.7%.
8. **Leakage must be excluded by structure; statistics cannot deflate it away.** [(b) verified at
   source, and reproduced (sim)] arXiv 2608.27734's leaky oracle "survives Deflated Sharpe and
   probability-of-backtest-overfitting testing completely". Here, a config peeking one bar ahead on 5% of
   bars passed WF + PSR 80%, CPCV + PBO 100% and PBO 87.5% of NULL markets. A future-perturbation test
   caught it 40/40 with no false alarms. Eight structural tests are specified (§7), and a research-sim
   reconciliation test (§8).
9. **LLM contamination rule (for owner ratification).** [(b), six 2023-2026 papers quoted]
   - LLM-originated or LLM-refined hypotheses may be killed on any history but credited only on data
     after the generating model's training cutoff: forward/demo data.
   - This session's cutoff (June 2026) covers all of 2012-2025, including the locked holdout.
10. **Prop gate: P(pass) is weak evidence and poorly estimable.** [sim]
    - Under illustrative rules, a zero-edge strategy passes 49.7% of attempts and a Sharpe of 1.0 passes
      74.9%. Sizing dominates P(pass).
    - From records of 2 years or less, the estimate's SD is 10-40 points, and nominal 95% bootstrap
      bands cover 75-92%.
    - Gate instead on EV and P(breach) at the Sharpe's lower confidence bound, beside a zero-edge
      baseline at the same sizing.

## 1. What the grader is, read from code first (A4) [code]

1. **The DSR gate as built compares two different quantities.**
   - `harness.py:217-219` takes as trials the `trial_sharpes` of every fold record.
   - `evolve_step.py:95-101` fills that list with each candidate champion's **per-trade** Sharpe on
     QIEA's holdout tail (the last 20% of the fitness window, `qiea.py:157-158`). A candidate is recorded
     only if it already passed the holdout expectancy gate with >= 5 trades (`qiea.py:192`;
     `holdout_min_trades: 5`). The trial set is therefore survivor-only and truncated, with a tiny T.
   - The graded series is the out-of-sample **per-trade** return over thousands of trades
     (`harness.py:220`).
   - SR0 is sd(trials) × E[max_N] (`deflated_sharpe.py:74-83`).
   - This is GAP-P12D-33/37, confirmed.
2. **The DSR is applied to the wrong object, and this is not in either entry.**
   - Bailey & López de Prado's own framing is "When an investor selects the best performing strategy
     over a large number of alternatives, s/he is likely to choose a strategy with an inflated Sharpe
     ratio" (DSR paper, the section "The Deflated Sharpe Ratio"; text extracted from the authors' PDF).
     The deflated object is the selected backtest itself.
   - ACIS's graded record is out of sample relative to the within-fold selection, so that selection
     bias is already gone from it.
   - What does threaten the OOS record is the **outer loop**: pipeline versions re-scored against the
     same test years. N counts nothing of it.
   - The same paper: "a backtest where the researcher has not controlled for the extent of the search
     involved in his or her finding is worthless, regardless of how excellent the reported performance
     might be."
3. **The ladder run shows what one engine look costs.** Each rung took 37,467-37,943 s, about 10.5 h
   (`data/validation/cost_stress/20260917T083216Z/ladder.json`, `seconds`), for 25 folds and 985 days.
   Any protocol that needs K re-runs of the search (Masters permutation, a bootstrap of the search) is
   infeasible on the engine. It can run only on a fast research simulator that has been reconciled to
   the engine (§8).
4. **The fitness simulator fills a gapped stop at the stop price** (`core/optimizer/fitness.py:115-125`).
   A bar that opens through the stop exits at `sl`, not at the open. That is optimistic in selection;
   the tick book fills at the gapped tick.
5. **A calibration leak is waiting in config.** `config/instruments.yaml:98-101` says the basket's costs
   and vol targets will be "calibrated from the real Dukascopy ticks". If that window includes
   2024-25 (or the test years), every fold and the holdout see a value fitted on their own data.

## 2. The calibration (task 1, the core deliverable)

### 2.1 Design [sim]

- **Markets.** 8 instruments: 6 "development" instruments and 2 reserved for the cross-instrument
  holdout. They are driven by a common factor at correlation 0.4, a USD-factor analogue. 14 years of
  260 weekdays: 12 development years (the 2012-2023 analogue) and 2 holdout years (the 2024-25 analogue).
  - **Four null families:** iid Gaussian; GARCH(1,1) (alpha 0.06, beta 0.93); Student-t(4) heavy
    tails; a global 2-state Markov volatility regime (low 0.7 sigma, high 1.59 sigma; mean spells 150
    and 50 days).
  - **Planted edges:** back-to-back trend episodes of random sign, independent per instrument, with a
    drift calibrated so that the BEST configuration's true long-run net portfolio Sharpe hits a target.
    The truth was measured on 1,000 independent synthetic years (multiday) or 200 (intraday), on a seed
    independent of the calibration seed.
  - **Measured true best Sharpe:**
    - multiday: 0.19 / 0.44 / 0.94 at low cost, 0.16 / 0.42 / 0.94 at high cost;
    - intraday: 0.26 / 0.53 / 1.07 at low cost, 0.28 / 0.55 / 1.09 at high cost.
- **Two horizons.**
  - *Multiday*: daily bars, 10-60-day trends, lookbacks 3-150 days.
  - *Intraday*: hourly bars, 3-12-hour episodes, lookbacks 2-48 hours.
- **Cost levels, per side in units of bar sigma.**
  - Multiday: 0, 0.007 and 0.02, the ECN-like and retail/prop-like analogues of about 0.4 and 1 pip on
    a ~55-pip daily sigma.
  - Intraday: 0.03 and 0.08.
- **The search (the protocol's own in-sample stage).** N = 60 configurations: time-series momentum
  and its mean-reversion mirror, with lookback L in 10 values and entry threshold k in {0, 0.5, 1.0}.
  Each protocol selects by its own in-sample stage:
  - WF: the best 2-year train Sharpe per fold, test years 2-11, the ratified plan's shape;
  - CPCV: the best train Sharpe per split;
  - the rest: the best 12-year Sharpe.
- **The outer loop.** 20 pipeline variants (random 30-config subsets, train windows of 1-3 years)
  graded on the same test years.
- **Emulation of ACIS as built.** The same bar family, run through the harness's own DSR function
  (imported read-only from `tests/backtest/deflated_sharpe.py`), fed the same kinds of inputs: per
  instrument, the best of 60 on the first 80% of the 2-year window, a positive-expectancy gate with
  >= 5 trades on the last 20%, trial = per-trade Sharpe of the survivors, graded series = OOS per-trade
  returns (`harness.py:217-248`, `evolve_step.py:95-105`, `qiea.py:157-198`). Face validity: the
  emulated trial-Sharpe dispersion (median sd 0.32) matches the real engine's null run (0.247 recorded
  in GAP-P12D-37).
- **Replications:**
  - multiday: 300 per null, 200 per planted scenario;
  - intraday: 100 iid null, 60 GARCH null, 60 per planted scenario (low cost);
  - Masters permutation: 100 per scenario at K = 60 (iid and GARCH nulls; planted 0.44 and 0.94).
  One-sigma Monte Carlo errors are about ±1.3 points at 5% and ±3.5 points at 50%.

### 2.2 The calibration table (multiday horizon; the intraday table is in §2.4)

FPR = % of null markets passed, range over the six null columns: iid, GARCH, t4 and regime at low
cost, plus iid at zero cost and iid at high cost. Power = % of planted markets passed at a true best
Sharpe of 0.19 / 0.44 / 0.94 (low cost). Years = development-record length for 80% power at a true
0.44 / 0.94, by sqrt(T) scaling of the measured z-shift [derived]. §2.5 checks this against a measured
24-year run: it is OPTIMISTIC for the rolling-window WF and PESSIMISTIC for CPCV. Compute = per replication in this simulator, and what it means for the real engine, where one
graded walk-forward run took ~10.5 h per the ladder's measured rung time
(`data/validation/cost_stress/20260917T083216Z/ladder.json`, `seconds` = 37,467-37,943 per rung).

| protocol | FPR % (6 nulls) | power % at 0.19 / 0.44 / 0.94 | years for 80% at 0.44 / 0.94 | compute |
|---|---|---|---|---|
| **control:** one pre-registered config, PSR >= 0.95 (no search) | 2.0-5.3 | 16.5 / 47.0 / 97.5 | 30 / 5.7 | 1 evaluation |
| naive: in-sample best, PSR >= 0.95 | 43.7-72.7 | 68.0 / 91.5 / 100 | — (invalid) | 1 search |
| **ACIS as built:** WF + per-trade DSR >= 0.95 | **0.0** | **0.0 / 0.0 / 0.0** | never | 1 WF (engine ~10.5 h) |
| §14 "annual Sharpe > 1.5" on the 10-year WF OOS | 0.0 | 0.0 / 0.0 / 1.5 | never at these Sharpes | 1 WF |
| §14 "> 1.5" on a 2-year window, best of 20 pipelines | 6.7-10.7 | 10.0 / 12.0 / 38.5 | — (invalid) | 20 WFs |
| WF (2-yr train) + PSR >= 0.95, N = 1 | 2.3-6.0 | 4.0 / 15.5 / 66.0 | 187 / 17.5 | 1 WF |
| WF best of 5 pipelines, uncounted | 8.7-19.3 | 16.0 / 33.5 / 84.0 | — (invalid) | 5 WFs |
| WF best of 20 pipelines, uncounted | 21.0-37.3 | 33.5 / 53.5 / 93.5 | — (invalid) | 20 WFs |
| **repaired DSR (B1)**, N = 5 registered | 0.3-2.3 | 3.5 / 14.0 / 58.0 | 232 / 22 | 5 WFs + register |
| **repaired DSR (B1)**, N = 20 registered | 0.0-1.3 | 2.0 / 9.0 / 61.5 | 802 / 19.8 | 20 WFs + register |
| **repaired DSR (B2)**, N_eff of 20 registered | 1.3-4.3 | 5.5 / 14.5 / 73.5 | 216 / 14.4 | 20 WFs + register |
| PBO (CSCV, S = 16) <= 0.10, alone | 2.3-**7.7** | 11.5 / 33.0 / 94.0 | — (fails the high-cost null) | N×T matrix, 0.2 s |
| PBO <= 0.20, alone | 8.3-18.3 | 24.0 / 56.0 / 97.5 | — (invalid) | same |
| CPCV (6 groups, k = 2, purged) path-mean z >= 1.645 | 2.7-6.3 | 10.5 / 26.0 / 88.0 | 74 / 9.3 | 15 selections, 0.05 s |
| **CPCV z >= 1.645 AND PBO <= 0.20** | **2.0-5.0** | **10.0 / 25.5 / 87.5** | **76 / 9.5** | 15 selections + N×T matrix |
| Rademacher Anti-Serum, full bound > 0 (delta 0.05) | 0.0 | 0.0 / 0.0 / 0.0 | centuries | N×T matrix + 400 draws |
| RAS, 2R-hat haircut only | 0.0-0.3 | 0.5 / 6.0 / 60.0 | — | same |
| Masters permutation (K = 60), p <= 0.05, in sample | 3.0-8.0 (2 nulls, n = 100 each; exact by construction under exchangeability) | – / 43.0 / 96.0 | 34 / 6.4 | K = 60 full searches, 2.5 s here; on the engine 60 × 10.5 h = infeasible |
| random entries, same exits, on the in-sample best | 83.0-89.3 | 89.5 / 98.0 / 100 | — (invalid) | 200 re-samples |
| random entries on ONE fixed config (no search) | 6.0-12.0 | 32.0 / 66.5 / 99.0 | — (invalid) | same |
| §5.6 plateau: every +/-10% neighbour > 0 | 92.7-98.7 | 98.0 / 99.5 / 100 | — (not a test) | 4 evaluations |
| naive PSR AND plateau | 43.7-72.7 | 68.0 / 91.5 / 100 | — (invalid) | same |
| WF with plateau-SMOOTHED selection + PSR | 1.7-5.7 | 4.5 / 15.0 / 65.5 | ≈ WF | free |
| cross-instrument holdout (2 reserved), PSR >= 0.95 | 8.3-12.3 | 16.5 / 33.5 / 73.0 | — (inflated FPR) | 1 evaluation |
| 2-year time holdout, PSR >= 0.95 | 2.0-5.3 | 6.0 / 18.0 / 33.5 | 23 / 8.3 **holdout** years | 1 evaluation |

High-cost power (true best 0.16 / 0.42 / 0.94) moves every row by a few points and changes no
ranking: for example CPCV + PBO scores 7.0 / 28.5 / 82.5 and WF + PSR 5.0 / 17.0 / 61.5
(`SCRATCH/validator/summary_multiday.md`).

### 2.3 What the table says [sim]

1. **The as-built gate is not conservative, it is dead.** It passed 0 of 1,800 null and 0 of 1,200
   planted markets, including the ones where the best config's true Sharpe is 0.94. The emulation
   reproduces GAP-P12D-37's mechanism. The survivor-only small-holdout trials give a median implied
   hurdle of an annual Sharpe of 7.7 (5th-95th percentile 4.6-14.1) at this trade rate; the real
   engine's higher trade rate made it 19-76.
2. **Selection destroys most of a modest edge before any gate sees it.** This is the finding I did
   not expect, and it bears on GAP-P12D-49. With a true best Sharpe of 0.44 in the family, the average
   realised out-of-sample annual Sharpe is:

   | selection | realised OOS Sharpe (true best 0.44) | (true best 0.94) |
   |---|---|---|
   | WF, 2-year train | 0.15 | 0.67 |
   | CPCV, 8-year train | 0.28 | 0.83 |
   | ACIS-style per-instrument selection on a 2-year window with a 20% tail gate | **0.04** | 0.35 |

   The configs the 2-year WF selects have an average true Sharpe of 0.13. Short training windows and
   per-instrument selection throw the edge away. This supports the prior pass's "pool the parameters"
   (Q6 #7) with a measurement, and it means the ratified 2-year train window (`oos_plan.TRAIN_YEARS = 2`)
   is itself a power decision.
3. **Honest single-look protocols sit at the nominal rate.** WF + PSR (N = 1): 2.3-6.0%. The 2-year
   holdout: 2.0-5.3%. The pre-registered control: 2.0-5.3%. These hold across GARCH, heavy tails and
   regime-switching volatility. Heavy tails and clustering did not break the PSR at this length.
4. **Uncounted iteration is the dominant false-positive source.** Keeping the best of 5 pipeline
   variants passes noise 8.7-19.3%, and the best of 20, 21.0-37.3%. This is "iterate until noise looks
   like an edge", measured.
5. **The repaired DSR holds at any N.** B1 stays at 0.0-2.3% at N = 5 and 20, and B2 (effective N) at
   1.3-4.3%. Their power is WF-limited: 58-74% at 0.94, and 9-15% at 0.44.
6. **CPCV + PBO is the most powerful honest combination measured.** FPR is 2.0-5.0%; power is 25.5% at
   0.44 and 87.5% at 0.94.
   - Its advantage comes from selection data: it trains on 8 of 12 years.
   - **PBO must never gate alone.** It is rank-based, so on the high-cost null (every config loses, but
     the low-turnover ones lose consistently less) PBO <= 0.10 passes 7.7% and PBO <= 0.20 passes 18.3%.
7. **Four popular protocols fail as validation.**
   - *Rademacher Anti-Serum:* no power at this length. Its full bound costs about 4.6 annual Sharpe at
     T = 12 years, N = 60. That is 0.286 per-day Sharpe; the three terms are 2R̂ = 0.069,
     3·sqrt(2 ln 40 / T) = 0.146 and sqrt(2 ln 2400 / T) = 0.071 [derived].
   - *Random entries with identical exits:* 83-89% false positives on the in-sample best. It is 6-12%
     even on a fixed config, because independently drawn random trades erase the cross-instrument
     correlation of real positions, so its null is too narrow.
   - *The ±10% plateau test:* not a significance test. 93-99% of null in-sample bests pass it, because
     neighbours in a smooth parameter family are near-identical. Used as a selection regulariser it
     changed WF power by less than a point here. The landscape here is smooth, and QIEA's may not be;
     that is the limit of this result.
   - *The cross-instrument holdout:* 8.3-12.3% false positives (see §2.6 for the cause).
8. **The §14 Sharpe row is miscalibrated in both directions.** On the full record it rejects real
   edges (1.5% power at 0.94). On a 2-year window, with iteration, it admits noise at 6.7-10.7%.

### 2.4 The intraday horizon (hourly bars, 3-12-hour episodes, cost 0.03 sigma per side) [sim]

Replications: iid null 100, GARCH null 60, planted 60 each. Measured true best Sharpe: 0.26 / 0.53 /
1.07. The permutation test and the high-cost planted runs were not run at this horizon (compute).

| protocol | FPR % (iid, GARCH) | power % at 0.26 / 0.53 / 1.07 |
|---|---|---|
| control: one pre-registered config | 0.0 | 13.3 / 35.0 / 93.3 |
| ACIS as built | 0.0 | 0.0 / 0.0 / 0.0 |
| WF + PSR, N = 1 | 0.0 | 13.3 / 23.3 / 68.3 |
| WF best of 20, uncounted | 0.0 | 35.0 / 56.7 / 90.0 |
| repaired DSR (B1), N = 20 | 0.0 | 3.3 / 10.0 / 65.0 |
| repaired DSR (B2), N_eff of 20 | 0.0 | 10.0 / 25.0 / 73.3 |
| CPCV z + PBO <= 0.20 | 0.0 | 15.0 / 25.0 / 86.7 |
| **PBO <= 0.10 alone** | **96.0-96.7** | 98.3 / 100 / 100 |
| random entries, same exits | 48.3-52.0 | 100 / 100 / 100 |
| ±10% plateau | 1.7-2.0 | 93.3 / 98.3 / 100 |
| cross-instrument holdout | 0.0 | 8.3 / 40.0 / 65.0 |
| 2-year time holdout | 0.0 | 5.0 / 16.7 / 30.0 |
| RAS full bound | 0.0 | 0.0 / 0.0 / 0.0 |

Reading it honestly:
- **The intraday nulls are cost-dominated.** At 0.03 sigma per side, every noise configuration loses
  heavily: the best true null Sharpe is −0.60 (`calib_intraday.log`). So the 0% FPRs of the
  Sharpe-based tests are trivially earned. The stringent false-positive case, zero cost, is the multiday
  zero-cost column in §2.2.
- **That same null is the cleanest proof that PBO must never gate alone.** Every configuration loses,
  but the low-turnover ones lose consistently less. The in-sample ranking is therefore stable out of
  sample, and PBO reads ≈ 0, "no overfitting". It passes 96-97% of these all-losing markets. PBO
  measures whether the ranking survives, not whether anything makes money.
- **The ranking of honest protocols is the same as at the multiday horizon.** CPCV + PBO >= WF + PSR >=
  repaired DSR, with none reliable below a true Sharpe of about 0.5.
- **Horizon changes cost, not the statistics.** The net Sharpe of the best intraday config moved from
  −0.35 to +2.5 as the planted drift went from 0.08 to 0.16 sigma per bar (the calibration probe). At
  intraday turnover, a small error in the cost model or in the gross edge flips the sign of the verdict,
  which is the GAP-P12D-36/46 lesson measured.

### 2.5 Record length, measured: 12 against 24 development years [sim]

The "years for 80%" column in §2.2 is a sqrt(T) extrapolation. It was checked by rerunning three
scenarios with 24 development years (80 replications each; multiday, iid, low cost).

| protocol | null FPR at 24 y | power at true 0.44: 12 y → 24 y | power at true 0.94: 12 y → 24 y |
|---|---|---|---|
| control: one pre-registered config | 2.5 | 47.0 → 78.8 | 97.5 → 100 |
| WF (2-year rolling train) + PSR, N = 1 | 1.2 | 15.5 → **18.8** | 66.0 → **77.5** |
| repaired DSR (B1), N = 20 | 0.0 | 9.0 → 16.2 | 61.5 → 83.8 |
| repaired DSR (B2), N_eff of 20 | 1.2 | 14.5 → 26.2 | 73.5 → 93.8 |
| CPCV z + PBO <= 0.20 | 1.2 | 25.5 → **55.0** | 87.5 → **98.8** |
| cross-instrument holdout (raw) | 7.5 | 33.5 → 53.8 | 73.0 → 80.0 |
| WF best of 20, uncounted | **26.2** | 53.5 → 71.2 | 93.5 → 100 |

- **The rolling 2-year WF barely benefits from more history.** Its selection still sees only 2 years,
  so extra data only lengthens the test record. The sqrt(T) extrapolation is optimistic for it.
- **CPCV's training set grows with the record, so it gains more than sqrt(T) predicts.** The
  extrapolation of 74 years to 80% power at 0.44 is pessimistic; the true figure is probably about
  30-40 years.
- **Uncounted iteration stays at 26% false positives however long the record.** More data does not fix
  an uncounted search.

### 2.6 The cross-instrument holdout: the common factor is the cause, and residualising fixes it [sim]

`xinst_control.py`: the same null, search and test, with only the noise correlation changed
(R = 300 per row).

| correlation of noise across instruments | raw cross-instrument FPR | residualised FPR | fixed-config control |
|---|---|---|---|
| 0.0 | 4.7% | 4.7% | 3.7% |
| 0.4 | 10.3% | 4.7% | 5.0% |
| 0.7 | **22.7%** | **2.7%** | 3.7% |

The selected config partly fits the shared factor's noise, and the reserved instruments carry the same
factor, so the "untouched" holdout inherits the selection bias. USD pairs share a large USD factor, so
this is the realistic case. Regressing the reserved instruments' daily P&L on the development P&L of
the same config (beta from the development period) and testing the residual restores the nominal rate.
**If reserved instruments are adopted (prior pass Q6 #13), grade the residual, never the raw P&L.**

### 2.7 Stage 2 under a realistic outer loop, and the expanding walk-forward [sim]

`run_cpcv_outer.py`. The researcher grades M pipeline variants (the full family plus random 30-config
subsets) by CPCV and keeps the best z. The "deflated" gate is z >= 1.645 + sqrt(1 - rho)·E[max_M],
with rho the mean correlation of the variants' path returns (measured at 0.73-0.87). PBO is computed on
the chosen variant's own matrix.

| gate | FPR: iid low (n=200) / GARCH low (100) / iid high cost (100) | power at true 0.44 / 0.94 (n=100 each) |
|---|---|---|
| CPCV z, one variant | 5.5 / 4.0 / 3.0 | 35 / 84 |
| CPCV z + PBO <= 0.2, best of 5, **uncounted** | 11.5 / 4.0 / 5.0 | 53 / 92 |
| CPCV z + PBO <= 0.2, best of 20, **uncounted** | 12.5 / 8.0 / 7.0 | 59 / 94 |
| **CPCV z (deflated for 5 looks) + PBO <= 0.2** | 6.0 / 3.0 / 3.0 | 39 / 80 |
| **CPCV z (deflated for 20 looks) + PBO <= 0.2** | 5.5 / 3.0 / 4.0 | 36 / 83 |
| expanding-window WF (train on all prior years) + PSR, one look | 5.0 / 1.0 / 3.0 | 25 / 74 |

Three readings:
1. **Stage 2 needs the register as much as the DSR does.** Uncounted CPCV + PBO passes 11.5-12.5%
   of iid nulls after 5-20 looks. Counted, it holds 3-6%. The 6.0% has a one-sigma error of ±1.7 points.
2. **Registered iteration is cheap in power when the variants are correlated.** At rho ≈ 0.8 the
   deflation for 20 looks costs little, and the best-of-20 search adds power (36% / 83% against 35% /
   84% for one look). Iteration is not the enemy; uncounted iteration is.
3. **More training data beats a clever gate.** The expanding window lifts WF power from 15.5% / 66% to
   25% / 74% at the same FPR. It is the cheapest change on the engine side, and it is compatible with the
   ratified calendar-year folds: only the train start stays at 2012 instead of rolling.

## 3. The protocol I recommend: "iterate freely, look rarely, count every look, promote only forward"

Each stage below is either [impl] (inside the existing contract) or [spec] (needs owner ratification).

| stage | where | what passes | measured basis |
|---|---|---|---|
| **0. Preconditions** [impl] | synthetic only | The oracle positive control PASSES the harness and null/permuted FAIL (GAP-P12D-37). Leakage tests T1, T2, T4, T6 and T7 pass (§7); leakage is excluded by structure because no statistic below can deflate it (§7.2). The research-simulator reconciliation R1-R6 passes (§8). The attempt register exists, and the grader writes its line BEFORE it grades (exclusive create, like `HoldoutGuard.begin_final`). | Without these, no number below means anything. |
| **1. Exploration** [impl] | synthetic; pre-2012 history (EUR/USD 1-minute bars back to 2000 are published by HistData); instruments outside the validation set | Nothing passes. Ideas are generated and killed. Unlimited looks, unregistered. Every LLM-originated idea starts here (§6). | "Iterate until we find an edge" happens here, where it cannot mislead. |
| **2. Research-simulator validation** [spec] | 2012-2023, one registered look per graded pipeline version | The family's candidate matrix (every configuration's daily net return, the same C8 cost objects as the harness) passes CPCV (6 groups, k = 2, purge >= the longest lookback) with path-mean z >= 1.645 + sqrt(1 - rho)·E[max_N], AND PBO (CSCV, S = 16) <= 0.20. N = the family's registered looks; rho = the mean correlation of their path returns. | Single look: FPR 2.0-5.0% over six null families; power 25.5% / 87.5% at a true Sharpe of 0.44 / 0.94. Under an outer loop: see §2.7. |
| **3. Engine confirmation** [spec] | 2012-2023 walk-forward (the ratified plan) | The frozen candidate runs through the real engine once. It is graded by the repaired DSR (B1, or B2 with effective N) on DAILY out-of-sample returns, with N = the register's engine looks, and by the non-statistical §14 rows the owner keeps (drawdown, rule violations, guardrail hash, trade floor). Its OOS Sharpe must also not be significantly below the stage-2 estimate: the engine must realise what the simulator measured. | B1/B2: FPR 0.0-4.3% at N up to 20. The engine's job here is to confirm; the power was spent in stage 2. |
| **4. Locked holdout** [spec — it changes what the holdout is for] | 2024-25, once | Kill-only: FAIL if the holdout Sharpe is below zero or below the pre-registered lower bound. A pass certifies nothing. | 2 years detects a true 0.94 only 33.5% of the time, and a claimed 0.75 that is really 0 only 28% of the time [sim, derived]. |
| **5. Forward incubation on the demo** [impl] | the owner's demo, from day one | Plumbing and model first: >= 100 round trips reconciled (shadow replay) inside the R4 band; behavioural distributions inside their backtest 95% bands; >= 1 month covering a weekend, a rollover and a macro event. Edge second: tracked sequentially under the K5 kill rules, never "certified". | The only clean record for LLM-shaped hypotheses. It cannot prove an edge in any practical time (§5.4). |
| **6. Prop-economics gate** [spec] | the validated OOS record plus the forward record | P(pass), P(breach), time to pass and EV, under the chosen firm's exact rules, with nested block-bootstrap confidence bands (§9). The owner decides. | §9. |

**Answer to the brief's direct question.** At 12 development years with a 2-year holdout, the best
measured protocol that holds the false-positive rate at or near 5% in every null family AND usually
detects a Sharpe near 1.0 is **CPCV + PBO <= 0.20, deflated for registered looks**: FPR 2.0-5.0% (one
look, six null families), 3.0-5.5% (20 registered looks); power 87.5% at a true 0.94 (83% after 20
looks). The Masters permutation test is the one more powerful honest test measured: FPR 3.0-8.0% ± 2.7
(exact by construction under exchangeability), power 43% / 96%. It needs K full re-runs of the search,
so it runs only on a research simulator. It is a valid alternative stage-2 screen, in-sample, and
counted per look by Bonferroni on p.
**No protocol detects a Sharpe near 0.5 reliably.** The best honest power at a true 0.44 is 25.5%
(CPCV + PBO) or 43% (permutation, in sample). With 24 years of data CPCV + PBO reaches 55%. That is a property of the data, not of any
protocol, and the only ways around it are:
- more **breadth** (more instruments with independent edges raise the portfolio Sharpe);
- more **time** (forward data, or pre-2012 history for exploration);
- a stronger **prior** (a pre-registered, literature-fixed specification faces no search deflation:
  the control row reaches 47% at 0.44).

## 4. Options for GAP-P12D-33 / GAP-P12D-37 (the owner-ratified DSR gate) [spec — owner ratification]

Every figure below is measured in §2's simulation (multiday family, 12 development years, walk-forward
test years 2-11, low cost unless stated). "FPR" is the WORST of the six null columns (iid, GARCH,
t4, regime-switching volatility at low cost; iid at zero and at high cost). "Power" is at a true
best-configuration Sharpe of 0.44 / 0.94.

| option | what changes | FPR (worst null) | power 0.44 / 0.94 | verdict |
|---|---|---|---|---|
| **A. Keep as built** | nothing | 0.0% | 0.0 / 0.0% | It passes nothing, true or false. The emulation's implied hurdle has a median annual Sharpe of 7.7 (5th-95th percentile 4.6-14.1); the real engine's was 19-76 (GAP-P12D-37). |
| **B1. Repair the inputs, keep "DSR >= 0.95"** | graded series = DAILY out-of-sample returns; trials = the daily OOS return series of every registered pipeline version graded on the same days; N = the register count; trial variance NULL-IMPLIED, (1 - rho)/(T - 1), with rho the mean correlation of the registered return series — never the observed dispersion of trial Sharpes | N=1: 6.0%; N=5: 2.3%; N=20: 1.3% | N=1: 15.5 / 66.0%; N=5: 14.0 / 58.0%; N=20: 9.0 / 61.5% | Honest at any N, and immune to both inversions (fewer or alike trials cannot loosen it; a real edge's wider dispersion cannot tighten it). Conservative. |
| **B2. As B1, N = effective count** | N replaced by the participation ratio (sum of eigenvalues)^2 / sum of squared eigenvalues of the register's correlation matrix | N=20: 4.3% | N=20: 14.5 / 73.5% | Least conservative honest DSR measured. |
| **C. CPCV + PBO as the primary gate; the DSR (B1, N=1) confirms on the engine** | the research simulator scores the family's candidate matrix by CPCV (6 groups, k=2, purged): path-mean z >= 1.645 + sqrt(1-rho)·E[max_N] for N registered looks; AND PBO (CSCV, S=16) <= 0.20; the engine walk-forward then confirms the frozen candidate once | one look: 5.0%; 20 registered looks: 3.0-5.5% (§2.7) | one look: 25.5 / 87.5%; 20 looks: 36 / 83%; at 24 years: 55 / 99% | Most power at an honest rate. CPCV trains on 8 of 12 years instead of 2. PBO must never gate alone: on the high-cost null it passes 7.7-18.3% (it rewards a stable ranking of losers). |
| **D. Procedural and structural, needed under any option** | an oracle positive control as the suite's first gate (GAP-P12D-37); the attempt register written BEFORE a grade, as the holdout marker is; the structural leakage tests of §7 | — | — | Without D, no option's numbers mean anything. No statistical gate removes a leak: a config that peeks one bar ahead on 5% of bars passed WF+PSR 80%, CPCV+PBO 100% and PBO 87.5% of NULL markets here, while a future-perturbation test caught it 40/40 (§7.2). |

Measured context for the decision:
- Recommended: **C with B2 as the engine-side confirmation**. B1 is the conservative fallback if
  the research simulator (§8) is not built. A is not an option; it is the status quo that passes nothing.
- Uncounted iteration is what the gate exists to stop. The best of 5 walk-forward pipeline variants,
  graded with no deflation, passes pure noise 9-19% of the time; the best of 20, 21-37%.
- The trials the harness records today (QIEA holdout per-trade Sharpes) are in-sample transparency.
  Under B1/B2/C they are not deflation inputs.

### 4.1 The §14 "annual Sharpe > 1.5" row — measured [spec — owner decision; no change proposed without it]

GAP-SP12E-01 records the owner's standing: "quality, not mediocre results or a lie". The simulation
says the 1.5 row does not deliver that property on either side:
- On the full 10-year walk-forward record it passes almost nothing true: power 1.5-3.0% at a true
  Sharpe of 0.94, 0% at 0.44 (and 0% on every null).
- On a 2-year graded window — the span a §14 run needs, and the span the falsification ran on — the
  row ALONE passes noise 0-3.3% of the time per pipeline, and 6.7-10.7% when the best of 20 pipeline
  variants is kept. Analytically, 50 iterated 2-year looks at noise clear 1.5 with probability 0.58.
- The honesty the owner asked for comes from a calibrated false-positive rate, not a high Sharpe
  threshold. Options: (i) keep 1.5 as an aspiration, not a pass condition; (ii) replace it with option
  B or C plus the prop-economics gate of §9; (iii) keep it as is and accept that no realistic edge
  will pass.

## 5. The data budget, the iteration register and the kill criteria (task 3)

### 5.1 The arithmetic that sets every budget [derived here, `analytic.py`]

The standard error of an annualised Sharpe estimate is about 1/sqrt(years), whatever the bar
frequency. For one pre-registered look (N = 1, one-sided 5%), 80% power needs:

| true annual Sharpe | 0.25 | 0.5 | 0.75 | 1.0 | 1.5 |
|---|---|---|---|---|---|
| years of out-of-sample record for 80% power | 98.9 | 24.7 | 11.0 | 6.2 | 2.7 |

Gencay (arXiv 2608.27734, §7) reaches the same wall independently: "a true SR=0.6 strategy needs
roughly eleven years of out-of-sample data to reach t≈2, and deflation raises the bar further."
The development record's walk-forward yields about 10 out-of-sample years (test years 2014-2023). No
protocol can manufacture information the data do not contain. At the realistic band (0.3-0.7), the
honest outcome is **low power at any protocol**, and the design question is how to spend it.

### 5.2 How many looks the development record can afford

Every re-scoring of a changed pipeline against 2012-2023 is a trial. With the repaired DSR (option B
in §4), the false-positive rate stays at or below 5% however many looks are registered, **if the
register is honest**. The price of each look is power. Power after N registered looks, with
the variants' out-of-sample returns correlated at rho = 0.4 (the correlation measured between
pipeline variants in the simulation), is Phi(s·sqrt(Y) − sqrt(1−rho)·E[max_N] − 1.645):

| validation years Y | post-selection OOS Sharpe s | N=1 | 2 | 3 | 5 | 10 | 20 | 50 |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.50 | 0.47 | 0.32 | 0.23 | 0.16 | 0.10 | 0.06 | 0.03 |
| 10 | 0.75 | 0.77 | 0.63 | 0.53 | 0.42 | 0.31 | 0.23 | 0.15 |
| 10 | 1.00 | 0.94 | 0.87 | 0.80 | 0.72 | 0.62 | 0.52 | 0.40 |
| 6 | 0.75 | 0.58 | 0.42 | 0.32 | 0.23 | 0.15 | 0.10 | 0.06 |

The price of a look depends on how different it is. Tweaks correlated at rho ≈ 0.8 (the CPCV variants
in §2.7) cost little power; genuinely different pipelines (rho ≈ 0.4) cost the amounts above. The
register's measured rho sets the price, so the budget is computed, not guessed. As a default for
genuinely new pipelines: **at most 3 registered looks per hypothesis family on 2012-2023** (power at s = 0.75 stays
above 50%). After that the family is spent on this record. If the register is NOT honest, the cost moves
from power to false positives: measured in the simulation, the uncounted best of 5 WF pipeline
variants passes pure noise 8.7-19.3% of the time, and the best of 20 passes it 21.0-37.3% (six null
families, 300 replications each); at 24 years it still passes 26.2%.

### 5.3 The split of 2012-2025

| tier | data | looks | what it may produce |
|---|---|---|---|
| 0 synthetic | `tests/backtest/synthetic_market.py`, this report's generator | unlimited | harness validity: oracle, null, permuted, leakage, reconciliation |
| 1 exploration | **not** 2012-2023. Candidates: HistData 1-minute bars before 2012 (EUR/USD back to 2000 is published, verified 2026-09-24; other pairs unverified), and instruments outside the validation universe | unlimited, unregistered | ideas and kills only; no claims |
| 2 validation | 2012-2023, walk-forward, test years 2014-2023 (the ratified `oos_plan.plan_folds`) | registered; <= 3 per family | the evidence gate (§4) |
| 3 locked holdout | 2024-2025, graded once (`oos_plan.HoldoutGuard`) | 1 | falsification only |
| 4 forward | the owner's demo, from its start date | continuous, sequential | the only clean record for LLM-shaped hypotheses (§6) |

### 5.4 What the holdout and the demo can and cannot prove

- **The 2-year holdout** is a weak falsifier. If the development record claims a Sharpe of 0.75 and
  the truth is 0, a one-sided test on 2 years catches it with probability Phi(0.75·sqrt(2) − 1.645) =
  0.28. It cannot certify: in the simulation, a true 0.94 clears PSR >= 0.95 on the 2-year holdout only 33.5%
  of the time (§2.2); the iid analytic value for 1.0 is 0.41. Use it as a one-shot **kill**, never as a pass.
- **Forward incubation on demo** cannot prove edge in any practical time. The probability that a
  strategy whose backtest claimed Sharpe 1.0 but whose truth is 0 is caught by a 5% one-sided test
  is 0.26 after 1 year, 0.41 after 2 and 0.53 after 3. Claimed 1.5: 0.44 / 0.68 / 0.83. The
  minimum track record for PSR >= 0.95 at 80% power is the same 6.2 years at a Sharpe of 1.0.
- **What the demo CAN prove quickly** is everything that is *not* the edge. Each forward trade can be
  replayed through the harness on the same feed (a shadow backtest), and the modelled and realised
  outcomes compared trade by trade. The noise that swamps an edge test cancels in a paired
  difference, so a cost or fill model that is wrong by a fraction of a pip shows within tens of trades.
  Behavioural invariants show within a few weeks at the engine's trade rate: trade rate, holding
  times, exposure, and the §9.5 rule-violation count. **Recommended minimum:** run the demo until
  (a) at least 100 round trips have reconciled within the R4 tolerance of §8, (b) every behavioural
  distribution sits inside its backtest 95% band, and (c) at least one full month has elapsed that
  includes a weekend, a rollover and a scheduled macro event. That is weeks, not years. The edge
  itself is then tracked **sequentially** from the first forward day, never "certified".

### 5.5 Kill criteria (pre-registered; each writes a register line)

- **K1 Budget.** A family that has used its 3 validation looks without a pass is retired on
  2012-2023. It may return only on new data: forward, or post-cutoff history.
- **K2 Overfit selection.** PBO > 0.5 on a family's candidate matrix at any look: stop tuning it,
  and shrink the search space before any further look.
- **K3 Harness integrity.** A failed oracle, reconciliation (§8) or leakage test (§7) voids every
  result since the last passing run.
- **K4 Holdout.** A 2024-25 Sharpe below zero, or below the pre-registered lower bound, kills the
  candidate. No re-run.
- **K5 Forward.** Any of: a reconciliation breach (the realised-minus-modelled cost gap outside the
  R4 band); a drawdown beyond the 99th percentile of the validated record's block-bootstrap
  drawdown distribution; or a one-sided CUSUM on forward daily returns rejecting "mean >= the
  claimed mean" at 5%.
- **K6 LLM provenance.** An LLM-shaped hypothesis whose only passes are on pre-cutoff data is
  exploration, not evidence (§6).

## 6. The LLM-contamination rule (task 4)

### 6.1 The literature, quoted (all arXiv preprints unless stated; graded (b): credible, verifiable, not yet peer-reviewed)

| source | the passage (verbatim) |
|---|---|
| Glasserman & Lin, arXiv 2309.17322, 29 Sep 2023 | "backtesting produces biased results if the training and backtesting periods overlap. This bias can take two forms: a look-ahead bias, in which the LLM may have specific knowledge of the stock returns that followed a news article, and a distraction effect, in which general knowledge of the companies named interferes with the measurement of a text's sentiment." Also: "In-sample (within the LLM training window), we find, surprisingly, that the anonymized headlines outperform, indicating that the distraction effect has a greater impact than look-ahead bias." |
| Lopez-Lira, Tang & Zhu, arXiv 2504.14765 (v2 15 Dec 2025) | "LLMs cannot be trusted for economic forecasts during periods covered by their training data. Counterfactual forecasting ability is non-identified when the model has seen the realized values: any observed output is consistent with both genuine skill and memorization. Any evidence of memorization represents only a lower bound on encoded knowledge. ... Instructions to respect historical boundaries fail to prevent recall-level accuracy, and masking fails as LLMs reconstruct entities and dates from minimal context. Post-cutoff, we observe no recall." |
| Gao, Jiang & Yan, arXiv 2512.23847 (v2 12 Jun 2026) | "LAP is materially positive throughout the in-sample period and collapses essentially to zero right after the training-data cutoff." |
| Roy & Roy, arXiv 2603.26797, 26 Mar 2026 | "in-sample accuracy rises with contamination (40.8% to 52.5%) while out-of-sample accuracy falls (47% to 42%), providing direct evidence that memorization inflates apparent accuracy at the cost of generalization." (graded (c) for its headline Sharpe claims; the mechanism is consistent with the others) |
| Li, Wang & Ma, arXiv 2605.24564, 23 May 2026 | "Backtesting large language models (LLMs) on historical financial data is unreliable when their pre-training data include the evaluated events. An LLM trained in 2024 may already encode how stocks moved during 2018-2020. We name this failure parametric look-ahead bias". Their mitigation cuts the largest model-level mean in-sample return by "-67.1%". |
| Gencay, arXiv 2608.27734, 27 Aug 2026 | Honest evaluation "rejects every LLM-discovered strategy (across two frontier models, search budgets up to one hundred candidates, and five repeated runs)". §6.1: "Deflation corrects for selection among honestly computed backtests; it has no mechanism against a strategy whose information set is contaminated, and the contamination survives out of sample by construction." §4.5: "At N=1 the threshold collapses to the benchmark and DSR equals PSR, so a single pre-registered hypothesis faces almost no deflation. The framework therefore rewards hypothesis-driven design over brute search." |

### 6.2 What transfers to ACIS, and what does not [derived here — my inference, not the papers' claim]

ACIS is LLM-free at runtime, so the papers' main object (an LLM *producing the forecast*) is not ours.
Our channel is different and, I argue, of the same logical kind: an LLM *producing the hypothesis*
(a module, a filter, a parameter range, "trend worked on USD/JPY in 2022") that is then backtested
on a period the model saw. Lopez-Lira et al.'s identification argument carries over word for word:
when the proposer has seen the realised values, "any observed output is consistent with both genuine
skill and memorization". The size of the effect for generic FX rules is unknown and probably smaller
than for firm-level news; it is also **unmeasurable** on pre-cutoff data, which is the point.

One asymmetry makes the rule cheap: memorisation can only *inflate* a contaminated backtest. So a
hypothesis that **fails** on contaminated history has failed with the wind at its back — that failure
is informative. A hypothesis that **passes** there has shown nothing that recall could not explain.

This session's agents run on a model whose stated knowledge cutoff is June 2026, so **all of
2012-2025, including the locked 2024-25 holdout, lies inside their training window.** The holdout is
therefore clean only for hypotheses that no LLM shaped.

### 6.3 The rule I propose ACIS adopt [spec — owner ratification]

- **L1 Provenance in the register.** Every hypothesis, module, parameter range or filter that enters
  the attempt register carries its origin: `literature (citation, publication date)`, `human`,
  `llm-assisted (model id, training cutoff)` or `llm-originated (model id, training cutoff)`.
- **L2 Kill on history, promote only forward.** An LLM-originated or LLM-refined hypothesis may be
  *rejected* on any historical data, but may be *counted toward a pass* only on data stamped after the
  generating model's training cutoff: forward/demo data, or history that post-dates the cutoff.
  Historical backtests of such hypotheses are exploration, never evidence.
- **L3 The literature exception.** A hypothesis whose full specification (rule and parameters) is fixed
  by a dated, peer-reviewed publication, e.g. the 12-month TSMOM of Moskowitz, Ooi & Pedersen (2012),
  may be graded on history after its publication date even if an LLM wrote the code, **provided no LLM
  chose or tuned any part of the specification.** Any LLM-chosen deviation makes it LLM-refined (L2).
- **L4 The cutoff rolls.** A newer model's cutoff re-contaminates the forward window for the
  hypotheses it touches; the register's cutoff field makes that mechanical.
- **L5 Design decisions count.** The ACIS design itself was co-written with LLMs. The register records
  which design choices an LLM made; those choices inherit L2 when the holdout or the forward record is
  read as evidence for them.

## 7. Leakage and timing guards the canary misses (task 5)

### 7.1 What `refuse_lookahead` does and cannot do

`tests/backtest/harness.py:77-88` checks one thing: that no evolution record cites a bar opening at
or after its fold's `train_end`. Its own docstring (lines 78-81) says it "catches a leaky data path,
not an evolve function that misreports its own spans". It is exactly the kind of instrument Fonseca
(arXiv 2607.04958, 6 Jul 2026, graded (b)) describes: "empirical detectors, which are sound only
channel by channel and certify nothing by their silence." Its silence certifies one channel: the
reference time of the bars that reach evolution.

### 7.2 The two 2026 leakage papers, tested against the harness

- **Zhang, Li, Peng & Chen, arXiv 2605.23959 (12 May 2026), (b)**: toggling one convention at a time
  around a clean t+1-open reference, "centered temporal features and same-day-open execution with
  post-open daily-bar information cause large and stable increases in both predictive and trading
  metrics, whereas global normalization, future-informed graph structure, and same-day-close
  execution are weak in most settings." Mapped onto ACIS (read, not run):
  - *Centered features*: indicators and NVMA are trailing by construction, and the labeller asserts
    causality (`tests/backtest/regime_labels.py:8-10`; session medians are rolling windows,
    `core/data/normaliser.py:271`). Nothing tests it end to end: the canary would stay silent on a
    centered feature, because the bar stamps would still precede `train_end`.
  - *Execution timing*: the fitness simulator enters at the NEXT bar's open
    (`core/optimizer/fitness.py:146-147`), the clean convention. The tick book fills at the order's
    own price on the tick that produced it (`tests/backtest/book.py:6`) — zero latency, mildly
    optimistic, unmeasured.
  - *Global normalisation*: the diversification basket's costs and vol targets are to be "calibrated
    from the real Dukascopy ticks" (`config/instruments.yaml:98-101`). If that calibration window spans
    2024-25, it is a config-level leak into every fold and into the holdout.
  - *Gap-through fills* (not in the paper): the fitness simulator exits at the stop price even when a
    bar opens beyond it (`core/optimizer/fitness.py:115-125`) — optimistic in selection, while the
    tick book correctly exits at the gapped tick.
- **Fonseca, arXiv 2607.04958, (b)**: look-ahead-freedom is temporal non-interference; the pipeline
  calculus separates "a datum's availability from its reference time"; "leakage is recursively
  enumerable but freedom is not" in general, but a type-and-effect check is decidable on the
  value-independent fragment (windowing, resampling, joins, point-in-time reads). ACIS stamps data by
  reference time only. The historical event calendar (GAP-P12D-03, still to build) and SPX closes are
  where availability and reference time part company: an event's actual is available at its
  publication time, not its scheduled time, and revised vintages are not what was known.
- **Gencay, arXiv 2608.27734, (b), verified at source (the lead the ARCHITECT relayed).** Abstract: "a
  deliberately leaky oracle posting a Sharpe ratio of 35 survives Deflated Sharpe and
  probability-of-backtest-overfitting testing completely." §6.1: "The look-ahead oracle survives
  statistical deflation completely; only the structural guardrail removes it." The oracle had a design
  Sharpe of 34.7, an evaluation Sharpe of 51.5, and DSR = 1.00.
- **Reproduced here [sim]** (`leak_oracle.py`, R = 40, NULL multiday market). One configuration that
  peeks one bar ahead on 5% of bars is added to the 60-config family. The statistical gates pass pure
  noise: WF + PSR 80%, CPCV + PBO 100%, PBO <= 0.10 87.5%, and the repaired DSR at N = 20 27.5%. A
  future-perturbation test (scramble every return after t, require positions up to t unchanged) at 30
  random t caught it in 40/40 replications, with 0/40 false alarms on honest configs.
  - At a 1% leak the statistics no longer pass it, but the 30-point test caught only 67.5%. A single
    random t caught the 5% leak only 15% of the time.
  - **So T2 must sweep every decision point** (or every day), not sample a few.
  - **Leakage must be excluded by structure; no statistic can deflate it away.**

### 7.3 Cheap structural tests to add [impl — tests only, no ratification]

| # | test | catches | cost |
|---|---|---|---|
| T1 | **Truncation invariance**: replay a synthetic tape to a random time t twice — data ending at t, and data continuing — and require byte-identical orders, labels and evolution records up to t | every channel through which later data reaches earlier decisions: centered features, whole-year label caches, full-sample statistics | two replays of a short tape |
| T2 | **Future-perturbation invariance**: scramble every price after t; decisions up to t must not change, at EVERY decision day (measured: 30 random t catch a 5% leak 40/40, a 1% leak 27/40) | the same, and caches or normalisers keyed on whole files | same |
| T3 | **Availability stamps**: every datum carries `available_at` beside its reference time; the grader asserts `available_at <= decision time` for every read | event calendar vintages, SPX closes (16:00 NY) against the 17:00 NY FX day, provider clock shifts (GAP-P12D-13) | a field and one assertion |
| T4 | **Config provenance**: every calibrated config value records its calibration window; a fold whose test window, or the holdout, overlaps a consumed value's window is refused | config-level look-ahead (costs, vol targets, thresholds) | a field and one check |
| T5 | **One-switch benchmark** (2605.23959 style) on synthetic tapes: fill at the signal tick against the next tick against the next bar open; causal against centered labels; in-window against full-period calibration | measures the inflation each convention causes, and proves the harness is sensitive to each | a handful of synthetic runs |
| T6 | **Gap-through exit**: a bar that opens through the stop exits at the open, not at the stop, in `simulate_trades` | the optimistic fill at `fitness.py:115-125` | one unit test |
| T7 | **Leaky-oracle positive control**: a strategy that reads the next bar's return must be caught by T1/T2 (and it will sail through the DSR, per 2608.27734 §6.1) | proves the structural guard works | one synthetic run |
| T8 | **Registry-only data access** (2608.27734 §3.2 style): evolution and strategy code read history only through an accessor that takes the decision time; direct cache reads fail a lint test | turns the canary from an empirical detector into a structural guard | an accessor and a lint test |

## 8. Reconciling a fast research simulator with the tick harness (task 6)

The defect class to exclude is GAP-P12D-36: two simulators, two cost models, and a result that
depends on which one ran. Principle: the research simulator may differ from the harness **only in
fill granularity** (bar against tick). Everything else is shared by *object identity*, not by copy:

- the run's C8 `CostModel` instances, built once (`tests/backtest/evolve_step.py:42-54`) and handed to
  both sides — the test asserts `research.costs[i] is harness.costs[i]`;
- the instrument specs and the quote-to-USD conversion (`book.quote_to_account`);
- the financing model and swap conventions;
- the FX clock and calendar (DST-correct, GAP-P12D-07/10);
- the position semantics: one position per instrument, a flip is a close plus an open, max-hold,
  the same treatment of zero-duration trades (GAP-P12D-38).

The test file (`tests/backtest/test_research_reconciliation.py`, proposed) holds six cases:

| case | what it pins | tolerance |
|---|---|---|
| R1 accounting identity | the same trade list through both accounting layers: per-trade net P&L, cost and financing | exact (Decimal equality; 1e-9 relative on floats) |
| R2 cost sentinel | swap in a sentinel cost (e.g. 1.2345 x spread + 0.0007): both sides' P&L moves by exactly the same amount per trade | exact |
| R3 decisions | a deterministic rule on a synthetic tape, with bars built by the engine's own `BarAggregator`: identical trade lists (entry bar, side) | zero mismatches |
| R4 fills | per trade, the difference is bounded by the bar-against-tick price gap at entry and exit; over >= 1,000 trades on each of the null, planted and permuted tapes, the summed P&L agrees within 5% of the total friction charged and the annual Sharpe within 0.10 | as stated; the SIGN of net P&L and every gate decision must agree |
| R5 edges | gap-through stops, weekend financing, max-hold exits, flips, JPY conversion, zero-duration trades | per-trade bound as R4; identical classification |
| R6 oracle | the positive control (knows the planted drift sign) passes in both and nets the same within R4's bound | as R4 |

Every grading run records both simulators' version hashes. A research-simulator result is
admissible (as exploration) only at hashes where the reconciliation test passed.

## 9. The prop-objective gate: P(pass), P(breach) and what a record can tell you (task 7) [sim]

**Method (`propgate.py`).**
- **Rules.** Illustrative and parametrised; the SCOUT codifies each firm's exact ones: profit target
  +8% of the initial balance; maximum daily loss 5% of initial; static maximum loss 10% below initial;
  >= 4 trading days; 250-day cap.
- **Intraday enforcement.** Loss limits are checked on intraday equity through the Brownian-bridge
  touch probability exp(−2a(a + x)/s²). Firms enforce on equity, not on the close.
- **Truth.** 20,000 attempts drawn from the known process (Student-t(4) daily P&L, sd 1% of initial,
  so ~16% annualised).
- **Estimate.** From an out-of-sample record of Y years: 2,000 attempts assembled by stationary block
  bootstrap (mean block 10 days) from the record.
- **Confidence band.** A nested bootstrap: resample the record, re-estimate, take the 2.5-97.5%
  quantiles; 40 records × 50 resamples per cell. Coverage is measured against the known truth.

| true annual Sharpe | true P(pass) | true P(breach) | record length | estimate mean | estimate SD | mean 95% band | band covers truth |
|---|---|---|---|---|---|---|---|
| 0.0 | 49.7% | 46.8% | 0.25 y | 42.4% | 40.2 pts | 11-83% | 75% |
| 0.0 | 49.7% | 46.8% | 0.5 y | 51.2% | 29.4 pts | 10-89% | 88% |
| 0.0 | 49.7% | 46.8% | 1.0 y | 51.5% | 26.4 pts | 16-85% | 88% |
| 0.0 | 49.7% | 46.8% | 2.0 y | 46.5% | 19.7 pts | 19-77% | 88% |
| 0.5 | 63.0% | 34.0% | 0.25 y | 48.1% | 39.7 pts | 15-89% | 75% |
| 0.5 | 63.0% | 34.0% | 0.5 y | 61.4% | 29.1 pts | 15-93% | 92% |
| 0.5 | 63.0% | 34.0% | 1.0 y | 63.2% | 24.5 pts | 25-92% | 88% |
| 0.5 | 63.0% | 34.0% | 2.0 y | 58.4% | 18.8 pts | 29-86% | 88% |
| 1.0 | 74.9% | 23.2% | 0.25 y | 71.2% | 33.0 pts | 25-98% | 88% |
| 1.0 | 74.9% | 23.2% | 0.5 y | 69.6% | 25.8 pts | 26-98% | 90% |
| 1.0 | 74.9% | 23.2% | 1.0 y | 70.9% | 21.1 pts | 32-95% | 88% |
| 1.0 | 74.9% | 23.2% | 2.0 y | 75.4% | 15.4 pts | 47-94% | 90% |
| 2.0 | 89.1% | 10.6% | 0.25 y | 84.3% | 24.8 pts | 41-100% | 75% |
| 2.0 | 89.1% | 10.6% | 0.5 y | 84.0% | 18.0 pts | 43-100% | 85% |
| 2.0 | 89.1% | 10.6% | 1.0 y | 84.7% | 15.1 pts | 53-99% | 85% |
| 2.0 | 89.1% | 10.6% | 2.0 y | 88.0% | 9.9 pts | 69-98% | 85% |

What it says:
1. **P(pass) is weak evidence of edge.** Under these rules a zero-edge strategy passes 49.7% of the
   time, because the target (8%) sits closer than the floor (10%). A Sharpe of 1.0 lifts that only to
   74.9%. A challenge pass, or a demo that "would have passed", says very little about skill. This is
   consistent with the industry framing that most challenge outcomes are variance, but the specific
   numbers depend on the rule geometry and on sizing (see the sizing map below).
2. **No practical record length makes a P(pass) estimate precise.** The estimate's SD is 15-40 points
   from records of a year or less, and still 10-20 points from 2 years. The error is the Sharpe-estimation
   error of §5.1 pushed through a nonlinear map; resampling cannot remove it.
3. **The nested bootstrap band under-covers.** A nominal 95% band covered the truth 75-92% of the time.
   Short records under-represent the tails, and so they understate breach risk. That is the unsafe
   direction.
4. **So the honest gate is not "P(pass) from the backtest".** It is:
   - (i) take the Sharpe from the validated record (stage 2/3), **at its lower 95% confidence bound**,
     not its point estimate;
   - (ii) push that bound, with the record's own volatility, drawdown shape and block structure,
     through the firm's exact rules at the proposed sizing;
   - (iii) report P(pass), P(breach), time to pass and EV net of fees at the lower bound, **side by side
     with the same quantities for a zero-edge strategy at the same sizing**. The difference is what the
     edge buys. The zero-edge baseline is what the rules give away for free, and it is not evidence.
   - Gate: EV at the lower bound > 0 after fees, AND P(breach) at the lower bound below the owner's
     tolerance.
   - Sizing is chosen to maximise the lower-bound EV, not the point-estimate P(pass).
5. **Record length.** Given the numbers above, the prop gate is a decision aid computed from the stage-2/3
   record, not a separate test with its own data requirement. The forward demo (§5.4) refines it
   sequentially; a quarter of demo data moves the P(pass) estimate by up to ±40 points and must not be
   read as confirmation.

**Sizing map (truth only, `prop_sizing.py`, 20,000 attempts per cell): P(pass) / P(breach), %**

| daily P&L sd (% of initial) | Sharpe 0 | Sharpe 0.5 | Sharpe 1.0 | Sharpe 2.0 |
|---|---|---|---|---|
| 0.25 | 3.8 / 1.2 | 9.6 / 0.3 | 20.5 / 0.2 | 55.8 / 0.1 |
| 0.5 | 28.3 / 20.5 | 45.8 / 10.8 | 63.1 / 4.9 | 89.9 / 1.4 |
| 0.75 | 45.3 / 37.8 | 61.0 / 24.8 | 75.7 / 14.8 | 92.4 / 5.4 |
| 1.0 | 50.3 / 46.1 | 62.8 / 34.1 | 75.2 / 23.0 | 89.6 / 10.1 |
| 1.5 | 47.9 / 52.1 | 57.5 / 42.5 | 66.0 / 34.0 | 78.3 / 21.7 |
| 2.0 | 44.0 / 56.0 | 51.0 / 49.0 | 57.0 / 43.0 | 68.1 / 31.9 |

Sizing, not edge, dominates P(pass) under these rules.
- Large sizing makes every strategy a coin flip: at 2% a day, a Sharpe of 1.0 passes 57.0% against
  44.0% at zero edge.
- Small sizing lets the edge show, but the 250-day cap then binds: at 0.5% a day, 63.1% pass / 4.9%
  breach against 28.3% / 20.5% at zero edge.
- The binding constraints are the time cap and the target-to-floor geometry, so the firm's exact rules
  (including whether a time limit exists at all) change these numbers materially. That part is the
  SCOUT's and the ECONOMIST's.

## What I could not verify

- **Paleologo's RAS bound in his own words.** The formula is from a secondary page, (c), quoting "The
  Elements of Quantitative Investing", and it matches a search snippet of a second secondary page.
  Neither the book nor his paper was reachable. If the primary constants are smaller, RAS gains some
  power; it would need to shed about 3.5 of its 4.6-Sharpe haircut to matter at our length.
- **Arian, Norouzi Mobarekeh & Seco (Knowledge-Based Systems 305, 2024).** SSRN, ScienceDirect and ACM
  all returned 403. Their conclusion ("the marked superiority of the Combinatorial Purged (CPCV) method
  ... lower Probability of Backtest Overfitting (PBO) and superior Deflated Sharpe Ratio (DSR) test
  statistic ... Walk-Forward ... exhibits notable shortcomings in false discovery prevention") is quoted
  from search-engine abstract text, not from a fetched page. My own simulation independently agrees on
  power; on false discoveries, my WF + PSR held its nominal rate. Their WF shortcoming may be a
  multiple-looks effect, which is what my outer-loop rows show.
- **Masters' permutation procedure in his own text.** His site failed TLS; I implemented the standard
  Monte Carlo permutation test (permute bar changes jointly across instruments, re-run the whole search,
  compare maxima) and cite the book (2020) by title only.
- **Whether QIEA's real fitness landscape is spiky enough** for the ±10% plateau to discriminate. My
  family is smooth; the plateau result may be kinder on the real optimiser. It still cannot control a
  false-positive rate by itself.
- **The size of LLM contamination for generic FX rules.** It is non-identified on pre-cutoff data. That
  is why the rule in §6 is structural, not a correction.
- **HistData's pre-2012 coverage for pairs other than EUR/USD.** Not checked.
- **The permutation test and the high-cost planted scenarios were not run at the intraday horizon**, and
  the intraday nulls are cost-dominated (every noise config loses), so intraday FPRs of 0% are trivially
  earned. The stringent zero-cost false-positive case is the multiday one.
- **The 'years for 80% power' figures are extrapolations**, checked at 24 years for three rows only (§2.5).
- **Everything here is synthetic.** The null families span iid, GARCH, heavy tails and regime-switching
  volatility, but not every property of real FX: jumps at fixes and news, intraday seasonality,
  time-varying correlation.

## Residual risk

- **The register is the weak joint.** Every honest-N protocol (B1, B2, stage-2 CPCV) is honest only if
  every look is registered. An unregistered look reverts the system to the 21-37% row. Make it
  structural (write before grade), not procedural.
- **The protocol will miss most real but modest edges** (power about 25% at a Sharpe near 0.45). The
  owner should expect "no pass" to be the common outcome at the realistic band, even when an edge exists.
- **Stage 2 depends on a research simulator that does not exist yet.** Until it does and passes
  reconciliation, only stage 3 (the WF with the repaired DSR, 66% power at 0.94) is available.
- **Common-factor leakage generalises.** Any holdout that shares a factor with the selection set (other
  USD pairs, the same years on other instruments) inherits some selection bias (§2.6).

## Ledger items this pass should generate (proposed; no IDs)

1. **The as-built DSR gate passes nothing, true or false.** In a calibrated emulation it passed 0 of
   1,800 null and 0 of 1,200 planted markets, including a true Sharpe of 0.94. Options B1/B2/C are in
   §4, with measured FPR and power.
   Severity critical · Likelihood high · proposed Status open → **[spec — owner ratification]**
   (extends GAP-P12D-33/37).
2. **The DSR is aimed at the wrong selection.** It deflates within-fold selection that the
   walk-forward already removes, and counts none of the outer loop. Uncounted outer-loop iteration
   passes noise 8.7-19.3% (best of 5) and 21.0-37.3% (best of 20).
   Severity critical · Likelihood high · open → **[spec — owner ratification]** (a new facet of
   GAP-P12D-33).
3. **Attempt register v2.** One line per graded look, written BEFORE the grade (exclusive create,
   like `HoldoutGuard`), with: pipeline hash, family, data window, cost map id, LLM provenance and model
   cutoff (§6), and the daily OOS return series (for the repaired DSR's rho and N_eff).
   Severity high · Likelihood high · open → **[impl]** (the gate that consumes it is [spec]).
4. **The §14 "annual Sharpe > 1.5" row is miscalibrated.** Power is 1.5% at a true 0.94 on the 10-year
   record, and noise passes 6.7-10.7% on 2-year windows with iteration (§4).
   Severity high · Likelihood high · open → **[spec — owner decision]** (links GAP-SP12E-01).
5. **Short-window, per-instrument selection throws away most of a modest edge.** At a true 0.44, the
   realised OOS Sharpe is 0.15 with WF on 2-year windows, 0.04 with ACIS-style per-instrument selection
   on a 2-year window, and 0.28 with CPCV on 8-year training. The training window
   (`oos_plan.TRAIN_YEARS = 2`) and per-regime × per-instrument fitting are power decisions. An expanding
   training window lifts WF power from 15.5% to 25% (true 0.44) and from 66% to 74% (true 0.94) at the
   same FPR (§2.7).
   Severity high · Likelihood high · open → **[spec — owner ratification]** (supports Q6 #7, pooling).
6. **Structural leakage tests T1-T8 (§7).** The canary covers one channel. A leaky oracle passes
   WF+PSR, CPCV+PBO and PBO at 80-100% on a null market in this simulator, and a 30-point
   future-perturbation test caught 40/40 with no false alarms. T2 must sweep every decision point.
   Severity high · Likelihood medium · open → **[impl]**.
7. **Config-level look-ahead.** Calibrated config values (costs, vol targets) carry no calibration
   window (`config/instruments.yaml:98-101`), so a fold or the holdout can consume a value fitted on
   itself. Add provenance, and refuse overlap (T4).
   Severity medium · Likelihood medium · open → **[impl]** (config schema: guardrail-adjacent, raise
   before touching).
8. **The fitness simulator fills gapped stops at the stop price** (`core/optimizer/fitness.py:115-125`).
   Optimistic in selection.
   Severity medium · Likelihood high · open → **[impl]**.
9. **The LLM-contamination rule L1-L5 (§6).**
   Severity high · Likelihood high · open → **[spec — owner ratification]**.
10. **The research simulator and its reconciliation test R1-R6 (§8).** It is required before any
    stage-2 CPCV/PBO or permutation work.
    Severity high · Likelihood high · open → **[impl]**.
11. **Re-state the locked holdout as kill-only, and the demo as plumbing-first with sequential edge
    tracking** (§3 stages 4-5, §5.4).
    Severity medium · Likelihood high · open → **[spec — owner ratification]**.
12. **The cross-instrument holdout inherits selection bias through the common factor** (10.3% FPR at
    rho 0.4, 4.7% at rho 0). The residualised variant restores 4.7%. If reserved instruments are used,
    grade their residual on the development P&L.
    Severity medium · Likelihood high · open → **[spec]** (links Q6 #13).
13. **Protocols to reject as gates:** Rademacher Anti-Serum (no power at our length), random-entry
    benchmarks (83-89% FPR on an in-sample best), the ±10% plateau as a test (93-99% FPR), and PBO alone
    (up to 18% FPR on a high-cost null). The plateau may stay as §5.6's selection rule; it is not
    evidence.
    Severity medium · Likelihood medium · proposed Status accepted-as-finding → **[impl]** (documentation
    of the gate design).
14. **Prop-objective gate** (§9): P(pass)/P(breach) from a nested block bootstrap; see §9 for the record
    length needed.
    Severity high · Likelihood high · open → **[spec — owner decision]**.

## Sources

Graded per §0.4. Dates are publication or last-revision dates; every page was accessed 2026-09-24.

- Bailey, D. H. & López de Prado, M. (2014). *The Deflated Sharpe Ratio*. J. Portfolio Management 40(5).
  **(a)** — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf (text extracted from the PDF;
  quotes in §1).
- Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. *The Probability of Backtest Overfitting*
  (revised February 2015; J. Computational Finance 2016). **(a)** —
  https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf. Its abstract: "the probability of backtest
  overfitting (PBO) ... is then evaluated as the conditional probability that this strategy
  underperforms the median OOS while remaining optimal IS."
- López de Prado, M. (2018). *Advances in Financial Machine Learning*, ch. 12 (CPCV). **(a)** — cited
  for the method; implemented as specified (groups, k, purge, path assembly).
- Arian, H., Norouzi Mobarekeh, D. & Seco, L. (2024). *Backtest overfitting in the machine learning
  era*. Knowledge-Based Systems 305, doi:10.1016/j.knosys.2024.112477. **(a)**, but quoted from
  search-engine abstract text only (the pages returned 403).
- Paleologo, G. *The Elements of Quantitative Investing* (Wiley), ch. 8 "Rademacher Anti-Serum". **(a)**
  as a source, but the formula was obtained **(c)** via
  https://www.research.hangukquant.com/p/probabilistic-inferencing-for-trading ("With probability
  1-delta, the true Sharpe satisfies θₙ ≥ θ̂ₙ − 2R̂ − 3√(2ln(2/δ)/T) − √(2ln(2N/δ)/T)").
- Masters, T. (2020). *Permutation and Randomization Tests for Trading System Development*. **(b)** —
  cited by title; the author's site failed TLS.
- Glasserman, P. & Lin, C. (2023). arXiv 2309.17322. **(b)** — https://arxiv.org/abs/2309.17322
- Lopez-Lira, A., Tang, Y. & Zhu, M. (2025). arXiv 2504.14765. **(b)** — https://arxiv.org/abs/2504.14765
- Gao, Z., Jiang, W. & Yan, Y. (2025/2026). arXiv 2512.23847. **(b)** — https://arxiv.org/abs/2512.23847
- Roy, A. & Roy, D. (2026). arXiv 2603.26797. **(b)/(c)** — https://arxiv.org/abs/2603.26797
- Li, W. W., Wang, M. & Ma, T. (2026). arXiv 2605.24564. **(b)** — https://arxiv.org/abs/2605.24564
- Zhang, F., Li, Z., Peng, S. & Chen, Y. (2026). arXiv 2605.23959. **(b)** — https://arxiv.org/abs/2605.23959
- Fonseca, X. (2026). arXiv 2607.04958. **(b)** — https://arxiv.org/abs/2607.04958
- Gençay, E. (2026). arXiv 2608.27734. **(b)** — https://arxiv.org/abs/2608.27734 and
  https://arxiv.org/html/2608.27734 (§4.1, §4.5, §6.1, §7 quoted).
- Build Alpha, *Robustness Testing Guide* (undated). **(c)** — https://www.buildalpha.com/robustness-testing-guide/
  (the "Vs. Random" description tested in §2).
- HistData EUR/USD 1-minute year list (from 2000). **(c)** —
  https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/eurusd

## Appendix A — reproduction (all in `SCRATCH/validator/`)

- `sim.py` — markets, the strategy family, CSCV/PBO, CPCV, the Rademacher estimate.
- `protocols.py` — one replication with every protocol's raw statistic. The ACIS as-built DSR is
  imported read-only from the repo.
- `calib.py` — drift calibration: `calib_multiday.json`, `calib_intraday.json`.
- `run.py` — scenario driver, writing `res_<horizon>_<noise>_<target>_<cost>.jsonl`.
- `run_perm.py` — Masters permutation (`perm_*.jsonl`).
- `run_cpcv_outer.py` — CPCV + PBO under an outer loop, and the expanding WF (`cpcvouter_*.jsonl`).
- `xinst_control.py` — the common-factor control.
- `leak_oracle.py` — the leaky-oracle check.
- `propgate.py` — the prop-objective bootstrap.
- `analytic.py` — the look-budget, MinTRL and incubation tables.
- `analyse.py`, `table.py`, `summary.py` — pass rules (declared before reading results) and tables.
- Seeds are fixed per scenario (see each `.jsonl` row's `seed`).
