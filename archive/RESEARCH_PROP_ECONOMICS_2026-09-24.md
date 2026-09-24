# RESEARCH — the economics of a ~$6k prop account, and what the paid minority does (ECONOMIST, 2026-09-24)

**Who asked, and under what brief.** The lead (an Opus 5.5 session) launched this under the pinned brief
`FIVE_AGENT_BRIEF_2026-09-24.md` §0 and §2, as part of GAP-P12D-52. The owner's words: *"we are not
entering a novel field. other people are crushing it in the prop firm venture via algo trading albeit a
minority. we need to know what that minority does and build on them."*

**Independence and method.**
- **Context and role.** Fresh context, no subagents. I am a finder, not a clearer (A5). Everything here
  is evidence for the lead to verify (A6), never an instruction (A9).
- **Repo.** Read-only. The only files written are this report and its checkpoint
  `archive/PARTIAL_PROP_ECONOMICS_2026-09-24.md`.
- **Web.**
  - WebSearch: 21 of 40 calls. After that I used WebFetch on primary URLs.
  - Every load-bearing external claim below carries a quoted passage and a URL, fetched 2026-09-24.
  - Three primaries could not be fetched and are marked: the CFTC release and SSRN returned HTTP 403,
    and one NTU PDF was unreadable.
- **Simulation.**
  - numpy and stdlib only, synthetic inputs only; no real market data touched.
  - Scratch code: `SCRATCH/economist/`.
  - Free memory was ~1.0–1.4 GB. Each run used < 100 MB, and one heavy process ran at a time. The box
    was at 100% CPU from other agents, so I stopped my own sweep once and reran it with lean grids for
    the variants.
- **The grader was validated before any result was believed.** The Monte Carlo reproduces the closed
  forms (§2.4).

## Executive summary (grades: a = peer-reviewed/regulator/firm primary; b = credible practitioner or dataset; c = unverifiable; [D] = derived here and reproduced by the validated simulation)

1. **(b, a) The base rates are brutal, and they measure negative drift, not difficulty.**
   - FPFX data via Finance Magnates (2024-09-18; b): ~14% of FX-prop buyers pass and ~7% are ever paid.
     The average payout is 4% of plan size, and an account spends ~$800 over ~3 challenges.
   - Topstep's own 2025 disclosure (a): 16.8% of evaluations completed, 33.3% of funded traders paid,
     0.71% ever moved to live capital.
   - A zero-edge, *disciplined* sizer would pass FundedNext's two phases 37% of the time and FTMO's 33%
     [D]. So the typical buyer carries a strongly negative drift net of costs.
2. **(b, with a supports) What the paid minority does:**
   - small, fixed risk tied to the drawdown buffer (FTMO: ≤1–1.5% per trade; showcased paid traders
     0.13–1%);
   - a slow cadence (none of the 5 long-lived verified Myfxbook survivors was a scalper; Hall: the
     funded payout rate falls from 34.8% to 3.9% going from 1 to 20 trades a day);
   - few simple, diversified rules (Carver); incubation (Davey); their own unique algorithm (FTMO: a
     third-party EA risks denial);
   - withdrawal at every date; scaling by allocation, not risk.

   **Anti-playbook (a):**
   - risk escalation after wins (Ben-David et al., *Review of Finance* 2018) or after losses (FTMO:
     "substantially larger position sizes");
   - churn at retail cost (ESMA: 74–89% lose; Chague et al.: 97% of persistent day traders lost);
   - hedging, group or third-party EAs, simulator exploits, request floods.
3. **[D] The challenge is a two-sided first passage.** P_pass = (1 − e^{−θL}) / (1 − e^{−θ(L+T)}),
   with θ = 2S/σ_a. **At zero edge P_pass = L/(L+T) whatever the size.** The funded stage is de
   Finetti's dividend problem with the barrier forced to b ≥ L. **At zero edge the expected lifetime
   withdrawals equal L exactly** (simulated 0.1013 against 0.1000; $478 against $480 under fat tails).
4. **[D] So the account is an option, and passing is not evidence.** A disciplined zero-edge
   static-floor account is +EV: FundedNext $6K ≈ +$88 per attempt (fat-tailed Monte Carlo). **Pass,
   payout or EV > 0 proves nothing about skill.** Grade ΔEV against a zero-edge control. Hall (arXiv
   2609.14859, b) reaches the same conclusion from the futures side.
5. **[D] The number.** On a FundedNext-style static-floor $6K 2-Step, under the survival-first policy
   ACIS should run, the account is +EV for an **OOS net Sharpe above ≈ −0.4**. Under conservative
   assumptions (50%/yr discount, 25% payout haircut) that is **≈ 0**.
   - The EV-optimal ("bold") policy breaks even at −0.74. The idealised closed form says ≈ −1.0.
   - Trailing floors are worse: FTMO 1-Step at its ~1.7% fee needs ≈ **+0.1** conservatively.
   - **Working threshold: S_net ≥ 0, out of sample, at the firm's own costs.**
6. **[D] Is the prop route +EV in the 0.3–0.7 band? Yes, on static-floor 2-Step geometry.**
   - +$57 to +$292 per $6K attempt under survival-first (≈1–5× the fee; $85–$336 at the EV optimum),
     across δ = 0.25–0.5/yr and haircut 0–25%.
   - P(pass) 0.42–0.52, about 6 months to pass on average.
   - **Conditions:** S is real and net of the firm's costs, the firm pays, and it accepts the
     automation (the SCOUT's question).
   - Small in dollars. The economics come from scale: fees fall from 1.0% of balance at $6K to 0.55% at
     $100K. Closed form, S = 0.5: $251 at $6K against $4,639 at $100K.
   - The SCOUT's pick is FTMO 2-Step Swing $10k at €89. It has the same geometry class and the same fee
     ratio. Closed form: +$193 to +$591 per attempt in the band before the §2.5 corrections (§2.8).
   - **An independent cross-check agrees with the ARCHITECT's FTMO numbers** (§2.8):
     - zero-edge pass: 0.28 here, ~0.25 there;
     - Sharpe 1.0 at 0.6%/day: pass 0.78 against 0.73, with a median of 271 against ~259 days;
     - funded year: trader share 9.7% against ~9.6%.
7. **[D] The EV-maximising risk scaling.**
   - Challenge: daily P&L volatility of ≈0.75–1.5% of the initial balance. The surface is flat: at
     S = 0.5, 1.25%/day passes in 88 days against 207 days at 0.75%, for ~5% of EV.
   - Funded: risk ∝ the cushion to the floor. The Højgaard–Taksar coefficient is (S_d + 2δ_d/S_d) ≈ 0.1
     per day. Cap it near 1%/day, and withdraw every eligible profit.
   - **A 1%/day cap costs ~0–4% of band EV and removes most of the option-value harvest at S ≤ 0.**
8. **(a) Evidence cannot certify the band.** Two OOS years give a Sharpe standard error of ≈ 0.75 (Lo
   2002). Certifying S = 0.5 at one-sided 95% takes ≈ 12 years. So act through capped-downside
   instruments (demo, then a small prop account) graded by ΔEV, never by a §14-style pass.
9. **(repo-verified) Where ACIS contradicts the playbook:**
   - **realised risk ≈ 0.04%/day** (ladder, $10k NAV). At that scale EV = −fee for every S ≤ 1.0: the
     challenge would take decades;
   - notional sizing from a fixed base unit;
   - a per-tick loop and order firehose (GAP-0075), against FTMO's 2,000 requests a day;
   - 771-second average holds, and §14's 48-hour duration cap;
   - 8 USD-correlated instruments;
   - no payout concept;
   - **the `ftmo` rulebook models FTMO's max loss on EOD balance, while FTMO measures intraday "equity
     (i.e., Balance + Open Positions P/L ± Swaps – Commissions)".** The rulebook is looser than the
     firm (a).
10. **[spec — owner ratification] The proposed objective, "PropEV".**
    - From a block bootstrap of OOS daily P&L under the exact rulebook: EV per attempt net of fees (90%
      interval), P(pass ≤ 60/126 days), P(breach ≤ 6 months), payouts a year, and **ΔEV against a
      zero-edge control**.
    - Gates:
      - G1: the lower bound of ΔEV > 0;
      - G2: the lower bound of EV > 0 after a 25% haircut;
      - G3: P(breach ≤ 6 months) ≤ 0.25;
      - G4: request, hold and news compliance.
    - LuxAlgo `prop-firm-sim` (MIT, TypeScript) has a good rule-semantics vocabulary. But it has no
      costs, no multi-day excursions, and rules sourced from an affiliate (c). Use it as an external
      cross-check only.

---

## Part 1 — the paid minority, graded adversarially

### 1.1 The base rates, from the few sources that publish denominators

**The whole evidence base on "who gets paid" is thin.** Hall (2026) surveyed the sector:
> "We identified more than twenty firms operating in this sector. Eight publish a pass rate in any form.
> Three firms publish a conditional payout rate themselves… π is disclosed and marketed, β is disclosed
> rarely and marketed never."

| Source | Grade | Population | Pass | Funded → paid | Buyers paid |
|---|---|---|---|---|---|
| FPFX Technology via Finance Magnates, 2024-09-18 | b (vendor dataset, trade press, unaudited) | 300k+ accounts, 100k traders, 10 firms, mostly FX/CFD | 14% of traders | ~45% | ~7% |
| Topstep risk disclosure, updated 2025-09-25 | a (firm primary) | futures, calendar 2025 | 16.8% of Combines (per account); 51.8% of people funded at least once | 33.3% of funded people | ≈17% per person (51.8% × 33.3%) |
| FTMO (as cited by Hall, Table 21) | c here (firm citation not fetched) | FX, 2-Step | 9–10% | — | — |

**Where the money goes.**
- Per FPFX, an account spends ~$800 on about three challenges, and the average payout is 4% of plan
  size.
- Per Topstep: "0.71% of individual participants trading in an Express Funded Account were called up to
  a Live Funded Account". Almost nobody is ever moved to real capital.

**The regulator view (a).**
- Belgian FSMA, 7 March 2024: "The consumer never makes any real trades. He or she plays on a demo
  account." "This is how prop trading firms earn money from them."
- ESMA, 27 March 2018 (retail CFDs generally): "74-89% of retail accounts typically lose money."

**Reading the base rates against the maths (§2.2).**
- A zero-edge but *disciplined* sizer would pass FundedNext's two phases 37% of the time and FTMO's
  33%. The observed FX cohorts pass 9–14%.
- So the typical buyer carries a strongly negative drift net of costs. The observed rates are consistent
  with an annualised S of about −1 at 1%/day risk, or about −2 at 2%/day.
- **The industry's economics run on that negative drift, not on the challenge being hard.** A buyer who
  merely stops bleeding (S ≈ 0) and sizes to the floors is already in the top of the distribution. That
  is the first and most important element of the playbook.

### 1.2 What distinguishes long-lived profitable accounts: evidence, graded

**Survivorship warning first.**
- FTMO's own "best traders" and EA showcases (2024-01-26, 2024-11-06) give no selection method, no
  sample size, and no failure denominators. They are advertising, graded (a) as documents but (c) as
  evidence about a population.
- The one systematic survivorship filter found:
  - Fernández (mechanicalforex.com, 2014-08-18, grade b) screened Myfxbook's "thousands" of accounts
    for live, verified, 3+ year, open-history, non-grid records, and "5 accounts make it through".
  - Of those five: "None were scalpers; lowest average trade duration was 5 hours". Their maximum
    drawdowns were 24–68%, and "The best long term retail performers never achieve a profit to drawdown
    ratio above 2."

**Behaviour that predicts failure (a):**
- Ben-David, Birru and Prokopenya (Review of Finance 22(6), 2018): retail FX traders "attribute random
  success to their own skill" and "expand their position sizes, increase trade variability, and execute
  more trades following gains", even though "past performance fail[s] to predict future success".
- Chague, De-Losso and Giovannetti (2019 working paper, grade b; complete Brazilian futures population):
  of day traders who persisted 300+ days, "97% of them lost money… we find no evidence of learning".

**Practitioners with verifiable process (b):**
- **Carver** (ex-AHL, runs his own money and publishes it):
  - A simple one-rule, one-instrument system has an expected Sharpe of 0.24; an experienced retail
    trader with a diversified mechanical system, 1.0; a world-class fund, 1.5–2.0 before fees
    (qoppac, 2020-03-05).
  - His own system trades trend (EWMAC, 4–64-day spans) and carry across 146 instruments, with a
    backtest Sharpe of 1.31 and costs of 1.06% a year (2021-12-02).
  - He sizes to "half the optimal risk target", where Kelly's risk target equals the Sharpe ratio.
- **Davey** (World Cup–placed futures trader, strategy factory): "After development is complete, it is
  best to let a strategy sit for a while, before dedicating capital for trading" (kjtradingsystems.com,
  undated). His incubation length is quoted as 3–6 months (a search summary of his site) and 6–12 months
  (a podcast summary). The two conflict, and neither is primary: **unresolved**.
