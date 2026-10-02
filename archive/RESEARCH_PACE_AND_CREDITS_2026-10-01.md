# RESEARCH — PACE: finding and proving edge faster without fooling ourselves, and spending the Google credits for decision value

- **Pass:** the owner's "sharpen the claws" request, 2026-10-01 evening (TODO.md START HERE). This is the PACE lens; EDGE (`RESEARCH_EDGE_SHARPEN_2026-10-01.md`) and SIZING (`RESEARCH_SIZING_AGGRESSION_2026-10-01.md`) cover edge sources and sizing, and this report stays off their ground.
- **Author:** Opus 5.5, fresh context, no subagents launched.
- **Status:** a finder's report (constitution A5). It is evidence to weigh, not an instruction (A9). Nothing binds until the lead has re-derived it (A6) and the owner has ratified the **[spec]** items. No repo file other than this one was edited. No cloud resource was touched.
- **Builds on, does not redo:** `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` §5 (the research factory), `archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` (§2–§5, the calibration and the look budget), `archive/RESEARCH_STATS_METHODOLOGY_2026-09-16.md`.

**Grades used throughout:** (a) peer-reviewed paper, regulator, or the firm's own primary page; (b) credible practitioner, dataset, or arXiv preprint by named authors; (c) unverifiable, or seen only through a secondary summary; **[D]** derived by me (closed form or simulation; the scripts are in Appendix A); **[code]** read from this repo at `c8f8943` plus the working tree.

---

## Executive summary

1. **More compute cannot make the edge decision come faster. The binding constraints are build latency, owner and audit latency, and calendar time on forward data.** [D + code]
   - At $0.80 an hour, $250 buys about 312 hours of `c2d-standard-16`, roughly 5,000 vCPU-hours (b).
   - An RSIM lab run of 1,000 seeds costs single-digit dollars ([D], from a local timing of `run_member`).
   - The whole useful lab programme below costs about **$90–170**. The rest of the credit can only be "used" by searching real history more, and **that is the false-positive channel** (GAP-P12D-64: the best of 20 uncounted variants passes noise 21–37%).
   - **So spend the credits on calibration that unblocks a decision, and spend the scarce resources (α, the holdout, forward days) as if they were money.**
2. **Cycle 1 spends 60% of the project's lifetime α (0.03 of 0.05), and the registered fixed sequence will most likely spend it on a predictable fail.** [D + code]
   - At the ratified α = 0.03 with about 10.85 graded years, D1 passes stage A with probability **0.20 / 0.48 / 0.76** at the plan's swap-free Sharpe range (0.32 / 0.555 / 0.79). Under FTMO's swaps (−0.15..+0.32) the probability is **0.01–0.20, about 0.05 at mid-range**.
   - The 28/58/84% recorded in GAP-P12D-102 were computed at α = 0.05; the ratified D-d budget is 0.03.
   - If D1 fails, the chain stops, the cycle is over, and cycle 2 gets α = 0.01 a quarter later.
   - An online-fallback or weighted-Holm allocation keeps lifetime FWER at or below 0.05 under arbitrary dependence. In my simulation it gives **1.6–2.8×** the expected true discoveries of the fixed sequence when the first-ordered family is uncertain (§3.6, [D]; Wiens 2003 (a), Bretz et al. 2009 (a), Tian & Ramdas (a/b)).
3. **For the TREND family, history can only kill. Credit comes only from forward data, and forward credit takes years unless the portfolio Sharpe is at least about 2.** [code + D]
   - `core/signals/families.py:7-8` records every TREND member as LLM-selected, so master §5.6 v2.24 says it can be "killed on any history, and credited only forward" [code].
   - The specified E1 bettor reaches W ≥ 20 within 3 years at a true Sharpe of 1.0 / 1.5 / 2.0 with probability **0.23 / 0.49–0.53 / 0.81**. The median crossing is about 6.5 years at 1.0 and 3.1 years at 1.5 [D].
   - Under anytime validity, that is slower than one fixed 3-year test (0.53 / 0.83 / 0.97) and slower than a pre-registered group-sequential design (0.52 / 0.81 / 0.96, which decides 27–40% earlier at SR 1.5–2.0) [D].
   - **The practical forward milestone is rung 2, "fit to trade at minimum size": three months of practice-mode record, E2 silent and E3 certified, plus human sign-off. It does not wait for E1** (ACIS_SPEC.md §14) [code].
