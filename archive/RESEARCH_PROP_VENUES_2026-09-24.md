# RESEARCH — Prop-venue due diligence for a fully autonomous engine (SCOUT, 2026-09-24)

> **Who, what.** I am **SCOUT**, one of five agents in the 2026-09-24 edge pass (GAP-P12D-52), launched by the lead
> (the Opus 5.5 session that wrote `FIVE_AGENT_BRIEF_2026-09-24.md`). My binding brief is that file's §0 and §1.
> **Independence:** I ran in fresh context, launched no subagents, and changed no code, config, spec, ledger or test.
> I wrote only `archive/PARTIAL_PROP_VENUES_2026-09-24.md` (checkpoint) and this report.
> **Status:** finder, not clearer (A5). Every claim below is evidence to weigh, not an instruction (A9). Nothing here
> binds until the lead verifies it (A6). Every rule quoted is as of **2026-09-24**; prop rules change often.
>
> **Question.** Where can a fully autonomous, unattended, Linux-server-hosted Python engine legally and practically
> earn payouts on a ~$5–10k funded account, for a Kenyan resident? And therefore, where should the owner's demo run?

**Evidence grades (brief §0.4).** **(a)** a firm's own primary document, a regulator, or source code/API docs read
directly; **(b)** credible trade press or a law firm's case summary; **(c)** affiliate sites, forums, aggregators.

---

## Executive summary (10 bullets)

1. **Only two firms pass the hard filter.** I examined ten firms: the owner's four plus six others. Only two allow a
   self-built, unattended program to trade a *funded* account through an API that runs natively on Linux (cTrader Open
   API): **FTMO** and **E8 Markets**. Each has explicit algo permission and accepts Kenyan residents. **(a)**
2. **All five of the lead's leads are CONFIRMED** from primary text (§1):
   - Apex bans automation.
   - Topstep bans VPS and remote servers for order flow.
   - FundedNext bans automation on cTrader and Match-Trader.
   - The5ers bans "bulk trading" and requires prior written approval for automated software.
   - FTMO caps activity at 2,000 server requests per day. **(a)**
3. **Apex is out three independent ways.**
   - Its own server refused this laptop, whose IP geolocates to Nairobi: *"Sorry but you are in a country that has been
     blocked from accessing our services."*
   - Its rules say *"No Automation or Algorithm Usage allowed"*.
   - It is futures-only, and positions must be closed before the market close. **(a)**
4. **Ranked recommendation (§6):**
   1. **FTMO Challenge 2-Step, Swing, $10,000, on cTrader via the Open API.** Fee €89, refundable with the first reward.
   2. **E8 Markets (E8 Pro or E8 One), $5–10k, on cTrader.**
   3. FundedNext $6K. Automation only via a Windows MT5 terminal plus paid EA and VPS add-ons.
   4. The5ers. Only with written approval and a written bulk-trading clarification.
   5. Atlas. Blocked on Kenya eligibility.

   **(a)** for the rules; the ranking is my judgement.
5. **Demo venue (§7).** A new OANDA **practice** account with v20 API access is very likely *not obtainable* by a Kenyan
   resident:
   - v20 is "available to all divisions except OANDA Global Markets" (a).
   - A Kenyan visitor is routed to OANDA Global Markets, whose demo is an **MT5** demo (a).
   - The legacy v20 demo sign-up gate returns HTTP 523 (observed).

   Run the one-call legacy-token test anyway. I recommend the **FTMO Free Trial on cTrader via the Open API** as the
   demo of record: free, 14 days, renewable, and on the destination platform and feed. That is a **SPEC §15 deviation
   the owner must ratify.**
6. **ACIS as built cannot run on any prop account today (§5).** Verified by `file:line` and one script:
   - The **$9,000 absolute equity floor** halts any account under $9,000 at start-up. On a $10k account it sits exactly on
     the firm's max-loss line, so it gives no pre-breach protection.
   - Typical orders are **about 330 units, roughly a third of the 0.01-lot minimum**, and nothing rounds to the lot step.
   - The GAP-0075 firehose sized **about 2,700 orders per trading day** on the planted run, against a 2,000/day cap.
   - Platform **daily** loss rules cannot be expressed in the schema.
   - **NEW:** a process restart re-bases every platform drawdown measure to 0%.

   **(a)**
7. **FTMO's forbidden "gap trading" practice applies to Swing accounts too.** It forbids opening trades
   *"two hours or less before a relevant financial market is closed for at least two hours"* and when *"major ... news
   ... are scheduled"*.
   - ACIS's 2-hour pre-close entry ban switches **off** whenever weekend holding is allowed
     (`capital_governor.py:353`). On Swing, ACIS would commit this practice.
   - This refutes the prior pass's claim that Swing removes the need for the event calendar.

   **(a)**
8. **Four entries in `config/platform_rules.yaml` are wrong about the world** (§8.2; corrections drafted, not applied):
   - `fundednext` names cTrader, where automation is banned.
   - `the5ers` names cTrader, but The5ers is MT5-only.
   - `ftmo` measures max loss on **balance**; FTMO tests **equity**, so the entry is looser than the real rule.
   - `atlas_funded` sets min-hold to 0; Atlas bans trades under 3 minutes.

   **(a)**
9. **Every firm says in its own terms that trading is simulated.** FundedNext adds that it must be able to "monetize
   the trading flow". This strengthens GAP-P12D-44: a prop account is no external referent for fills. **(a)**
10. **Counterparty.**
    - FTMO is the strongest. It has operated since 2015 and has owned **OANDA Global Corporation since 1 Dec 2025**. (a)
    - The industry's tail risk is real:
      - My Forex Funds spent about 21 months in receivership before the CFTC case was dismissed with prejudice on
        13 May 2025. (b)
      - MetaQuotes pulled prop-firm platform licences in 2024. (b/c)
      - MyFundedFX ended prop trading on 6 Feb 2026. (c)

---

## 0. Method

- **Web budget.** I used **21 of 45 WebSearch calls**. Everything else is WebFetch or a direct HTTP fetch of the primary URL.
- **Direct fetches.** A stdlib-only helper (`SCRATCH/scout/grab.py`, scratch only) pulled verbatim passages and
  `dateModified` stamps.
- **FTMO's T&C** is a PDF (`cdn.ftmo.com`). I extracted its text with a stdlib PDF reader (`SCRATCH/scout/pdftext.py`)
  and quote it from that extraction.
- **Apex's help centre returns 403 to this machine**; the reason is in §2.5. I quote it from a Wayback Machine capture
  (2026-03-25) and from the search index's rendering of its support article. I say so wherever I rely on them.
- **Prices.** Where a pricing page is script-rendered, I read the price data embedded in the page's HTML. Where a price
  mapping is inferred, I say so.
- **Code claims.** Each carries a `file:line` from `main` at `7695ed0`. One claim is reproduced by a short read-only
  script (§5.1-F).
- **Rules followed.** No account was created, no form submitted, nobody contacted, no browser automation used, no money
  spent.
- **A9.** Every web page was treated as data. None contained instructions I acted on.

---

## 1. The lead's five UNCONFIRMED leads — verdicts

| # | Lead | Verdict | Primary quote |
|---|---|---|---|
| 1 | Apex bans automation on funded (PA) accounts | **CONFIRMED, and wider: all account types** | *"No Automation or Algorithm Usage allowed: Rewards are intended to recognize human traders actively participating in the learning process, not to reward automated systems executing preprogrammed logic."* (Wayback capture 2026-03-25 of apextraderfunding.com/help-center/getting-started/prohibited-activities/, page modified 2026-03-13) **(a)**. Current support article as indexed on 2026-09-24 (live fetch 403): *"the use of automation is strictly prohibited on all account types, including any form of AI (Artificial Intelligence), Autobots, algorithms, fully automated trading systems, and high-frequency trading (HFTs)"* **(a, via search index)** |
| 2 | Topstep permits its API but bans VPS or remote hosting | **CONFIRMED** | *"All trading activity must originate from your personal device. The use of VPS, VPNs, and remote servers is prohibited by Topstep's Terms of Use. Running automation on a VPS can result in account suspension or removal from the program."* and *"The line is order transmission: your server can watch and record, but it cannot trade."* Also: *"No, Live funded accounts are not allowed to trade through the ProjectX API."* (help.topstep.com, TopstepX API Access, modified 2026-09-17) **(a)** |
| 3 | FundedNext bans automation on cTrader and Match-Trader; EAs are MT4/MT5 only, as a paid add-on | **CONFIRMED** | *"FundedNext does not allow the use of EAs or automated trading on the cTrader and Match-Trader platforms regardless of account size."* (help article 8020763, modified 2026-09-08) and *"Both EAs and VPS are allowed in 5K-25K accounts. EAs and VPS each require their own paid add-on to enable usage. MT4 and MT5 only. Match-Trader and cTrader do not support automated trading."* (fundednext.com/general-rules/cfds/what-is-allowed) **(a)** |
| 4 | The5ers bans "bulk trading" and needs prior written approval for automation | **CONFIRMED** | *"Bulk trading, is when multiple trades are open simultaneously. Situation: A trader opens manually or uses automatic trading tools that open multiple trades at the same time, clearly showing a trader is not behind the strategy activity."* (the5ers.com/faqs/prohibited-trading-practices/) and *"User shall notify the Company in writing and obtain written approval from the Company prior to using any Automated Trading Software; no Automated Trading Software may be used unless the Company has given prior written approval for its use, which approval shall be at the Company's sole discretion"* (T&C, "Last update – Sep. 23rd 2026") **(a)** |
| 5 | FTMO allows EAs and algos without pre-approval, caps 2,000 server requests per day, and calls every account simulated | **CONFIRMED on all three** | *"perform simulated trades that are operated or managed by automated robots / EAs (Expert Advisors) which cause the trading account to become hyperactive in the sense of an excessive number of more than 2,000 server requests per day on individual simulated trades or pending orders being opened, modified, or closed"* (forbidden-trading-practices, modified 2026-02-02). *"Whether it's discretionary trading, algorithmic trading, EAs, etc."* are permitted and *"Platform servers have 200 orders at a time and 2000 max positions per day limitation."* (FAQ, modified 2026-05-27). T&C 5.2: *"No actual trading is taking place and there is no execution of trades in financial markets."* **(a)** |

**Note on lead 5's ambiguity, which the prior pass also flagged.** The two FTMO texts differ:
- the forbidden-practices page counts "server requests ... being opened, modified, or closed";
- the FAQ counts "2000 max positions per day".

Neither says whether price subscriptions or account queries count. That question is in email Q2 (§9.1).

---

## 2. The firms

### 2.0 Summary matrix (rules as of 2026-09-24)

