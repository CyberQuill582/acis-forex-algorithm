# Research: scheduled macro-event risk & historical event calendars (2012–2025)

> **What this is and who asked for it.** A research pass commissioned by the ACIS session coordinator on 2026-09-16, briefed as "market-microstructure researcher": (A) the documented effect of trading through scheduled high-impact releases on an intraday-to-2-day systematic retail FX system (EUR/USD, USD/JPY, spot gold), and (B) where to get a free/cheap **historical economic event calendar covering 2012–2025**, with licensing checked. Written up on 2026-09-17 from material gathered 2026-09-16.
>
> **Status: COMPLETE.** Findings are final. This document is the record — it lives in `archive/` and is deliberately out of the orienting read path.
>
> **Scope discipline:** research only. No engine code, config, spec or ledger was modified. Two files were opened read-only to ground Part A6: `core/optimizer/costs.py` and `config/instruments.yaml`.

---

## Method note and its one weakness

The session's WebSearch budget (200 calls) was already exhausted by earlier work in the same process, so after two searches this pass worked entirely by **direct fetch of primary URLs** — PDF extraction, terms-of-service pages, and live API probes. That biased the work *toward* primary sources, which is what the brief asked for.

It has one real cost, stated plainly: **no broad discovery was possible for retail-broker execution-quality disclosures.** Part A3 is therefore the weakest section and is graded accordingly. Everything else comes from documents read directly.

**Grading key**

| Grade | Meaning |
|---|---|
| **[ACADEMIC]** | peer-reviewed or central-bank working paper, read directly |
| **[ACADEMIC-2°]** | academic claim seen only in a search summary, *not* verified against the primary |
| **[BROKER-PRIMARY]** | broker / prop-firm / regulator published text, read directly |
| **[PRIMARY-DATA]** | measured by me from a live API or page during this research |
| **[CREDIBLE PRACTITIONER]** | named practitioner / industry source |
| **[UNVERIFIABLE]** | folklore, marketing content, secondary blogs |
| **[DERIVED]** | my own arithmetic from the graded inputs above — reasoning, not observation |

---

# PART A — trading through scheduled high-impact releases

## A1. Spread widening around NFP / FOMC / CPI

### Institutional (EBS interdealer) — the honest baseline

**Yamada & Ito, "Price discovery and liquidity recovery: Forex market reactions to macro announcements", NBER WP 27036 / *Journal of International Money and Finance* 120 (2022) 102502.** 20 years of ICAP **EBS** tick data (1999–2017), EUR/USD, around US macro announcements. PDF extracted and read directly. **[ACADEMIC]**

- Free full text: https://www.nber.org/system/files/working_papers/w27036/w27036.pdf
- **Table 1 — median EUR/USD bid-ask spread measured at announcement + 30 seconds, in pips, by year:**

| Year | 1999 | 2003 | 2005 | 2007 | 2009 | 2010 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BAS at +30s (pips) | 0.95 | 0.91 | 0.83 | 0.74 | 1.35 | 0.79 | 0.77 | 0.76 | 0.77 | 1.33 | 1.33 | 0.89 |

- Mechanism, verbatim: *"liquidity dries up prior to the announcement time, as traders prefer to stay on the sidelines given a strong amount of uncertainty. After the number of macro statistics is announced and news contents are fully digested, the liquidity recovers to the pre-announcement time."*
- **Recovery horizon:** the liquidity-recovery measure is parameterised with **T = 300 seconds**, and Figure 3 plots the recovery path over **0–240 seconds**, converging toward 1. Price discovery uses **T = 600 s**, plotted 0–600 s.
- Headline finding: *"the speed of price discovery has changed little and the speed of liquidity recovery has **slowed down** over the years"* — i.e. **liquidity recovery has not improved with electronification; it has got worse.**
- **Calibration point that matters:** on EBS the widening is *modest* — roughly 0.8 → 1.3 pips at +30 s in bad years. **The spectacular widening retail traders see is a retail-book phenomenon, not an interdealer one.** Do not import retail folklore numbers as if they described the underlying market.
- Data caveat they state: EBS minimum tick changed 1 pip → 1/10 pip (7 Mar 2011) → 1/2 pip (24 Sep 2012), making cross-2011/2012 spread comparisons discontinuous. Directly relevant — the ACIS sample starts in 2012.

**Chaboud, Chiquoine, Hjalmarsson & Vega on algorithmic trading around announcements.** Seen in a search summary only: *"during the minute right before scheduled macroeconomic news announcements, bid-ask spreads widen by over 30% [for algorithmic traders], which is much larger than the 10% widening by dealers."* **[ACADEMIC-2°]** — the exact percentages are **unconfirmed against the primary**. The *direction* (widening begins in the minute **before** release; machine liquidity withdraws harder than human liquidity) is corroborated independently by Yamada-Ito's pre-announcement dry-up.

**Chaboud, Chernenko & Wright, "Trading Activity and Macroeconomic Announcements in High-Frequency Exchange Rate Data", *JEEA* 6(2-3), 2008; Fed IFDP 903.** Located, not extracted. **[ACADEMIC-2°]**
- https://www.federalreserve.gov/pubs/ifdp/2007/903/ifdp903.pdf
- Relevant finding: a sharp pickup in EBS trading **volume** in the minutes after US announcements **which occurs even when the release is exactly in line with expectations.**
- **Consequence for ACIS:** volume/activity regime filters will fire on event minutes **even with zero surprise**. An activity-based regime classifier cannot distinguish "news happened" from "news surprised".

**Andersen, Bollerslev, Diebold & Vega (2003), "Micro Effects of Macro Announcements", *AER* 93(1) 38-62 / NBER w8959.** Extracted and read directly. **[ACADEMIC]**
- https://www.nber.org/system/files/working_papers/w8959/w8959.pdf
- Baseline spread for scale: *"0.16% is also large relative to the average DM/$ spread, which tends to be around **0.06%** during the period we study"* (1991–2001, citing Bessembinder 1994 and Hasbrouck 1999) — roughly **1 pip** on a 1.60 DM/$.
- **Implication:** the pre-electronic baseline spread was already ~1 pip, so with modern sub-pip EBS spreads the *relative* widening today is **larger** than these older papers imply.

### Retail brokers — the gap in the evidence

No broker execution-quality disclosure with numbers could be obtained. The FXCM / IG / Pepperstone / OANDA execution pages probed all returned 404 or 403, and there was no search budget to rediscover their current URLs.

What exists is **[UNVERIFIABLE]** secondary material from the one search that did run:

- "EURUSD spreads typically widen anywhere from **50% to several hundred percent** above baseline during the ±2 minute NFP window"
- "EUR/USD spreads normally under a pip can hit **10, 15, sometimes 20 pips** in the first seconds"
- "roughly **2 to 5 seconds before** an NFP release, Tier-1 liquidity providers systematically cancel their resting limit orders at the top of the book"
- "it usually takes **a couple of minutes or more** for the spread to narrow to something resembling normal"

Sources: https://fxnx.com/en/blog/spread-widening-scheduled-news-peaks-recovery-times and https://www.wikifx.com/en/newsdetail/202606097794817944.html — marketing/content sites.

> **Do not put these numbers in the spec as facts.** They are directionally plausible and evidentially worthless.

### The structural point — and why this gap is closeable

The ratio of **retail-quoted spread to EBS spread in the event window** is the single number nobody publishes, and it is exactly the number the ACIS cost model depends on.

**This does not have to be taken on faith.** The Dukascopy tick set is bid+ask, 2012–2025, 8 instruments. Once release timestamps exist, the spread percentile path from −120 s to +300 s can be computed per instrument and per event class. That converts A1 from literature-grade to own-data-grade, and it is the single highest-value use of the calendar being built.

