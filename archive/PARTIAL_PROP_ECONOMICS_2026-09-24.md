# PARTIAL — ECONOMIST: the prop-firm economics pass (checkpoint, 2026-09-24)

> **SUPERSEDED (19:10 EAT):** the final report is `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`,
> which is complete, including §2.8, the cross-check against the ARCHITECT and the SCOUT. This file is
> kept only as the durability trail (§0.4).

**Who asked, and for what.** The lead (an Opus 5.5 session) launched this under the pinned brief
`FIVE_AGENT_BRIEF_2026-09-24.md` §2, as part of GAP-P12D-52. The owner's directive: learn what the paid
minority of prop-firm algo traders actually does, and build on it. Three parts:
1. a paid-minority playbook and anti-playbook, graded for evidence;
2. the mathematics of the challenge (two-sided first passage) and the funded stage (a de Finetti-style
   payout problem), and the minimum out-of-sample edge at which a ~$6k account is +EV;
3. a translation into ACIS: a prop-route grading objective [spec — owner ratification], sizing
   requirements, and where ACIS contradicts the playbook.

**Independence.** Fresh context, no subagents, repo read-only except these two report files.
Simulation code lives in the session scratchpad (`SCRATCH/economist/`), synthetic inputs only.

## Status at checkpoint 1 (14:25 EAT)
WebSearch used: 8 of 40.

### Found so far (graded; quotes and URLs go in the final report)
- **(b) FPFX Technology data, reported by Finance Magnates, 2024-09-18.** 300,000+ accounts, 100,000
  traders, 10 firms: 14% of traders passed; about 45% of those were paid (7% of all traders); the average
  payout was 4% of plan size; an account spends ~$800 on about three challenges.
- **(a) Topstep's own calendar-2025 cohort disclosure,** as tabulated in arXiv 2609.14859 (not yet
  fetched from Topstep itself): 16.8% of evaluations completed (per account); 51.8% of individuals funded
  at least once; 33.3% of funded individuals paid; 0.71% reached a live-capital account.
- **(b) arXiv 2609.14859 (N. Hall, 14 Sep 2026, a single-author working paper on futures EOD-trailing
  firms).**
  - At zero skill, sizing alone yields P(pass) of about 0.36–0.47. The continuous benchmark is d/(d+T).
  - A trailing ratchet costs 14–17 points of pass probability.
  - A cost floor beats every gross edge that survived its protocol.
  - Break-even is a 40.5–41.5% win rate at 1:1.5 net (driftless 40%).
  - Firms publish pass rates, not payout rates.
- **(c) The LuxAlgo `prop-firm-sim`** is MIT-licensed TypeScript, 13 commits. Its engine is trade-level
  (win rate and R-multiple, or a block bootstrap of real trades) and assumes same-day round trips with no
  intra-trade excursions. Its rules come from LuxAlgo's own prop-firm directory API, and LuxAlgo is an
  affiliate (it advertises discount codes). Engine files not read yet.
- **A repo fact for Part 3.** The Governor sizes by USD notional:
  `base_unit_usd × conviction × … × vol_norm × taper` (`core/governor/capital_governor.py:283`). It does
  not size by risk to the stop as a fraction of the drawdown budget. `base_unit_usd` is a fixed $1000
  (`config/system_config.yaml:3`).

### A first analytic observation (to be verified by simulation)
With zero drift and a static max-loss buffer L, the funded account's expected lifetime withdrawals are
about L × split (optional stopping on the martingale balance + withdrawals). So a zero-skill trader who
passes collects about split × L on average. That is why the firms' discretionary "gambling" and
"risk per trade idea" rules, consistency rules and payout gates exist. **The EV-optimal sizing sits exactly
where the firms' discretionary payout-denial rules live.** This belongs in the anti-playbook.