| Firm | Automation on funded | Hosting on a remote server | API that runs on Linux | Kenya | ~$5–10k product and fee | Daily loss | Max loss | Verdict |
|---|---|---|---|---|---|---|---|---|
| **FTMO** | ✅ "algorithmic trading, EAs, etc." (a) | ✅ "VPN/VPS ... generally allowed"; no US geolocation (a) | ✅ cTrader **Open API**, advertised by FTMO (a) | ✅ not on list (a) | $10k 2-Step **€89** (refundable) / 1-Step €79 (a) | 5% of initial from the 00:00 CE(S)T balance, equity intraday (2-Step) (a) | 10% static on equity (2-Step) (a) | **#1** |
| **E8 Markets** | ✅ "Algo, EA, Bots and Indicators" (a) | not stated (ask) | ✅ cTrader (+$10 if the account costs < $100) (a) | ✅ Classic markets; ❌ futures (a) | $5k ≈ $32, $10k ≈ $68 (mapping inferred) (a) | 2.5% (Pro) or 3% (One) of initial from the day-start balance, 00:00 server time (a) | 8% static (Pro); 4% dynamic (One) (a) | **#2** |
| **FundedNext** | ⚠️ MT4/MT5 only, $5k–25k, paid EA add-on (a) | ⚠️ paid VPS add-on (a) | ❌ cTrader and Match-Trader banned; MT5 needs Windows | ✅ not restricted (a) | Stellar 2-Step $6K **$59.99** list (a) | $300 (5%), from the previous day's closing balance, 00:00 server time (a) | $600 (10%) from the starting balance (a) | #3, conditional |
| **The5ers** | ⚠️ prior written approval, sole discretion (a) | not stated | ❌ MT5 only ("Mt5 Hedge") (a) | ✅ not in Forbidden Territory (a) | High Stakes $5K $39 / $10K $78 (mapping inferred) (a) | 5% of max(previous-day closing balance, equity), 00:00 server time (a) | 10% absolute, equity stop-out (a) | #4, conditional |
| **Atlas Funded** | ✅ (prior pass, a) | ⚠️ "geographically inconsistent locations" need notice (a) | none documented | ❓ **no list published** (a) | $10K $79 (prior pass) | midnight UTC, higher of balance or equity (prior pass) | static (prior pass) | #5, blocked |
| **Darwinex Zero** | ✅ algo-native | n/a | MT4/MT5 (Windows) | ❓ | subscription, not a challenge | none | allocation-based | alternative route only |
| **Apex** | ❌ "No Automation or Algorithm Usage allowed" (a) | — | futures stacks | ❌ **server geo-blocks Kenya** (a) | smallest 25k | — | — | **OUT** |
| **Topstep** | API bots allowed, but not on Live funded (a) | ❌ "VPS ... and remote servers is prohibited" (a) | ProjectX API | not checked | — | — | — | **OUT** |
| **Alpha Capital** | ❌ "will not be approved under any circumstances" (a) | — | cTrader, but no EAs there | not checked | — | — | — | **OUT** |
| **FTMO Futures** | ✅ "Automated trading is permitted" (a) | — | futures | not checked | — | — | — | set aside: intraday-only |

**Why the six others were chosen (brief §1):**
- **Topstep:** the lead's lead, and it has an explicit API programme.
- **Atlas:** carried from the prior pass, which found an explicit algorithmic permission.
- **Alpha Capital:** the prior pass's only other cTrader, DXtrade and TradeLocker firm.
- **E8 Markets:** its own help centre explicitly allows "Algo, EA, Bots" and it offers cTrader.
- **Darwinex Zero:** the track-record allocation route the brief names.
- **FTMO Futures:** FTMO's 2026 futures brand, which the brief names.

### 2.1 FTMO — the only shortlist firm that passes the hard filter

**Automation and hosting**

| Topic | Quote | Source (fetched 2026-09-24) |
|---|---|---|
| Algo permitted | *"Whether it's discretionary trading, algorithmic trading, EAs, etc."* | ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/ (modified 2026-05-27) **(a)** |
| Open API | *"On the automation side, cTrader Automate enables you to build and run custom indicators and trading robots using the platform's developer-friendly APIs, with support for C# and Python. Developers can also integrate apps using the Open API."* | ftmo.com/en/trading-platforms/ (modified 2026-08-31) **(a)** |
| cTrader identity | *"You log in with your own cTrader registration, and we only connect our simulated trading accounts to your own cTrader registration."* This cTrader ID is the identity the Open API authorises against (§3). | ftmo.com/en/faq/how-do-i-log-in-to-ctrader/ **(a)** |
| VPS | *"The use of VPN/VPS is also generally allowed. ... When using VPN/VPS, clients should also avoid changing their geolocation to the United States when using MetaTrader, cTrader or TradingView."* | ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/ (modified 2026-08-24) **(a)** |
| Request cap | quoted in §1, lead 5 | forbidden-trading-practices **(a)** |
| Third-party EAs | *"By using a third-party EA, you potentially run a risk of being denied the FTMO Account if you exceed the maximum capital allocation rule."* | FAQ as above **(a)** |
| Third parties | T&C 7.2.1: you will not *"allow access to Simulated Trading on any of your FTMO Challenge Accounts or data related thereto by any third party nor engage or cooperate with any third party in order to have such third party perform simulated trades for you"*. The owner's own program is not a third party. | T&C, LAST UPDATED 4 AUGUST 2026 **(a)** |
| Ambiguity to clear | T&C 9.4.6: you must not *"use automated means to view, display or collect information available through the Website, the Services or the Content"*. It is almost certainly aimed at scraping, but it is literal enough to ask about (email Q4). | T&C **(a)** |

**Forbidden practices that bind an engine on every FTMO account, Swing included**

Source: ftmo.com/en/forbidden-trading-practices/, modified 2026-02-02 **(a)**.
- **Gap trading.** *"perform gap trading (a high-risk practice ...) by opening simulated trades: when major global news,
  macroeconomic events, or corporate reports or earnings are scheduled and they might affect the relevant financial
  market ...; or two hours or less before a relevant financial market is closed for at least two hours"*
- **Profit smoothing.** *"use trading strategies that artificially distribute profit across multiple days without
  proportionally distributing market risk, such as hedging or holding opposing positions on the same or highly
  correlated instruments, or partially closing and managing the same trade idea across multiple trading days, in order
  to circumvent the Best Day Rule"*
- **Discretion.**
  - T&C 7.3: *"We reserve the right to determine, at our own discretion, whether certain simulated trades, practices,
    strategies, or situations qualify as ... a Forbidden Trading Practice."*
  - T&C 7.6.6 allows FTMO to *"enforce the limitation on Risk per Trade Idea to the maximum limit we determine ... as a
    percentage of the Initial Simulated Capital, which must not be exceeded in terms of realised or unrealised loss"*.
  - T&C 7.9: *"we may adopt measures to prevent you from using our services in the future."*

**Rules for the $10k product** (ftmo.com/en/trading-objectives/, modified 2026-05-13) **(a)**

| Rule | 2-Step (Swing is available only here) | 1-Step |
|---|---|---|
| Profit target | 10% Challenge, 5% Verification | 10% |
| Daily loss | *"recalculated daily at 00:00 CE(S)T as the difference between: the account balance recorded at 00:00 CE(S)T of the current day and the Maximum Daily Loss Amount, which is 5% of the Initial Simulated Capital"*, tested on *"account equity (i.e., Balance + Open Positions P/L ± Swaps – Commissions)"* | same text at **3%** |
| Max loss | *"a static limit ... below which your account equity ... cannot drop"*, at 10% of initial | *"end-of-day trailing"*, from *"the highest account balance achieved at 00:00 CE(S)T of any preceding trading day or, if higher, the amount of Initial Simulated Capital"*, 10% |
| Minimum days | 4 trading days | — |
| Consistency | none | Best Day ≤ 50% of Positive Days' Profit (not treated as a breach; you trade on) |
| Swing | *"The Swing account type is offered exclusively within the FTMO Challenge: 2-Step product."* (FAQ, modified 2026-05-28) | n/a |

**Weekend and news** (FAQs modified 2026-04-27 and 2026-09-03) **(a)**
- The restrictions apply **only to Standard accounts, and only on the funded FTMO Account.** During evaluation:
  *"You are allowed to keep your positions open overnight and over the weekend."*
- On a Standard funded account:
  - *"you are required to close your positions shortly before the markets close for the weekend or if the rollover
    (market break) lasts longer than 2 hours"*
  - *"it is not permitted to open or close any trades, including the execution of pending orders (such as Stop Loss or
    Take Profit), within a time window starting 2 minutes before and ending 2 minutes after the release of selected news
    announcements"*
  - *"if a Stop Loss or Take Profit is triggered within the restricted time window, this will also be considered a
    breach"*
  - A server-side stop (master §279) can fire inside that window. **So Standard is structurally incompatible with ACIS.
    Swing is required.** *"The Swing account type have no restrictions on trading during news releases."*
- The restricted-event list is FTMO's own economic calendar ("Restricted event" marks). **(a)**

**Economics, eligibility and disclosure** **(a)**
- **Fee.** $10k 2-Step €89 and 1-Step €79, read from the pricing data embedded in ftmo.com/en/; the site notes a displayed
  price "may has been rounded up". T&C 3.7: *"The FTMO Challenge Fee is stated in EUR"*.
- **Refund.** *"FTMO Challenge: 2-Step The entry fee may be refunded with the first Reward withdrawal."*; 1-Step: not
  refunded.
- **Split.** 2-Step 80%, rising to 90% with scaling or the Premium Programme; 1-Step 90%.
- **First claim.** *"on the 14th or any following day after the first placed trade"*.
- **Methods.** *"bank wire transfer, instant transfer through Visa Direct / Mastercard Send (up to $20,000), Skrill (up to
  $3,000), or cryptocurrencies"*.
- **Kenya.** *"Apart from the exceptions listed below, we accept clients globally"*. Kenya is not among the exceptions
  (FAQ who-can-join-ftmo, modified 2026-02-13).
- **KYC timing.** KYC ("FTMO Identity") becomes available only after the evaluation is passed.
- **Simulated.** T&C 5.2, and the FAQ: *"all accounts we provide to our clients are demo accounts with fictitious funds
  and any trading is in a simulated environment only"*.
- **Adjustment fee.** **T&C 5.3.4 verified verbatim:** *"where the profit or loss of a position is denominated in a
  currency different from the simulated account's denomination currency, a flat adjustment fee of 0.7% from the
  realised profit and loss at the moment the position is closed will be applied. The adjustment reduces a realised
  profit and increases a realised loss accordingly."*

**Free Trial.** Source: ftmo.com/en/ftmo-free-trial/ (modified 2026-05-12) and FAQ (2026-05-05) **(a)**.
- *"Traders can use our Free Trial demo account for 14 days. After this period, they can create a new one."*
- *"Each trader is permitted only one Free Trial at a time"*.
- It is available on *"MetaTrader 4 (MT4), MetaTrader 5 (MT5), cTrader and"* TradingView.
- The profit target is halved; the loss rules are the Challenge's.

**Counterparty** **(a)**
- In operation *"since 2015"*. Customer and reward totals on the site are self-reported.
- T&C 2.1: *"We are not regulated by the Czech National Bank or a similar authority"*.
- FTMO *"has completed the acquisition of OANDA Global Corporation"*, finalised *"on December 1"* (press release,
  2025-12-02).
- US clients are served *"via our affiliated entity at https://ftmo.oanda.com"*.
- Rule changes: *"We will send you a notice of any Modification at least seven (7) calendar days before"* (T&C 15.1).
- Payout disputes: only forum and aggregator anecdotes, e.g. Risk-per-Trade-Idea caps enforced after a first payout
  **(c)**. I treat them as illustrating clause 7.6.6, not as facts.

### 2.2 E8 Markets — second, and the only other firm that passes the hard filter

**Automation and limits**
- *"Tools you can use while trading with us: Algo, EA, Bots and Indicators."* and *"you can use any EA ... as long as we
  don't see multiple users executing the same trades/strategy."* **(a)**
- Limits: *"Server requests per day: 2000 (order place/cancel/modify, TP/SL edits, etc.)"*, *"Max positions per day:
  2000 (per account)"*, *"Open-order cap at time: 100"*, *"Max ticket size (most symbols): 50 lots"*.
- Source: help.e8markets.com article 5515409, 2026-05-14 **(a)**.

