# PARTIAL — SCOUT: prop-venue due diligence (checkpoint, 2026-09-24)

**Who asked, what:** the lead (Opus 5.5 session, five-agent edge pass, GAP-P12D-52) launched me as **SCOUT** under
`FIVE_AGENT_BRIEF_2026-09-24.md` §0 + §1. Fresh context, no subagents. Mission: from primary sources, decide where a
fully autonomous, unattended, Linux-server-hosted Python engine can legally and practically earn payouts on a
~$5-10k funded account, and so where the owner's DEMO should run. Firms: FTMO, FundedNext, The5ers, Apex Trader
Funding + at most six others. Deliverables: per-firm quote matrix, prop-fit pre-mortem of ACIS as built,
verification of the 2026-09-17 venue pass's unverified claims (incl. OANDA practice for a Kenyan), ranked
recommendation, demo-venue recommendation (flag SPEC §15 deviation), draft platform_rules.yaml entries +
corrections (text only), draft emails. Final report: `archive/RESEARCH_PROP_VENUES_2026-09-24.md`.
Repo is read-only for me except this file and the final report. WebSearch cap 45.

**Status:** repo reading DONE; web research STARTING (0/45 searches used at this checkpoint).

## Repo findings so far (pre-mortem inputs, verified by file:line)

1. **Equity floor halts a ~$6k account at start-up.** `config/guardrail_limits.yaml:13` `equity_floor_usd: 9000.0`
   ("dev/paper account assumed 10k start"); `core/risk/guardrails.py:220`
   `equity_breached = ctx.equity < Decimal(str(self._limits.equity_floor_usd))` -> flatten + global HALT. Any
   account with equity < $9,000 (a $5k or $6k product) is halted at the first evaluation. Human-only fix
   (guard-integrity law). On a $10k product the floor sits at -10%, i.e. at the firm's own max-loss line.
2. **A platform DAILY loss limit cannot be expressed.** `core/risk/guardrails.py:122` — every platform rule is
   appended with `resets_daily=False` ("platform rules never reset daily"). `DrawdownRule` (`config/schemas.py:450`)
   has no reset instant, no timezone, no "% of initial balance" vs "% of anchor" distinction, no
   "higher of balance/equity" basis. The current `ftmo`/`atlas_funded`/`fundednext` entries model the firm's
   daily loss as `trailing/intraday/equity 5%`, which ACIS computes as a 5% trailing drawdown from the
   ALL-TIME equity high-water mark (never resets) — far stricter than any firm's daily rule, and each breach is a
   global HALT with human-only resume.
3. **Sizing is below the venue minimum lot.** `config/system_config.yaml:3` `base_unit_usd: 1000.0`;
   `core/governor/capital_governor.py` raw_usd = base_unit x conviction x liq x corr x regime x marginal_alpha
   (<=1.5) x vol_norm (<=1) x taper; quantised to 0.01 UNITS (`capital_governor.py:291`), never to the venue
   lot step. Max notional ~$1,500; EUR/USD ~925-1,390 units = 0.009-0.014 lots. `core/execution/orchestrator.py:136-152`
   `_capable_venues` never checks `d.min_lot` or rounds to `d.lot_step`. So a real venue with a 0.01-lot (1,000-unit)
   minimum would reject most orders. And $1k notional per trade can never reach a 8-10% profit target in any
   realistic time: it is a paper-safety size, not a prop size.
4. **Order firehose.** GAP-0075: the composed loop opens a new position every tradeable tick; the position-aware
   re-entry gate exists (`test_position_accounting_gates_reentry`) but no production runtime consumes it (engine
   `ExecStart` empty). Any firm with a request cap (FTMO reportedly 2,000/day) is breached within minutes.
   Also `config/system_config.yaml` execution: orders >= 1.0 lot are split into jittered fragments
   (`fragment_threshold_lots: 1.0`, size jitter 0.85-1.15, time jitter 0.5-3 s) — more requests per order.
5. **Daily boundary.** Engine day = 17:00 New York (`core/risk/guardrails.py:62-66`, `trading_day`); FTMO
   reportedly resets at 00:00 CE(S)T. Engine daily limit 2% (`guardrail_limits.yaml:4`).
6. **Account currency hard-coded USD** (`core/governor/units.py` `ACCOUNT_CCY = "USD"`).
7. Enabled instruments today: EUR_USD, USD_JPY only (`config/instruments.yaml`); 6 declared disabled.

## Prior pass (2026-09-17) — what it left unverified (to close now)
FTMO Open-API permission; FTMO T&C 5.3.4 0.7% non-USD adjustment; OANDA v20 for OGM (BVI); OANDA PRACTICE for a
Kenyan; Atlas/Kenya; The5ers bulk trading; FundedNext everything; Apex futures-only + automation; reputations;
Alpha Capital Group (cTrader); DXtrade/Match-Trader API reach.