---

## A2. Price jump / gap magnitude in EUR/USD

**Yamada & Ito, Table 2** — median absolute EUR/USD log return over the **10 minutes after** the release, in basis points (1 bp ≈ 1.1 pips at 1.10), plus the regression coefficient on a 1-standard-deviation surprise (also in bps of 10-min return). **[ACADEMIC]**

| Release | coef. on 1-SD surprise (bps) | t-stat | median \|10-min return\| (bps) |
|---|---|---|---|
| **Change in Nonfarm Payrolls** | −20.19 | −6.46 | **22.9** |
| Unemployment Rate *(same release)* | +7.82 | +3.66 | 22.9 |
| Avg. Hourly Earnings *(same release)* | −7.96 | −2.84 | 22.9 |
| GDP Advance | −11.07 | −4.45 | 13.4 |
| ISM Manufacturing | −6.84 | −4.45 | 10.0 |
| Trade Balance | −6.45 | −4.30 | 9.8 |
| **CPI** | −2.35 | −2.15 | **9.6** |
| Retail Sales | −6.05 | −4.43 | 9.4 |
| Consumer Confidence | −4.64 | −3.44 | 8.9 |
| Durable Goods Orders | −3.05 | −3.10 | 7.5 |
| ADP | −4.98 | −2.96 | 6.2 |

Read as: **the median NFP 10-minute EUR/USD move ≈ 22.9 bps ≈ 25 pips**, of which a 1-SD payroll surprise accounts for ≈ 20 bps ≈ 22 pips. CPI's median ≈ 9.6 bps ≈ 10.5 pips. **NFP's median is ~2.4× CPI's** — the tiers are not interchangeable.

**ABDV (2003)** for the 5-minute horizon and a tail reference. **[ACADEMIC]**

- *"a one standard deviation U.S. payroll employment surprise tends to appreciate (if positive) or depreciate (if negative) the dollar against the DM by **0.16 %**"* — in the **first 5-minute interval**.
- *"only **0.7%** of our 5-minute returns show an appreciation or depreciation bigger than **0.10%**."*
- **⇒ The NFP 5-minute bar is routinely in the top ~0.7% tail of the entire 5-minute return distribution.** This is the cleanest single-line statement of the distortion.
- **Adjustment structure — two different clocks:**
  - *"very quick exchange rate conditional mean adjustment, characterized by a **jump immediately following the announcement, and little movement thereafter**"*
  - *"exchange rate **volatilities adjust only gradually**, with complete adjustment occurring only after J = 12 5-minute periods, or **one hour**."*
  - **⇒ The *level* is repriced in ~5 minutes; the *volatility* stays elevated for ~60 minutes.** Any ATR / vol-regime estimator is contaminated for a full hour after the release, not for two minutes.
- Announcement-only regressions reach **R² ≈ 0.3, sometimes approaching 0.6**, versus near-zero R² unconditionally.

**Lahaye, Laurent & Neely, "Jumps, Cojumps and Macro Announcements", FRB St. Louis WP 2007-032D (Aug 2009) / *Journal of Applied Econometrics*.** Extracted and read directly. **[ACADEMIC]**

- https://s3.amazonaws.com/real.stlouisfed.org/wp/2007/2007-032.pdf
- At 15-minute sampling: **dollar exchange rates jump on ~25% of sample days**; P(jump per 15-min observation) ≈ **0.25–0.37%**.
- **Mean absolute FX jump size = 0.27% to 0.36%** (vs 0.51–1.61% for stock-index and bond futures). Coefficient of variation of |jump| ≈ 63–74% across assets.
- *"Nonfarm payroll and federal funds target announcements are the most important news across asset classes. Trade balance shocks are important for foreign exchange jumps."*
- Intraday timing: *"Exchange rate jumps are modestly more frequent around **8:30 a.m.**, 16:00 to 20:00 and 22:00–02:00 … Exchange rate jumps tend to get larger after the opening of European markets … and appear to be **especially large near announcements**."*
- **The low-liquidity mirror, which matters for a 24h system:** jumps are *also* frequent during "Tokyo lunch and early Asian trading" — *"illiquidity can cause jumps"* — and those are *"more frequent but smaller"*. **An event filter must not be the only thin-liquidity filter.**

### What does not exist, and what to do about it

**No published percentile table of EUR/USD NFP moves at 1 s / 10 s / 1 min / 5 min could be found**, and on the evidence it does not exist in the free literature at that resolution.

It is directly producible: with ~160 NFPs and ~110 FOMCs in 2012–2025, the Dukascopy set supports 5th/25th/50th/75th/95th/99th percentiles per horizon, per instrument.

> **Choose the avoidance window from your own percentiles, not from a prop firm's rulebook.**

---

## A3. Slippage on market and STOP orders during releases

**NFA Compliance Rule 2-43 (US retail forex).** Read directly. **[BROKER-PRIMARY / regulator]**

- https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43
- Verbatim: *"A Forex Dealer Member may not cancel an executed customer order or adjust a customer account in a manner that would have the direct or indirect effect of changing the price"* — except where favourable to the customer as part of a complaint settlement, or where initiated by a non-affiliate straight-through-processing counterparty.
- **Implication for the model:** in the US, an adverse slipped fill during a release **stands**. The dealer may not re-price it and may not cancel it. **Slippage is a real, irreversible cost — not a reversible glitch.** (The rule blocks abuse of the favourable direction too; it does not cap slippage.)

**What is *not* documented anywhere reachable:** a quantitative, broker-published distribution of stop-order slippage during Tier-1 releases. Brokers publish aggregate "% filled at requested price or better" figures dominated by non-event minutes, which are useless for this question. No FCA / ESMA / CFTC publication with event-window slippage numbers was found.

**The one hard, universally-published broker fact** **[BROKER-PRIMARY, structural]**: ordinary stop-loss orders are **not guaranteed**; guaranteed stops are a separately-priced product precisely because the broker is pricing gap and slippage risk. **The existence and pricing of guaranteed-stop premiums is the market's own estimate of event-window stop slippage.**

### Recommendation

Treat A3 as an **open measurement**, and log it in `OPERATIONS_LEDGER.md` as a day-one live observable — this is exactly what the standing operational-referent pass exists for (GAP-0001 territory).

Until live fills exist, model event-window stop slippage from own tick data. The honest proxy: **the distance from the stop level to the first opposite-side quote actually printed after the level was crossed**, measured on Dukascopy quotes in event windows. That is a **lower bound** on real retail slippage — it ignores latency, queue position and LP rejection.

---

## A4. "Stop hunting" — evidence vs folklore

**Osler, "Stop-Loss Orders and Price Cascades in Currency Markets", FRB New York Staff Report 150 (later *JIMF* 24(2) 2005, 219-241).** PDF extracted and read directly. **[ACADEMIC]**

- https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf
- **Order composition:** *"Stop-loss orders represent **43 percent** of all orders by volume, and **45 percent** by value."*
- **Round-number clustering (Osler 2002/2003):** *"Almost **10 percent** of all such orders are placed at rates ending in 00 … about **3 percent** of orders are placed at each of the other rates ending in 0 … about **2 percent** of orders are placed at each of the rates ending [in other digits]."*
- **The asymmetry that makes it exploitable:** *"**14.3 percent** of executed stop-loss BUY orders have requested execution rates ending in the range **[01,10]**, while only **6.9 percent** of those orders have requested execution rates ending in the range [90,99]."*
  → stop-buys sit just *above* round numbers, stop-sells just *below*, so crossing a round number triggers a wave **in the direction of travel**.
