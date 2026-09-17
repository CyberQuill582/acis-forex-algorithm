# RESEARCH — Fill fidelity: Dukascopy tick backtest vs live OANDA retail execution

**Date:** 2026-09-16 (finalised 2026-09-17). **Status:** COMPLETE.
**Supersedes:** `archive/PARTIAL_execution_fidelity_dukascopy_vs_oanda_2026-09-16.md` (crash-safety checkpoint written mid-task; retained per the never-delete convention, but this file is the record).
**Scope of the question put to this research pass:** the fidelity gap between (a) backtesting on Dukascopy tick bid/ask with a fill at the order price plus a small declared friction, and (b) live retail FX / spot-gold execution at a retail broker like OANDA — for a system trading 7 FX majors + spot gold, 1-minute bars built from tick data, holds of 30 minutes to 48 hours, $10k–$500k notional per order.
**Nature of this document:** external research evidence, graded by source class. **It is not a spec, not a decision, and not a ledger entry.** Nothing here has been applied to engine code, config, specs or the ledger. §10 lists the items that need owner triage into `KNOWN_GAPS.md` / `TODO.md` / `OPERATIONS_LEDGER.md`.

**Evidence grading used throughout:** [REGULATORY] · [BROKER-PRIMARY] · [ACADEMIC] · [CREDIBLE PRACTITIONER] · [DERIVED] (computed here from stated inputs) · [UNVERIFIABLE] · [NOT REACHED] (tooling gap — see below).

**Tooling constraint that shaped this pass — read before judging coverage.** The session's WebSearch budget was exhausted (200/200) before the work began. Every source below was obtained by direct WebFetch against a primary URL, with local PDF text extraction. Bing, DuckDuckGo, Mojeek, Startpage and web.archive.org were all captcha-gated, 403, or returned unrelated cached content. This biased the pass *toward* primary sources (regulator orders, broker legal documents, API specifications, academic PDFs) and *away* from secondary commentary — which suits the brief — but it means several items could not be reached at all. Those are marked [NOT REACHED], which means "tooling gap", **not** "does not exist". §11 lists them so they cannot quietly harden into assumed facts.

---

## 1. EXECUTIVE SUMMARY

Ranked by size of the fidelity gap for this system:

| # | Gap | Size | Confidence |
|---|---|---|---|
| 1 | **Spread level.** Dukascopy SWFX is a real ECN; OANDA is a principal market maker that sets its own prices. OANDA's own time-weighted average spreads are ~1.3–2.4 pips on the majors. | **≈0.8–3.4 bps per round trip, per instrument** | [BROKER-PRIMARY], high |
| 2 | **Wrong venue entirely.** OANDA states in writing that its prices "MIGHT NOT BE THE BEST PRICES AVAILABLE" and makes no warranty that they "represent exchange rates available elsewhere in the market." The backtest prices are a *different firm's* prices. | structural — affects every fill, every stop trigger, every bar | [BROKER-PRIMARY], certain |
| 3 | **Stop fills / gap-through**, including a specific API trap: a stop carrying a `priceBound` is **cancelled, not filled**, if the market gaps through both. | tail risk, potentially unbounded | [BROKER-PRIMARY], certain |
| 4 | **Rejects are adversely selected**, not random: the price check removes disproportionately the fills that would have been good for you. | 0.5–2 bps equivalent at retail; much larger in stress | [ACADEMIC] + [BROKER-PRIMARY] |
| 5 | **Latency.** For 30 min–48 h holds this is the *smallest* term. | ~0.03–0.07 pips (0.03–0.07 bps) of EUR/USD diffusion per 100 ms, normal regime | [DERIVED] |
| 6 | **Partial fills / size impact.** At $10k–$500k this is effectively a non-issue: OANDA's own "large transaction" threshold is **$100,000,000 in 10 seconds**. | ≈0 | [BROKER-PRIMARY], certain |

**The headline finding is not a slippage model.** It is that filling at the Dukascopy tick's own bid/ask systematically under-charges roughly **1.0–1.4 pips per round trip on EUR/USD-class pairs and up to ~3.4 bps on NZD/USD**, and no "small declared friction" fixes that unless the friction is calibrated to the **destination broker's** spread rather than the **source data's** spread. At 500 round trips/year that is ~4–11% of notional per year of cost the backtest never charges; at 2000 round trips/year, 20–45%. For a strategy holding 30 minutes to 48 hours, that is very likely larger than its entire gross edge.

Two secondary findings carry disproportionate weight for a live-readiness gate:
- **A `priceBound` on a protective stop is a live safety defect, not a refinement** — it converts a bad fill into *no protection at all* exactly in the gap.
- **OANDA's US Customer Agreement Event-of-Default clause reaches automated systems** ("using any ultra-high speed trading or automated or mass data entry system"), at OANDA's sole discretion, without notice. That is a counterparty risk to log before the first live fill, not an execution-model parameter.

---

## 2. DUKASCOPY DATA FIDELITY

### What the feed is
- SWFX is **Dukascopy Bank's own ECN**, launched 2006. Dukascopy Bank is FINMA-regulated as both a bank and a securities dealer. [UNVERIFIABLE-tertiary for the launch date — https://en.wikipedia.org/wiki/Dukascopy_Bank — corroborated by Dukascopy's own pages]
- Dukascopy's trading page: **"Large liquidity pool from 20+ banks"**, **"ECN"**, **"Transparent pricing - All clients have access to the same liquidity at equal prices through a single datafeed"**, **"eur/usd spread from 0.1"** pips, leverage up to 1:200, minimum deposit $100. — https://www.dukascopy.com/swiss/english/forex/trading/ [BROKER-PRIMARY]

