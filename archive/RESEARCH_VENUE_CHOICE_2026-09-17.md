# RESEARCH — Execution venue choice for ACIS (2026-09-17)

> **RESUME LINE (for a fresh session):** Brief = *"execution-venue analyst: decide where ACIS actually executes — OANDA, Dukascopy, a hybrid, or something else — for a Kenya-resident owner running a deterministic Python engine, 30 min–48 h holds, ~$10k modelled NAV, hard requirement of server-side stops."* Mid-pass the owner **decided on the prop-firm route (~$6,000 funded account; shortlist The5ers, FundedNext, Apex Trader Funding, FTMO)**, which demoted §1–§2 to background and made §3.1 the live section. **This document was checkpointed under an imminent usage limit; §9 lists exactly what is unfinished and how to resume.** Read-only pass: no engine code, config, spec or ledger file was modified, nothing was committed.

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

*(This section integrates two parallel primary-source sweeps: §3.1 the prop-firm route, §3.2 alternative retail brokers. Both returned. Like the rest of this pass they ran with **zero WebSearch budget** — every finding is a directly-fetched primary URL, and every "not found" means "not reachable this session", never "does not exist".)*

### 3.1 The prop-firm route — the owner's chosen path (decision taken 2026-09-17)

**Mid-pass the owner decided on the prop-firm route: a ~$6,000 funded account, shortlist The5ers, FundedNext, Apex Trader Funding, FTMO.** That decision demotes §1–§2 to background: the venue is then chosen *for* him by the firm, and the questions that matter become rule-fit, platform/API, and payout reliability. What follows is the prop research that completed; §9 records what the shortlist change left unresearched.

**All three firms researched are simulated environments.** This is the most important structural fact about the whole route and it is stated in their own terms, not inferred:

> "Simulated Trading simulates trading on financial markets… **No actual trading is taking place and there is no execution of trades in financial markets.**"
> — FTMO Challenge Terms and Conditions, cl. 5.2, last updated 4 August 2026 **(a) PRIMARY**

The5ers' T&C likewise describes "a simulated training environment" with "fictitious funds" that "do not represent any currency" **(a)**; Atlas describes "simulated capital in a simulated trading environment" **(c)**. **None of the three names its underlying broker or liquidity provider anywhere in its published terms (a, full-text searched).**

> ⚠️ **This inverts the operational-correctness design in `CLAUDE.md`.** Guard 3 (runtime ledger discipline) and the standing operational-referent audit both assume a *real broker fill* to reconcile the model against. On a prop account there is no external referent: the counterparty is the firm's own simulation, priced by rules it may change at discretion (FTMO T&C 7.3 reserves the right "to determine, at our own discretion, whether certain simulated trades, practices, strategies, or situations qualify as… a Forbidden Trading Practice"; cl. 5.6 reserves the right to modify any element of the service). **GAP-0001-style live-vs-modelled fill comparison cannot be performed against a prop account.** The prop route is a way to trade size without capital; it is *not* a validation environment, and it must not be allowed to substitute for one.

#### Hard-filter results

| | **FTMO** | **The5ers** | **Atlas Funded** |
|---|---|---|---|
| 30 min–48 h holds + weekends | **Only on Swing, which is 2-Step only** | ✅ | ✅ (explicit) |
| Custom Python drives the account | ✅ **best — cTrader Open API** | ⚠️ MT5 terminal bridge **+ written pre-approval** | ⚠️ MT5 bridge, **no API documented** |
| Server-side stops survive disconnect | ✅ | ✅ | ✅ (and risk rules push toward always-on stops) |
| Algo explicitly permitted | ✅ | ⚠️ only with prior written approval | ✅ **clearest statement of the three** |
| Kenya accepted | ✅ **verified against the published list** | ✅ **verified against the published list** | ❌ **(X) no list published at all** |
| Rule determinism for a kill-switch | Medium | **Low** | **High** |

#### The findings that actually decide it

1. **⛔ The5ers prohibits "Bulk Trading" — "multiple trades are open simultaneously"** (Prohibited Trading Practices page, **(a)**). An 8-instrument portfolio engine has multiple positions open essentially all the time. Taken literally this is **incompatible with the strategy**. Its "One-Sided Bets" rule ("consistently takes positions in one single direction") compounds it for a momentum system during a sustained USD trend. Combined with the written-approval gate and the fact that **The5ers publishes neither equity-vs-balance nor static-vs-trailing drawdown semantics (X)**, it is the **worst rule-fit of the three despite looking usable on paper.** Given the owner has shortlisted it, this is the single most urgent thing to clarify in writing before paying.

2. **💰 FTMO charges 0.7% of realised P&L on every non-account-currency position** (T&C 5.3.4, **(a)**): "a flat adjustment fee of **0.7% from the realised profit and loss** at the moment the position is closed… The adjustment reduces a realised profit and **increases a realised loss** accordingly." On a USD account that hits USD/JPY, USD/CHF, USD/CAD, EUR/GBP — **5 of the 8 declared instruments**. It is not a spread; it is a symmetric percentage haircut on |P&L|, applied hundreds of times a year. **It appears in no spread table and is currently absent from the harness cost model.** This is a first-order term for this strategy and must be modelled before any FTMO purchase.