- Take-profit orders cluster differently and are negative-feedback (they do **not** cascade): *"About **9.9 percent** of executed take-profit orders (weighted by [value]) [end in 00]… [the corresponding figure] for … stop-loss orders is **3.8 percent**."*

### The number that deflates the folklore

> *"dollar-mark moves an average **0.061 percent** during the 15 minutes after crossing a round number, but only **0.054 percent** after crossing an arbitrary number."*

**That differential is 0.007% ≈ 0.7 basis points ≈ ~1 pip over 15 minutes.** It is unambiguously real — round > arbitrary in **51 of 58** ten-day intervals, marginal significance below 0.001% — but its magnitude is **about one pip**, comparable to the spread and far below any sensible stop distance.

### Verdict

The academic evidence **supports a mechanism** (clustered stops → positive-feedback cascades → measurably faster trending after round numbers) and **refutes the retail narrative** (a broker deliberately spiking your particular stop).

The *mean* effect is ~1 pip. **The tail is where it bites.** Osler opens: *"On October 7, 1998, the dollar-yen exchange rate fell **11 percent**. On March 7, 2002, the rate dropped over **3 percent**"* — against a *"**0.7 percent** standard deviation of daily returns"* — and attributes the March 2002 move partly to stop waves, per Deutsche Bank's own analysis. Osler's framing: the cascades stop-loss orders contribute to *"need be neither dramatic nor infrequent."*

**Design consequence: do not build an anti-stop-hunting feature. Do avoid placing stops at round numbers, and do assume cascade-fat tails when a release pushes price through a cluster.**

---

## A5. What credible sources recommend, and what prop firms mandate

### Prop firms — published rules, read directly

**FTMO** — https://ftmo.com/en/faq/can-i-trade-news/ **[BROKER-PRIMARY]**

- Exact rule: *"it is not permitted to open or close any trades, **including the execution of pending orders (such as Stop Loss or Take Profit)**, within a time window starting **2 minutes before and ending 2 minutes after** the release of selected news announcements."*
- Scope: applies on **funded FTMO Accounts** (Standard); **not** during Evaluation; **Swing accounts have no news restriction**.
- Instruments: *"USD pairs, EUR pairs, GBP pairs, CAD pairs, AUD pairs, NZD pairs, CHF pairs, **Gold (XAUUSD)**, US Indices, DXY, and Crude Oil"* — **XAU/USD explicitly in scope**, directly relevant to the third ACIS instrument.
- Calendar source: *"our Economic Calendar, where these restricted events are marked by the note **'Restricted event'**."*
- Positions opened **more than 2 minutes before** the event may be held through it.

**The5ers** — https://the5ers.com/faqs/can-i-trade-during-news/ plus their July 2024 announcement **[BROKER-PRIMARY]**

- *"Executing orders **2 minutes before until 2 minutes after** high-impact news is prohibited."* Profits in that window are **deducted**; losses are the trader's. Since July 2024 it is a profit deduction, **not** termination; TP and SL may still trigger.
- Calendar source: *"The5ers refers to **Forex Factory** and follows the **server time**."* — note the server-time dependency, a real DST hazard, and note that their chosen source is the one with the worst licence (see B1).

**Topstep** — **[BROKER-PRIMARY, with conflicting secondary claims]** Topstep's own position: news trading is permitted at the trader's risk, with **no published blackout window**. What *is* prohibited is *"purposefully trading at maximum position size into a major news event"* as a prohibited strategy. Several third-party sites assert a 2-minute rule; this could not be corroborated from Topstep's own text and should be treated as unreliable.

**MyForexFunds successors** — not checkable without search budget.

### The convergent standard, and what it actually means

**±2 minutes around Tier-1 releases, sourced from Forex Factory's high-impact tier**, is the *de facto* industry rule.

> It is a **risk-transfer rule for the firm**, not an edge-preservation rule for the trader. The firm's concern is that a trader's tail loss exceeds the firm's buffer. **It is evidence about tail severity — not about optimal avoidance.**

### What the evidence actually recommends **[DERIVED from A1–A4]**

The ±2 min window is too short for a *systematic* system, because it is calibrated to price-jump risk alone. The academic timing evidence gives three different clocks:

| | Window | Basis |
|---|---|---|
| **1. No new entries, no discretionary exits** | **−2 min to +5 min** | Covers the jump (ABDV: level repriced in ~5 min) and the spread hole |
| **2. Size reduction / no fresh risk** | **−5 min to +15 min** | Covers liquidity recovery (Yamada-Ito T = 300 s, path plotted to 240 s, *slowing over the years*) and the cascade tail |
| **3. Do not trust the vol / ATR / regime estimate** | **+0 to +60 min** | ABDV: volatility fully adjusted only after ~1 hour |

**Window 3 is the one almost everybody misses, and it is the one that matters most to the ACIS architecture** — the Governor sizes off ATR and the regime classifier reads fast stats. An hour of post-announcement elevated vol will make the regime classifier believe the world changed.

> **Consider flagging event-contaminated bars rather than deleting them.** Deletion creates its own bias.

**Hold-through is a separate decision from entry.** FTMO permits holding a position opened >2 min before; The5ers permits SL/TP to trigger. For a 2-day-horizon system, forced flattening before every Tier-1 release would shred the strategy. The sane policy: **no new risk in the window; existing risk held with a server-side stop; no stop placed at a round number.**

---

## A6. Backtest distortion — the arithmetic, shown

### Step 1 — what fraction of trading minutes is inside a Tier-1 window?

**[PRIMARY-DATA]** Measured from TradingView's public economic-calendar endpoint (see Part B for why that endpoint is *legally* disqualified — it was used here only to *measure a statistic*, not as a data dependency), calendar year **2019**, countries **US, EU, DE, GB, JP**, `importance >= 1` (their high tier):

```
2019: 5,637 total events; 246 high-impact
high-impact by country: US 96, DE 50, GB 48, JP 40, EU 12
distinct high-impact release MINUTES: 217   (fewer than events — NFP/UR/AHE share one minute)
FX trading minutes per year (52 wk x 5 d x 24 h x 60) = 374,400

union coverage of +/- W minutes around each distinct release minute:
  +/-  2 min :   1,085 min =  0.290 %
  +/-  5 min :   2,387 min =  0.638 %
  +/- 15 min :   6,717 min =  1.794 %
  +/- 30 min :  12,875 min =  3.439 %
  +/- 60 min :  25,082 min =  6.699 %
```

**Independent cross-check — ABDV [ACADEMIC]:** *"fifty-eight percent of the days in our sample contain a news announcement, [but] the news predicts only … the 5-minute post-release intervals, which correspond to only **two tenths of one percent** of the sample observations."*

ABDV's 0.2% (US-only, one-sided 5-min) vs the measured 0.29% (5 countries, two-sided ±2 min). **Consistent.**

> **Tier-1 windows are ~0.3% of trading time at ±2 min, and ~0.6% at ±5 min.**

### Step 2 — what fraction of *volatility* is in those minutes?

**[DERIVED]** from Yamada-Ito's median |10-min| plus a baseline:

- EUR/USD long-run annualised vol ≈ 8% ⇒ daily σ ≈ 8%/√252 ≈ 0.50% ⇒ per-10-min σ ≈ 0.50%/√144 ≈ 4.2 bps ⇒ median |return| ≈ 0.6745σ ≈ **2.8 bps**.
- Intraday vol is U-shaped and 13:30 UTC is already a high slot, so a fairer *active-hours* 10-min median is **~4–6 bps**.
- NFP median |10-min| = **22.9 bps** ⇒ **≈ 4× to 8×** the typical active-hours move ⇒ **variance multiple m ≈ 16× to 64×**.
- Variance share inside a window of time-share *s*: `s·m / (s·m + (1 − s))`, with **s = 0.0064** (±5 min):