- **Darwinex** (a regulated allocator, grade a as a firm document):
  - It normalises every strategy to a target of "6.5% monthly VaR", and its risk-stability attribute
    penalises "erratic risk adjustments".
  - Its allocation rating weights 6-month return (67%), current month (22%) and max drawdown (11%), plus
    an experience bonus of up to +3 for records over 18 months (rating doc, updated 2025-10-01).
  - In short, the allocator rewards **stable risk over a long record**, not a sprint.

**What the paid minority's process looks like, as far as evidence allows:**
- The showcased paid traders run small, fixed risk: 0.13% per trade (a $400k account, 15 consecutive
  payouts) up to 1%.
- They target modest monthly returns (2–3%), trade a handful of instruments, and scale through
  *allocation*, not through risk.
- That matches the maths. At a small positive edge, the funded account's value comes from surviving
  many payout cycles (the de Finetti flow), so risk per unit of cushion is what matters.

### 1.3 The playbook (each element graded)
| # | Element | Grade | Why |
|---|---|---|---|
| P1 | Fix risk as a small fraction of the **distance to the floor**. Never raise it after wins or to "catch up". | **a** | Ben-David et al. 2018 (escalation after gains is the documented failure mode); FTMO forbids "opening substantially larger position sizes compared to your other simulated trades" (2026-02-02); the Højgaard–Taksar control of §2.3 |
| P2 | Per-trade risk about 0.25–1% of the initial balance. Challenge: daily P&L volatility of 0.75–1.25% of it (EV is flat across 0.75–1.5%). Funded: about 10% of the cushion per day, capped near 1%/day | **b** (maths and simulation, with firm guidance) | FTMO: "maximum recommended risk on one trading position is… 1% to 1.5%" (2024-07-26); simulation §2.5 |
| P3 | Trade slowly: hours-to-days holds, few trades. Hold still slower on the funded account | **b** | Fernández 2014 (no scalpers among the survivors); Chague et al.; Hall 2026: the funded payout rate falls from 34.8% at 1 trade/day to 3.9% at 20/day; the cost Sharpe −c·√N (§2.6) |
| P4 | A few simple, diversified rules with a published rationale (trend, carry) at horizons the costs permit | **b** | Carver (Sharpe expectations; trend + carry at 4–64 days) |
| P5 | Incubate forward before paying: a demo on the destination feed | **b** (principle) / **c** (duration) | Davey |
| P6 | Run your OWN algorithm; never a commercial EA | **a** | FTMO FAQ (2026-05-27): third-party EA users may share "exactly the same strategy" and "run a risk of being denied" |
| P7 | Withdraw every eligible profit while the edge is modest. Keep a cushion only when the out-of-sample Sharpe is high and the discount low | **a** (maths) | The de Finetti barrier with b ≥ L (§2.3) |
| P8 | Prefer static-floor, no-consistency, uncapped-payout geometries. Avoid trailing floors | **b** | Hall 2026: the ratchet costs 14–17 points of pass probability; simulation §2.5 |
| P9 | Scale by account *size* once proven. Fees fall with size (FundedNext $6K is 1.00% of balance, $100K 0.55%) | **a** (price list) | FundedNext Stellar 2-Step page |
| P10 | Judge a strategy against a **zero-edge control** run through identical rules, never by pass rate or EV alone | **b** | Hall 2026: "Every account-level result is reported against a zero-edge control"; this report §2.4 |

