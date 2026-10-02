# RESEARCH — PRACTITIONERS: what winning systematic traders at our scale do that ACIS does not (2026-10-02)

- **Who asked, and why.** The owner launched five research agents on 2026-10-02. This is PRACTITIONERS (web search first-class, cap 40). The owner's question: *"what is it that the top algorithmic traders have that we dont, what do those scalpel-sharp algorithms at our level (not HFTs) do that keeps them winning ... we need to ensure that its very tight on losing but not stuck without making trades and making money."*
- **Status.** This is a finder's report (constitution A5): evidence for the lead to verify (A6), never an instruction (A9). Nothing here binds until the lead has re-checked it and the owner has ratified any **[spec]** or **[OWNER]** item.
- **Builds on, does not repeat.** I read three reports in full first: `archive/RESEARCH_EDGE_SHARPEN_2026-10-01.md` (EDGE), `archive/RESEARCH_EDGE_FACTORY_2026-09-24.md` (FACTORY) and `archive/RESEARCH_FX_METHODS_2026-09-16.md` (FX-METHODS). I also skimmed the openings of `RESEARCH_SIZING_AGGRESSION_2026-10-01.md` and `RESEARCH_EXECUTION_COSTS_2026-09-16.md`. Where those reports already settle a point, I cite them and do not search again. I spent my searches on what they did not cover:
  - live and verified records: CTA sub-indices, FX-manager indices, social-trading providers, Darwinex, bank risk-premia products;
  - how named practitioners build systems (Carver, Davey, Chan, QIM);
  - live evidence on regime models and evolutionary search;
  - small-account construction under minimum lots;
  - execution at a daily cadence.
- **Contamination, disclosed.** The harness put `CLAUDE.md` and the owner's memory index into my context, so I knew the GAP-P12D-49 verdict before I started. I am an LLM with a June 2026 cutoff.
- **What I did not do.** I read no market data, ran no backtest, wrote nothing but this file, used no git and launched no agents.
- **Grades.**
  - **(a)**: peer-reviewed; an audited or regulated disclosure; or a firm's own primary document about itself.
  - **(b)**: an experienced practitioner with a public record, an index provider's figures as reported by trade press, or a working paper.
  - **(c)**: blog, forum, aggregator or marketing. **Never fact.**
  - **[D]**: derived here, with the inputs shown.
  - **[repo]**: read in this repository's code or ledger at `9076742`.

  Every URL was read on **2026-10-02**.

---

## Plain-language answer to the owner

**What the winners at our scale have that ACIS does not (yet):**

1. **Many small, different bets, not one clever bet.**
   - Rob Carver trades 100+ futures. Kevin Davey runs about 20 strategies at a time across 40–50 markets.
   - Even a whole index of professional short-term CTAs had a best-ever year of +11.3%.
   - ACIS's 13 FX pairs behave like **about 2 independent bets**: its own declared diversification multiplier of 1.5 implies 1.5² ≈ 2.25 [D].
   - More FX pairs add little. Different *mechanisms* (other trend markets, flow and calendar effects) add a lot.
2. **They trade slowly enough to beat costs.**
   - Every live record that wins at retail cost holds positions for days to months.
   - The intraday ideas that look good before costs net about zero after the spread:
     - opening-range breakouts on five index CFDs;
     - FX fixing reversals at the full quoted spread.
   - In Carver's words, profitable day trading at retail costs *"is an idea that deserves to be rebutted constantly"*.
3. **Few fixed rules, not tuned per regime.**
   - Across 215 bank-built strategies, the live Sharpe was **73% below the backtest** (1.20 → 0.31).
   - The most complex strategies lost about 30% more. Currencies decayed the most, and trend-following the least.
   - ACIS's old design of 12 regimes × an evolved gene set is the profile that degrades most.
4. **"Tight on losing" means small size and wide stops, not tight stops.**
   - A tight stop makes the spread a large share of every bet. On index CFDs, the opening-range breakout's gross edge of about 0.1R was eaten exactly by spread and slippage.
   - Switching a system off after a losing streak (an "equity-curve filter") **cut returns** in Carver's tests of profitable systems, and was *"an unmitigated disaster"* for trend.
   - The tightness belongs in position size (volatility targeting), the daily-loss guard and the prop room. ACIS already has those.
5. **They incubate forward and kill systems by pre-set rules.**
   - Davey watches a new system live, without money, for 6–12 months.
   - They expect losing years. Carver's account made +23.7% net in 2025/26, after **−16.3%** the year before by his year-12 post (EDGE carried −14.7% from the year-11 post).
6. **They expect modest numbers, and the money is mostly noise week to week.**
   - At $10k, 20% volatility and a true Sharpe of 0.5, the expected profit is about **$19 a week**, with a weekly swing of about **±$277**.
   - About 53% of weeks are positive, and about 69% of years [D].

**Where ACIS stands.** The new R1.6 path already copies the core of what works:
- Carver's EWMAC trend on daily bars;
- banded target positions and volatility targeting;
- a wide disaster stop and no take-profit;
- a swap-free venue.

The legacy engine's loss (GAP-P12D-49) is what the literature predicts for its design: 1-minute decisions, tight ATR exits, per-regime evolution and regime gating.

**Three gaps remain:**
- **Breadth.** The book is FX only, at one lot per instrument.
- **A leftover regime gate.** The 1-minute NVMA classifier's confidence veto still blocks the *daily* book's entries, with no retry that day [repo, read in code; how often it fires is unmeasured]. It can silently keep the engine "stuck without trades".
- **Execution.** Orders are market orders. Carver's simple "limit first, then market" routine cut his measured slippage by about 40%.

---

## Q1. Which strategy families demonstrably make money for non-HFT systematic traders at our scale, after costs?

### 1.1 The live and verified evidence, by family

