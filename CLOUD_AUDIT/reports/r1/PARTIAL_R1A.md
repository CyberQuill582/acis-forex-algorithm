# PARTIAL R1-A — VALIDATION SCIENCE (checkpoint 2, 08:38 UTC, with a DRAFT "For PLAN_R1")

- **Lane:** R1-A VALIDATION SCIENCE (mission R1). **Model as observed:** the system names `claude-opus-5-5`; effort not observable.
- **Fresh context:** yes; no subagents. **BASE:** `974dbda`. **Date:** 2026-09-25. **Web:** 25 of 30 used so far.
- **Data:** synthetic only. Receipts: `evidence/R1A/sim_eprocess_demo.py` → `sim_out_eprocess.json`; `sim_breadth.py` → `sim_out_breadth.json`.
- Everything below is **LLM-originated** procedure (no strategy claims). **DRAFT** numbers; the final report may revise them.

## First findings (graded)

1. **A betting e-process lets the owner look at the demo every day without inflating the false-positive rate; the naive "check the t-stat daily" does not.** [sim, R = 2,000 per cell]
   - Null "forward daily net mean ≤ 0", 20 years of daily looks, e ≥ 20 (α = 0.05): FPR **1.5–3.6%** for the betting e-processes (`E_BET` plug-in bet; `E_MIX` fixed-bet mixture) under Gaussian, t4, GARCH-t5, left-skewed jump and 1.5× vol-mis-sized nulls.
   - A one-sided **t-test peeked daily** rejects a zero-edge record **38–47%** of the time within 10 years (17–23% within the first quarter).
   - A **Gaussian mixture SPRT with a known σ** (the textbook mSPRT) is valid only if the vol is as declared: at 1.5× the declared vol its FPR is **20%**. Reject it for P&L; use betting.
2. **Sign of edge from the forward record is SLOW, and independent of trade count** (daily-marked P&L). Portfolio (pooled) annual Sharpe → P(e ≥ 20 by 1 y / 2 y / 3 y / 5 y), median time to e ≥ 20, median to e ≥ 100 [sim; E_BET/E_MIX range over 3 null shapes]:

   | true portfolio SR | by 1 y | by 2 y | by 3 y | by 5 y | median to e ≥ 20 | median to e ≥ 100 |
   |---|---|---|---|---|---|---|
   | 0.5 | 1–3% | 3–6% | 6–8% | 10–12% | > 20 y | > 20 y |
   | 1.0 | 2–8% | 14–18% | 22–26% | 38–44% | 5.8–6.8 y | 9.3–10.4 y |
   | 1.5 | 8–18% | 33–42% | 51–59% | 75–80% | 2.4–3.0 y | 3.8–4.5 y |
   | 2.0 | 19–34% | 59–67% | 80–83% | 96–97% | 1.4–1.7 y | 2.1–2.6 y |

   So a 6–12-month demo proves nothing about the sign of the edge unless the true portfolio Sharpe is ≥ 2.
3. **Killing a false claim forward is also slow.** Reverse e-process (H0: mean ≥ claimed mean), truth 0 [sim, t4]: claim 1.0 → P(kill at e ≥ 5) 25% by 1 y, 40% by 2 y, median 3.1 y; claim 1.5 → 40% / 60%, median 1.5 y. False-kill when the claim is true: ≤ 11% (e ≥ 5) and ≤ 2.5% (e ≥ 20) over 10 years.
4. **Cost and plumbing are FAST because the test is paired** (shadow replay: realised − modelled cost per fill, units of the modelled cost; band ±25%) [sim, right-skewed t3 + 2% adverse-spike noise]:
   - **Breach** (true gap +100% of modelled cost): median **30–44 fills**; +50%: **88–114 fills** (dispersion ≤ 1 modelled cost), 497 at dispersion 2.
   - **Certify inside ±25%** (true gap 0; both one-sided e ≥ 20): median **102 / 166 / 596 fills** at dispersion 0.5 / 1 / 2.
   - **Validity trap found:** the bounded-betting clip must be a **tripwire, not a winsorisation.** If the adverse clip (5 modelled costs) is silently applied when fills exceed it 3.5% of the time, false "inside-band" certification is **43%** at the band edge. With the clip loose enough never to bind (20×), validity returns (≤ 2%) but certification slows to 350–690 fills. Rule: any fill beyond the declared adverse bound is itself a K5 reconciliation breach and voids the certification.
