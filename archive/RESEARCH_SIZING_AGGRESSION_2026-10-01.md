# RESEARCH — Is ACIS sized too timidly, and what is the right aggression? (SIZING researcher, 2026-10-01)

**Who asked, and why.** The lead launched this pass on 2026-10-01. The owner's words: *"the engine might be too
conservative about not blowing an account and end up never trading and make pennies. we are here to make this a
money maker still without recklessly throwing cash away ... we need to sharpen the claws on this trading engine."*
My lens is sizing and aggression only. Where the edge comes from and how to validate faster belong to sibling agents.

**Status.** This is a finder's report (A5): evidence to weigh, not an instruction (A9). Nothing here binds until the
lead verifies it (A6). Anything touching `config/guardrail_limits.yaml`, the equity floor, HALT/veto semantics or the
VaR cap is **marked OWNER** and is never recommended silently.

**Builds on, does not redo:**
- `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`: the first-passage maths, "the account is an option", the
  survival-first and EV-optimal policies;
- `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md`, executive-summary items 1, 8 and 10;
- `archive/RESEARCH_PROP_VENUES_2026-09-24.md`: firm rules as of 2026-09-24, re-checked here on 2026-10-01.

**Grades.**
- **(a)**: peer-reviewed, regulator, or a firm's own primary page.
- **(b)**: credible practitioner or dataset.
- **(c)**: unverifiable.
- **[D]**: derived here. The derivation or the simulation is shown, and the simulator was validated against closed
  forms first (§3.1).
- **[repo]**: read from this repository at `main` (c8f8943 plus the working-tree changes shown at session start).

---

## Executive summary

**The plain answer.** ACIS is **far too timid in size**, by roughly an order of magnitude. It is **too loose in rule
fidelity** in two specific places. And it **sizes the wrong way near limits**: full size until 60% of a limit, then a
cliff. The aggression that pays is not "more risk everywhere". It is three things together:
- the top of the challenge band;
- a cushion-proportional funded stage;
- scale through **allocation** (more and bigger accounts), never through risk per account.

None of it matters until the edge exists. GAP-P12D-49 still has the engine losing on its own positive control, and a
bigger size on a negative edge only loses the fee faster.

1. **[repo + D] The binding constraint is the guardrail notional caps, not the drawdown limits.**
   - The legacy Governor sizes a fixed $1,000 notional, which realises about **0.04% of NAV a day** (GAP-P12D-61).
   - Replace that with any NAV-relative sizing and the next wall is `cluster_cap_pct: 20` and
     `single_currency_delta_cap_pct: 30`. Both are measured as **USD notional as a % of NAV**
     (`core/governor/exposure.py`). Both are owner-only.
   - For the two enabled pairs, the caps allow at most **0.16% of NAV a day** in P&L volatility, **at any account
     size**. Inputs: ECB reference rates 2023–25, EUR/USD 0.455%/day, USD/JPY 0.661%/day, correlation −0.51 [D].
   - That is **5–8× below** the prop challenge band (0.75–1.25%/day). It is even 1.4–3× below a skeptical Bayesian
     half-Kelly on a personal account (§3.2).
   - At that ceiling, an FTMO 2-Step **never passes within two years at any true Sharpe ≤ 1.0** (P(pass) = 0.00 in
     900 paths per cell). The EV is minus the fee. **"Pennies" is literally true: at S = 0.5 the ceiling earns about
     $6 a month on $6k and $106 a month on $100k.**
2. **[repo] The next walls, in order.**
   - **The VaR cap, 3%, undiversified.** Its arithmetic ceiling is ≈1.29%/day for a single instrument, ≈0.5–0.85%/day
     for a diversified book. Its σ is scaled from 10-second marks, so it inflates during active hours. A breach is a
     **global HALT with human-only resume**.
   - **The per-instrument 1% open-loss halt.** As built it is **human-resume only**. On a multi-week trend book with
     0.25%/day per instrument, **37% of 20-day holds would trip it** [D].
   - **The 2% daily session halt.** It is harmless at ≤ 0.75%/day: 0.8% of days.
   - **RSIM is not capped.** Its Carver vol target puts 0.3–1.0× NAV of notional on each FX pair at 10%/yr. That is
     2–5× the 20% cluster cap, so **the book R1 grades is not the book the Governor will let trade**. This is the
     GAP-P12D-36 defect class again. R1.6's plan ("risk sizing with a vol target in `core/`") does not mention the
     caps. **NEW item.**
3. **[repo + (a)] Too LOOSE where prop fidelity matters.**
   - The `ftmo` rulebook still models the 10% max loss as `anchor: eod, basis: balance`.
   - FTMO's page, **modified 2026-09-30**, still tests *"account equity (i.e., Balance + Open Positions P/L ± Swaps –
     Commissions)"*.
   - **GAP-P12D-54 is NOT fixed.** The schema can now express FTMO's rule; the corrected entry awaits the owner's
     commit.
   - Separately, the Risk Monitor measures cluster exposure at **mark** notional against **current equity**, while the
     Governor admits orders at **entry** notional. Price drift or a loss can therefore push a book admitted at 19.9%
     over 20%. That is a **human-only global HALT** (read in code, not reproduced).
4. **[D, new] Holding period moves the answer more than the risk dial does.**
   - FTMO and E8 anchor the daily limit on the **balance** at the day's reset, so open losses carried overnight eat
     the day's room.
   - In a synthetic book holding positions about 20 days, at S = 0.5 and 1%/day, FTMO 2-Step EV per $100k attempt
     falls from **≈$4.1k** (flat at each day end) to **≈$0.6k**, and 95% of accounts die on the *daily* limit.
   - E8 Pro, with its 2.5% daily, goes **negative**.
   - The 2026-09-24 economics pass measured the daily loss from start-of-day *equity*, which is **looser than both
     firms** for multi-day holds.
   - A **daily-room guard** (daily vol ≤ room/4) recovers most of the loss: EV ≈ $2.9k, and the 126-day funded breach
     rate falls from 83% to 12%.
   - **Caveat:** random exits overstate carried losses for trend rules that cut losers. **Measure it on R1's real
     open-P&L path.**
5. **[D] The right aggression is stage-dependent, and uncertainty pushes the two stages opposite ways.**
   - **Challenge.** The loss is capped at the fee, so uncertainty about S *raises* the EV-optimal risk (EV is convex
     in S). **Run 1.0–1.25%/day under the room guard.** The EV surface is flat; at S = 0.5 the hybrid policy has a
     median pass of 103 trading days.
   - **Funded.** This is a dividend annuity with a barrier. **Cushion-proportional sizing**, ≈0.10 × the cushion per
     day capped at 1%/day, gives the highest present value **and** the lowest breach rate at S = 0, 0.5 and 1.0, and
     under S uncertainty. At S = 0.5 over 4 funded years: PV 11.8% of A, 126-day breach 1.5%. Constant 1.5%/day:
     11.3% and 10.8%.
   - **Personal, uncapped money.** Bayesian half-Kelly is **0.2–0.5%/day** after 2 out-of-sample years with Ŝ =
     0.5–1.0 under a skeptical prior. It rises toward 1%/day only with a 5–10-year record.
6. **[D] The pennies question, in dollars: the money is in allocation.**
   - At a true net S = 0.5, a funded FTMO $100k under the recommended policy yields **≈$320/month**: the 4-year
     average including ruin, before any payout haircut. At S = 1.0, **≈$600/month**.
   - The **zero-edge control yields ≈$170/month**. That is option value, not skill.
   - At FTMO's $400k identical-strategy cap: ≈$1.3k/month (S = 0.5) and ≈$2.4k/month (S = 1.0).
   - A $6k personal account at Carver's 10% vol and S = 0.5 earns ≈$25/month.
   - More risk does not buy more: a constant 1.5%/day funded policy earns *less* than cushion-proportional at every S
     tested.
7. **[D + (a)] Parallel or sequential.**
   - Identical strategies on parallel accounts are perfectly correlated: no diversification, and N fees at risk at
     once.
   - A pass or a fail barely informs S: P(S = 0) goes from 0.60 to 0.48 after a pass, or to 0.69 after a fail.
   - So **sequence for operational learning**: one FTMO $10k at €89. Then **scale with identical $100k accounts**, up
     to FTMO's $400k (or E8's $500k per market). At $100k the fee is 0.63% of the account against 1.04% at $10k, and
     every instrument is lot-feasible.
   - **Put every sleeve in every account.** Two uncorrelated S = 0.5 sleeves combined (S = 0.71) earn **+42% EV** over
     splitting them across two accounts.
8. **[(a)/(b)] Drawdown-adaptive sizing, by the evidence.**
   - **Vol targeting** is tail control, not a Sharpe lever for FX (Harvey et al. 2018). Vol-managed equity factors
     failed out of sample in 72 of 103 cases (Cederburg et al. 2020).
   - **Equity-curve or drawdown de-risking** lowers returns of profitable systems, and for trend it is "an unmitigated
     disaster" (Carver 2015). Stop rules cost money under a random walk (Kaminski & Lo 2014).
   - **Cushion-proportional (CPPI-like) sizing** is optimal *because of the barrier* (Grossman & Zhou 1993; Højgaard &
     Taksar 1999).
   - **So:** use it as barrier-distance control, never as a performance filter. Never escalate to catch up. Browne's
     deadline result does not apply, since neither FTMO nor E8 has a time limit.