| Family (horizon) | Best live or verified evidence | Typical net Sharpe | Win rate / payoff | Frequency | Drawdown | Survivorship and other caveats |
|---|---|---|---|---|---|---|
| **Diversified trend** (days to months, 50+ markets) | Carver's own futures account (b, year-12 post):<br>• 2025/26 net **+23.7%**, after −16.3% the year before;<br>• the post's comparison table shows *"Stdev 17.3%"* and *"SR (rf=0) 0.80"*. **Read these as the whole record, not one year** (23.7/17.3 would be 1.37); the fetch was ambiguous and the lead should confirm;<br>• vol-adjusted CAGR: *"7.7% (AHL), 8.2% (SG) and 13.0% for me"*. SG Trend about 0.38–0.42 (b, carried from EDGE). Two centuries of backtest: Sharpe **0.8** on futures since 1960 (t ≈ 5), 0.72 on spot since 1800 (a, backtest) | 0.3–0.8 | Below 50% hit rate with positive skew (Man AHL, b). The noise-band replication: 41% wins, payoff 1.69 (c, carried) | Carver's Starter System trades a handful of times a year per instrument (b) | SG Trend maximum 20.6% (b, carried); Carver's 2024/25 −16.3% (year-12 post) or −14.7% (year-11 post, carried) (b) | Index constituents are surviving large managers. **Short trends (about 3 days) "have significantly decayed since 1990"; long trends are stable** (Lempérière et al., a) |
| **FX-only managers** | Barclay Currency Traders Index: 2024 **+11.11%**, "best ... since 1997", first double digits since 2003; positive every year since 2006 except −0.8% in 2017 (b) | not reported | — | — | — | Small, self-reported index, with survivorship. I could not verify the constituent count |
| **Short-term systematic CTAs** (holds under 10 days, multi-sector futures) | SG Short-Term Traders Index: 2022 **+11.3%**, which *"equalled its best yearly return"* and was the best risk-adjusted CTA index that year (b). About 20–27 programs at its 2008 launch (b) | modest; long-run figure not found | — | — | — | **The best year of an index of professional short-term systems is about +11%.** That is the ceiling to keep in mind for "scalpel-sharp" short-term trading |
| **Bank-built alternative risk premia** (carry, value, momentum, volatility, trend; 5 asset classes, 15 banks) | Suhonen, Lennkh & Perez, *JPM* 2017, 215 products: median live Sharpe **0.31 against 1.20 in the backtest**; 65 of 215 negative live (a, read through CXO, b) | 0.3 | — | — | — | Decay *"most pronounced in currencies"* and in event, value and carry; *"least pronounced"* in trend-following and volatility |
| **Retail copy-trading signal providers** (eToro, ZuluTrade and two others; 150 providers, 2012) | Doering, Neumann & Paul, EFMA 2015 working paper: median weekly mean **0.07%**, sd 1.79%, skew −0.21, excess kurtosis about 2, median maximum drawdown 9.6% (b) | **about 0.28** annualised [D: 0.07/1.79 × √52] | — | — | 9.6% median | Restricted to providers with a minimum track record, so it carries survivorship. The paper's own "top half" shows Sharpe ≈ 1 [D], but it was sorted on the same returns, so that number is meaningless as a forecast. **Sorting on realised return manufactures Sharpe** |
| **Darwinex DARWINs** | Firm disclosure: *"53% of retail investor accounts lose money when trading CFDs with this provider"* (a, regulated disclosure). Every DARWIN is risk-normalised to *"maximum 6.5% monthly VaR"* (a) | not published per DARWIN in aggregate; **no survivorship-free study found** | — | — | — | Darwinex's investability attributes reward **risk stability** and penalise **loss aversion**: *"Hold losing positions too long while closing winning positions prematurely"* means *"DARWINs with low La scores are not particularly investable"* (a, firm doc) |
| **FX fixing reversals** (intraday, the W pattern) | Krohn, Mueller & Whelan, *JF* 79(1) 2024, G9 1999–2019: the dollar appreciates into the Tokyo, ECB and London fixes and reverses after (a). **At the full quoted spread, most windows turn negative.** At 50% of the spread, Sharpe is 0.12–1.03. The Tokyo reversal netted flat to negative for EUR and GBP from about 2013 (a) | about 0 at retail cost | — | daily | — | The authors: *"it is not obvious that this can be exploited by the average trader"* |
| **5-minute opening-range breakout on indices** | Zarattini & Aziz, QQQ 2016–23: 24% hit rate, +0.13R gross (b, backtest). Independent CFD replication on NQ, SPX, Dow, DAX and FTSE, 2015–2026: gross +0.05 to +0.13R at 20–23% hit rates, **net about 0 (NQ +0.002R)**, because the spread and slippage are about 0.1R (c, 2026-09-25) | about 0 | 20–24% / about 10:1 target | daily | — | The stop is the first 5-minute range, so cost is a large fraction of R. It is the barrier identity from FX-METHODS §0.2 in another market |
| **FX styles portfolio** (carry + momentum + value) | Kröncke, Schindler & Schrimpf, *Rev. Finance* 2014: an FX-style overlay lifts a global stock/bond portfolio's out-of-sample Sharpe from **0.64 to 1.05** after costs (a) | — | — | monthly | — | It needs a broad currency cross-section. **On a swap-free account carry is not merely expensive, it is zero:** no swap is paid *or received* [D]. Weekly FX across 63 currencies shows momentum, not reversal (Raza 2015 thesis, b) |
| Calendar and flow sleeves (TOM, REBAL, index intraday momentum, gotobi) | Covered by EDGE §3 and §6. **Not re-verified here** | — | — | — | — | — |

### 1.2 What the evidence says, plainly

- **Live, verified records of profitable non-HFT systematic trading cluster at a net Sharpe of 0.3–0.8.**
  - The largest such records are diversified trend: SG Trend, AHL and Carver's account (b).
  - The one large, survivorship-aware live sample (the bank risk-premia products) is 0.31 (a).
