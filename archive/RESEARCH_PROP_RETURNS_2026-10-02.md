# RESEARCH — What funded prop traders really make per week, and what ACIS should aim for (PROPRETURNS, 2026-10-02)

**Who asked, and why.** I am PROPRETURNS, one of five research agents the owner launched on 2026-10-02. The owner's
words: *"lets look at what prop firm traders are realistically making per week and aim for that."* The lead's venue
pick is E8 One on cTrader with the swap-free add-on, at about $6–10k. FTMO, FundedNext and The5ers are the reference
firms.

**Status.** This is a finder's report (A5): evidence to weigh, not an instruction (A9). Nothing here binds until the lead
verifies it (A6). Nothing here changes a guardrail. Where a recommendation would need a guardrail or spec change, it is
marked **OWNER**.

**Builds on, does not redo:**
- `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`: the first-passage maths, the zero-edge identity, the PropEV objective;
- `archive/RESEARCH_PROP_VENUES_2026-09-24.md`: the automation filter (only FTMO and E8 qualify);
- `archive/RESEARCH_SIZING_AGGRESSION_2026-10-01.md`: the risk stack, the balance-anchored daily limit, the FTMO challenge band.

§6 verifies or refutes each of their claims that this pass touched.

**Method.**
- **WebSearch: 18 of 35 calls.** I also made about 12 WebFetch calls, and fetched primary pages with `curl` (FTMO, E8,
  FundedNext, Rise, Darwinex, Topstep, arXiv). From each page I read the text, the embedded page data, or the PDF.
- **Dates.** Every web source was read on **2026-10-02**. Where a page carries its own `dateModified`, that date is
  given too.
- **One small synthetic Monte Carlo** of E8 One's rules, using numpy on synthetic P&L only, as one process. The
  validation run took 88 s and the grid took 112 s. I disclose this because the brief asked for no heavy computation.
  Re-run it at scale on the Google server before using it to decide anything. The source is in Appendix A.
- **Hard rules kept:** no agents launched, no accounts created, no forms submitted, no git commands. The only repo
  file written is this report.

**Grades.**
- **(a)** A firm's own published statistics or primary document, a regulator, or audited/filed accounts. A firm's
  statistic is graded **(a) as a record of what the firm says**. It is only **(c)-strength as population evidence**
  when it has no denominator or counts only winners (survivorship). I flag every such case.
- **(b)** Credible industry analysis or trade press with a stated method.
- **(c)** Blog, forum, affiliate or marketing material, or a search-engine summary. Never treated as fact.
- **[D]** Derived here. The arithmetic is shown, or it comes from the validated simulator in Appendix A.

---

## The plain answer to the owner

**Realistically, most prop traders make nothing.**
- 5–18% of buyers pass an evaluation.
- Only 20–45% of funded traders ever receive a payout.
- So only about **1–7% of FX buyers** are ever paid (17% at one unusually transparent futures firm).
- In 2023 FTMO paid its traders back **about 37 cents per dollar** of its revenue, most of which is challenge fees.

**The ones who do get paid take about 2–6% of the account per payout,** usually 3–6 weeks after funding:
- E8 One's own average payout is 5–6% of the account.
- FTMO's average reward is about 6%.
- E8's daily-payout product, E8 Pro, averages 1.3–2.7% per payout.

**While they are on a winning run, that is roughly 0.5–1.5% of the account a week.** That is a *survivor's* number:
it is measured only on the accounts that happened to win.

**The durable top tier makes about 1.5–3% a month, i.e. 0.35–0.7% a week,** with 5–6% drawdowns along the way. This
tier is the traders the firms showcase and scale, and the winners of Darwinex's allocation programme. FTMO's own bar
for scaling a trader up is 10% in 4 months, about 0.55% a week.

**Averaged over a funded account's whole life,** including the payouts that never come because the account breached,
a trader with a genuine Sharpe of 0.5–1.0 extracts only **about 0.03–0.12% of the account per week** under E8 One's
rules [D, synthetic].

**What ACIS should aim for:**
- **Target:** an expected **0.2% of the account per week** (≈0.85% a month, ≈10% a year), in a range of **0.1–0.3% a
  week**.
- **Risk:** a daily P&L volatility of **0.75–1.0% of the initial balance**, on **E8 One's 8% drawdown option, not the
  preset 4%**.
- **Edge needed:** an out-of-sample net **Sharpe of about 0.65–0.85**.
- **Break-even:** below a Sharpe of roughly 0.3 (8% option) to 0.65 (4% preset), E8 One loses money after the fee [D].

**Do not aim for the 0.5–1.5% a week the survivors show.** At the risk E8 One's drawdown line allows, that needs a
Sharpe of 2–4. No evidence says ACIS has it: its own positive control still loses (GAP-P12D-49). Chasing that rate with
size is how most funded accounts get breached.

**Two cautions.**
1. **A week is the wrong yardstick.** Even a Sharpe-1.0 strategy loses money in about 44% of weeks. Judge ACIS over 6–12
   months, against a zero-edge control.
2. **On a $10k account, 0.2% a week is $20 a week before the split.** The money comes from allocation, meaning bigger
   and more accounts once the edge is proven. It does not come from more risk per account.

---

## Executive summary

1. **(a/b) The funnel.**
   - **Pass rates:**
     - E8 17.7% (its own disclaimer, Jan 2023–Mar 2024);
     - The Funded Trader 5–10%;
     - FPFX dataset 14%;
     - FTMO 9–10%, a firm citation via Hall;
     - Topstep (futures) 16.8% of accounts.
   - **Funded traders ever paid:**
     - The Funded Trader ~20%;
     - Topstep 33.3%;
     - MyFundedFutures 28.6% (via Hall);
     - FPFX 45%.
   - **FTMO's 2023 economics:** rewards were $75.2M against revenue of $203.9M, a ratio of **0.37**.
   - **Survivorship:** no firm publishes a funded-account survival curve.
2. **(a, survivorship-heavy) The paid minority, from FundedNext's own February 2026 payout report.** It covers 8,340
   traders and 13,712 payouts. The CFD traders who got paid:
   - median payout **$567**, mean **$1,119**;
   - median **1.5 trades a day**, and 83.6% traded 1–2 a day;
   - median win rate **50%**, reward-to-risk **1.49**, profit factor **1.47**;
   - median **2 instruments**;
   - **82.1%** had at least one losing week;
   - median **28 days** to the first payout.

   Accounts last only briefly. **60%** of paid accounts had been funded within the last 30 days, and only **415 of
   10,346** (4%) had been active more than 6 months.
3. **(a) E8 publishes its payouts.** Its page data, read 2026-10-02:
   - 23,850 payouts totalling $78.97M since December 2021;
   - September 2026: **809 payouts, $1.39M, an average of $1,723**;
   - **E8 One's average payout runs 4.7–6.8% of the account for $25k–$500k accounts (9.1% at $10k)**;
   - E8 Pro (daily payouts) averages 1.3–2.7%.

   These are averages over paid events only. E8 publishes no denominator.
4. **(a, selected) The durable top tier.**
   - FTMO's showcased traders make 2–3% a month at 0.13–1% risk per trade (prior pass).
   - FTMO's scaling bar is 10% net in 4 months.
   - Darwinex's DarwinIA SILVER allocation recipients (the top 10–24% of 3,365–9,092 participants) show a median
     6-month return of **9.4–11.2%** with a median 6-month drawdown of **5.0–5.75%**, in five recaps from 2023 to 2026.
     That is **≈0.35–0.41% a week** at a normalised risk of roughly 0.4–0.9% a day, and these winners were selected on
     that same window.
   - E8 says *"The most successful traders on E8 risk between 1–1.5% per trade idea."*
5. **[D] The arithmetic that decides the target.**
   - The expected weekly return is **0.315 × k × S**, where k is daily P&L volatility in % of the initial balance and S
     is the annual Sharpe.
   - So 0.2% a week needs S ≈ 0.63 at 1%/day, or S ≈ 0.85 at 0.75%/day.
   - 0.5% a week needs S ≈ 1.6 at 1%/day.
   - 1% a week needs S ≈ 3.2 at 1%/day.
   - The weekly noise is ≈ 2.24 × k, about 7–14 times the weekly mean, so **≈44–47% of weeks lose money even with a real
     edge**.
6. **[D, new] Size the risk to the cushion, not to a weekly figure.**
   - The ratio of the loss line L to the daily volatility k decides both the pass odds and the funded lifetime. At zero
     edge, a funded account that withdraws everything above its floor lasts **(L/k)² trading days** on average:
     - E8 One's 4% option at 1%/day lasts **16 days**;
     - the 8% option at 0.75%/day lasts 114 days.
   - Run **L/k ≈ 8–10**. That means:
     - k ≈ 0.4–0.5%/day on E8 One's 4% preset;
     - **0.8–1.0%/day on its 8% option**;
     - 1.0–1.25%/day on FTMO's 10% static line, which matches the SIZING pass's band.