3. **FTMO's 48-hour holds force the 2-Step Swing route.** Standard accounts: "you are required to close your positions shortly before the markets close for the weekend or if the rollover (market break) lasts longer than 2 hours" **(a)** — flatly incompatible. Swing removes all news and holding restrictions, but "is available exclusively within the FTMO Challenge: 2-Step" **(a)**, runs **1:30 leverage** (vs 1:100 Standard), and existing Standard accounts cannot be converted. Silver lining: on Swing there is **no news restriction at all**, so the unbuilt historical event calendar is not needed for FTMO compliance.

4. **FTMO's 2,000/day cap is ambiguous and could bite.** Its FAQ says "200 orders at a time and 2000 max positions per day"; its Forbidden Practices page says "more than **2,000 server requests per day**" **(a, both)**. At ~30 round trips/day the *position* count is a non-issue; the *request* count is not — a polling loop blows through it trivially. **If FTMO is chosen the engine must be event-driven off the streaming channel, not polling, with an instrumented request counter.** No page disambiguates the two **(X)**.

5. **Atlas has the most engine-friendly rules, and the one blocking unknown.** Daily limit recalculated "Each day at **Midnight UTC**… based on the **higher of your account's balance or equity**", "fixed for the following day — **it does not adjust intraday**"; max drawdown "**fixed from your starting balance**" (static) for every model except Instant Funded, whose trailing "locks at your initial balance" once 5% profit is hit **(a)**. Minimum hold **3 minutes** (a 10× margin for this strategy). Weekend/overnight holding explicitly permitted across all stages. News: evaluation unrestricted; funded restricts only trades *opened or closed* within ±5 min of high-impact releases — **"Trades that are already open and held through the news event are not impacted."** EAs explicitly allowed, including "Algorithmic trading systems – Designed to follow predefined risk management rules", with no prior-approval requirement and no numeric request cap. Pricing verified: 2-Step $10K **$79** / $25K **$160** / $50K **$240** / $100K **$443**. Payouts: crypto ≤$3,000 fee-free, Rise above that ($50 fee) — both workable rails for a Kenyan resident. **But Atlas publishes no restricted-country list at all — Kenya acceptance is UNVERIFIED (X), and that is the blocking question.**

6. **A sizing constraint the Governor must enforce at Atlas:** "One-Sided Risk Exposure" caps risk on a single trade at **50% of the account's daily drawdown limit** **(a)**. On a 2-Step account with a 5% daily limit that is a hard 2.5%-of-account cap per trade. Separately, an "Excessive Risk-Taking" breach triggers if "80% or more of your trades show excessive risk-taking or are placed without a stop-loss" — which *aligns* with §279, but makes the stop mandatory in practice.

7. **FTMO's discretionary correlated-exposure clause is the soft risk.** T&C 7.5 tests "Risk per Trade Idea" cumulatively across "a specific symbol (**or correlated symbols**)" **(a)**. USD/JPY, GBP/USD, AUD/USD, USD/CHF and USD/CAD are heavily USD-correlated; FTMO retains discretion to treat simultaneous same-direction USD exposure as a single oversized trade idea. The engine's linked-groups machinery (§9.5) is the right place to model this, but the rule is discretionary and therefore not fully modellable.

8. **Daily-boundary timezone mismatch at every firm.** FTMO resets at **00:00 CE(S)T**; Atlas at **00:00 UTC**. Neither is the engine's 17:00-New-York daily-loss boundary (master v2.14). Whichever is chosen needs a new `{zone, at}` entry in the risk layer — a real change, not a config tweak.

9. **❌ Nobody publishes spreads or commissions.** FTMO explicitly refuses: "The account specification can be seen directly in the trading platform… right-click on the relevant instrument, and choose 'Specification'" **(a)**. The5ers and Atlas publish none. **For a strategy with hundreds of round trips per instrument-year this is the largest unpriced variable in the entire comparison**, and it is resolvable only by opening a free trial and reading the specs off the platform. Treat it as a mandatory pre-purchase step.

10. **The5ers is MT5-only** (all program pages, **(a)**) — no cTrader, no documented REST/FIX. **Atlas runs TradeLocker, MT5 and Match-Trader**, with no API documented anywhere in its 68-article help centre **(X)**. **Only FTMO offers cTrader**, and therefore the only genuinely server-side API path on the shortlist.

#### The cTrader Open API is the reason FTMO leads on engineering

https://help.ctrader.com/open-api/ **(a) PRIMARY, read directly:** Protobuf or JSON over a persistent connection; **official Python SDK (`github.com/spotware/OpenApiPy`)**; "Perform all possible types of trading operations permitted in official cTrader applications" (→ order with attached stop); "Retrieve and process information about past, current and pending operations (including deals, orders and positions)" (→ **the post-reconnect reconciliation requirement, met natively**); real-time streaming plus historical bars; rate limits 50 req/s general, 5 req/s historical. Available to "anyone registered with a cTrader-affiliated broker".

**This runs on Linux, in-process, with no terminal and no Windows dependency** — it is the only option on the shortlist compatible with the existing `python:3.11-slim` Docker + systemd deployment, and it is the repo's already-ratified next adapter (§7.5 order: cTrader → DXtrade → TradeLocker → Match-Trader → IBKR → futures gateways). **The ratified adapter order was right.**