- **No source I found gives survivorship-free statistics on retail "verified" systems** (Myfxbook, MQL5 signals). My searches returned only forum posts and marketing (c). **The evidence on "what retail winners do" is thin.** The base rates come from regulators and brokers (ESMA 74–89% of retail accounts lose, carried; Darwinex 53%).
- **Intraday families with a mechanism are real before costs but marginal after them.** The fix reversals, ORB and IMOM (EDGE: decaying since 2025) all net about zero at retail spreads. The short-term CTA index's best year is +11%.
- **Medium and long trend is the only family with centuries of significance** (t ≈ 5–10, a) **and live records that held up after costs.** Its weaknesses:
  - it is weaker on FX alone (EPAT 0.43, c, carried);
  - it has multi-year flat spells;
  - its win rate is under 50%.

---

## Q2. How do successful practitioners build systems?

### 2.1 What named practitioners actually do

- **Rob Carver** (b: public live account, 12 years of annual reports).
  - **Design, not fit.** He uses a few speeds of one rule, pools across instruments, and treats parameters as a diversification problem (carried from FX-METHODS §1.2 and §6.2).
  - **His retail book** (*Leveraged Trading*, 2019, written for FX, CFD and spread-bet traders "without much money"):
    - the "Starter System" is one instrument, a 16/64 moving-average crossover to open, and a stop at **0.5× annual standard deviation** to close;
    - it needs *"just £1,100 or $1,500"*;
    - his verdict on day trading: *"the idea that you can be profitable day trading, whilst paying retail level commissions and crossing the trading spread, is an idea that deserves to be rebutted constantly"*;
    - his warning on OTC holding costs: *"you are paying LIBOR+3% in overnight funding charges"*.
  - **Costs in his own account:** 0.88%/yr all-in (0.55% slippage, 0.33% commission). His execution routine *"earned 78bp and cut my slippage bill by around 40%"* against market orders (2026-04 report).
- **Kevin Davey** (b: an interview on 2025-04-18; his book).
  - **Pipeline:** idea → feasibility → walk-forward with a *"one-shot test"* (*"once defined, the strategy is evaluated without adjustments"*) → Monte Carlo on the trades → **incubation in live markets, without money, for 6 to 12 months** → deployment.
  - **Library:** over 200 strategies, of which *"generally only 20 or so will be deployed at a time"*, across about 40–50 futures symbols in 7 sectors, with equal risk per sector and monthly rotation.
  - **Rules:** simple and causal; the return-to-drawdown objective is fixed up front.
- **Ernest Chan** (c: through a vendor page and search renderings only).
  - He promotes "conditional parameter optimisation" (ML-chosen parameters per regime), sold by his firm.
  - He also describes mean reversion as having short-volatility character, with tail losses in crises.
  - I found **no independent out-of-sample evidence** for the method.
- **QIM (Jaffray Woodriff)** (c).
  - It ran short-term pattern recognition (about 90% short-term holds) built on heavy data-mining discipline.
  - A CTA database snippet shows a lifetime compound return of about 5.9%; I could not open the record.
  - **The most famous data-mined short-term shop is not evidence that intraday mining pays at retail scale.**

### 2.2 Few robust parameters versus heavy optimisation: the evidence

| Claim | Evidence | Grade |
|---|---|---|
| Live performance falls well below the backtest, and complexity makes it worse | 215 products: median Sharpe 1.20 → 0.31 (−74% [D]); the most complex (*"many trading rules, filters and parameters"*) about 30% worse; currencies worst | (a), read through (b) |
| You cannot pick tomorrow's best technical rule ex ante, and costs kill even the in-sample winners | Bajgrowicz & Scaillet, *JFE* 2012, DJIA 1897–2011: *"an investor would never have been able to select ex ante the future best-performing rules ... even in-sample, the performance is completely offset by the introduction of low transaction costs"* | (a) |
| Evolutionary search found real money once, in daily FX, in the 1980s, and it decayed | Neely, Weller & Dittmar, *JFQA* 1997: GP rules earned *"economically significant out-of-sample excess returns ... for each of six exchange rates over 1981–1995"*. The same family of rules had decayed by the early 1990s (Neely, Weller & Ulrich 2009) and failed intraday after costs (Neely & Weller 2003), both carried | (a) |
| GA rules on equities do not beat buy-and-hold after costs | Allen & Karjalainen 1999 (carried) | (a) |
| Overfitting probability rises with the number of configurations tried | Bailey et al. (PBO); Harvey & Liu (carried) | (a) |

**Reading [D].**
- Evolutionary search **rediscovers whatever simple structure is there.** In daily FX of the 1980s that was trend, and it adds nothing a fixed trend rule would not have captured.
- Then it **overfits** what is not there. The single live sample that measured complexity (Suhonen) shows complexity costing extra.
- **No practitioner I could verify runs per-regime evolved parameters in production.**

### 2.3 Regime classifiers: where they help and where they hurt

| Use | Evidence | Grade |
|---|---|---|
| **Exposure scaling on a 2-state model** (cut size in the high-volatility state) | Bulla et al., *J. Asset Management* 2011: 40 years of US, Japanese and German equity indices; out of sample *"the strategy proves profitable after taking transaction costs into account"*; volatility −41%, excess return +18.5 to +201.6 bp/yr. Nystrup 2014: an adaptive 2-state Gaussian HMM adds value after costs, with *"a realistic delay"* | (a); Nystrup (b, thesis) |
| **Forecasting or strategy routing with a regime model** | Daccò & Satchell 1999: even the true regime model can forecast worse than a random walk under small misclassification (carried) | (a) |
| **Practitioner use** | Davey rotates strategies monthly, not by a classifier. Carver uses volatility scaling, not a classifier. Chan's ML regime parameters are a vendor claim (c) | (b)/(c) |

