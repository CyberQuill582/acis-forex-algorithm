# RESEARCH — Execution venue choice for ACIS (2026-09-17)

**Question put to this pass:** the backtest uses Dukascopy tick data and the spec (§3, §7.5) names OANDA v20 as the primary execution adapter. Where should this system actually execute — OANDA, Dukascopy, a hybrid, or something else?

**Status:** research only. No engine code, config, spec or ledger file was modified; nothing was committed. Findings that belong in the ledger are listed in §7 for the owner to file.

**Source grading used throughout:**
- **(a) PRIMARY** — a regulator register, a broker legal/pricing document, or API documentation read directly at its own URL in this session.
- **(b) SECONDARY** — credible practitioner or industry source.
- **(c) UNVERIFIED** — marketing copy, folklore, or something a fetch could not confirm. Flagged explicitly.

Where a claim is carried forward from the 2026-09-16 research pass already in `archive/` (`PARTIAL_oanda_execution_research_2026-09-16.md`, `PARTIAL_execution_fidelity_dukascopy_vs_oanda_2026-09-16.md`), it is marked **[carried]** and its own grade is preserved.

---

## 0. THE FINDING THAT REFRAMES THE QUESTION

> **"To use this API you must have a v20 trading account, which is available to all divisions except OANDA Global Markets and OANDA TMS BROKERS S.A."**
> — OANDA v20 REST API, Introduction. https://developer.oanda.com/rest-live-v20/introduction/ **(a) PRIMARY, read directly**

**OANDA Global Markets Limited is the entity a Kenyan resident onboards to.** It is the BVI entity:

> "OANDA Global Markets Ltd is a company registered in BVI number 2026433, and has its registered office at Kingston Chambers, PO Box 173, Road Town, Tortola, British Virgin Islands. It is authorised and regulated by the BVI Financial Services Commission, number: SIBA/L/20/1130."
> — https://www.oanda.com/bvi-en/legal/ **(a) PRIMARY**

Therefore: **the spec's primary execution adapter — OANDA v20 REST — is not available to this owner.** This is not a preference, a tier, or something support can enable; it is a division-level exclusion published by OANDA itself.

Corroborating evidence from the same division's own site: the OANDA Global Markets platform list is **fxTrade app, MetaTrader 5, TradingView, and Depth of Market** — there is no API page at all under `/bvi-en/`, and the MT5 download links point at `OANDA-OGM MT5 Live` / `OANDA_Global-Live-1` servers (https://www.oanda.com/bvi-en/cfds/platforms/, **(a) PRIMARY**).

**Consequence:** "execute at OANDA" for this owner means **OANDA BVI on MetaTrader 5**, not OANDA v20. That is a different adapter, a different order model, a different sizing granularity, a different regulator, and — as §1.4 shows — a materially different set of client protections. Any plan that assumes v20 is planning for an account he cannot open.

---

## 1. OANDA vs DUKASCOPY FOR THIS PROFILE

### 1.1 Which legal entity, and what it is

