# R1-A VALIDATION SCIENCE — what exact statistic gives each verdict under R-1, and what each record proves

- **Lane:** R1-A VALIDATION SCIENCE (ACIS mission R1). Reports only. A finder, not a clearer.
- **Model and effort, as observed:** the system prompt names `claude-opus-5-5` (Opus 5.5). Effort is not observable from inside the session.
- **Fresh context:** yes. No subagents launched.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`, read-only at `/tmp/review-acis`.
- **Date:** 2026-09-25, 08:00–~10:25 UTC.
- **Web:** 25: 19 fetches (one returned 403) and 6 searches of the 30-call cap (searches and fetches combined).
- **Data:** synthetic only. No market data, bundled datasets or `.bi5` fixtures were touched. Every number in §2 regenerates from `evidence/R1A/` (§2.9).
- **Compute:** at most 2 worker processes, `OMP_NUM_THREADS=1`, heavy work in `/tmp/r1-R1A/`.
- **LLM-originated marking.** Every design here is LLM-originated: the e-processes, the verdict rule, the bar numbers and the planning rates. They are **procedures**, not market hypotheses, so testing them on synthetic data is legitimate. Any strategy they end up admitting is still credited only on post-cutoff forward data when it is LLM-shaped (GAP-P12D-66).
- **Builds on, does not redo:**
  - C1: the frontier, SPA/StepM over the union, keep-best inflation, and the prop CIs;
  - VAL: CPCV/PBO calibration, leakage tests T1–T8, the R1–R6 reconciliation, K1–K6, and §2.6's residualisation.
  - Where I extend or correct them, I say so.

---

## 1. Executive summary (≤ 10 bullets, graded)

1. **The demo's forward verdict should be a betting e-process on the book's daily net P&L, which the owner can read every day without inflating false positives.** [sim; method (a)/(b)]
   - Over 20 years of daily looks its FPR is **≤ 3.7%** across Gaussian, t4, GARCH-t, left-skewed and 1.5×-mis-sized nulls.
   - A t-test checked daily passes zero-edge records **38–47%** of the time within 10 years (17–23% in the first quarter).
   - The textbook known-σ mixture SPRT reaches **20%** when the vol is mis-sized. Reject it for P&L.
2. **What the forward record proves, and when** [sim, derived]:
   - **cost and plumbing: fast**, because the test is paired. A doubled cost shows in **30–44 fills**; the model is certified inside ±25% in a median **102–166 fills**, ≈ 3–28 weeks (≈ 5–8 weeks at 20 fills/week) at the 6–40 fills/week a 20–40-instrument daily set trades (Carver's turnover (b) plus my assumption (c));
   - **sign of edge: slow, and independent of trade count.** The median time to W ≥ 20 is **1.4–1.7 y** at a portfolio SR of 2.0, **2.4–3.0 y** at 1.5 and **5.8–6.8 y** at 1.0;
   - **magnitude: never** in a demo's life (the anytime-valid band is ±1.8 SR at 3 years).
3. **A new validity trap: the bounded-bet clip must be a tripwire, not a winsorisation.** Silently clipping cost spikes produced **43%** false "cost model certified" at the band edge. [sim]
4. **"Register every run" is necessary but NOT sufficient under "iterate freely".** [sim, R = 400; extends C1]
   - With an adaptive researcher (70% hill-climbing), the test over the **registered union** (C1's SPA_union) runs at **10–16%** FPR, and Bonferroni over the registered runs at **6.5–13%**.
   - The count must run over the **declared search space**: max-t over the declared grid holds **5.2–5.5%**; fixed pooled family combinations with Holm hold **1.5%**.
5. **Under R-1 a family is a fixed pooled combination (no argmax inside it), so VAL's CPCV + PBO stage drops out of the path.** The development verdict is a Holm lower bound over K family-versions. Power: 64–69% for the fixed combination against 45–58% for max-t over the declared grid, in the weak-idiosyncratic and common-factor worlds (99–100% in a strong world). [sim]
6. **Breadth is real but saturates.** [derived + sim; correlations (a)]
   - IDM = √(N/(1 + (N − 1)ρ)) with ρ the correlation of the **rules' P&L**, which for trend rules is ≈ ρ_price² (measured).
   - The published TSMOM P&L correlations (MOP 2012) give a planning ρ of 0.10–0.15, and IDM(20 / 30 / 40) = **2.28–2.63 / 2.37–2.77 / 2.42–2.86**.
   - Going from 1 to 8 instruments divides the years needed by 2.6–4.7; from 8 to 30, only by 1.2–1.6.
   - At a per-instrument net SR of 0.3, a pooled family needs **8.4–13 y** at K = 1. **One family is certifiable on 2012–2023; ten are not.**
7. **Pooled verdicts must use the portfolio series.** A stacked instrument × day panel t-test passes a zero-edge pooled rule **9.5–32%** of the time. [sim]
8. **Held-out instruments:**
   - the raw same-window test leaks, and **the leak grows with the search**: 14.5% → 24% FPR from K = 20 to 200;
   - residualising restores **2.5–3.2%**;
   - power is flat past **6–8 held out of 30**;
   - residualised power is 19–96% for an idiosyncratic edge but **12–17% for a common-factor edge**: residualising removes the edge itself;
   - a "kill if SR̂ < 0" on held-out instruments, or on the 2-year holdout, wrongly kills a realistic edge **18–32%** of the time, so the kill floors should sit at t < −0.5 [sim]
9. **The acceptance bar (§2.7):**
   - **A:** development Holm lower bound > 0, i.e. **SR̂ > 0.81** at K ≤ 10 over 10 OOS years (72% power at a true 1.0);
   - **B/C:** held-out and holdout **kill-only** at t < −0.5. The usual SR̂ < 0 wrongly kills 18–32% of realistic edges;
   - **D:** E3 cost certified;
   - **E:** E1 **γ·W ≥ 20** for "edge shown";
   - **F:** the E2 kill at half the claimed SR.

   Every stage's error rates are measured or derived; the end-to-end false-promotion rate is ≤ 0.2%. [sim; spec — owner ratification]
10. **Corrections, and one addition.**
    - C1's 9.3-year frontier (SR 1, K = 1) is **6.2 years** on daily data.
    - **No historical gate catches a code-level look-ahead leak.** It works on held-out instruments and on 2024–25 alike. A live-versus-replay zero-decision-mismatch rule on the demo catches one in days (R1A-13, derived).
    - Per-instrument parameter selection loses 4–10% of a pooled edge when instruments are alike (τ ≤ 0.1). EB shrinkage matches the better choice at every τ, and should gate any deviation. [derived, sim]

---

## 2. Body

### 2.1 The map: gate → record → statistic → what a pass proves (and what it cannot)

R-1's gates, each with the one statistic proposed here and the honest scope of its record. The numbers are in §2.2–§2.7.

| gate | record | verdict statistic (proposed) | a PASS proves | it can NOT prove |
|---|---|---|---|---|
| G0 machinery | synthetic lab (R1-C) | the same statistics as below, on null and planted worlds | the grader has its stated FPR and power | anything about markets |
| G1 exploration | pre-2012 history, synthetic data, non-validation instruments | none (unregistered; VAL tier 1) | nothing | — |
| G2 development | 2012–2023 on the **development** instruments; expanding-window walk-forward, daily OOS P&L of each registered **family-version's pooled combination** | one-sided Holm (≡ max-t at low family correlation) lower bound of the OOS Sharpe > 0 over the K registered family-versions | at least one registered family had a positive pooled OOS mean on this history, **if** the register is complete and there is no leak (VAL §7) | persistence; anything, for an LLM-originated family (GAP-P12D-66); magnitude (±0.62 at 10 y) |
| G3 held-out instruments | 2012–2023 on the locked held-out instruments | same-window test **residualised** on the development P&L; kill-only at t < −0.5 | an *idiosyncratic* edge that transfers | a common-factor edge: residualising removes it (§2.6) |
| G4 holdout-once | 2024–25, the frozen candidate, once | kill if the holdout t < −0.5 (§2.7) | nothing; a pass certifies nothing | — (power ≤ 41% at a true 1.0) |
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
| unit | daily net P&L as a fraction of equity: of the whole demo book, and separately of each promoted family's sleeve (attributed) for γ_j·W_j | same | per fill: d_i = realised − modelled cost, in units of the modelled cost; modelled = the shadow replay of the same fill through the C8 `CostModel` on the same feed |
| H0 | E[r_t \| past] ≤ 0 | E[r_t \| past] ≥ μ_claim | breach: E[d] ≤ +0.25. Certify: E[d] ≥ +0.25, and separately E[d] ≤ −0.25 |
| bet on | x_t = max(r_t/(6σ*), −1) | x_t = max((μ_claim − r_t)/(6σ*), −1) | x_i = max((d_i − 0.25)/5, −1) for breach. Certify: (0.25 − d_i)/5 and (d_i + 0.25)/5 |
| stake | **default `E_MIX`:** W = the mean of the wealths at fixed λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8}. Alternative `E_BET`: λ_t = clip(m̂/(v̂ + m̂²), 0, 0.8), from the running mean and variance of past x plus a 20-observation prior (m 0, v 1/36) | same | same |
| wealth | W_t = Π(1 + λ_s x_s) | same | same; **certify** when BOTH one-sided wealths ≥ 20 (intersection–union) |
| verdict | W ≥ 20: sign shown (α 0.05). W ≥ 100: strong. Else "not yet", never "failed" | W ≥ 5: review, freeze scale-ups. W ≥ 20: kill | breach W ≥ 20: kill the venue or recalibrate C8. Certify at W ≥ 20 on both |

- σ* is the **declared** daily vol target, a constant fixed before the demo; it is not estimated. An estimated σ would make x non-predictable.
- `E_MIX` averages the wealths of fixed stakes λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8}. An average of e-processes is an e-process. It is 3 lines and never needs tuning.
- **Recommended default: `E_MIX`.** It has no prior and no plug-in, and its median path rises steadily: 1.3 / 1.9 / 2.4 after 1 / 2 / 3 years at SR 1.0. The plug-in `E_BET`'s median path dips to 0.85 in year 1, which an owner reading W daily will misread, even though it hits W ≥ 20 early slightly more often [sim].
- **Tripwire rule (new; load-bearing).** The lower bound (−1) is what makes the bet safe, so it must be a **tripwire, not a winsorisation**:
  - a day with r_t < −6σ* means the sizing broke;
  - a fill whose realised cost differs from the modelled cost by more than ~5 modelled costs, in either direction, is a reconciliation breach.
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

The same for the recommended **`E_MIX`**:

| true SR | P(W ≥ 20) by 1 y / 2 y / 3 y / 5 y / 10 y | median to W ≥ 20 | median to W ≥ 100 |
|---|---|---|---|
| 0.5 | 0.8–1.1% / 3.2–4.4% / 6.1–6.8% / 9.9–10.9% / 21–22% | > 20 y (42–43% by 20 y) | > 20 y |
| 1.0 | 2.4–3.4% / 14% / 22–26% / 39–44% / 74–76% | **5.8–6.3 y** | 9.3–10.1 y |
| 1.5 | 8–9% / 33–36% / 52–57% / 77–80% / 98–99% | **2.6–2.9 y** | 4.0–4.5 y |
| 2.0 | 19–20% / 59–63% / 80–83% / 96–97% / 100% | **1.6–1.7 y** | 2.4–2.6 y |

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
| **Cost level** (paired) | E3, both-sided at W ≥ 20 | 100–170 fills (80% by ~250) at dispersion ≤ 1 modelled cost ⇒ **~3–28 weeks** (≈ 5–8 at 20 fills/week); a 2× cost error shows in 30–44 fills (**1–7 weeks**) | the C8 cost model is within ±25% of the venue, or is not |
| **Sign of edge** | E1 at W ≥ 20 | portfolio SR 2.0: 1.4–1.7 y (80% by ~3 y). 1.5: 2.4–3.0 y (80% by ~5 y). 1.0: 5.8–6.8 y. 0.5: > 20 y (both bettors) | the forward mean is positive |
| **Falsify a claim** | E2 | claimed 1.5 against a truth of 0: median 1.5 y at W ≥ 5; claimed 1.0: 3.1 y; claimed 0.5: > 10 y | the claim was wrong |
| **Magnitude** | a confidence sequence on the annual SR (a normal-mixture boundary tuned for 3 y) | ±3.3 at 1 y, ±2.2 at 2 y, ±1.8 at 3 y, ±1.4 at 5 y, ±1.0 at 10 y [derived] | effectively never within a demo's life |

- **So "the demo's forward record is the decisive test" (R-1 item 6) is true for plumbing and cost within weeks.** For the edge it is decisive only as a **slow, anytime-valid accumulator**.
- A 6–12-month demo verdict can say "plumbing and cost certified; the edge is not contradicted (W < 5 on E2)". It cannot say "edge proven" unless the portfolio SR is about 2 or more, and even then only 19–34% of the time within the first year.
- This agrees with, and quantifies, VAL §5.4 and C1 §2.7 (the ±1.65 CI at 12 months).

**2.2.6 Two ways to make the slow part faster, both honest.**
1. **Optional continuation across stages** [S6] **(a)**. For a hypothesis **fully specified by a dated paper** (exempt from the LLM-contamination law, GAP-P12D-66), start E1 at the first day of the locked 2024–25 holdout, then continue it into the demo.
   - The holdout is still used once: an e-process is one continuous look. A strategy at portfolio SR 1.5 then reaches its median W ≥ 20 about 2 years earlier in calendar time, i.e. ≈ 0.5–1 y into the demo instead of 2.4–3 y.
   - It is **not** allowed for LLM-originated or LLM-refined hypotheses: this model's cutoff covers 2024–25.
2. **Breadth** (§2.3) raises the portfolio SR that E1 sees. At an IDM of 2.1–2.4, the same per-instrument edge is seen 4.4–5.8× faster.

**2.2.7 What each e-process does NOT protect against.**
- A leak. E1 on a leaky strategy's forward record is honest, because forward data cannot leak, but a backtest-derived μ_claim can be inflated by one. E2 then kills faster, which is the right direction.
  - **A faster, non-statistical leak catcher exists only in live time (R1A-13; my inference).** Every live decision is made before the next bar exists. Replay the same bars through the backtest path once they have closed, and require **zero decision mismatches** (same side, same target position, same bar).
  - A look-ahead leak in the backtest/research path shows up as systematic mismatches within days, long before any P&L statistic could see it.
  - This is VAL's R3 (identical decisions, research simulator vs harness) applied to live vs replay. It also catches non-determinism.
  - It matters because **no historical gate catches a code leak**: the leak works on held-out instruments and on 2024–25 alike.
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

**2.4.1 Why per-instrument performance is almost all noise at our record length [derived].**
- On 12 development years the standard error of one instrument's annual Sharpe is 1/√12 ≈ **0.29**.
- A realistic per-instrument net SR for one pooled rule is 0.2–0.4. So:
  - "is the rule's edge > 0 on instrument i?" has power Φ(0.3·√12 − 1.645) = **27%** at s = 0.3 before any multiplicity, and ≈ 3% after Holm over 30 instruments;
  - the spread of the 30 estimated Sharpes (SD ≈ 0.29) is mostly estimation noise unless the true spread τ is comparable.
- The empirical-Bayes (James–Stein-type) weight on an instrument's own estimate is 1 − B, with B = SE²(1 − ρ)/(SE²(1 − ρ) + τ²). The (1 − ρ) is there because the errors share the common factor. At τ = 0.1 / 0.2, B = 0.88 / 0.65: shrink 65–88% of each deviation back to the pool.
- Jensen, Kelly & Pedersen [S11] **(a)** apply the same hierarchical logic to the "replication crisis" argument: *"Several papers argue that financial economics faces a replication crisis because the majority of studies cannot be replicated or are the result of multiple testing of too many factors."* Their answer is a Bayesian hierarchical model: I quote only the abstract's framing; the rest was summarised by the fetch tool, so it is context, not evidence.

**2.4.2 Simulation** (`sim_shrinkage.py`; N = 30, 6 speeds, 12 years, error correlation 0.1 across instruments and 0.85 between adjacent speeds, R = 2,000).
- **Score:** the *true* Sharpe of what each method picks, per instrument, i.e. the realised OOS edge.
- **True profile over speeds:** 0.15 / 0.25 / 0.30 / 0.30 / 0.25 / 0.20. Heterogeneity τ is correlated 0.8 across speeds.

Mean true per-instrument SR of what each method picks (the realised OOS edge; oracle = the best speed per instrument):

| true heterogeneity τ | oracle | literature-fixed speed | pooled argmax | **per-instrument argmax** | **EB-shrunk argmax** | P(EB allows deviation) |
|---|---|---|---|---|---|---|
| 0.0 | 0.300 | 0.300 | 0.285 | **0.256** (−10% vs pooled) | 0.284 | 0.0% |
| 0.1 | 0.330 | 0.300 | 0.285 | **0.273** (−4%) | 0.288 | 0.1% |
| 0.2 | 0.375 | 0.300 | 0.288 | 0.317 (+10%) | 0.317 | 8.1% |
| 0.3 | 0.428 | 0.301 | 0.296 | 0.372 (+26%) | 0.372 | 63.4% |

- **Per-instrument argmax loses 4–10% of the edge when the true heterogeneity is ≤ 0.1**: it fits noise. It gains only when τ ≥ 0.2.
- **EB-shrunk selection is never worse than the better of the two** (≈ pooled at τ ≤ 0.1, ≈ per-instrument at τ ≥ 0.2).
- Its deviation flag is calibrated: it fires 0–0.1% of the time at τ ≤ 0.1, 8% at 0.2 and 63% at 0.3.
- **A caveat on the fixed column.** The literature-fixed speed sits on the true peak here by construction. A literature choice one step off the plateau would lose ≈ 0.05 (the profile's slope). The equal-weight combination of all six speeds has a true SR of ≈ 0.24 × FDM ≈ 0.26 per instrument, where FDM ≈ 1.07 at a speed correlation of 0.85. That is ~14% below the best single speed.
- That ~14% is the price of R1A-2's "no argmax inside a family". §2.5.3 shows the price is repaid in verdict power: 64–69% against 45–58% for grid selection at realistic edges. Choose the combination's grid coarse and near the literature's plateau so the price stays small.

**2.4.3 The verdict statistics and the deviation rule (proposed; LLM-originated).**
1. **"Is the rule's pooled edge > 0"** is the only question the history can answer. Statistic: the one-sided t of the **portfolio's** daily OOS P&L (§2.3.5), inside the register rule of §2.5.
   - Never "k of N instruments significant". Never the mean of per-instrument t-statistics: that treats correlated instruments as independent, the §2.3.5 defect.
2. **"Is it > 0 on instrument i"** is reported only as an EB posterior: the shrunk mean, and P(s_i > 0) under the fitted normal prior.
   - It never gates anything, except that a posterior P(s_i > 0) < 0.10 on ≥ 12 years may **retire** an instrument from a family. That is a kill-only use, and it is registered.
3. **Per-instrument deviation of parameters** is allowed only when one of these holds:
   - **(a) a performance-blind, pre-registered reason.** In practice that is cost: Carver's speed limit, cost ≤ ⅓ of expected pre-cost SR (C4 verified the quote (b)), which forces slower speeds on expensive instruments. It is decided from the cost model before any P&L is seen;
   - **(b) the EB fit says heterogeneity dominates noise:** B̂ < 0.5, i.e. τ̂ > SE·√(1 − ρ) ≈ 0.28 annual SR at 12 years. The deviation is then a **new registered family-version** (it counts in K).
   - Otherwise one pooled parameter set.
- **Value:** it keeps the per-instrument noise out of the parameters (§2.4.2) and removes 29 of 30 parameter sets. **Complexity:** EB is ~15 lines (moments), or zero if the rule is "pool, except for cost".

### 2.5 Task 4 — one verdict rule over the whole register, under "iterate freely"

**2.5.1 The literature, and the catch it does not advertise.**
- The stream-FDR procedures (alpha-investing, LORD, SAFFRON, and e-LOND) control error over a *stream* of hypotheses.
  - e-LOND *"provides FDR control under arbitrary, possibly unknown, dependence"* [S4] **(b)**.
  - e-BH *"controls the FDR at the desired level -- with no correction -- for any dependence structure between the e-values"* [S3] **(b)**.
- **Every one of them assumes each hypothesis's p- or e-value is valid for that hypothesis.** Arbitrary *dependence* between the values is allowed. What is not allowed is choosing hypothesis k + 1 **because** runs 1..k looked good **on the same data** and then testing it on that data: its p-value is then no longer valid.
- Dwork et al. [S15] **(b)**: *"Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself."*
- The online-FDR set-up itself, per SAFFRON [S16] **(b)**: *"one observes a possibly infinite sequence of p-values P₁,P₂,…, each testing a different null hypothesis"*. Each p-value must be valid for its own null.
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
- Under an adaptive hill-climber, **the registered-union test runs at 10–16%**, and even **Bonferroni over the registered runs at 6.5–13%**, which is normally the most conservative rule there is.
- The mechanism: the union bound holds for a fixed set of hypotheses. Hill-climbing makes *which* configurations enter the register depend on their noise, so the register over-samples the high-noise corner. The inflation *falls* as K grows (K = 200 covers 26% of the grid), because the tried set approaches the declared space.
- **"Register every run" is necessary but NOT sufficient.** The count must run over the **declared reachable space**, the grid the researcher *could* have visited, fixed before the first look. Then the test holds 5.2–5.5% however the researcher wanders.

**2.5.3 Power** (planted worlds; §2.6 has the held-out rows).

Power, in %, at K = 20 / 50 / 100 / 200 registered runs (R = 300 per world). The "truth" is the forward 2-year annual Sharpe of a **fixed, pre-registered** EWMAC(16,64) pooled on all 20 development instruments, averaged over the replications:

| verdict rule | **idiosyncratic trend, weak** (μ 0.05; fixed-config truth 0.31) | **idiosyncratic trend** (μ 0.08; fixed-config truth 0.87; best config in the grid ≈ 2.0 in sample) | **common-factor trend** (μ 0.08; fixed-config truth 0.58) |
|---|---|---|---|
| Bonferroni over runs *(invalid: 6.5–13% FPR)* | 42.0 / 50.0 / 51.0 / 51.0 | 94.7 / 98.3 / 99.3 / 99.7 | 66.0 / 69.7 / 66.0 / 61.0 |
| max-t over the registered union *(invalid: 10–16% FPR)* | 44.0 / 54.7 / 55.3 / 56.7 | 95.0 / 99.0 / 99.3 / 99.7 | 68.7 / 72.3 / 67.7 / 65.0 |
| **max-t over the declared grid** (FPR 5.2–5.5%) | 45.0 / 47.3 / 47.3 / 47.3 | 99.0 / 100 / 100 / 100 | 58.0 / 56.7 / 56.7 / 56.7 |
| **Holm over fixed family combinations** (FPR 1.5%) | **64.3 / 68.3 / 68.3 / 68.3** | 100 / 100 / 100 / 100 | **69.3 / 69.0 / 69.0 / 69.0** |
| e-Bonferroni over runs (FPR 0%) | 0.3 / 0 / 0 / 0 | 26.0 / 25.0 / 21.0 / 15.0 | 17.3 / 15.7 / 13.7 / 11.7 |
| forward 2 y once, best run | 12.3 / 13.0 / 15.7 / 16.0 | 44.7 / 63.3 / 73.3 / 78.7 | 19.7 / 19.0 / 17.7 / 16.7 |
| forward 2 y once, best family combination | 26.3 / 27.0 / 27.0 / 27.0 | 80.3 / 85.3 / 85.3 / 85.3 | 27.7 / 28.0 / 28.0 / 28.0 |

Readings:
1. **The fixed family combination costs no power, and at realistic edge sizes it GAINS 11–23 pp over the declared-grid max-t:**
   - weak idiosyncratic world: **64–68% against 45–47%**;
   - common-factor world: **69% against 57–58%**.

   The combination is not charged for the 770-configuration multiplicity; the grid max-t is. It is the most powerful valid rule measured, and also the one with the lowest FPR (1.5%).
2. **In the strong idiosyncratic world, search does find better configurations.** The best run's forward Sharpe (1.1–1.8) exceeds the fixed EWMAC16's 0.87. A fixed combination forgoes that gain *in what is traded*, but not in the verdict's power (both 100%).
   - The honest way to capture that gain is to register the better-looking configuration as a **new family-version** and let it earn its place forward.
   - The combination's forward test is also more powerful than the best run's at K ≤ 100 (80–85% against 45–73%). A single run, often on a 5-instrument sub-universe, is noisier than the pooled combination.
3. **e-values on development history are valid but weak** (0–26% where Holm has 64–100%). e-values belong on the forward record.
4. **The rules inflated on the null** (Bonferroni over runs, the registered union) look "more powerful" in the common-factor world. That is their false-positive rate talking.

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

- **Value:** it holds 1.5–5.5% FPR under adaptive iteration where the registered-union and Bonferroni-over-runs rules reach 6.5–16%. It deletes CPCV/PBO from the R-1 path.
- **Complexity:** the register gains one field (the declared grid). The G2 statistic is ~10 lines (a t-stat and Holm). The forward weights are one line.
- **Falsifier:** a synthetic adaptive-researcher null on which rule 2 exceeds 7% (the upper Wilson bound at R = 400).

### 2.6 Task 5 — held-out instruments

**2.6.1 How to choose and lock them.** LLM-originated procedure; **[impl]** except where marked.
1. **Choose blind and stratified, before any look at 2012+ data on the candidates.**
   - Within each asset-class stratum of the declared universe (FX majors, FX crosses, metals, indices, energies), draw ⌈25%⌉ of the instruments with a seed fixed in the register line, e.g. the SHA-256 of the register's first line.
   - **Never hand-pick**, and never exclude an instrument "because it behaves differently". That is selection on the outcome.
   - Stratifying is what keeps a held-out set from being all USD pairs, i.e. all one factor.
2. **Lock by structure, not by promise.** Put the held-out list in the register, and have the data loader refuse those symbols for any run whose register line is not a G3 line.
   - Model the G3 line on `HoldoutGuard.begin_final`, which is exclusive-create, once-only (`tests/backtest/oos_plan.py:64-80` at BASE).
   - A research-simulator run that touches a held-out symbol is void (K3).
3. **The cost is small.** Holding out M of 30 instruments cuts the development effective breadth to 0.98 / 0.95 / 0.90 of its value at M = 4 / 8 / 12 (ρ 0.15) [derived]. That is a 2–10% loss of development power, for an independent test.

**2.6.2 The leak and the fix, now under adaptive iteration** (the same simulation as §2.5; 8 held-out instruments; FPR, % on the null):

| held-out test of the kept best run | K = 20 | K = 50 | K = 100 | K = 200 |
|---|---|---|---|---|
| raw, same 12-year window | **14.5** | **18.0** | **21.0** | **24.0** |
| residualised on the development P&L of the same config (VAL §2.6) | 2.8 | 2.5 | 3.2 | 2.8 |
| forward 2 years on the held-out instruments | 7.0 | 7.0 | 5.2 | 5.0 |

- VAL measured the raw leak at 10.3% (noise correlation 0.4) for a fixed search.
- **Under iteration the leak grows with the search**: 14.5% → 24% as K goes from 20 to 200 at price correlation 0.3. A harder search fits more of the common factor's noise, and the held-out instruments inherit it.
- Residualising restores size at every K.
- Forward on the held-out instruments is clean by construction; its 5–7% sits within noise of 5%.

**2.6.3 Power, and the catch in residualisation** (planted worlds):

Same simulations; the kept best run's base configuration applied to the 8 held-out instruments:

| held-out test | null FPR (K 20→200) | idiosyncratic weak | idiosyncratic μ 0.08 | common-factor μ 0.08 |
|---|---|---|---|---|
| raw, same window *(leaky)* | 14.5 → 24.0 | 34.0 / 40.7 / 42.7 / 42.7 | 87.7 / 93.0 / 96.3 / 98.0 | 67.7 / 73.7 / 72.0 / 72.7 |
| **residualised, same window** | 2.5–3.2 | 18.7 / 25.0 / 29.7 / 30.3 | **59.7 / 77.7 / 89.7 / 96.3** | **16.0 / 17.0 / 14.3 / 12.3** |
| forward 2 y | 5.0–7.0 | 11.7 / 13.0 / 14.3 / 14.0 | 34.3 / 38.0 / 41.3 / 43.0 | 16.3 / 16.0 / 18.0 / 18.0 |

**The catch, measured.**
- Residualising on the development P&L removes whatever the held-out instruments share with the development instruments. For an idiosyncratic edge that is only noise, and power is 60–96%.
- For a **common-factor edge** (a USD-wide trend) it removes the edge itself: power falls from ~70% (raw) to **12–17%**, barely above the 2.5–3.2% null.
- **The kill side, measured** (kill-rate reruns, R = 200 per world). A residualised held-out kill at SR̂ < 0 wrongly kills a real **common-factor** edge **24–27%** of the time (K 20→200). That is about the same as the 2-year forward kill of the best run (21.5–24.5%), and far above the raw test's 4–5.5%. For a weak idiosyncratic edge (fixed-config truth 0.32) it is **18–28%**. The 2-year forward kill of the best run is 25.5–32.5% in the same world.
- **Any "kill if SR̂ < 0" on a short or narrow record wrongly kills a realistic edge 18–32% of the time**, whether it is held out by instrument or by time. Stacked B and C let a weak real edge survive only ≈ 0.75 × 0.72 ≈ 54%. The kill floor must therefore sit below zero (§2.7, the kill-floor table).
- A held-out *pass* can only certify idiosyncratic transfer.
- **Can a family be classified as factor-borne in advance? Not reliably** (quick check, 6 seeds, EWMAC16 on the 20 development instruments). The mean pairwise rule-P&L correlation was 0.09 on the null, 0.07–0.08 with an idiosyncratic edge and 0.11–0.17 with a common-factor edge (μ 0.05–0.12). The signal is an excess of only +0.02 to +0.08 over the no-edge level ρ_price², too small to gate on. So B is applied to every family at the −0.5 floor. Its wrongful-kill rate there is ≈ 12% for both kinds of weak edge (derived from the measured ~25% at t < 0).
- A factor-borne edge can be tested honestly only on **forward time** (G4/G5). That is one more reason R-1 item 6 names forward time as the decisive test.

**2.6.4 How many held-out instruments give how much power** [derived; ρ_P&L 0.15; one-sided 5%; a single test]:

| M held out | portfolio SR if per-instrument s = 0.3 | same-window 10 OOS y | forward 2 y | forward 5 y | if s = 0.5: same-window / fwd 2 y |
|---|---|---|---|---|---|
| 4 | 0.50 | 47% | 17% | 30% | 84% / 32% |
| 6 | 0.56 | 54% | 20% | 34% | 90% / 37% |
| 8 | 0.59 | 59% | 21% | 37% | 93% / 40% |
| 10 | 0.62 | 62% | 22% | 40% | 95% / 43% |
| 12 | 0.64 | 65% | 23% | 41% | 96% / 44% |

- These are upper bounds for the residualised test: residualising removes the (β) part of the held-out edge that co-moves with the development P&L (§2.6.3).
- **The curve is flat past M ≈ 8.** Recommend **M = 6–8 of 30**, or 25% per stratum. More buys < 3 pp per instrument and costs development breadth.
- **Forward on held-out instruments is weak** (17–23% at s = 0.3). Held-out instruments earn their keep on the **same window**, residualised. They are a G3 *falsifier* (kill-only), not a certifier. Their same-window detection power for an idiosyncratic edge at s = 0.3 is ~50–65%.

### 2.7 Task 6 — the acceptance bar (numbers for PLAN §6)

All proposed; LLM-originated; **[spec — owner ratification]** for A–F. A, C and E replace the DSR gate of GAP-P12D-16/33 and the `annual_sharpe > 1.5` row. The FPRs are measured in this report unless marked.

| # | gate | bar (exact) | measured / derived FPR | power |
|---|---|---|---|---|
| **A** | G2 development | Register-corrected lower bound **LB_j = SR̂_j − z_{1−0.05/K}/√Y > 0**. SR̂_j is the annual Sharpe of family-version j's pooled combination on daily expanding-window OOS P&L; Y ≈ 10 (test years 2014–2023); K = every family-version declared on 2012–2023. **Budget K ≤ 10** ⇒ the bar is SR̂ > 0.81 (K = 5: 0.74; K = 3: 0.67) | 1.5% [sim, adaptive null, Holm over fixed combinations]; ≤ 5% by construction | true portfolio SR 1.0: 72% (K = 10), 80% (K = 5); SR 0.7: 36% / 46% [derived]. Planted, sim: 64–69% at a fixed-config truth of 0.31–0.58 (7 families, adaptive researcher) |
| **B** | G3 held-out instruments | M = 6–8 of 30, stratified and blind. Residualised same-window t of the frozen family on them: **kill if t < −0.5**; "transfers" if t > 1.645 (support only). Applied to every family. A "skip B for factor-dominated families" rule was considered and dropped (§2.6.3) | 2.5–3.2% false "transfers" [sim]; a wrongful kill at the t < −0.5 floor ≈ 12% for a weak edge (derived from the measured 18–28% at t < 0) | "transfers" detected: 19–30% (weak idiosyncratic edge), 60–96% (strong), 12–17% (common-factor). Wrongful kill at SR̂ < 0: 18–28% (weak idiosyncratic), 24–27% (common-factor) [sim] |
| **C** | G4 holdout 2024–25, once | **kill if t < −0.5** (i.e. SR̂ < −0.35 over 2 y). The owner's alternative is VAL/C1's SR̂ < 0 | catches a dead strategy 31% (at SR̂ < 0: 50%) | falsely kills a true 1.0 2.8% (at SR̂ < 0: 7.9%), and a true 0.5 11% (24%) [derived; sim agrees at 25–32% for SR̂ < 0] |
| **D** | G5a forward cost | **E3 certify** the realised − modelled cost per fill inside ±25%: both one-sided W ≥ 20, with the 5×-modelled-cost tripwire. **E3 breach** W ≥ 20 = kill the venue or recalibrate C8 | false certify ≤ 2.5% at the band edge, false breach ≤ 2.2% (dispersion ≤ 1) [sim] | certify: median 102–166 fills; a 2× cost error: 30–44 fills; +50%: 88–114 [sim] |
| **E** | G5b forward edge | **γ_j · W_j ≥ 20** (E1; γ_j = 1 for the first promotion if J_max = 1, else pre-committed weights). "Edge shown" | ≤ 3.7% over 20 y of daily looks, five null shapes [sim] | portfolio SR 1.5: median 2.4–3.0 y; 2.0: 1.4–1.7 y; 1.0: 5.8–6.8 y [sim] |
| **F** | G5b forward kill | **E2 with μ_claim = SR̂_j/2** (a 50% haircut of A's estimate). W ≥ 5: freeze scaling. W ≥ 20: kill | false kill when the haircut claim is true: ≤ 6.5% by 1 y, 10–11% by 10 y at W ≥ 5; ≤ 2.5% at W ≥ 20 [sim] | truth 0 against a claim of 1.0: 25% by 1 y, median 3.1 y (W ≥ 5) [sim] |

**The kill-floor trade-off** (B and C) [derived; the t-statistic of the kill test ~ N(δ, 1)]. δ ≈ 0.67 is the measured weak-edge case (25% wrongful kill at t < 0 in §2.6.3); δ = SR·√2 for the 2-year holdout:

| kill if t < | catches a dead strategy | wrongly kills: weak edge (δ 0.67) | holdout, true SR 0.5 | holdout, true SR 1.0 |
|---|---|---|---|---|
| 0 (VAL/C1) | 50% | 25% | 24% | 7.9% |
| **−0.5 (proposed)** | **31%** | **12%** | **11%** | **2.8%** |
| −1.0 | 16% | 4.7% | 4.4% | 0.8% |

- A has already bounded the false-promotion rate at ≤ 5%, so B and C are **secondary** filters. They should not destroy a quarter of the real edges each.
- −0.5 halves the wrongful kills for a 38% loss of catch rate.
- **Neither B nor C catches a look-ahead leak.** The leak is in the code, so it works on any historical instrument and period, including 2024–25. Only live time catches it; see R1A-13.

**End to end** [derived from the rows above; the stages use disjoint data, so the probabilities multiply]. P(A passes at K = 10) × P(C does not kill) × P(E "edge shown" within t years of demo), true **portfolio** SR:

| true portfolio SR | P(A) | P(C survives) | "edge shown" within 1 / 2 / 3 / 5 y of demo |
|---|---|---|---|
| 0 (null) | ≤ 5% (1.5% measured) | 50% (69% at the −0.5 floor) | ≤ 0.2% at any horizon (≤ 0.05 × 0.69 × 0.05) |
| 1.0 | 72% | 92% | 2–5% / 9–12% / 14–18% / 25–29% |
| 1.5 | 98% | 98% | 8–17% / 32–40% / 49–57% / 73–78% |
| 2.0 | ≈ 100% | ≈ 100% | 19–34% / 58–67% / 80–83% / — |

The table uses C's kill at SR̂ < 0. At the proposed −0.5 floor, P(C survives) rises to 97% at a true 1.0. The pipeline is safe against false promotion (≤ 0.2%). At realistic portfolio Sharpes it is **slow to say yes**: at SR 1.0, "edge shown" within 3 years of demo happens 14–18% of the time. Optional continuation (R1A-12) shifts each column two years earlier for literature-fixed hypotheses.

**What a full pass certifies, stated plainly.**
- **A + B + C + D:** "a pre-declared pooled family had a significant register-corrected OOS mean on 2012–2023; it was not contradicted on held-out instruments or on 2024–25; and the venue's costs match the model". That is the bar to **run the demo at scale, or to buy a challenge** (a C1/ECO money decision).
- **E:** "the forward edge's sign is shown". Nothing short of E is "edge proven".
- **Magnitude is never certified.** The best available is A's lower bound, with E2 watching it.

### 2.8 For PLAN_R1

Each item has five parts: **value** (what gets sharper), **complexity** (lines and concepts, + added / − removed), **grade**, **falsifier**, and **verdict**. All are LLM-originated procedures.

**R1A-1. Declare the search space, not only the runs** (register rule). **[spec]**
- Value: the development verdict holds its FPR under "iterate freely". It is 5.2–5.5% for max-t over the declared grid and 1.5% for fixed family combinations, where the registered-union max-t runs at 10–16% and Bonferroni over the runs at 6.5–13% under an adaptive hill-climber (§2.5).
- Complexity: +1 register field (the hashed grid, formula and instrument list); +1 concept (the family-version); ~10 lines.
- Grade: [sim], R = 400. Method (a)/(b).
- Falsifier: an adaptive-researcher null on which the declared-grid rule exceeds 7%.
- Verdict: **adopt**.

**R1A-2. A family is a fixed pooled combination; no argmax inside a family.** **[spec]**
- Value: removes within-family multiplicity; FPR 1.5% on the adaptive null. It **deletes** VAL's CPCV + PBO stage from the R-1 path. Power in the planted worlds: 64–69% for Holm over fixed combinations against 45–58% for the declared-grid max-t at realistic edges (fixed-config truth 0.31–0.58); both 99–100% in a strong world.
- Complexity: −(the CPCV/PBO stage, never built) and −(per-regime QIEA selection). A combination is ~10 lines.
- Grade: [sim].
- Falsifier: a planted world where the fixed combination's power falls below the declared-grid max-t's by > 15 pp at equal FPR. Then allow grid selection with rule R1A-1.
- Verdict: **adopt**.

**R1A-3. Pooled verdicts on the daily portfolio series only.** **[impl]**
- Value: removes a 9.5–32% FPR channel (the stacked panel).
- Complexity: 0 lines as a rule; one assertion in the grader.
- Grade: [sim].
- Falsifier: none plausible; it is algebra.
- Verdict: **adopt**.

**R1A-4. Planning breadth.** **[plan]**
- The formula: IDM = √(N/(1 + (N − 1)ρ_P&L)), with ρ_P&L ≈ 0.10–0.15 (MOP (a)) and a 0.20–0.30 stress for FX-heavy sets. Use ρ_P&L, not price correlation (≈ ρ_price² for trend rules).
- IDM(20 / 30 / 40) at ρ 0.15 = **2.28 / 2.37 / 2.42**; at 0.10 = 2.63 / 2.77 / 2.86.
- Certifying a per-instrument net SR of 0.3 takes **8.4–13 y** at K = 1 on 20–40 instruments (16–25 y at K = 10). That argues for **≤ 3–5 family-versions on 2012–2023**.
- Value: the plan's universe size and look budget rest on a measured law, not hope.
- Complexity: 0.
- Grade: correlations (a) [S9, S10]; the law derived; checked by [sim].
- Falsifier: the realised ρ_P&L of the chosen universe, measured **on exploration data only** (pre-2012 or synthetic), above 0.3. Then 20–40 instruments buy < 1.8× and the budget halves.
- Verdict: **adopt**.

**R1A-5. The universe of 30, with 6–8 held out, stratified and blind, locked.** **[impl + spec]**
- Value: an independent same-window test. Its power is 54–59% at a per-instrument SR of 0.3 (up to 93% at 0.5) [derived]. It costs 4–6% of development breadth, and the curve is flat past 8. The simulated residualised power is 19–30% (weak world, per-instrument SR ≈ 0.12, which agrees with the analytic 22%) and 60–96% (strong world). Residualised FPR is 2.5–3.2%. The raw same-window test is 14.5–24% on the null and must never be used.
- Complexity: +1 register line type; a loader refusal (~20 lines); the residualisation (~5 lines).
- Grade: [sim] + [derived].
- Falsifier: a residualised false-kill rate (SR̂ < 0) above 25% on a real idiosyncratic edge (18–28% at SR̂ < 0, measured on a weak edge; hence the −0.5σ floor of §2.7). For a **common-factor** edge the residualised test has only 12–17% power (§2.6.3), so it can never certify one: kill-only, and factor claims go to forward time.
- Verdict: **adopt**, as a kill-only falsifier.

**R1A-6. Forward edge e-process E1.** **[impl; thresholds spec]**
- Statistic: **`W_t` = the mean over λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8} of Π(1 + λ·max(r_s/(6σ*), −1))**, on the demo book's daily net P&L, with σ* declared (`E_MIX`). The alternative is a plug-in λ_t = clip(m̂/(v̂ + m̂²), 0, 0.8).
- Verdict: γ_j·W ≥ 20 = sign of edge shown. Read it daily.
- Value: FPR ≤ 3.7% over 20 years of daily looks, where daily t-peeking gives 38–47%. Median to "shown" (both bettors, three null shapes): 1.4–1.7 y at portfolio SR 2.0, 2.4–3.0 y at 1.5, 5.8–6.8 y at 1.0.
- Complexity: ~25 lines, 1 concept (bettor's wealth). −(the CUSUM in VAL K5 for the edge claim).
- Grade: method (a)/(b); numbers [sim].
- Falsifier: FPR > 5% on any synthetic null without a tripwire event.
- Verdict: **adopt**.

**R1A-7. Forward kill E2.**
- μ_claim = SR̂_dev/2. W ≥ 5 freezes scaling; W ≥ 20 kills.
- Value: false kill ≤ 6.5% in year 1. Catches a truth of 0 against a claim of 1.0 in 25% of cases by 1 y (median 3.1 y).
- Complexity: +5 lines.
- Grade: [sim]. The flat 50% haircut is a rule of thumb that Harvey & Liu criticise as nonlinear in reality [S17] (search summary only, (c)). It is used here only as a deliberately conservative kill claim, not as an estimate.
- Falsifier: a false-kill rate > 11% by 10 y at W ≥ 5 when the claim is true.
- Verdict: **adopt**.

**R1A-8. Forward cost gate E3.**
- Paired per-fill cost gap against the shadow replay through the same C8 `CostModel`. The band is ±25%, with a 5×-modelled-cost tripwire.
- Certify: both sides W ≥ 20. Breach: W ≥ 20 → kill or recalibrate.
- Value: certify at a median 102–166 fills (≈ 3–28 weeks at 6–40 fills/week; ≈ 5–8 at 20 a week). A doubled cost is caught in 30–44 fills. False certify ≤ 2.5%.
- Complexity: ~15 lines on R1A-6's bettor.
- Grade: [sim]; the fill rates are (b) turnover plus a (c) fills-per-turnover assumption.
- Falsifier: measured fill-gap dispersion > 1.5 modelled costs. Then certification needs ~600 fills, and the tripwire must widen.
- Verdict: **adopt**.

**R1A-9. The honest demo timeline, written into the plan.**
- Weeks 0–4: plumbing (VAL §5.4 (c)).
- Weeks 3–28 (≈ 5–8 at 20 fills a week): cost certified (E3).
- From then: E1 and E2 run silently. "Edge shown" is not expected before year 2–3 even at portfolio SR 1.5.
- Value: prevents "it trades" or "it's up" being read as "it works" (the owner directive in CLAUDE.md).
- Complexity: 0.
- Grade: [sim] + [derived].
- Falsifier: an observed fill rate below 6 a week. Then every week figure scales up by the shortfall.
- Verdict: **adopt**.

**R1A-10. Acceptance bar A–F** (§2.7) **[spec]**
- **A:** Holm lower bound > 0 on 10 OOS years, K ≤ 10, i.e. **SR̂ > 0.81** (0.74 at K = 5). Power 72% (80%) at SR 1.0.
- **B:** residualised held-out, kill-only at t < −0.5, for every family.
- **C:** holdout 2024–25 once, kill-only at t < −0.5 (SR̂ < −0.35).
- **D:** E3 certified.
- **E:** E1 γW ≥ 20 for "edge shown".
- **F:** E2 on, at μ_claim = SR̂/2.
- Value: replaces a gate with 0% power (C1) with one that has a measured FPR and power at each stage.
- Complexity: −(`deflated_sharpe` in `passed`, `trial_count`, the per-trade basis); + ~60 lines in total.
- Falsifier: stage FPRs measured above 5% on R1-C's synthetic lab.
- Verdict: **adopt** (owner ratification).

**R1A-11. EB shrinkage as a report, and per-instrument deviation only for cost reasons (or τ̂ > SE√(1 − ρ)).**
- Value: per-instrument argmax loses 4–10% of the edge at τ ≤ 0.1; EB matches the better of pooled and per-instrument at every τ, and its deviation flag fires 0–0.1% when τ ≤ 0.1 [sim].
- Complexity: ~15 lines, or 0 if the rule is "pool except cost".
- Grade: [sim]; method (a) (James–Stein / empirical Bayes).
- Falsifier: EB-shrunk selection loses to pooled in the τ ≥ 0.2 world.
- Verdict: **adapt**, as a reporting tool and a gate on deviation, not as a selector.

**R1A-12. Optional continuation of E1 from the first holdout day, for literature-fixed hypotheses only.**
- Value: ~2 y earlier "edge shown" at portfolio SR 1.5.
- Complexity: 0 lines; a rule.
- Grade: (a) [S6].
- Falsifier: none statistical (Grünwald et al. (a)). The risk is contamination; not for LLM-shaped ideas.
- Verdict: **adapt** (owner decision).

**R1A-13. Live-versus-replay decision reconciliation on the demo (zero-mismatch rule).** **[impl]**
- Rule: after each bar closes, the live decision must equal the replay decision on the same bars (side, target, timing). Any mismatch raises K3 or K5.
- Value: the only gate that can catch a look-ahead leak (GAP-P12D-65) after the fact. It is deterministic, so a single mismatch is a finding, and it works in days, not years.
- Complexity: ~30 lines on the shadow replay that E3 already needs.
- Grade: [derived]. It extends VAL R3.
- Falsifier: a planted one-bar leak in the replay path that yields no mismatch within 20 decisions.
- Verdict: **adopt**.

**R1A-14. Kill floors below zero for the secondary gates:** B and C kill at t < −0.5.
- Value: halves the wrongful kills of realistic edges (25% → 12%) and keeps 31% catch of dead strategies. Gate A already bounds false promotion at ≤ 5%.
- Complexity: 0.
- Grade: [sim] + [derived].
- Falsifier: a pipeline-level null FPR above 5% with the −0.5 floors.
- Verdict: **adapt** (owner choice between 0, −0.5 and −1.0).

**Rejected:**
- **online FDR (LORD, SAFFRON, alpha-investing) over development runs.** Invalid under adaptive reuse of the same history (§2.5.1). It is fine only for streams tested on fresh data, where R1A-6's weights already are e-LOND's single-discovery case.
- **e-values computed on development history as the development gate:** valid (0% FPR) but weak. Power is 0–26%, where Holm on the same data has 64–100% (§2.5.3). e-values belong where data arrive sequentially: the forward record.
- **the known-σ mixture SPRT:** 20% FPR under vol mis-sizing.
- **stacked-panel pooled tests.**
- **raw same-window held-out tests.**

### 2.9 Reproduction

Everything runs from `CLOUD_AUDIT/reports/r1/evidence/R1A/` with `OMP_NUM_THREADS=1`. No file there imports the repo, and none reads any data.

| receipt | command | output | wall time (2 workers, shared box) |
|---|---|---|---|
| e-processes E1, E2, E3 | `python sim_eprocess_demo.py 2000`, then `python sim_eprocess_demo.py 2000 costonly` (the tripwire/clip variants) | `sim_out_eprocess.json` | ~2 min + 1 min |
| breadth, IDM, the panel-vs-portfolio FPR, the price→P&L correlation map | `python sim_breadth.py 400` | `sim_out_breadth.json` | ~1 min |
| register verdicts under an adaptive researcher; held-out instruments | `python sim_register_verdict.py null 400` → `sim_out_register_null.json`; `... idio 300 0.08` → `sim_out_register_idio_mu08.json` (renamed by hand from an earlier run with an identical generator); `... factor 300` → `sim_out_register_factor.json`; `... idio_weak 300 0.05` → `sim_out_register_idio_weak_mu005.json`; the kill-rate reruns `... factor 200 0.08` → `sim_out_register_factor_mu008.json` and `... idio 200 0.05` → `sim_out_register_idio_mu005.json` | as listed | ~6–10 min per world |
| pooled vs per-instrument vs EB parameter choice | `python sim_shrinkage.py 2000` | `sim_out_shrinkage.json` | < 1 min |

Declared simplifications:
- the returns are Gaussian with a common factor (the e-process sims also use t4, GARCH-t, skewed and mis-sized nulls);
- there are no costs in the register simulation (FPR is cost-free on a null; power is gross);
- the calendar family's two forms are opposite signs, so its fixed combination is identically zero. It still counts in Holm's K, which is conservative;
- the "researcher" is a stylised hill-climber;
- the planted edges are Markov drift states, idiosyncratic (per instrument) or common-factor.

---

## 3. What I could not verify

- **Publication status of five method papers** (S1–S5, S8, S15). The arXiv pages I fetched carry no journal reference, so I grade them (b). The methods are standard; the load-bearing guarantee (Ville's inequality for a nonnegative supermartingale) is textbook and is also checked by my FPR simulation.
- **The IDM cap of 2.5** is attributed to Carver only through a search summary [S14], graded (c). I did not reach a primary quote. Nothing here depends on the cap: my breadth numbers are uncapped, and at ρ ≥ 0.15 they stay below 2.5 anyway.
- **Carver's turnover table** is as rendered by the fetch tool from his post. I did not see the raw HTML. I **assume** (c) that one turnover unit ≈ one round-trip-equivalent executed as 2–4 fills. The fills-per-week range (6–40) inherits that assumption.
- **The paired cost-gap dispersion** (0.5–2 modelled costs per fill) is a planning grid, not a measurement. The first 50 demo fills will measure it. If it is above ~1.5, E3 needs a larger tripwire bound and certification slows to ~600 fills (§2.2.3).
- **MOP's correlations** are for 12-month TSMOM on monthly futures returns, 1985–2009. ACIS's rules are daily EWMAC-type rules on CFDs, 2012–2025. I use MOP only to set a planning range, not as a measurement of ACIS's universe. Computing it from the Dukascopy data would be a look, so I did not.
- **The register simulation's researcher** is a stylised hill-climber (§2.5). Real researchers are cleverer at finding noise: they change the rule's *form*, which my grid only partly represents. The measured inflation is therefore a **lower bound** for keep-best-style rules.
- **Not simulated:** R1A-13 (live-versus-replay reconciliation); the forward weights γ_j across several promotions; and the kill floors' effect on a full pipeline (derived analytically).
- **Not run:** a heavy-tailed or GARCH version of the register and held-out simulations (C1 and VAL showed that size holds across those shapes); CPCV/PBO inside the register simulation (VAL's; not duplicated); an e-LOND implementation (argued analytically in §2.5, not simulated).

## 4. Residual risk

- **The declared grid is the new load-bearing honesty assumption.** §2.5's rule holds only if the grid was declared **before** the first look, and if every "new idea" that is a disguised grid extension is declared as a new version. No statistic can detect a grid quietly redrawn after looking. It is an organisational control: exclusive-create register lines, hashed grids, and the LLM-contamination law (GAP-P12D-66).
- **The forward e-process's validity rests on σ\* and the tripwire.** If the sizing drifts, E1 stays valid (§2.2.3, the 1.5× row) but its power falls. If a tripwire exceedance is handled by clipping instead of halting, validity can fail in the flattering direction (the 43% row).
- **The slow part stays slow.** Nothing here makes a realistic edge (portfolio SR 0.5–1.0) provable forward in under ~6 years. The design only makes the wait honest and daily-readable. At a true portfolio SR of 1.0 the median W after 1 / 2 / 3 years is only 1.3 / 1.9 / 2.4 (`E_MIX`), or 0.85 / 1.0 / 1.4 for the plug-in bettor, whose median path dips below 1 in year 1. An owner reading a W of 2–4 as "nearly there" is misreading it [sim].
- **Breadth assumes that the edge is shared and the noise is not.**
  - If the edge rides a common factor (a USD trend), breadth multiplies the noise as much as the edge, and residualised held-out tests remove the edge itself (§2.6.3).
  - The planning ρ (0.10–0.15) comes from a 1985–2009 futures study. A 2012–2025 FX-heavy CFD universe may sit at 0.2–0.3, which adds 30–70% more years (§2.3.4).
- **Holm over family-versions is honest but blunt.** At K = 10 the bar is SR̂ > 0.81 over 10 OOS years. A real pooled family at portfolio SR 0.7 passes only 36% of the time. "No pass" remains the likely outcome even for a real edge (as C1 and VAL found), and the pressure to iterate that creates is exactly what the declared-grid rule has to withstand.
- **Leakage defeats every statistical row** (VAL §7; GAP-P12D-65). None of these statistics detects a look-ahead. Only the structural tests do, plus R1A-13's live decision reconciliation, which is deterministic, not statistical, and is itself unsimulated.

## 5. Proposed ledger items (no IDs)

1. **Counting registered runs is not enough under adaptive iteration: the register must declare the reachable search space (the grid) before the first look, and the development verdict must count over it.**
   - Severity: critical. Likelihood: high. Proposed status: open. **[spec — owner ratification]** (it amends the counting rule proposed in GAP-P12D-64 and GAP-P12D-33).
   - Measured on an adaptive null: the registered-union max-t runs at 10–16% FPR and Bonferroni over the runs at 6.5–13%, against 5.2–5.5% for the declared grid and 1.5% for fixed pooled combinations.
   - Cost: +1 register field (the hashed grid); ~10 lines.
2. **Pooled-across-instruments verdicts must use the daily portfolio series (or date-clustered errors), never the stacked instrument × day panel.**
   - Severity: high. Likelihood: high once pooling lands. Proposed status: open. **[impl]** (a rule plus one guard assertion in the grader).
   - Measured: the panel t passes a zero-edge pooled rule 9.5–32%.
3. **Demo forward verdicts use anytime-valid e-processes (E1 edge, E2 kill, E3 cost gap), with a declared σ\* and tripwires, not t-stats read daily and not CUSUM alone.**
   - Severity: high. Likelihood: high: the owner looks daily, and daily t-peeking passes zero-edge records 38–47% in 10 years. Proposed status: open. **[impl]** for the statistics; **[spec — owner ratification]** for the thresholds (W ≥ 20; kill at W ≥ 5 and 20; the ±25% cost band).
   - Cost: ~40 lines, one concept. It replaces the CUSUM leg of VAL K5.
4. **The bounded-betting clip must be a tripwire (halt and raise K5), never a winsorisation.**
   - Severity: high. Likelihood: medium. Proposed status: open. **[impl]**
   - Measured: silent clipping at a 5×-cost bound gave 43% false "cost model certified" at the band edge.
5. **State in the plan what the demo record can prove and when:**
   - plumbing and cost in ~3–28 weeks (100–170 fills);
   - the sign of the edge only at a portfolio SR ≥ 1.5 within 2–3 years (median 6–7 years at 1.0);
   - magnitude never.

   Severity: high (money and expectations). Likelihood: high. Proposed status: open. **[spec — owner ratification]**. It amends the reading of R-1 item 6.
6. **C1's detectability frontier is conservative by Lo's (1 + S²/2) factor applied with annual S; the daily-data frontier at SR 1, K = 1, is 6.2 years, not 9.3.**
   - Severity: low. Likelihood: certain. Proposed status: fix wording. **[impl — docs]**
7. **Held-out instruments: 6–8 of 30, stratified blind draw, locked by an exclusive-create register line and a loader refusal; graded residualised on the same window as a kill-only falsifier.** A common-factor edge cannot be tested this way (§2.6.3).
   - Severity: medium. Likelihood: medium. Proposed status: open. **[impl]** plus **[spec]** for the gate.
8. **Acceptance bar A–F (§2.7) to replace the DSR `passed` gate (GAP-P12D-16/33) and the `annual_sharpe > 1.5` row, with a family-version budget K ≤ 10 on 2012–2023.**
   - Severity: critical. Likelihood: certain (the current gate passes nothing, per C1). Proposed status: owner decision. **[spec — owner ratification]**
9. **Per-instrument parameter deviation only for pre-registered cost reasons, or when the EB fit shows τ̂ > SE·√(1 − ρ); otherwise pool.**
   - Severity: medium. Likelihood: high. Proposed status: open. **[spec — owner ratification]**
10. **Optional continuation: for literature-fixed (GAP-P12D-66-exempt) hypotheses only, E1 may start at the first day of the 2024–25 holdout and continue into the demo** (one continuous look).
    - Severity: low. Likelihood: n/a. Proposed status: owner decision. **[spec — owner ratification]**
11. **Kill floors for held-out and holdout gates at t < −0.5, not SR̂ < 0.** Measured: "SR̂ < 0" wrongly kills realistic edges 18–32% per gate.
    - Severity: medium. Likelihood: high. Proposed status: owner decision. **[spec — owner ratification]**
12. **Live-versus-replay decision reconciliation (zero mismatches) on the demo, as the only post-hoc look-ahead catcher.**
    - Severity: high. Likelihood: medium. Proposed status: open. **[impl]** (extends the structural leakage work of GAP-P12D-65).

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
| S16 | Ramdas, Zrnic, Wainwright & Jordan, "SAFFRON: an adaptive algorithm for online control of the false discovery rate" (arXiv 1802.09098) | https://arxiv.org/abs/1802.09098 | (b) |
| S17 | Harvey & Liu, "Backtesting", *JPM* 2015: the "50% haircut is a serious mistake; the haircut is nonlinear" point, from a web-search summary only | https://papers.ssrn.com/abstract=2345489 (not fetched) | (c) |
| L1 | C1 CALIBRATOR (cloud run 2); VAL, ARC, ECO and SCO local finals (`/tmp/review-acis/archive/RESEARCH_*_2026-09-24.md`) | local | untrusted evidence (A9), cited as such |