**HFT rule, discretion, interviews** (article 6929927, updated 2026-09-23) **(a)**
- *"To avoid high-frequency trading (HFT) behaviors, you cannot hold more than 50% of your trades for under one
  minute."*
- *"We reserve the right to de-risk your trading strategy by limiting your risk to no more than 1% per trade idea or
  time horizon if we detect prohibited practices."*
- *"E8's risk team may request a brief interview with traders at any stage."*

**Platforms** (article 9799834, 2026-09-23) **(a)**
- *"TradeLocker MatchTrader cTrader MetaTrader 5 / MT5 E8 Terminal"*
- *"cTrader costs an extra $10 if the account costs less than $100"*.
- E8's MT5 exposes exportable bid/ask tick history (article 8480398, 2024-05-17), which is useful for cost calibration.

**Kenya** (article 5514278, modified 2026-09-11) **(a)**
- Kenya is **not** on the Classic-markets (CFD) restricted list. It **is** on the E8 futures restricted list.
- Kenyans *"can purchase only E8 Pro (all sizes), E8 Signature accounts (all sizes), E8 Zero (all sizes), and E8 One
  accounts up to $200,000"*.

**Products** (single-phase; articles 13106558, 15274219, 11775980, all updated 2026-09-23) **(a)**
- **E8 Pro:**
  - *"8% Profit Target"*, *"2% Daily Profit cap - In each day, only 2% counts toward the target or profit"*
  - *"2.5% Daily Drawdown – Your account must not lose more than 2.5% of your initial balance in a single day."*
  - *"8% Static drawdown – A fixed loss limit based on your initial balance. It never moves, except when a first payout
    is processed."*
  - News trading allowed, weekend holding allowed, EAs allowed, daily payouts.
- **E8 One:** 6% target, 3% daily, and a *"4% Dynamic Drawdown – A moving loss limit based on your highest closed
  balance ... It locks permanently at the initial balance level."* A 40% best-day rule applies to payouts. News is not
  allowed on the performance account.

**Daily drawdown mechanics** (article 11769446) **(a)**: *"Every new day at 00:00 Server Time, we set your loss level =
Starting Balance of the new day − that fixed $ amount. A permanent violation occurs if your account's equity or balance
reaches/falls below this calculated level at any point during the day."*

**Weaknesses**
- The rules are re-edited constantly ("Updated today" on several articles).
- The daily limits are tight: 2.5–3% of initial.
- The VPS policy, the server timezone and the Kenyan payout rails are all unverified. E8's page says only that *"payment
  services that we use for payouts limit transactions to specific countries"*.
- The firm is US-based (site title *"SimFi™ Trading Platform — 150+ Markets, US-Based"*). Its operating history is not
  verified in this pass.

### 2.3 FundedNext — conditional third; ACIS cannot use its cTrader

**Automation**
- Lead 3 is confirmed (§1).
- *"Traders on accounts of $50,000 and above must trade fully manually"*.
- *"EAs or bots designed specifically to pass Prop firm challenges are strictly prohibited"*.
- *"Using EA that incorporates third-party applications such as Telegram or WhatsApp is strictly prohibited."*
- The EA and VPS add-on fees *"[are] non-refundable"*.
- Sources: article 8020763, 2026-09-08; general-rules page **(a)**.

**Monetization and consistency** (article 8388896, 2026-04-07) **(a)**
- *"the Expert Advisor's trading strategy is entirely unknown to the system, making it impossible for us to monetize
  the trading flow."*
- Switching strategy between challenge and funded is prohibited.
- Note: ACIS's regime-by-regime parameter re-evolution could be *read* as a strategy change. Ask (§9.3).

**Prohibited practices that hit ACIS** (article 8020351, 2026-09-22) **(a)**
- **Quick Strike.** *"positions closed within 30 seconds of opening ... A Quick Strike percentage of 30% or higher
  constitutes a violation"* (the percentage is the share of profit).
- **Statistical arbitrage.** *"A trader engages in statistical arbitrage by simultaneously buying and selling related
  instruments based on historical price patterns"* is listed under prohibited arbitrage. **This describes the
  PAIR_DIVERGENCE module.**
- **One-sided betting** includes *"opens multiple trades in the same direction"*.
- **Hyperactivity:** *"frequent and rapid execution of trades within a short period of time. This also includes
  frequent modifications to orders"*. No number is published.
- **Settlement window.** *"The settlement window on FundedNext runs from 00:00 to 02:00 server time"*.

**Rules for the $6K product** (Stellar 2-Step: article 8021076 and the pricing data embedded on fundednext.com) **(a)**
- Targets $480 (8%) then $300 (5%).
- *"Daily Loss Limit $300 ... measured from the previous day's closing balance"*. *"your daily loss limit will reset
  every day at 00:00 (server time)"*.
- *"Maximum Loss Limit $600 ... The total you can lose from the starting balance."*
- 5 minimum trading days.
- *"First Withdrawal 21 days"*.
- Fee: $59.99 list ($29.99 with a promo code).
- News on funded accounts: *"Profits made during the news window count at 40%. Losses count at 100%."* The window is
  ±5 minutes.
- Weekend holding: not found on the rules pages. Treat as unverified.

**Eligibility, disclosure, payouts** **(a)**
- Kenya: *"FundedNext Ltd. does not offer services to residents of the following jurisdictions: North Korea (DPRK),
  Myanmar, Belarus, Iran, and Russia."*
- Entity: *"FundedNext Ltd is a company registered in accordance with the laws of Comoros Islands, with registration
  number HY01023052"*.
- Simulated: *"executed solely by FundedNext Ltd. using virtual funds in a simulated environment"*.
- Payouts: *"USDT (ERC20/TRC20), USDC (ERC20), Confirmo, RiseWorks, Bank Transfer and direct deposit to FNmarkets"*.
  Kenya is not on the bank-transfer exclusion list.
- KYC happens only after the challenge is passed.

**Payout disputes:** forum reports only **(c)**.

### 2.4 The5ers — conditional fourth

**Automation**
- The T&C approval clause is quoted in §1. It continues: *"the Company may require advance testing of Automated
  Trading Software in its sole discretion."* It also bans automated software *"owned or developed by any third party
  other than the User"*.
- The EA FAQ (last update 22 Jul 2026) is looser in tone: *"You can use any EA you have in your trading account, as long
  as it does not: ... Perform High-frequency trading Use emulators"*.
- Stops must be visible: *"you cannot use a 'stealth mode' stop-loss"*.
- **The T&C governs, so assume approval is required.** **(a)**

**Prohibited practices** (prohibited-practices page) **(a)**
- Bulk trading (quoted in §1).
- *"High-frequency trading, in which the majority of trade durations span is measured within a few seconds or less."*
- *"One-sided bets, which refer to a trading strategy where the user consistently takes positions in one single
  direction."*
- *"Using automated robots or Expert Advisors that cause the trading account to generate an excessive number of server
  requests per day"* (no number).

**High Stakes, $5K or $10K** (the5ers.com/high-stakes/; drawdown FAQ, last update 15 Sep 2026) **(a)**
- *"Platform: Mt5 Hedge."*
- *"Holding trades overnight and over the weekend is allowed"*.
- *"Executing orders 2 minutes before until 2 minutes after high-impact news is not allowed."*
- *"Leverage 1:100"*.
- *"Accounts without trading activity for more than 30 consecutive days will get expired."*
- Loss rules: *"The max loss on the account is 10% from your initial balance (absolute drawdown) and 5% daily drawdown
  that is taken from the closing equity or balance of your previous day (the highest between them). This is taken at
  00:00 server time."*
- Minimum profitable days: 3, each at least 0.5% of initial.
- Fees read in page order: $5K $39 (sale $35), $10K $78 (sale $69).
- Hyper Growth has a 6% stop-out, a 3% daily limit and 1:30 leverage.

**Eligibility, disclosure, fees** **(a)**
- Kenya is not in the T&C's "Forbidden Territory" list.
- Simulated: *"simulated environments ... using Hub-designated fictitious funds"*.
- Interviews: *"If the Company requests an interview, both the scheduling of the interview and the conduct of the
  interview itself must take place within five (5) business days"*.
- Refunds: *"Evaluation fee is non-refundable, once you commence said Evaluation trading activity."* This conflicts with
  the program page's "Refund" cell; ask.

**Reputation.** Forum threads report accounts closed for "continued bulk trading" at payout requests (May and Dec 2025)
**(c)**. That is exactly the rule an 8-instrument engine collides with.

### 2.5 Apex Trader Funding — OUT

- **Geo-block.** On 2026-09-24 its server answered this laptop (ipinfo.io: country **KE**, Nairobi) with **HTTP 403**:
  *"Sorry but you are in a country that has been blocked from accessing our services."* **(a, observed directly)**
  Circumventing that with a VPN is exactly what several firms' terms forbid; FTMO T&C 9.4.2, for example, forbids you
  to *"circumvent geographical restrictions"*.
- **Automation ban.** Quoted in §1 **(a)**.
- **No overnight holds.** *"Holding open trade positions through the market close"* is a prohibited activity:
  *"Traders are responsible for ensuring that all open trade positions are closed prior to the market close."* **(a)**
- **Futures only.** Products in the archived menu are Tradovate, Rithmic and WealthCharts futures accounts from 25k to
  150k **(a)**.
- **This settles the prior pass's (e): Apex is futures-only, and it is disqualified regardless.**

### 2.6 Topstep — OUT

The VPS and remote-server ban and the Live-funded API exclusion are quoted in §1 **(a)**. It is also futures-only.

### 2.7 Atlas Funded — blocked on Kenya

- *"If your country is restricted, you may not be able to proceed beyond the KYC stage."* No list is published (article
  9903318, 2025-02-20) **(a)**. That means paying first, then learning at KYC.
- From article 9904237 (5 Jun 2026) **(a)**:
  - *"Trades held for less than three minutes are not permitted."*
  - *"Risk on any single trade — or multiple trades on the same instrument — may not exceed 50% of your account model's
    daily drawdown limit."*
  - Prohibited: *"Trading from geographically inconsistent locations without prior notice or approval"*. A remote VPS
    triggers this.
  - Prohibited: *"Using automated systems or strategies that: Place large volumes of orders in short succession Spam
    market/limit orders Cause server strain"*.
  - *"opening new positions on Saturdays or Sundays is not allowed"*.

### 2.8 Alpha Capital Group — OUT

Article 6934236 (2026-09-07) **(a)**:
- *"Automated EAs that execute trades independently, without human oversight, are strictly prohibited and will not be
  approved under any circumstances."*
- *"EA functionality is not currently available for cTrader, DX Trade, or TradeLocker accounts"*.

The prior pass hoped Alpha Capital's cTrader offering could rival FTMO. It cannot.

### 2.9 Darwinex Zero — an alternative route, not a funded account

darwinexzero.com **(a)**:
- *"Trade consistently on a virtual account"*, *"Monthly allocations, awarded on merit"*.
- *"Earn 15% real profits on your virtual allocations - paid without excuses."*
- The pricing page is a subscription: *"Trading capital not required – all you pay is your membership"*.

It is MetaTrader-based (Windows terminal). Kenya eligibility and API trading are unverified. It is worth a later look as
a way to build an investable track record without breach risk. It does not answer "a ~$6k funded account".

### 2.10 FTMO Futures — set aside

- Launched 2026-09-17 (press release) **(a)**.
- *"Automated trading is permitted."* But also: *"You must not carry any open position or active resting order past the
  end of the permitted trading day."* (futures forbidden-practices, modified 2026-09-22) **(a)**
- Intraday-only CME contracts clash with the multi-day-hold direction of the prior research. They would need the last
  adapter tier in §7.5 and GAP-0109.