**What it means for ACIS [D].**
- The evidence supports a **slow, 2-state, exposure-scaling** use of regime: risk down in turbulence. Volatility targeting already does most of this.
- The evidence does not support a **12-state, 1-minute router or gate**. R1 already demoted NVMA to a veto (FACTORY change 7).
- **§5.3 shows that one gate from the old design survives on the new path.**

---

## Q3. Portfolio construction at our scale

### 3.1 Diversify across mechanisms, not just instruments [D, with grade (a/b) anchors]

- **Carver's IDM is √(N_eff)**, the square root of the effective number of independent bets: SR_p = s·√N_eff, with N_eff = N/(1+(N−1)ρ).
- **ACIS's declared `targets.idm: 1.5` over 13 FX pairs** ([repo] GAP-P12D-141 (7), a prior for a subsystem correlation of 0.4) **means N_eff ≈ 2.25.** The 13-pair FX trend book is worth about **two and a quarter independent bets.**
- **Adding asset classes** [D]: the 6 explored indices at ρ ≈ 0.7 give 1.33 bets; the 2 metals at ρ ≈ 0.6 give 1.25. All 21 instruments, if the classes were uncorrelated with each other, give about **4.8 bets**. At a per-instrument Sharpe of 0.15–0.3 that is a book Sharpe of about 0.33–0.66.
- **Adding mechanisms** whose P&L correlation with trend is about 0 adds about one full bet each. Examples are EDGE's REBAL (contrarian to equity trend) and TOM or IREV (calendar and liquidity).
- **This is why practitioners diversify across sectors and strategies.** Davey sets equal risk across 7 sectors (b); Kröncke et al. find FX styles add Sharpe to a stock/bond book after costs (a).
- **Carver on diversification:** it *"gives you a massively statistically significant improvement in returns"* (b, 2019).

### 3.2 Volatility targeting

- It buys **tail control, not Sharpe**, outside equities and credit (Harvey et al. 2018, a, carried in EDGE N4).
- The 2-state exposure-scaling results above (Bulla) are the same effect seen through a regime lens.
- **Keep it.** It is the right way to be "tight on losing".

### 3.3 How many bets a small account can hold under minimum-lot constraints

- **The arithmetic [D].** One cTrader minimum lot (0.01 = 1,000 units) of EUR/USD is about $1,170 of notional. At about 7% annual volatility that carries about **$82 a year of risk**: about $100 for USD/JPY, and about $600 for 1 oz of gold at about $3,800 (an assumed price).
  - At $10k and a 20% target, the whole book's risk budget is $2,000 a year.
  - Spread across 13 FX pairs with IDM 1.5, that is about $230 of average risk per pair, so the average position is about **2.8 minimum lots**.
  - **A forecast below about a third of average strength rounds to zero.** At 10% volatility the threshold doubles. That matches J1's finding ([repo] GAP-P12D-101): at $10k and 10% the book is flat on about 75–80% of days.
- **What practitioners do about integer constraints.**
  - **Carver's "dynamic optimisation"** (b, *"Mr Greedy and the Tale of the Minimum Tracking Error Variance"*, 2021-10). It runs a greedy search that adds one contract at a time to minimise the tracking-error variance against the ideal fractional portfolio, with a cost penalty.
  - **The results** (backtest, 45 instruments at $100k):
    - Sharpe **1.19** optimised, against **1.06** for simple rounding and 1.17 for the unrounded ideal;
    - it held on average **6** positions (at most 18) out of 45;
    - *"The dimension of the returns just isn't all that high."*
  - **Caveat, stated on the page:** the author later found *"backtesting results were producing misleading results"* from a cost-calculation issue and revised the method. **Treat the numbers as indicative.**
- **Relevance to ACIS [repo].** GAP-P12D-142 records that at $10k the hard caps admit *"a truncated, order-dependent subset"* of the graded book. The current gate rounds each instrument's target toward zero independently and admits entries in slot order. **A tracking-error-minimising selection is the practitioner answer to exactly that problem.** It chooses *which* instruments to hold so that the small book tracks the big one. Today the order in which slots arrive decides.

---

## Q4. Execution edge at our scale

Most of this is already measured in `archive/RESEARCH_EXECUTION_COSTS_2026-09-16.md`. Only the new points are added here.

| Lever | Evidence | ACIS today | Verdict |
|---|---|---|---|
| **Avoid the 17:00 New York rollover** | The repo's own Dukascopy measurement: EUR/USD spread about **3×** baseline at 21:00 UTC, USD/JPY about **4.5×** (EXECUTION_COSTS §1.1, primary data). Ito & Hashimoto 2006 (a): *"a negative correlation ... between the number of deals and the width of bid-ask spread"*, with activity concentrated in the session overlaps | Decide at 17:02 New York; **fill FX and metals at 08:00 New York** (RSIM slot, [repo] EDGE §1), inside the London/New York overlap | **KEEP.** Already right |
| **Time-of-day is not neutral around the fixes** | Krohn et al. (a): the dollar appreciates from 02:00 to 08:15 ET into the ECB fix, then reverses after the London fix (11:00 ET) | The FX slot at 08:00 ET sits at the end of the pre-ECB-fix dollar run | **Measure, do not change yet:** record slippage to the mid by slot on the demo. A trend book that is long and short USD about equally should average about 0 [D] |
| **Passive first, then market** | Carver: join the best bid or offer; if not filled, cross. He pays *"about a quarter of the spread on average"* (search rendering, c) and his slippage was cut by **about 40%** against market orders (2026 report, b) | Market orders at the slot | **START** (§5): at a daily cadence a few minutes' wait costs nothing measurable |
| **Spread filter** | Spreads widen with illiquidity and news (Pepperstone, a; EXECUTION_COSTS §5) | NVMA's spread veto plus the news blackouts | **KEEP** as a data-quality veto |
| **News avoidance** | NFP minute about 22σ (EXECUTION_COSTS §5.1, repo primary data). E8 One has a ±5-minute news ban (SIZING, carried) | Two-layer blackouts | **KEEP** |
| **Fragmentation and limit-order tricks** | Pointless at one lot (FACTORY change 13) | — | Leave off |

