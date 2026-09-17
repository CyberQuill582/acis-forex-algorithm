# PARTIAL — Execution-fidelity research: Dukascopy tick backtest vs live OANDA retail execution

**What this is / who asked:** A research subagent was asked (by the ACIS coordinator session, 2026-09-16) to research, with web search and primary sources, the fidelity gap between (a) backtesting on Dukascopy tick bid/ask with a fill at the order price plus a small declared friction, and (b) live retail FX/spot-gold execution at a retail broker like OANDA — for a system trading 7 FX majors + spot gold, 1-minute bars from tick data, 30 min–48 h holds, $10k–$500k notional per order. Eight required topics: Dukascopy data fidelity; MM vs ECN/STP; last look; OANDA specifics; partial fills/rejects/requotes; stop-order execution and gaps; the bid/ask-at-signal latency problem; and ranked modelling changes.

**Status:** Research COMPLETE. The full report was delivered to the coordinator via SubagentHandback. This file is a disk checkpoint of the findings so a fresh session can resume without re-fetching. **Nothing in the repo was modified except this file. Nothing was committed. No engine code, config, spec or ledger file was touched.**

**Tooling constraint that shaped the work:** the session's WebSearch budget was already exhausted (200/200) before this task began. Every source below was reached by direct WebFetch against a primary URL (plus local `pypdf` text extraction for PDFs). Bing/DuckDuckGo/Mojeek/Startpage/archive.org were all captcha-gated, 403, or returned unrelated cached content. "NOT REACHED" below therefore means "tooling gap", not "does not exist".

---

## 1. HEADLINE CONCLUSION

Ranked by size of the fidelity gap for this system:

| # | Gap | Size | Confidence |
|---|---|---|---|
| 1 | **Spread level.** Dukascopy SWFX is a real ECN; OANDA is a principal market maker that sets its own prices. OANDA's own time-weighted average spreads are ~1.3–2.4 pips on majors. | **≈0.8–3.4 bps per round trip** | BROKER-PRIMARY, high |
| 2 | **Wrong venue entirely.** OANDA states its prices "MIGHT NOT BE THE BEST PRICES AVAILABLE" and makes no warranty they "represent exchange rates available elsewhere in the market." | structural | BROKER-PRIMARY, certain |
| 3 | **Stop fills / gap-through**, incl. the `priceBound` cancellation trap | tail risk, potentially unbounded | BROKER-PRIMARY, certain |
| 4 | **Rejects are adversely selected**, not random | 0.5–2 bps at retail; more in stress | ACADEMIC + BROKER-PRIMARY |
| 5 | **Latency** — the *smallest* term for 30 min–48 h holds | ~0.03–0.07 pips per 100 ms, normal regime | DERIVED |
| 6 | **Partial fills / size impact** — a non-issue at this size | ≈0 | BROKER-PRIMARY, certain |

**The single most important correction is not a slippage model.** Filling at the Dukascopy tick's own bid/ask systematically under-charges roughly 1.0–1.4 pips per round trip on EUR/USD-class pairs and up to ~3.4 bps on NZD/USD. No "small declared friction" fixes that unless it is calibrated to the *destination broker's* spread, not the *source data's* spread.

---

## 2. DUKASCOPY DATA FIDELITY

- SWFX = Dukascopy Bank's own ECN, launched 2006. FINMA-regulated as bank + securities dealer.
- Dukascopy trading page: "Large liquidity pool from 20+ banks"; "ECN"; "Transparent pricing - All clients have access to the same liquidity at equal prices through a single datafeed"; "eur/usd spread from 0.1"; leverage up to 1:200. — https://www.dukascopy.com/swiss/english/forex/trading/ [BROKER-PRIMARY]
- `ITick.getAsk()` = "Best ask price on the market"; `getAskVolume()` = "Volume available at the best ask price on the market". — https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/ITick.html [BROKER-PRIMARY]
- Dukascopy support, quoted on the record: "Ticks are quotes arriving in our system from our liquidity providers. They are neither orders nor trades. We reflect only best ask and bid available in our system." and "Volumes shown are volumes quoted on the best bid and ask levels. **This is not a guarantee that your trade will be executed at those prices.**" — https://www.elitetrader.com/et/threads/interpreting-dukascopy-tick-data.352792/ [CREDIBLE PRACTITIONER quoting broker support]
- **Volume units: millions of base currency** (a `bidVolume` of 1.5 = 1.5M). [CREDIBLE PRACTITIONER — two forums quoting Dukascopy support; NOT in the javadoc. VERIFY EMPIRICALLY.]
- bi5: 20-byte big-endian records — int32 ms-from-hour, int32 ask, int32 bid, float32 askVol, float32 bidVol; LZMA-compressed despite the extension; divisor 100,000 (1,000 for JPY pairs and CFDs). — https://github.com/mayeranalytics/bi5
- **No published Dukascopy statement that the historical feed is filtered/cleaned**; the Historical Data Export page carries no data-quality or execution disclaimer. [BROKER-PRIMARY negative result]
- Two artefacts [CREDIBLE PRACTITIONER, EliteTrader]:
  1. **Repeated-price ticks exist** — "Ticks can be with equal prices and reflected one-by-one on the tick chart and in the downloaded history." Tick counts are not a clean activity proxy.
  2. **Post-weekend/post-holiday spreads are Dukascopy-specific wide**: "spreads are quite a bit wider than other high quality fx aggregators. But that usually settles an hour into the session."
- Volume is quoted size, not traded volume. There is no consolidated FX tape.

**Top-of-book vs a $100k order:** if volume is in millions, EUR/USD top-of-book is routinely 1–5M, so $100k is ~2–10% of it — a rounding error. **But this is irrelevant to live fills**, because execution will not be on SWFX. It matters only for judging whether the quote series is a credible reference price.

**ACTION (cheap, uses data already on disk):** compute per-instrument distribution of `askVolume`/`bidVolume` (median, p05) over 2012–2025 from the 35,008 day files. Expect XAU/USD and NZD/USD to be the interesting cases.

---

## 3. REGULATORY EVIDENCE ON MARKET-MAKER EXECUTION (the best-evidenced section)

### CFTC v. Forex Capital Markets LLC, 3 Oct 2011 [REGULATORY — primary order]
https://www.cftc.gov/sites/default/files/idc/groups/public/@lrenforcementactions/documents/legalpleading/enffxcmorder10032011.pdf

> "if the price received by FXCM in its offsetting trade… was better than the bid/ask price at the time that FXCM received the order from the customer… then the customer still received the order at the original requested price and FXCM kept the difference"

