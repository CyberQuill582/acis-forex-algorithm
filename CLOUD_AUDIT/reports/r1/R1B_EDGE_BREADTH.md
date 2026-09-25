# R1B — EDGE AND BREADTH (ACIS mission R1, lane R1-B)

- **Lane:** R1-B, edge and breadth. Brief: `CLOUD_AUDIT/reports/r1/BRIEF_R1.md` §0 and §B.
- **Model and effort, as observed:** the system prompt names `claude-opus-5-5` (Opus 5.5). I cannot observe the effort setting from inside the session; the brief says xhigh.
- **Fresh context:** yes. I launched no subagents and wrote only my own files.
- **BASE:** `974dbdadd538ffd0b4941169dd8979bcabc3e8cd`, read-only at `/tmp/review-acis`.
- **Date:** 2026-09-25, 08:00–08:40 UTC by the container clock.
- **Web budget:** **36 of 40** used (WebSearch, WebFetch, and direct HTTP GETs of primary pages, counted together).
- **Status:** a finder's report (A5). It is evidence to weigh, not instruction (A9). Nothing binds until the lead verifies it (A6).
- **Data rule:** I read no market price data of any kind. Everything computed here is either:
  - arithmetic on a broker's published specification (swap points, commission, trading hours), which is documentation, not prices;
  - a synthetic random walk; or
  - arithmetic on **published** figures, quoted.
- **Price levels:** where a unit conversion needs a price level, the level is a labelled round **assumption** typed by me. It is never read from data.
- **Every strategy idea in this report is LLM-originated.** Under the contamination rule (GAP-P12D-66) it may be *falsified* on 2012–2025 history but *credited* only on forward, post-cutoff data.

---

## 1. Executive summary

1. **At FTMO, the dominant cost of a daily-to-weekly rule is the swap markup, not the spread.**
   - FTMO publishes its whole symbol specification as JSON. From its swap points, the per-side markup is:
     - FX majors: 1.3–2.6%/yr of notional;
     - gold: about 4.8%/yr;
     - index cash CFDs: 3.6–5.0%/yr.
   - That is **0.08–0.46 Sharpe units per year held (median about 0.21)**, against about 0.01–0.02 SR/yr of spread plus commission for a 16/64-speed trend rule.
   - Grade (a) for the table; the SR conversion rests on labelled price and volatility assumptions.
2. **FX carry is mostly confiscated at this venue.**
   - On FTMO's 28 G10 pairs, the positive-carry side keeps a **median of 21%** of fair carry.
   - 6 of 28 pairs pay on *both* sides.
   - So carry is a **cost to model**, not a return source to trade. Grade (a); the decomposition is price-free.
3. **Under that markup, a full-time pooled trend program on the proposed universe is marginal-to-negative after costs.**
   - Net portfolio SR ≈ (s − c)·√N_eff, with N_eff ≈ 6. That gives **−0.15 to +0.32** at FTMO's median markup, against **+0.32 to +0.79 on a swap-free account**, for per-instrument gross SR s = 0.15–0.34.
   - s = 0.34 is the published median single-asset TSMOM gross SR (Babu et al. 2020 (a)); 0.15 is a post-publication haircut.
   - **Consequence:** the account's swap regime is the single most decisive, and cheapest, owner decision for the daily family. E8 is reported to sell a swap-free option at +10% of the fee, and FTMO to offer Islamic accounts. Both reports are (c) and unverified; eligibility terms must be asked openly, never misrepresented.
   - Grade: derived, with (a) inputs.
4. **Breadth.**
   - Published per-instrument trend-return correlations are low *across* classes (0.07; Babu et al. (a)). FX, however, shares a dollar and a carry factor, which "account for 20% to 90%" of bilateral moves (Verdelhan 2018 (a)).
   - For the proposed 23 explored instruments, the **effective breadth is about 5–8, against about 2–3 for FX-only**. Adding FX pairs beyond about 10 buys little; indices, metals and energy buy the breadth.
   - Grade: (a) inputs; the within-class correlation is a swept assumption.
5. **Few rules is right, and breakout is not a second family.**
   - On a synthetic null, Carver-style breakout(N) and EWMAC at the matched speed have **position correlation 0.95**. TSMOM(12m) correlates 0.77 with EWMAC(64,256).
   - They are variants of one TREND family, and trial accounting should count them that way.
   - Carver's own record: adding four new rule types gave "slightly worse performance; although not with a statistically significant difference" (b).
   - Grade: synthetic receipt plus (b).
6. **The combination should be fixed, not fitted.**
   - Equal weights across three EWMAC speeds (FDM about 1.09).
   - Class-equal, then equal-within-class, instrument weights (IDM about 2.4–2.5).
   - Forecast scale fixed on the synthetic null, spending zero looks.
   - "Of the 14 models … none is consistently better than the 1/N rule" (DeMiguel et al. 2009 (a)).
   - The only per-instrument deviation allowed is the pre-registered cost filter.
7. **Universe: 30 instruments, all on FTMO, all with Dukascopy history to at least 2013.** 23 are explored and **7 held out by a salted-hash draw** that nobody chooses:
   - FX: AUD/NZD, NZD/USD, CAD/JPY;
   - metal: XCU/USD;
   - indices: GER40, US100;
   - energy: USOIL.

   **Excluded:**
   - XPT (Dukascopy from 2021-11-01) and US2000 (from 2018-08-08);
   - softs, whose FTMO Swing leverage is 1 and whose Dukascopy history starts in 2017;
   - exotics, whose markups are 10–135 points.

   Grade: (a) FTMO, (c) Tickstory's Dukascopy date table.
8. **The data plan is small.**
   - Daily rules need **hourly bid and ask candles**, not ticks. 17:00 New York is always a whole UTC hour.
   - 30 instruments × 14 years is **about 10,080 files and about 0.1–0.2 GB**: hours on a residential link.
   - Ticks for the 22 new instruments would add **about 33 GB and about 96k files** (extrapolated from 12 GB and 35,008 files for 8), and **R1 does not need them**.
   - Grade: derived; the candle layout is (b/c).
9. **FTMO's gap-trading clause fixes the execution clock.**
   - A 17:00 New York rebalance on a **Friday** opens trades less than 2 h before a closure of 2 h or more, which is forbidden.
   - At 17:00 New York, indices, metals and oil are **inside their 20:50–22:05 UTC break**.
   - EU50, UKOIL, AUS200 and XCU have breaks of 2 h or more on weekdays.
   - **The pre-registered execution calendar must be per symbol.** Grade (a).
10. **The daily slate** (§5.6; LLM-originated) ranks against ARC's:
    - D1 (pooled multi-speed trend) ranks **conditional on the swap regime**: top if swap-free, and below ARC's H3 at FTMO swaps.
    - D3 (turn-of-month index long) is a small, cheap, 4-night sleeve comparable to ARC H5.
    - Carry, FX value and cross-sectional FX momentum are **rejected** for R1.
    - Grade: derived.

