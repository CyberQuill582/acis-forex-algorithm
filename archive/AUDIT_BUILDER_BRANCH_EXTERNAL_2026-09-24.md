# AUDIT — BUILDER branch, EXTERNAL-REFERENT lens (2026-09-24/25)

- **Auditor:** AUDIT-EXTERNAL, on Opus 5.5.
- **Independence:** fresh context, no subagents, no edits to the builder's worktree or the main
  tree. This file is my only repo write. I am a finder, not a clearer (A5). A clean line here is
  not a sign-off.
- **Brief:** `AUDIT_BRIEF_BUILDER_2026-09-24.md` (pinned). I read `BUILDER_REPORT_2026-09-24.md`
  last, after forming my attack from the code (A4).
- **Under audit:** branch `worktree-agent-a128ab904780ce593`, head `9b9ec80` (8 commits on `7695ed0`).
- **Private copies:** `SCRATCH/audit_external/tree` (head) and `…/base` (`7695ed0`), where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
  Every script I cite is in `SCRATCH/audit_external/work/`.
- **Web:** 6 of the 25 WebSearch calls used. Everything else came from WebFetch or curl on primary
  URLs, with PDF text extracted locally (`SCRATCH/audit_external/lit/`). Retrieval dates are
  2026-09-24 and 2026-09-25.
- **Evidence grades:**
  - (a) peer-reviewed paper, primary regulation or official documentation;
  - (b) arXiv preprint or a credible educational source;
  - (c) vendor page;
  - [run] reproduced here by a script;
  - [code] `file:line`.

## Executive summary

1. **The oracle positive control works, but it is saturated.** [run]
   - I reproduced the BUILDER's planted record exactly on the ladder plan: Sharpe 10.199, 2,656
     trades, PF 555.5, DD 0.94%.
   - The same oracle still clears every non-DSR clause with 1/15 of the planted drift (Sharpe 7.24),
     or with 35% of its episode signs wrong (Sharpe 7.94).
   - A 10×-friction harness mutant survives all 8 oracle tests. An exact-cost unit test elsewhere
     does catch it.
   - Stage 1 therefore proves that the grader is not grossly broken. It says nothing about the
     harness's power near the §14 decision level, which is what a negative engine verdict
     (GAP-P12D-49) needs.
   - **Recommendation:** a graded control, with strengths near the cut-off
     (finding E1, **Medium**).
2. **Stage 1 certifies a different criterion than the one the engine is graded on.** [code]
   - It excludes the DSR and trial clauses, by construction.
   - So it cannot detect the GAP-P12D-37 defect class itself, a dead pass gate.
   - A run whose gate is dead still ends "FALSIFICATION FAILED — wrong answer on planted" and is
     charged to the engine (E2, **Medium**).
3. **`--kinds null permuted` runs with no positive control and exits 0.** [run] It prints
   "falsification held: … planted passes", yet planted never ran. A dead grader "holds"
   (E3, **Medium**).
4. **The "oracle DSR 0.000" is not a Deflated Sharpe in Bailey & López de Prado's sense.** [(a) + run]
   - The oracle is not a member of the trial set.
   - The trial Sharpes are small-sample per-trade estimates: sd 2.216, max 19.4. The oracle's is
     over 2,656 trades.
   - Against a like-for-like hurdle (SR0 ≈ 0.05) the oracle scores DSR 1.0.
   - The BUILDER's conclusion ("no strategy could pass this gate as fed") is right, but the
     mechanism is the gate's T-mismatch, not the oracle's weakness (E4, **Low–Medium**).
5. **TSMOM (brief Q4).**
   - The BUILDER's account of Moskowitz, Ooi & Pedersen's method is correct: 12-month lookback,
     1-month hold, 40%/σ sizing with an EWMA σ of centre of mass 60 days.
   - Its "possibly undeclared spot-return deviation" is **refuted**: the deviation is declared at
     `core/signals/canonical.py:101-102`, and GAP-0073 is closed.
   - **The declaration's own premises are wrong about the world** (E5, **Medium**, pre-existing,
     outside the diff):
     - MOP's FX returns are currency-forward returns, so they include carry;
     - on the repo's own ECB and overnight-rate data, the TSMOM vote flips direction on
       2.1–10.4% of days (2013–2025), and on up to 42% of days in a year (USD/CHF 2019).