---

## 3. Platform and API facts that decide the engineering

- **cTrader Open API, from help.ctrader.com/open-api/ (fetched 2026-09-24)** **(a)**:
  - *"the API can be accessed by anyone with a cTID, and, by default, it is supported by all trading accounts of any
    cTrader-affiliated brokers."*
  - *"You can use cTrader Open API to trade on behalf of both demo and live accounts."*
  - Rate limits: *"a maximum of 50 requests per second per connection for any non-historical data requests ... a
    maximum of 5 requests per second per connection for any historical data requests."*
  - Official SDKs are C# and Python. *"If you intend to use JSON, there is no need to use our SDKs"*. JSON runs over
    TCP or WebSocket, so it runs natively on Linux.
- **Server-side stops (master §279), re-verified in Spotware's `OpenApiMessages.proto` (last commit 2025-11-13)** **(a)**:
  - The prior pass's key constraint still holds: `stopLoss = 11; // The absolute Stop Loss price ... Not supported for
    MARKET orders.` Only `relativeStopLoss` (a distance applied to the **fill** price) can ride on a market order.
  - Protection orders are server-held objects. `ProtoOAReconcileReq.returnProtectionOrders`: *"If TRUE, then current
    protection orders are returned separately, otherwise you can use position.stopLoss and position.takeProfit
    fields."* That is the reconnect-reconciliation hook.
  - **Not documented anywhere:** how a firm's simulated server fills a stop that is gapped through (fills worse, or
    cancels). That is the GAP-P12D-42 class. It must be proven per venue by the ACIS-06 conformance suite.
- **Volume units.** `volume ... represented in 0.01 of a unit (e.g. 1000 in protocol means 10.00 units)` **(a)**.
  Minimum volume and step are per symbol, so read them at attach time, not from `config/instruments.yaml`.
- **MT5** remains Windows-only for Python. That comes from the prior pass (the PyPI `MetaTrader5` wheels are Windows
  x86-64 only) and was not re-fetched. It is what makes FundedNext and The5ers a deployment-gate problem.
- **TradeLocker and Match-Trader APIs** were not assessed. E8 offers both, and so does Atlas, but no firm's permission to
  use their APIs was found.

---

## 4. Verifying the 2026-09-17 venue pass

| Prior claim | Status today | Evidence |
|---|---|---|
| OANDA v20 is unavailable to OANDA Global Markets (BVI), the Kenyan's division | **CONFIRMED** | developer.oanda.com/rest-live-v20/introduction/: *"available to all divisions except OANDA Global Markets and OANDA TMS BROKERS S.A."* **(a)** |
| (new) Can a Kenyan get an OANDA **practice** account with v20 API access? | **Very likely NO for a new account** (inference from four (a) facts); **UNTESTED for an existing legacy token** | (1) the exclusion above; (2) www.oanda.com routed this Kenyan IP to `/bvi-en/`, whose MT5 download links name `OANDA-OGM MT5 Demo` (observed); (3) OANDA's BVI guide: *"your location determines which legal documents, leverage limits, and asset classes are available to you"* and *"After your demo account is set up, you will be prompted to download either the MT5 desktop application, MT5 Web Trader, or the MT5 mobile app."* **(a)**; (4) the developer portal's "free demo account" link (`fxtrade.oanda.com/.../register/gate`) returned **HTTP 523** (observed). `/apply/demo/` redirects to a script-only app at hub.oanda.com, which I could not inspect without a browser (not allowed). |
| FTMO T&C 5.3.4: 0.7% non-USD adjustment | **CONFIRMED verbatim** (§2.1), T&C of 4 Aug 2026 | **(a)** |
| …"hits 5 of the 8 declared instruments" | **CORRECTED: 4 of 8** | The instruments whose `quote_ccy` is not USD are USD_JPY, USD_CHF, USD_CAD and EUR_GBP (`config/instruments.yaml`). The prior pass listed those four and called them five. Of the **2 enabled** instruments, **1** (USD_JPY) is affected. |
| FTMO permits the cTrader Open API | **Strongly supported, not explicitly stated for unattended funded use** | FTMO advertises *"Developers can also integrate apps using the Open API"* and allows algos and VPS **(a)**. Written confirmation is still the first email question. |
| Atlas accepts Kenyan residents? | **STILL UNVERIFIABLE** | No list is published; eligibility is decided at KYC, after purchase **(a)** |
| Atlas: a 3-minute minimum hold | **CONFIRMED, and stronger** | *"Trades held for less than three minutes are not permitted."* **(a)** |
| The5ers is MT5-only | **CONFIRMED** | *"Platform: Mt5 Hedge."* **(a)** |
| The5ers publishes no equity/balance basis or static/trailing semantics | **REFUTED** | It now publishes them: 10% absolute; 5% daily from the higher of the previous day's closing equity or balance, at 00:00 server time **(a)** |
| Apex: futures-only? | **CONFIRMED, and moot** | §2.5 **(a)** |
| FundedNext: "everything unknown" | **RESOLVED** | §2.3 **(a)** |
| "On Swing there is no news restriction at all, so the unbuilt historical event calendar is not needed for FTMO compliance" | **REFUTED as stated** | The ±2-minute rule is off on Swing, but the forbidden "gap trading" practice (opening trades *"when major ... news ... are scheduled"*) binds every account. An entry blackout around scheduled events is still needed (GAP-P12D-03), with the window to be confirmed by FTMO. **(a)** |
| Alpha Capital is worth a dedicated pass because of cTrader | **CLOSED: disqualified** | §2.8 **(a)** |

---

## 5. Prop-fit pre-mortem of ACIS as built

Repository `main` at `7695ed0`, read-only. The config values and code paths decide the verdicts, not intentions.

### 5.1 Blocking at every firm

**A. The equity floor is absolute and sized for a $10k paper account.**
- `config/guardrail_limits.yaml:13` reads `equity_floor_usd: 9000.0  # dev/paper account assumed 10k start`.
- `core/risk/guardrails.py:220` reads `equity_breached = ctx.equity < Decimal(str(self._limits.equity_floor_usd))`,
  then flattens everything and issues a global HALT with human-only resume (`:227-234`).
- The consequences:
  - On a $5k account (E8, The5ers) or a $6k account (FundedNext): **flatten and HALT at the first evaluation.** The
    engine cannot trade at all.
  - On FTMO $10k 2-Step: the floor is $9,000, **exactly FTMO's max-loss line**. By the time ACIS flattens, FTMO has
    already failed the account, so the floor gives no pre-breach protection.
  - On E8 Pro $10k (8% static, a line at $9,200): **E8 fails the account first.**
- Changing this value is human-only under the guard-integrity law. **[spec — owner ratification]**

**B. Orders are below the venue's minimum lot, and nothing rounds to the lot step.**
- Sizing: `config/system_config.yaml:3` sets `base_unit_usd: 1000.0`. `core/governor/capital_governor.py:283-291`
  computes `raw_usd = base_unit × conviction × liquidity × correlation × regime × marginal_alpha(≤1.5) × vol_norm(≤1) ×
  taper`, then quantises to **0.01 units**, not to the venue's lot step.
- `core/execution/orchestrator.py:136-152` (`_capable_venues`) never checks `descriptor.min_lot` or `lot_step`, which are
  declared at `core/execution/venue.py:119-120`.
- Arithmetic at EUR/USD 1.08:
  - The maximum is $1,500, or 1,389 units (0.0139 lot).
  - With every factor neutral, it is 926 units (0.0093 lot).
  - A typical case (conviction 0.7, liquidity NORMAL 0.8, regime 0.8×0.8) is **332 units ≈ 0.0033 lot**. USD/JPY lands
    at about 358 units.
- Retail and prop FX venues commonly have a **0.01-lot = 1,000-unit minimum**. The prior pass verified this at OANDA
  OGM, IC Markets and Pepperstone; FTMO's and E8's own values are unverified (email Q6). Against that minimum, **most
  orders are un-placeable**.
- The honest fix rounds **down** to the step, so most orders become zero. Rounding up would violate the Governor's
  clamp-only-downward law.
- Scale: a $1,000 notional ticket risks cents to single dollars per trade. That cannot reach a $600–$1,000 profit target
  in any useful time. Quantifying P(pass) is the ECONOMIST's job.
- Tags: **[impl]** for the lot-step and min-lot check; **[spec — owner ratification]** for NAV-relative prop sizing.

**C. Nothing in the execution path enforces a request or order budget.**
- `grep` over `core/execution/` finds no rate or budget logic, only the observability-only `dispatch_budget_ms`.
- On the planted falsification run the composed loop produced `SIZED 1,425,326` against 2,018 booked trades over about
  two graded years (GAP-P12D-31). That is **about 2,700 sized decisions per trading day** for two instruments.
- If each one reached the venue as a request, the **FTMO and E8 cap of 2,000 per day would be breached on day one.**
- With a position-aware gate (GAP-0075), the same run's 2,018 trades are about 4 trades per day, roughly 8–16 requests.
  That is two orders of magnitude inside the cap.
- Execution also splits any order of 1 lot or more into jittered fragments (`config/system_config.yaml`,
  `fragment_threshold_lots: 1.0`). Each fragment is another request.
- **[impl]**: a hard adapter-level daily counter, part of the GAP-0075 runtime fix.

**D. A platform's daily loss rule cannot be expressed.**
- `core/risk/guardrails.py:122` appends every platform rule with `resets_daily=False`, commented `# platform rules
  never reset daily`.
- `DrawdownRule` (`config/schemas.py:450-454`) has no reset instant or zone. It has no "% of initial capital" option;
  ACIS computes `(anchor − basis)/anchor`, at `guardrails.py:79`. It has no day-start-anchor variant either.
- Every firm's headline rule is a daily reset, and they differ:
  - FTMO: the balance at 00:00 CE(S)T.
  - E8: the day-start balance at 00:00 server time.
  - FundedNext: the previous day's closing balance at 00:00 server time.
  - The5ers: the higher of the previous day's closing equity or balance, at 00:00 server time.
  - Atlas: the higher of balance or equity at 00:00 UTC.
- The current `ftmo`, `atlas_funded` and `fundednext` entries stand in `trailing/intraday/equity 5%`. That is the wrong
  semantics (§8.2, correction 2 under `ftmo`).
- **[spec — owner ratification]**. It is guardrail-adjacent, and platform rules are human-commit.

**E. The engine's daily limit is an entry halt, not a loss cap, and its day is not the firm's day.**
- `core/risk/guardrails.py:245-248` handles the engine daily breach as a *session* halt that auto-clears at the **next
  session boundary**, which can be the Tokyo, London or New York open, not the next trading day (`capital_governor.py:
  123-131`, `:336-340`).
- A platform-rule breach issues `_issue_halt("all", ...)` (`:250`) and **never flattens**. Master §9.5 states: *"Open
  positions and their stops are untouched"*.
- The engine day starts at 17:00 New York. FTMO's day starts at 00:00 CE(S)T, **1 hour later** for most of the year and
  **2 hours later** in the weeks when US and EU daylight saving are out of step.
- So one firm-day can contain the tail of one engine day and the head of the next: **up to two 2% engine budgets, plus
  whatever open positions lose after the halt.**
  - Against FTMO 2-Step's 5% that is tolerable.
  - Against FTMO 1-Step's 3%, E8 One's 3%, E8 Pro's 2.5% and The5ers Hyper Growth's 3%, **a breach path exists.**
- The ratified pre-limit defence (GAP-0010) tapers entries only.
- **[spec — owner ratification]**: a per-account daily boundary, and a pre-breach *flatten* on platform limits.