⚠️ **(X) Unverified and high-value:** no FTMO page states whether connecting via the **Open API** (rather than the cTrader GUI) is permitted account usage. FTMO advertises the Open API on its own platforms page and nothing in its Forbidden Practices list prohibits API connectivity — but **this is the single most important question to put to FTMO in writing before paying.**

#### Alternatives touched, and the two shortlist firms that could not be reached

- **Alpha Capital Group** — confirmed to offer **MetaTrader 5, cTrader, TradeLocker and DXtrade** **(a)**, i.e. the only alternative found that matches FTMO's API strength. Its drawdown rules, hold-time rules and restricted-country list were not reached **(X)**. **Worth a dedicated pass specifically because of cTrader.**
- **Funding Pips** — HTTP 429 on both attempts, help centre 404. Not assessed.
- **Blueberry Funded** — bot-mitigation interstitial. Not assessed.
- **E8 Markets** — not reached.
- **FundedNext (shortlisted by the owner)** — **NOT RESEARCHED.** The homepage confirms only that it offers "prop trading challenge accounts for **CFDs and Futures**" with "up to 95% reward share" in "**a simulated environment**" **(a)**; `/faq` returns 404 and no rules page was reachable before the checkpoint. Platforms, drawdown semantics, news/weekend rules, consistency rule, minimum trading days and Kenya acceptance are all **unknown**.
- **Apex Trader Funding (shortlisted by the owner)** — **NOT VERIFIED; both `apextraderfunding.com` and `support.apextraderfunding.com` returned HTTP 403** to this session. ⚠️ **The coordinator explicitly asked whether Apex is futures-only rather than FX, and I must not answer that from memory.** What can be said honestly: every platform Apex is publicly associated with — **Rithmic, Tradovate, NinjaTrader** — is an exchange-traded **futures** order-routing stack with no spot-FX capability, which is strong circumstantial evidence for futures-only, graded **(c) UNVERIFIED**. **If that is right, Apex is disqualified for this system as it stands:** ACIS's enabled universe is spot FX and spot gold; futures would mean CME FX futures (6E/6J/M6E/M6A) and GC/MGC, which is a *different instrument class* carrying master §3.7's roll-or-flatten lifecycle risk (still open as **GAP-0109**) and a §7.5 adapter tier the spec deliberately ordered **last**. **This must be confirmed before Apex gets any further consideration.**

#### One economic note on a ~$6,000 funded account

At the owner's stated size the evaluation fee is a large fraction of the capital at risk: Atlas's verified 2-Step $10K challenge is **$79**, i.e. ~1.3% of a $6,000 notional account, and it is **not refundable at Atlas (X — refundability not stated)** while FTMO's 2-Step fee **"may be refunded with the first Reward withdrawal"** **(a)**. Against that, §4's arithmetic still applies to the *funded* account: at the prototype's ~1,800 round trips/year and L≈2, modelled trading costs run to tens of percent of account equity per year. **A prop account does not make the turnover problem go away — it makes it someone else's money and adds a hard 4–5% daily kill-switch on top.** At ~900 trades/instrument-year the system would very likely hit a prop daily-loss or max-drawdown breach before it hit a profit target, and a breach at a prop firm is terminal (fee forfeited, account closed) where at a personal account it is merely a drawdown.

### 3.2 Alternative retail brokers — and the finding that beats both OANDA and Dukascopy

**The CMA Kenya register changes the answer.** Read directly at `https://licensees.cma.or.ke/licenses/5/` — **NON-DEALING ONLINE FOREIGN EXCHANGE BROKER (a) PRIMARY**. Fourteen licensees, of which two matter here:

| Lic. | Entity |
|---|---|
| **128** | **Pepperstone Markets Kenya Ltd** |
| **199** | **IC Markets (KE) Ltd** |

Others on the register: EGM Securities (FX Pesa) 107, Scope Markets 123, Exinity Capital East Africa 135, HFM Investments 155, Windsor Markets Kenya 156, Exness KE 162, Ingot Ke 173, Admirals KE 178, FP Markets 193, Anzo Capital 219, TPXMGLOBAL Kenya 233, Ava Trade Kenya 262. Separately, `/licenses/17/` (DEALING online FX): Empire FX Trade 203, CC Kenya Securities t/a Capital.com 244.

**What a CMA-licensed local entity buys him:** local recourse under the Capital Markets Act, the Capital Markets (Online Foreign Exchange Trading) Regulations 2017 and the Conduct of Business (Market Intermediaries) Regulations 2011 — both brokers' Kenyan T&Cs name these as the governing client-money rules **(a)**; KES as a base currency and fee-free wire via a Kenyan bank at IC Markets **(a)**; and **leverage set by the local entity at 1:400** at both, not the 1:500 offshore or 1:30 EU figure. **Neither lists M-Pesa on any reachable page (X).** **Whether Kenya's Investor Compensation Fund extends to online FX brokers is unverified — assume it does not until proven.**

#### The grid