| | **OANDA Global Markets Ltd** | **Dukascopy Bank SA** |
|---|---|---|
| Entity a Kenyan resident gets | BVI company no. 2026433 **(a)** | Swiss bank, Geneva **(a)** |
| Regulator | BVI Financial Services Commission, SIBA/L/20/1130 **(a)** | FINMA — "regulated by the Swiss Financial Market Supervisory Authority FINMA **both as a bank and a securities firm**" (https://www.dukascopy.com/swiss/english/about/) **(a)** |
| Product traded | **CFDs**, not spot FX — "allow you to trade investment products known as contracts for difference (our 'Products' or 'CFDs')" (ToB §1.2) **(a)** | Spot FX / metals on SWFX, plus CFDs |
| Client money | "held in a segregated Client Money bank account" (ToB §15.1), **pooled**, may sit in term deposits up to 95 days; "in the unlikely event of insolvency… such amounts may not be immediately available" (§15.2) **(a)** | Swiss bank deposit insurance: **"The protection is limited to a maximum of CHF 100 000 per client and institution"** (esisuisse) **(a)** |
| Negative balance protection | **NONE.** "All negative balances are payable." (ToB §1.3); "You will be responsible for the payment of all negative balances." (§6.11) **(a)** | Not stated on the client-protection page; Dukascopy offers pre-set **Slippage Control** instead **(a)**. Treat NBP as **not confirmed**. |
| Compensation scheme | None (BVI has no investor compensation scheme) | esisuisse, CHF 100,000 **(a)** |
| Kenya accepted | Not excluded; ToB §17.4 pushes the duty onto the client — "It is your responsibility to verify that you are permitted to use and access the Trading Platform in the country in which you are located." **(a)** | Solicitation disclaimer excludes only **"Belgium, Israel, Russian Federation, Turkey, Canada (including Québec) and the UK"** — **Kenya is not on it** **(a)** |

**Source for the OANDA rows:** *OANDA GLOBAL MARKETS LIMITED Retail Clients Terms of Business, effective 2 June 2025*, PDF retrieved and text-extracted in this session from `https://legal.oanda.com/?code=ogm_terms_of_business&language=en`. **(a) PRIMARY, read directly.**

> **The single largest non-cost difference between these two venues is not execution model. It is that one is a FINMA-licensed Swiss bank with CHF 100,000 of deposit insurance, and the other is a BVI CFD counterparty with no compensation scheme and a contractual right to pursue you for a negative balance.** For a system whose own guardrail design is built around surviving a CHF-style gap (GAP-0108, −35% modelled), that asymmetry is directly on-topic: the 15 January 2015 event is precisely where a client owes more than their deposit, and where the broker itself can fail.

### 1.2 Execution model

**OANDA — principal market maker, in its own words. [carried, (a) PRIMARY]**
- "THE FOREIGN CURRENCY TRADING YOU ARE ENTERING INTO IS NOT CONDUCTED ON AN EXCHANGE. OANDA IS ACTING AS A COUNTERPARTY… **OANDA ESTABLISHES THE PRICES AT WHICH IT OFFERS TO TRADE WITH YOU. THE PRICES OANDA OFFERS MIGHT NOT BE THE BEST PRICES AVAILABLE.**" (*OANDA Additional Disclaimer*, Dec 2025)
- OANDA Europe Order Execution Policy §2.1: "We will act as **principal and not as your agent**… we therefore act as **the sole trading venue** for those Orders."
- §11.2: "…**do not apply asymmetrical slippage parameters. Positive and negative slippage are handled with strict symmetry.**" — a genuine, documented protection, and better than most of the market-maker field.
- §3.1(c): "We are not obliged to accept your Order(s) and may therefore reject any Order(s)."

**Dukascopy — SWFX, a real ECN. (a) PRIMARY**
- "Large liquidity pool from 20+ banks"; "ECN"; "**Transparent pricing — All clients have access to the same liquidity at equal prices through a single datafeed**"; clients may "propose your own liquidity by placing your ask/bid pending orders." (https://www.dukascopy.com/swiss/english/forex/trading/)
- `ITick.getAsk()` = "Best ask price on the market" **(a)**.
- Dukascopy support, on the record: "We reflect only best ask and bid available in our system… **This is not a guarantee that your trade will be executed at those prices.**" **(b)** [carried]

**What this means concretely.** OANDA's price is OANDA's opinion of the market ("an average of the pricing, excluding outliers, available from those third parties" — OEL §5.1). Dukascopy's price is an actual multi-bank book you can also *post into*. For a 30 min–48 h holding period the microstructure difference is largely irrelevant to alpha; what matters is (i) the level of the spread you pay and (ii) whether the venue's incentives are aligned. On (ii), OANDA has written down that its "interests may be in conflict with yours" and that it "may make more money if the market goes against you"; Dukascopy, as an agency ECN charging explicit commission, does not have that conflict.

### 1.3 All-in cost at retail size — **the result is not what the spec assumes**

**OANDA Global Markets (BVI) published spreads**, https://www.oanda.com/bvi-en/cfds/our-pricing/ **(a) PRIMARY, but "typical" marketing-grade figures, not a measured time-weighted average:**

| | Spread-only account | Core (spread + commission) |
|---|---|---|
| EUR/USD | **1.0 pips** | 0.1 pips + commission |
| USD/JPY | **1.1 pips** | 0.1 pips + commission |
| GBP/USD | **1.2 pips** | 0.1 pips + commission |
| XAU/USD | **not published for OGM** | not published |

> ⚠️ **Correction to a figure now sitting in the live ledger.** `GAP-P12D-41` calibrates against **1.5578 pips** EUR/USD business-hours. That number comes from `labs-api.oanda.com/…&division=OC` — **OANDA Corporation, the US division**, which a Kenyan resident cannot open. Querying the same endpoint per division in this session gave EUR/USD 1-month business-hours averages of **OC 1.5578 / OEL 0.7578 / OAP 0.9578**, and **division=OGM returns HTTP 500 — OANDA publishes no measured spread series for the BVI division at all** **(a) PRIMARY**. Two honest observations follow: (i) the gap's 1.44 bps target is roughly 1.5× too pessimistic for the venue this owner would actually use, whose *published* spread is 1.0 pip ≈ 0.93 bps; (ii) the three divisional figures differ by exact constants (identical fractional tails `.x57796`), so they are one base series with a per-division offset applied — they are **not** three independent measurements, and should not be cited as such. **There is no measured spread series for OGM. Its real spread must be sampled from a live OGM demo account before any §14 grading is trusted.**

**Dukascopy commission schedule** — https://www.dukascopy.com/swiss/english/about/fee-schedule/ **(a) PRIMARY**, "The lowest possible volume commission is applied as per table below using three criteria: Net Deposit, Equity or Traded Volume":

| Equity (USD) | Currency pairs | Metals/commodities |
|---|---|---|
| < 5,000 | $35 / million | $52.50 / million |
| ≥ 5,000 | $33 / million | $49.50 / million |
| **≥ 10,000** | **$30 / million** | **$45 / million** |
| ≥ 25,000 | $25 / million | $37.50 / million |
| ≥ 50,000 | $18 / million | $27 / million |
| ≥ 250,000 | $16 / million | $24 / million |
| ≥ 1,000,000 | $14 / million | $21 / million |

MT4/MT5 accounts at Dukascopy add **"$0.5 per 1 MT4 / MT5 lot"** on top, and the sub-$5k tier is quoted as **"8"** USD per round-turn lot for currencies **(a)**.

**All-in round-trip cost, in bps of notional** *(derived; assumes EUR/USD 1.08, USD/JPY 150, GBP/USD 1.27, gold $4,000/oz. Dukascopy's realised retail spread is taken at **0.4 pips** — the site's "from 0.1" is marketing **(c)**, and a $10k account does not see the top of the aggregate book)*:

| Instrument | **OANDA OGM spread-only** | **Dukascopy @ $10k equity** | Δ |
|---|---|---|---|
| EUR/USD | 1.0 pip → **0.93 bps** | 0.37 (spread) + 0.60 (comm) = **0.97 bps** | **Dukascopy ~0.04 bps WORSE** |
| USD/JPY | 1.1 pip → **0.73 bps** | 0.27 + 0.60 = **0.87 bps** | Dukascopy 0.14 bps worse |
| GBP/USD | 1.2 pip → **0.94 bps** | 0.31 + 0.60 = **0.91 bps** | ≈ tie |
| XAU/USD | **unpublished** (US division implies ~1.4 bps) | ~0.6 + 0.90 = **~1.5 bps** | ≈ tie, both uncertain |

> **The headline cost result: at a $10,000 account, Dukascopy is NOT cheaper than OANDA.** Its ECN spread advantage (~0.6 bps) is consumed almost exactly by its commission at the $10k tier (0.60 bps round trip). The ECN economics only start to win above roughly **$50,000 equity** ($18/million → 0.36 bps RT → ~0.73 bps all-in, a ~0.2 bps edge), and only become decisive above ~$250k. **Anyone choosing Dukascopy over OANDA at $10k for cost reasons is choosing it for a reason that does not exist at that size.**

A second, smaller finding of the same kind: **OANDA's Core Pricing (commission) account is the wrong account for this system.** $0.70 per 10,000 units per side = $70/million/side ≈ 1.30 bps round trip, plus the 0.1 pip spread ≈ 0.09 bps → **~1.39 bps**, versus **0.93 bps** on the spread-only account. [carried **(a)**, arithmetic derived.] Take the spread-only account.

### 1.4 Leverage, minimum deposit, sizing granularity

| | OANDA OGM (BVI) | Dukascopy Bank SA |
|---|---|---|
| Minimum deposit | not published on the BVI pages **(c)** | **"$100, or the equivalent in other currencies"** **(a)** |
| Max leverage | **888:1** tier-1 for accounts opened after 3 Oct 2022 (`OANDA_OGM_Margin_Rates_20260828.pdf`, header "888:1 LEVERAGE Instruments"; EURUSD < 0.5m → ~0.11% margin; XAUUSD < 0.5m → ~0.11%) **(a)** | **"leverage up to 1:200"** **(a)** |
| Minimum ticket | **0.01 lots = 1,000 units** FX; **0.001 lots = 0.1 oz** XAUUSD **(a)** | 1,000 units on JForex **(b)**; MT4/MT5 0.01 lots **(b)** |

**On the HARD REQUIREMENT of fine-grained sizing:** OANDA *v20* sizes in single units. **OANDA OGM does not** — its published minimum ticket is 0.01 lots (1,000 units) with 0.01-lot increments, i.e. MT5 semantics. For a $10k account sizing at ~$20–30k notional per position, 1,000-unit quantisation is a ~3–5% rounding of each position. That is tolerable for a risk-sizing Governor but it is **not** the "units, not whole lots" property the spec assumed it was buying from OANDA, and `core/governor/units.py` / the `UNITS_PER_LOT` path (already flagged under GAP-P12D-22) will be doing real rounding work.

**888:1 leverage is a red flag, not a feature.** It is offshore-tier leverage, offered by an entity with no negative balance protection. Nothing in ACIS wants it; the Governor should cap far below it, and the margin-closeout mechanics (ToB §9, "We do not need to give you advance notice or time to respond to a Margin Closeout") should be modelled explicitly.

### 1.5 Financing / swap markup method

- **Dukascopy — published method, with a disclosed markup. (a) PRIMARY.** Overnight rates are built off named central-bank target rates (Fed Funds Target, ECB Main Refinancing, BoE Official Bank Rate, …), and the bank states plainly: **"It must be stressed that Dukascopy Bank adds its own carry costs to the rates applied to the clients."** It also runs a **Trading Activity** tier — `Trading Activity = Trading Volume / (Trading Volume + Overnight Volume) × 100%` over 30 days — giving Premium (>90%), Advanced (>20%) and Regular (≤20%) rollover policies. **This matters for ACIS specifically:** a system holding 30 min–48 h carries real overnight volume, so it will *not* sit in the Premium tier, and its financing cost is tier-dependent in a way the current carry model does not know about.
- **OANDA OGM** — the BVI pricing page says only "Financing costs can affect your cost of trading" and links onward; **no rate table or markup method was retrievable** in this session. **(c) UNVERIFIED — must be pulled from a live OGM account.**

### 1.6 API quality for an always-on Python algo

| | OANDA OGM | Dukascopy |
|---|---|---|
| REST/streaming API | **v20 explicitly unavailable to this division (a)** | — |
| Native programmatic API | MT5 only | **JForex API (Java)** and **FIX 4.4** |
| Python path | `MetaTrader5` PyPI package — **Windows x86-64 wheels only; no Linux/macOS builds** **(a)**, and it drives a running MT5 terminal | FIX 4.4 via `quickfix`/`simplefix`, **or** a Java JForex-SDK sidecar bridged to Python |
| Instrument coverage of the API | full | **FIX is "limited to FX only"** **(a)** — **XAU/USD is not reachable over Dukascopy FIX** |
| Historical candles | MT5 `copy_rates_*` | JForex, plus the public tick archive already on disk |

Two hard engineering facts fall out:

1. **The MT5 Python path breaks the current deployment.** `Dockerfile` is `FROM python:3.11-slim` and `deploy/systemd` supervises a Linux process. The `MetaTrader5` package ships **Windows wheels only**. Choosing OANDA-BVI therefore means either a Windows VPS (abandoning the Docker/systemd work done at the phase-12 deployment gate) or an MT5-under-Wine bridge (a new, fragile component squarely in the protective-stop path).
2. **Dukascopy's clean API does not cover the declared universe.** FIX 4.4 is FX-only, so XAU/USD — a declared instrument — would need JForex, i.e. a Java process in the loop. A Java sidecar is a second runtime between the Risk Monitor and the venue; under the §2 Layer Communication Law and §279 that is a serious design cost, not a detail.

### 1.7 Server-side stop semantics, including gap-through

- **OANDA v20 (documented, but for divisions this owner cannot use): (a) PRIMARY [carried].** `StopLossOrder` "will be filled (closing the Trade) by the first price that is equal to or **worse** than the threshold" — gap-through is passed to the client. And the trap now logged as GAP-P12D-42: a `StopOrder` carrying a `priceBound` — "If the market gaps and crosses through both the price and the priceBound, the Stop Order **will be cancelled instead of being filled**." A protective bound converts a bad fill into *no protection at all*.
- **OANDA MT5 (the actual OGM path): (b).** MT5 SL/TP rest on the broker's server and survive terminal disconnect — this is standard MT5 semantics and satisfies §279 in principle, but **it must be proven by the ACIS-06 conformance suite against an OGM demo account**, not assumed. The `resting_stops()` / `BrokerPosition.stop_loss` contract exists precisely for this.
- **Dukascopy: (a).** Orders rest at the bank; the client-protection page describes server-side Stop-Loss that "automatically closes positions when account reaches a client-set level", plus **"Slippage Control allowing clients to preset maximum acceptable negative slippage on order execution"** — Dukascopy's analogue of `priceBound`, and it deserves the same GAP-P12D-42 scrutiny (does preset slippage control *cancel* or *fill worse* on a gap? Unverified — **(c)**).
- **Both venues pass the gap risk to the client.** The calibration target remains FCA CP18/38 §3.47 on the 2015 CHF event: "one client lost €280,000 from an initial investment of €28,000… A UK retail client lost £2.7mn from a £200,000 initial investment" — 10× and 13.5× the stake, *through stops* **(a) [carried]**. The OGM entity's "all negative balances are payable" clause is what that risk looks like contractually.

### 1.8 Execution-quality disclosures

- **OANDA: none that binds.** No "% filled at requested price", no average execution speed, **no RTS 27/28** from any OANDA entity (consistent with ESMA suspending RTS 27 and the FCA dropping the equivalent post-Brexit). **(a) negative result [carried].** The one usable instrument is the US division's on-request **Trade Execution Report** (transactions in the same pair in the 15 minutes either side, up to 15 each) — and it is a *US-division* facility, so **its availability to an OGM client is unverified (c)**.
- **Dukascopy: no fill-rate disclosure found either (c)**, but it publishes the full historical tick feed of its own venue — a structurally stronger form of transparency, and the reason §2 below is interesting.
- Regulatory context worth keeping in view **[carried, (a) REGULATORY]:** CFTC 2020 order against OANDA Corporation, $500,000, for **capital/reporting/supervision** failures — explicitly "no indication that customers suffered losses" and nothing to do with execution quality. It is not a reason to avoid OANDA; it is a reason not to treat any retail FX counterparty as risk-free.

### 1.9 The clause nobody reads, which applies to this system by name

OGM Terms of Business §23.1(i), Event of Default:

> "we reasonably believe you have acted in an unfair or abusive manner, for example, but not limited to, using any **ultra-high speed trading; automated or mass data entry system**; or **Scalping** with or on the Trading Platform"

**(a) PRIMARY.** On an Event of Default OANDA may, "in its absolute discretion, at any time and without prior notice", close out all open positions. ACIS is, on its face, an "automated system". The clause is almost certainly aimed at latency arbitrage and quote-sniping rather than a 30-minute-to-48-hour position system, and it is standard boilerplate across the CFD industry — but it is **discretionary, un-appealable, and written broadly enough to reach this system**. It belongs in `OPERATIONS_LEDGER.md` before the first live fill, and it is worth a written pre-clearance email to OANDA describing the strategy's turnover and holding period.

---

## 2. IS THE HYBRID COHERENT? (backtest on Dukascopy, execute elsewhere)

**Yes — and it is what essentially every serious retail/small-fund FX system does.** Nobody backtests on their broker's own historical quotes, because (i) retail brokers do not publish tick-grade history (OANDA's own historical API is candle-grade — already established in master §13 v2.9), and (ii) a venue's own quote history is not a neutral referent for the venue's own fills. The mismatch is normal. What matters is whether you model it or pretend it away.

### What genuinely breaks

1. **The spread level — and this is the whole ballgame.** Filling at the Dukascopy tick's own bid/ask charges you an ECN's spread for execution at a market maker's spread. Against OGM's published 1.0 pip that is roughly **0.93 bps vs ~0.37 bps** — about **2.5× optimistic** on EUR/USD (not the 3.9× in GAP-P12D-41, which was measured against the US division; see §1.3). This is the one that invalidates §14 grading, and it is already owned by GAP-P12D-41.
2. **Feed resolution asymmetry — a look-ahead, not a latency question.** The Dukascopy archive can carry many ticks per second. OANDA's v20 best-practices page notes prices "can change more than once a second" but the client stream is aggregated; MT5 ticks likewise. **A decision that depends on intra-second tick detail the live feed never delivers is a look-ahead bug wearing a latency costume.** This is the most insidious failure mode of the hybrid, and the cheapest to test for (the GAP-P12D-28 canary family extends to it naturally).
3. **Financing.** Dukascopy's tiered, activity-dependent, explicitly-marked-up swap (§1.5) and OANDA's unpublished BVI financing are different numbers. Modelled carry calibrated to one is wrong for the other.
4. **The gold contract is not the same product.** Dukascopy spot XAU/USD on SWFX, OANDA XAUUSD CFD with a 100-ounce lot and 0.001-lot minimum, are different instruments with different calendars and different financing. The v2.15 OTC spot-gold calendar work was done against the Dukascopy convention.

### What is merely approximate (and fine)

- **Mid-price path.** The *mid* of a 20+-bank ECN is an excellent reference for where the market was. Signal generation off Dukascopy mids is sound. It is the *transacted* price, not the reference price, that needs replacing.
- **Latency.** Already quantified in the prior pass: at 100 ms the unconditional EUR/USD move is ~0.05 bps, about 3% of the spread. **Third-order for 30 min–48 h holds** — except in event windows, where instantaneous vol runs 10–50×.
- **Partial fills / size impact.** Zero at this size. OANDA FX market orders are FOK ("There are no partial fills of the order"), and its Special Handling threshold is **$100,000,000 in 10 seconds** — 200× the largest ACIS order **(a) [carried]**. Do not build a liquidity ladder; recording that as a *rejected* change is the right move under §17/§18.

### What practitioners actually do about it

Three things, in this order — and the prior pass's ranked list is the right one:
1. **Use the source's mid, synthesise the destination's spread.** `spread(instrument, session, realised_vol)` calibrated to the *venue you will trade at*, wrapped around the Dukascopy mid. This is standard practice and it closes 60–80% of the gap.
2. **Model rejects as adversely selected, never as an unconditional probability.** A reject is conditioned on the price having moved *in your favour*. IG's own best-execution disclosure shows the mechanism twice over: "100% of successfully filled orders executed at requested price or better" *and* "98.97% of orders filled" — **the rejection rate IS the slippage** **(a) [carried]**.
3. **Wire a live-vs-modelled comparison from the first fill** (`OPERATIONS_LEDGER.md`, GAP-0001). No amount of data-source sophistication substitutes for measuring your own fills at your own broker.

### The property nobody has costed: executing at Dukascopy collapses the mismatch

If ACIS executes **at Dukascopy**, the backtest data source and the execution venue become the same firm's book. The spread-level defect (GAP-P12D-41) largely disappears; the modelled quote *is* the venue's quote; the weekend-gap, rollover-spike and gold-break calendar marks already validated against Dukascopy in `scripts/run_data_validation.py` are validated against the live venue too. **This is a genuinely rare and valuable coherence property and it is the strongest argument for Dukascopy that has not yet been put on the table.**

It is not perfect, and the honest caveats are:
- The historical feed is the **aggregate** SWFX top of book. A $10k account's actual liquidity allocation is a *subset*, so realised spreads will be worse than the archive implies. Closer, not identical.
- The archive carries repeated-price ticks and Dukascopy-specific post-weekend spread widening **(b) [carried]** — artefacts of the venue, which is exactly why they now become *correct* rather than noise.
- It does not remove latency, rejects, or gap-through. It removes the **level** error, which is the dominant one.

---

## 3. IS NEITHER THE RIGHT ANSWER?

*(This section integrates two parallel primary-source sweeps run for this pass: one on alternative brokers, one on the prop-firm route. Their findings are summarised here with grades preserved.)*

<!-- AGENT_FINDINGS -->

---

## 4. COST ARITHMETIC THAT DECIDES IT

Define **L** = notional per trade ÷ NAV (gross exposure multiple) and **R** = round trips per year. Then:

> **Annual trading cost as a fraction of NAV = cost_bps × 10⁻⁴ × R × L**

At a $10,000 NAV with risk-based sizing and ATR-width stops, **L ≈ 2–3** is the realistic range (a 1% risk budget against a 30-pip EUR/USD stop is ~33,000 units ≈ 3.3× NAV).

**Annual cost as % of NAV, at L = 2:**

| Venue / instrument mix | cost per RT | R = 300 | R = 500 | R = 1,000 | **R = 1,800** *(today's prototype)* |
|---|---|---|---|---|---|
| OANDA OGM spread-only, FX majors | 0.93 bps | 5.6% | 9.3% | 18.6% | **33.5%** |
| Dukascopy @ $10k equity | 0.97 bps | 5.8% | 9.7% | 19.4% | **34.9%** |
| Dukascopy @ $50k equity | 0.73 bps | 4.4% | 7.3% | 14.6% | 26.3% |
| **Venue Δ at $10k** | **0.04 bps** | 0.02% | 0.04% | 0.08% | **0.14%** |
| **Venue Δ, OANDA vs Dukascopy@$50k** | **0.20 bps** | 1.2% | 2.0% | 4.0% | 7.2% |

**Read the table in this order:**

1. **The venue difference at this account size is NOISE.** 0.04 bps per round trip is 0.14% of NAV per year even at the prototype's churn. **It cannot decide anything.** Anyone who tells you Dukascopy's ECN saves money on a $10k account is quoting a table that starts at $50k.
2. **Turnover is the decision.** At R = 1,800 the *absolute* cost is **33% of NAV per year** at either venue. No FX system with a 30 min–48 h horizon earns 33% of NAV gross with any reliability. **At today's turnover the system is unprofitable at every venue on this list, and the venue question is moot until turnover comes down.** This is the same conclusion GAP-P12D-41 reached from the other end, and it is reinforced, not weakened, by the corrected (lower) OGM spread.
3. **The decision-relevant differences are therefore not cost.** They are, in descending order: **(i) whether an API exists that this Python engine can actually drive on Linux; (ii) what happens to the owner in a CHF-2015 event; (iii) whether the venue lets an algo trade at all.**
4. **Gold is a wash and is the most uncertain line.** Neither venue's gold cost is properly established (OGM publishes nothing; Dukascopy metals commission is 1.5× the FX rate). If XAU/USD stays in the live universe, its cost must be sampled from a demo account at whichever venue wins, not modelled from the FX number.
5. **Financing is the term nobody has priced.** At 30 min–48 h holds a meaningful fraction of positions carry overnight. Dukascopy publishes its method *and its markup*; OANDA BVI publishes neither. On carry-negative pairs held two nights, financing can rival the spread. **This is an open hole in the cost model at both venues.**

---

## 5. RECOMMENDATION

<!-- RECOMMENDATION -->

---

## 6. WHAT COULD NOT BE VERIFIED — do not let these rot into assumed facts

- OANDA OGM's **actual** (as opposed to "typical") spreads. No measured series exists; `division=OGM` returns HTTP 500 on OANDA's own spread API. **Must be sampled from an OGM demo account.**
- OANDA OGM's **XAU/USD spread** and **financing/swap rate table** — not published anywhere reachable.
- OANDA OGM's **minimum deposit** — not published on the BVI pages.
- Whether the US division's **Trade Execution Report** facility is available to an OGM client.
- Whether OANDA MT5 at OGM **actually** holds stops server-side in the way §279 requires — standard MT5 semantics say yes; the ACIS-06 conformance suite must prove it.
- Dukascopy **negative balance protection** — not stated on the client-protection page.
- Dukascopy **FIX API access requirements** (minimum equity, fees) — "For professional market participants" is all the page says.
- Dukascopy's realised **retail** spread at a $10k equity tier. "from 0.1" is marketing **(c)**; the 0.4-pip figure used in §1.3 and §4 is an assumption and the arithmetic is sensitive to it.
- Whether Dukascopy's **Slippage Control** cancels or fills-worse on a gap-through (the GAP-P12D-42 question, asked of the other venue).
- Kenya-specific onboarding reality at either venue (KYC acceptance, funding rails, withdrawal friction) — the legal documents do not exclude Kenya, but **not excluded ≠ will onboard**.

---

## 7. LEDGER ITEMS THIS PASS GENERATES (for the owner to file — nothing was written)

1. **The spec's primary execution adapter is unavailable to the owner.** Master §3 / §7.5 name OANDA v20 as the v1 primary. OANDA publishes that v20 is unavailable to OANDA Global Markets, the only division a Kenyan resident can open. This is a **spec-vs-world defect of exactly the class the external-referent audit exists to catch**, and it invalidates the v1 adapter plan as written.
2. **GAP-P12D-41 is calibrated against the wrong division.** Its 1.5578 pip / 1.44 bps EUR/USD target is OANDA Corporation (US). OGM's published spread is 1.0 pip ≈ 0.93 bps; the optimism ratio is ~2.5×, not 3.9×. Also: the divisional figures from `labs-api` are one base series with constant offsets, not independent measurements, and **no measured series exists for OGM at all**.
3. **Sizing granularity regression.** OGM's minimum ticket is 0.01 lots (1,000 units) / 0.001 lots (0.1 oz gold), not v20's 1 unit. Affects `core/governor/units.py`, `UNITS_PER_LOT`, and the §14 sizing fidelity claim.
4. **Deployment-platform conflict.** The `MetaTrader5` Python package is Windows-only; `Dockerfile` and `deploy/systemd` target Linux. Any MT5-based adapter breaks the phase-12 deployment gate's platform assumption.
5. **Counterparty clause.** OGM ToB §23.1(i) names "automated or mass data entry system" and "Scalping" as Events of Default, actionable without notice at absolute discretion. `OPERATIONS_LEDGER.md` item before the first live fill; seek written pre-clearance.
6. **No negative balance protection at OGM.** "All negative balances are payable" (§1.3, §6.11). The equity-floor/CHF-gap scenario work (GAP-0108) assumes losses stop at zero; at this entity they contractually do not.
7. **Financing is unmodelled at both candidate venues.** Dukascopy discloses a tiered, activity-dependent, marked-up method; OANDA OGM discloses nothing retrievable. At 30 min–48 h holds this is a first-order cost term with no calibration source.
8. **Feed-resolution parity canary** (carried from the prior pass, and reinforced): assert that no decision depends on tick detail finer than the live feed delivers. The hybrid makes this a look-ahead risk, not a latency risk.

---

## 8. SOURCES

**Primary — read directly in this session**
- OANDA v20 REST API Introduction (the division exclusion) — https://developer.oanda.com/rest-live-v20/introduction/
- OANDA Global Markets Ltd legal hub (entity, BVI FSC SIBA/L/20/1130) — https://www.oanda.com/bvi-en/legal/
- OANDA Global Markets Ltd Retail Clients Terms of Business, effective 2 June 2025 — https://legal.oanda.com/?code=ogm_terms_of_business&language=en
- OANDA Global Markets pricing (spreads, spread-only vs Core) — https://www.oanda.com/bvi-en/cfds/our-pricing/
- OANDA Global Markets spreads & margin — https://www.oanda.com/bvi-en/cfds/spreads-margin/
- OANDA OGM Margin Rates, 28 Aug 2026 (888:1, min ticket sizes) — https://www.oanda.com/assets/documents/1261/OANDA_OGM_Margin_Rates_20260828.pdf
- OANDA Global Markets platforms (MT5 / TradingView / app; no API) — https://www.oanda.com/bvi-en/cfds/platforms/
- OANDA divisional spread API (OC / OEL / OAP / OGM=HTTP 500) — https://labs-api.oanda.com/v1/spreads/spread-stability-and-average
- Dukascopy Forex Trading (ECN, min deposit $100, 1:200, CHF 100k, country disclaimer) — https://www.dukascopy.com/swiss/english/forex/trading/
- Dukascopy Fee Schedule (commission tiers) — https://www.dukascopy.com/swiss/english/about/fee-schedule/
- Dukascopy Client Protection (esisuisse CHF 100,000, Slippage Control) — https://www.dukascopy.com/swiss/english/about/client-protection/
- Dukascopy Overnight Policy (central-bank basis, explicit markup, Trading Activity tiers) — https://www.dukascopy.com/swiss/english/forex/forex-trading-accounts/overnight/
- Dukascopy FIX API ("limited to FX only", FIX 4.4) — https://www.dukascopy.com/swiss/english/forex/api/fix-api/
- Dukascopy JForex (Java, strategies run locally) — https://www.dukascopy.com/swiss/english/forex/jforex/
- Dukascopy About (FINMA bank + securities firm; group entities) — https://www.dukascopy.com/swiss/english/about/
- Dukascopy MT4/MT5 trading fees — https://www.dukascopy.com/swiss/english/forex/mt4-accounts/trading-fees/
- cTrader Open API (Protobuf/JSON, official Python SDK `spotware/OpenApiPy`) — https://help.ctrader.com/open-api/
- MetaTrader5 Python package (Windows x86-64 wheels only) — https://pypi.org/project/MetaTrader5/

**Carried from the 2026-09-16 pass** (`archive/PARTIAL_oanda_execution_research_2026-09-16.md`, `archive/PARTIAL_execution_fidelity_dukascopy_vs_oanda_2026-09-16.md`) — OANDA Additional Disclaimer Dec 2025; OANDA Europe Order Execution Policy May 2026; OANDA US Customer Agreement Mar 2026; v20 order/transaction/pricing definitions; CFTC v. FXCM 2011; FCA Final Notice FXCM 2014; FCA CP18/38; FCA Occasional Paper 50; GFXC last-look report; Oomen 2017; Cartea et al. 2018; IG best-execution Apr–Jun 2024; CFTC PR 8224-20.