### What the bid/ask represents, and at what size
- `ITick.getAsk()` = "Best ask price on the market"; `getAskVolume()` = **"Volume available at the best ask price on the market"** (same for bid). — https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/ITick.html [BROKER-PRIMARY]
- Dukascopy support, quoted on the record: **"Ticks are quotes arriving in our system from our liquidity providers. They are neither orders nor trades. We reflect only best ask and bid available in our system."** and **"Volumes shown are volumes quoted on the best bid and ask levels. This is not a guarantee that your trade will be executed at those prices."** — https://www.elitetrader.com/et/threads/interpreting-dukascopy-tick-data.352792/ [CREDIBLE PRACTITIONER quoting broker support]
- **Units: millions of base currency.** A `bidVolume` of `1.5` = 1.5 million units. [CREDIBLE PRACTITIONER — two independent forums quoting Dukascopy support; **not** stated in Dukascopy's own javadoc. Treat as strong-but-not-primary and verify empirically.]

**What this means for a $100k order.** If the volume field is in millions, EUR/USD top-of-book is routinely 1–5M, so **$100k is ~2–10% of displayed top-of-book — a rounding error, not a liquidity constraint.** This can be settled from data already on disk (§9, item 8a) rather than from any published source.

**Caveat that survives all of the above:** top-of-book size on SWFX is **irrelevant to live fills**, because execution will not happen on SWFX. It matters only for judging whether the quote series is a credible *reference price*.

### Format, filtering and known artefacts
- **bi5:** 20-byte big-endian records — `int32` ms-offset-from-hour, `int32` ask, `int32` bid, `float32` askVolume, `float32` bidVolume; **LZMA-compressed despite the extension**; price divisor 100,000 for standard pairs, 1,000 for JPY pairs and CFDs. — https://github.com/mayeranalytics/bi5 [CREDIBLE PRACTITIONER]
- **No published Dukascopy statement that the historical feed is filtered or cleaned.** The Historical Data Export page carries no data-quality, filtering or execution disclaimer. — https://www.dukascopy.com/swiss/english/marketwatch/historical/ [BROKER-PRIMARY, negative result]
- Two artefacts, both [CREDIBLE PRACTITIONER] from the EliteTrader thread:
  1. **Repeated-price ticks exist.** "Ticks can be with equal prices and reflected one-by-one on the tick chart and in the downloaded history" — an LP requoting the same BBO still emits a record. **Tick counts are therefore not a clean activity proxy.**
  2. **Post-weekend/post-holiday spreads are Dukascopy-specific wide:** spreads "are quite a bit wider than other high quality fx aggregators. But that usually settles an hour into the session." The first hour of the week in this data is a venue artefact, not a market fact — directly relevant to Sunday-open handling.
- **Volume is not traded volume.** There is no consolidated FX tape; the field is quoted size at top of book. Any volume-conditioned feature must say so in `declared_deviations`.

### Comparison to other tick sources
[NOT REACHED] — no rigorous published Dukascopy-vs-X comparison could be retrieved. The in-flight HistData cross-check (with the Frankfurt−6h clock correction, GAP-P12D-13) is the better instrument for this question anyway.

---

## 3. MARKET MAKER vs ECN/STP — WHAT REGULATORS ACTUALLY MEASURED

This is the best-evidenced section in the pass, because two regulators independently measured the same firm's asymmetric slippage.

### CFTC v. Forex Capital Markets LLC, 3 October 2011 [REGULATORY — primary order]
https://www.cftc.gov/sites/default/files/idc/groups/public/@lrenforcementactions/documents/legalpleading/enffxcmorder10032011.pdf

Mechanics, as found:
> "if the price received by FXCM in its offsetting trade… was better than the bid/ask price at the time that FXCM received the order from the customer—i.e., the price slipped positively for the customer while the trade was executed—then the customer still received the order at the original requested price and FXCM kept the difference"

> "for market orders during the relevant period, FXCM's customers were denied the benefit of any positive price slippage, but forced to bear the consequences of any negative slippage."

Quantified harm:
> "more than **57,000** of its customers were deprived of approximately **$8,261,937** in positive slippage (which amount FXCM retained) from **June 18, 2008 until December 17, 2010**"

> "the unequal treatment of price slippage… occurred **thousands of times a day across thousands of customer accounts for more than two years**"

Sanction: $6,000,000 civil penalty + $8,261,937 restitution (≈$14.2m total).

### FCA Final Notice, FXCM Ltd & FXCM Securities Ltd, 24 February 2014 [REGULATORY — primary notice]
Mirror used: http://dl.icdst.org/pdfs/files3/07e0f20234f7fd2708e195dc952e4738.pdf (the FCA's own URL 404'd during this pass)

**This is the more useful of the two, because it gives per-trade magnitudes.**
- Period **1 August 2006 – 17 December 2010**.
- "FXCM Group retained USD **$6,725,106** as profits from positive price improvements in **2,214,053 trades**" → **$3.04 per trade**.
- "FXCM Group retained USD **$3,103,571** from positive price movements in **1,101,161 limit orders**" → **$2.82 per limit order**. Limit orders were treated asymmetrically in a different way: favourable moves were pocketed, adverse moves left the order "reset to a pending status and the customer losing the opportunity to have the order executed at that time."
- FXCM Securities: **$113,293 over 24,709 trades** = $4.59/trade.
- FCA's own mitigation paragraph 2.5(2): **"The average slippage retained by FXCM Ltd on those trades where slippage was retained, a subset of all trades, was approximately $3.70."**
- Penalty £4,000,000 combined; redress up to **USD $9,941,970**; ~**75,000 active retail accounts** at 17 December 2010.

**Calibration reading:** one-sided suppression of positive slippage cost roughly **$3–4 per affected trade** at retail ticket sizes. That is the same order of magnitude as an entire ECN spread — i.e. **pure dealer-side execution asymmetry is a first-order cost, not a rounding error.** It is the best empirical anchor in the public record for "how much does dealer-side asymmetry cost a retail client."

### The rules that now constrain this
- **17 CFR 5.18(f)(2)**: a retail forex dealer may not "Adjust or alter prices for a retail forex transaction after the transaction has been confirmed to the retail forex customer" (subject to RFA rules). **5.18(f)(3)** requires bid/ask symmetry: may not "Provide a retail forex customer a new bid price… that is higher than its previous bid without providing a new asked price that is also higher" (and vice versa). **5.18(f)(1)** constrains giving different customers materially different prices simultaneously. — https://www.law.cornell.edu/cfr/text/17/5.18 [REGULATORY]
- **NFA Compliance Rule 2-43(a)**: Forex Dealer Members may not cancel or adjust an executed customer order to change pricing, except where "cancellation or adjustment is favorable to the customer and is done as part of a settlement of a customer complaint", or under narrow straight-through-processing / counterparty-adjustment conditions (15-minute notification; must "either cancel or adjust all executed customer orders executed during the same time period and in the same currency pair"). **2-43(b)**: members "may not carry offsetting positions in a customer account but must offset them on a first-in, first-out basis." Effective 15 May 2009, amended through 15 September 2022. — https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43 [REGULATORY]

**Two direct consequences for this system:**
1. On a **US** account, NFA 2-43(b) FIFO means independent long/short or independently-stopped positions in the same instrument are unreachable. OANDA's v20 API surfaces this as `OrderCancelReason.FIFO_VIOLATION`, plus `FIFO_VIOLATION_SAFEGUARD_VIOLATION` and `FIFO_VIOLATION_SAFEGUARD_PARTIAL_CLOSE_VIOLATION`. If the Governor can ever stage two same-instrument positions with separate stops, that is a live/backtest divergence class — and it is **jurisdiction-dependent**, so it must be a config-driven account rule, not a hard-coded assumption.
2. The "no re-quote" property at a US RFED is a **regulatory** property (5.18(f)(2) + NFA 2-43(a)), not a broker courtesy — and it is bought with a **rejection** right, not surrendered. The dealer's escape valve is refusing the order, not repricing it.

---

## 4. LAST LOOK

### The Code, exactly
**FX Global Code Principle 17**, reproduced in full in Appendix A of the GFXC's own report — https://www.globalfxc.org/uploads/gfxc_report_last_look-1.pdf [industry/REGULATORY primary]:
> "Last look is a practice utilised in Electronic Trading Activities whereby a Market Participant receiving a trade request has a final opportunity to accept or reject the request against its quoted price."

> "If utilised, last look should be a risk control mechanism used in order to verify validity and/or price. … The price check should be intended to confirm whether the price at which the trade request was made remains consistent with the current price that would be available to the Client."

> "the Market Participant has sole discretion, based upon the validity and price check processes, over whether the Client's trade request is accepted or not, **leaving the Client with potential market risk in the event the trade request is not accepted**."

The Code requires disclosure of "whether, and if so how, changes to price **in either direction** may impact the decision to accept or reject the trade, the expected or typical period of time for making that decision."

### Correction to a common premise — there was no 2025 revision to last look or pre-hedging
- **2021 (Three-Year Review, 15 July 2021):** "the GFXC agreed that the text of Principle 17 remains appropriate." **Principle 17 was NOT amended.** Instead the GFXC issued the August 2021 *Execution Principles Working Group Report on Last Look*, explicitly "not part of the Code." Its three recommendations: ensure a fair and effective last look process; enhance ex-ante disclosures; make information available to evaluate the handling of trade requests. Its hardest line:
  > "LPs should apply the price and validity check **without delay**… **Incorporating any delay that is additional to what is required to complete the price and validity check is considered contrary to Principle 17.**"

  It also requires (Disclosures Cover Sheet 3-II / 3-III) disclosure of whether the price check is **symmetrical or asymmetrical**, and of the **"Last Look window maximum and minimum length (in m/s)."**
- **2024/2025 (the next Three-Year Review, published January 2025):** "The 2024 Code amendments focus on **five of the Code's fifty-five principles (P9, P10, P35, P50, and P51)**" — client-generated data on e-trading platforms (P9), delegated execution where the provider is also Principal (P10), FX settlement risk (P35), plus P50/P51. — https://www.globalfxc.org/uploads/gfxc_3year_review_outcomes_dec2024.pdf [industry/REGULATORY primary]

**Neither Principle 17 (last look) nor Principle 11 (pre-hedging) was amended in 2021 or in 2024/25.** Any ACIS documentation asserting a "2025 last-look / pre-hedging revision" is factually wrong and should be corrected (§10, item 7). Pre-hedging *did* move in 2025 — at **IOSCO**, not the GFXC. [IOSCO final report NOT REACHED.]

### Hold times and price checks — the best current named-firm disclosure
**XTX Markets eFX Disclosure Cover Sheet, dated 18 September 2025** — https://www.xtxmarkets.com/assets/disclosures/global-efx-cover-sheet.pdf [BROKER-PRIMARY]
> "The last look window, being the time between receipt of a trade request by XTX and submission by XTX of its acceptance or rejection decision to the client, typically (**99th percentile**) ranges from a minimum of **0 m/s** to a maximum of **1 m/s**."

> "XTX uses zero hold time. The last look checks are applied as soon as the trade request is received."

Companion disclosure — https://www.xtxmarkets.com/assets/disclosures/global-efx-trading-practices-disclosures.pdf :
> "In respect of the price check, the standard setting is for the price check to be applied **symmetrically and without any tolerance applied i.e. if the price has moved at all, in either direction, the trade request will be rejected.**"

> "any trade request accepted by XTX shall be executed in its entirety. **There will be no partial fills of trade requests.**"

XTX also offers a **"No Last Look Stream"** where requests are accepted regardless of price movement (subject to maximum size and risk limits), and states plainly that tailoring produces "differences in pricing and **trade acceptance rates** between counterparties." **The market therefore prices last-look-vs-firm as an explicit spread/certainty trade-off** — which is exactly Oomen's theorem below, observed in the wild.

Note the implication of a **zero-tolerance symmetric** check: the reject rate becomes *whatever fraction of requests arrive on a stale price*, which at retail round-trip latency is a large number. That is why tolerance exists at all.

### Academic quantification — Oomen (2017), *Last look*, Quantitative Finance 17(7), 1057–1070 [ACADEMIC]
https://researchonline.lse.ac.uk/id/eprint/68811/1/Oomen_Last%20look_2017.pdf

Baseline calibration (N=15 homogeneous LPs, ω=0.5, β=0.75, ρ=0.5, nominal spread s=1, latency buffer n=1, σ=0.5):
- "the volatility of the trade-sign adjusted price move over the latency buffer is σα = 0.60 with a mean of −µα = −0.15. This implies that **the price is about 50% more likely to move over the latency buffer against the LP that wins the deal request than it is to move in its favour (i.e. 60% in trader's favour and 40% in LP's favour)**."
- Tolerance δ⁻ = ½ (half the intended spread capture): **"it will reject 28.5% of deal requests on that side"**; two-sided with δ⁺ = ½ rejects **"another 14.1% of deals… in the right-tail."**
- Loosening to δ⁻ = δ⁺ = 1: **"these figures reduce to 8.1% and 2.9% respectively."**
- Adverse-flow case: the break-even nominal spread is "substantially higher than before: **ranging between 1.65 and 2.55** depending on the setup."
- Indifference result: "assuming a reject rate of 20% for on-rate trading, an LP adopting one-sided last look **will reject 12.5%** of deal requests while the LP that uses two-sided last look with rebates **will reject 20%** in order to achieve the same effective spread."

Latency context from the same paper: "One-way transmission latencies tend to be in microseconds within the same data centre, sub-millisecond within the same city, around **10 milliseconds** between Chicago and New York, **30 milliseconds** between New York and London, and **over 100 milliseconds** between London and the Asia Pacific." Human reaction speed "around 150 – 200 milliseconds."

**Oomen's central theorem, and the one that matters here:** last look design changes **execution risk** (which of your orders happen), while effective transaction cost can be held constant by adjusting the quoted spread. **"No last look" is not free — it is paid for in spread.**

### Cartea, Jaimungal & Walton, *Foreign Exchange Markets with Last Look* (arXiv:1806.04460) [ACADEMIC]
Theoretical, no pip calibration, but it supplies the sentence that belongs verbatim in the execution spec:
> "with the Last Look option the costs of only accepted trades from STs is reduced to zero, but **the most profitable trades executed by the ST are cancelled**"

Plus the counterintuitive equilibrium result that a last-look venue can quote a *wider* spread than a firm venue once traders migrate between venues.

**Modelling implication — the whole point of this section:** a reject is **not** a coin flip. It is conditioned on the price having moved *in your favour* since you saw the quote. **Modelling rejects as an unconditional probability is strictly wrong and will flatter the backtest**, because it removes trades at random instead of removing your best ones.

### Implicit cost in bps — the nearest quantified regulatory analogue
**FCA Occasional Paper 50, Aquilina, Budish & O'Neill, *Quantifying the High-Frequency Trading "Arms Race"*, January 2020** — https://www.fca.org.uk/publication/occasional-papers/occasional-paper-50.pdf [REGULATORY/ACADEMIC]
- "The average FTSE 100 symbol has **537 latency-arbitrage races per day**. That is about one race per minute per symbol."
- "In the modal race, the winner beats the first loser by just **5-10 microseconds**… about 4% of the time the winner's message actually arrives to the exchange slightly later than the first loser's message, but nevertheless gets processed first."
- "about **22%** of daily trading volume is in latency-arbitrage races."
- "The top 3 firms win about **55%** of races, and also lose about **66%**."
- "The average race is worth a bit more than half a tick, which on average comes to about **2 GBP**. Even at the 90th percentile of races, the races are worth just 3 ticks and about **7 GBP**."
- "Price impact from trading in races is about **31%** of all price impact, and about **33%** of the effective spread."
- "the 'latency-arbitrage tax'… is **0.42 basis points** if using total trading volume, and **0.53 basis points** if using only trading volume that takes place outside of latency-arbitrage races. **The average value-weighted effective spread paid in our data is just over 3 basis points.**… market designs that eliminate latency arbitrage would reduce investors' cost of liquidity by **17%**."

**Use:** in a *firm-quote, exchange-traded* market the entire cost of being the slow side of the latency race is **~0.4–0.5 bps, ~17% of the effective spread**. In OTC FX, last look exists precisely to push that cost back onto the taker. **0.4–0.5 bps is a defensible order-of-magnitude floor for the implicit last-look/latency cost to a slow taker; the FXCM $3–4/trade figures are the empirical retail analogue.**

---

## 5. OANDA SPECIFICS

All [BROKER-PRIMARY] unless marked otherwise.

### Capacity — principal market maker, in writing
**OANDA Additional Disclaimer (US), version December 2025** — https://www.oanda.com/assets/documents/2003/OANDA_Additional_Disclaimer-2025.pdf
> "THE FOREIGN CURRENCY TRADING YOU ARE ENTERING INTO IS NOT CONDUCTED ON AN EXCHANGE. OANDA IS ACTING AS A COUNTERPARTY IN THESE TRANSACTIONS AND, THEREFORE, ACTS AS THE BUYER WHEN YOU SELL AND THE SELLER WHEN YOU BUY. AS A RESULT, OANDA'S INTERESTS MAY BE IN CONFLICT WITH YOURS. UNLESS OTHERWISE SPECIFIED IN YOUR WRITTEN AGREEMENT OR OTHER WRITTEN DOCUMENTS, **OANDA ESTABLISHES THE PRICES AT WHICH IT OFFERS TO TRADE WITH YOU. THE PRICES OANDA OFFERS MIGHT NOT BE THE BEST PRICES AVAILABLE.**"

> "IF OANDA ELECTS NOT TO COVER ITS OWN TRADING EXPOSURE, THEN YOU SHOULD BE AWARE THAT OANDA MAY MAKE MORE MONEY IF THE MARKET GOES AGAINST YOU."

Revenue model, same document: "For most accounts, OANDA charges no commissions, fees, or service charges from trading, and hence generates revenues from the spreads alone… you pay the equivalent of **half the spread, on average**, for each (opening or closing) trade… This goes to pay for the costs of sales, including: (1) the cost of hedging OANDA's excess exposure… **the spreads OANDA has to pay can be higher or lower than the spreads OANDA offers its clients**; (2) the cost of OANDA's exposure to market movements before third-party hedging occurs; and (3) interest and swap charges that OANDA incurs."

**OANDA Europe Limited Order Execution Policy, version May 2026** — https://legal.oanda.com/?code=execution_policy_oel&language=en
- §2.1 "We will act as **principal and not as your agent** when executing your Orders, we therefore act as **the sole trading venue** for those Orders. This means you will be dealing directly with us and not with the wider market."
- §2.2 "We cannot guarantee, when executing an Order, that our price will always be better than a price which might have been available elsewhere."
- §3.1(c) "We are not obliged to accept your Order(s) and may therefore reject any Order(s) in accordance with our Terms of Business."
- §5.1 — **how the price is constructed, key for the data question**: "The prices shown to you are based on an **average of the pricing, excluding outliers**, available from those third parties. This average is our objective view of the bid and ask prices available to arms' length market participants in respect of transactions of a **Normal Market Size**…"
- §5.5 "While we act as matched principal in respect of your Orders, OANDA group companies will look to the execution venues available to them for the pricing, hedging, and execution of your Orders and Trades. OANDA group companies may seek to manage their risk as market maker and may choose to hedge… **Accordingly, this may impact the execution price of your Orders.**"
- §10.2 "If the requested Transaction exceeds limits that we have established for the relevant Product, you may not be able to place your Order."
- §14.1 "We will not aggregate your Trade(s) or Order(s) with those of any other client during execution."
- §4.2 price improvement is a factor, not a guarantee: "…we will consider the need for timely execution, availability of price improvement, liquidity of the Instrument in relation to the size of your Order…"

### Slippage policy — symmetric, explicitly, and measured at their server
§11.1–11.2 of the same policy:
> "All Orders are executed at the prevailing price(s) at the time the Order is processed **after receipt on our execution server**."

> "The pricing and execution components of our Trading Platform **do not apply asymmetrical slippage parameters. Positive and negative slippage are handled with strict symmetry** to protect clients from foreseeable harm during execution gaps. Our Trading Platform is designed to ensure that any slippage, both negative and positive, is based on market conditions."

**There is no "no requotes, bounded slippage" guarantee anywhere in OANDA's legal documents.** The marketing phrase "policy of no re-quotes" appears only on the platform landing page (https://trade.oanda.com/). The actual mechanism is: **no requote, but they fill you at their post-latency price — or reject.**

### Order-type table (OEL Order Execution Policy, Annex 1) — settles the partial-fill question
> "**Market FOK** — A market order executed on an order execution venue at the most recent price appropriate for the quantity of the order. **There are no partial fills of the order. The order is rejected/cancelled in the case where the order size exceeds available liquidity.**"

Market FOK is used for **FX & Metals** and Indices & Commodities market orders. Only **equity-share** orders use Market IOC ("Partial fills are possible only in the case where the order size exceeds available liquidity. Any remaining quantity not filled will be cancelled"). Stop Entry / Stop Loss / Close Out route to "Market GTC Full" (an FOK leg) for FX/Metals; Limit / Take Profit route to "Limit GTC Full". Unfilled remainder "returns to the pending state in the OANDA group order book."

### Volatility and gap risk, in OANDA's own words (OEL §12.1)
> "(a) execution at a **substantially different price** from the quoted bid or ask or the last reported price at the time of Order entry, as well as partial executions or execution of large Orders in several Transactions at different prices; (b) delays in executing Orders for financial Instruments that we, or an OANDA group company, must send to external market makers; (c) **opening prices that may differ substantially from the previous day's closing prices**; and (d) Instrument market conditions, such as locked…, crossed…, **halted**, limit up…, limit down…, protected…, which may prevent the execution of client Orders."

### US Customer Agreement, version March 2026 — https://legal.oanda.com/?code=fxtrade_customer_agreement&language=en
- Definition (x): **"'Market Order' means an order to buy or sell a currency pair at the prevailing Exchange Rate. Please note that prices displayed for Market Orders are indicative and not guaranteed."**
- Definition (n): "'Exchange Rate' means the rate at which OANDA agrees to enter into a Trade with you." Definition (rr): "'Trade' means an Order executed by OANDA, **acting as counterparty**."
- §9(b): "Each Exchange Rate is valid only on the exact date and at the exact time that such Exchange Rate is presented to you. You acknowledge that in a rapidly changing market the Exchange Rate presented to you… may no longer remain in effect at the time your Order is executed at the OANDA Trading System server, and you agree that any Trade resulting from the execution of such Order shall be at the Exchange Rate in effect at the time such Order is executed on the OANDA Trading System server. **OANDA makes no warranty, express or implied, that the Exchange Rates represent exchange rates available elsewhere in the market.**"
- §9(c) Order Execution: "OANDA will use commercially reasonable efforts to execute any Order… at the prevailing Exchange Rate at the time such Order is **received at the OANDA Trading System server**. **OANDA will have no obligation to execute any Order** (other than a Close Out Order), including but not limited to any Order which would cause your Account to fail to meet the Margin Requirement."
- §9(d) Trading Limits: OANDA reserves the right to limit "the size of any Trade, the size of any Open Positions…, the total number of Open Positions…, and the number of Trades permitted within a set period of time", with or without notice.
- §9(e) Spreads: "Spreads may widen or narrow at any time at OANDA's sole discretion… **there is no limit to how wide the Spread may be.**"
- §9(g) Rejection of Orders: may reject any Order or close any Open Positions without prior notice, including "(iv) in the event of any circumstances or developments that OANDA, **in its sole discretion**, deems necessary or advisable for its protection."
- §11(e) **Special Handling for Large Transactions**: "If a Transaction or series of Transactions occurs in your Account which results in the immediate opening or closure of a Trade or series of Trades **within a period of 10 seconds**, in either case with an aggregate notional value that exceeds **$100,000,000 USD equivalent in any major currency pair** (e.g., a pair comprised of any two of AUD, CAD, CHF, EUR, GBP, JPY, USD), or **$30,000,000 USD equivalent in any other instrument**, then OANDA will execute your Trade(s) at the price shown in the OANDA Trading System at the time of your Trade(s) and subsequently may debit or credit your Account for the difference between the price shown… and an amount equal to **1.0-pip in excess of OANDA's actual volume-weighted cost of clearing such Trades.**" (Exhibit A worked examples use 40,000,000 USD/SEK and 125,000,000 EUR/USD.)
- "Invalid Price" = "an erroneous or otherwise incorrect Exchange Rate"; an Account Adjustment may result from "OANDA providing an Invalid Price quote" — the error-trade escape hatch, consistent with NFA 2-43(a).
- §13(b): OANDA "will not be liable to you for any loss or damage you may suffer or incur as a result of: i) OANDA's refusal to execute any Transaction; ii) any Account Adjustment; iii) **any failure, delay or error in executing or confirming any Transaction**…"
- ⚠️ **§11(f) Event of Default (iv):** "we reasonably believe you have acted in an unfair or abusive manner, for example, but not limited to, **using any ultra-high speed trading or automated or mass data entry system**". On an Event of Default, OANDA may "in its absolute discretion, at any time and **without prior notice**, initiate a Close Out Order for some or all your Open Positions, close any or all of your Accounts… or refuse to open new positions or Accounts for you." **ACIS is an autonomous automated system; this clause is broad enough to reach it.** Counterparty/venue risk for `OPERATIONS_LEDGER.md` before the first live fill, with a stated plan for a force-closed account.

### v20 API mechanics that change the fill model
Sources: https://developer.oanda.com/rest-live-v20/order-df/ · /transaction-df/ · /pricing-df/ · /primitives-df/ · /best-practices/
- **MarketOrder `timeInForce`: "Restricted to FOK or IOC for a MarketOrder", default `FOK`.** Fill-or-kill → **no partial fills**; the order is rejected instead.
- **`priceBound`: "The worst price that the client is willing to have the Market Order filled at."**
- ⚠️ **`StopOrder` + `priceBound`: "If the market gaps and crosses through both the price and the priceBound, the Stop Order will be *cancelled* instead of being filled."** A "protective" bound on a stop **removes the protection exactly in the gap**.
- **`StopLossOrder`: "An order that is linked to an open Trade and created with a price threshold. The Order will be filled (closing the Trade) by the first price that is equal to or *worse* than the threshold."** → gap-through is passed to the client.
- Trigger condition is selectable: "based on the bid, ask, mid, default (ask for buy, bid for sell) or inverse (ask for sell, bid for buy) price depending on the desired behaviour." **The backtest must use the same convention as the live account**; the default triggers a long's stop on the **bid**. A backtest triggering on mid or on a trade price will systematically under-count stop hits.
- `OrderFillTransaction.fullVWAP`: "The price that all of the units of the OrderFill should have been filled at, in the absence of guaranteed price execution. This factors in the Account's current ClientPrice, used liquidity and the units of the OrderFill only…" `fullPrice`: "The price in effect for the account at the time of the Order fill." The deprecated `price` field notes that "the individual tradesClosed, tradeReduced and tradeOpened fields contain the exact/official price each unit was filled at."
- `PriceBucket`: "A PriceBucket represents a price available for an amount of liquidity" — `{price, liquidity}`. `ClientPrice` carries `bids`/`asks` arrays ("It is possible for this list to be empty if there is no bid liquidity currently available"), `closeoutBid`/`closeoutAsk` (used "when a bid is required to closeout a Position (margin closeout or manual) yet there is no bid liquidity"), and a `tradeable` boolean.
- `Instrument` schema: `displayPrecision`, `pipLocation` ("The decimal position of the pip in this Instrument's price can be found at 10 ^ pipLocation"), `tradeUnitsPrecision`, `minimumTradeSize` ("The smallest number of units allowed to be traded for this instrument"), `maximumOrderUnits`, `maximumPositionSize`, `minimum/maximumTrailingStopDistance`, `marginRate`, `guaranteedStopLossOrderMode`, `guaranteedStopLossOrderExecutionPremium`, `guaranteedStopLossOrderLevelRestriction`. **No static numeric values are published** — they are served per-account from `/v20/accounts/{id}/instruments` (authenticated).
- **Enum-shape correction — important if ACIS models these.** There is **no `PRICE_BOUND_EXCEEDED`** anywhere in the v20 spec. The fill-time bound breach is **`OrderCancelReason.BOUNDS_VIOLATION`** — "Filling the Order would have violated the Order's price bound." `MARKET_HALTED`, `INSUFFICIENT_LIQUIDITY` and `FIFO_VIOLATION` are all **`OrderCancelReason`**, not `TransactionRejectReason`; the latter (≈198 values) carries pre-trade validation reasons such as `PRICE_BOUND_INVALID`, `PRICE_BOUND_PRECISION_EXCEEDED`, `UNITS_MINIMUM_NOT_MET`, `UNITS_LIMIT_EXCEEDED`, `INSTRUMENT_NOT_TRADEABLE`, `INSTRUMENT_PRICE_UNKNOWN`, `INSUFFICIENT_MARGIN`, `TIME_IN_FORCE_GTD_TIMESTAMP_IN_PAST`. Other `OrderCancelReason` values worth handling: `INSTRUMENT_BID_HALTED`, `INSTRUMENT_ASK_HALTED` (one-sided halts), `INSTRUMENT_BID_REDUCE_ONLY`, `INSTRUMENT_ASK_REDUCE_ONLY`, `FIFO_VIOLATION_SAFEGUARD_VIOLATION`, `FIFO_VIOLATION_SAFEGUARD_PARTIAL_CLOSE_VIOLATION`, `POSITION_SIZE_EXCEEDED`, `ACCOUNT_POSITION_VALUE_LIMIT_EXCEEDED`, `TIME_IN_FORCE_EXPIRED`, `LINKED_TRADE_CLOSED`, `HEDGING_GSLO_VIOLATION`, `OPEN_TRADES_ALLOWED_EXCEEDED`, `PENDING_ORDERS_ALLOWED_EXCEEDED`, `POSITION_CLOSEOUT_FAILED`, `MIGRATION`, `CLIENT_REQUEST`.
- **Two verbatim typos in OANDA's own published docs — reproduce, do not silently "fix", when quoting for an audit trail:** `FIFO_VIOLATION` reads "Filling the Order would have resulted in a a FIFO violation." (double "a"); `INSUFFICIENT_LIQUIDITY` reads "Filling the Order wasn't possible because enough liquidity available." (missing "not").
- API pacing guidance: new connections "we recommend you limit this to twice per second (2/s)"; established connections "one hundred per second (100/s)"; persistent connections recommended because they "reduce latency by avoiding repeated TCP handshaking"; on account state, AccountState updates are "likely to be frequent as **prices can change more than once a second**." — **Note the asymmetry: Dukascopy tick files can carry many ticks per second; the live client stream is aggregated. A backtest that reacts to intra-second tick detail is reacting to information the live system will never receive.**

### OANDA's own published spreads
Two OANDA-primary sources, which disagree slightly (marketing page vs live API).

*Marketing "typical spreads"* — https://www.oanda.com/us-en/trading/our-pricing/ : EUR/USD 1.4, GBP/USD 2.0, USD/JPY 1.4, AUD/USD 1.4, USD/CHF 1.8, USD/CAD 2.2, NZD/USD 1.7 pips. (FX-only table; **no metals row**.)

*Live time-weighted averages* from the API backing https://www.oanda.com/us-en/trading/spreads-margin/ — `labs-api.oanda.com/v1/spreads/spread-stability-and-average?division=OC&locale=en&instrument=<PAIR>`, pulled 2026-09-16:

| Pair | 50%-of-time | 80%-of-time | Avg 24h (1mo) | Avg business hrs (1mo) | Avg 24h (3mo) |
|---|---|---|---|---|---|
| EUR/USD | 1.6 | 1.6 | 1.6505 | 1.5578 | 1.6960 |
| GBP/USD | 1.8 | 2.0 | 2.1984 | 1.8288 | 2.2715 |
| USD/JPY | 1.5 | 1.6 | 1.6899 | 1.5166 | 1.7213 |
| AUD/USD | 1.3 | 1.3 | 1.5034 | 1.3162 | 1.4857 |
| USD/CHF | 1.6 | 1.7 | 1.8930 | 1.5890 | 1.9211 |
| USD/CAD | 1.8 | 1.8 | 1.9989 | 1.7660 | 2.0786 |
| NZD/USD | 2.4 | 2.4 | 2.5707 | 2.3579 | 2.6056 |
| **XAU/USD** ("Gold") | 56.1 | 63.2 | 57.1015 | 56.4535 | 61.4819 |

XAU/USD three-month detail: stability50 60.3, stability80 68.1, avg24h 61.4819, avgBusinessHours 60.6035.
**XAU/USD unit is unlabelled in the JSON.** Given OANDA's `pipLocation` for XAU/USD is −2 and the FX pairs from the same endpoint return values matching known pip spreads, 56.45 ≈ **$0.565**. [BROKER-PRIMARY, **unit inferred** — confirm against a practice account's instrument definition before hard-coding.]