> "for market orders during the relevant period, FXCM's customers were denied the benefit of any positive price slippage, but forced to bear the consequences of any negative slippage."

> "more than **57,000** of its customers were deprived of approximately **$8,261,937** in positive slippage (which amount FXCM retained) from **June 18, 2008 until December 17, 2010**"

> "the unequal treatment of price slippage… occurred **thousands of times a day across thousands of customer accounts for more than two years**"

Sanction: $6,000,000 penalty + $8,261,937 restitution (≈$14.2m).

### FCA Final Notice, FXCM Ltd & FXCM Securities Ltd, 24 Feb 2014 [REGULATORY — primary notice]
Mirror used: http://dl.icdst.org/pdfs/files3/07e0f20234f7fd2708e195dc952e4738.pdf (FCA's own URL 404'd)

**This one gives per-trade magnitudes — the most useful calibration anchor in the public record.**
- Period 1 Aug 2006 – 17 Dec 2010.
- "FXCM Group retained USD **$6,725,106** as profits from positive price improvements in **2,214,053 trades**" → **$3.04/trade**.
- "FXCM Group retained USD **$3,103,571** from positive price movements in **1,101,161 limit orders**" → **$2.82/limit order**. Limit orders were asymmetric differently: favourable moves pocketed, adverse moves "reset to a pending status and the customer losing the opportunity to have the order executed at that time."
- FXCM Securities: $113,293 over 24,709 trades = $4.59/trade.
- FCA mitigation para 2.5(2): "**The average slippage retained by FXCM Ltd on those trades where slippage was retained, a subset of all trades, was approximately $3.70.**"
- Penalty £4,000,000 combined; redress up to USD $9,941,970; ~75,000 active retail accounts at 17 Dec 2010.

**Interpretation:** pure dealer-side execution asymmetry cost roughly **$3–4 per affected trade** at retail ticket sizes — the same order of magnitude as an entire ECN spread.

### Rules now constraining this
- **17 CFR 5.18(f)(2)**: may not "Adjust or alter prices for a retail forex transaction after the transaction has been confirmed to the retail forex customer". **5.18(f)(3)**: bid/ask symmetry — may not "Provide a retail forex customer a new bid price… that is higher than its previous bid without providing a new asked price that is also higher". **5.18(f)(1)**: no materially different prices to different customers at the same time. — https://www.law.cornell.edu/cfr/text/17/5.18 [REGULATORY]
- **NFA Compliance Rule 2-43(a)**: no cancelling/adjusting an executed customer order to change pricing, except where "cancellation or adjustment is favorable to the customer and is done as part of a settlement of a customer complaint", or narrow STP/counterparty-adjustment conditions (15-minute notification; must adjust *all* customer orders in that pair in that window). **2-43(b)**: "may not carry offsetting positions in a customer account but must offset them on a first-in, first-out basis." Effective 15 May 2009, amended through 15 Sep 2022. — https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43 [REGULATORY]

**Consequences for ACIS:** (i) on a US OANDA account FIFO forbids independent same-instrument positions (v20 `FIFO_VIOLATION`); (ii) "no requotes" at a US RFED is a *regulatory* property, bought with a **rejection** right — the dealer refuses rather than reprices.

---

## 4. LAST LOOK

### FX Global Code Principle 17 (full text in Appendix A of https://www.globalfxc.org/uploads/gfxc_report_last_look-1.pdf) [industry/REGULATORY primary]
> "Last look is a practice utilised in Electronic Trading Activities whereby a Market Participant receiving a trade request has a final opportunity to accept or reject the request against its quoted price."

> "the Market Participant has sole discretion, based upon the validity and price check processes, over whether the Client's trade request is accepted or not, **leaving the Client with potential market risk in the event the trade request is not accepted**."

### CORRECTION TO A COMMON PREMISE — the "2025 revisions on last look and pre-hedging" do not exist
- **2021 (Three-Year Review, 15 Jul 2021):** "the GFXC agreed that the text of Principle 17 remains appropriate." **P17 was NOT amended.** Instead the Aug 2021 Execution Principles Working Group Report on Last Look was issued, explicitly "not part of the Code". Its hardest line: "LPs should apply the price and validity check **without delay**… **Incorporating any delay that is additional to what is required to complete the price and validity check is considered contrary to Principle 17.**" It also requires disclosure of symmetric vs asymmetric price checks and of the "Last Look window maximum and minimum length (in m/s)".
- **2024/2025 (published Jan 2025):** "The 2024 Code amendments focus on **five of the Code's fifty-five principles (P9, P10, P35, P50, and P51)**" — client-generated data on e-trading platforms, delegated execution where the provider is also Principal, FX settlement risk. — https://www.globalfxc.org/uploads/gfxc_3year_review_outcomes_dec2024.pdf
- **Neither P17 (last look) nor P11 (pre-hedging) was amended in 2021 or 2024/25.** Pre-hedging did move in 2025 — at **IOSCO**, not the GFXC. [IOSCO report NOT REACHED.]

### XTX Markets eFX Disclosure Cover Sheet, dated 18 Sep 2025 [BROKER-PRIMARY — best current named-firm datapoint]
https://www.xtxmarkets.com/assets/disclosures/global-efx-cover-sheet.pdf
> "The last look window, being the time between receipt of a trade request by XTX and submission by XTX of its acceptance or rejection decision to the client, typically (**99th percentile**) ranges from a minimum of **0 m/s** to a maximum of **1 m/s**."

> "XTX uses zero hold time. The last look checks are applied as soon as the trade request is received."

From https://www.xtxmarkets.com/assets/disclosures/global-efx-trading-practices-disclosures.pdf :
> "In respect of the price check, the standard setting is for the price check to be applied **symmetrically and without any tolerance applied i.e. if the price has moved at all, in either direction, the trade request will be rejected.**"

> "any trade request accepted by XTX shall be executed in its entirety. **There will be no partial fills of trade requests.**"

XTX also offers a **"No Last Look Stream"** (accepted regardless of price movement, subject to max size/risk limits) and states that tailoring produces "differences in pricing and **trade acceptance rates** between counterparties" — i.e. the market prices last-look-vs-firm as an explicit spread/certainty trade-off.

