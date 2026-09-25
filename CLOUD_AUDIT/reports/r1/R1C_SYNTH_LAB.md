# R1-C — SYNTHETIC MARKET LAB (final)

- **Lane:** R1-C, synthetic market lab. ACIS mission R1, reports only.
- **Model and effort as I observe them:** Claude Opus 5.5 (`claude-opus-5-5`). The effort setting is not visible to
  me.
- **Fresh context:** yes. I read these, and nothing else from the prior review:
  - BRIEF_R1 (§0 and §C), and FLEET_PLAN §1 and §6;
  - C3 §2.5 and §5, P3 § C3, and C2 §2.7;
  - the LEAD bridge probe, and VAL §8 (the reconciliation R1–R6);
  - the BASE files cited below.
- **BASE:** `974dbda`, read-only at `/tmp/review-acis`. Nothing there was written. My runs left no `.pyc` newer
  than the session.
- **Date:** 2026-09-25. Work ran 08:00–08:35 UTC.
- **Web:** 23 of the 25 allowed (searches and fetches combined, including 2 `curl` PDF fetches). 5 of the fetches
  failed or were partial (§6).
- **Everything is synthetic.** No real price series was downloaded, loaded, bootstrapped or computed from. Every
  stylized-fact target is quoted from the literature. The one real-data-derived number I use is the rollover spike
  range at `ACIS_SPEC.md:407`, which the project recorded; I did not compute it. It sets a spread knob only, never an
  edge. Every design idea here is **LLM-originated**.

---

## 1. Executive summary

1. **At R-1's breadth the demeaning bug decides the verdict.** Grade: own simulation, and a closed form that
   matches it.
   - Whole-path demeaning (`tests/backtest/synthetic_market.py:113-114`) turns every path into a Brownian bridge.
     The tilt has the same sign on every instrument, so pooling adds it up while the noise averages out.
   - On 2.8-year null paths, one instrument's annual Sharpe bias is **−0.26** (126-day momentum) and −0.17 to −0.28
     (EWMAC at 8/32 to 32/128).
   - Pooled over 20 instruments it is about **−1.2, and +1.2 for the mirror reversal rule.** On the demeaned null,
     a pooled reversal rule is a false positive.
   - A direct pooled simulation (EWMAC 16/64, 20 correlated lab instruments, 400 seeds) gives:
     - the null: **−0.199** (6 se from zero);
     - the power on a planted trend: **halved** (18.8% against 40.3%).
2. **The fix is to demean nothing. Permuted also needs a sign flip, because permuted is a bridge by construction.**
   Grade: own simulation.
   - A shuffle of a fixed set of returns has a fixed sum, so it is a bridge. BASE's shuffle-then-demean pins that
     sum at zero.
   - C3's alternative, "demean only the planted drift", is itself a bridge on the drift. It cost 45% of the slow
     rule's planted Sharpe.
   - Permuted must be built as **shuffle + one independent random sign per return** (per day in the lab). That is
     a martingale-difference sequence given the pool, so every non-anticipating rule has exactly zero expected
     gross P&L. Measured: |t| < 1 on every rule tried.
3. **New defect: the BASE planted market is ~3.3× more volatile per day than its null.** Grade: own measurement on
   the production generator, analytic ratio 3.51.
   - Daily sd is 0.0176 on planted against 0.0053 on null, because the 1–4 h episodes carry ~92% of planted's
     daily variance.
   - The frictionless oracle's annual Sharpe is about **157**.
   - So "planted passes, null fails" also compares a ~28%-vol market with an ~8%-vol one: a different cost/move
     ratio, ATR, NVMA inputs, stops and VaR. The lab plants **variance-matched** effects.
4. **The machinery lab is parametric.** Grade: primary sources (a/b) plus own reasoning.
   - GANs and diffusion models are data-driven. Training one on real series is a look (§0.4), and diffusion
     models are shown to memorise training items.
   - Neither family offers a *plantable effect with a known Sharpe*, and a surveyed author states "no model yet
     satisfies all the stylized facts".
   - Agent-based simulators (ABIDES) are equity-protocol, heavy, and give ground truth only at the agent level.
   - **Verdict:** adopt parametric; reject GAN and diffusion for the lab; ABM is out of scope for R-1.
5. **The prototype works.** Grade: own simulation.
   - It generates 20 instruments × 3,640 weekdays in **~130 ms** (40 instruments in 155 ms), and intraday ticks in
     1.3 ms per day for 20 instruments.
   - It has:
     - a common factor;
     - Student-t shocks by scale mixture;
     - GARCH(1,1) × a multi-scale log-volatility;
     - jumps;
     - weekend gaps;
     - rate differentials and financing;
     - session spreads with a rollover spike and random spikes;
     - five plantable effects with closed-form or calibrated Sharpe.
6. **Stylized facts: the lab passes 9/9 probes; a plain GARCH(1,1) fails the discriminating one.** Targets are
   quoted from Cont (2001), grade (a).
   - Lab results:
     - no linear autocorrelation;
     - Hill tail index 3.52, inside "higher than two and less than five";
     - skew +0.04, consistent with FX's up/down symmetry;
     - aggregational Gaussianity;
     - volatility clustering;
     - conditional heavy tails;
     - slow decay β = 0.400, with a power law fitting better than an exponential.
   - GARCH(1,1) alone gives β = 0.33, inside Cont's range, **but an exponential fits better** (R² 0.98 against
     0.78). The β-range alone does not discriminate; the shape test does.
7. **The lab is calibrated.** Grade: own simulation.
   - Test: a parameter-free pooled EWMAC 16/64 on 20 lab instruments, run on the null, a planted trend, and
     permuted.
   - **The null centres on zero:** −0.020 ± 0.031 (2.8-year paths) and −0.013 ± 0.025 (13.3-year paths). False
     detection is 4.3% and 4.0%.
   - **The planted trend is detected at the theoretical rate:** 40.3% against a theory of 39.8% (2.8 years), and
     96.0% against 91.5% (13.3 years). The mean Sharpe is 0.806–0.808 against a theory of 0.828.
8. **Intraday refinement must bridge the common factor jointly, or it plants a pairs edge.** Grade: own simulation.
   - Separate per-instrument bridges pinned at correlated daily closes make j's day-so-far predict i's rest of the
     day: +0.08 to +0.12 vol units a day, t 6.3–8.6.
   - One shared factor bridge plus idiosyncratic bridges gives |t| ≤ 1.7 on three seeds.