## Web findings so far (checkpoint 2; 5/45 searches used; all fetched 2026-09-24)

**FTMO (all (a), firm's own pages):**
- 2,000 cap CONFIRMED: https://ftmo.com/en/forbidden-trading-practices/ (modified 2026-02-02): "automated robots / EAs
  ... more than 2,000 server requests per day on individual simulated trades or pending orders being opened,
  modified, or closed". FAQ (modified 2026-05-27): "Platform servers have 200 orders at a time and 2000 max
  positions per day limitation." Algo/EAs permitted ("discretionary trading, algorithmic trading, EAs, etc.").
- Open API: https://ftmo.com/en/trading-platforms/ (modified 2026-08-31): "Developers can also integrate apps using
  the Open API." VPS: FAQ (2026-08-24) "The use of VPN/VPS is also generally allowed" (US geolocation excepted).
- Rules: 2-Step 10%/5% target, 5% daily (of initial, reset 00:00 CE(S)T, equity incl. floating), 10% static,
  4 min days; 1-Step 10% target, 3% daily, 10% EOD-trailing max loss, Best Day <= 50% (trading-objectives, 2026-05-13).
- Weekend/news restrictions: Standard FTMO Account only (close before weekend / >2 h breaks; +-2 min on targeted
  news incl. SL/TP triggering = breach). Swing exempt; Swing is 2-Step only; evaluation unrestricted.
- T&C (LAST UPDATED 4 AUGUST 2026, PDF extracted): 5.2 "No actual trading is taking place"; 5.3.4 0.7% currency
  conversion adjustment CONFIRMED verbatim; 7.3 discretion; 7.5 Risk per Trade Idea; 9.4.6 "use automated means to
  view, display or collect information available through the Website, the Services or the Content" (ambiguity).
- Kenya NOT on restricted list (https://ftmo.com/en/faq/who-can-join-ftmo/, modified 2026-02-13).
- Payouts: bank wire, Visa Direct/Mastercard Send, Skrill, crypto; first claim day 14; 2-Step 80% (90% w/ scaling),
  1-Step 90%; 2-Step fee refundable with first reward, 1-Step not. Free Trial unlimited.
- FTMO completed acquisition of OANDA Global Corporation 2025-12-01 (press release 2025-12-02); FTMO Futures
  launched 2026-09-17 (automation permitted but NO positions past end of trading day -> intraday only).

**FundedNext (a):** Lead 3 CONFIRMED. help article 8020763 (modified 2026-09-08): "FundedNext does not allow the use
of EAs or automated trading on the cTrader and Match-Trader platforms regardless of account size"; EAs MT4/MT5 only,
< $50k, paid add-on; general-rules page: "Both EAs and VPS are allowed in 5K-25K accounts. EAs and VPS each require
their own paid add-on". Prohibits statistical arbitrage on related instruments (hits PAIR_DIVERGENCE), "Quick
Strike" (<30 s) >= 30% of profit, one-sided betting ("opens multiple trades in the same direction"), hyperactivity.
Stellar 2-Step: 5% daily of initial (00:00 server time), 10% max, 5 min days. Kenya NOT restricted (list: DPRK,
Myanmar, Belarus, Iran, Russia). Entity FundedNext Ltd, Comoros. States it "monetize[s] the trading flow".

**The5ers (a):** Lead 4 CONFIRMED. Prohibited practices page: "Bulk trading, is when multiple trades are open
simultaneously." T&C (Last update Sep. 23rd 2026): "no Automated Trading Software may be used unless the Company
has given prior written approval ... may require advance testing". Platform: "Mt5 Hedge" only (High Stakes,
Hyper Growth). High Stakes: 5% daily from max(prev-day close balance, equity) at 00:00 server time; 10% static.
Kenya NOT in Forbidden Territory list.

## Checkpoint 3 (21/45 searches used)
- **Apex: DISQUALIFIED, three ways.** Its own server answered this laptop (egress IP geolocates to Nairobi, KE, via
  ipinfo) with "Sorry but you are in a country that has been blocked from accessing our services." Wayback capture
  2026-03-25 of /help-center/getting-started/prohibited-activities/ (page modified 2026-03-13): "No Automation or
  Algorithm Usage allowed" + "Holding open trade positions through the market close" prohibited. Products are
  Tradovate/Rithmic/WealthCharts futures, 25k-150k.
- **Topstep: lead CONFIRMED** (help.topstep.com TopstepX API Access, modified 2026-09-17): "All trading activity must
  originate from your personal device. The use of VPS, VPNs, and remote servers is prohibited ... your server can
  watch and record, but it cannot trade." Live Funded cannot use the API.
- **OANDA:** v20 exclusion of OANDA Global Markets re-verified today; OANDA routes a Kenyan visitor to /bvi-en/, whose
  demo is an "OANDA Global Markets MT5 demo account" (MT5 login by email). The legacy fxTrade demo gate returns
  HTTP 523. So a NEW v20 practice account is not obtainable by a Kenyan through the normal flow (inference from (a)
  pieces); an existing legacy practice token may still work -> the one-call test stays the decider.
- **Atlas:** still no country list (article of 2025-02-20: "If your country is restricted, you may not be able to
  proceed beyond the KYC stage"). Bans trades < 3 min; "Trading from geographically inconsistent locations without
  prior notice or approval" prohibited (hits a remote VPS); automation "that ... spam market/limit orders" banned.
- **Alpha Capital: DISQUALIFIED** (help article, 2026-09-07): "Automated EAs that execute trades independently,
  without human oversight, are strictly prohibited and will not be approved under any circumstances"; no EAs on
  cTrader/DXtrade/TradeLocker.
- **E8 Markets: CANDIDATE.** "Tools you can use ...: Algo, EA, Bots and Indicators" (2026-05-14); caps "Server
  requests per day: 2000", "Max positions per day: 2000", open-order cap 100; HFT = >50% of trades held < 1 min.
  Platforms TradeLocker, MatchTrader, cTrader (+$10 if account < $100), MT5. Kenya NOT restricted for Classic
  markets (restricted only for E8 futures). E8 One: 6% target, 3% daily (of initial, from day-start balance at
  00:00 server), 4% dynamic (closed-balance trailing, locks at initial). E8 Pro: 8% target, 2% daily PROFIT cap,
  2.5% daily DD, 8% static. Single-phase. Rules change often ("Updated today").
- **cTrader Open API (a):** "by default, it is supported by all trading accounts of any cTrader-affiliated brokers";
  demo and live; 50 req/s, 5 req/s historical; SDKs C#/Python, JSON needs none. Proto (last commit 2025-11-13):
  stopLoss "Not supported for MARKET orders" (re-verified); ProtoOAReconcileReq returns protection orders.
- **Prices (embedded pricing data, 2026-09-24):** FTMO $10k 2-Step EUR 89, 1-Step EUR 79 (fees stated in EUR);
  FundedNext Stellar 2-Step $6K $59.99 list (targets $480/$300, daily $300 from prev-day close balance, max $600,
  5 days, first withdrawal 21 days); The5ers High Stakes $5K $39 / $10K $78 (sale $35/$69).
- **Reputation:** MFF case dismissed with prejudice 2025-05-13, CFTC sanctioned (Willkie, (b)); receivership from
  2023-08-29. MetaQuotes Feb 2024 licence pulls (Finance Magnates (b)). MyFundedFX ceased prop 2026-02-06 ((c)).
  Payout-dispute evidence for FTMO/FundedNext/The5ers is forum/aggregator only ((c)); The5ers "bulk trading"
  enforcement on payout requests reported May/Dec 2025 ((c)).
- **Pre-mortem additions (code):** engine daily limit = session entry-halt only, clears at next session boundary,
  no flatten (`core/risk/guardrails.py:245-251`, `capital_governor.py:123-131`); platform-limit breach = HALT all, no
  flatten; weekend 2-h entry ban only when `weekend_holding_allowed` is false (`capital_governor.py:353-356`) ->
  on FTMO Swing ACIS would open trades <= 2 h before the weekend close = FTMO forbidden "gap trading".
- **Correction to prior pass:** FTMO 0.7% hits 4 of 8 declared instruments (quote ccy != USD: USD_JPY, USD_CHF,
  USD_CAD, EUR_GBP), not 5; of the 2 ENABLED instruments, 1 (USD_JPY).

- **NEW code finding (reproduced by script, read-only import):** platform drawdown anchors live only in memory
  (`core/risk/guardrails.py:90` `_anchors`), `core/risk/store.py` persists halts/snapshots/taper/alpha but NOT the
  anchors; after a simulated restart at -6% the static 10% rule, the trailing rule and the engine daily all measure
  0.0% -> a restart RELAXES every platform limit (contradicts GAP-0050 "a restart is never a relaxation"). Also:
  static anchor = first observed basis, not the declared initial capital (`guardrails.py:72-73`).
- FTMO 2-Step Max Loss is tested on EQUITY (trading-objectives page) -> repo `ftmo` entry `basis: balance` is looser.
- FTMO Free Trial (ftmo.com/en/ftmo-free-trial/, 2026-05-12): 14 days, renewable, one at a time, cTrader available.

## Status: COMPLETE — superseded by `archive/RESEARCH_PROP_VENUES_2026-09-24.md` (2026-09-24)
Final report written; 21/45 WebSearch calls used. This checkpoint is kept only as the durability record the brief
requires (§0.4); the lead `git mv`s it with the brief when the pass closes.
