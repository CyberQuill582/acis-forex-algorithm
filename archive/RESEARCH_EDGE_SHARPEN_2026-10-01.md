# RESEARCH — EDGE: where the claws come from (EDGE researcher, 2026-10-01)

- **Who asked, and why.** The lead launched this pass on the owner's request of 2026-10-01 evening (TODO "sharpen the claws"): *"make the engine better at winning in trades across the many instruments ... a money maker still without recklessly throwing cash away."* The lens here is **where the edge comes from**. Sizing and conservatism belong to SIZING, and validation pace belongs to PACE. This report touches them only where they bind on edge.
- **Status.** This is a finder's report (constitution A5). It is evidence for the lead to verify (A6), never an instruction (A9). Nothing in it binds until the lead has re-checked it and the owner has ratified any **[spec]** item.
- **Independence and contamination.** I ran in fresh context and launched no subagents. The harness put `CLAUDE.md` and the owner's memory index into my context at the start, so I knew the GAP-P12D-49 verdict and the prop-firm choice before I began. I am an LLM with a June 2026 knowledge cutoff, so I know some outcomes after publication. **Every hypothesis in this report is therefore LLM-selected.** Under master v2.24 §5.6, history can kill these hypotheses, and only forward data can credit them.
- **What I read in the repo** (read-only):
  - `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` (the H-slate), `archive/RESEARCH_FX_METHODS_2026-09-16.md`, and the executive summary of `archive/RESEARCH_PROP_ECONOMICS_2026-09-24.md`;
  - `R1_LEAD_REVIEW_2026-09-25.md` and the TODO R1 block;
  - `KNOWN_GAPS.md` GAP-P12D-136, `OPERATIONS_LEDGER.md` OPS-0001 and `archive/RESEARCH_VENUE_CHOICE_2026-09-17.md`;
  - the code: `tests/backtest/universe.py`, `rsim.py` (head), `swaps.py`, `cost_filters.py` and `core/signals/families.py`;
  - the venue's own data file `tests/backtest/swap_tables/ftmo_2026-09-25.json`.

  I read no market prices and ran no backtest.

Grades: **(a)** peer-reviewed, regulator, or a firm's own primary document; **(b)** credible practitioner, unrefereed working paper, or dataset; **(c)** unverifiable; **[D]** derived by me, with the inputs stated so the lead can re-derive it. Backtest-only evidence is marked *backtest*. Live or out-of-sample evidence is marked *live/OOS*.

---

## Executive summary

1. **H4, the overnight drift, is dead, and its own authors say so.**
   - **Evidence.** Boyarchenko, Larsen and Whelan, writing on the NY Fed's Liberty Street blog on 2026-07-01: the 02:00–03:00 ET window "that previously generated roughly 3.7 percent per annum has averaged close to zero since 2021". They attribute the fade to the dispersion of end-of-day order imbalances falling from 6.5% to 2.9%. Grade (a/b).
   - **Knock-on.** The same mechanism carried part of H3, the index reversal after selloffs. H3's overnight channel is therefore at risk too.
   - **Action.** Retire H4 to the graveyard and reuse it as a **second negative control** for 2021–2023.
2. **At FTMO's own swap table, R1's own swap filter admits only about 2–3 of the 21 explored non-energy instruments for the TREND family [D, from (a) venue data].**
   - **The markups.** The table is FTMO's dated 2026-09-25 snapshot. Under the symmetric-markup reading:
     - the median FX markup is 1.45%/yr per side;
     - index markups are 3.5–4.8%/yr, and holding the **long** side of an index costs 6–10%/yr;
     - gold costs 7.2%/yr long.
   - **Carry is gone.** The best-side swap a carry position *earns* at FTMO averages 0.02 Sharpe units a year, against about 0.21 for the fair rate differential. The venue keeps roughly 90% of the FX carry premium.
   - **The filter result.** Master §5.6's swap filter (markup × time in market ÷ vol ≤ 0.10 SR) refuses US500 (0.21), gold (0.20) and even EUR/USD (0.16). With assumed vols, it admits only EUR/JPY, CHF/JPY and EUR/AUD.
   - **Implication.** **R1-D9 (the swap regime) decides the breadth of the flagship family. It is an edge decision, not a cost detail.**
3. **The strongest new candidate the slate missed is institutional rebalancing pressure.** Source: Harvey, Mazzoleni and Melone, version of 2026-01-14 (b; AFA 2026 / NBER AP 2025).
   - "When stocks are overweight ... a decrease in equity returns of 17 basis points over the next day."
   - Their front-running portfolio returned **10.20% a year at 9.17% vol, Sharpe 1.11, skew +5.23** over 1997–2023. The Sharpe is 0.90 excluding the GFC and COVID, and about 1 net of their cost assumptions.
   - **Fit with ACIS:**
     - The signal days are mostly **short-equity** days, and the short side of an index carries almost no swap at FTMO.
     - The rule is contrarian to equity trend, so its correlation with TREND should be negative.
     - Only the equity leg is tradable here: FTMO lists **no bond and no VIX CFDs** (verified in its symbol table).
4. **Index intraday momentum (H1/H2) is alive but decaying, and it is the only candidate with about 250 observations per instrument per year and no swap at all.**
   - One independent replication of the noise-band strategy: "Sharpe 1.4–2.0 every year" in 2020–2024, then "Edge compressed since 2025: recent Sharpe ≈ 0" (c).
   - Its mechanism is under pressure: high 0DTE dealer gamma is linked to *lower* intraday volatility, not momentum amplification (Dim, Eraker and Vilkov 2024, via a secondary summary, b).
   - The gross edge is about 1.2–2.6 bp per trade, against 0.6–1 bp of spread. Gross/cost is about 1.5–4.
5. **Realistic numbers** for a portfolio of many weak sleeves:
   - **Century of factor premia** (a, gross): the average single factor in a single asset class has Sharpe **0.40**. Out of sample it is 18–49% lower. Arbitrage degradation after publication is about 0 for momentum and for the multifactor portfolio.
   - **Live diversified trend** (b): the SG CTA Trend Index has Sharpe **0.38** over the last 5 years. The SG Trend Index has a 5.33% CAGR since inception and a maximum drawdown of 20.6%.
   - **Carver's futures account** (b), 2014/15–2024/25, 100+ instruments: he reports Sharpe **0.76**, against 0.42 for AHL and 0.45 for SG CTA. His worst year was −14.7%. His median instrument contributes Sharpe **0.15** (*backtest*).
   - **For ACIS [D]:**
     - **0.25–0.5 net** at a swap-free venue, with about 20 instruments and 4–6 sleeves;
     - **0.15–0.35** at FTMO's swaps.

     A sustained Sharpe above about 1 is a bug suspect.
6. **Breadth arithmetic [D]:** SR_p = s·√(N/(1+(N−1)ρ)).
   - At a per-unit Sharpe of s = 0.2:
     - 6 sleeves at ρ = 0.1 give 0.40;
     - 21 instruments at ρ = 0.1 give 0.53;
     - ρ = 0.3 caps either at about 0.35.
   - **The cheapest claws are cross-mechanism sleeves**: trend (positive skew), contrarian flow, and intraday windows. Their correlations are near zero or negative, and they are uncorrelated by mechanism rather than by luck.
7. **Demote or kill:**
   - **H5**, the month-end fix: the FCA found reversals around the fix gone after 2015 (a, via a search rendering). Fade variants were rejected (c).
   - **H7**, local-hours depreciation: its own authors say a simple strategy is "not profitable for most pairs because of trading frictions" (a).
   - **H9**, short USD on FOMC days: no post-2017 replication found, and its sibling, the pre-FOMC equity drift, died (a).
   - **Cross-sectional FX carry** is dead at the venue [D, finding 2]. **FX value** is weak:
     - Carver's slow price mean reversion and relative value backtest at about 0 (b);
     - the yen stayed "18% undervalued" through 2024 (c).
   - **Volatility premia** are not expressible, because FTMO lists no VIX or bond CFDs (a).