---

## Q5. Synthesis: the gap between ACIS and what winning systematic traders at our scale do

### 5.1 The gap in one table

| Practice of live winners at our scale | ACIS legacy engine (what lost, GAP-P12D-49) | ACIS R1.6 path (as built, [repo]) |
|---|---|---|
| Decide slowly (daily to weekly); trend horizons of weeks | 1-minute decisions, 12.8-minute holds | **Daily decisions** at 17:02 New York ✔ |
| Few fixed rules, pooled, designed not fitted | 12 regimes × evolved genes (QIEA) | Fixed Carver speeds pinned to pysystemtrade ✔ |
| A stop at the signal's scale, or none; let winners run | ATR(1-minute) stop and target, 48 h maximum hold | **10× daily ATR disaster stop** (≈ 0.78× annual vol on EUR/USD [D]; Carver's Starter System exits at 0.5×), no take-profit ✔ |
| Target positions with a no-trade buffer | Event signals plus dedup | Banded target ✔ |
| Breadth: 20–100+ markets and several mechanisms | 2 FX pairs | **13 FX pairs ≈ 2.25 bets** ✘ |
| Integer-aware portfolio selection on small capital | — | Per-instrument round toward zero, entries in slot order, one-lot cap in practice ✘ |
| Regime used only to scale exposure, if at all | NVMA routes modules and keys parameters | **NVMA's 1-minute confidence still vetoes daily entries, with no retry** ✘ (§5.3) |
| Cost-aware execution (passive first) | Market orders | Market orders ✘ |
| Forward incubation for 6–12 months; kill on pre-set rules | — | Spec'd (master §5 D-a, stage D) ✔; clock starts at the cutover |
| Expect a Sharpe of 0.3–0.8 and losing years | §14 asked for Sharpe above 1.5 | R1 re-based; owner expectations: §5.4 |

### 5.2 Why "tight on losing" and "not stuck" are not in conflict, once the levers are right [D, with graded anchors]

**Where the tightness should come from:**
- **Size:** volatility targeting, many small bets, the daily-loss guard and the prop-room guard (SIZING). Size cuts the tail without cutting the edge per trade (Harvey 2018, a).
- **Not per-trade stops.** Expected gross per trade grows with the square of the barrier width, while cost is fixed (FX-METHODS §0.2). Tight stops convert edge into spread. The ORB replication on CFDs is a fresh example (c).
- **Not equity-curve switches.** Carver's tests on profitable systems: the filter idea is *"probably, wrong"*, *"robust across different positive sharpe ratios and levels of skew"*, and for trend *"an unmitigated disaster"* (b). Kill a system on its **pre-registered forward falsifier** (Davey's quit rules; ACIS stage D), not on a moving average of its own equity.

**Where the trade frequency should come from:**
- **Breadth** (N instruments × M mechanisms), each slow. It should not come from trading one instrument faster.
- A Starter-style trend system trades a handful of times a year per instrument (b). Twenty instruments at that pace give dozens of position changes a year; 20 instruments × 3 sleeves give a hundred or more.
- **Nothing in the evidence lets a $10k account trade daily on one or two instruments and keep the edge.**

### 5.3 A specific, checkable finding: the regime gate survives on the R1.6 path [repo, read in code; frequency unmeasured]

**What the code does:**
- `core/governor/target_gate.py:_entry_size` calls `gov.guards.check(instrument, portfolio, regime, now)` on every **opening** leg of the daily target.
- `core/governor/guards.py:check` zeroes the entry when `not regime.tradeable` (`"veto"`) and when `regime.confidence < 0.55` (`"low_confidence"`).
- In `core/regime/nvma.py` (lines 315–352), `confidence` is the mean "agreement" of **1-minute** ADX and Bollinger-width readings (`signal_bar_seconds: 60`), and `LOW_CONFIDENCE` alone makes `tradeable` false. For example, in `RANGING_WIDE` with `bb_pct` = 0.6 and ADX = 18, confidence is (0.6 + 0.28)/2 = 0.44, so the entry is **vetoed** [D].
- `core/runtime/target_loop.py`'s header: a slot that sends nothing is *"never caught up ... the next decision acts"*.
- `tests/backtest/rsim.py` contains no regime or confidence term (grep, [repo]).

**What that means.** Whether the daily trend book opens a position depends on whether EUR/USD's last few **minutes** at 08:00 New York looked "ranging with low agreement". The decision is then dropped for 24 hours. Three consequences:
1. **It thins trades at random with respect to the edge.** Daccò–Satchell's point (a) is that a noisy gate destroys value even when the model is right. This gate is not even about the daily signal.
2. **It makes the traded book differ from the graded one.** RSIM does not model it, and GAP-P12D-141's declared departures do not list it.
3. **It may be a large contributor to "stuck without making trades".** How often it fires is **unmeasured**.

**What to do (the lead's verification, then the owner's call).**
1. **Measure, P&L-blind.** Find the fraction of R1.6 decision slots where an entry was zeroed with `veto` or `low_confidence`. Use the demo's `TARGET_ENTRY_ZERO` events after the cutover, or replay the lab tape through the runtime.
2. **The options, if it is material:**
   - (a) let the target path's entries ignore NVMA's *confidence* and regime-derived vetoes, while keeping the data-quality ones (spread, staleness, session or market closed, blackout);
   - (b) retry a vetoed entry at the next tradeable minute inside a declared window;
   - (c) model the veto in RSIM so that what is graded is what trades.