6. **The plateau law's "±10% of value" step is scale-inconsistent across genes.** [run]
   - The median move is 44.5% of the search range for `rsi_overbought`, against 6–10% for most
     other genes.
   - A range-relative step moves the BUILDER's "RSI knife-edge" refusals (8 of 30) down to 2–3 of 30.
   - The VALIDATOR's measurement stands: a plateau test is a fragility veto, not evidence of edge
     (E6, **Low–Medium**).
7. **NaN convention.**
   - An empty mean giving NaN matches numpy. The standard library raises instead.
   - No §14 gate flips.
   - `ladder.json` and the new `oracle_deflation.json` can emit the non-RFC-8259 token `NaN`
     (E7, **Low**).
8. **Minor items:** the evaluation registry is necessary but not sufficient for CSCV, and it
   records M dependent trials, not the DSR's N (E8, **Low**). The oracle's fixed 10,000 units would
   be $18M of gold if XAU_USD were enabled (E9, **Low**, latent).
9. **Honest negatives:**
   - the synthetic tapes are byte-identical before and after the branch;
   - the BUILDER's SR0 figures (5.654 over 106 trials; 2.430 over 121) reproduce exactly;
   - the plateau refusal counts (14/30 and 11/30) reproduce exactly;
   - the Brownian-bridge explanation of TSMOM's negative tilt is theory-consistent in sign.

---

## Findings (ranked)

### E1 — The oracle control is saturated: it cannot see a harness that destroys most of an edge, and it says nothing about power at the §14 level
- **Severity:** Medium. **Likelihood:** High (structural).
- **Claim.** Stage 1 (`scripts/falsify_engine.py:73-83`, `oracle.void_reasons`) VOIDs only when
  the planted oracle fails a non-DSR clause.
  - The planted oracle's edge is so large that it clears every clause with a large fraction of
    that edge removed.
  - A negative engine verdict ("the engine loses on planted", GAP-P12D-49) is credible only if the
    grader would pass an edge of the size the engine could plausibly realise. The oracle does not
    measure that.
- **Reproduction [run].** `work/oracle_full.py` ran the ladder's exact plan: `plan(60,30,25)`,
  985 days, 2.53 graded years, EUR_USD, `dev_paper`, 1x costs, the branch's own `grade_oracle`.
  The per-episode sign error is applied through a patched `episode_sign`.

  | variant | annual Sharpe | per-trade SR | win | PF | non-DSR failures |
  |---|---|---|---|---|---|
  | planted, drift 0.15 (as built) | 10.20 | 1.273 | 0.993 | 555.5 | none |
  | drift 0.03 (1/5) | 14.78 | 0.679 | 0.770 | 8.34 | none |
  | drift 0.02 (1/7.5) | 12.62 | 0.481 | 0.681 | 4.05 | none |
  | drift 0.01 (1/15) | 7.24 | 0.236 | 0.579 | 1.91 | none |
  | drift 0.15, 35% of episode signs wrong | 7.94 | 0.337 | 0.657 | 2.35 | none |

  - **Mutant.** `SCRATCH/audit_external/tree/tests/backtest/book.py` `close_at` friction ×10 (a
    units bug, the GAP-P12D-19 class). All 8 tests in `test_oracle_control.py` stay green.
  - The bug is caught elsewhere, by `test_cost_stress.py::test_the_book_charges_exactly_the_stressed_friction`.
  - Arithmetic: ×10 friction is about 2,656 × $8.4 ≈ $22k against $311k, so the full-plan stage 1
    would also pass it. The file was restored and `cmp`-verified identical.
  - The short plan (`work/oracle_strength.py`, 2 folds) shows the same pattern: drift 0.02 still
    gives Sharpe 11.6 with no failures.
- **A side effect:** the oracle's annual Sharpe is neither monotone nor calibrated in the edge
  (10.2 at 0.15, but 14.8 at 0.03).
  - At a large drift, daily P&L variance is dominated by exposure variation (max-hold closes,
    fold-boundary carry through warm-up), not by price noise.
  - So the rungs of a graded control must be chosen by *measured* out-of-sample Sharpe, not by
    drift.