Methodology, quoted from OANDA's own page config: "The average spread is calculated as a **time-weighted** 'mean' (average) of our quoted spread for the last month and last three months. We break this down into two periods, '24 hours' and 'excluding 5 pm to 7 pm Eastern,' because spreads during this time are generally wider coming up to the close of the U.S. trading day." Footnote: "**Time-weighted** refers to the time a spread was displayed rather than using the number of prices published with a given spread." And: "The quoted spread was at the value stated, or better, **50% and 80% of the time** during open trading hours."

**Core Pricing commission (US):** "Enjoy our lowest spreads and commissions of only **$0.70 per 10,000 units traded**, when you deposit $10K or more and sign up." → **$70 per million units per side**. — https://join.oanda.com/us-en/core-spreads-new-clients/ . From the pricing page: "Commission charges are assessed on the buy and sell sides of a trade. Trade sizes greater or smaller than 100,000 will be charged on a pro-rata basis. The minimum commission of is $0.01 per trade." [sic — grammatically broken in OANDA's own copy] and "Earn cash rebates from US$5 to US$17 per million with our Elite Trader program" (a rebate tier on top of, not instead of, the base commission).

### Translating to bps of notional — the decisive table
[DERIVED. OANDA spreads are broker-primary; **the Dukascopy 0.35-pip figure is a PLACEHOLDER that must be replaced with a measurement from the 2.79 B ticks**, per instrument and per session bucket. Quote prices assumed: EURUSD 1.08, GBPUSD 1.27, USDJPY 150, AUDUSD 0.66, USDCHF 0.88, USDCAD 1.37, NZDUSD 0.60. "Round trip" = open + close, i.e. one full spread.]