3. **[OWNER]:** the NVMA veto sits in master §2's conflict table (priority 2), and veto semantics are owner-only (CLAUDE.md). (a) and (b) are spec changes. (c) is research-side and keeps the guard untouched.

---

## STOP / START / KEEP

The items are ranked by expected effect on net expectancy and on trading often enough. "Effect" is my judgement [D] from the graded evidence cited.

### STOP

| # | Item | Expected effect | Evidence | Flag |
|---|---|---|---|---|
| S1 | **Stop gating the daily target path's entries on NVMA's 1-minute confidence and regime vetoes**, or at least stop dropping a vetoed entry for 24 h. Measure first (§5.3) | Frequency ↑ (unquantified); graded equals traded | Daccò & Satchell (a); [repo] code | **[OWNER]** (veto semantics) / [impl] for option (c) |
| S2 | **Stop treating the legacy six-module QIEA engine on `acis-demo-1` as information about edge.** Retire per-regime QIEA and the 1-minute modules to the graveyard with revival conditions, as R1 already does on the universe | Removes the profile that degrades most | Suhonen (a); Bajgrowicz–Scaillet (a); Neely & Weller (a); GAP-P12D-49 | [spec], mostly done (R6-3) |
| S3 | **Stop counting FX pairs as breadth.** Thirteen pairs ≈ 2.25 bets; a fourteenth adds almost nothing | Redirects effort to S/T1 | [D] from the IDM | decision |
| S4 | **Stop admitting any family whose stop is a small fraction of its holding-horizon volatility**, unless measured gross/cost ≥ 3 (FACTORY G0) | Avoids net-zero churn | ORB CFD replication (c); KMW at the full spread (a); FX-METHODS §0.2 | already law (G0); enforce |
| S5 | **Never add equity-curve, losing-streak or "pause after N losses" switches** to a profitable family. Use pre-registered forward falsifiers | Protects expectancy | Carver 2015 (b); Davey (b) | decision |
| S6 | **Stop any optimiser upgrade** | — | Carried (FX-METHODS §6) | decision |

### START

| # | Item | Expected effect | Evidence | Flag |
|---|---|---|---|---|
| T1 | **Breadth by asset class and mechanism.** Metals and indices into TREND at the swap-free venue (GAP-P12D-27); then EDGE's shortlist sleeves (REBAL, IREV, TOM, GOTOBI), each at one lot on its own forward clock, in parallel | **Largest on Sharpe and frequency:** N_eff about 2.25 → about 5 for trend over 21 instruments, plus about 1 per uncorrelated mechanism | §3.1 [D]; Davey (b); Carver (b); Kröncke (a) | [impl] + [spec] per family |
| T2 | **Integer-aware book selection** (greedy minimum tracking error, Carver/Hohner) in place of independent round-toward-zero and slot-order admission under the caps | Keeps a small account trading a book that tracks the graded one (GAP-P12D-142) | Carver 2021 (b, backtest; cost-bug caveat) | [spec] ACIS-05 §6.4 + RSIM parity |
| T3 | **A "starvation" monitor**, P&L-blind: share of decision days with a non-zero target against a non-zero position, and entries zeroed by reason (`low_confidence`, `veto`, caps, lot rounding, taper), per week. Alarm when realised exposure falls below a declared share of RSIM's on the same days | Makes "stuck" visible within days, not months | [repo] reason codes already logged (`TARGET_ENTRY_ZERO`) | [impl] (monitoring only) |
| T4 | **Passive-first execution at the daily slot:** join the touch, then cross after a declared timeout | Cost −25 to −40% of spread and slippage | Carver's live records (b) | [impl] ACIS-06; the demo measures it |
| T5 | **Start each registered family's forward clock now, at one lot, judged by pre-registered falsifiers over 6–12 months** | Earliest kills; the only route to certification for LLM-selected families | Davey (b); master §5 D-a [repo] | already permitted |
| T6 | **Publish the expectation table** (below) with the forward record so a losing month is read as noise | Prevents panic re-tuning | [D] | — |

**Expectation table [D]** (normal returns; $10k sizing):

| Vol target | True Sharpe | Mean / week | sd / week | P(week > 0) | P(month > 0) | P(year > 0) |
|---|---|---|---|---|---|---|
| 10% | 0.3 / 0.5 / 0.8 | $6 / $10 / $15 | $139 | 0.52 / 0.53 / 0.54 | 0.54 / 0.56 / 0.59 | 0.62 / 0.69 / 0.79 |
| 20% | 0.3 / 0.5 / 0.8 | $12 / $19 / $31 | $277 | 0.52 / 0.53 / 0.54 | 0.54 / 0.56 / 0.59 | 0.62 / 0.69 / 0.79 |

### KEEP

| # | Item | Why | Evidence |
|---|---|---|---|
| K1 | **Carver EWMAC trend on daily bars, banded targets, volatility targeting, no take-profit, a wide disaster stop** | It matches the one family with centuries of significance and live records; it is Carver's own design for small retail CFD accounts; trend decayed least from backtest to live | Lempérière (a); Carver (b); Suhonen (a) |
| K2 | **The swap-free venue** | Retail funding of about LIBOR + 3% taxes every multi-day hold. Note: swap-free also means **carry is zero** | Carver (b); EDGE §4 |
| K3 | **Fill slots away from the rollover** (FX at 08:00 New York); **news blackouts; the daily-loss guard; the weekend buffer** | Measured spread spikes and event moves | Repo primary data; Ito & Hashimoto (a) |
| K4 | **Pre-registration, trial counting, B0 parity, HAC stage A, the held-out instruments** | Backtest-to-live haircuts of about 50–75% are normal, and ex-ante rule selection fails without this discipline | Suhonen (a); Bajgrowicz & Scaillet (a) |
| K5 | **The 10× daily-ATR stop as a *disaster* stop, not an exit** | It sits beyond Carver's 0.5× annual-vol exit, so it rarely fires on noise [D] | Carver (b); Kaminski & Lo (a, carried) |