**F. NEW — a process restart relaxes every platform limit.** Reproduced by script, read-only import of
`core.risk.guardrails`.
- `DrawdownSeries._anchors` lives only in memory (`core/risk/guardrails.py:90`).
- `core/risk/store.py` persists halts, snapshots, the taper and alpha state (`save_restrictive_state(alpha_armed,
  taper_factor)`), but **not** the static inception anchor, the trailing high-water mark or the engine day-open anchor.
- The static anchor is also *"the first observed basis"* (`guardrails.py:72-73`), not a declared initial capital.
- The reproduction: an equity path of 10,000 → 10,400 → 9,800 → 9,400 measures `static 10%: 6.0`, `trailing: 9.62` and
  `engine:daily: 6.0`. A fresh series built at 9,400, which is what a restart does, measures **0.0 on all three**.
- On an FTMO $10k account at −6%, a restart hands ACIS a fresh 10% budget while FTMO has 4% left.
- This contradicts the principle GAP-0050 set for the risk layer: "a restart is never a relaxation". The ledger has no
  entry for it; GAP-P9E-01 fixed only the *calendar* reset of the trailing anchor.
- **[impl]**, guardrail-adjacent: raise it, do not self-fix.

**G. The weekend pre-close entry ban is tied to `weekend_holding_allowed`.**
- `capital_governor.py:353-356` only calls `within_weekend_buffer(... weekend_entry_buffer_s=7200)` when
  `not weekend_holding_allowed`.
- On FTMO Swing (`weekend_holding_allowed: true`) ACIS would open trades in the last 2 hours before the Friday close.
  That is FTMO's forbidden **gap trading**, on every account type.
- Separately, master §9.5 says weekend bans mean *"positions flattened before the ban window by policy"*, but the code
  only bans *entries*. `grep` finds no weekend flatten in `core/`.
- **[impl]**; the new rulebook field is **[spec]**.

### 5.2 Firm-by-firm, the top three

| Check | FTMO 2-Step Swing $10k | E8 Pro / E8 One $5–10k | FundedNext Stellar 2-Step $6K |
|---|---|---|---|
| Can ACIS attach from Linux at all? | Yes: cTrader Open API (the ACIS-13 adapter is unbuilt) | Yes: cTrader Open API (+$10) | **No**: automation banned on cTrader. Only a Windows MT5 terminal with paid EA and VPS add-ons |
| Equity floor $9,000 (5.1-A) | Sits on FTMO's max-loss line: no pre-breach protection | $5k: **halts at start**; $10k: below E8's 8% line, so E8 fails first | **Halts at start** |
| Request caps (5.1-C) | 2,000/day plus 200 open orders: **breach on day one** unless GAP-0075 is fixed | 2,000/day plus 100 open orders: same | "Hyperactivity", no number: same risk |
| Daily loss against the engine's 2% at 17:00 New York (5.1-E) | 5% of initial ($500) from 00:00 CE(S)T. Two engine budgets ($400) plus overshoot < $500: **tight but inside** | 2.5% ($250 at $10k) or 3%: two engine budgets reach 4% ($400): **breach path** | 5% ($300) from the previous day's close; two engine budgets ($240) plus overshoot: **tight** |
| Existing rulebook entry | Max-loss **basis wrong** (balance; FTMO tests equity); daily semantics wrong | **No entry** | Platform wrong (ctrader); "EAs on all programs" false |
| Weekend | Swing: allowed. Standard funded: must close before the weekend, and ACIS has **no flatten** | Allowed (Pro and One) | Unverified |
| Pre-close and pre-news opens (5.1-G) | **Forbidden "gap trading"**: ACIS would open within 2 h of the Friday close | No such rule found | No such rule found |
| News | Swing: no ±2-minute rule, but the gap-trading clause needs a scheduled-news entry blackout (GAP-P12D-03). Standard: a stop firing inside ±2 minutes is a breach, which is incompatible with §279 | Pro: allowed. One performance account: not allowed | Funded: news profits count at 40% (±5 min) |
| Minimum lot (5.1-B) | Typical 332–358 units vs a probable 1,000-unit minimum: **un-placeable** | Same | Same (MT5) |
| Hold-time and HFT rules vs GAP-P12D-38 (79% of graded trades zero-duration) | No hold-time rule | **HFT if more than 50% of trades are under 1 minute: breach if the zero-duration trades are live behaviour** | Quick Strike: trades under 30 s must stay below 30% of profit |
| PAIR_DIVERGENCE | Discretionary risk: "opposing positions on ... highly correlated instruments", to circumvent the Best Day rule (a 1-Step concern) | Hedging is defined on the same asset | **Prohibited**: "statistical arbitrage ... related instruments" |
| Non-USD profit and loss | **0.7% on USD_JPY** (1 of 2 enabled; 4 of 8 declared) | None published | None published |
| Same-direction clustering | Risk per Trade Idea on correlated symbols (T&C 7.5.3, 7.6.6): discretionary | 1% de-risk "if we detect prohibited practices" | "opens multiple trades in the same direction" |
| Hosting | No US geolocation | US clients cannot use MT5 or cTrader, so do not host in the US | Paid VPS add-on required |

**The FTMO 0.7% adjustment, quantified.** Let GW be gross wins, GL gross losses and PF = GW/GL. The adjustment removes
0.007·(GW+GL) from the net GW−GL. So the share of expectancy lost on an affected instrument is **0.007·(PF+1)/(PF−1)**:

| PF | Expectancy lost |
|---|---|
| 1.5 | 3.5% |
| 1.2 | 7.7% |
| 1.1 | 14.7% |

It belongs in the C8 cost model as a per-instrument, per-account term. It is not a spread. **[impl]**

### 5.3 What the §9.5 rulebook schema cannot express

`AccountRulebook` is at `config/schemas.py:457-468` and `DrawdownRule` at `:450-454`. Rules it cannot express:
1. **Daily-reset loss rules:** the reset instant and zone, a limit as a % of *initial* capital, and the day-start anchor
   (balance; previous-day close; max of balance and equity) (§5.1-D).
2. **A declared initial capital** for static and trailing anchors, instead of the first observed basis (§5.1-F).
3. **EOD-trailing and closed-balance-trailing max loss that locks at the initial balance:** FTMO 1-Step, E8 One.
4. **Request and order caps:** 2,000 requests per day (FTMO, E8); 200 or 100 open orders; 2,000 positions per day.
5. **A pre-close entry ban independent of weekend holding:** FTMO's "≤ 2 h before a ≥ 2 h close".
6. **Richer news semantics:**
   - open **or close**, including stop and target triggers (FTMO Standard);
   - a news profit split (FundedNext 40%);
   - event lists by source.
7. **Distributional hold-time rules:** E8 (at most 50% of trades under 60 s); FundedNext Quick Strike (at most 30% of
   profit from trades under 30 s); The5ers ("majority ... within a few seconds"). Atlas's 3 minutes *is* expressible as
   `min_hold_seconds: 180`.
8. **Profitable-day thresholds:** The5ers (3 days at ≥ 0.5%). `min_trading_days` only counts days.
9. **Daily profit caps for target counting:** E8 Pro (2%).
10. **Per-trade and per-instrument risk caps:** Atlas (50% of the daily limit); FTMO Risk per Trade Idea; E8 1%.
11. **Rules that differ by phase:** FTMO Standard evaluation vs funded; E8 One challenge vs performance.
12. **Inactivity expiry:** The5ers 30 days; E8 60 days.
13. **Per-symbol lot caps:** E8's XAU is 20 lots. `max_lots` divides by 100,000 units (`capital_governor.py:297-298`),
    which is FX-only.

**Fields declared but enforced nowhere:**
- `consistency_max_day_profit_pct` and `min_trading_days` have **no consumer** in `core/`, `tests/backtest/` or
  `scripts/`. Only `config/account_doctrine.py` carries them.
- `min_hold_seconds` is graded after the fact in the backtest (`tests/backtest/harness.py:187`) and gates
  MOMENTUM_SCALP eligibility in the Governor (`capital_governor.py:357-360`). Nothing enforces it at run time.

---

## 6. Ranked recommendation for ACIS's first funded account

1. **FTMO: FTMO Challenge 2-Step, Swing, $10,000, USD, on cTrader via the Open API.**
   - **Why.**
     - It permits algorithmic trading and VPS hosting in plain words.
     - It advertises Open API integration and connects its cTrader accounts to the trader's own cTrader ID.
     - It accepts Kenyan residents.
     - Its fee is the lowest-risk on the list (€89, refundable with the first reward).
     - It has the most generous loss geometry among the passers: 5% daily and 10% static, both on equity.
     - It is the strongest counterparty: 10+ years, and owner of OANDA.
   - **Why Swing.** Standard funded accounts make any stop that fires within ±2 minutes of listed news a breach, and they
     forbid weekend holding. §279 stops make Standard unusable.
   - **Before paying:**
     - Get FTMO's written answers to Q1–Q4 (§9.1).
     - Fix §5.1-A to G.
     - Model the 0.7% adjustment.
     - Set up a request counter well under 2,000 per day.
     - Wire always-on pre-close and pre-news entry bans.
     - Host the VPS outside the US.
2. **E8 Markets: E8 Pro (8% static) or E8 One, $5–10k, on cTrader.**
   - **Why.** E8 explicitly permits "Algo, EA, Bots", offers cTrader and accepts Kenyans for its CFD products.
   - **Why second.**
     - The daily limits (2.5–3%) are tight against ACIS's day-boundary mismatch.
     - Products are single-phase, and the rules change often.
     - The E8 Pro 2% daily profit cap slows target-counting.
     - Its HFT rule is distributional, so it bites if GAP-P12D-38's zero-duration trades are live behaviour.
     - Its VPS policy and Kenyan payout rails are unverified.
     - Its counterparty history is thinner, and unverified here.
   - **Before paying:** written answers to §9.2.
3. **FundedNext: Stellar 2-Step $6K on MT5, with the EA and VPS add-ons. Only if the owner accepts a Windows MT5 host.**
   - That breaks the Linux Docker and systemd deployment gate (GAP-P12D-43).
   - PAIR_DIVERGENCE must be off for this account, because statistical arbitrage is prohibited.
   - The Quick Strike and "same strategy" rules add review risk.
   - The firm states that it monetizes the trading flow.
4. **The5ers: High Stakes $5K or $10K, MT5 only. Only with prior written approval of ACIS and a written ruling that
   holding several positions on different instruments is not "bulk trading".** The payout-time enforcement reports
   **(c)** make this the least deterministic option.
5. **Atlas Funded: blocked until it confirms Kenya in writing.** Even then: MT5, TradeLocker or Match-Trader with no API
   permission found; a 3-minute minimum hold; VPS-location notice.

**Disqualified:**
- **Apex:** automation ban, a Kenya geo-block, and intraday futures.
- **Topstep:** VPS and remote servers banned; no API on Live funded accounts; futures.
- **Alpha Capital:** fully automated EAs "will not be approved under any circumstances".

**Set aside:**
- **FTMO Futures:** intraday-only.
- **Darwinex Zero:** a subscription track-record route, not a funded account.

**Recommended shortlist change (owner):** replace Apex with E8 Markets. Keep FTMO. Demote The5ers and FundedNext to
conditional.

---

## 7. Demo-venue recommendation (Track A, step 1)

**The spec's ordained venue.** SPEC §15, phase 12: *"Live broker connection via conformant adapters (OANDA practice
account first, MT5 next; live only after §14 minimums met and human sign-off ...)"* (`ACIS_SPEC.md:368`).