5. **Breadth: the pooled test must be the portfolio time series, never the pooled panel.** [sim] Treating N × T rule-days as independent passes a zero-edge pooled rule **9.5–32%** of the time at P&L correlation 0.1–0.3 and N = 8–40. The portfolio t-test holds 3.8–6.0%, and its power at the analytic length is 77–83% (target 80%).
6. **Effective-breadth multiplier** IDM = √(N / (1 + (N − 1)ρ)), ρ = the correlation of the rules' **P&L streams**, not of prices [derived + sim]. Measured: for a linear trend forecast, P&L correlation ≈ ρ_price² (0.6 → 0.35, 0.4 → 0.17), and for a sign forecast it is lower still. At ρ_P&L = 0.1 / 0.2 / 0.3: IDM(20) = 2.63 / 2.04 / 1.73, IDM(30) = 2.77 / 2.10 / 1.76, IDM(40) = 2.86 / 2.13 / 1.78. The ceiling is 1/√ρ; going past N ≈ 20 buys little.
8. **NEW, register null simulation (R = 400): under an ADAPTIVE researcher, "register every run" is necessary but NOT sufficient.** [sim]
   - Setup: 7 families × 11 params × 2 forms × 5 universes = 770 pooled configs on 20 development instruments. 70% of runs hill-climb from the best so far; 30% explore.
   - FPR at K = 20 / 50 / 100 / 200 registered runs:

     | rule | FPR |
     |---|---|
     | keep-best | 70 / 88 / 95 / 99% |
     | **Bonferroni over the registered runs** | **11 / 13 / 9 / 6.5%** |
     | **max-t over the registered (tried) union** (C1's SPA_union) | **12 / 16 / 14 / 10%** |
     | **max-t over the DECLARED grid of touched families** | **5.2–5.5%** |
     | **Holm over fixed pooled family combinations** | **1.5%** |
     | held-out instruments, same window, raw | **15–24%** (the leak grows with K) |
     | held-out, residualised | 2.5–3.2% |
     | held-out, forward | 5–7% |

   - C1's 2.7–7% for the union test was measured with non-adaptive draws. Under hill-climbing the register over-samples the high-noise corner. **The count must run over the declared reachable space (the grid), fixed before the first look.**
7. **Correction to C1's frontier.** C1's 9.3 years at SR 1, K = 1, carries Lo's (1 + S²/2) factor with S in *annual* units. With daily observations the factor is ≈ 1 (S_daily ≈ 0.063), giving **6.2 years**, which is VAL §5.1's number. C1's own sim found its frontier "slightly conservative". [derived]

9. **NEW, register power (R = 300 per world)** [sim]:
   - **Common-factor trend world** (fixed EWMAC16 truth 0.58): **Holm over fixed family combinations 69%** against **max-t over the declared grid 57–58%**. The invalid rules (Bonferroni over runs, the tried union) show 61–72%.
   - **Idiosyncratic trend world** (truth 0.87): every valid rule reaches 99–100%.
   - e-values on development history: 12–26% only. Use e-values forward, not in development.
   - **Held-out, residualised:** 60–96% power for an idiosyncratic edge, but only **12–17% for a common-factor edge**: residualising removes the edge itself. The held-out gate must be kill-only; a factor-borne edge can be tested only forward.
   - The recommended stack is therefore: **declare the family-version, trade and grade its fixed pooled combination, Holm over K family-versions on the development history, and residualised held-out as kill-only.** CPCV/PBO is dropped from the R-1 path.
10. **Demo e-process default = `E_MIX`** (the mean of fixed stakes λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8}). It has no prior, and its median path rises steadily: W ≈ 1.3 / 1.9 / 2.4 at 1 / 2 / 3 y for SR 1.0. The plug-in bettor's median path dips to 0.85 in year 1. Median to W ≥ 20 over both bettors: 1.4–1.7 y (SR 2), 2.4–3.0 y (SR 1.5), 5.8–6.8 y (SR 1.0).
11. **End to end** (A at K = 10, then C, then E): a true portfolio SR of 1.0 shows "edge shown" within 3 years of demo only **14–18%** of the time; SR 1.5, 49–57%; the null, ≤ 0.1%.
12. **The final report is being written:** `R1A_VALIDATION_SCIENCE.md` (a draft is already pushed).