| | **IC Markets (KE)** | **Pepperstone Kenya** | **IBKR (IB LLC)** | **LMAX (Mauritius)** | **Saxo** |
|---|---|---|---|---|---|
| Kenyan can onboard | ✅ CMA 199; site redirects Kenyans to the KE entity **(a)** | ✅ CMA 128 **(a)** | ✅ on IBKR's own country list **(a)**; entity = IB LLC **(b, inferred)** | ✅ Kenya in the application dropdown **(a)** | ❌ **no African country in the selector; "If your country is not listed, we are currently unable to open an account" (a)** |
| Client money | Pooled + segregated **(a)** | Trust account, segregated **(a)** | SIPC — but spot FX is not a security and is likely outside it | ❌ **title transfer: "we will not hold such money in a bank account which is separate from our own money… In the event of our insolvency you rank as a general creditor" (ToB 18.2) (a)** | Danish Guarantee Fund (moot) |
| Negative balance protection | ❌ not in contract **(a)** | ✅ **T&Cs Apr 2026 v5 cl. 6.2 (a)** | n/a | ❌ **(a)** | unverified |
| Min deposit | $200 **(a)** | **$10** **(a)** | $0 **(a)** | MU not published | moot |
| Commission | cTrader **$3.00/100k/side → $0.60 RT** on 10k units **(a)** | cTrader **$6 RT/lot → $0.60 RT**; scales pro-rata below 1 lot **(a)** | **0.20 bps, min $2.00/order** **(a)** | 0.0025%/side → $0.55 RT **(a)** | USD 1 minimum ticket fee **(a)** |
| **All-in RT, 10,000 units EUR/USD** | **≈$0.70** | **≈$0.70** | **$4.00+** | $0.55 + spread + **$0.50/RT amortised data fee** | $1.00–3.00 |
| XAU/USD RT ($10k notional) | ≈$1.50 **(a)** | ≥$1.40 **(a)** | $4.00 + 1.1% p.a. carry, **IBUK entity only** | unknown | not published |
| Server-side stops | ✅ **+ "freeze level of 0", no minimum stop distance (a)** | ✅ **(a)** | ✅ held in IBKR's system (simulated, not native) | ✅ at LMAX Global — ⚠️ **attached SL/TP not available over FIX; Cancel-on-Disconnect exists** | ✅ |
| Unit granularity | 0.01 lot = 1,000 units **(a)** | 0.01 lot = 1,000 units **(a)** | integer base-currency units (excellent — but cost kills it) | 1,000 units / 1 oz **(a)** | native units |
| Python API | ✅ **cTrader Open API + documented cTrader FIX** **(a)** | ✅ cTrader Open API **(a)** | ✅ Web API / TWS API | ❌ **FIX 4.4 + .NET/Java only; balance & positions impossible over FIX** | ✅ REST+WS — ❌ **20-min token, no cert auth for retail** |

#### Why the other four are out

- **Interactive Brokers — ruled out on cost, decisively.** Commission is 0.20 bps of trade value with a **USD 2.00 minimum per order** **(a)**. On $10,000 notional 0.20 bps is $0.20, so the minimum binds: **$4.00 per round trip = 4.0 bps**, roughly **10× a raw-spread cTrader broker**, and it stops binding only at $100,000 notional per order. Worse for this system: *"Orders that persist overnight will be considered a new order for the purposes of determining order minimums"* **(a)** — a resting protective stop that survives the day re-incurs the minimum. Two further operational hazards: a **10 req/s** global limit with an IP penalty box, and *"A single username can only have one brokerage session active at a time across all IB platforms"* **(a)** — logging into Client Portal by hand kills the algo's session. IBKR is excellent at ≥1 standard lot; its FX pricing is structurally hostile to the fine-grained unit sizing that is hard requirement (3). (Also: US Spot Gold is US-residents-only; a Kenyan would need **IBKR UK unallocated XAUUSD**, and whether an IB LLC client can reach it is **unverified (X)**.)
- **Saxo — apparently cannot onboard a Kenyan at all.** No African country appears in the country selector, and the help centre states outright that an unlisted country cannot be opened **(a)**. Even if eligible, a **20-minute access token / 40-minute refresh token with certificate auth reserved for "select IBs and White Label Clients"** means a >40-minute outage needs a human at a browser — disqualifying for an unattended engine.
- **LMAX — takes Kenyans, into the entity with no client-money segregation.** LMAX Broker Mauritius Terms of Business §18.2 is a **title-transfer clause**: the money becomes theirs and the client ranks as a general creditor on insolvency **(a)**. "Segregat", "retail", "negative balance" and "compensation" appear **zero times** in the 45-page document. Add a **$300/month market-data fee** (≈36% of a $10k NAV), no published spreads anywhere, and the fact that **balance and positions are not retrievable over FIX** — LMAX's own FAQ directs you to write a .NET or Java program, i.e. a JVM sidecar beside the Python engine.
- **CME micro FX futures — ruled out on sizing, not cost.** One M6E ≈ **$14,500 notional ≈ 1.45× the entire account**, in indivisible 1-contract steps: a risk-targeted sizer wanting ~$12,500 must round to 0 or 1, a quantisation error of 100% or +16%. MGC micro gold ≈ 4× NAV. Coverage breaks (the JPY micro is **MJY**, not M6J; **there is no EUR/GBP future at all**), **MJY is inverse-quoted** so long USD/JPY = short MJY and every price, ATR, stop distance and PnL sign inverts, and quarterly physical-delivery rolls force four exogenous flattenings per instrument-year — making GAP-0109 load-bearing rather than optional. And the cost intuition is backwards: M6E ≈ 1.4 bp vs cTrader Raw ≈ 0.6–0.9 bp. ⚠️ **Every CME page returned 403 to this session — the contract specs are AMP Global Clearing's republication (b), not CME primary.**
- **FXCM** — international clients are served by **Stratos Global LLC (St Vincent & the Grenadines)**, whose FSA does not license or supervise forex brokers, and FIX API needs a **$5,000 minimum balance** (half the NAV). **Darwinex Zero** is a track-record programme at €45/month, not an execution venue.