### Oomen (2017), *Last look*, Quantitative Finance 17(7) 1057–1070 [ACADEMIC]
https://researchonline.lse.ac.uk/id/eprint/68811/1/Oomen_Last%20look_2017.pdf
Baseline: N=15 LPs, ω=0.5, β=0.75, ρ=0.5, s=1, n=1, σ=0.5.
- "σα = 0.60 with a mean of −µα = −0.15. This implies that **the price is about 50% more likely to move over the latency buffer against the LP that wins the deal request than it is to move in its favour (i.e. 60% in trader's favour and 40% in LP's favour)**."
- δ⁻ = ½ → "it will reject **28.5%** of deal requests on that side"; two-sided δ⁺ = ½ → "another **14.1%** of deals will be rejected in the right-tail."
- δ⁻ = δ⁺ = 1 → "these figures reduce to **8.1%** and **2.9%** respectively."
- Adverse flow: break-even nominal spread "ranging between **1.65 and 2.55**".
- Indifference: at 20% reject for on-rate trading, one-sided last look "will reject **12.5%**" vs two-sided-with-rebates "**20%**" for the same effective spread.
- Latency context: "microseconds within the same data centre, sub-millisecond within the same city, around **10 milliseconds** between Chicago and New York, **30 milliseconds** between New York and London, and **over 100 milliseconds** between London and the Asia Pacific."
- **Central theorem:** last look design changes *execution risk*, while effective transaction cost can be held constant by adjusting the quoted spread. "No last look" is paid for in spread.

### Cartea, Jaimungal & Walton, *Foreign Exchange Markets with Last Look* (arXiv:1806.04460) [ACADEMIC]
Theoretical, no pip calibration. The load-bearing sentence:
> "with the Last Look option the costs of only accepted trades from STs is reduced to zero, but **the most profitable trades executed by the ST are cancelled**"

Plus the equilibrium result that a last-look venue can quote a *wider* spread than a firm venue once traders migrate.

### FCA Occasional Paper 50 (Aquilina, Budish & O'Neill, Jan 2020) [REGULATORY/ACADEMIC]
https://www.fca.org.uk/publication/occasional-papers/occasional-paper-50.pdf
- "The average FTSE 100 symbol has **537 latency-arbitrage races per day**. That is about one race per minute per symbol."
- "In the modal race, the winner beats the first loser by just **5-10 microseconds**."
- "about **22%** of daily trading volume is in latency-arbitrage races."
- "The average race is worth a bit more than half a tick, which on average comes to about **2 GBP**… Even at the 90th percentile… just 3 ticks and about **7 GBP**."
- "the 'latency-arbitrage tax'… is **0.42 basis points** if using total trading volume, and **0.53 basis points** if using only trading volume that takes place outside of latency-arbitrage races. **The average value-weighted effective spread paid in our data is just over 3 basis points.**… would reduce investors' cost of liquidity by **17%**."

**Use:** 0.4–0.5 bps is a defensible order-of-magnitude floor for the implicit last-look/latency cost to a slow taker in a *firm-quote* market. The FXCM $3–4/trade figures are the retail OTC analogue.

**KEY MODELLING POINT:** a reject is **not** a coin flip. It is conditioned on the price having moved *in your favour*. Modelling rejects as an unconditional probability is strictly wrong and **flatters** the backtest.

---

## 5. OANDA SPECIFICS (all BROKER-PRIMARY unless noted)

### Capacity — principal market maker, in writing
**OANDA Additional Disclaimer (US), Dec 2025** — https://www.oanda.com/assets/documents/2003/OANDA_Additional_Disclaimer-2025.pdf
> "THE FOREIGN CURRENCY TRADING YOU ARE ENTERING INTO IS NOT CONDUCTED ON AN EXCHANGE. OANDA IS ACTING AS A COUNTERPARTY IN THESE TRANSACTIONS AND, THEREFORE, ACTS AS THE BUYER WHEN YOU SELL AND THE SELLER WHEN YOU BUY. AS A RESULT, OANDA'S INTERESTS MAY BE IN CONFLICT WITH YOURS. UNLESS OTHERWISE SPECIFIED IN YOUR WRITTEN AGREEMENT OR OTHER WRITTEN DOCUMENTS, **OANDA ESTABLISHES THE PRICES AT WHICH IT OFFERS TO TRADE WITH YOU. THE PRICES OANDA OFFERS MIGHT NOT BE THE BEST PRICES AVAILABLE.**"

> "IF OANDA ELECTS NOT TO COVER ITS OWN TRADING EXPOSURE, THEN YOU SHOULD BE AWARE THAT OANDA MAY MAKE MORE MONEY IF THE MARKET GOES AGAINST YOU."

Revenue: "For most accounts, OANDA charges no commissions… and hence generates revenues from the spreads alone… you pay the equivalent of **half the spread, on average**, for each (opening or closing) trade."

**OANDA Europe Limited Order Execution Policy, May 2026** — https://legal.oanda.com/?code=execution_policy_oel&language=en
- §2.1 "We will act as **principal and not as your agent**… we therefore act as **the sole trading venue** for those Orders. This means you will be dealing directly with us and not with the wider market."
- §2.2 "We cannot guarantee, when executing an Order, that our price will always be better than a price which might have been available elsewhere."
- §3.1(c) "We are not obliged to accept your Order(s) and may therefore reject any Order(s)…"
- §5.1 "The prices shown to you are based on an **average of the pricing, excluding outliers**, available from those third parties. This average is our objective view of the bid and ask prices available to arms' length market participants in respect of transactions of a **Normal Market Size**…"
- §5.5 "OANDA group companies may seek to manage their risk as market maker and may choose to hedge… Accordingly, **this may impact the execution price of your Orders.**"
- §11.1 "All Orders are executed at the prevailing price(s) at the time the Order is processed **after receipt on our execution server**."
- §11.2 "The pricing and execution components of our Trading Platform **do not apply asymmetrical slippage parameters. Positive and negative slippage are handled with strict symmetry** to protect clients from foreseeable harm during execution gaps."
- §10.2 "If the requested Transaction exceeds limits that we have established for the relevant Product, you may not be able to place your Order."
- §14.1 "We will not aggregate your Trade(s) or Order(s) with those of any other client during execution."
- §12.1 risks NOT protected against: "(a) execution at a **substantially different price** from the quoted bid or ask… (b) delays in executing Orders… (c) **opening prices that may differ substantially from the previous day's closing prices**; and (d) Instrument market conditions, such as locked…, crossed…, **halted**, limit up…, limit down…, protected…, which may prevent the execution of client Orders."
- **Annex 1 (order-type table):** "**Market FOK** — A market order executed on an order execution venue at the most recent price appropriate for the quantity of the order. **There are no partial fills of the order. The order is rejected/cancelled in the case where the order size exceeds available liquidity.**" Used for FX & Metals and Indices & Commodities market orders. Only equity shares use Market IOC ("Partial fills are possible only in the case where the order size exceeds available liquidity"). Stop Entry/Stop Loss/Close Out route to "Market GTC Full" (an FOK leg); Limit/Take Profit to "Limit GTC Full". Unfilled remainder "returns to the pending state in the OANDA group order book."