---

## 2. Body

### 2.1 The venue's real cost of holding: FTMO's own swap table (task 4, new; extends SCO)

**Source.** `https://ftmo.com/en/symbols/` (modified 2026-09-02) is a script-rendered table. Its data endpoint is `https://ftmo.com/wp-json/ftmo/symbols`, which I fetched on 2026-09-25. Grade **(a)**: the firm's own primary document.
- It carries 166 active symbols: `'Equities CFD': 59, 'Crypto CFD': 30, 'Forex': 28, 'Cash CFD': 25, 'Exotics': 15, 'Metals CFD': 9`.
- It also carries `tradingHours` for the current week, and `platformTimeOffset {'UTC': 3, 'Europe/Prague': 1}`.
- A verbatim record fragment:

  > `"code":"EUR\/USD" … "contractSize":100000 … "swapLong":-9.49,"swapShort":0.36,"swapType":"points" … "commission":5,"commissionType":"flat_USD" … "leverageStandard":100,"leverageSwing":30,"digits":5 … "pipCommissionPerLot":0.3`

**Method** (`evidence/R1B/probe_ftmo_swap_carry.py`).
- Standard broker swap construction: swap_long = d − m and swap_short = −d − m. Here d is the fair carry and m ≥ 0 is the markup per side.
- So d = (L − S)/2 and m = −(L + S)/2. The share of fair carry that the positive side keeps, (|d| − m)/|d|, is **free of any price level**.
- The model is exact for symmetric markups. If the firm marks up asymmetrically, m is the *average* markup, and it is still exactly the average cost of being long versus short.

**Result 1: carry is confiscated.**
- On the 28 G10 pairs, the positive-carry side keeps a median of **21%** of fair carry. It keeps 26% on USD/JPY long, 7% on EUR/USD short and 2% on NZD/USD short.
- On 6 pairs neither side is positive: AUD/USD, GBP/AUD, GBP/USD, EUR/CAD, EUR/NZD and NZD/CAD.
- On index cash CFDs the long pays everything and the short receives about nothing.
- Gold pays on both sides (`XAU/USD swapLong -83, swapShort -8.3`).

**Result 2: the markup as a holding cost** (`evidence/R1B/probe_holding_cost_sr.py`).
- The conversion from points to %/yr uses **assumed** round prices. EUR/USD 1.15, USD/JPY 150, XAU 3,500, US500 6,500 and GER40 23,500 are typed assumptions, not data; the cost scales as 1/price.
- Volatilities are also round assumptions.
- Swaps are charged about 365 nights a year, with a triple Wednesday-to-Thursday night. FTMO's own blog, via search rendering (a): *"the triple swap being charged overnight from Wednesday to Thursday"*.

| Symbol | Markup m (%/yr, per side) | Long (%/yr) | Short (%/yr) | m ÷ vol (SR/yr held) |
|---|---|---|---|---|
| EUR/USD | 1.45 | −3.01 | +0.11 | 0.21 |
| USD/JPY | 1.80 | +0.62 | −4.22 | 0.18 |
| GBP/USD | 1.34 | −1.47 | −1.21 | 0.17 |
| AUD/USD | 2.54 | −1.94 | −3.14 | 0.25 |
| USD/CHF | 2.62 | +0.88 | −6.12 | 0.33 |
| EUR/JPY | 0.89 | +0.35 | −2.13 | 0.09 |
| CAD/JPY | 0.89 | +0.19 | −1.97 | 0.08 |
| EUR/AUD | 1.11 | −2.71 | +0.48 | 0.12 |
| XAU/USD | 4.76 | −8.66 | −0.87 | 0.30 |
| XAG/USD | 6.72 | −13.82 | +0.38 | 0.24 |
| US500 | 4.65 | −9.16 | −0.14 | 0.27 |
| US100 | 4.98 | −10.48 | +0.51 | 0.23 |
| GER40 | 3.56 | −7.04 | −0.07 | 0.19 |
| UK100 | 4.56 | −9.57 | +0.44 | 0.33 |
| JP225 | 4.84 | −6.78 | −2.90 | 0.22 |

All 27 rows are in `probe_holding_cost_sr.out`.

**Why this is decisive for R-1.**
- Carver's speed limit, verified by C4 (b): *"DO NOT SPEND MORE THAN ONE THIRD OF YOUR EXPECTED PRE-COST RETURNS ON COSTS"*.
- It is conventionally applied to **turnover × spread**. For a slow rule at a CFD prop firm, the binding cost is **time-in-market × markup**, and that cost is **independent of speed**.
  - The synthetic receipt `sim_rule_turnover_null.py` shows a capped EWMAC forecast is non-zero essentially all the time.
  - A forecast threshold of 5 keeps 92% of the average exposure; a threshold of 10 keeps about 71%.
- So "trade expensive instruments slower", Carver's cost remedy (*"more expensive instruments will end up trading slower"*, search rendering of his "Optimising weights with costs" (b)), **does not help here**. Only three things help:
  - **(i)** a swap-free account;
  - **(ii)** instruments with low m/σ;
  - **(iii)** rules that are flat most of the time, meaning calendar and flow sleeves that hold for days, not months.
- This refines GAP-P12D-45. There, "turnover is the decision" held at minute horizons. At daily horizons, turnover cost is noise (about 0.01–0.02 SR/yr) and **holding markup is the decision**.
- **BASE under-charges the venue.** `tests/backtest/financing.py:7-11` charges "an annual admin fee (1.00% for the majors) that is charged to BOTH sides", which is OANDA's method. For gold it charges an "ASSUMED gold lease rate (default 0.25%/yr)" (`financing.py:19`).
  - Against FTMO, the FX fee is 0.3–1.6 points too low per side.
  - For gold and indices it is off by 3–4 points per side.

**Energies are uninterpretable.**
- USOIL shows `swapLong 49.65, swapShort -225.45, digits 3, contractSize 100`. Under the point convention that implies percentages far outside any plausible range.
- Cash oil CFD swaps probably embed the futures term structure.
- **Treat energy holding cost as unknown until FTMO answers** (§2.8 question 3).

**Commission semantics are ambiguous.**
- FX has `"commission":5,"commissionType":"flat_USD"`, but `pipCommissionPerLot` works out to about $3 per lot on every quote currency (0.30 pip × $10 on USD-quoted pairs; 0.48 pip × about $6.7 on JPY-quoted).
- So it is not settled whether $5 is per side or per round turn. At daily horizons it does not matter (about 0.01 SR/yr).
- Metals carry `0.0014 percent`; index CFDs carry 0 commission.

### 2.2 Rule families: evidence, decay, critique, cost, correlation, and the minimal rule (task 1)