#### ⚠️ The cTrader finding that lands directly on ACIS code

From Spotware's own `OpenApiMessages.proto`, `ProtoOANewOrderReq`, **verbatim (a) PRIMARY**:

```
optional double stopLoss = 11;  // The absolute Stop Loss price. Not supported for MARKET orders.
optional int64  relativeStopLoss = 19;  // Specified in 1/100000 of unit of a price.
        // For BUY stopLoss = entryPrice - relativeStopLoss, for SELL stopLoss = entryPrice + relativeStopLoss.
```

**You cannot attach an absolute-price stop to a MARKET order on cTrader.** `SizedOrder.stop_loss` is an absolute price; it must be converted to an integer *distance* in 1/100000 price units, and that distance is applied to the **actual fill price** — so a slipped fill silently shifts the resting stop away from the level the Risk Monitor computed. The alternatives are worse: a pending order with an absolute stop, or market-in-then-`ProtoOAAmendPositionSLTPReq`, which leaves a naked window and violates §279 outright. **This needs an explicit conversion layer plus a post-fill assertion that the resting stop is within tolerance of the intended price.** It is a design constraint on the ACIS-13 cTrader adapter, not a detail — and it is the kind of thing that would have been discovered at integration time, expensively.

Other verified cTrader Open API mechanics **(a)**: `live.ctraderapi.com:5035` protobuf / `:5036` JSON, both TCP and WebSocket; OAuth 2.0 with one-time browser consent then refreshable tokens (suitable headless); 50 req/s general, **5 req/s historical**, heartbeat ≤10 s; `ProtoOAReconcileReq` returns open positions + pending orders and `ProtoOADeal` carries both `volume` and `filledVolume`, so **partial fills are first-class** and the reconnect-reconciliation requirement is met natively; `ProtoOAGetTrendbarsReq` covers M1…MN1 — ⚠️ **no H2/H6/H8 and no tick-bar period, so any such bar must be aggregated, not fetched.**

⚠️ **SDK health:** the official `ctrader-open-api` (spotware/OpenApiPy) is Twisted-based, latest non-yanked release **0.9.2, 26 Jun 2024** (0.9.3 yanked) — ~27 months stale. Spotware's own docs say *"If you intend to use JSON, there is no need to use our SDKs"*. **For a deterministic fast loop, hand-rolling a thin JSON/WebSocket client on port 5036 is almost certainly better than pulling a Twisted reactor into the decision path** — and it keeps the §16 adapter-tier SDK exception unused.

#### One contractual term that is a blocker

**IC Markets (KE) T&Cs cl. 3.1(l) (a) PRIMARY, verbatim:** *"an Open Position must remain open for the minimum period of time as determined by us and cannot be Closed Out by you during this period."* **The period is not stated anywhere in the document.** A 30-minute-hold strategy is directly exposed to an unquantified, unilaterally-determined minimum holding period. **Get this in writing before funding.** Pepperstone Kenya has no equivalent term and a *narrow* algo clause (manipulation and latency abuse only) — a meaningful contrast with OANDA BVI's broad "automated or mass data entry system" Event of Default.

#### A live external-referent defect this sweep turned up

v20's own `InstrumentFinancing.financingDaysOfWeek` shows **day-of-week rollover charging, not per-second accrual (a)**. **If the ACIS financing/carry model encodes per-second OANDA financing, that is a spec-vs-world error** of exactly the class §13/§5 care about. Worth a gap entry regardless of which venue wins, since the carry model outlives the adapter choice.

#### Spread data: verified for nobody

**Commissions were verified for every venue; average spreads for none.** Pepperstone publishes average-spread tables with a stated period but **the numeric rows are client-side JS and absent from the served HTML** across four pages. IC Markets' table renders server-side and is **arithmetically self-contradictory** — EUR/USD Standard MIN 0.8 against Standard AVG 0.1, an average below its own minimum; minors reconcile (`Std AVG = Raw AVG + 1.00`), majors do not. **Reject those cells.** LMAX, OANDA BVI and Saxo publish nothing fetchable.