8. **Infrastructure the new sleeves need. Both items are P&L-blind.**
   - **An at-the-cash-close execution slot for daily index flow sleeves.** RSIM's index slot fills at 10:00 New York the next day (GAP-P12D-136), which would miss a close-to-close effect.
   - **1-minute index candles plus a window simulator** for intraday sleeves. The tick set covers 8 FX and gold only; it has no index ticks.
9. **Shortlist** (§6; at most 6, ranked):
   1. **REBAL**: rebalancing pressure on index CFDs;
   2. **TREND**: as built, with the swap world chosen for breadth;
   3. **IMOM**: index intraday momentum into the cash close;
   4. **IREV**: index 1-day reversal;
   5. **TOM**: turn of the month on indices;
   6. **GOTOBI**: USD/JPY into the Tokyo fix.
10. **Honesty bound.** Compute cannot buy edge. At Sharpe 0.5, one-sided certification at t = 2 takes about 16 years of data. Forward data from any of these sleeves will mostly **kill**, not certify, unless the true Sharpe is ≥ 1 (§5.4). The owner's lever for "winning more" is therefore breadth across genuinely different, venue-cheap mechanisms, run at the risk level the contract rewards (SIZING's lane). It is not a search for a stronger single rule.

---

## 1. What ACIS has now (verified in the repo, 2026-10-01)

- **Universe** (`tests/backtest/universe.py`): 30 instruments, 7 of them held out. The explored set is:
  - FX 13: EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF, EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/CHF, EUR/AUD, CHF/JPY;
  - metals 2: XAU, XAG;
  - indices 6: US500, US30, UK100, JP225, EU50, AUS200;
  - energy 2: UKOIL, NATGAS. RSIM refuses energy until its rolls are back-adjusted (GAP-P12D-137).
- **The TREND family** (`core/signals/families.py`):
  - D1 = EWMAC 16/64, 32/128 and 64/256 at equal weight, pinned to pysystemtrade `a62269d2`;
  - breakout 40/80/160;
  - MOP's 12-month sign.

  Its declared deviation reads: *"at the venue, carry is a cost term, not a return source"*. Finding 2 confirms that with numbers.
- **The cost filters** (`tests/backtest/cost_filters.py`):
  - turnover cost ≤ 0.10 SR;
  - swap markup × time in market ÷ vol ≤ 0.10 SR, i.e. one third of a declared 0.30 pre-cost Sharpe. The member time-in-market values are 0.76–0.82 for EWMAC and breakout, and 1.00 for MOP.
- **RSIM** decides on the 17:00 New York close. Fills run on pre-registered per-symbol slots (GAP-P12D-136): FX and metals at 08:00 New York; US indices at 10:00 New York; UK100 at 09:00 London; EU50 at 09:00 Frankfurt; JP225 at 10:00 Tokyo; AUS200 at 11:00 Sydney.
- **Data on hand:**
  - hourly bid/ask candles for all 30 instruments, 2012–2025;
  - ticks for 8 instruments (AUD/USD, EUR/GBP, EUR/USD, GBP/USD, USD/CAD, USD/CHF, USD/JPY, XAU/USD), with **no index ticks**;
  - dated policy and overnight rates (`data/macro`: BIS, ESTR/DFR, SONIA, TONA, SARON, CORRA), with **no 10-year bond yields**.
- **Lot granularity** (R1 lead review X1): at $6k and a 10% vol target, all 13 FX pairs, gold and silver can never hold one minimum lot. The holdable instruments are the index CFDs.

---

## 2. The H-slate, challenged with 2023–2026 evidence

The 2026-09-24 slate carries H1–H10 and H12–H14. **There is no H11**: a numbering gap only.