- **External referents.**
  - Harvey & Liu (2020), *J. Finance*: *"In a single-hypothesis test, the Type II error rate at a
    particular parameter value … is calculated as the probability of failing to reject the null
    hypothesis at this value"*, and *"when a study's main finding is the non existence of an effect
    … test power directly affects the credibility of the finding because it determines the
    probability of not rejecting the null hypothesis when the effect is true."* (a)
    [arXiv 2006.04269, https://arxiv.org/pdf/2006.04269, retrieved 2026-09-25]
  - Power is a function of effect size. One control at about 15× the needed effect measures it at
    one irrelevant point.
  - 42 CFR 493.1256(d)(3)(i): quantitative procedures must *"include two control materials of
    different concentrations"*. (a, regulation, cross-domain analogue)
    [https://www.law.cornell.edu/cfr/text/42/493.1256, retrieved 2026-09-25]
  - ASCP molecular-lab guidance: *"Ideally, the PC should be at a concentration near the Limit of
    Detection (LoD). This is the most sensitive monitor."*, and *"If reagents are slightly degraded
    (e.g., enzyme lost 50% activity), a high-concentration control might still amplify, but the
    weak control will fail."* (b) [https://molecular.mlsascp.com/assay-controls.html, retrieved 2026-09-25]
  - The VALIDATOR measured honest power at true Sharpes of 0.19 / 0.44 / 0.94
    (`archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` §2.2). The oracle sits at 7–15.
- **Proposed fix [impl, test-side].**
  - Keep the perfect oracle as the gross-defect check.
  - Add a **graded ladder** of 3–4 rungs whose measured OOS Sharpe spans about 1.0–3.0. Use either
    a sign-accuracy parameter (the per-episode flip used here) or a detection-lag oracle, which
    learns the sign d minutes into an episode, as a real filter must.
  - Pin each rung's expected pass/fail from the ratified §14 thresholds.
  - A rung that should pass and fails VOIDs the run. That is the "low positive near the cut-off".

### E2 — Stage 1 does not test the criterion the engine is graded on, so it cannot catch the defect class that motivated it
- **Severity:** Medium. **Likelihood:** High, while GAP-P12D-33/37 is open.
- **Claim.** `oracle.non_dsr_failures` (`tests/backtest/oracle.py:159-173`) deliberately omits
  `trial_count >= 2` and `deflated_sharpe >= 0.95`, and the oracle's trial record is empty by
  construction.
  - GAP-P12D-37 was precisely an unsatisfiable pass gate.
  - With the gate as ratified, the BUILDER's own evidence says nothing can pass planted.
  - Stage 1 nonetheless "recognises" the grader, the engine stage runs for hours, and the script
    exits 1 with "FALSIFICATION FAILED — wrong answer on planted" (`falsify_engine.py:108-111`).
    That charges to the engine a failure the gate guarantees.
  - `grade()`'s `failed` list (`synthetic_grade.py:135`) holds only `targets_met` rows, so the DSR
    refusal does not even appear in the printed reason.
- **External referent.** 42 CFR 493.1256(d)(8): *"Test control materials in the same manner as
  patient specimens."* (a) [https://www.law.cornell.edu/cfr/text/42/493.1256, retrieved 2026-09-25]
- **Proposed fix [impl + owner].**
  - Until GAP-P12D-33 is ruled, a planted engine failure whose only unmet clause is the DSR or
    trial count must print, and exit with, a distinct code: "gate-limited, uninterpretable". It is
    not an engine verdict.
  - Or give stage 1 a like-for-like hurdle check (see E4).

### E3 — A falsification run without the planted market has no positive control and still "holds"
- **Severity:** Medium. **Likelihood:** Medium (a CLI flag away).
- **Reproduction [run].** `work/test_no_positive_control.py` stubs the heavy stages exactly as
  `test_oracle_control._falsify_script` does. The grader is dead: `passed=False` for every market.
  - Invocation: `--kinds null permuted`.
  - Output: `EXIT 0 | oracle ran on: [('oracle','null'), ('oracle','permuted')] | falsification
    held: null and permuted fail, planted passes`.
  - `void_reasons` checks planted only if planted was run (`oracle.py:182-187`). The success
    message (`falsify_engine.py:112`) asserts "planted passes" for a market that never ran.
- **Why it matters.** This is exactly the "a grader that passes nothing makes every negative
  verdict look right" defect that the positive control exists to exclude (E1, Harvey & Liu).
- **Proposed fix [impl].**
  - Always grade the planted oracle in stage 1, whatever `--kinds` says. Or refuse any run whose
    kinds exclude planted.
  - Print only the kinds actually graded.

### E4 — "The oracle deflated by the engine's trial set" is not a faithful DSR; the "DSR 0.000" measures the gate's T-mismatch, not the oracle
- **Severity:** Low–Medium. It is informational (no gate reads it), but it is evidence cited for
  GAP-P12D-33/37. **Likelihood:** High.
- **External referent** (Bailey & López de Prado 2014, *JPM* 40(5)): (a)
  [https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf, retrieved 2026-09-24]
  - *"consider a set of N independent backtests or track records associated with a particular
    strategy class … Each element of the set is called a trial, and it is associated with a SR
    estimate"*;
  - *"V[{SR_n}] is the variance across the trials' estimated SR and N is the number of
    independent trials. We also use information concerning the selected strategy: SR is its
    estimated SR, T is the sample length"*;
  - *"Under the null hypothesis that the actual Sharpe ratio is zero … the expected maximum SR can
    be estimated as the SR0"*;
  - the worked example states SR0 *"non-annualized (with 250 observations per year)"*.
  - SR0 is the expected maximum of **the same estimator** that the selected strategy's SR is.
    The selected strategy is **one of the trials**, measured on a common frequency and sample.
- **Reproduction [run].**
  - Recomputed from the on-disk runs (read-only), the BUILDER's figures reproduce:
    - `data/validation/cost_stress/20260917T083216Z/rung_1x.json`: 106 trials, sd 2.216, max 19.40,
      SR0 5.654;
    - `data/validation/falsification/20260915T231127Z/planted.json`: 121 trials, sd 0.936, SR0 2.430.
  - A per-trade Sharpe of 19.4 exists only on a handful of near-constant trades. The dispersion is
    small-T estimation noise from about-5-trade holdouts, not the spread of true Sharpes across the
    search.
  - The oracle's SR is estimated over T = 2,656 trades. Under the null, that estimator has sd
    ≈ 1/√2656, so the like-for-like SR0 for N = 106 or 121 is **0.0495–0.0504**, and the oracle's
    DSR is **1.0** (`deflated_sharpe.expected_max_sharpe(1/2656, N)`).
  - Per-trade Sharpe also has no fixed time base. On the same oracle trades (`work/oracle_pertrade.py`,
    8 short folds) it is 1.29 per trade but 2.44 per hour-normalised return.
- **Verdict.** The BUILDER's conclusion, that the ratified gate as fed refuses everything, is
  **right**. The mechanism is the T and time-base mismatch the VALIDATOR identified (§1.1), not a
  "weak" oracle.
  - "The oracle's own per-trade Sharpe is only 1.273" is not a meaningful comparison against SR0.
  - `oracle_deflation.json` is labelled as "the Deflated Sharpe the ratified gate gives the oracle"
    (`falsify_engine.py:15-17`). It is a hurdle comparison.
- **Proposed fix [impl].**
  - Rename it, or record `{sr0, oracle_sr, trial_T_median, oracle_T}` side by side.
  - Stop citing "DSR 0.000" as the oracle's DSR in the ledger text.

### E5 — TSMOM: the spot-return deviation IS declared, but its declared premises are wrong about MOP and the immateriality claim fails on the repo's own data
- **Severity:** Medium. **Likelihood:** Medium.
- **Scope.** Pre-existing and outside the diff. Raised under brief Q4. Owned by closed GAP-0073,
  which needs re-opening or a successor entry.
- **Checking the BUILDER's claims against the paper** (MOP 2012, *JFE* 104: 228–250) (a)
  [https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf, retrieved 2026-09-25]:
  - **Headline rule: correct.** *"we focus on the properties of the 12-month time series momentum
    strategy with a 1-month holding period (e.g., k=12 and h=1)"*;
    *"r^TSMOM_{t,t+1} = sign(r_{t−12,t}) · 40%/σ_t · r_{t,t+1}"*.
  - **Volatility: correct.** *"the position size is chosen to be 40%/σ_{t−1}"*, with *"The
    parameter δ is chosen so that the center of mass of the weights is … δ/(1−δ) = 60 days"*.
    The engine's C16 vol-norm replaces this. That is declared (`canonical.py:97-98`).
  - **Holding: correct.** *"go long the contract if positive and short if negative, holding the
    position for h months"*, against the book's 48 h cap (`harness.py:98`). The ACIS-09
    "multi-month" contradiction is internal-lens.
  - **"Spot returns … does not appear in the declared deviations": REFUTED.**
    `core/signals/canonical.py:101-102` declares *"signs RAW price returns, not excess-over-risk-free
    returns as in MOP 2012 (immaterial at 3-12m FX horizons) — GAP-0073"*.
    `KNOWN_GAPS_CLOSED.md:366-372` closed it on 2026-07-17 with `Residual: none`.
- **The declaration's premises fail:**
  1. For currencies, MOP's return is not "excess over risk-free". It is the currency-forward
     return: *"The universe of currency forwards covers the following ten exchange rates … We use
     spot and forward interest rates from Citigroup to calculate currency returns"* (Appendix A.3).
     The omitted term is the interest-rate differential, i.e. carry.
  2. "Immaterial" is measured false in some years [run] (`work/tsmom_carry.py`).
     - Data: ECB reference rates (USD pairs from EUR crosses) and the repo's overnight rates
       (`data/macro/`: EFFR, €STR-DFR, SONIA, TONA, SARON, CORRA, BIS AU policy), carry accrued
       ACT/360, daily, 2013–2025.
     - The direction of `sign(r63)+sign(r126)+sign(r252)` differs between spot and forward-return
       bases on this share of days:

       | pair | EUR_USD | GBP_USD | USD_JPY | AUD_USD | USD_CHF | USD_CAD |
       |---|---|---|---|---|---|---|
       | days with a different vote | 4.0% | 2.1% | 5.5% | 3.8% | 10.4% | 2.8% |

     - Worst years: USD_CHF 2019 **42%**, 2024 21%; EUR_USD 2024 **22%**; USD_JPY 2019 18%,
       2025 13%.
     - Caveat: ECB fixings at 14:15 CET and overnight rates only proxy forward points, since the
       CIP basis is ignored.
- **Proposed fix [spec — owner ratification].** Re-open GAP-0073 or add a successor. Either:
  - sign the carry-inclusive return (the dated-rates model already exists for the book); or
  - restate the declared deviation with the measured disagreement rate and the correct referent
    ("forward return", not "excess over risk-free").

### E6 — The plateau law's "±10% of value" is a scale-inconsistent perturbation; the observed "RSI knife-edge" is largely an artifact of it
- **Severity:** Low–Medium. It is an owner-ratification item and changes production selection.
  **Likelihood:** High.
- **Measured [run].**
  - `work/plateau_scale.py` draws 20,000 uniform random repaired champions and runs the branch's
    own `neighbours()`. It reports each move as a share of the gene's search range:

    | gene | median move / range | sides untestable |
    |---|---|---|
    | rsi_overbought (65–80) | **44.5%** (max 53%) | 0% |
    | mean_rev_zscore_entry | 19.1% | 0% |
    | rsi_oversold (20–35) | 17.5% | 0% |
    | atr_multiplier_tp | 9.6% | **11.4%** |
    | max_holding_periods | 6.4% | **9.5%** |
    | ema_fast, ema_slow, rsi_period, momentum_lookback | 6–7% | 2–7% |

  - RSI thresholds are interval-scale levels around 50, not ratio-scale quantities, so "10% of the
    value" moves overbought about 2.5 times as far as oversold, measured on the RSI scale.
  - `work/plateau_scale_refusals.py` re-ran the BUILDER's fixture scan. The champions are
    identical; only the neighbours change. It reproduced the branch's refusals of 14/30 (trend)
    and 11/30 (ranging-25).

    | | refused (trend) | refused (ranging-25) | `rsi_overbought` kills (per fixture) | `ema_fast` kills (per fixture) |
    |---|---|---|---|---|
    | ±10% of value (as built) | 14/30 | 11/30 | 8 | 3 |
    | ±10% of range | 10/30 | 9/30 | 2–3 | 8 |
- **External referents** (b, arXiv preprints):
  - The AlgoXpert IS–WFA–OOS protocol's cliff veto uses *"the neighborhood N(θ) consisting of
    adjacent points along each parameter dimension with displacement equal to one grid resolution
    step (e.g., ±1 step), holding other dimensions fixed"*. It rejects on *"the worst-case Sharpe
    degradation under minimal perturbation"* above a threshold τ, and defines the plateau as
    *"Ω_stable = {θ | SR(θ) ≥ α·SR_opt}"*.
    [arXiv 2603.09219, https://arxiv.org/pdf/2603.09219, retrieved 2026-09-25]
    ACIS matches its one-at-a-time structure but departs on the step unit (value, not grid or
    range) and on the criterion (an absolute C9 cliff, not relative degradation).
  - Mroziewicz & Ślepaczuk smooth rather than veto: *"This method weights the Sharpe ratio of a
    cell based on the average Sharpe ratios of its neighboring cells"*.
    [arXiv 2602.10785, https://arxiv.org/pdf/2602.10785, retrieved 2026-09-25]
  - Bailey, Borwein, López de Prado & Zhu propose no neighbourhood test. Their remedy is counting
    the trials (PBO/CSCV, DSR). Their warning applies to any in-sample screen: *"even if the prior
    is false, the researcher is very likely to identify a combination of parameters that happens
    to deliver an outstanding performance IS"* ("Pseudo-Mathematics and Financial Charlatanism",
    *Notices AMS* 2014, §5) (a)
    [https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf, retrieved 2026-09-25].
  - The VALIDATOR measured the ±10% plateau passing 92.7–98.7% of null in-sample bests (§2.2, §2.3
    item 7).
- **Proposed fix [spec — owner ratification, add to the BUILDER's choice 2].**
  - Express the step in range-relative (grid-step) units.
  - Consider a relative-degradation "dies" (τ on the fitness drop) beside the C9 cliff.
  - Record in the spec that the law is a fragility veto that never counts as evidence of edge.

### E7 — NaN reaches two JSON writers that emit the non-RFC token `NaN`
- **Severity:** Low. **Likelihood:** Medium: any run whose §14 band is empty while carve-out
  trades exist, e.g. a TSMOM-only rung; or an oracle with fewer than 3 trades.
- **Where it is written.**
  - `scripts/cost_stress_ladder.py:153` dumps rows containing `avg_duration_s`, `dsr` and `sharpe`
    with `json.dumps` defaults.
  - The new `scripts/falsify_engine.py:103` writes `oracle_deflation.json` the same way.
  - The report writer is safe: `report_json`/`_plain` (`oos_runner.py:145-164`) maps non-finite
    values to `null`.
- **Reproduction [run].** `compute_metrics` on one TSMOM trade, then
  `json.dumps({"avg_duration_s": m.avg_trade_duration_s})`, gives `{"avg_duration_s": NaN}`.
  A strict re-parse raises `non-RFC constant NaN`.
- **External referents.**
  - RFC 8259 §6: *"Numeric values that cannot be represented in the grammar below (such as
    Infinity and NaN) are not permitted."* (a) [https://www.rfc-editor.org/rfc/rfc8259.txt,
    retrieved 2026-09-25]
  - Python `json`: *"If True (the default), their JavaScript equivalents (NaN, Infinity,
    -Infinity) are used"*, and *"The RFC does not permit the representation of infinite or NaN
    number values."* (a) [https://docs.python.org/3/library/json.html, retrieved 2026-09-25]
- **The NaN convention itself is sound.**
  - numpy 2.4.1 `mean([])` returns `nan` with a "Mean of empty slice" RuntimeWarning [run].
  - The stdlib instead raises: *"If data is empty, StatisticsError will be raised."* (a)
    [https://docs.python.org/3/library/statistics.html, retrieved 2026-09-25]
- **Honest negative [run + code].** No gate flips.
  - `DURATION_MIN_S <= nan <= DURATION_MAX_S` is False (`report.py:94`), exactly as 0.0 failed
    before.
  - `non_dsr_failures` and `void_reasons` see the same `targets_met`.
  - The MCP plane (`monitoring/`) reads no ladder or falsification JSON.
  - Python `json.loads` accepts the token, so the repo's own readers do not break.
- **Proposed fix [impl].** Route both writers through `_plain`, or `allow_nan=False`.

### E8 — The evaluation registry is necessary but not sufficient for PBO/CSCV, and it counts M, not N
- **Severity:** Low. **Likelihood:** Medium (it bites when someone consumes the registry).
- **External referents.**
  - PBO (Bailey, Borwein, López de Prado & Zhu, 2015 revision): *"each column n = 1,...,N
    represents a vector of profits and losses over t = 1,...,T observations … i) M is a true
    matrix … where observations are synchronous for every row across the N trials"*. (a)
    [https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf, retrieved 2026-09-25]
  - DSR Appendix A.3: *"It is critical to understand that the N used to compute E[max{SR_n}]
    corresponds to the number of independent trials. Suppose that we run M trials, where only N
    trials are independent, N<M. Clearly, using M instead of N will overstate E[max{SR_n}]."* (a)
- **Code.**
  - The registry logs genomes plus scalar train fitness (`qiea.py` `_log_evaluations`).
  - `simulate_trades` (`core/optimizer/fitness.py:82-171`) re-simulates a closed-trade PnL list,
    not a per-bar P&L on a common clock.
  - The genomes are highly dependent: QIEA converges, and about 310 distinct genomes come from
    600 draws.
- **Proposed fix [impl, doc].**
  - Say in the stage-5 docstring that CSCV additionally needs a synchronous per-bar P&L
    re-simulator.
  - Say that the registry count is M, reduced to N by the A.3 correlation method before any DSR use.

### E9 — Latent: the oracle's fixed 10,000 units would dominate on gold
- **Severity:** Low. **Likelihood:** Low today: only EUR_USD and USD_JPY are enabled (`load_config`).
- `ORACLE_UNITS = 10000` for every instrument (`oracle.py:48`). `FIRST_MID` includes `XAU_USD: 1800`.
- Enabled, the gold leg is 10,000 × $1,800 = **$18M notional on a $10k NAV**, about 1,600× the
  EUR leg. The planted oracle would then fail max-drawdown, and stage 1 would VOID the run for
  sizing, not grading.
- The engine sizes USD-balanced legs (GAP-P12D-22).
- **Fix:** size the oracle per-instrument USD-balanced.

---

## Honest negatives (verified, not assumed)

- **The tape is unchanged.** Returns for 3 kinds × 2 seeds × 2 instruments are byte-identical
  between `7695ed0` and `9b9ec80`: sha256 `3326534e…a5ca8` on both (`work/fp.py`). The RNG
  consumption order (noise → per-episode `randint` then `choice` → permuted's `shuffle`) is
  preserved.
- **The BUILDER's oracle record reproduces exactly on the full plan:** Sharpe 10.199, 2,656 trades,
  win 0.993, PF 555.46, DD 0.94%, SPX 0.074, 7.07 h, no non-DSR failures.
- **The BUILDER's SR0 figures reproduce exactly** from the on-disk trial sets (5.654 / 106 and
  2.430 / 121).
- **The BUILDER's plateau refusal counts reproduce exactly** on its fixtures (14/30 and 11/30).
- **The oracle has no foresight beyond the current return.** `episode_sign` returns the episode
  of the return that produced tick t, so the first step of each new episode is lost. This is a
  perfect-state-knowledge oracle, not a look-ahead one.
- **The oracle is graded through the same book, C8 costs and metrics:**
  `grade_oracle` → `Backtest.run` → `PositionModel` → `compute_metrics` → `build_report`, with the
  same folds and SPX. Financing is `None` for both it and the engine.
- **The BUILDER's MOP method description** (lookback, holding, 40%/σ, EWMA with a 60-day centre of
  mass) matches the paper's text (quotes in E5).