**Framing numbers**, graded and quoted:
- **Cross-instrument out-of-sample trend: the strongest available evidence for pooled rules.**
  - Babu, Levine, Ooi, Pedersen & Stamelos (2020), *JOIM* 18(1), AQR PDF, fetched 2026-09-25. Grade **(a)**, with an interest noted: the authors run trend funds.
  - The paper covers *"82 securities not previously examined"*, and reports: *"the gross Sharpe ratio of 12-month time series momentum for traditional assets is 1.17, and the strategy delivers an even higher Sharpe ratio of 1.34 for the alternative assets"*.
  - Its Table 2 gives *"Median Across Individual Assets 0.34 0.34 0.39 0.35"* for the Sharpe ratio. **A single instrument earns about a third of a Sharpe gross; the portfolio earns the rest from breadth.**
- **Post-publication decay.**
  - McLean & Pontiff (2016), *JF* 71(1), grade (a), via search rendering of the abstract: *"portfolio returns are 26% lower out-of-sample and 58% lower post-publication"*.
  - That covers 97 stock anomalies. Applying it to trend is an **analogy**, which I use only to set the pessimistic planning value s = 0.15.
- **The 2010s drought and the recovery.**
  - Hurst–Ooi–Pedersen: 0.76 net over 1880–2016, 0.41 in 2010–16 (ARC, text-verified (a)).
  - The SG CTA Index finished 2024 at *"close to flat performance of +2.4%"*, and the SG Trend constituents' *"pairwise correlation … in 2024 was 0.78"* (search rendering of the SG/CFM pages (b)).
  - The SG Trend Index is at **YTD +15.16% as of Sep-25-2026** (BarclayHedge page, fetched (b)).
  - The shape is lumpy: multi-year flats, then large years.

| Family | Gross SR in the literature | Decay and critique | Cost at FTMO (SR/yr) | Correlation to trend | Minimal faithful rule (≤ 3 free parameters, literature-fixed) | Verdict |
|---|---|---|---|---|---|---|
| **TREND (EWMAC, 3 speeds)** | Single asset about 0.34 gross; diversified 1.17 gross (Babu (a)). HOP net 0.76, 2010–16 0.41 (a) | **Critique:** Huang et al. 2020, *"little evidence"* asset by asset (a, prior report). Kim et al. (2016) say vol scaling explains it; Babu rebuts: *"volatility scaling and static exposures do not fully explain the strong performance"* (a). **Speed:** *"Turning points are the Achilles' heel of time-series momentum portfolios. Slow signals fail to react quickly … while fast signals are often false alarms"* (Goulding, Harvey & Mazzoleni 2023, *JFE* (a)), which argues for a blend of speeds | Holding 0.08–0.46 (median 0.21) + trading 0.01–0.02 | — | EWMAC(16,64), (32,128), (64,256) on 17:00 New York closes. σ is the 25-day EWMA of daily price changes. The scale is fixed on the synthetic null (4.66 / 3.26 / 2.28, `sim_rule_turnover_null.out`). Cap ±20, equal weights, FDM 1.09. **Free parameters: 0 fitted.** The speed set is the only choice | **ADOPT**, *conditional* on the swap regime (§2.1). Carry-inclusive signal per GAP-P12D-71 |
| **BREAKOUT** | Carver runs it (b) | — | as TREND | **0.95** with EWMAC at the matched speed (synthetic null). BREAKOUT40 ≈ EWMAC(8,32), 80 ≈ (16,64), 160 ≈ (32,128) | — | **REJECT as a family.** Allow at most one registered *variant* of TREND |
| **TSMOM (MOP 12m sign)** | MOP ≈ 1.1 diversified (a, prior) | As trend | as TREND, turnover 1.5 RT/yr | 0.77 with EWMAC(64,256) (synthetic null) | sign of the 12-month carry-inclusive return, monthly | **ADAPT:** a registered *variant* of TREND's slowest speed, to satisfy ACIS-04 §6.6's "canonical" requirement. **Not additive** |
| **CARRY (FX; cross-asset)** | FX 0.68 (1983–2012, skew −0.68); cross-asset 1.2; timing strategies average 0.6 (Koijen et al. 2018, *JFE* (a)). Post-GFC FX about 0.25 (a, prior report) | Crash risk: skew −0.68 | **Confiscated:** the median positive side keeps 21% of fair carry. Bonds, equity carry and options legs are not offered at FTMO | Low with trend (Koijen) | forecast = the venue's net annual swap for the side ÷ σ | **REJECT as a return source at FTMO.** **ADOPT as a cost term** (the per-symbol markup in C8) |
| **FX VALUE (PPP/REER)** | Menkhoff et al. 2017, *RFS* (a): real exchange rates predict the cross-section, better *"adjusting … for key country-specific fundamentals (productivity, the quality of export goods, net foreign assets, and output gaps)"* (search rendering) | Needs macro data; about 7 G10 bets | low turnover, but full-time holding at the markup | negative with trend (standard) | 5-year real-exchange-rate reversal | **REJECT for R1:** a data dependency, low breadth, and it pays the markup full-time |
| **XS FX MOMENTUM** | 0.95 gross, but *"fairly sensitive to transaction costs"* and 48 currencies (Menkhoff et al. 2012 (a), prior report) | Needs a cross-section G10 lacks | full-time holding | high with TREND on the same pairs | — | **REJECT** |
| **TURN-OF-MONTH (index)** | *"investors received no reward for bearing market risk except at turns of the month"*, *"in 31 of the 35 countries"* (McConnell & Xu 2008, *FAJ* (a), search rendering). Mechanism: *"temporary increases in the costs of debt and equity capital that coincide with key dates associated with month-end cash needs"* (Etula et al. 2020, *RFS* (a), fetched abstract). But McConnell & Xu found it *"not caused by month-end buying pressure as measured by trading volume or net flows"*, so the mechanism is contested | Widely known since the 1980s, so decay is likely. Replication only on post-2008 data | about 5 nights × index long swap ≈ 0.12% per event | low (a calendar sleeve) | long from 14:30 New York on the last trading day (T−1) to the cash close of T+3. 0 free parameters | **ADAPT** (D3). It holds only about 5 nights a month, so it sidesteps the markup |
| **INDEX 1-day REVERSAL** | ARC H3 (a) | — | 1 night | negative with IM | ARC's card | Already on ARC's slate; do not duplicate |
| **SKEW, commodity term structure** | Needs a futures cross-section | — | — | — | — | **REJECT for R1:** no futures cross-section on the venue |

**The FX-heavy tension.**
- The classes where trend has the most published strength (bonds, commodities, indices) are, at FTMO, either **absent** (bonds) or the **most expensive to hold** (indices and metals at m/σ 0.19–0.33).
- The cheapest instruments to hold are the JPY crosses (0.08–0.14). FX is where simple rules decayed first: Neely, Weller & Ulrich (a) and the FX-only walk-forward at 0.43 (c), both via the prior report.
- **Expect ACIS's pooled trend to under-perform the published CTA numbers by more than the usual haircut.**

### 2.3 Pooled parameterisation and forecast combination (task 2)