| Pair | OANDA avg (business hrs) | = bps per round trip | Dukascopy @ ~0.35 pip | **Un-modelled gap, bps/round trip** |
|---|---|---|---|---|
| EUR/USD | 1.56 pips | 1.44 | 0.32 | **1.12** |
| GBP/USD | 1.83 | 1.44 | 0.28 | **1.16** |
| USD/JPY | 1.52 | 1.01 | 0.23 | **0.78** |
| AUD/USD | 1.32 | 1.99 | 0.53 | **1.46** |
| USD/CHF | 1.59 | 1.81 | 0.40 | **1.41** |
| USD/CAD | 1.77 | 1.29 | 0.26 | **1.03** |
| NZD/USD | 2.36 | 3.93 | 0.58 | **3.35** |
| XAU/USD | $0.565 | 1.25–2.26 (gold $4500→$2500) | ~0.7–1.2 | **~0.5–1.1** |

Note that the low-priced pairs (NZD/USD, AUD/USD, USD/CHF) are the worst offenders in bps terms, because a pip is worth proportionally more.

At **500 round trips/year** this is **~4–11% of notional per year** of cost the backtest never charges (NZD/USD ~17%). At **2000 round trips/year**, 20–45%. **For a strategy with 30 min–48 h holds, this is almost certainly larger than its entire gross edge. Nothing else in this document matters as much.**