- **The whole-path demeaning really is a Brownian bridge.** *"B(t) = W(t) − (t/T)W(T)"*, with
  covariance *"min(s,t) − st/T"*. (b) [https://en.wikipedia.org/wiki/Brownian_bridge, retrieved 2026-09-25]
  - Its increments are negatively correlated, so long-lookback trend votes are tilted against.
  - The theory predicts a correlation of about −√(L·h)/T, i.e. −0.016 to −0.032 for L = 63–252,
    h = 2 days and T ≈ 704 weekdays.
  - The BUILDER measured −0.044. The sign is consistent; the size is about 1.5–2.5× theory and
    within its noise.
  - The bridge explains at most a minor share of TSMOM's loss. "Nothing requires a code bug"
    stands.

## What I could not verify

- **Pardo's primary text** (*The Evaluation and Optimization of Trading Strategies*, 2008).
  O'Reilly and Google Books returned 403/429, and no archive copy exists. The plateau comparison
  therefore rests on two 2026 arXiv preprints (grade b), Bailey et al. (a), and the VALIDATOR's
  simulation.
- **The Wu, Lin, Huang & Wu (2024) *Knowledge-Based Systems* 293 plateau paper:** metadata only;
  no abstract was retrievable.
- **The pandas empty-mean convention:** pandas is not installed. numpy is verified [run].
- **Hurst, Ooi & Pedersen (2017)** and the canonical entry's "Sharpe ~0.4 every decade" (not in
  the diff).