**There is NO "no requotes, bounded slippage" guarantee in the legal documents.** The marketing phrase "policy of no re-quotes" appears only on the platform landing page (https://trade.oanda.com/). The real mechanism is: no requote, but they fill at their post-latency price **or reject**.

### US Customer Agreement, version March 2026 — https://legal.oanda.com/?code=fxtrade_customer_agreement&language=en
- Def. (x) "'**Market Order**' means an order to buy or sell a currency pair at the prevailing Exchange Rate. **Please note that prices displayed for Market Orders are indicative and not guaranteed.**"
- §9(b) "Each Exchange Rate is valid only on the exact date and at the exact time that such Exchange Rate is presented to you… in a rapidly changing market the Exchange Rate presented to you… may no longer remain in effect at the time your Order is executed at the OANDA Trading System server, and you agree that any Trade resulting from the execution of such Order shall be at the Exchange Rate in effect at the time such Order is executed on the OANDA Trading System server. **OANDA makes no warranty, express or implied, that the Exchange Rates represent exchange rates available elsewhere in the market.**"
- §9(c) "…at the prevailing Exchange Rate at the time such Order is **received at the OANDA Trading System server**. **OANDA will have no obligation to execute any Order** (other than a Close Out Order)…"
- §9(e) "Spreads may widen or narrow at any time at OANDA's sole discretion… **there is no limit to how wide the Spread may be.**"
- §9(g) may reject any Order or close positions without notice, incl. "(iv) in the event of any circumstances or developments that OANDA, **in its sole discretion**, deems necessary or advisable for its protection."
- §11(e) **Special Handling for Large Transactions**: "If a Transaction or series of Transactions occurs… **within a period of 10 seconds**, in either case with an aggregate notional value that exceeds **$100,000,000 USD equivalent in any major currency pair**… or **$30,000,000 USD equivalent in any other instrument**, then OANDA will execute your Trade(s) at the price shown… and subsequently may debit or credit your Account for the difference between the price shown… and an amount equal to **1.0-pip in excess of OANDA's actual volume-weighted cost of clearing such Trades.**" (Exhibit A worked examples use 40M USD/SEK and 125M EUR/USD.)
- "Invalid Price" = "an erroneous or otherwise incorrect Exchange Rate"; an Account Adjustment may result from "OANDA providing an Invalid Price quote" — the error-trade escape hatch.
- **§11(f) Event of Default (iv): "we reasonably believe you have acted in an unfair or abusive manner, for example, but not limited to, using any ultra-high speed trading or automated or mass data entry system".** ⚠️ ACIS is an autonomous automated system; this clause is broad enough to reach it, enforced at OANDA's sole discretion without notice. **Operational-ledger item before first live fill.**

### v20 API mechanics that change the fill model
Sources: https://developer.oanda.com/rest-live-v20/order-df/ , /transaction-df/ , /pricing-df/ , /primitives-df/ , /best-practices/
- **MarketOrder `timeInForce`: "Restricted to FOK or IOC for a MarketOrder", default `FOK`** → no partial fills; rejected instead.
- **`priceBound`: "The worst price that the client is willing to have the Market Order filled at."**
- ⚠️ **`StopOrder` + `priceBound`: "If the market gaps and crosses through both the price and the priceBound, the Stop Order will be *cancelled* instead of being filled."** A "protective" bound converts a bad fill into **no protection at all**.
- **`StopLossOrder`: "will be filled (closing the Trade) by the first price that is equal to or *worse* than the threshold."** → gap-through is passed to the client.
- Trigger condition selectable "based on the bid, ask, mid, default (ask for buy, bid for sell) or inverse (ask for sell, bid for buy)". **Backtest must match the live convention** or it under-counts stop hits.
- `OrderFillTransaction.fullVWAP`: "The price that all of the units of the OrderFill should have been filled at, in the absence of guaranteed price execution. This factors in the Account's current ClientPrice, used liquidity and the units of the OrderFill…" `fullPrice`: "The price in effect for the account at the time of the Order fill." The deprecated `price` field notes "the individual tradesClosed, tradeReduced and tradeOpened fields contain the exact/official price each unit was filled at."
- `PriceBucket`: "A PriceBucket represents a price available for an amount of liquidity" — `{price, liquidity}`. `ClientPrice` carries `bids`/`asks` arrays plus `closeoutBid`/`closeoutAsk` ("when a bid is required to closeout a Position… yet there is no bid liquidity") and a `tradeable` boolean.
- **Enum-shape correction (important if ACIS models these):** there is **NO `PRICE_BOUND_EXCEEDED`**. The fill-time bound breach is `OrderCancelReason.BOUNDS_VIOLATION` — "Filling the Order would have violated the Order's price bound." `MARKET_HALTED`, `INSUFFICIENT_LIQUIDITY`, `FIFO_VIOLATION` are all **`OrderCancelReason`**; `PRICE_BOUND_INVALID`, `UNITS_MINIMUM_NOT_MET`, `UNITS_LIMIT_EXCEEDED`, `INSTRUMENT_NOT_TRADEABLE` are **`TransactionRejectReason`** (198 values total). Also present in OrderCancelReason: `INSTRUMENT_BID_HALTED`, `INSTRUMENT_ASK_HALTED`, `INSTRUMENT_BID_REDUCE_ONLY`, `INSTRUMENT_ASK_REDUCE_ONLY`, `FIFO_VIOLATION_SAFEGUARD_VIOLATION`, `FIFO_VIOLATION_SAFEGUARD_PARTIAL_CLOSE_VIOLATION`, `POSITION_SIZE_EXCEEDED`, `TIME_IN_FORCE_EXPIRED`, `LINKED_TRADE_CLOSED`, `ACCOUNT_POSITION_VALUE_LIMIT_EXCEEDED`, `HEDGING_GSLO_VIOLATION`.
- **Two verbatim typos in OANDA's own docs — reproduce, do not silently fix, if quoting for an audit trail:** `FIFO_VIOLATION` reads "Filling the Order would have resulted in a a FIFO violation." (double "a"); `INSUFFICIENT_LIQUIDITY` reads "Filling the Order wasn't possible because enough liquidity available." (missing "not").
- `Instrument` schema has `minimumTradeSize`, `maximumOrderUnits`, `maximumPositionSize`, `tradeUnitsPrecision`, `displayPrecision`, `pipLocation`, `marginRate`, `guaranteedStopLossOrderMode`, `guaranteedStopLossOrderExecutionPremium`, `guaranteedStopLossOrderLevelRestriction` — but **no static numeric values are published**; they are served per-account from `/v20/accounts/{id}/instruments` (authenticated).
- API pacing: new connections "twice per second (2/s)", established "one hundred per second (100/s)"; on account state, "prices can change more than once a second." **Dukascopy tick files can carry many ticks/second; the live client feed is aggregated. A backtest reacting to intra-second tick detail is reacting to information the live system never receives.**

### OANDA's own published spreads
*Marketing "typical spreads" — https://www.oanda.com/us-en/trading/our-pricing/ :* EUR/USD 1.4, GBP/USD 2.0, USD/JPY 1.4, AUD/USD 1.4, USD/CHF 1.8, USD/CAD 2.2, NZD/USD 1.7 pips. (This table is FX-only — no metals row.)

*Live time-weighted averages, `labs-api.oanda.com/v1/spreads/spread-stability-and-average?division=OC&locale=en&instrument=<PAIR>`, pulled 2026-09-16:*

| Pair | 50%-of-time | 80%-of-time | Avg 24h (1mo) | Avg bus. hrs (1mo) | Avg 24h (3mo) |
|---|---|---|---|---|---|
| EUR/USD | 1.6 | 1.6 | 1.6505 | 1.5578 | 1.6960 |
| GBP/USD | 1.8 | 2.0 | 2.1984 | 1.8288 | 2.2715 |
| USD/JPY | 1.5 | 1.6 | 1.6899 | 1.5166 | 1.7213 |
| AUD/USD | 1.3 | 1.3 | 1.5034 | 1.3162 | 1.4857 |
| USD/CHF | 1.6 | 1.7 | 1.8930 | 1.5890 | 1.9211 |
| USD/CAD | 1.8 | 1.8 | 1.9989 | 1.7660 | 2.0786 |
| NZD/USD | 2.4 | 2.4 | 2.5707 | 2.3579 | 2.6056 |
| **XAU/USD** ("Gold") | 56.1 | 63.2 | 57.1015 | 56.4535 | 61.4819 |

XAU/USD 3-month detail: stability50 60.3, stability80 68.1, avg24h 61.4819, avgBusinessHours 60.6035. **Units unlabelled in the JSON; inferred as the 2nd-decimal unit (pipLocation −2), i.e. ~$0.56–0.68.** [BROKER-PRIMARY, unit inferred — confirm against a practice account's instrument definition.]

Methodology, quoted from OANDA's page config: "The average spread is calculated as a **time-weighted** 'mean' (average) of our quoted spread for the last month and last three months… **Time-weighted** refers to the time a spread was displayed rather than using the number of prices published with a given spread." And: "The quoted spread was at the value stated, or better, **50% and 80% of the time** during open trading hours."

**Core Pricing commission (US):** "Enjoy our lowest spreads and commissions of only **$0.70 per 10,000 units traded**, when you deposit $10K or more and sign up." → **$70 per million units per side** — https://join.oanda.com/us-en/core-spreads-new-clients/ . Plus, from the pricing page: "Commission charges are assessed on the buy and sell sides of a trade. Trade sizes greater or smaller than 100,000 will be charged on a pro-rata basis. The minimum commission of is $0.01 per trade." [sic] and "Earn cash rebates from US$5 to US$17 per million with our Elite Trader program" (a rebate tier on top of, not instead of, the base commission).

### Translating to bps of notional — THE decisive table
[DERIVED. OANDA spreads are broker-primary; **the Dukascopy 0.35-pip figure is a PLACEHOLDER that must be replaced with a measurement from the 2.79B ticks**, per instrument, per session bucket. Quote prices assumed: EURUSD 1.08, GBPUSD 1.27, USDJPY 150, AUDUSD 0.66, USDCHF 0.88, USDCAD 1.37, NZDUSD 0.60.]

| Pair | OANDA avg (bus. hrs) | = bps/round trip | Duk @0.35 pip | **Un-modelled gap, bps/round trip** |
|---|---|---|---|---|
| EUR/USD | 1.56 pips | 1.44 | 0.32 | **1.12** |
| GBP/USD | 1.83 | 1.44 | 0.28 | **1.16** |
| USD/JPY | 1.52 | 1.01 | 0.23 | **0.78** |
| AUD/USD | 1.32 | 1.99 | 0.53 | **1.46** |
| USD/CHF | 1.59 | 1.81 | 0.40 | **1.41** |
| USD/CAD | 1.77 | 1.29 | 0.26 | **1.03** |
| NZD/USD | 2.36 | 3.93 | 0.58 | **3.35** |
| XAU/USD | $0.565 | 1.25–2.26 (gold $4500→$2500) | ~0.7–1.2 | **~0.5–1.1** |

At 500 round trips/year: **~4–11% of notional/year** un-charged (NZD/USD ~17%). At 2000 round trips/year: 20–45%. **For 30 min–48 h holds this is almost certainly larger than the strategy's entire gross edge.**

### Execution statistics, size limits, RTS 27/28
- **No standing OANDA fill-statistics disclosure exists** (no "% filled at requested price", no average execution speed in ms) on US, UK or EU legal pages. [BROKER-PRIMARY negative result — treat as "does not exist".] Closest analogues: (a) the UK policy's spread-stability metric (a price-stability stat, not a fill-rate/latency stat); (b) the US on-request Trade Execution Report.
- ⭐ **Per-trade audit right worth using:** "On request, OANDA will generate a **Trade Execution Report** of all the transactions OANDA executed, in the same currency pair, in the **15 minute windows before and after** execution of the customer's transaction. The report will contain up to **15 transactions from each time period**." — https://www.oanda.com/us-en/legal/ (content itself is gated at hub.oanda.com/documents/execution-report, login required). **This is the purpose-built instrument for the standing operational-referent audit / GAP-0001 live-vs-modelled fill comparison.**
- **No live RTS 27/28 reports** from any OANDA entity — consistent with ESMA suspending RTS 27 from 2021 and the FCA removing the equivalent post-Brexit. The May 2026 OEL policy mentions only "FCA Consumer Duty". Historical 2018–2021 PDFs NOT REACHED (web.archive.org CDX API returned 503). Retry later: `http://web.archive.org/cdx/search/cdx?url=oanda.com*&filter=urlkey:.*rts.*`
- **Min/max trade size: no published numeric table.** Pull from `/v20/accounts/{id}/instruments` on a practice account. The widely repeated "OANDA lets you trade 1 unit" claim could NOT be confirmed against a primary source.
- **CFTC action against OANDA (2020)**: "CFTC Orders Toronto-Based Firm to Pay $500,000 for Violating Capital, Reporting, and Supervision Rules" — https://www.cftc.gov/PressRoom/PressReleases/8224-20 . "OANDA failed to meet net capital requirements from April 26, 2019 to August 21, 2019 and made dividend payments on October 15, 2018, April 26, 2019, and May 28, 2019 in violation of the equity withdrawal restriction." The order "notes that the Division of Enforcement found no indication that customers suffered losses." **Capital/supervision, not execution quality.** NFA ID 0325821. [REGULATORY]

---

## 6. PARTIAL FILLS, REJECTS, REQUOTES AT RETAIL SIZE

**Partial fills at $10k–$500k: essentially zero probability at OANDA.** Two independent primary confirmations: (1) the OEL Annex 1 Market FOK text ("There are no partial fills of the order"); (2) the Special Handling threshold of **$100,000,000 in 10 seconds** — 200× the largest ACIS order.

**→ Model fills as all-or-nothing at a single price. Do NOT build a ladder/VWAP walk (that would be over-delivery against a non-existent problem, SPEC §17/§18). DO model rejection.**

**IG Group "Best execution", Apr–Jun 2024** — https://www.ig.com/uk/about-us/best-execution [BROKER-PRIMARY]
- "**98.97% of orders filled**" (→ ~**1.03% non-fill**), rejections attributed to "market dynamics and erroneous/excessive orders"
- "**100% of successfully filled orders executed at requested price or better**"
- "Over **263,000** of IG Group's at-quote orders received a price improvement," worth "**£3.5 million** in total client benefit", across "**31.5 million trades filled**" / "£2.3 trillion in notional flow per quarter"
- **Currencies overall: stops 89% zero slippage / 11% negative; limits 55% positive / 45% zero**

| | stops 0 | stops − | limits + | limits 0 | avg neg (pips) | avg pos (pips) |
|---|---|---|---|---|---|---|
| EUR/USD | 93% | 7% | 49% | 51% | 0.053 | 0.086 |
| GBP/USD | 88% | 12% | 57% | 43% | 0.062 | 0.083 |
| USD/JPY | 87% | 13% | 59% | 41% | 0.097 | 0.107 |
| AUD/USD | 96% | 4% | 43% | 57% | 0.090 | 0.083 |
| USD/CAD | 93% | 7% | 53% | 47% | 0.005 | 0.009 |

Indices for contrast: US 500 stops 76%/24%, avg neg 0.140; Wall Street 67%/33%, avg neg 0.184; Germany 40 92%/8%, avg neg 0.128; FTSE 100 95%/5%, avg neg 0.013; Australia 200 82%/18%, avg neg 0.034. Indices overall: stops 72% zero / 28% negative; limits 74% positive / 26% zero.

**Pepperstone**: "Receive a **99.32%** fill rate, with no dealer intervention," footnote "Fill rates are based on all trades data between 01/01/2026 and 31/03/2026." — https://pepperstone.com/ [BROKER-PRIMARY]

**How to read IG's numbers:** "100% at requested price or better" and "1.03% not filled" are the *same mechanism viewed twice* — the dealer never gives a worse price on an at-quote order, it declines the order instead. **The rejection rate IS the slippage.**

**Event-window reject/slippage rates: NOT REACHED.** No broker or regulator publication breaks execution statistics out by news-event window. Genuine gap in the public record; make it a declared, stressed parameter (5–15%).

---

## 7. STOP-ORDER EXECUTION AND GAPS

- **Server-side stop:** resting at OANDA. Zero signal-to-venue latency, but accepts whatever price exists when the trigger fires, including a gap-through price. Fills "by the first price that is equal to or worse than the threshold."
- **Signal-driven market order:** full round-trip latency, and can be rejected outright (§9(c) "no obligation to execute any Order (other than a Close Out Order)").
- **Asymmetry to encode: server-side stops fill in states where a market order would be rejected, and at prices no quote ever showed you.** The opposite of the naive backtest assumption (fill at the stop price), which is the single most optimistic assumption in the engine.
- ⚠️ `priceBound` on a stop → cancelled, not filled, on gap-through.
- GSLO exists in some jurisdictions (`guaranteedExecutionPremium`, charged "in price units… for each unit of the Trade"); unavailable to US retail. It is the market price of removing gap risk.

**CHF de-peg tail evidence — FCA CP18/38 para 3.47** [REGULATORY] — https://www.fca.org.uk/publication/consultation/cp18-38.pdf :
> "German regulator BaFin reported that **one client lost €280,000 from an initial investment of €28,000**… **A UK retail client lost £2.7mn from a £200,000 initial investment.**"

→ **10× and 13.5× the initial stake, through stops, in one event.** This is the calibration target for whether the equity floor survives a stop that does not stop (cf. GAP-0108, CHF gap −35%, 7.5% ceiling).

Same CP18/38, general retail CFD context: "an estimated **78%** of active retail client accounts were loss-making… Retail consumers lost **£268.4mn** from trading over a 3-month period from August to October 2017, equal to a projected loss of **£1.07bn a year**" (weighted average of risk warnings from 7 firms ≈65% of the UK retail CFD market). Negative-balance-protection debt forgiven Aug–Oct 2018: **£1.45mn** across 63 firms (>90% of the UK market), scaled to "an annual ongoing benefit… of £6.4mn". Per-firm loss-making-account rates in FCA's chart range roughly 35%–87% (labels did not survive PDF extraction — do not attribute to named firms).

Broker-level consequences of 15 Jan 2015 [UNVERIFIABLE-tertiary — en.wikipedia.org/wiki/FXCM , /Swiss_franc]: franc "surged roughly 30% against the euro within minutes before partially reversing. By day's end… approximately **23%** versus the euro and 21% against the U.S. dollar"; FXCM "lost **$225 million**", took **$300m** Leucadia financing at 10% "as high as 17%", forgave "**90%** of its accounts that incurred negative balances"; Alpari UK insolvent; Saxo reported significant losses; Global Brokers NZ ceased operations. **Your broker can fail in the same event that triggers your stop.**

**Sunday-open gaps EUR/USD & XAU/USD 2012–2025: NOT REACHED.** No published quantitative study found. IG's weekend page is qualitative only.
**→ COMPUTE IT FROM YOUR OWN DATA.** ~700 weekend transitions per instrument. Last tick before Friday close vs first tick after Sunday open, in bps of mid; mean/p50/p90/p99/max, conditioned on the prior week's realised vol. Caution: measure the gap on **mid** (Dukascopy's post-weekend spread widening is venue-specific) and measure spread decay separately.

---

## 8. THE BID/ASK-AT-SIGNAL PROBLEM (LATENCY)

**The contract settles the model:** OANDA US CA §9(c) and OEL §11.1 both define the fill as the price prevailing at *their server on receipt*. So: **fill at t_signal + Δ, on OANDA's book — not at t_signal, and not on Dukascopy's book.**

**Realistic Δ** [DERIVED / practitioner-plausible, not primary]: VPS in the same region as the OANDA endpoint ≈ 20–80 ms signal-to-ack; different region 100–300 ms; plus the in-process loop (non-negligible given the measured ~26 ticks/s engine throughput, GAP-P12D-12). OANDA recommends persistent connections precisely because "using persistent connections… reduce[s] latency by avoiding repeated TCP handshaking."

**EUR/USD diffusion over the latency window** [DERIVED — √t scaling; sanity-checked: σ_ann=7.5% reproduces ~1.3 pips 1-min σ and ~50 pips daily σ]:

| Window | σ_ann=6% | σ_ann=7.5% | σ_ann=10% |
|---|---|---|---|
| 50 ms | 0.028 bps / 0.031 pips | 0.035 / 0.038 | 0.047 / 0.051 |
| 100 ms | 0.040 / 0.043 | 0.050 / 0.054 | 0.067 / 0.072 |
| 250 ms | 0.063 / 0.068 | 0.079 / 0.085 | 0.105 / 0.114 |
| 500 ms | 0.090 / 0.097 | 0.112 / 0.121 | 0.149 / 0.161 |
| 1 s | 0.127 / 0.137 | 0.158 / 0.171 | 0.211 / 0.228 |
| 5 s | 0.283 / 0.306 | 0.354 / 0.382 | 0.472 / 0.510 |
| 60 s | 0.98 / 1.06 | 1.23 / 1.32 | 1.63 / 1.77 |

**At 100 ms the unconditional move is ~0.05 bps — about 3% of the 1.44 bps spread. Pure latency is third-order for this system.** Three caveats keep it non-zero: (1) around NFP/FOMC instantaneous vol runs 10–50×, putting 100 ms σ at 0.5–2.5 bps; (2) **adverse selection** — conditional on the signal firing, the move is not zero-mean (Oomen's 60/40 asymmetry); (3) **feed asymmetry** — acting on a tick the live feed never delivers is a look-ahead, not a latency question.

---

## 9. RANKED MODELLING CHANGES

**Rank 1 — Replace the data's spread with the destination broker's spread.** Use Dukascopy **mid** as reference; synthesise `spread(instrument, session, realised_vol)` calibrated to OANDA's published time-weighted averages. Evidence: OANDA's own averages vs Dukascopy "from 0.1"; OANDA's written "MIGHT NOT BE THE BEST PRICES AVAILABLE" and §5.1 "average of the pricing, excluding outliers… at Normal Market Size". **Closes 60–80% of the gap (~1.0–3.4 bps/round trip).** Cost: low. Subsumes the brief's (f). **Do this before any paid walk-forward run — it is the change most likely to invalidate current OOS results.**

**Rank 2 — Fill stops at the worse of stop price and next traded price (gap-through).** [brief's (e)] Evidence: v20 StopLossOrder "equal to or **worse** than the threshold"; OEL §12.1; FCA CP18/38 CHF client losses. **Closes ~10% of EV but most of the tail risk.** Also add: correct trigger side (bid for long exits), a test for the `BOUNDS_VIOLATION` cancel-not-fill case, and a weekend-gap replay using the measured distribution.

**Rank 3 — Model rejects, and make them adversely selected.** [brief's (d), corrected] Not `P(reject)=p`; reject when the price moved *in your favour* beyond a tolerance between t and t+Δ. Evidence: Cartea et al. "the most profitable trades executed by the ST are cancelled"; Oomen's tolerance/reject curve; XTX's zero-tolerance default; IG's "100% at requested price or better" + 1.03% unfilled; FXCM's $8.26m/57,000 order. Calibrate normal conditions to IG 1.03% / Pepperstone 0.68%; make the event-window rate a declared stressed parameter (5–15%). **~5–10% of EV normally, much more in stress. An unconditional `p` closes NONE of the gap and can flatter the backtest.**

**Rank 4 — Add a latency delay Δ before taking the fill price.** [brief's (b)] Evidence: OANDA CA §9(c) / OEL §11.1 — this is the contract, not a modelling choice. **2–5% of EV at 100 ms normally; more at 200–500 ms and in events.** Cost: low. **Do it anyway — it forecloses a bug class.** **Subsumes the brief's (a):** "next tick's opposite side" is a crude Δ≈one-tick-interval, and tick intervals vary by orders of magnitude, so it silently makes Δ *small when vol is high* — exactly backwards. Prefer an explicit time delay.

**Rank 5 — Fat-tailed slippage conditioned on realised vol.** [brief's (c)] Evidence: IG's per-instrument distributions for the normal-conditions shape; OEL §11.2 symmetry; OEL §9(e) "no limit to how wide the Spread may be" and the CHF evidence for the tail. **~3–5% of EV; more of the variance. Do not double-count with Ranks 1/2/4.** **Tie the parameters to the IG table (public, dated) so the assumption is auditable**, and record it in `declared_deviations`.

**Rank 6 — Do NOT model a liquidity ladder / VWAP walk at this size.** Evidence: FOK, and the $100m/10s Special Handling threshold. **Closes zero — that is the point.** Recording it as a *rejected* change prevents a future audit raising it as a gap.

**Rank 7 — Feed-resolution parity canary.** Assert no decision depends on tick detail finer than the live feed delivers. Natural extension of GAP-P12D-28.

**Rank 8 — Wire the live-vs-modelled comparison from day one.** Use OANDA's on-request Trade Execution Report (15-min windows either side, ≤15 transactions each) to compare modelled vs realised fills against OANDA's own contemporaneous population. **The only mechanism here that measures YOUR fills at YOUR broker.**

---

## 10. LEDGER ITEMS THIS RESEARCH GENERATES

1. **Spread-source defect (Rank 1).** Dukascopy quoted bid/ask under-charges ~1.0–3.4 bps/round trip vs OANDA's published averages. Blocks any honest §14 grading.
2. **Stop `priceBound` cancellation trap.** A v20 StopOrder with a priceBound is *cancelled* on gap-through. Affects GAP-0091b/0099/0075 (threading `SizedOrder.stop_loss` to the venue).
3. **Stop trigger-side convention.** v20 default triggers bid-for-sell / ask-for-buy; backtest must match or it under-counts stop hits.
4. **FIFO / jurisdiction constraint.** NFA 2-43(b) + v20 `FIFO_VIOLATION`: same-instrument multi-position states unreachable on a US account.
5. **Reject-reason enum shape.** `BOUNDS_VIOLATION` / `MARKET_HALTED` / `INSUFFICIENT_LIQUIDITY` / `FIFO_VIOLATION` are `OrderCancelReason`; `PRICE_BOUND_INVALID` / `UNITS_*` are `TransactionRejectReason`. No `PRICE_BOUND_EXCEEDED` exists. Also `INSTRUMENT_BID_HALTED` / `INSTRUMENT_ASK_HALTED` (one-sided halts).
6. **Counterparty/venue risk: automated-trading clause.** OANDA US CA §11(f)(iv) Event of Default covers "using any ultra-high speed trading or automated or mass data entry system", sole discretion, no notice. `OPERATIONS_LEDGER.md` item before first live fill.
7. **Doc correction.** Any claim of a "2025 FX Global Code revision to last look / pre-hedging" is FALSE: the 2024 review (published Jan 2025) amended P9, P10, P35, P50, P51 only; P17 was last confirmed unchanged in 2021.
8. **Two measurements from data already on disk:** (a) per-instrument top-of-book size distribution from the tick volume fields; (b) per-instrument Friday-close→Sunday-open gap distribution across ~700 weekends, on mid, spread decay measured separately.
9. **Operational-referent instrument identified.** OANDA's on-request Trade Execution Report is the purpose-built evidence source for the standing GAP-0001 live-vs-modelled fill comparison.

---

## 11. OPEN / UNVERIFIED — DO NOT LET THESE ROT INTO ASSUMED FACTS

- Dukascopy volume units ("millions") — practitioner-attested, not in the javadoc. Verify empirically.
- XAU/USD spread unit in labs-api (56.45 = $0.5645 assumes pipLocation −2). Confirm against a practice account.
- OANDA minimum/maximum trade size numerics — not published; pull from `/v20/accounts/{id}/instruments`. The "1 unit minimum" claim is unconfirmed folklore.
- Event-window reject and slippage rates at any retail broker — no public source reached.
- Weekend-gap distributions for EUR/USD and XAU/USD — no published study reached.
- IOSCO 2025 pre-hedging final report — NOT REACHED.
- NFA/CFTC actions against FXDD, Gain Capital, Interbank FX — NOT REACHED; no docket numbers asserted.
- BIS Markets Committee reports (sterling flash event 2016; FX execution algorithms 2020) — URL guesses 404'd.
- OANDA historical RTS 27/28 (2018–2021) — archive.org CDX returned 503; retry.
- CFTC/NFA docket numbers for the FXCM 2017 Effex/"no dealing desk" action — the 2011 order (captured above) is verified; the 2017 one is only secondary-sourced.

---

## 12. SOURCES

**Regulatory:** CFTC order, Forex Capital Markets LLC, 3 Oct 2011 — https://www.cftc.gov/sites/default/files/idc/groups/public/@lrenforcementactions/documents/legalpleading/enffxcmorder10032011.pdf · FCA Final Notice FXCM, 24 Feb 2014 — http://dl.icdst.org/pdfs/files3/07e0f20234f7fd2708e195dc952e4738.pdf · 17 CFR 5.18 — https://www.law.cornell.edu/cfr/text/17/5.18 · NFA Compliance Rule 2-43 — https://www.nfa.futures.org/rulebook/rules.aspx?Section=4&RuleID=RULE%202-43 · CFTC PR 8224-20 (OANDA) — https://www.cftc.gov/PressRoom/PressReleases/8224-20 · FCA CP18/38 — https://www.fca.org.uk/publication/consultation/cp18-38.pdf · FCA PS19/18 — https://www.fca.org.uk/publication/policy/ps19-18.pdf · FCA Occasional Paper 50 — https://www.fca.org.uk/publication/occasional-papers/occasional-paper-50.pdf · GFXC Report on Last Look, Aug 2021 — https://www.globalfxc.org/uploads/gfxc_report_last_look-1.pdf · GFXC Three-Year Review Outcomes, Jan 2025 — https://www.globalfxc.org/uploads/gfxc_3year_review_outcomes_dec2024.pdf · FX Global Code, Dec 2024 — https://www.globalfxc.org/uploads/fx_global.pdf

**Academic:** Oomen, *Last look*, Quantitative Finance 17(7) 2017 — https://researchonline.lse.ac.uk/id/eprint/68811/1/Oomen_Last%20look_2017.pdf · Cartea, Jaimungal & Walton, *Foreign Exchange Markets with Last Look*, arXiv:1806.04460 — https://arxiv.org/abs/1806.04460

**Broker-primary:** OANDA Additional Disclaimer Dec 2025 — https://www.oanda.com/assets/documents/2003/OANDA_Additional_Disclaimer-2025.pdf · OANDA US Customer Agreement Mar 2026 — https://legal.oanda.com/?code=fxtrade_customer_agreement&language=en · OANDA Europe Order Execution Policy May 2026 — https://legal.oanda.com/?code=execution_policy_oel&language=en · OANDA US legal index — https://www.oanda.com/us-en/legal/ · OANDA pricing — https://www.oanda.com/us-en/trading/our-pricing/ · OANDA Core Pricing offer — https://join.oanda.com/us-en/core-spreads-new-clients/ · OANDA spreads & margin — https://www.oanda.com/us-en/trading/spreads-margin/ · OANDA live spread API — https://labs-api.oanda.com/v1/spreads/spread-stability-and-average?division=OC&locale=en&instrument=EUR_USD · v20 docs — https://developer.oanda.com/rest-live-v20/order-df/ , /transaction-df/ , /pricing-df/ , /primitives-df/ , /best-practices/ · XTX eFX Cover Sheet 18 Sep 2025 — https://www.xtxmarkets.com/assets/disclosures/global-efx-cover-sheet.pdf · XTX eFX Trading Practices — https://www.xtxmarkets.com/assets/disclosures/global-efx-trading-practices-disclosures.pdf · IG Best Execution Apr–Jun 2024 — https://www.ig.com/uk/about-us/best-execution · Pepperstone — https://pepperstone.com/ · Dukascopy ITick javadoc — https://www.dukascopy.com/client/javadoc3/com/dukascopy/api/ITick.html · Dukascopy Forex Trading — https://www.dukascopy.com/swiss/english/forex/trading/ · Dukascopy Historical Data Export — https://www.dukascopy.com/swiss/english/marketwatch/historical/

**Practitioner/tertiary:** EliteTrader "Interpreting Dukascopy Tick Data" — https://www.elitetrader.com/et/threads/interpreting-dukascopy-tick-data.352792/ · mayeranalytics/bi5 — https://github.com/mayeranalytics/bi5 · Wikipedia: Dukascopy Bank / FXCM / Swiss franc