> **Recommendation: do not take any published spread into the cost model.** The repo already holds 2.79 B Dukascopy ticks and a working harness. Capture a week of live top-of-book from a demo token at the shortlisted broker and measure the spread distribution directly. That is cheaper and more honest than any broker's table, and it is precisely what the operational-referent guard exists for — and it is the only thing that will close GAP-P12D-41 honestly.

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
5. **The 8-instrument case is far worse, and it is the one the spec declares.** §4's table counts only the two *enabled* instruments (~1,800 RT/yr). The declared universe is eight. At ~900 round trips per instrument-year across all eight — **7,200 RT/yr** — the second sweep's arithmetic at 10,000 units per trade gives **≈$5,040/yr at the cheapest venue found (cTrader Raw, ≈$0.70/RT), i.e. ~50% of a $10,000 NAV**, and ≈$28,800 (288%) at IBKR. Even the two enabled instruments alone cost ~$1,260/yr ≈ 12.6% of NAV at the best venue. **The venue choice moves this by roughly ±15%; the turnover and size assumptions move it by 5–10×.**

   > **Concrete next action that outranks choosing a venue:** re-run the §14 honesty gate with a per-round-trip cost floor of **0.7 pips EUR/USD equivalent** wired in, and ask the walk-forward whether the edge survives it. If it does not, the answer is fewer and larger trades — not a cheaper broker.

6. **Financing is the term nobody has priced.** At 30 min–48 h holds a meaningful fraction of positions carry overnight. Dukascopy publishes its method *and its markup*; OANDA BVI publishes neither. On carry-negative pairs held two nights, financing can rival the spread. **This is an open hole in the cost model at both venues.**

---

## 5. RECOMMENDATION

### 5.1 The ranking

The owner's mid-pass decision (prop route, ~$6,000 funded account) changes the ranking, so both are given — the second is the one that now binds.

**Given the prop-firm decision, ranked:**

1. **FTMO — 2-Step Swing, on cTrader via the Open API.** The only shortlisted firm with a real server-side API and an official Python SDK; the only one compatible with the existing Linux Docker/systemd deployment; Kenya verified accepted against the published list; fee refundable on first payout; Swing removes every news and holding restriction, which also removes the need for the unbuilt event calendar. **Two conditions before paying:** (i) get FTMO to confirm **in writing** that connecting via the cTrader Open API is permitted account usage; (ii) model the **0.7% non-USD realised-P&L adjustment** in the harness, because it is invisible in every spread table and touches 5 of 8 instruments.
2. **Atlas Funded.** Best rules of the three by a clear margin — midnight-UTC anchor on the higher of balance/equity, fixed intraday, static max drawdown from starting balance, explicit algorithmic permission with no approval gate and no request cap, 3-minute minimum hold, weekend holding explicit, open positions unaffected by news, verified low fees and workable crypto/Rise payout rails. **Blocked on one question: Kenya acceptance, which Atlas publishes nowhere.** Ranked second only because its Python path is an MT5 terminal bridge — a Windows dependency that breaks the current deployment — and because its help centre is internally inconsistent about its own model taxonomy.
3. **FundedNext — unranked, unresearched.** Confirmed only as a simulated CFD-and-futures prop firm. Cannot be placed until its rules are read.
4. **Apex Trader Funding — provisionally disqualified, pending verification.** Its associated platforms (Rithmic/Tradovate/NinjaTrader) are futures-only stacks. If that holds, it is the wrong instrument class for this engine and pulls in the §3.7 roll-or-flatten lifecycle risk (GAP-0109, still open) and the §7.5 adapter tier the spec deliberately put last.
5. **The5ers — recommend against.** Its published "Bulk Trading" prohibition ("multiple trades are open simultaneously") is prima facie incompatible with an 8-instrument portfolio engine; "One-Sided Bets" compounds it for a momentum system; automated trading needs prior written approval; and it publishes neither the equity/balance basis nor the static/trailing nature of its drawdown — the two facts an engine needs to model its own kill-switch. Usable only if it clarifies Bulk Trading in writing, and even then it is the least deterministic rule set on the shortlist.

**If the prop decision were reversed (personal capital), ranked — now fully researched:**