9. **Integration needs no second cost model or financing model.** Grade: code references.
   - The lab sets only the *quoted* bid/ask, and `CostModel.per_side_cost(spread)` (`core/optimizer/costs.py:53`)
     prices it.
   - Financing goes through a synthetic `RateTable` into `make_financing` (`tests/backtest/financing.py:52,90`).
   - The ground truth generalises `episode_sign` (`tests/backtest/synthetic_market.py:145`).
   - **Two BASE unit tests encode the bug** (`tests/backtest/test_synthetic_market.py:27-32, 42-45`) and must change.
10. **Planted effects are not orthogonal to the other families' rules.** Grade: own simulation.
    - A planted carry with persistent rates pays a trend rule +0.16 and an XS rule +0.17 in Sharpe per instrument.
    - Power must therefore be stated per (effect, rule) pair, never per family label.

---

## 2. Body

### 2.1 The defect restated and quantified (task 1)

**Mechanism.** `_returns` subtracts the path's own realised mean from every return
(`tests/backtest/synthetic_market.py:113-114`).
- The sum of a demeaned path is exactly zero, so the path is a random walk *conditioned to end where it started*:
  a Brownian bridge.
- Its increments are negatively correlated: Cov(x_i, x_j) = −σ²/n for i ≠ j.
- Take a past window P of L steps and a disjoint future window F of h steps. Then Cov(F, P) = −hLσ²/n and
  Var(P) = Lσ²(1 − L/n).
- Under joint Gaussianity this gives, per holding step:
  **E[sign(P)·F] = −(h/n)·σ·√L / √(1 − L/n) · √(2/π).**
  This is the lead's closed form (`P3_LEAD_VERIFICATION.md` § C3), re-derived and algebraically identical.
- **As an annual-Sharpe drag on one instrument:** ≈ −√(252·L)·√(2/π) / (n·√(1 − L/n)).
  - It shrinks as 1/n (the path length) and grows as √L (the lookback). It does not depend on the tick count or
    the holding period.
  - That is why it is negligible for BASE's minute-scale arena and **material for R-1's daily rules on short
    paths**.

**What R-1 changes: pooling makes the bias coherent.** The tilt has the same sign on every path. Pooling N
independent instruments multiplies the mean by N and the noise by √N, so the pooled Sharpe bias grows like √N.

| Null, daily analogue (`repro_bridge.py`, 800 paths each) | n = 705 weekdays (the ladder span): per instrument → pooled N = 20 (×√20) | n = 3,640 (14 y): per instrument → pooled |
|---|---|---|
| 126-day momentum, BASE (demeaned) | −0.259 → **−1.16** (t −9.9) | −0.047 → −0.21 (t −4.9) |
| 126-day **reversal**, BASE | **+0.259 → +1.16** | +0.047 → +0.21 |
| 63/126/252 vote, BASE | −0.317 → −1.42 | −0.056 → −0.25 |
| EWMAC 8/32 · 16/64 · 32/128, BASE | −0.17 · −0.22 · −0.28 | −0.03 · −0.04 · −0.06 |
| Every rule, FIX-A (undemeaned) | \|t\| ≤ 1.2 | \|t\| ≤ 2.2 |
| Closed form, 126-day momentum, mean per path | −0.0312 (simulated −0.0363 ± 0.004) | −0.0423 (simulated −0.0505 ± 0.010) |

The pooled column above assumes independent instruments. The direct pooled simulation in §2.8 uses correlated lab
instruments with a vol-targeted rule, which dilutes the tilt. It still measures **−0.199** on 2.8-year paths (6 se)
and −0.03 on 13.3-year paths.

**The three fixes, on planted and permuted** (daily analogue: 5–20-day episodes at 0.15 sd/day, per-instrument annual Sharpe):