- **Internal-lens items I did not run:** the full-suite count (828/6), the 2.6 s / 3.4% plateau
  cost claim, `repair_invariants` equivalence, and RNG-neutrality of the plateau check. I left
  them to the internal auditor to save memory on the shared laptop.
- **The full-plan stage 1 under the 10× mutant:** derived (friction about $22k against $311k), not run.

## Residual risk

- **Negative engine verdicts stay weakly credible** until a graded positive control (E1) exists,
  and a gate-limited failure is distinguished from an engine failure (E2). The oracle proves only
  that the harness recognises an overwhelming edge.
- **The plateau law is live in production QIEA,** and its refusals depend on a step-unit choice
  (E6). Its planted and real refusal rates are still unmeasured (BUILDER residual).
- **TSMOM's signal differs from its cited referent** on up to 42% of days in some years (E5),
  under a ledger entry closed as "immaterial".
- **The DSR gate:** everything here agrees with the VALIDATOR that the gate as fed is dead. That
  remains an owner decision (GAP-P12D-33/37). The "oracle DSR 0.000" should not be cited as
  independent evidence of it (E4).

## Sources (external; retrieved 2026-09-24/25)

- **(a)** Bailey & López de Prado, "The Deflated Sharpe Ratio", *JPM* 40(5), 2014 —
  https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- **(a)** Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (rev.
  Feb 2015) — https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- **(a)** Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism",
  *Notices AMS* 2014 — https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf
