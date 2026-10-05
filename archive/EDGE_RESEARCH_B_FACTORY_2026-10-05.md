# EDGE RESEARCH B — the edge factory: how ACIS keeps finding, validating and retiring edges (2026-10-05/06)

**Agent B, launched on the owner's explicit request (brief: `archive/EDGE_RESEARCH_BRIEF_2026-10-05.md`; ledger owner [[GAP-P12D-161]]).** Research, not an A3 audit. Every proposal here is **LLM-origin under §5.6**: history can only kill it, and credit comes only forward. Nothing below binds until the lead triages it and the owner rules.

## Executive summary (10 lines)

1. **Build order:** B1 the pooled forward book (equal risk over ALL admitted entries, composition fixed before its first exposure) → B2 the weekly report's "evidence weight" line (likelihood ratio + years-to-certify, beside the luck odds) → B3 report-only decay flags (per-entry CUSUM with its false-alarm rate printed; the tripwire's fat-tail void rate) → B4 the forward-entry admission card (ex-ante, P&L-blind: mechanism, publication-age prior, ≥ 3× cost at the DEMO's spreads, one variant per family, a slot budget with 5 of 20 reserved for human origin) → B5 E3, the cost bettor on real fills (specified in ACIS-09, not built: the only FAST guard) → B6 lab calibration as a condition of every book shape → B7 quarterly candidate batches of ≤ 3 cards, owner-launched → B8 the 2027-04 review written now as a KILL review with a decision table.
2. **Power-math headline (scripted, synthetic, `/opt/acis/edge-B/power_math.py`):** the forward record cannot certify a true Sharpe of 0.5 in any owner-relevant horizon: one entry needs ~25 years of forward data at 80% power with NO multiplicity, ~64 years under the tournament's capacity correction; E1 ≥ 400 takes ~48 years in expectation.
3. **Milestone D is near-uninformative, as the owner already ruled:** at 126 days a dead strategy passes 36%, a live-at-0.5 one 49%, a live-at-1.0 one 63%; the best of six dead entries shows a 6-month Sharpe of 1.8 on average. Six months at SR̂ = 0.5 moves the odds "alive at 0.5 vs dead" by a factor of 1.06.
4. **Only breadth shortens the clock.** Ten uncorrelated streams at 0.3 each make a 0.95 book (80% power in ~10 years at full α); six at 0.5 make 1.22 (~6 years). Per-stream quality at CFD costs is Agent A's question; the factory's output metric is *independent, cost-clearing streams*, not winners.
5. **Decay cannot be detected fast at this signal-to-noise by ANY method:** a CUSUM tuned to 7.5% false alarms per 2 years catches a 0.5 → 0 drop within a year 15% of the time, within 3 years 49%; stage D's E2 kills it within 3 years 1%. The fast guards are the tripwire, the cost bettor E3 and plumbing checks; the slow guard is the e-process. Build E3.
6. **Allocation:** equal risk wins. Thompson sampling over six streams (true S 0.5/0.3/0.3/0/0/−0.2, no costs) earns 0.22 against equal risk's 0.38; a trailing-Sharpe picker 0.35; posterior-mean shrinkage 0.38 = equal. DeMiguel et al. (2009) and Carver's equity-curve test say the same. Demotion-only adjustments; no return optimiser, no bandit, no regime weights.
7. **Automated generation:** every honest study rejects the miner (Allen & Karjalainen 1999; Gençay 2026: every LLM-discovered strategy fails certification against its own trial count; Chordia et al. 2020: hurdle t 3.4–3.8). The honest generator is a *card writer*, not a backtester: it proposes mechanisms with ex-ante numbers before any look, takes one kill look and one stage C, and spends a forward slot. Falck, Rej & Thesmar (2022): newer publications decay MORE (+5 pp a year), so prefer old, structural mechanisms.
8. **Stop doing:** reading "survived stage C" as a positive (it kills a dead strategy 31% of the time and a live-at-0.5 one 11%); LLM paper-mining passes for single-market intraday anomalies on CFDs (4 of 4 failed on fresh data, 2 cost-killed ex ante); any adaptive allocator; adding near-null survivors (FXVALUE 0.07) as separate entries without the admission card; treating the Dukascopy-simulated forward P&L as the demo's P&L (E3 is a different guard).
9. **Spec changes needed (marked [SPEC]):** the pooled book as PRIMARY endpoint at full α with the components gatekept behind it (ACIS-09 v1.14 P-1a); the admission card as the registry's entry condition; a CUSUM freeze as a §5.7 demotion trigger (report-only needs none).
10. **Honest negative:** at ~$6k on retail CFDs, with history Sharpes of 0.07–0.5 and three published effects that fell to ≤ 0 on 2024–25, a *certified* 0.5 by 2027-04 is unlikely; the 2027-04 review can honestly decide only "killed / not killed / spend on accepted luck odds". What changes it: more independent mechanisms, human-origin rules certifiable on history, or a cost structure that lifts per-stream Sharpe above 1.

---

## 0. Attestation and method

- **Model:** Fable 5.1 (`claude-fable-5-1`), run as a fresh-context subagent. My context held the brief, the project's `CLAUDE.md`, the memory index and the files I read in this session; no earlier research session's working memory.
- **Web:** 27 WebSearch calls (cap 70) and 6 WebFetch calls. The Eaton Vance/Morgan Stanley CUSUM PDF returned 403; the Winton PDF was saved by the fetch tool and text-extracted locally with `pypdf`.
- **Compute:** `acis-compute-1` (started by me; left RUNNING per the brief), directory `/opt/acis/edge-B/` only: `power_math.py` (numpy, 16-vCPU host, 130 s), outputs `power_math_out.txt` (run 2, cited below), `power_math_out_run1.txt`, `power_math_results.json`. Copies in this session's scratchpad `edge-B/`. **No real market data was read**; every simulation is iid normal or Student-t daily returns with a planted annual Sharpe. The HAC t and the stage-D mixture bettor reproduce `tests/backtest/hac.py` and `tests/backtest/tournament_rule.py` by reading them, not importing.
- **Repo:** nothing edited except this file. No commits. No subagents. `acis-demo-1`, AWS, `/opt/acis/repo` and `data/validation/looks` untouched.
- **Source grades:** (a) primary text read; (b) abstract/digest only; UNCONFIRMED where stated. Internal facts cite the file or ledger ID.

## 1. What exists today (verified in the repo), and the seams

| Piece | State | Seam |
|---|---|---|
| Forward record (`tests/backtest/forward_record.py`, `data/forward/record` 7 lines) | append-only, hash-chained, anchored on `forward-anchor`; six entries from 2026-10-05/06 with α_i = 0.0025 each | records a **simulated** daily net P&L from Dukascopy inputs (`tournament_books.py`), never a fill |
| Promotion rule (`tournament_rule.py`, v1.1) | screen (≥ 126 d, SR ≥ 0.5, no kill, no tripwire) + weighted Holm over capacity 20 at looks 126/252/504 (Bonferroni over looks) OR E1 ≥ 1/α_i = 400; E2 freeze 5 / kill 20; tripwires pinned (D1 5.49 → floor 6, REBAL 8.46, GOTOBI 9.60, HALLOWEEN 12.64, HEDGEP 9.52, FXVALUE 2.21 → floor 6) | correct and honest; see §3 for what it can and cannot do |
| Daily job and weekly report (`scripts/tournament_daily.py`, `tournament_report.py`, `deploy/forward/`) | fetch → record → recheck → anchor; the report prints luck odds and the Sharpe each look would need | no evidence-weight line; no decay flag |
| Stage D in the spec (ACIS-09 v1.14 C-BT-11 v2 step 7) | E1, E2, **E3 (cost, per fill)**, tripwires, multiplicity | **E3 is not built anywhere** (`grep E3` over the rule, record, reports: nothing); it needs `VENUE_COSTS` in the demo logs ([[GAP-P12D-160]], built) and a paired-fill reader |
| Demo shadow book (`scripts/demo_report.py`) | Carver's uncapped optimum, daily USD P&L, realised vol | separate from the forward record; the one place real fills exist |
| Look register (`look_register.py`, tiers, cycles, claims) | the attempt registry; kill-only looks spend no α; stage C once per variant; forward tier 4 from 2026-07-01 | nothing to add |
| Synthetic lab (`lab_market.py`, `rsim_lab.py`, `lab_intraday.py`) | planted/null calibration of RSIM books (B0) | event-book shapes (`close_book`, `window_book`) are not required to pass a lab calibration before a forward entry |
| §5.7 lifecycle (rungs, quarterly re-validation, graveyard with revival conditions, challenger lane, literature cadence) | specified | the cadence and intake format are not operationalised; `hypotheses/README.md` is the only intake and it is empty (owner plan 2026-10-04 item 3) |

Two facts that shape everything below: the six entries' development Sharpes are 0.165 (D1), 0.495 (REBAL), 1.81 (GOTOBI, −0.20 on 2024–25), 0.26 (HALLOWEEN), 0.14 (HEDGEP), 0.07 (FXVALUE) (`data/forward/record/000002..000007`, `archive/RESEARCH_FACTORY_2026-10-03.md`); and every one is LLM-selected, so only the forward tier can credit it.

## 2. Q1 — how systematic shops run research to retirement, and what transfers to a solo operator

**A primary record.** Cliffwater's 2011 investment due-diligence report on Winton (a public record on the Rhode Island treasury's open-data site, grade (a), dated: practice may have changed) describes the lifecycle of a $22bn CTA with 120+ markets: "After initial testing, researchers must compile a one page summary of their thesis to be submitted to the Trading System Committee for peer review … If the Trading System Committee cannot unanimously agree on a research proposal, it will not be implemented … Research projects that pass … are assigned to an independent group of peer reviewers. Assuming the model is approved, it will be subjected to stress testing and other quantitative analysis for a period up to 12 months. If a model successfully passes the stress testing, it will initially enter the portfolio with a very small risk allocation to ensure that the model performs as expected during 'live' trading. Eventually, the model's allocation will be permitted to grow … Every two years, each system is completely deconstructed to verify that the original assumptions still hold true … the risk allocated to a system may be reduced to zero if warranted." The committee "meets at least once a month." ([PDF](https://data.treasury.ri.gov/dataset/96dcb86f-e97e-4b05-8ce2-a40289e477a6/resource/3bc987e1-c783-4404-b2a4-909423393f24/download/winton-cliffwater-investment-due-diligence-reportredacted.pdf), pp. 2–5.)

What transfers: a one-page thesis before any build (ACIS: the hypothesis card, B4); independent review (ACIS: the A3 audit pair, already); a long stress/paper period (ACIS: kill looks + stage C + the forward record); **entry at a very small allocation** (ACIS: the one-lot demo, master §5.6 "minimum size"); growth gated on live results (ACIS: milestone D as a spending gate, never evidence); periodic deconstruction (ACIS: §5.7 quarterly re-validation and the three forward looks); allocation to zero (ACIS: demotion is risk-reducing and agent-executable). What does not transfer: a committee's unanimity and 120 markets. The solo operator's substitute for the committee is pre-registration (the look register) plus the owner's ruling; the substitute for 120 markets is breadth by *mechanism* (GAP-P12D-158's rule).

**What the numbers say about any shop's pipeline.**
- Backtest-to-live: across 215 bank "alternative beta" strategies the median Sharpe fell from 1.20 in backtest to 0.31 live, a 73% deterioration, worse for complex strategies (Suhonen, Lennkh & Perez, JPM Winter 2017; digest grade (b): [Alpha Architect](https://alphaarchitect.com/?p=36892)). Quantopian's cross-section: backtest Sharpe predicts out-of-sample Sharpe with R² < 0.025 (Wiecki et al. 2016, cited in `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` §5.6).
- Published anomalies "evaluated outside the data sample deliver about 50% of in-sample performance"; across 72 strategies "the year of publication alone explains 30% of the variance of Sharpe decay … every year, the Sharpe decay of newly-published factors increases by 5ppt"; overfitting proxies (operations to compute the signal, outlier sensitivity of the in-sample Sharpe) add 15%; arbitrage variables are significant but marginal (Falck, Rej & Thesmar, *Quantitative Finance* 22(11) 2022, 1955–1969, [abstract](https://dspace.mit.edu/handle/1721.1/163650), [CFM summary](https://cfm.com/why-and-how-systematic-strategies-decay/); grade (a) for the abstract). McLean & Pontiff (JF 2016): 26% lower out of sample, 58% lower post-publication ([[GAP-P12D-158]]).
- Pénasse (*Management Science* 68(5) 2022, 3966–3973, [RePEc](https://ideas.repec.org/a/inm/ormnsc/v68y2022i5p3966-3973.html), grade (b)): decay biases measured alpha by about 1.4%/year, and the repricing during decay produces *positive* realised returns that look like persistence. A fading edge looks healthy while it fades.

**Implication for the intake.** The publication-year effect is the strongest single predictor of decay, and it runs the "wrong" way for an LLM miner, which gravitates to recent papers. The factory should weight *old, structural, many-market* mechanisms (trend, carry, seasonality with a physical cause, forced rebalancing) over recent single-market anomalies, and should price the Falck prior into each card: expected net ≈ ½ × history, less for post-2010 publications. That is also the ex-ante arithmetic that correctly dropped GOLD-EW without a look and predicted FXHEDGE's 0.92 ([[GAP-P12D-158]]).

**What solo quants do that works** (Carver's published practice, consistent with the practitioner survey in [[GAP-P12D-148]] item 6): one slow system over many instruments, fixed literature parameters, equal "handcrafted" risk weights, no selection of rules on backtest Sharpe, no equity-curve overlays. His own test of "trading the equity curve" on 1,000 random curves: for systems with a positive Sharpe the overlay lowered return/drawdown; it hurt most with negative autocorrelation (trend) and helped only losing systems ([qoppac, 2015-11-10](https://qoppac.blogspot.com/2015/11/random-data-evaluating-trading-equity.html), grade (a)).

## 3. Q2 — honest discovery under many trials, and the forward power math

### 3.1 Which statistics apply where

| Tool | Where it binds in ACIS | Verdict |
|---|---|---|
| The look register as attempt registry (every look written first; kill-only looks spend no α; stage C once) | history | the right tool; keep |
| Deflated Sharpe (Bailey & López de Prado 2014, [SSRN 2460551](https://papers.ssrn.com/abstract=2460551)) | history, informational since C-BT-11 v2 (GAP-P12D-104) | keep informational; its E[max SR] formula is the right way to state the tournament's luck (§3.3) |
| PBO/CSCV | history, explored families | specified for explored families; fixed-rule families have no configuration matrix, so it is moot for the forward entries |
| FDR hurdles: Harvey & Liu (JF 75(5) 2020, double-bootstrap FDR hurdle, [RePEc](https://ideas.repec.org/a/bla/jfinan/v75y2020i5p2503-2553.html)); Chordia, Goyal & Saretto (RFS 33(5) 2020: t hurdles 3.84 time-series / 3.38 cross-section from two million random strategies; 45.3% false rejections if ignored, [SFI](https://www.sfi.ch/en/publications/anomalies-and-false-rejections)) | history, any discovery claim | the ACIS kill rule (t < −0.5) is a *falsification* hurdle, not a discovery hurdle; a discovery on history would need t ≈ 3.4–3.8, which only a human-origin family may attempt |
| Harvey & Liu "Backtesting" (JPM 2015, [PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)): the haircut depends on t and the trial count; "a 50% haircut is a serious mistake" as a flat rule | history | use the trial count from the register, not a flat half; the Falck/McLean–Pontiff half is a *decay* prior, a different thing, and both apply |
| Anytime-valid e-processes (Waudby-Smith & Ramdas, JRSS-B 2024, DOI 10.1093/jrsssb/qkad009, [arXiv 2010.09686](https://arxiv.org/abs/2010.09686v4)) | forward (stage D's E1/E2/E3) | the right forward tool: valid under daily peeking; its price is the growth rate (§3.2) |
| Weighted Holm over a fixed capacity, Bonferroni over three looks | forward | valid; the capacity-not-count design is correct; its price is a z of 3.14 at every look (§3.2) |
| Novy-Marx (NBER w21329, 2015, [NBER](https://www.nber.org/papers/w21329)): combining the best k of n in-sample-signed signals biases like selecting the best of nᵏ | the pooled book (§5 B1) | the pooled book's composition must be fixed by a rule that does NOT read performance, and before any forward data of the book exists |

### 3.2 The power table (scripted, `power_math.py` §1–3; iid daily, known σ, one-sided)

**Days (years) of forward data to reject S = 0, by the true annual Sharpe S:**

| true S | single test α 0.05: 50% / 80% power | tournament look α_i/3 = 0.00083: 50% / 80% | pooled book as PRIMARY, α 0.05/3: 50% / 80% |
|---|---|---|---|
| 0.25 | 43 y / 99 y | 158 y / 254 y | 73 y / 141 y |
| **0.50** | **10.8 y / 24.7 y** | **39.5 y / 63.5 y** | 18.1 y / 35.3 y |
| 0.75 | 4.8 y / 11.0 y | 17.6 y / 28.2 y | 8.1 y / 15.7 y |
| 1.00 | 2.7 y / 6.2 y | 9.9 y / 15.9 y | 4.5 y / 8.8 y |
| 1.50 | 1.2 y / 2.7 y | 4.4 y / 7.1 y | 2.0 y / 3.9 y |
| 2.00 | 0.7 y / 1.5 y | 2.5 y / 4.0 y | 1.1 y / 2.2 y |

Formula: n = ((z_α + z_power) / (S/√252))². Trade frequency enters only through the annual Sharpe: an event strategy with 62 active days a year and the same annual Sharpe needs the same calendar time (its per-event Sharpe is higher, its events fewer; Monte Carlo §2 of the script, shape `event62`, confirms the screen and look probabilities are identical to the daily shape, and E1 is *slower* because the mixture bettor earns less on lumpy returns: P(E1 ≥ 20 by 504 d) at S = 1.5 is 0.335 daily vs 0.069 event).

**The e-process route (E1 ≥ 400 = 1/α_i):** the mixture bettor's best log-growth per day is s_d²/2 with s_d = S/√252 (optimal λ = 6 s_d, inside the pinned grid for S ≤ 2): years to E1 ≥ 20 / ≥ 400 are 24 / 48 at S = 0.5, 6 / 12 at S = 1.0, 2.7 / 5.3 at S = 1.5. Monte Carlo (2,000 paths, 30 years): at S = 0.5, 80% of paths never reach 400 in 30 years. This reproduces ACIS-09's own "about two decades at 0.5" for the W ≥ 20 threshold.

**Monte Carlo of the rule as registered (4,000 paths, 504 days, normal daily):**

| true S | P(screen at 126 d) | P(screen at 252 d) | P(look p ≤ α_i/3 at 126/252/504 d) | P(E1 ≥ 400 by 504 d) | P(E2 kill by 504 d) |
|---|---|---|---|---|---|
| 0.00 | 0.36 | 0.32 | 0.001 / 0.001 / 0.001 | 0.000 | 0.017 |
| 0.50 | 0.49 | 0.50 | 0.004 / 0.005 / 0.007 | 0.002 | 0.005 |
| 1.00 | 0.63 | 0.69 | 0.013 / 0.018 / 0.043 | 0.009 | 0.001 |
| 1.50 | 0.76 | 0.84 | 0.029 / 0.067 / 0.175 | 0.049 | 0.001 |
| 2.00 | 0.86 | 0.94 | 0.059 / 0.143 / 0.397 | 0.161 | 0.000 |

Reading: within the three pre-registered looks, the rule as written certifies a true 0.5 with probability 0.7% (the null: 0.1%) and a true 1.5 with 17.5%. E2's kill of a dead strategy within two years is 1.7%, matching ACIS-09's "1–4% by year 1". **With Student-t(4) daily tails and σ* = the realised σ, the −6σ* tripwire voids 22–25% of two-year records regardless of S** (script §2, third block); the per-family pins at 1.5× the history worst day (REBAL 8.46, GOTOBI 9.60) lower that, but D1 (5.49) and FXVALUE (2.21) sit on the floor of 6. The tripwire's false-void rate should be stated per entry (B3), because a void is permanent.

### 3.3 Milestone D, and the evidence weight of a forward record

- **Best of N null strategies** (Bailey & López de Prado's E[max SR] = σ_SR·((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))), σ_SR = √(252/n); Monte Carlo 20,000 draws agrees to 0.03): at 126 days the best of 6 dead entries shows SR̂ = 1.84 on average and passes the 0.5 screen with probability 0.93; the best of 20 shows 2.69. At 504 days: 0.92 and 1.34. The record's `luck_any` already says this; the report should also print the expected best-of-N Sharpe so that a 1.5 after six months reads as "average for the best of six".
- **Likelihood ratio of "alive at S = 0.5" against "dead"**, from an observed forward SR̂ over n days with known σ: LR = exp((n/252)(0.5·SR̂ − 0.125)). Posterior from a prior of 0.5 (the McLean–Pontiff survival rate):

| months | SR̂ = 0.0 | SR̂ = 0.5 | SR̂ = 1.0 | SR̂ = 1.5 |
|---|---|---|---|---|
| 6 | 0.94 → 0.48 | **1.06 → 0.52** | 1.21 → 0.55 | 1.37 → 0.58 |
| 12 | 0.88 → 0.47 | 1.13 → 0.53 | 1.45 → 0.59 | 1.87 → 0.65 |
| 24 | 0.78 → 0.44 | 1.28 → 0.56 | 2.12 → 0.68 | 3.49 → 0.78 |
| 36 | 0.69 → 0.41 | 1.45 → 0.59 | 3.08 → 0.75 | 6.52 → 0.87 |
| 60 | 0.54 → 0.35 | 1.87 → 0.65 | 6.52 → 0.87 | 22.8 → 0.96 |

Six months at exactly the milestone-D threshold moves the owner's odds from 50:50 to 52:48. This is the number to print beside the spending gate: it is what "never evidence" means in arithmetic, and it is the honest input to the paid-challenge EV table in [[GAP-P12D-148]] (P(pass) 0.27 / 0.43 / 0.62 at S = 0 / 0.5 / 1.0).

### 3.4 What a portfolio of forward candidates changes (script §5)

Equal-risk pooling of N streams with per-stream S and pairwise ρ gives S_pool = S·N/√(N + N(N−1)ρ):

| N | ρ | S each | S_pool | years to 80% power, pooled as PRIMARY (α 0.05/3) | as one of the capacity (α_i/3) |
|---|---|---|---|---|---|
| 3 | 0 | 0.3 | 0.52 | 33 | 59 |
| 6 | 0 | 0.3 | 0.73 | 16 | 29 |
| 10 | 0 | 0.3 | 0.95 | 10 | 18 |
| 6 | 0.1 | 0.3 | 0.60 | 25 | 44 |
| 6 | 0 | 0.5 | 1.22 | 5.9 | 10.6 |
| 10 | 0 | 0.5 | 1.58 | 3.5 | 6.4 |
| 6 | 0.25 | 0.5 | 0.82 | 13 | 24 |

Three lessons. (i) Breadth is the only lever on the clock that the factory controls; correlation is its enemy (ρ = 0.25 halves the gain of six streams). (ii) Testing the pooled book as one entry among twenty throws away half the power; it should be the PRIMARY endpoint [SPEC]. (iii) Even then, a book of six honest 0.5 streams needs ~6 years at 80% power. The forward record is a kill-and-spend machine with a slow certification tail, not a certification machine: design the factory for that.

### 3.5 Stage C's power (script §8, analytic)

On a two-year holdout with the kill rule t < −0.5 and t ~ N(S√2, 1): P(kill) = 0.82 / 0.58 / 0.31 / 0.11 / 0.03 at S = −1.0 / −0.5 / 0 / 0.5 / 1.0, and P(t > 0, "looks alive") = 0.50 at S = 0. Stage C is a weak kill screen and no evidence at all; "not killed" is to be read exactly as the ledger reads it now. (GOTOBI's 1.81 → −0.20 was a kill of the *expectation*, not of the rule: the rule was powerless there too.)

## 4. Q3 — adaptive allocation and decay detection

### 4.1 Allocation: what works out of sample

- DeMiguel, Garlappi & Uppal (RFS 22(5) 2009, 1915–1953, [RePEc](https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html), grade (b)): none of 14 optimising models consistently beats 1/N out of sample; mean-variance needs ~3,000 months of data to win with 25 assets. Harvey & Liu (RFS 31(7) 2018, "Detecting repeatable performance", [Duke](https://scholars.duke.edu/publication/1112843), grade (b)): shrinking each fund's alpha toward the cross-section improves out-of-sample alpha forecasts; that is a *reporting* improvement, not an allocation edge, and ACIS's six streams are too few for a cross-section.
- Thompson sampling over strategies has a literature ("Portfolio blending via Thompson sampling", [IJCAI 2016](https://www.ijcai.org/Abstract/16/283), grade (b)) but no out-of-sample evidence I could find at our signal-to-noise. Regime-conditional weighting: the evidence is mixed at best (e.g. Nystrup et al., DTU, [abstract](https://www2.imm.dtu.dk/pubdb/pubs/6808-full.html), grade (b): lower volatility, no higher return than static). Online portfolio selection (universal portfolios; survey Li & Hoi, [arXiv 1212.2129](https://arxiv.org/pdf/1212.2129), grade (b)) rebalances every period and is eaten by costs.
- **My horse race (script §7; 1,500 five-year paths; six uncorrelated streams with true S = 0.5, 0.3, 0.3, 0, 0, −0.2; daily rebalance; NO costs, which favours the adaptive rules):** equal risk 0.38 (theory 0.37); Thompson sampling 0.22; a 1-year trailing-Sharpe top-3 picker 0.35; posterior-mean-positive weights 0.38; an oracle that knows the three positive streams 0.65. The posterior barely moves in five years (§3.3), so every adaptive rule is allocating on noise, and the one that concentrates (Thompson) pays the diversification it gives up.

**Verdict:** ACIS's existing design (fixed equal-risk weights, vol targeting, a per-family cap, adjustments only by demotion: freeze → reduce → retire) is what the evidence supports. Do not build a bandit, an equity-curve filter or a regime weighter. Any regime conditioning stays a registered family-version (master §5, v2.22), as the spec already says.

### 4.2 Decay detection: how fast anything can see it

CUSUM is the optimal sequential detector for a given false-alarm rate (Page 1954; Philips, Yashchin & Stein, JPM Fall 2003, 86–94: it "can be used to detect flat-to-the-benchmark performance in 40 months, and to detect underperformance faster still"; Morgan Stanley PSG builds its manager-monitoring on it, [IBM record](https://researcher.ibm.com/publications/using-statistical-process-control-to-monitor-active-managers), [MS article](https://www.morganstanley.com/im/en-us/capital-seeker/about-us/news-and-insights/articles/when-good-managers-stumble.html); grade (b)). Their 40 months is for a manager with a monthly information ratio well above ours.

**Script §6:** a stream true at S = 0.5 for two years then falling to S_after; one-sided CUSUM on daily returns with reference k = half the healthy daily mean (the same claim convention as E2), threshold h calibrated on healthy streams:

| calibration | S_after | CUSUM P(detect ≤ 1 y / 2 y / 3 y) | E2 freeze P(≤ 1 y / 3 y) | E2 kill P(≤ 1 y / 3 y) |
|---|---|---|---|---|
| h = 57.5: 9.1% false alarms per 5 y | 0.0 | 0.04 / 0.13 / 0.24 | 0.01 / 0.03 | 0.00 / 0.01 |
| | −0.5 | 0.09 / 0.29 / 0.51 | 0.02 / 0.10 | 0.00 / 0.03 |
| | −1.0 | 0.14 / 0.52 / 0.79 | 0.04 / 0.25 | 0.01 / 0.10 |
| h = 40: 7.5% false alarms per 2 y | 0.0 | 0.15 / 0.34 / 0.49 | 0.01 / 0.03 | 0.00 / 0.01 |
| | −0.5 | 0.25 / 0.55 / 0.71 | 0.02 / 0.10 | 0.00 / 0.03 |
| | −1.0 | 0.38 / 0.74 / 0.86 | 0.04 / 0.25 | 0.01 / 0.10 |

Reading: a strategy that quietly dies (0.5 → 0) is invisible to everything for a year and to E2 for years; the CUSUM is 3–10× faster than E2 at the same claim but still slow, and with six entries a 7.5%-per-2-years false alarm means roughly a 37% chance that *some* healthy entry flags within two years. So: (i) a CUSUM flag is **report-only**, printed with its own false-alarm rate like the luck odds; (ii) a freeze on a flag is a demotion (risk-reducing) and could be allowed under §5.7 [SPEC], but on a one-lot demo there is nothing to reduce, so defer; (iii) the kills that can be fast are the ones with per-fill or per-day evidence of a *different kind*: the tripwire (one day), **E3 on paired fills** (a cost-model breach shows in weeks because every fill is an observation against a ±25% band), and plumbing checks (live vs replay decisions identical, ACIS-09 step 7). E3 is specified and unbuilt: it is the highest-value piece of decay machinery ACIS does not have, and it is also the operational-referent audit's evidence (CLAUDE.md guard 3).

## 5. Q4 — automated hypothesis generation, and the LLM's honest role under §5.6

**The evidence on miners.** Genetic programming on the S&P 500 (1928–95): "after transaction costs, the rules do not earn consistent excess returns over a simple buy-and-hold strategy in the out-of-sample test periods" (Allen & Karjalainen, JFE 51 (1999) 245–271, [PDF](https://www.cs.montana.edu/courses/spring2007/536/materials/Lopez/genetic.pdf), grade (a)). GP on six exchange rates 1981–95 found out-of-sample excess returns (Neely, Weller & Dittmar, JFQA 32(4) 1997, [RePEc](https://ideas.repec.org/a/cup/jfinqa/v32y1997i04p405-426_00.html), grade (b)), and the later literature finds those FX technical profits gone by the early 1990s ([J. Int. Fin. Markets 21(2) 2011](https://ideas.repec.org/a/eee/intfin/v21y2011i2p176-206.html), grade (b)): the miner found a real 1980s effect and its own publication-era decay. LLM miners: with leakage-safe point-in-time tools and search-aware deflation built into the system, "every LLM-discovered strategy in the suite, across two universes, two frontier models, cost regimes, search budgets up to one hundred candidates, and five repeated runs, including discoveries that were genuinely profitable out of sample, fails certification against the agent's own recorded trial count", while passive benchmarks certify (Gençay 2026, [arXiv 2608.27734](https://arxiv.org/pdf/2608.27734), grade (b) via abstract); "The Alpha Illusion" ([arXiv 2605.16895](https://www.alphaxiv.org/abs/2605.16895), 2026-05, grade (b)) sets six validity tests (temporal integrity, frictions, counterfactual robustness, calibration, numerical execution, multi-agent disaggregation) and recommends "LLMs as auditable information interfaces upstream of independent calibration, risk, and execution modules", which is ACIS's §0 boundary stated by someone else. López de Prado's first failure mode is using the backtest as a discovery tool rather than a research tool ([JPM 2018 / GARP](https://www.garp.org/white-paper/the-10-reasons-most-machine-learning-funds-fail), grade (b)). Harvey's presidential address: over half of claimed findings are likely false (JF 72(4) 2017, grade (b)).

**ACIS's own record is the same evidence:** fifteen LLM-selected families, four survived to 2024–25 and none earned there, two were cost-killed ex ante. The miner is not the bottleneck; honest evidence is, and the miner cannot make evidence.

**So what is an honest generator?** One that produces *forward-certifiable candidates cheaply* rather than mined history. Its properties, all already latent in ACIS:
1. **It writes cards, not backtests.** A card (B4) is a declarative plan under §5.6 R1-D13 (rule id, ≤ 3 literature-fixed parameters, universe id) plus ex-ante, P&L-blind arithmetic: the forced counterparty; the publication year and the Falck decay prior; the expected gross per trade from the source against the C8 round trip **at the demo's own observed spreads** (not Dukascopy's: GOTOBI's book idealises this, [[GAP-P12D-158]]); the expected correlation with the live entries; the clock (daily RSIM certifiable; intraday kill-only); the failure motif check against the graveyard. GOLD-EW was dropped by exactly this arithmetic with no look spent; that is the generator working.
2. **It spends looks by a fixed budget:** one kill look on 2012–2023, one stage C, then a forward slot or the graveyard. No exit-time, threshold or instrument variants after a look (GOTOBI v1c and FXHEDGE v1d were pre-ruled; keep that discipline).
3. **It is calibrated on the lab before it binds:** each book shape (RSIM, close, window) must detect a planted effect and not the null, and refuse a leaky oracle, before its first forward entry (B6). Gençay's "a leaky oracle with Sharpe 35 survives DSR and PBO completely" is the reason.
4. **The LLM proposes before any look and never after seeing one.** A proposal after a look is a search step and counts as a trial (the 09-24 report's rule; it stands).
5. **Its base rate is managed, not its volume:** ≤ 3 cards a quarter, ranked by GAP-P12D-158's rule (forced flow or a century-old premium; survival after publication; old publications first), with the human route (`hypotheses/`) always ahead of the queue because it is the only route history can certify.

## 6. Q5 — the architecture, in build order (extends what exists; nothing replaced)

| # | Build | Extends | Cost to build | Running cost | [SPEC]? |
|---|---|---|---|---|---|
| **B1** | **The pooled forward book**, two entries: `POOL-ALL` = equal risk (each component scaled by its declared σ*) over every admitted entry, composition fixed by rule with no performance read; and the owner's plan-2 book (D1 + REBAL + GOTOBI, ± HALLOWEEN/HEDGEP as the owner rules). A `pooled_book` shape in `tournament_books.py` reading the components' recorded `days` rows; settled = the latest common settled day; σ* = the realised daily sd of the equal-risk combination of the development vectors (P-3's convention); `sharpe_dev` = that combination's; tripwire pinned from the combination's worst history day. Registered BEFORE its first exposure, which the record enforces. Later admissions create a NEW pooled version (never a re-composition). | registry, books, record | ~half a day | none | **yes, if PRIMARY:** ACIS-09 v1.14 P-1a amended to a fixed-sequence (gatekeeping) design: the pooled book tests at α 0.05 (Bonferroni over its three looks); the components keep α_i only if the primary rejects. FWER stays ≤ 0.05 (fixed-sequence testing); it reallocates α, it does not loosen the error rate. Without the ruling, register it at α_i like any entry (no spec change, half the power). |
| B2 | **The evidence-weight line** in `tournament_report.py`: per entry and for the pool, LR("alive at the entry's half-history Sharpe" vs dead), the posterior from a stated prior, the expected best-of-N null Sharpe at this n, and "years to certify at the current estimate". Computes, never decides. | report | ~2 h | none | no |
| B3 | **Decay flags, report-only:** per entry a one-sided CUSUM at k = half the E2 claim with h calibrated on the lab to a stated false-alarm rate (10% per 2 years), printed WITH that rate; the tripwire's expected false-void rate per entry from a fat-tailed lab null at its pinned k. | report, lab | ~half a day | minutes a quarter on the lab | no (a freeze on a flag would be a §5.7 demotion trigger: [SPEC], defer) |
| B4 | **The admission card** as the registry's entry condition: the fields in §5 item 1, a cost ratio ≥ 3 at the demo's spreads, one variant per family in the record, |expected ρ| ≤ 0.3 with every live entry, a slot budget (capacity 20: 5 reserved for human origin, ≤ 3 new LLM-selected entries a quarter), the graveyard motif check. The card is the `entry` line's `params` plus a `card` block, hashed into `spec_hash`. | registry, record | ~1 day | none | **yes**: ACIS-09 stage D's entry conditions |
| B5 | **E3, the cost bettor on real fills** (ACIS-09 step 7, unbuilt): paired realised − modelled cost per fill from the demo's `VENUE_COSTS` logs, in modelled-cost units against the ±25% band, W ≥ 20 breach, plus the 5-modelled-costs tripwire; written to the operational ledger. After the cutover, as soon as fills exist. | demo logs, record | ~1 day | none | no (already specified) |
| B6 | **Lab calibration as a condition of every book shape:** `close_book` and `window_book` get the RSIM B0 treatment (planted detected, null not, leaky oracle refused) before any further forward entry of that shape; a registry test pins it. | lab, registry | ~1 day | minutes | no |
| B7 | **Quarterly candidate batches:** ≤ 3 cards, owner-launched (CLAUDE.md 2026-09-25), the lead judges each card ex ante, each gets one kill look + one stage C, admitted ones enter the record at the next quarter boundary (so first-exposure timestamps are clean). The §5.7 literature cadence runs at this rhythm, not monthly. | process | none | one agent session a quarter | no |
| B8 | **The 2027-04 review, written now:** a decision table the review only fills in: any entry killed / voided / E3-breached → retire; pool LR < 0.7 → recommend stop; pool screen passed → the owner's luck-odds acceptance or not; nothing certifies. | TODO | ~1 h | none | no |

**Owner minutes a month (estimate):** the Monday report, 5 min × 4; a monthly glance at flags, 15 min; a quarterly batch ruling, 30–60 min → about 45–60 min a month, and the 2027-04 review 1–2 h. **Compute:** the AWS data server's daily oneshot (minutes a day on a stopped-by-default instance plus S3; dollars a month, UNCONFIRMED: instance type not in the files I read); lab calibrations on `acis-compute-1` or, after the credits end 2026-10-21, on any small VM (they run in minutes); nothing continuous. This is the owner's low-cost autopilot: after B1–B5 the factory runs itself and asks for a human only at a flag, a batch or the review.

**What to stop doing (restated with the evidence):** (1) stage C survival as a positive: P(kill | S = 0) = 0.31; (2) LLM paper-mining passes for single-market intraday anomalies on CFDs: 4/4 failed fresh data, 2/2 cost-killed, and newer papers decay faster; (3) adaptive allocators: §4.1; (4) separate forward entries for near-null survivors without a card (FXVALUE's 0.07 adds variance to the pool and nothing else; FACTORY itself said "the lead may decline it"); (5) reading the record's simulated P&L as the demo's: the fill side is E3; (6) any ad-hoc look at the stored forward series between the pre-registered looks as if it were a test (peeking earns nothing by design, but it costs attention).

## 7. Attacking my own proposal

1. **"The pooled book as primary is Novy-Marx's trap."** Its components survived a selection on 2012–2023 (15 families → 6), so their *history* is biased upward; the forward record is not, provided the composition is fixed before the pool's first exposure and never re-composed on forward results. The remaining risk is that a weak component drags the pool: that is the price of refusing to select on performance, and the cost ratio in the card is the only admissible filter.
2. **"Reallocating α to the pool loosens the gate."** It does not raise the family-wise error; it changes which hypothesis gets the power. But it is a change to a ratified rule after six entries exist, and it must be ruled before the pool's first exposure, or the pool enters at α_i.
3. **"The simulations are iid normal."** Autocorrelation would lengthen every horizon (the HAC t already pays for it); fat tails raise the tripwire's void rate (shown) and the e-process is robust by construction. Every number here is therefore an optimistic bound on speed.
4. **"CUSUM flags will cause the owner to act on noise."** They might; that is why they are report-only with the false-alarm rate on the same line, and why the freeze is deferred.
5. **"Breadth is not available at this venue."** Possibly true: 13 FX pairs are ~2.25 independent bets ([[GAP-P12D-148]]), the index CFDs correlate, and every cheap mechanism has been tried. If Agent A cannot supply 6–10 independent, cost-clearing streams, the arithmetic in §3.4 says the forward clock is decades long and the honest recommendation at 2027-04 is to stop, with the money intact (owner plan item 6).
6. **"The Winton referent is 2011 and $22bn."** Yes; only the rung structure transfers, and it already matches ACIS's.
7. **"You wrote no new idea."** Correct, and deliberately: every honest study says the pipeline, not the idea, is where a small operator loses, and ACIS's pipeline is already better than most; its remaining defects are the four seams in §1 (no pool, no E3, no evidence-weight line, no admission card).

## 8. Pre-registration specs offered to the owner (none runs real data; B1 is a registration, not a look)

- **PR-B1 (registration):** `POOL-ALL` and `POOL-3` as above, written to `data/forward/record` before their first exposure (the next NY weekday after the owner's ruling), α per the ruling on B1. No look, no kill threshold: the record's own rule grades them.
- **PR-B2 (synthetic):** lab calibration of the per-entry CUSUM h at k = half the E2 claim to 10% false alarms per 2 years, and of the tripwire's void rate at each pinned k under the lab's fat-tailed null; outputs are constants in the report, nothing graded.
- **PR-B3 (synthetic):** B0-style planted/null/leaky-oracle calibration of `close_book` and `window_book`.
- **PR-B4 (fills):** E3 on the first 60 demo fills after the cutover: ±25% band on realised − modelled cost in modelled-cost units; breach at W ≥ 20; one-sided certification when both nulls reach 20; written to `OPERATIONS_LEDGER.md`.

## 9. Sources

Internal: `tests/backtest/tournament_rule.py`, `tournament_registry.py`, `forward_record.py`, `tournament_books.py`, `hac.py`, `look_cycles.py`, `look_claims.py`; `scripts/tournament_daily.py`, `tournament_report.py`, `demo_report.py`; `deploy/forward/acis-forward-run.sh`; `specs/ACIS-09` v1.14 C-BT-11 v2 step 7; `ACIS_SPEC.md` §5.6–5.7 and v2.36; `data/forward/record/000001–000007`; `hypotheses/README.md`; `KNOWN_GAPS.md` [[GAP-P12D-148]], [[GAP-P12D-158]], [[GAP-P12D-159]], [[GAP-P12D-160]]; `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` §5, `RESEARCH_STATS_METHODOLOGY_2026-09-16.md` §1.4/§3.4/§6, `RESEARCH_FACTORY_2026-10-03.md`, `LEVER3_MEMO_2026-10-03.md`, `TOURNAMENT_REPORT_2026-10-03.md`, `TOURNAMENT_SPEC_PROPOSAL_2026-10-03.md`.

External (grade in text): Falck, Rej & Thesmar, QF 22(11) 2022 — https://dspace.mit.edu/handle/1721.1/163650 , https://cfm.com/why-and-how-systematic-strategies-decay/ · Pénasse, Mgmt Sci 68(5) 2022 — https://ideas.repec.org/a/inm/ormnsc/v68y2022i5p3966-3973.html · Suhonen, Lennkh & Perez, JPM 2017 — https://alphaarchitect.com/?p=36892 · DeMiguel, Garlappi & Uppal, RFS 22(5) 2009 — https://ideas.repec.org/a/oup/rfinst/v22y2009i5p1915-1953.html · Novy-Marx, NBER w21329 — https://www.nber.org/papers/w21329 · Harvey & Liu, JF 75(5) 2020 — https://ideas.repec.org/a/bla/jfinan/v75y2020i5p2503-2553.html · Harvey & Liu, JPM 2015 — https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF · Harvey & Liu, RFS 31(7) 2018 — https://scholars.duke.edu/publication/1112843 · Chordia, Goyal & Saretto, RFS 33(5) 2020 — https://www.sfi.ch/en/publications/anomalies-and-false-rejections · Harvey, JF 72(4) 2017 — https://afajof.org/2017-annual-meeting/ · Bailey & López de Prado 2014 — https://papers.ssrn.com/abstract=2460551 · Waudby-Smith & Ramdas, JRSS-B 2024 — https://arxiv.org/abs/2010.09686v4 · Philips, Yashchin & Stein, JPM 2003 — https://researcher.ibm.com/publications/using-statistical-process-control-to-monitor-active-managers ; Morgan Stanley PSG — https://www.morganstanley.com/im/en-us/capital-seeker/about-us/news-and-insights/articles/when-good-managers-stumble.html · Carver 2015 — https://qoppac.blogspot.com/2015/11/random-data-evaluating-trading-equity.html · Allen & Karjalainen, JFE 51 1999 — https://www.cs.montana.edu/courses/spring2007/536/materials/Lopez/genetic.pdf · Neely, Weller & Dittmar, JFQA 1997 — https://ideas.repec.org/a/cup/jfinqa/v32y1997i04p405-426_00.html ; FX technical decay — https://ideas.repec.org/a/eee/intfin/v21y2011i2p176-206.html · Gençay 2026 — https://arxiv.org/pdf/2608.27734 · The Alpha Illusion 2026 — https://www.alphaxiv.org/abs/2605.16895 · López de Prado 2018 — https://www.garp.org/white-paper/the-10-reasons-most-machine-learning-funds-fail · Thompson-sampling blending, IJCAI 2016 — https://www.ijcai.org/Abstract/16/283 · Regime allocation, DTU — https://www2.imm.dtu.dk/pubdb/pubs/6808-full.html · Li & Hoi survey — https://arxiv.org/pdf/1212.2129 · Winton / Cliffwater due diligence, July 2011 — https://data.treasury.ri.gov/dataset/96dcb86f-e97e-4b05-8ce2-a40289e477a6/resource/3bc987e1-c783-4404-b2a4-909423393f24/download/winton-cliffwater-investment-due-diligence-reportredacted.pdf

Script and outputs: `acis-compute-1:/opt/acis/edge-B/power_math.py` (sha256 prefix in the handback), `power_math_out.txt` (run 2, all numbers above), `power_math_out_run1.txt`, `power_math_results.json`; copies in the session scratchpad `edge-B/`.