### Execution statistics, size limits, RTS 27/28, enforcement
- **No standing OANDA fill-statistics disclosure exists** — no "% of orders filled at requested price", no average execution speed in ms — on the US, UK or EU legal pages. [BROKER-PRIMARY negative result; treat as "does not exist", not "not found".] The closest analogues are (a) the UK policy's spread-stability metric (a *price*-stability statistic, not a fill-rate or latency statistic), and (b) the US on-request Trade Execution Report below.
- ⭐ **A per-trade audit right worth using from day one:** "On request, OANDA will generate a **Trade Execution Report** of all the transactions OANDA executed, in the same currency pair, in the **15 minute windows before and after** execution of the customer's transaction. The report will contain up to **15 transactions from each time period**." — https://www.oanda.com/us-en/legal/ (the report itself is gated at hub.oanda.com/documents/execution-report, login required). **This is a purpose-built instrument for the standing operational-referent audit (CLAUDE.md guard 3 / GAP-0001):** it compares a modelled fill against the *distribution of OANDA's own contemporaneous fills*, on demand, rather than reverse-engineering it from logs.
- **No live RTS 27/28 reports** from any OANDA entity — consistent with ESMA suspending the RTS 27 quarterly obligation from 2021 and the FCA removing the equivalent post-Brexit. The May 2026 OEL policy does not mention RTS 27/28 at all, only "FCA Consumer Duty". Historical 2018–2021 PDFs [NOT REACHED — web.archive.org CDX API returned 503]. Retry: `http://web.archive.org/cdx/search/cdx?url=oanda.com*&filter=urlkey:.*rts.*`
- **Minimum / maximum trade size: no published numeric table.** The fields exist in the v20 `Instrument` schema and the reject reasons `UNITS_MINIMUM_NOT_MET` / `UNITS_LIMIT_EXCEEDED` exist, but values are served per-account from an authenticated endpoint. **The widely repeated "OANDA lets you trade 1 unit" claim could not be confirmed against a primary source** — pull the real values from a practice account and pin them in config rather than citing folklore.
- **CFTC action against OANDA (2020)** — https://www.cftc.gov/PressRoom/PressReleases/8224-20 [REGULATORY]: "CFTC Orders Toronto-Based Firm to Pay $500,000 for Violating Capital, Reporting, and Supervision Rules". "OANDA failed to meet net capital requirements from **April 26, 2019 to August 21, 2019** and made dividend payments on October 15, 2018, April 26, 2019, and May 28, 2019 in violation of the equity withdrawal restriction." The order "notes that the Division of Enforcement found **no indication that customers suffered losses** as a result of the firm's net capital and equity withdrawal restriction violations." **This is a capital/supervision matter, not an execution-quality matter** — relevant to counterparty soundness, not to fill modelling. NFA ID 0325821.

---

## 6. PARTIAL FILLS, REJECTS, REQUOTES AT RETAIL SIZE

### Partial fills at $10k–$500k: essentially zero probability at OANDA
Two independent primary confirmations:
1. **OEL Order Execution Policy, Annex 1:** FX & Metals market orders are **Market FOK** — "There are no partial fills of the order. The order is rejected/cancelled in the case where the order size exceeds available liquidity."
2. **US Customer Agreement §11(e):** the Special Handling threshold is **$100,000,000 in 10 seconds** for major pairs ($30m for other instruments). The largest ACIS order is **0.5% of that threshold** — two and a half orders of magnitude below the size at which OANDA charges the VWAP of its hedge.

**→ Model fills as all-or-nothing at a single price. Do not build a ladder / VWAP walk. Do model rejection.** A ladder walk would be over-delivery against a non-existent problem (SPEC §17 non-goals, §18 lean-build), while un-modelled rejects are a real omission.

### Measured reject and slippage distributions
**IG Group "Best execution", reporting period April–June 2024** — https://www.ig.com/uk/about-us/best-execution [BROKER-PRIMARY]. The most granular retail dataset reached in this pass.
- "**98.97% of orders filled**" (→ **~1.03% non-fill rate**), with rejections attributed to "market dynamics and erroneous/excessive orders"
- "**100% of successfully filled orders executed at requested price or better**"
- "Over **263,000** of IG Group's at-quote orders received a price improvement," worth "**£3.5 million** in total client benefit", across "**31.5 million trades filled**" and "£2.3 trillion in notional flow per quarter"
- **Currencies overall: stops — 89% zero slippage, 11% negative slippage; limits — 55% positive slippage, 45% zero slippage**