| m (variance multiple) | share of annual EUR/USD variance inside ±5 min Tier-1 windows |
|---|---|
| 20× | **11.4 %** |
| 40× | **20.5 %** |
| 64× | **29.2 %** |

> **Roughly 10–30% of EUR/USD's annual return variance is generated in ~0.6% of trading minutes.**

Order-of-magnitude corroboration: ABDV's *"only 0.7% of 5-minute returns exceed 0.10%"* combined with *"a 1-SD payroll surprise moves DM/$ 0.16% in 5 minutes"* says the NFP bar sits *routinely* in that 0.7% tail.

### Step 3 — what the ACIS cost model charges there

Read read-only from the repo. `core/optimizer/costs.py`:

```python
def per_side_cost(self, spread: float) -> float:
    return spread / 2.0 + self.commission_per_side + self.slippage_per_side
```

`config/instruments.yaml`:

| Instrument | `commission_per_side` | `slippage_per_side` | = |
|---|---|---|---|
| `EUR_USD` | 0.0 | 0.00002 | **0.2 pip per side, constant** |
| `USD_JPY` | 0.0 | 0.002 | **0.2 pip per side, constant** |

Two observations:

1. **The spread half is data-driven** — `per_side_cost` takes the *observed* spread. If the harness feeds the real Dukascopy quoted spread at the fill instant (rather than a per-instrument constant), the *spread* component of the event-window error is largely already handled, and better than the brief's premise of "a constant declared spread" assumed.
   > **Open item to verify: does the harness actually pass the tick-time spread, or a constant? If a constant, that is a finding in its own right.**
2. **The slippage term is a flat 0.2 pip per side, always.** That is the structurally wrong piece — and it is wrong *precisely* in the 0.3% of minutes that generate 10–30% of the variance.

### Step 4 — net-PnL overstatement **[DERIVED]**

Per event-window round trip on EUR/USD:

- **Modelled:** half(entry spread) + half(exit spread) + 0.4 pip. With a Dukascopy ECN event spread ≈ 1.5 pips on entry and ≈ 0.2 pips on a later exit: ≈ 0.75 + 0.10 + 0.40 = **≈ 1.25 pips**.
- **Retail reality:** a retail book marks up a thinner book — plausibly a 4–8 pip effective half-spread on entry plus 2–5 pips adverse slippage on a market or stop order: ≈ **7 pips**.
- **Error ≈ +5 to +6 pips of unmodelled cost per event-window round trip.**

Now weight by how often trades land there. **Trade arrivals are not uniform in time, and this is the crux.** A breakout / momentum / volatility-expansion system is *attracted* to exactly these minutes, because that is where range expansion happens. Realistic over-representation versus the 0.64% time share: **5×–20×**.

| p = share of round trips in a ±5 min Tier-1 window | avg unmodelled cost per trade (at 5.5 pips) | erosion of a 0.3–1.5 pip net edge |
|---|---|---|
| **3 %** (mildly event-seeking) | 0.17 pip | **11 % – 55 %** |
| **10 %** (typical breakout system) | 0.55 pip | **37 % – 183 %** — *can flip the sign* |
| **20 %** (aggressive vol-expansion) | 1.10 pip | **73 % – 367 %** — *certainly flips the sign* |

> **Headline.** A backtest that trades through releases with a flat 0.2-pip-per-side slippage constant **overstates net PnL by roughly 10–55% of the edge** for a mildly event-seeking system, and **can invert the sign entirely** for a breakout system. The error is not diffuse — it is concentrated in ~0.6% of the time, **which is why it survives every aggregate sanity check.**

### Step 5 — three errors worse than the PnL number

**1. Stop-fill asymmetry corrupts the left tail, and therefore the §14 honesty gates.**
A tick backtest fills a stop at the first tick through the level plus 0.2 pips. Reality in an event window is 3–15 pips beyond, and in a true tail (CHF Jan-2015, GBP Oct-2016, JPY Jan-2019) hundreds of pips. With 20-pip stops and 10% of stop-outs in event windows, the mean loss per losing trade rises ~2.5% — trivial — **but the 99th percentile of the loss distribution rises enormously.**
> This directly falsifies the Kupiec VaR tally and the intraday-drawdown gate — **the very gates built to enforce honesty. They can pass while being wrong, for a reason the gates cannot see.** *Rank this first.*

**2. Fill-rate overstatement.**
The backtest never gets rejected or requoted. Retail market orders during Tier-1 releases are rejected or requoted at materially elevated rates. The backtest gets 100% fill in exactly the minutes where the modelled PnL looks best. **This is a selection bias, not a cost bias — no cost model fixes it.**

**3. Regime / ATR contamination for 60 minutes.**
ABDV: volatility adjusts fully only after ~1 hour. The Governor sizes off ATR; the regime classifier reads fast stats. An hour of post-release elevated vol systematically mis-sizes and mis-classifies — **and it does so identically in backtest and live, so it will never surface as a backtest-vs-live divergence.** It is a persistent, invisible mis-specification.

### Step 6 — closing the gap without inventing numbers

1. **Build the calendar** (Part B), joined to the existing DST-correct `{zone, at}` clock (GAP-P12D-10 / master v2.14). **The event calendar must use the same local-time machinery — not a naive UTC offset.**
2. **Measure from Dukascopy quotes**, per instrument and event class: the spread percentile path −120 s → +300 s, and the "distance from stop level to next available opposite-side quote" distribution in event windows.
3. **Replace the scalar `slippage_per_side` with an event-state-conditional friction**: normal / ±5 min Tier-1 / ±60 min Tier-1-shadow. This keeps the C8 "one cost model, one module" law intact — **a parameter change, not a second cost model.**
4. **Run the walk-forward twice — with and without the event filter.**
   > **If the edge survives only when trading through releases, the edge is a cost-model artefact.** Cheap, decisive, and it belongs in `falsify_engine.py`.

---

# PART B — free/cheap historical event calendars 2012–2025, with licensing

## B0. The finding that governs everything else

> **Almost no free source gives an authoritative release *instant*.** They give either (a) a date with no time, or (b) a time of unverifiable provenance under terms that forbid you from using it.

The one clean path is to **assemble it from official statistical-agency and central-bank release schedules**, which are public domain (US) and which *do* publish the minute.

## B1. Sources checked

### ★ BLS yearly release schedules — the best US source, full stop

- **URL pattern:** `https://www.bls.gov/schedule/{YEAR}/home.htm` — **verified working for 2012 and 2015**.
- **Timestamp: date AND time, with an explicit timezone note.** **[PRIMARY-DATA]** Verified from the 2012 page:
  - *"Friday, January 06, 2012 08:30 AM Employment Situation for December 2011"*
  - … through *"Friday, December 07, 2012 08:30 AM Employment Situation for November 2012"*
  - footer: ***"NOTE: All times on calendar are Eastern Time."***
  - From the 2015 page: *"Friday, January 09, 2015 | 08:30 AM | Employment Situation for December 2014"*; *"Wednesday, January 14, 2015 | 08:30 AM | U.S. Import and Export Price Indexes for December 2014"*