| ID | What changed 2023–2026 | Strongest counter-evidence | Verdict |
|---|---|---|---|
| **H1** index intraday momentum into the cash close | Li, Sakkas & Urquhart 2022 (a): in- and out-of-sample in most of 16 markets. A noise-band replication (c) on SPY and ES, at 0.25–0.4 bp cost: Sharpe 1.4–2.0 every year 2020–24, +2.6 bp per trade, win rate 41%, payoff 1.69, 2022 +25.8% while SPY fell 19.5%. | The same replication: "Edge compressed since 2025: recent Sharpe ≈ 0 on both instruments … Not allocable today" (c). The mechanism has shifted: Dim, Eraker & Vilkov 2024 find 0DTE open-interest gamma linked to *reduced* intraday vol, with no amplification (b, read via a summary). In Chinese commodity futures, intraday momentum held "before the launch of night trading" (a). 23-hour CFDs may likewise dilute an effect anchored to the open. | **Keep, rank lower than the slate did.** It is still the highest-breadth family and swap-free by construction. Expect decay; add a post-2023 sub-period kill check. |
| **H2** noise-band intraday trend | As H1; the Zarattini et al. paper ran net Sharpe 1.33 over 2007–24 (b, *backtest*). | As H1; plus crowding, since it is popular with retail algorithms. | **Fold into H1's family**, as the slate already says. |
| **H3** index 1-day reversal after large down days | Indexing keeps growing, so the Baltussen–van Bekkum–Da mechanism (a) has more fuel. Anecdotal post-2010 numbers: after a ≥1.5% Monday loss, Tuesday averaged +0.9% (c, small sample). | Part of the reversal ran through the **overnight** dealer-inventory channel, which Boyarchenko et al. now say faded after 2021 (H4 row). No post-2016 academic update found. | **Keep**, with a 2021–2023 sub-period check. |
| **H4** US500 overnight drift into the European open | **Dead.** Liberty Street, 2026-07-01 (a/b): the 2:00–3:00 ET window "has averaged close to zero since 2021"; it was ">60%" of the E-mini's 5.9% annual return over 1998–2020. End-of-day signed-volume dispersion fell from 6.5% to 2.9%. | — | **Retire** to the graveyard. Revival condition: closing-imbalance dispersion returns to pre-2021 levels. **Reuse it as a negative control on 2021–2023.** |
| **H5** month-end hedging flow into the London 4 pm fix | The FCA (OP46): short-term reversals around the fix disappeared from 2015 on (a, via a search rendering; not fetched). A practitioner test of 4 pairs, 469 trades in 2017–22, 48 parameter cells: the best cell made $0.41 a trade, and only 4 of 48 cells finished positive; "Rejected" (c; it tested the fade, not Melvin–Prins' direction). | Melvin–Prins' *directional* pre-fix effect is untested after 2015 in anything I found. | **Demote** to the bottom of the slate; it has 12 bets a year per pair and they share the USD factor. |
| **H6** gotobi USD/JPY into 09:55 JST | Bessho, Sugimoto & Suzuki, arXiv 2301.13204 (b): over 2018–2020, a long from 3:00 to 9:55 JST on gotobi days "stably" earns after the bid-ask; the same window on non-gotobi days "stably decreased by the bid-ask spreads". | That paper is *about* the anomaly's popularity, which signals crowding risk. Nothing found after 2020. | **Keep. It is the cheapest test there is: USD/JPY ticks are on disk.** |
| **H7** FX local-hours depreciation | — | The original authors: "not profitable for most pairs because of trading frictions" (a, SNB WP 2011-04 abstract). | **Demote**; test only for EUR/USD, which the authors exempt, and only if trials are cheap. |
| **H8** cross-asset TSMOM / TREND | Live: SG CTA Trend Sharpe 0.38 over 5 years (b). The SG Trend Index was −10.0% YTD and −13.0% over 12 months to July 2025, max drawdown 20.6% (b). Carver's live account: −14.7% in 2024/25, his "worst ever" (b). Momentum's out-of-sample Sharpe is about 23% below in-sample, with no measurable arbitrage degradation (a). | Huang et al. 2020 (a): little time-series momentum asset by asset. Slow-biased CTAs had better drawdown efficiency (b). **At FTMO the long side of indices and metals carries a 6–10%/yr swap** (§4). | **Keep as the backbone, but only at a venue where its breadth survives** (finding 2). |
| **H9** FOMC-day short USD | None found after 2017. | The sibling pre-FOMC equity drift "essentially disappeared after 2015" (a). | **Demote**; it also needs the unbuilt event calendar. |
| **H10** pre-FOMC drift (negative control) | Unchanged. | — | **Keep**, and add H4 as a second control. |
| **H12** gold and WTI intraday momentum | Commodity intraday momentum is documented: crude oil (USO, 2006–18) in- and out-of-sample; first-half-hour predictability on non-EIA days (a, J. Futures Markets 40(4) and Energy Journal 44(5)). | The night-trading dilution result (a), as in H1. No gold-specific magnitude. WTI is refused until rolls are built (GAP-P12D-137). | **Keep at low rank; gold first.** |
| **H13** gold London-open opening-range breakout | No new evidence. | Lore (c). | **Keep as the lore test**, under the discovery standard (t ≥ 3). |
| **H14** NVMA `trend_direction` | — | R1 already demoted NVMA to a veto. | **Retire** from the slate. |

**Cross-cutting decay evidence.**
- **Ilmanen et al. 2021, *JOIM*, Table 2** (a). Out-of-sample Sharpe falls by these amounts: value −49%, momentum −23%, carry about −25%, multifactor −18%. "Arbitrage degradation" (post-publication minus pre-sample) is about zero: −0.03 for multifactor, p = 0.83.
- **What that means for ACIS [D].** Published premia shrink, but mostly because of in-sample overfitting, not crowding. **So the haircut to apply to a published Sharpe is roughly 25–50%, not 100%.**

---

## 3. Edges the slate missed

Each item below gives: its mechanism; the evidence and its grade; how it fits this universe; whether it survives costs; and whether it reaches the shortlist.

### N1 — Institutional rebalancing pressure on equity indices (REBAL). **Shortlisted, #1.**
- **Mechanism.** About $20 trillion of 60/40-style money rebalances mechanically: on thresholds, at about 2% drift, roughly 16 times a year, and on the calendar at month-end, 12 times a year. Both are predictable from public prices. "When stocks are overweight, funds sell stocks and buy bonds, leading to a decrease in equity returns of 17 basis points over the next day" (b).
- **Evidence** (Harvey, Mazzoleni & Melone, version of 2026-01-14, Dice WP 2025-01, SSRN 5122748; grade b):
  - **Table 6, 1997-09-10 to 2023-03-17:** RStrategy returns 10.20% a year at 9.17% vol, **Sharpe 1.11**, skew 5.23. The authors say it is "robust to the inclusion of transaction costs", with net Sharpe "close to 1". Excluding Sept 2008–Mar 2009 and Mar 2020, it is 0.90.
  - **Robustness:** alphas exceed 9% a year with t > 4 against CAPM, C4, FF5 and HXZ.
  - **Seasonality:** "Calendar predictability is strong at month-end but absent at other times"; predictive power "increase[s] as the quarter-end approaches".
  - **Timing and reach:** the effect "became significant in the early 2000s"; the signals "also extend to international equity markets".
- **Fit.**
  - **Breadth:** the 6 explored index CFDs, with GER40 and US100 in stage C.
  - **Holding:** 1 day, about 28 events a year.
  - **Costs:** the signal is mostly *sell equities after equity outperformance*. That is the side FTMO barely charges: US500 short is −0.14%/yr, against a long of −8.76%/yr. At Pepperstone, a short *receives* ARR − 2.5% (a).
  - **Correlation:** it is contrarian to equity trend, so expect ρ(REBAL, TREND) ≤ 0.
- **Declared deviations needed:**
  1. **Equity leg only.** FTMO has no bond CFDs (verified in `ftmo_2026-09-25.json`), so the paper's stock-minus-bond spread is not tradable.
  2. **The US 60/40 signal drives non-US indices,** unless local bond data are acquired.
  3. **A bond return series is needed to build the signal:** FRED DGS10 with a duration approximation, or 10-year note futures. It is not on disk; acquiring it is P&L-blind.
- **Risk.** The skew of +5.23 means the money is made in stress: GFC and COVID were "significant contributors". Its large positions fall exactly where a prop daily-loss rule bites. ACIS's vol scaling must cap the exposure (SIZING's lane).

### N2 — Turn of the month in equity indices (TOM). **Shortlisted, #5.**
- **Evidence.**
  - McConnell & Xu 2008, *FAJ* 64(2) (a): since 1987 the average daily value-weighted excess return is "0.14%" during the TOM window (day −1 to day +3), against "−0.01%" on the other 16 days. The effect appears in "31 of the 35 countries".
  - Quantpedia's digest of the (−1, +3) strategy, 1926–2005 (b, *backtest*): 7.2% a year at 6.9% vol, Sharpe 1.04, maximum drawdown −20.8%.
  - Hatlemark & Grohshennig 2022 (b): 0.55% per 4-day TOM window in US stocks, 1986–2021.
  - "After the introduction of ETF trading, the TOM effect … is concentrated on the first trading day" (b).
- **Counter-evidence.** It is long-only, so it partly *is* the equity premium, timed. Calendar effects "tend to vanish or rotate" (b). At month-end it overlaps REBAL's calendar component, with the opposite sign after an equity-outperformance month.
- **Cost at FTMO [D].** The window holds about 5–6 nights long. At the 4.45%/yr markup (1.2 bp a night) that is about 7 bp, plus about 1 bp of spread. Against the pre-publication 56 bp a window, gross/cost is about 7; against a post-publication guess of 28 bp, it is about 3.5.
- **Family accounting.** Register it in the **same family as REBAL** (equity calendar flow) for trial accounting, and test it after REBAL.

### N3 — Cross-sectional FX carry, momentum and value as a portfolio. **Not shortlisted.**
- **Evidence** (Ilmanen et al. 2021, Table 1; a, gross, 1974–2020, rescaled): currency value 0.60, currency carry 0.42, currency (cross-sectional) momentum 0.16, currency multifactor 0.62.
- **Why not.**
  - **Carry:** the venue keeps about 90% of it (§4.1).
  - **Momentum:** weak even gross.
  - **Value:** it needs CPI and PPP data, which are not on disk. Its holding period is months, so it pays the ~1.45%/yr FX markup almost continuously, about 0.17 SR at 8% vol. Recent experience was poor: the yen stayed "18% undervalued in real terms" (c) while value was long it.
  - **Breadth:** only 7 explored currencies (USD, EUR, JPY, GBP, AUD, CAD, CHF), too thin for a cross-sectional sort (the FX-methods report §4.1 says the same).
  - **Carver's price-based slow mean reversion:** Sharpe −0.48, and 5-year relative value "basically zero" (b, *backtest*).
- **Revival.** Only on a swap-free account, once CPI data are on disk, as a low-weight diversifier.