| | **A. OANDA practice (v20)** | **B. FTMO Free Trial, cTrader, Open API** | **C. cTrader demo at a CMA-licensed Kenyan broker** |
|---|---|---|---|
| Available to the owner? | **New account: very likely no** (§4). A legacy token: untested | **Yes** (Kenya accepted; free) | Probably. The brokers are CMA-licensed and offer cTrader (prior pass), but demo availability was not verified today |
| Runs on the Linux deployment? | Yes (REST) | Yes (JSON over WebSocket/TCP) | Yes (same Open API) |
| Adapter reused on the prop route? | No (v20 ≠ cTrader) | **Yes: the destination's adapter**, first in the ratified §7.5 order after the v1 trio | **Yes: the same adapter** |
| Destination feed, symbols, costs, swaps, 0.7% fee, firm rule engine | No | **Yes.** The demo doubles as forward incubation and as a live test of ACIS's §9.5 model against FTMO's own breach engine | No |
| Continuity | Good | **A 14-day life, one trial at a time, ends on a breach.** Account IDs churn, and the adapter must re-attach | Good (typical broker demos; unverified) |
| Risk to the owner's standing at the destination | None | **Real.** FTMO's rules apply to the trial: the 2,000/day cap, forbidden practices, and T&C 7.9 ("prevent you from using our services in the future") | None |
| SPEC §15 conformance | **Conformant** | **Deviation: owner ratification required** | Deviation (in the spirit: "a broker practice account first") |

**Recommendation**
1. **Today, free, one command:** the owner runs Track A step 1,
   `curl -H "Authorization: Bearer <practice token>" https://api-fxpractice.oanda.com/v3/accounts`. It is the only way
   to learn whether a legacy practice token still opens the spec's path. I cannot run it: I have no token, and creating
   an account is out of scope.
2. **Build the demo on the cTrader Open API regardless.** It is the destination's adapter under ACIS-13. Mind the
   market-order stop constraint (§3) and read `minVolume`/`stepVolume` at attach time.
3. **Demo of record: B, the FTMO Free Trial on cTrader.** **This is a SPEC §15 deviation; flag it for owner
   ratification** (drafted text below). Point ACIS at it only when all of these hold:
   - GAP-0075 is fixed, and a hard counter holds requests at or below 1,000 per day (half the cap).
   - Orders round down to the lot step and are checked against the minimum lot.
   - The pre-close (2 h) and scheduled-news entry bans are on for every rulebook.
   - The VPS is not in the US.
   - FTMO has not said "no" to Q1.
4. **Fallback with zero extra code: C.** Use it for the first plumbing shake-down while items in step 3 are still open,
   or if FTMO's answer is slow or negative. The same adapter attaches to a broker demo through the same cTrader ID flow.
5. **Keep the TODO's warning attached.** The demo proves plumbing, not edge. GAP-P12D-49 says to expect it to lose. On
   FTMO a losing trial simply ends and is recreated; that is acceptable, but it must never be read as "the engine
   works".