- **Pooling is Carver's default for a scale-free rule** (b), from his 2016 post, fetched: *"One implication of this is that the forecast scalar should also be identical for all instruments. And one implication of that is that we can pool data across multiple markets to measure the right scalar."*
  - **Extension proposed here** (LLM-originated): fix the scalar on the **synthetic null**. For a scale-free rule on a random walk it is a property of the rule, so this spends **zero** real-data looks.
  - Measured on 400 synthetic years: EWMAC 16/64 → 4.66, 32/128 → 3.26, 64/256 → 2.28, with ÷√2 per speed doubling, consistent with Carver's *"dividing by sqrt(2)"* rule (search rendering (b)).
  - On trending real data the scalar would be somewhat smaller. That changes only how often the ±20 cap binds, not the sign, and the null value is the honest pre-registered one.
- **Combination.**
  - Equal weights within TREND. FDM = 1/√(w′ρw) = **1.09**, using the null position correlations 0.87 (adjacent speeds) and 0.58 (16/64 against 64/256).
  - Equal risk across families (handcrafting).
  - Instruments: **class-equal, then equal within the class** (FX, metals, indices, energy). This stops 13 FX pairs dominating.
  - IDM from a *pre-registered, assumed* correlation block (within-class 0.25, across 0.05): **2.51**, about 2.4–2.7 across 0.15–0.35. Cap it at 2.5, Carver's documented ceiling, which I did not re-verify in this pass.
- **The evidence that fixed beats fitted:**
  - DeMiguel, Garlappi & Uppal (2009), *RFS* (a), search rendering: *"Of the 14 models we evaluate across seven empirical datasets, none is consistently better than the 1/N rule in terms of Sharpe ratio, certainty-equivalent return, or turnover"*.
  - Carver (2017), fetched (b): adding rules gave *"slightly worse performance; although not with a statistically significant difference"*.
  - Wiecki et al. 2016, R² < 0.025 (via ARC).
- **Per-instrument deviation is justified only by cost, and here it is mechanical.**
  - Exclude instrument *i* from a full-time family when c_i > ⅓·s_plan. c_i is holding m_i/σ_i plus trading; s_plan is the pre-registered planning SR (0.34 historical, 0.15–0.25 honest).
  - This is Carver's `ceiling_cost_SR: 0.13` (C4, (b)) generalised to holding cost.
  - **At FTMO swaps it admits only EUR/JPY, CAD/JPY, CHF/JPY, EUR/AUD (and AUD/JPY and GBP/JPY at the margin) at s_plan = 0.34, and nothing at s_plan = 0.25.**
  - That is the finding in §1 bullet 3, stated as a rule.

### 2.4 What the durable minority does (task 3): primary and verifiable only

| Finding | Source and grade | Map to ACIS |
|---|---|---|
| A diversified trend portfolio earns its Sharpe from breadth; the single asset is about 0.34 | Babu et al. 2020 (a) | **ADOPT:** 20–40 instruments, pooled. Never grade one instrument alone |
| Trend works on **held-out instruments**: 82 new ones | Babu et al. 2020 (a) | **ADOPT** the held-out-instrument test design (§2.5). It is the literature's own form of out-of-sample |
| Carver runs a pooled, multi-rule futures system. Year to 2025-04: *"Net: -16.3%"*, vol 16.8%, Sharpe 0.76 since inception, CAGR 12.0%. Costs: slippage 0.56% + commissions 0.29% of capital. Correlation 0.66 to SG CTA and 0.56 to AHL | Carver, "Annual performance update returneth — year 11", fetched (b) | **ADOPT** the architecture: pooled forecasts, vol targeting, a cost ceiling. **Expect a −16% year** in the backtest distribution. Prop sizing (ECO) must survive one |
| Top-10 CTAs are 0.78 pairwise-correlated (2024), with returns spread over about 15% | CFM/SG, search rendering (b) | The CTA edge is one common trend beta, and execution and universe decide the dispersion. **ADAPT:** ACIS's universe (no bonds, a CFD markup) will sit at the weak end |
| Trend is lumpy: SG CTA +2.4% in 2024, Carver −16.3% to 2025-04, SG Trend +15.16% YTD 2026 | (b) as above | Forward incubation of 3–6 months **cannot** confirm a trend edge (ARC §5.5). The demo proves plumbing and cost only |
| CTAs trade **futures** (no swap markup; roll yield is the carry) and include **bonds** | Koijen et al. 2018 (a); SG index constituents (b) | **REJECT** the premise that CTA Sharpe transfers to FTMO CFDs. Holding cost and the missing bond class cut it. Owner option: a futures venue is set aside by SCO (FTMO Futures is intraday-only) |
| No verifiable primary evidence exists on what profitable prop *algo* traders do | ARC §1, ECO | Unchanged: build on CTA and Carver evidence, adapted for cost |

### 2.5 The instrument universe and held-out set (task 4)

**History on Dukascopy.** Source: Tickstory's table of Dukascopy's earliest dates, `dateModified 2025-10-15`, fetched 2026-09-25. Grade **(c)**, a vendor page; it agrees with a (b) dukascopy-node snippet giving USA500.IDX from 2011-09-18.
- **Verbatim rows:**
  - `EURUSD | Euro/US Dollar | 2003.05.04 21:00` (all 16 FX candidates: 2003–2006);
  - `XAUUSD | Gold (USD) | 2003.05.04`, `XAGUSD | Silver (USD) | 2003.05.05 16:00`;
  - `USA500.IDX/USD | S&P 500 | 2011.09.19` (likewise USA30, USATECH, GBR, JPN, EUS, FRA, HKG);
  - `DEU.IDX/EUR | DAX 30 (Germany) | 2012.01.19`;
  - `AUD.IDX/AUD | All Ords / ASX 200 (Australia) | 2013.01.03`;
  - `BRENT.CMD/USD | Brent Crude Oil | 2011.09.20`;
  - `LIGHT.CMD/USD | Light Crude Oil | 2013.01.01`;
  - `GAS.CMD/USD | Natural Gas | 2012.09.02`;
  - `COPPER.CMD/USD | High Grade Copper | 2012.03.01`.
- **Rows that exclude an instrument:**
  - `XPT.CMD/USD | Platinum | 2021.11.01`;
  - `USSC2000.IDX/USD | Russell 2000 Index | 2018.08.08`;
  - `BUND.TR/EUR | Euro Bond | 2016.02.05`. FTMO offers no bonds anyway.
  - The softs start in 2017.
- **The owner verifies** with `scripts/download_dukascopy_s3.py check`, which prints the bucket's symbols (`download_dukascopy_s3.py:18`).

**The proposed 30.** All 30 are on FTMO: `leverageSwing` 30 for FX and 15 for metals and indices. Dukascopy history runs from 2013 or earlier. They are split by `evidence/R1B/probe_holdout_draw.py`:

| Class | Explored (23) | Held-out, locked (7) | FTMO daily break (UTC, current week) |
|---|---|---|---|
| FX (16) | EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF, EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/CHF, EUR/AUD, CHF/JPY | **AUD/NZD, NZD/USD, CAD/JPY** | 20:55–21:05 (0.17 h) |
| Metals (3) | XAU/USD, XAG/USD | **XCU/USD** | 20:50–22:05; XCU 20:00–22:05 (2.08 h) |
| Indices (8) | US500, US30, UK100, JP225, EU50, AUS200 | **GER40, US100** | 20:50–22:05; EU50 20:00–06:05 (10.1 h); AUS200 3 h |
| Energy (3) | UKOIL, NATGAS | **USOIL** | 20:50–22:05; UKOIL 20:50–00:05 (3.25 h) |

- **The draw rule is mechanical and pinned.** Sort each class by `sha256("ACIS-R1-holdout-2026-09-25|" + symbol)`, then hold out the first k (FX 3, metal 1, index 2, energy 1).
  - **All 8 instruments already on disk are forced into the explored set.** They have been read by runs, by the GAP-P12D-14 source checks and by an auditor (GAP-P12D-71 measured TSMOM votes on the declared FX pairs), so none of them is clean.
  - The salt is pre-registered by this commit. Re-salting after any real-data look is forbidden.
- **Honest limits of the held-out set:**
  1. **The common factor leaks** (VAL §2.6: 10.3–22.7% FPR). Grade held-out results on returns residualised against the explored set's class factor (R1-A owns the statistic).
  2. **It is clean with respect to the project's looks, not the LLM's knowledge.** I know gold and the US indices rallied in 2024–25. Only forward data is fully clean (GAP-P12D-66).
  3. **Power is low.** 7 instruments at N_eff of about 3 can detect a gross pooled SR of about 0.6 over 12 years, but not 0.3. The final gate is forward.
- **Effective breadth** (`evidence/R1B/probe_effective_breadth.py`, published inputs):
  - The formula reproduces Babu's diversified 1.17 from s = 0.34, N = 58, ρ = 0.07: **1.16**.
  - For the 23 explored, with cross-class ρ = 0.05, N_eff = **10.2 / 7.9 / 6.1 / 5.0 / 4.0** at within-class ρ = 0.07 / 0.15 / 0.25 / 0.35 / 0.50.
  - The 8 declared at BASE give 5.5 / 3.3 / 2.2.
  - FX16 alone gives 2.6, against 5.5 for the 30 mixed (ρ_w 0.35).
  - The within-FX correlation of *trend-strategy returns* is **not** published in what I read. Verdelhan's 20–90% factor share argues for 0.25–0.5.

### 2.6 Data plan (task 5)

- **Signals.** Daily 17:00 New York closes come from **hourly** bid and ask bars. 17:00 New York is 21:00 UTC in EDT and 22:00 UTC in EST, always a whole hour, so no minute data is needed for the signal.
- **The file layout** (grade (b/c): third-party documentation via search rendering, hexdocs `Dukascopy.DataFeed` and dukascopy-node):
  - `https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM}/{DD}/BID_candles_min_1.bi5`: 1-minute candles, one file per day;
  - `…/{YYYY}/{MM}/{BID|ASK}_candles_hour_1.bi5`: hourly candles, one file per month;
  - the month is zero-based and the files are LZMA.
  - **The S3 bucket ACIS uses holds ticks.** The downloader syncs only `*_ticks.bi5` (`scripts/download_dukascopy_s3.py:88-89`). Candles come from the public feed, which is *"per-IP rate-limited and bans datacenter IPs"* (`ACIS_SPEC.md:355`). **The owner runs it from the laptop.**

| Dataset | Files | Size (estimate) | Time (estimate, residential, about 1 request/s sustained) | Needed for |
|---|---|---|---|---|
| **Hourly bid+ask, 30 instruments, 2012–2025** | 30 × 14 × 12 × 2 = **10,080** | 744 rows × 24 B ≈ 18 KB raw per file; LZMA → **about 0.06–0.2 GB** | **about 3 h** | **R1 signals and costs (required)** |
| 1-minute bid+ask, 30 instruments | about 30 × 14 × 300 × 2 ≈ **252k** | about 10–15 KB per file → **about 2.5–4 GB** | **about 3 days** | Optional: execution realism inside the hour |
| Ticks, 22 new instruments (S3, requester-pays) | about 22 × 4,376 ≈ **96k** | 12 GB ÷ 8 × 22 ≈ **33 GB** | "days" for 8 (GAP-P12D-50) → **about 1–2 weeks** | **Not for R1.** RSIM↔tick reconciliation (VAL R1–R6) uses the existing 8 |

- **Basis:**
  - 12 GB and 35,008 files for 8 instruments over 2012–2025, and "took days" (`KNOWN_GAPS.md:856`);
  - about 2.99 B ticks at 4.3 B/tick compressed (GAP-P12D-12);
  - the 24-byte candle record (time plus four prices plus volume, 4 bytes each) is my assumption.
- **The owner should measure one hourly file and one minute file first**, then rescale this table.
- **Also required, as non-price inputs:**
  - **Swaps.** Dated overnight rates for NZD (new) and, for index CFDs, index dividend treatment. Whether Dukascopy's cash-index CFD prices are dividend-adjusted is **unverified**.
  - **The firm markup m_i per symbol**, from the FTMO table (§2.1), held constant historically and stressed ±50%. FTMO publishes today's table only.
  - A **weekly snapshot** of `wp-json/ftmo/symbols` into the operations ledger, to measure markup drift.

### 2.7 Execution clock under the prop rules (new)

- **FTMO's gap-trading clause** (SCO (a)) forbids opening trades *"two hours or less before a relevant financial market is closed for at least two hours"*.
- **From the JSON's `tradingHours`:**
  - FX closes about 21:00 UTC Friday for the weekend. **So a Friday 17:00 New York rebalance is forbidden.**
  - Indices, metals and oil are **closed** from 20:50 to 22:05 UTC, which includes 17:00 New York in EDT.
- **The pre-registered execution rules:**
  - **(1)** Signal on the 17:00 New York bar close. That is the last pre-break hourly close for symbols in their break.
  - **(2)** Execute FX at 17:05 New York, and indices, metals and energy at 18:10 New York, after the reopen.
  - **(3)** On Fridays, and before holiday closures, do not rebalance after 14:30 New York. The Thursday target carries through, which Swing allows.
  - **(4)** Execute EU50 and AUS200 at their next session open. XCU and UKOIL obey their 2 h breaks.
- These rules are cheap to encode, and they belong in the RSIM calendar and in the live runtime alike (GAP-P12D-58).

### 2.8 Owner questions to draft into SCO's emails (no contact made)