4. **The critical path to "challenge-eligible" is R1.6, not the first look.**
   - The spec already lets a REGISTERED, B0-passed family trade at one minimum lot in practice mode (ACIS_SPEC.md §5, "Validated", D-a) [code].
   - D1 passed B0(a)/(b) on the lab (GAP-P12D-121), but it cannot trade on the demo until the engine runs it, which is R1.6 (the Governor's band, min size, flatten-then-promote).
   - **Building R1.6 alongside R1.4, instead of after the first look, starts the three-month rung-2 clock about 6–10 weeks earlier** [D].
5. **B0 item (d) puts R1.6 on the path to ANY real-data verdict, a sequencing conflict nobody has ruled on.** [code]
   - ACIS-09 C-BT-11 v2 step 0 requires "the research simulator ≡ the engine on lab tapes" before a real-data verdict is issued.
   - GAP-P12D-105 records that (d) "needs RSIM (R1.3) and the engine reconciliation (R1.6)".
   - TODO.md schedules the first look after R1.1–R1.4.
   - The owner rules either (i) that (d) binds from stage B on, so stage A may be graded before R1.6, or (ii) that the first look waits for R1.6. The case for (i) is that an RSIM-only kill stays a valid kill and stage B re-tests the engine. The case against it is that a buggy RSIM can produce a false kill that burns D1 on this record.
6. **Pooling helps less than people expect, and breadth across families helps more.** [D; Grinold 1989 (a)]
   - At an average pairwise strategy correlation of 0.2, 21 instruments multiply a per-instrument Sharpe by 2.05, and 30 by only 2.10. The ceiling is 1/√ρ̄.
   - The pace lever is independent *mechanisms* (families), each adding breadth on its own clock. More instruments in one family barely move it.
   - Events at 8–12 a year can only be killed on history, never credited forward in practical time. For a per-event effect of 0.3 sd, 80% power needs about 82 events: about 10 years of FOMC days.
7. **The proven traps are uncounted search, post-publication decay and LLM memory. None of them shrinks with more compute.**
   - Backtest-to-live Sharpe fell a median 73% (1.20 → 0.31) across 215 commercial strategies (Suhonen et al. 2017, (a) via (b) summaries).
   - Published anomalies deliver about 50% of in-sample performance out of sample (Falck, Rej & Thesmar 2022 (a)). Returns are 26% lower out of sample and 58% lower after publication (McLean & Pontiff 2016 (a)).
   - 65% of 452 anomalies fail |t| ≥ 1.96, and 82% fail t ≥ 2.78 (Hou, Xue & Zhang 2020 (a)).
   - An LLM's look-ahead propensity "collapses essentially to zero right after the training-data cutoff" (Gao, Jiang & Yan 2025/26 (b)).
8. **Ranked credit plan.** Full list in §5; all on-demand at $0.80/h. The top three need R1.4/R1.6 code that does not exist yet, so they run once it lands; the jobs that run today on existing code are J9 and J1.
   - **(1) J2:** the end-to-end lab calibration of the R1.4 verdict chain at B0's n ≥ 2,000, including the cycle-1 order design. About 200 vCPU-h, **~$10**; it is the B0 a real-data verdict needs.
   - **(2) J3:** B0(d), RSIM ≡ engine on lab tapes, plus a stage-B dry run. About 400–900 vCPU-h, **~$25–45**; it needs R1.6.
   - **(3) J5:** lab machinery (B0) for the 2–3 next sleeves EDGE recommends, so they can join cycle 1. About **$3–12 each**; it needs their rule code.
   - **Today's job, J1:** the stage-A operating characteristics across the owner's R1-D9 (swap world) × R1-D14 (account size and vol target). About 650 vCPU-h, **~$33**. It shows whether the first look is worth its α at all.
   - The P&L-blind admission run and the covariance input, J9, cost under $1 and are on R1.3's critical path.
9. **Free-trial terms that bind** (Google's page, updated 2026-09-24, (a)):
   - no GPUs, no Marketplace, **no quota increases**, no Windows;
   - the credit "must be consumed within the original 90 days", so upgrading does NOT extend it past 10-21;
   - at the end, resources are stopped and Compute Engine data is "marked for deletion", with a 30-day grace period if the account upgrades;
   - the page states no vCPU cap and no Spot ban. The binding limit is the project's regional quota, which the lead can read with a read-only `gcloud compute regions describe europe-west1`.
   - After the trial, Spot `c2d-standard-16` is about $0.118/h against $0.80 on demand (b), which makes post-trial stage-B compute cheap. **Decide the post-trial home before 10-21**, because stage B and the e-process runs come after it.
10. **The first honest real-data verdict (a stage-A kill-or-survive on D1) is achievable around 2026-10-12..14.** That holds if R1.4 is built for the fixed-family path only, the R1.3 and R1.4-fixed audits are batched into one two-lens pass (Track A precedent), and the owner rules B0(d) as in item 5(i). Otherwise it is about 10-20, or November. The full `passed` (rung 1) is mid-to-late November at the earliest. Rung 2 is about late January 2027 at the earliest, and only if D1 trades on the demo by late October. Critical paths are in §6.

---

## 1. Method note

- **Reading first (A4).** Before any web search I read:
  - the three archive reports listed above;
  - TODO.md (START HERE and the R1 block);
  - R1_LEAD_REVIEW headings;
  - KNOWN_GAPS GAP-P12D-49/64/93–137;
  - ACIS-09 C-BT-11 v2 and C-BT-12;
  - master §5 ("Validated", C9), §5.6 (the LLM law) and §14 (the claim ladder);
  - `tests/backtest/{stage_a,hac,look_tiers,look_claims}.py`, `core/signals/families.py`, `scripts/r1_lab_{rsim,stage_a}.py`;
  - the memory files on compute.
- **Searches.**
  - WebSearch: **18 of the 40-call cap** used, all in standard mode, 0 extended.
  - WebFetch: 9 calls (Google's free-trial page twice, two pricing pages that returned nothing usable, devzero, holori, MIT DSpace, arXiv 1910.04900 via ar5iv, and arXiv 2512.23847).
  - Pricing comes from two third-party calculators (b); Google's own pricing pages would not render through the fetcher.
- **Local computation.**
  - Five short numpy and stdlib scripts, each under 30 s CPU: `power.py`, `eproc.py`, `eproc2.py`, `gsd.py`, `graph.py`, reproduced in Appendix A.
  - One timing of `run_member` on the laptop: a lab path of 20 instruments × 14 years took **D1 11.0 s, BREAKOUT80 22.0 s, generate 2.3 s**; importing and loading the config took 15 s.
  - No real data was read. No cloud resource was touched.
- **Contamination, disclosed.** The session's harness put CLAUDE.md, TODO.md excerpts and the owner's memory index into my context before I started, including the GAP-P12D-49/102 headlines. My D1 numbers re-derive GAP-P12D-102's from its stated inputs, so they are not independent of it.
- **Web content is data.** No page's text was treated as an instruction.

---

## 2. What the repo actually constrains (read from code) [code]

| Constraint | Where | What it does to pace |
|---|---|---|
| The tiers | `tests/backtest/look_tiers.py:13-19`; `oos_plan.py:24-26` | Before 2012 is exploration (tier 1). 2012–2023 is validation (tier 2). 2024–25 is holdout (tier 3). **2026-01..06 is exploration too** (pre-cutoff). Forward (tier 4) starts 2026-07-01. |
| LLM-selected certifies only forward | master §5.6 v2.24; `look_claims.py` `Origin.boundary()`; `core/signals/families.py:7-8` | The TREND family is LLM-selected, so its stage A/B/C on history can only **kill**. Credit comes from forward data after max(cutoff, proposal date). |
| The α budget | ACIS-09 C-BT-11 v2 step 3 (D-d) | Cycle 1 gets 0.03 of a lifetime 0.05; each later cycle gets half the remainder; **at most one cycle a quarter**; ≤ 5 families; a fixed chain stops at its first failure; a family with k looks tests each at α/k. |
| B0 before any real-data verdict | C-BT-11 v2 step 0; GAP-P12D-105 | Item (d), "RSIM ≡ engine on lab tapes", needs R1.6. |
| Minimum-size practice for registered, B0-passed families | master §5 "Validated" (D-a); GAP-P12D-106 | A forward record can start before any historical verdict. |
| The claim ladder | master §14 | Rung 1 = `passed`. Rung 2 = rung 1 + ≥ 3 months of practice (E2 silent, E3 certified, live = replay) + human sign-off. Rung 3 adds E1 ≥ 20. |
| Stage-A pieces already built | `stage_a.py`, `hac.py` (Newey–West, lag floor(4(T/100)^(2/9)), about 8 at T ≈ 2,830) | Lab results: null 2.6% at α 0.03; planted 98 / 65 / 18% (GAP-P12D-136). |
| R1.4 items | TODO R1.4 | 104, 111, 119, 120, 112, 114, 110, 100, 86. **119/120 (max-t, PBO) apply only to EXPLORED families.** |

---

## 3. Statistical power, concretely (task 1)

### 3.1 The one law that sets everything

The standard error of an annualised Sharpe estimate is about √(VIF / Y), whatever the sampling frequency. Y is years. VIF is the long-run variance inflation from autocorrelation, which is what the Newey–West HAC estimates (Lo 2002 (a): serial correlation can overstate an annual Sharpe "by as much as 65 percent"; Bailey & López de Prado 2012 (a), the minimum track-record length).

The years needed for a one-sided test of mean > 0 are then Y = VIF·((z₁₋α + z_power)/SR)² [D, `power.py`]:

| α (one-sided) | SR 0.3 | SR 0.5 | SR 0.75 | SR 1.0 | SR 1.5 | SR 2.0 |
|---|---|---|---|---|---|---|
| 0.05 (50% / 80% power) | 30 / 69 | 10.8 / 24.7 | 4.8 / 11.0 | 2.7 / 6.2 | 1.2 / 2.7 | 0.7 / 1.5 |
| **0.03 (cycle 1)** | 39 / 82 | 14.1 / 29.6 | 6.3 / 13.2 | 3.5 / 7.4 | 1.6 / 3.3 | 0.9 / 1.9 |
| 0.015 (cycle 1, k = 2 looks) | 52 / 101 | 18.8 / 36.3 | 8.4 / 16.1 | 4.7 / 9.1 | 2.1 / 4.0 | 1.2 / 2.3 |
| 0.01 (cycle 2) | 60 / 112 | 21.6 / 40.1 | 9.6 / 17.8 | 5.4 / 10.0 | 2.4 / 4.5 | 1.4 / 2.5 |
| 0.005 (cycle 3) | 74 / 130 | 26.5 / 46.7 | 11.8 / 20.8 | 6.6 / 11.7 | 2.9 / 5.2 | 1.7 / 2.9 |

Multiply every entry by VIF. A trend book at lag-1 ρ ≈ 0.1 has VIF ≈ 1.2.

**Power on the development tier** (2012–2023 less the 300-weekday warm-up gives Y = 10.85; VIF = 1) [D]:

| α | SR 0.3 | SR 0.5 | SR 0.75 | SR 1.0 | SR 1.5 |
|---|---|---|---|---|---|
| 0.03 | 0.19 | 0.41 | 0.72 | 0.92 | 1.00 |
| 0.015 | 0.12 | 0.30 | 0.62 | 0.87 | 1.00 |
| 0.01 | 0.09 | 0.25 | 0.56 | 0.83 | 1.00 |
| 0.005 | 0.06 | 0.18 | 0.46 | 0.76 | 0.99 |

**D1 at the ratified α = 0.03** [D; inputs from PLAN_R1 via GAP-P12D-94/102]:

| World | Assumed portfolio SR | P(stage-A HAC bound > 0) |
|---|---|---|
| Swap-free, low / mid / high | 0.32 / 0.555 / 0.79 | 0.20 / 0.48 / 0.76 |
| FTMO swaps, low / mid / high | −0.15 / 0.085 / 0.32 | 0.01 / 0.05 / 0.20 |

The kill-only conditions (C9 over seven members, plateau, 2× cost, benchmark) cost a further 1–3 points (lab, GAP-P12D-136). **GAP-P12D-102's 28/58/84% were at α = 0.05; this table supersedes them at the budget the owner ratified (D-d).**

### 3.2 Pooling across 20+ instruments [D]

The portfolio Sharpe is SR_i·√(N / (1 + (N−1)ρ̄)), where ρ̄ is the average correlation of the instruments' *strategy P&L* (not their prices):

| N | ρ̄ = 0 | 0.1 | 0.2 | 0.3 | 0.5 |
|---|---|---|---|---|---|
| 5 | ×2.24 | ×1.89 | ×1.67 | ×1.51 | ×1.29 |
| 10 | ×3.16 | ×2.29 | ×1.89 | ×1.64 | ×1.35 |
| 21 | ×4.58 | ×2.65 | ×2.05 | ×1.73 | ×1.38 |
| 30 | ×5.48 | ×2.77 | ×2.10 | ×1.76 | ×1.39 |

- Past about 10 instruments, extra instruments in the *same* family add almost nothing. Correlation sets the ceiling, 1/√ρ̄. PLAN_R1's N_eff ≈ 6 (GAP-P12D-101) is consistent with ρ̄ ≈ 0.12–0.15.
- Grinold's fundamental law, IR ≈ IC·√breadth (Grinold 1989, *JPM* (a)), counts **independent** bets. Breadth bought with correlated instruments is mostly illusory, as the 9.5–32% false-pass rate of the stacked panel shows (GAP-P12D-100).
- **Pace implication:** the cheapest way to raise the testable Sharpe is a second and third *mechanism*, not instruments 22–30. The edge slate (archive EDGE_FACTORY §4: intraday momentum, fix flows, reversal) is low-correlated with slow trend by construction. That is EDGE's ground for *which*; the arithmetic here says *why breadth across families is the pace lever*.

### 3.3 Intraday effects with one observation per day [D]

- An intraday window sleeve (for example, momentum into the cash close) yields one P&L per instrument-day. Its *test* obeys the same √Y law as any daily series.
- Being intraday does not shorten the evidence clock. What it can do is give a **higher Sharpe per unit of risk**, through more independent bets a year and low correlation with trend.
- Gao et al. (2018, *JFE* (a), quoted in archive EDGE_FACTORY H1) report the effect "stronger on more volatile days". Concentrating trades raises the per-trade gross/cost ratio, but it cuts the bets a year, so the Sharpe moves only if the IC rises faster than √breadth falls.
- **What 12 years can show:** a pooled index sleeve over 3–5 correlated indices (ρ̄ about 0.6–0.8, N_eff about 1.2–1.5) at a true net Sharpe of 0.75 has stage-A power of about 0.72 at α 0.03. At 0.5 it is about 0.41.

### 3.4 Event effects [D]

For n events, t ≈ d·√n, where d is the effect per event in per-event standard deviations. At 80% power and α 0.03:

| n events | 24 | 48 | 96 | 144 | 250 | 500 | 1,000 |
|---|---|---|---|---|---|---|---|
| d needed | 0.56 | 0.39 | 0.28 | 0.23 | 0.17 | 0.12 | 0.09 |

- FOMC (8 a year) over 2012–2023 gives 96 events, so only d ≥ 0.28 is detectable. Month-end FX flows (12 a year per pair, perhaps 3–4 effective pairs once the USD factor is netted out) give about 400–600 events.
- **An event sleeve that an LLM selected can never be credited forward in practical time.** At d = 0.3 it needs about 82 forward events: 10 years of FOMC, or about 2–3 years of month-ends across 3–4 effective pairs.
- So event sleeves suit **history kills** and portfolio-level forward evidence, not stand-alone forward certification.

### 3.5 What sequential methods buy [D, against (a) theory]

They buy **nothing on history**: 2012–2023 is available at once, and a fixed-sample test is optimal there. **On forward data** they buy the right to monitor continuously without inflating α. Ten unadjusted looks at nominal 5% give about 19% (Armitage, McPherson & Rowe 1969 (a), figure via (b)). The time saved is modest:

| Design (forward, one-sided 5%) | True SR 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|
| Fixed 3-year test: power | 0.53 | 0.83 | 0.97 | 1.00 |
| Group-sequential, OBF-type Lan–DeMets spending, quarterly looks, 3-year max: power / expected years to decision | 0.52 / 2.59 | 0.81 / 2.18 | 0.96 / 1.78 | 1.00 / 1.24 |
| **ACIS E1 as specified** (mixture over 5 λ, r/(6σ*), W ≥ 20): P(by 1 / 2 / 3 years) | 0.03 / 0.13 / 0.23 | 0.08–0.09 / 0.29–0.33 / 0.49–0.53 | 0.18 / 0.59–0.61 / 0.81–0.82 | 0.57 / 0.96 / 1.00 |
| E1 with one pre-registered λ = 6·SR_claim/√252, claim 1.5: P(by 1 / 2 / 3 years) | 0.06 / 0.26 / 0.40 | 0.15 / 0.48 / 0.70 | 0.30 / 0.74 / 0.91 | — |
| E1 median crossing | ~6.5 years | ~3.1 years | ~1.7 years | ~0.9 years |

The table rests on these points:
- **Size.** The E1 null rate within 5 years was 0.013 (Ville's bound is 0.05).
- **Wald's SPRT,** for a simple alternative at α 0.05 and β 0.2, needs on average 0.62× the fixed-sample n under H1 and 0.43× under H0 [D]. Wald (1945) is (a). That gain holds only when the alternative is the true one, which here it never is exactly.
- **Anytime-valid e-processes** (Ramdas, Grünwald, Vovk & Shafer 2023, *Statistical Science* 38(4) (a); Johari et al. 2022, *Operations Research* 70(3) (a)) pay for robustness to optional stopping and to an unknown effect size.
- **The specified mixture is the slowest design here.** At SR 1.5 it reaches about half the 3-year power of a fixed or group-sequential test.
- **Tuning helps but does not change the scale.** A single λ tuned to a pre-registered claim recovers about 15–20 points, and it stays valid (null 0.011).

**Verdict.** Sequential methods shorten forward time-to-decision by roughly a quarter to a half. They do not change its order of magnitude.

The spec's own rung-3 note ("about two decades at 0.5, about 11 years at 0.8, 2.4–3 years at 1.5") matches this simulation.

### 3.6 Testing several families in a cycle: the fixed sequence costs discoveries [D]

- **Setup** (`graph.py`): 200,000 simulated cycles; three families at Y = 10.85, α = 0.03, test statistics correlated 0.2.
- **Prior for D1:** true with probability 0.5, at SR 0.5 (or 0.3 for the swap-heavy row).
- **Prior for families 2 and 3:** each true with probability 0.3, at SR 0.8 and 0.6.
- **FWER under the global null:** all three designs measured 0.0294–0.0297.

| Design | E[true discoveries] | P(≥ 1 true) | P(D1) / P(F2) / P(F3) passes |
|---|---|---|---|
| Fixed sequence D1 → F2 → F3 (as registered) | 0.269 | 0.206 | 0.217 / 0.062 / 0.014 |
| Holm, equal weights | 0.441 | 0.358 | 0.140 / 0.201 / 0.125 |
| Weighted Holm 0.6 / 0.2 / 0.2 (a Bretz graph) | 0.439 | 0.355 | 0.177 / 0.180 / 0.106 |
| Swap-heavy D1 (SR 0.3): fixed sequence | 0.125 | 0.096 | 0.107 / 0.031 / 0.008 |
| Swap-heavy D1: weighted Holm 0.6 / 0.2 / 0.2 | 0.331 | 0.283 | 0.080 / 0.174 / 0.099 |

- **What the fixed sequence is for:** it maximises the first family's power (0.217 against 0.177) and starves the rest. It is the right design only when the first family is the one you are most sure of.
- **What the alternatives guarantee:**
  - Weighted Bonferroni/Holm and the fallback procedure (Wiens 2003, *Pharmaceutical Statistics* 2(3) (a); generalised by Bretz, Maurer, Brannath & Posch 2009, *Stat. Med.* 28(4) (a)) control FWER under **arbitrary dependence**.
  - Their online versions test families **one at a time as they become ready** and recycle α from each rejection. "Online Fallback controls FWER for arbitrarily dependent p-values" (Tian & Ramdas, arXiv 1910.04900 (b), published in a peer-reviewed journal per my recollection (c)).
- **What this replaces:** "at most one cycle a quarter" plus "stop at the first failure" is a pace limiter the statistics do not require.

---

## 4. Faster without self-deception (task 2)

### 4.1 What can run in parallel (with the honest condition for each)

| # | Parallelise | Today | Condition that keeps it honest | Protection lost |
|---|---|---|---|---|
| P1 | **Build R1.6 (engine parity) alongside R1.4**, not after the first look | R1.6 listed after R1.5 (TODO R1 block), behind the first look | It is a build, not a look. The owner must authorise any builder agent (CLAUDE.md, launches owner-only); otherwise the lead interleaves. | None. It unblocks B0(d), stage B and the min-size demo forward record. |
| P2 | **Start D1's forward record now, before its historical verdict** | The demo trades one QIEA champion (GAP-P12D-129) | (a) Register the frozen D1 family-version now (`look_claims.Claim`, origin LLM-selected) so the forward window opens at registration. (b) A daily RSIM "shadow-forward" ledger on Dukascopy daily candles from that date (tier 4; `rsim_real.py` must grow a tier-4 path). (c) Once R1.6 lands, D1 at one minimum lot in practice mode (master §5, D-a). | None. Forward data after a registered freeze is the cleanest evidence the project can get. Whether an RSIM paper-forward record may feed E1/E2 is an owner ruling. E3 needs real fills. |
| P3 | **Screen several pre-registered sleeves in one cycle with an online-fallback α** instead of a single-family chain | Fixed sequence; ≤ 5 families; one cycle a quarter | Weights and order registered before any look. Each family's α share fixed. Recycling only on rejection. Lifetime ≤ 0.05 unchanged. | None in FWER (Bonferroni-based, any dependence). The first family has less power than as sole heir. |
| P4 | **Exploration-tier kill screens** for candidate sleeves on 2003–2011 and on 2026-01..06, before they take a cycle slot | Tier 1 exists in `look_tiers.py`; the data store holds 2012–2025 | Kill-only. Literature parameters only, so the family stays "fixed". Used to *order or drop* candidates, never to tune them. Each run still writes a register line. | Small. A pilot on independent data that informs the order is legitimate data-splitting (Cox 1975 (a)). Weights set from independent data keep error control (Genovese, Roeder & Wasserman 2006 (a)). LLM memory covers this tier too, which is why it is kill-only. |
| P5 | **Run lab calibration jobs on acis-compute-1 while the lead builds** | Runs are sequential with the build | Synthetic only (C-BT-12). Results never enter a real verdict. | None |
| P6 | **One two-lens audit pass for R1.3 plus R1.4's fixed-family path** | TODO item 4 asks for R1.3's audits separately | Track A precedent: one pass of both lenses covered steps 3–5 (TODO). The owner must launch it. | Some depth per lens, because the scope is wider. The lens count and model floor are unchanged. |

### 4.2 Gates that can be re-sequenced or simplified with no loss of protection

1. **Build R1.4 for the fixed-family path first** [impl sequencing].
   - The first look on D1 needs:
     - 104 (`passed`), 111 (α-spending plus the order row), 100 (the portfolio unit) and 86 (the anchor);
     - the HAC bound, which is built;
     - B0 at n ≥ 2,000.
   - It does not need max-t or PBO (119/120, explored families only) or the stage-D bettors (110, forward only).
   - Deferring 119/120/110 until an explored family is registered, or the forward record starts, loses nothing. **Counter:** the owner ratified "REAL_LOOKS_OPEN after R1.4" as one gate. Opening it per family type is a governance change that needs the owner's words.
2. **Replace "≤ 5 families per quarterly cycle, the chain stops at the first failure, cycles halve α" with an online fallback over a registered γ-sequence** [spec].
   - Example: γ = 0.4, 0.2, 0.1, 0.1, 0.05, … of 0.05, with α recycled forward on each rejection.
   - Same lifetime FWER at or below 0.05, under any dependence. Families are tested when ready, not when the quarter turns.
   - **Counter:** the fixed sequence was chosen (GAP-P12D-102, R1-D2) precisely to give D1 its full α. If the owner believes D1 is the strongest candidate, it is the right design for cycle 1. The data in §3.1 say D1 is weak under FTMO's swaps.
3. **Do not spend cycle 1 on a look whose outcome is predictable** [owner decision at the first look].
   - Under FTMO swaps, D1's P(pass) is 0.01–0.20. A look with an almost-known answer still spends 60% of the lifetime α.
   - Either register the swap-free world (E8, GAP-P12D-94), or put a stronger-prior family first, or allocate D1 a small α share under P3.
   - **Counter:** a fast kill of D1 has value too: it stops R1.6 work on a dead family. P2/P1 recover most of that value cheaply.
4. **E1: the mixture over five λ with a factor of 6 is the slowest valid design measured** (§3.5) [spec, low priority].
   - A single λ pre-registered from the development claim, or a group-sequential design on the portfolio series with registered quarterly looks, both stay valid and decide about 15–40% sooner.
   - **Counter:** the mixture is robust to a mis-stated claim. A wrong single λ (claim 1.5, truth 1.0) still reaches 0.40 by 3 years against the mixture's 0.22–0.23, so the risk is small, but the robustness argument is real.
5. **Certify forward at the portfolio level** (GAP-P12D-100's portfolio unit) [spec].
   - k uncorrelated sleeves at SR 0.6 make a portfolio at 0.6·√k. Ten such sleeves reach about 1.9, where E1 crosses in about 2 years.
   - The account trades the portfolio, so that is the claim that matters for the money.
   - **Counter:** a dead sleeve inside a live portfolio gets carried. Per-sleeve E2 kills must still run.

Gates I would **not** touch, with the reason:
- **Registration before every grade.** Uncounted best-of-5 or best-of-20 variants pass noise 9–37% (GAP-P12D-64, VALIDATOR §2).
- **B0** (GAP-P12D-37 class).
- **The 2024–25 holdout, once.**
- **Forward-only credit for LLM-selected hypotheses.** Its cost is pace, and §3.5 shows it is large. It is the only structural defence against LLM memory, and statistics cannot deflate that memory away: "a leaky oracle … survives Deflated Sharpe and PBO completely" (Gençay 2026 (b), quoted in archive VALIDATION_FIREWALL §7.2). Gao, Jiang & Yan (2025/26 (b)): look-ahead propensity "collapses essentially to zero right after the training-data cutoff".
- **The 2×-cost kill.**
- **The C9 member set.** Owner-ruled; it costs only 1–3 points of power (lab).

### 4.3 Shortcuts that are known traps (evidence)

| Shortcut | Why it fails | Evidence |
|---|---|---|
| "Credits are free, so sweep parameters on 2012–2023" | Every re-score is a trial. The best of 20 uncounted passes noise 21–37%, and at 24 years still 26%. | VALIDATOR §2 [sim], GAP-P12D-64; Bailey et al. 2014 MinBTL (a); Harvey, Liu & Zhu 2016 *RFS*, t > 3 (a) |
| Trusting a backtest Sharpe as the live expectation | Median backtest Sharpe 1.20 against 0.31 live; the haircut is worse for complex strategies | Suhonen, Lennkh & Perez 2017 *JPM*, 215 strategies ((a) via (b) summaries); Wiecki et al. 2016 (b): R² < 0.025 |
| Trusting a published effect at its published size | About 50% of in-sample performance out of sample; 26% lower OOS and 58% lower after publication | Falck, Rej & Thesmar 2022 *QF* 22(11) (a); McLean & Pontiff 2016 *JF* (a); Hou, Xue & Zhang 2020 *RFS*: 65% fail |t| 1.96, 82% fail 2.78 (a) |
| Peeking at the demo P&L and adjusting | Unadjusted repeated looks inflate α to about 19% at 10 looks. Any change creates a new family-version, which resets the forward clock. | Armitage et al. 1969 (a); Johari et al. 2022 (a) |
| Certifying an LLM-proposed rule on pre-cutoff history | Look-ahead propensity is positive in-sample and about 0 after the cutoff. LLM-backtested in-sample returns needed corrections of up to −67%. | Gao, Jiang & Yan arXiv 2512.23847 (b); arXiv 2605.24564 (b); Lopez-Lira, Tang & Zhu 2025 (a/b) |
| Grading the stacked instrument × day panel | Passes a zero-edge rule 9.5–32% of the time | GAP-P12D-100 [sim, PLAN_R1] |
| Using the 2-year holdout as a pass | It detects a true 0.94 only about 33.5% of the time; kill-only | VALIDATOR §5.4 [sim] |
| Counting a passed prop challenge as edge | A zero-edge strategy passes 25% (FTMO 2-Step at 1%/day) | EDGE_FACTORY §2 [sim] |

---

## 5. The credit plan (task 3)

### 5.1 Terms and prices

- **What the trial allows.** Google's free-trial page, last updated 2026-09-24 (a), says that while on the trial you cannot:
  - "Add GPUs to your VM instances";
  - "Use Google Cloud Marketplace";
  - "Request a quota increase";
  - "Create VM instances that are based on Windows Server images".

  Mining cryptocurrency is prohibited. The page **states no vCPU cap and no Spot restriction**. (Forums report 8- or 24-vCPU trial limits (c), but this account already runs 16.) **The binding ceiling is the project's regional CPU quota, which cannot be raised during the trial.** Before sizing larger jobs, the lead reads it read-only: `gcloud compute regions describe europe-west1` (CPUS, C2D_CPUS, PREEMPTIBLE_CPUS) and `gcloud compute project-info describe` (CPUS_ALL_REGIONS).
- **Upgrading.** "Your remaining credit is available … but [it] must be consumed within the original 90 days period from your sign-up date" (a). Upgrading keeps the credit until 10-21 but does not extend it.
- **The end.** The "billing account will be closed and all of its associated projects and resources will be stopped". Compute Engine data is "marked for deletion and might be lost", with a 30-day grace period if the account upgrades (a). **The bucket's run archive and the Google candle copy are at risk.** The AWS copy of the candles exists (GAP-P12D-136).
- **Prices** (b: two independent calculators agree):

  | `c2d-standard-16`, europe-west1 | Per hour | Per vCPU-hour |
  |---|---|---|
  | On-demand | $0.7998 | ≈ $0.050 |
  | Spot | $0.118 | ≈ $0.0074 |

  For comparison, us-central1 on-demand is $0.726.
- **Spot during the trial is not worth it.** The credit expires anyway and preemption costs wall-clock time. After the trial, Spot makes heavy runs about 7× cheaper.
- **Is the money binding?** At $0.80/h, running the VM 24/7 to 10-21 (about 456 h) would cost about $365. So the credit covers roughly 2/3 of the remaining wall-clock. **Dollars are not the constraint. Ready, honest jobs are.**

### 5.2 Throughput basis

- **Measured on the laptop:** one lab path (20 instruments × 14 years) through RSIM takes D1 11 s and BREAKOUT80 22 s.
- **The memory's ratio:** the server is about 8× faster than the laptop at whole-job level (1.3 h against 10.5 h), with 16 against about 3 workers, which implies about 1.5–3× per core.
- **Planning figure:** I use **about 6 s per member-run per vCPU** on the server.
- **How to check it:** read `elapsed_s` from `gs://acis-compute-0929-data/runs/2026-10-01-r1-lab-{rsim,stage-a}/summary.json`. The stage-A runner does 64 member-runs per seed.

### 5.3 Ranked jobs (decision value per dollar)

| Rank | Job | Prerequisite | vCPU-h | $ (on-demand) | Decision it unlocks |
|---|---|---|---|---|---|
| 1 | **J9: the P&L-blind admission run of the cost filters** (spreads and vol) on the real candles, plus the instruments' return covariance for N_eff and the IDM | Code exists (GAP-P12D-136 item; `cost_filters.py`) | ~1–5 | **< $1** | Finishes R1.3. Gives real ρ̄ for every power number. P&L-blind; whether covariance counts as a look is for the owner to confirm. |
| 2 | **J1: stage-A operating characteristics across R1-D9 × R1-D14.** Swap world {FTMO markup, swap-free} × {$6k/10%, $10k/10%, $10k/20%, $25k/10%} × effects {null, 0.3, 0.5, 0.8}; D1 + benchmark + 2× at n = 2,000; kill-only conditions at n = 500 | `r1_lab_stage_a.py` plus a world/size flag (RSIM already has three financing worlds and the one-lot rule) | ~650 | **~$33** (range $20–60) | Whether the first look is worth its α. Which world and size to register. P(pass) with lot rounding (GAP-P12D-101), not the analytic proxy of §3.1. |
| 3 | **J2: the R1.4 verdict chain end-to-end on the lab** at B0's n ≥ 2,000 (null + planted). Includes α-spending per look, the order row, the fallback or weighted-Holm alternative of §3.6 on the actual candidate set, the raw stage C at t < −0.5, and the per-account re-grade | R1.4 fixed path built | ~200 | **~$10** | B0 for the real verdict function. The cycle-1 design ruling (§4.2 items 2–3). |
| 4 | **J4: forward machinery operating characteristics.** E1/E2/E3 and the tripwires under t(4), GARCH and min-lot discretisation at the demo's real size. Single λ and group-sequential alternatives. Portfolio-level E1 for k sleeves. | Numpy only (Appendix A is the seed) | ~5–20 | **< $2** | The stage-D design ruling. What "E2 silent ≥ 3 months" certifies (GAP-P12D-110 says little). |
| 5 | **J3: B0(d), RSIM ≡ engine on lab tapes**, trade by trade (paired, so about 32–64 paths suffice), plus a stage-B dry run on the lab | R1.6 parity built | ~400–900 | **~$25–45** | Unblocks every real-data verdict under B0(d), and stage B. **Timing risk:** if R1.6 is not ready by about 10-18, run it after the trial on Spot (about 7× cheaper). |
| 6 | **J5: lab B0 for the 2–3 next sleeves** EDGE recommends (the intraday lab C-4 `lab_intraday.py` for window sleeves; event/flow labs as needed) | Their rule code, ≤ 3 literature-fixed parameters | ~60–250 each | **$3–12 each** | Whether they can join cycle 1 instead of cycle 2 a quarter later at α 0.01 |
| 7 | **J6: mutation gate on the new grader modules** (`stage_a`, `hac`, `evaluate`, `look_claims`, `rsim`, the verdict module) | R1.4 built | ~100–200 (mutmut 2 is single-process; run it beside other jobs) | **$5–10** | Grader correctness, the GAP-P12D-37 class. Doubles as audit evidence. |
| 8 | **J10: download pre-2012 Dukascopy hourly candles** (2003–2011, instruments that exist) on acis-compute-1 (inbound is free) **plus an exploration-tier kill screen** for the candidate sleeves | Owner OK (real data, tier 1, kill-only, register lines) | ~5–20 | **$1–5** | P4: order or drop candidates on independent data before they consume cycle α |
| 9 | **J7: explored-family machinery** (stationary-bootstrap max-t, PBO with S = 16, Masters permutation): FPR and power at this record length | R1.4's 119/120 built | ~150–400 | **$8–20** | Whether explored families are worth building at all. VALIDATOR measured CPCV + PBO power at 25% / 87% for SR 0.44 / 0.94. |
| 10 | **J8: prop-rule Monte Carlo grids** (SIZING's design) | SIZING's spec | ~20–100 | **$1–5** | SIZING's lane; budgeted here only |
| — | **Do not buy:** re-runs of the legacy cost ladder or `falsify_engine` (verdict known, engine being retired); any real-data parameter sweep; any look not registered | — | — | $0 | — |

- **Planned total:** about **$90–170**.
- **Reserve:** about $20 for acis-demo-1 to the 10-15..17 cutover and about $10 for disks and the bucket.
- **The remainder:** about $60–140, best left for larger-n re-runs (n = 10,000 for tighter B0 bounds) or for J3 if R1.6 lands early. **Burning the remainder on real-data search would be worse than leaving it unused.**

**Strongest counter-argument to this plan.** It spends little of the credit, and "use it or lose it" argues for buying *something*. My answer: the unspent credit is not lost value, because the only remaining buyable goods are (a) more synthetic precision, which has diminishing returns, and (b) more searches of the one history, which have negative value. If the owner wants the credit fully used, the next best buy is J3 and J5 at larger n, not real-data work.

### 5.4 After 10-21 (decide before then)

- **The work that follows needs compute:** stage B (engine on hourly bars), stage C, the e-process monitoring and later cycles.
- **Option 1, upgrade:** before 10-21, upgrade to a paid account and run Spot `c2d-standard-16` at about $0.12/h (b), about $3 a day if run continuously. Upgrading also avoids the deletion of trial data.
- **Option 2, AWS:** move heavy runs to AWS (the free-plan credits; instance types are restricted (c), unverified here).
- **Option 3, the laptop:** this is ruled out by the owner (no heavy runs on the laptop).
- **This is an owner decision with a hard date.**

---

## 6. Proposed schedule to the first honest real-data verdict (task 4)

The dates assume the build pace observed on 2026-10-01 (R1.3's lab half plus the real-data source in about a day) and same-day owner answers. Every launch is the owner's.

| When (2026) | Lead / builder | Server (synthetic or P&L-blind) | Owner |
|---|---|---|---|
| 10-02..03 | Finish R1.3: the passive-benchmark arms, the provenance amendment path. **Freeze and register D1's family-version for forward** (P2a). | **J9** (< $1). **J1** starts (~$33, about 1–2 days unattended, auto-poweroff). | ASK: one two-lens audit pass for R1.3 + R1.4's fixed path (P6). Rule B0(d) sequencing (exec summary item 5). |
| 10-03..08 | R1.4 fixed-family path (104, 111, 100, 112, 114, 86). **R1.6 parity in parallel** (P1; an owner-authorised builder in a worktree, or interleaved). The RSIM shadow-forward ledger (P2b). | **J4** (< $2). **J5** as soon as EDGE's sleeves have rule code. **J10** if OK'd. | Decide the post-trial compute home (§5.4). |
| 10-08..10 | Audit-pass triage. | **J2** (~$10), **J6** (~$5–10). | Launch the audit pass (owner). |
| 10-10..12 | Close the audit findings; push the anchor. | J1/J2 results are in. | **R1-D9 + R1-D14 with J1's numbers**; register the cycle-1 order and α design (§4.2); `REAL_LOOKS_OPEN` (fixed families). |
| **10-12..14** | **FIRST REAL-DATA LOOK: stage A on D1** (21 explored non-energy instruments, 2012–2023). Minutes of compute. **The first honest verdict: kill or survive.** | — | — |
| 10-15..17 | The AWS demo cutover (owner-fixed window). | — | — |
| 10-17..20 | If R1.6 is ready: **J3** (B0(d) + stage-B dry run). D1 to the demo at one minimum lot (P2c). | J3 (~$25–45) | Move or keep the bucket data before 10-21. |
| 10-21 | The trial ends. | — | — |
| Late Oct–Nov | Stage B (engine on real hourly bars), per-account re-grade, stage C (held-out + 2024–25 holdout, once). | Post-trial compute | **Rung 1 (`passed`) at the earliest mid-to-late November.** |
| Late Jan 2027 | Three months of practice record (live = replay, E3, E2 silent). | — | **Rung 2 sign-off at the earliest**, if D1 survived and traded from late October. |

**Critical paths:**
- **To the first verdict:** R1.4 fixed path → the two-lens audit → owner D9/D14 and order registration → stage A. If B0(d) binds before stage A, R1.6 + J3 joins this path and the first verdict moves to about 10-20, or November.
- **To "challenge-eligible" (rung 2):** R1.6 → D1 trading at minimum size in practice → three calendar months. **This path is the long one. It starts only when R1.6 lands**, which is why P1 matters more than any compute job.
- **To "edge shown forward" (rung 3):** years for any single sleeve below SR 1.5 (§3.5). Only portfolio breadth shortens it.

---

## 7. Owner decisions and ledger items this report raises (proposed; no IDs)

1. **B0(d) sequencing** [owner]. Does "RSIM ≡ engine on lab tapes" bind before stage A, or from stage B? Today it silently puts R1.6 on the path to the first look.
2. **The cycle-1 α design** [spec]. Options: keep the fixed sequence, adopt weighted Holm or a Bretz graph, or adopt an online fallback with α recycling. Same lifetime FWER; 1.6–2.8× the expected true discoveries when the first family is uncertain (§3.6).
3. **Correct GAP-P12D-102's power figures** [ledger]. They were at α = 0.05. At the ratified 0.03 they are 0.20 / 0.48 / 0.76 swap-free, and about 0.05 mid-range at FTMO's swaps.
4. **Do not spend cycle 1 on a near-certain fail** [owner, at the first look]. This ties R1-D9 (swap world) to the order.
5. **Forward clock** [impl + owner]. Register D1 frozen now. Build an RSIM tier-4 shadow-forward ledger. The owner rules whether an RSIM paper-forward record may feed E1/E2; E3 needs fills.
6. **R1.6 in parallel with R1.4** [owner]. Authorise a builder agent, or accept the interleaving cost.
7. **The post-trial compute home before 10-21** [owner]. Covers the deletion risk to the bucket data.
8. **A read-only quota check** before any larger VM [impl].
9. **The E1 design** [spec, low]. A single pre-registered λ or a group-sequential test on the portfolio series; and portfolio-level forward certification under GAP-P12D-100.
10. **Batch the R1.3 and R1.4-fixed audits** into one two-lens pass [owner; Track A precedent].

---

## 8. What I could not verify

- **The project's actual CPU quotas** (regional and all-regions). The trial page names no cap; forum reports of 8 or 24 vCPU are (c).
- **Whether Spot VMs run on a trial account.** The trial page names no ban. Unverified.
- **Google's own C2D price table** would not render through the fetcher. Both prices come from two third-party calculators that agree (b).
- **The server's per-member RSIM speed.** It is inferred from a laptop timing and the memory's whole-job ratio. Read `elapsed_s` from the bucket.
- **Suhonen, Lennkh & Perez 2017 and Armitage et al. 1969** figures are via secondary summaries ((a) papers, (b) quotes).
- **Tian & Ramdas's journal of record:** the arXiv text is verified; the venue is from memory (c).
- **Dukascopy's pre-2012 coverage per instrument.** About 2003 for the majors, per archive DATA_VENUE_ARCHITECTURE (b/c); indices and metals are unknown.
- **The power figures for each sleeve type** use assumed Sharpe ranges. EDGE's report owns the sleeve-specific estimates.
- **No real data was read.** Every number here is analytic or synthetic.

## 9. Residual risk

- **My D1 inputs are PLAN_R1's estimates.** If D1's true net Sharpe is outside them, the P(pass) table moves with it. J1 replaces the proxy with lot-rounded lab numbers, but the lab cannot tell the true Sharpe.
- **The online-fallback recommendation trades D1's power for breadth.** If D1 is in fact the best family, cycle 1 under weighted Holm detects it about 4 points less often (0.177 against 0.217).
- **P2's shadow-forward record is RSIM, not the engine.** If RSIM and the engine diverge, the e-processes measure the wrong book until J3 and stage B reconcile them.
- **Pace pressure is the standing risk to every gate here.** "Faster" is honest only while every look is registered first and every forward claim waits for its clock.

---

## Sources

| Source | Grade | URL | What it supports |
|---|---|---|---|
| Google Cloud, "Free Trial" features and limits, last updated 2026-09-24 | (a) | https://docs.cloud.google.com/free/docs/free-cloud-features | No GPUs, no quota increases, the 90-day credit, stop/delete at the end, the 30-day grace |
| devzero, c2d-standard-16 instance page | (b) | https://www.devzero.io/instances/gcp/c2d-standard-16 | europe-west1 on-demand $0.800/h, Spot $0.118/h |
| Holori calculator, c2d-standard-16 europe-west1 | (b) | https://calculator.holori.com/gcp/vm/c2d-standard-16/europe-west1?os=Linux | $0.7998/h; Spot $0.1180/h |
| Lo, A. (2002), "The Statistics of Sharpe Ratios", *FAJ* 58(4) | (a) | https://ideas.repec.org/a/taf/ufajxx/v58y2002i4p36-52.html | Serial correlation; overstated by up to 65% |
| Bailey & López de Prado (2012), "The Sharpe ratio efficient frontier", *J. Risk* 15(2) | (a) | https://ideas.repec.org/a/rsk/journ4/2223785.html | PSR, minimum track-record length |
| McLean & Pontiff (2016), *JF* 71(1) | (a) | https://www.gwern.net/doc/economics/2016-mclean.pdf | 26% lower OOS, 58% lower after publication |
| Falck, Rej & Thesmar (2022), "When do systematic strategies decay?", *QF* 22(11) | (a) | https://dspace.mit.edu/handle/1721.1/163650 | About 50% of in-sample performance OOS |
| Hou, Xue & Zhang (2020), "Replicating Anomalies", *RFS* 33(5) | (a) | https://www.nber.org/papers/23394 | 65% fail 1.96; 82% fail 2.78 |
| Suhonen, Lennkh & Perez (2017), *JPM* | (a) via (b) | https://alphaarchitect.com/?p=36892 | Median Sharpe 1.20 → 0.31 live, a 73% haircut |
| Harvey, Liu & Zhu (2016), *RFS*; Harvey (2017) *JF* | (a) | via archive EDGE_FACTORY §10 (NBER w20592) | t > 3 for discoveries |
| Bailey, Borwein, López de Prado & Zhu (2014), MinBTL | (a) | via archive EDGE_FACTORY §10 | Overfitting rises with trials |
| Grinold (1989), fundamental law, *JPM* | (a) | standard reference | IR ≈ IC·√breadth |
| Wald (1945), SPRT, *Ann. Math. Stat.* | (a) | standard reference | Expected sample sizes (my derivation) |
| Armitage, McPherson & Rowe (1969), *JRSS A* 132 | (a) via (b) | https://www.jameslindlibrary.org/?p=22624 | 10 looks at 5% give about 19% |
| Lan & DeMets (1983), *Biometrika* 70(3); O'Brien & Fleming (1979), *Biometrics* 35 | (a) | standard references | The spending function used in `gsd.py` |
| Ramdas, Grünwald, Vovk & Shafer (2023), "Game-theoretic statistics and SAVI", *Stat. Sci.* 38(4) | (a) | https://projecteuclid.org/journals/statistical-science/volume-38/issue-4/Game-Theoretic-Statistics-and-Safe-Anytime-Valid-Inference/10.1214/23-STS894.full | E-processes valid at all stopping times |
| Johari, Koomen, Pekelis & Walsh (2022), "Always valid inference", *OR* 70(3) | (a) | https://ideas.repec.org/a/inm/oropre/v70y2022i3p1806-1821.html | Continuous monitoring trades sample size for power |
| Wiens (2003), fixed-sequence Bonferroni, *Pharm. Stat.* 2(3) | (a) | (bibliographic, via search) | The fallback procedure |
| Bretz, Maurer, Brannath & Posch (2009), *Stat. Med.* 28(4) | (a) | https://pmc.ncbi.nlm.nih.gov/articles/PMC3427907 (related) | Graphical α propagation |
| Tian & Ramdas, "Online control of the familywise error rate" | (b) arXiv; venue (c) | https://arxiv.org/pdf/1910.04900 | Online fallback valid under arbitrary dependence |
| Genovese, Roeder & Wasserman (2006), *Biometrika* 93(3) | (a) | standard reference | Weights from independent information keep error control |
| Cox (1975), data-splitting, *Biometrika* 62 | (a) | standard reference | Pilot-then-confirm on split data |
| Gao, Jiang & Yan, "Detecting Lookahead Bias in LLM Forecasts" (2025/26) | (b) | https://arxiv.org/abs/2512.23847 | Look-ahead propensity about 0 after the cutoff |
| "Summoning the Oracle to Slay It" (2026) | (b) | https://arxiv.org/abs/2605.24564 | In-sample LLM return corrections up to −67% |
| Lopez-Lira, Tang & Zhu (2025); Gençay (2026), arXiv 2608.27734 | (a/b); (b) | via archive VALIDATION_FIREWALL §6–7 | The LLM-memory law; a leaky oracle survives DSR/PBO |
| ACIS archive reports (EDGE_FACTORY, VALIDATION_FIREWALL, STATS_METHODOLOGY) | [sim]/(a) as graded there | `archive/` | Built on, not re-derived |

---

## Appendix A — reproduction (all [D]; the session scratchpad, reproduced here because the scratchpad is temporary)

**`power.py`** produces the §3.1–3.4 tables, stdlib only. For each power figure:
- years needed: `Y = vif*((z(1-a)+z(p))/sr)**2`;
- power on a record of Y years: `Phi(sr*sqrt(Y) - z(1-a))`;
- the pooling factor: `sqrt(N/(1+(N-1)*rho))`;
- the per-event effect needed: `d = (z(.97)+z(.8))/sqrt(n)`.

**`eproc.py` / `eproc2.py`** simulate the stage-D E1 bettor (seeds 20261001 and 11; 600–800 paths):

```python
LAM = [0.05, 0.1, 0.2, 0.4, 0.8]           # ACIS-09 C-BT-11 v2 step 7
x = max(r/(6*sigma), -1); logW_l += log(1 + lam_l*x); W = mean_l exp(logW_l); cross at W >= 20
r ~ N(SR/sqrt(252)*sigma, sigma) daily     # single-lambda variant: lam = 6*SR_claim/sqrt(252)
```

**`gsd.py`** is the group-sequential comparison (seed 7). It uses 12 quarterly looks over 3 years and the spending function α(t) = 2 − 2Φ(z_{α/2}/√t) with α = 0.05:
- boundaries are set by simulating 200,000 null paths;
- power and expected stopping time come from drift SR·√(years);
- it prints the null rejection rate (0.0500).

**`graph.py`** compares the testing designs (seed 3; 200,000 cycles; three families; correlation 0.2; Y = 10.85; α = 0.03):
- fixed sequence;
- equal-weight Holm;
- weighted Holm (0.6 / 0.2 / 0.2), the weighted-Bonferroni steps re-normalised over unrejected hypotheses.

The global-null FWER printed for each was 0.0294–0.0297.

**The laptop timing**, 2026-10-01, Python 3.11, laptop:

```
generate(LabSpec(seed=1, effect=Effect(trend_sharpe=1.0, trend_halflife=40.0)))   2.27 s
run_member(path, 'D1', cfg)          10.97 s   (daily shape 3640)
run_member(path, 'BREAKOUT80', cfg)  22.02 s
```
