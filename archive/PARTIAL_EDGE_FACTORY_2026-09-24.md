# PARTIAL — ARCHITECT checkpoint, five-agent edge pass (2026-09-24)

**Stage 1 recorded:** 2026-09-24T11:38:25Z (host UTC clock). Stage 2 had not started when this was written.
**Status:** STAGE 1 COMPLETE. STAGE 2 IN PROGRESS. The brief was read at 2026-09-24T11:40Z, after this Stage 1 text was written.
**Asked by:** the five-agent edge-pass lead (Opus 5.5 session), under brief §4 (ARCHITECT), GAP-P12D-52.
**Progress at 2026-09-24T12:40Z:**
- Read: spec §§0–18, ACIS-04, `core/signals/agon.py`, the four prior reports, and GAP-P12D-49/40/39/45, GAP-0075 and GAP-0035.
- Fetched: the agentic-quant abstracts.
- Found:
  - spec §5.6 misstates the century trend study: the net-of-fee Sharpe is 0.76, not "≈0.4 every decade";
  - the `platform_rules.yaml` FTMO drawdown semantics contradict FTMO's own page.
- Protocol breach: the synthetic sizing-band run started with 835 MB free, below the 1 GB rule. It was tiny, and it is disclosed in the report.

**COMPLETE 2026-09-24T12:55Z.** The deliverable is `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md`. This file stays as the timestamped Stage 1 record. Its Stage 1 text below has not been edited since 11:38:25Z. One quote in it (Baltussen–van Bekkum–Da) joins fragments out of order; the final report corrects it (§1 and §4, H3).

## Independence statement (read this before trusting Stage 1)