1. **FTMO and E8:** "Is a swap-free account available to an algorithmic trader who does not request it on religious grounds? Is there any administration fee or maximum holding period on it? Does it cover indices, metals and energy?"
   - E8's page, per search rendering (c): *"Choosing the swap-free option (not for futures) adds 10% to the final account price."*
   - E8's page also says *"There is no overnight financing on positions held through rollover"*, but it is unclear which product that covers.
   - FTMO's Islamic option is reported only by an aggregator (c).
   - **The owner must not misrepresent eligibility.** That would be a T&C breach and a counterparty risk.
2. **FTMO:** is `commission: 5 flat_USD` charged per side or per round turn? And is the 0.7% adjustment (T&C 5.3.4) applied to index CFDs denominated in EUR, GBP or JPY?
3. **FTMO:** how are the USOIL and UKOIL cash CFD swaps computed? Is it the futures basis, or the rate plus a fee?

---

## 2.9 For PLAN_R1

Each item gives its value, its complexity, its grade, its falsifier and a verdict. Line counts are LLM estimates.

1. **R1B-1. The venue's holding cost goes into C8.** Per-symbol swap = dated rate differential (existing `financing.py`) ± the firm markup m_i from the firm's table, replacing the flat 1% fee and the 0.25% gold lease. Stress m_i at 1.5× on the cost ladder.
   - **Value:** removes a 0.3–4 point per side under-charge (larger for gold and indices). Without it, every daily-rule backtest overstates net SR by about 0.1–0.3.
   - **Complexity:** +about 30 lines, one table of about 30 rows, 0 concepts.
   - **Grade:** (a).
   - **Falsifier:** the demo's realised swap per night differs from the modelled one by more than 20% on more than 3 of the first 20 symbols → recalibrate.
   - **ADOPT.**
2. **R1B-2. The speed limit counts holding cost:** c_i = turnover × RT cost ÷ σ + time-in-market × m_i ÷ σ, and inclusion needs c_i ≤ ⅓·s_plan, with s_plan pre-registered at 0.25.
   - **Value:** a look-free, mechanical universe filter that prevents paying 60–100% of edge in swap.
   - **Complexity:** +about 15 lines in the registry.
   - **Grade:** (b) Carver, extended.
   - **Falsifier:** if RSIM on the **synthetic** lab shows a planted s = 0.25 trend is still detected at FWER 5% with c = 0.21, drop the filter.
   - **[spec]. ADOPT.**
3. **R1B-3. Owner decision first: the swap regime of the account.** Ask E8 and FTMO the §2.8 questions *before* committing the daily family.
   - **Value:** it moves the expected net pooled trend SR from about −0.15..+0.32 to about +0.32..+0.79. It is the largest lever found.
   - **Complexity:** 0 lines.
   - **Grade:** (a) inputs, (c) for swap-free availability.
   - **Falsifier:** the swap-free terms carry an admin fee or holding cap with m ≥ 1%/yr, in which case the lever is gone.
   - **[owner decision].**
4. **R1B-4. TREND family** = EWMAC(16,64) + (32,128) + (64,256), equal weights, null-fixed scalars 4.66 / 3.26 / 2.28, cap ±20, FDM 1.09. σ is a 25-day EWMA. Signals on 17:00 New York hourly closes, carry-inclusive (GAP-P12D-71). Registered variants, each counted as a trial:
   - (v1) TSMOM 12m replacing (64,256), which is the ACIS-04 §6.6 canonical;
   - (v2) BREAKOUT(80) replacing (16,64);
   - (v3) Friday-flat.
   - **Value:** the most evidenced cross-market family, with 0 fitted parameters.
   - **Complexity:** about 80 lines of rules; −1 family (breakout), −1 module (per-tick TSMOM).
   - **Grade:** (a) evidence, synthetic receipts.
   - **Falsifiers:**
     - G2 (E = 2012–19): pooled net SR ≤ 0 at 1× cost, or measured gross/cost < 2 → kill;
     - G3 (V = 2020–23): net SR < 0 at 1× cost, or < −0.1 at 2× → kill;
     - G4: the held-out 7, residualised, net SR ≤ 0 → kill;
     - G5: 60 trades or 3 months with the per-trade mean below V's 10th percentile, or a swap-cost breach → kill.
   - **ADOPT, conditional on R1B-3.**
5. **R1B-5. Rejected families for R1:** carry as a return source, FX value, cross-sectional FX momentum, commodity skew and term structure, and breakout as a family.
   - **Value:** keeps the family count, and so the trial budget, at 2–4.
   - **Complexity:** −4 candidate families.
   - **Grade:** (a) + receipts.
   - **Falsifier:** a swap-passing venue appears (carry), or the universe gains 20 or more currencies (cross-sectional momentum).
   - **REJECT.**
6. **R1B-6. Combination:** handcrafted equal risk. Class-equal then equal-within instrument weights; IDM from a pre-registered assumed block (within 0.25, across 0.05) = 2.5, capped at 2.5; equal risk across families; a 10% no-trade buffer. **No fitted weights anywhere.**
   - **Value:** 1/N is not beaten out of sample (DeMiguel (a)), and it removes weight-fitting looks.
   - **Complexity:** about 40 lines.
   - **Grade:** (a)/(b).
   - **Falsifier:** none needed at G2. Revisit only if a *forward* record shows a class contributing negative risk-adjusted P&L for 24 months.
   - **ADOPT.**
7. **R1B-7. Universe: 30 instruments, 23 explored and 7 held out,** as in §2.5. The salted-hash draw is pinned. The 8 on-disk instruments are forced into the explored set. XPT, US2000, softs and exotics are excluded.
   - **Value:** N_eff about 6 against about 3 at BASE's 8, which is √2 on SR; plus a cross-instrument OOS test.
   - **Complexity:** config only, about 30 instrument entries plus exchange-anchored calendars (GAP-P12D-68 item 5).
   - **Grade:** (a) FTMO, (c) history dates.
   - **Falsifier:** a symbol's hourly history, once downloaded, has more than 5% missing weekdays in 2013–2025 → drop it before any look, and record why.
   - **[spec]. ADOPT.**