| Kind / variant | mom126 | vote | EWMAC 8/32 | EWMAC 32/128 |
|---|---|---|---|---|
| planted, BASE (demean the whole path) | −0.098 | −0.142 | +0.232 | −0.210 |
| planted, **FIX-A (demean nothing)** | **+0.178** | **+0.182** | **+0.359** | **+0.096** |
| planted, FIX-B (demean the drift only; C3's option) | +0.101 | +0.091 | +0.329 | +0.037 |
| permuted, BASE (shuffle, then demean) | −0.249 | −0.293 | −0.109 | −0.269 |
| permuted, shuffled but not demeaned | +0.049 | +0.072 (t 2.5) | +0.040 | +0.052 |
| permuted, **FIX-C (shuffle + random sign)** | +0.025 (t 0.9) | +0.018 | +0.006 | +0.012 |

**Why the author demeaned, and why the sign flip is the right tool.**
- In the BASE tick generator the planted episodes dominate the path's net drift. Episode-drift variance is
  d²·Σlen², which is **~11× the noise variance** at d = 0.15σ and lengths of 180–720 steps (§2.2).
- So an undemeaned *shuffle* would carry a large, real, within-path drift that a slow rule harvests.
- Demeaning "fixed" that by pinning the sum, which is a bridge. A random sign per return removes both problems:
  - the conditional mean is exactly zero;
  - the increments are uncorrelated;
  - every |move| is kept.

**Which BASE tests change.**
- `tests/backtest/test_synthetic_market.py:27-32` asserts `abs(math.fsum(returns)) < 1e-9`: zero *realised* drift.
  **That is the bug, written down as a test.** Replace it with zero *expected* drift: over about 200 seeds, the
  mean of path sums lies within 3 se of 0. Also add a martingale check: the mean of sign(past L)·future h lies
  within 3 se of 0 at L ∈ {63, 126, 252} on a daily-tick spec.
- `:42-45` asserts `sorted(planted) == sorted(permuted)`. It becomes `sorted(map(abs, …))`.
- `tests/backtest/test_oracle_control.py:44-59` already subtracts an offset ("up to the two markets' different
  demeaning constants"), so it holds with the offset at 0.
- `:262` and `:266` (planted annual Sharpe > 5; null net < planted/10) are unaffected in sign.
- **Re-verify the oracle rungs** (`tests/backtest/oracle.py:127`, `RUNGS` 0.42/0.46, calibrated near the
  PF-1.4 cut). Planted returns shift by the removed constant, about 1% of the drift per step.
- Re-fingerprint every recorded synthetic run, as C3 §5 item 2 asked.

### 2.2 New: the BASE planted market is a different-volatility market

`evidence/R1C/probe_planted_vol.py` calls the production `_returns` read-only, at the BASE defaults
(`MarketSpec`: `daily_vol` 0.005, `drift_sigma` 0.15, episodes 1–4 h, 20 s ticks).

| kind | daily sd | hourly sd | per-tick sd |
|---|---|---|---|
| null | 0.00530 | 0.00103 | 7.61e-5 |
| **planted** | **0.01759** | 0.00216 | 7.69e-5 |
| permuted | 0.00463 | 0.00102 | 7.69e-5 |

- **Analytic check.** The daily variance ratio is 1 + drift_sigma²·E[len²]/E[len] ≈ 12.3, so the sd ratio is
  **3.51**. Measured: 3.32.
- **Frictionless oracle.** Its per-step Sharpe is `drift_sigma`, which annualises to 0.15·√(252·4,320) ≈ **157**.
  This fits GAP-P12D-37's history (the old gate needed an annual Sharpe of 76 on planted).
- **Consequence.** Two things separate planted from null, not one: the direction *and* the scale.
  - A rule that trades on volatility level (an ATR breakout, a regime gate) behaves differently on planted with
    no directional skill at all.
  - Friction is 3.3× cheaper relative to a daily move.
  - The cost-stress ladder's split between "direction and friction" (GAP-P12D-49) is therefore made on a market
    whose cost/move ratio is not the null's.
- **Fix: variance-matched planting.** Set the planted drift from a target oracle Sharpe and shrink the noise so
  that total variance equals the null's. The lab does this by construction: the drift is in volatility units,
  with var(m) ≈ 0.0024 of the total at a 0.5 oracle Sharpe.
- **Governance.** For the BASE tick generator this changes the positive control's calibration and every recorded
  run, so it is **[spec — owner ratification]**.

### 2.3 Which generator family for a machinery lab (task 2)

**The criterion (§C of the brief):** a machinery lab needs **known, plantable ground truth**. Concretely:
- the expected P&L of the rule under test must be computable, so that a detection rate can be compared with a
  theoretical power;
- the null must be a martingale in the P&L the grader books;
- no real data may enter the generator, because a trained generator is a look.

| Family | Known, plantable ground truth | Needs real data | Stylized facts | Speed | Failure modes (sourced) | Verdict |
|---|---|---|---|---|---|---|
| **Parametric**: GARCH-t / EGARCH, jumps, Markov regimes, weekend gaps, session spreads, a common factor, fat-tailed shocks | **Yes.** The effect is an explicit drift term; its Sharpe is closed-form or calibrated to Monte Carlo precision (§2.4). | No. Knobs are set to quoted literature ranges and are never fitted. | Most. The GARCH-t for daily FX is sourced (Baillie & Bollerslev, below). Slow decay needs multi-scale volatility; plain GARCH(1,1) fails the shape test (§2.5). | ms per path | Mis-specification: it is "a model's world", and a rule that exploits a lab artefact passes. Guarded by the probe set, the permuted control, and never treating lab results as edge evidence. | **ADOPT** |
| **Agent-based** (ABIDES and its variants) | Only at the agent-rule level. Stylized facts *emerge*, and there is no Sharpe-level ground truth. | Usually calibrated to real order-book data. | Partial: "many market simulation approaches fail to reproduce statistics and stylized facts" (Vyetrenko et al.). | Slow: "tens of thousands of trading agents", discrete-event. | Equity protocol ("modeled after NASDAQ's published equity trading protocols ITCH and OUCH"). One search found no FX dealer-market variant. | **REJECT** for R-1's daily machinery lab. Adapt later only for execution or microstructure questions. |
| **GANs** (Quant GANs, TimeGAN) | No. The "truth" is whatever the training data held; nothing can be planted at a known Sharpe. | **Yes.** Quant GANs are "a data-driven model"; TimeGAN keeps "the original relationships between variables". Training on 2012–2025 is a look. | Partial: "no model yet satisfies all the stylized facts" (Takahashi & Mizuno, about GANs and VAEs). | Sampling is fast; training is heavy. | Learns and replays the real sample's structure, including any real edge, which contaminates holdout and forward logic. Mode collapse is widely reported but **not verified here from a finance primary source**. | **REJECT** for the lab |
| **Diffusion models** (2023–2026) | Partial *conditioning*: CoFinDiff meets "specified conditions for trends and volatility", but a condition is not a known rule Sharpe, and its conditions are "derived from price data". | **Yes** | Claimed ("our proposed approach satisfies stylized facts"). | Heavy | **Memorisation:** "diffusion models memorize individual images from their training data and emit them at generation time" (Carlini et al., images). A memorised real stretch inside a lab tape is a covert look. | **REJECT** for the lab |

**Why parametric wins.** It is the only family where the three properties hold together:
- ground truth sits *in the equation*;
- the null is a martingale by construction;
- no real data enters.

Generative models answer a different question ("does my rule survive realistic-looking paths?"). Because they are
trained on the very history R-1 wants to protect, that question is already answered by the contamination rule:
**don't**. A related prior-art lesson: Carr & López de Prado (2014) propose fixing trading rules on synthetic
(Ornstein–Uhlenbeck) paths because "calibrating a trading rule using a historical simulation (also called
backtest) contributes to backtest overfitting". R-1 item 5 takes the safer half of that: **the synthetic lab
tests machinery, never the edge.**

### 2.4 The generator design and prototype (task 3)

`evidence/R1C/gen_lab.py`: 394 lines as a prototype. It is split for production in §2.7. Numpy only. Its
docstring carries the full mental model.

**The construction.** Daily-first. One weekday is one bar, and everything is in volatility units.
- In vol units: y[i,t] = m[i,t] + ε[i,t] + J[i,t] + G[i,t].
- The excess return is x = σ[i,t]·y. The spot return is x − c, where c = rate differential/252 is the financing
  accrual of a long.
- A long that is charged financing therefore earns exactly x. **The null is m ≡ 0: the excess return is a
  martingale difference, and nothing is demeaned.**

| Component | Construction | Default knob |
|---|---|---|
| Common factor | ε_i = b_i·f + √(1−b_i²)·e_i, with b_i = ±√ρ; corr(ε_i, ε_j) = b_i·b_j | ρ = 0.3. The measured Pearson \|corr\| of raw returns is 0.22, because the independent volatility and jump parts dilute it. A per-currency factor is future work. |
| Fat tails | Student-t by variance mixing (N·√w, w = (ν−2)/χ²_ν), separately for f and e | ν = 8 |
| Volatility | σ = σ̄_i · √(GARCH(1,1) on the standardised return) · exp(Σ_k h_k − s²). The h_k are AR(1) log-vol components with log-spaced half-lives of 3, 15, 75, 375 and 1,875 days; E[factor²] = 1 keeps the unconditional variance. | GARCH (a, b) = (0.04, 0.90); log-vol sd 0.5; annual vol spread evenly over 6–14% |
| Jumps | Compound Poisson, Laplace sizes in σ units; the diffusive part is rescaled so total variance is kept | 2 a year, sd 3σ |
| Weekend gap | A Monday-only extra shock (t-distributed), placed on the week's first tick intraday | variance 0.25 of a weekday |
| Carry / financing | Rate differentials as an AR(1) (half-life 500 days, cross-sectional sd 2%). `financing_in_grader=False` forces them to 0 and refuses a planted carry (§2.7 C-6). | on |
| Session spreads | Base × hour profile × (roll_mult for `roll_minutes` after the day's 17:00 New York open) × random spikes | ×8 for 10 min. `ACIS_SPEC.md:407` records 6–13×. Spike probability 0.2%, ×8. |
| Tick arrivals | Quotes thinned by a session-shaped intensity; the path itself is unchanged | half the grid |

**The plantable effects**, each with its Sharpe known:

| Effect | Planted as | Known Sharpe | Verified (`probe_effects.py`, 20 seeds × 20 instruments, target 0.5 per instrument) |
|---|---|---|---|
| **Trend** (speed, strength) | An AR(1) latent drift per instrument (or one common drift, scope `factor`); half-life = speed | Strength = the oracle's annual Sharpe, E = φ√(2/π)√v_m. For **any EWMA crossover the Sharpe is closed-form**: E[sign(X)y′] = √(2/π)·Cov(X, y′)/sd(X), with X = Σ w_k y_{t−k} and w_k = (1−α_s)^{k+1} − (1−α_f)^{k+1} (`theory_ewmac`). | Oracle 0.501 ± 0.013. EWMAC 16/64 0.135 ± 0.021 against a closed form of 0.115. |
| **Carry** | m = κ·z, where z is the standardised rate differential | Rule sign(rate): κ√(2/π) a day; κ solved from the target | 0.500 ± 0.014 |
| **Cross-sectional momentum** | m = u_i − mean_j u_j, u an AR(1); demeaned cross-sectionally *per day* (intended, not a bridge) | The XS oracle's Sharpe, closed-form; a practical rank rule's Sharpe is Monte-Carlo-calibrated | Oracle 0.514 ± 0.016; rank-EWMA60 rule 0.140 |
| **Seasonal / calendar** | Drift s·dir_i on the last trading day and the first three of each month | Closed form in s and the flagged fraction | 0.500 ± 0.018 |
| **Null** | m ≡ 0 | 0 | Every rule within 2 se of 0 |

- **Permuted control** (`permuted()`): shuffle whole days (all instruments together, so the cross-section is
  kept), then one random sign per day. Given the pool it is exactly a martingale difference. Rates keep their own
  path.
- **Cross-talk to report, not to hide.** Planted effects leak into other families' rules, as they do in real
  markets. Carry with persistent rates pays EWMAC 16/64 +0.16 and XS rank +0.17. A planted XS drift pays EWMAC
  +0.12. A lab user must state power per (effect, rule).
- **Speed** (one core, `OMP_NUM_THREADS=1`):
  - daily: 20 × 3,640 in 129 ms, and 40 × 3,640 in 155 ms. That is about 1,000 null paths in ~2–3 minutes;
  - intraday: 20 instruments × 1,440 one-minute ticks in 1.3 ms a day, on demand.

### 2.5 Stylized-facts checks (task 4)

Targets are quoted verbatim from Cont (2001), grade (a), at `http://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf`
(accessed 2026-09-25). `probe_stylized.py` covers 20 instruments × 3,640 weekdays × 4 seeds on the null.

| Cont's fact (quoted) | Lab statistic | Tolerance | Lab | GARCH(1,1) only |
|---|---|---|---|---|
| 1. "(linear) autocorrelations of asset returns are often insignificant, except for very small intraday time scales (≃ 20 minutes)" | share of lags 1–20 outside a **heteroskedasticity-robust** 95% band | ≤ 0.10 (lab tolerance) | **PASS** 0.054 | PASS 0.045 |
| 2. "a tail index which is finite, higher than two and less than five for most data sets studied" | Hill α, top 2.5% | 2 < α < 5 | **PASS** 3.52 (excess kurtosis 9.95) | PASS 3.80 |
| 3. Gain/loss asymmetry; Cont's footnote: "This property is not true for exchange rates where there is a higher symmetry in up/down moves." | mean skew | \|skew\| < 0.2 (lab tolerance) | **PASS** +0.04 | PASS −0.09 |
| 4. "as one increases the time scale over which returns are calculated, their distribution looks more and more like a normal distribution" | excess kurtosis at 1d / 5d / 20d | monotone, and 20d < half of 1d (lab tolerance) | **PASS** 9.95 / 4.58 / 2.47 | PASS 6.20 / 3.97 / 2.23 |
| 6. "different measures of volatility display a positive autocorrelation over several days" | mean acf(\|r\|) over lags 1–5 | > 0.05 (lab tolerance) | **PASS** 0.199 | PASS 0.166 |
| 7. "even after correcting returns for volatility clustering … the residual time series still exhibit heavy tails. However, the tails are less heavy than in the unconditional distribution" | kurtosis(r/σ) against kurtosis(r) | 3 < conditional < unconditional | **PASS** 7.07 < 12.95 | PASS 7.07 < 9.20 |
| 8. "the autocorrelation function of absolute returns decays slowly … roughly as a power law with an exponent β ∈ [0.2, 0.4]" | log-log slope over lags 1–100, **and** whether a power law beats an exponential (R²) | β ∈ [0.2, 0.4] **and** R²(power) > R²(exp) | **PASS** β 0.400; R² 0.943 against 0.895 | **FAIL** β 0.330 but R² 0.776 against **0.978** |
| Intraday seasonality: Andersen & Bollerslev capture "the pronounced intraday activity patterns" in DM-dollar | corr(mean\|r\| by UTC hour, the declared profile); rollover spread spike | > 0.9; spike > 3× an hour off | **PASS** 1.00; 8.3× | same |
| Not modelled or not asserted: 5 intermittency, 9 leverage (an equity fact), 10 volume, 11 time-scale asymmetry | — | — | n/a | n/a |

The FX-specific parametric anchor is Baillie & Bollerslev (1989), grade (a): daily FX first differences "are
approximately uncorrelated through time", and a GARCH "with daily dummy variables and conditionally t-distributed
errors is found to provide a good representation to the leptokurtosis and time dependent conditional
heteroscedasticity". The same abstract observes the leptokurtosis "is reduced as the length of the sampling interval
increases". That is fact 4 for FX.

**Declared tuning. This is honesty, not a result.**
1. I swept the volatility knobs about six times on the lab itself, toward Cont's quoted qualitative targets. I
   never fitted them to data.
2. β = 0.400 sits **at the edge** of Cont's range. Log-vol sd 0.6 gives β = 0.391, but excess kurtosis rises to 13.
3. After the first run I changed two tolerances:
   - the ACF band went from iid to robust. The iid band 1.96/√T is invalid under volatility clustering. Cont makes
     the same point via Mikosch and Starica about GARCH sample ACFs;
   - aggregational Gaussianity went from "20-day < 1.0" to "20-day < half of 1-day". Its first form was an
     arbitrary number that Cont's qualitative statement does not imply.
4. Daily excess kurtosis of 9.95 may be heavier than some FX pairs. I have no quoted per-pair target, so it is a
   knob.

### 2.6 Intraday ticks on demand: exact, and joint (part of task 3)

**Design.** The lab's trading day runs 17:00 New York → 17:00 New York, DST-correct. Monday's day opens Sunday at
17:00 New York, which is the FX convention.
- The diffusive part of each day is Gaussian *given* (σ, the mixing draws). A Brownian bridge on the session
  time-change, pinned at that day's endpoint, therefore has **exactly** the law of generating the ticks forward.
  The endpoint was drawn from the martingale law, so conditioning on it is harmless.
- This is the legitimate use of a bridge. BASE's whole-path demeaning pins a *fixed* endpoint (zero) that no
  forward process would produce.
- The planted drift is spread in proportion to session variance, a jump lands on one random tick, and Monday's gap
  lands on the first tick.

**The trap, measured** (`probe_intraday.py`, ρ = 0.5, 3,600 days, 3 seeds):
- **Exactness:** each instrument's ticks sum to its daily bar to 3e-17.
- **No tilt inside the day:** the rule "at hour 12, go with the day so far and hold to the close" earns
  +0.0005 / −0.010 / +0.0001 on the lab null (t overstated by the within-day cross-correlation). On a day pinned
  to zero it earns **−0.40 (t −356)**: the BASE defect at day scale.
- **The pairs trap:** "long i when correlated j led it so far".
  - With **independent** per-instrument bridges pinned at correlated closes, it earns **+0.11 / +0.12 / +0.08
    (t 8.2 / 8.6 / 6.3)**. That is a spurious lead-lag edge that ACIS's PAIR_DIVERGENCE would happily find.
  - With **joint** bridges (one factor bridge plus idiosyncratic bridges) it earns +0.021 / −0.004 / −0.024,
    |t| ≤ 1.7.

### 2.7 The integration design (task 5)

**One interface, one cost model, one financing model, one clock.**

1. **The BASE generator fix** (C-1 below) is in place in `tests/backtest/synthetic_market.py`.
   - Delete the demean at `:113-114` for null and planted.
   - For permuted, append the random signs **after** `rng.shuffle`, from the same `rng`. The noise → schedule →
     shuffle order stays unchanged, so null's and planted's draws and `episode_sign` are untouched.
   - Update the docstring line at `:10` ("Every kind is demeaned").
   - Size: about −2 / +3 lines, plus the two tests in §2.1.
2. **A new lab module, beside the tick generator.** It never replaces it: the tick generator stays the engine's
   minute-scale falsifier. Split to respect the 300-line module budget (constitution A12):
   - `tests/backtest/lab_market.py` (~230 lines): `LabSpec`, `Effect`, `generate`, `permuted`;
   - `lab_theory.py` (~70): the closed forms;
   - `lab_intraday.py` (~90): the joint bridge and the spreads;
   - `lab_source.py` (~70): `LabTickSource(TickSource)`. It implements `load(instrument, start, end)`
     (`tests/backtest/data_loader.py:36-45`) by yielding `RawTick(event_time, recv_time, instrument, bid, ask,
     volume, book=None, provider=name, raw_payload={})` (`core/data/normaliser.py:45-56`) where `emit` is true.
     The mid is the exponential of the cumulative **spot** log return (x − accrual): the tape carries spot, and the
     harness charges financing.
3. **Kinds are kept.** `LabTickSource(kind="null"|"planted"|"permuted")` keeps `falsify_engine.py`'s and
   `cost_stress_ladder.py`'s `KINDS` contract (`scripts/falsify_engine.py:36,49`). The lab adds `Effect` for the
   planted kind.
4. **The truth API generalises `episode_sign`.**
   - `truth(instrument, ts) -> m`: the planted drift in force on ts's trading day, fixed at the day's start, with no
     foresight.
   - `sign(truth)` is what the oracle reads (`tests/backtest/oracle_loop.py:147`).
   - `effect_sharpe(rule)` returns the closed-form or Monte-Carlo-calibrated Sharpe, **recorded in the run report**,
     so a detection rate is always graded against a stated power.
5. **No second cost model** (GAP-P12D-36 class). The lab sets only the *quoted* bid/ask.
   - Commission and slippage stay in `CostModel` (`core/optimizer/costs.py:27-61`), built once per run by
     `evolve_step.cost_model(cfg, i)` (`tests/backtest/evolve_step.py:44-56`). That function requires a declared
     `costs` block.
   - Synthetic instruments (for N up to 40) therefore get entries **in a test-only `AcisConfig` fixture** that
     copies a declared instrument's `costs` and `max_plausible_spread`. **Never in `config/instruments.yaml`.**
   - Spread spikes above `max_plausible_spread` deliberately exercise the loader's rejection path, which C2 §2.7
     asked for.
   - RSIM prices daily bars through the **same instances** (VAL §8: `research.costs[i] is harness.costs[i]`).
6. **No second financing model.**
   - With financing on, the lab's rates become a synthetic `RateTable(series)` (`tests/backtest/financing.py:52`),
     passed to `make_financing(table, broker_fee_pct=…)` (`:90`).
   - With financing off (`synthetic_grade.py:118` passes `financing=None` today), the lab **must** zero its rate
     differentials. Under uncovered interest parity the spot drifts by −(rate differential), and a spot-only grader
     would score that as an edge. The prototype enforces this: `financing_in_grader=False` zeroes the rates and
     refuses a planted carry.
   - Note that `make_financing` charges an admin fee to **both** sides, so a financing-on null is gross-zero and
     net-negative. That is correct friction, not bias.
7. **One clock.** The prototype's `session_start_utc` must be replaced by `core/data/fx_clock.rollover_utc`
   (`core/data/fx_clock.py:102`), and weekends by `in_weekend` (`:115`). The DST-correct clock (GAP-P12D-07/10) is
   then shared by the lab, the harness and RSIM.
   - BASE's tick tape runs Monday 00:00 to Friday 24:00 UTC. The loader drops Friday after the roll, and no ticks
     exist Sunday 17:00–24:00 New York.
   - The lab's 17:00-to-17:00 days fix that misalignment.
8. **A guard that keeps the lab from ever being fitted to real data.** A structural test asserts that `lab_*.py`
   imports nothing from `tests/backtest/sources.py`, the download scripts, or `data/`. Knob defaults cite their
   quoted source in a comment.

**Lines: added about 460 production + about 350 tests; removed about 2.** Concepts added: volatility units, the
effect registry with its theory, the truth API, variance-matched planting, and the joint bridge. The prototype's
394 lines exceed the 300-line budget, so the split above is mandatory.

**What must be preserved:**
- the null / planted / permuted triad;
- the oracle's `episode_sign` semantics (the state in force, never the next one);
- the RNG draw order of the tick generator;
- the `load` split-invariance (`test_synthetic_market.py:48-58`);
- the oracle-control tests (`tests/backtest/test_oracle_control.py`, `test_oracle_loop.py`,
  `test_oracle_full_scale.py`).

### 2.8 Calibration of usefulness (task 6)

`probe_calibration.py` uses **a parameter-free pooled rule**: EWMAC 16/64 on daily bars, a sign position,
vol-targeted by a 36-day EWMA volatility, equal risk across 20 lab instruments (ρ = 0.3), a 300-day burn-in, and
no costs. It is a pure test of the machinery.
- **Planted trend:** half-life 60 days, strength chosen so the rule's theoretical Sharpe is 0.25 per instrument.
- **Pooled theory:** 0.25·√(N/(1 + (N−1)ρ_pnl)) = **0.828**, with ρ_pnl = (2/π)·arcsin(ρ_X)·ρ/(v_m + σ²_other).
- **Detection:** a one-sided t > 1.645 on the path's daily pooled P&L.

| Market | 2.8 graded years, 400 seeds: mean SR (se), detect rate | 13.3 graded years, 100 seeds: mean SR (se), detect rate |
|---|---|---|
| **null** | **−0.020 (0.031), 4.3%** | **−0.013 (0.025), 4.0%** |
| **planted** (theory 0.828; power 39.8% / 91.5%) | **+0.806 (0.030), 40.3%** | **+0.808 (0.023), 96.0%** |
| **permuted** (FIX-C, day level) | −0.026 (0.027), 2.8% | −0.053 (0.027), 3.0% |
| null, BASE demeaning re-applied | **−0.199 (0.032)**, 3.0% | −0.031 (0.026), 2.0% |
| planted, BASE demeaning | +0.442 (0.032), **18.8%** | +0.771 (0.025), 91.0% |
| permuted, shuffle then demean (BASE-style) | **−0.445 (0.028)**, 1.3% | −0.169 (0.027), 2.0% |

**Reading.**
- The lab's null centres on zero with the nominal false-detection rate.
- The planted trend is detected at its theoretical power on short paths. On long paths it is detected slightly
  *above* it: the realised Sharpe sd, 0.227, is below the 1/√years = 0.275 that the theory power assumes.
- With the BASE demeaning, the null tilts negative, a reversal rule would profit by symmetry, and the power halves
  on the 2.8-year span that the ladder and fold windows use.

### 2.9 What the lab is for in R-1 (machinery only)

1. **The register verdict's false-positive rate under realistic nuisance** (R1-A task 4): volatility clustering,
   fat tails, correlated instruments and correlated variants, which the iid BASE tape cannot provide.
2. **The e-process on synthetic forward records** at a chosen true Sharpe, with GARCH-t P&L instead of iid.
3. **Breadth and the held-out common-factor leak** (VAL §2.6). The ρ knob and the factor loadings reproduce the
   leak; residualisation can be verified against known truth.
4. **RSIM reconciliation R1–R6** (VAL §8), which wants "≥ 1,000 trades on each of the null, planted and permuted
   tapes". The lab supplies an unlimited supply of such tapes, at bar and tick level, from one path.
5. **A falsifier for GAP-P12D-14's validation checks.** Run `scripts/run_data_validation.py`'s clock-mark checks on a
   correct lab tape, which must pass, and on the same tape shifted by one hour, which must flag. That gives the data
   validator its own positive and negative control.

### 2.10 For PLAN_R1

| # | Recommendation | Value (what gets sharper) | Complexity (what gets heavier) | Grade | Falsifier (drop it if…) | Verdict |
|---|---|---|---|---|---|---|
| **C-1** | **Fix the null.** Demean nothing (null, planted). Permuted = shuffle, then an independent random sign per return, drawn after the shuffle from the same rng. Rewrite the two tests that encode zero *realised* drift. Re-verify the oracle rungs, then re-fingerprint. | Null = martingale: zero expected P&L at every horizon. Removes a pooled −1.2 / +1.2 (momentum / reversal) Sharpe bias at N = 20 on 2.8-year paths, and restores the halved power. | −2 / +3 lines; 2 tests rewritten, +1 martingale test. No new concept. | own sim + closed form | Undemeaned null paths show a pooled rule mean more than 3 se from 0 over 1,000 seeds. | **adopt** [impl] |
| **C-2** | **Variance-matched planting** for the tick generator: set `drift_sigma` from a target oracle Sharpe, and scale the noise so planted and null variances are equal. | Planted differs from null by direction only, not by 3.3× the daily volatility. The ladder's direction/friction split becomes interpretable. | ~8 lines. Changes the positive control's calibration and every recorded run. | own measurement (production code) | The planted/null daily variance ratio is outside 1 ± 0.05. | **adapt** [spec — owner ratification] |
| **C-3** | **Build the daily-first lab** (§2.4) as four modules of ≤ 300 lines each, beside the tick generator. | Unlimited machinery iteration at R-1's horizon, with known Sharpe. About 1,000 null paths of 20 × 14 years in ~2–3 min on one core. | ~460 production lines and ~350 test lines. Concepts: volatility units, effect and theory, truth API. | own sim | The Cont probe set fails at default knobs, or a planted detection rate misses theory power by more than 2 se over 500 seeds. | **adopt** [impl] |
| **C-4** | **Joint intraday refinement.** One factor bridge plus idiosyncratic bridges on a session time-change; FX-clock days (`fx_clock.rollover_utc`); a rollover spike; spikes above `max_plausible_spread`; session tick thinning. | Tick tapes for the harness with no planted lead-lag. Exercises the spread veto, the loader's rejection path, and the weekend and rollover rules. | ~90 lines | own sim | The joint-bridge catch-up rule has \|t\| > 3 on 2 of 3 seeds. | **adopt** [impl] |
| **C-5** | **The truth API and a power statement per (effect, rule).** `truth(instrument, ts)` generalises `episode_sign`. Every lab run report records each effect's theoretical Sharpe for the rule graded, and the power at the run's length. | Every detection rate is graded against a stated power, and cross-family leakage (carry → trend +0.16) is visible. | ~40 lines | own sim | A reported detection rate has no stated power beside it. | **adopt** [impl] |
| **C-6** | **The null is null in the P&L the grader books.** Financing off ⇒ rate differentials zero and planted carry refused. Financing on ⇒ a synthetic `RateTable` through `make_financing`. | No UIP-drift false positives. One financing model. | ~20 lines | code refs + own reasoning | A spot-only grade on a financing-on lab null shows a carry "edge". | **adopt** [impl] |
| **C-7** | **One cost model.** The lab sets quoted spreads only. Synthetic instruments reuse declared `costs` blocks in a test-only config. RSIM and the harness hold the same `CostModel` instances, and VAL §8 R1–R6 runs on lab tapes. | Excludes the GAP-P12D-36 defect class by object identity. | ~30 lines of fixture | code refs | Any friction constant exists in a `lab_*` module. | **adopt** [impl] |
| **C-8** | **The stylized-facts probe set as the lab's own gate:** Cont 1, 2, 3 (FX symmetry), 4, 6, 7 and 8, with a *shape* test for 8, a robust ACF band for 1, and intraday seasonality as self-consistency. | Catches a lab that is too easy (iid Gaussian, as BASE is: C2 §2.7). Shows why GARCH(1,1) alone is not enough. | ~150 lines of tests | Cont 2001 (a); Baillie & Bollerslev 1989 (a) | — (a gate, not a hypothesis) | **adopt** [impl] |
| **C-9** | **Family choice.** Parametric hybrid (GARCH-t × multi-scale log-volatility, jumps, a factor, gaps; optional Markov regime switching as a later knob for R1-D's regime-as-weight). Reject GAN and diffusion for the lab. ABM is out of R-1 scope. | Known ground truth, no look, ms speed. | 0 (a decision) | (a)/(b) sources, §2.3 | A GAN or diffusion model is shown to support a *planted effect with known Sharpe* **and** training with no real data. | **adopt** parametric; **reject** GAN/diffusion [spec — owner ratification: a recorded design decision] |
| **C-10** | **Lab hygiene law.** The lab is never evidence of edge, never fitted to real data (knobs cite quoted ranges), and imports no real-data source (a structural test). | Keeps R-1 item 5 ("for the machinery only") mechanically true. | ~15 lines of tests | own reasoning; §0.4 | — | **adopt** [impl] |
| **C-11** | **Use the lab as the positive and negative control of the data validator** (GAP-P12D-14): a correct tape passes, a tape shifted by one hour flags. | The validator is itself validated, with no real data. | ~40 lines | own reasoning | — | **adapt** (a later phase) |

---

## 3. What I could not verify

- **Per-currency rates.** The prototype plants rate differentials per instrument, not per currency. The real
  structure, pairs sharing a currency, needs per-currency rates for the synthetic `RateTable`. This is designed,
  not built.
- **The integration code.** No lab module was run through the real harness (`Backtest.run`, `BacktestDataLoader`,
  the oracle loop). The integration lines are a design with estimated line counts, and the adapter was not built.
- **The BASE fix run through the production tests.** I did not apply C-1 in a copy of BASE and run the test suite,
  the oracle rungs or the falsification. The consequence for the rungs (±1% drift) is an estimate.
- **Regime switching and EGARCH or leverage.** Both are named in the brief. Neither is in the prototype: leverage is
  an equity fact, and regimes are a planned knob.
- **A finance-specific source for GAN mode collapse.** Not found in budget; it is not relied on. The case against
  GANs rests on the look and on the absence of ground truth.
- **Whether Carlini et al. and Takahashi–Mizuno are peer-reviewed.** Not confirmed on the pages I fetched. Their
  grades are stated conservatively in §6.
- **An FX-specific ABIDES variant.** One search found none. "None exists" is not established.
- **Intraday seasonality targets.** The profile's *shape* is a lab knob. Andersen & Bollerslev establish that the
  pattern is pronounced, but the Duke PDF is scanned and I could not quote its shape.
- **Stylized-fact fragility.** The slow-decay β sits at the edge (0.400) and is fragile across seeds. The daily
  excess kurtosis (~10) may be heavy for majors.

## 4. Residual risk

- **A lab artefact is mistaken for an edge.** A rule that learns a parametric lab's own structure (for example, the
  exact volatility process) could pass the lab and fail reality. The mitigation is C-10: the lab grades machinery,
  never edge, and the permuted control is required.
- **The theory depends on joint Gaussianity.** The closed-form Sharpe assumes X is Gaussian. With t-shocks and
  jumps, the measured EWMAC Sharpe (0.135) sat about 1 se above theory (0.115). The long-path power ran above
  theory (96% against 91.5%). A plan should calibrate the theory constants by Monte Carlo per (effect, rule) and
  record them, not trust the closed form blindly.
- **Changing the BASE generator moves history.** Every recorded synthetic verdict (GAP-P12D-49's ladder included)
  was made on the demeaned, high-volatility planted market. Their conclusions must be re-stated after C-1 and C-2,
  not silently carried over.
- **Tolerance drift.** Two probe tolerances were revised after a first run (§2.5). They are declared here, but a
  future tuner could quietly loosen them. The plan should pin the tolerances with their quote.

## 5. Proposed ledger items (no IDs)

1. **The synthetic null is a bridge, not a martingale.** Whole-path demeaning; the permuted kind is also a bridge.
   At R-1 breadth it gives a pooled Sharpe bias of −1.2 (momentum) / +1.2 (reversal) on 2.8-year paths, and halves
   planted power. Two unit tests encode the bug.
   - Severity high · Likelihood high · proposed Status open · **[impl]** (C-1). It extends C3 §5 item 2 and
     corrects its fix option (b).
2. **The BASE planted market is ~3.3× more volatile per day than null and permuted** (the episodes carry ~92% of
   its daily variance; the frictionless oracle Sharpe is ~157). "Planted passes, null fails" is confounded by the
   volatility level and the cost/move ratio.
   - Severity medium · Likelihood high · proposed Status open · **[spec — owner ratification]** (C-2). The
     positive-control calibration moves.
3. **Synthetic grading with `financing=None` needs zero rate differentials in any carry-capable generator**, or
   UIP drift becomes a spurious edge.
   - Severity medium · Likelihood medium (only once a carry lab exists) · proposed Status open · **[impl]** (C-6).
4. **Any intraday refinement of correlated daily bars must bridge the common factor jointly.** Independent bridges
   plant a lead-lag/pairs edge (t 6–9).
   - Severity medium · Likelihood medium · proposed Status open · **[impl]** (C-4).
5. **The daily synthetic market lab (C-3, C-5, C-7, C-8, C-10) is needed** for R-1's machinery: the register FPR,
   the e-process, breadth and residualisation, RSIM reconciliation.
   - Severity medium · Likelihood high · proposed Status open · **[impl]**.
6. **The generator-family decision is recorded:** parametric for the machinery lab; GAN and diffusion rejected as a
   look with no ground truth.
   - Severity low · Likelihood — · proposed Status accepted-risk once ratified · **[spec — owner ratification]**.

## 6. Sources

All were accessed on 2026-09-25. Quotes are verbatim from the fetched page or PDF text.

| # | Source | What I quote or use | Grade |
|---|---|---|---|
| 1 | Cont, R. (2001), "Empirical properties of asset returns: stylized facts and statistical issues", *Quantitative Finance* 1:223–236. PDF: http://rama.cont.perso.math.cnrs.fr/pdf/empirical.pdf (the rice.edu copy was partial, and lpsm.paris blocked the fetch) | Facts 1, 2, 3 and its footnote, 4, 6, 7 and 8, quoted in §2.5; the note on GARCH sample ACFs (Mikosch & Starica) | (a) |
| 2 | Baillie, R.T. & Bollerslev, T. (1989), "The Message in Daily Exchange Rates: A Conditional-Variance Tale", *JBES* 7(3):297–305. https://ideas.repec.org/a/bes/jnlbes/v7y1989i3p297-305.html | "approximately uncorrelated through time"; "…conditionally t-distributed errors is found to provide a good representation to the leptokurtosis and time dependent conditional heteroscedasticity"; "…reduced as the length of the sampling interval increases" | (a) |
| 3 | Andersen, T.G. & Bollerslev, T. (1998), *J. Finance* 53(1):219–265; NBER WP 5783. https://www.nber.org/papers/w5783 | "Our modeling approach explicitly captures the pronounced intraday activity patterns, the strong macroeconomic announcement effects, and the volatility persistence" | (a) |
| 4 | Wiese, M. et al. (2020), "Quant GANs: Deep Generation of Financial Time Series", *Quantitative Finance*. https://arxiv.org/abs/1907.06673 | "we introduce Quant GANs, a data-driven model" | (a) |
| 5 | Yoon, J., Jarrett, D. & van der Schaar, M. (2019), "Time-series Generative Adversarial Networks", NeurIPS 32. https://papers.nips.cc/paper/2019/hash/c9efe5f26cd17ba6216bbe2a7d26d490-Abstract.html | "A good generative model for time-series data should preserve temporal dynamics, in the sense that new sequences respect the original relationships between variables across time." | (a) |
| 6 | Takahashi, T. & Mizuno, T. (2024), "Generation of synthetic financial time series by diffusion models". https://arxiv.org/abs/2410.18897 (a *Quantitative Finance* 2025 version appears in search results, DOI 10.1080/14697688.2025.2528697; not fetched) | "…although no model yet satisfies all the stylized facts"; "We demonstrate that our proposed approach satisfies stylized facts." | (b), (a) if the journal version is confirmed |
| 7 | Tanaka, Y. et al. (2025), "CoFinDiff: Controllable Financial Diffusion Model for Time Series Generation". https://arxiv.org/abs/2503.04164 | "incorporating conditions derived from price data"; "the generated data accurately meet specified conditions for trends and volatility" | (b) |
| 8 | Carlini, N. et al. (2023), "Extracting Training Data from Diffusion Models". https://arxiv.org/abs/2301.13188 | "diffusion models memorize individual images from their training data and emit them at generation time" (images, not financial series) | (b) as fetched |
| 9 | Byrd, D., Hybinette, M. & Balch, T.H. (2019), "ABIDES: Towards High-Fidelity Market Simulation for AI Research". https://arxiv.org/abs/1904.12066 | "tens of thousands of trading agents"; "modeled after NASDAQ's published equity trading protocols ITCH and OUCH" | (b) |
| 10 | Vyetrenko, S. et al. (2019), "Get Real: Realism Metrics for Robust Limit Order Book Market Simulations", NeurIPS 2019 workshop. https://arxiv.org/abs/1912.04941 | "many market simulation approaches fail to reproduce statistics and stylized facts seen in real markets"; "there are still significant discrepancies between simulated markets and real ones" | (b) |
| 11 | Eckerli, F. & Osterrieder, J. (2021), "Generative Adversarial Networks in finance: an overview". https://arxiv.org/abs/2106.06364 | Context only ("the lack of sufficient data to train these models") | (b) |
| 12 | Carr, P. & López de Prado, M. (2014), "Determining Optimal Trading Rules without Backtesting". https://arxiv.org/abs/1408.1159 | "calibrating a trading rule using a historical simulation (also called backtest) contributes to backtest overfitting" | (b) |
| 13 | ACIS at BASE: `ACIS_SPEC.md:407` (the project's recorded "rollover spike 6–13× at the real instant"); code at the `file:line` references above | The rollover knob range; the integration anchors | primary (project) |
| — | Not used as evidence: a search-result summary of broker blogs on rollover spreads (FP Markets and Ox Securities pages returned 403); the Duke PDF of Andersen–Bollerslev (a scan, not extractable) | — | (c), unused |

**Evidence files** (all under `CLOUD_AUDIT/reports/r1/evidence/R1C/`; synthetic; each under 2 MB):

| File | Receipt | What it is |
|---|---|---|
| `repro_bridge.py` | `repro_bridge_out.txt` | The bias and the fixes |
| `probe_planted_vol.py` | `probe_planted_vol_out.txt` | The BASE production generator, read-only |
| `gen_lab.py` | — | The lab prototype |
| `probe_stylized.py` | `probe_stylized_lab_out.txt`, `probe_stylized_garch11_out.txt` | The stylized-fact probes |
| `probe_effects.py` | `probe_effects_out.txt` | Whether each effect delivers its declared Sharpe |
| `probe_intraday.py` | `probe_intraday_out.txt` | The intraday bridge |
| `probe_calibration.py` | `probe_calibration_out.txt` (13.3 y), `probe_calibration_short_out.txt` (2.8 y) | The pooled calibration |

The brief suggested `probe_pooled_ewma.py`. That role is served by `probe_calibration.py`.