### 1.4 The anti-playbook (what reliably loses accounts or payouts)
| # | Anti-pattern | Grade | Evidence |
|---|---|---|---|
| X1 | Churn at retail cost: many short trades | **a**/**b** | ESMA; Chague et al.; GAP-P12D-45 (~33% of NAV a year at ACIS's churn); the cost Sharpe −c·√N |
| X2 | Raising risk after wins, or after losses (martingale, grid, averaging down) | **a** | Ben-David et al.; FTMO "substantially larger position sizes"; Darwinex Rs; ACIS §17 |
| X3 | Variance harvesting: one big bet per day to "pass fast" | **b** | Legal only in the maths. It is what the firms' discretionary clauses target, and one lumpy day fails consistency and qualifying-day rules at many firms (Hall §12.7) |
| X4 | Hedging across accounts, or opposite positions | **a** | FTMO: "simultaneously entering into opposite positions"; Hall: roughly EV-neutral at payout ceilings anyway |
| X5 | Exploiting the simulator: latency, price errors, tick scalping, "ultra-high-speed tools", request floods | **a** | FTMO forbidden practices; 2,000 server requests a day; 200 orders at a time |
| X6 | Trading scheduled news, or opening within 2 h of a ≥2 h close ("gap trading") where the account forbids it | **a** | FTMO forbidden practices |
| X7 | Buying a commercial EA | **a** | FTMO FAQ |
| X8 | Reading a pass as proof of skill | **b** | Hall: zero-skill sizing passes 0.36–0.47 against a 0.168 cohort; this report: FundedNext 0.37 at zero edge |
| X9 | Trusting affiliate or vendor statistics | **c** | Most "prop statistics" pages are affiliates. LuxAlgo, whose simulator is assessed in §2.7, sells discount codes for the firms it rates |

### 1.5 The incentive structure, and what it implies about tolerated strategies
- **Firms earn on fees.**
  - FSMA (a).
  - FPFX (b): ~$800 spent per trader; ~7% of buyers paid; the average payout is 4% of plan.
  - Hall (b): the evaluation is "permeable" and marketed, while the payout gate is hard and unpriced.
- **The account is simulated.** FTMO (T&C 5.2, quoted in the 2026-09-17 venue pass); Topstep
  ("realistic simulations"); FSMA. The firm is therefore the counterparty of last resort, and paying a
  winner costs it real fee revenue.
- **Implication 1.** A firm is indifferent to, or pleased by, negative-drift traders. It must police
  the zero-drift *variance-harvesting* play (X3), because that play extracts ≈ split × L per pass by
  pure geometry. Expect discretionary scrutiny of lumpy, high-variance accounts.
- **Implication 2.** A slow, stable-risk, unique algorithm that "conforms to the real market conditions"
  (FTMO FAQ) is exactly the profile the firms say they want. It is also the profile with the lowest
  denial risk.
- **Implication 3.** Payout reliability is a counterparty risk to price.
  - The CFTC complaint against My Forex Funds alleged the firm, "not a third-party liquidity provider",
    was the counterparty to substantially all trades. That quote comes from a search snippet; the
    primary returned HTTP 403.
  - The case was later dismissed with prejudice, with sanctions against the CFTC (Willkie and Quinn
    Emanuel summaries, grade c). The allegations are therefore unproven.
  - The SCOUT owns firm-level counterparty risk. This report prices it as a payout haircut h (§2.5).

## Part 2 — the mathematics (derive first, then verify by simulation)

### 2.1 Set-up and notation
- **Units.** Money is a fraction of the initial balance A ($6,000 on the base account). Time is in
  trading days (252 a year).
- **Constant-risk policy.** Under it, trading P&L is dX = k(μ̃ dt + dW), where:
  - k is the daily P&L volatility as a fraction of A. This is the one risk dial.
  - μ̃ = S/√252, where S is the annualised Sharpe measured on daily P&L, **out of sample and net of every
    cost the firm charges** (spread, commission, swap, FTMO's 0.7% non-USD P&L adjustment).
- **The one dimensionless number that matters:** θ = 2μ/σ² = 2S/σ_a, with σ_a = k√252 the annualised
  volatility.

### 2.2 The challenge phase: a two-sided first passage
The scale function of drifted Brownian motion is s(x) = (1 − e^{−θx})/θ. For a static floor L below the
phase's start and a target T above it:

  **P_pass = s(L)/s(L+T) = (1 − e^{−θL}) / (1 − e^{−θ(L+T)})**    (zero drift: P_pass = L/(L+T))

  **E[exit time] = (T·P_pass − L·(1 − P_pass)) / μ**                     (zero drift: L·T/k²)

The discounted, or killed, version is the two-sided Laplace transform:

  E[e^{−ρτ}; pass] = (e^{r₊L} − e^{r₋L}) / (e^{r₊(L+T)} − e^{r₋(L+T)}),  where
  r± = (−μ ± √(μ² + 2ρk²))/k².

The daily-loss limit D, measured on intraday equity against the day-start reference, acts as an
exponential killing clock. Its rate is κ(k) ≈ 2Φ(−D/k) per day (reflection principle), and it enters
exactly like a discount rate: ρ = δ + κ.

Consequences:
- **P_pass depends on the edge and the risk only through θL = 2S·L/σ_a.** At zero edge the pass
  probability is L/(L+T), whatever the size: sizing cannot create or destroy it.
- **Bold versus timid play** (the Dubins–Savage dichotomy):
  - With S > 0, the pass probability rises as k falls ("timid play"), towards 1, but the expected time
    grows like 1/k².
  - With S < 0, bold play is best: the largest k the daily limit tolerates.
  - When time has value (δ > 0), the EV-optimal k is interior.
- **Two phases** multiply: P = P(T₁)·P(T₂), each from a fresh start. At zero drift:
  - FundedNext Stellar 2-Step (8% / 5% / 10%): (10/18)(10/15) = **0.370**;
  - FTMO 2-Step (10% / 5% / 10%): (10/20)(10/15) = **0.333**.

  Compare the observed cohorts: FPFX 14% (mostly FX), FTMO 9–10%, Topstep 16.8%. **The observed
  population does far worse than a zero-edge disciplined sizer.** Retail drift net of cost is strongly
  negative, which ESMA's 74–89% and Chague et al.'s 97% corroborate.

### 2.3 The funded stage: de Finetti's dividend problem with the prop constraint
- **How the stage works.** At each eligible date the funded account pays `split × (profit above the
  initial balance)` and resets to the initial balance. The max-loss floor is static at 1 − L.
- **In dividend terms.** Measure the cushion x = X − (1 − L). The account is then a dividend process
  with ruin at x = 0, and a withdrawal barrier b that **cannot sit below L**: nothing below the initial
  balance is withdrawable.
- **Classical solution (Gerber–Shiu).** V(x) = g(x)/g′(b) on [0, b], with g(x) = e^{r₊x} − e^{r₋x}. The
  unconstrained optimal barrier is b* = 2·ln(−r₋/r₊)/(r₊ − r₋).
- **The prop-optimal barrier is max(L, b*).** Worked cases:
  - S = 0: b* = 0, so **withdraw everything at every payout date**.
  - S = 0.5, σ_a = 10%, δ = 0.25/yr: b* = 15.2% of A. Keep about 5% of profit in the account as a
    cushion before withdrawing.
  - Same, but δ = 0.5/yr: b* = 8.6% < L, so withdraw everything.

**The zero-drift identity** (the most useful single fact in this report). If S = 0, then M_t = X_t + D_t
(cushion plus cumulative withdrawals) is a martingale bounded below. By optional stopping at the ruin
time, **E[total lifetime withdrawals] = L exactly**. That holds whatever the position size, payout
cadence or withdrawal rule, so long as the account ends at its floor.
- Verified by simulation: 0.1013 against 0.1000.
- The trader's share is split × L.
- Daily-limit kills (which end the account with cushion left over) and a finite horizon only reduce it.

With drift and continuous withdrawal at the initial balance, the undiscounted total is (e^{θL} − 1)/θ,
which is more than L for S > 0. The discounted value is g(L)/g′(L).

**So a disciplined zero-edge account is worth about P_pass(0) × split × L − fee.**
- FundedNext $6K: 0.370 × 0.8 × $600 − $60 ≈ **+$118** (idealised).
- The account is a call option on the trader's P&L. The fee buys limited liability, and limited
  liability has positive value even at zero drift.
- Firms price the fee against the population's *negative* drift. They defend the option value with
  discretionary clauses: FTMO's "substantially larger position sizes", "risk per trade idea", group or
  third-party EA rules, and hedging bans.

**Risk control in the funded stage** (the analogue of Højgaard–Taksar 1999; Grossman–Zhou 1993 for
floors).
- If exposure can be scaled, the HJB gives an exposure proportional to the cushion below the cap:
  **k*(x) = (S_d + 2δ_d/S_d) · x**, with S_d = S/√252 and δ_d = δ/252.
- At δ = 0.25/yr the coefficient is:

  | S | coefficient (per day) |
  |---|---|
  | 0.3 | 0.124 |
  | 0.5 | 0.095 |
  | 0.7 | 0.089 |
  | 1.0 | 0.095 |

  So daily risk is about 9–12% of the distance to the floor. With a full 10% cushion that is ≈ 0.9–1.2%
  of the initial balance per day, and it falls linearly to zero at the floor.
- This is the continuous-time ideal of ACIS's §9.5 pre-limit taper. The taper, by contrast, holds full
  size until 60% of the limit is consumed.
- At zero drift, proportional sizing never breaches in continuous time (the CPPI property). The
  zero-drift identity still caps its expected lifetime withdrawals at L: it changes the timing, not the
  total.

### 2.4 The simulation: design and validation (the grader was validated first)

**Design.** The simulator is `propsim.py`, with numpy and synthetic inputs only.
- Rules are checked on 8 intraday sub-steps a day. Daily loss is measured against the start-of-day
  equity; max loss on intraday equity. Minimum trading days are enforced.
- After the target: flat, with token trades until the minimum days (the simplification R7 discusses).
- Funded payouts follow FundedNext's cadence: the first eligible at 15 trading days (21 calendar), then
  every 10 (14 calendar). All profit is withdrawn at the split, with the balance reset to initial; the
  fee is refunded at the first payout.
- The challenge horizon is 504 trading days; the funded horizon is 756 trading days (3 years).
  Discounting is applied afterwards (δ = 0.10, 0.25 and 0.50 a year).
- A payout haircut h ∈ {0, 0.25} prices counterparty and denial risk.

**Market scenarios.**
- "gauss": Gaussian i.i.d.
- **"fat" (the stress base case):**
  - Student-t(4) sub-steps;
  - log-stochastic volatility (ρ = 0.97, sd 0.10);
  - 1%/day symmetric 4σ jumps;
  - 0.1%/day adverse 6σ gap-through-stop crashes;
  - Monday first-sub-step gap × 2.
  - Measured: daily kurtosis **16.05**; the 0.1% quantile at **−6.35σ**; the 99.9% quantile at +5.57σ;
    mean compensated to zero so S stays the all-in mean.
- "fat_trend": the same, with AR(1) φ = +0.15 in daily P&L (measured +0.150).

**Validation against the closed forms** (Gaussian, no daily limit; 10,000 paths each):

| Check | Simulation | Closed form |
|---|---|---|
| P_pass, S=0, k=1% | 0.547 / 0.545 (m=16 / 8) | 0.556 |
| P_pass, S=0.5, k=1% | 0.683 / 0.689 | 0.689 |
| P_pass, S=1.0, k=1% | 0.801 / 0.803 | 0.799 |
| P_pass, S=−0.5, k=1% | 0.411 / 0.409 | 0.416 |
| P_pass, S=0.5, k=2% | 0.638 / 0.625 | 0.624 |
| P_pass, S=0.5, k=0.5% | 0.801 / 0.805 | 0.799 |
| Funded lifetime withdrawals, S=0 | 0.1013 | **0.1000 (= L)** |
| same, S=0.5 | 0.1457 | 0.1393 (daily rather than continuous withdrawal adds cushion) |
| same, S=−0.5 | 0.0716 | 0.0742 |
| same, S=0, k=2% | 0.0999 | 0.1000 |
| Discounted at 25%/yr, S=0 | 0.0947 | 0.0939 |
| Discounted at 25%/yr, S=0.5 | 0.1325 | 0.1278 |

Under the fat scenario the zero-drift identity still holds: FundedNext's undiscounted 3-year payouts at
S = 0 are **$478 against split × L = $480**.

### 2.5 Results — FundedNext Stellar 2-Step $6K ($59.99), fat-tailed stress case, 5,000 paths per cell

**EV-maximising policy per S** (δ = 0.25/yr, no haircut; break-even **S = −0.74**):

| S (OOS, net) | EV per attempt | challenge k/day | P(pass) | E[days to pass] | P(pass ≤126 d) | funded policy | P(any payout) | P(breach ≤6 mo) |
|---|---|---|---|---|---|---|---|---|
| −1.0 | −$20 | 2.00% | 0.164 | 38 | 0.163 | 1.5%/day | 0.57 | 0.93 |
| −0.5 | +$18 | 1.50% | 0.236 | 64 | 0.217 | 1.5%/day | 0.65 | 0.88 |
| 0.0 | +$88 | 1.50% | 0.324 | 66 | 0.296 | 1.5%/day | 0.72 | 0.82 |
| **0.3** | **+$162** | 1.50% | 0.402 | 65 | 0.365 | 1.0%/day | 0.83 | 0.51 |
| **0.5** | **+$234** | 0.75% | 0.536 | 207 | 0.153 | 1.0%/day | 0.85 | 0.49 |
| **0.7** | **+$336** | 0.75% | 0.606 | 196 | 0.197 | 0.25×cushion ≤1.5% | 0.81 | 0.40 |
| 1.0 | +$533 | 0.50% | 0.790 | 305 | 0.068 | 0.15×cushion ≤1.5% | 0.86 | 0.30 |
| 1.5 | +$961 | 0.50% | 0.920 | 252 | 0.121 | 0.10×cushion ≤1.5% | 0.87 | 0.22 |

**The survival-first policy (SF): the one to actually run.**
- The policy: challenge 1.0%/day; funded 0.10 × cushion capped at 1.5%/day; withdraw everything at
  each date.
- **It gives up only ~10–15% of the maximum EV in the band.** At δ = 0.25: $140 / $208 / $292 at
  S = 0.3 / 0.5 / 0.7, against $162 / $234 / $336 at the optimum.
- It cuts the 6-month funded breach probability from ~0.5 to **0.15–0.17**.
- At S = 0.5 it passes in 128 days on average (P = 0.48; 0.29 within 126 days) and pays ~5.8 times
  over 3 years ($709 undiscounted).
- **The EV surface is flat** across a challenge k of 0.75–1.5%/day (at S = 0.5: $217–234). So speed can
  be bought cheaply: 1.25%/day passes in 88 days against 207 days for about 5% of EV. Below 0.5%/day
  the time cost dominates: 0.25%/day gives EV −$46 to +$87.

**Break-even S across assumptions** (FundedNext $6K, fat):

| discount δ / haircut h | EV-optimal policy | survival-first policy |
|---|---|---|
| 0.10 / 0 | −0.79 | — |
| 0.25 / 0 | −0.74 | −0.37 |
| 0.25 / 0.25 | −0.49 | −0.23 |
| 0.50 / 0 | −0.66 | — |
| 0.50 / 0.25 | −0.42 | **−0.08** |

**Fat tails against Gaussian, both by Monte Carlo** (δ = 0.25, h = 0):

| Scenario | S = 0 | S = 0.3 | S = 0.5 | S = 0.7 | Break-even |
|---|---|---|---|---|---|
| Gaussian (lean grid) | +$110 | +$190 | +$300 | +$429 | −0.80 |
| Fat tails | +$88 | +$162 | +$234 | +$336 | −0.74 |

**Fat tails and gaps cost ~15–22% of EV in the band.** The main channel is the daily limit: at 1%/day
under fat tails, ~18–20% of phase-1 attempts die on the *daily* limit, not the max loss. That is the
sign the daily-limit guard (R3) is worth having. The fat model has no stop truncation, so it is
conservative: a real stop-based strategy truncates the left tail except on gaps. The Gaussian closed
form ($98 / $165 / $251 / $382) sits close to the Gaussian Monte Carlo. The remaining difference is the
continuous-killing approximation and the daily rather than continuous withdrawal.

**Rule geometry** (fat tails, **equal $60 fee**, δ = 0.25, h = 0, EV-optimal policy):

| Geometry | Break-even S | S = 0 | S = 0.3 | S = 0.5 | S = 0.7 |
|---|---|---|---|---|---|
| FundedNext 2-Step: static 10%; 5% daily vs day start | −0.74 | +$88 | +$162 | +$234 | +$336 |
| FTMO 1-Step: 10% EOD-trailing, reset on reward; 3% daily | −0.46 | +$53 | +$98 | +$156 | +$204 |
| Futures-style, stylised: 5% intraday-trailing locking at initial; 6% target; 90% split; **no payout gates** | −0.48 | +$38 | +$72 | +$110 | +$172 |

- **A trailing floor costs ~30–50% of the band EV at the same fee.**
- At FTMO's real fee (~1.7% of balance on the smallest account), the FTMO 1-Step conservative
  break-even (δ = 0.25, h = 0.25) is **+0.09**, and band EV is only $8–$73.
- Hall (2026) models real futures firms with their payout gates (safety net, qualifying days,
  consistency, payout caps) and finds them slightly **−EV at zero edge**: −$0 to −$25 per evaluation at
  Apex, trade level. Those gates are exactly what my stylised futures case omits.

**Risk cap** (FundedNext, fat): capping daily risk at 1.0% of initial leaves band EV essentially
unchanged:
- S = 0.5: $234 → $234. S = 0.7: $336 → $327.
- It moves break-even from −0.74 to −0.44, and to −0.19 conservatively.
- At a 0.75% cap: S = 0.5 gives $209, and the conservative break-even is **+0.02**.

**A 1%/day cap costs almost nothing if the edge is real, and removes most of the option-value harvest
if it is not.** That is the right asymmetry for an honest engine.

**P&L autocorrelation** (FundedNext, fat tails, AR(1) φ = +0.15 in daily P&L; lean grid, 2,500 paths
per cell). At δ = 0.25, h = 0:
- EV is +$117 / +$206 / +$289 / +$392 at S = 0 / 0.3 / 0.5 / 0.7, against +$88 / +$162 / +$234 / +$336
  at φ = 0. Break-even is −0.85.
- **Streaky, trend-like P&L raises EV by ~20–25% here.** The multi-day variance is (1+φ)/(1−φ) = 1.35×
  the daily-implied variance, which buys more option value and faster passage at the same daily risk.
- By the same mechanism, mean-reverting P&L (φ < 0) should lower EV. It was not run (CPU budget).
- Hall's warning applies to rulebooks this case does not have: under trailing floors and consistency
  rules, lumpy P&L is punished at the funded stage.

### 2.6 The number the owner needs, and how sensitive it is

**The minimum out-of-sample edge for +EV.** On a FundedNext-style static-floor $6K 2-Step account, run
under the survival-first policy, the account is +EV once the **net OOS Sharpe is above about −0.4**
(δ = 0.25, no haircut). Under conservative assumptions (δ = 0.5, a 25% payout haircut) that rises to
**≈ 0**. **Working threshold: S_net ≥ 0, with the edge measured out of sample and net of the firm's own
costs.**

**Inside the 0.3–0.7 band the static-floor prop route is +EV, and not by much in dollars.** Under
survival-first, EV is **+$57 to +$292 per $6K attempt** across the assumption grid: roughly 1–5× the
$60 fee, with P(pass) 0.42–0.52, about 6 months to pass on average (121–130 trading days), and 24–33% passing
within 126 trading days. Three reasons it is worth doing at all:
1. The downside is capped at the fee.
2. It is a forward test on the destination platform.
3. EV scales about linearly with account size while fees fall as a share of balance. Closed form, δ =
   0.25, S = 0.5: $251 at $6K, $2,294 at $50K, $4,639 at $100K.

**Sensitivity, ranked by how much each input moves the answer:**

| Rank | Input | Effect | Source |
|---|---|---|---|
| 1 | **Risk scale** | Decisive. At ACIS's realised ~0.04%/day, EV is −$60 at every S ≤ 1.0: the fee is lost to time. 0.10%/day gives −$60 to −$6; 0.25%/day turns positive only for S ≥ 0.3. | closed form, §3.3 C1 |
| 2 | **Costs, via S_net** | For a continuously invested FX book, the annual Sharpe drag is c·N/σ_FX ≈ **0.14 per 100 round trips a year at 1 bp all-in** (0.29 at 2 bp). Per trade, the break-even information ratio is c/σ_trade: 0.24 for a 13-minute hold, 0.023 for 1 day, 0.010 for 5 days at 1 bp. At ACIS's measured churn (~520 round trips per instrument-year at a 12.8-minute average hold) no plausible gross edge survives. | arithmetic; GAP-P12D-45/49 |
| 3 | **Rule geometry** | Large. Going from a static floor (FundedNext 2-Step) to an EOD-trailing floor (FTMO 1-Step) to an intraday-trailing floor (futures style) cuts band EV by ~30–50% at equal fee. At FTMO's real fee the conservative break-even reaches ≈ +0.1. | §2.5 |
| 4 | **Discount and payout haircut** | Together they move break-even by ≈0.3–0.4 Sharpe (the table in §2.5). | Monte Carlo |
| 5 | **Fat tails and gaps** | −15 to −22% of band EV against Gaussian, mostly daily-limit kills. Conservative, since the model has no stop truncation. | Monte Carlo |
| 6 | **P&L autocorrelation** | φ = +0.15 raises band EV ~20–25% on static-floor FundedNext geometry. Mean-reverting P&L should cut it (not run). | Monte Carlo |
| 7 | **Fee** | Small at this size. The fee is refunded with the first reward, so $30 promo against $60 regular moves EV by ≈$30 × (1 − P(pass)·P(first payout)), about $18–$25. | arithmetic |

**Is the band itself achievable, and where is such an edge documented?** The prior research
(`archive/RESEARCH_FX_METHODS_2026-09-16.md` §4.3) puts a realistic net Sharpe for a handful of FX
majors at **0.3–0.7**, from:
- FX-only trend walk-forward: 0.43 (c);
- the SG Trend Index: 0.42 (b);
- post-GFC carry: 0.25 (a);
- cross-sectional FX momentum: 0.95 gross, needing ~48 currencies (a).

Carver's 2020 table: 0.24 for a one-rule, one-instrument system, ~1.0 for a diversified retail system.
**Documented edges in the band are slow, diversified trend and carry**, holding days to months. ACIS has
no out-of-sample evidence of being in the band. On its own positive control it is at −1.12
(GAP-P12D-49).

**What an OOS record can prove.** For i.i.d. returns, SE(Ŝ) ≈ √((1 + S²/2)/T) (Lo 2002). Over T = 2
years that is ≈0.75. Showing S = 0.5 above zero at one-sided 95% needs **≈12 years**; S = 0.7 needs ≈7;
S = 0.3 needs ≈31. **No two-year OOS window can certify an edge inside the band.** This is why the
capped downside of a demo, then a small prop account, is the rational instrument for this uncertainty.
That holds *provided* the grading subtracts the zero-edge option value (§3.1, G1). Otherwise a pass or a
payout gets read as proof.

**The dangerous corner.** The EV-optimal policy at S ≤ 0 is **bold**: maximum daily risk, P(pass) → the
geometric L/(L+T), expected payouts → split × L. That is the variance-harvesting play the firms police
("substantially larger position sizes"; hedging and group bans). ACIS must **never** size up because its
edge is weak. The risk budget is set for the S > 0 hypothesis and capped by firm norms. The loss when
S ≤ 0 is capped at the fee anyway.

### 2.7 Proven parts: LuxAlgo `prop-firm-sim` as a referent (read, not added)

**What it is.** github.com/LuxAlgo/prop-firm-sim, fetched 2026-09-24:
- MIT licence ("MIT © LuxAlgo Global, LLC").
- TypeScript (pnpm and vitest), with an engine, a CLI and an MCP server. The main branch had 13 commits
  when read.

**Method** (read from `README.md`, `docs/rule-semantics.md`, `engine/attempt.ts`, `engine/funded.ts`,
`analyze/optimalRisk.ts`):
- A trade-level Monte Carlo. Parametric mode draws trades from a win rate and R-multiples; trade-log
  mode uses a block bootstrap "preserving your autocorrelation".
- Risk is set as a % of current balance, a % of initial balance, or a fixed amount.
- It checks rules at each trade close and at the day close.
- Its rule semantics are the best-documented public set found. The four max-loss variants are:
  - static;
  - EOD-trailing;
  - intraday-trailing;
  - trail-then-lock.

  Daily loss is split into four independent choices: `limitBasis`, `basis`, `includesOpenPnl` and
  `evaluation`.
- Consistency is modelled as a moving target, with an explicit "rational trader" assumption.
- Its "optimal risk" search reports both the pass-maximising and the EV-maximising risk, and says
  plainly that they differ.

**Fidelity limits**, which are its own declared assumptions plus what the code shows:

| Area | Limit |
|---|---|
| Intra-trade path | "Trades are same-day round trips; intra-trade excursions are not modeled. This slightly understates trailing-drawdown risk". It has no multi-day holding model, which is ACIS's intended regime. |
| Costs | No commission or cost term in the trade loop (`attempt.ts`). The user must supply net R-multiples. |
| Horizon | No discounting. The funded horizon defaults to 90 trading days, which understates the value of a real edge (the de Finetti flow) and overstates the weight of the first payout. |
| Post-payout state | "balances and loss floors carry across payouts; nothing resets" (`funded.ts`). FTMO's 1-Step page says its trailing max loss "resets upon reward withdrawal", so this is a candidate infidelity. **Unverified:** `rules.ts` was not read line by line. |
| Rules provenance | LuxAlgo's own prop directory API. LuxAlgo is an affiliate: its FTMO page advertises "FTMO 19% OFF". Grade (c) until checked against the firm's page, which its own README says "is always authoritative". |
| Attempts | Treated as i.i.d. |

**Verdict.**
- As a *design* referent for ACIS's prop grader it is useful, and its rule-semantics vocabulary is worth
  adopting almost verbatim for the §9.5 rulebook schema.
- As an *oracle*: not directly. It is TypeScript (ACIS is Python), it lacks costs and multi-day
  excursions, and its rule data is affiliate-sourced.
- Best use: an **external cross-check**. Feed the same OOS trade list to both it and ACIS's own PropEV
  grader on the static-floor case, where the two should agree within Monte Carlo error. A disagreement
  is a finding against one of them. This is the proven-parts pattern at the referent tier, the same
  status ta-lib has for indicators.
- Licence is not an obstacle: MIT permits vendoring with attribution. But the brief bars adding it, and
  ACIS §16 would need a spec edit for a new dependency.

### 2.8 Cross-check against the other agents (added 19:05 EAT after the lead relayed their results; nothing re-researched)

**The ARCHITECT's synthetic FTMO 2-Step Monte Carlo, as relayed, re-run through this pass's validated
simulator.** Same cells; FTMO 2-Step rules from the firm's page (10%/5% targets, 5% daily, 10% static,
4 minimum days); 4,000 paths; `xcheck_ftmo.py`.

| Quantity | ARCHITECT | This pass (fat) | This pass (Gaussian) | Closed form | Verdict |
|---|---|---|---|---|---|
| Zero edge, ~1%/day: P(pass both phases) | ~0.25 | 0.283 | 0.313 | 0.333 | **agree** in size and direction; mine 3–6 points higher |
| Sharpe 1.0, 0.6%/day: P(pass both) | 0.73 | 0.783 | 0.822 | 0.817 | **agree**; mine 5 points higher |
| Same cell: median trading days to pass | ~259 | 271 | 263 | mean ≈300 | **agree** |
| Funded year at Sharpe 1.0, 0.6%/day | ~9.6% of initial | 12.2% gross, **9.7% trader share (80%)** | 12.4% gross, 9.9% trader share | — | **agree** if the ARCHITECT's figure is the trader's share; mine is ~27% higher if it is gross. **Unresolved:** the relayed number does not say which |

Why the P(pass) figures differ slightly:
- The residual 3–6 points is within the spread I would expect from tail and daily-limit modelling
  choices. My fat case has kurtosis 16 but no stop truncation; the ARCHITECT's tail model and
  daily-reference semantics were not relayed.
- Both implementations sit below the idealised closed form, as they should: discrete monitoring, a
  daily limit, and minimum days all cut the pass rate.

**Two independent implementations agreeing is useful evidence on its own.** It supports the zero-edge
anchor: the zero-edge pass rate ≈ L/(L+T) per phase, reduced by tails. It also supports the
edge-to-time relation: a real edge buys pass probability only at the price of time, here ~1 year at
Sharpe 1.0.

**The SCOUT's venue finding changes which of my geometries is the live one; it leaves the conclusions
standing.**
- Per the SCOUT, only FTMO and E8 Markets let an unattended Linux engine trade a funded account (cTrader
  Open API). Its top pick is **FTMO 2-Step Swing $10k at €89 (refundable)**.
- That makes my FundedNext base case a *geometry proxy*, not a venue. FundedNext EAs are a paid MT
  add-on, which is consistent with C11.
- FTMO 2-Step's geometry is the FundedNext one with a 10% (not 8%) phase-1 target. So its zero-edge pass
  is 0.333 against 0.370 in closed form, and the fee ratio is the same (€89 ≈ $100 ≈ 1.0% of $10k).
- **Closed-form EV per FTMO 2-Step Swing $10k attempt** (Gaussian, best constant risk):

  | S (OOS, net) | −0.5 | 0 | 0.3 | 0.5 | 0.7 | 1.0 |
  |---|---|---|---|---|---|---|
  | δ = 0.25 | +$32 | +$132 | +$242 | +$378 | +$591 | +$1,034 |
  | δ = 0.5 | +$22 | +$107 | +$193 | +$269 | +$374 | +$599 |

- Apply the §2.5 corrections to these numbers:
  - fat tails, about −15 to −22%;
  - the survival-first policy, about −10 to −15% in the band;
  - the payout haircut.

  **The working threshold is unchanged: S_net ≥ 0**, where S_net must include FTMO's 0.7% non-USD P&L
  adjustment (venue pass 2026-09-17 §3.1 item 2).
- Swing's 1:30 leverage does not bind at these risk levels. About 1%/day of P&L volatility on $10k needs
  only a few times notional. Swing's removal of the news and weekend restrictions (venue pass §3.1
  item 3) is what lets multi-day holds run at all (C5).
- **E8 Markets was not modelled:** its rules were not fetched in this pass. Run it through PropEV once
  the SCOUT's rulebook exists.

## Part 3 — translation into ACIS

### 3.1 A prop-route grading objective — **[spec — owner ratification]** (§14 is master-spec text)

**Why §14 cannot be the prop objective as written.**
- §14 grades a return stream: Sharpe > 1.5, win rate, PF, positive months, average duration.
- The owner's money on a prop account depends on something else: P(pass), time to pass, P(breach),
  and payouts net of fees, all under the firm's exact rules.
- §14's own rule-restricted clause already says the platform limits apply *during* evaluation. But no
  §14 row measures any of these quantities.
- And §14's Sharpe > 1.5 is outside the prior research's realistic 0.3–0.7 band for FX majors.

**The trap this objective must avoid (the central methodological finding of this report).**
- On a static-floor FX account, **a zero-edge strategy is already +EV** in expectation (§2.3–2.5). The
  account is an option, and limited liability has positive value.
- So "EV > 0", "passed the challenge" or "got paid" is NOT evidence of skill. The engine's own
  positive-control Sharpe of −1.12 (GAP-P12D-49) sits at roughly break-even on FundedNext geometry in
  the idealised model.
- Hall (2026) reached the same conclusion from the futures side: "Whatever passes through these
  accounts is the account's option value. The strategy contributes nothing."

**Proposed objective.** A prop Monte Carlo, the "PropEV" grader, under the attached account's exact
§9.5 rulebook:
- **Rulebook features:** static or trailing floor, balance or equity basis, the daily reference and its
  timezone, minimum days, payout cadence, split, fee and refund.
- **Input:** a stationary block bootstrap of the strategy's **out-of-sample** walk-forward daily P&L. It
  is costed at the firm's own spread, commission and swap schedule, including FTMO's 0.7% non-USD P&L
  adjustment where it applies.
- **Reported, each with a 90% interval:**
  - **E1** EV per attempt, net of fees (δ = 0.25/yr; payout haircut h = 0.25 for counterparty and
    denial risk);
  - **E2** P(pass all phases within 60 and 126 trading days);
  - **E3** P(breach within 6 months of funding);
  - **E4** P(at least one payout within 6 months) and E[payouts per year];
  - **E5** **ΔEV = EV(strategy) − EV(zero-edge control)**. The control is the *same* risk policy driven
    by the strategy's own OOS P&L after demeaning, so the option value cancels.

**Proposed gates.**
- **G1:** the lower 90% bound of **ΔEV** > 0. This is the skill test, and it replaces "EV > 0".
- **G2:** the lower bound of EV > 0 after the haircut. This is the economic test.
- **G3:** P(breach within 6 months) ≤ 0.25.
- **G4:** the OOS order and request profile fits the firm's caps (for example, FTMO's 2,000 requests a
  day and 200 open orders) and hold, news and weekend rules, all measured in the same run.

**Relationship to §14.** Keep §14 as the bar for **real-money personal accounts**. For rule-restricted
prop accounts, PropEV G1–G4 would **replace** the Sharpe, positive-months and win-rate rows. Two §14
rows can stay as sanity checks: max drawdown against the firm floor, and SPX correlation. The owner
decides, and nothing here is live-enabling: live still requires human sign-off.

**Data budget.** Every PropEV run on real history is a trial against the holdout (principle 1), so it
belongs in the VALIDATOR's accounting regime.

### 3.2 The sizing policy the objective implies (requirements, not code)

**R1. The risk unit is the daily loss budget, not notional.**
- The Governor needs a first-class quantity: the expected daily P&L volatility, and the worst-case loss
  to the stops (with a gap allowance), both as fractions of the **account's initial balance**.
- `BASE_UNIT_USD × factors` should be derived from that budget. Today it is a fixed $1,000 of notional
  (`config/system_config.yaml:3`, `core/governor/capital_governor.py:283-291`), which fixes neither.

**R2. The budget follows the cushion.**
- Budget = min(k_cap, c × (equity − platform floor)), with c ≈ 0.10 per day (the Højgaard–Taksar
  coefficient at S ≈ 0.3–1.0, δ = 0.25; §2.3).
- k_cap ≈ 0.75–1.25% a day in the challenge. The exact value is to be set by PropEV on OOS data, not by
  this report.
- Funded: the proportional rule applies throughout.

**R3. A daily-limit guard in the firm's semantics.**
- The sum over open positions of the loss to the stop, plus a gap allowance, must stay ≤ ~0.8 × the
  remaining *platform* daily allowance.
- That allowance is measured from the firm's own reference (FTMO: the balance at 00:00 CE(S)T; The5ers:
  the higher of balance and equity at midnight), not from ACIS's 17:00-New-York day.

**R4. Composition with the §9.5 taper, within the law.**
- The cushion rule (R2) and the §9.5 pre-limit taper are both multipliers ≤ 1, applied as min().
- The cushion rule is stricter than the taper everywhere below 60% consumption. The taper still zeroes
  entries at 80%.
- Nothing loosens a guardrail. The Risk→Governor edge still carries only restrictive factors.

**R5. Composition with C16.**
- vol_norm stays dampen-only, and must act on the *budget-derived* size.
- The per-instrument `vol_target_atr_frac` must be calibrated so that the median vol regime delivers
  the budget. Otherwise C16 silently shrinks realised risk below the budget in calm regimes, and the
  challenge slows down (time is the hidden cost; §2.5).

**R6. The payout policy is part of the strategy.**
- Withdraw all profit at every eligible date unless the PropEV-optimal barrier says otherwise, which
  happens only at a high OOS Sharpe with a low discount (§2.3).
- The funded risk budget is recomputed from the new cushion after each payout.

**R7. After the target.**
- Flatten at the target. Then trade only on ordinary signals until the minimum days are met.
- §17 forbids opening a trade to satisfy an activity rule, so ACIS pays a small, measurable cost here
  (the risk of giving back gains before day N). PropEV must model ACIS's actual behaviour, not the
  "token trade" behaviour most simulators assume.

**R8. Guardrail interplay (owner-owned; flagged, not proposed).**
- ACIS's own daily guardrail (2%) and per-instrument guardrail (1%) are far inside the firms' 5% daily
  limit, so they bind first.
- Under R1–R3 this is acceptable. But whether they lower the achievable EV is a question PropEV can
  answer, and only the owner can act on the answer.
- The equity floor ($9,000, set for a $10k dev account) must be re-set by a human for a $6k account,
  above the firm's floor.

### 3.3 Where ACIS today contradicts the playbook
| # | Contradiction | Evidence (repo) | Playbook element |
|---|---|---|---|
| C1 | **Realised risk is ~20–30× below the prop optimum.** On a $6k account ACIS cannot pass in any relevant time, even with a good edge | Ladder: −$147.84 over 2.05 years at Sharpe −1.12 on $10k NAV (GAP-P12D-49; `tests/backtest/harness.py:93`; `tests/backtest/metrics.py:65-92`) ⇒ ~0.64%/yr ≈ 0.04%/day. The closed form gives EV = −$60 (the whole fee) at 0.04%/day for **every** S ≤ 1.0 | P1/P2, R1 |
| C2 | Sizing is notional, not risk-to-stop and not cushion-relative | `capital_governor.py:283-291`; fixed `base_unit_usd: 1000.0` | P1, R1–R2 |
| C3 | Per-tick decisions; order firehose not wired out | GAP-0075 (67–71 orders from one signal); master §10 "tick–5s" loop against FTMO's 2,000 requests a day and 200 orders at a time | X5, G4 |
| C4 | Churn and minute-scale holds | Ladder: 2,141 trades, average 771 s; fitness horizon ≤48 one-minute bars (GAP-P12D-32); ~33% of NAV a year in cost at the prototype's churn (GAP-P12D-45) | P3, X1 |
| C5 | §14 "avg trade duration 30min–48h" caps holds below the multi-day horizon the cost identity favours. FTMO Standard also bans weekend holds (Swing allows them) | ACIS_SPEC.md §14; `platform_rules.yaml` `ftmo.weekend_holding_allowed: false` | P3 — **[spec]** |
| C6 | An 8-instrument, USD-heavy book, against The5ers' "bulk trading" ban and FTMO's "correlated symbols" risk-per-trade-idea test | venue pass 2026-09-17 §3.1 items 1 and 7; master §6 clusters | P1 (one risk budget across correlated legs) |
| C7 | §14 is the wrong objective for prop (no P(pass), time, P(breach), EV, zero-edge control) | ACIS_SPEC.md §14 | P10, §3.1 |
| C8 | The §9.5 taper keeps full size until 60% of a limit is consumed; the optimum shrinks in proportion to the cushion from the start | ACIS_SPEC.md §9.5; `guardrail_limits.yaml` | R2/R4 (a refinement inside the law, not a loosening) |
| C9 | §17 "no trade to satisfy an activity rule" against minimum-trading-day rules (5 per phase at FundedNext, 4 at FTMO) | ACIS_SPEC.md §9.5/§17 | R7: small cost, keep the law |
| C10 | **The `ftmo` rulebook under-models FTMO's max loss.** FTMO measures "equity (i.e., Balance + Open Positions P/L ± Swaps – Commissions)" against the static floor; the rulebook says `anchor: eod, basis: balance`. The same shape recurs in the `fundednext`, `atlas_funded` and `prop_demo` total-loss entries (their firms unverified) | `config/platform_rules.yaml` `ftmo.drawdown_rules[1]`; FTMO trading-objectives page (updated 2026-05-13) | R3; guard-integrity (a rulebook looser than the firm) |
| C11 | The `fundednext` rulebook says "EAs on all programs" and models a 40% consistency rule. The FundedNext Stellar 2-Step page says EAs are "Available with add-ons" and lists no consistency rule | `platform_rules.yaml` `fundednext`; fundednext.com/cfds/stellar-2-step (fetched 2026-09-24) | the SCOUT owns this; corroborated here |
| C12 | The daily boundary is ACIS's 17:00 New York, while the firms reset at 00:00 CE(S)T (FTMO) or at server midnight | master v2.14; FTMO objectives | R3 |
| C13 | The funded stage needs a payout policy; ACIS has no concept of a withdrawal | the §12 control plane and the Governor have no payout state | R6 |

## What I could not verify
- **FTMO's pass rate (9–10%).** Taken only from Hall's Table 21 ("firm citation"). No FTMO primary was
  found. FTMO's "Trader's Analysis" post (2023-07-21) turned out to be a tool tutorial with no
  population data.
- **FPFX's methodology.** Firms, period, and whether "payout" counts one or all payouts are not stated
  in the Finance Magnates article. It is unaudited vendor data.
- **Davey's incubation length.** A summary of his site says 3–6 months; a podcast summary says 6–12.
  The page I fetched states only the principle.
- **LuxAlgo `rules.ts`** was not read line by line. The post-payout floor reset (FTMO 1-Step) is a
  candidate infidelity only.
- **FundedNext:**
  - the basis of the *overall* max loss (balance or equity);
  - payout caps, if any;
  - the "15% of challenge profit" reward mechanics;
  - whether any consistency rule applies to Stellar 2-Step. The product page lists none; the repo
    rulebook models 40%.
- **The5ers' small-account price.** The fetch returned "$19" for both $2.5K and $5K, which is
  implausible, so I did not use it.
- **The CFTC My Forex Funds complaint.** The primary returned HTTP 403; the counterparty allegation is
  quoted from a search snippet only.
- **Swiset's 1-phase versus 2-phase pass rates (20.3% / 11.8%)** and the Take Profit Trader, Earn2Trade,
  MyFundedFutures, The Funded Trader and ATFunded figures come only through Hall (2026).
- **Real payout-denial rates** at any firm. The haircut h is a free parameter, not a measurement.
- **Whether any shortlisted firm accepts ACIS's automation profile** on funded accounts. That is the
  SCOUT's question and it gates everything here.
- **The Andrea Unger process** was not researched (web budget).

## Residual risk
- **Model risk.** Strategy P&L is synthetic: Gaussian, or fat-tailed with stochastic volatility, jumps,
  gaps and AR(1). Real ACIS P&L will carry skew and regime shifts: trend strategies are positively
  skewed, mean-reversion negatively. The numbers are conditional on S being the *true* out-of-sample,
  net-of-firm-cost Sharpe.
- **Estimation risk dominates model risk.** Two years of OOS data give a Sharpe standard error of
  ≈0.75. Certifying S = 0.5 at one-sided 95% needs ≈12 years of data (≈7 years for S = 0.7). The
  PropEV ΔEV gate will usually be inconclusive. That is a fact about the world, not a flaw of the gate.
- **The option value is revocable.** The firms' discretionary clauses (FTMO 7.3/7.5; "substantially
  larger position sizes"), rule changes at will (FTMO T&C 5.6) and firm failure can all remove it.
- **Simulated counterparty** (GAP-P12D-44). A prop payout is paid from the firm's fee revenue, not from
  a market.
- **Semantics not modelled:**
  - the balance-referenced daily limit with floating P&L carried over midnight (FTMO);
  - payout caps and consistency rules where they exist;
  - scaling plans (an upside);
  - taxes and payout fees.
- **Reading risk.** An owner, or a later session, may read "+EV at zero edge" as licence to buy
  challenges with the current engine. It is not. At ACIS's current risk scale the EV is −fee (C1).
  At a true S ≤ 0 what remains is revocable option value. And GAP-P12D-49's engine may be well below
  S = −1 on real data.

## Ledger items this pass should generate (proposed; no IDs; for the lead to verify and triage — A6)

1. **The prop-route objective (PropEV).** Severity high · Likelihood high · proposed Status open ·
   **[spec — owner ratification]**.
   - Add the PropEV objective beside §14 for rule-restricted accounts:
     - EV per attempt net of fees, with a 90% interval;
     - P(pass within 60/126 trading days);
     - P(breach within 6 months);
     - payouts per year;
     - **ΔEV against a zero-edge control** run through the identical rules.
   - The gates are G1–G4 (§3.1). The Sharpe, positive-months and win-rate rows would be replaced for
     prop accounts.
   - Why: on static-floor FX accounts a zero-edge strategy is +EV, so pass, payout or EV > 0 is not
     evidence of skill.
2. **Build the PropEV grader.** Severity high · Likelihood high · open · **[impl]**.
   - Python, numpy and stdlib. Driven by a stationary block bootstrap of the out-of-sample daily P&L,
     costed at the firm's own schedule.
   - Validated first against the closed forms in §2.2–2.3: the scale-function P_pass, E[τ], the
     zero-drift identity E[W] = L, and the de Finetti value. The scratch code of this pass is a
     starting referent, not production code.
   - Cross-checked against LuxAlgo `prop-firm-sim` on the static-floor case. It must model ACIS's §17
     behaviour after the target (no token trades) and payout caps where they exist.
3. **The Governor's risk unit.** Severity critical · Likelihood high · open ·
   **[spec — owner ratification]** (ACIS-05 sizing contract).
   - Replace the fixed `base_unit_usd` notional with a daily loss budget, expressed as a fraction of the
     account's initial balance and proportional to the cushion to the binding platform floor (R1–R2),
     composed by min() with the §9.5 taper and C16 (R4–R5).
   - Measured fact: ACIS's realised risk (~0.04%/day, GAP-P12D-49) makes every prop attempt −fee for
     any S ≤ 1.0.
4. **The `ftmo` rulebook is looser than FTMO.** Severity high · Likelihood medium · open ·
   **[impl — human-committed rulebook, §9.5]**.
   - FTMO's 2-Step max loss is equity-based ("Balance + Open Positions P/L ± Swaps – Commissions"). The
     rulebook's `static/eod/balance` under-models it.
   - Verify `fundednext`, `atlas_funded` and `the5ers` the same way. The5ers' daily limit uses "the
     higher of midnight balance or equity"; FundedNext's daily limit "Includes realized and unrealized
     P&L".
   - A rulebook looser than the firm is the guard-integrity failure class.
5. **The `fundednext` rulebook against the product page.** Severity medium · Likelihood high · open ·
   **[impl — human-committed rulebook]**.
   - EAs are "Available with add-ons", not "on all programs".
   - The Stellar 2-Step page lists no consistency rule, while the rulebook models 40%.
   - The first payout is at 21 days, then every 14 (no rulebook field exists).
   - This corroborates the SCOUT's lead 3.
6. **The §14 duration row against the cost–horizon identity and the prop playbook.** Severity medium ·
   Likelihood high · open · **[spec — owner ratification]**.
   - The 30 min–48 h cap excludes the multi-day holds that clear costs: a 5-day hold's per-trade hurdle
     is 0.010 IR, against 0.239 for a 13-minute hold at 1 bp.
7. **A payout/withdrawal policy concept** (R6: the de Finetti barrier, b ≥ L). Severity medium ·
   Likelihood high · open · **[spec — owner ratification]** (a new Governor/Risk state).
8. **A daily-limit guard in the firm's own reference and timezone** (R3). Severity high · Likelihood
   medium · open · **[impl]**, extending the §9.5 platform-measured series.
   - FTMO: 00:00 CE(S)T balance.
   - FundedNext: 0:00 server time, realised + unrealised.
   - The5ers: the higher of balance and equity.
9. **Surface realised risk in every grading run.** Severity medium · Likelihood high · open · **[impl]**.
   - Add daily P&L volatility as a % of initial NAV as a first-class harness metric, so C1 is visible.
10. **Owner decision: how to read a prop pass.** Severity high (false encouragement) · Likelihood high ·
    open · **[owner decision]**.
    - Treat a $6K account as a cheap option. It tests plumbing, payout reliability and live behaviour.
      It is never evidence of edge, because the account's option value alone is +EV.
    - Scale to larger accounts (fees 0.55% at $100K against 1.00% at $6K) only on ΔEV evidence
      accumulated forward.
11. **Owner decision: the evidence horizon.** Severity high · Likelihood high · open · **[owner
    decision]**, linked to the VALIDATOR's data budget.
    - Two OOS years cannot certify any Sharpe in the 0.3–0.7 band. Certifying S = 0.5 at one-sided 95%
      takes ≈12 years (Lo 2002).
    - Decisions under this uncertainty should lean on capped-downside instruments (demo, then a small
      prop account) rather than on a §14 "pass".
12. **The anti-playbook as design constraints.** Severity medium · Likelihood medium · open ·
    **[spec — owner ratification]** (extends §17).
    - The EV-maximising risk at S ≤ 0 is "bold play", the variance-harvesting pattern firms police
      under "substantially larger position sizes". ACIS must never size up because its edge is weak.
    - The risk budget is chosen for the S > 0 hypothesis and capped by firm norms (≤ ~1–1.5% per
      trade; FTMO guidance).

## Sources (graded; all fetched 2026-09-24 unless stated; quotes are verbatim from the fetch)

**Firm primary documents (a)**
- **FTMO, Trading Objectives** (page updated 2026-05-13), https://ftmo.com/en/trading-objectives/
  - 2-Step Maximum Loss: "The Maximum Loss rule establishes a static limit… below which your account
    equity (i.e., Balance + Open Positions P/L ± Swaps – Commissions) cannot drop."
  - "The Maximum Daily Loss Limit is recalculated daily at 00:00 CE(S)T as the difference between: the
    account balance recorded at 00:00 CE(S)T of the current day and the Maximum Daily Loss Amount, which
    is 5%".
  - 1-Step: "end-of-day trailing limit"; it "Only increases; resets upon reward withdrawal".
  - "at least 4 Trading Days".
- **FTMO, Forbidden Trading Practices** (modified 2026-02-02),
  https://ftmo.com/en/forbidden-trading-practices/
  - "perform simulated trades or combinations of trades for manipulative purposes, for example by
    simultaneously entering into opposite positions"
  - "use any software, artificial intelligence, ultra-high-speed tools, or mass data entry that might
    manipulate, abuse, or give you unfair advantage"
  - "an excessive number of more than 2,000 server requests per day"
  - "opening substantially larger position sizes compared to your other simulated trades"
  - gap trading: "two hours or less before a relevant financial market is closed for at least two hours".
- **FTMO FAQ, "Which instruments can I trade and what strategies am I allowed to use?"** (modified
  2026-05-27),
  https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/
  - "if you use an EA from a third party, there might be other traders already using the same EA and
    therefore exactly the same strategy"
  - "potentially run a risk of being denied the FTMO Account if you exceed the maximum capital
    allocation rule"
  - "200 orders at a time and 2000 max positions per day limitation"
  - "trading style should be replicable on live accounts to generate the same results".
- **FTMO blog, "How much should you risk on one trade?"** (2024-07-26, modified 2025-12-05),
  https://ftmo.com/en/blog/how-much-should-you-risk-on-one-trade/ — "the maximum recommended risk on
  one trading position is a whopping 1% to 1.5% of the initial account balance".
- **FTMO blog showcases.** Graded (a) as documents but (c) as population evidence: no selection method.
  - https://ftmo.com/en/blog/how-do-our-best-ftmo-traders-trade/ (2024-01-26): "0.13% per trade",
    "2-3% per month", "15 payouts in a row".
  - https://ftmo.com/en/blog/what-does-profitable-trading-look-like-with-a-working-ea/ (2024-11-06):
    "159 positions", "The average RRR of 1.64… trade success rate of almost 68%".
- **FundedNext, Stellar 2-Step** (no page date), https://fundednext.com/cfds/stellar-2-step
  - $6K: "$29.99" (promotional) / "$59.99" (regular); Phase 1 "8%"; Phase 2 "5%"; "5% Daily"; "10% Max";
    "Static"; "5 days (each phase)"; time limit "None".
  - Reward "Up to 80%"; first payout "21 days"; then "every 14 days"; fee refund "With 1st reward";
    leverage "Forex 1:30".
  - EAs "Available with add-ons".
  - The price ladder: $15K $119.99; $25K $199.99; $50K $299.99; $100K $549.99; $200K $1,099.99.
- **FundedNext, general rules (CFDs)**, https://fundednext.com/general-rules/cfds/trading-objectives
  - daily loss: "Includes realized and unrealized P&L, swap, and commission"; "Resets daily at 0:00
    server time";
  - a trading day: "when you place at least one trade with non-zero P&L".
- **The5ers, High Stakes**, https://the5ers.com/high-stakes/ — daily loss "computed from the higher of
  midnight balance or equity"; 10% static max loss; 3 minimum profitable days. Prices unreliable in the
  fetch; not used.
- **Topstep, Risk Disclosure** (last updated 2025-09-25), https://www.topstep.com/risk-disclosure
  - "16.8% of all Trading Combines initiated were successfully completed…"
  - "51.8% of individual participants who entered one or more Trading Combines advanced to the Funded
    Level…"
  - "33.3% of all individual participants at the Funded Level received a payout"
  - "0.71% of individual participants trading in an Express Funded Account were called up to a Live
    Funded Account"
  - "realistic simulations of trading under actual market conditions".
- **Darwinex, "How the Risk Engine works"** (no date), https://help.darwinex.com/risk-manager —
  "6.5% monthly VaR"; "oscillate in between a monthly 3.25 and 6.5% VaR".
  **Darwinex Risk Stability**, https://help.darwinex.com/risk-stability-attribute: "measures the
  stability of the risk assumed across the positions that form a trading strategy".
- **Darwinex Zero, DarwinIA Rating** (updated 2025-10-01),
  https://darwinexzero.document360.io/docs/rating — "Current calendar month return (22%). Previous last 5
  months return plus current month's return (67%). Maximum drawdown… (11%)"; "+3 points for DARWINs with
  a track-record of more than 18 months".

**Regulators (a)**
- **FSMA (Belgium), 07/03/2024**,
  https://www.fsma.be/en/warnings/fsma-warns-consumers-against-shadow-investment-game
  - "The consumer never makes any real trades. He or she plays on a demo account."
  - "This is how prop trading firms earn money from them"
  - "The gaming element in prop trading can lead to overconfidence and recklessness".
- **ESMA, 27/03/2018**,
  https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors
  — "74-89% of retail accounts typically lose money on their investments, with average losses per
  client ranging from €1,600 to €29,000."
- **CFTC v. Traders Global Group (My Forex Funds)**, Release 8771-23 (2023). HTTP 403 on fetch. The
  allegations were seen only in search snippets: 135,000 customers, $310M in fees, and "Traders
  Global—not a third-party 'liquidity provider'—was the counterparty to substantially all customer
  trades". The later dismissal with prejudice and the sanctions are from law-firm summaries (c).
  **Unverified.**

**Peer-reviewed, and working papers with complete data**
- **(a)** Ben-David, Birru and Prokopenya, "Uninformative Feedback and Risk Taking: Evidence from Retail
  Forex Trading", *Review of Finance* 22(6):2009–2036 (2018); NBER w22146,
  https://www.nber.org/papers/w22146 — traders "expand their position sizes, increase trade variability,
  and execute more trades following gains versus losses".
- **(b)** Chague, De-Losso and Giovannetti, "Day trading for a living?" (2019 WP),
  https://ideas.repec.org/p/spa/wpaper/2019wpecon47.html — "97% of them lost money, only 0.4% earned
  more than a bank teller… we find no evidence of learning by day trading."
- **(b)** Hall, N., "Gate Design and Stage-Dependent Incentives in Retail Proprietary-Trading
  Evaluations…", arXiv:2609.14859 (v1, 14 Sep 2026; single author; working paper, not peer-reviewed;
  code linked), https://arxiv.org/abs/2609.14859
  - "position sizing alone yields a pass probability near 0.40, against a measured cohort rate of 0.168"
  - "Fourteen to seventeen percentage points of pass probability are consumed by the ratchet alone."
  - "Splitting the cadence — fast in evaluation, slow when funded — produces 8.8%" (against 1.0%)
  - "π is disclosed and marketed, β is disclosed rarely and marketed never."
  - "Whatever passes through these accounts is the account's option value. The strategy contributes
    nothing."
  - "Cost-free, the account is worth +$28 per evaluation purchased."
- Classical control theory, cited from the literature rather than fetched (a):
  - Gerber & Shiu, "Optimal dividends: analysis with Brownian motion", *NAAJ* 8(1) (2004);
  - Højgaard & Taksar, "Controlling risk exposure and dividends payout schemes: insurance company
    example", *Mathematical Finance* 9 (1999);
  - Grossman & Zhou, "Optimal investment strategies for controlling drawdowns", *Mathematical Finance*
    3 (1993);
  - Dubins & Savage, *How to Gamble If You Must* (1965);
  - Lo, "The Statistics of Sharpe Ratios", *FAJ* 58(4) (2002).

**Practitioners (b)**
- **Carver**, "How much risk should we take?" (2020-03-05),
  https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html — "Optimal risk target =
  Expected Sharpe Ratio"; "A better rule of thumb is to use half the optimal risk target"; Sharpe 0.24
  for a simple one-rule, one-instrument system.
- **Carver**, "My trading system" (2021-12-02), https://qoppac.blogspot.com/2021/12/my-trading-system.html
  — backtest Sharpe 1.307; EWMAC spans 4–64 days; "Costs come in at a very reasonable 1.06% a year".
- **Davey**, https://kjtradingsystems.com/build-an-algo-trading-system.html (undated) — "After
  development is complete, it is best to let a strategy sit for a while, before dedicating capital for
  trading."
- **Fernández (Asirikuy)**, "Looking at Forex Retail Champions…" (2014-08-18),
  https://mechanicalforex.com/2014/08/looking-at-forex-retail-champions-the-best-live-trading-verified-and-long-term-myfxbook-trading-account-results.html
  — "5 accounts make it through the above mentioned filters"; "The best long term retail performers
  never achieve a profit to drawdown ratio above 2."

**Trade press and vendor data**
- **(b)** Finance Magnates (D. Chmiel, 2024-09-18), FPFX Technology data,
  https://www.financemagnates.com/forex/analysis/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/
  - "14% of traders passed the challenge and obtained a funded account"
  - "about 45% achieved a payout (7% of all traders)"
  - "4% of the plan size"
  - "a single account spends an average of $800 on challenge purchases… typically taking three
    different challenges".
- **(c)** LuxAlgo `prop-firm-sim`: https://github.com/LuxAlgo/prop-firm-sim (MIT; README,
  `docs/rule-semantics.md`, `packages/core/src/engine/{attempt,funded}.ts`,
  `analyze/optimalRisk.ts`) — "The firm's page is always authoritative"; "balances and loss floors
  carry across payouts; nothing resets". LuxAlgo's FTMO page advertises "FTMO 19% OFF", so it is an
  affiliate.
- **(c)** Affiliate aggregators (quantvps, coinlaw, tradersyard and others). Used only as leads; no
  number from them is load-bearing here.

**Repo (read-only)**
- `config/system_config.yaml:3`
- `core/governor/capital_governor.py:283-291`
- `core/governor/factors.py:43-51`
- `config/guardrail_limits.yaml`
- `config/platform_rules.yaml`
- `tests/backtest/harness.py:93`
- `tests/backtest/metrics.py:65-92`
- `ACIS_SPEC.md` §6, §9.5, §14, §17
- `KNOWN_GAPS.md`: GAP-P12D-49, GAP-P12D-45, GAP-P12D-32, GAP-0075, GAP-P12D-44
- `archive/RESEARCH_FX_METHODS_2026-09-16.md` §4.3 (the 0.3–0.7 band)
- `archive/RESEARCH_VENUE_CHOICE_2026-09-17.md` §3.1

**Scratch code (reproducible, synthetic inputs only)**, in
`SCRATCH/economist/` = `C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad\economist\`:
- `propsim.py` — the simulator and closed forms;
- `validate.py` — the checks against the closed forms, with output in `validate_result.txt`;
- `analytic.py` — the closed-form EV;
- `sweep.py` and `runall.py` — the Monte Carlo sweeps (`res_*.json`);
- `analyse.py` and `summary.py` — EV and break-even.
- `xcheck_ftmo.py` — the §2.8 cross-check of the ARCHITECT's FTMO 2-Step cells, with output in
  `xcheck_ftmo.out`.