---

## Open questions and residual risk

1. **How often the NVMA veto blocks R1.6 entries (§5.3) is unmeasured.** It is the cheapest high-value measurement available, and it is P&L-blind.
2. **The NVMA gate may conflict with what the demo is meant to prove.** It sits inside the one-lot, $10k-sizing practice book (GAP-P12D-142, J1). That book can stay flat on most days, so a 6–12-month forward record may hold too few position changes to falsify anything. Breadth (T1) and integer-aware selection (T2) are the levers; their sizes are not estimated here.
3. **Positive skew collides with consistency rules [D].** A positive-skew trend book earns in few, large days, and E8 One's 40% "Best Day" payout rule (SIZING, carried) penalises exactly that. Quantify it before funding.
4. **E8's cTrader contract sizes, minimums and commissions for metals and indices** remain unverified. One search returned only aggregators (c). They decide whether T1's metals and indices are holdable at one lot.
5. **Carver's dynamic-optimisation numbers** carry the author's own cost-bug caveat. The corrected figures should be read from his later posts or the *Advanced Futures Trading Strategies* book before T2 is costed.
6. **There is no survivorship-free evidence on retail "verified" systems** (Myfxbook, MQL5, Darwinex) in anything I could find. Darwinex's aggregate DARWIN statistics are not published in a form I could locate. **This leg of the owner's question rests on thin evidence.**
7. **SG Short-Term Traders long-run statistics** (since 2008) were not found; only its best year was.
   - **Carver's year-12 figures need a second read.** Is "SR 0.80 / Stdev 17.3%" the whole record or 2025/26? Why does 2024/25 read −16.3% in the year-12 post and −14.7% in year 11?
8. **Adding to a held position is unsupported on the target path** (`add_unsupported`, declared in code [repo]). It is moot at one lot, but it must be built before any multi-lot rung, or targets that grow will be truncated.

## Ledger items this pass suggests (the lead assigns IDs)

1. **R1.6's entries pass NVMA's 1-minute confidence and regime veto with no same-day retry. RSIM does not model it, and GAP-P12D-141 does not declare it.**
   - Action: measure (§5.3), then the owner chooses option (a), (b) or (c).
   - Severity high · Likelihood high · Status open · **[OWNER]** / [impl].
2. **Integer-aware book selection (T2)** as the answer to GAP-P12D-142's order-dependent subset.
   - Severity medium · Likelihood high · Status open · [spec].
3. **A starvation monitor (T3).**
   - Severity medium · Likelihood high · Status open · [impl].
4. **Passive-first slot execution (T4)**, measured on the demo.
   - Severity low · Likelihood medium · Status open · [impl].
5. **The best-day rule against positive skew** (open question 3), before E8 funding.
   - Severity medium · Likelihood medium · Status open · [owner decision].

---

## Sources

All URLs were read on 2026-10-02.

**Live and verified records**
- Carver, "Annual performance update — year 12", 2026-04-15 — (b) — https://qoppac.blogspot.com/2026/04/annual-performance-update-year-12.html
- Carver, "New book: Leveraged Trading", 2019-10 — (b) — https://qoppac.blogspot.com/2019/10/new-book-leveraged-trading.html?m=1
- Hedgeweek, "Trend followers turn leaders: CTAs deliver record returns in 2022", 2023-01-27 (SG CTA, Trend and Short-Term Traders indices) — (b) — https://www.hedgeweek.com/trend-followers-turn-leaders-ctas-deliver-record-returns-2022/
- Global Custodian / Opalesque, the Newedge Short-Term Traders Index description (2008) — (b) — https://www.globalcustodian.com/?p=29683
- The Full FX, "Currency Traders End Year on Strong Note", 2025-02-11 (Barclay Currency Traders Index) — (b) — https://thefullfx.com/currency-traders-end-year-on-strong-note/
- Suhonen, Lennkh & Perez, "Quantifying Backtest Overfitting in Alternative Beta Strategies", *JPM* 2017, via CXO Advisory, 2016-04-19 — (a) via (b) — https://www.cxoadvisory.com/big-ideas/live-performance-of-alternative-beta-products/
- Doering, Neumann & Paul, "A Primer on Social Trading Networks", EFMA 2015 (PDF text-extracted) — (b) — https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2015-Amsterdam/papers/EFMA2015_0306_fullpaper.pdf
- Krafft et al., "Popularity and Performance: A Large-Scale Study" (eToro), arXiv 1406.7729 — (b; read, not used for numbers) — https://arxiv.org/abs/1406.7729
- Darwinex, "What are investable attributes" — (a, firm document) — https://help.darwinex.com/what-are-investable-attributes
- Darwinex, "Loss Aversion attribute" — (a, firm document) — https://help.darwinex.com/loss-aversion-attribute
- DarwinIA allocation thresholds (search rendering of an aggregator) — (c) — https://thegodfunded.com/en/news/changes-in-the-darwinia-silver-rating-bonus-for-duration-of-the-track-record
- FTMO trader anecdotes (34% win rate with 2.45 R:R and similar), search rendering — (c) — https://ftmo.com/?p=539836
- QIM program snippet (CROR about 5.9%), search rendering; the page needs a login — (c) — https://www.autumngold.com/Advisor/gold_report.php?id=113924