- **(a)** Moskowitz, Ooi & Pedersen, "Time Series Momentum", *JFE* 104 (2012) —
  https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- **(a)** Harvey & Liu, "False (and Missed) Discoveries in Financial Economics", *J. Finance* 2020 —
  https://arxiv.org/pdf/2006.04269
- **(a)** RFC 8259 — https://www.rfc-editor.org/rfc/rfc8259.txt
- **(a)** Python `json` documentation — https://docs.python.org/3/library/json.html
- **(a)** Python `statistics` documentation — https://docs.python.org/3/library/statistics.html
- **(a)** 42 CFR 493.1256 — https://www.law.cornell.edu/cfr/text/42/493.1256
- **(b)** ASCP molecular assay controls — https://molecular.mlsascp.com/assay-controls.html
- **(c)** SeraCare (Morreale, 2019-11-26), consistent with the ASCP source —
  https://blog.seracare.com/molecular-serology-blog/for-clinical-labs-avoid-false-positives-and-negatives-by-being-a-control-freak
- **(b)** AlgoXpert IS–WFA–OOS protocol — arXiv 2603.09219
- **(b)** Mroziewicz & Ślepaczuk — arXiv 2602.10785
- **(b)** Wikipedia, "Brownian bridge" — https://en.wikipedia.org/wiki/Brownian_bridge
- **Repo data, read-only:** `data/macro/{ecb_exr,usd_effr,eur_dfr,gbp_sonia,jpy_tona,chf_saron,cad_corra,bis_policy}.csv`;
  `data/validation/cost_stress/20260917T083216Z/rung_1x.json`;
  `data/validation/falsification/20260915T231127Z/planted.json`.
