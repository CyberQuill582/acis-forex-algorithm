# External research: statistical methodology of the ACIS validation stack

**Date:** 2026-09-16 · **Pass:** external-referent (statistics / validation methodology), read-only
**Scope:** `tests/backtest/{deflated_sharpe,walk_forward,evolve_step,harness,report,metrics,oos_plan}.py`,
`core/optimizer/{qiea,fitness,costs}.py`, `config/system_config.yaml`, `ACIS_SPEC.md` §5/§13/§14,
`specs/ACIS-09-BACKTEST_VALIDATION.md`, `specs/ACIS-03-QIEA_OPTIMIZER.md`.
**Companion:** `archive/RESEARCH_FX_METHODS_2026-09-16.md` (strategy design, costs, horizons). This
document deliberately does not re-argue that one's conclusions; where they overlap (§14 target
realism, per-regime fitting) it is cross-referenced and, where I derived the same number
independently, that is said.

**Nothing in this document was applied.** No engine code, config, spec or ledger was modified.
Every numeric claim marked **[derived here]** is reproducible from the scripts in Appendix B.

### How to read the source grades

- **(a) academic** — peer-reviewed paper, or a book by a recognised author in the field.
- **(b) credible practitioner / regulator** — industry index, regulator publication, well-known
  practitioner writing under their own name.
- **(c) unverifiable** — blog, vendor doc, secondary summary. Used only where it agrees with (a)/(b)
  or where it is the only statement of a widely-used convention; always flagged.
- **[derived here]** — arithmetic I performed against this repo's own code and config.

---

## Executive summary — the six things that matter

1. **The Deflated Sharpe gate is faithfully implemented and incorrectly fed.** The formula in
   `deflated_sharpe.py` reproduces Bailey & López de Prado (2014) exactly — the pinned numerical
   example (SR0 = 0.1132, DSR = 0.9004 at N=100) is the paper's own. But the *trial Sharpe ratios*
   it is fed are estimated on **5–50 trades** (`holdout_min_trades: 5`) while the *graded* Sharpe is
   estimated on **thousands** of trades. The DSR's SR₀ is the expected maximum of N estimates drawn
   from the same null distribution; mixing sample lengths that differ by two orders of magnitude
   makes SR₀ a number about the *noise in tiny holdouts*, not about selection. **[derived here]**:
   with trial-Sharpe dispersion of 0.2 (which is *less* than the pure sampling noise of a Sharpe
   estimated on 5 trades, ≈0.45), SR₀ ≈ 0.54 in per-trade units, against a graded per-trade Sharpe
   of ≈0.05 for a system that exactly meets §14 — **DSR ≈ 0.000**. The gate as wired will refuse
   every honest run, for a reason that has nothing to do with the strategy.
2. **And it is perversely easier the *less* you record.** `sharpe_threshold` estimates the trial
   variance *from the trials supplied*. With exactly 2 recorded trials whose Sharpe ratios happen to
   be close, the sample variance collapses, SR₀ → ~0, and DSR → PSR against zero, which a
   §14-passing record clears easily. **A run that records fewer trials gets an easier gate.** That
   inverts the honesty property the gate exists to provide (`report.py:117`, `harness.py:210`).
3. **The recorded trial count understates the real search by ~3 orders of magnitude.**
   `population_size: 20 × generations: 30` = **600 parameter configurations evaluated and maximised
   over per QIEA run**; the ratified development plan is 10 folds × 9 tradeable regimes × 2 enabled
   instruments = 180 runs ⇒ **108,000 configurations evaluated, ≤180 recorded as trials**
   **[derived here]**. Only the per-run winner is ever recorded. Bailey & López de Prado are explicit
   that N is the number of trials carried out in the search, not the number kept.
4. **The DSR is also applied to the wrong object.** A concatenated walk-forward record is not "the
   maximum of N trials" — the selection it corrects for already happened *inside* each fold, and the
   test years are out-of-sample with respect to it. The multiple-testing exposure that actually
   threatens the final grade is the **outer loop** (how many times the pipeline, gene ranges, regime
   definitions, fitness weights and cost model have been revised against this same 2012–2023 data),
   and nothing in the report counts it.
5. **§14's rows are mutually inconsistent, and the binding row is not the headline one.**
   **[derived here]** "positive months > 70%" implies an annual Sharpe of **1.82** under iid normal
   monthly returns; Sharpe 1.5 implies only **66.7%** positive months. The stretch "> 85%" implies
   Sharpe **3.59**, far beyond the stretch Sharpe of 2.5. Meanwhile "win rate > 48%" contradicts the
   spec's own §5.6 statement that published trend following wins ~35–48% of trades. Independently
   derived, matching the companion research pass.
6. **The nominal fitness weights are not the effective ones.** `0.40·mean_sigma` looks like a
   risk-adjusted-return objective with the largest weight. Because `mean_sigma_c = clamp01((s+3)/6)`
   spans only ≈0.45–0.57 over the realistic range of per-trade mean/σ, that term supplies
   **9.5% of the actual ranking discrimination**, while the 0.20 drawdown penalty supplies **39.5%**
   and the 0.20 profit-factor term **34.9%** **[derived here]**. The spec sentence
   "Fitness = Sharpe×0.40 + …" is a true description of the arithmetic and a false description of
   the behaviour.

---

## Q1. Multiple testing and selection bias

### 1.1 Is the Deflated Sharpe implementation faithful?

**Yes, as a formula.** `tests/backtest/deflated_sharpe.py` implements

```
SR0 = sqrt(V[{SR_n}]) · ( (1-γ)·Φ⁻¹(1 - 1/N) + γ·Φ⁻¹(1 - 1/(N·e)) )
DSR = Φ[ (SR - SR0)·sqrt(T-1) / sqrt(1 - γ₃·SR + (γ₄-1)/4·SR²) ]
```

with γ = Euler–Mascheroni, γ₄ **raw** (not excess) kurtosis. That matches Bailey & López de Prado,
*The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*,
Journal of Portfolio Management 40(5), 2014 (**(a)**;
[SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551),
[author PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)), and the
non-normal standard error is the Mertens/Johnson form as reproduced in
[MetricGate's DSR reference](https://metricgate.com/docs/deflated-johnson-sharpe-ratio/) (**(c)**,
agreeing with (a)).

`test_deflated_sharpe.py::test_reproduces_the_papers_numerical_example` pins the paper's own example
(annualised SR 2.5, T = 1250, N = 100, trial-SR variance 1/2, skew −3, kurtosis 10 ⇒ SR₀ = 0.1132,
DSR = 0.9004; DSR = 0.9505 at N = 46). This is exactly the kind of external-referent pin the
constitution asks for, and it holds. **The module is not the problem.**