7. **[D, new] E8 One's geometry is harsher than the static-floor firms the earlier passes modelled.**
   - The target is 1.5 × L; the daily limit is 0.66 × L from the day's starting balance.
   - The drawdown floor trails the highest *closed* balance until it locks at the initial balance. After a payout the
     floor does not reset. There is a 40% best-day rule on payouts, and **no fee refund**.
   - The zero-edge pass probability is ≈ e⁻¹ × ⅔ ≈ 0.245 in closed form (0.26–0.29 simulated).
   - A zero-edge funded account is worth only about 0.37–0.5 × L, not L.
   - **So on E8 One the zero-edge control is −EV after the fee:** −$49 to −$92 per $10k attempt. The break-even edge
     rises to S ≈ 0.3 (8% option) to 0.65 (4% preset), against ≈ −0.4 to 0 for the static floors. That is good for
     honest grading, and bad for a weak edge.
8. **(a) What the firms forbid, as it bears on an automated engine.**
   - **E8:** any EA, but one strategy per user; ≤ 50% of trades held under one minute; 2,000 server requests a day; 100
     open orders; no hedging across accounts; no "all-or-nothing" (risking the whole daily drawdown on one trade). E8
     may de-risk a flagged trader to 1% per trade idea.
   - **E8 One performance accounts:** no opening, closing, **stop-loss or take-profit** fills from 5 minutes before to
     5 minutes after high-impact news.
   - **FTMO:** 2,000 server requests a day; no "ultra-high-speed tools"; no "gap trading"; no "substantially larger
     position sizes".
   - **FundedNext:** no EAs at all on cTrader, and MT4/MT5 only below $50k.
   - **No firm publishes EA-versus-manual outcomes.** The "EAs pass twice as often" claim comes from an EA vendor (c).
9. **[D] What the target means in money, at E8 One with the 8% option, k = 0.75–1.0%/day, S = 0.5–1.0:**
   - EV per $10k attempt is **+$34 to +$274**, and per $100k attempt **+$0.9k to +$3.3k**, assuming the preset price
     applies to the 8% option, which is unverified;
   - ΔEV against the zero-edge control is +$90 to +$323 per $10k attempt;
   - the trader's lifetime-average payout is **0.06–0.12% of the account per funded week**.
10. **[D] Sizing on $10k with 0.01-lot minimums.**
    - At 0.75%/day, each of 13 FX pairs carries about $8–12 a day of P&L volatility. One minimum lot carries $4–7, so
      the book holds **1–2 lots per pair, up to 3–4 at full forecast**: workable, if coarse.
    - **Gold is infeasible at $10k.** One 0.01 lot is 1 oz, about $4,566 of notional and ≈ $55–70 a day of volatility,
      which is the whole budget.
    - **Today's guardrail caps would bind long before this budget.** Cluster 20% and currency 30% of NAV admit about
      one lot per cluster on $10k (GAP-P12D-142). The ratified-later per-account profiles are the precondition
      (**OWNER**, after rung 1).

---

## 1. What funded prop traders really earn (question 1)

### 1.1 The funnel: who passes, and who is ever paid

| Source | Grade | Population | Pass | Funded traders paid | All buyers paid |
|---|---|---|---|---|---|
| **E8 Markets**, footer disclaimer on e8markets.com/e8-one | (a) | "customer pass rate from January 1, 2023, to March 1, 2024 … for those who traded at least once during this period and obtained an E8 Trader Account" | **17.7%** | — | — |
| **The Funded Trader**, via Finance Magnates 2025-03-18 | (b), a firm statement in trade press | FX/CFD | **5–10%** | **"only about 20%"** | **"1% to at most 2%"** |
| **FPFX Technology**, via Finance Magnates 2024-09-18 (prior pass) | (b), vendor dataset, unaudited | 300k accounts, 10 firms, mostly FX | 14% | 45% | ~7%; average payout 4% of plan size |
| **Topstep** risk disclosure, updated 2025-09-25 (re-read 2026-10-02) | (a) | futures, calendar 2025 | 16.8% of Combines (accounts); 51.8% of persons funded at least once | **33.3% of persons** | ≈17% of persons (51.8% × 33.3%) |
| MyFundedFutures, via Hall Table 21 | (b) via (b) | futures | — | 28.6% | — |
| Swiset study, via Hall | (b) via (b) | ~10,000 traders, 11 regions | 1-phase 20.3%; 2-phase 11.8% | — | — |
| ATFunded, firm social disclosure, June 2025, via Hall and Finance Magnates | (b) | FX | ~6% overall to funded | — | — |
| Velotrade rulebook review of 6 firms, via Hall | (b) via (b) | mixed | — | — | 7% of buyers |
| FTMO, "firm citation", via Hall | (c) as a primary | FX, 2-Step | 9–10% | — | — |

**The firms' own money flows (a/b).**
- **FTMO, 2023.**
  - Its blog says it paid **$75,170,210** in rewards in 2023: 1,713 payouts a month on average, so an average payout
    of **$3,376**.
  - TradeInformer, reading FTMO's filed 2023 accounts, gives revenue of **$203.9M**. Finance Magnates gives turnover of
    "almost CZK 5 billion (over $213 million)".
  - **So rewards were ≈ 35–37% of revenue [D].** The average buyer gets back about a third of the fee: the negative
    population drift the economics pass inferred.
- **FTMO today.** Its homepage, modified 2026-09-22, says **"$650M+ Paid in rewards"**. Finance Magnates had $450M on
  2025-09-29, so FTMO paid roughly $200M in the year to September 2026.
- **E8.** Its page data shows **$78.97M over 23,850 payouts** since December 2021, and **$19.1M over 7,684 payouts in
  the last year**. That is roughly a tenth of FTMO's or FundedNext's recent flow; FundedNext paid $15.19M in February
  2026 alone.

**What the funnel means.** The paid fraction is small at every firm and on every denominator. Hall (2026, (b)) puts it
plainly:
> "Several publish cumulative payout totals … which are numerators without denominators and cannot be converted into a
> rate. The asymmetry is systematic: π is disclosed and marketed, β is disclosed rarely and marketed never."

Where the funnel breaks also matters. Hall collects two independent failure attributions: drawdown mechanics cause the
large majority of failures (45–55% daily loss, 20–30% trailing drawdown), and **"Missing the profit target is not a
leading cause of failure anywhere in the published data."** Traders fail by blowing the loss line, not by failing to
make money fast enough. That is the core argument for the risk budget in §5.

### 1.2 Payout size and frequency: the distribution, not the best case

**FundedNext Payout Report, February 2026** (published 2026-03-11; (a) as a document, survivorship-heavy). It is the
only full payout distribution any firm in scope has published:

| Measure | Value |
|---|---|
| Paid | **$15.19M to 8,340 traders**, 13,712 transactions on 10,346 funded accounts |
| Payout size | **median $567, mean $1,119**; 54.4% of the *volume* lay in $1,000–5,000; the largest was $60,580 |
| Repeat payouts | 50.1% of paid accounts had been paid before; 1,609 transactions were a 5th-or-later payout |
| Long-lived payers | 284 traders with 25+ lifetime payouts took $2.37M (15.8% of the month); 55 traders have 60+ |
| Account age at payout | **60% funded within the last 30 days**; 26% 1–3 months; 14% more than 90 days; **415 accounts more than 6 months** |
| Time to first payout (CFD) | **median 28 days**; 20.3% within 14 days; 18.3% after 90 days or more |
| Lifetime | $271.4M over 205,380 transactions, a mean of **$1,321** [D] |
| Caveat | Finance Magnates notes "An independent blockchain analytics platform tracked approximately $2.2 million less in payouts during the same period" (b). FundedNext promised monthly reports; the March–September 2026 URLs return 404 (checked 2026-10-02) |

**E8's own page data** (e8markets.com/e8-one and /e8-pro, fetched 2026-10-02; (a) as a document, paid events only).
- **Average payout by product and account size, as a % of account [D from (a)]:**

  | Product | $5k | $10k | $25k | $50k | $100k | $200k | $500k |
  |---|---|---|---|---|---|---|---|
  | **E8 One** | 6.6% | **9.1%** | 6.8% | 6.0% | **5.8%** | 4.9% | 4.7% |
  | E8 Pro (daily payouts, minimum 1%) | 2.7% | 1.9% | 1.3% | 1.6% | 1.6% | 2.1% | 1.3% |
  | E8 Signature (capped) | — | — | 2.3–2.8% | 2.0–2.3% | 2.0–2.1% | — | — |

  The page labels the $100k E8 One figure ($5,809) "Average First Payout". The data key is `avg_payouts`, so whether it
  counts only first payouts is **unclear**.
- **A snapshot of the last 30 payouts in E8's live feed** (2026-10-01 14:10 to 2026-10-02 11:01): median **1.8%** of the
  account, mean 2.1%, interquartile range 1.6–2.0%, range 0.7–8.0%. A day's snapshot is not a sample design, so this is
  context only.