### N4 — Volatility-managed exposure. **Not a sleeve; a property of all sleeves.**
- **Evidence.** Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert 2018, *JPM* 45(1), Man AHL, 60 assets, 1926–2017 (a). Vol targeting raises Sharpe for equity and credit (the leverage effect) and is "negligible" for bonds, FX and commodities. It "reduces the likelihood of extreme returns, across all asset classes".
- **Counter-evidence.** Cederburg et al. 2020 (a, already in the slate's sources): vol-managed factor portfolios fail out of sample as a return source.
- **ACIS.** RSIM already sizes on Carver's vol. The gain is in the left tail, which matters under a 5% daily loss rule. Expect no Sharpe gain outside the index sleeves.

### N5 — Time-of-day effects. Partly shortlisted (IMOM, GOTOBI); the rest are low priority.
- **Gold sessions** (b/c):
  - The World Gold Council's 2024 attribution: the largest contributions came "during Asian trading hours".
  - A 2026-07 note: gold was "up 12.9 percent [H1] … during Asian trading hours" and "down 15 percent" during North American hours (c).
  - **Status:** no peer-reviewed prior, so it needs the discovery standard (t ≥ 3). The window crosses the rollover, so a long pays gold's 7.2%/yr long swap at FTMO, about 2 bp a night.
  - **Verdict:** register as a low-rank novel hypothesis, not on the shortlist.
- **FX local hours (H7)** and **the London fix (H5):** both demoted, §2.

### N6 — Skew and volatility premia. **Not expressible here.**
- FTMO's 2026-09-25 symbol table has no VIX and no bond CFDs (a, verified locally).
- Short-volatility proxies are negative-skew. They are incompatible with a 5% daily loss limit and a static 10% maximum loss.
- **The useful idea is the skew mix.** TREND, IMOM and REBAL are positive-skew: REBAL's skew is +5.23, and IMOM gained +25.8% in 2022 (c). IREV is negative-skew. Combining them balances the tails without selling options.

### N7 — Commodity carry through the oil CFD swaps. **Later.**
- FTMO's USOIL.cash swap is long +49.65 / short −225.45 points. That implies the venue passes the futures curve to the CFD holder.
- The magnitudes look implausible under the "points per unit" reading I used for other classes, and energy is refused until GAP-P12D-137.
- **Revival:** once energy rolls and the CFD swap units are verified.

---

## 4. Cost realism at the venue

### 4.1 FTMO: what its own swap table implies

**Source and method [D].** The source is FTMO's own symbol feed, `ftmo.com/wp-json/ftmo/symbols`, snapshot 2026-09-25 in the repo (a).
- **Annual %:** points × 10^−digits × 365 ÷ the reference price.
- **Reading:** the symmetric-markup reading of `swaps.py`, i.e. markup = −(L+S)/2.
- **Assumptions, stated:** reference prices are late-2025 levels and annual vols are typical values.
- **Robustness:** the markup-to-vol ratios for indices and metals sit about 2× the 0.125 admission line, so the conclusion survives vol errors of ±40%.

| Instrument | Long %/yr | Short %/yr | Markup %/yr | Markup ÷ vol | Admitted for EWMAC (time in market 0.8)? |
|---|---|---|---|---|---|
| EUR/USD (vol 7%) | −2.99 | +0.11 | 1.44 | 0.205 | no |
| USD/JPY (10%) | +0.62 | −4.22 | 1.80 | 0.180 | no |
| GBP/USD (8%) | −1.47 | −1.21 | 1.34 | 0.168 | no |
| AUD/USD (10%) | −1.91 | −3.09 | 2.50 | 0.250 | no |
| USD/CHF (8%) | +0.88 | −6.12 | 2.62 | 0.328 | no |
| EUR/JPY (10%) | +0.34 | −2.11 | 0.88 | 0.088 | **yes** |
| CHF/JPY (11%) | −2.27 | +0.34 | 0.96 | 0.088 | **yes** |
| EUR/AUD (9%) | −2.72 | +0.48 | 1.12 | 0.124 | **yes** (marginal) |
| XAU/USD (16%) | −7.21 | −0.72 | 3.97 | 0.248 | no |
| XAG/USD (28%) | −10.63 | +0.29 | 5.17 | 0.185 | no |
| US500 (17%) | −8.76 | −0.14 | 4.45 | 0.262 | no |
| US30 (16%) | −9.05 | +0.44 | 4.30 | 0.269 | no |
| UK100 (14%) | −8.98 | +0.41 | 4.28 | 0.306 | no |
| JP225 (22%) | −6.10 | −2.61 | 4.36 | 0.198 | no |
| EU50 (18%) | −7.20 | −0.07 | 3.64 | 0.202 | no |
| AUS200 (14%) | −9.12 | +0.59 | 4.26 | 0.305 | no |

- **The full sweep.** Across the 21 explored non-energy instruments, EWMAC members are admitted on 3 (EUR/JPY, EUR/AUD, CHF/JPY) and MOP12 on 2. The FX median markup is 1.45%/yr, and its median markup ÷ vol is 0.174.
- **Carry.** The mean best-side swap ÷ vol across the 16 FX pairs is **0.024**, against **0.208** for |fair differential| ÷ vol.
- **Other FTMO costs** (a, the same JSON):
  - FX commission is "$5 flat_USD" per lot. The JSON also lists `pipCommissionPerLot` 0.3 for EUR/USD, so whether $5 is per side or round turn needs reading off the platform. That is 0.26–0.52 bp round trip.
  - Metals: 0.0014% per side.
  - Indices: 0 commission.
  - **Spreads are not published:** "see 'Specification'" in the platform (a, carried from `RESEARCH_VENUE_CHOICE`).
  - **The 0.7% adjustment.** A 0.7% adjustment applies to realised P&L on every non-account-currency position (T&C 5.3.4, a, carried). It hits USD/JPY, UK100, EU50, JP225, AUS200 and GER40.
    - Its effect [D] is about 0.7% × E|P&L per trade| ≈ 0.0056 × the per-trade P&L sd.
    - For a sleeve with per-trade Sharpe 0.1, that takes about 6% of the edge: real, but second-order.
- **XCU** (held out) decodes to nonsense under this reading. Its units are unverified.

### 4.2 Pepperstone (the demo venue) and E8 (the swap-free candidate)
- **Pepperstone** (a):
  - **Index CFDs:** no commission. August 2026 average spreads are US500 0.4 pt (≈0.59 bp at 6,800), US30 2 pt (≈0.43 bp), NAS100 1 pt (≈0.40 bp), AUS200 1 pt (≈1.15 bp). The GER40, UK100 and JPN225 figures on that page are for forwards.
  - **Index funding:** `(price × size × (2.5% ± ARR)) / 360`, i.e. a 2.5% markup against FTMO's ~4.4%.
  - **Razor FX and gold:** $3.50 per lot per side. The demo account shows $3 per lot per side on cTrader (OPS-0001).
  - **FX swaps,** from the venue's demo API (OPS-0001, read as pips) [D]: EUR/USD markup ≈ 0.91%/yr, USD/JPY ≈ 1.55%/yr; fair differentials −1.38% and +2.23%, consistent with FTMO's.
  - **Admission [D]:** US500 is still refused narrowly at the 2.5% markup (0.118), and EUR/USD is borderline (0.104).
- **E8:**
  - The swap-free option on E8 One and Pro is (a), per the R1 lead review. It reportedly costs about +10% on the fee (c).
  - Commissions (c, aggregator): FX $5/lot, metals, indices and energies $6/lot.
  - **The binding unknown is the index contract size.** If one lot is 1 × the index (≈$6,800 on US500), $6 is about 8.8 bp a round trip, and that would kill every intraday index sleeve. **Verify it on the platform before choosing E8 for IMOM.**

### 4.3 Holding period against friction: which candidates survive

All figures [D] unless graded; the gross edges come from the cited sources.

| Sleeve | Holding period | Observations per year | Gross edge per trade | Cost per trade, FTMO | Cost per trade, Pepperstone | Gross/cost |
|---|---|---|---|---|---|---|
| REBAL, short day | 1 night | ~28 per index | 17 bp per event (b; read as the conditional mean, to be verified) | ~1 bp spread (unpublished; measure) + short markup ≈ 0 | 0.6 bp, and the short *earns* ARR − 2.5% | ≈ 10–17 |
| REBAL, long day | 1 night (×3 on Friday) | (same) | 17 bp | 1 + 1.2 bp (3.6 on Friday) | 0.6 + 0.7 bp | ≈ 4–8 |
| TREND (daily) | weeks to months | turnover 3–18 a year | Sharpe ≈ 0.15–0.3 per instrument | **markup 0.09–0.33 SR/yr** (§4.1) | 0.10–0.12 SR (FX, US500) | refused on most instruments at FTMO |
| IMOM | 30 min | ~250 per index (~85 on the top tercile) | 1.2–2.6 bp (Li et al. derived; replication (c)) | spread unknown, ≈ 0.6–1 bp; no swap | 0.4–0.6 bp + slippage; no swap | ≈ 1.5–4 (top tercile ≈ 3–5) |
| IREV | 1 night long | ~40–60 per index | ~10–30 bp (c, small samples) | 1 + 1.2 bp (3.6 on Friday) | 0.6 + 0.7 bp | ≈ 4–10 |
| TOM | ~4 trading days, 5–6 nights, long | 12 per index | 56 bp pre-publication (a); ~28 bp assumed after | 1 + ~7 bp | 0.6 + ~4 bp | ≈ 3.5–7 |
| GOTOBI | ~3 h, after the rollover | ~60–70 | not extracted; measure on the E segment (ticks on disk) | ~0.2–0.3 bp spread + 0.26–0.52 bp commission + the 0.7% JPY adjustment | ~0.2–0.3 bp + 0.5 bp | unknown; kill at < 2 |

**What this means.**
1. **At FTMO, multi-day holding of long index or metal positions is taxed heavily.** Each long night costs about 1.2 bp of index markup, or 2.4 bp all-in long. **The venue-cheap shapes are therefore:**
   - intraday sleeves, which carry no swap;
   - 1-day flow sleeves that are mostly short;
   - FX crosses with small markups.
2. **The swap-free route removes the swap entirely** and restores the daily TREND family's breadth. The E8 commission question then decides whether the intraday sleeves survive there.

---

## 5. How to win across many instruments

### 5.1 The arithmetic [D]
- **Equal risk weights.** With N units, each of Sharpe s, and average pairwise P&L correlation ρ:

  SR_p = s·√(N / (1 + (N−1)ρ)).

  Carver's IDM and FDM are the same factor: 1/√(wᵀHw), with H the correlation matrix of the units' returns. ACIS caps it at 2.5 (`rsim.IDM_CAP`).

| s per unit | N = 3 | N = 6 | N = 10 | N = 21 |
|---|---|---|---|---|
| 0.1, ρ = 0 / 0.1 / 0.3 | 0.17 / 0.16 / 0.14 | 0.24 / 0.20 / 0.15 | 0.32 / 0.23 / 0.16 | 0.46 / 0.26 / 0.17 |
| 0.2, ρ = 0 / 0.1 / 0.3 | 0.35 / 0.32 / 0.27 | 0.49 / 0.40 / 0.31 | 0.63 / 0.46 / 0.33 | 0.92 / 0.53 / 0.35 |
| 0.3, ρ = 0 / 0.1 / 0.3 | 0.52 / 0.47 / 0.41 | 0.73 / 0.60 / 0.46 | 0.95 / 0.69 / 0.49 | 1.37 / 0.79 / 0.52 |

- **Correlation, not count, is the binding term.** At ρ = 0.3 a portfolio cannot pass about 1.7 × s, however many units it has.
- **Same-mechanism trend instruments correlate.** FX pairs share the USD factor, and indices share the equity factor.
- **Different mechanisms correlate near zero or negatively**, as §5.2 sets out.

### 5.2 Which combinations are least correlated

This is a prior [D] with its reasons. Measure position correlations P&L-blind on the null, as the FDM was measured.

| | TREND | REBAL | IMOM | IREV | TOM | GOTOBI |
|---|---|---|---|---|---|---|
| TREND | 1 | −0.1 (REBAL sells after equity outperformance) | +0.1 | −0.15 (opposite skew) | +0.1 | 0 |
| REBAL | | 1 | 0 | +0.2 (both contrarian next-day) | −0.2 (month-end overlap, opposite sign) | 0 |
| IMOM | | | 1 | −0.2 (intraday momentum "reverts over the next days", Baltussen et al. 2021, a) | +0.05 | 0 |
| IREV | | | | 1 | +0.1 | 0 |
| TOM | | | | | 1 | 0 |

- **The resulting planning range.** The average off-diagonal is about 0, so plan on ρ̄ in [0, 0.15].
- **Breadth inside sleeves.** Within a sleeve, the index instruments correlate highly: index returns have ρ ≈ 0.6–0.8. The event sleeves' within-sleeve breadth across indices is therefore worth only about √2–√3, not √6.

### 5.3 What portfolio net Sharpe is realistic (live and OOS evidence first)

| Evidence | Sharpe | Type | Grade |
|---|---|---|---|
| SG CTA Trend Index, last 5 years | 0.38 | live index | (b) |
| SG CTA and AHL, 2014–2025, per Carver | 0.45 / 0.42 | live | (b) |
| Carver's futures account, 100+ instruments, trend + carry + others, 2014/15–2024/25 | 0.76 (worst year −14.7%) | live, self-reported | (b) |
| Carver, median instrument inside a 100-instrument book | 0.15 per instrument; book 0.84 | *backtest* | (b) |
| AQR Style Premia (QSPIX), Oct 2013 – May 2026 | 7.56%/yr; Sharpe ≈ 0.6–0.75 if vol ≈ 10–12%; 2018–20 cumulative ≈ −37% | live fund | (b) data; vol and Sharpe are [D] |
| Century of factor premia: average single factor in a single asset class / multifactor | 0.40 / 1.46 gross; OOS −18 to −49% | long history, gross | (a) |
| HMM rebalancing, stock–bond long/short | 1.11 gross, about 1 net, 0.90 excluding crises | *backtest*, one paper | (b) |
| FX-only trend, walk-forward on 7 majors | 0.43 | *backtest* | (c) (carried) |

**ACIS expectation [D].**
- **Inputs.** Four to six sleeves with s ≈ 0.2–0.35 each (published values after a 25–50% decay haircut), ρ̄ ≈ 0–0.15, and costs at the venue.
- **Result:**
  - **0.3–0.55 at a swap-free venue**, where TREND keeps about 20 instruments;
  - **0.2–0.4 at FTMO's swaps**, where TREND shrinks to about 3 FX crosses and the index sleeves must stay intraday or short-biased.
- **For comparison.** The ECONOMIST found the prop route +EV for an OOS net Sharpe above about −0.4 to 0 on static-floor 2-Step geometry. That band clears it, but not by much. **What turns it into money is breadth and venue-cheap shapes, not a sharper single rule.**

### 5.4 The forward clock (for PACE; stated once)

Under master v2.24 every hypothesis here is LLM-selected: it can be killed on history and credited only forward. Years of data needed for t = 2 are (2/SR)²:
- 44 years at Sharpe 0.3;
- 16 at 0.5;
- 6.2 at 0.8;
- 4.0 at 1.0;
- 1.8 at 1.5.

Forward data will therefore kill failures quickly, and certify nothing below Sharpe ~1 within the life of a prop account. The lever is to run many cheap, different sleeves forward at minimum size **in parallel**, so that the kills arrive early.

---

## 6. The ranked shortlist (test these first)

Common to all six:
- Each is a **fixed family** under R1: at most 3 free parameters at the literature values; the C8 cost model per fill; master §5.6's two cost filters; the plateau law as kill-only; stage A as registered (expanding walk-forward, fixed-sequence order, HAC lower bound, net > 0 at 2× cost including swap); and stage C on the held-out instruments and 2024–25.
- "E" below means the exploration years inside the expanding walk-forward before the first OOS year.
- **Each needs a provenance record** with its citation, falsifier and declared deviations before any look (ACIS-11).

### S1. REBAL — rebalancing pressure on index CFDs (new; family FLOW-EQ, tested first in it)

**Rule, pinned to its source.** Harvey, Mazzoleni & Melone, "The Unintended Consequences of Rebalancing", version dated 2026-01-14 (SSRN 5122748):
- §1.2, eq. (2): the Threshold signal is the average of threshold signals over δ from 0% to 2.5%, computed on a simulated 60/40 S&P 500 / 10-year T-note portfolio from daily futures returns.
- Appendix B, eq. (B.2): the Calendar signal.
- §4: its modification. The sign is −Calendar in the last week of the month, and Calendar(−4) on the first business day.
- Table 6: the managed portfolio. **Re-read §4 before registration.**

ACIS's form:
- each explored index CFD holds −sign(signal) × the vol-scaled unit, from one cash close to the next, on signal days;
- it is flat otherwise.

Declared deviations:
- equity leg only, because FTMO lists no bond CFDs;
- non-US indices use the US 60/40 signal;
- the bond return is approximated from DGS10 with a duration of about 8.5, unless futures data are acquired.

**Other details:**
- **Instruments:** US500, US30, UK100, JP225, EU50, AUS200, with GER40 and US100 in stage C.
- **Holding:** 1 day, about 28 events a year.
- **Expected net Sharpe:** about 0.2–0.5 per index, and 0.3–0.6 for the family [D from (b): 17 bp ÷ ~110 bp daily vol ≈ 0.155 per event, × √28 ≈ 0.82 gross, then a 50% decay and equity-leg haircut].
- **Data:** the hourly candles (on disk) plus **a 10-year Treasury daily series (not on disk)**.
- **Testable in RSIM now?** Daily RSIM, after two P&L-blind additions:
  1. the bond series;
  2. **an at-the-cash-close execution slot.** Decide on the local cash close and fill at the open of the first hourly candle after it, before the daily break, plus a declared adverse slippage. RSIM's current index slot (10:00 New York the next day) would miss a close-to-close effect.

**Numeric falsifiers.** These are pre-registered; the first is P&L-blind.
1. **P&L-blind:** the signal fires 10–40 times a year on 2012–2023. Otherwise the construction is wrong: fix it, do not look.
2. **E:** the pooled slope of the next-day index return on the Threshold signal is ≥ 0, i.e. the wrong sign.
3. **Mechanism check:** the Calendar component's effect in the last week of the month is ≤ its mid-month effect.
4. **Stage A:** the HAC lower bound is ≤ 0, or the family is net ≤ 0 at 2× cost including swap.
5. **Reported, not gated:** the 2021–2023 sub-period mean ≤ 0 is flagged as post-publication decay.
6. **Stage D:** E2 reaches 20 and kills it.

### S2. TREND — as built; choose the world that keeps its breadth (family TREND)
- **Rule:** unchanged (`core/signals/families.py`, pysystemtrade `a62269d2`, MOP 2012).
- **Instruments:**
  - **swap-free:** all 21 explored non-energy instruments;
  - **FTMO markup world:** about 3 FX crosses (§4.1).
- **Holding:** weeks to months.
- **Expected net Sharpe:**
  - **0.2–0.45 swap-free** (b/a: SG CTA 0.38–0.45 live; per-instrument 0.15 × √N_eff ≈ √6–√9);
  - **0.05–0.25 at FTMO's swaps** [D].
- **Data:** on disk.
- **RSIM:** now.
- **Falsifiers:** stage A as registered (fixed sequence, strict C9 over all seven members, owner-ruled).
- **Added pre-registration rule (owner decision):** if fewer than 8 instruments are admitted in the chosen swap world, TREND is **not** first in the fixed sequence. A thin TREND first would likely burn the cycle: at FTMO, D1's power is about 9% (R1 lead X2).

### S3. IMOM — index intraday momentum into the cash close (family IM: H1 + H2)
- **Rule.** Gao, Han, Li & Zhou 2018, *JFE* 129(2), eq. (1)'s timing strategy, as replicated across 16 markets by Li, Sakkas & Urquhart 2022, *JFM* 57:
  - over the last 30 minutes of the cash session, hold the sign of the return from the previous cash close to 30 minutes after the open;
  - vol-scaled;
  - flat at the close.
- **Pre-registered variant:** top tercile only, by first-period |return| or 20-day realised vol, where "stronger on more volatile days" (a).
- **Instruments:** US500, US30 (NYSE close), UK100, EU50 (local closes), JP225, AUS200.
- **Holding:** 30 minutes; ~250 trades per instrument a year, ~85 on the top tercile.
- **Expected net Sharpe:** 0.1–0.5 per instrument family after decay [D from (a) plus the (c) replication].
- **Data:** **1-minute bid/ask candles for the indices, 2012–2023, not on disk.** Dukascopy supplies them, and downloading them is P&L-blind.
- **RSIM:** it **needs an intraday window simulator.** Hourly candles do not align with the 09:30 New York open.
- **Falsifiers** (H1's):
  - **E:** the mean of sign(close→open+30) × (last-30 return) is ≤ 0; the top-tercile effect is ≤ the bottom tercile's; or the measured gross/cost is < 2.
  - **Stage A:** net ≤ 0 at 2× cost.
  - **Reported:** a 2021–2023 per-trade mean ≤ 0 is flagged as decay.

### S4. IREV — index 1-day reversal after large down days (family REV: H3)
- **Rule.** Per the slate (H3), pinned to Baltussen, van Bekkum & Da 2019, *JFE* 132(1):
  - if the close-to-close return is < −1σ (60-day σ), go long at the cash close and hold to the next cash close;
  - the crash filter (declared) skips when 20-day realised vol > 2× its 1-year median;
  - no Friday entries (FTMO's gap rule).
- **Instruments:** the 6 explored indices.
- **Holding:** 1 night; about 40–60 trades per index a year.
- **Expected net Sharpe:** 0.1–0.4 [D]. Its overnight channel is weakened since 2021 (the H4 evidence).
- **Data:** on disk.
- **RSIM:** daily RSIM with the at-the-close slot from S1.
- **Falsifiers:**
  - **E:** the mean next-day return after a −1σ day is ≤ the mean after a +1σ day.
  - **Stage A:** net ≤ 0 at 2× cost including swap.
  - **Tail:** the worst single day at the proposed size exceeds 2% of equity.
  - **Reported:** a 2021–2023 sub-period mean ≤ 0.

### S5. TOM — turn of the month on indices (family FLOW-EQ, after S1)
- **Rule.** McConnell & Xu 2008, *FAJ* 64(2), Table 3 panel A1, the (−1, +3) window:
  - long from the cash close of trading day −2 to the cash close of day +3 of the new month;
  - vol-scaled.
- **Instruments:** the 6 explored indices.
- **Holding:** 4 trading days; 12 trades a year per index.
- **Expected net Sharpe:** 0.1–0.4 [D: 1.04 gross 1926–2005 (b), halved for decay, minus about 7 bp of markup per window at FTMO].
- **Data:** on disk.
- **RSIM:** daily RSIM with the at-the-close slot.
- **Falsifiers:**
  - **E:** the TOM-day mean excess return minus the non-TOM-day mean is ≤ 0.
  - **Stage A:** its paired excess over a time-matched `PASSIVE_LONG` arm is ≤ 0, or it is net ≤ 0 at 2× cost.

### S6. GOTOBI — USD/JPY into the Tokyo fix (family FLOW-FX: H6)
- **Rule.** Ito & Yamada 2017, *JIE* 109; Bessho, Sugimoto & Suzuki 2023 (arXiv 2301.13204):
  - long USD/JPY on gotobi days (the 5th, 10th, 15th, 20th, 25th and month-end, business-day adjusted per Ito–Yamada);
  - from the first full hour after the 17:00 New York rollover (07:00 JST in winter, 06:00 in summer; a declared deviation from Bessho's 03:00, to avoid the swap and the rollover spread, R1 lead X3) to 09:55 JST.
- **Instrument:** USD/JPY, explored; CAD/JPY is held out.
- **Trades:** about 60–70 a year.
- **Expected net Sharpe:** 0.1–0.3 [D]; single instrument, low weight.
- **Data:** **USD/JPY ticks on disk.**
- **RSIM:** **needs the window simulator**, or the tick harness with `{zone, at}` windows.
- **Falsifiers:**
  - **E:** the mean gotobi-window return is ≤ 0, or ≤ the same window's mean on non-gotobi days.
  - **Stage A:** net ≤ 0 at 2× cost.
  - **Reported:** a 2021–2023 mean ≤ 0.
- **Why it is on the list.** It is the cheapest intraday test: its data exist, and its mechanism (importers' settlement) is independent of every other sleeve.

**Order to test** (my recommendation; the owner decides):
1. **S1 and S4/S5:** daily RSIM with two P&L-blind additions; days to build.
2. **S2:** at the first look, once R1-D9 is decided with §4.1's admission result in hand.
3. **S6:** when the window simulator lands.
4. **S3:** after the minute candles and the window simulator.

---

## 7. Experiments for the lead (specified for `acis-compute-1`)

1. **X-1: swap admission in three worlds** (P&L-blind; this is GAP-P12D-136's owed admission run).
   - **Inputs:**
     - the 21 explored non-energy instruments' realised vol, 2012–2023, from the hourly candles (vol only, no returns read);
     - `cost_filters.MEMBER_INPUTS` time in market;
     - three swap tables: FTMO 2026-09-25; Pepperstone, from the demo account's symbol swap fields through the Open API (P&L-blind); and swap-free.
   - **Output:** the admitted (instrument × member) set per world.
   - **Prediction to check:** FTMO 2–4 instruments, Pepperstone 3–8, swap-free 21.
2. **X-2: lab power for S1.**
   - On `lab_market` index paths, plant a next-day effect of −8.5 bp per event (half the paper's), triggered by a 60/40 drift rule at about 28 events a year, over 11 OOS years. Seeds 1–500.
   - **Metric:** stage-A pass rate, planted against null. The null must be ≤ α + 2 se.
   - This tells the owner whether S1 can pass at all before a look is spent.
3. **X-3: portfolio expectation Monte Carlo** (synthetic).
   - Six sleeves with Sharpe vector (0.30, 0.35, 0.30, 0.20, 0.20, 0.15), the §5.2 correlation matrix, t(4) daily innovations, 11 years, seeds 1–2000.
   - **Report:** the distribution of the realised portfolio Sharpe, P(SR̂ ≤ 0), and P(maximum drawdown > 10%) at 10%/yr vol.
   - The point is to set the owner's expectations before real data do.
4. **X-4: data, P&L-blind.**
   - Dukascopy 1-minute bid/ask candles, 2012–2023, for the 6 explored indices, XAU, and the 2 held-out indices (stage C only).
   - FRED DGS10, daily, 2011–2025.
   - A spread-by-minute profile in the 60 minutes around each cash close, as S3's cost input.

---

## 8. What I could not verify (residual risk)

- **FTMO's real spreads** (unpublished), and **whether its $5 FX commission is per side or round turn.**
- **E8's index contract sizes and commission** (c).
- **Pepperstone's swap units** are inferred as pips per lot from OPS-0001. Their fair differentials agree with FTMO's to within about 10%.
- **HMM's 17 bp:** the abstract's wording does not say whether it is per unit of signal or the conditional mean. Their international construction and §4's exact rules need a full read. The paper's own sample ends in March 2023; its first public version was 2025, so ACIS's 2012–2023 data are **pre-publication** for it.
- **No post-2017 study of H9, and no post-2020 study of H6.**
- **Carver's 0.76** is his self-reported account Sharpe, and the fetched summary labelled the block "vol-adjusted". **QSPIX's vol is not verified.** The H3 magnitudes are anecdotal (c). The Dim–Eraker–Vilkov and FCA claims were read through secondary renderings.
- **FTMO's triple-swap weekday** for metals and CFDs is unverified (GAP-P12D-136). It does not change annual markups.
- **The model-selection hazard.** I selected these sleeves knowing some outcomes up to June 2026: for example, that trend struggled in 2025 and that intraday momentum compressed. That knowledge is why §6 credits nothing on history.

## 9. Ledger items this pass should generate (the lead assigns IDs)

1. **H4 is dead per its authors (2026-07).**
   - Action: graveyard it with the revival condition in §2, and add it as a negative control on 2021–2023.
   - Severity medium · Likelihood high · Status open · [impl].
2. **At FTMO's swaps, TREND's admissible universe is about 3 of 21 instruments [D].** R1-D9 is an edge decision.
   - Action: attach §4.1 and X-1 to the R1-D9/D14 ruling.
   - Severity high · Likelihood high · Status open · [owner decision].
3. **Register REBAL (S1) as a new family**, plus bond-data acquisition. Its equity-leg and US-signal deviations are declared.
   - Severity medium · Likelihood medium · Status open · [spec — owner ratification of a new family].
4. **An at-the-cash-close execution slot for daily index flow sleeves** (S1, S4, S5), extending GAP-P12D-95's clock.
   - Severity medium · Likelihood high · Status open · [spec + impl].
5. **The intraday window simulator plus minute candles** for S3 and S6 (and H12/H13 later).
   - Severity medium · Likelihood high · Status open · [impl].
6. **E8's index commission and contract size** must be read from the platform before a swap-free route is chosen for intraday index sleeves.
   - Severity medium · Likelihood medium · Status open · [owner action].
7. **Demote H5, H7 and H9; retire H14; flag H3's overnight channel** as decayed since 2021.
   - Severity low · Likelihood high · Status open · [impl, registry].
8. **Check that FTMO's 0.7% non-USD P&L adjustment is owned in C8** for the index CFDs (UK100, EU50, JP225, AUS200, GER40) as well as for FX.
   - Severity low · Likelihood medium · Status open · [impl].

---

## Sources

Every URL was accessed on 2026-10-01. The grade is per source; a claim's grade can be lower where it was read through a secondary.

**Slate updates and new edges**
- Boyarchenko, Larsen & Whelan, "The Disappearing Overnight Drift", Liberty Street Economics, 2026-07-01 — (a/b) — https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/
- Boyarchenko, Larsen & Whelan, "The Overnight Drift", *RFS* 36(9), 2023 (NY Fed SR 917) — (a) — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf
- Harvey, Mazzoleni & Melone, "The Unintended Consequences of Rebalancing", 2026-01-14 (Dice WP 2025-01, SSRN 5122748); text extracted — (b) — https://www.edhec.edu/sites/default/files/2026-03/Scientific%20paper.%20ssrn-5122748.pdf ; summary at https://www.fuqua.duke.edu/duke-fuqua-insights/what-do-pensions-lose-from-rebalancing (b)
- Independent replication of Zarattini–Aziz–Barbon 2024 (GitHub, codecat-ops) — (c) — https://github.com/codecat-ops/zarattini-2024-momentum-spy
- Zarattini, Aziz & Barbon, "Beat the Market…", SFI WP 24-97 — (b) — https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- Gao, Han, Li & Zhou, "Market intraday momentum", *JFE* 129(2), 2018 — (a) — https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351
- Dim, Eraker & Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation", 2024, via a summary — (b) — https://harbourfrontquant.substack.com/p/the-rise-of-0dte-options-cause-for
- Commodity intraday momentum: *J. Futures Markets* 40(4) — (a) — https://ideas.repec.org/a/wly/jfutmk/v40y2020i4p632-650.html ; *Energy Journal* 44(5) — (a) — https://ideas.repec.org/a/aen/journl/ej44-5-xu.html
- Bessho, Sugimoto & Suzuki, arXiv 2301.13204 (gotobi, 2018–2020); text extracted — (b) — https://arxiv.org/abs/2301.13204
- Breedon & Ranaldo, SNB WP 2011-04 (abstract) — (a) — https://snb.ch/de/mmr/papers/id/working_paper_2011_04
- FCA Occasional Paper 46 (read via a search rendering) — (a) — https://www.fca.org.uk/publication/occasional-papers/occasional-paper-46.pdf
- Month-end fix fade portfolio test — (c) — https://yuratrading.com/blogs/month-end-fix-portfolio
- Mueller, Tahbaz-Salehi & Vedolin, *JF* 72(3) (no post-2017 replication found) — (a) — https://eprints.lse.ac.uk/77256/
- McConnell & Xu, "Equity Returns at the Turn of the Month", *FAJ* 64(2), 2008 — (a) — https://ideas.repec.org/a/taf/ufajxx/v64y2008i2p49-64.html
- Quantpedia, Turn of the Month in Equity Indexes — (b) — https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes
- Harbourfront Quant, "Do Calendar Anomalies Still Work?" (Hatlemark & Grohshennig 2022) — (b) — https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work
- Baltussen, van Bekkum & Da, *JFE* 132(1) (no update found) — (a) — https://personal.eur.nl/vanbekkum/2018%20JFE%20BaltussenVanBekkumDa.pdf
- S&P 500 post-down-day anecdotes — (c) — https://www.schaeffersresearch.com/content/analysis/2021/09/22/is-turnaround-thursday-a-real-thing
- World Gold Council, "Let's tally the rally" (2024) — (b) — https://www.gold.org/goldhub/gold-focus/2024/11/lets-tally-rally ; Money Metals, 2026-07-12 — (c) — https://www.moneymetals.com/news/2026/07/12/a-strange-dichotomy-gold-up-on-the-year-in-asian-markets-down-big-in-the-west-005059
- Harvey et al., "The Impact of Volatility Targeting", *JPM* 45(1), 2018 — (a) — https://quantpedia.com/the-impact-of-volatility-targeting-on-equities-bonds-commodities-and-currencies
- G10 FX valuation notes (yen undervaluation) — (c) — https://am.vontobel.com/en/insights/the-yen-reloaded-a-hidden-hedge

**Portfolio and live evidence**
- Ilmanen, Israel, Moskowitz, Thapar & Wang, "How Do Factor Premia Vary Over Time? A Century of Evidence", *JOIM* Q4 2021; Tables 1 and 2 text-extracted — (a) — https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/JOIM_How-Do-Factor-Premia-Vary-Over-Time.pdf
- Carver, "Annual performance update returneth — year 11" (2025-04) — (b) — https://qoppac.blogspot.com/2025/04/annual-performance-update-returneth.html
- Carver, "PCA analysis of futures returns … part deux" (2025-09) — (b, *backtest*) — https://qoppac.blogspot.com/2025/09/pca-analysis-of-futures-returns-for-fun.html
- Carver, "Very slow mean reversion…" (2025-03) — (b, *backtest*) — https://qoppac.blogspot.com/2025/03/very-slow-mean-reversion-and-some.html
- CFA Institute Enterprising Investor, "Decoding CTA allocations by trend horizon" (2026-01-28) — (b) — https://rpc.cfainstitute.org/blogs/enterprising-investor/2026/decoding-cta-allocations-by-trend-horizon
- SG Trend Index 2025 reports (Top Traders Unplugged, Alternatives Watch) — (b) — https://www.alternativeswatch.com/2025/06/02/trend-following-hedge-funds-endure-more-pain-societe-generale-indices/
- AQR Style Premia Alternative Fund (QSPIX) returns — (b) — https://funds.aqr.com/funds/aqr-style-premia-alternative-fund
- G10 carry 2022–2024 (secondary) — (c) — https://fffinstill.com/learning/concepts/the-carry-trade

**Venue costs**
- FTMO symbol feed, snapshot 2026-09-25, in the repo at `tests/backtest/swap_tables/ftmo_2026-09-25.json` (fetched by the lead from `ftmo.com/wp-json/ftmo/symbols`) — (a)
- Pepperstone, Index trading fees and spreads (averages for 01/08/2026–31/08/2026) — (a) — https://pepperstone.com/en/markets/indices/index-fees
- Pepperstone, Trading accounts (Razor $3.50/lot/side) — (a) — https://pepperstone.com/en/trading/accounts/
- Pepperstone demo account, venue-reported swaps and commission (OPS-0001 in `OPERATIONS_LEDGER.md`) — (a) for the fields; [D] for the units
- E8 Markets commissions (aggregator) — (c) — https://proptradingvibes.com/blog/e8-markets-spreads-commissions
- FTMO 0.7% non-USD P&L adjustment, T&C 5.3.4 (carried from `archive/RESEARCH_VENUE_CHOICE_2026-09-17.md`) — (a)

**Carried from the earlier ACIS reports** (not re-fetched): Li, Sakkas & Urquhart 2022 (a); Hurst, Ooi & Pedersen 2017 (a); Huang et al. 2020 (a); Moskowitz, Ooi & Pedersen 2012 (a); Neely & Weller 2003/2013 (a); Melvin & Prins 2015 (a); Ito & Yamada 2017 (a); Kurov, Wolfe & Gilbert 2020 (a); Cederburg et al. 2020 (a); Falck, Rej & Thesmar (a); McLean & Pontiff 2016, via Ilmanen et al. (a); Carver, "Fast but not furious" 2023 (b).

## Method note

- **WebSearch: 31 calls of the 50 allowed; 2 in "extended" mode.** The two calls that returned several result sets (FTMO spreads, FOMC) are counted once each; counted conservatively, the total is 34. After that I used WebFetch on primary URLs (about 22 fetches, 4 of which failed with 403/404/redirect).
- **Three PDFs** (AQR *JOIM*, Harvey–Mazzoleni–Melone, Bessho et al.) were fetched as binaries and text-extracted locally with `pypdf`. The extracts are in my session scratchpad, outside the repo.
- **Local computation** was light, under 5 seconds of CPU in all: the FTMO swap-table arithmetic from the repo's JSON, the cost-filter admission sweep, and the closed-form diversification and forward-clock tables. **No market price data was read and no backtest was run.**
- **Web content was treated as data.** No fetched page contained instructions that I acted on.
- **Repo and git:** no repo file was edited except this report, and I ran no git commands. I launched no subagents.