The de-annualisation discipline in the docstring ("every Sharpe ratio here is PER PERIOD, never
annualised") is also correct and is the mistake most implementations make.

### 1.2 Is the trial count honest? **No — three separate defects.**

**Defect 1 — only winners are counted.** `evolve_step.py:87` appends one trial Sharpe per *champion*
(one per instrument × regime × fold that survived the C9 train gate **and** the §6.3 holdout gate).
Inside each `QIEA.evolve` call, `qiea.py` observes `population_size × generations` individuals and
keeps `max`. With `config/system_config.yaml` at `population_size: 20`, `generations: 30`:

| stage | count |
|---|---|
| configurations evaluated & maximised over, per QIEA run | 600 |
| QIEA runs in the ratified development plan (10 folds × 9 tradeable regimes × 2 enabled instruments) | 180 |
| **configurations actually tried** | **108,000** |
| configurations recorded as DSR trials | **≤ 180** (fewer — gated-out runs record nothing) |

**[derived here]**; if the remaining six declared instruments are enabled the figures become 720 runs
and **432,000** configurations. The paper's N is "the number of trials carried out in the search for
the selected strategy"; the search here is 600× larger than what is recorded.

**Defect 2 — survivorship truncation of the trial set.** A QIEA run that fails the C9 train gate or
the §6.3 holdout gate returns `None` and contributes **no** trial at all
(`qiea.py` `EVOLUTION_REJECTED_TRAIN` / `EVOLUTION_REJECTED_OOS`). The recorded trials are therefore
a conditioned-on-success subsample. The DSR null assumes the N trial Sharpe ratios are the *whole*
draw, including the failures.

**Defect 3 — the fatal one: incomparable sample lengths.** The recorded trial Sharpe is
`moments(holdout_pnls(...)).sharpe`, a per-trade Sharpe over a holdout requiring only
`holdout_min_trades: 5` trades. The graded statistic is the per-trade Sharpe of the concatenated
out-of-sample record, with T in the thousands. The DSR derivation assumes the N trial estimates and
the selected estimate come from the same estimation setting; a secondary review states this
assumption explicitly — "the DSR assumes trials have the same sample length"
([LuxAlgo DSR concept note](https://www.luxalgo.com/library/concept/deflated-sharpe-ratio/),
**(c)**) — and it is implicit in Eq. (2) of the paper (**(a)**).

Why it is fatal, in numbers **[derived here]**:

| quantity | value |
|---|---|
| sampling sd of a Sharpe estimated on 5 trades (true SR 0) | **0.447** |
| ... on 10 trades | 0.316 |
| ... on 30 trades | 0.183 |
| SR₀ at N = 180 when trial-SR sd = 0.20 | **≈ 0.54** (per-trade units) |
| per-trade Sharpe of a record that *exactly* meets §14 (Sharpe 1.5, 250 trades/yr) | **0.095** |
| ... at 1,000 trades/yr | 0.047 |
| resulting DSR | **0.000** |

Even at an implausibly tight trial-SR sd of 0.02, a §14-meeting record at 1,000 trades/yr scores
DSR = 0.236 with N = 180 and 0.000 with N = 108,000. The only configuration in which the gate passes
is the degenerate one: **two** trials with nearly identical Sharpe ratios (sample variance → 0,
SR₀ → 0, DSR → PSR against zero ≈ 1.0).

**This is the headline finding.** The gate is not conservative, it is uncalibrated: it returns ≈0 in
the honest case and ≈1 in the under-recorded case. The `_MIN_TRIALS = 2` floor in `report.py:44`
does not fix this — it is precisely the passing configuration.

**A related mis-specification:** the graded series is per-*trade* returns from concurrent positions
across instruments. Bailey & López de Prado's T counts (approximately) iid return observations.
Trades held simultaneously in EUR/USD and USD/JPY share a common USD shock, so the effective T is
materially below the trade count and the `sqrt(T-1)` term overstates confidence. This is not in the
declared deviations.

### 1.3 What the authors and subsequent literature say about counting trials

- **The literal count is an upper bound; the effective count is what matters.** López de Prado &
  Lewis, *Detection of False Investment Strategies Using Unsupervised Learning Methods*,
  Quantitative Finance 19(9), 2019, 1555–1565 (**(a)**;
  [SSRN 3167017](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167017),
  [PDF](https://codemacher.com/wp-content/uploads/2021/02/Detection-of-false-investment-strategies-using-unsupervised-learning-methods_M.LopezDePrado_and_M.Lewis_2018.pdf)):
  cluster the trials (ONC algorithm) and use the number of *effectively uncorrelated* clusters as N.
  For ACIS this is directly applicable and cheap: the 600 individuals in one QIEA run are highly
  correlated (they are rotations toward one attractor); the honest N for one run is somewhere
  between 1 and 600, and clustering their return series would pin it. **Guessing is not required.**
- **Under-counting is the documented failure mode.** The DSR's own summary literature notes "N is
  rarely known exactly. Correlated trials make the effective N smaller than the literal count" and
  advises using "the count of independent strategy variants you actually evaluated before selecting
  the reported one" (**(c)**, MetricGate). ACIS records the *selected* ones, which is the opposite
  end of the definition.
- **Minimum Backtest Length.** Bailey, Borwein, López de Prado & Zhu, *Pseudo-Mathematics and
  Financial Charlatanism*, Notices of the AMS 61(5), 2014 (**(a)**) give the rule of thumb
  `MinBTL ≈ 2·ln(N) / SR_IS²` years. **[derived here]**, at an in-sample annual Sharpe criterion
  of 1.0: N=600 (one QIEA run) ⇒ **12.8 years**; N=108,000 ⇒ **23.2 years**; N=432,000 ⇒ 26.0 years.
  **Each QIEA run selects the best of 600 on a 2-year training window** (and the window is
  regime-filtered, so the effective span per regime is a fraction of that). By this criterion every
  fold's selection is over-fit by construction. *(I could not re-read the primary PDF's exact
  equation in this session — the arXiv/author PDFs did not text-extract. Treat the constant as "as
  commonly reproduced" and verify against the primary before quoting it in a spec.)*

### 1.4 Which multiple-testing tools are worth adding, and which are theatre

| method | verdict for ACIS | why |
|---|---|---|
| **PBO via CSCV** (Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*, J. Computational Finance 20(4), 2016; **(a)**, [author PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), [eScholarship](https://escholarship.org/uc/item/4w1110bb)) | **Add — highest value.** | It is the one tool that directly answers "is my *selection procedure* over-fitting?" rather than "is this one number significant?". It needs exactly what ACIS already produces: an in-sample performance matrix of **all** configurations × time blocks. The 600 per-run individuals are already evaluated; recording their fitness-by-block is a logging change, not a compute change. CSCV also degrades gracefully: PBO → 1 as N grows *regardless of true skill*, which is the property that would have exposed defects 1–3 above. |
| **Deflated / Probabilistic Sharpe** | **Keep, but repair the inputs** (see Q6). | The PSR half (against SR₀ = 0) is genuinely useful and cheap: it is the right way to state "how confident are we that the true Sharpe exceeds 1.5", including the skew/kurtosis correction. The DSR half is only meaningful once N and V are honest. |
| **White's Reality Check** (White, *A Reality Check for Data Snooping*, Econometrica 68(5), 2000; **(a)**) | **Skip.** | It tests whether the *best of a fixed universe of rules* beats a benchmark, using a stationary bootstrap over the full rule universe's return matrix. ACIS's universe is a stochastic search, not a fixed rule set, and the RC is known to be conservative and to lose power badly when the universe contains many poor models. |
| **Hansen's SPA** (Hansen, *A Test for Superior Predictive Ability*, JBES 23(4), 2005; **(a)**; comparison in [Hsu & Kuan](https://homepage.ntu.edu.tw/~ckuan/pdf/snoop01.pdf), **(a)**) | **Skip at this stage; consider later.** | SPA is strictly better than RC (studentised, avoids the least-favourable configuration, much more powerful) and is the standard tool in the technical-trading-rule literature. But it answers the same "best-of-a-fixed-universe" question as RC. It becomes the right tool the day ACIS has a **fixed, enumerable** set of candidate strategies to compare against a benchmark — not while the candidate set is generated by an evolutionary search. |
| **Stepwise SPA / Romano–Wolf** ([Hsu, Hsu & Kuan](https://homepage.ntu.edu.tw/~ckuan/pdf/Step-SPA-20090720.pdf), **(a)**) | Skip. | Same reasoning; it identifies *which* rules beat the benchmark, a question ACIS does not ask. |
| **Effective-N clustering (ONC)** | **Add — cheap.** | Turns the un-answerable "what is N" into a computed number, and would replace the current arbitrary `len(trials) + min_trials`. |

**Blunt summary for Q1:** the *statistically* correct upgrade is PBO/CSCV as the primary honesty
gate, with a repaired PSR (not DSR) as a secondary confidence statement. RC and SPA are theatre
*here* — not because they are weak tools, but because they test a hypothesis ACIS is not posing.

---

## Q2. Sample fragmentation

### 2.1 How much data does each parameter set actually see?

The unit that matters is **trades**, not bars — but both are worth stating.

**Bars** (1-minute, `fitness_span_days: 730`) **[derived here]**:

| quantity | value |
|---|---|
| 1-minute bars per instrument-year (≈5.2 trading days/week) | ≈389,000 |
| bars in a 730-day fitness span | ≈779,000 |
| even split over 9 tradeable regimes | ≈86,500 bars |
| a 5%-occupancy regime (BREAKOUT_IMMINENT, POST_BREAKOUT) | ≈39,000 bars |

Bar counts look comfortable and are **misleading**: bars inside one regime episode are massively
autocorrelated, and the estimation unit for an entry/exit rule is the *episode* and the *trade*.

**Trades.** The optimiser's own floors are the tell: `fitness_min_trades: 10` on train,
`holdout_min_trades: 5` on the holdout. A champion can therefore be selected out of 600 candidates
on **10 training trades** and validated on **5**. `_MIN_TRADES = 30` guards the final §14 grade but
nothing guards the per-regime fit. A Sharpe estimated on 5 observations has a sampling sd of 0.45
**[derived here]** — the holdout gate is essentially a coin flip.

### 2.2 What the literature says about minimum sample sizes

- **Regime-conditional estimation needs 100–200 observations per regime** to be stable, per applied
  Markov-switching practice (**(c)**, [MetricGate regime-switching reference]
  (https://metricgate.com/docs/regime-switching-models/); Monte-Carlo evidence in the
  high-dimensional factor setting suggests a floor of ~40 per regime, **(a)**,
  [Estimation and Inference for High Dimensional Factor Model with Regime Switching]
  (https://arxiv.org/pdf/2205.12126)). ACIS's floors (10 train / 5 holdout **trades**) are an order
  of magnitude below the weaker of these.
- **The decisive negative result is about exchange rates specifically.** Dacco & Satchell, *Why do
  regime-switching models forecast so badly?*, Journal of Forecasting 18(1), 1999 (**(a)**): even a
  *correctly specified* regime-switching model can be beaten by a random walk out of sample, because
  a small regime-misclassification rate destroys the entire advantage of knowing the right model.
  This is the single most relevant citation in this document for ACIS's architecture, and the
  companion research pass reached it independently.
- **Multiple testing is multiplicative across regimes, not per-regime.** PBO is a function of the
  total number of configurations evaluated in the search (**(a)**, Bailey et al. 2016). Splitting
  the search into 9 per-regime searches does not give each one its own error budget; it multiplies
  the family-wise exposure by 9 while dividing each one's sample by ~9.

### 2.3 Verdict: is per-regime optimisation defensible?

**It is a recognised overfitting trap in exactly this form.** The specific form — a *hard*
partition of the sample by a noisy classifier, followed by an independent parameter fit per cell —
combines the two failure modes the literature names: sample fragmentation (Dacco & Satchell) and
family-wise inflation (Bailey et al.). 9 tradeable regimes × 11 genes = **99 fitted parameters per
instrument**, before the regime classifier's own thresholds, against a per-cell effective sample of
tens of trades.

**What is defensible** (and is the standard resolution in the literature): make the regime a
*continuous conditioning weight* on a small, pooled parameter set rather than a *partition key* for
independent fits. The intuition ("trend rules should matter more in trending markets") survives; the
99-parameter fit does not. The companion pass reaches the same conclusion from the strategy side.

**A smaller, concrete point specific to this repo:** only **two** instruments are `enabled: true`
(`EUR_USD`, `USD_JPY` in `config/instruments.yaml`). The pooling that would most cheaply de-fragment
the sample — pooling across instruments — is already blocked by the universe being this narrow, and
`evolve_step` fits each instrument separately even so. Pooling EUR/USD and USD/JPY into one fit
would roughly double every per-cell sample at zero compute cost.

---

## Q3. Walk-forward design

### 3.1 The fold geometry as built

`oos_plan.plan_folds`: calendar-year test folds, `train_years = 2`, `EMBARGO = 7 days`,
development folds test 2014–2023, holdout 2024-01-01 → 2026-01-01 locked behind an
exclusive-create marker (`HoldoutGuard.begin_final`). `walk_forward.generate_folds` refuses
`step < test_window` (non-overlapping OOS, GAP-P11E-06) and `Fold.__post_init__` refuses unordered
folds. `require_embargo` (`harness.py:133`) checks the **real** first test tick against `train_end`
using the engine's 48 h max hold.

**What is right, and it is a lot:**

- Test windows never overlap, so the concatenated record counts each day once. This is the single
  most common walk-forward error and it is closed, with a test.
- The embargo is enforced on realised data, not asserted in prose.
- The holdout is locked by a file the code cannot delete, and `begin_final` validates the fold plan
  *before* writing the marker.
- The graded period is derived from the data, not claimed by the caller (GAP-P11I-01).

### 3.2 Is a 7-day embargo adequate?

**For the leak it is designed to stop, yes.** López de Prado, *Advances in Financial Machine
Learning* (Wiley, 2018), ch. 7 (**(a)**; summarised at
[Wikipedia: purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation),
**(c)**) distinguishes two mechanisms: **purging** removes training observations whose *label
window* overlaps the test set, and **embargo** removes training observations *immediately after* the
test set, because trailing-window features computed after the test block still contain test-period
information. In a strictly forward walk-forward, only the first mechanism can bite, and 7 days
comfortably exceeds the 48 h maximum hold. `require_embargo`'s comment cites this correctly.

**But two adjacent leaks are not closed:**

1. **Feature memory, not label memory.** The engine's own indicator windows at the first test tick
   are warmed on the embargo-window ticks (`warmup_states = stream(train_end, test_start)`), which is
   correct. However the *fitness* harness warms indicators on training bars (`entry_start`) — also
   correct. The uncovered case is NVMA's own regime-classifier windows and any statistic with a
   lookback longer than 7 days (correlation windows, TSMOM's multi-month lookback seeded from
   `first.train_end`). A TSMOM module with a 3–12 month lookback has a feature memory two orders of
   magnitude longer than the embargo. That is not a label leak, but it means the "embargo ≥ max
   hold" rule is answering a smaller question than the one the module poses. **Recommendation:
   state the embargo as ≥ max(max_hold, longest feature lookback), or declare the deviation.**
2. **The outer-loop leak, which no embargo can close.** Test years 2014–2023 have been visible to
   the designer throughout the build. The DSR's N does not count design iterations, and the locked
   holdout is the only structure that does — see §3.4.

### 3.3 Are the folds independent enough for the DSR to mean anything?

**No, for three reasons, in increasing order of severity.**

1. **Adjacent training windows overlap by one year** (fold Y trains 〔Y−2, Y〕, fold Y+1 trains
   〔Y−1, Y+1〕). The champions of adjacent folds are therefore positively correlated, so the trial
   Sharpe ratios are not N independent draws. Per López de Prado & Lewis (**(a)**) the effective N is
   below the literal N — which, note, cuts *against* the deflation and is the one direction where the
   current implementation is accidentally conservative.
2. **The trial set is not the object being deflated** (see Q1.4). The concatenated OOS record is not
   the max over the recorded trials; it is the realised output of a procedure whose selections were
   all made in-sample. A DSR computed this way is a haircut of unclear magnitude, not a test.
3. **Walk-forward produces exactly one path.** This is the structural limitation
   *Advances in Financial Machine Learning* ch. 12 addresses with **Combinatorial Purged
   Cross-Validation (CPCV)** (**(a)**): by training on all C(N,k) combinations of blocks and testing
   on the complement, CPCV yields many backtest paths and hence a *distribution* of Sharpe ratios
   rather than a point estimate. With 12 yearly blocks and k = 2, CPCV gives 66 splits and 11 paths
   from the same data. **That distribution is the input the DSR actually wants** — the variance of
   trial Sharpe ratios estimated on series of the *same* length as the graded series, which is
   exactly what defect 3 lacks.

### 3.4 The holdout is statistically too short to carry the claim

**[derived here]**, using Lo, *The Statistics of Sharpe Ratios*, Financial Analysts Journal 58(4),
2002 (**(a)**, [PDF](https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf)),
`SE(SR) ≈ sqrt((1 + SR²/2)/T)`:

| OOS length | SE(annual Sharpe) | 95% CI around an observed 1.5 |
|---|---|---|
| **2 years (the locked holdout)** | **0.71** | **[0.11, 2.89]** |
| 3 years | 0.58 | [0.37, 2.63] |
| 5 years | 0.45 | [0.62, 2.38] |
| 10 years (concatenated development record) | 0.32 | [0.88, 2.12] |
| 14 years | 0.27 | [0.97, 2.02] |

- Years needed to **separate Sharpe 1.5 from 0.5** at 5% size / 90% power: **9 years**.
- Years needed to **reject Sharpe ≤ 0** when the truth is 1.5: **4 years**.

So: the 2024–2025 locked holdout, graded once, **cannot distinguish a Sharpe of 1.5 from a Sharpe of
0.1**. It is a good falsification device (it can kill a bad system) and a useless confirmation device
(it cannot certify a good one). The 10-year concatenated development record *can* support the claim
statistically — but it is the record against which the design was iterated, so its selection bias is
precisely what nobody has counted. **This is the real bind, and no amount of DSR arithmetic resolves
it.** See Q6.1–Q6.3.

Note also the Lo (2002) serial-correlation warning, which `metrics.py:73` already declares honestly:
the naïve √252 annualisation can overstate an annualised Sharpe "by as much as 65 percent" when
returns are positively autocorrelated — the sign that applies to trend strategies. That declared
deviation is correct and should be *acted on*, not just declared, before a number is compared to 1.5.

---

## Q4. Target realism

The companion pass grades the §14 table strategy-by-strategy. Here is the **statistical** reading,
derived independently.

### 4.1 Internal consistency of the §14 table **[derived here]**

| §14 row | implied by the others? | number |
|---|---|---|
| Positive months > 70% | **No — it is stricter than the Sharpe row** | 70% positive months ⇒ annual Sharpe **1.82**; Sharpe 1.5 ⇒ **66.7%** positive months |
| Positive months > 85% (stretch) | **No — far stricter than the stretch Sharpe** | ⇒ annual Sharpe **3.59** vs stretch 2.5 |
| Win rate > 48% with PF > 1.4 | consistent, but constrains geometry | requires avgWin/avgLoss ≥ **1.52** |
| Win rate > 48% | **contradicts the spec's own §5.6** | §5.6: "published trend-following wins ~35–48% of trades yet profits through R:R" |
| Max DD < 15% with Sharpe 1.5 | consistent, but it is a **volatility** statement | MC over 10y daily paths: median maxDD **1.35× annual vol**, 95th pct **2.15×** ⇒ annual vol must be ≤ **7%**, i.e. ~10.5% annual return |
| SPX correlation < 0.25 | free | FX trend/carry is naturally low-beta; the row will pass without effort and therefore carries no information |

Two of the seven rows are mutually inconsistent, one contradicts the spec's own prose, and one is
free. **The positive-months row is the binding §14 constraint and nobody appears to have noticed.**
Worse, on a 2-year OOS the sd of the observed positive-month fraction is **9.6 percentage points**
**[derived here]** — a true 66.7%-per-month system passes or fails the ">70%" gate essentially at
random.

### 4.2 What credible FX programmes actually report

| source | grade | figure |
|---|---|---|
| Menkhoff, Sarno, Schmeling & Schrimpf, *Currency Momentum Strategies*, JFE 106(3), 2012 ([PDF](https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20(1).pdf), [BIS WP 366](https://www.bis.org/publ/work366.pdf)) | **(a)** | MOM(1,1) annualised Sharpe **0.95**; carry **0.82** — **gross**, cross-sectional, on a ~48-currency universe including illiquid EM |
| Menkhoff, Sarno, Schmeling & Schrimpf, *Carry Trades and Global FX Volatility*, JF 67(2), 2012 | **(a)** | carry returns are compensation for global FX volatility risk — i.e. the Sharpe is a risk premium, not an inefficiency |
| Neely, Weller & Ulrich, *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market*, JFQA 44(2), 2009 ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345)) | **(a)** | technical-rule excess returns of the 1970s–80s were genuine, **had disappeared by the early 1990s** for filter and MA rules; less-studied rules declined but had "probably not completely disappeared" |
| McLean & Pontiff, *Does Academic Research Destroy Stock Return Predictability?*, JF 71(1), 2016 ([PDF](https://www.hec.ca/finance/Fichier/McLean.pdf)) | **(a)** | predictor returns **26% lower out-of-sample**, **58% lower post-publication** |
| Barclay Currency Traders Index ([BarclayHedge](https://portal.barclayhedge.com/cgi-bin/indices/displayIndices.cgi?indexID=cta)) | **(b)** | the realised industry aggregate: **+1.93% YTD Aug 2026**, negative in 2025 YTD. Professional currency managers as a class are not producing Sharpe 1.5 |

**Verdict.** The dual-EMA/RSI core ACIS actually optimises is precisely the rule family Neely,
Weller & Ulrich show stopped working in FX by the early 1990s. The strategies that *do* have durable
published evidence report gross Sharpe ≈0.8–0.95 on wide cross-sections, and both sources note
sensitivity to transaction costs. Applying the McLean–Pontiff haircut to any published figure, and
then narrowing the universe from 48 currencies to 2, leaves nothing that supports **1.5 net**.
**Statistically implausible** is the right grade for the Sharpe row, and it is the row every other
target is anchored to.

### 4.3 Does our sample support the claim we intend to make?

No, and the gap is quantified in §3.4. Concretely:

- To claim "Sharpe > 1.5" as distinct from "Sharpe ≈ 0.5" needs **9 years of clean OOS**
  **[derived here]**. The locked holdout is 2.
- To claim "the edge is real" (Sharpe > 0) at the observed 1.5 needs **4 years**. The locked holdout
  is 2 — borderline, and only if the point estimate really is 1.5.
- Bailey et al.'s MinBTL for the *search size actually performed* (N ≈ 108,000) is **23 years** at an
  IS Sharpe criterion of 1.0 **[derived here]**. The whole dataset is 14.

The honest formulation of what 2012–2025 can support is therefore **"we can falsify, we cannot
certify."** A validation protocol built on that premise is a different protocol from one built on
"pass §14 and go live" — see Q6.

### 4.4 A cost-model finding, since it determines everything above

`core/optimizer/costs.py::per_side_cost = spread/2 + commission_per_side + slippage_per_side`, and
`config/instruments.yaml` sets `EUR_USD: commission_per_side: 0.0, slippage_per_side: 0.00002`
(0.2 pip/side). The `spread` fed in comes from **Dukascopy** tick bid/ask
(`regime_labels.py:66` takes `st.spread` from `MarketState`). Dukascopy is an ECN feed: its spreads
are ECN-tight *because the venue charges commission*. Modelling ECN spreads with
`commission_per_side = 0.0` takes the benefit of one venue's pricing and the cost structure of
another. A real ECN account is ~0.3–0.4 pip round-trip in commission on top of the quoted spread —
roughly a **50–70% increase** in the modelled round-trip cost for EUR/USD. Every §14 number is
levered on this. (The spec says the C8 parameters are "phase-11 OANDA calibration"; OANDA is a
spread-only venue, so the calibration and the tick source are not the same venue — that mismatch is
the defect, not the zero itself.)

---

## Q5. Fitness function design

### 5.1 What it actually selects for **[derived here]**

Nominal (spec §5, ACIS-03 §6.1):
`0.40·mean_sigma_c + 0.20·win_rate + 0.20·pf_c − 0.20·mdd_pen`, gated on `E_R > 0`.

Measured over a grid of plausible 200-trade series (win rate 0.35–0.65 × avgWin/avgLoss 0.8–2.5),
the **span of each weighted term** — i.e. how much it can actually move the ranking:

| term | nominal weight | realised span | **share of discrimination** |
|---|---|---|---|
| `0.40 · mean_sigma_c` | 0.40 | 0.180 → 0.227 (0.047) | **9.5%** |
| `0.20 · win_rate` | 0.20 | 0.066 → 0.146 (0.080) | 16.1% |
| `0.20 · pf_c` | 0.20 | 0.027 → 0.200 (0.173) | 34.9% |
| `−0.20 · mdd_pen` | 0.20 | −0.200 → −0.004 (0.196) | **39.5%** |

The cause is `mean_sigma_c = clamp01((s + 3)/6)` (`fitness.py:212`). Per-trade mean/σ for any
realistic minute-bar system lives in roughly [−0.3, +0.4]; mapping that onto a ±3 range compresses
the term to ≈0.45–0.57. **The largest nominal weight is the smallest effective one, by a factor of
four.** A spec sentence that reads "Fitness = Sharpe×0.40 + …" is describing a system that is
actually ranking candidates ~40% on a drawdown ratio and ~35% on profit factor.

Three further structural problems with the composite:

1. **`mdd_pen = max_drawdown / gross_win` is not a risk measure.** Normalising drawdown by gross
   profit means a candidate can improve its score by *trading more* (raising `gross_win`) at
   unchanged risk. It rewards turnover — the one thing a 1 bp-cost retail system must not do.
2. **The components are strongly collinear.** `win_rate`, `pf_c` and `mdd_pen` are all functions of
   the same win/loss distribution (visible in the measured grid: `pf_c` and `mdd_pen` move together
   almost perfectly). The "four-component composite" is effectively two-dimensional, so the weights
   are not doing the tuning work they appear to do.
3. **`pf_c` saturates at PF = 3** and `mean_sigma_c` at |s| = 3; beyond those points the objective is
   flat, so the optimiser is indifferent between a good candidate and an excellent one.

### 5.2 Is including win rate a known error?

**Yes, in the specific sense that matters here.** Win rate is a free parameter of the exit geometry,
not a property of the edge: widen the stop and tighten the take-profit and the win rate rises
monotonically at constant (or falling) expectancy. Rewarding it with a positive coefficient biases
the search toward tight-TP/wide-SL designs — negatively skewed, left-tail-heavy payoff geometry.
That is precisely the shape the DSR's own skew term penalises at the grading stage, so the optimiser
and the grader are pulling in opposite directions.

ACIS is *aware* of this: §5.6 says "Maximise win rate is honoured only as maximise win rate
**subject to** positive expectancy," and C9 implements the constraint. **But a constraint and a
reward are different things.** C9 removes E ≤ 0 candidates; the 0.20 coefficient then still ranks the
survivors by win rate, delivering 16% of the discrimination — 1.7× more than the risk-adjusted term.
If the intent is "subject to", the correct implementation is the gate alone, with **zero** weight on
win rate in the objective.

The spec's own §5.6 sentence — "published trend-following wins ~35–48% of trades yet profits through
R:R" — is the argument against its own §5 formula, and against the §14 win-rate row.

### 5.3 What objective functions are defensible

Ranked by how well they are supported:

1. **Expectancy per unit of risk, measured on the *decision* horizon** — i.e. mean net PnL per trade
   divided by the volatility of that PnL, with no transform and no clamp, on the same holding horizon
   the engine trades. This is the `mean_sigma` term *without* the compression, and it is the only
   component here with a defensible decision-theoretic reading.
2. **Robustness / plateau criteria.** The strongest practical anti-overfitting device in the
   evolutionary-trading literature is not a better metric but a *neighbourhood* requirement: score a
   candidate by the **worst** or **mean** fitness in a ball around it in parameter space, so isolated
   spikes in the fitness landscape cannot win. **ACIS's own spec already mandates this** (§5.6
   anti-overfitting law: "Parameter plateaus required — a strategy that dies at ±10% on any parameter
   fails") — **and it is not implemented anywhere in the codebase.** `grep -rn plateau --include=*.py`
   returns exactly one hit, a prompt string in `monitoring/prompts.py:40`. This is a spec obligation
   with no code, and it is the single highest-value-per-line change available.
3. **Utility-based objectives** (CRRA/Kelly-fractional certainty equivalent). Defensible, and
   naturally penalises left tails without a hand-tuned drawdown term; but it needs a declared risk
   aversion, which is a spec decision.
4. **Weighted composites of correlated performance ratios** — what ACIS has. The practitioner
   consensus is blunt and, for once, correct: "A GA doesn't optimize your strategy — it optimizes
   your fitness function… Most 'GA overfitting' is really fitness misspecification" (**(c)**, but
   consistent with (a) sources on search-induced overfitting). A composite of four collinear ratios
   with hand-set weights maximises the number of ways in-sample luck can enter the score.

**Direct answer to the question asked:** a weighted composite like this selects for **in-sample
luck**, not robustness — not because compositing is wrong in principle, but because (i) it contains
no out-of-sample or neighbourhood term at all, (ii) its components are collinear so the weights are
not identifiable, and (iii) its nominal and effective weights differ by 4×. The §6.3 chronological
holdout is the only robustness device present, and with `holdout_min_trades: 5` it has essentially
no power.

### 5.4 One more mismatch, already in the ledger and worth restating here

`GAP-P12D-31` records that `max_holding_periods` (gene range 1–48) is counted in **1-minute bars**
inside `fitness.py`, giving every candidate a ≤48-**minute** hold, while the harness runs the engine
at `max_hold_s = 48 **hours**`. The optimiser is therefore selecting parameters under a horizon ~60×
shorter than the one they are graded on. Combined with GAP-0035 (candidates scored by a dual-EMA
proxy, graded on six different AGON modules), the fitness function is not a noisy estimate of the
graded objective — **it is an estimate of a different objective.** No amount of multiple-testing
correction repairs that, and it is the most plausible single explanation for the failed engine-level
falsification run recorded in GAP-P12D-31.

---

## Q6. What would make our validation trustworthy

Ranked by value-for-effort. **[impl]** = implementation change inside the existing contract;
**[spec]** = requires human ratification because it changes a locked spec value or a §14 claim.

| # | Change | Type | Value / effort |
|---|---|---|---|
| **1** | **Fix the DSR's trial basis, or stop gating on it.** The trial Sharpe ratios must be estimated on series of the same length and from the same generating process as the graded series. The only clean way to get that is CPCV paths (#3). Until then: compute the DSR but **do not gate** on it, and record it with the sample-length mismatch as a declared deviation. As wired, the gate returns ≈0 for an honest run and ≈1 for an under-recorded one — it is worse than no gate, because it confers false assurance in exactly the case it should refuse. | **[spec]** (C-BT-11 / GAP-P12D-16 is owner-ratified) | Highest. The current gate is a blocking defect either way. |
| **2** | **Delete the perverse incentive immediately.** `n_trials = len(trials) + min_trials` with `V` estimated from the same `trials` means recording fewer trials loosens the gate. At minimum, floor the trial variance at a value derived from the graded series' own estimation noise, and refuse to compute a DSR when `len(trials) < 10`. | **[impl]** | Very high / one function. |
| **3** | **Add PBO via CSCV as the primary honesty gate.** Record every QIEA individual's fitness per time block (a logging change — the evaluations already happen), then run CSCV over the configuration × block matrix. PBO answers "is my selection procedure over-fitting?", degrades correctly as N grows, and needs no guess at N. | **[impl]** to compute, **[spec]** to gate | Highest value per unit of new compute. |
| **4** | **Record the true trial count, and the effective one.** Log all 600 per-run evaluations (id, genes, fitness, holdout Sharpe) to the attempt registry, including gated-out runs. Then estimate effective N by clustering the candidates' return series (López de Prado & Lewis ONC). Report both the literal and the effective count. | **[impl]** | High / moderate. |
| **5** | **Implement the §5.6 plateau law.** Score each champion by the worst fitness in a ±10% ball on every gene, and refuse to stage a champion that dies inside the ball. This is already spec-mandated and entirely absent from the code. It is the cheapest genuine anti-overfitting device available and it acts at the point where overfitting enters. | **[impl]** (discharges an existing spec obligation) | Highest value per line of code. |
| **6** | **Raise the per-fit sample floors.** `fitness_min_trades: 10` and `holdout_min_trades: 5` cannot support a best-of-600 selection. A Sharpe on 5 trades has sd 0.45. Floor both at ≥30 (matching `_MIN_TRADES`) and refuse to evolve a regime that cannot supply it. | **[impl]** (config value; tightening only) | High / trivial. |
| **7** | **Pool the parameter fit.** Fit one parameter set across instruments and across regimes, and let the regime modulate *weight*, not *parameters*. Reduces 99 fitted parameters per instrument to ~11 shared, roughly 9× every per-cell sample, and cuts the family-wise exposure by the same factor. | **[spec]** (§5 ParamSet / per-regime library) | Highest statistical value, largest change. |
| **8** | **Fix the §14 table's internal contradictions before it is used to grade anything.** Positive-months > 70% implies Sharpe 1.82 and is the binding row; the stretch 85% implies 3.59. Either derive positive-months from the Sharpe target or delete the row. Delete the win-rate row (it is exit geometry, and it contradicts §5.6). State max-DD as a volatility target. | **[spec]** | High / cheap, but it is a §14 edit. |
| **9** | **Re-state what the locked holdout can prove.** Two years gives a 95% CI of [0.11, 2.89] around an observed Sharpe of 1.5. The holdout can **falsify**; it cannot **certify**. Write the go-live criterion as a falsification test ("does the holdout refute the development-record hypothesis at the declared tolerance?"), not as a §14 pass. | **[spec]** | High / cheap. It changes a claim, not a computation. |
| **10** | **Count the outer loop.** Maintain a design-iteration register: every time the pipeline, gene ranges, regime definitions, fitness weights or cost model change and are re-evaluated against 2012–2023, that is one trial against the development record. It is the only multiple-testing exposure that actually threatens the final grade, and it is currently uncounted. Cheap, and it is a ledger-discipline matter more than a code one. | **[impl]** (ledger) | High / near-zero effort. |
| **11** | **Apply, don't just declare, the Lo (2002) autocorrelation correction** to the §14 annualised Sharpe — or report both figures side by side. `metrics.py:73` already names the bias and its direction (trend returns are positively autocorrelated ⇒ √252 *overstates*), and the bias lands directly on the live gate. | **[impl]** + **[spec]** if it changes the graded number | Medium / low. |
| **12** | **Declare the per-trade-return deviation properly.** The DSR's `sqrt(T-1)` assumes near-iid observations; concurrent positions across correlated pairs are not. Either use the daily equity-curve returns (already computed, `_returns_from_equity`) as the graded series — which also makes it commensurate with the §14 annual Sharpe — or add the cross-sectional dependence to `declared_deviations`. | **[impl]** | Medium / low. |
| **13** | **Add a cross-instrument holdout.** Reserve two declared-but-disabled pairs (e.g. `GBP_USD`, `AUD_USD`) that no fit ever touches, and grade the frozen parameters on them. This is the cheapest test of whether the fit found structure or noise, and it is orthogonal to every time-based split. | **[spec]** | Medium-high / low. |
| **14** | **Fix the cost model's venue mismatch.** Dukascopy ECN spreads with `commission_per_side: 0.0` understate round-trip cost by ~50–70% on EUR/USD. Either add the ECN commission or calibrate the spread series to the spread-only venue actually being traded. | **[impl]** (config, but guardrail-adjacent — raise it) | Medium-high / trivial, and it moves every §14 number. |

### 6.1 The one-paragraph answer

A "pass" on this system would mean something if the honesty gate were **PBO from CPCV paths** rather
than a DSR fed with incommensurable trials; if the trial register contained **every** configuration
evaluated rather than only the winners; if the optimiser were forbidden from staging a champion that
dies within ±10% of its own genes (the spec's own rule, unimplemented); if the parameter count were
pooled down from 99-per-instrument to something a 2-year window can carry; and if the final claim
were stated as a falsification the 2024–25 holdout is actually powerful enough to perform, rather
than a certification it is not. Every one of those is achievable inside the existing architecture.
None of them is what the current gate does.

---

## Appendix A — where our implementation is wrong about a method it names

Stated plainly, because this is the category the brief asked for.

| the code names | the referent says | the gap |
|---|---|---|
| "Deflated Sharpe Ratio (Bailey & López de Prado 2014)" | N is the number of trials **carried out**; the N trial SR estimates and the selected SR come from the **same** estimation setting | trials = the ≤180 **winners** of a 108,000-configuration search, estimated on **5–50** trades, deflating a statistic estimated on **thousands** — a category error, not an approximation. Not in `declared_deviations`. |
| "N independent trials" | correlated trials ⇒ effective N **below** the literal count; cluster to estimate it (LdP & Lewis 2019) | declared deviation (1) acknowledges the clustering omission but the far larger under-count of the literal N is not declared at all |
| "López de Prado's purge/embargo" (`walk_forward.py`) | embargo length is set by the horizon over which train and test share information — **label window and feature memory** | embargo is set to ≥ max *hold* (48 h) only; TSMOM's 3–12-month feature lookback is two orders of magnitude longer |
| "Fitness = Sharpe×0.40 + …" (spec §5, ACIS-03 §6.1) | a weight of 0.40 should mean 40% of the ranking influence | the ±3 clamp compresses the term to ~9.5% of realised discrimination; the drawdown ratio (nominal 0.20) supplies ~39.5% |
| "MaxDrawdownPenalty" | a drawdown penalty is a **risk** term | `max_drawdown / gross_win` falls as turnover rises at constant risk — it rewards trading more |
| "Win rate is a component, never the objective" (C9) | a *constraint* removes candidates; it does not rank them | C9 gates correctly **and** the 0.20 coefficient then ranks survivors by win rate at 1.7× the influence of the risk-adjusted term |
| §14 "Annual Sharpe > 1.5" as the minimum | the table's own "positive months > 70%" row implies **1.82** | the stated minimum is not the binding one; the binding one was never derived |
| C8 "fitness is net of costs… calibrated against OANDA practice-feed spreads" | the spread series fed to the cost model is **Dukascopy** ECN | ECN spreads priced with zero commission: one venue's spreads, another's cost structure |

## Appendix B — reproducing the numbers

Three read-only scripts were used; they touch no repo state and are in the session scratchpad:

- `stats.py` — SR₀ vs N and vs trial dispersion; per-trade DSR thresholds; Lo (2002) Sharpe standard
  errors and the years-to-separate calculations; bars-per-regime arithmetic; QIEA configuration
  counts.
- `targets.py` — positive-months ↔ Sharpe mapping; win-rate/profit-factor consistency; Monte-Carlo
  maximum drawdown as a multiple of annual volatility (2,000 paths × 10 years daily, seed 7).
- `fitness_sens.py` — imports `core.optimizer.fitness` read-only and measures the realised span of
  each weighted fitness term over a 4×4 grid of (win rate, avgWin/avgLoss) 200-trade series.

Key constants read from the repo: `config/system_config.yaml` (`population_size: 20`,
`generations: 30`, `fitness_span_days: 730`, `fitness_min_bars: 300`, `fitness_min_trades: 10`,
`holdout_fraction: 0.20`, `holdout_min_trades: 5`, `expectancy_min_r: 0.0`);
`config/instruments.yaml` (2 enabled instruments; `EUR_USD` commission 0.0, slippage 0.00002);
`core/regime/regime_types.py` (12 regimes, 3 never-tradeable ⇒ 9 evolved);
`tests/backtest/oos_plan.py` (`TRAIN_YEARS = 2`, `EMBARGO = 7 days`, holdout 2024–2026).

## Sources

- Bailey, D. H. & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*. Journal of Portfolio Management 40(5). **(a)** — [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) · [author PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2016). *The Probability of Backtest Overfitting*. Journal of Computational Finance 20(4). **(a)** — [author PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) · [eScholarship](https://escholarship.org/uc/item/4w1110bb)
- Bailey, D. H., Borwein, J., López de Prado, M. & Zhu, Q. J. (2014). *Pseudo-Mathematics and Financial Charlatanism*. Notices of the AMS 61(5). **(a)** — [Statistical Overfitting and Backtest Performance](https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf)
- López de Prado, M. & Lewis, M. J. (2019). *Detection of False Investment Strategies Using Unsupervised Learning Methods*. Quantitative Finance 19(9), 1555–1565. **(a)** — [SSRN 3167017](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167017) · [PDF](https://codemacher.com/wp-content/uploads/2021/02/Detection-of-false-investment-strategies-using-unsupervised-learning-methods_M.LopezDePrado_and_M.Lewis_2018.pdf)
- López de Prado, M. (2018). *Advances in Financial Machine Learning*, ch. 7 (purged/embargoed CV) and ch. 12 (CPCV). **(a)** — [purged cross-validation overview](https://en.wikipedia.org/wiki/Purged_cross-validation) **(c)**
- Lo, A. W. (2002). *The Statistics of Sharpe Ratios*. Financial Analysts Journal 58(4). **(a)** — [PDF](https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf) · [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios)
- White, H. (2000). *A Reality Check for Data Snooping*. Econometrica 68(5). **(a)** — [ResearchGate](https://www.researchgate.net/publication/2551052_A_Reality_Check_For_Data_Snooping)
- Hansen, P. R. (2005). *A Test for Superior Predictive Ability*. JBES 23(4). **(a)** — [ResearchGate](https://www.researchgate.net/publication/4724332_A_Test_for_Superior_Predictive_Ability)
- Hsu, P.-H. & Kuan, C.-M. *Re-Examining the Profitability of Technical Analysis with White's Reality Check*. **(a)** — [PDF](https://homepage.ntu.edu.tw/~ckuan/pdf/snoop01.pdf); stepwise SPA: [PDF](https://homepage.ntu.edu.tw/~ckuan/pdf/Step-SPA-20090720.pdf)
- Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, A. (2012). *Currency Momentum Strategies*. JFE 106(3). **(a)** — [PDF](https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20(1).pdf) · [BIS WP 366](https://www.bis.org/publ/work366.pdf)
- Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, A. (2012). *Carry Trades and Global Foreign Exchange Volatility*. Journal of Finance 67(2). **(a)** — [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2012.01728.x)
- Neely, C. J., Weller, P. A. & Ulrich, J. M. (2009). *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market*. JFQA 44(2). **(a)** — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345) · [Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/adaptive-markets-hypothesis-evidence-from-the-foreign-exchange-market/9D336CDCA83233819EB5CDD0F4BC0DAA)
- McLean, R. D. & Pontiff, J. (2016). *Does Academic Research Destroy Stock Return Predictability?*. Journal of Finance 71(1), 5–32. **(a)** — [PDF](https://www.hec.ca/finance/Fichier/McLean.pdf) · [SSRN 2156623](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623)
- Dacco, R. & Satchell, S. (1999). *Why do regime-switching models forecast so badly?*. Journal of Forecasting 18(1), 1–16. **(a)** — cited via the companion research pass
- BarclayHedge, Barclay CTA / Currency Traders Index. **(b)** — [portal](https://portal.barclayhedge.com/cgi-bin/indices/displayIndices.cgi?indexID=cta)
- MetricGate, *Deflated (Johnson) Sharpe Ratio* reference. **(c)** — [docs](https://metricgate.com/docs/deflated-johnson-sharpe-ratio/)
- LuxAlgo, *Deflated Sharpe Ratio* concept note (same-sample-length assumption). **(c)** — [library](https://www.luxalgo.com/library/concept/deflated-sharpe-ratio/)
- Applied Markov-switching sample-size guidance. **(c)** — [MetricGate](https://metricgate.com/docs/regime-switching-models/); Monte-Carlo floor in the high-dimensional setting **(a)** — [arXiv 2205.12126](https://arxiv.org/pdf/2205.12126)