- **Volume trend:** 809 payouts and $1.39M in September 2026, an average of $1,723. The average payout has fallen from
  about $4.0k in October–November 2025 to about $1.7–2.1k a month through 2026.

**FTMO** (homepage data, page modified 2026-09-22; (a) as a document). The "Avg. Reward" shown for each 2-Step account,
"Based on global average reward with FTMO":

| Account | $10k | $25k | $50k | $100k | $200k |
|---|---|---|---|---|---|
| Average reward | $680 | $1,431 | $2,805 | $5,957 | $12,234 |
| As a % of account [D] | **6.8%** | 5.7% | 5.6% | **6.0%** | 6.1% |

Rewards are paid at an 80–90% split, so the gross profit behind an average reward is ≈ 6.7–8.5% of the account [D].

**FPFX** (prior pass, (b)): the average payout is 4% of plan size.

**The pattern across firms.**
- **Per payout:** firms whose payouts wait for accumulated profit (E8 One, FTMO) average **≈5–7% of the account**.
  Daily-payout products (E8 Pro) average ≈1.5–2%.
- **The mean overstates the typical case.** At FundedNext the mean is ≈2× the median. So the *typical* paid cycle is
  probably ≈2–4% of the account.
- **Frequency:** FundedNext pays 1.33 transactions per paid account per month, and the CFD median wait for a first
  payout is 28 days.

### 1.3 What the paid minority looks like (FundedNext, CFD payout recipients, February 2026; (a) as a document, selected on success)

- **Slow.** The median recipient makes 1.5 trades a day; **83.6% trade 1–2 a day**. This agrees with Hall's simulation
  (b): the funded payout rate falls from 34.8% at 1 trade a day to 3.9% at 20.
- **Modest per-trade edge.** Median win rate 50%, median reward-to-risk 1.49, **profit factor 1.47**. That is an
  expectancy of about +0.25R per trade [D].
- **Few instruments.** The median is 2. A third trade one instrument, a third 2–3, a third 4 or more.
- **Losing weeks are normal.** **82.1%** of paid CFD traders had at least one losing week. Only 5.8% came within 70% of
  their daily loss limit. The median recovery from the deepest drawdown took 3 trading days.
- **Short account lives.** 60% of paid accounts were under 30 days old; 4% were over 6 months.

### 1.4 What the evidence cannot tell us (said plainly)

- **No firm publishes a denominator for its payouts.** None publishes a funded-account survival curve or a distribution
  of payouts per funded account. Payout rates exist for only four sources (Hall: "the paper's thinnest empirical
  footing").
- **Every "average payout" counts winners only,** so it is a survivor's statistic.
- **The 22-day lifetime is unverified.** An aggregator attributes "funded accounts typically last just 22 days" to FPFX
  (c, via search). I found it in no primary, so I did not use it. The zero-edge arithmetic in §2.3 makes that order of
  magnitude plausible for aggressive traders on tight lines.

---

## 2. Realistic weekly and monthly returns, and the drawdowns behind them (question 2)

### 2.1 Three different numbers that all get called "what prop traders make"

| # | What is measured | Weekly, % of account | Evidence |
|---|---|---|---|
| 1 | **A survivor's winning cycle**: a paid account between funding and payout | **≈0.5–1.5%** | [D] from (a): payouts of ≈2–6% of the account after ≈3–6 weeks (E8 One 5–7%, FTMO 6–7%, FundedNext's 28-day median). Counts winners only. |
| 2 | **The durable top tier**: traders the firms showcase, scale, or allocate to | **≈0.35–0.7%** | FTMO showcase 2–3% a month (a doc, (c) population); FTMO scaling bar 10% in 4 months ≈ 0.55% a week (a); DarwinIA SILVER recipients' median 9.4–11.2% per 6 months ≈ 0.35–0.41% a week, with 5.0–5.75% median drawdown (a doc, selected) |
| 3 | **A funded account's lifetime average** for a genuinely skilled trader, including breaches and unpaid profit | **≈0.03–0.12%** (to the trader) | [D] synthetic, E8 One rules, S = 0.5–1.0 (§4.1) |

Reading the three together:
- **Row 1 is what the owner sees on social media and payout feeds.** It is a selected run, not a rate anyone sustains.
- **Row 2 is what a real, durable edge looks like in this market,** and it comes with ~5–6% drawdowns per half-year.
  - Return over drawdown is about 2. That matches Fernández's Myfxbook survivors (prior pass): "never achieve a profit to
    drawdown ratio above 2".
  - **A 5–6% half-year drawdown would breach E8 One's preset 4% line.** That is why ACIS cannot simply copy row 2 at E8
    One's preset.
- **Row 3 is what an honest strategy earns, averaged over the life of the account.**

**The industry folk number** is "1–5% a month, 3% is above average" (c; traderssecondbrain.com via search). It is
consistent with rows 1–2 and says nothing about row 3.

### 2.2 The identity that turns an edge into a weekly return [D]

