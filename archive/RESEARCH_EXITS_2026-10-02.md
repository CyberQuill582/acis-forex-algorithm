# RESEARCH — EXITS: entries, exits, stops and the win-rate/payoff trade-off (EXITS researcher, 2026-10-02)

- **Who asked, and why.** The owner launched five research agents on 2026-10-02. This one covers the trade-level mechanics of winning. In the owner's words: *"very tight on losing but not stuck without making trades and making money ... a highly intelligent and efficient risk mitigation agent that works to expose the money to the market when the math agrees and make money."*
- **Status.** This is a finder's report (constitution A5): evidence for the lead to verify (A6), never an instruction (A9). Nothing binds until the lead has re-checked it and the owner has ratified any **[spec]** item. Items that touch guardrails, the equity floor or HALT/veto semantics are marked **OWNER**.
- **Independence and contamination.**
  - I ran in fresh context and launched no agents.
  - The harness put `CLAUDE.md` and the owner's memory index into my context, so I knew the GAP-P12D-49 verdict, the venue pick (E8 One, swap-free) and the R1.6 build before I started.
  - I am an LLM with a June 2026 knowledge cutoff. Every recommendation here is LLM-selected (master v2.24 §5.6): history can kill it; only forward data can credit it.
- **Read first, so as not to repeat them:**
  - `archive/RESEARCH_SIGNAL_TO_POSITION_2026-09-16.md`;
  - `archive/RESEARCH_EXECUTION_COSTS_2026-09-16.md`;
  - `archive/RESEARCH_EDGE_SHARPEN_2026-10-01.md`;
  - the summary and prop-rule table of `archive/RESEARCH_SIZING_AGGRESSION_2026-10-01.md`, which owns risk-of-ruin at the account level. This report stays at the trade level.

  §6 checks their claims that bear on exits.
- **Code read (read-only):**
  - the legacy path: `core/runtime/policy.py`, `core/signals/agon.py`, `core/optimizer/param_types.py`, `core/optimizer/fitness.py`;
  - the R1.6 path: `core/governor/target_gate.py`, `core/governor/target.py`, `core/runtime/target_loop.py`, `core/runtime/target_decision.py`;
  - `tests/backtest/rsim.py`, `tests/backtest/cost_filters.py`, `config/system_config.yaml`, `config/platform_rules.yaml`;
  - ACIS-05 §6.4 and §7, and the ledger entries GAP-P12D-49, -59, -118 and -141, and OPS-0001.
- **Computation.** Closed forms plus one light Monte Carlo, under 2 s of CPU in total. Scripts are in the session scratchpad, outside the repo. **No market price data was read and no backtest was run.**

**Grades.**
- **(a)** peer-reviewed, a regulator, or the firm's own primary page.
- **(b)** a credible practitioner with a record, or a working paper.
- **(c)** a blog, forum, aggregator or marketing; never treated as fact.
- **[D]** derived here, with the inputs stated so the lead can re-derive it.
- **[repo]** read in this repository at `9076742`.

---

## Plain answer for the owner

1. **"Tight on losing" should not mean tight stops.**
   - **What the evidence says:**
     - Under a random walk, a stop-loss rule always *lowers* expected return. Stops add value only when prices trend at the stop's own horizon (Kaminski & Lo 2014, (a)).
     - On thousands of US stocks, *tight* stops lost to buy-and-hold because they trade too much (Lo & Remorov, (a)).
     - Layering stops on top of a trend rule did not help: *"a change of trend is the best stop loss"* (Clare et al. 2013, (a)).
   - **Why this bites hardest in FX:** at minute horizons FX returns are *negatively* autocorrelated (Goodhart & Figliuoli 1991, (a)), and retail stops cluster just beyond round numbers, where moves cascade and then reverse (Osler, NY Fed, (a)). A tight stop is paid to sell the noise.
2. **Be tight on SIZE and on the DAY instead.** That means four numbers, set in §2.6:
   - each position's loss if its stop fills is at most about 1.5% of the account;
   - the sum of those losses over one correlated "trade idea" stays below the firm's daily limit;
   - the book's daily volatility is at most about a quarter of the daily limit;
   - costs eat at most a third of the expected edge.
3. **The legacy engine lost mainly because its trades were too short to beat costs.** Two separate failures:
   - **The hold was too short.** At a 12-minute hold, a strategy would need an *annual* Sharpe of about **45 on EUR/USD, 29 on gold and 18 on the US500, just to break even** while in the market [D, §3]. Nothing real has that.
   - **The stops were too tight.** Its stops sat 1–3.5 one-minute ATRs from entry. On those stops, round-trip cost alone is **0.1–0.7 of the risk unit on every trade** (0.2–0.4 at central values).

   The same arithmetic says a daily-decided trend book clears costs comfortably once it holds for **days to weeks**. That is what R1.6 does.
4. **R1.6's exits are broadly right.** It has:
   - no take-profit and no time stop;
   - exits by the forecast itself;
   - Carver's no-trade band;
   - a far disaster stop at 10× daily ATR, which is about one year's volatility.

   Keep that shape. It matches the trend literature, and it keeps trend following's positive skew. Trend following is the one documented strategy family that earns money *and* has positive skew (Lempérière et al. 2017, (a)), and a take-profit would cut off exactly that right tail.
5. **Four changes before R1.6 trades a funded account** (§5, each with a simulation that would confirm it):
   - **(a) Cap each position's loss at its stop** (size toward zero, never a tighter stop). At the configured vol target, one FX position at full forecast would lose about **4.3% of the account** if its 10×ATR stop filled. That is nearly the whole 5% daily limit, and E8 forbids risking the whole daily drawdown on one trade (a).
   - **(b) Move the US-index execution slot off 10:00 New York.** That is exactly when ISM, JOLTS and other US releases print (a). Inside E8 One's ±5-minute news window, profit from a fill is deducted at payout (a).
   - **(c) Put the disaster stop into RSIM.** The research simulator grades a book with no stop at all, so any future stop change would be ungraded. This is the GAP-P12D-36 defect class.
   - **(d) Build same-side adds, or make RSIM refuse them.** The engine refuses to add to a position (`add_unsupported`) while RSIM adds freely. Adds are how a target-position system pyramids into a strengthening trend.