- **Not opened before this record:** `ACIS_SPEC.md`, `specs/`, `KNOWN_GAPS.md`, `TODO.md`, `CLAUDE.md`, `STATUS.md`, `README.md`, `archive/` (the only check was a glob for this file's own name, which found nothing), and `FIVE_AGENT_BRIEF_2026-09-24.md`.
- **Read, as the protocol allows:** `config/instruments.yaml`. It enables EUR_USD and USD_JPY. It declares, disabled: USD_CHF, XAU_USD, GBP_USD, AUD_USD, USD_CAD and EUR_GBP. It declares no index CFDs and no energies.
- **Contamination disclosure.** At session start the harness put `CLAUDE.md` and the owner's memory index into my context. I did not open either file, but I have seen their text. That text says the following about ACIS:
  - the engine loses on its own planted positive control;
  - TSMOM is the whole loss, and MEAN_REVERSION gives the edge back;
  - the venue is a ~$6k prop-firm account.

  I have tried not to lean on these claims. Where Stage 1 agrees with them (for example, the low weight it gives to slow TSMOM), the agreement is less independent than it looks. Every such conclusion below is argued from external sources alone.
- **Scratch work:** one synthetic Monte Carlo (numpy; no real data, nothing under `data/`), in `scratchpad/architect/prop_barrier_mc.py`.

## Evidence grades

- **(a)** peer-reviewed, regulator, or primary.
- **(b)** a credible practitioner with a verifiable record.
- **(c)** unverifiable: affiliates, EA vendors, prop-firm blogs, aggregators.

All URLs were accessed on 2026-09-24.

---

## 0. The answer in one paragraph

Do not bet the account on one big directional model. The account is a **survival-constrained contract that pays for variance**, so passing it is weak evidence of skill. What earns money beyond that lottery value is **breadth**: many small, independent, low-cost bets whose mechanism can be named. Those bets should be mostly **intraday and flat at the close**, in the instruments that are cheapest per unit of volatility: US and EU index CFDs, gold and WTI first, and FX majors and crosses only for **flow and fixing effects**, not for generic technical rules. Combine them at a **portfolio daily volatility of about 0.5–0.7% of initial capital**. Use a hard internal daily stop at half the firm's limit, and cut risk in proportion to the headroom left above the static floor. Find the edges through a **pre-registered hypothesis registry**:
- one shared cost model;
- global trial accounting (Deflated Sharpe, PBO, t > 3);
- a sealed holdout that is used once;
- **≥ 3 months of forward incubation on demo**, with kill rules written down in advance.

Expect live Sharpe to be roughly **half** of the backtest.

**Three-line thesis**
1. The contract pays for variance, so passing is weak evidence. What pays beyond that is breadth: many small, cheap, independent bets with named mechanisms, run at ~0.5–0.7%/day portfolio volatility.
2. The documented, prop-compatible edges are mostly intraday flow and microstructure effects. They sit in index CFDs, gold and oil, and in FX fixings and time-of-day patterns, not in generic trend or technical rules on FX majors. Slow TSMOM is a small diversifier at most.
3. Only pre-registered, trial-counted, cost-stressed results that survive a sealed holdout and demo incubation count. Everything else is a draw from the overfitting distribution.

---

## 1. What the venue actually rewards

### 1.1 The rules (FTMO 2-Step, the reference prop contract)

These are from the FTMO trading-objectives page, last modified 2026-05-13, https://ftmo.com/en/trading-objectives/ — grade (a), primary for FTMO.
- **Daily loss** is "recalculated daily at 00:00 CE(S)T as the difference between: the account balance recorded at 00:00 CE(S)T of the current day and the Maximum Daily Loss Amount". The amount is 5% of initial capital on 2-Step and **3% on 1-Step**. What counts is "equity (i.e., Balance + Open Positions P/L ± Swaps – Commissions)".
- **Maximum loss** on 2-Step is a "static limit" = initial capital minus 10%. On 1-Step it is an "end-of-day trailing limit".
- **Profit target**: 10% for the Challenge and 5% for Verification. Minimum "at least 4 Trading Days".
- **Best Day Rule** (1-Step, and for Rewards on an FTMO Account): "your Best Day does not represent more than 50% of your Positive Days' Profit".

These are from the forbidden-practices page, last modified 2026-02-02, https://ftmo.com/en/forbidden-trading-practices/ — grade (a):
- Gap trading means "opening simulated trades: when major global news, macroeconomic events, or corporate reports or earnings are scheduled and they might affect the relevant financial market …; or two hours or less before a relevant financial market is closed for at least two hours".
- "hedging or holding opposing positions on the same or highly correlated instruments, or partially closing and managing the same trade idea across multiple trading days, in order to circumvent the Best Day Rule".
- EAs "causing … more than 2,000 server requests per day".
- "use any software, artificial intelligence, ultra-high-speed tools, or mass data entry that might manipulate, abuse, or give you an unfair advantage".
- "overleveraging, overexposure, one-sided bets, account rolling".

These are from the FTMO FAQ, modified 2026-05-27, https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/ — grade (a):
- Algorithmic trading is permitted.
- "if you use an EA from a third party, there might be other traders already using the same EA … you potentially run a risk of being denied the FTMO Account".
- Server limits are 200 simultaneous orders and 2,000 positions a day.

Two rules come from grade (c) secondary sources only; I could not fetch FTMO's own page for them (https://tradingfinder.com/props/ftmo/rules/):
- funded "Normal" accounts may not open or close a trade from 2 minutes before to 2 minutes after a restricted news release;
- weekend holding is not allowed on funded Normal accounts, but is allowed on Swing accounts.

**Design consequences.**
- The engine must run on the **firm's clock** (00:00 CE(S)T), not on UTC or the New York close.
- It needs a **scheduled-event calendar**, both for the news blackout and for the gap-trading rule.
- It may open **no new positions within 2 h of a ≥ 2 h closure**, such as the weekend.
- It must stay **within the request budget**.
- A **custom strategy is better than an off-the-shelf EA**, because of the "sameness" rule.

### 1.2 The contract is a barrier option that pays for variance

Lim, B. C. (2026-07-25), "The Price of a Funded Account: An Actuarial Analysis of Proprietary Trading Firm Challenges", SSRN 7178078, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7178078. The fetch returned HTTP 403, so the quotes come from the search-engine abstract. Grade (b/c): an unrefereed working paper whose model is reproducible. Its claims:
- "A zero-edge trader passes the frictionless benchmark with probability 0.50 but the baseline contract with probability 0.30".
- "Contract value concentrates on a narrow risk-sizing ridge near 2 per cent daily volatility".
- "the model-implied average value of a USD 500 challenge is USD 221".

**My own synthetic reproduction.** The model:
- t(4) daily tails, 16 intraday steps a day, and the strategy is flat at each day end;
- the FTMO 2-Step rules above, with each phase capped at 250 trading days;
- a funded year that pays 80% of the profit every 21 days and ends at the first breach.

| net SR | daily vol (% of initial) | P(pass both phases) | median days to pass both | P(funded breach within 1 yr) | E[paid in 1 yr] (% of initial) |
|---|---|---|---|---|---|
| 0.0 | 0.5 | 0.09 | 256 | 0.31 | 4.0 |
| 0.0 | 1.0 | **0.25** | 127 | 0.84 | 6.6 |
| 0.0 | 2.0 | 0.20 | 35 | 1.00 | 5.0 |
| 0.5 | 1.0 | 0.40 | 122 | 0.75 | 9.3 |
| 1.0 | 0.5 | 0.41 (43% still unresolved at 250 d) | 238 | 0.12 | 8.0 |
| 1.0 | 1.0 | 0.57 | 115 | 0.64 | 13.0 |
| 2.0 | 0.5 | 0.80 | 198 | 0.04 | 13.4 |
| 2.0 | 1.0 | 0.77 | 91 | 0.47 | 22.4 |

**What the table says:**
1. A **zero-edge** algorithm at ~1%/day passes both phases about **1 time in 4**, and harvests about 6–7% of initial capital a year in funded payouts before it dies, because losses are capped and gains are paid out.
2. So "a minority is crushing it" is **exactly what zero skill plus survivorship produces**, whatever else is going on.
3. A real SR of 1 lifts the pass odds only from 0.25 to 0.57.
4. **Survival** is what separates edge from lottery. At 1%/day even SR 2 blows the funded account within a year about half the time. At 0.5%/day the chance is about 4%.
5. On a ~$6k account, a real SR-1 edge at a survivable volatility is worth only **hundreds of dollars a year** (8% × $6k ≈ $480 gross). The real prize is a **verified live record** that can be scaled across accounts, not the income from this one.

**Base rates** — so we do not mistake survivors for method:
- Chague, De-Losso & Giovannetti (2020), "Day trading for a living?", https://ideas.repec.org/p/fgv/eesptd/525.html — grade (a), working paper by academic authors. Of individuals who persisted ≥ 300 days, "97% of them lost money, only 0.4% earned more than a bank teller (US$54 per day)".
- Industry pass and payout figures come from aggregators only, grade (c), https://www.quantvps.com/blog/prop-firm-statistics: ~5–15% pass, "only 7% ever receive a payout", and 1–3% stay funded for more than six months. They are not verifiable.
- **There is no public primary data on what profitable prop algo traders actually do.** FTMO's "Trader's Analysis" blog posts are single-trader anecdotes (e.g. https://ftmo.com/en/blog/traders-analysis-long-term-statistics-you-wont-find-elsewhere/, 2023-07-21 — grade (c)). So "copy the minority" cannot be done from evidence. It has to be replaced by "copy the mechanisms that the literature shows survive costs".

---

## 2. Where the edge evidence actually is

### 2.1 Negative and decay evidence (what not to build on)

**FX technical rules on majors.**
- Neely & Weller (2003), JIMF 22(2), https://ideas.repec.org/a/eee/jimfin/v22y2003i2p223-237.html — grade (a): "When realistic transaction costs and trading hours are taken into account, we find no evidence of excess returns to the trading rules".
- Neely & Weller (2013), JBF 37(10), https://ideas.repec.org/a/eee/jbfina/v37y2013i10p3783-3798.html — grade (a): "trading rule returns still exist in forex markets … though they have migrated to emerging markets to a considerable degree".
- **The edge does not live in generic TA on FX majors.**

**TSMOM on single assets.**
- Huang, Li, Wang & Zhou (2020), JFE 135(3), https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html — grade (a): "asset-by-asset time series regressions reveal little evidence of TSM, both in- and out-of-sample … its performance is virtually the same as that of a similar strategy that is based on historical sample mean".
- Industry reality, via Top Traders Unplugged, 2025-07-23, https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/ — grade (b), with SG index data: the SG Trend Index has an "annualized return of 4.90% since 2000", a "max drawdown … 20.61%", and a "12-month trailing loss … -15.05%" (June 2025).
- **A 20% drawdown profile does not fit a 10% static max loss** unless it is run at a volatility too low to reach the target.
- The supporting evidence is real but diversified and slow. Moskowitz, Ooi & Pedersen (2012), JFE 104(2), https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html — grade (a): "a diversified portfolio of time series momentum strategies across all asset classes delivers substantial abnormal returns". **The key word is diversified.** Two FX majors do not qualify.

**The carry trade.**
- Brunnermeier, Nagel & Pedersen (2008), NBER Macro Annual 23, https://ideas.repec.org/h/nbr/nberch/7286.html — grade (a): "carry traders are subject to crash risk … negatively skewed".
- A negative-skew payoff under a hard daily-loss barrier is the wrong shape.

**Calendar anomalies that decayed.**
- Lucca & Moench (2015), JF 70(1), https://ideas.repec.org/a/bla/jfinan/v70y2015i1p329-371.html — grade (a), documented the pre-FOMC drift.
- Kurov, Wolfe & Gilbert (2020), FRL 40, https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/ — grade (a): "the pre-FOMC drift essentially disappeared after 2015".
- **Published calendar effects decay. Pre-register the decay test.**

**Volatility management as alpha.**
- Cederburg et al. (2020), JFE 138(1), https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html — grade (a): "Volatility-managed portfolios do not systematically outperform … out-of-sample". Use volatility targeting for **risk control** (the daily-loss barrier), not as a source of return.

### 2.2 Positive evidence that fits the prop contract (intraday, flat by the close)

1. **Index and futures intraday momentum into the close.**
   - Gao, Han, Li & Zhou (2018), JFE 129(2), https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html — grade (a): "the first half-hour return … predicts the last half-hour return … stronger on more volatile days … on major macroeconomic news release days".
   - Baltussen, Da, Lammers & Martens (2021), JFE 142(1), https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html — grade (a): "over 60 futures on equities, bonds, commodities, and currencies between 1974 and 2020, we find strong market intraday momentum everywhere … reverts over the next days … gamma hedging demand".
   - Li, Sakkas & Urquhart (2022), JFM 57, https://research.birmingham.ac.uk/en/publications/intraday-time-series-momentum-global-evidence-and-links-to-market/ — grade (a): "16 developed markets … significant both in- and out-of-sample in most countries".
   - The practitioner variant: Zarattini, Aziz & Barbon (2024), SFI WP 24-97, https://www.sfi.ch/en/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy — grade (b), unrefereed and a single backtest: SPY 2007–2024, "Sharpe Ratio of 1.33", net of costs.
   - **The mechanism is named (hedging flows), the effect appears across many markets, it is flat at the close, and costs are low relative to index volatility. This is the strongest prior.**
2. **Negative daily serial dependence in equity indices since the 2000s.** Baltussen, van Bekkum & Da (2019), JFE 132(1), https://ideas.repec.org/a/eee/jfinec/v132y2019i1p26-48.html — grade (a): "serial dependence … switches to negative since the 2000s … 20 major market indexes … links to the increasing popularity of index products". This is a multi-day reversal sleeve. It carries overnight, swap and crash-tail costs, so it gets a small weight.
3. **Index overnight drift at the European open.** Boyarchenko, Larsen & Whelan, NY Fed SR 917 (rev. 2022-08), https://www.newyorkfed.org/research/staff_reports/sr917.html — grade (a): "U.S. equity returns are large and positive during the opening hours of European markets … market selloffs generate robust positive overnight reversals". The window falls **after** the 00:00 CE(S)T rollover, so it can be traded intraday on the firm's clock with no swap.
4. **FX flow and time-of-day effects** — the only FX edges I would bet on:
   - Breedon & Ranaldo (2013), JMCB 45(5), https://ideas.repec.org/a/wly/jmoncb/v45y2013i5p953-965.html — grade (a): "a significant tendency for currencies to depreciate during local trading hours".
   - Melvin & Prins (2015), JFM 22, https://ideas.repec.org/a/eee/finmar/v22y2015icp50-72.html — grade (a): "equity market appreciation over the month can be used to predict currency depreciation before the end-of-month fix".
   - Ito & Yamada, NBER w22820 (2016; JIE 2017), https://www.nber.org/papers/w22820 — grade (a): at the Tokyo fixing "customer orders are biased toward buying the foreign currencies, which is predictable … calendar effects also matter". This bears on USDJPY, which is configured.
   - Their samples are older. **Each must first pass a pre-registered decay test** before it earns weight.

### 2.3 Costs are part of the hypothesis

- Carver's *Systematic Trading* (2015), via CXO Advisory 2015-09-30, https://www.cxoadvisory.com/big-ideas/a-few-notes-on-systematic-trading/ — grade (b):
  - "the costs of an instrument's trading system should be at most one-third of a conservative estimate of the pre-cost Sharpe ratio";
  - "SR consistently greater than 1.0 are rarely achieved".
- Index CFD overnight financing at a reference broker, IG, https://www.ig.com/en/help-and-support/cfds/fees-and-charges/why-is-overnight-funding-charged-and-how-is-it-calculated- — grade (a) for IG's own terms, (c) as a proxy for prop firms: the benchmark rate ± an admin fee of about 2.5–3%. **At 4–5% rates a long index CFD pays ~7%/yr of notional to carry.** That makes multi-day index longs expensive and intraday index trading cheap.
- **FTMO's actual spreads, commissions and swaps were not retrievable** (the pages are dynamic). They must be measured on the platform.

---

## 3. What I would build (the Stage 1 design)

**Instruments**, in order of evidence × cost per unit of volatility:
1. **US500, US100, GER40** index CFDs (add JP225 or UK100 later): intraday momentum, overnight drift, and daily reversal.
2. **XAUUSD, and WTI/Brent CFDs**: intraday momentum, because Baltussen covers commodities, plus a small TSMOM diversifier.
3. **FX: USDJPY, EURUSD, GBPUSD, AUDUSD, USDCAD**, and one or two crosses: fixing and time-of-day flows only.

Exclude crypto (24/7 gaps and wide prop spreads), single stocks (earnings and gap rules) and EM or exotic FX (spreads).

**Horizons:**
- The **core is intraday and flat by the firm's day end**: no swaps, no weekend gaps, the daily-loss window is self-contained, and the gap-trading rule is satisfied by construction.
- There is a small **multi-day sleeve** (index reversal, TSMOM), capped at ≤ 25% of risk.

**Strategy sleeves** (the hypotheses to test, with parameters fixed from the literature):
- (S1) Index and futures intraday momentum into the close.
- (S2) Index overnight drift at the European open.
- (S3) Index multi-day reversal, with a volatility-regime filter.
- (S4) Month-end FX hedging flows before the 4pm fix.
- (S5) The Tokyo-fix / gotobi USDJPY pattern.
- (S6) Local-hours FX depreciation.
- (S7) A cross-asset TSMOM diversifier on indices, gold, oil and FX, at low weight.

Carry, pre-FOMC and generic TA on FX majors appear only as **negative controls and decay exhibits**.

**Risk sizing:**
- A portfolio volatility target of **0.5–0.7% of initial capital a day**.
- A **hard internal daily stop at 2.5%**, which is half the 5% rule. It is measured on equity including floating P&L, from the 00:00 CE(S)T balance.
- **Risk proportional to headroom** above the static floor (Grossman & Zhou 1993, Math. Finance 3(3), https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html — grade (a); page paraphrase: the optimal risky investment is "proportional to the 'surplus' W_t − αM_t"). With FTMO's static floor this becomes CPPI: halve risk at −5% and flatten, then hold for a human, at −7%.
- Per-trade risk of 0.25–0.5% of initial capital. Correlation clusters are capped.
- No trade opens within 2 h of a ≥ 2 h closure.
- News blackouts on funded accounts.
- Fewer than 2,000 requests a day.

**Finding and verifying the edge:**
1. A **registry** that records mechanism, market, window, parameters, expected sign and size, and the falsifier **before** any data is touched.
2. **One cost model** for research, demo and live, calibrated from the firm's platform.
3. **Global trial accounting.** Bailey, Ger, López de Prado, Sim & Wu, "Statistical Overfitting and Backtest Performance", https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf — grade (a/b):
   - "if only five years of daily market data are available, and if 45 or more independent variations of a strategy are tried, it is more than likely that the best strategy selected in this process has a Sharpe ratio of 1.0 or better";
   - "the hold-out method does not control for the number of trials";
   - "overfitting a backtest on time series with memory … leads to persistent losses, rather than just zero expected performance".

   Use Deflated Sharpe and PBO with the global N, and require **t > 3** (Harvey, Liu & Zhu, NBER w20592, https://www.nber.org/papers/w20592 — grade (a): "a t-ratio greater than 3.0").
4. **Mechanism checks as well as P&L.** For S1 the effect should be stronger on high-volatility and news days, and it should revert over the following days. If it is not, treat the result as spurious.
5. A **sealed holdout** covering the most recent ~2 years, **opened once**.
6. **Forward incubation on demo for at least 3 months**, with pre-registered kill rules: a sequential test on live returns against the backtest distribution, and a mismatch between modelled and realised costs.
7. **Expect about 50% decay.** Falck, Rej & Thesmar, arXiv 2105.01380 / Quant. Finance 22(11), https://arxiv.org/abs/2105.01380 — grade (a): "The year of publication alone … explains 30% of the variance of Sharpe decay … overfitting … another 15%". So a sleeve enters only if its **deflated OOS SR ≥ 2×** the SR the prop maths needs.
8. **Portfolio assembly** uses fixed equal-risk sleeve weights with correlation caps. There is **no return optimizer**. Wiecki et al. (2016), Quantopian, J. Investing 25(3), via Quantpedia 2016-05-04, https://quantpedia.com/quantopians-academic-paper-about-in-vs-out-of-sample-performance-of-trading-alg/ — grade (a/b):
   - "the Sharpe ratio offer[s] little value in predicting out of sample performance (R² < 0.025)";
   - "the more backtesting a quant has done for a strategy, the larger the discrepancy between backtest and out-of-sample performance";
   - volatility, max drawdown and hedging "show significant predictive value".

**Linux server:**
- cTrader CLI runs cBots headless, with a Linux Docker image, backtesting and optimisation. See Spotware, https://help.ctrader.com/ctrader-cli/ (grade a), and Finance Magnates, 2026-08-13, https://www.financemagnates.com/forex/spotware-launches-ctrader-cli-for-ai-controlled-trading-and-cbots/ (grade b).
- FTMO provisions cTrader through Spotware (Finance Magnates, 2025-10-22, https://www.financemagnates.com/forex/ftmo-instant-funding-begin-using-spotware-demo-accounts-for-prop-firms-on-ctrader/).
- **I could not verify that FTMO permits Open API connections from an external engine.** Keep the engine platform-agnostic behind an adapter. The fallback is a thin cBot bridge.

## 4. Unverified at Stage 1
- Any primary data on what profitable prop algo traders do.
- The full text of Lim (2026): SSRN returned 403.
- FTMO's cost schedule.
- Whether FTMO allows the Open API.
- The McLean & Pontiff decay figures: not fetched, and not used.
- Whether intraday momentum survives on **CFD** prices. A cash CFD has no closing auction, and its "close" window must be mapped to the underlying cash session.
- Gold time-of-day return seasonality: only grade (c) sources, so it is not used.

*End of Stage 1. Stage 2 appends below after reading the brief.*