- **"Eastern Time" → `America/New_York` → DST-correct by construction**, provided the zone is applied rather than a fixed −05:00.
- **Coverage:** every BLS principal release — Employment Situation (NFP, unemployment rate, average hourly earnings), CPI, PPI, ECI, JOLTS, Productivity & Costs, Real Earnings, Import/Export Price Indexes, State Employment. **A large fraction of the Tier-1 US set.**
- **Actual / forecast / previous: NO** — schedules only. Actuals come from FRED/ALFRED; consensus forecasts are the genuinely hard part (see B3).
- **Licence — clean.** https://www.bls.gov/bls/linksite.htm:
  > *"The Bureau of Labor Statistics (BLS) is a Federal government agency and **everything that we publish, both in hard copy and electronically, is in the public domain**, except for previously copyrighted photographs and illustrations."*
  > *"You are free to use our public domain material without specific permission, although we do ask that you cite the Bureau of Labor Statistics as the source."*
- **Access — the one catch.** bls.gov **blocks bots**. A `curl` fetch returned: *"Automated retrieval programs (commonly called 'robots' or 'bots') can cause delays and interfere with other customers' timely access to information. Therefore, bot activity that doesn't conform to BLS usage policy is prohibited."*
  Their policy page https://www.bls.gov/bls/pss.htm: *"**Excessive** robot activity on BLS websites is prohibited"*; robots must *"contain information that can be used to contact the owner"*; they block *"robots that attempt to access or download survey information multiple times per second."*
  > **This is an access-rate rule, not a licence restriction. The data is public domain.** 14 one-off page fetches (one per year, 2012–2025), done politely with an identifying User-Agent and seconds apart, is squarely inside their policy. **Fetch once, store locally, never re-fetch.**

### ★ Federal Reserve — FOMC