| Instrument | stops 0 | stops − | limits + | limits 0 | avg neg (pips) | avg pos (pips) |
|---|---|---|---|---|---|---|
| EUR/USD | 93% | 7% | 49% | 51% | 0.053 | 0.086 |
| GBP/USD | 88% | 12% | 57% | 43% | 0.062 | 0.083 |
| USD/JPY | 87% | 13% | 59% | 41% | 0.097 | 0.107 |
| AUD/USD | 96% | 4% | 43% | 57% | 0.090 | 0.083 |
| USD/CAD | 93% | 7% | 53% | 47% | 0.005 | 0.009 |

Indices for contrast, showing how much instrument class matters: **Indices overall — stops 72% zero / 28% negative; limits 74% positive / 26% zero.** US 500 stops 76%/24%, avg neg 0.140; Wall Street 67%/33%, avg neg 0.184; Germany 40 92%/8%, avg neg 0.128; FTSE 100 95%/5%, avg neg 0.013; Australia 200 82%/18%, avg neg 0.034. **(No XAU/gold row is published.)**

**Pepperstone:** "Receive a **99.32%** fill rate, with no dealer intervention," footnoted "Fill rates are based on all trades data between 01/01/2026 and 31/03/2026." — https://pepperstone.com/ [BROKER-PRIMARY]

**How to read IG's numbers — they are easy to misread.** "100% at requested price or better" and "1.03% not filled" are the **same mechanism viewed twice**: the dealer never gives a worse price on an at-quote order — it declines the order instead. **The rejection rate IS the slippage.** That is the retail equivalent of last look, and it is why rejects must be modelled conditionally (§9, Rank 3).

Note also the *shape*: stops slip negatively only 4–13% of the time with a mean of ~0.05–0.10 pips; limits get positive slippage 43–59% of the time. **In normal conditions the distribution is not the problem; the tail is** (§7).

**Event-window reject and slippage rates: [NOT REACHED].** No broker or regulator publication reached breaks execution statistics out by news-release window. This is a genuine gap in the public record, and it is the regime that matters most for a system holding through NFP and central-bank releases. Make it a declared, stressed parameter rather than pretending to know it.

---

## 7. STOP-ORDER EXECUTION AND GAPS

### Server-side stop vs signal-driven market order
- A **server-side stop** rests on OANDA's own book. It has **zero signal-to-venue latency** (the trigger is evaluated at OANDA), but it **accepts whatever price exists when the trigger fires** — including a gap-through price. It fills "by the first price that is equal to or worse than the threshold."
- A **signal-driven market order** carries the full round-trip latency and can be rejected outright (§9(c): "no obligation to execute any Order (other than a Close Out Order)").
- **The asymmetry to encode: server-side stops fill in states where a market order would be rejected, and they fill at prices no quote ever showed you.** That is the opposite of how a naive backtest treats them — filling a stop *at* the stop price is the single most optimistic assumption in a backtest engine.
- ⚠️ Repeating the API trap because it is load-bearing: **a `StopOrder` carrying a `priceBound` is cancelled, not filled, if the market gaps through both.**
- OANDA offers **Guaranteed Stop Loss Orders** in some jurisdictions (`guaranteedExecutionPremium` / `guaranteedStopLossOrderExecutionPremium`, charged "in price units… for each unit of the Trade", with a `guaranteedStopLossOrderLevelRestriction`). GSLO is not available to US retail. **The premium is the market's price for removing gap risk** and would be a clean way to bound the tail if the account jurisdiction supports it.

### Tail evidence — the 2015 CHF de-peg
**FCA CP18/38, para 3.47** — https://www.fca.org.uk/publication/consultation/cp18-38.pdf [REGULATORY]:
> "This happened when the Swiss National Bank ceased pegging the Swiss Franc to the Euro, which resulted in a sudden and significant change in the value of the Swiss Franc and large losses for consumers. For example, German regulator Bundesanstalt für Finanzdienstleistungsaufsicht (BaFin) reported that **one client lost €280,000 from an initial investment of €28,000**, during the Swiss Franc event. **A UK retail client lost £2.7mn from a £200,000 initial investment.**"

**That is 10× and 13.5× the initial stake, through stops, in a single event.** The existing GAP-0108 treatment (CHF gap −35%, ceilings raised to 7.5% after proven equity-floor survival) is the right shape; these regulator-reported client outcomes are the calibration target for whether the equity floor survives a stop that does not stop.

Same CP18/38, wider retail-CFD context: "an estimated **78%** of active retail client accounts were loss-making… Retail consumers lost **£268.4mn** from trading over a 3-month period from August to October 2017, equal to a projected loss of **£1.07bn a year**" (weighted average of the risk warnings published by 7 firms representing c. 65% of the UK retail CFD market). Negative-balance-protection debt forgiven Aug–Oct 2018: **£1.45mn** across 63 firms (>90% of the UK market), scaled to "an annual ongoing benefit… of **£6.4mn**". FCA's per-firm loss-making-account chart spans roughly **35%–87%** (labels did not survive PDF extraction — do not attribute percentages to named firms).