With k the daily P&L volatility as a % of the initial balance, and S the annualised Sharpe (out of sample, net of the
firm's costs):

  **weekly mean = 5·k·S/√252 = 0.315·k·S**    **weekly σ = k·√5 = 2.24·k**    **P(losing week) = Φ(−0.141·S)**

| k (%/day) | S = 0.5 | S = 1.0 | S = 1.5 | S = 2.0 |
|---|---|---|---|---|
| 0.5 | 0.08%/wk (4%/yr) | 0.16%/wk (8%/yr) | 0.24%/wk | 0.32%/wk |
| 0.75 | 0.12%/wk (6%/yr) | **0.24%/wk (12%/yr)** | 0.35%/wk | 0.47%/wk |
| 1.0 | 0.16%/wk (8%/yr) | **0.32%/wk (16%/yr)** | 0.47%/wk | 0.63%/wk |
| P(losing week) | 0.47 | 0.44 | 0.42 | 0.39 |

**The Sharpe a weekly target needs:**

| Target | k = 0.75 | k = 1.0 | k = 1.5 |
|---|---|---|---|
| 0.2%/wk | 0.85 | 0.63 | 0.42 |
| 0.5%/wk | 2.12 | 1.59 | 1.06 |
| 1%/wk | 4.23 | 3.17 | 2.12 |
| 2%/wk | 8.47 | 6.35 | 4.23 |

**How plausible those Sharpe ratios are.** The documented realistic band for a handful of FX majors is S ≈ 0.3–0.7
(prior research). GAP-P12D-94's swap-free estimate for the pooled trend book is +0.32 to +0.79. Carver puts a diversified
retail system at ≈1.0.

**So:**
- 0.2% a week is at the top of the realistic band;
- 0.5% a week needs a Sharpe found only in selected, in-sample records;
- 1–2% a week is not a sustainable rate at any vol a 4–10% loss line allows.

### 2.3 The return/volatility profile that maximises passing *and* staying funded [D]

**(i) The cushion-to-volatility ratio L/k is the master dial.**
- The pass probability depends on edge and risk only through θL = 2·(S/√252)·(L/k) (economics pass §2.2; the same holds
  for E8 One's trailing line, §4.1).
- At zero edge a funded account that withdraws everything above its floor survives **E[τ] = (L/k)² trading days** on
  average. That is a reflected Brownian motion absorbed at the floor.

  | L \ k (%/day) | 0.4 | 0.5 | 0.75 | 1.0 | 1.25 |
  |---|---|---|---|---|---|
  | 4% (E8 One preset) | 100 d | 64 d | 28 d | **16 d** | 10 d |
  | 8% (E8 One option) | 400 d | 256 d | **114 d** | 64 d | 41 d |
  | 10% (FTMO static) | 625 d | 400 d | 178 d | **100 d** | 64 d |

- **Without withdrawals, the chance of ever touching a static floor at cushion c is e^(−2·S_d·c/k):**
  - at c = 8%, k = 0.75%: 0.51 at S = 0.5, and 0.26 at S = 1.0;
  - at c = 4%, k = 0.75%: 0.71 and 0.51.

  Even a real edge does not make a tight line safe.
- **Rule: run L/k ≈ 8–10.**
  - Below about 5, the funded life is weeks and the edge barely moves the pass odds.
  - Above about 12–15, the challenge takes years at a realistic Sharpe.
  - On FTMO's 10% static line this gives 1.0–1.25%/day, which is exactly the SIZING pass's challenge band.
  - On E8 One it gives **0.4–0.5%/day at the 4% preset, and 0.8–1.0%/day at the 8% option.**

**(ii) The daily limit must not bind.** Keep the daily volatility ≤ 1/4 of the room to the daily line (the SIZING pass's
z = 4 room guard). E8 One's daily line is 0.66·L, so this means k ≤ 0.165·L: 0.66%/day at L = 4%, 1.32% at L = 8%.
Together with (i), it makes the 8% option the first one that lets a realistic edge run at ~0.75–1%/day.

**(iii) The shape of the P&L.**
- **Positive skew** (trend: small losses, occasional large wins) suits static floors.
- **But E8 One's 40% best-day payout rule** and its "partial closing across days = one trade idea" clause penalise lumpy
  *closed* profit. This **delays payouts; it does not breach the account** (§3.2).
- **Low trade frequency** (the paid minority's 1–2 trades a day) is the profile that gets paid, by both Hall's
  simulation and FundedNext's data.

**(iv) Never size up to catch up.** Size in proportion to the cushion when funded: min(cap, ≈0.10 × cushion per day),
as in the economics and SIZING passes. On E8 One, after the floor locks at the initial balance **the cushion is only the
profit left in the account.** E8's own advice is "leave at least 2–3% in the account after every payout", so funded size
must fall after each withdrawal unless profit is retained.

### 2.4 The drawdowns paid traders actually run

- **DarwinIA SILVER recipients (a doc, selected): median 6-month drawdown 4.95–5.75%.**
  - From the recaps of September 2023, December 2023, January 2025, June 2025 and January 2026, at normalised risk.
  - Darwinex targets 3.25–6.5% monthly VaR. The page does not state the confidence level. At 95%, that is ≈0.43–0.86%/day.
- **FundedNext CFD recipients (a doc, selected):** 82.1% had a losing week; 5.8% came within 70% of their daily limit;
  the median worst losing streak was 5 trades.
- **Fernández's 5 long-lived Myfxbook survivors (prior pass, (b)):** maximum drawdowns of 24–68% over 3+ years. Over a
  long enough life every account visits a deep drawdown, which is why loss lines bound account lifetimes.

---

## 3. Automated traders: what they achieve and what firms forbid (question 3)

### 3.1 What automated traders achieve in prop accounts

- **No firm in scope publishes outcomes split by EA versus manual trading.** I searched FTMO and the industry. FTMO
  publishes no EA share; FundedNext's report does not split by tool.
- **The only "data" is vendor marketing.** An EA vendor claims "internal data from 2024" showing rule-compliant EAs pass
  at 28–32% against 15–18% for discretionary traders (jptradingcapital.com via search). That is **(c): a seller of EAs
  marketing EAs.**
- **What the evidence does support (graded in §1.3):** the paid profile is slow (1–2 trades a day), uses few
  instruments, and makes a modest edge per trade. A slow daily-decision engine like ACIS's target path matches that
  profile. A minute-scale churner does not (GAP-P12D-45/49).

### 3.2 Current rules on EAs and bots (primary pages, read 2026-10-02)

| Rule | E8 (all classic products) | E8 One specifically | FTMO | FundedNext |
|---|---|---|---|---|
| EAs and bots | "Tools you can use while trading with us: Algo, EA, Bots and Indicators" (2026-05-14) | EAs: Yes (product overview, 2026-09-23) | allowed (forbidden-practices page, 2026-02-02; FAQ per prior pass) | **"FundedNext does not allow the use of EAs or automated trading on the cTrader and Match-Trader platforms regardless of account size"**; MT4/MT5 only below $50k, as a paid add-on; "$300,000 for each EA or trading bot's strategy" (2026-09-08) |
| Same strategy as others | "We limit one strategy per user … if we see multiple users utilize the same EA, it may lead to the termination of your account" | — | third-party EA risk of denial (prior pass) | "Each EA or bot is required to employ a distinct strategy" |
| Request and order caps | "Server requests per day: 2000 (order place/cancel/modify, TP/SL edits, etc.)"; "Open-order cap at time: 100"; "Max positions per day: 2000"; 50 lots per ticket (gold 20) (2026-09-07) | same | "more than 2,000 server requests per day" forbidden | not stated |
| HFT and scalping | "you cannot hold more than 50% of your trades for under one minute" (2026-09-23) | same | "ultra-high-speed tools" forbidden | "Quick Strike" (closed within 30 s; ≥ 30% of profit) per prior pass |
| Sizing | "Risking your entire daily drawdown on a single trade is not permitted"; may de-risk to "no more than 1% per trade idea … if we detect prohibited practices"; "There are no hard limits on maximum risk per trade idea" and "The most successful traders on E8 risk between 1–1.5% per trade idea. This is not a rule but a clear pattern" (2026-05-21) | same | "opening substantially larger position sizes compared to your other simulated trades" forbidden | — |
| Hedging and copying | hedging across accounts "strictly prohibited"; copy trading across *your own* accounts allowed | same | opposite positions across accounts forbidden | — |
| News | Pro and Signature: allowed | **Performance account: no opening, closing, "Stop/Loss and Take/Profit", or Buy/Sell Stop from 5 minutes before to 5 minutes after high-impact news (and during speeches); "profits are automatically deducted from your account balance after your request payout"** (2026-09-11, 2026-09-23) | "gap trading": opening when major news is scheduled, or ≤ 2 h before a ≥ 2 h close | news profits count at 40% on funded accounts (prior pass) |
| Consistency | Pro: none | **40% best day on payouts.** Splitting a winner by "partially closing a large winning position across multiple days" "may result in all profit from that position being consolidated into a single day" (2026-07-02) | 1-Step: 50% best day, with a similar anti-circumvention clause ("partially closing and managing the same trade idea across multiple trading days") | — |
| Weekend and overnight | One and Pro: yes | yes | Swing: yes | — |

**What this means for ACIS** (findings for the lead):
1. **The E8 One news window covers stop-loss fills** (`Stop/Loss and Take/Profit` is listed). A server-side stop that
   fires inside the ±5-minute window is a prohibited action on a performance account. E8's stated remedy is removing
   profit, and a stop-out has none to remove. **Whether a stop fill in the window can also void the account is not
   stated.**
   - ACIS's runtime needs the event calendar (GAP-P12D-03) to gate entries and exits on E8 One performance accounts.
   - Its stop policy around scheduled releases is an **OWNER/[spec]** question.
   - The daily 08:00 New York slot sits 30 minutes before the 08:30 ET US releases, so it is probably clear. It still
     needs checking against E8's list of targeted instruments.
2. **Carver-style daily position adjustments realise P&L in pieces across days.** On E8 One this risks
   "consolidation" under the best-day rule when the move came in one day. The cost is a delayed payout, not a breach,
   but PropEV must model it.
3. **ACIS fits everything else comfortably:** at most one decision per instrument per day, no HFT, no hedging, its own
   code (one strategy per user), and per-position risk ≈ 0.1–0.3% of the account (§5), far below "all-or-nothing".
4. **FundedNext stays out** for a cTrader engine. Its EA ban on cTrader is current (2026-09-08).

---

## 4. The economics: fees against expected payouts (question 4)

### 4.1 E8 One, simulated under its own rules [D] (Appendix A; synthetic; validated against the closed form)

**Model.**
- **E8 One's rules:**
  - target 1.5·L of closed profit;
  - daily line 0.66·L below the day's starting balance, on equity or balance;
  - the floor trails the highest closed balance minus L and locks at the initial balance;
  - funded payouts on demand once profit exceeds 0.33·L and the best day is ≤ 40% of cycle profit, with 0.5·L of
    cushion kept above the floor (E8's own example keeps 2–3% on 6%);
  - **no fee refund** (E8 refund policy, 2026-08-11: "do not provide bonuses by refunding the fee with the first payout
    share"); 80% split.
- **The P&L:** two sleeves, closed at random with a mean hold of 5 days; Student-t(4) shocks, 4 sub-steps a day; the
  SIZING pass's room guard (k ≤ room/4); a 2-year horizon from purchase; discount 25%/yr.
- **The fee:** $107 for $10k, from the page's $88 price plus 10% swap-free plus the $10 cTrader add-on under $100.
  **The same price is assumed for every drawdown option; the real option prices are unverified.** For $100k the fee is
  $537 ($488 + 10%).
- 1,500 paths a cell. The Monte Carlo error is about ±1.3 points on probabilities and about ±15% on EV.

**Validation first** (Gaussian, no daily limit, continuous trailing on equity, 16 sub-steps):

| Cell | MC P(pass) | Closed form |
|---|---|---|
| S = 0, k = 1%, L = 4% | 0.271 | 0.245 |
| S = 1.0, k = 0.5% | 0.485 | 0.456 |
| S = 0.5, k = 0.25% | 0.464 | 0.456 |
| S = −0.5, k = 0.5% | 0.178 | 0.162 |

The closed form is e^(−γL) × s(L)/s(1.5L), with γ = θ/(e^(θL) − 1) (Taylor 1975; Lehoczky 1977), then a static lock.
The simulation sits **1–3 points above it in every cell, in the direction discrete monitoring predicts** (Broadie–Glasserman:
a missed crossing and a lagged maximum both help the trader). Real monitoring is continuous, so **real pass rates are
slightly lower than the table below.**

**Results** (fat tails, H = 5 days, room guard z = 4):

| L | k %/day | S | P(pass) | median days to pass | funded breach < 126 d | P(any payout) | trader paid, 2 yrs, % of A | **EV per $10k** | **EV per $100k** | ΔEV per $10k against S = 0 | trader payout per funded week, % of A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4% | 0.40 | 0 / 0.5 / 1.0 | 0.28 / 0.45 / 0.62 | 110 / 114 / 109 | 0.07 / 0.04 / 0.04 | 0.10 / 0.24 / 0.44 | 0.32 / 0.96 / 2.33 | −81 / −33 / +71 | −279 / +206 / +1,239 | 0 / +49 / +152 | 0.018 / 0.032 / 0.055 |
| 4% | 0.75 | 0 / 0.5 / 1.0 | 0.28 / 0.41 / 0.55 | 46 / 50 / 52 | 0.08 / 0.07 / 0.07 | 0.08 / 0.15 / 0.29 | 0.38 / 0.91 / 2.37 | −75 / −31 / +85 | −213 / +227 / +1,380 | 0 / +44 / +159 | 0.018 / 0.031 / 0.059 |
| 6% | 0.75 | 0 / 0.5 / 1.0 | 0.28 / 0.42 / 0.59 | 75 / 78 / 81 | 0.06 / 0.04 / 0.05 | 0.09 / 0.20 / 0.37 | 0.52 / 1.50 / 3.66 | −64 / +13 / +178 | −106 / +662 / +2,318 | 0 / +77 / +242 | 0.026 / 0.050 / 0.087 |
| **8%** | **0.75** | 0 / 0.5 / 1.0 | 0.28 / 0.46 / 0.64 | 122 / 128 / 121 | 0.06 / 0.04 / 0.03 | 0.11 / 0.26 / 0.46 | 0.66 / 1.84 / 4.59 | **−55 / +34 / +239** | −19 / +878 / +2,920 | 0 / +90 / +294 | 0.036 / 0.062 / 0.108 |
| **8%** | **1.00** | 0 / 0.5 / 1.0 | 0.28 / 0.42 / 0.59 | 75 / 78 / 81 | 0.06 / 0.04 / 0.05 | 0.09 / 0.20 / 0.37 | 0.69 / 2.00 / 4.88 | **−49 / +53 / +274** | +38 / +1,062 / +3,269 | 0 / +102 / +323 | 0.035 / 0.067 / 0.116 |

The full 27-cell grid, adding k = 0.4/1.0 at 4–6% and 0.4 at 8%, is in the scratch output (Appendix A).

**Two cross-checks.**
1. **The model is scale-free in L/k.** The 6%/0.75 rows and the 8%/1.00 rows share L/k = 8, and they have *identical*
   pass statistics on the same seeds; their payouts scale with k. That is a structural check of the code.
2. **The simulated size of each payout matches E8's published averages.** Per funded payout it comes to ≈5–7% of the
   account: for example 4.88% / (0.372 × 1.95 payouts) = 6.7%. E8 One's published averages are 4.7–6.8% for
   $25k–$500k. That checks the funded payout mechanics, **not the edge**.

**Reading the table.**
1. **The zero-edge pass rate is ≈0.27–0.29 whatever the size.** A pass proves nothing (GAP-P12D-62 holds on E8 One).
2. **The zero-edge control is −EV at the fee on E8 One** (−$49 to −$92 per $10k). Unlike FundedNext's or FTMO's static
   floors, E8 One sells little option value: the trailing floor and the lack of a refund remove it. It is a fairer test
   of skill, and an unforgiving one for a weak edge.
3. **Break-even edge per $10k attempt [D, interpolated]:**
   - S ≈ 0.6–0.65 at the 4% preset;
   - ≈ 0.4 at 6%;
   - **≈ 0.25–0.3 at 8%**, at the assumed price.

   At $100k the fee falls to 0.54% of the account and break-even drops by about 0.25–0.4 (to ≈0.25 at 4% and ≈0 at 8%).
4. **The drawdown option is the single biggest lever ACIS controls.**
   - At S = 0.5, moving from the 4% preset to 8% turns −$31 into +$34 to +$53 per $10k.
   - It roughly doubles the lifetime payout rate.
   - **A price premium for the 8% option of up to ≈$65–80 per $10k is worth paying at S = 0.5 [D].** The actual
     premium must be read at checkout.
5. **Time to money is slow.** Median passes take 50–130 trading days, and those fast passes are mostly luck: the pass
   time barely changes with S. The first payout comes ≥ 3 days after funding, under E8's best-day mechanics.
6. **The weekly number again.** At the recommended cell (8%, 0.75–1.0%/day), a genuinely S = 0.5–1.0 strategy pays the
   trader **≈0.06–0.12% of the account per funded week, on average over its life.** That is ≈$6–12 a week at $10k and
   ≈$60–120 a week at $100k.

**Comparison with FTMO and FundedNext (prior passes; not re-run here).**
- FTMO 2-Step $10k (P4 policy, about 1.25%/day; SIZING pass): EV ≈ $100 / $215 / $322 / $720 at S = 0 / 0.3 / 0.5 / 1.0.
  That is higher than E8 One at the same S because of the static 10% floor and the refunded fee.
- **But FTMO's swaps cut the trend book's net Sharpe to −0.15..+0.32, against +0.32..+0.79 swap-free (GAP-P12D-94).**
  So the comparison that matters is E8 One at S ≈ 0.55 (EV ≈ +$40–60 per $10k at 8%) against FTMO at S ≈ 0.1 (EV
  ≈ +$120, mostly option value).
- On **ΔEV, the skill part,** E8 One is ahead but the gap is small: about +$90–100 against about +$30–40. **This is the lead's verification item: it
  does not overturn the E8 One pick, but the pick rests on the swap-free Sharpe being real.**

### 4.2 Scaling plans: the firms' own definition of a good trader

| Firm | Scaling condition | Implied pace | Grade |
|---|---|---|---|
| FTMO | +25% balance every 4 months if ≥ 10% net profit in 4 months and ≥ 2 rewards, up to $2M | ≈2.5%/month ≈ 0.55%/wk | (a), SIZING pass 2026-10-01 |
| FundedNext | +40% if ≥ 10% over 4 months with ≥ 2 payouts, up to $4M | ≈2.5%/month | (c), affiliate summaries via search |
| The5ers High Stakes | the next level at each +10% | — | (c) |
| E8 One | **none found** in E8's product pages (absence in pages fetched, not proof of absence) | — | (a) absence |

The firms set their bar near **2.5% a month**. By §2.2 that needs S ≈ 1.6–2.1 at 0.75–1%/day: an upside, not a plan.
That agrees with the SIZING pass.

### 4.3 Counterparty and payout-rail facts for the E8 pick

- **Scale.** E8 pays ≈$1.3–2.0M a month (2026), roughly a tenth of FTMO's or FundedNext's recent pace (a).
- **Payout rails.** E8 pays only through WorkMarket, Rise or Aeropay (US only): "If you can't undergo WorkMarket and
  Riseworks KYC, we cannot provide you with a payout" (a, 2026-09-23). **Rise's restricted list, updated 2026-09-04, does
  not include Kenya** (a). WorkMarket/Hyperwallet coverage was not checked.
- **Payout speed.** Median 11 h to approval and 24 h to funds (E8, January–May 2026); the page data says 18.9 h on
  average (a).
- **Denials.** Trustpilot complaints, read only through a search summary (c), cluster on *fast, lumpy* profits: "passed
  [a 500k] in 4 days"; "$28,181 USD in 3 days … only agreed to pay 20%"; banned for "allocating a substantial portion of
  drawdown to single trade ideas". These are anecdotes, but they fit the economics pass's thesis that firms police
  variance harvesting. **A slow, steady 0.1–0.3% a week is the least-scrutinised profile there is.**
- **Firm mortality** (c; Proptradingvibes Q3 2026, affiliate-disclosed, 67 dated closures): among firms that died,
  36–58% did not reach year two. That is a conditional statistic, not a hazard rate, but it supports a payout haircut.
  E8's own payout series starts in December 2021 (a).
- **Swap-free terms are unverified.** Brokers' swap-free accounts often carry *holding fees* (IC Markets announced
  "holding fees applicable to our swap-free trading accounts", 2026-02-13, (a) for IC, relevant only by analogy). E8's
  swap-free conditions were not found on its help centre. **Check for holding fees or day limits before purchase:** a
  holding fee would hit a multi-day trend book exactly where swap-free was supposed to help.

---

## 5. The recommended weekly target for ACIS (question 5)

| Item | Recommendation | Why |
|---|---|---|
| **Weekly target (expected)** | **0.2% of the initial balance per week** (≈0.85% a month, ≈10–11% a year) | Half the durable top tier's pace (§2.1 row 2), because ACIS has no demonstrated edge yet and E8 One's line is tighter than FTMO's |
| **Range** | **0.1–0.3%/week**. Floor 0.1% ≈ break-even territory; 0.3% only if out-of-sample S ≥ 0.95–1.3 is shown | §2.2 |
| **Never plan for** | ≥ 0.5%/week (needs S ≥ 1.6–2.1) or the survivors' 0.5–1.5%/week | §2.1–2.2; the anti-playbook |
| **Daily vol budget** | **k = 0.75–1.0% of the initial balance per day** (12–16%/yr) on E8 One's **8%** option (L/k = 8–10.7; daily line 5.28% = 5–7 k). On the 4% preset: k = 0.4–0.5%/day, and the target falls to ≈0.1%/week | §2.3 rules (i)–(ii); §4.1 |
| **Funded stage** | min(k, 0.10 × cushion per day); after the floor locks, keep a retained buffer (E8: 2–3%; PropEV should optimise between 0.5·L and L) | economics/SIZING passes; E8's buffer article |
| **Minimum edge** | **Out-of-sample net S ≥ 0.65 at 1.0%/day (≥ 0.85 at 0.75%/day)** to sustain 0.2%/week. **Break-even ≈ 0.25–0.3** (8% option, assumed price) **to 0.65** (4% preset) per $10k attempt | §2.2, §4.1 |
| **How to judge it** | Never by the week (44–47% of weeks lose at S = 0.5–1.0). Use a rolling ≥ 26-week realised Sharpe and realised daily vol (GAP-P12D-61's requested metric), and **ΔEV against the zero-edge control** (GAP-P12D-62) | §2.2; prior passes |

**What it means in dollars [D]**, as gross expected P&L at k = 0.75%/day and S = 0.65 (0.15%/week):

| Account | Per week, gross | Per week, trader share (80%) | Lifetime average paid per funded week (§4.1, S = 0.5–1.0, 8% option) |
|---|---|---|---|
| $10k | ≈$15 | ≈$12 | ≈$6–12 |
| $100k | ≈$150 | ≈$120 | ≈$60–120 |

"Pennies" at $10k is the honest number. The way out is **allocation, not aggression**: E8 One up to $200k for Kenyan
residents (venue pass), identical copies across one's own accounts (allowed by E8), and fees that fall to 0.54% of the
account at $100k. Do it after the edge holds rung 1. This matches the SIZING pass's R9.

**Sizing on a $10k account with 0.01-lot minimums [D].** Inputs: 13 FX pairs, `targets.idm: 1.5`, Carver forecast 10
on average and 20 at the cap. Daily σ from the SIZING pass's ECB data: EUR/USD 0.47%, USD/JPY 0.6%.

| Quantity | k = 0.75%/day | k = 1.0%/day |
|---|---|---|
| Book P&L σ | $75/day | $100/day |
| Per pair at forecast 10: k × IDM / N | 0.087%/day = $8.7/day | $11.5/day |
| One 0.01 lot: EUR/USD (1,000 EUR) | ≈$5.5/day | same |
| One 0.01 lot: USD/JPY (1,000 USD) | ≈$6.0/day | same |
| One 0.01 lot: AUD/USD | ≈$4.0/day | same |
| **Lots per pair** | **≈1–2; 3–4 at forecast 20** | ≈2; 4–5 at forecast 20 |
| Risk to a ~3σ stop per position | ≈$25–35 = **0.25–0.35% of the account** | ≈0.35–0.45% |
| Gross notional | ≈$20–30k ≈ 2–3× NAV (E8 One FX leverage 1:30 allows 30×) | ≈3–4× NAV |
| **Gold (0.01 lot = 1 oz ≈ $4,566 at E8's example price)** | **≈$55–70/day per minimum lot** (at an assumed gold daily σ of 1.2–1.5%): **the whole budget. Infeasible at $10k** | infeasible |

- **Rounding** at 1–2 lots is ±25–50% per position, which is coarse but workable. At k = 0.4%/day it rounds many days to
  flat; J1 found the minimum lot costs ~40% of stage A's power at $10k and 10%/yr (GAP-P12D-101).
- **The binding constraint is ACIS's own guardrails, not E8.**
  - The 20% cluster cap and the 30% single-currency cap, at 90% headroom under G-5, admit $1,800 of notional per
    cluster at $10k, about one lot (GAP-P12D-142).
  - So the recommended budget **cannot run on a real $10k account under today's caps**. It caps realised risk at about
    0.16%/day (GAP-P12D-61), which is ≈0.03–0.05% a week at S = 0.5–1.0.
  - The per-account guardrail profiles (G-1..G-4, `archive/GUARDRAIL_PROFILES_DRAFT_2026-10-02.md`) are the
    precondition. They are **OWNER-owned and ratified to apply only after a family holds rung 1.** The $100k demo with
    $10k sizing (GAP-P12D-142's ruling) sidesteps the caps on the demo only.
- **Index CFDs** were not sized. Their contract sizes at E8 on cTrader were not checked.

---

## 6. Verification of the prior passes' claims (verify or refute)

| Prior claim (source) | Verdict 2026-10-02 | Evidence |
|---|---|---|
| FTMO "average reward" 680 / 1,431 / 2,805 / 5,957 / 12,234 (SIZING §2) | **CONFIRMED**, unchanged | ftmo.com page data, `step_2` list, page modified 2026-09-22 (a). As population evidence it counts winners only (c) |
| E8 "Average first payout $1,594 on $100k" (SIZING §2) | **CONFIRMED, re-attributed.** It is the *E8 Pro* entry of E8's `avg_payouts` table. **E8 One's** $100k figure is **$5,809** | e8markets.com page data (a) |
| E8 Pro prices $32 / $68 / $148 / $228 / $488 / $998 / $2,098 / $2,598 | **CONFIRMED** | page data (a) |
| E8 One "6% target, 3% daily, 4% dynamic on closed balance" (venue pass) | **CONFIRMED as the preset, but it is one option.** The page data sets the target at 1.5×L and the daily line at 0.66×L, with L ∈ {4, 6, 8, 10, 14}%; the preset object says L = 6. The help article's "3%" daily at L = 4% conflicts with 0.66 × 4 = 2.64%. **Verify at checkout.** GAP-P12D-94's "3/4/5.3/6.6/9.2%" matches 0.66 × L | (a) |
| E8 swap-free at +10% (GAP-P12D-94, from a search rendering) | **CONFIRMED in page data**: `swapFree: 10` for E8 One and E8 Pro. The terms (holding fees) are **unverified** | (a) |
| "E8 may cap risk at 1% per trade idea" (SIZING) | **CONFIRMED with scope.** It is a sanction only "if we detect prohibited practices". E8 also states "There are no hard limits on maximum risk per trade idea" | (a), 2026-05-21 and 2026-09-23 |
| E8 One performance news ban ±5 min incl. SL/TP (SIZING) | **CONFIRMED**, and it also covers *closing* trades and speeches | (a), 2026-09-11 and 2026-09-23 |
| The zero-edge identity "E[lifetime withdrawals] = L" (economics §2.3) | **TRUE for static floors; does NOT carry to E8 One.** With a floor that trails the closed maximum until it locks, the zero-edge funded value is ≈0.37·L (hold for the lock, then withdraw) to ≈0.5·L (withdraw increments). Its E[D] = L − E[floor rise] [D]. So E8 One's zero-edge control is −EV after the fee | §4.1 |
| "+EV for OOS net S above ≈ −0.4 … working threshold S_net ≥ 0" (economics, FundedNext static) | **Does not apply to E8 One.** Break-even is ≈ +0.25 to +0.65 per $10k attempt [D] | §4.1 |
| Challenge risk 1.0–1.25%/day (SIZING R1) | **Valid for FTMO's 10% static line** (L/k = 8–10). **On E8 One the same rule gives 0.4–0.5%/day (4%) or 0.8–1.0%/day (8%)** | §2.3 |
| FPFX "average payout 4% of plan size", 14% / 45% / 7% (economics) | Unchanged (b); corroborated by TradeInformer's reuse of it | (b) |
| FTMO pass rate 9–10% (via Hall) | Still no FTMO primary found; stays (c) as a primary | — |
| "Funded accounts typically last 22 days" (FPFX, aggregator) | **UNVERIFIED**, not found in any primary; not used | (c) |
| FundedNext EA rules (venue pass) | **CONFIRMED** current (modified 2026-09-08) | (a) |
| FTMO forbidden practices (economics, venue) | **CONFIRMED**, page unchanged since 2026-02-02. It now also contains a best-day anti-circumvention clause | (a) |

---

## 7. Open questions (for the lead, then the owner)

1. **E8 One option prices.** What does each drawdown option (6 / 8 / 10 / 14%) cost at $10k and $100k? How do the
   swap-free (+10%) and cTrader (+$10 under $100) add-ons stack? The page data has per-tier fields `dlt`, `dht`, `plt`
   and `pht` whose meaning I could not establish. The §4.1 EV assumes the preset price for every option.
2. **E8 swap-free terms.** Are there holding fees, holding-day limits or eligibility conditions? This decides whether the
   swap-free Sharpe uplift (GAP-P12D-94) is real for multi-week holds.
3. **E8 One news rule versus server-side stops.** Is a stop fill inside the ±5-minute window only a profit removal, or a
   breach? Does ACIS flatten, widen or suspend stops around releases on E8 One performance accounts? (**OWNER/[spec]**;
   GAP-P12D-03 event calendar.)
4. **Best-day consolidation.** Will E8 read Carver's daily partial adjustments of one trend position as one trade idea?
   It delays payouts only, but PropEV must measure it on R1's real closed-P&L path, not on random exits.
5. **The payout and buffer policy on E8 One.** Should ACIS keep 0.5·L or L after the lock? This trades payout speed
   against funded lifetime. Optimise it in PropEV, not by rule of thumb.
6. **Denominators.** No firm publishes funded-account counts or survival. The FundedNext monthly series (promised
   2026-03-11) is not online after February. E8 publishes averages without denominators. **Row 3 of §2.1 therefore
   rests on simulation only.**
7. **WorkMarket/Hyperwallet coverage for Kenya** was not checked. Rise covers Kenya per its 2026-09-04 list.
8. **Scale-up of the simulation.** Re-run Appendix A at ≥ 20,000 paths on the Google server. Use RSIM's per-day realised
   and unrealised split in place of random exits (SIZING §3.4), and add the E8 One options' real prices.

---

## 8. Ledger items this pass should generate (proposed; no IDs; for the lead to verify and triage, A6)

1. **[NEW, high] E8 One's geometry sells little option value and raises the break-even edge.**
   - The floor trails the closed maximum to a lock; the target is 1.5L; the daily line is 0.66L; the fee is not refunded;
     there is a 40% best-day rule.
   - The zero-edge control is −EV after the fee. Break-even S ≈ 0.25–0.3 (8%) to 0.65 (4% preset) [D].
   - **Choose the drawdown option by PropEV, not by price.** The preset 4% caps the achievable return at about 0.1% a
     week.
   - Links: GAP-P12D-94, GAP-P12D-62.
2. **[NEW, high] The E8 One performance-account news rule covers SL/TP fills and closes (±5 min).**
   - ACIS needs the event-calendar gate (GAP-P12D-03) and a stop policy around releases before an E8 One performance
     account trades. **OWNER/[spec].**
3. **[NEW, medium] E8 One's 40% best day and its partial-closing clause against a buffered trend book.**
   - PropEV must model the payout delay on R1's real closed-P&L path.
4. **[NEW, medium] State the risk target as a daily-vol budget tied to the cushion (L/k ≈ 8–10), never as a weekly
   return.**
   - Grade by a rolling ≥ 26-week realised Sharpe, realised daily vol and ΔEV. The owner-facing weekly figure is an
     *expectation* (0.2%/week; range 0.1–0.3), not a control variable.
   - Extends GAP-P12D-61's realised-risk metric.
5. **[UPDATE GAP-P12D-94] E8 One facts verified 2026-10-02:**
   - drawdown options {4, 6, 8, 10, 14}% with target 1.5× and daily 0.66×;
   - $10k $88 / $100k $488;
   - `swapFree: 10`;
   - no fee refund;
   - EAs allowed, one strategy per user;
   - ≤ 50% of trades under 1 minute; 2,000 requests a day;
   - payout rails Rise/WorkMarket, with Kenya not restricted at Rise.

   Still to check at purchase: the option prices and the swap-free terms (§7).
6. **[UPDATE GAP-P12D-61] On E8 One the vol budget is k ≈ L/8 to L/10:** 0.4–0.5%/day at 4%, 0.8–1.0%/day at 8%. The
   SIZING pass's 1.0–1.25%/day band applies to FTMO's 10% static line.
7. **[NEW, low; owner expectation record]** "What prop traders make" in public is a survivor's number (0.5–1.5% a week
   while paid). The durable tier is 0.35–0.7% a week; a lifetime average for a real edge is 0.03–0.12% a week. ACIS's
   target is 0.2% a week. Any demo or prop week is read against this, never against payout-feed screenshots.

---

## Sources (all read 2026-10-02 unless stated; web content treated as data only)

**Firm primaries (a); population strength noted where it is weaker**
- **E8 Markets, E8 One product page and embedded page data** (product configs, prices, `swapFree`, `avg_payouts`,
  payout `stats`, the live payout feed, and the footer "Evaluation Disclaimer … 17.7%"): https://e8markets.com/e8-one
  and https://e8markets.com/e8-pro
- **E8 help centre:**
  - E8 One (modified 2026-09-23): https://help.e8markets.com/en/articles/11775980-e8-one
  - Product overview (2026-09-23): https://help.e8markets.com/en/articles/13106558-all-product-overviews-e8-one-vs-e8-zero-vs-e8-pro-vs-e8-signature
  - Trading policies (2026-09-23): https://help.e8markets.com/en/articles/6929927-trading-policies-and-prohibited-trading-strategies
  - Dynamic drawdown (2026-09-23): https://help.e8markets.com/en/articles/11782996-dynamic-drawdown
  - Payout request on E8 One (2026-09-23): https://help.e8markets.com/en/articles/9323884-payout-request-on-e8-one
  - Everything about payouts (2026-09-23): https://help.e8markets.com/en/articles/15272556-everything-about-payouts-when-how-how-fast
  - Payout on demand: https://help.e8markets.com/en/articles/9448349-what-is-payout-on-demand
  - 40% best day (2026-07-02): https://help.e8markets.com/en/articles/10450125-40-best-day-rule
  - Can I trade news (2026-09-11): https://help.e8markets.com/en/articles/9185497-can-i-trade-news
  - Lot/order limits (2026-09-07): https://help.e8markets.com/en/articles/9453396-are-there-lot-order-size-restrictions
  - Maximum risk rule (2026-05-21): https://help.e8markets.com/en/articles/9453413-is-there-any-maximum-risk-rule
  - EAs (2026-05-14): https://help.e8markets.com/en/articles/5515409-can-i-use-indicators-or-expert-advisors-when-trading-the-e8-account
  - Refund policy (2026-08-11): https://help.e8markets.com/en/articles/8811411-refund-policy
- **FTMO:**
  - Homepage and embedded price/"average_reward" data (modified 2026-09-22): https://ftmo.com/en/
  - Forbidden trading practices (modified 2026-02-02): https://ftmo.com/en/forbidden-trading-practices/
  - Blog, "We pay millions in payouts to our FTMO Traders" (published 2024-02-09, modified 2025-11-04): https://ftmo.com/en/blog/we-pay-millions-in-payouts-to-our-ftmo-traders/
- **FundedNext:**
  - Payout Report, February 2026 (published 2026-03-11): https://fundednext.com/blog/fundednext-payout-report-feb-2026 (a as a document; selected on payout)
  - "Is EA allowed in FundedNext?" (modified 2026-09-08): https://help.fundednext.com/en/articles/8020763
- **Topstep, risk disclosure** (updated 2025-09-25): https://www.topstep.com/risk-disclosure
- **Darwinex:**
  - DarwinIA SILVER & GOLD recaps: https://blog.darwinex.com/hubfs/DarwinIA_SILVER_GOLD_Darwinex/Recap%20Jan%2026.pdf , …/RecapJune25.pdf , …/RecapJanuary25.pdf , …/RecapDecember.pdf (December 2023), …/RecapSeptember.pdf (September 2023). Each carries the disclaimer "All returns are gross, before deducting 1.2% management fees and 20% performance fees." (a as documents; recipients are selected on the ranking window)
  - Risk engine: https://help.darwinex.com/risk-manager — "6.5% monthly VaR"; "between a monthly 3.25 and 6.5% VaR"; no confidence level stated
- **Rise, unsupported countries** (updated 2026-09-04): https://help.riseworks.io/en/articles/7198515-which-countries-are-not-serviced
- **IC Markets (by analogy only)**, "Important update: holding fees on swap-free accounts" (2026-02-13): https://ic.com/blog/important-update-holding-fees-on-swap-free-accounts/

**Research and trade press (b)**
- Hall, N., "Gate Design and Stage-Dependent Incentives in Retail Proprietary-Trading Evaluations …", arXiv:2609.14859
  (v1, 2026-09-14; single author; preprint), PDF read: https://arxiv.org/abs/2609.14859 — Tables 11, 20 and 21; §9.3
  failure attribution; §9.5.
- Finance Magnates:
  - "Only 1 in 20 Traders Pass Prop Firm Challenges, Reports The Funded Trader" (2025-03-18): https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/
  - "FTMO Announces Over $450 Million Paid Out …" (2025-09-29): https://www.financemagnates.com/forex/ftmo-announces-over-450-million-paid-out-as-prop-trading-firm-turns-10/
  - "Prop Firm Match Tracked About $325 Million in Payouts to Traders in 2025" (2026-01-06): https://www.financemagnates.com/forex/prop-firm-match-tracked-about-325-million-in-payouts-to-traders-in-2025/
  - FundedNext February report coverage (2026-03-05), read via the TradingView mirror: https://www.tradingview.com/news/financemagnates%3A95944afde094b%3A0-prop-firm-fundednext-says-it-paid-15m-to-more-than-8-000-traders-in-february/
- TradeInformer, "What FTMO tells us about prop firm finances" (D. Kimberley, 2025-03-07; from FTMO's 2023 accounts): https://www.tradeinformer.com/prop-weekly/what-ftmo-tells-us-about-prop-firm-finances

**Weak or marketing sources (c): context only, nothing load-bearing**
- Trustpilot E8 reviews, via a search summary only: https://www.trustpilot.com/review/e8markets.com?page=4
- Proptradingvibes, "Q3 2026 Industry Report" (affiliate relationships disclosed): https://proptradingvibes.com/state-of-prop-trading/q3-2026
- An EA vendor's EA-versus-manual pass claim, via a search summary: https://www.jptradingcapital.com/blog/en/prop-firm-ea-vs-manual
- Folk monthly-return guidance, via a search summary: https://traderssecondbrain.com/guides/how-much-can-you-make-prop-firm
- FundedNext and The5ers scaling summaries, via search: https://www.track360.io/blog/fundednext-review-2026-operator-trader-guide
- Backtrex and Gitnux "prop firm statistics" pages (seen in search results, not used): e.g. https://backtrex.com/en/blog/prop-firm-challenge-success-rate

**Repo (read-only)**
- `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`
- `archive/RESEARCH_PROP_VENUES_2026-09-24.md`
- `archive/RESEARCH_SIZING_AGGRESSION_2026-10-01.md`
- `KNOWN_GAPS.md`: GAP-P12D-61, 62, 94, 142, 101, 49
- `config/instruments.yaml` (lot steps, clusters)
- `config/system_config.yaml` (`targets.idm: 1.5`)

---

## Appendix A — the E8 One simulator (synthetic only; validated as in §4.1)

The scratch copy is in this session's scratchpad (`…/scratchpad/pr/e8sim.py`, `val.py`, `grid.py`, `grid_out.json`).
**The scratchpad is temporary.** The full source is reproduced here so the lead can rerun it on the Google server.

```python
"""Lean synthetic Monte Carlo of E8 One (dynamic closed-balance drawdown) — PROPRETURNS, 2026-10-02.
Units: fraction of initial balance A. Synthetic P&L only; no market data.
Rules (E8 help centre, updated 2026-09-23): target = 1.5L closed profit; daily DD = 0.66L below the
day's starting balance (equity or balance); dynamic DD floor = highest CLOSED balance - L, locks at
the initial balance; funded: payout > 50% of daily DD, 40% best day, floor does not reset on payout."""
import numpy as np

def closed_form_pass(S, k, L, T_mult=1.5):
    """continuous trailing-max barrier (Taylor 1975 / Lehoczky 1977) then static lock."""
    mu = k * S / np.sqrt(252.0); th = 2 * mu / k**2
    if abs(th) < 1e-12:
        return np.exp(-1.0) * (1.0 / T_mult)
    g = th / np.expm1(th * L)
    return np.exp(-g * L) * (-np.expm1(-th * L)) / (-np.expm1(-th * T_mult * L))

def run(S, k, L, n=3000, days=504, M=4, H=5, N=2, fat=True, guard_z=4.0, keep=0.5,
        split=0.8, seed=7, delta=0.25, validate=False):
    rng = np.random.default_rng(seed)
    D = 0.66 * L; T = 1.5 * L
    mu_d = S / np.sqrt(252.0)
    stage = np.zeros(n, int)            # 0 challenge, 1 funded, -1 dead
    bal = np.ones(n); opl = np.zeros((n, N)); hwm = np.ones(n)
    pass_day = np.full(n, -1); dead_day = np.full(n, -1); fstart = np.full(n, -1)
    paid = np.zeros(n); paid_disc = np.zeros(n); npay = np.zeros(n, int)
    cyc_start = np.ones(n); best_day = np.zeros(n)
    funded_days = np.zeros(n)
    sq = 1.0 / np.sqrt(M)
    p_close = 1.0 if H <= 1 else 1.0 / H
    for d in range(days):
        alive = stage >= 0
        if not alive.any(): break
        eq0 = bal + opl.sum(1)
        floor = np.minimum(hwm - L, 1.0)
        dfloor = bal - D
        kk = np.full(n, k)
        if guard_z:
            room = np.maximum(np.minimum(eq0 - dfloor, eq0 - floor), 0.0)
            kk = np.minimum(kk, room / guard_z)
        ks = (kk / np.sqrt(N))[:, None]
        drift = (kk / N)[:, None] * (mu_d / M)
        z = (rng.standard_t(4, size=(M, n, N)) / np.sqrt(2.0)) if fat else rng.standard_normal((M, n, N))
        hit = np.zeros(n, bool)
        for j in range(M):
            act = alive & ~hit
            opl += np.where(act[:, None], drift + ks * z[j] * sq, 0.0)
            eq = bal + opl.sum(1)
            if validate:                       # continuous trailing on equity (closed-form check)
                hwm = np.where(act, np.maximum(hwm, eq), hwm)
                floor = np.minimum(hwm - L, 1.0)
            dead = act & ((eq <= floor) | ((eq <= dfloor) & (not validate)))
            if dead.any():
                stage[dead] = -1; dead_day[dead] = d; opl[dead] = 0.0
                alive &= ~dead
            h = alive & (stage == 0) & ~hit & (eq - 1.0 >= T)      # flatten at target
            if h.any():
                bal[h] = eq[h]; opl[h] = 0.0; hit |= h
        # end of day: random closes realise open P&L into the closed balance
        close = np.ones((n, N), bool) if p_close >= 1 else rng.random((n, N)) < p_close
        day_closed = np.where(close, opl, 0.0).sum(1)
        bal = bal + day_closed; opl = np.where(close, 0.0, opl)
        alive = stage >= 0
        hwm = np.where(alive, np.maximum(hwm, bal), hwm)
        newly = alive & (stage == 0) & hit
        if newly.any():
            stage[newly] = 1; pass_day[newly] = d; fstart[newly] = d
            bal[newly] = 1.0; opl[newly] = 0.0; hwm[newly] = 1.0
            cyc_start[newly] = 1.0; best_day[newly] = 0.0
        f = (stage == 1) & ~newly
        funded_days += f
        # funded payouts on demand: best day <= 40% of cycle profit, payout > 0.33L, keep cushion
        best_day = np.where(f, np.maximum(best_day, day_closed), best_day)
        prof = bal - cyc_start
        floor = np.minimum(hwm - L, 1.0)
        W = np.minimum(prof, bal - floor - keep * L)
        ok = f                                       # payout from closed balance; open P&L stays
        due = ok & (prof > 0) & (best_day <= 0.4 * prof) & (W > 0.33 * L)
        if due.any():
            disc = np.exp(-delta * d / 252.0)
            pay = np.where(due, W, 0.0)
            paid += split * pay; paid_disc += split * pay * disc; npay += due
            bal[due] -= W[due]; cyc_start[due] = bal[due]; best_day[due] = 0.0
    passed = pass_day >= 0
    fb = passed & (dead_day >= 0) & (dead_day - fstart < 126)
    return dict(p_pass=passed.mean(),
                med_days=float(np.median(pass_day[passed])) if passed.any() else float('nan'),
                p126=(passed & (pass_day < 126)).mean(),
                fbreach126=fb.sum() / max(passed.sum(), 1),
                p_paid=(npay > 0).mean(),
                payouts=paid.mean(), pay_disc=paid_disc.mean(),
                pay_per_funded_week=(paid.sum() / max(funded_days.sum() / 5.0, 1)),
                mean_npay_paid=float(npay[npay > 0].mean()) if (npay > 0).any() else 0.0)
```

**Calls.**
- **Validation:** `run(S, k, 0.04, n=3000, days=2000, M=16, H=1, fat=False, guard_z=None, validate=True, seed=11)`.
- **Grid:** `run(S, k, L, n=1500, seed=21)` for L ∈ {0.04, 0.06, 0.08}, k ∈ {0.004, 0.0075, 0.01} and S ∈ {0, 0.5, 1.0}.
- **EV:** EV = A × `pay_disc` − fee, with the fee at $107 for $10k and $537 for $100k.

**Known simplifications** (each pushes in a stated direction):
- **Optimistic for the trader:**
  - discrete monitoring;
  - the target is checked on equity, then the book flattens.
- **Pessimistic for the trader:**
  - random exits instead of trend exits, so more closed lumpiness for the best-day rule;
  - the guard is applied even when the room is ample.
- **Direction unknown:**
  - no costs inside S (S is net by definition);
  - no news-window or weekend effects;
  - the same fee for every drawdown option.
