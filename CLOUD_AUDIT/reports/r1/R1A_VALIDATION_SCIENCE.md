# R1-A VALIDATION SCIENCE — what exact statistic gives each verdict under R-1, and what each record proves

- **Lane:** R1-A VALIDATION SCIENCE (ACIS mission R1). Reports only. A finder, not a clearer.
- **Model and effort, as observed:** the system prompt names `claude-opus-5-5` (Opus 5.5). Effort is not observable from inside the session.
- **Fresh context:** yes. No subagents launched.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`, read-only at `/tmp/review-acis`.
- **Date:** 2026-09-25, 08:00–~10:25 UTC.
- **Web:** __WEB__ of the 30-call cap (searches and fetches combined).
- **Data:** synthetic only. No market data, bundled datasets or `.bi5` fixtures were touched. Every number in §2 regenerates from `evidence/R1A/` (§2.9).
- **Compute:** at most 2 worker processes, `OMP_NUM_THREADS=1`, heavy work in `/tmp/r1-R1A/`.
- **LLM-originated marking.** Every design here is LLM-originated: the e-processes, the verdict rule, the bar numbers and the planning rates. They are **procedures**, not market hypotheses, so testing them on synthetic data is legitimate. Any strategy they end up admitting is still credited only on post-cutoff forward data when it is LLM-shaped (GAP-P12D-66).
- **Builds on, does not redo:**
  - C1: the frontier, SPA/StepM over the union, keep-best inflation, and the prop CIs;
  - VAL: CPCV/PBO calibration, leakage tests T1–T8, the R1–R6 reconciliation, K1–K6, and §2.6's residualisation.
  - Where I extend or correct them, I say so.

---

## 1. Executive summary (≤ 10 bullets, graded)

__EXEC__

---

## 2. Body

### 2.1 The map: gate → record → statistic → what a pass proves (and what it cannot)

R-1's gates, each with the one statistic proposed here and the honest scope of its record. The numbers are in §2.2–§2.7.

| gate | record | verdict statistic (proposed) | a PASS proves | it can NOT prove |
|---|---|---|---|---|
| G0 machinery | synthetic lab (R1-C) | the same statistics as below, on null and planted worlds | the grader has its stated FPR and power | anything about markets |
| G1 exploration | pre-2012 history, synthetic data, non-validation instruments | none (unregistered; VAL tier 1) | nothing | — |
| G2 development | 2012–2023 on the **development** instruments; expanding-window walk-forward, daily OOS P&L of each registered **family-version's pooled combination** | one-sided Holm (≡ max-t at low family correlation) lower bound of the OOS Sharpe > 0 over the K registered family-versions | at least one registered family had a positive pooled OOS mean on this history, **if** the register is complete and there is no leak (VAL §7) | persistence; anything, for an LLM-originated family (GAP-P12D-66); magnitude (±0.62 at 10 y) |
| G3 held-out instruments | 2012–2023 on the locked held-out instruments | same-window test **residualised** on the development P&L, or better, forward on the held-out instruments | an *idiosyncratic* edge that transfers | a common-factor edge: residualising removes it (§2.6) |
| G4 holdout-once | 2024–25, the frozen candidate, once | kill if the holdout SR < 0 (or below a pre-registered floor) | nothing; a pass certifies nothing | — (power ≤ 41% at a true 1.0) |
| G5a forward plumbing and cost | demo fills (paired shadow replay) | E3 cost-gap e-process, both sides at W ≥ 20; tripwire | the C8 cost model is within ±25% at this venue | the edge |
| G5b forward edge | demo daily P&L | E1 edge e-process at W ≥ 20 (weighted across promotions, §2.5); E2 kill always on | the sign of the forward edge | magnitude, in any practical time |
| G6 challenge | prop account | ECO/C1 economics; a capped-loss experiment | — | edge (C1 §2.7: a pass is a likelihood ratio of ~1.6) |

### 2.2 Task 1 — anytime-valid testing of the demo forward record

**2.2.1 The literature, quoted.**
- Ramdas, Grünwald, Vovk & Shafer [S1]: *"Safe anytime-valid inference (SAVI) provides measures of statistical evidence and certainty -- e-processes for testing and confidence sequences for estimation -- that remain valid at all stopping times, accommodating continuous monitoring and analysis of accumulating data and optional stopping or continuation for any reason."* **(b)**, arXiv as fetched.
- Johari, Pekelis & Walsh [S5], on why the owner's daily look is a problem for classical tests: *"these inferences are wholly unreliable if users endogenously choose samples sizes by continuously monitoring their tests."* **(b)**.
- Grünwald, de Heide & Koolen [S6], on why e-values compose across stages: *"Tests based on e-values are safe, i.e. they preserve Type-I error guarantees, under such optional continuation."* The paper is *"Accepted as discussion paper to the Journal of the Royal Statistical Society series B"*. **(a)**.
- Waudby-Smith & Ramdas [S2], on betting for bounded means: *"our bounds are adaptive to the unknown variance, and empirically vastly outperform existing approaches based on Hoeffding or empirical Bernstein inequalities and their recent supermartingale generalizations."* **(b)**.
- Howard, Ramdas, McAuliffe & Sekhon [S7], *Annals of Statistics* 49(2) 2021: confidence sequences are *"a sequence of confidence intervals that is uniformly valid over an unbounded time horizon"*. **(a)**.
- Shin, Ramdas & Rinaldo [S8], the anytime-valid analogue of VAL K5's CUSUM: *"We first introduce simple Shiryaev-Roberts and CUSUM-style e-detectors"*, with *"clean, nonasymptotic bounds on the average run length (frequency of false alarms)."* **(b)**.

The mechanism, as used here: a bettor starts with wealth 1 and each day stakes a fraction λ_t, chosen from the past only, on "tomorrow's P&L is positive". Under H0 (conditional mean ≤ 0) the wealth is a nonnegative supermartingale. **Ville's inequality** then gives P(sup_t W_t ≥ 1/α) ≤ α, so the owner may look every day, stop any time, or keep going. `W_t` is the e-value.

**2.2.2 The three e-processes (LLM-originated designs).**

| | E1 EDGE (sign of edge) | E2 KILL (claim falsified) | E3 COST GAP (plumbing and cost) |
|---|---|---|---|
| unit | daily net P&L of the whole demo book, r_t, as a fraction of equity | same | per fill: d_i = realised − modelled cost, in units of the modelled cost; modelled = the shadow replay of the same fill through the C8 `CostModel` on the same feed |
| H0 | E[r_t \| past] ≤ 0 | E[r_t \| past] ≥ μ_claim | breach: E[d] ≤ +0.25. Certify: E[d] ≥ +0.25, and separately E[d] ≤ −0.25 |
| bet on | x_t = max(r_t/(6σ*), −1) | x_t = max((μ_claim − r_t)/(6σ*), −1) | x_i = max((d_i − 0.25)/5, −1) for breach. Certify: (0.25 − d_i)/5 and (d_i + 0.25)/5 |
| stake | λ_t = clip(m̂/(v̂ + m̂²), 0, 0.8), with m̂, v̂ the running mean and variance of past x plus a 20-observation prior (m 0, v 1/36) | same | same |
| wealth | W_t = Π(1 + λ_s x_s) | same | same; **certify** when BOTH one-sided wealths ≥ 20 (intersection–union) |
| verdict | W ≥ 20: sign shown (α 0.05). W ≥ 100: strong. Else "not yet", never "failed" | W ≥ 5: review, freeze scale-ups. W ≥ 20: kill | breach W ≥ 20: kill the venue or recalibrate C8. Certify at W ≥ 20 on both |

- σ* is the **declared** daily vol target, a constant fixed before the demo; it is not estimated. An estimated σ would make x non-predictable.
- The alternative bettor `E_MIX` averages the wealths of fixed stakes λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8}. An average of e-processes is an e-process. It is 3 lines and never needs tuning.
- **Tripwire rule (new; load-bearing).** The lower bound (−1) is what makes the bet safe, so it must be a **tripwire, not a winsorisation**:
  - a day with r_t < −6σ* means the sizing broke;
  - a fill with d_i − 0.25 < −5, or a cost more than 5 modelled costs above the model, is a reconciliation breach.
  - Either one halts the verdict and raises a K5 event. It must never be silently clipped. §2.2.3 shows what silent clipping does.
- Complexity: one shared function (~25 lines) and three call sites (~15 lines). Concepts added: 1 (a bettor's wealth). E2 replaces the CUSUM leg of VAL K5; E3 gives VAL §5.4's "≥ 100 reconciled round trips" a stopping rule.
- Alternatives measured and **rejected**:
  - the textbook Gaussian-mixture SPRT with known σ (`E_NMIX`, Johari et al.'s mSPRT form), because it is valid only if the declared vol is right (§2.2.3);
  - a daily-peeked t-test.

**2.2.3 Simulation results** (`sim_eprocess_demo.py`; R = 2,000 per cell; 20-year horizon; daily looks; σ* = 0.5%/day).

*False-positive rate: P(W ever ≥ 20) on zero-edge records.* Ville bounds it at 5%.

| null family | E_BET 10 y / 20 y | E_MIX 10 y / 20 y | E_NMIX (known σ) 10 y / 20 y | daily t-test peeking, 1 y / 10 y |
|---|---|---|---|---|
| Gaussian | 2.8 / 2.9% | 2.3 / 2.5% | 2.6 / 3.0% | 26 / 38% |
| Student-t4 | 2.2 / 2.3% | 1.9 / 2.2% | 2.1 / 2.5% | 28 / 41% |
| GARCH(1,1)-t5 | 2.2 / 2.8% | 1.6 / 2.3% | 2.5 / 3.0% | 27 / 39% |
| left-skewed (1%/day −6σ jumps) | 3.4 / 3.7% | 2.6 / 3.3% | 1.7 / 2.4% | 34 / 47% |
| true vol 1.5× the declared σ* | 2.1 / 2.4% | 2.0 / 2.7% | **17.0 / 20.3%** | 26 / 39% |

- The daily t-test passes 17–23% of zero-edge records **within the first quarter**.
- The betting e-processes hold ≤ 3.7% everywhere, including under vol mis-sizing, where the known-σ mixture fails. (Wilson 95% half-width at 3% with R = 2,000: ±0.75 pp.)

*Power and stopping times for the SIGN of the edge* (E_BET, and the range over the Gaussian / t4 / GARCH worlds). SR is the **portfolio's** true annual net Sharpe:

| true SR | P(W ≥ 20) by 3 m / 6 m / 1 y / 2 y / 3 y / 5 y / 10 y | median time to W ≥ 20 | median time to W ≥ 100 | E[min(τ₂₀, 20 y)] |
|---|---|---|---|---|
| 0.5 | 0–0.2% / 0.4–0.7% / 2.4–2.8% / 5.2–5.8% / 7.3–7.5% / 11% / 18–19% | > 20 y (35–37% by 20 y) | > 20 y | 16.2–16.3 y |
| 1.0 | 0.1–0.3% / 0.9–2.2% / 6.7–7.5% / 16–18% / 23–26% / 38–42% / 68–72% | **6.1–6.8 y** | 9.6–10.4 y | 7.4–7.9 y |
| 1.5 | 0.1–0.2% / 3.1–3.6% / 16–18% / 35–42% / 51–59% / 75–79% / 97–98% | **2.4–3.0 y** | 3.8–4.5 y | 3.2–3.6 y |
| 2.0 | 0.4–0.6% / 7.6–8.3% / 30–34% / 61–67% / 80–83% / 96–97% / 100% | **1.4–1.6 y** | 2.1–2.4 y | 1.8–2.0 y |

- `E_MIX` is within ±0.3 y of `E_BET` on the medians. It is slower in the first year (at SR 1.0, 2.4–3.4% vs 6.7–7.5% by 1 y) and slightly better after 5 y.
- The known-σ `E_NMIX` is no faster (median 5.8–5.9 y at SR 1.0) and is invalid under mis-sizing.
- **Rule of thumb, derived and confirmed:** the growth rate of the optimal bettor is ≈ SR²/2 per year, so τ(e ≥ 1/α) ≈ 2·ln(1/α)/SR² years plus a learning overhead. That is ≈ 6/SR² years for e ≥ 20 and ≈ 9.2/SR² for e ≥ 100. The simulation lands 5–15% above it.
- **The trade count does not enter.** A daily-marked P&L's information about the edge's sign is SR²·T regardless of how many trades produced it.

*Kill power* (E2, t4 world; truth, claim):

| truth → claim | P(W ≥ 5) by 1 y / 2 y / 3 y / 5 y | median to W ≥ 5 | P(W ≥ 20) by 1 y / 3 y / 5 y |
|---|---|---|---|
| 0 → 0.5 | 13 / 19 / 23 / 29% | > 10 y | 3 / 9 / 11% |
| 0 → 1.0 | 25 / 40 / 49 / 65% | 3.1 y | 7 / 26 / 40% |
| 0 → 1.5 | 40 / 60 / 75 / 90% | 1.5 y | 17 / 52 / 76% |
| 0.5 → 1.0 | 13 / 19 / 22 / 28% | > 10 y | 3 / 7 / 10% |
| claim true (0.5 / 1.0 / 1.5) | false kill ≤ 6.5% by 1 y; 10–11% by 10 y | — | ≤ 1% by 1 y; ≤ 2.5% by 10 y |

*Cost-gap e-process* (E3; paired fill differences with right-skewed noise, a t3 core plus 2% adverse +5-cost spikes; band ±25%; dispersion = the SD of d in modelled costs):

| true gap | dispersion 0.5 | dispersion 1.0 | dispersion 2.0 |
|---|---|---|---|
| +100% (costs doubled): breach, median fills | **30** | **32** | **44** |
| +50%: breach, median fills (P by 100 / 250) | **88** (72% / 100%) | **114** (39% / 95%) | 497 (10% / 27%) |
| +25% (band edge): false breach by 5,000 fills | 2.0% | 2.2% | 0.2% |
| 0: **certify inside ±25%**, median fills (P by 250) | **102** (100%) | **166** (81%) | 596 (4%) |
| +25% (band edge): **false certify** by 5,000 fills, 5× tripwire *silently clipped* | 2.2% | 2.5% | **42.7%** |
| same, loose 20× bound (never binds) | 0.2% | 2.0% | 2.0% |
| certify at gap 0 with the loose 20× bound, median fills | 353 | 405 | 688 |

- **Silent clipping is invalid, and it failed in the direction that flatters.** At dispersion 2, 3.5% of fills exceed the 5× bound. Clipping them manufactured "cost model certified" 43% of the time at the band edge.
- A bound loose enough never to bind is valid but 2–3.5× slower, because the stake cap (λ ≤ 0.8) then binds.
- Hence the tripwire rule: keep the tight bound, halt on any exceedance, and treat a dispersion above ~1 modelled cost as its own finding (the fill model is wrong in shape, not only in level).

**2.2.4 The demo's likely rates.** Carver's measured turnover [S12] is (b); the table is as reproduced by the fetch tool: buffered position turnover **13.88** (EWMAC16), **8.92** (EWMAC32) and **7.04** (EWMAC64) per year. Even a constant long forecast turns over 2.14 a year, from vol-scaling alone.
- My assumption (c): one turnover unit ≈ one round-trip-equivalent, executed as 2–4 fills.
- A slow-to-medium pooled trend set on **N = 20–40** instruments at ~8–12 a year each is **≈ 160–480 round-trip-equivalents a year: ≈ 3–9 a week, ≈ 6–40 fills a week.** Daily-horizon carry or seasonal sleeves add little.
- Trade count matters only for E3 (and for VAL's behavioural bands), never for E1.

**2.2.5 The direct answer: what forward record length and trade count prove what.**

| claim | statistic | record needed (median; 80% by) at the rates above | proves |
|---|---|---|---|
| **Plumbing:** orders, brackets, reconciliation, weekend, rollover, event | deterministic per-event checks (VAL §5.4 (c)) | ≥ 1 month containing a weekend, a rollover and a scheduled event; every fill reconciled | the machine does what the harness does |
| **Cost level** (paired) | E3, both-sided at W ≥ 20 | 100–170 fills (80% by ~250) at dispersion ≤ 1 modelled cost ⇒ **~3–17 weeks**; a 2× cost error shows in 30–44 fills (**1–5 weeks**) | the C8 cost model is within ±25% of the venue, or is not |
| **Sign of edge** | E1 at W ≥ 20 | portfolio SR 2.0: 1.4–1.6 y (80% by ~3 y). 1.5: 2.4–3.0 y (80% by ~5 y). 1.0: 6.1–6.8 y. 0.5: > 20 y | the forward mean is positive |
| **Falsify a claim** | E2 | claimed 1.5 against a truth of 0: median 1.5 y at W ≥ 5; claimed 1.0: 3.1 y; claimed 0.5: > 10 y | the claim was wrong |
| **Magnitude** | a confidence sequence on the annual SR (a normal-mixture boundary tuned for 3 y) | ±3.3 at 1 y, ±2.2 at 2 y, ±1.8 at 3 y, ±1.4 at 5 y, ±1.0 at 10 y [derived] | effectively never within a demo's life |

- **So "the demo's forward record is the decisive test" (R-1 item 6) is true for plumbing and cost within weeks.** For the edge it is decisive only as a **slow, anytime-valid accumulator**.
- A 6–12-month demo verdict can say "plumbing and cost certified; the edge is not contradicted (W < 5 on E2)". It can **never** say "edge proven" unless the portfolio SR is ≥ 2.
- This agrees with, and quantifies, VAL §5.4 and C1 §2.7 (the ±1.65 CI at 12 months).

**2.2.6 Two ways to make the slow part faster, both honest.**
1. **Optional continuation across stages** [S6] **(a)**. For a hypothesis **fully specified by a dated paper** (exempt from the LLM-contamination law, GAP-P12D-66), start E1 at the first day of the locked 2024–25 holdout, then continue it into the demo.
   - The holdout is still used once: an e-process is one continuous look. A strategy at portfolio SR 1.5 then reaches its median W ≥ 20 about 2 years earlier in calendar time, i.e. ≈ 0.5–1 y into the demo instead of 2.4–3 y.
   - It is **not** allowed for LLM-originated or LLM-refined hypotheses: this model's cutoff covers 2024–25.
2. **Breadth** (§2.3) raises the portfolio SR that E1 sees. At an IDM of 2.1–2.4, the same per-instrument edge is seen 4.4–5.8× faster.

### 2.2.7 What each e-process does NOT protect against
- A leak. E1 on a leaky strategy's forward record is honest, because forward data cannot leak, but a backtest-derived μ_claim can be inflated by one. E2 then kills faster, which is the right direction.
- Non-stationarity: a real edge that decays. E1 still controls the false-positive rate, but its power falls. E2 at a pre-registered μ_claim is the decay alarm.
- **An unregistered restart.** Resetting W to 1 after a bad month, or after a "fix", is a new look. Every restart must be registered and **counted** in the forward weights of §2.5, or W is meaningless.

### 2.3 Task 2 — breadth and effective breadth

**2.3.1 The law, derived here (a: algebra; it is the variance of an average).**
- Take N equal-risk rule P&L streams, each with annual Sharpe s and average pairwise correlation ρ. The equal-weight portfolio has
  SR_p = s · IDM, with IDM = √(N / (1 + (N − 1)ρ)).
- IDM² = N/(1 + (N − 1)ρ) is the **effective breadth**: the fundamental law with correlated bets. It is also Carver's instrument diversification multiplier for equal weights.
- Carver floors negative correlations at zero: *"I also floor negative correlations to avoid getting very large values for the multiplier"* [S13] **(b)**. A cap of 2.5 on the multiplier is attributed to him by a secondary source [S14] **(c)**, not verified at the primary.
- The ceiling is 1/√ρ as N → ∞, so breadth saturates.
- **Years to certify** (80% power, one-sided FWER 5%, Bonferroni over K) = (z_{1−0.05/K} + 0.842)² / SR_p². The years shrink by 1/IDM².

**2.3.2 ρ is the correlation of the rules' P&L, not of prices (measured; this matters).**
- `sim_breadth.py` part C runs an EWMAC(16,64) rule on factor-correlated prices.

  | price corr | linear-forecast P&L corr (theory ρ²) | sign-forecast P&L corr (theory ρ·(2/π)·asin ρ) |
  |---|---|---|
  | 0.2 | 0.03 (0.04) | 0.02 (0.03) |
  | 0.4 | 0.17 (0.16) | 0.11 (0.10) |
  | 0.6 | 0.35 (0.36) | 0.23 (0.25) |
  | 0.8 | 0.65 (0.64) | 0.49 (0.47) |

- For a trend rule on iid returns, the positions are correlated at ρ_price and the next-day returns at ρ_price, so the P&L correlation is ≈ ρ_price².
- **A planted *common-factor* trend breaks this.** It raises the P&L correlation, because every instrument earns together. That case is §2.6's leak case.

**2.3.3 Published correlation levels (quoted, not computed).**
- Moskowitz, Ooi & Pedersen, *JFE* 2012 [S9] **(a)**, on 12-month TSMOM on 58 futures, monthly, 1985–2009:
  - text: *"The correlations are positive within each asset class, ranging from 0.37 to 0.38 for equities and fixed income futures to 0.10 and 0.07 for commodities and currencies."*
  - Table 4 Panel A gives TSMOM within-class averages of commodities **0.07**, equities **0.37**, fixed income **0.38** and currencies **0.10**. The text's order for commodities and currencies is the reverse of the table's. Either way both are ≤ 0.10.
  - Panel B, across asset-class TSMOM portfolios: 0.05–0.21.
  - The same paper: a diversified TSMOM portfolio *"yielding a Sharpe ratio greater than one on an annual basis"*. That is gross and in sample; R1-B owns the decay.
- Verdelhan, *JF* 2018 [S10] **(a)**: *"The two high−minus−low risk factors account for 18% to 80% of the monthly exchange rate movements."* The USD pairs share a large common component, so FX **price** correlations among USD pairs are high. By §2.3.2, the trend **P&L** correlation is roughly the square of that. That agrees with MOP's 0.10 for currencies.
- **Planning value, my inference [derived]:** ρ_P&L ≈ **0.10–0.15** for a multi-asset 20–40 set (FX, metals, indices, energies). For an FX-heavy set use a **0.20–0.30 stress**: crosses such as EUR/GBP share legs with EUR/USD and GBP/USD.

**2.3.4 How C1's frontier shrinks.**
- **A correction first.** C1's 9.3 y at SR 1, K = 1, uses Lo's (1 + S²/2) with S in annual units. With daily observations the per-period S is ≈ 0.063 and the factor is ≈ 1.002, so the daily-data frontier is **6.2 y**. That is VAL §5.1's number. C1's own simulation found its frontier "slightly conservative" (0.95 power against 0.90 analytic at 1.22). [derived]

IDM and the certification years for a pooled rule whose *per-instrument* net SR is s (K = 1; for K = 10 multiply the years by 1.89):

| ρ_P&L | IDM at N = 8 / 20 / 30 / 40 | C1's 9.3 y (daily-correct 6.2 y) becomes, at N = 8 / 20 / 30 / 40 | years at s = 0.3: N = 1 → 8 / 20 / 30 / 40 | years at s = 0.5: N = 8 / 20 / 30 / 40 |
|---|---|---|---|---|
| 0.10 | 2.17 / 2.63 / 2.77 / 2.86 | 2.0 / 1.35 / 1.2 / 1.1 (1.3 / 0.9 / 0.8 / 0.8) | 69 → 14.6 / 10.0 / 8.9 / 8.4 | 5.3 / 3.6 / 3.2 / 3.0 |
| 0.15 | 1.98 / 2.28 / 2.37 / 2.42 | 2.4 / 1.8 / 1.7 / 1.6 (1.6 / 1.2 / 1.1 / 1.1) | 69 → 17.6 / 13.2 / 12.2 / 11.7 | 6.3 / 4.8 / 4.4 / 4.2 |
| 0.20 | 1.83 / 2.04 / 2.10 / 2.13 | 2.8 / 2.2 / 2.1 / 2.05 (1.85 / 1.5 / 1.4 / 1.4) | 69 → 20.6 / 16.5 / 15.6 / 15.1 | 7.4 / 5.9 / 5.6 / 5.4 |
| 0.30 | 1.61 / 1.73 / 1.76 / 1.78 | 3.6 / 3.1 / 3.0 / 2.95 (2.4 / 2.1 / 2.0 / 2.0) | 69 → 26.6 / 23.0 / 22.2 / 21.8 | 9.6 / 8.3 / 8.0 / 7.9 |

Readings:
1. **From 1 to 8 instruments is the big step** (years ÷ 2.6–4.7). **From 8 to 30 buys a further ÷ 1.2–1.6**, and 30 → 40 buys ≤ 7%.
   - The owner's 20–40 is right for other reasons: the 1/ρ ceiling, held-out instruments (§2.6), and room for a cross-sectional family.
   - It is not right because 40 certifies much faster than 20.
2. At the realistic per-instrument net SR of **0.3** and ρ 0.10–0.15, a pooled rule on 20–40 instruments needs **8.4–13 years** at K = 1. The expanding walk-forward on 2012–2023 has ≈ 10 OOS years.
   - **So one pre-registered pooled family is just about certifiable on history, and ten are not** (K = 10 → 16–25 y).
   - This is the quantitative case for R-1's "few rules".
3. **Simulation check** (`sim_breadth.py` part B, R = 400): the analytic length gives power **77–83%** against a target of 80%, at ρ 0.1 and 0.3, N 8, 20 and 40.

**2.3.5 The pooled test must be the portfolio time series, never the stacked panel (new finding).**
- A pooled regression or t-test that treats the N × T rule-days as independent observations passes a **zero-edge** pooled rule **9.5–32%** of the time in the same simulation:

  | ρ \ N | 8 | 20 | 40 |
  |---|---|---|---|
  | 0.1 | 9.5% | 15.8% | 25.0% |
  | 0.3 | 19.0% | 22.8% | 31.8% |

- The portfolio time-series test (equivalently, errors clustered by day) holds **3.8–6.0%**.
- **Every pooled verdict statistic in the plan must be computed on the daily portfolio P&L**, or be clustered by date. This is exactly the defect class a "pooled across instruments" redesign invites. [sim]

### 2.4 Task 3 — pooling and shrinkage of rule performance across instruments

__T3__

### 2.5 Task 4 — one verdict rule over the whole register, under "iterate freely"

**2.5.1 The literature, and the catch it does not advertise.**
- The stream-FDR procedures (alpha-investing, LORD, SAFFRON, and e-LOND) control error over a *stream* of hypotheses.
  - e-LOND *"provides FDR control under arbitrary, possibly unknown, dependence"* [S4] **(b)**.
  - e-BH *"controls the FDR at the desired level -- with no correction -- for any dependence structure between the e-values"* [S3] **(b)**.
- **Every one of them assumes each hypothesis's p- or e-value is valid for that hypothesis.** Arbitrary *dependence* between the values is allowed. What is not allowed is choosing hypothesis k + 1 **because** runs 1..k looked good **on the same data** and then testing it on that data: its p-value is then no longer valid.
- Dwork et al. [S15] **(b)**: *"Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself."*
- "Iterate freely on 2012–2023" is exactly that adaptive reuse. So the question is not "which FDR procedure", but "**over what set** is the multiplicity counted".

**2.5.2 Simulation: an adaptive researcher on a null market** (`sim_register_verdict.py`; R = 400).
- **Market:** 20 development and 8 held-out instruments, price correlation 0.3, 12 development years and 2 forward years, no edge anywhere.
- **Declared search space:** 7 rule families (EWMAC, breakout, TSMOM, reversal, calendar, cross-sectional momentum, vol-filtered EWMAC) × 11 parameters × 2 forms × 5 universes (all 20, or one of four groups of 5) = **770 pooled configurations**.
- **The researcher** registers every run (K = 20, 50, 100 or 200). 30% of runs **explore** (a new family is preferred) and 70% **hill-climb**: change one coordinate of the best-so-far run. By K = 50 all 7 families have been touched.

FPR, in % (Wilson 95% CI), for rejecting the global null "no edge":

| verdict rule | K = 20 | K = 50 | K = 100 | K = 200 |
|---|---|---|---|---|
| keep-best, PSR of the best run (uncounted) | 69.5 | 87.8 | 94.8 | 98.5 |
| **Bonferroni over the K registered runs** | **10.8** (8.1–14.2) | **12.8** (9.8–16.4) | **9.2** (6.8–12.5) | 6.5 (4.5–9.4) |
| **max-t / StepM over the registered (tried) union** (C1's SPA_union) | **11.5** (8.7–15.0) | **16.2** (13.0–20.2) | **13.8** (10.7–17.5) | **9.8** (7.2–13.1) |
| **max-t over the DECLARED grid of every touched family** | 5.2 (3.5–7.9) | 5.5 (3.7–8.2) | 5.5 | 5.5 |
| **Holm over the touched families' fixed pooled combinations** | 1.5 (0.7–3.2) | 1.5 | 1.5 | 1.5 |
| e-Bonferroni over runs (betting e-values, reject if max e ≥ K/α) | 0.0 | 0.0 | 0.0 | 0.0 |
| forward 2 y, once, on the best run | 6.5 | 6.0 | 5.2 | 4.5 |
| forward 2 y, once, on the best family combination | 3.2 | 4.2 | 4.2 | 4.2 |

Mean annual Sharpe of the kept "best run" on the development years: 0.57 / 0.67 / 0.72 / 0.76 at K = 20 / 50 / 100 / 200. The same run's forward Sharpe: 0.05–0.08. That is the false encouragement, reproduced.

**Reading (new; it corrects the scope of C1's union result):**
- C1 measured SPA/StepM over the registered union at 2.7–7.0% FPR, but with **non-adaptive** random draws from the pool.
- Under an adaptive hill-climber, **the registered-union test runs at 10–16%**, and even **Bonferroni over the registered runs at 7–13%**, which is normally the most conservative rule there is.
- The mechanism: the union bound holds for a fixed set of hypotheses. Hill-climbing makes *which* configurations enter the register depend on their noise, so the register over-samples the high-noise corner. The inflation *falls* as K grows (K = 200 covers 26% of the grid), because the tried set approaches the declared space.
- **"Register every run" is necessary but NOT sufficient.** The count must run over the **declared reachable space**, the grid the researcher *could* have visited, fixed before the first look. Then the test holds 5.2–5.5% however the researcher wanders.

**2.5.3 Power** (planted worlds; §2.6 has the held-out rows).

__REGPOWER__

**2.5.4 How it composes with VAL's CPCV + PBO and C1's SPA/StepM, and the one rule.**
- Under R-1, a family is a **fixed pooled combination** (equal-risk over a coarse, literature-fixed grid × all development instruments). There is **no within-family selection**, so there is nothing for PBO to measure and nothing for CPCV's selection step to purge.
  - VAL's stage-2 CPCV + PBO machinery is **not needed** for R-1 families. That is a deletion.
  - It is needed only if the owner wants per-family parameter *selection*, and then the grid must be declared (row 4 of the table).
- C1's SPA/StepM survives as the **max-t over K family-version combinations**. With 5–15 weakly correlated families it is ≈ Holm, which needs no bootstrap.

**THE VERDICT RULE (proposed; LLM-originated; [spec — owner ratification]):**
1. **Declare before the first look.** A family-version = (the rule's formula, its coarse grid, its instruments, the cost model hash). Declaring it writes one register line, exclusive-create (C1's stage 0).
   - Any change to the grid, the formula or the instruments is a **new family-version**, and K increases by one.
   - Changing ONLY the combination's internal weights toward what worked is forbidden: that is selection by the back door.
2. **Development verdict (G2):** for each family-version j, t_j = the one-sided t of its pooled combination's **daily** expanding-window OOS P&L. It is computed on the portfolio series, never the panel (§2.3.5).
   - **Pass** if t_j > z_{1 − 0.05/K_total}, where K_total = every family-version ever declared on 2012–2023. This is Holm for the first rejection.
   - With per-family parameter selection, replace t_j with the max-t over the **declared** grid (bootstrap), and still count K_total over versions.
3. **Forward verdict (G5b):** each promotion j (a family-version sent to the demo, in order) gets a pre-committed weight γ_j with Σγ_j ≤ 1, e.g. γ_j = 6/(π² j²), or 1/J_max for a declared cap J_max.
   - Declare "edge shown" when γ_j · W_j ≥ 20. A restart of W is a new promotion.
   - This is the online e-Bonferroni (the degenerate, single-discovery case of e-LOND) and is valid under any dependence [S3, S4].
   - At J_max = 3 the threshold is W ≥ 60: the median time rises by ln 3/(SR²/2) ≈ 2.2/SR² years (≈ +1 y at SR 1.5).
4. **Kill rules** stay per promotion (E2; VAL K1–K6), and each writes a register line.

- **Value:** it holds 1.5–5.5% FPR under adaptive iteration where the registered-union and Bonferroni-over-runs rules reach 7–16%. It deletes CPCV/PBO from the R-1 path.
- **Complexity:** the register gains one field (the declared grid). The G2 statistic is ~10 lines (a t-stat and Holm). The forward weights are one line.
- **Falsifier:** a synthetic adaptive-researcher null on which rule 2 exceeds 7% (the upper Wilson bound at R = 400).

### 2.6 Task 5 — held-out instruments

__T5__

### 2.7 Task 6 — the acceptance bar (numbers for PLAN §6)

__T6__

### 2.8 For PLAN_R1

__PLAN__

### 2.9 Reproduction

__REPRO__

---

## 3. What I could not verify

- **Publication status of five method papers** (S1–S5, S8, S15). The arXiv pages I fetched carry no journal reference, so I grade them (b). The methods are standard; the load-bearing guarantee (Ville's inequality for a nonnegative supermartingale) is textbook and is also checked by my FPR simulation.
- **The IDM cap of 2.5** is attributed to Carver only through a search summary [S14], graded (c). I did not reach a primary quote. Nothing here depends on the cap: my breadth numbers are uncapped, and at ρ ≥ 0.15 they stay below 2.5 anyway.
- **Carver's turnover table** is as rendered by the fetch tool from his post. I did not see the raw HTML. I **assume** (c) that one turnover unit ≈ one round-trip-equivalent executed as 2–4 fills. The fills-per-week range (6–40) inherits that assumption.
- **The paired cost-gap dispersion** (0.5–2 modelled costs per fill) is a planning grid, not a measurement. The first 50 demo fills will measure it. If it is above ~1.5, E3 needs a larger tripwire bound and certification slows to ~600 fills (§2.2.3).
- **MOP's correlations** are for 12-month TSMOM on monthly futures returns, 1985–2009. ACIS's rules are daily EWMAC-type rules on CFDs, 2012–2025. I use MOP only to set a planning range, not as a measurement of ACIS's universe. Computing it from the Dukascopy data would be a look, so I did not.
- **The register simulation's researcher** is a stylised hill-climber (§2.5). Real researchers are cleverer at finding noise: they change the rule's *form*, which my grid only partly represents. The measured inflation is therefore a **lower bound** for keep-best-style rules.
- **Not run:** a heavy-tailed or GARCH version of the register and held-out simulations (C1 and VAL showed that size holds across those shapes); CPCV/PBO inside the register simulation (VAL's; not duplicated); an e-LOND implementation (argued analytically in §2.5, not simulated).

## 4. Residual risk

__RISK__

## 5. Proposed ledger items (no IDs)

__LEDGER__

## 6. Sources

All accessed 2026-09-25. **Grades as fetched:** an arXiv page that shows no journal reference is graded (b), even where I believe it was later published. I did not verify publication in this session.

| # | Source | URL | Grade |
|---|---|---|---|
| S1 | Ramdas, Grünwald, Vovk, Shafer, "Game-theoretic statistics and safe anytime-valid inference" (arXiv 2210.01948; the fetched page says "under review") | https://arxiv.org/abs/2210.01948 | (b) |
| S2 | Waudby-Smith & Ramdas, "Estimating means of bounded random variables by betting" (arXiv 2010.09686) | https://arxiv.org/abs/2010.09686 | (b) |
| S3 | Wang & Ramdas, "False discovery rate control with e-values" (arXiv 2009.02824) | https://arxiv.org/abs/2009.02824 | (b) |
| S4 | Xu & Ramdas, "Online multiple testing with e-values" (arXiv 2311.06412) | https://arxiv.org/abs/2311.06412 | (b) |
| S5 | Johari, Pekelis & Walsh, "Always Valid Inference: Bringing Sequential Analysis to A/B Testing" (arXiv 1512.04922) | https://arxiv.org/abs/1512.04922 | (b) |
| S6 | Grünwald, de Heide & Koolen, "Safe Testing" (arXiv 1906.07801; "Accepted as discussion paper to the Journal of the Royal Statistical Society series B") | https://arxiv.org/abs/1906.07801 | (a) |
| S7 | Howard, Ramdas, McAuliffe & Sekhon, "Time-uniform, nonparametric, nonasymptotic confidence sequences", *Ann. Statist.* 49(2) 2021 | https://arxiv.org/abs/1810.08240 | (a) |
| S8 | Shin, Ramdas & Rinaldo, "E-detectors: a nonparametric framework for sequential change detection" (arXiv 2203.03532) | https://arxiv.org/abs/2203.03532 | (b) |
| S9 | Moskowitz, Ooi & Pedersen, "Time series momentum", *JFE* 2012; §4.5 and Table 4 read from the authors' PDF | https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf | (a) |
| S10 | Verdelhan, "The Share of Systematic Variation in Bilateral Exchange Rates", *JF* 73(1) 2018, 375–418 (abstract) | https://ideas.repec.org/a/bla/jfinan/v73y2018i1p375-418.html | (a) |
| S11 | Jensen, Kelly & Pedersen, "Is There a Replication Crisis in Finance?", *JF* 78(5) 2023, 2465–2518 (abstract; context only) | https://ideas.repec.org/a/bla/jfinan/v78y2023i5p2465-2518.html | (a) |
| S12 | Carver, "Fast but not furious: Do fast trading rules actually cost a lot to trade?" (2023-02-01; the turnover table as rendered by the fetch tool) | https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html | (b) |
| S13 | Carver, "Correlations, Weights, Multipliers.... (pysystemtrade)" (2016-01-29) | https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html | (b) |
| S14 | the "IDM capped at 2.5" attribution, a web-search summary of a book review | https://the7circles.uk/systematic-trading-3-frameworks-and-forecasts/ (not fetched) | (c) |
| S15 | Dwork, Feldman, Hardt, Pitassi, Reingold & Roth, "Generalization in Adaptive Data Analysis and Holdout Reuse" (arXiv 1506.02629) | https://arxiv.org/abs/1506.02629 | (b) |
| L1 | C1 CALIBRATOR (cloud run 2); VAL, ARC, ECO and SCO local finals (`/tmp/review-acis/archive/RESEARCH_*_2026-09-24.md`) | local | untrusted evidence (A9), cited as such |