6. **"Not stuck": the band, not the stop, keeps it from churning or freezing.** A daily trend book across 13 (later 21) instruments makes dozens of position changes a year, not thousands. Each one is large enough to beat its cost. The risk of being "stuck" is in the guardrail caps and the one-lot practice rule (SIZING's lane), not in the exits.

---

## 0. What ACIS does today (read in code)

| | **Legacy fast loop** (AGON + QIEA) | **R1.6 target path** (TREND D1) |
|---|---|---|
| Decision clock | Every completed 60 s bar (`signal_bar_seconds: 60`) | Once per weekday, 17:02 New York (`settle_s: 120`) |
| Entry | Module triggers (EMA cross, channel breakout, z-score, tick velocity, TSMOM vote) | `banded_target` change; executed at the instrument's slot (FX/metals 08:00 New York; US indices 10:00 New York; others local) |
| Stop | `entry − dir × atr_multiplier_sl × ATR(14)`, on **1-minute bars**; `atr_multiplier_sl` evolved per regime in [1.0, 3.5] (`param_types.py`). TSMOM: 10× daily ATR | `mark − dir × 10 × daily ATR(14)`, broker-side, fixed from entry (`target_gate.py`, `tsmom_disaster_stop_atr: 10.0`) |
| Target | `atr_multiplier_tp` evolved in [1.5, 5.0], always > SL (repair invariant). None for TSMOM | **None** |
| Time exit | Engine: `max_hold_s: 172800` (48 h). QIEA fitness: `max_holding_periods` 1–48 *bars*, i.e. 1–48 minutes | **None** |
| Signal exit | An opposite order reverses; same-side repeats are ignored | Forecast moves the target outside the band → trade to the band's edge; a flip closes then opens |
| Re-entry | Next qualifying signal | After a disaster stop: not before the next decision (the slot skips with `position_changed`) |
| Adds/pyramiding | No (one position per instrument) | **Refused** (`add_unsupported`), "practice holds at most one lot" |
| What grades it | QIEA fitness simulates stop/target on 1-min bars; the harness book | RSIM (`tests/backtest/rsim.py`): **no stop, no re-entry rule, adds allowed** [repo] |

R6-3 turns the legacy modules and the QIEA champion off for the target universe on the demo. So the legacy review in §5.2 is short, and aimed at anything that ever revives a fast sleeve.

---

## 1. Stop-losses: what the evidence says (Q1)

### 1.1 Theory

- **Kaminski & Lo (2014), *J. Financial Markets* 18:234–254 (a).** *"Under the Random Walk Hypothesis, simple 0/1 stop-loss rules always decrease a strategy's expected return, but in the presence of momentum, stop-loss rules can add value."* The published abstract adds that *"at longer sampling frequencies, certain stop-loss policies can increase expected return while substantially reducing volatility."*
  - Read via MIT DSpace's abstract and Kaminski's 2007 MIT thesis abstract. The PDF itself was behind a bot wall.
  - **Mechanism.** A stop helps exactly when a loss predicts further loss, i.e. positive serial correlation or regime-switching at the stop's horizon. It hurts when a loss predicts a bounce.
- **Optional stopping [D, the textbook result; Warburton & Zhang 2006, *Computers & OR* 33(1):32–42 (a) model it computationally].** On a driftless (martingale) price, every bounded rule built from stops, targets and time exits has expected gross P&L of exactly zero.
  - What a stop/target geometry changes is the *shape* of the outcome distribution: the win rate, the payoff ratio and the skew. It never changes the mean before costs.
  - **Consequence for ACIS:** an optimiser that tunes stop and target multiples on a finite sample is selecting a distribution shape that happened to fit noise (§5.2).
- **Glynn & Iglehart (1995), *Management Science* 41(6):1096–1106 (a).** This paper derives the distribution, mean and duration of a trailing-stop trade for a random walk and Brownian motion *with positive drift*, and optimises the stop distance. The value of a trailing stop is a function of the drift. With no drift there is nothing to optimise.

### 1.2 Empirics

| Study | Setting | Finding | Grade |
|---|---|---|---|
| Kaminski (2007 thesis) / Kaminski & Lo | US equities → long bonds on stop-out, monthly, 1950–2004 | *"certain stop-loss rules add 50 to 100 basis points per month ... during stop-out periods"*; attributed to regime-switching "flights to quality" | (a) |
| Lo & Remorov (*J. Financial Markets*, 2017; Remorov's 2016 MIT thesis abstract) | US single stocks 1964–2014; costs = actual half-spreads (~0.2%) | *"tight stop-loss strategies tend to underperform the buy-and-hold policy due to excessive trading costs. Outperformance is possible for stocks with sufficiently high serial correlation"*; downside reduced *"but not substantially"*. Per the CXO summary: daily stops 0 to −6% and 10-day stops 0 to −14%; wide 10-day stops ≈ buy-and-hold; recent decades' negative autocorrelation is *"unfavorable for tight stop-losses"* | (a) thesis; (c) for the summary's numbers |
| Clare, Seaton, Smith & Thomas (2013), *J. Asset Management* 14(3):182–194 | S&P 500, daily 1988–2011, monthly 1952–2011 | On a 200-day MA trend rule, trailing stops of 3–15% and a 5σ "purchase cost" stop *"would seem to make performance worse"*; the Sharpe is *"the same or lower in nearly all cases"*; *"a change of trend is the best stop loss"*. Monthly decisions beat daily ones | (a), full text read |
| Han, Zhou & Zhu, *Taming Momentum Crashes: A Simple Stop-Loss Strategy* (working paper) | US cross-sectional stock momentum, 1926–2013 | Per-stock 10–15% stops: worst month −49.8% → −17.4% (15% stop); Sharpe 0.17 → 0.40 (15%) and 0.50 (10%). **Gross of costs**; the authors flag data snooping and *"fitting to a handful of stock market crashes"* | (b), via CXO's summary (c) |

**Reconciling them.**
- **Where stops help:** in **negatively skewed, crash-prone** strategies (cross-sectional momentum; equities in flight-to-quality regimes), where a loss signals a regime with persistence.
- **Where they hurt or do nothing:**
  - on strategies that already **cut losers by construction**: a trend rule exits when the trend turns, and its P&L is positively skewed;
  - wherever **short-horizon returns mean-revert**.
- **Where ACIS sits:** its TREND family is the second kind (§2.1), and its legacy 1-minute stops live in the mean-reverting regime (§1.4).

### 1.3 Stop types, ranked by the evidence

| Type | Evidence | Verdict for ACIS |
|---|---|---|
| **Signal exit** (the rule's own reversal) | Clare et al. (a): the best stop; pysystemtrade and MOP have no stop (b, a) | **Primary exit for trend.** R1.6 already does this |
| **Trailing stop at X × annual vol** | Carver, "How fast should we trade?" (b, fetched): a trailing stop **is** a trend rule; X sets the holding period. His table: X = 0.1 → 46.9 trades/yr; 0.2 → 21.4; 0.3 → 11.9; **0.4 → 7.8 (6–7-week holds)**; **0.5 → 5.4**; 1.0 → 1.7. *"make sure you use a trading rule that has an expected holding period which matches the stoploss holding period."* His Leveraged Trading starter system uses X = 0.5 as its exit (via a QuantConnect replication, (c)) | Valid as a **stand-alone** exit. Layering one on a forecast rule duplicates the exit (Clare: no value) |
| **Fixed stop from entry** | Lo & Remorov (a): tight ones lose to costs, wide ones ≈ no effect. Clare (a): no benefit | Only as a **disaster stop**, far away |
| **Volatility-scaled (ATR) vs fixed-%** | **No peer-reviewed comparison found.** The search returned only practitioner blogs (c). The case is mathematical [D]: a stop of k·σ keeps P(stop-out) stationary across volatility regimes, and a fixed-% stop does not. Turtles (2N) and Carver (X·σ) both scale by vol (b) | Scale every stop by volatility. Treat any claim that ATR stops "work better" as lore |
| **Time stop** | No direct evidence found for a time stop as a risk tool. Time-based throttles have *negative* measured evidence (Novy-Marx & Velikov, via the SIGNAL report, (a)). Legitimate only when the hypothesis **is** a time window (the EDGE report's IMOM "flat at the close", GOTOBI "to 09:55 JST") | **None for trend.** For window sleeves, the window end *is* the method |
| **Take-profit** | No support for trend. MOP/Carver use none; the right tail is the payoff (Lempérière, (a)). Osler (a): take-profit orders cluster *at* round numbers, where rates tend to reverse; a TP there sells into the reversal crowd | **None for trend.** For mean reversion, the target is the reversion level, which is part of the method |

### 1.4 FX microstructure: why tight stops are worse here

- **Minute returns mean-revert.** Goodhart & Figliuoli (1991), *JIMF* 10(1):23–52 (a, via a search rendering) report *negative first-order autocorrelation* at the highest frequencies, which "disappears once the price formation process is over". In Kaminski–Lo's terms, a stop set inside minute noise has a negative stopping premium.
- **Stops cluster and cascade (Osler, NY Fed Staff Report 150, 2002; *JIMF* 2005; (a), full text read):**
  - *"executed stop-loss sell orders cluster just below round numbers; stop-loss buy orders cluster just above round numbers"*;
  - almost 10% of orders sit at rates ending in 00;
  - rates trend unusually fast once they reach stop clusters, and the effect is *"statistically significant for hours, although not for days"*;
  - rates *"reverse course relatively frequently"* at take-profit clusters.
  - **Practical rule [D]:** never place a stop at or just beyond a round figure. A vol-scaled far stop (R1.6) makes this moot. A tight stop does not.
- **Stop hunting is a regulatory fact, not lore, at the interbank level.** The FCA's 2014-11-12 release on five banks says traders attempted to *"trigger client 'stop loss' orders"* (a). At retail size the counterpart risk is the dealer's last-look reject and the stop's gap-through, which the EXECUTION report §6.5–6.8 already covers.
- **Rollover and gaps (repo-measured, EXECUTION report §1.1 and §6.4):**
  - the EUR/USD spread is about 3× baseline, and USD/JPY about 4.5×, around 17:00 New York;
  - weekend gaps: p95 47 bp on EUR/USD, 56 bp on USD/JPY, 69 bp on gold.
  - **Consequence:** a stop within a few bp of price is hit by the rollover spread alone.

### 1.5 Verdict on stops

- **For trend (R1.6):** the forecast is the stop. Keep a *far* broker-side disaster stop for the §279 law (bounded risk if ACIS vanishes) and for gaps. Do **not** tighten it to "control losses": control losses through size (§2.6).
- **For any short-horizon module:** a stop inside minute noise is a measured loser. Size it beyond the noise and cost scale (§3), or do not trade that horizon.

---

## 2. Win rate, payoff, and what "tight on losing" means mathematically (Q2)

### 2.1 By strategy family

- **Trend following: positive skew, low hit rate.**
  - Lempérière, Deremble, Nguyen, Seager, Potters & Bouchaud, "Risk premia: asymmetric tail risks and excess returns", *Quantitative Finance* 17(1), 2017 (a; arXiv 1409.7720):
    - across equity, Fama–French, FX carry, short vol, bonds and credit, the Sharpe is roughly **linear in *negative* skewness**;
    - *"trend following has both positive skewness and positive excess returns."*
  - Hit rates of 30–45% are widely quoted (c, practitioner lore). The data points I can stand behind are (b)/[repo]:
    - **ACIS's own** ladder ran at a 0.37–0.43 win rate (GAP-P12D-49 table);
    - the intraday replication in the EDGE report shows a 41% win rate at a 1.69 payoff (c).
- **Mean reversion / risk premia: negative skew, high hit rate.** By the same paper, the premium is paid for left-tail risk.
  - **Illustration [D]:** an 80% win-rate system earning +0.45R, losing −1.05R 17% of the time and −6R 3% of the time has an expectancy of **+0.002R**. That is zero: three tail events in a hundred erase eighty wins.
- **Cross-sectional stock momentum is the exception that proves the rule.** It is negatively skewed (crashes), which is why stops helped there (Han–Zhou–Zhu, §1.2). Time-series trend is not.

### 2.2 Break-even win rate [D]

With an average win of b R, an average loss of 1 R, and a round-trip cost of c_R in R units on every trade:

  **p_be = (1 + c_R) / (1 + b)**

| payoff b | c_R = 0 | 0.05 | 0.20 | 0.50 |
|---|---|---|---|---|
| 0.5 | 0.667 | 0.700 | 0.800 | 1.000 |
| 1.0 | 0.500 | 0.525 | 0.600 | 0.750 |
| 1.5 | 0.400 | 0.420 | 0.480 | 0.600 |
| 2.0 | 0.333 | 0.350 | 0.400 | 0.500 |
| 3.0 | 0.250 | 0.263 | 0.300 | 0.375 |

- **Read-out.** A trend system at a 38% win rate with a 2R payoff earns +0.14R at c_R = 0.05 and **−0.06R at c_R = 0.20**.
- **That is the legacy engine.** Its 1-minute ATR stops put c_R at 0.2–0.4 at central costs (§3.4).
- **Profit factor:** gross PF = p·b / (1 − p). At p = 0.38 and b = 2.2 it is 1.35 gross and 1.25 at c_R = 0.05.

### 2.3 Losing streaks against a 10% max-loss line [D]

Exact dynamic programme: P(at least one run of ≥ k consecutive losses within n trades), at loss probability q = 1 − win rate.

| q (win rate) | n | k=6 | k=8 | k=10 | k=12 | k=15 |
|---|---|---|---|---|---|---|
| 0.55 (45%) | 200 | 0.93 | 0.53 | 0.20 | 0.06 | 0.01 |
| **0.62 (38%)** | 100 | 0.91 | 0.57 | 0.26 | 0.11 | 0.03 |
| **0.62 (38%)** | 200 | 0.99 | 0.82 | **0.47** | 0.21 | 0.05 |
| 0.70 (30%) | 200 | 1.00 | 0.98 | 0.84 | 0.57 | 0.24 |

- **Read-out.** At a 38% win rate over 200 trades, a 10-loss streak is a coin flip.
- **At 1% risk per trade:** a 10-loss streak costs ~10.5% with costs, which is the whole 10% max loss, before counting any interleaved drawdown.
- **The fix is sizing.** Per-trade risk must be ≤ ~0.5–0.75% for a trend profile on a 10% static line, unless the risk unit is volatility rather than a stop (R1.6's case, §2.6).

### 2.4 Pass/fail against ±10% barriers, by risk per trade [D, Monte Carlo]

- **Set-up:** 20,000 paths, i.i.d. trades, seed 20261002, no time limit (as at FTMO and E8).
- **Profile:** win 38%, +2.2R gross, −1R, cost per trade c_R.

| profile | E per trade | net PF | r = 0.25% | 0.5% | 1.0% | 1.5% | 2.0% |
|---|---|---|---|---|---|---|---|
| trend, c_R = 0.05 | +0.166R | 1.25 | 0.998 (210 trades) | **0.952** (90) | **0.817** (32) | 0.730 (17) | 0.667 (10) |
| trend, c_R = 0.20 | +0.016R | 1.02 | 0.629 (510) | 0.563 (134) | 0.544 (36) | 0.519 | 0.505 |
| zero edge (p = 0.3125), c_R = 0.05 | −0.050R | 0.93 | 0.139 | 0.283 | 0.377 | 0.402 | 0.406 |

Each cell is P(+10% before −10%), with the median number of trades to resolution in brackets.

- **Positive edge: bet small.** The pass probability rises toward 1 as risk falls, at the price of time.
- **Negative edge: bet big.** Small bets lose surely. This is the classic gambler's-ruin asymmetry (closed form below).
- **Thin edge: risk size does not help.** At c_R = 0.20 the edge is +0.016R, and the outcome is ~55/45 at any size.

**The closed form [D]** (drifted Brownian motion, barriers ±D):

  P(pass) = (e^{2θD} − 1) / (e^{2θD} − e^{−2θD}), with θ = mean / variance of the equity increments.

- **80% pass:** this needs θ = ln 4 / (2D) ≈ **6.9 for D = 10%**. In annual terms, θ = S/σ, so **S/σ_ann ≥ 6.9**.
  - Examples: S = 0.5 at σ ≤ 7.2%/yr, or S = 0.35 at σ ≤ 5%/yr.
  - It holds for any S > 0, at the cost of a longer expected time.
- **Robustness:** the Monte Carlo matches it (r = 1%: closed form 0.80, Monte Carlo 0.817).
- **Overlap:** SIZING already showed the account-level version. This is the same result in trade units.

**An honest negative.** I also ran a mean-reversion profile (85% win, +0.45R, −1.05R, a 2% chance of −4R).
- **Result:** at *equal per-trade Sharpe*, i.i.d. negative skew did **not** lower the pass rate in this model. Mean reversion's lower variance in R units even raised it (0.91 vs 0.81 at r = 1%).
- **What the i.i.d. model cannot show:** a mean-reversion book's tail events **cluster across instruments in a crisis and gap through stops**. A single correlated cluster then exceeds the day's room.
- **So:** the skew coefficient alone is not the danger. **The size of one bad event against the daily room** is. That is what §2.6's per-idea cap targets.

### 2.5 The daily line [D]

- **Simultaneous stop-outs.** With per-position risk-at-stop r, a gap multiplier g (the stop fills g× beyond its level) and K positions that can stop out together, the worst plausible day costs K·r·g.
- **Example (E8 One, 5% daily room):**

  | r | g | K |
  |---|---|---|
  | 1% | 1.5 | ≤ 3 |
  | 0.5% | 1.5 | ≤ 6 |

- **Who owns it:** account-level daily-room sizing is SIZING's guard: book daily vol ≤ room/4, verified by the lead. The pre-breach *flatten* that a firm's line needs is owned by **GAP-P12D-59** (OWNER, open).

### 2.6 "Tight on losing", as four numbers [D]

Proposed for ratification after rung 1, consistent with the ratified post-edge profile plan:

1. **Per-position loss at its stop** = |size| × stop distance ≤ **L_pos × capital**, with L_pos = min(firm per-trade norm, 0.4 × daily room). For E8 that is ≈ **1–1.5%**:
   - E8 states *"no hard limits on maximum risk per trade idea"* and that its successful traders risk *"1–1.5% per trade idea"*;
   - *"risking your entire daily drawdown on a single trade is not permitted"*;
   - E8 *"reserves the right to ... limit your risk to no more than 1% per trade idea"* (a, via a search rendering of E8's help page; a direct fetch returned 403).

   **Applied by shrinking the size toward zero, never by tightening the stop.** A bigger position with a tighter stop is the perverse version.
2. **Per "trade idea" (a correlated cluster):** the sum of loss-at-stop ≤ **the daily room**. E8's rule counts correlated positions as one idea. Six long index CFDs are one idea; so are 13 FX pairs that are all short USD.
3. **Book daily σ ≤ room / 4** (SIZING; a 5% room gives ≤ 1.25%/day).
4. **Cost ≤ 1/3 of the expected gross edge** (Carver's speed limit; already master §5.6's cost filter at 0.10 SR).
   - **The expectancy this implies at the trade level:** net PF ≈ 1.2–1.3 at a 35–40% win rate for 1% risk per idea, or about 1.13 at 0.5% (§2.4).

---

## 3. Holding period against friction (Q3)

### 3.1 Two framings, both needed

- **(i) A persistent drift** (trend). The edge accrues uniformly in time: an in-market annual Sharpe S on annual vol σ earns S·σ·h over a hold of h years. **Break-even: S·σ·h ≥ c**, and Carver's 1/3 rule asks for 3c.
- **(ii) An event or window edge**, with a fixed information coefficient per trade. The EXECUTION report's **h_min = (c / (IC·σ_1min))²** applies. I re-derived its 7.3 h at IC 0.05 and c = 1.5 bp: (1.5 / (0.05 × 1.43))² = 440 min ✓.

Both say the same thing about 12 minutes.

### 3.2 The in-market annual Sharpe needed to break even [D]

- **Inputs:** σ_ann = 7% (EUR/USD), 16% (XAU), 17% (US500); 6,240 trading hours a year.
- **Round-trip cost ranges** (low / central / high):
  - **EUR/USD 0.7 / 1.0 / 1.5 bp.** Pepperstone Razor is ~0.5 bp of commission plus a tight spread (a, OPS-0001 and the EDGE report). E8's commission is unverified (c): "0.005% of notional" would be ~1 bp round trip. OANDA is 1.44 bp of spread (a).
  - **XAU 1.0 / 1.5 / 2.5 bp.** OANDA's $0.565 is 1.32 bp (a); the Dukascopy median is 1.79 bp [repo].
  - **US500 0.6 / 1.0 / 1.6 bp.** Pepperstone averages 0.59 bp, no commission (a); E8 is unverified.

Each cell gives low / central / high cost; ×3 applies Carver's 1/3 rule to the central cost.

| hold | EUR/USD | ×3 | XAU/USD | ×3 | US500 | ×3 |
|---|---|---|---|---|---|---|
| **12 min** | 31 / **45** / 67 | 134 | 20 / **29** / 49 | 88 | 11 / **18** / 29 | 55 |
| 1 h | 6.2 / 8.9 / 13.4 | 27 | 3.9 / 5.9 / 9.8 | 18 | 2.2 / 3.7 / 5.9 | 11 |
| 4 h | 1.6 / 2.2 / 3.3 | 6.7 | 1.0 / 1.5 / 2.4 | 4.4 | 0.55 / 0.92 / 1.5 | 2.8 |
| 1 day | 0.26 / 0.37 / 0.56 | 1.1 | 0.16 / 0.24 / 0.41 | 0.73 | 0.09 / 0.15 / 0.24 | 0.46 |
| 5 days | 0.05 / 0.07 / 0.11 | 0.22 | 0.03 / 0.05 / 0.08 | 0.15 | 0.02 / 0.03 / 0.05 | 0.09 |
| 20 days | ≤ 0.03 | 0.06 | ≤ 0.02 | 0.04 | ≤ 0.01 | 0.02 |

**Minimum hold at the central cost** [D]:

| instrument | gross S = 0.3: break-even / 1/3 rule | S = 0.5: break-even / 1/3 rule |
|---|---|---|
| EUR/USD | 1.2 d / 3.7 d | 0.7 d / 2.2 d |
| XAU | 0.8 d / 2.4 d | 0.5 d / 1.5 d |
| US500 | 0.5 d / 1.5 d | 0.3 d / 0.9 d |

The realistic per-instrument trend Sharpe is 0.15–0.4 (the EDGE report, (b)).

### 3.3 Why the ~12-minute holds failed: three independent reasons

1. **Drift arithmetic:** the in-market Sharpe needed is 18–45 (above). The R1.1 audit's planted-market figure, *"no hold under ~36 minutes can clear friction even with perfect direction"*, re-derives exactly: 7.6e-5 / 7.13e-7 × 20 s = 35.5 min ✓ (GAP-P12D-49).
2. **Cost in R:** a 1-minute ATR(14) is ≈ 1.6 × 1.43 bp ≈ 2.3 bp on EUR/USD. That assumes ATR ≈ 1.6σ for Brownian motion; the lead can measure it P&L-blind. At a stop of k × ATR, the round-trip cost per trade in R units [D] is:

   | RT cost | k = 1 | k = 2 | k = 3.5 |
   |---|---|---|---|
   | 0.37 bp (old harness) | 0.16 | 0.08 | 0.05 |
   | 1.0 bp | 0.44 | 0.22 | 0.12 |
   | 1.5 bp | 0.66 | 0.33 | 0.19 |

   By §2.2, c_R of 0.2–0.4 erases any plausible trend payoff.
3. **The sign of the noise.** Minute returns are negatively autocorrelated (§1.4), so a stop at 1–3.5 minute-ATRs fires disproportionately on moves that revert: Kaminski–Lo's harmful case.

---

## 4. Entry timing and execution at ACIS's scale (Q4)

### 4.1 Sessions and the rollover

- **Liquidity and spreads move together.** Ito & Hashimoto (2006), *J. Japanese & Int'l Economies* 20(4):637–664 (EBS USD/JPY and EUR/USD; (a), abstract):
  - activity and volatility are positively correlated;
  - *"a negative correlation [is] observed between the number of deals and the width of bid-ask spread during business hours"*;
  - the intraday U-shape holds for Tokyo and London participants.
- **Rollover [repo]:** the EUR/USD spread is ~3× and USD/JPY ~4.5× baseline for about an hour around 17:00 New York.
- **R1.6 is already well placed.**
  - It decides at 17:02 on the bar that closes at 17:00, with no fill, and fills at 08:00 New York for FX. That is London afternoon, inside the London–New York overlap, the deepest window.
  - **One residual:** the decision close is a BID bar at the rollover (GAP-P12D-141 (1)). Rollover spread noise enters the close and the daily true range. Against a 45 bp daily σ this is second-order; the lead can confirm it P&L-blind.
- **Any future intraday sleeve should never enter in 16:55–18:00 New York.**

### 4.2 News windows: a slot collision found

- **The E8 One rule (a, fetched from E8's help centre).**
  - In the SimFI performance stage, trading is prohibited *"5 minutes before the scheduled news release"* until *"5 minutes after"*.
  - The listed prohibited actions include *"Stop/Loss and Take/Profit"*.
  - The consequence: *"profits are automatically deducted from your account balance after your request payout."*
  - The Challenge stage, E8 Pro and E8 Signature are unrestricted.
- **ACIS's slots against the US calendar:**

  | Slot (ACIS-05 §6.4) | Nearby scheduled releases | Collision? |
  |---|---|---|
  | FX and metals, **08:00 New York** | 08:30 ET US/Canada data; ECB decision 14:15 CET ≈ 08:15 ET | No, 15–30 min clear. The position then carries the release, which a daily book is built for |
  | **US500/US30, 10:00 New York** | **10:00 ET exactly: ISM Manufacturing (first business day), ISM Services, JOLTS, UMich sentiment, Conference Board, new home sales.** The ISM page states 10:00 a.m. ET (a, via a search rendering) | **Yes, on several days a month** |
  | UK100 09:00 London; EU50 09:00 Frankfurt; JP225 10:00 Tokyo; AUS200 11:00 Sydney | The euro-area flash PMIs (09:15–10:00 CET) and Australia's 11:30 Sydney prints are nearby | Not inside ±5 min as far as I know; **check against the calendar** |

  On a collision day, the master §3.5 blackout skips the slot "never caught up" if ACIS's calendar marks the release Tier-1. If it does not mark it (ISM is not in ACIS's Tier-1 list: NFP, CPI, central banks, GDP), the engine fills **inside E8's window**, and profit is deducted on the closes.
- **Recommendation (§5.1 R-3):** move the US-index slot to 10:15–10:30 New York, and screen every slot against E8's own high-impact list.

### 4.3 Spread filters

- **The veto exists.** NVMA's spread veto (3× the session median) already zeroes an entry through `guards.check`.
- **One gap [repo].** `TargetLoop.execute` *pops* the pending decision at the first tick after the slot. An entry vetoed by a transient spread spike at that second loses the whole day's decision, even though `slot_grace_s: 300` allows five minutes.
- **The cheap fix:** retry a vetoed *entry* each minute within the grace window. Closes are never blocked anyway. Expected effect: small; it removes a source of random missed days.

### 4.4 Scaling in and out, and pyramiding

- **Turtles** (Curtis Faith's published rules, 2003; (b), read only via secondary renderings (c), which agree on the following and disagree on the correlated-market limits):
  - N = the 20-day ATR;
  - one unit moves 1% of equity per 1N;
  - the initial stop at 2N gives ~2% risk per unit;
  - add one unit every ½N in the trade's favour, up to 4 units per market, so up to ~8% at risk before the stops trail.
- **That cannot coexist with a 5%/10% prop account.** The sizing scale is the lesson, not the mechanics.
- **Carver's forecast system pyramids by construction [D from pysystemtrade defaults (b), via the SIGNAL report].**
  - An EWMAC forecast grows as the trend persists, up to the cap of 20, which is 2× the average.
  - The band turns that growth into a few discrete adds and trims.
  - Scaling *out* is the same mechanism in reverse: a weakening trend shrinks the forecast, and the band trades to its edge.
  - **Separate pyramid or partial-profit rules would duplicate the forecast and should not be added.**
- **Parity gap [repo].** The gate refuses same-side increases (`add_unsupported`); RSIM grades them.
  - In practice mode the one-lot cap makes adds impossible, so nothing diverges today.
  - **At live sizing the engine would hold a different book than RSIM grades** (GAP-P12D-36 class), and it would never pyramid into a strengthening trend. Not listed in GAP-P12D-141.
- **Weekend flatten.** A trend book carried for weeks must run on a weekend-holding account, or §9.5's weekend flatten forces a round trip every Friday on each held instrument.
  - **Cost [D]:** ~52 round trips × ~1 bp ≈ 0.5%/yr of notional, or ≈ 0.07 SR units at 7% vol. That is most of the 0.10 SR cost budget.
  - **Account check:** `platform_rules.yaml` sets `weekend_holding_allowed: false` on two entries; E8 (Pro) allows weekend holding per SIZING. **Verify E8 One.**

### 4.5 Order type

- **What a passive limit order would save** at the slot is about half the spread, ~0.1–0.3 bp a fill.
- **Why it is not worth building now:** at the R1.6 turnover that is ≤ 0.005 SR. It is not worth the non-fill risk or the code (lean-build law).

---

## 5. ACIS's exits reviewed: what to change, the expected effect, and the confirming simulation (Q5)

### 5.1 R1.6 (the path that matters)

**Keep, because the evidence supports it:**
- no take-profit (Lempérière (a); MOP/Carver);
- no time stop (§1.3);
- the forecast as the exit (Clare (a));
- Carver's band traded to the edge (the SIGNAL report, NMV (a));
- the forecast cap of 20;
- no same-day re-entry after a disaster stop. After a ~15σ adverse day the forecast has usually weakened anyway; this only removes the noise-driven whipsaw.

**The disaster stop's geometry [D].**
- **Distance:** 10 × daily ATR(14) ≈ 15σ_daily (with ATR ≈ 1.5σ_d) ≈ 0.94 × the annual σ. That is about twice Carver's starter-system distance (X = 0.5), and fixed from entry rather than trailing.
- **Driftless touch probability within a hold of H days,** 2Φ(−15/√H): 0.001 at 20 days, 0.05 at 60, 0.17 at 120.
  - These are Gaussian figures; fat tails raise them.
  - For the slow members (EWMAC64/256, MOP's monthly holds), the stop is therefore *not* inert over long holds. It is still far outside any signal exit.

| ID | Change | Why | Expected effect | Confirming simulation |
|---|---|---|---|---|
| **R-1** [impl, **before any stop change**] | Put the disaster stop into RSIM: touch on the H1 path, fill at the **worse** of the stop and the next bar's open (gap-through), and no re-entry before the next decision. Record it in GAP-P12D-141 meanwhile as a declared departure | RSIM has no stop, so the engine's stop is ungraded (GAP-P12D-36 class). Any tightening would otherwise go live unmeasured | At 10× ATR: Sharpe change ≈ 0 (prediction ≤ ±0.01) on the Gaussian lab. Measurable only on fat-tailed and crash tapes | SIM-1 |
| **R-2** [spec, **OWNER**, before live] | **A per-position loss-at-stop cap,** applied as a size cap toward zero: \|size\| × stop distance ≤ L_pos × capital_ref, L_pos ≈ 1–1.5% (E8 norm, ≤ 0.4 × daily room). Plus a **cluster cap**: the sum of loss-at-stop over a correlated idea ≤ the daily room. **Do not tighten the stop to achieve it** | At the configured `idm: 1.5`, 13 FX equal weights and a 20% vol target, a position's daily σ is 0.144% of capital at forecast 10, so loss at a 10× ATR stop ≈ **2.2% (f10) and 4.3% (f20)**. With metals at class-equal weights it is **7.8% to 15.6%** (IDM 2.5, 20%). Either can exceed E8's "entire daily drawdown on a single trade" line. Practice mode is unaffected (one lot ≈ 0.8% of $10k at the stop) | Binds mostly on strong forecasts and concentrated instruments. Prediction: gross Sharpe −0.02 to −0.08, with the worst single-instrument gap loss held under the day's room. **Measure; do not assume** | SIM-2 |
| **R-3** [spec, OWNER] | Move the US-index slot from 10:00 to **10:15–10:30 New York**. Screen all slots against E8's high-impact list ±5 min; add ISM/JOLTS-class 10:00 ET releases to the blackout calendar for E8 accounts | §4.2 collision: profit deducted (E8 One performance), or the day skipped | Removes a systematic collision on ~3–6 days a month (prediction; count it with SIM-3). No P&L change expected otherwise | SIM-3 (P&L-blind) |
| **R-4** [impl] | Retry a vetoed entry within `slot_grace_s` instead of dropping the day's decision | §4.3 | Small: fewer random missed days | A unit test plus the demo log count of `TARGET_ENTRY_ZERO` with reason `veto` at slots |
| **R-5** [impl, before live] | Build same-side adds (an entry through every guard), **or** make RSIM refuse adds as the engine does. Pick one, so graded = traded | §4.4: parity, and it is how the system pyramids | Parity. With adds, live P&L tracks RSIM's; without, the live book is under-sized in strong trends | A B0(d)-style parity test at a lot cap > 1 |
| **R-6** [measure, no change] | Keep 10× ATR. Test 6–8× and a Carver-style trailing X = 0.5–1.0 only as *comparisons* | Evidence predicts no gain from tighter stops on a forecast-exit trend rule (Clare; Kaminski–Lo) | Prediction: tighter = lower Sharpe; trailing ≈ equal or lower | SIM-1 |

### 5.2 The legacy fast loop

**Verdict: do not spend effort tuning its exits.** Retire it from any money-bearing account; R6-3 already silences it on the target universe. Its exits fail for structural reasons, not parameter reasons:

1. **The stop/target scale is the minute-noise scale.** Cost is 0.1–0.7 R per trade (§3.3), and the noise mean-reverts (§1.4).
2. **The stop/target multiples are evolved per regime by QIEA on 1–48-*minute* fitness holds** (`fitness.py`, `max_holding_periods` 1–48 bars). By optional stopping (§1.1), on a near-driftless path the geometry changes only the distribution's shape. **Evolving it selects the shape that fit the sample's noise.**
3. **The take-profit always sits closer than 5 ATR** (`atr_multiplier_tp` ≤ 5), so TREND and BREAKOUT trades cannot reach the trend's right tail.
4. **The 48 h max hold forces information-free round trips.** It capped TSMOM's holds (the BUILDER's 53–55 h finding in GAP-P12D-49), and a same-side signal then re-opens the position.

**If any fast sleeve is ever revived** (the EDGE report's IMOM or GOTOBI):
- its exit is its **published window end**;
- one disaster stop at ≥ 3× the window's own σ;
- **no TP, and no evolved stop or target**;
- **stop distance ≥ 10× round-trip cost**, so c_R ≤ 0.1;
- entries outside 16:55–18:00 New York and outside ±5 min of any high-impact release;
- the existing 3× spread veto.

### 5.3 Simulation specs (for the lead, on acis-compute-1; lab first, because real-data looks stay closed until R1.4)

- **SIM-1: the disaster-stop sweep on the TREND book (lab only).**
  - **Set-up:**
    - RSIM extended per R-1, with an H1 intrabar path from the lab's tick generator;
    - the C-BT-12 market: planted, null, and the fat-tailed GARCH knobs (ν = 4.5);
    - a 21-instrument class-equal book at a 20% vol target, IDM per config;
    - seeds 1–500, 11 OOS years.
  - **Grid:** stop_mult ∈ {3, 5, 7, 10, 15, ∞} × type ∈ {fixed from entry, trailing at X·σ_annual with X ∈ {0.5, 1.0}}.
  - **Metrics:**
    - net Sharpe and the paired difference vs ∞;
    - skew; maximum drawdown; the worst day;
    - P(day < −2.5%) and P(day < −5%);
    - stop-outs per instrument-year; the cost of stop round trips;
    - the gap-through loss in excess of the stop level.
  - **Predictions:**
    - 10 ≈ 15 ≈ ∞ within ±0.01 Sharpe;
    - ≤ 5 is lower by a measurable margin on planted;
    - null loses only cost;
    - tighter stops shave the worst day only on the fat-tailed tape.
  - **Decision:** keep 10× unless a tighter stop cuts P(day < −5%) materially at a Sharpe cost ≤ 0.02.
- **SIM-2: the loss-at-stop cap (lab only).**
  - **Set-up:** as SIM-1 at stop 10×; L_pos ∈ {0.75, 1.0, 1.5, 2.0%, none}; cluster cap ∈ {3%, 5%, none}, with clusters from `config` correlation clusters.
  - **Metrics:** the share of decision-days a cap binds per instrument class; the gross Sharpe change; the worst single-position stop loss; P(the firm's 5% daily line), using the balance-anchored day (SIZING's simulator).
  - **Decision:** the largest L_pos with P(daily breach) below the owner's tolerance.
- **SIM-3: the slot-timing audit (P&L-blind, real data allowed).**
  - **Set-up:** for each slot candidate (US indices 10:00 / 10:15 / 10:30 New York; FX 08:00 / 09:00 / 11:00 New York; each other index's slot ±30 min), over 2012–2023 from the hourly bid/ask candles and the 8-instrument ticks:
    - the median and p95 spread in the ±2 min window;
    - the unsigned |mid move| over the next 5 min;
    - the share of slot-days within ±5 min of a high-impact release (needs the historical calendar: BLS plus the Fed for the US first, per the EXECUTION report §5.4).
  - **Decision:** take the earliest slot outside every window, with a spread ≤ 1.2× the session median.
- **SIM-4: the holding-period frontier check (lab).**
  - **Set-up:** a planted constant drift giving an in-market Sharpe S ∈ {0.3, 0.5, 1, 3, 10}; perfect-direction and realistic (IC-matched) oracles; holds {12 min, 1 h, 4 h, 1 d, 5 d}; C8 costs at the §3.2 low/central/high values for EUR/USD, XAU and US500.
  - **Output:** the net Sharpe surface.
  - **Prediction:** the break-even contour lies on §3.2's table within Monte Carlo error. This validates the table before anyone cites it in a spec.
- **SIM-5: trade-level barrier risk on the real book's shape (lab, after SIM-1).**
  - **Set-up:** replace §2.4's i.i.d. trades with the lab book's daily P&L series under the balance-anchored daily limit and E8 One's static/dynamic max loss.
  - **Output:** P(pass) and P(daily breach) by vol target. It hands the daily-room number to SIZING's guard.

---

## 6. The prior reports' claims, checked

| Claim (source) | Status |
|---|---|
| Stops cost money under a random walk (SIZING §8, citing Kaminski & Lo) | **Verified** (a). Add the stated exception: they can add value with momentum, at the stop's horizon |
| Carver: *"make sure your stop loss is consistent with your forecast horizon"*; speed limit = 1/3 of pre-cost return (SIGNAL §7.2) | **Verified** by fetch, plus the X-vs-trades table (§1.3) |
| Time-based throttles: negative evidence (SIGNAL §4) | **Consistent.** Clare et al. (a) also find monthly MA decisions beat daily ones, and stops add nothing |
| h_min = (c/(IC·σ_1min))², 7.3 h at IC 0.05 / 1.5 bp (EXECUTION §3.3) | **Verified** arithmetic. Complemented by the drift framing (§3.1), which puts EUR/USD's break-even at ~0.7–1.2 days for S = 0.3–0.5 |
| The harness tests stops against mid and fills at the level (EXECUTION F4) | Superseded for R1.6: **RSIM models no stop at all** (new; R-1) |
| Rollover spread 3× / 4.5× (EXECUTION §1.1, repo-measured) | Not re-measured. Consistent with Ito–Hashimoto's activity–spread link (a) |
| "No hold under ~36 min clears friction even with perfect direction" (GAP-P12D-49, R11I-01) | **Verified**: 35.5 min |
| IMOM: win rate 41%, payoff 1.69 (EDGE, (c)) | Consistent with a thin edge: break-even is 37% at zero cost and 39% at c_R = 0.05 (§2.2) |
| E8 One performance: no trading ±5 min of high-impact news, SL/TP included (SIZING) | **Verified** (a). Consequence: profit deduction at payout, not a breach |
| E8 "may cap risk at 1% per trade idea" (SIZING) | **Verified** via a search rendering of E8's page (a); the direct fetch returned 403. Wording: "no hard limits ... reserves the right to ... limit your risk to no more than 1% per trade idea ... if prohibited practices are detected" |

---

## 7. Open questions and what I could not verify

1. **How E8 measures "risk per trade idea".**
   - Is it the stop distance × size, or the floating loss?
   - Does a far disaster stop count as "risking the entire daily drawdown"?

   **Owner action:** read or ask E8 before live. R-2's L_pos depends on it.
2. **E8's cost schedule.** The commission (c: "0.005% of notional", about $5.50 per EUR/USD lot) and the index contract sizes are unverified; E8's help pages returned 403. This is the EDGE report's item 6 again.
3. **Whether E8 One allows weekend holding** (§4.4).
4. **ATR/σ on the venue's BID H1 bars,** including rollover spikes (GAP-P12D-141 (1)). It sets the stop's true σ distance; measurable P&L-blind.
5. **Kaminski & Lo's full paper** (the 2014 JFM version) was behind a bot wall. I relied on the published abstract and Kaminski's thesis abstract (a). **Lo & Remorov's numbers** come via CXO's summary (c).
6. **The Turtle rules** were read only through secondary renderings (c). They agree on 2N stops, ½N adds and 4 units per market, and disagree on the correlated-market limits, which I do not use.
7. **No peer-reviewed study compares ATR stops with fixed-% stops.** §1.3's case for vol-scaling is mathematical, not empirical.
8. **The i.i.d. Monte Carlo in §2.4 has no clustering, no gaps and no daily line.** SIM-5 replaces it.

## 8. Ledger items this pass should generate (the lead assigns IDs)

1. **RSIM grades no disaster stop and no re-entry rule; the engine trades both** (R-1).
   - Severity medium · Likelihood certain · Status open · [impl].
   - Add to GAP-P12D-141 now as a declared departure, and build it before any stop change.
2. **The engine refuses same-side adds while RSIM grades them** (R-5).
   - Severity medium (latent in practice, live-blocking) · Likelihood certain at live sizing · Status open · [impl].
3. **Per-position and per-idea loss-at-stop caps** (R-2), tied to E8's "entire daily drawdown on a single trade" rule.
   - Severity high at live · Likelihood high · Status open · [spec, OWNER, post-rung-1 with the guardrail profiles].
4. **The US-index slot (10:00 New York) collides with 10:00 ET releases; screen all slots against E8's ±5-minute list** (R-3, SIM-3).
   - Severity medium · Likelihood high · Status open · [spec].
5. **A vetoed slot entry drops the day instead of retrying within the grace window** (R-4).
   - Severity low · Likelihood medium · Status open · [impl].
6. **Weekend-holding must be true on any account running TREND, or the cost filter must include the forced Friday round trips; verify E8 One** (§4.4).
   - Severity medium · Likelihood medium · Status open · [owner check].
7. **The legacy fast loop's exits:** record "do not tune; retire from money-bearing accounts", with §5.2's rules for any revived fast sleeve.
   - Severity low · Likelihood n/a · Status open · [registry/spec note].

---

## Sources

All accessed **2026-10-02**. The grade is for the source; a claim read through a secondary carries the lower grade.

**Stops: theory and empirics**
- Kaminski & Lo, "When Do Stop-Loss Rules Stop Losses?", *J. Financial Markets* 18 (2014) 234–254, abstract: https://dspace.mit.edu/handle/1721.1/114876 (a)
- Kaminski, *General superposition strategies and asset allocation* (MIT thesis, 2007), abstract with the 1950–2004 result: https://dspace.mit.edu/handle/1721.1/40384 (a)
- Remorov, *Dynamic Trading and Behavioral Finance* (MIT PhD thesis, 2016; the Lo & Remorov stop-loss chapter), abstract: https://dspace.mit.edu/handle/1721.1/107017 (a)
- CXO Advisory, "Stop-Losses on Stock Positions in Depth" (summary of Lo & Remorov's thresholds and costs): https://www.cxoadvisory.com/equity-premium/stop-losses-on-stock-positions-in-depth (c)
- Clare, Seaton, Smith & Thomas, "Breaking into the blackbox: trend following, stop losses and the frequency of trading", *J. Asset Management* 14(3) (2013) 182–194, accepted version, full text: https://openaccess.city.ac.uk/17842/8/BLACKBOX%20%20%20SSRN-id2126476.pdf (a)
- Han, Zhou & Zhu, "Taming Momentum Crashes: A Simple Stop-Loss Strategy" (working paper), via CXO's summary: https://www.cxoadvisory.com/?p=25071 (b via c)
- Glynn & Iglehart, "Trading Securities Using Trailing Stops", *Management Science* 41(6) (1995) 1096–1106: https://ideas.repec.org/a/inm/ormnsc/v41y1995i6p1096-1106.html (a, abstract)
- Warburton & Zhang, "A simple computational model for analyzing the properties of stop-loss, take-profit, and price breakout trading strategies", *Computers & OR* 33(1) (2006) 32–42: https://iaorifors.com/paper/52451 (a, abstract)

**FX microstructure**
- Osler, "Stop-Loss Orders and Price Cascades in Currency Markets", NY Fed Staff Report 150 (2002; *JIMF* 2005), full text: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf (a)
- FCA press release, 2014-11-12, five banks fined for FX failings ("trigger client 'stop loss' orders"): https://www.fca.org.uk/news/press-releases/fca-fines-five-banks-%C2%A311-billion-fx-failings-and-announces-industry-wide (a)
- Goodhart & Figliuoli, "Every minute counts in financial markets", *JIMF* 10(1) (1991) 23–52, via the stylized-facts page and a search rendering: https://finance.martinsewell.com/stylized-facts/dependence (a via c)
- Ito & Hashimoto, "Intraday seasonality in activities of the foreign exchange markets: evidence from the electronic broking system", *JJIE* 20(4) (2006) 637–664: https://ideas.repec.org/a/eee/jjieco/v20y2006i4p637-664.html ; NBER w12413: https://www.nber.org/papers/w12413.pdf (a, abstract)

**Payoff shape and practitioners**
- Lempérière, Deremble, Nguyen, Seager, Potters & Bouchaud, "Risk premia: asymmetric tail risks and excess returns", *Quantitative Finance* 17(1) (2017), arXiv 1409.7720: https://ar5iv.org/html/1409.7720 (a)
- Carver, "How fast should we trade?" (2020-04), the stop-fraction table and the horizon rule: https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html (b)
- Carver, *Leveraged Trading* starter system (MAC 16/64, stop fraction 0.5), via a QuantConnect replication: https://www.quantconnect.com/terminal/cache/embedded_backtest_8375db950b6c237460ab18e37fae0b61.html (b via c)
- Curtis Faith's Original Turtle Trading Rules, via secondary renderings: https://www.mql5.com/en/articles/23448 (b via c)
- Trend-following hit-rate lore (not used as fact): https://www.turtletrader.com/babe-ruth (c)

**Venue and calendar**
- E8 Markets help centre, "Can I trade news?" (fetched): https://intercom.help/e8/en/articles/9185497-can-i-trade-news (a)
- E8 Markets help centre, "Is there any maximum risk rule?" (403 on fetch; read via a search rendering): https://help.e8markets.com/en/articles/9453413-is-there-any-maximum-risk-rule (a via search)
- E8 Markets help centre, "Trading Policies and Prohibited Trading Strategies" (search rendering only): https://help.e8markets.com/en/articles/6929927-trading-policies-and-prohibited-trading-strategies (a via search)
- E8 commission figure (unverified): https://www.metalsmine.com/thread/post/14399893 (c)
- ISM Report On Business release time (10:00 a.m. ET), via a search rendering: https://ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/ (a via search)

**Carried from the repo, not re-fetched:** Pepperstone index spreads and Razor commissions (a, the EDGE report); OANDA time-weighted spreads (a, the EXECUTION report); Novy-Marx & Velikov and Gârleanu–Pedersen (a, the SIGNAL report); repo-measured spreads, rollover and weekend gaps (the EXECUTION report §1.1 and §6.4); OPS-0001 venue facts.

## Method note

- **Search:** WebSearch 25 calls, under the 30 allowed. Then about 12 WebFetch calls, 4 of which failed (403/405/redirect), plus curl downloads into my scratchpad. Two PDFs were text-extracted locally with `pypdf`: Osler SR 150 and Clare et al. The Kaminski–Lo PDF was blocked by a bot challenge and was not read.
- **Computation:** closed forms and one i.i.d. Monte Carlo, 20,000 paths per cell, under 2 s of CPU in total. Scripts `exits_calc.py`, `barrier_mc.py` and `barrier_mc2.py` are in the session scratchpad. **No market data was read and no backtest was run.**
- **Web content was treated as data.** No fetched page contained instructions that I acted on.
- **Repo and git:** no file was edited except this report. I made no git writes and launched no agents.