**Methods and overfitting**
- Bajgrowicz & Scaillet, "Technical Trading Revisited", *JFE* 2012 — (a) — https://ideas.repec.org/a/eee/jfinec/v106y2012i3p473-491.html
- Neely, Weller & Dittmar, "Is Technical Analysis in the Foreign Exchange Market Profitable? A Genetic Programming Approach", *JFQA* 32(4) 1997 — (a) — https://ideas.repec.org/a/cup/jfinqa/v32y1997i04p405-426_00.html
- Lempérière, Deremble, Seager, Potters & Bouchaud, "Two centuries of trend following", *J. Investment Strategies* 2014 — (a, backtest) — https://ar5iv.arxiv.org/html/1404.3274
- Davey interview, The Algorithmic Advantage #036, 2025-04-18 — (b) — https://algoadvantage.substack.com/p/036-kevin-davey-part-i-its-all-about
- Carver, "Random data: Evaluating 'Trading the equity curve'", 2015-11 — (b) — https://qoppac.blogspot.com/2015/11/random-data-evaluating-trading-equity.html
- Carver, "Mr Greedy and the Tale of the Minimum Tracking Error Variance", 2021-10 — (b, backtest, with the author's cost caveat) — https://qoppac.blogspot.com/2021/10/mr-greedy-and-tale-of-minimum-tracking.html
- Carver, "Advanced Futures Trading Strategies" (book announcement) — (b) — https://qoppac.blogspot.com/2023/04/advanced-futures-trading-strategies.html
- Carver's execution algo, via search renderings of "The world's simplest execution algo" — (c for the "quarter of the spread" figure) — https://qoppac.blogspot.com/2014/10/the-worlds-simplest-execution-algorithim.html
- Man AHL (Skaliotis), "How trend-following CTAs can generate returns", AIMA, 2015-06-30 — (b) — https://www.aima.org/article/how-trend-following-ctas-can-generate-returns.html
- Ernest Chan, mean reversion and conditional parameter optimisation (search rendering) — (c) — https://www.quantinsti.com/faculty/ernest-chan

**Regimes**
- Bulla, Mergner, Bulla, Sesboüé & Chesneau, "Markov-switching asset allocation: Do profitable strategies exist?", *J. Asset Management* 12(5) 2011 — (a) — https://ideas.repec.org/a/pal/assmgt/v12y2011i5d10.1057_jam.2010.27.html
- Nystrup, "Regime-Based Asset Allocation — Do Profitable Strategies Exist?", DTU thesis 2014 — (b) — https://www2.imm.dtu.dk/pubdb/pubs/6808-full.html

**Intraday, FX and execution**
- Krohn, Mueller & Whelan, "Foreign Exchange Fixings and Returns Around the Clock", *JF* 79(1) 2024; Bank of Canada SWP 2021-48 (PDF text-extracted) — (a) — https://www.bankofcanada.ca/wp-content/uploads/2021/10/swp2021-48.pdf
- Ito & Hashimoto, "Intra-Day Seasonality in Activities of the Foreign Exchange Markets", NBER w12413, 2006 — (a) — https://www.nber.org/papers/w12413
- Zarattini & Aziz, "Can Day Trading Really Be Profitable?", SSRN 4416622 — (b, backtest) — https://papers.ssrn.com/abstract=4416622
- Krueger, "The opening-range breakout paper, replicated on five indices: gross reproduced, net zero", MQL5 blog, 2026-09-25 — (c) — https://www.mql5.com/en/blogs/post/776235
- Kröncke, Schindler & Schrimpf, "International Diversification Benefits with Foreign Exchange Investment Styles", *Rev. Finance* 18(5) 2014 — (a) — https://www.zew.de/en/publications/international-diversification-benefits-with-foreign-exchange-investment-styles-2
- Raza, "Essays on Foreign Exchange Rate Predictability", Massey PhD thesis 2015 (text-extracted) — (b) — https://mro.massey.ac.nz/bitstreams/8d7c87d0-7a19-46ab-b2ad-fa49a8176b48/download
- Pepperstone, "Bid-offer spreads", 2020-04-01 — (a, firm document) — https://pepperstone.com/en-ae/learn-to-trade/trading-guides/bid-offer-spreads
- E8 cTrader index specifications: **not found**; aggregators only — (c) — https://proptradingvibes.com/blog/e8-markets-spreads-commissions

**Repo evidence** (read-only, at `9076742`)
- `core/governor/target_gate.py`, `core/governor/guards.py`, `core/regime/nvma.py` (lines 212–352), `core/runtime/target_loop.py` (header), `tests/backtest/rsim.py` (grep), `config/system_config.yaml`, `specs/ACIS-05-CAPITAL_GOVERNOR.md` §6.4
- `KNOWN_GAPS.md`: GAP-P12D-49, -101, -141, -142
- `archive/RESEARCH_EXECUTION_COSTS_2026-09-16.md` §1.1, §1.3 and §5

**Carried, not re-fetched:** Daccò & Satchell 1999; Allen & Karjalainen 1999; Neely & Weller 2003; Neely, Weller & Ulrich 2009; Bailey et al. (PBO); Harvey & Liu 2014; Harvey et al. 2018 (volatility targeting); Kaminski & Lo 2014; Hurst, Ooi & Pedersen 2017; SG Trend statistics; Carver's 2024/25 −14.7% and the year-11 Sharpe 0.76; ESMA 74–89%; EPAT FX-trend 0.43 (c).

## Method note

- **Web searches:** 31 WebSearch calls of the 40 allowed. Three calls ran internal follow-up queries, so the conservative count is **37**. After that I used WebFetch freely, about 30 fetches; 6 failed with 403, 404, a login wall or binary output.
- **PDFs text-extracted locally** with `pypdf` into the session scratchpad: EFMA 2015, Bank of Canada SWP 2021-48 and the Massey thesis. Local computation was closed-form only (the expectation, N_eff and stop-width tables), under 1 second of CPU.
- **Web content was treated as data.** No fetched page's text was acted on as an instruction.
- **Repo and git:** no repo file was edited except this report. I ran no git commands, launched no agents, and read no market data.