1. **Pepperstone Markets Kenya Ltd (CMA licence 128), cTrader, via the Open API.** CMA-licensed so there is local recourse; **contractual negative-balance protection (T&Cs Apr 2026 v5 cl. 6.2)**; **$10** minimum deposit; 1:400; 1,000-unit granularity; server-side stops; ≈**$0.70 all-in per round trip** on 10,000 units; a *narrow* algo clause covering manipulation and latency abuse only; and **no minimum-holding-period term**. It is the best combination of protection and API reach available to this owner.
2. **IC Markets (KE) Ltd (CMA licence 199), cTrader.** ~$0.10/round trip cheaper than Pepperstone (≈$720/yr at high turnover), the only broker found that **documents a retail FIX API** on cTrader, and it commits to a **"freeze level of 0" with no minimum stop distance** — which matters directly for resting tight protective stops. Ranked second only because of two contractual gaps: **no negative-balance protection clause at all**, and **cl. 3.1(l)'s unquantified, unilaterally-determined minimum holding period**, which is an unbounded risk to a 30-minute-hold strategy. **It moves to first if IC answers that in writing satisfactorily.**
3. **Dukascopy Bank SA** — the best *protections* on the list (FINMA bank, CHF 100,000 deposit insurance) and the only venue that collapses the backtest/execution data mismatch entirely. Held back by two things: FIX is FX-only so XAU/USD needs a Java JForex sidecar, and its commission tier at $10k equity erases the ECN cost advantage. **It becomes the right answer at ≥ $50k of personal capital**, and at ≥ $250k it is not close. (One cheap question worth asking: if the volume tier is assessed *monthly* rather than on equity, this system's turnover sits well inside the $18/million band and Dukascopy is materially cheaper than modelled — the assessment window is unverified.)
4. **OANDA Global Markets (BVI) on MT5** — the spec's named venue, but **not** via v20, which OANDA excludes from this division. Tight published spreads (1.0 pip EUR/USD ≈ 0.93 bps), easy onboarding, but: no negative balance protection, no compensation scheme, 0.01-lot sizing granularity, a Windows-only Python path, and a broad Event-of-Default clause naming automated systems. **Beaten on every axis by the two CMA-licensed cTrader brokers.**
5. **Ruled out: Interactive Brokers** (the $2.00 minimum commission per order makes it ~10× more expensive at 0.1 lot, and a resting overnight stop re-incurs it); **Saxo** (cannot onboard a Kenyan; and a 20-minute token with no retail cert auth); **LMAX** (Mauritius entity takes client money by title transfer — general creditor on insolvency — plus a $300/month data fee and no positions over FIX); **CME micro FX futures** (one M6E ≈ 1.45× NAV in indivisible steps, no EUR/GBP contract, inverse-quoted MJY, quarterly roll); **FXCM** (SVG entity, $5,000 FIX minimum); **Darwinex Zero** (not an execution venue).

### 5.2 The single most important trade-off

**Server-side API reach versus everything else.**

Every other axis on this comparison turns out to be second-order for this system at this size. Cost between venues is noise (§4: 0.04 bps/round trip at $10k — 0.14% of NAV per year even at the prototype's churn). Execution model is largely irrelevant at 30 min–48 h. Leverage is something the Governor should be *refusing*, not shopping for.

What is **not** second-order is whether a deterministic Python process running unattended on a Linux VPS can place an order with an attached server-side stop, and reconcile its positions after a reconnect, **without a Windows terminal in the loop.** Exactly one option on the whole shortlist does that: **cTrader Open API.** Everything else — OANDA BVI, The5ers, Atlas, Dukascopy's full instrument set — puts a GUI terminal or a JVM between the Risk Monitor and the venue's stop order. Under §279 and the §2 Layer Communication Law that is not a packaging detail; it is a new, unsupervised failure surface in the one path that is supposed to survive the engine vanishing.

That is why the ratified §7.5 adapter order (cTrader first) turns out to be correct, and why the spec's *primary* adapter (OANDA v20) turns out to be unavailable. **The spec was right about the direction and wrong about the first stop.**

### 5.3 The thing I would say even though it was not asked

§4's arithmetic is the uncomfortable part of this pass. At the prototype's ~900 trades/instrument-year, modelled costs run to roughly **a third of NAV per year at every venue examined** — and that is before the prop route adds a 4–5% daily kill-switch whose breach is terminal. Combined with the live ledger's own open findings (GAP-P12D-40: MEAN_REVERSION giving back almost exactly what TREND earns; GAP-P12D-41: the backtest priced on the wrong firm's book), **the venue is not currently the binding constraint on this system — turnover and the mean-reversion module are.** Choosing a venue is worth doing now because it unblocks adapter work and the cost calibration that GAP-P12D-41 needs. It should not be mistaken for progress on profitability.

### 5.4 What I need to know from the owner to firm this up

1. **Is the ~$6,000 prop account the whole plan, or a supplement to personal capital?** If prop is the only path, the operational-referent audit (guard 1) has no referent and the §14 out-of-sample record has to be earned somewhere else. If it is a supplement, the personal account should be chosen for *audit quality* and the prop account for *size*, and they need not be the same firm.
2. **Is XAU/USD actually in the v1 live universe?** It changes the answer materially — it disqualifies Dukascopy FIX, it is the instrument with the least-verified cost at every venue, and it is the one where a futures-only firm like Apex would fail hardest.
3. **Will he accept a Windows VPS?** If yes, MT5-based options (OANDA BVI, The5ers, Atlas) reopen and the ranking loosens. If no — and the existing Docker/systemd work says no — the field narrows to cTrader almost immediately.
4. **What turnover does he intend to run at?** §4 is a function of R. At R ≈ 300 the whole cost question is manageable at any venue; at R ≈ 1,800 no venue saves it.
5. **Is he willing to ask three firms a written question and wait?** The four blocking unknowns (FTMO/Open-API permission, Atlas/Kenya, The5ers/Bulk-Trading, and every firm's actual spreads) are all answerable by email or a free trial, and all four are cheap relative to the cost of picking wrong.

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
9. **cTrader cannot attach an absolute-price stop to a MARKET order.** `ProtoOANewOrderReq.stopLoss` is documented "Not supported for MARKET orders"; only `relativeStopLoss` (a distance in 1/100000 price units, applied to the *actual fill price*) is available. `SizedOrder.stop_loss` is an absolute price, so the ACIS-13 cTrader adapter needs an explicit conversion layer **plus a post-fill assertion that the resting stop is within tolerance of the intended level** — otherwise a slipped fill silently moves the stop away from what the Risk Monitor computed. Guardrail-adjacent (§279); belongs in the ACIS-06 conformance suite alongside GAP-P12D-42.
10. **The OANDA financing model may be wrong about the world.** v20's `InstrumentFinancing.financingDaysOfWeek` describes **day-of-week rollover charging, not per-second accrual**. If the carry model encodes per-second financing, that is a spec-vs-world defect, and it outlives the venue choice.
11. **No published spread is trustworthy for calibration.** Pepperstone's tables are client-side JS; IC Markets' table is arithmetically self-contradictory on majors (Standard MIN 0.8 vs Standard AVG 0.1); LMAX, OANDA BVI and Saxo publish nothing fetchable. **GAP-P12D-41 cannot be closed from published tables** — it needs a week of live top-of-book capture from a demo token at the chosen venue.
12. **cTrader trendbar coverage gap.** `ProtoOAGetTrendbarsReq` offers M1…MN1 only — **no H2/H6/H8 and no tick-bar period.** Any such bar in the backtest must be built by aggregation, and the adapter must not silently substitute a different period.

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

---

## 9. UNFINISHED — how to resume this pass

**Checkpointed 2026-09-17 under an imminent weekly usage limit.** Nothing below was abandoned for lack of interest; it was cut for budget.

**Tooling state that will shape a resume:** this session's **WebSearch budget was fully exhausted (200/200)** before this pass began. Everything above was reached by **direct WebFetch / curl against primary URLs**. "Could not verify" below therefore sometimes means *tooling gap*, not *does not exist*. A fresh session with search budget will close several of these quickly.

### 9.1 Returned after the first checkpoint, now folded in
- The alternative-broker sweep (IBKR / LMAX / Pepperstone / IC Markets / Saxo / CMA-Kenya register / CME micro FX) **completed and is integrated as §3.2**, with the personal-capital ranking in §5.1 rewritten accordingly. Its two highest-value findings — **the CMA Kenya register (Pepperstone 128, IC Markets 199)** and **the cTrader `stopLoss` "Not supported for MARKET orders" constraint** — are also reflected in §7.
- **New blocking question from that sweep, added to the list below:** IC Markets (KE) T&Cs **cl. 3.1(l)** imposes an unstated minimum holding period determined unilaterally by the broker. For a 30-minute-hold strategy that is the single contractual term most worth resolving before funding anything.

### 9.2 Blocking unknowns, in priority order
1. **(X) Apex Trader Funding: futures-only or does it offer FX?** Both `apextraderfunding.com` and `support.apextraderfunding.com` returned **HTTP 403** to this session. The coordinator explicitly said to verify rather than assume, so no answer is asserted. Circumstantial evidence only (its associated platforms Rithmic/Tradovate/NinjaTrader are futures-only stacks), graded **(c)**. **Resume via a search engine or a browser session, not WebFetch.**
2. **(X) FundedNext: everything.** Only the homepage was reachable ("prop trading challenge accounts for CFDs and Futures", "up to 95% reward share", "a simulated environment") — `/faq` is 404. Need: platforms (does it offer cTrader?), daily-loss and max-drawdown semantics (equity vs balance, static vs trailing, anchor time), news rules, weekend holding, minimum trading days, consistency rule, EA permission, restricted-country list, fee schedule, payout rails.
3. **(X) Does FTMO permit connecting via the cTrader Open API** rather than the cTrader GUI? Highest-value single question on the whole shortlist — it is what makes FTMO rank first. Ask FTMO support in writing.
4. **(X) Is Kenya accepted by Atlas Funded?** Atlas publishes no restricted-country list at all. Ask support in writing.
5. **(X) The5ers "Bulk Trading"** — does holding 8 simultaneous positions in different instruments breach it? Ask in writing before paying.
6. **(X) Actual spreads and commissions at every prop firm.** FTMO explicitly refuses to publish and directs you to the platform's Market Watch; The5ers and Atlas publish none. **This is the largest unpriced variable in the comparison.** Only resolvable by opening a free trial and reading the instrument specs off the platform. Do this before committing to any firm.
7. **(X) Alpha Capital Group's rules** (drawdown, hold time, news, restricted countries). It is the only non-shortlist firm confirmed to offer **cTrader** and is therefore the only candidate that could plausibly beat FTMO on the axis that matters most. Worth a dedicated pass.

### 9.3 Non-blocking, carried from §6
The OANDA-OGM and Dukascopy unknowns in §6 remain open but are now **secondary** given the prop decision. The two worth keeping alive regardless of route: **OGM's real (not "typical") spread**, because GAP-P12D-41's calibration target depends on it; and **financing/swap**, which is unmodelled at every venue examined and is a first-order cost term at 30 min–48 h holds.

### 9.4 Not done, and arguably should be
- **Payout reliability and reputation** for the four shortlisted firms was in the narrowed brief and was **not researched at all** — it needs secondary sources (Trustpilot, payout-proof aggregators, prop-firm failure history), and this session had no search budget. Note the live repo comment that **MyFundedFX shut in Feb 2026**, which is why `config/platform_rules.yaml` already carries 2–3 firms as insurance. Counterparty failure is a real risk class here and it is currently unassessed.
- **DXtrade and Match-Trader API reach** was not investigated. If FTMO's Open API answer comes back negative, these are the next place to look for a server-side API path, and they are the next two entries in the ratified §7.5 adapter order.