## Checkpoint 2 (14:45 EAT) — WebSearch 24 of 40
- **Primary sources added, all fetched today:**
  - **(a) Topstep risk disclosure** (page updated 2025-09-25): 16.8% of Combines completed; 51.8% of
    participants funded at least once; 33.3% of funded participants paid; 0.71% called up to Live.
  - **(a) FTMO trading objectives** (updated 2026-05-13). **(a) FTMO forbidden practices** (modified
    2026-02-02), including "substantially larger position sizes" and software giving an "unfair
    advantage". **(a) FTMO FAQ** (modified 2026-05-27): third-party EAs risk "exactly the same
    strategy" denial.
  - **(a) FundedNext $6K Stellar 2-Step:** $59.99; 8%/5% targets; 5% daily; 10% static max loss; 5 days
    per phase; 80% split; first payout at 21 days, then every 14 days; EAs as a paid add-on.
  - **(a) Regulators and peer review:** FSMA warning (2024-03-07); ESMA (2018-03-27: 74–89% of retail
    CFD accounts lose money); Ben-David, Birru and Prokopenya, Review of Finance 2018 (risk escalation
    after gains).
  - **(b) Practitioners and working papers:** Chague et al. (SSRN 3423101); Carver (2020 risk post,
    2021 system post); Davey (the incubation principle; the duration is unresolved: 3–6 vs 6–12 months).
- **The LuxAlgo engine, read:**
  - It is per-trade, with checks at trade close and day close only. It models no commissions, no
    discounting, and a 90-day funded horizon.
  - Its funded model says "balances and loss floors carry across payouts; nothing resets". That may be
    unfaithful to FTMO 1-Step's stated reset of the floor on reward (unverified).
- **Maths:**
  - Closed forms derived: pass probability via the scale function; expected exit time.
  - The funded-stage value is a de Finetti problem with the prop constraint b ≥ L. Under a proportional
    control, the Højgaard–Taksar form gives daily risk k*(x) = (μ_d + 2δ_d/μ_d)·cushion.
  - **The zero-drift identity:** expected lifetime withdrawals = L. So a zero-edge disciplined account is
    worth about P_pass(0) × split × L − fee. For FundedNext $6K that is ~0.37 × 0.8 × $600 − $60 ≈
    +$118 in the idealised model.
- **Simulator** (`SCRATCH/economist/propsim.py`): being validated against the closed forms.
  `sweep.py` is ready to run.

## Checkpoint 3 (15:16 EAT) — WebSearch 21 of 40
- **Simulator validated against the closed forms.**
  - Pass probability agrees within 1–2 SE in six (S, k) cells.
  - The zero-drift funded identity holds: 0.1013 against 0.1000.
  - The discounted funded value agrees: 0.0947 against 0.0939 at S = 0, and 0.1325 against 0.1278 at
    S = 0.5. The extra comes from daily rather than continuous withdrawal.
- **Closed-form EV** (idealised: Gaussian, killing-rate daily limit), FundedNext $6K ($59.99), δ = 0.25/yr:

  | S | −1.0 | 0 | 0.3 | 0.5 | 0.7 | 1.0 |
  |---|---|---|---|---|---|---|
  | EV per attempt | −$4 | +$98 | +$165 | +$251 | +$382 | +$652 |

  Break-even S ≈ −1.0. The EV-optimal challenge risk is 0.75–1.0%/day (12–16% annualised).
  **At ACIS's realised risk (~0.04%/day, from the GAP-P12D-49 ladder on $10k NAV) the EV is −$60 at
  every S ≤ 1.0: the fee is lost to time.**
- **A new finding (a, FTMO page fetched today).** FTMO's 2-Step max loss is on "equity (i.e., Balance +
  Open Positions P/L ± Swaps – Commissions)". The repo's `ftmo` rulebook models it as
  `anchor: eod, basis: balance`, looser than the firm's own rule.
- The fat-tail Monte Carlo sweeps are running (FundedNext base case first; then FTMO 1-Step, a futures
  intraday-trailing contrast, Gaussian, and autocorrelated variants).
- Drafts of Parts 1–3 are in scratch.

## What remains
1. Firm rule semantics for the math: FTMO, The5ers, FundedNext, via primary pages (the SCOUT owns full
   due diligence).
2. Darwinex (VaR normalisation, allocation stats); Myfxbook/retail evidence; ESMA CFD loss disclosures;
   Davey, Carver and Unger process quotes.
3. Analytic derivation: the scale function, time to pass, the daily-loss barrier; the de Finetti analogue.
4. Monte Carlo: fat tails, autocorrelation, gaps, intraday equity; sweeps of risk scaling and edge. Then
   the minimum +EV out-of-sample Sharpe, with its sensitivity.
5. Read the LuxAlgo engine files (`attempt.ts`, `funded.ts`, `rules.ts`, `optimalRisk.ts`) for fidelity.
6. The Part-3 translation, then the final report `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`.