Broker-level consequences of 15 January 2015 [UNVERIFIABLE-tertiary — https://en.wikipedia.org/wiki/FXCM , https://en.wikipedia.org/wiki/Swiss_franc]: the franc "surged roughly **30%** against the euro within minutes before partially reversing. By day's end… approximately **23%** versus the euro and 21% against the U.S. dollar"; FXCM "lost **$225 million** and was in breach of regulatory capital requirements", took **$300 million** of Leucadia financing at 10% rising "as high as 17%", and forgave "**90%** of its accounts that incurred negative balances"; Alpari UK "temporarily declared insolvency"; Saxo Bank "reported significant losses"; Global Brokers NZ "ceased operations." **The counterparty-failure mode belongs in the risk model alongside the price gap: the broker can fail in the same event that triggers the stop.**

### Sunday-open gaps, EUR/USD and XAU/USD, 2012–2025
**[NOT REACHED]** — no published quantitative study, broker or academic, of the Friday-close/Sunday-open gap distribution for these instruments. IG's weekend-trading page is qualitative only: "As the only provider of weekend trading, we do not have access to real-time data of underlying asset prices during weekend trading hours. However, we base prices on underlying market conditions such as volatility, as well as client activity and news flow…"

**No published study is needed.** The repository holds 2.79 B verified ticks across 8 instruments for 2012–2025 — roughly **700 weekend transitions per instrument**. Measure the last tick before Friday close against the first tick after Sunday open, per instrument, in bps of **mid**; report mean, p50, p90, p99, max, and the distribution conditional on the preceding week's realised volatility. This is a short computation that produces a **better** number than anything published, on data already paid for, and the DST-correct FX clock work (GAP-P12D-07 / P12D-10) makes the session boundaries trustworthy. **One caution:** the Dukascopy post-weekend spread widening documented in §2 means the first post-open ticks are venue-specific — measure the gap on mid and measure spread decay separately.

---

## 8. THE BID/ASK-AT-SIGNAL PROBLEM (LATENCY)

### The contract settles the model
OANDA US Customer Agreement §9(c) and OEL §11.1 both define the fill as the price prevailing **at OANDA's server on receipt of the order**. So the correct model is unambiguous and is not a modelling preference:

> **Fill at the price prevailing at `t_signal + Δ_latency`, on OANDA's book — not at the price at `t_signal`, and not on Dukascopy's book.**

### Realistic Δ for a retail API client
No broker publishes it. Physical bounds from Oomen (2017) [ACADEMIC]: microseconds within a datacentre, sub-ms within a city, ~10 ms Chicago–NY, ~30 ms NY–London, >100 ms London–Asia-Pacific. For a retail REST/streaming client the total is dominated by TLS/HTTP round trips and the client's own decision loop, not by physics. A realistic band [DERIVED / practitioner-plausible, **not primary**]:
- **VPS in the same region as the OANDA endpoint: 20–80 ms** signal-to-ack.
- **VPS in a different region: 100–300 ms.**
- **Plus the in-process component** — bar close → decision → serialise → send. Given the measured ~26 ticks/s engine throughput (GAP-P12D-12), this is not negligible and should be **measured directly** rather than assumed.
- OANDA's own guidance to use persistent connections exists precisely because of this: they "reduce latency by avoiding repeated TCP handshaking."

### How far does EUR/USD move in that window?
[DERIVED — √t scaling of a driftless diffusion. Sanity check: σ_ann = 7.5% reproduces ~1.3 pips of 1-minute σ and ~50 pips of daily σ, both consistent with observed EUR/USD behaviour. Values shown as **bps / pips**.]

| Window | σ_ann = 6% | σ_ann = 7.5% | σ_ann = 10% |
|---|---|---|---|
| 50 ms | 0.028 / 0.031 | 0.035 / 0.038 | 0.047 / 0.051 |
| 100 ms | 0.040 / 0.043 | 0.050 / 0.054 | 0.067 / 0.072 |
| 250 ms | 0.063 / 0.068 | 0.079 / 0.085 | 0.105 / 0.114 |
| 500 ms | 0.090 / 0.097 | 0.112 / 0.121 | 0.149 / 0.161 |
| 1 s | 0.127 / 0.137 | 0.158 / 0.171 | 0.211 / 0.228 |
| 5 s | 0.283 / 0.306 | 0.354 / 0.382 | 0.472 / 0.510 |
| 60 s | 0.98 / 1.06 | 1.23 / 1.32 | 1.63 / 1.77 |

**At 100 ms the unconditional diffusive move in EUR/USD is ~0.05 bps — about 3% of the 1.44 bps paid in spread. Pure latency is a third-order term for this system.**

**Three caveats that keep it from being zero:**
1. **Regime.** These are unconditional. Around NFP/FOMC, instantaneous volatility runs 10–50× the average, putting the 100 ms σ at **0.5–2.5 bps** — comparable to the whole spread. Condition the latency model on realised volatility, not on a constant.
2. **Adverse selection.** Conditional on the signal firing, the move over the latency window is **not** zero-mean. Oomen measures exactly this asymmetry in the aggregation setting (60/40 against the winning LP). The sign of the conditional drift is a property of *this* strategy and is **measurable directly from the ticks already on disk**: for each historical entry, compute the mid change from t to t+Δ for Δ ∈ {50, 100, 250, 500} ms and examine the **mean**, not just the σ. A non-zero mean is an adverse-selection tax the backtest never charges.
3. **Feed asymmetry.** The backtest sees every Dukascopy tick; live, the system sees an aggregated OANDA client stream where "prices can change more than once a second." A backtest that can act on a tick the live feed never delivers is a **look-ahead**, not a latency question. Given the existing look-ahead canary work (GAP-P12D-28), a natural extension is a canary that fails if any decision depends on intra-bar tick detail finer than the live feed's realistic resolution.

---

## 9. MODELLING CHANGES, RANKED

Ranked by (gap closed) × (confidence in the evidence) ÷ (implementation cost). The brief's proposed changes (a)–(f) are folded into this ordering; two additions are marked *(new)*.

### Rank 1 — Replace the data's spread with the destination broker's spread *(new; subsumes the brief's (f))*
**What:** stop treating the Dukascopy quote pair as the tradeable spread. Use Dukascopy's **mid** as the reference price and synthesise the spread from an OANDA-calibrated model: `spread(instrument, session, realised_vol)`. Anchor the level on OANDA's published time-weighted averages (§5) and the shape on the repository's own tick data.
**Evidence:** OANDA's own time-weighted averages (1.32–2.36 pips business-hours on the seven majors; ~$0.565 on gold) vs Dukascopy "from 0.1"; plus OANDA's written statement that its prices "MIGHT NOT BE THE BEST PRICES AVAILABLE" and are "an average of the pricing, excluding outliers" from third parties at Normal Market Size. [BROKER-PRIMARY on both sides]
**Gap closed: 60–80% of the total** — ~1.0–3.4 bps per round trip, which at any realistic turnover dominates everything else combined.
**Cost:** low. One function, one calibration table, one regression test per instrument.
**Sequencing note:** this is also the change most likely to **invalidate current OOS results**, which is exactly why it belongs *before* any paid walk-forward run rather than after.

### Rank 2 — Fill stops at the worse of the stop price and the next traded price (gap-through) *(brief's (e))*
**What:** a stop fills at `worse(stop_price, next_price_after_trigger)`. Never at the stop price when the market gapped.
**Evidence:** v20 `StopLossOrder` — "will be filled (closing the Trade) by the first price that is equal to or **worse** than the threshold" [BROKER-PRIMARY]; OEL §12.1 warns of "execution at a substantially different price from the quoted bid or ask"; FCA CP18/38's 10×- and 13.5×-stake CHF client losses show the tail is not theoretical [REGULATORY].
**Gap closed: ~10% of expected value, but most of the tail risk.** This is the change that determines whether the equity floor is real.
**Cost:** low. Also required alongside it: (i) trigger on the correct side (bid for long exits, per the v20 default); (ii) a test for the `BOUNDS_VIOLATION` case where a bounded stop is **cancelled** rather than filled; (iii) a weekend-gap replay using the measured gap distribution from §7.

### Rank 3 — Model rejects, and make them adversely selected *(brief's (d), corrected)*
**What:** not `P(reject) = p`. Instead: reject when the price has moved *in your favour* by more than a tolerance δ between `t_signal` and `t_signal + Δ`. That reproduces the real mechanism.
**Evidence:** Cartea/Jaimungal/Walton — "the most profitable trades executed by the ST are cancelled" [ACADEMIC]; Oomen's reject rates as a function of tolerance (28.5%/14.1% at δ=½; 8.1%/2.9% at δ=1) [ACADEMIC]; XTX's default zero-tolerance symmetric check [BROKER-PRIMARY]; IG's structure — "100% at requested price or better" *and* 1.03% unfilled — is the same mechanism at retail [BROKER-PRIMARY]; FXCM's $8.26m / 57,000-customer order is what it looks like when the asymmetry sits on the *price* rather than the *accept* decision [REGULATORY].
**Calibration:** IG's 1.03% overall non-fill and Pepperstone's 0.68% are the retail anchors for normal conditions. There is no public event-window figure, so make the event-window rate a **declared parameter** and stress it (5–15%).
**Gap closed: ~5–10% of expected value in normal conditions; considerably more in stress.** Crucially, **an unconditional `p` closes none of the gap and can make the backtest look better** — it must be conditional to be worth implementing.
**Cost:** moderate. Note that rejecting the trade is only half of it: the system must then decide whether to re-send (paying a worse price) or skip. That is a SPEC §5 conflict-table question, not an execution-model detail.

### Rank 4 — Add a latency delay Δ before taking the fill price *(brief's (b); subsumes (a))*
**What:** the fill price is the prevailing quote at `t_signal + Δ`, with Δ drawn from a measured distribution (a fixed Δ is an acceptable first cut).
**Evidence:** OANDA US CA §9(c) and OEL §11.1 both define the fill as the price at their server on receipt — **this is not a modelling choice, it is the contract.** [BROKER-PRIMARY]
**Gap closed: 2–5% of expected value at 100 ms in normal regimes** (per §8), more if Δ is realistically 200–500 ms, and much more in event windows.
**Cost:** low. **Do it despite the small EV**, because it is the change that makes the look-ahead structurally impossible; the bug class it forecloses matters more than the EV it removes.
**On the brief's (a):** "fill at the next tick's opposite side" is a crude Δ ≈ one-tick-interval. Prefer an explicit **time** delay — tick intervals vary by orders of magnitude between the London open and Sunday night, so "next tick" silently makes Δ *small when volatility is high*, which is exactly backwards.

### Rank 5 — Draw residual slippage from a fat-tailed distribution conditioned on realised volatility *(brief's (c))*
**What:** residual slippage beyond the spread and the latency drift, drawn from a heavy-tailed law scaled by realised volatility.
**Evidence:** IG's per-instrument distributions give the *normal-conditions* shape (stops slip negatively 4–13% of the time, mean 0.005–0.097 pips; limits get positive slippage 43–59% of the time). Symmetric in principle (OEL §11.2: "Positive and negative slippage are handled with strict symmetry"). The tail comes from OEL/CA §9(e) ("no limit to how wide the Spread may be") and the CHF evidence. [BROKER-PRIMARY + REGULATORY]
**Gap closed: ~3–5% of expected value; more of the variance.** With Ranks 1, 2 and 4 in place, much of what is casually called "slippage" is already accounted for — **do not double-count.**
**Cost:** moderate, and this is the change most likely to degenerate into an unfalsifiable fudge factor. **Tie its parameters to the IG table (public and dated) so the assumption is auditable**, and record the citation in `declared_deviations`.

### Rank 6 — Do NOT model a liquidity ladder / VWAP walk at this size *(new)*
**Evidence:** OANDA fills FX/Metals market orders **FOK** ("There are no partial fills of the order"), and its own Special Handling threshold is **$100,000,000 in 10 seconds** — 200× the largest ACIS order. [BROKER-PRIMARY]
**Gap closed: zero — that is the point.** Recording this as an explicitly **rejected** modelling change is worth more than implementing it: it prevents a future audit raising it as a gap, and it is the §17/§18 lean-build answer.

### Rank 7 — Feed-resolution parity canary *(new)*
**What:** assert that no decision depends on tick detail finer than the live feed delivers.
**Evidence:** OANDA's own note that "prices can change more than once a second" for a client feed, against Dukascopy tick files that carry far more. [BROKER-PRIMARY]
**Gap closed:** not EV — it closes a **look-ahead class**. Natural extension of the GAP-P12D-28 canary work.

### Rank 8 — Wire the live-vs-modelled comparison from day one *(new; the one that makes all the others honest)*
**What:** from the first live fill, for a sample of trades, request OANDA's **Trade Execution Report** (all OANDA transactions in the same pair in the 15 minutes before and after the fill, up to 15 each side) and compare the modelled fill against the realised one **and** against OANDA's contemporaneous population.
**Evidence:** https://www.oanda.com/us-en/legal/ [BROKER-PRIMARY]
**Why it ranks here:** every number in Ranks 1–5 is an estimate from someone else's data. This is the only mechanism in this document that measures **your** fills at **your** broker. It is precisely the standing operational-referent pass CLAUDE.md mandates, it feeds `OPERATIONS_LEDGER.md` directly, and it is available on request rather than needing to be reverse-engineered from logs.

---

## 10. ITEMS FOR OWNER TRIAGE INTO THE LEDGER

These are findings, not decisions. Per the ledger-closure law they need an ID and a status in `KNOWN_GAPS.md` / `TODO.md` / `OPERATIONS_LEDGER.md`, or they die with this document.

1. **Spread-source defect (Rank 1).** Backtest fills on Dukascopy quoted bid/ask under-charge ~1.0–3.4 bps per round trip versus OANDA's own published time-weighted averages. **Blocks any honest §14 grading**, and should be resolved before a paid walk-forward run.
2. **Stop `priceBound` cancellation trap.** A v20 `StopOrder` carrying a `priceBound` is *cancelled*, not filled, on a gap-through. Affects the GAP-0091b/0099/0075 work that threads `SizedOrder.stop_loss` to the venue stop. Needs both a code rule and a reconciliation path that detects a cancelled-not-filled stop.
3. **Stop trigger-side convention.** v20 defaults to bid-for-sell / ask-for-buy; the backtest must match or it under-counts stop hits.
4. **FIFO / jurisdiction constraint.** NFA 2-43(b) plus v20 `FIFO_VIOLATION` make same-instrument multi-position states unreachable on a US account. Must be an account-rule config, not a hard-coded assumption (ties to the GAP-P11I-02/10 per-account-universe remainders).
5. **Reject-reason enum shape.** `BOUNDS_VIOLATION`, `MARKET_HALTED`, `INSUFFICIENT_LIQUIDITY`, `FIFO_VIOLATION` are `OrderCancelReason`; `PRICE_BOUND_INVALID`, `UNITS_MINIMUM_NOT_MET`, `UNITS_LIMIT_EXCEEDED` are `TransactionRejectReason`. **There is no `PRICE_BOUND_EXCEEDED`.** Also handle `INSTRUMENT_BID_HALTED` / `INSTRUMENT_ASK_HALTED` (one-sided halts) as a `DataQualityError`-adjacent state.
6. **Counterparty/venue risk: automated-trading clause.** OANDA US CA §11(f)(iv) Event of Default covers "using any ultra-high speed trading or automated or mass data entry system", at sole discretion, without notice. `OPERATIONS_LEDGER.md` item **before the first live fill**, with a stated plan for a force-closed account.
7. **Documentation correction.** Any claim of a "2025 FX Global Code revision to last look / pre-hedging" is false: the 2024 review (published January 2025) amended P9, P10, P35, P50, P51 only; P17 was last confirmed unchanged in 2021.
8. **Two measurements from data already on disk** — both cheap, both replace unreachable public sources: **(a)** per-instrument top-of-book size distribution from the tick volume fields (median, p05), which also settles the "millions" unit question empirically; **(b)** per-instrument Friday-close → Sunday-open gap distribution across ~700 weekends, on **mid**, with spread decay measured separately.
9. **Operational-referent instrument identified.** OANDA's on-request Trade Execution Report (15-minute windows either side, up to 15 transactions each) is the purpose-built evidence source for the standing GAP-0001 live-vs-modelled fill comparison.

---

## 11. OPEN / UNVERIFIED — DO NOT LET THESE HARDEN INTO ASSUMED FACTS

- **Dukascopy volume units ("millions")** — attested by two practitioner forums quoting Dukascopy support; **not** stated in Dukascopy's own javadoc. Verify empirically before any feature depends on it.
- **XAU/USD spread unit** in OANDA's `labs-api` (56.45 = $0.5645 assumes `pipLocation` −2). Confirm against a practice account's instrument definition.
- **OANDA minimum / maximum trade size numerics** — not published; pull from `/v20/accounts/{id}/instruments`. The "1 unit minimum" claim is unconfirmed folklore.
- **Event-window reject and slippage rates** at any retail broker — no public source reached. Declare and stress instead.
- **Weekend-gap distributions** for EUR/USD and XAU/USD — no published study reached; compute from own data.
- **IOSCO's 2025 pre-hedging final report** — [NOT REACHED]. (The GFXC premise is settled: P11 and P17 were not amended in 2021 or 2024/25.)
- **NFA/CFTC actions against FXDD, Gain Capital, Interbank FX** — [NOT REACHED]; no docket numbers asserted here.
- **BIS Markets Committee reports** (sterling flash event 2016; FX execution algorithms 2020) — URL guesses 404'd.
- **OANDA historical RTS 27/28 (2018–2021)** — archive.org CDX returned 503; retry later.
- **CFTC/NFA docket numbers for the FXCM 2017 Effex / "no dealing desk" action** — the 2011 order is verified and captured above; the 2017 action is only secondary-sourced in this pass.
- **Third-party execution-quality pages** for CMC Markets, Saxo, Interactive Brokers, FOREX.com/GAIN and LMAX — 403/404 on every reachable URL. They may exist at current URLs not discoverable without search.

---

## 12. SOURCES

**Regulatory / official**
- CFTC order, Forex Capital Markets LLC, 3 Oct 2011 — https://www.cftc.gov/sites/default/files/idc/groups/public/@lrenforcementactions/documents/legalpleading/enffxcmorder10032011.pdf
- FCA Final Notice, FXCM Ltd & FXCM Securities Ltd, 24 Feb 2014 — http://dl.icdst.org/pdfs/files3/07e0f20234f7fd2708e195dc952e4738.pdf
- 17 CFR 5.18 — https://www.law.cornell.edu/cfr/text/17/5.18
- NFA Compliance Rule 2-43 — https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43
- CFTC Press Release 8224-20 (OANDA Corporation) — https://www.cftc.gov/PressRoom/PressReleases/8224-20
- FCA CP18/38 — https://www.fca.org.uk/publication/consultation/cp18-38.pdf
- FCA PS19/18 — https://www.fca.org.uk/publication/policy/ps19-18.pdf
- FCA Occasional Paper 50 — https://www.fca.org.uk/publication/occasional-papers/occasional-paper-50.pdf
- GFXC Execution Principles Working Group Report on Last Look, Aug 2021 — https://www.globalfxc.org/uploads/gfxc_report_last_look-1.pdf
- GFXC Outcomes of the Three-Year Review, Jan 2025 — https://www.globalfxc.org/uploads/gfxc_3year_review_outcomes_dec2024.pdf
- FX Global Code, Dec 2024 — https://www.globalfxc.org/uploads/fx_global.pdf

**Academic**
- Oomen, R. (2017), *Last look*, Quantitative Finance 17(7), 1057–1070 — https://researchonline.lse.ac.uk/id/eprint/68811/1/Oomen_Last%20look_2017.pdf
- Cartea, Á., Jaimungal, S. & Walton, J., *Foreign Exchange Markets with Last Look*, arXiv:1806.04460 — https://arxiv.org/abs/1806.04460

**Broker-primary**
- OANDA Additional Disclaimer (US), Dec 2025 — https://www.oanda.com/assets/documents/2003/OANDA_Additional_Disclaimer-2025.pdf
- OANDA US Customer Agreement, Mar 2026 — https://legal.oanda.com/?code=fxtrade_customer_agreement&language=en
- OANDA Europe Limited Order Execution Policy, May 2026 — https://legal.oanda.com/?code=execution_policy_oel&language=en
- OANDA US legal index (incl. Trade Execution Report) — https://www.oanda.com/us-en/legal/
- OANDA pricing — https://www.oanda.com/us-en/trading/our-pricing/
- OANDA Core Pricing offer — https://join.oanda.com/us-en/core-spreads-new-clients/
- OANDA spreads & margin — https://www.oanda.com/us-en/trading/spreads-margin/
- OANDA live spread API — https://labs-api.oanda.com/v1/spreads/spread-stability-and-average?division=OC&locale=en&instrument=EUR_USD
- OANDA v20 docs — https://developer.oanda.com/rest-live-v20/order-df/ · /transaction-df/ · /pricing-df/ · /primitives-df/ · /best-practices/
- XTX Markets eFX Disclosure Cover Sheet, 18 Sep 2025 — https://www.xtxmarkets.com/assets/disclosures/global-efx-cover-sheet.pdf
- XTX Markets eFX Trading Practices Disclosures — https://www.xtxmarkets.com/assets/disclosures/global-efx-trading-practices-disclosures.pdf
- IG Group Best Execution, Apr–Jun 2024 — https://www.ig.com/uk/about-us/best-execution
- Pepperstone — https://pepperstone.com/
- Dukascopy `ITick` javadoc — https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/ITick.html
- Dukascopy Forex Trading — https://www.dukascopy.com/swiss/english/forex/trading/
- Dukascopy Historical Data Export — https://www.dukascopy.com/swiss/english/marketwatch/historical/

**Practitioner / tertiary**
- EliteTrader, "Interpreting Dukascopy Tick Data" — https://www.elitetrader.com/et/threads/interpreting-dukascopy-tick-data.352792/
- mayeranalytics/bi5 — https://github.com/mayeranalytics/bi5
- Wikipedia: Dukascopy Bank · FXCM · Swiss franc