**Draft ratification text (for the lead to put to the owner, not applied):**
> SPEC §15 phase 12 venue order — proposed amendment: "Live broker connection via conformant adapters: **a
> practice/trial account on the destination platform first** (for the owner's route, cTrader via the Open API on the
> chosen firm's free trial), an OANDA v20 practice account only where a practice token for the owner's division exists,
> MT5 only on a Windows host; live only after §14 minimums met and human sign-off; …" Rationale: OANDA v20 is closed to
> OANDA Global Markets, the only division a Kenyan resident onboards to (GAP-P12D-43; re-verified 2026-09-24).

---

## 8. Drafted rulebook entries and corrections (TEXT ONLY — not applied)

`config/platform_rules.yaml` is human-commit only under the guard-integrity law. These are drafts for the owner.

### 8.1 Draft entries for the top two

```yaml
  # ── DRAFT (SCOUT 2026-09-24) — NOT APPLIED. Verify every value on purchase day. ─────────────────────────
  ftmo_2step_swing_10k:            # FTMO Challenge 2-Step, SWING account type, $10,000 USD, cTrader via Open API
    platform: ctrader              # ftmo.com/en/trading-platforms/ (2026-08-31)
    news:
      restricted: true             # Swing is exempt from the Standard +-2 min rule, BUT the forbidden "gap trading"
      window_before_s: 3600        # practice bans OPENING trades "when major ... news ... are scheduled" on every
      window_after_s: 120          # account. FTMO publishes no window: 3600/120 is a PLACEHOLDER pending email Q3.
    min_hold_seconds: 0            # no hold-time rule published (forbidden-trading-practices, 2026-02-02)
    max_lots: null                 # none published at $10k ("200 orders at a time" is not expressible)
    weekend_holding_allowed: true  # Swing only. NB: FTMO still forbids OPENING trades <= 2 h before a >= 2 h close;
                                   # ACIS's 2 h buffer switches off when this is true (capital_governor.py:353) -> needs
                                   # a new always-on field before this entry is safe.
    drawdown_rules:
      - type: static               # "static limit ... below which your account equity ... cannot drop", 10% of initial
        anchor: intraday
        basis: equity
        limit_pct: 10.0
      # Max Daily Loss — 5% of INITIAL capital below the 00:00 CE(S)T BALANCE, tested on equity intraday — is NOT
      # expressible (platform rules never reset daily: core/risk/guardrails.py:122). Do not substitute
      # trailing/intraday/equity 5% (see 8.2). Also not expressible: 2,000 requests/day, 200 open orders, the 0.7%
      # currency adjustment (cost model), Risk per Trade Idea (discretionary), declared initial capital (§5.1-F).
    consistency_max_day_profit_pct: null   # 2-Step has no Best Day rule (1-Step: 50%)
    min_trading_days: 4
    taper_start_fraction: 0.50     # SUGGESTION (stricter-only override, like prop_demo): a breach is terminal
    entry_halt_fraction: 0.70

  e8_pro_10k:                      # E8 Markets "E8 Pro", Classic Markets, $10,000, cTrader (+$10 if account < $100)
    platform: ctrader              # help.e8markets.com 9799834 (2026-09-23)
    news:
      restricted: false            # E8 Pro: "News Trading Yes" (13106558, 2026-09-23)
    min_hold_seconds: 0            # E8's rule is distributional (<= 50% of trades under 60 s) — not expressible
    max_lots: 50.0                 # "Max ticket size (most symbols): 50 lots" (XAUUSD 20 lots — not expressible)
    weekend_holding_allowed: true  # "Weekend Holding Yes", "Overnight holding Yes"
    drawdown_rules:
      - type: static               # "8% Static drawdown ... based on your initial balance"; E8 breaches if "equity OR
        anchor: intraday           # balance" reaches the level, so test both bases:
        basis: equity
        limit_pct: 8.0
      - type: static
        anchor: intraday
        basis: balance
        limit_pct: 8.0
      # 2.5% Daily Drawdown (of INITIAL, below the day's starting balance at 00:00 SERVER TIME, equity or balance) —
      # NOT expressible. Also not expressible: 2% daily profit cap (counting), 2,000 requests/day, 2,000 positions/day,
      # 100 open orders, 60-day inactivity, the HFT share rule, E8's move of the static line at first payout.
    consistency_max_day_profit_pct: null   # E8 Pro: "No consistency rules"
    min_trading_days: null
    taper_start_fraction: 0.50     # SUGGESTION
    entry_halt_fraction: 0.70
```

### 8.2 Corrections to the existing entries

**`ftmo`**
1. The `static / eod / balance / 10.0` rule must be `static / intraday / equity / 10.0`. FTMO tests *"account equity
   (i.e., Balance + Open Positions P/L ± Swaps – Commissions)"*. With `basis: balance` ACIS ignores floating losses,
   so the entry is **looser than the real rule**.
2. The `trailing / intraday / equity / 5.0` stand-in for the daily loss has the wrong semantics in both directions:
   - **It is looser than FTMO whenever a day opens at a new high above initial capital.** Example: initial 10,000 and a
     day opening at a balance and high-water mark of 11,000. FTMO's floor is 11,000 − 500 = 10,500. ACIS's floor is
     11,000 × 0.95 = 10,450.
   - **Otherwise it is far stricter.** It acts as a 5% trailing *account* drawdown that never resets, with a global HALT
     and human-only resume, which halves the usable 10% budget. Replace it with a real daily rule (§5.3, item 1).
3. The file's header claims to model the daily rule *"STRICTER than the real rule where in doubt"*. The claim is false
   in the in-profit case above.
4. The header claims *"ACIS's own 2% daily guardrail is far inside every prop 5% daily, so ACIS essentially cannot
   breach a prop daily limit"*. It is false:
   - Several daily limits are 2.5–3%: FTMO 1-Step, E8, The5ers Hyper Growth.
   - The day boundaries differ (§5.1-E).
   - The engine's limit halts entries only; it does not cap losses.
5. `news: 120/120` and `weekend_holding_allowed: false` describe the **Standard funded** account only. Evaluation phases
   are unrestricted, and Swing is unrestricted by that rule. The Standard news rule also counts stop and target
   triggers, which §279 stops cannot avoid. Model Swing (8.1).
6. Add `min_trading_days: 4` (2-Step).

**`the5ers`**
1. Change `platform: ctrader` to **`mt5`**. The firm states *"Platform: Mt5 Hedge."*
2. Change `news.restricted: false` to `true, 120/120` for High Stakes (*"Executing orders 2 minutes before until 2
   minutes after high-impact news is not allowed"*). Hyper Growth allows news.
3. Change `static / eod / balance / 10.0` to `static / intraday / equity / 10.0`: the rule is an *"equity stop-out"* at
   10% of initial.
4. Add the daily rule, which is **not expressible**: 5% of the higher of the previous day's closing equity or balance,
   at 00:00 server time. The comment *"some have NO daily"* is out of date: Hyper Growth has 3%, and Bootcamp funded
   has a 3% daily pause.
5. Missing, and **blocking rather than a field**:
   - prior written approval for automated software;
   - the bulk-trading ban;
   - one-sided bets;
   - ownership of the source code;
   - 3 profitable days at 0.5% or more (not expressible);
   - 30-day inactivity expiry.

**`atlas_funded`**
1. Change `min_hold_seconds: 0` to **`180`** (*"Trades held for less than three minutes are not permitted."*). The
   comment *"scalp runs at its native horizon here"* is wrong.
2. Add a blocking comment: **Kenya eligibility unverified** (no list published; decided at KYC).
3. The daily rule: per the prior pass it is midnight UTC on the higher of balance or equity, and fixed intraday. That
   is not expressible, and the current `trailing / intraday / equity 5` has the wrong semantics.
4. Missing:
   - single-trade risk at most 50% of the daily limit;
   - notice for a VPS in another country;
   - the ban on automated order spam;
   - news on funded accounts: ±5 minutes for opening or closing, which the prior pass found (a); set `restricted: true,
     300/300` for funded accounts.

**`fundednext`**
1. `platform: ctrader` is **wrong about the world for an automated engine**: automation is banned on cTrader. The
   entry must be `mt5` (or `mt4`), on an account of $5k–$25k with the EA and VPS add-ons purchased. The comment
   *"cTrader + Match-Trader; EAs on all programs"* is false.
2. The comment *"SWING account modelled ... live leverage is reduced to 1:30"*: no Swing product appears on the current
   general-rules pages, which list Stellar 2-Step, 1-Step, Lite and Instant. Remove the comment or verify it.
3. `news.restricted: false` is right for challenge phases. On funded accounts the 40% news profit split is an
   accounting rule, which the schema cannot express.
4. Drawdown:
   - The daily rule is 5% of initial, below the **previous day's closing balance**, at 00:00 server time. It is not
     expressible.
   - The max-loss rule should be `static / intraday / equity / 10.0`: it counts losses *"on closed or running trades"*.
5. `consistency_max_day_profit_pct: 40.0` does not appear in the Stellar 2-Step rules. A 40% consistency rule appears
   only as a remedial "On-Demand Performance Reward" arrangement. Remove it or verify it.
6. Missing:
   - Quick Strike;
   - the statistical-arbitrage ban (PAIR_DIVERGENCE off);
   - one-sided betting;
   - hyperactivity;
   - the same strategy from challenge to funded;
   - the 00:00–02:00 settlement window;
   - first withdrawal after 21 days.

---

## 9. Draft emails for the owner to send

These are drafts only: nothing was sent. The owner fills in his name and account IDs. The addresses are those shown on
each firm's own pages (FTMO: `support@ftmo.com`; The5ers: `help@the5ers.com`; Atlas: `support@atlasfunded.com`). For E8
and FundedNext, use their help-centre contact channel.

### 9.1 To FTMO — send first

> **Subject:** Automated trading through the cTrader Open API from a Linux VPS — questions before purchase
>
> Hello, I live in Kenya and plan to buy an FTMO Challenge 2-Step, Swing account type, $10,000 USD, on cTrader. My
> trading is fully automated: a Python program I wrote myself runs unattended on my own Linux VPS (hosted outside the
> United States) and connects to my cTrader account through the cTrader Open API, authorised with my own cTrader ID.
> Every position carries a stop-loss resting on the server, and the program places well under 50 order operations a day.
> Could you please confirm in writing:
> 1. Is it permitted for such a self-developed, unattended program to trade my FTMO cTrader accounts through the Open
>    API — Free Trial, FTMO Challenge, Verification and the FTMO Account (Swing)?
> 2. For the limit of "2,000 server requests per day", which messages count: only opening, modifying and closing trades
>    and pending orders, or also price subscriptions, position/account reconciliation queries and heartbeats sent over
>    the Open API?
> 3. On a Swing account, how is the "gap trading" practice applied? (a) What time window around a scheduled release
>    counts as "opening simulated trades when major … news … are scheduled", and which calendar defines the events?
>    (b) For "two hours or less before a relevant financial market is closed for at least two hours", which closures
>    count — the weekend and holidays only, or also daily breaks on particular symbols?
> 4. Does clause 9.4.6 of the Terms ("use automated means to view, display or collect information available through the
>    Website, the Services or the Content") apply to a trading program reading prices and account state through the
>    Open API?
> 5. Does the cTrader Free Trial use the same servers, symbols and price feed as the paid Challenge and the FTMO
>    Account, and does the Open API work with Free Trial accounts?
> 6. For EURUSD and USDJPY on cTrader: minimum volume, volume step, commission per lot and typical spread? Does the 0.7%
>    currency conversion adjustment (clause 5.3.4) apply to USDJPY on a USD account?
> 7. Risk per Trade Idea (clauses 7.5 and 7.6.6): if a limit is applied to my account, will you tell me the exact
>    percentage in advance? Would simultaneous positions in EURUSD and USDJPY be treated as one trade idea?
> 8. Can a resident of Kenya receive Rewards by bank wire and by cryptocurrency?
> Thank you.

### 9.2 To E8 Markets

> **Subject:** Automated trading on cTrader via the Open API — E8 Pro, Kenya
>
> Hello, I am a Kenyan resident considering an E8 Pro account (Classic Markets, $10,000) on cTrader. My trading is a
> self-developed Python program running unattended on my own Linux VPS, connected through the cTrader Open API; every
> position has a server-side stop. Please confirm in writing:
> 1. Is trading an E8 cTrader account through the Open API by such a program permitted in both the Challenge and the
>    Performance account?
> 2. Is a VPS in another country (not the US) permitted, and must I notify you of its location or IP?
> 3. Which timezone is "00:00 Server Time" for the Daily Drawdown reset — is it aligned to 17:00 New York?
> 4. For "Server requests per day: 2000", which messages count (orders and modifications only, or also data and account
>    queries)?
> 5. For the rule that no more than 50% of trades may be held under one minute — over what period is it measured, and
>    does a partial close count as a trade?
> 6. Which payout methods are available to a resident of Kenya?
> 7. Are the rules of a purchased account fixed for its life, or can later changes apply to it?
> 8. EURUSD and USDJPY on cTrader: minimum volume, volume step and commission?

### 9.3 To FundedNext

> **Subject:** EA add-on on MT5 for an external Python program — Stellar 2-Step $6K
>
> Hello, I am a Kenyan resident. I understand automation is not allowed on cTrader or Match-Trader. Please confirm:
> 1. If I buy the EA and VPS add-ons on a Stellar 2-Step $6K MT5 account, may the account be traded by my own external
>    Python program controlling the MT5 terminal (MetaTrader5 Python package), unattended? What do the two add-ons cost?
> 2. Does the VPS add-on mean your VPS, or permission to use my own? May the terminal run on Linux under Wine?
> 3. Would holding a long USDJPY and a short EURUSD position at the same time — a two-leg position that is roughly
>    USD-neutral — be treated as the prohibited "statistical arbitrage"?
> 4. My program re-optimises its parameters on a schedule, with the same method and instruments throughout. Would that
>    count as "switching strategy" between the Challenge and the FundedNext Account?
> 5. Which timezone is "00:00 server time"? Is weekend holding allowed on Stellar 2-Step?

### 9.4 To The5ers

> **Subject:** Request for written approval of Automated Trading Software — High Stakes
>
> Hello, under your Terms ("Use of Automated Trading Software") I request written approval for a program I wrote myself
> and own the source code of: a Python engine on my own Linux VPS, trading MT5 with a visible server-side stop on every
> position, holding positions from minutes to about two days, typically fewer than 10 trades a day across 2–8 currency
> pairs and gold, never hedging and never trading news releases.
> 1. Will you approve it, and what advance testing do you require?
> 2. Does "bulk trading" prohibit a single program holding several positions on *different* instruments that were opened
>    at different times? Is there a maximum number of concurrent positions?
> 3. Is any access other than the MT5 terminal available (an API)?
> 4. Which timezone is "00:00 server time"?
> 5. Is the High Stakes fee refunded with the first payout? Your Terms say evaluation fees are non-refundable once
>    trading starts.

### 9.5 To Atlas Funded

> **Subject:** Eligibility from Kenya and automated trading
>
> Hello, before purchasing:
> 1. Are residents of Kenya accepted through KYC, and can they receive payouts? By which methods?
> 2. My trading program runs on a VPS in another country. What notice or approval do you need under the rule on trading
>    from geographically inconsistent locations?
> 3. May a self-developed program trade through the TradeLocker or Match-Trader API, and is fully automated trading
>    permitted on funded accounts?

---

## 10. What I could not verify

**OANDA**
- Whether a **legacy OANDA practice token** still works. This is the owner's one-command test.
- What `hub.oanda.com/apply/demo/` offers a Kenyan. It is a script-only app; browser automation is disallowed and I
  created no account.

**FTMO**
- Explicit permission for **unattended Open API trading on a funded FTMO account**. It is advertised, but no page states
  it.
- What counts toward the 2,000-request cap.
- The gap-trading windows.
- Minimum volume and step on its cTrader symbols.
- Whether the Free Trial runs on the same servers as the paid products.
- Swing leverage (the prior pass said 1:30; not re-fetched).

**E8**
- VPS policy, the server timezone, Kenyan payout rails.
- The product-to-price mapping, which I inferred from page data.
- Operating history.

**FundedNext**
- Weekend holding on Stellar 2-Step, the server timezone, the add-on prices, whether a "Swing" product exists, the
  founding year.

**The5ers**
- Payout methods, the server timezone, whether approval is ever granted to algorithms, and the price mapping (page
  order).

**Apex**
- I could not fetch the live support centre, because it is geo-blocked. Its automation text rests on a March 2026
  archive **(a)** and the search index's rendering **(a−)**.

**Other firms**
- Atlas: Kenya eligibility and API permission.
- Darwinex Zero: Kenya eligibility, API, price.

**Kenya**
- The legality and tax treatment of prop payouts for a Kenyan resident. No Kenyan regulator publication on prop
  programmes was found. The September 2026 CMA warning, known only through press reports, names 15 entities, none of
  them on the shortlist **(b/c)**.
- The5ers' T&C puts the burden on the user: *"By using the Services, You explicitly state that you have verified in
  your own jurisdiction if your use of the Services is legally allowed."* **(a)**

**Industry and venue behaviour**
- Payout-dispute rates: forum and aggregator evidence only **(c)**.
- The MetaQuotes 2024 and MyFundedFX facts: trade press or aggregators **(b/c)**; primary sources not fetched.
- How any firm's simulated server fills a gapped stop (GAP-P12D-42). Only the ACIS-06 conformance suite can show it.
- How far back cTrader historical bid/ask data goes on FTMO's server.

---

## 11. Residual risk

- **Rules move under a live account.**
  - FTMO gives 7 days' notice of term changes (T&C 15.1).
  - The5ers' changes are *"effective immediately upon posting"*.
  - E8 edits its rules weekly.
  - The rulebook is only as true as the day it was committed. Re-verify at every phase change and payout.
- **Discretion cannot be modelled.** Examples: FTMO 7.3, 7.4 and 7.6; FundedNext's risk parameter; E8's 1% de-risk;
  The5ers' "justified concerns". An automated engine can be fully compliant with the published numbers and still be
  restricted.
- **The counterparty is the firm.** Every firm says the environment is simulated, there is no regulator (FTMO T&C 2.1),
  and payouts depend on the firm's solvency and goodwill. My Forex Funds froze traders for about 21 months even though
  the regulator's case failed.
- **Platform-vendor risk.** MetaQuotes withdrew prop licences in 2024. cTrader is Spotware's platform, a similar single
  point of failure.
- **The prop route cannot manufacture edge.** GAP-P12D-49 stands. A funded account adds a terminal kill-switch; it does
  not add alpha.
- **Coupling.** Making the destination firm the demo venue couples plumbing mistakes to the owner's standing there
  (T&C 7.9).

---

## 12. Ledger items this pass should generate (proposed; no IDs assigned)

1. **Four rulebook entries are wrong about the world.**
   - `fundednext`: platform and EA claim.
   - `the5ers`: platform and news.
   - `ftmo`: max-loss basis is balance, so looser than the real rule; the daily stand-in has the wrong semantics.
   - `atlas_funded`: min-hold.

   Severity high · Likelihood high · Status open. **[impl — human-commit config]**
2. **The §9.5 schema cannot express the real prop rulebooks.** It lacks daily-reset rules (instant, zone, % of initial,
   day-start anchor), a declared initial capital, request and order caps, an always-on pre-close entry ban, news
   open/close and profit-split semantics, distributional hold-time rules, profitable-day thresholds, daily profit caps,
   per-trade risk caps and rules that differ by phase. Two fields are carried and enforced nowhere.

   Severity critical · Likelihood high · open. **[spec — owner ratification]**
3. **A process restart re-bases every platform drawdown anchor and the engine day-open.** Reproduced: after a restart at
   −6%, all measures read 0.0%. The static anchor is the first observed basis, not the declared initial capital. This
   violates GAP-0050's "a restart is never a relaxation".

   Severity high · Likelihood medium · open. **[impl — guardrail-adjacent, raise not fix]**
4. **The absolute $9,000 equity floor halts any account under $9k at start-up** and sits on the firm's max-loss line at
   $10k. It needs to be account-relative and above the firm's line.

   Severity critical · Likelihood high · open. **[spec — owner ratification; guardrail value]**
5. **Orders are below the venue minimum lot.** The typical order is about 330 units against a probable 1,000-unit
   minimum. The orchestrator never checks `min_lot` or `lot_step`. NAV-relative sizing is needed for prop accounts.

   Severity high · Likelihood high · open. **[impl]** for rounding and the check; **[spec — owner ratification]** for
   the sizing base.
6. **No request budget exists anywhere in `core/execution/`.** FTMO and E8 cap requests at 2,000 per day; the planted run
   sized about 2,700 per day (GAP-0075).

   Severity critical · Likelihood high · open. **[impl]**, inside the GAP-0075 runtime fix.
7. **The pre-close entry ban exists only when weekend holding is disallowed.** FTMO forbids opening trades up to 2 hours
   before a close of 2 hours or more, and when major news is scheduled, on every account. This refutes the prior pass's
   claim that "Swing removes the event calendar".

   Severity high · Likelihood high · open. **[impl]** plus **[spec]** for the field. Linked: GAP-P12D-03.
8. **Master §9.5 requires flattening before a weekend ban window; the code only bans entries.**

   Severity medium · Likelihood medium · open. **[impl]**
9. **Engine day (17:00 New York) ≠ firm day (00:00 CE(S)T or server time), and platform and engine limits halt entries
   but never flatten.** Two engine budgets can fall inside one firm-day, which is a breach path at 2.5–3% daily limits.

   Severity high · Likelihood medium · open. **[spec — owner ratification]** (per-account daily boundary; pre-breach
   flatten). Linked: GAP-0010.
10. **A new OANDA practice account is not obtainable by a Kenyan resident.** The demo of record should be the FTMO Free
    Trial on cTrader via the Open API, which is a SPEC §15 deviation (draft text in §7).

    Severity high · Likelihood high · open. **[spec — owner ratification]**. Linked: GAP-P12D-43.
11. **Shortlist update.** Drop Apex (automation ban, Kenya geo-block, intraday futures). Add E8 Markets. Record Topstep
    and Alpha Capital as out, and The5ers and FundedNext as conditional.

    Severity medium · Likelihood high · open. **[owner decision]**
12. **FTMO's 0.7% currency adjustment hits 4 of 8 declared instruments** (1 of 2 enabled), correcting the prior pass's
    5. Its expectancy drag is 0.007·(PF+1)/(PF−1), or 7.7% at PF 1.2. Add it to the C8 cost model per instrument and
    account.

    Severity medium · Likelihood high · open. **[impl]**
13. **Module eligibility per account.**
    - PAIR_DIVERGENCE is prohibited "statistical arbitrage" at FundedNext, and discretionary at FTMO and The5ers.
    - Sub-minute trades breach E8's HFT rule, FundedNext's Quick Strike and Atlas's 3-minute minimum if GAP-P12D-38's
      zero-duration trades are live behaviour.

    Severity medium · Likelihood medium · open. **[spec — owner ratification]**. Linked: GAP-P12D-38.
14. **Deployment constraint:** the engine's VPS must not geolocate to the US (FTMO FAQ; E8's restrictions on US clients),
    and must be disclosed where a firm asks (Atlas).

    Severity medium · Likelihood medium · open. **[impl]**
15. **Evidence for GAP-P12D-44:** each firm's own simulation disclosure, and FundedNext's "monetize the trading flow".

    Severity info. Attach to GAP-P12D-44.
16. **The legal and tax status of prop payouts for a Kenyan resident is unassessed.** The firms put the burden on the
    user.

    Severity medium · Likelihood low · open. **[owner decision — professional advice]**

---

## 13. Sources

All were fetched on **2026-09-24** unless stated. The date after each page is its own modified or updated stamp where
it shows one.

**FTMO (a)**
- https://ftmo.com/en/forbidden-trading-practices/ (2026-02-02)
- https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/ (2026-05-27)
- https://ftmo.com/en/trading-platforms/ (2026-08-31)
- https://ftmo.com/en/faq/how-do-i-log-in-to-ctrader/
- https://ftmo.com/en/faq/can-i-travel-or-use-vpn-vps/ (2026-08-24)
- https://ftmo.com/en/faq/do-i-have-to-close-my-positions-overnight-or-before-the-weekend/ (2026-04-27)
- https://ftmo.com/en/faq/can-i-trade-news/ (2026-09-03)
- https://ftmo.com/en/faq/is-the-swing-account-type-available-for-ftmo-challenge-1-step/ (2026-05-28)
- https://ftmo.com/en/faq/ftmo-swing-account-type/ (2026-07-27)
- https://ftmo.com/en/trading-objectives/ (2026-05-13)
- https://ftmo.com/en/faq/who-can-join-ftmo/ (2026-02-13)
- https://ftmo.com/en/faq/how-do-i-withdraw-my-profits/ (2026-04-27)
- https://ftmo.com/en/faq/is-the-entry-fee-refunded/ (2026-04-27)
- https://ftmo.com/en/faq/when-do-i-complete-ftmo-identity/ (2026-04-27)
- https://ftmo.com/en/ftmo-free-trial/ (2026-05-12)
- https://ftmo.com/en/faq/how-about-a-free-trial/ (2026-05-05)
- https://ftmo.com/en/ (embedded `ftmoPricingTable`; 2026-09-22)
- FTMO Challenge Terms and Conditions, "LAST UPDATED ON 4 AUGUST 2026":
  https://cdn.ftmo.com/docs%2Fterms-and-conditions%2Ff8d5ca5086964c86a6ee2a77f20bdbd7 (PDF; text extracted)
- https://ftmo.com/en/press-release/ftmo-completes-acquisition-of-oanda-from-cvc/ (published 2025-12-02)
- https://ftmo.com/en/press-release/ftmo-launches-ftmo-futures/ (published 2026-09-17)
- https://ftmo.com/en/futures/forbidden-trading-practices/ (2026-09-22)

**E8 Markets (a)**
- help.e8markets.com articles:
  - 5515409 (2026-05-14)
  - 6929927 (2026-09-23)
  - 9799834 (2026-09-23)
  - 5514278 accepted countries (2026-09-11)
  - 13106558 (2026-09-23)
  - 15274219 E8 Pro (2026-09-23)
  - 11775980 E8 One (2026-09-23)
  - 11769446 daily drawdown (2026-09-23)
  - 11782996 dynamic drawdown (2026-09-23)
  - 8480398 (2024-05-17)
- https://e8markets.com/ (embedded price data)

**FundedNext (a)**
- help.fundednext.com articles:
  - 8020763 (2026-09-08)
  - 8388896 (2026-04-07)
  - 8020351 (2026-09-22)
  - 8021076 (2026-09-08)
  - 8019811 (2026-04-08)
  - 8020084 (2026-08-11)
  - 8224149 (2025-10-13)
  - 8020293 (2026-07-31)
- https://fundednext.com/general-rules/cfds/what-is-allowed
- https://fundednext.com/general-rules/cfds/trading-objectives
- https://fundednext.com/ (embedded price data)

**The5ers (a)**
- https://the5ers.com/faqs/prohibited-trading-practices/
- https://the5ers.com/terms-and-conditions/ (Last update Sep. 23rd 2026)
- https://the5ers.com/faqs/can-i-use-an-ea-expert-advisor-can-i-set-a-stealth-mode-stop-loss/ (22 Jul 2026)
- https://the5ers.com/high-stakes/
- https://the5ers.com/hyper-growth/
- https://the5ers.com/bootcamp/
- https://the5ers.com/faqs/what-is-the-drawdown-rule-for-high-stakes/ (15 Sep 2026)
- https://the5ers.com/faqs/what-is-drawdown-and-how-is-it-calculated/ (22 Jul 2026)
- https://the5ers.com/faqs/how-do-you-define-a-profitable-day-in-the-high-stakes-program/ (5 Jul 2026)
- https://the5ers.com/faqs/2-step-plan-rules-specifications/ (7 Sep 2026)

**Apex**
- https://apextraderfunding.com/help-center/performance-accounts-pa/prohibited-activities/: live response HTTP 403,
  "country ... blocked" (observed) **(a)**
- Wayback capture http://web.archive.org/web/20260325193331/https://apextraderfunding.com/help-center/getting-started/prohibited-activities/
  (page 2026-03-13) **(a)**
- https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities (search-index rendering
  only) **(a−)**
- Egress geolocation: https://ipinfo.io/json → KE, Nairobi (observed)

**Topstep (a)**
- https://help.topstep.com/en/articles/11187768-topstepx-api-access (2026-09-17)

**Atlas (a)**
- https://help.atlasfunded.com/en/articles/9903318-are-there-any-geographical-restrictions-for-joining-atlas-funded (2025-02-20)
- https://help.atlasfunded.com/en/articles/9904237-what-are-the-prohibited-trading-activities-at-atlas-funded (2026-06-05)

**Alpha Capital (a)**
- https://help.alphacapitalgroup.uk/en/articles/6934236-can-i-use-an-expert-advisor-ea (2026-09-07)

**Darwinex Zero (a)**
- https://www.darwinexzero.com/capital-allocation
- https://www.darwinexzero.com/pricing

**cTrader (a)**
- https://help.ctrader.com/open-api/
- https://raw.githubusercontent.com/spotware/openapi-proto-messages/main/OpenApiMessages.proto (last commit 2025-11-13)

**OANDA (a)**
- https://developer.oanda.com/rest-live-v20/introduction/
- https://www.oanda.com/ → /bvi-en/ (observed routing)
- https://www.oanda.com/bvi-en/skills-and-insights/education/platforms-and-tools/oanda-platforms/how-to-create-demo-account/
- https://fxtrade.oanda.com/your_account/fxtrade/register/gate?... → HTTP 523 (observed)
- https://www.oanda.com/apply/demo/ → hub.oanda.com (script-only)

**Regulation and industry**
- https://complianceconcourse.willkie.com/articles/new-jersey-federal-judge-dismisses-forex-case-with-prejudice-and-awards-attorney-fees/ (2025-05-26) **(b)**
- CFTC Special Master report, https://www.cftc.gov/media/12106/ogc_KazmiReportRecommendationSactions051325/download
  (listed by search; not fetched) **(a, unread)**
- https://theindustryspread.com/retail-prop-trading-regulation-2026-my-forex-funds-cftc/ **(c)**
- Finance Magnates on MetaQuotes and prop firms (2024), via search results only **(b, unread)**
- MyFundedFX closure: aggregator pages via search **(c)**
- CMA Kenya warning, September 2026: press via search **(b/c)**
- Payout-dispute threads on Forex Peace Army and aggregators, via search **(c)**

**Repository (read-only, `main` @ `7695ed0`)**
- `config/guardrail_limits.yaml:13`
- `config/system_config.yaml:3`
- `config/platform_rules.yaml`
- `config/schemas.py:450-468`
- `config/instruments.yaml`
- `config/account_doctrine.py`
- `core/governor/capital_governor.py:283-298,336-340,353-360`
- `core/governor/units.py:23`
- `core/execution/orchestrator.py:99,136-152`
- `core/execution/venue.py:25,119-120`
- `core/risk/guardrails.py:72-79,90,122,220-251`
- `core/risk/store.py`
- `tests/backtest/harness.py:180-191`
- `ACIS_SPEC.md:257,280,297-299,368`
- `KNOWN_GAPS.md` (GAP-P12D-31, 41–47, 49, 52; GAP-0075)
- `archive/RESEARCH_VENUE_CHOICE_2026-09-17.md`