- **Calendar page:** https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm — **meeting dates only, no times**; covers 2021–2027 (older via https://www.federalreserve.gov/monetarypolicy/fomc_historical.htm). **[PRIMARY-DATA]**
- **Press-release pages** (checked `monetary20150318a.htm` and `monetary20121212a.htm`): header reads *"March 18, 2015 / Federal Reserve issues FOMC statement / For immediate release"* — **date only, no time.** **[PRIMARY-DATA]**
- **The RSS feed DOES carry the minute, in UTC:** https://www.federalreserve.gov/feeds/press_monetary.xml returns e.g. `<pubDate>Wed, 16 Sep 2026 18:00:00 GMT</pubDate>` = **14:00 EDT**; `Wed, 19 Aug 2026 18:00:00 GMT` for the minutes. **[PRIMARY-DATA]** **But the feed holds recent items only — it is not a 2012–2025 archive.**
- **⇒ For 2012–2025 the release-time convention must be applied, and it changed.** FOMC statements: **14:00 ET** under the current regime; historically **14:15 ET**; and in **2011–2012 the statement came out 12:30 ET on press-conference days**.
  > ⚠️ **These transition dates were NOT verified from a primary source and must be before encoding.** Getting the 2011–2012 press-conference-day statements wrong puts the window **90 minutes off** on exactly the highest-impact events of that period.

### BEA

- **Schedule:** https://www.bea.gov/news/schedule — **date + time** (e.g. *"September 30 · 8:30 AM · News · GDP (Third Estimate)…"*), but the year selector offers only **2024, 2025, 2026**. **No historical archive of the schedule.** **[PRIMARY-DATA]**
- **RSS:** https://apps.bea.gov/rss/rss.xml carries explicit DST-aware pubDates: `<pubDate>Thu, 03 Sep 2026 08:30:00 EDT</pubDate>`. **[PRIMARY-DATA]** Recent items only.
- **⇒ Historical BEA dates come from FRED release dates; the time is the stable 08:30 ET convention.** US-government public domain.

### Census Bureau

- https://www.census.gov/economic-indicators/calendar.html is JavaScript-rendered; rows could not be extracted. Census publishes on the **08:30 / 10:00 ET** convention. US-government public domain. **[PRIMARY-DATA on access; the convention itself is [UNVERIFIABLE] here]**

### ★ FRED / ALFRED — the authoritative *date* spine, but **NO time**

- **Docs read directly:** https://fred.stlouisfed.org/docs/api/fred/release_dates.html
- > **The endpoint returns only `release_id` and `date` (YYYY-MM-DD). There is no time-of-day and no timezone field.**
  **[PRIMARY-DATA — the single most important negative finding in Part B.]**
- Parameters: `api_key` (required), `release_id`, `file_type`, `realtime_start` / `realtime_end`, `limit` (1–10,000), `offset`, `sort_order`, `include_release_dates_with_no_data`. `realtime_start` defaults to **1776-07-04**, `realtime_end` to **9999-12-31** — **historical depth effectively unlimited; 2012–2025 fully covered for every release FRED tracks.**
- **ALFRED vintages** give the *as-of-that-date* value — how to reconstruct "previous" and "revised previous" honestly, **avoiding look-ahead from later revisions.** Directly valuable for the look-ahead canary work (GAP-P12D-28).
- **Licence — more restrictive than commonly assumed.** https://fred.stlouisfed.org/legal/ prohibits:
  > *"Engage, or otherwise participate, in the use of any **data mining, mirroring, robots, scraping**, or similar data-gathering or extraction methods"*
  > *"Take all the data on FRED or related services and claim it is a unique product or service."*
  Attribution required. **⇒ Scraping fred.stlouisfed.org is forbidden; the API is the sanctioned route.**
- **API terms:** https://fred.stlouisfed.org/docs/api/terms_of_use.html — requires the notice *"This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."* Rate limits discretionary and unquantified: *"may impose or adjust the limit on the amount of bandwidth you may use or the number of transactions."* Third-party series carry their owners' restrictions: *"You are solely responsible for complying with any requirements or restrictions imposed on usage of the data series by their respective owners."* Prohibited: *"Use the FRED® API for any application that replicates or attempts to replace the essential user experience of the FRED® API, or the FRED® or ALFRED® web sites."*
- **Verdict:** clean for private research **through the API with a key**, not by scraping. **Gives dates, not instants.**

### ✗ Forex Factory — licence-unclean, do not use

- `robots.txt` contains only a `Sitemap:` line (no `Disallow`) — **but the site returns HTTP 403 to non-browser user agents** (Cloudflare). **[PRIMARY-DATA]**
- **The ToS is at https://www.forexfactory.com/notices** (not `/legal`, which is a user profile; not `/terms`, which 404s). Read in full. **[PRIMARY-DATA]** Verbatim:
  > *"The copying, republication, or redistribution of FEI's copyrighted content - including but not limited to, forum posts, **calendar schedules and specs**, news mix, news comments, trader lists, and account data - is **explicitly prohibited** without prior written consent."*
  > *"The Fair Economy Economic Database ("FEED") includes all data displayed on FEI's Calendar product, including events listed, event names, **impact ratings**, descriptions, specs, links, **historic data**, and other assembled data. FEED is a unique, creative, easily-identifiable compilation requiring thousands of man-hours to compile. FEED is protected by US and international **database copyright law**, and the **copying**, republication or redistribution of FEED, in part or in whole, is **explicitly prohibited**."*
  > *"Users are not permitted to interfere with Services or **try to access them using a method other than the interface and the instructions that FEI provides**."* ← the anti-scraping clause
  > *"These terms were last updated February 2023."*
- **Note the word "copying" in the FEED clause — it is not limited to redistribution.** On its face, building a private local copy of the FF calendar for a backtest is prohibited, and scraping it is separately prohibited.
  > **This is the source everyone uses — including The5ers' own rulebook — and it is the one you cannot cleanly use.**
- Incidental observation: FF's `sitemap-calendar.xml` publishes `<lastmod>` values with a full UTC offset, e.g. `2026-09-04T08:30:00-04:00` for `us-non-farm-employment-change`, confirming FF's internal timestamps are US-Eastern-with-DST. Interesting; **not a licence to use them.**
- **GitHub scrapers exist** — `fizahkhalid/forex_factory_calendar_news_scraper` (103★, MIT), `FabianStammen/ForexFactoryScraper` (GPL-3.0), and several smaller ones. **The scraper's licence is irrelevant:** an MIT licence on the *code* grants nothing with respect to FEI's *data*. Using them puts you in breach of FF's ToS.

### ✗ Investing.com — the most restrictive terms of any source checked

- Site-wide legal notice, present on every page including the calendar, extracted from live HTML **[PRIMARY-DATA]**:
  > *"prohibited to use, store, reproduce, display, modify, transmit or distribute the data contained in this website without the explicit prior written permission of Fusion Media and/or the data provider."*
- **It prohibits "use" and "store" — not merely redistribution.** Even a private backtest copy falls outside these terms.
- `robots.txt` has **no** `Disallow` on `/economic-calendar/` — but robots.txt is not a licence.
- Full ToS body is JS-rendered; the terms PDF (`https://cdn.investing.com/about-us/terms_and_conditions.pdf`) returns 403.
- **`investpy` is broken and its author says so.** README, verbatim **[PRIMARY-DATA]**:
  > *"⚠️ `investpy` is not working fine currently due to some Investing.com changes in their APIs, so please use `investiny` in the meantime…"*
  Repo not archived (1,856★, 244 open issues, last push 2026-04-13), but the notice stands.

### ✗ Trading Economics — no free tier any longer

- The historical `guest:guest` key was probed directly. Live response for `/calendar`, `/calendar/country/united states/2015-01-01/2015-01-31`, and `/calendar/country/all/...` **[PRIMARY-DATA]**:
  > *"We are sorry, but the guest account has been discontinued. Please subscribe to a plan at https://tradingeconomics.com/api/pricing.aspx"*
  > **This is current as of this research and contradicts most online guides.**
- Pricing page: *"To prevent abuse, **trial users are limited to 100,000 data points and 100 requests for data**."* Trial fee non-refundable, auto-converts.
- **ToS** (https://tradingeconomics.com/terms.aspx) is short and notably **grants** something:
  > *"Trading Economics grants you a **limited, personal, nontransferable, revocable license to analyse data** from 232 countries…"*
  **No explicit anti-scraping clause** in the ToS as read.
- **Verdict: licence-cleanest of the commercial calendars for private research.** Cost is the barrier. The `tradingeconomics` Python package is a wrapper over the paid API.

### ✗ TradingView calendar endpoint — technically excellent, legally disqualified

- **It works, unauthenticated, with excellent timestamps.** Verified directly **[PRIMARY-DATA]**:
  ```
  GET https://economic-calendar.tradingview.com/events
      ?from=2015-01-08T00:00:00.000Z&to=2015-01-11T00:00:00.000Z&countries=US
  → {"date":"2015-01-09T13:30:00.000Z","title":"Non Farm Payrolls",
     "importance":1,"actual":252,"forecast":240, ...}
  ```
  Fields: `id, title, country, indicator, ticker, comment, period, referenceDate, source, source_url, actual, previous, forecast, actualRaw, previousRaw, forecastRaw, currency, importance, date`.
  **ISO-8601 UTC to the minute; actual AND forecast AND previous; importance tier (1 = high, 0 = medium, −1 = low).**
- **DST correctness verified:** NFP 2015-01-09 at `13:30Z` (= 08:30 **EST**, winter) and NFP 2016-07-08 at `12:30Z` (= 08:30 **EDT**, summer). ISM PMI `15:00Z` (10:00 ET); FOMC Minutes `19:00Z` (14:00 ET). **All correct.**
- **Coverage measured:** **2012 returns ZERO events.** 2013 returns 1,064 events (138 high) but is sparse in Jan–Feb — only two NFPs appear before late February. 2014 onward is dense. January 2025 alone: 325 events, 21 high.
  **⇒ usable coverage ~mid-2013 → present; does NOT cover 2012.**
- **Licence — disqualifying.** https://www.tradingview.com/policies/ §3 forbids **non-display usage**, defined to include *"automated trading, automated order generation, price referencing, order verification, **algorithmic decision-making**, algorithmic trading, smart order routing"* and *"any machine-driven processes that do not involve the direct, human-readable display of such data."* They *"expressly forbid direct non-display usage by our users."* **[PRIMARY-DATA]**
  > **Using this feed to gate a systematic backtest is the textbook definition of the prohibited use.**
  >
  > **Flagged explicitly because it is the tempting option:** free, unauthenticated, minute-accurate, has forecasts, works right now — **and its terms name this exact use case as prohibited.**

### ~ MQL5 / MetaTrader 5 built-in calendar — the best *practical* free option

- **Terminal API:** https://www.mql5.com/en/docs/calendar/calendarvaluehistory and https://www.mql5.com/en/docs/constants/structures/mqlcalendar. **[PRIMARY-DATA]**
  `CalendarValueHistory(values[], datetime_from, datetime_to, country_code, currency)`.
  `MqlCalendarValue` carries `time`, `period`, `revision`, `actual_value`, `prev_value`, `revised_prev_value`, `forecast_value`, `impact_type`.
  `MqlCalendarEvent` carries `importance` (`ENUM_CALENDAR_EVENT_IMPORTANCE`), `sector`, `frequency`, `unit`, `source_url`.
- **The timezone trap, quoted from the docs:**
  > *"All functions for working with the economic calendar use the **trade server time (TimeTradeServer)**. This means that the time in the MqlCalendarValue structure and the time inputs … are set in a **trade server timezone**, rather than a user's local time."*
  **⇒ Timestamps inherit the broker's server DST regime — typically EET/EEST, which shifts on *European* DST dates, not US ones.**
  > For a system whose entire clock discipline is `{zone, at}` (master v2.14), silently importing broker-server time would be a serious defect. **Convert explicitly and test the conversion on a known DST boundary.**
- **Web CSV export** (`https://www.mql5.com/en/economic-calendar/united-states/nonfarm-payrolls/export`) works unauthenticated: **235 rows back to 2007-03**, tab-separated `Date / ActualValue / ForecastValue / PreviousValue` — **but DATE ONLY, no time.** The page's table header says *"Date (GMT)"*; times are JS-rendered. **[PRIMARY-DATA]**
- Page disclaimer: *"The Calendar data are provided **as is** … You can use the provided information, but you accept all the risks associated with making trade decisions based on the Calendar data."* — permissive in tone, **a disclaimer, not a licence grant.**
- **Verdict:** if MT5 is already running, this is free, has the minute, has forecasts, and goes back to ~2007. Its problems are the server-timezone dependency and that MetaQuotes' calendar is itself a third-party compilation with no stated redistribution licence.

### ✗ EODHD — fails on coverage

- https://eodhd.com/financial-apis/economic-events-data-api. Returns `YYYY-MM-DD HH:MM:SS` (timezone not documented), with actual / previous / estimate. **Coverage is "from 2020 onwards" — fails the 2012–2025 requirement outright.** Requires All-In-One or Fundamentals plan; the `demo` token returns `Forbidden`. **[PRIMARY-DATA on the probe; coverage per their docs]**

### ✗ Finnhub, FinancialModelingPrep — both require keys

- `finnhub.io/api/v1/calendar/economic` → `{"error":"Invalid API key."}`; FMP `/economic_calendar` → invalid key. Economic calendar is a **premium** endpoint on both. Not investigated further. **[PRIMARY-DATA on the probes]**

### ✗ FXStreet

- Calendar API at `calendar-api.fxstreet.com` **returns HTTP 401** without credentials (tested `/en/api/v1/eventDates/...`). Docs at https://docs.fxstreet.com/ say FXStreet *"owns macroeconomic data of the most relevant events and provides it to third parties with http requests"*; OAuth2 (API Key deprecated). **No public pricing, no public licence terms, no stated historical depth.** Commercial B2B licensing — requires contacting them. **[PRIMARY-DATA on the 401]**

### ✗ Econoday — commercial only

- https://www.econoday.com/ is now a B2B product site ("Request a Demo"). No free historical access, no public API. **Econoday is the upstream compiler behind several retail calendars.** **[PRIMARY-DATA]**

### ✗ Kaggle / HuggingFace / academic datasets

- HuggingFace dataset search for "economic calendar" returned **exactly one** result: `electricsheepafrica/africa-economic-calendar-2020-2025` (54 downloads) — wrong region, wrong period. **[PRIMARY-DATA]**
- Kaggle requires authentication and could not be checked.
  > **Treat Kaggle/HF economic-calendar datasets as licence-poisoned by default** unless provenance is stated and is an official agency. Any "forex economic calendar" dataset is almost certainly a Forex Factory or Investing.com scrape, and carries their licence defect regardless of the Kaggle licence tag.

### Central banks — ECB / BoE / BoJ

- **ECB:** the press-conference page states *"The press conference can be watched live at **14:45 CET**"*. The ECB press RSS (https://www.ecb.europa.eu/rss/press.html) carries minute-precise DST-aware pubDates, e.g. `<pubDate>Wed, 16 Sep 2026 10:00:00 +0200</pubDate>` — recent items only. **[PRIMARY-DATA on both]**
  > ⚠️ **The historical decision time could NOT be verified from a primary source** (widely believed 13:45 CET pre-2022, 14:15 CET from Feb 2022, press conference moving 14:30 → 14:45). **Verify before encoding — a wrong transition date is a 30-minute error on every ECB decision in the sample.** **[UNVERIFIABLE here]**
- **BoE:** https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates lists MPC announcement **dates only, no times** (verified: "Thursday 5 February — February MPC Summary and minutes and February Monetary Policy Report", etc.). Bank Rate announcements are conventionally **12:00 London**, so the UTC instant shifts with *UK* DST. **Verify.** **[PRIMARY-DATA on dates; time [UNVERIFIABLE] here]**
- **BoJ: there is no scheduled release minute.** The policy statement is released *when the meeting ends* — typically somewhere in 03:00–04:30 UTC, but genuinely variable.
  > **A schedule-derived calendar cannot give a BoJ timestamp — an observed one is required.** This matters specifically for USD/JPY. **[CREDIBLE PRACTITIONER / structural]**
- **Corroborating academic evidence that "scheduled" ≠ "timed" — ABDV, verbatim [ACADEMIC]:**
  > *"the release times of U.S. macroeconomic indicators are known **exactly (day and time)** but only **inexactly for Germany (day but not time)**. Uncertain release times may result in less market liquidity (and trading) around the announcement times, hence resulting in **smaller news effects** around the announcements, ultimately producing a **more gradual adjustment**."*
  **⇒ Non-US, non-fixed-time releases should get a *wider but shallower* avoidance window — not the same ±2 min.**

## B2. Ranking

By **timestamp authoritativeness × coverage × licence cleanliness**, for private non-redistributed research:

| # | Source | Timestamp | 2012–2025 | Licence | Verdict |
|---|---|---|---|---|---|
| **1** | **BLS yearly schedules** `bls.gov/schedule/{YEAR}/home.htm` | **date + minute + "Eastern Time"** | **full** | **public domain** (cite BLS); polite-fetch only | **Build on this.** |
| **2** | **FRED / ALFRED release-dates API** | **date only** | full, unlimited depth | clean via API + attribution; **scraping forbidden** | Date spine + revision vintages. |
| **3** | **Fed / BEA / Census / ECB / BoE conventions + RSS** | minute (RSS, recent) / convention (historical) | dates via FRED | public domain (US); ECB/BoE permissive | Fills the non-BLS Tier-1 set. |
| **4** | **MQL5 terminal calendar** | **minute, but in broker-server tz** | ~2007+ | undefined; "as is" disclaimer | Best free practical option **if** the tz is converted explicitly. |
| **5** | **Trading Economics (paid)** | minute | full | **ToS grants a licence "to analyse data"**; no anti-scrape clause | Cleanest paid option; no free tier since guest was discontinued. |
| 6 | FXStreet API | minute | unknown | commercial, opaque | Requires a sales conversation. |
| 7 | EODHD | minute | **2020+ only** | commercial | **Fails coverage.** |
| — | **TradingView endpoint** | **minute, UTC, DST-correct** | **2013+** (no 2012) | **§3 expressly forbids algorithmic decision-making / non-display use** | **Technically ideal, legally disqualified.** |
| — | **Forex Factory** | minute | full | **FEED database copyright: copying explicitly prohibited**; scraping prohibited | **Do not use.** |
| — | **Investing.com / investpy** | minute | full | **"prohibited to use, store, reproduce…"**; investpy broken | **Do not use.** |
| — | Econoday | minute | full | commercial B2B only | No access. |
| — | Kaggle / HF datasets | varies | poor | provenance-poisoned | Nothing usable found. |

## B3. The clean-licence path — concrete build

**Spine.** FRED/ALFRED `release/dates` (API key + attribution notice) for **every release date, 2012–2025**, with ALFRED vintages for previous / revised-previous. Public, unlimited depth, no look-ahead.

**Time-of-day layer.** A small, explicit, versioned table mapping `release_id → (local_time, tz)`:

| Publisher | Time | Zone | Note |
|---|---|---|---|
| BLS | **verified per-year from the BLS schedule pages** (typically 08:30) | `America/New_York` | 14 one-off fetches, stored, never re-fetched. Don't assume — *confirm* per release per year; this also catches the odd 10:00 release. |
| BEA | 08:30 | `America/New_York` | |
| Census | 08:30 or 10:00 | `America/New_York` | per indicator |
| Fed — FOMC statement | **14:00 current; 14:15 historically; 12:30 on 2011–2012 press-conference days** | `America/New_York` | ⚠️ **VERIFY the transitions before encoding** |
| Fed — minutes | 14:00 | `America/New_York` | |
| Fed — Industrial Production | 09:15 | `America/New_York` | |
| ISM | 10:00 | `America/New_York` | private body — the *time* is a public fact, the *data* is licensed; only the time is needed |
| U. Michigan | 10:00 | `America/New_York` | as above |
| ECB | **decision time — VERIFY (13:45 → 14:15 in 2022)** | `Europe/Berlin` | |
| BoE | 12:00 | `Europe/London` | verify |
| BoJ | **no fixed time** | — | either exclude, or use a wide asymmetric window (e.g. 02:30–05:00 UTC on meeting days) rather than false precision |

**Then apply the existing `{zone, at}` clock machinery (GAP-P12D-10 / master v2.14). Do not introduce a second, naive timezone path for the calendar.**
> The specific failure mode to guard against: a calendar module that quietly does `datetime.utcoffset(-5)` while the rest of the engine correctly does zone-aware conversion. **The DST-boundary test class in SPEC §13 should get an event-calendar case.**

**Consensus forecasts.** This is the piece official sources do **not** give — and the piece every licence-unclean source *does*.
> If the event logic only needs "is this a Tier-1 window" (avoidance / sizing), **forecasts are not needed at all** and the clean path is complete. If surprise-magnitude conditioning is wanted later, that is where Trading Economics would have to be paid. **Recommend deferring it:** surprise-conditioned trading is a materially bigger modelling commitment than event avoidance, and is arguably outside what SPEC §17 asks for.

**Tiering without Forex Factory's impact ratings** (which are FEED-copyrighted). **Derive the tier from own data:** rank releases by the measured median |10-min return| in the Dukascopy ticks — exactly the statistic Yamada-Ito's Table 2 reports.

This is strictly better than an inherited impact rating:
- it is **instrument-specific** (an event that moves EUR/USD may not move XAU/USD);
- it is measured on **the actual execution venue's prices**;
- it is **licence-free**;
- it is **falsifiable**.

> It turns the impact tier from an unverifiable external input into a **derived, testable artefact** — which is the standard the external-referent audit lens would demand anyway.

---

# Bottom line for ACIS

1. **The one number to take away.** Tier-1 windows are **~0.3% of trading minutes (±2 min) / ~0.6% (±5 min)** — *measured* — and they carry **~10–30% of EUR/USD's annual return variance** — *derived*. The flat `slippage_per_side: 0.00002` charges the same 0.2 pip there as at 3 a.m. on a Tuesday.
2. **The biggest risk is not the PnL number — it is the left tail.** Event-window stop slippage is what breaks the Kupiec VaR tally and the intraday-drawdown gate, i.e. **the honesty gates can pass while being wrong, for a reason the gates cannot see.**
3. **The decisive cheap test.** Run the walk-forward with and without an event filter. **If the edge only exists when trading through releases, it is a cost-model artefact.** Belongs in `falsify_engine.py`.
4. **The calendar is buildable clean.** BLS schedule pages + FRED release dates + a small verified time-of-day table yields 2012–2025 with public-domain provenance and minute-accurate, DST-correct instants. More work than scraping Forex Factory, and the only path that breaches nobody's terms.
5. **Three things NOT verified, which must be before encoding:**
   - FOMC statement-time transitions (14:15 → 14:00, and the 12:30 press-conference-day regime in 2011–2012);
   - the ECB decision-time change (13:45 → 14:15, ~Feb 2022);
   - the BoE Bank Rate announcement time across the sample.
   **Each is a 30–90 minute error on the highest-impact events if wrong.**
6. **Scope discipline.** All of the above supports an **event-avoidance / sizing / vol-contamination** feature. Surprise-magnitude conditioning is a different and much larger commitment, needs paid forecast data, and SPEC §17 arguably excludes it.
   **Recommended landing: a Tier-1 window flag + an event-state-conditional friction parameter inside the existing C8 cost model — a parameter change, not a second cost model.**

---

# Open items this research did not close

| # | Item | Why it matters |
|---|---|---|
| 1 | **Does the harness pass the tick-time spread to `per_side_cost`, or a per-instrument constant?** | If a constant, the whole spread component of the event error is unmodelled too, not just slippage. Cheap to check; changes the severity of A6 materially. |
| 2 | **FOMC / ECB / BoE historical release-time transitions** | 30–90 min errors on the highest-impact events. Needs primary-source verification. |
| 3 | **Retail-vs-EBS spread ratio in event windows** | The number the cost model depends on; no public source. **Measurable from own Dukascopy quotes.** |
| 4 | **Event-window stop-slippage distribution** | Drives the left tail and the VaR/drawdown gates. Lower bound measurable from own quotes; true value needs live fills → `OPERATIONS_LEDGER.md`. |
| 5 | **EUR/USD NFP/FOMC move percentiles at 1 s / 10 s / 1 min / 5 min** | Does not exist publicly. Needed to *choose* the avoidance window from evidence rather than from a prop firm's rulebook. Producible from own data. |
| 6 | **Retail broker execution-quality disclosures** | Part A3's weakness, caused by the exhausted search budget. Worth one targeted pass with search available. |

---

# Sources

**Academic / central bank**
- Yamada & Ito, *Price Discovery and Liquidity Recovery: Forex Market Reactions to Macro Announcements*, NBER w27036 — https://www.nber.org/system/files/working_papers/w27036/w27036.pdf
- Andersen, Bollerslev, Diebold & Vega, *Micro Effects of Macro Announcements*, NBER w8959 — https://www.nber.org/system/files/working_papers/w8959/w8959.pdf
- Osler, *Stop-Loss Orders and Price Cascades in Currency Markets*, FRBNY Staff Report 150 — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf
- Lahaye, Laurent & Neely, *Jumps, Cojumps and Macro Announcements*, FRB St. Louis WP 2007-032D — https://s3.amazonaws.com/real.stlouisfed.org/wp/2007/2007-032.pdf
- Chaboud, Chernenko & Wright, *Trading Activity and Exchange Rates in High-Frequency EBS Data*, Fed IFDP 903 — https://www.federalreserve.gov/pubs/ifdp/2007/903/ifdp903.pdf

**Broker / prop firm / regulator**
- FTMO — Can I trade news? — https://ftmo.com/en/faq/can-i-trade-news/
- The5ers — Can I Trade During News? — https://the5ers.com/faqs/can-i-trade-during-news/
- NFA Compliance Rule 2-43 — https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43

**Official data sources**
- FRED API — release/dates — https://fred.stlouisfed.org/docs/api/fred/release_dates.html
- FRED legal — https://fred.stlouisfed.org/legal/
- FRED API terms of use — https://fred.stlouisfed.org/docs/api/terms_of_use.html
- BLS 2012 release schedule — https://www.bls.gov/schedule/2012/home.htm
- BLS 2015 release schedule — https://www.bls.gov/schedule/2015/home.htm
- BLS copyright / linking policy — https://www.bls.gov/bls/linksite.htm
- BLS robots policy — https://www.bls.gov/bls/pss.htm
- Federal Reserve FOMC calendars — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- Federal Reserve monetary press RSS — https://www.federalreserve.gov/feeds/press_monetary.xml
- BEA release schedule — https://www.bea.gov/news/schedule
- BEA RSS — https://apps.bea.gov/rss/rss.xml
- ECB monetary policy statements — https://www.ecb.europa.eu/press/press_conference/monetary-policy-statement/html/index.en.html
- ECB press RSS — https://www.ecb.europa.eu/rss/press.html
- Bank of England MPC dates — https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates

**Commercial calendars and their terms**
- Forex Factory Notices / Terms of Service — https://www.forexfactory.com/notices
- Trading Economics Terms — https://tradingeconomics.com/terms.aspx
- Trading Economics API pricing — https://tradingeconomics.com/api/pricing.aspx
- Investing.com Terms and Conditions — https://www.investing.com/about-us/terms-and-conditions
- investpy README (deprecation notice) — https://github.com/alvarobartt/investpy
- TradingView Policies — https://www.tradingview.com/policies/
- MQL5 CalendarValueHistory — https://www.mql5.com/en/docs/calendar/calendarvaluehistory
- MQL5 Economic Calendar structures — https://www.mql5.com/en/docs/constants/structures/mqlcalendar
- EODHD Economic Events API — https://eodhd.com/financial-apis/economic-events-data-api
- FXStreet API docs — https://docs.fxstreet.com/
- Econoday — https://www.econoday.com/

**Ungraded / marketing content, cited only as [UNVERIFIABLE]**
- https://fxnx.com/en/blog/spread-widening-scheduled-news-peaks-recovery-times
- https://www.wikifx.com/en/newsdetail/202606097794817944.html