8. **R1B-8. Data:** hourly bid+ask candles from the public feed, owner-run on the residential IP. About 10k files, about 0.1–0.2 GB, about 3 h. Measure one file first. No new ticks for R1.
   - **Value:** unblocks R1 at about 1/200th of the tick cost.
   - **Complexity:** +about 60 lines (an hourly-candle reader reusing `bi5.py`'s LZMA path) + 1 script.
   - **Grade:** (b/c) layout, derived sizes.
   - **Falsifier:** a measured file is more than 3× the estimate → re-plan.
   - **ADOPT.**
9. **R1B-9. Execution calendar per symbol** (§2.7): no Friday rebalance after 14:30 New York; indices, metals and energy execute after the 22:05 UTC reopen; EU50 and AUS200 at the next open.
   - **Value:** makes the backtest's trades legal at FTMO (GAP-P12D-58).
   - **Complexity:** about 30 lines in the shared calendar.
   - **Grade:** (a).
   - **Falsifier:** FTMO confirms in writing that a Friday 17:00 New York entry is not "gap trading" → relax.
   - **ADOPT.**
10. **R1B-10. Daily-horizon slate** (§2.10), ranked alongside ARC's.

### 2.10 Daily-horizon slate (LLM-originated; extends ARC §4; standards per ARC §5.4)

The gates are ARC's: E = 2012–19, V = 2020–23, H = 2024–25 once, F = forward demo.

| Rank vs ARC | ID | Hypothesis | Mechanism | Fixed parameters | Instruments | Expected gross/cost | Numeric falsifiers per gate |
|---|---|---|---|---|---|---|---|
| **Swap-free: between H1 and H5. At FTMO swaps: below H3** | **D1** | Pooled multi-speed trend (R1B-4) | Slow diffusion of information, hedging-pressure and risk-transfer premia. Babu 2020 (a) and Goulding et al. 2023 (a) | 3 EWMAC speeds, null scalars, cap 20, FDM 1.09, IDM 2.5 | the 23 explored (held-out 7 at G4) | swap-free ≈ 10–20; at FTMO ≈ 0.7–1.6 on majors/indices/metals and ≈ 2.5–4 on JPY crosses (s 0.25–0.34 ÷ c) | **G0:** gross/cost ≥ 3 on at least 8 instruments at the chosen venue's swaps, else park. **G2:** pooled net SR ≤ 0 → kill. **G3:** net SR at 1× < 0 or at 2× < −0.1 → kill; no single year more than 50% of P&L. **G4:** held-out residualised net SR ≤ 0 → kill. **G5:** the realised swap/night model error is above 20%, or the per-trade mean is below V's p10 after 60 trades → kill |
| comparable to H5 | **D3** | Turn-of-month index long | Month-end cash needs and inflows (Etula et al. 2020 (a)), with the mechanism contested (McConnell & Xu (a)) | long 14:30 New York on T−1 → the cash close of T+3; 0 free parameters | US500, US30, UK100, JP225, EU50, AUS200 (GER40 and US100 held out) | about 0.5% gross per event in the literature (the equity premium concentrated in about 48 days a year; my arithmetic) ÷ about 0.13% cost (5 nights × about 0.025% + spread) ≈ **3.7**; ≈ **1.6** after a 58% decay | **G2:** TOM-window mean ≤ non-TOM mean on E → kill. **G3:** t < 2 on V, net of swap (replication standard, post-2008) → kill. **G4:** held-out GER40/US100 TOM mean ≤ 0 → kill |
| below D1, same family | **D1-v3** | D1 Friday-flat (for Standard accounts) | as D1 | as D1, flat by 14:30 New York Friday | as D1 | lower: weekend exposure is dropped, costing 2 spreads a week | Registered variant of D1. **G2:** keep only if its net SR on E is ≥ D1's − 0.1 |
| — | **D2** (withdrawn from the checkpoint-2 draft) | D1 with a forecast threshold | — | — | — | Receipt: a threshold of 5 keeps 92% of exposure and a threshold of 10 keeps 71%, so it barely cuts holding cost | **REJECT:** a weak lever that adds a parameter |

**Portfolio arithmetic (derived).** At FTMO swaps, the evidence ranks ARC's short-hold items above D1: H1 intraday momentum, H5 month-end fix, H3 index reversal and H6 Tokyo fix. They hold 0–1 nights and pay little swap.
- D1 is the **breadth engine** only if the account is swap-free. Otherwise D1 is a small-weight, JPY-cross-and-low-markup sleeve, and ARC's scheduled windows plus D3 carry the book.
- **This is a disappointing but honest re-ranking** relative to the ratified "few pooled rules on 20–40 instruments" direction. The direction survives, and the venue's swap regime decides its weight.

---

## 3. What I could not verify

- **E8's primary pages** return HTTP 403 or a Cloudflare challenge to this container. Its swap-free option, its "no overnight financing" line, its symbols, spreads and swaps are **search renderings (c)**. SCO's (a)-graded E8 quotes were fetched from the laptop.
- **FTMO's commission semantics:** per side or per round turn.
- **FTMO's energy swap convention.**
- **FTMO's Islamic/swap-free availability and terms:** aggregator only (c).
- **Whether today's swap table represents 2012–2025.** The markup is modelled as constant plus a stress.
- **Carver's published forecast scalars and turnover tables, and his IDM cap of 2.5.** My null values are measured on synthetic data; the book values I recall (about 3.75 / 2.65 / 1.87) are **unverified here**.
- **Within-FX correlation of trend-strategy returns:** not found in a primary source. It is swept as an assumption.
- **The Dukascopy candle file layout and sizes:** third-party documentation. Sizes are estimates, and the owner must measure one file of each kind.
- **Whether Dukascopy's cash-index CFD prices are dividend-adjusted.**
- **Post-2008 TOM magnitude and post-publication decay of each family:** not measured, because doing so needs data.
- **The McLean–Pontiff, Verdelhan, McConnell–Xu, DeMiguel and Goulding et al. quotes** are from search-engine renderings of the abstracts, not from fetched PDFs. Babu et al. and Koijen et al. were read from the PDFs.

## 4. Residual risk

1. **The SR conversions in §2.1 use my assumed price and volatility levels.** A 10% level error moves each cost by about 10%. The ranking of symbols is robust, and the carry-kept percentages are price-free.
2. **The swap table is a 2026-09 snapshot.** In a different rate regime (for example 2012–2015 near zero), fair carry shrinks while the markup may not. The markup may be *larger* relative to carry, which strengthens finding 2.
3. **The per-instrument planning SR (0.15–0.34) is analogy-based.** If the 2020s trend regime persists (SG Trend +15% YTD), D1 at FTMO swaps could still net about +0.3. The G2/G3 falsifiers decide, not this report.
4. **The held-out set is clean with respect to project looks only.** An LLM, this lane included, knows 2012–2025 market history, so family selection here is contaminated by construction. Only forward data certifies (GAP-P12D-66).
5. **Excluding bonds is a structural handicap** against the CTA benchmarks. No mitigation exists at FTMO.

## 5. Proposed ledger items (no IDs)

1. **The C8 financing model charges a flat 1% per side (and a 0.25% gold lease). FTMO's own table implies 1.3–2.6% per side on FX majors, about 4.8% on gold and 3.6–5.0% on index CFDs.** The backtest under-charges every multi-day hold.
   - S high / L high. Proposed status: open. **[impl]**, with the calibration table from the firm's JSON.
2. **The speed limit and G0 gross/cost gate ignore holding cost.** At a CFD prop firm, time-in-market × markup is about 10× the trading cost of a daily rule.
   - S high / L high. Open. **[spec — owner ratification]**.
3. **The daily family's viability depends on the account's swap regime,** and nothing in the plan asks for it. Draft questions are in §2.8.
   - S critical / L high. Open. **[spec — owner ratification]**: an owner decision before D1 is built.
4. **Breakout, TSMOM and EWMAC are one family** (position correlation 0.95 / 0.77 at matched speeds on the null). They must be counted as variants of TREND in the look register, not as independent families.
   - S medium / L high. Open. **[spec — owner ratification]**.
5. **A 17:00 New York daily rebalance violates FTMO's gap-trading clause on Fridays,** and falls inside the index, metals and oil break.
   - S high / L high. Open. **[impl]**, extending GAP-P12D-58's scope to the daily clock.
6. **Universe expansion needs hourly candles only:** about 10k files and 0.1–0.2 GB. XPT and US2000 lack Dukascopy history before 2021 and 2018.
   - S medium / L high. Open. **[impl]**; the owner runs the download.
7. **The held-out instrument set is pinned by a salted-hash draw,** with the 8 on-disk instruments forced into the explored set.
   - S medium / L medium. Proposed. **[spec — owner ratification]**.
8. **FTMO's energy swap semantics and commission side are unknown.**
   - S medium / L medium. Open. **[impl]**: an owner question.

## 6. Sources (accessed 2026-09-25 unless stated)

| # | Source | URL | Grade |
|---|---|---|---|
| 1 | FTMO symbol specification JSON, the data source of the Symbols page (page modified 2026-09-02) | https://ftmo.com/wp-json/ftmo/symbols ; https://ftmo.com/en/symbols/ | (a) |
| 2 | FTMO FAQ, account specifications (modified 2026-08-24): *"The Swing account type has leverage set to up to 1:30."* | https://ftmo.com/en/faq/what-are-the-account-specifications/ | (a) |
| 3 | FTMO blog on swaps, triple Wednesday (search rendering) | https://ftmo.com/en/blog/what-is-a-swap-and-for-whom-is-it-important/ | (a) via rendering |
| 4 | Babu, Levine, Ooi, Pedersen & Stamelos (2020), "Trends Everywhere", *JOIM* 18(1), PDF | https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf | (a), interest noted |
| 5 | Koijen, Moskowitz, Pedersen & Vrugt (2018), "Carry", *JFE* 127, PDF | https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2019/04/Carry.pdf | (a) |
| 6 | McLean & Pontiff (2016), *JF* 71(1) (abstract, search rendering) | https://ideas.repec.org/a/bla/jfinan/v71y2016i1p5-32.html | (a) via rendering |
| 7 | Verdelhan (2018), *JF* 73(1) (abstract, search rendering) | https://ideas.repec.org/a/bla/jfinan/v73y2018i1p375-418.html | (a) via rendering |
| 8 | Menkhoff, Sarno, Schmeling & Schrimpf (2017), "Currency Value", *RFS* 30(2) (search rendering) | https://ideas.repec.org/a/oup/rfinst/v30y2017i2p416-441..html | (a) via rendering |
| 9 | McConnell & Xu (2008), *FAJ* 64(2) (abstract, search rendering) | https://ideas.repec.org/a/taf/ufajxx/v64y2008i2p49-64.html | (a) via rendering |
| 10 | Etula, Rinne, Suominen & Vaittinen (2020), "Dash for Cash", *RFS* 33(1), abstract (fetched) | https://ideas.repec.org/a/oup/rfinst/v33y2020i1p75-111..html | (a) |
| 11 | DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5) (search rendering) | https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901 | (a) via rendering |
| 12 | Goulding, Harvey & Mazzoleni (2023), "Momentum Turning Points", *JFE* 149 (search rendering) | https://people.duke.edu/~charvey/Research/Published_Papers/P158_Momentum_turning_points.pdf | (a) via rendering |
| 13 | Carver, "pysystemtrader: Estimated forecast scalars" (2016) | https://qoppac.blogspot.com/2016/01/pysystemtrader-estimated-forecast.html | (b) |
| 14 | Carver, "Some more trading rules" (2017) | https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html | (b) |
| 15 | Carver, "Annual performance update returneth — year 11" (2025) | https://qoppac.blogspot.com/2025/04/annual-performance-update-returneth.html | (b) |
| 16 | Carver, "Quickies #1: Overfitting and EWMAC forecast scalars" (2025); "Optimising weights with costs" (2016; search rendering) | https://qoppac.blogspot.com/2025/06/quickies-1-overfitting-and-ewmac.html ; https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html | (b) |
| 17 | SG Trend Index, BarclayHedge page: *"YTD: 15.16%"* as of Sep-25-2026 | https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=SG-Prime-Services-Indices&indexName=SG-Trend-Index | (b) |
| 18 | CFM, "Steady Trends: The Reality of CTA Return Dispersion" (search rendering: 2024 pairwise correlation 0.78; SG CTA +2.4%) | https://www.cfm.com/steady-trends-the-reality-of-cta-return-dispersion/ | (b) via rendering |
| 19 | Tickstory, "Dukascopy Historical Data – Available Date Ranges" (dateModified 2025-10-15) | https://tickstory.com/dukascopy-historical-data-available-date-ranges/ | (c) |
| 20 | Dukascopy datafeed candle layout (hexdocs `Dukascopy.DataFeed`; dukascopy-node; search rendering) | https://hexdocs.pm/dukascopy/Dukascopy.DataFeed.html ; https://www.dukascopy-node.app/ | (b/c) |
| 21 | E8 Markets swap-free option and "no overnight financing" (search rendering; direct fetch refused with 403) | https://e8markets.com/e8-pro ; https://help.e8markets.com/en/articles/5514977-what-instruments-are-allowed-to-be-traded-spreads | (c) |
| 22 | TradersUnion, "FTMO Islamic account" (aggregator) | https://tradersunion.com/brokers/prop/view/ftmo/halal-or-haram/ | (c) |
| — | Prior work cited and not re-fetched: ARC (HOP 2017 text-verified; H3/H5/H8; gates G0–G6), SCO (FTMO/E8 rules, gap-trading clause, 0.7% T&C 5.3.4), C4 (Carver's speed limit, `ceiling_cost_SR`), and the 2026-09-16 FX-methods report (Huang 2020, Neely–Weller, Menkhoff 2012, post-GFC carry) | `/tmp/review-acis/archive/…`, `CLOUD_AUDIT/reports/C4_PROVEN_PARTS.md` | as graded there |

**Receipts** are in `CLOUD_AUDIT/reports/r1/evidence/R1B/`. Each is a script plus its `.out`, and each is synthetic, or documentation-only, or price-free:
- `probe_ftmo_swap_carry.py`
- `probe_holding_cost_sr.py` (uses labelled assumptions)
- `sim_rule_turnover_null.py`
- `sim_tsmom_vs_ewmac_null.py`
- `probe_effective_breadth.py`
- `probe_holdout_draw.py`

To re-run the FTMO probes, fetch `https://ftmo.com/wp-json/ftmo/symbols` to `ftmo_symbols.json` first. The raw JSON is not committed, because it is 232 KB of broker documentation that the firm updates.