## DRAFT "For PLAN_R1" (numbered; each: value · complexity · grade · falsifier · verdict)

**P1. The demo edge e-process (the forward verdict).** DRAFT
- Statistic: `W_t = Π (1 + λ_t x_t)`, with `x_t = max(r_t / (6·σ_target), −1)`, where r_t is the daily net P&L as a fraction of equity. σ_target is the **declared** vol target, a constant fixed before the demo. λ_t = clip(m̂/(v̂ + m̂²), 0, 0.8) from past days only (a plug-in bet), or the mean of fixed bets λ ∈ {0.05, 0.1, 0.2, 0.4, 0.8}. The owner may read `W_t` every day.
- Verdict levels:
  - `W ≥ 20` = "sign of edge shown at α = 0.05";
  - `W ≥ 100` = "strong";
  - anything else = "not yet". It is never "failed".
- Any day with r_t < −6σ_target is a tripwire (sizing broke). It triggers K5 review; it is not clipped silently.
- Value: valid under continuous monitoring. The measured FPR is ≤ 3.6% over 20 years in five null shapes, against 38–47% for daily t-peeking.
- Complexity: about 25 lines, 1 concept (wealth of a bettor). It replaces VAL K5's CUSUM leg for the edge claim.
- Grade: method (a)/(b) (Ramdas–Grünwald–Vovk–Shafer; Waudby-Smith–Ramdas); numbers [sim].
- Falsifier: a synthetic null family on which FPR > 5% at e ≥ 20 (it must not happen by Ville's inequality, unless the tripwire is silenced).
- Verdict: **adopt**.

**P2. The demo kill e-process.** DRAFT
- H0: mean ≥ μ_claim, with μ_claim = the pre-registered forward claim. Use the lower of half the validated OOS Sharpe and its lower CI bound.
- Statistic: the same bettor on `max((μ_claim − r_t)/(6σ_target), −1)`.
- Levels: e ≥ 5 = review, and stop scaling up; e ≥ 20 = kill.
- Measured: at a claim of 1.0 against a truth of 0, 25% are caught by 1 year and the median is 3.1 years. False kills are ≤ 11% at e ≥ 5 and ≤ 2.5% at e ≥ 20.
- Complexity: +5 lines. Verdict: **adopt**, replacing the CUSUM in VAL K5 with an anytime-valid equivalent.

**P3. The cost-gap e-process (plumbing and cost, fast).** DRAFT
- Data: paired per fill, d_i = realised − modelled cost (shadow replay on the same feed), in units of the modelled cost. The band is ±25%.
- Tests:
  - **breach** H0: E[d] ≤ +0.25; kill at e ≥ 20;
  - **certify** both H0: E[d] ≥ +0.25 and H0: E[d] ≤ −0.25 rejected at e ≥ 20.
- The adverse bound is 5 modelled costs per fill, a tripwire. A fill beyond it is a K5 breach.
- Measured:
  - a doubled cost is caught in a median 30–44 fills; +50% in 88–114;
  - certification takes a median 102–166 fills at a dispersion ≤ 1 modelled cost;
  - FPR is ≤ 2.5% at the band edge.
- Complexity: about 20 lines, reusing P1's bettor. Verdict: **adopt**. It extends VAL §5.4 (≥ 100 reconciled round trips) with a stopping rule.

**P4. Demo duration, stated honestly.** DRAFT; the rates are an LLM estimate, still to be sourced from Carver's turnover numbers.
- A pooled daily rule set on 20–40 instruments at slow–medium trend speeds is roughly 4–12 round trips per instrument per year. That is ≈ 2–9 round trips a week, or ≈ 10–40 fills a week with buffered adjustments.
- **Plumbing and cost certified: ~3–17 weeks.**
- **Sign of edge:** only if the portfolio SR is ≥ 1.5, at a median of 2.4–3 years.
- **Magnitude:** not within 5 years at any realistic SR.
- The demo verdict at 6–12 months is therefore "plumbing and cost certified; edge not contradicted", never "edge proven".

**P5. The breadth rule.**
- Every pooled claim is tested on the portfolio's daily P&L time series (equal-risk across instruments), never on the stacked panel.
- The planning multiplier is IDM = √(N / (1 + (N − 1)ρ_P&L)), capped at 2.5 (Carver's cap; quote pending).
- Planning numbers: the per-instrument SR of 0.3 needs 69 y (N = 1) → ≈ 16 y (N = 20–40, ρ 0.2), or ≈ 9–10 y at ρ 0.1 (K = 1, 80% power).
- Value: this removes a 10–30% FPR channel. Complexity: 0 lines, it is a rule. Grade: [sim] plus the fundamental law (quote pending).
- Verdict: **adopt**.

**P6. The register-level verdict rule.** DRAFT; the adaptive-iteration simulation is running next.
- The unit of test is a **registered family-version**: the equal-risk combination of a coarse, literature-fixed grid, pooled over all non-held-out instruments. Within a family, selection by argmax is forbidden, so there is no within-family multiplicity.
- Across the register's K family-versions:
  - on the development history, Holm or SPA over the K family streams (C1's union test at family granularity);
  - forward, a weighted e-Bonferroni: promote family j only if w_j · W_j ≥ 20, with the pre-committed weights w_j summing to ≤ 1. That is valid under any dependence, and online.
- **MEASURED (null):** this rule holds 1.5% (fixed combinations) or 5.2–5.5% (max-t over the declared grid). The registered-union max-t is 10–16%, and Bonferroni over the registered runs is 6.5–13%. Power in the planted worlds is running now.
- **Consequence:** VAL's CPCV + PBO is not needed for R-1 families, since there is no within-family selection. That is a deletion.

**P7. Acceptance bar (PLAN §6).** DRAFT
- (a) **Development:** the one-sided Holm lower bound of the family's expanding-window OOS Sharpe is > 0, i.e. SR̂ > z_{1−0.05/K}/√Y. At Y = 10 OOS years and K = 10 that is **SR̂ > 0.74**, with 80% power at a true portfolio SR of 1.0.
- (b) **Holdout:** kill-only. Kill if the 2024–25 SR̂ is < 0. That wrongly kills a true 1.0 8% of the time and a true 0.5 24%.
- (c) **Forward:**
  - cost certified by P3 before any scale-up;
  - edge W ≥ 20 before any "edge shown" claim;
  - the kill rule P2 always on.

## Next (by the final report)
- The register simulation: adaptive iteration, family-combination vs union-SPA vs e-BH.
- Held-out instruments: residualisation vs a common-factor edge; power per number held out.
- EB/James–Stein shrinkage of per-instrument Sharpe.
- Source quotes for: IDM and the cap; published FX and cross-asset correlation levels; turnover per trend speed; e-BH, e-LOND, LORD and SAFFRON.