9. **[D] §14's "max drawdown < 15%" is a hidden vol cap.**
   - At a 20%/yr vol target (RSIM's default), a true S = 0.5 passes it **11% of the time over 2 years and ~0% over
     10**.
   - At 10%/yr: 69% and 11%.
   - **R1-D14 (account size and vol target) silently decides the §14 pass rate.**
10. **[(a)] Current rules (fetched 2026-10-01; full table in §2).**
    - **FTMO 2-Step:** 10% then 5%; 5% daily, from the 00:00 CE(S)T balance, measured on equity; 10% static on equity;
      4 minimum days; no time limit; 80% split, 90% with scaling; reward from day 14, positions closed; $400k
      identical-strategy cap. €89 for $10k, €540 for $100k.
    - **E8 Pro:** 8%, counted at ≤ 2% a day; 2.5% daily; 8% static that moves to the initial balance at the first
      payout; daily payouts of 50% of profit. $68 for $10k, $488 for $100k.
    - **E8 forbids** "risking your entire daily drawdown on a single trade", and may cap risk at 1% per trade idea.
    - **FTMO forbids** "substantially larger position sizes".

**The binding constraint.** The guardrail notional caps bind first: `cluster_cap_pct: 20` and
`single_currency_delta_cap_pct: 30`, measured on notional. They keep ACIS at pennies even with a real edge, and the
R1.6 sizing build will hit them. On a prop account the next wall is the firm's **balance-anchored daily limit**,
together with open losses carried across the reset.

---

## 1. ACIS's actual risk stack, mapped to the risk it really takes

### 1.1 Inputs
- **Volatility [repo data, (b)].** Computed from `data/macro/ecb_exr.csv`, the ECB reference rates, 2023–2025, 766
  days:
  - EUR/USD daily σ is 0.455% (7.2%/yr);
  - USD/JPY daily σ is 0.661% (10.5%/yr);
  - their correlation is −0.51.

  Over 2012–2025 the figures are 0.49% and 0.59%, with kurtosis 6.6 and 8.9. USD/CHF over 2012–25 has kurtosis 149
  (the SNB day).
- **Levels on 2025-12-31.** EUR/USD 1.175; USD/JPY 156.7.
- **The demo's minimum lot is 1,000 units**, i.e. 0.01 lot ([repo] `OPERATIONS_LEDGER.md` OPS-0001). The demo
  rulebook says to open the demo at $10,000.

### 1.2 Each constraint and the daily P&L volatility it permits (% of NAV) [D, `riskstack.py`]

| # | Constraint (file) | Owner-only? | $6k | $10k | $100k | Binds when |
|---|---|---|---|---|---|---|
| 1 | Legacy sizing: `base_unit_usd: 1000` × factors ≤ 1, marginal α ≤ 1.5 (`config/system_config.yaml`, `capital_governor.py`) | config, human-committed; not a guardrail | typical $330 → 0.025%; max $1,500 → 0.11% | 0.015–0.07% | **0.0015–0.007%** | always; **realised ≈ 0.04%/day** on the ladder (GAP-P12D-61) |
| 2 | Practice mode: one venue minimum lot (master §5 v2.22; ACIS-05 v1.6 `fixed_units`) | master spec | 0.09–0.11% *if held a day* | 0.05–0.07% | 0.005–0.007% | in paper and practice, by design |
| 3 | **Cluster cap 20% of NAV in notional; single-currency delta cap 30%** (`guardrail_limits.yaml`; `exposure.py`) | **OWNER** | **0.16%** | **0.16%** | **0.16%** | as soon as sizing is NAV-relative |
| 4 | VaR cap 3% NAV: 99% 1-day, delta-normal, **undiversified**, σ from 10-s marks × √8640 (`exposure_metrics.py`) | **OWNER** | Σ notional·σ ≤ **1.29%/day** | same | same | after #3 is lifted; ≈0.5–0.85%/day diversified; earlier in active hours |
| 5 | Per-instrument 1% NAV open loss: taper from 0.6%, entries stop at 0.8%, **instrument HALT** at 1.0% | **OWNER** | — | — | — | multi-day holds (table below); **human-resume as built** |
| 6 | Engine daily 2%: session halt, taper 1.2–1.6% (equity anchor at 17:00 NY) | **OWNER** | — | — | — | taper on 11% of days and halt on 0.8% at 0.75%/day; 23% and 4.6% at 1%/day |
| 7 | Equity floor $9,000, absolute | **OWNER** | **HALTS AT START** | 10% cushion | 91% cushion (useless) | GAP-P12D-56 |
| 8 | RSIM vol target (`BookSpec.vol_target = 0.20` default; R1-D14 open) | owner decision pending | 20%/yr = **1.25%/day**; 10% = 0.625%/day | — | — | grading only; nothing caps it |
| 9 | §14 max drawdown < 15% (`tests/backtest/report.py: MAX_DD_MAX_PCT = 15.0`) | **OWNER** (master §14) | — | — | — | a hidden vol cap (§3.7) |
| 10 | Firm rules (FTMO 2-Step 5% / 10%; E8 Pro 2.5% / 8%) | firm | — | — | — | with multi-day holds, the daily limit binds first (§3.4) |

**Row 3 in detail** [D]: EUR/USD and USD/JPY sit in disjoint clusters, so each may hold up to 20% of NAV. The 30%
USD-delta cap then limits how USD-directional the pair book can be.
- **The best legal book:** EUR/USD short at 10% plus USD/JPY long at 20%, giving USD delta +30%. Its σ is **0.160% of
  NAV a day**.
- **A USD-neutral book:** both long at 20%. Its σ is 0.11%/day.

**Per-instrument halt [D].** The reflection principle gives P(the open loss touches 1% of NAV during a hold of H days)
= 2Φ(−1%/(s√H)):

| Instrument σ (% NAV/day) | H = 1 | 5 | 20 | 60 |
|---|---|---|---|---|
| 0.10% | 0.0% | 0.0% | 2.5% | 19.7% |
| 0.25% | 0.0% | 7.4% | **37.1%** | 60.6% |
| 0.40% | 1.2% | 26.4% | 57.6% | 74.7% |

[repo] The halt is `Guardrails._issue_halt(inst, "per_instrument_drawdown")`. The Governor holds it in `_halts` until
`resume(human_token)`. `PersistentHaltSink` has "no clearing verb". ACIS-07 §5 says an instrument halt *"clears when
its condition clears or by human resume per policy"*. **The code is the stricter reading.** The owner should rule
which one is meant before a multi-week book trades.

**Per-trade risk today.**
- **The demo** [D, assumptions stated]. One lot of EUR/USD (1,000 units, $0.10 a pip) with a stop of 1.0–3.5 ×
  ATR(14) on 1-minute bars (`param_types.py`), at ≈1–2 pips of ATR, risks **≈$0.10–0.70 a trade, i.e. 0.001–0.007% of
  a $10k demo**.
  - The practitioner norm is 0.25–1% (FTMO: "1% to 1.5%", via the 2026-09-24 economics pass, (a)).
  - This is by design: master §5 says practice proves plumbing, not edge (GAP-P12D-129).
- **The legacy engine in live mode** sizes on the order of 330–1,500 units, so the risk is of the same order.

### 1.3 Verdict on the stack
- **Size: over-conservative, by 5–30×.**
  - Today's realised 0.04%/day sits 20–30× below the prop challenge band.
  - The notional caps alone sit 5–8× below it, and below a skeptical Bayesian half-Kelly too (§3.2).
  - A real S = 1.0 strategy behind these caps would still fail every FTMO challenge on time (§3.3, P0).
- **Fidelity: too loose in two places.**
  - (i) The `ftmo` rulebook's max loss is on balance, against FTMO's equity (GAP-P12D-54, open).
  - (ii) The economics pass's simulator used start-of-day equity, where the firms use the midnight balance (§3.4).
  - Also loose: the equity floor at $100k (91% cushion) and the lack of a pre-breach flatten on platform limits
    (GAP-P12D-59 [spec]).
- **Shape near limits: wrong.**
  - The §9.5 taper holds full size until 60% of a limit, then falls linearly to zero at 80%.
  - The optimum (Grossman–Zhou, Højgaard–Taksar, §3.6) shrinks in proportion to the cushion from the start.
  - Several breaches (VaR, cluster, instrument) are **human-only global or instrument halts**. Halts are cheap only
    when someone is watching. For an unattended demo they are a starvation mechanism, and master §10's anti-paralysis
    rule warns about exactly that.
- **Strongest counter-argument.** The caps are not a mistake for what they protect. The scenario book's CHF case,
  20% NAV × a 35% gap = 7% NAV (`scenario_book.yaml`), is the reason they exist. On a **personal** account, 3× gross
  FX notional in a CHF-style gap loses ~100% of NAV. The counter only fails on a **prop** account, where the owner's
  capital at risk is the fee and the firm bears the gap beyond its floor. The fix is therefore per-account profiles
  (§4 R2), not a looser global cap.

---

## 2. Current prop rules (primary pages, fetched 2026-10-01)

| Item | FTMO 2-Step (Swing for ACIS) | FTMO 1-Step | E8 Pro | E8 One |
|---|---|---|---|---|
| Target | 10% Challenge, then 5% Verification (a) | 10% (a) | 8% of *closed* profit; **only 2%/day counts** (a) | 6% (a) |
| Daily loss | 5% of initial below **the balance at 00:00 CE(S)T**, tested on **equity incl. open P/L** (a) | 3%, same anchor (a) | 2.5% of initial below the day's **starting balance**; equity *or* balance breach (a) | 3% of initial from the day's starting balance (a) |
| Max loss | **Static** 10% below initial, on **equity** (a) | **EOD-trailing** 10% from the highest 00:00 balance; *"fully resets"* on reward (a) | **Static** 8%; *"never moves, except when a first payout is processed"*, then **set to the initial balance** (a) | 4% **dynamic** on the highest *closed* balance, locking at initial (a) |
| Minimum days / time limit | 4 trading days per phase; no time limit stated (a) | none / none (a) | none; one closed trade every 60 days (a) | same (a) |
| Consistency | none (a) | Best Day ≤ 50% of positive days' profit, not a breach (a) | none (a) | Best Day 40% on payouts (a) |
| Split / cadence | 80%, 90% via scaling or Premium; claim *"on the 14th or any following day after the first placed trade"*, **all positions and pending orders closed** (a, via ftmo.com search index) | 90% (a) | 80% (100% as a paid add-on); **daily** once ≥ 1% profit since the last payout; each payout takes **50% of total profit** and leaves 50% as buffer (a) | up to 100%; minimum payout > 50% of the daily DD (a) |
| Scaling | +25% every 4 months if ≥ 10% net profit in 4 months and ≥ 2 rewards; up to **$2,000,000** across accounts (a; modified 2026-09-15) | — | — | — |
| Multiple accounts | unlimited count, but **$400,000** per trader *or strategy* before scaling ($600k Premium); identical strategies above it may be suspended (a) | same | challenges unlimited; performance **$500,000 per market**, 5 accounts per market, per household (a) | same |
| Automation and news | algos and EAs allowed; 2,000 server requests a day; Swing has no news restriction; *"gap trading"* banned on every account (a, 2026-09-24 venue pass) | — | EAs allowed; news allowed; weekend holding allowed; ≤ 50% of trades under 60 s; **"All-or-nothing: risking your entire daily drawdown on a single trade is not permitted"**; may cap risk at *"1% per trade idea"* (a, 2026-09-23) | **performance accounts: no trading ±5 min around high-impact news, SL/TP included**, which is structurally incompatible with server-side stops (a) |
| Leverage | Swing 1:30 (venue pass) | — | FX 1:30; indices and metals 1:15 (a) | same (a) |
| Fee by size | **€89 ($10k), €250 ($25k), €345 ($50k), €540 ($100k; €439 promo), €1,080 ($200k)**; refundable with the first reward (a: page data; size mapping read from the order and the $100k deal text) | €79, €199, €319, €499 (€399 promo), €999; not refunded | **$32 ($5k), $68 ($10k), $148, $228, $488 ($100k), $998, $2,098 ($400k), $2,598 ($500k)**; 10% off displayed (a: page data) | (not fetched) |
| Firm-stated averages | "average reward": 680 / 1,431 / 2,805 / 5,957 / 12,234 by size (a as a document, **c as population evidence**: no denominator) | — | "Average first payout" $1,594 on $100k (same caveat) | — |

**What changed since 2026-09-24.**
- FTMO's objectives page was re-modified on 2026-09-30, with no substantive change found.
- E8's articles were re-edited on 2026-09-23 and its rules still drift often (venue pass).
- All E8 facts here are from articles stamped 2026-09-11 to 2026-09-23.

**Sizing implications of the rules [D].**
1. **The daily limit is balance-anchored at both firms.** It punishes carried open losses (§3.4).
2. **E8 Pro is a sharp funded trap.** After the first payout the floor *is the initial balance*. The cushion is only
   the retained 50%, so a first payout requested at 2% profit leaves a 1% cushion. Request late, or size to the
   retained buffer.
3. **FTMO's reward requires a flat book.** Each claim forces a full round trip of a slow-trend book, but it also resets
   carried open P&L, which helps the next day's room.
4. **Both firms police size.** FTMO forbids "substantially larger position sizes"; E8 forbids "all-or-nothing" and may
   cap risk at 1% per idea. That caps the useful aggression independently of any maths.

---

## 3. The right aggression, phase by phase

### 3.1 Method and validation [D]
- **The simulator.** `propsim2.py` (Appendix A), numpy only, synthetic only.
  - Units are fractions of the initial balance A.
  - There are N = 2 independent sleeves with daily σ = k/√2 each. The total drift is k·S/√252 a day.
  - Each day has 4 sub-steps, with Student-t(4) shocks scaled to unit variance.
  - Sleeves close at random with mean holding period **H days**. A close realises the open P&L into the balance.
  - The daily floor is (balance at the reset − D). The static floor is applied to equity.
  - Targets are hit on equity, then the book flattens. A minimum-days target counts only once the minimum is met.
  - **FTMO funded:** a reward every 10 trading days; flatten, withdraw everything above initial at 80%; refund the fee
    at the first reward.
  - **E8 Pro funded:** request a payout at ≥ 6% total profit (a stated policy choice); pay 50% × 80%; the floor moves
    to initial at the first payout.
- **Horizon.** Two years from purchase (four for the funded-only runs), discounted at δ = 0.25/yr.
- **Fees.** €540 ≈ $632 and €89 ≈ $104, at EUR/USD 1.175.
- **Common random numbers.** Every policy uses the same seeds, so policy *rankings* are sharper than the Monte Carlo
  error on levels. Levels carry about ±2–3 points on probabilities and ±10–15% on EV.

**Validation before any result was used** (Gaussian, no daily limit, one 10%/10% phase, 3,000 paths):

| Case | Monte Carlo | Closed form s(L)/s(L+T) |
|---|---|---|
| S = 0, k = 2% / 1% | 0.508 / 0.498 | 0.500 |
| S = 0.5, k = 2% | 0.577 | 0.578 |
| S = 1.0, k = 1% / 2% | 0.787 / 0.661 | 0.779 / 0.652 |
| S = −0.5, k = 1% | 0.342 | 0.348 |
| S = 0.5, k = 1%, H = 20 (equity limits only, so H should not matter) | 0.655 | 0.652 |

**The zero-drift identity was reproduced:** funded-only, S = 0, lifetime trader payouts were 7.9–8.1% of A against
split × L = 8.0%, under every funded policy (EXP3).

**A bug found and fixed before use.** The first version summed sleeve drift as √N·kμ. Validation caught it (0.613
against 0.578), and every number below comes from the corrected code.

### 3.2 Kelly under parameter uncertainty: the personal-account answer [D, (a)/(b)]
- **Kelly.** For Gaussian returns, the Kelly fraction f* = μ/σ² gives a portfolio vol equal to S. So the Kelly vol
  target is S per year, and half-Kelly is S/2 (Carver, "How much risk should we take?", 2020, (b): *"Optimal risk
  target = Expected Sharpe Ratio"*, *"use half"*).
- **Fractional Kelly.** At a fraction c the growth is c(2−c) of the maximum, so half-Kelly keeps 75% of the growth.
  MacLean, Thorp and Ziemba (a): fractional Kelly gives *"smoother wealth paths but with generally less final wealth"*.
- **Raw half-Kelly is far above the prop limits.** At S = 0.5 half-Kelly is 25%/yr = **1.58%/day**; at S = 1.0 it is
  3.15%/day. Kelly is never the binding constraint on a prop account.
- **Parameter uncertainty is the binding argument for personal money.**
  - Take a skeptical prior S ~ N(0, τ²): most strategies have no edge. The sampling SE of Ŝ is √((1+Ŝ²/2)/T), per Lo
    2002.
  - The posterior mean, and half-Kelly at it:

    | Prior τ | OOS years | Ŝ = 0.5 → posterior; half-Kelly/day | Ŝ = 1.0 → posterior; half-Kelly/day |
    |---|---|---|---|
    | 0.3 | 2 | 0.07; **0.22%** | 0.11; **0.34%** |
    | 0.3 | 10 | 0.22; 0.70% | 0.38; 1.18% |
    | 0.5 | 2 | 0.15; **0.48%** | 0.25; **0.79%** |
    | 0.5 | 10 | 0.34; 1.09% | 0.62; 1.97% |

- **So a personal account** should run **≈0.2–0.5%/day** after a 2-year OOS record, and earn more risk only with a
  longer record. Even that conservative band is **1.4–3× above ACIS's 0.16%/day notional-cap ceiling**.
- **The barrier lens agrees.** For additive P&L the probability of *ever* touching a −10% floor (no withdrawals,
  infinite horizon) is e^{−2·S_d·L/k}. Holding it to 10% needs k ≤ 0.27%/day at S = 0.5, or 0.55% at S = 1.0.

### 3.3 The challenge: an option with the fee as its capped loss [D]

**EXP2 and EXP7.** FTMO 2-Step at $100k, H = 5 days, fat tails, with the room guard at z = 4 (daily vol ≤ room/4,
where room = min(distance to the daily floor, distance to the static floor)). 900 paths, 2-year horizon.

| Policy | S | P(pass) | P(pass < 126 d) | Median days | Funded breach < 126 d | Trader paid, 12 mo | Trader paid, 24 mo | EV/attempt |
|---|---|---|---|---|---|---|---|---|
| **P0 ACIS cap ceiling, 0.16%/day** | 0 / 0.3 / 0.5 / 1.0 | **0.00** | 0.00 | — | — | $0 | $0–3 | **−$632** |
| P1 moderate: 0.6% challenge, 0.5% funded | 0.5 | 0.47 | 0.04 | 258 | 0.00 | $568 | $2,652 | $1,470 |
| P2 1.0% challenge, cushion-proportional funded | 0.5 | 0.49 | 0.23 | 133 | 0.01 | $2,420 | $4,888 | $3,388 |
| **P4 1.25% challenge, cushion-proportional funded** | 0.0 | 0.31 | 0.20 | 107 | 0.03 | $1,469 | $2,233 | $1,314 |
| P4 | 0.3 | 0.40 | 0.25 | 105 | 0.02 | $2,105 | $3,610 | $2,432 |
| **P4** | **0.5** | **0.46** | **0.30** | **103** | **0.02** | **$2,768** | **$4,916** | **$3,480** |
| P4 | 1.0 | 0.66 | 0.41 | 97 | 0.02 | $4,850 | $9,931 | $7,396 |
| P3 1.5% both stages (the guard caps it at ≤ 1.25% at full room) | 0.5 | 0.45 | 0.33 | 86 | **0.09** | $3,665 | $5,513 | $4,062 |
| P3 | 1.0 | 0.63 | 0.45 | 86 | 0.09 | $6,525 | $10,895 | $8,387 |

The full P1–P3 grid at S = 0, 0.3, 0.5 and 1.0 is in EXP2.

**The $10k equivalent of P4** (fee $104): EV ≈ $100 / $215 / $322 / $720 at S = 0 / 0.3 / 0.5 / 1.0.

**Under parameter uncertainty** (EXP4a: S drawn per path from N(m, 0.5²)), EV per attempt:

| Policy | m = 0.0 | m = 0.3 |
|---|---|---|
| P1 | $539 | $1,311 |
| P2 | $1,769 | $3,093 |
| P3 | $2,296 | $3,817 |

Each is *higher* than the fixed-S EV (P2 at fixed S: $1,129 and $2,269). The payoff is convex in S, so uncertainty
adds option value. **In the challenge, uncertainty about the edge argues for the top of the band, not the bottom.**
That is the reverse of the Kelly intuition, and it holds only because the loss is capped at the fee.

**Why P3 "wins" the 2-year EV, and why it is still not the recommendation:**
1. The 2-year truncation drops funded value after month 24, which is exactly what P3's higher funded breach rate
   destroys (EXP3 below).
2. P3 at S ≤ 0 is the variance-harvesting play the firms police: FTMO's "substantially larger position sizes" and
   E8's "all-or-nothing" rules.
3. Hall (2026, arXiv 2609.14859, (b)) finds that *"the evaluation rewards aggressive position sizing while funded
   accounts punish it"*.

**So the challenge should run at 1.0–1.25%/day under the room guard: P4.** That is the top of FTMO's own guidance,
not beyond it.

**Time to money [D].** At S = 0.5 under P4, 46% pass, with a median of **103 trading days, about 5 months**. The first
reward comes about 2 weeks after funding. More than half of attempts never pay.

**No catch-up escalation.** Browne (1999, (a)) shows that maximising P(reach a goal *by a deadline*) is replicating a
digital option, which raises risk when you are behind near the deadline. FTMO 2-Step and E8 now state **no time
limit**, so there is no deadline to chase. Time enters only through the discount rate, which gives an interior
optimum and no escalation. That agrees with the anti-playbook: escalation after losses is the documented failure mode
(Ben-David et al. 2018, via the economics pass).

### 3.4 NEW: the balance-anchored daily limit and carried open P&L [D]

**EXP1 and EXP1b.** S = 0.5, fat tails, constant k in both stages, 1,000 paths.

| Venue | H (days) | k/day | Guard | P(pass) | Died on daily (any stage) | Died on static (any stage) | Funded breach < 126 d | EV per $100k |
|---|---|---|---|---|---|---|---|---|
| FTMO 2-Step | 1 (flat daily) | 1.00% | none | 0.49 | 0.05 | 0.88 | 0.42 | **$4,117** |
| FTMO 2-Step | 20 | 0.75% | none | 0.28 | **0.90** | 0.07 | 0.56 | $991 |
| FTMO 2-Step | 20 | 1.00% | none | 0.23 | **0.95** | 0.05 | 0.83 | **$632** |
| FTMO 2-Step | 20 | 1.00% | z = 3 | 0.42 | 0.43 | 0.33 | 0.27 | $2,559 |
| FTMO 2-Step | 20 | 1.00% | **z = 4** | 0.46 | 0.23 | 0.14 | **0.12** | **$2,922** |
| FTMO 2-Step | 5 | 1.00% | z = 3 | 0.47 | 0.18 | 0.50 | 0.19 | $3,437 |
| E8 Pro | 1 | 0.75% | none | 0.57 | 0.32 | 0.66 | 0.68 | $1,367 |
| E8 Pro | 20 | 0.50–1.25% | none | 0.23–0.25 | **0.97–0.98** | 0.02–0.03 | 0.75–1.00 | **−$115 to −$216** |
| E8 Pro | 20 | 0.75% | z = 4 | 0.52 | 0.45 | 0.09 | 0.20 | $768 |

**Why.**
- The firm's daily floor is (the balance at the reset − D). A position carried overnight with an open loss of x leaves
  only D − x of room.
- The breach probability is convex in the room, so by Jensen's inequality any spread in carried open P&L raises it.
- An *equity*-anchored daily model, as in the 2026-09-24 economics pass (*"daily loss is measured against the
  start-of-day equity"*), cannot see this effect.

**What it means.**
1. **Slow trend at E8 Pro is the wrong venue.** A 2.5% daily limit cannot carry multi-day risk: EV ≤ $0.8k per $100k
   even with the guard, against ≈$2.9k at FTMO.
2. **The room guard is worth roughly $2.3k per $100k attempt** for a multi-day book. It is inside the guardrails,
   because it only shrinks size.
3. **The risk dial and the holding period are one decision.** R1's TREND family (EWMAC 16–64, breakout 40–160) holds
   for weeks.

**The strongest counter-argument.** Random exits overstate carried losses. Trend rules close losers (the forecast
fades as price retraces) and let winners run, and Carver-style buffering realises P&L on every partial reduction. The
true effect lies between the H = 1 and H = 20 rows. **It must be measured**: RSIM, or the PropEV grader, has to export
each day's realised and unrealised P&L so the firm's balance anchor can be applied exactly. A daily P&L series alone
is not enough.

### 3.5 The funded stage: an annuity with a barrier [D]

**EXP3 and EXP4b.** FTMO funded only, 4 years, H = 5, guard z = 4, 600 paths. Values are % of A, with the trader's
80% share.

| Funded policy | S | Paid over 4 yrs | PV (δ = 0.25) | $/month at $100k (4-yr avg) | Breach < 126 d |
|---|---|---|---|---|---|
| F1 constant 0.5% | 0 | 7.9 | 6.1 | $164 | 1.0% |
| F3 cushion 0.10, cap 1% | 0 | 8.1 | 6.8 | $169 | 1.5% |
| F4 constant 1.5% | 0 | 8.0 | 7.3 | $167 | 10.5% |
| F1 | 0.5 | 14.3 | 10.3 | $298 | 0.8% |
| F2 constant 1.0% | 0.5 | 14.2 | 11.7 | $295 | 6.3% |
| **F3** | **0.5** | **15.5** | **11.8** | **$323** | **1.5%** |
| F4 | 0.5 | 13.0 | 11.3 | $271 | 10.8% |
| F2 | 1.0 | 24.4 | 18.9 | $509 | 5.3% |
| **F3** | **1.0** | **28.8** | **20.3** | **$600** | 1.8% |
| F4 | 1.0 | 22.0 | 18.0 | $459 | 9.8% |
| F1 / F2 / **F3** / F4, S ~ N(0.5, 0.5²) | — | 16.6 / 17.2 / **19.2** / 15.4 | 11.6 / 13.7 / **14.1** / 13.0 | $346 / $358 / **$399** / $321 | — |

Breach rates are the raw counts divided by 600.

**Reading.**
- At **zero edge every funded policy pays the same split × L**. That is the martingale identity: risk changes only
  the timing.
- With an edge, **cushion-proportional (F3) is the best policy undiscounted, discounted and under uncertainty, and it
  has the second-lowest breach rate**.
- Constant 1.5%/day is dominated.

This is the Højgaard–Taksar (1999, (a)) structure: *"the risk exposure monotonically increases on (0, u₀) from 0 to
the maximum possible"*. The economics pass's coefficient (S_d + 2δ_d/S_d) ≈ 0.09–0.12 a day matches c = 0.10.

### 3.6 Drawdown-adaptive sizing: what the evidence supports

| Method | Evidence | Grade | Use in ACIS |
|---|---|---|---|
| **Vol targeting** | "Volatility targeting ... improves Sharpe only for risk assets (equity, credit); for bonds, FX and commodities negligible; it **reduces the likelihood of extreme returns across all asset classes**" (Harvey et al., JPM 45(1), 2018). Vol-managed equity factors underperformed out of sample in 72 of 103 strategies (Cederburg, O'Doherty, Wang & Yan, JFE 2020) | (a) | **Yes, as risk control.** It holds P(daily breach) roughly constant, which is what a barrier needs. It is not an alpha source. RSIM's Carver sizing already does it; estimate vol on a horizon matched to the 1-day barrier |
| **Cushion-proportional (CPPI-like)** | Under a floor or drawdown constraint, the optimal policy invests in proportion to the surplus W − αM (Grossman & Zhou, Math Finance 3(3), 1993; Cvitanić & Karatzas 1995). With dividends: Højgaard & Taksar 1999. In continuous time CPPI never breaches; its known costs are gap risk and "cash lock" | (a) | **Yes, funded stage and room guard.** The cash lock is the "never trading" failure the owner fears, so cap the shrink with a floor-free cap (1%/day) and apply it only against the *binding* floor |
| **Equity-curve or drawdown de-risking** | Carver (2015, random-data study): for profitable systems it *"reduces, rather than increases, your returns"*; for trend, *"applying the filter will be an unmitigated disaster"* | (b) | **No**, as a performance filter. Barrier distance (above) is a different motivation |
| **Stop-loss as alpha** | Under a random walk, stop-loss rules *always decrease expected return*; they add value only with momentum (Kaminski & Lo, JFM 18, 2014) | (a) | Stops are for the firm's floor and gap control, not for return |
| **Catch-up / deadline sizing** | Probability-maximising sizing to a deadline replicates a digital option (Browne, AAP 31(2), 1999) | (a) | **No.** There is no deadline at FTMO or E8; ACIS §17 bans martingales |
| **Fractional Kelly** | Smoother paths at lower terminal wealth (MacLean, Thorp & Ziemba); half-Kelly keeps 75% of the growth [D] | (a) / [D] | The personal-account cap only (§3.2); never binding on a prop account |

### 3.7 §14's 15% drawdown gate is a hidden vol cap [D]

**EXP5.** Additive fixed-capital P&L (RSIM's convention), t(4) tails, 2,000 paths. P(max drawdown ≤ 15% of
capital):

| Vol/yr | S = 0.3: 2y / 10y | S = 0.5: 2y / 10y | S = 1.0: 2y / 10y |
|---|---|---|---|
| 5% | 0.97 / 0.64 | 0.99 / 0.77 | 1.00 / 0.97 |
| 8% | 0.81 / 0.16 | 0.85 / 0.30 | 0.94 / 0.67 |
| 10% | 0.61 / 0.06 | 0.69 / 0.11 | 0.86 / 0.36 |
| 12% | 0.46 / 0.01 | 0.54 / 0.02 | 0.70 / 0.15 |
| 20% | 0.07 / 0.00 | **0.11 / 0.00** | 0.21 / 0.00 |

**The Sharpe-based gates are scale-free; the drawdown row is not.** If stage-A or §14 grading runs at RSIM's default
20%/yr, the drawdown row fails almost every realistic edge. At 10%/yr it fails a true S = 0.5 about 31% of the time
on 2 years. **R1-D14 must be decided with this coupling explicit.** One option, OWNER: evaluate the drawdown row at a
declared reference vol (10%/yr), or with the cushion-proportional overlay the account will actually run.

### 3.8 Parallel versus sequential, and account size [D + (a)]
- **Parallel identical accounts are one bet, N times over.**
  - On the same signals, the path in units of A is identical, so pass and fail outcomes are perfectly correlated.
  - EV scales by N, risk is undiversified, and N fees are at risk together.
  - FTMO allows this up to $400k per strategy (a); E8 allows $500k per market (a).
- **Sequential barely buys statistical information.** Take a prior of P(S = 0, 0.5, 1.0) = 0.6 / 0.3 / 0.1, with
  P(pass) of 0.33 / 0.49 / 0.69 from EXP2.
  - One pass moves P(S = 0) to 0.48; one fail moves it to 0.69.
  - A 5-month challenge's daily P&L carries a Sharpe SE of ≈1.4.
  - The real value of sequencing is **operational**: fills, costs, the 0.7% currency adjustment, rule interpretation,
    payout reliability and denial risk (GAP-P12D-44). That information is cheap to buy once at €89.
- **Bigger is strictly better once the edge is believed.**
  - Fee/A is 1.04% at $10k, 0.63% at $100k, and 0.63% at $200k.
  - At $10k and 10% vol, 6 of 23 instruments can never hold one minimum lot; at $100k all can (GAP-P12D-101).
- **One combined book in every account beats sleeves split across accounts.** Two uncorrelated S = 0.5 sleeves give a
  combined S of 0.71.
  - Split, one sleeve per account: 2 × $3,388 = $6,776.
  - Combined in both accounts: 2 × $4,798 = **$9,596, +42%** (EXP6).
  - FTMO permits identical strategies across accounts within the $400k cap. E8 forbids hedging across accounts, and
    so would FTMO.

### 3.9 The "pennies" question, in dollars [D]

**Gross expected P&L per month while trading** = A × k × S/√252 × 21, before ruin, fees or the trader's split:

| Policy | k/day | S = 0.3 | S = 0.5 | S = 1.0 |
|---|---|---|---|---|
| ACIS realised (legacy) | 0.04% | $1 ($6k) / $16 ($100k) | $1.6 / $26 | $3 / $53 |
| ACIS notional-cap ceiling | 0.16% | $4 / $63 | **$6 / $106** | $13 / $212 |
| Moderate | 0.50% | $12 / $198 | $20 / $331 | $40 / $661 |
| Funded cap of the recommended policy | 0.75% | $18 / $298 | $30 / $496 | $60 / $992 |

**What the account actually pays the owner**, from EXP3 and EXP7, as the trader's 80% share, 4-year funded averages
including ruin, with **no payout haircut**:

| Route | Zero edge (option value) | S = 0.5 | S = 1.0 |
|---|---|---|---|
| $6k personal at Carver 10%/yr | $0 | ≈$25/mo | ≈$50/mo |
| FTMO $10k funded, F3 | ≈$17/mo | ≈$32/mo | ≈$60/mo |
| FTMO $100k funded, F3 | ≈$170/mo | **≈$320/mo** | **≈$600/mo** |
| FTMO 4 × $100k identical (the $400k cap) | ≈$680/mo | **≈$1,300/mo** | **≈$2,400/mo** |
| Per $100k *attempt* from purchase (P4, 24-month average, failures included) | ≈$93/mo | ≈$205/mo | ≈$414/mo |

**Reading.**
- What skill adds is the gap to the zero-edge control: **+$150/month per funded $100k at S = 0.5, +$430 at S = 1.0**.
- **Apply a 25% payout haircut** for counterparty and denial risk (economics pass).
- **FTMO's scaling plan** needs ≥ 10% net in 4 months. At 0.75–1%/day that is roughly a 20–30% chance per window at
  S = 1.0 and rare at S = 0.5 [D, rough]. **Treat it as an upside, not a plan.**

---

## 4. Recommendations

Each item is marked **(i) buildable inside the current guardrails** (it only shrinks or redistributes size) or
**(ii) OWNER**.

**R1 (ii, OWNER [spec]; built in R1.6). Make the risk unit a daily P&L-volatility budget, as a % of the account's
declared initial capital, per account and per stage.**
- **Prop challenge:** 1.0–1.25%/day, starting at 1.0%.
- **Prop funded:** min(1%/day, 0.10 × the cushion to the binding firm floor).
- **Personal:** 0.25%/day, rising to at most 0.5%/day only with a forward record of 2 or more years.
- **Why:** §3.2–3.5 and §3.9. P4 at S = 0.5 has EV $3,480 per $100k against −$632 at today's ceiling.
- **Counter-argument:** there is no edge yet (GAP-P12D-49), and sizing up loses the fee faster. **Sequence it after
  rung 1, never ahead of the edge** (GAP-P12D-61's own warning).

**R2 (ii, OWNER, guardrail). Per-account guardrail profiles for the notional caps.**
- Keep `cluster_cap_pct: 20` and `single_currency_delta_cap_pct: 30` for **personal** accounts. They are what bounds
  the CHF scenario at 7% NAV.
- For **prop** accounts, replace them with risk caps:
  - per cluster ≤ 50% of the daily vol budget;
  - per currency net ≤ 60% of the budget;
  - plus a hard **gross-notional ceiling** as the bug-catcher: ≤ 5× NAV for FX and ≤ 2× for indices and metals,
    inside FTMO Swing's and E8's 1:30 / 1:15 leverage.
- **The risk, stated quantitatively.** A 3× FX book through a 35% CHF-style gap loses ≈105% of NAV. On a personal
  account that is ruin. On a prop account it is the fee plus the lost record, and the firm absorbs the rest.
- The scenario-replay ceilings (`scenario_book.yaml`) would need per-account keying (GAP-P11I-10 already owns that).
- **Counter-argument:** the caps also catch runaway-sizing bugs, and a breached firm floor ends the forward record,
  which is the real asset. Hence the gross ceiling stays.

**R3 (ii, OWNER, guardrail). The VaR cap.**
- Today 3% NAV, 99%, undiversified, with σ from 10-second marks × √8640. That reads high during the London and New
  York opens, and a breach is a **human-only global HALT**.
- **Options:** (a) a daily-return σ estimator, which is a config `risk:` method change but changes when a guardrail
  fires, so OWNER; (b) a per-account cap consistent with the R1 budget, roughly 2.326 × budget × DR, where DR is the
  diversification ratio.
- **Risk:** a diversified VaR understates crisis correlation, so keep the undiversified sum as a *report* and gate on
  the diversified figure only on prop profiles.

**R4 (i). The daily-room guard in the firm's semantics.**
- **The rule:** daily vol budget ≤ room/z with **z = 4**, where room = min(equity − the firm's daily floor, equity −
  the firm's static floor), both measured per the corrected rulebook (balance at the reset).
- It only shrinks size, so it composes by min() with the §9.5 taper.
- **Value:** at H = 20 and 1%/day, EV per $100k rises from $632 to $2,922, and the funded 126-day breach rate falls
  from 83% to 12% (§3.4).
- **Counter-argument:** it de-risks after carried losses, which can cut a trend just before it pays. The evidence
  (Kaminski–Lo; Carver 2015) says that costs return for profitable systems. It is justified only by the barrier.
  Measure its cost with the zero-edge control.

**R5 (i). Cushion-proportional funded sizing**, c = 0.10/day of cushion, cap 1%/day, recomputed after every payout
(R6 of the economics pass).
- **Why:** the best PV with ≈1.5% 126-day breach at S = 0.5 (EXP3/4b).
- **Counter-argument:** cash lock near the floor. That is acceptable, because the alternative near the floor is
  ruin, and the zero-edge identity says it costs nothing in expectation.

**R6 (i). Headroom on hard caps.**
- The Governor should admit orders only to ≤ 90% of the cluster and currency caps, and to ≤ 80% of the VaR cap.
- Then mark drift and NAV losses cannot trip human-only global halts. Today the Governor checks entry notional and the
  Risk Monitor checks mark notional against current equity.
- **Verify first:** a regression test — admit at 19.9% NAV of EUR/USD, move the mark +1%, and assert no global HALT.

**R7 (ii, OWNER). Commit the corrected `ftmo` rulebook.**
- Static 10% on equity; daily 5% of initial below the 00:00 Europe/Prague balance; `account_class` for Swing.
- The schema supports it (GAP-P12D-54; tests `test_ftmo_day1_floor_is_95000_on_equity`,
  `test_ftmo_day2_floor_is_97000_after_a_102000_close`).
- Until it is committed, every FTMO simulation or demo is looser than the firm.

**R8 (ii, OWNER). The per-instrument 1% halt.**
- Rule whether it clears when the condition clears (ACIS-07 §5's text) or only by human resume (the code).
- If R1 runs multi-week holds at ≥ 0.25%/day per instrument, the human-only reading halts about a third of holds.
- The safe alternative inside the law: express the per-instrument limit as a *budget share* (≤ 1% NAV of open loss
  for a sleeve sized at ≤ 0.1%/day).
- **Counter-argument:** an instrument halt is a cheap safety stop. True, but only when someone is watching.

**R9 (ii, OWNER). Venue and size (R1-D14), ordered.**
1. While the demo proves plumbing, keep one minimum lot (master §5).
2. After rung 1, run **one FTMO 2-Step Swing $10k (€89)** at the R1 budget as the operational forward test, graded by
   ΔEV against the zero-edge control (GAP-P12D-62).
3. Then scale with **identical $100k accounts** up to the $400k cap, one combined book in each.
4. **Prefer FTMO 2-Step over E8 Pro for slow trend.** The 5% daily limit carries multi-day risk; the 2.5% one does not
   (§3.4). Consider E8 Pro only for intraday-flat sleeves.

- **Counter-argument:** four parallel $100k challenges put about €2,160 of fees at risk on one correlated path. Hence
  "after a forward record", not before.

**R10 (ii, OWNER, §14). Decide R1-D14's vol target with the drawdown-row coupling visible** (§3.7).
- At 10%/yr the drawdown row passes a true S = 0.5 about 69% of the time on 2 years and 11% on 10 years; at 20%/yr,
  11% and 0%.
- Alternatively, normalise the row to a declared reference vol.

**R11 (i). Report realised daily vol (% of initial) and the binding constraint on every run and every demo day.**
GAP-P12D-61 already asks for the first. The second extends master §10's take-rate attribution from "which gate zeroed
an order" to "which cap set the size".

**R12 (ii, OWNER, master §5). A "practice at budget" mode after rung 1.**
- A demo at one minimum lot cannot test the daily-room guard, carried open-P&L behaviour or the per-instrument halt.
- A practice account trading the full budget risks no money, only misreading.
- **Counter-argument:** the minimum-size rule exists to stop an unvalidated family earning a flattering record. Keep
  it until rung 1.

**What I do NOT recommend.**
- Raising risk above 1.25%/day in the challenge.
- Any catch-up or martingale escalation.
- Equity-curve filters.
- Constant high funded risk.
- Any change that makes a guardrail reachable by code.

---

## 5. Heavy Monte Carlo to run on the Google compute server (specification; not run here)

**Purpose.** Replace the indicative numbers in §3 with a decision-grade grid. Use Appendix A's simulator, extended as
below. Start with the economics pass's validated `propsim.py` as the reference oracle.

**Rulebooks.** Each exactly as in §2:
- **FTMO 2-Step Swing:**
  - the daily floor at the 00:00 Europe/Prague balance minus 5% of initial, on equity;
  - static 10% on equity;
  - 4 trading days, counted only on days with a trade;
  - reward on day 14 or later after the first trade, flat book, 80%, fee refunded;
  - **FTMO's 0.7% adjustment on non-USD realised P&L** (T&C 5.3.4).
- **FTMO 1-Step:** 3% daily; 10% EOD trailing that resets on reward; Best Day 50%; 90%.
- **E8 Pro:** 2% a day counted toward the target; 2.5% daily on equity *or* balance; 8% static moving to initial at
  the first payout; daily payouts of 50% at ≥ 1%; 80%.
- **E8 One:** 6% target; 3% daily; 4% closed-balance dynamic floor; 40% Best Day on payouts; ±5-minute news ban in
  performance.

**P&L input, two modes.**
- **(a) Synthetic.** N ∈ {2, 4, 8} sleeves; H ∈ {1, 3, 10, 20, 60} days.
  - Exits either random or **trend-like**: close when the forecast's sign flips, modelled as an adverse excursion of
    1.5–3σ√h. That is the counter-argument case of §3.4.
  - Shocks: t(4) × GARCH(1,1) vol, 1%/day 4σ jumps, 0.1%/day 6σ adverse gaps, Monday gaps ×2.
- **(b) Bootstrap.** A stationary block bootstrap (mean block 20 days) of **R1 RSIM's per-day realised and unrealised
  P&L per instrument**, out of sample only.
  - **RSIM must export the realised/unrealised split first.** It is an [impl] prerequisite.
  - Every run is a look, so it is counted against the look budget.

**Policies.**
- Challenge k ∈ {0.25, 0.5, …, 1.75}%/day.
- Guard z ∈ {none, 3, 4, 5}.
- Funded:
  - constant k ∈ {0.25, …, 1.5}%;
  - cushion-proportional c ∈ {0.05, 0.10, 0.15, 0.25} with cap ∈ {0.5, 0.75, 1.0}%;
  - FTMO reward timing: every 14 days, or when profit ≥ {2, 4, 6}%;
  - E8 request threshold ∈ {1, 3, 6, 10}%.

**Edge.**
- S ∈ {−0.5, −0.25, 0, 0.25, 0.5, 0.75, 1.0, 1.5}.
- S uncertainty, sd ∈ {0, 0.5}.
- **A zero-edge control for every cell:** the same policy and seeds with S = 0. That gives ΔEV.

**Monte Carlo design.**
- 2,000 paths per cell for the scan, with common random numbers (seed = hash(venue, H, S, mode)).
- Then **20,000 paths** for the ~20 finalist cells.
- Horizon 5 years, 4 sub-steps a day.
- Discount δ ∈ {0.10, 0.25, 0.50}; payout haircut h ∈ {0, 0.25}.

**Metrics.** Each with a 90% interval:
- EV per attempt at A ∈ {$10k, $100k} at the firm's fee;
- **ΔEV against the zero-edge control**;
- P(pass ≤ 60 / 126 / 252 trading days) and median days;
- P(funded breach ≤ 126 days);
- E[payouts per year] and $/month at A ∈ {$10k, $100k, $400k};
- the share of deaths on the daily limit against the static limit;
- P(any payout ≤ 6 months).

**Validation gates, before any result is read:**
1. Reproduce the closed forms in §3.1 to within 1 point.
2. Reproduce the zero-drift identity (lifetime payouts = split × L) to within 2%.
3. With H = 1 and D = ∞, reproduce the economics pass's survival-first EV to within 10%.

**Budget.** About 2 venues × 3 H × 8 S × 2 S-sd × 12 policies ≈ 1,150 cells × 2,000 paths × 1,260 days × 4 ×
N sleeves. That is ≈ 2–4 × 10¹³ draws, about 6–10 hours on 16 vCPU; then the finalists. Keep the server STOPPED
otherwise.

---

## 6. Ledger items this pass should generate (proposed; no IDs; for the lead to verify and triage, A6)

1. **[NEW, high] RSIM's vol-target book cannot be traded under the notional caps.**
   - At 10%/yr, a 7-pair Carver FX book holds 0.34–0.98× NAV per pair, against a 0.20× cluster cap.
   - The graded book is not the tradeable book: the GAP-P12D-36 class.
   - R1.6 must either size under the caps (≈0.16%/day for 2 pairs) or wait for R2 (OWNER).
   - Links GAP-P12D-61 and -101.
2. **[NEW, medium] Mark-to-market drift can trip a human-only global HALT.**
   - The Governor admits orders on entry notional; the Risk Monitor tests `max_cluster_pct` on mark notional and
     current equity.
   - Fix (i): headroom in the Governor (R6). Write a repro test first.
3. **[NEW, high] The PropEV daily limit must be balance-anchored, with carried open P&L.**
   - The 2026-09-24 simulator's equity anchor overstates EV for multi-day holds by up to ≈6× (§3.4).
   - RSIM must export each day's realised and unrealised P&L.
   - Links GAP-P12D-62 and -54.
4. **[NEW, medium] The per-instrument halt's resume semantics.**
   - Code: human-only. ACIS-07 §5: "clears when its condition clears or by human resume per policy".
   - OWNER ruling (R8).
5. **[NEW, medium] §14's 15% max-drawdown row is a hidden vol cap** (§3.7). It belongs with R1-D14 (GAP-P12D-101).
6. **[UPDATE GAP-P12D-54]** Re-verified on 2026-10-01: FTMO's page (modified 2026-09-30) still measures max loss on
   equity. The `ftmo` entry is still balance/EOD.
7. **[UPDATE GAP-P12D-61]** Add the binding-constraint ranking of §1.2: base unit → notional caps → VaR →
   per-instrument halt. The base unit is not the only wall.
8. **[UPDATE prop-venue memory, OWNER]** E8 Pro is a poor venue for slow trend: 2.5% daily, balance-anchored, and the
   floor moves to initial at the first payout.

## 7. What I could not verify
- **FTMO's Swing price.** The page data carries Standard prices; the tooltip says rounding "applies to FTMO Standard
  accounts only". I assumed Swing costs the same (venue pass: €89 for $10k).
- **FTMO's 14-day reward claim requires all positions closed.** Seen only through the search index of FTMO's FAQ; the
  page was not fetched directly. Graded (a) via the index.
- **The currency of FTMO's "average reward" figures, and their population.** Not stated (c).
- **E8 One pricing and E8's server time zone.** Not fetched.
- **The R1 book's real carried open P&L.** Not measured; it drives §3.4 and needs RSIM's realised/unrealised split.
- **1-minute ATR levels for the demo's per-trade risk.** Assumed at 1–2 pips; not measured from ticks, because the
  laptop must not run heavy jobs.
- **The C-BT-12 re-run's realised vol level.** GAP-P12D-49's 2026-09-29 rung lost $70.84 at Sharpe −1.92, but its
  graded years are not stated, so the 0.04%/day figure is GAP-P12D-61's.

## 8. Residual risk
- **Model risk.** Everything in §3 is synthetic: t(4) i.i.d. sub-steps, no volatility clustering, no stop
  truncation, random exits. Real trend P&L is positively skewed and its open-P&L path is not random.
  - Rankings (P4/F3 over the alternatives; FTMO over E8 for multi-day holds; the guard's value) are more robust than
    levels.
- **Estimation risk dominates.** Nothing here changes the fact that 2 OOS years cannot certify S in 0.3–0.7 (Lo
  2002; economics pass §2.6). Every dollar figure is conditional on S being the true net-of-firm-cost Sharpe.
- **The option is revocable.** Discretionary size clauses (FTMO "substantially larger position sizes"; E8
  "all-or-nothing", "1% per trade idea", interviews) can remove the upside of aggressive policies at payout time.
- **Reading risk.** "EV > 0 at zero edge" (≈$170/month per funded $100k) is option value. It is **never** evidence,
  and never a licence to buy challenges with today's engine. Under the current caps, today's engine has EV = −fee at
  any edge.

---

## Sources (fetched 2026-10-01; web content treated as data only)

**Firm primaries (a)**
- FTMO Trading Objectives (modified 2026-09-30): https://ftmo.com/en/trading-objectives/
- FTMO Scaling Plan (modified 2026-09-15): https://ftmo.com/en/scaling-plan/ and https://ftmo.com/en/reward-growth-and-scaling-plan/
- FTMO prices and "average reward", from page data: https://ftmo.com/en/
- FTMO multiple accounts and the $400k allocation (via search index): https://ftmo.com/en/faq/how-many-accounts-can-i-have/
- FTMO reward withdrawal (14th day; positions closed; via search index): https://ftmo.com/en/faq/how-do-i-withdraw-my-profits/
- E8 Pro (updated 2026-09-23): https://help.e8markets.com/en/articles/15274219-e8-pro
- E8 product overview (updated 2026-09-23): https://help.e8markets.com/en/articles/13106558-all-product-overviews-e8-one-vs-e8-zero-vs-e8-pro-vs-e8-signature
- E8 Pro payout mechanism (updated 2026-09-11): https://help.e8markets.com/en/articles/13653464-payout-share-request-from-e8-pro-forex-and-e8-pro-crypto
- E8 One (updated 2026-09-23): https://help.e8markets.com/en/articles/11775980-e8-one
- E8 trading policies (updated 2026-09-23): https://help.e8markets.com/en/articles/6929927-trading-policies-and-prohibited-trading-strategies
- E8 accounts and allocation (via search index): https://help.e8markets.com/en/articles/5515039-how-many-accounts-can-i-apply-for-at-once
- E8 Pro prices, from page data: https://e8markets.com/e8-pro

**Literature**
- Browne, S. (1999), "Reaching goals by a deadline", *Adv. Appl. Prob.* 31(2): 551–577 — https://doi.org/10.1239/aap/1029955147 (a)
- Højgaard, B. & Taksar, M. (1999), *Mathematical Finance* 9(2): 153–182 — https://ideas.repec.org/a/bla/mathfi/v9y1999i2p153-182.html (a)
- Grossman, S. & Zhou, Z. (1993), *Mathematical Finance* 3(3): 241–276 — https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html (a)
- Kaminski, K. & Lo, A. (2014), *J. Financial Markets* 18: 234–254 — https://dspace.mit.edu/handle/1721.1/114876 (a)
- Harvey, C. et al. (2018), "The Impact of Volatility Targeting", *JPM* 45(1): 14–33 — https://scholars.duke.edu/publication/1370354 (a; findings via the abstract and summaries)
- Cederburg, O'Doherty, Wang & Yan (2020), *JFE*: 95–117 — https://www.lehigh.edu/~xuy219/research/COWY.pdf (a)
- MacLean, Thorp & Ziemba, "Good and bad properties of the Kelly criterion" — https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf (a)
- Hall, N. (2026), arXiv 2609.14859 — https://arxiv.org/abs/2609.14859 (b, preprint)
- Carver, R. (2020), "How much risk should we take?" — https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html (b)
- Carver, R. (2015), "Random data: Evaluating 'Trading the equity curve'" — https://qoppac.blogspot.com/2015/11/random-data-evaluating-trading-equity.html (b)

**Repo and data**
- [repo] `config/guardrail_limits.yaml`, `config/system_config.yaml`, `config/platform_rules.yaml`,
  `config/instruments.yaml`, `config/scenario_book.yaml`
- [repo] `core/governor/{capital_governor,exposure,factors,units}.py`, `core/risk/{guardrails,monitor,exposure_metrics,drawdown_series,halt_ledger}.py`,
  `core/runtime/{portfolio,wiring}.py`, `tests/backtest/{rsim,report}.py`
- [repo] `ACIS_SPEC.md` §5, §6, §9.5, §14, §17; `specs/ACIS-05`, `ACIS-07`, `ACIS-13`; `KNOWN_GAPS.md`
  (GAP-P12D-49/54/56/57/59/61/62/101/129); `OPERATIONS_LEDGER.md` OPS-0001
- (b) `data/macro/ecb_exr.csv`: ECB reference rates 2012–2025, used for the FX vol inputs

## Method note
- **Web budget.**
  - **15 of 45 WebSearch calls**, none in "extended" mode.
  - About 9 WebFetch calls.
  - E8's help centre returned HTTP 403 to WebFetch, so I fetched E8 pages and FTMO's homepage price data with a plain
    `curl` and read the embedded text and JSON.
  - No account was created and nothing was submitted.
- **Repo.** Read-only. The only repo file written is this report. No git commands.
- **Compute.** Light local Python only: each run ≤ ~100 s wall time on the laptop, all synthetic, except one
  read of the 470 KB ECB CSV.
  - Scripts live in the session scratchpad: `riskstack.py`, `propsim2.py`, and EXP1–EXP7 outputs (`exp*.out`).
  - **The scratchpad is temporary.** The simulator's full source is Appendix A, so the lead can rerun it on the
    Google server.
- **Two process slips, disclosed.**
  - An accidental `du` over `data/` was started and stopped after about 2 minutes.
  - A first vol script had an O(n²) loop and was stopped and rewritten.
  - Neither touched market tick data or wrote anything.

---

## Appendix A — `propsim2.py` (the simulator behind §3; validated as in §3.1)

```python
"""Lean prop-account Monte Carlo (synthetic only). Units: fraction of the initial balance A.
Daily limit anchored on the BALANCE at the day reset; open P&L carried by sleeves closing at rate 1/H;
E8 Pro one phase with a 2%/day count cap, 2.5% daily, 8% static moving to initial at the first payout,
payouts = 50% of total profit x split; per-path Sharpe draws; optional room guard k <= room/z."""
import numpy as np

N_SLEEVES, M = 2, 4
DAYS = 504

VENUES = {
    "FTMO2": dict(targets=(0.10, 0.05), min_days=4, D=0.05, L=0.10, split=0.80,
                  fee=632.0 / 100000, refund=True, payout="ftmo"),
    "E8PRO": dict(targets=(0.08,), min_days=1, D=0.025, L=0.08, split=0.80,
                  fee=488.0 / 100000, refund=False, payout="e8pro", daily_cap=0.02),
}

def run(venue, S, k_ch, k_f, H=1, n=1500, S_sd=0.0, fat=True, c_cush=None, guard_z=None,
        e8_req=0.06, seed=1, delta=0.25, fee=None, start_funded=False, days=None):
    v = VENUES[venue]
    fee = v["fee"] if fee is None else fee
    rng = np.random.default_rng(seed)
    mu_day = (S + S_sd * rng.standard_normal(n)) / np.sqrt(252.0)
    p_close = min(1.0, 1.0 / H)
    nphase = len(v["targets"])
    tgt_arr = np.array(list(v["targets"]) + [np.inf, np.inf])
    phase = np.full(n, nphase if start_funded else 0)
    bal = np.ones(n); opl = np.zeros((n, N_SLEEVES)); counted = np.zeros(n)
    dip = np.zeros(n, int)
    floor_s = np.full(n, 1.0 - v["L"])
    pass_day = np.full(n, -1); dead_day = np.full(n, -1); kind = np.zeros(n, int)
    fstart = np.full(n, 0 if start_funded else -1)
    paid = np.zeros(n); paid1 = np.zeros(n); paid_disc = np.zeros(n); refund_disc = np.zeros(n)
    first_paid = np.zeros(n, bool); last_pb = np.ones(n)
    sq = 1.0 / np.sqrt(M)
    for d in range(days or DAYS):
        alive = phase >= 0
        if not alive.any():
            break
        funded = phase == nphase
        eq0 = bal + opl.sum(1)
        k = np.where(funded, k_f, k_ch).astype(float)
        if c_cush is not None:
            k = np.where(funded, np.minimum(k_f, c_cush * np.maximum(eq0 - floor_s, 0.0)), k)
        dfloor = bal - v["D"]
        if guard_z is not None:
            room = np.maximum(np.minimum(eq0 - dfloor, eq0 - floor_s), 0.0)
            k = np.minimum(k, room / guard_z)
        ks = (k / np.sqrt(N_SLEEVES))[:, None]
        drift = (k / N_SLEEVES)[:, None] * (mu_day[:, None] / M)   # total drift = k*S/sqrt(252)
        z = (rng.standard_t(4, size=(M, n, N_SLEEVES)) / np.sqrt(2.0)) if fat else rng.standard_normal((M, n, N_SLEEVES))
        start_eq = eq0
        hit = np.zeros(n, bool)
        tgt = tgt_arr[np.where(phase < 0, nphase + 1, phase)]
        can_hit = alive & (phase < nphase) & (dip + 1 >= v["min_days"])
        for j in range(M):
            act = alive & ~hit
            opl += np.where(act[:, None], drift + ks * z[j] * sq, 0.0)
            eq = bal + opl.sum(1)
            dead = act & ((eq < dfloor) | (eq < floor_s))
            if dead.any():
                kind[dead] = np.where(eq[dead] < floor_s[dead], 2, 1)
                dead_day[dead] = d; phase[dead] = -1; opl[dead] = 0.0
                alive = alive & ~dead
            prog = counted + np.minimum(eq - start_eq, v["daily_cap"]) if venue == "E8PRO" else eq - 1.0
            h = alive & can_hit & ~hit & (prog >= tgt)
            if h.any():
                bal[h] = eq[h]; opl[h] = 0.0; hit |= h
        alive = phase >= 0
        close = np.ones((n, N_SLEEVES), bool) if p_close >= 1.0 else rng.random((n, N_SLEEVES)) < p_close
        bal = bal + np.where(close, opl, 0.0).sum(1); opl = np.where(close, 0.0, opl)
        if venue == "E8PRO":
            counted = counted + np.where(alive & (phase < nphase),
                                         np.minimum(bal + opl.sum(1) - start_eq, v["daily_cap"]), 0.0)
        dip[alive] += 1
        adv = alive & hit
        if adv.any():
            phase[adv] += 1
            bal[adv] = 1.0; opl[adv] = 0.0; counted[adv] = 0.0; dip[adv] = 0
            floor_s[adv] = 1.0 - v["L"]
            newly = adv & (phase == nphase)
            pass_day[newly] = d; fstart[newly] = d; last_pb[newly] = 1.0
        funded = (phase == nphase) & ~adv
        disc = np.exp(-delta * d / 252.0)
        if v["payout"] == "ftmo":
            due = funded & (d - fstart >= 10) & ((d - fstart) % 10 == 0)
            if due.any():
                eqd = bal + opl.sum(1)
                pos = due & (eqd > 1.0)
                pay = np.where(pos, v["split"] * (eqd - 1.0), 0.0)
                refund_disc += (pos & ~first_paid & v["refund"]).astype(float) * disc
                paid += pay; paid_disc += pay * disc
                if d < 252: paid1 += pay
                first_paid |= pos
                bal[pos] = 1.0; opl[pos] = 0.0
        else:
            eqd = bal + opl.sum(1)
            due = funded & (eqd - 1.0 >= e8_req) & (eqd - last_pb >= 0.01)
            if due.any():
                prof = eqd - 1.0
                pay = np.where(due, v["split"] * 0.5 * prof, 0.0)
                paid += pay; paid_disc += pay * disc
                if d < 252: paid1 += pay
                bal[due] = 1.0 + 0.5 * prof[due]; opl[due] = 0.0
                last_pb[due] = bal[due]
                floor_s[due & ~first_paid] = 1.0
                first_paid |= due
    passed = pass_day >= 0
    return dict(p_pass=passed.mean(),
                med_pass=float(np.median(pass_day[passed])) if passed.any() else float("nan"),
                p_pass_126=(passed & (pass_day < 126)).mean(),
                dd=(kind == 1).mean(), ds=(kind == 2).mean(),
                # NB: with start_funded=True this is a COUNT; divide by n
                fb126=((fstart >= 0) & (dead_day >= 0) & (dead_day - fstart < 126)).sum() / max(passed.sum(), 1),
                paid1=paid1.mean(), paid2=paid.mean(), pay_disc=paid_disc.mean(),
                refund_disc=refund_disc.mean(),
                ev=paid_disc.mean() - fee * (1.0 - refund_disc.mean()), p_pay=(paid > 0).mean())

def ev_at(r, A, fee_usd):
    return A * r["pay_disc"] - fee_usd * (1.0 - r["refund_disc"])
```

**Experiment calls**, all fat-tailed:

| Experiment | Call |
|---|---|
| EXP1 | `run(venue, 0.5, k, k, H∈{1,20}, n=1000, seed=11)` |
| EXP1b | as EXP1, plus `guard_z∈{3,4}` and `H=5` |
| EXP2 | `run("FTMO2", S, k_ch, k_f, H=5, n=900, seed=21, guard_z=4, c_cush=…)` |
| EXP3 | `run("FTMO2", S, 0.01, k_f, H=5, n=600, seed=31, guard_z=4, c_cush=…, start_funded=True, days=1008, fee=0)` |
| EXP4 | as EXP2 and EXP3 with `S_sd=0.5` |
| EXP6 | P2 at S ∈ {0.5, 0.71} |
| EXP7 | `run("FTMO2", S, 0.0125, 0.010, H=5, n=900, seed=21, guard_z=4, c_cush=0.10)` |
| EXP5 | separate: t(4) additive daily P&L, 2,000 paths, max drawdown ≤ 15% |
