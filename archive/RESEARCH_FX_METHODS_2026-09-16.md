# External research: making a retail-scale systematic FX engine actually work

**Date:** 2026-09-16
**Status:** research artifact, OUT of the orienting read path (`archive/`). Not a spec, not a ledger entry. Nothing here binds until the owner ratifies it.
**Author role:** external research analyst. No engine code was read or written for this report; the brief's description of ACIS is taken as given.

### How to read the source grades

Every non-obvious claim carries a source with a grade:

- **(a) peer-reviewed / academic** — journal article, NBER/CEPR working paper, university working paper.
- **(b) credible practitioner** — named fund, exchange, central bank, regulator, or an established quant author writing under their own name with reproducible method.
- **(c) unverifiable / marketing / low-confidence** — broker content, vendor blog, student project, anything whose method I could not inspect. Used only where nothing better exists, and flagged.

Where I compute something myself I label it **[derived here]** and give the inputs so you can check it. Two of the most important conclusions in this report are arithmetic, not citations — you should re-derive them with your own measured volatility and cost numbers before acting.

---

## Executive summary — the five things that matter most

**1. Your holding period is the strategy. Everything else is detail.** There is a hard identity: for a continuously-exposed system, the cost drag in Sharpe-ratio units equals (round trips per year × round-trip cost) ÷ (annualised volatility). At 1 bp round trip on EUR/USD (≈7% annualised vol), an 8-minute holding period costs **≈67 Sharpe units per year**; 8 hours costs 1.11; 48 hours costs 0.19; five days costs 0.07 **[derived here, verified numerically]**. Rob Carver's independently-derived practitioner "speed limit" — never spend more than one third of expected pre-cost Sharpe on costs, which he operationalises as ≈0.13 SR units per year — lands at a **minimum holding period of ~69 hours (≈2.9 trading days)** for your cost structure ([qoppac, *How fast should we trade?*, 2020](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html), **(b)**; [*Fast but not furious*, 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html), **(b)**). **Your declared 30 min – 48 h band is viable only at its extreme upper end. The lower half of it is arithmetically impossible, not merely hard.** This is a spec-level finding.

**2. Your ATR barriers, not your signal, are why the planted market failed.** For symmetric barriers at ±d with per-step drift μ and per-step sd σ, P(take-profit first) = 1/(1+e^(−2μd/σ²)), so expected gross profit per trade grows with **d²** while cost is fixed. At your planted edge (0.15σ/step) and EUR/USD-scale volatility, break-even is at d ≈ 3 bps — which is **exactly** a 2× multiple of 1-minute ATR. Widen the barrier to 10 bps and the same signal yields +7.7 bps net per trade instead of +0.12 **[derived here, verified numerically]**. Your engine is sitting precisely on the zero-profit isoquant of its own exit geometry. That is why planted, null and permuted all land in a 0.4-Sharpe band: the exit destroys the edge before the entry can express it.

**3. The optimiser–execution mismatch is the textbook failure, and making the optimiser *better* makes it *worse*.** You optimise a dual-EMA proxy with 8 of 11 genes on continuous bars, and trade a six-module, ATR-barriered, dedup-gated system. This is Goodhart's law in its *extremal* form ([Manheim & Garrabrant, arXiv:1803.04585](https://arxiv.org/abs/1803.04585), **(a)**) and *objective mismatch* in the RL sense ([Lambert et al., L4DC 2020](http://proceedings.mlr.press/v120/lambert20a.html), **(a)**). Worse: Bailey/Borwein/López de Prado/Zhu prove the probability of backtest overfitting **approaches 1 as the number of configurations tried grows**, independent of whether any configuration has real skill ([*The Probability of Backtest Overfitting*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253), **(a)**). A quantum-inspired evolutionary search over 11 genes × 12 regimes is a machine for maximising exactly the quantity that PBO says destroys you. **Search power is not your bottleneck; search power is your liability.**

**4. Your §14 targets are internally inconsistent and, at the top end, not supported by any evidence for FX at retail scale.** ">70% positive months" implies annual Sharpe 1.82, which is *stricter* than your stated Sharpe > 1.5 (which implies 66.7% positive months) **[derived here]**. "PF > 1.4" combined with "Sharpe > 1.5" pins trade count at ≈125/year — a horizon statement your spec never makes; at your realised 900 trades/year, PF > 1.4 would require annual Sharpe ≈ 4.0 **[derived here]**. And the external evidence: a walk-forward FX-only trend study on your exact seven majors, 2003–2025, got a **portfolio Sharpe of 0.43** ([QuantInsti/EPAT project](https://www.quantinsti.com/articles/trend-following-strategies-major-currency-markets-epat-project/), **(c)** — student project, but the method is honest walk-forward); the SG Trend Index (the ten largest trend CTAs, all asset classes, professional execution) has run a Sharpe of ~0.42 ([ReSolve Asset Management](https://investresolve.com/how-to-replicate-trend-following-managed-futures/), **(b)**); a century of trend-following evidence shows Sharpe ≈0.4 *in every decade* (Hurst, Ooi & Pedersen, AQR, **(b)**); post-GFC FX carry Sharpe fell from ~1.08 to ~0.25 ([*Currency carry trade: the decline in performance after the 2008 GFC*, JIFMIM 2022](https://www.sciencedirect.com/science/article/abs/pii/S1042443121001670), **(a)**). **Verdict: Sharpe > 1.5 net, out-of-sample, on 2–9 FX instruments at retail cost is fantasy. 0.4–0.7 is ambitious-but-possible. Anything above 1.0 sustained should be treated as evidence of a bug until proven otherwise.**

**5. Your regime engine is the least defensible component you have, and the literature specifically says so.** Daccò & Satchell's result is directly on your architecture: with regime-switching models on exchange rates, *forecasts based on the true model can have higher MSE than a random walk*, because "only a small misclassification when forecasting which regime the world will be in" destroys the advantage of knowing the correct specification ([*Why do regime-switching models forecast so badly?*, J. Forecasting 1999](https://onlinelibrary.wiley.com/doi/abs/10.1002/(SICI)1099-131X(199901)18:1%3C1::AID-FOR685%3E3.0.CO;2-B), **(a)**). Your classifier is not even an estimated model — it is threshold rules on ATR/ADX-proxy/Bollinger-width/Hurst, and Hurst via R/S is known to be badly biased in short windows (the Anis–Lloyd correction exists precisely because expected R/S of white noise sits above the H=0.5 asymptote; R/S estimates still run +0.05 to +0.16 high versus other estimators). Twelve regimes × 11 genes fragments your sample into cells that cannot support parameter estimation, and Carver's pooling experiment across 214 instruments found **pooled** fitting beat per-unit fitting in three of four window configurations ([qoppac, *Jumping back in the pool(ing)*, 2026](https://qoppac.blogspot.com/2026/07/jumping-back-in-pooling-testing-pooling.html), **(b)**).

---

## §0. Two pieces of arithmetic that dominate questions 1–4

I put these first because the answers to Q1, Q2, Q3 and Q4 are largely consequences of them. Both are derivations, not citations — check them.

### 0.1 The cost–horizon identity

Let `c` = round-trip cost as a fraction of notional, `σ_ann` = annualised volatility of the instrument, `T` = market minutes per year (FX ≈ 1440 × 260 = 374,400), `h` = mean holding period in minutes, `N` = round trips per year.

For a system that is **continuously exposed** (N = T/h):

```
cost drag, in annual Sharpe-ratio units  =  c · N / σ_ann  =  c · T / (σ_ann · h)
```

i.e. **the cost hurdle is inversely proportional to holding period.** With c = 1 bp and σ_ann = 7% (EUR/USD, 2012–2025 order of magnitude; measure your own):

| holding period `h` | round trips/yr | cost drag (Sharpe units) |
|---|---|---|
| 8 min (your realised) | 46,800 | **66.9** |
| 30 min (your spec floor) | 12,480 | **17.8** |
| 2 h | 3,120 | 4.46 |
| 8 h | 780 | 1.11 |
| 24 h | 260 | 0.37 |
| 48 h (your spec ceiling) | 130 | **0.19** |
| 5 trading days | 52 | 0.07 |
| 10 trading days | 26 | 0.04 |

*(If each "trade" is a full long→short reversal it moves 2× notional, so double every drag figure; the qualitative conclusion only hardens.)*

Carver's speed limit — costs ≤ ⅓ of expected pre-cost Sharpe, in practice ≈0.13 SR units/yr — is met at **h ≈ 4,100 minutes ≈ 69 hours ≈ 2.9 trading days**. Your entire declared band sits below that except the last few hours of it.

For your actual falsification run (not continuously exposed — 2,018 trades in 817 days, ~8 min each, so the engine is flat ~99.3% of the time):

- 902 round trips/year, per-trade sd ≈ 3.24 bps (8 minutes of EUR/USD-scale noise)
- annual cost ≈ **9.02% of notional**
- annual P&L standard deviation ≈ **0.97% of notional**
- **cost drag ≈ 9.3 Sharpe units**

**This number does not reconcile with your reported −0.65 / −0.90 / −0.49.** Either (i) the synthetic markets are roughly 8–9× more volatile than real EUR/USD, or (ii) the simulated costs are far below 1 bp round trip. Both are findings. If (i), your falsification harness is *flattering* the engine and the same configuration on real Dukascopy ticks will be far worse than −0.65. **Recommendation: measure the synthetic markets' realised 1-minute standard deviation against real EUR/USD 1-minute standard deviation and report the ratio.** A falsification harness whose markets are not volatility-calibrated to the real thing cannot falsify anything about cost-sensitivity, which is your dominant failure mode.

### 0.2 The barrier-geometry identity

For arithmetic Brownian motion with per-step drift μ and per-step sd σ, starting at 0, with symmetric absorbing barriers at ±d:

```
P(hit +d before −d)  =  1 / (1 + exp(−2μd/σ²))
E[gross per trade]   =  (2P − 1) · d
```

For small θ = 2μd/σ², this expands to **E[gross] ≈ μd²/σ²** — quadratic in barrier width — while cost `c` is **constant in d**. Break-even barrier width is therefore `d* = σ·√(c/μ)`.

With your planted market (μ = 0.15σ/step), σ ≈ 1.144 bps/min (EUR/USD scale), c = 1 bp:

| barrier d (bps) | ≈ E[duration] | P(win) | gross (bp) | **net (bp)** |
|---|---|---|---|---|
| 1 | 0.8 min | 0.565 | 0.13 | **−0.87** |
| 2 | 3.1 min | 0.628 | 0.51 | **−0.49** |
| **3** | **6.9 min** | **0.687** | **1.12** | **+0.12** |
| 5 | 29 min | 0.788 | 2.88 | +1.88 |
| **10** | **58 min** | **0.932** | **8.65** | **+7.65** |
| 20 | 117 min | 0.995 | 19.79 | +18.79 |
| 30 | 175 min | 1.000 | 29.98 | +28.98 |

Read the bolded row: **d = 3 bps gives a 6.9-minute expected duration, a 68.7% win rate and +0.12 bp per trade — essentially zero.** Your observed mean duration is 8 minutes and your observed win rate on the planted market is 42.7%. A 2× multiple of 1-minute ATR on EUR/USD *is* about 3 bps. You are not near the zero-profit line by coincidence; your exit geometry places you on it by construction, and the residual gap between 68.7% theoretical and 42.7% observed is what the other five modules and the untuned genes are costing you.

**The single highest-expected-value change available to you is to multiply your barrier widths by roughly an order of magnitude.** Same signal, same optimiser, same everything: +0.12 bp/trade → +7.65 bp/trade.

---

## §1. Optimiser / execution consistency

### 1.1 What class of error this is, and what the literature calls it

You optimise `f(θ)` = the P&L of a dual-EMA mini-backtest on continuous bars using 8 genes, and you deploy `g(θ)` = a six-module signal layer with ATR barriers, regime gating, dedup and a session-boundary promotion gate, using 11 genes. `f` is a *surrogate* for `g`. Three literatures name this:

1. **Goodhart's law, formalised.** Manheim & Garrabrant decompose proxy failure into *Regressional* (optimising the proxy also optimises proxy-minus-goal noise), *Extremal* (the region where the proxy is extreme is not the region where proxy and goal were observed to correlate), *Causal* and *Adversarial* ([arXiv:1803.04585](https://arxiv.org/abs/1803.04585), **(a)**; [MIRI summary](https://intelligence.org/2018/03/27/categorizing-goodhart/), **(b)**). Yours is primarily Extremal: the dual-EMA proxy's profitability comes from *holding through the trend*, which is precisely the property the deployed system lacks. In the region of parameter space where the proxy scores highest, the correlation between proxy and deployed P&L is not merely weak — there is no mechanism connecting them.

2. **Objective mismatch (model-based RL).** Lambert, Amos, Yadan & Calandra, *Objective Mismatch in Model-based Reinforcement Learning* (L4DC 2020, [PMLR v120](http://proceedings.mlr.press/v120/lambert20a.html), **(a)**): a dynamics model is trained on likelihood while the policy is evaluated on reward, and improving the former can *degrade* the latter. Your evolution improves the dual-EMA proxy; there is no reason for that to improve booked P&L, and empirically it does not.

3. **Training/serving skew (ML engineering).** The engineering literature's remedy is structural, not analytic: *one shared calculation core called by both runtimes, plus an automated replay assertion that the two agree*. Divergence in NaN handling, rolling-window boundaries and warm-up behaviour is the canonical cause of backtest-live drift ([Feature Store for Live and Backtest Parity](https://skills.himanshujangir.com/skills/feature-store-for-live-and-backtest-parity/), **(c)**; the same principle in [QuantStart's backtesting-considerations article](https://www.quantstart.com/articles/backtesting-systematic-trading-strategies-in-python-considerations-and-open-source-frameworks/), **(b)**).

Your bug is a *sharper* version of training/serving skew: the industry usually worries that the backtest and live engine differ by accident. Yours differ **by design** — the fitness function is a deliberately different strategy.

### 1.2 What production systematic shops actually do

There is no serious systematic shop that optimises a proxy strategy and trades a different one. The four things they do instead, in rough order of how commonly you see them:

**(i) Fitness *is* the backtest of the deployed system.** López de Prado is explicit that "research through backtesting" is itself one of the ten reasons ML funds fail — not because backtesting is wrong, but because *backtest-as-search* is ([*The 10 Reasons Most Machine Learning Funds Fail*, JPM 2018](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104816), **(a)**; [GARP copy](https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf)). His prescription is the *meta-strategy paradigm*: build a theory first, and use the backtest to **falsify**, not to select. That is exactly the discipline your falsification harness was built for — you already have the right tool; you are just not using its output as the fitness.

**(ii) Two-stage decomposition with an explicit contract between the stages (meta-labelling).** López de Prado's triple-barrier + meta-labelling design *legitimises* having two models — a primary signal model and a secondary sizing/filter model — by making the second model's training labels come from the **actual realised outcome of the first model's trades under the real barrier geometry** ([*Advances in Financial Machine Learning*, 2018; summary at Hudson & Thames](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/), **(b)**). The key structural point for you: the label is generated by simulating the *deployed* exit rules. That closes the loop your architecture leaves open.

**(iii) Per-rule fitness with portfolio-level combination, not joint search.** Carver's approach is to fit each trading rule's parameters (or rather, to *not* fit them, and use a spread of speeds), then allocate between rules with robust optimisation — treating parameter selection as "a diversification problem, not an optimisation problem" ([Better System Trader ep. 26](https://bettersystemtrader.com/026-robert-carver/), **(b)**; [*Trading Strategies That Are Designed Not Fitted*](https://www.slideshare.net/Quantopian/trading-strategies-that-are-designed-not-fittedby-robert-carver-independent-systematic-futures-trader-writer-and-research-consultant), **(b)**). This is what your "three unoptimised genes" problem is begging for: the breakout / mean-reversion / momentum-scalp modules should each carry their own fitness on their own realised trades, or be switched off.

**(iv) Walk-forward as a simulation of the whole process, not of one component.** Pardo's original point is that WFO "simulates the actual process of trading a strategy over time" ([Better System Trader ep. 60 with Robert Pardo](https://bettersystemtrader.com/060-strategy-optimization-with-robert-pardo/), **(b)**). If the thing you re-optimise each fold is not the thing you trade, the simulation is not of your process, and its out-of-sample numbers carry no information about your process.

### 1.3 Recommendations for Q1

| # | Change | Type |
|---|---|---|
| 1.1 | **Fitness must be the deployed execution path**, end to end: same regime gating, same six modules, same barriers, same dedup, same promotion gate, same cost model. If that is too slow, make it faster (§8.6) — do not make it different. | **spec-level** (it changes what QIEA optimises, SPEC §5) |
| 1.2 | Add a **parity assertion test**: replay one fold through the fitness path and through the engine path and assert the two order sequences are identical. If they cannot be made identical, the difference is the finding. | implementation fix |
| 1.3 | Until 1.1 lands, **disable the breakout, mean-reversion and momentum-scalp modules**. Three genes selected by nothing are not "unoptimised"; they are random, and the modules they drive are emitting trades that cost money and carry no fitness pressure. Disabling is the lean-build answer (SPEC §18) and is testable this week. | implementation fix (module enablement), but touching SPEC §5's module list is **spec-level** |
| 1.4 | Record the **promotion gate** as part of the optimised object. "39 of 91 promoted" means a silent filter sits between what was selected and what runs. Either fold the gate into the fitness simulation or remove it. | implementation fix |
| 1.5 | The **marginal-alpha sizing input pinned constant across 1.4M sizings** means position size carries zero signal-strength information. See §2.3 — this is the same class of error at the Governor layer. | implementation fix |

---

## §2. Entry / holding policy: turning a signal stream into positions

### 2.1 The central design principle: target position, not entry event

The dominant modern formulation is **not** "when do I enter / when do I exit". It is: at each decision time, compute a **desired position** as a continuous function of signal strength and volatility, and then trade *toward* it subject to cost.

The canonical theory is Gârleanu & Pedersen, *Dynamic Trading with Predictable Returns and Transaction Costs* (Journal of Finance 68(6), 2013; [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1364170), [NBER w15205](https://www.nber.org/papers/w15205), [author PDF](https://nbgarleanu.github.io/DynTrad.pdf), **(a)**). Two results matter to you directly:

- **"Aim in front of the target, and trade partially towards the aim."** The optimal portfolio is a linear blend of your current portfolio and an *aim* portfolio, which itself weights the current Markowitz portfolio against expected future ones. You never jump to the target; you move a fraction of the way.
- **Predictors with slower alpha decay get more weight in the aim portfolio.** Fast-decaying signals are systematically *down-weighted* because you cannot capture them net of cost. Your 3–12 month TSMOM module should therefore carry far more weight than your momentum-scalp module — the opposite of what per-tick emission produces.

The follow-on literature confirms the structure: with proportional switching costs the optimal policy is **a no-trade zone whose boundary is a function of the signal state**, and with a fast-decaying signal "the optimal trading can even be buy-and-hold" ([*On the Effect of Alpha Decay and Transaction Costs on the Multi-period Optimal Trading Strategy*, arXiv:2502.04284](https://arxiv.org/abs/2502.04284), **(a)**).

### 2.2 The empirically validated components, ranked by how much they matter at your scale

**(1) A no-trade band / buffer around the target position — the highest-value single fix after barrier width.**
Novy-Marx & Velikov tested cost-mitigation techniques across 23 anomalies and found: *"Introducing a buy/hold spread, which allows investors to continue to hold [positions] that they would not actively trade into, is the single most effective simple cost mitigation strategy. The average reduction in turnover … is 41%, while transaction costs decrease by 42%, with net returns consequently higher"* ([*A Taxonomy of Anomalies and their Trading Costs*, NBER w20721 / RFS](https://www.nber.org/system/files/working_papers/w20721/w20721.pdf), **(a)**). They also find that anomalies with one-sided monthly turnover **below 50%** keep significant net spreads while few above it do — a turnover ceiling that maps almost exactly onto Carver's speed limit.
Carver measures the same effect directly on trend rules: buffering cut turnover ~17% for the fastest EWMA rules, and dynamic optimisation cut costs by about a third ([*Fast but not furious*, 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html), **(b)**).

**(2) Continuous, capped, volatility-scaled forecasts instead of binary signals.**
Carver's construction: forecast is scaled so that a +10 reading corresponds to a positive expected Sharpe, capped at ±20; position = forecast × (target risk / instrument volatility) ([Systematic Trading, summarised at 7 Circles](https://the7circles.uk/systematic-trading-3-frameworks-and-forecasts/), **(b)**). His stated reason for rejecting binary signals is exactly a cost argument: a binary system must sell *two* full positions to flip, so it pays double at every reversal. **Your Governor already has the machinery for this (fractional-Kelly, volatility targeting) but the marginal-alpha input is pinned to a constant, which makes it binary in practice.**

**(3) Signal aggregation across speeds rather than selection of one speed.**
Carver: *"I recommend keeping at least 3 variations of moving average in your system"* ([*How fast should we trade?*](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html), **(b)**). This is diversification of the *parameter* rather than optimisation of it, and it is the single most robust known defence against parameter overfitting in this family. Baltas & Kosowski find the analogous result on the volatility-estimation side: a better (Yang–Zhang range-based) estimator cut turnover by ~17–33% *without material performance impact* ([*Demystifying Time-Series Momentum Strategies*, CME PDF](https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf), **(a)/(b)**).

**(4) Minimum holding period / trade throttle.** Less well documented in the literature as a standalone device (because target-position designs make it unnecessary — a buffer *is* a throttle), but it is the cheapest emergency brake you can install and it directly attacks your 706:1 signal-to-trade ratio.

### 2.3 What is actually wrong with your loop

The reported diagnostics are decisive:

- **1,425,326 signals emitted across 2,352,960 instrument-minutes = a signal on 60.6% of all instrument-minutes** **[derived here]**. The layer is not producing signals; it is producing a continuous opinion, which is fine — but you are treating that opinion as an event stream.
- **2,018 booked trades × 8 min = 0.7% of available instrument-time in the market** **[derived here]**. The engine holds an opinion 60% of the time and a position 0.7% of the time. The book-level dedup is therefore discarding **99% of your intended exposure**, and it is doing so on a criterion that has nothing to do with the strategy.
- **The dedup layer is your de facto position-management policy.** It was never designed to be one. This is the same failure class as §1: a component whose behaviour dominates outcomes was never subject to the fitness function.

### 2.4 Recommendations for Q2

| # | Change | Type |
|---|---|---|
| 2.1 | **Replace event-based entries with a target-position map.** At each decision bar, each module emits a bounded forecast; forecasts are combined; the combined forecast maps to a desired position via volatility scaling. The orchestrator's job becomes "close the gap between current and desired", not "open/close trades". | **spec-level** (rewrites the AGON→Governor→Execution contract, SPEC §2/§5/§6) |
| 2.2 | **Add a buffer/no-trade band** around the desired position (Carver's default is roughly ±10% of the average absolute position; Novy-Marx & Velikov's buy/hold spread is the same idea). Do not trade unless the gap exceeds the band. | implementation fix once 2.1 lands; **spec-level** if 2.1 is deferred and you bolt a band onto the current design |
| 2.3 | **Un-pin the marginal-alpha input** so position size varies with signal strength. Cap the forecast. A binary-in-practice system pays double at every reversal. | implementation fix |
| 2.4 | **Move the decision clock off the tick.** Decide once per bar at a frequency matched to the signal horizon (see §3). Per-tick decisioning is the root cause of the 706:1 ratio and buys you nothing at 1 bp costs — you are not an HFT. | **spec-level** |
| 2.5 | **Ensemble the speeds**: run ≥3 EMA speed variants per module and average their forecasts rather than evolving one "best" speed. | **spec-level** (changes what a ParamSet is) |

**Which of these matter most at 1-minute resolution with ~1 bp costs?** In order: (2.4) horizon/clock, (2.1) target-position mapping, (2.2) buffering, (2.3) continuous sizing, (2.5) speed ensembling. The first two are worth more than the rest combined, because they are the only ones that change the *order of magnitude* of turnover.

---

## §3. Exit design and horizon matching

### 3.1 What the evidence actually says about stops

The results here are more nuanced than either "always use stops" or "never use stops", and the nuance is exactly your problem.

**Under a random walk, simple stop-loss rules strictly reduce expected return; under momentum, they can add value.** Kaminski & Lo, *When do stop-loss rules stop losses?* (Journal of Financial Markets 18, 2014, pp. 234–254; [MIT DSpace PDF](https://dspace.mit.edu/bitstream/handle/1721.1/114876/Lo_When%20Do%20Stop-Loss.pdf), **(a)**) prove the random-walk case analytically and show empirically that on US index futures 1950–2004, stop-loss overlays on a buy-and-hold added **50–100 bp/month during stop-out periods**. The mechanism is momentum, i.e. *the stop has to be wide enough and slow enough that being stopped out is itself informative.*

**Stops at the right scale for the signal work; stops at the wrong scale destroy.** Han, Zhou & Zhu, *Taming Momentum Crashes: A Simple Stop-Loss Strategy* ([SSRN 2407199](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199), **(a)**): a **10% monthly** stop on a monthly-rebalanced momentum strategy cut maximum monthly loss from −49.8% to −11.4% and **more than doubled the Sharpe** (0.119 → 0.179 for the equal-weighted book). Note the scale: a 10% stop on a *monthly* signal. That is roughly 0.5× the annualised volatility of the underlying — the same order as Carver's rule of thumb.

**On individual securities with no momentum overlay, stops neither help nor hurt returns; their value is risk reduction.** Lei & Li, *The Value of Stop Loss Strategies* (Financial Services Review 18(1), 2009; [SSRN 1214737](https://www.ssrn.com/abstract=1214737), **(a)**).

**The practitioner synthesis: a stop is a trading rule, and if you already have a continuous trading rule you do not need a separate stop.** Carver's stop-width formula is `stop = X × annualised volatility of the instrument`, with X the parameter that sets holding period — his worked example is Apple at 20% annual vol, X = 0.5 → a 10% stop ([*What is the right way to set stop losses?*, 2020](https://qoppac.blogspot.com/2020/02/what-is-right-way-to-set-stop-losses.html), **(b)**). And crucially, he publishes the mapping from X to trading frequency ([*How fast should we trade?*](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html), **(b)**):

| X (stop width / annual vol) | trades per year |
|---|---|
| 0.1 | 46.9 |
| 0.3 | 11.9 |
| 0.5 | 5.4 |
| 1.0 | 1.7 |

**Now locate ACIS on that table.** Your stop is `atr_multiplier_sl × ATR(1-minute)`. With EUR/USD at ~7% annualised vol, 1-minute ATR is on the order of 1.5 bps, so a 2× multiple is ≈3 bps = 0.03%. In Carver's units, **X ≈ 0.03 / 7 ≈ 0.004** — roughly **25× tighter than the tightest row on his table**, which already produces 47 trades/year. Extrapolating the first-passage relation (E[T] ≈ (d/σ)² periods) gives an expected holding time of ≈7 minutes — and you measured 8. **Your observed holding period is a deterministic consequence of your stop width under a driftless random walk. The exit is carrying no information whatsoever.**

### 3.2 The asymmetry between stop distance and expected drift — the quantitative rule

This is §0.2 restated as a design rule. For a drift-capture system:

> **Expected gross profit per trade grows with the square of the barrier width; cost is constant in barrier width. Therefore, as long as the drift persists over the implied holding time, wider barriers strictly dominate — and there is a hard minimum barrier width `d* = σ·√(c/μ)` below which the system has negative expectancy *no matter how good the signal is*.**

For your planted market: `d* ≈ 3 bps`. You are at 3 bps. This is why planted, null and permuted are indistinguishable.

**The corollary is the horizon-matching rule:** the barrier width must be set so the implied first-passage time is *comparable to the alpha decay horizon of the signal*, not shorter. Your edge pays over 1–4 hours; the barrier that gives a ~1-hour expected duration under EUR/USD-scale volatility is **d ≈ 10 bps** (58 min), and at that width the same planted signal yields +7.65 bp/trade net **[derived here]**.

This is the same conclusion Gârleanu & Pedersen reach from the other direction (trade rate should scale with alpha decay rate, not with signal arrival rate) and the same one López de Prado's triple-barrier method encodes structurally: the **vertical (time) barrier** exists specifically so that the horizon is a designed quantity rather than an accident of the price barriers ([triple-barrier description, Hudson & Thames](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/), **(b)**; [mlfinpy docs](https://mlfinpy.readthedocs.io/en/latest/Labelling.html), **(c)**).

### 3.3 Time-based exits

Under-appreciated and cheap. The triple-barrier method's vertical barrier is the standard formulation: if neither price barrier is touched within `n` periods, exit flat and label the trade neutral. Two properties make it valuable for you:

- It **bounds holding period from above** without truncating the winners from below (unlike a tight stop).
- It makes the holding horizon an **explicit, optimisable parameter** instead of an emergent property of ATR and volatility. Your `max_holding_periods` gene (1–48) already exists but on a 1-minute base it caps you at 48 minutes — below the horizon of the edge you are trying to capture. **That is a second, independent horizon bug: the gene's unit is wrong.**

### 3.4 Trailing stops

Evidence is thin and mixed; treat as a second-order refinement. Dai et al., *Risk reduction using trailing stop-loss rules* (International Review of Finance, 2021, **(a)**) find risk reduction rather than return improvement, consistent with Lei & Li. Trailing stops have the same scale problem as fixed stops: a trailing stop at 2× 1-minute ATR is still a 3-bps barrier.

### 3.5 Recommendations for Q3

| # | Change | Type |
|---|---|---|
| 3.1 | **Re-base ATR (and every volatility input to the exit) onto the signal's own timeframe**, not 1-minute bars. If the signal is a 4-hour trend, the stop must be sized off 4-hour (or daily) ATR. | **spec-level** (changes SPEC's indicator time base — note your own external review already found a tick-vs-bar time-base problem; this is the same defect in the exit layer) |
| 3.2 | **Re-express the stop gene in volatility-of-the-instrument units, not ATR multiples**: `stop = X × σ_ann`, with X ∈ [0.2, 1.0] as in Carver. This makes the parameter horizon-meaningful and cross-instrument comparable. | **spec-level** (ParamSet gene semantics, SPEC §5) |
| 3.3 | **Re-base `max_holding_periods` to the decision bar**, and widen its range so the vertical barrier can reach 48 h. Currently it cannot express your own declared holding intent. | **spec-level** |
| 3.4 | **Make take-profit asymmetric or remove it.** A symmetric TP truncates exactly the right tail that trend capture depends on. The evidence for profit targets in trend-following is essentially absent; the evidence for letting winners run is the entire trend-following literature. If you keep a TP, it should be ≥3× the stop. | **spec-level** |
| 3.5 | **Add a falsification assertion**: for any promoted ParamSet, assert `barrier_width > σ·√(cost/expected_drift)` using the fitness function's own measured expected drift. A ParamSet that fails this cannot have positive expectancy and should never be promoted. | implementation fix (and a very cheap guard) |
| 3.6 | **Report mean holding period as a first-class metric in every backtest and every walk-forward fold**, with a hard alarm if it falls below the declared band. You lost a full falsification run to a number nobody was watching. | implementation fix |

---

## §4. Does this approach work at all at our scale? (Blunt answer)

### 4.1 What is documented, and what survives costs

**Time-series momentum / trend-following — documented, contested, decayed, and horizon-dependent.**
- Moskowitz, Ooi & Pedersen (JFE 2012) is the origin: past 12-month returns predict the next 1–12 months across ~58 instruments; the diversified strategy had annualised Sharpe ≈1.1 ([NYU Stern PDF](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf), **(a)**).
- **The critique is serious.** Huang, Li, Wang & Zhou, *Time-series momentum: Is it there?* (JFE 135(3), 2020, 774–794; [SMU PDF](https://ink.library.smu.edu.sg/context/lkcsb_research/article/7520/viewcontent/Time_series_momentum_JFE_sv.pdf), **(a)**): asset-by-asset regressions show little evidence in or out of sample; the pooled t-statistic fails parametric and non-parametric bootstraps; and the TSM strategy's performance is *virtually identical to a strategy based on the historical sample mean, which requires no predictability at all.* Their conclusion: the overall evidence for TSM is weak.
- **The honest long-run number is ~0.4, not ~1.1.** Hurst, Ooi & Pedersen's century study (1880–2016) finds annualised Sharpe near 0.4 in *every* decade (**(b)**, AQR). The SG Trend Index — the ten largest trend CTAs, professional execution, all asset classes — has run about 0.42 ([ReSolve](https://investresolve.com/how-to-replicate-trend-following-managed-futures/), **(b)**).
- **AQR's own explanation of the weak 2010s** is that market moves were smaller, not that trend broke: they explicitly reject declining "trend efficiency" and declining diversification as causes ([*You Can't Always Trend When You Want*, JPM 2020](https://images.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-You-Cant-Always-Trend-When-You-Want.pdf), **(b)**). This is a defensible position but it is also an unfalsifiable-sounding one; treat it as an argument, not a finding.
- **FX-only trend is materially worse than diversified trend.** The walk-forward study on your exact universe (7 majors, daily bars, 2003–2025, spreads + FRED-derived swap costs, 3y train / 1y test × 23 windows) found: only USDJPY (0.78) and EURUSD (0.54) cleared Sharpe 0.5 on a standalone basis; every other pair was between 0.05 and 0.42; **the best portfolio construction achieved Sharpe 0.43, CAGR 1.24%, max DD −8.25%**; and the overall out-of-sample Sharpe across all pair×strategy combinations was **0.14** ([QuantInsti/EPAT](https://www.quantinsti.com/articles/trend-following-strategies-major-currency-markets-epat-project/), **(c)** — student project, no slippage modelled, but honest walk-forward and the closest published analogue to your exact setup). Their leverage sensitivity is also worth reading: 2× leverage took Sharpe from 0.38 to 0.06 because financing cost and compounding asymmetry eat it.

**Carry — documented, substantial, and largely destroyed for retail by broker swap markups.**
- Pre-GFC Sharpe ~1.08; post-GFC ~0.25 ([JIFMIM 2022](https://www.sciencedirect.com/science/article/abs/pii/S1042443121001670), **(a)**). The Lustig–Roussanov–Verdelhan HML-FX benchmark runs ~0.76 over its full sample (**(a)**). Skewness is meaningfully negative (~−0.94 for diversified carry), i.e. Sharpe overstates it.
- **The retail killer:** carry returns accrue through overnight financing, and retail brokers add a markup to *both sides*. IBKR's published FX/margin financing applies roughly 1.5% over benchmark on the first $100k, stepping down above $1m ([IBKR margin rates](https://www.interactivebrokers.com/en/trading/margin-rates.php), **(b)**). CFD/spread brokers typically add 0.5–3% annually, and the markup is applied so that you pay more when short the funding currency *and* receive less when long it (**(c)**, broker education content — verify against your own broker's published swap table, not against this). **A 1–3% annual round-trip markup against a post-GFC carry Sharpe of 0.25 on a ~8% vol strategy is roughly the whole premium.** This is also a direct hit on your current financing model: you model financing from central-bank overnight rates. That is the *right* number for the world and the *wrong* number for your P&L, and it will make carry-tilted strategies look better in backtest than they will ever be live. Flag as a modelling bias, not just an approximation.

**Cross-sectional FX momentum — documented, but transaction-cost sensitive and needs many currencies.**
Menkhoff, Sarno, Schmeling & Schrimpf (JFE 106(3), 2012; [PDF](https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20(1).pdf), **(a)**): up to 10% p.a. spread between winner and loser currencies, MOM(1,1) Sharpe 0.95 versus 0.82 for carry. But: *"Momentum returns are fairly sensitive to transaction costs … adjusting returns for bid-ask spreads lowers the profitability significantly since momentum portfolios are skewed towards currencies with high transaction costs."* Their cross-section is 48 currencies; **with 8 instruments you cannot run this strategy** — you do not have enough cross-section for the sort to mean anything.

**Technical trading in FX — genuine historically, gone by the early 1990s for the simple rules.**
Neely, Weller & Ulrich, *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market* (JFQA 2009; [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345), **(a)**): the 1970s–80s excess returns were real and not data-mining artefacts, **but had disappeared by the early 1990s for filter and moving-average rules**; returns to less-studied rules declined but probably have not vanished entirely. Neely & Weller (JBF 2013) confirm the decay mechanism ([*Lessons from the Evolution of FX Trading Strategies*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1932844), **(a)**).
The main dissent is Hsu, Taylor & Wang, *Technical trading: Is it still beating the foreign exchange market?* (Journal of International Economics 102, 2016, 188–208; [SSRN](https://papers.ssrn.com/abstract=2765673), **(a)**): 30 currencies, 45 years of daily data, >21,000 rules, stepwise SPA test against data-snooping, and they *do* find substantial predictability and excess profitability. **Where the sources conflict, my judgement:** Hsu et al. is the more rigorous multiple-testing treatment and is credible, but (i) it is daily data, (ii) its strongest results are in emerging-market currencies where spreads are wide and capital controls bind, and (iii) surviving a stepwise SPA test tells you a rule beat a null of no predictability — it does not tell you a *retail* trader nets anything after 1.3 bps round trip plus swap markup. For the developed-market majors you actually trade, the Neely/Weller decay result is the one I would plan against.

**Intraday FX technical trading — specifically tested, specifically negative.**
Neely & Weller, *Intraday Technical Trading in the Foreign Exchange Market* (FRB St. Louis WP 1999-016; Journal of International Money and Finance 22(2), 2003, 223–237; [SSRN](https://www.ssrn.com/abstract=189495), **(a)**). They used genetic programming *and* an optimised linear forecasting model on intraday FX. The finding: *"When realistic transaction costs and trading hours are taken into account, we find no evidence of excess returns to the trading rules derived with either methodology."* They did find "remarkably stable patterns in the data" — which is precisely the trap: the patterns are real and the money is not.
**This paper is the closest published analogue to what ACIS is attempting, it used an evolutionary search like yours, and its answer was no.** That should weigh heavily.

**Intraday session / flow effects — real, small, structurally-motivated, and the most promising intraday family.**
- Breedon & Ranaldo, *Intraday Patterns in FX Returns and Order Flow* (Journal of Money, Credit and Banking 45(5), 2013, 953–965; [SNB WP PDF](https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf), **(a)**): currencies **depreciate during their own local trading hours** and show no pattern during foreign hours, matching order flow. Consistent across currencies and time zones, driven by participants being net buyers of foreign exchange in their own hours.
- Melvin & Prins, *Equity hedging and exchange rates at the London 4 p.m. fix* (Journal of Empirical Finance 2015; [ECB workshop PDF](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_Workshop_MELVIN_PRINS_Equity%20hedging%20and%20exchange%20rates%20Nov%202013.pdf), **(a)**): month-end equity performance predicts currency moves into the final London fix of the month, with partial reversal — an inelastic, calendar-known flow. Note the FCA and NBER have both studied post-scandal reform of the fix ([FCA Occasional Paper 46](https://www.fca.org.uk/publication/occasional-papers/occasional-paper-46.pdf), **(b)**; [NBER w23327](https://www.nber.org/system/files/working_papers/w23327/w23327.pdf), **(a)**), so the effect's current magnitude is an open question.
- Mueller, Tahbaz-Salehi & Vedolin, *Exchange Rates and Monetary Policy Uncertainty* (Journal of Finance 72(3), 2017, 1213–1252; [Kellogg PDF](https://www.kellogg.northwestern.edu/faculty/alirezat/FXAnnouncements.pdf), **(a)**): short-USD/long-other earns significantly larger excess returns **on scheduled FOMC announcement days**, larger for higher rate differentials and rising with policy uncertainty. A calendar-conditioned, multi-hour-to-one-day holding period edge — exactly the shape your architecture *could* express.

**Order flow — the single strongest documented FX predictor, and you cannot access it.**
Evans & Lyons (Journal of Political Economy 110(1), 2002; [NBER w7317](https://www.nber.org/system/files/working_papers/w7317/w7317.pdf), **(a)**): order flow explains >50% of daily DM/$ changes and >30% of Yen/$, versus R² rarely above 10% for macro models. **This is worth stating plainly: the thing that actually predicts exchange rates at your horizons is order flow, and you have explicitly excluded order-book/volume data.** Any intraday FX edge you find without it is either (i) a flow proxy you have reconstructed from price, (ii) a calendar/session effect, or (iii) overfitting. It is worth deciding consciously which of those you are pursuing.

**And the baseline nobody gets to ignore:** Meese & Rogoff (Journal of International Economics 14, 1983, 3–24, **(a)**) — a random walk matched or beat every structural exchange-rate model at 1–12 month horizons *even when fed the realised future values of the explanatory variables.* Forty-three years and thousands of papers later this has been softened but not overturned at short horizons.

### 4.2 The retail base rate

- ESMA's national-authority analyses across EU jurisdictions found **74–89% of retail CFD accounts lose money**, with average losses per client of €1,600–€29,000 ([ESMA product intervention press release](https://www.esma.europa.eu/sites/default/files/library/esma71-98-128_press_release_product_intervention.pdf), **(b)** — regulator).
- Chague, De-Losso & Giovannetti, *Day Trading for a Living?* ([SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101), **(a)**): of 19,646 Brazilians who began day-trading index futures 2013–2015, **97% of those who persisted more than 300 days lost money**; 1.1% earned more than minimum wage.
- Barber, Lee, Liu & Odean on the entire Taiwan Stock Exchange 1992–2006: ~19% of heavy day traders positive in a given year, <1% consistently profitable (**(a)**).

These do not prove a systematic engine cannot work. They do establish the prior, and the prior is brutal.

### 4.3 Verdict on your §14 targets

| Target | Verdict | Reasoning |
|---|---|---|
| **Annual Sharpe > 1.5 OOS** | **Fantasy** at 2–9 FX instruments, retail cost | FX-only trend walk-forward: 0.43 (**(c)**). SG Trend Index: 0.42 (**(b)**). Century of trend: ~0.4/decade (**(b)**). Post-GFC carry: 0.25 (**(a)**). Cross-sectional FX momentum 0.95 gross, "fairly sensitive" to costs, needs 48 currencies (**(a)**). Nothing in the literature supports 1.5 net on a handful of majors. **Realistic band: 0.3–0.7.** |
| **Max DD < 15%** | **Plausible**, but it is a volatility-target statement, not a skill statement | Achievable by scaling exposure down. At Sharpe 0.5 it implies ~8–10% annualised vol and ~4–5% annual return. Expected maximum drawdown scaling for Brownian motion with drift is in Magdon-Ismail & Atiya, *On the maximum drawdown of a Brownian motion* (J. Applied Probability 41, 2004; [RPI PDF](https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_journal.pdf), **(a)**) — use it to set the target coherently rather than by intuition. |
| **Win rate > 48%** | **Should be deleted** | Win rate is a free parameter of the exit geometry, not a quality measure. §0.2 shows d=3 bps gives a 68.7% theoretical win rate with zero expectancy. Specifying a win-rate floor biases the optimiser toward tight-TP/wide-SL designs — negative skew, blow-up geometry — which is the opposite of what trend capture needs. |
| **PF > 1.4** | **Inconsistent with Sharpe > 1.5 except at ≈125 trades/year** | PF 1.4 implies a per-trade mean/sd ratio of 0.134; annual Sharpe = 0.134·√N. N=125 → 1.5. N=260 → 2.2. **N=900 (your realised) → 4.0.** N=46,800 → 29 **[derived here]**. The target pair silently encodes a holding period you never declared. |
| **Positive months > 70%** | **Inconsistent — it is stricter than the Sharpe target** | 70% positive months ⇒ annual Sharpe 1.82. Sharpe 1.5 ⇒ 66.7% positive months **[derived here]**. As written, positive-months is the binding constraint and it is harder than the headline target. |
| **S&P500 correlation < 0.25** | **Free** | FX trend and carry are naturally low-beta to equities; carry has some crisis co-movement but nowhere near 0.25 on a full-sample basis. This target will pass without effort and therefore tells you nothing. |
| **Avg duration 30 min – 48 h** | **Only the top ~10% of the band is viable** | §0.1. At 1 bp, the cost budget is met at h ≈ 69 h. |

---

## §5. Regime switching

### 5.1 What the literature concludes

**The negative result is specific, old, and directly about exchange rates.** Daccò & Satchell, *Why do regime-switching models forecast so badly?* (Journal of Forecasting 18(1), 1999, 1–16, **(a)**): non-linear models fit exchange rates well in sample and are routinely beaten by a random walk out of sample; for regime-switching specifically, *forecasts based on the true model can have higher MSE than a random walk*, because it takes only a small misclassification rate in forecasting the next regime to lose all the advantage of knowing the correct specification. **This is not a criticism of bad regime models. It is a proof that even a correct one fails if classification is noisy.** Your 12-regime threshold classifier on 1-minute bars is much noisier than the estimated two-state Markov models they were criticising.

**The survey position is "good description, weak prediction."** Ang & Timmermann, *Regime Changes and Financial Markets* (Annual Review of Financial Economics 4, 2012; [NBER w17182](https://www.nber.org/system/files/working_papers/w17182/w17182.pdf), **(a)**): regime-switching models successfully capture fat tails, heteroskedasticity, skewness and time-varying correlation, and the estimated regimes often correspond to real policy/regulatory eras. That is a *descriptive* success. On the predictive side they note the same instrument-decay problem that afflicts all predictability research.

**Where regime detection does earn its keep, it is for risk management, not signal gating.** The positive practitioner results — e.g. HMM and statistical-jump-model regime signals improving *downside risk reduction* and drawdown control ([*Downside Risk Reduction Using Regime-Switching Signals: A Statistical Jump Model Approach*, arXiv:2402.05272](https://arxiv.org/html/2402.05272v2), **(a)**) — are about turning exposure down in bad states, which is closer to volatility targeting than to strategy selection. And even there, the authors are explicit that "identified regimes show some latency at the beginnings and endings of market crashes" and that the model "does not incorporate transaction costs, slippage, or liquidity constraints, meaning that real-world performance may be lower."

Note the related finding that volatility targeting — the simplest regime-like overlay — **improves Sharpe for equities and credit but has negligible Sharpe impact for bonds, currencies and commodities** (Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert, *The Impact of Volatility Targeting*, JPM 45(1), 2018; [SSRN 3175538](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538), **(a)**). It does reduce extreme-return likelihood across all asset classes. **For an FX book, expect vol targeting to buy you tail control, not Sharpe.**

### 5.2 The failure modes, mapped to your design

| Failure mode | How it manifests in ACIS |
|---|---|
| **Misclassification destroys the edge** (Daccò & Satchell) | 12 states on 1-min bars from noisy indicators. A single misclassified bar flips which modules may fire. |
| **Latency at transitions** | Your regime is a lagging function of ATR/ADX/Bollinger/Hurst windows. By the time BREAKOUT_IMMINENT fires, the breakout has happened. |
| **Whipsaw at boundaries** | Threshold rules with no hysteresis oscillate at the boundary, which turns into gating churn and therefore trade churn. Jump-model literature's "jump penalty" exists precisely to moderate transition frequency. |
| **Sample fragmentation** | 12 regimes × 11 genes on regime-labelled bars. See §6.3 — this is the more serious problem. |
| **Estimator bias** | Hurst via R/S is systematically biased high in finite samples (+0.05 to +0.16 versus alternative estimators by some comparisons); the Anis–Lloyd correction addresses the asymptote, not short-window noise. Structural breaks, fat tails and volatility clustering all bias H. Lo's modified R/S test and surrogate-data significance testing are the standard remedies ([Macrosynergy, *Detecting trends and mean reversion with the Hurst exponent*](https://macrosynergy.com/research/detecting-trends-and-mean-reversion-with-the-hurst-exponent/), **(b)**; [Hamed, *Improved finite-sample Hurst exponent estimates*, WRR 2007](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2006WR005111), **(a)**). |

### 5.3 Recommendations for Q5

| # | Change | Type |
|---|---|---|
| 5.1 | **Run the regime engine's own falsification test.** On your synthetic markets you know the ground truth (episode / no episode). Measure classification precision and recall for STRONG_TREND_* against the planted episodes. If precision is not far above the base rate, the regime engine is decoration. **This is a one-day experiment and it should be the next thing you run.** | implementation (experiment) |
| 5.2 | **Collapse 12 regimes to 2–3.** The evidence supports "risk-on/risk-off"-scale distinctions for exposure scaling, not 12-way strategy selection. Every regime you delete returns sample to the remaining ones quadratically in effect. | **spec-level** (SPEC §2/§4) |
| 5.3 | **Demote regime from a gate to a weight.** Instead of "regime R permits modules {A,B}", let regime shift the *forecast weights* continuously. A misclassification then costs you a suboptimal weight, not a completely different strategy — which is exactly the robustness Daccò & Satchell say you need. | **spec-level** |
| 5.4 | **Add hysteresis / minimum dwell time** to regime transitions (the jump-penalty idea). Cheap, and directly attacks whipsaw. | implementation fix |
| 5.5 | **Hold Hurst to a significance test** (Lo's modified R/S or surrogate-data bootstrap) before it is allowed to move a classification, or drop it. An H estimate on a short 1-minute window is not evidence. | **spec-level** if it changes the classifier definition |

---

## §6. Parameter optimisation methodology

### 6.1 The state of evidence: evolutionary search on financial data

**The two canonical GA-on-trading-rules papers reached opposite-looking conclusions that actually agree.**
- Allen & Karjalainen, *Using genetic algorithms to find technical trading rules* (JFE 51, 1999; [PDF](https://www.cs.montana.edu/courses/spring2007/536/materials/Lopez/genetic.pdf), **(a)**): GA-evolved rules on the S&P beat buy-and-hold after costs in 1970–89 — but on other periods since 1929 they identified high returns and low volatility **without** producing excess returns after costs, and there was **no evidence of risk-adjusted outperformance**; out-of-sample performance varied year to year, so GP "could not consistently find outperforming technical trading rules."
- Neely & Weller on intraday FX (see §4.1, **(a)**): GP *and* optimised linear forecasting, and **no excess returns once realistic transaction costs and trading hours are imposed.**

The agreement is: **evolutionary search reliably finds in-sample structure and unreliably finds out-of-sample money, and costs are usually what kills it.**

**On QIEA specifically.** Han & Kim's original contribution (IEEE TEC 6(6), 2002, 580–593, **(a)**) is a genuine advance *in combinatorial optimisation* — better convergence with small populations, no premature convergence versus conventional GA. The finance applications of QIEA are a thin literature, largely in-sample, largely low-tier venue, and I found **no credible out-of-sample, cost-inclusive, multiple-testing-corrected evidence that a quantum-inspired search produces better trading strategies than a coarse grid.** Claims of "up to 73.4% performance improvement" in portfolio optimisation papers are improvements in *solving the optimisation problem*, not in *out-of-sample returns* — a distinction those papers do not always make. **Grade the QIEA-in-finance literature (c).**

**And here is the deeper point, which is the most important thing in this section:** for a noisy objective, a *more powerful* optimiser is strictly *worse*. Bailey, Borwein, López de Prado & Zhu prove that under CSCV the probability of backtest overfitting **approaches 1 as the number of configurations tried grows, regardless of whether any configuration has genuine predictive power**, and that the expected out-of-sample rank of the best in-sample configuration declines sharply with the number of configurations ([*The Probability of Backtest Overfitting*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253); [Bailey's PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), **(a)**; [*Pseudo-Mathematics and Financial Charlatanism*, Notices of the AMS 61(5), 2014](https://www.ams.org/notices/201405/rnoti-p458.pdf), **(a)**). **Upgrading QIEA to Bayesian optimisation would make your problem worse, not better.** The right direction is *less* search, not better search.

Bergstra & Bengio's random-search result (JMLR 13, 2012, 281–305; [JMLR](https://jmlr.org/papers/v13/bergstra12a.html), **(a)**) is worth knowing — random beats grid at equal budget because effective dimensionality is usually lower than nominal — but it is an ML-hyperparameter result on clean objectives and does not transfer to a financial objective whose signal-to-noise is near zero.

### 6.2 The overfitting controls that actually work, ranked

1. **Not searching.** Literature-default parameters, or a spread of parameters chosen by design. Carver: treat parameter selection as a diversification problem, not an optimisation problem (**(b)**). This is the only control with zero failure mode.
2. **Pooling across instruments.** Carver's 214-instrument experiment: asset-class pooling won in 2 of 4 window configurations and was runner-up in the other 2; all-pooled won one; unpooled won only in the 10y-in/1y-out cell (0.664 vs 0.635, within noise). His conclusion is to **blend** unpooled, all-pooled and asset-class-pooled ([qoppac 2026-07](https://qoppac.blogspot.com/2026/07/jumping-back-in-pooling-testing-pooling.html), **(b)**). Applied to you: fit one parameter set across EUR/USD, USD/JPY and the other six, not per-instrument and certainly not per-instrument-per-regime.
3. **Parameter-plateau selection rather than peak selection.** Choose the centre of a broad region of acceptable performance rather than the argmax. The EPAT walk-forward study used "neighbourhood stability scoring on training data only" and noted the honest trade-off: *"parameter stability approach may be overly conservative; peak-Sharpe fitting would likely yield higher but less robust results"* (**(c)**). That is the trade you want to be on the conservative side of.
4. **PBO via CSCV.** Model-free, non-parametric, gives you an actual probability. You should be computing this alongside DSR (**(a)**).
5. **Deflated Sharpe Ratio.** You already gate on it. **Three caveats you must respect:** (i) DSR requires the *true* number of trials N and the variance of trial Sharpes — and "N and the trial variance are rarely recorded precisely"; if your trial register does not include every discarded configuration, every abandoned gene range, and every exploratory run, your DSR is inflated. (ii) It assumes a returns distribution. (iii) **A high DSR says nothing about future regime change.** Best practice when the trial record is incomplete is to bound the answer across plausible N and check the conclusion is stable ([Bailey & López de Prado, *The Deflated Sharpe Ratio*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551), **(a)**; [Wikipedia summary of limitations](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio), **(c)**).
6. **Haircutting for multiple tests.** Harvey & Liu, *Evaluating Trading Strategies* (JPM 40(5), 2014; [SSRN 2474755](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2474755), **(a)**) give a principled alternative to the practitioner habit of arbitrarily halving Sharpe.
7. **Minimum track record length / minimum backtest length.** Bailey & López de Prado's MinTRL tells you how long a record must be to reject "true Sharpe ≤ 0" at a confidence level, and MBL tells you how long a backtest must be given the number of trials to avoid selecting a zero-expected-OOS-Sharpe strategy (**(a)**). **Compute your MBL against your actual trial count. I suspect 14 years is not enough for the number of configurations QIEA has evaluated.**
8. **Walk-forward.** Necessary, not sufficient. Pardo's own framing is that WFO simulates the process (**(b)**); Bailey & López de Prado's counterpoint is that a walk-forward backtest is still *a single historical path*, so overfitting remains possible (**(a)**). Your embargo and locked holdout are correct and should stay.
9. **Cross-instrument validation.** Fit on EUR/USD + USD/JPY, test on GBP/USD + AUD/USD. This is the cheapest genuinely-out-of-sample test you have available and you are not using it.

### 6.3 Is per-regime parameter evolution defensible?

**No, not at 12 regimes with 11 genes.** The argument is arithmetic:

- 12 regimes × 11 genes = 132 free parameters per instrument, before you count the regime classifier's own thresholds.
- Regime-labelled bars are not independent observations — bars within a regime episode are highly autocorrelated. Your *effective* sample in the rare regimes (MACRO_EVENT, ILLIQUID, BREAKOUT_IMMINENT) is a small number of *episodes*, not a large number of bars.
- The relevant statistic is trades, not bars: your own §14 gate has a ≥30-trade floor, and a per-regime fit needs that floor **per regime**, per fold.
- And the multiple-testing cost is multiplicative: PBO grows with the total number of configurations evaluated across all regimes, not per regime.

**The defensible middle ground:** keep the regime engine as a *weighting* input (§5.3), fit **one** parameter set pooled across regimes and across instruments, and let the regime shift forecast weights rather than parameter values. That preserves the intuition ("trend rules should count for more in trending markets") while keeping the estimated-parameter count in the single digits.

### 6.4 Recommendations for Q6

| # | Change | Type |
|---|---|---|
| 6.1 | **Cut the searched parameter count hard.** Target ≤4 fitted parameters total, pooled across instruments and regimes. Everything else fixed by design at literature defaults or ensembled across a fixed spread of values. | **spec-level** (SPEC §5, ParamSet definition) |
| 6.2 | **Replace per-regime evolution with pooled evolution + regime weighting.** | **spec-level** |
| 6.3 | **Add PBO (CSCV) alongside DSR** in the honesty gate. DSR alone is a point estimate that depends on a trial count you may not have recorded completely. | implementation fix (new metric) + **spec-level** if it becomes a gate |
| 6.4 | **Audit the trial register.** Does it contain every configuration ever evaluated, including abandoned gene ranges and exploratory runs? If not, your DSR ≥ 0.95 gate is not measuring what it claims. Bound DSR across plausible N. | implementation fix (and a ledger-discipline matter) |
| 6.5 | **Compute Minimum Backtest Length** for your actual trial count and compare to 14 years. Report the answer even if it is uncomfortable. | implementation fix |
| 6.6 | **Add cross-instrument holdout**: two pairs never used in any fitting, reserved as a final falsification set. | **spec-level** (SPEC §14 validation protocol) |
| 6.7 | **Do not upgrade the optimiser.** QIEA vs Bayesian vs grid is not your problem, and a stronger optimiser strictly increases PBO. If you touch it at all, reduce its budget. | decision, no code |

---

## §7. What I would build instead

Constraints assumed: deterministic Python, no numpy/pandas in the engine, 1-min bars available from 14 years of validated tick data, 8 FX instruments + gold, retail costs, ~16-core box, no order book.

### Rank 1 — Low-turnover, multi-instrument, continuous-forecast trend + carry on daily (or 4-hour) decision bars

**What it is.** One decision per instrument per day. Each instrument gets a combined forecast from a small ensemble of trend speeds (e.g. EWMAC 16/64, 32/128, 64/256) plus a carry forecast (interest-rate differential ÷ volatility). Forecasts are capped, volatility-scaled to a target risk, combined with fixed diversification weights, buffered, and traded as a target position. No stops — the forecast reversing *is* the exit. Vol-targeted at the portfolio level with correlation/cluster caps (which your Governor already implements).

**Evidence.** Trend: MOP 2012 (**(a)**, contested by Huang et al. 2020 (**(a)**)), Hurst-Ooi-Pedersen century evidence ~0.4/decade (**(b)**), SG Trend ~0.42 (**(b)**), FX-only walk-forward 0.43 (**(c)**). Carry: HML-FX ~0.76 full sample, ~0.25 post-GFC (**(a)**). Combination: value-and-momentum-everywhere style diversification across the two is the standard construction (Asness, Moskowitz & Pedersen, JF 68(3), 2013, **(a)**). Position buffering: Novy-Marx & Velikov's buy/hold spread, −41% turnover, −42% costs (**(a)**). Speed ensembling and the 0.13 SR cost budget: Carver (**(b)**).

**Expected outcome, honestly:** net Sharpe **0.3–0.6** on 9 instruments, max drawdown 10–20% at a 10% vol target, several consecutive losing years possible. It will not hit §14 as written.

**What you must change:**
- Decision clock to daily/4-hour (**spec-level**).
- Exits: forecast-reversal + buffer, remove ATR barriers as the primary exit (**spec-level**).
- ParamSet reduced to a handful of pooled parameters (**spec-level**).
- Onboard all 8 instruments + gold — **diversification is the only free lunch here and you are currently running 2 instruments, which caps your achievable Sharpe at roughly 1/√4.5 of what the full universe supports** (implementation, plus data onboarding).
- Carry forecast requires broker swap modelling, not central-bank rates (**spec-level**, and it is a correctness issue — see §8).

**What you keep:** the Governor (correlation caps, vol targeting, drawdown tapers), the Risk Monitor, the MCP plane, the walk-forward/DSR harness, the tick data. Most of your build survives. It is the AGON/QIEA/NVMA middle that changes.

### Rank 2 — Calendar- and session-conditioned event strategies with a designed holding window

**What it is.** A small number of rules that fire on a *known schedule* and hold for a *designed window*, so the horizon problem is solved by construction:
- **Local-hours flow:** currencies depreciate in their own trading hours (Breedon & Ranaldo, JMCB 2013, **(a)**). Expressible as session-boundary positions.
- **Month-end London 4pm fix:** equity performance over the month predicts currency direction into the final fix, with partial reversal (Melvin & Prins, JEF 2015, **(a)**). ~12 trades/year, hours of holding.
- **FOMC-day dollar:** short-USD carries a significant premium on scheduled FOMC days, larger with rate differentials and policy uncertainty (Mueller, Tahbaz-Salehi & Vedolin, JF 2017, **(a)**). ~8 events/year.
- **Intraday momentum (first-period-to-last-period):** documented in FX-adjacent markets; Elaut, Frömmel & Lampaert find intraday momentum in RUB/USD is consistent with liquidity providers' overnight risk-aversion rather than informed trading ([J. Financial Markets 37, 2018](https://www.sciencedirect.com/science/article/abs/pii/S1386418116300313), **(a)**) — which is a *mechanism*, which is what López de Prado means by "theory first."

**Why it suits you.** Turnover is tiny (tens of trades/year → cost drag well under 0.1 SR units). Holding windows are defined by the calendar, not by a stop. Each rule has a stated economic mechanism, so it is falsifiable. It uses your 1-minute data for what 1-minute data is actually good for: precise entry/exit timing inside a decided window, rather than the decision itself.

**Risks.** Each effect is small and several have been studied to death (the fix has been reformed post-scandal — [FCA OP46](https://www.fca.org.uk/publication/occasional-papers/occasional-paper-46.pdf), **(b)**). Spread widening at the fix and around FOMC is material and must be modelled (see §8.5). Expect a handful of trades per month and wide confidence intervals for years.

**What you must change:** you need the historical event calendar (currently missing), and you need time-varying spreads.

### Rank 3 — Do less: run the low-turnover program at low risk and treat the rest as research

Honest option. Run Rank 1 at a 5% volatility target with a hard equity floor, accept a Sharpe around 0.4, and keep the ACIS infrastructure (which is genuinely good) as a research and risk-control platform. The expected value of this is positive and its variance is small; the expected value of continuing to chase Sharpe 1.5 intraday is, on the evidence in §4, negative.

### What NOT to waste time on

1. **A better optimiser.** QIEA → Bayesian → CMA-ES → anything. PBO rises with search power (**(a)**). This is the clearest "do not" in the report.
2. **Per-regime × per-instrument parameter fitting.** §6.3.
3. **1-minute bars as the decision clock.** §0.1.
4. **Hurst on short windows as a classification input**, unless you add a significance test (**(a)/(b)**).
5. **The EUR/USD vs USD/JPY "pair divergence" module.** This is a mathematical error, not just a weak strategy: `EURUSD × USDJPY = EURJPY` exactly (your own data validation checks triangular consistency, so you have already proved this holds in your data). A "spread" between log EURUSD and log USDJPY with β = −1 *is* log EUR/JPY — a directly tradeable cross. With β = +1 it is a dollar-index-like combination. Either way there is no stationary residual, there is no economic reason for two floating exchange rates to be cointegrated (Meese & Rogoff, **(a)**), and you are paying **two** spreads to trade what one instrument gives you for one. Cointegration relationships in currency pairs are also documented as unstable across periods (**(c)**). **Delete the module or replace it with a straight EUR/JPY instrument.**
6. **Chasing the §14 targets as written.** Fix the targets (§4.3) before spending another compute-year trying to hit numbers that are internally inconsistent.
7. **Any intraday strategy that does not have an explicit flow or calendar mechanism.** Without order-book data you are structurally disadvantaged at intraday horizons (Evans & Lyons, **(a)**), and the one paper that tested evolutionary search on intraday FX with realistic costs found nothing (Neely & Weller, **(a)**).
8. **More instruments beyond ~10–15 for FX.** Diversification benefit saturates; the currencies are highly correlated through the dollar factor. Adding non-FX assets (which you already have in scope per SPEC §3.7 — indices, energies, futures) would buy far more diversification than adding a ninth currency pair.

---

## §8. Anti-patterns and failure modes, including ones you are already committing

### 8.1 Your own list, graded

| Your stated weakness | My grade | Note |
|---|---|---|
| Three unoptimised genes | **Severe** | Worse than "unoptimised" — they are unconstrained. Three modules are trading on random parameters. Disable the modules or give them their own fitness. |
| No holding policy | **Critical** | §2. This and barrier width are the two binding problems. |
| Per-tick signal spam | **Severe** | 706:1 signal-to-trade ratio; dedup has become the strategy. |
| ATR exits truncating trends | **Critical** | §0.2. This alone explains the falsification result. |
| Regime fragmentation | **Severe** | §5, §6.3. |
| 1-minute base with multi-hour intent | **Critical** | §0.1. This is the root cause of which the others are symptoms. |
| No historical event calendar | **Severe** | §8.4. |
| Financing from central-bank rates, not broker swaps | **Moderate but systematically biased** | §8.3. It does not add noise; it adds *optimistic bias*, which is the dangerous kind. |

### 8.2 Anti-patterns you have not listed

**(i) The falsification harness may not be volatility-calibrated.** §0.1: your reported Sharpes are ~9× better than the cost arithmetic predicts. Resolve this before drawing any further conclusion from the harness. A harness whose synthetic markets are 8× more volatile than the real one cannot test cost sensitivity, which is your dominant failure mode.

**(ii) Constant cost assumption.** You model ~0.8–1.2 bps round trip as a constant. Reality: OANDA's Core Pricing runs ~0.4 pips average spread **plus ~$10 round-turn commission per standard lot**, and $10 per $100k *is* one full pip on EUR/USD — so round-trip cost is ≈1.4 pips ≈ **1.3 bps**, not 0.8–1.2 (**(c)**, broker-review sourced; verify against OANDA's own pricing page and your own account). More importantly the mean is the wrong statistic: spreads widen sharply at the 5pm New York rollover, on Friday close, and around scheduled releases, where tier-1 liquidity providers systematically pull resting orders seconds before the print (**(c)**, but the underlying microstructure is well established — see Mancini, Ranaldo & Wrampelmeyer, *Liquidity in the Foreign Exchange Market*, Journal of Finance 68(5), 2013, **(a)**, which documents substantial FX illiquidity costs and strong commonality using EBS interdealer data). **A system holding 8 minutes will be disproportionately exposed to the widened-spread regimes because that is when price moves and signals fire.** Model spread as a function of time-of-day and event proximity, or you are systematically under-costing exactly the trades that matter.

**(iii) Last look and asymmetric slippage.** Retail FX fills go through aggregators where dealers have a short window to accept or reject, and the acceptance rule may be asymmetric ([BIS Quarterly Review, *FX trade execution: complex and highly fragmented*, Dec 2019](https://www.bis.org/publ/qtrpdf/r_qt1912g.htm), **(b)**). Your symmetric 0.2 bps slippage assumption is optimistic in the direction that matters. Log realised-vs-modelled slippage from the first live fill (your GAP-0001 already anticipates this).

**(iv) Backtest trades through the weekend gap and the rollover.** You have DST-correct session clocks, which is good. Confirm you also suppress or specially cost the 21:00–22:00 UTC rollover window and Friday close.

**(v) The `max_holding_periods` gene is in the wrong unit.** 1–48 *1-minute* periods caps holding at 48 minutes, below the horizon of every edge you are trying to capture. This is a concrete, checkable bug.

**(vi) The win-rate target biases the search toward the wrong geometry.** §4.3.

**(vii) The trial register may be incomplete, which inflates DSR.** §6.2 item 5.

### 8.3 Financing: what to do about it

Central-bank overnight rates are the right *reference* and the wrong *charge*. Retail brokers apply a markup to both the paid and received side. IBKR publishes a tiered benchmark spread (~1.5% over benchmark on the first $100k, falling above $1m) ([IBKR margin rates](https://www.interactivebrokers.com/en/trading/margin-rates.php), **(b)**), which is a credible, documented figure you can model. CFD brokers are typically worse and less transparent (**(c)**).

**Recommendation (spec-level):** model financing as `benchmark_differential ∓ markup`, with markup a config value taken from your intended broker's published swap table, and default it *pessimistically*. Then re-run any carry-sensitive result. If a strategy's edge disappears under a 1.5% two-sided markup, it was never a retail strategy.

### 8.4 The event calendar

You need this before any honest §14 number. Practical sourcing:

- **Release dates:** FRED/ALFRED vintage-date endpoints give you the exact dates on which each series was released or revised, free and via API ([FRED `series/vintagedates`](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html), **(b)** — Federal Reserve Bank of St. Louis). `realtime_start` / `realtime_end` give point-in-time correctness, which also protects you from look-ahead on any macro input.
- **Release *times*:** ALFRED gives dates, not clock times. Times are conventional and stable: US BLS/BEA releases at 08:30 ET, FOMC statements at 14:00 ET, ECB decisions at 13:45 CET with the press conference at 14:15 CET. Reconstruct from the official release-schedule archives rather than a vendor.
- **Avoid vendor scrapers of ForexFactory-style calendars** for anything load-bearing: no provenance, no revision history, and you cannot audit them (**(c)**).

**Minimum viable version:** a list of (timestamp_utc, importance) for NFP, CPI, FOMC, ECB, BoE, BoJ over 2012–2025. That is a few thousand rows and it unlocks both event avoidance and the FOMC-day strategy in §7 Rank 2.

### 8.5 Do you avoid news, or trade it?

Both are defensible; doing neither is not. Andersen, Bollerslev, Diebold & Vega (*Micro Effects of Macro Announcements*, American Economic Review 93(1), 2003, 38–62; [Duke PDF](https://public.econ.duke.edu/~boller/Published_Papers/aer_03.pdf), **(a)**) establish that announcement surprises produce **conditional mean jumps** in FX, with asymmetric response (bad news moves more than good news). For a system with stops, a jump is not a price move — it is a gap through your stop with slippage you did not model. **For Rank 1 (low-turnover, no stops) news avoidance matters little; for anything with barriers it is essential.**

### 8.6 On the replay-speed blocker (GAP-P12D-12)

Not a research question, but it interacts with §1.1: the reason it is tempting to optimise a cheap proxy is that the real engine is slow. Two observations from outside:

- Your measured ~26 ticks/s is roughly 3–4 orders of magnitude below what pure-Python event loops typically achieve for simple state updates; the bottleneck is almost certainly per-tick object construction (frozen dataclasses with validation on every tick) and per-tick JSONL logging at ~583 B/tick. **Both are policy choices, not physics.** Aggregating to 1-minute bars *before* the engine (which §7 Rank 1 wants anyway) reduces tick count by ~2 orders of magnitude at a stroke.
- Sampling the log (log every Nth event, plus all state transitions) is the standard fix for log-volume-bound replays and costs you nothing you actually read.

Moving the decision clock to daily bars makes this blocker mostly disappear: 14 years × 9 instruments × 1 bar/day ≈ 33,000 decisions, which runs in seconds.

---

## Ranked action list

Ordered by (expected value ÷ effort). **[S] = spec-level change requiring owner ratification. [I] = implementation fix.**

| # | Action | Type | Why it is here |
|---|---|---|---|
| **1** | **Widen the exit barriers by ~10×** (or express them in instrument-volatility units, X ∈ [0.2, 1.0] × σ_ann). Re-run the falsification suite with nothing else changed. | **[S]** | §0.2: turns +0.12 bp/trade into +7.65 bp/trade on the same signal. Single highest-EV change available. One parameter. |
| **2** | **Reconcile the falsification harness's volatility with real EUR/USD.** Report the ratio of synthetic to real 1-minute sd. | **[I]** | §0.1: your Sharpes are 9× better than cost arithmetic allows. If the harness is mis-calibrated, every conclusion from it is suspect. |
| **3** | **Fix `max_holding_periods` units** so the vertical barrier can express 30 min – 48 h. | **[I]**/**[S]** | Concrete bug; the gene currently caps holding at 48 minutes. |
| **4** | **Disable the breakout, mean-reversion and momentum-scalp modules** until each has fitness over its own realised trades. | **[I]** (module list is **[S]**) | Three genes selected by nothing. Lean-build law applies. |
| **5** | **Delete the EUR/USD × USD/JPY pair-divergence module** (or replace with a EUR/JPY instrument). | **[S]** | Mathematical error: the "spread" is EUR/JPY, traded at double the spread. |
| **6** | **Move the decision clock from ticks to bars, and the bar from 1 min to ≥4 h (preferably daily).** | **[S]** | §0.1. The root cause. Also largely dissolves GAP-P12D-12. |
| **7** | **Replace event entries with a target-position map + buffer.** Forecast → volatility-scaled desired position → trade only outside a no-trade band. | **[S]** | §2. −41% turnover, −42% costs in the best-evidenced study of cost mitigation. |
| **8** | **Un-pin the marginal-alpha sizing input.** | **[I]** | Binary sizing pays double at every reversal. |
| **9** | **Make fitness the deployed execution path**, with a parity assertion test. | **[S]** | §1. Until this holds, optimisation is measuring something you do not trade. |
| **10** | **Rewrite the §14 targets.** Sharpe 0.5 (stretch 0.8), drop the win-rate floor, make PF and positive-months consistent with the Sharpe target and the declared trade count, state the target holding period explicitly. | **[S]** | §4.3. Three demonstrable internal inconsistencies. |
| **11** | **Onboard the remaining 6 instruments + gold.** | **[I]** | Diversification is the only free lunch; two correlated majors caps achievable Sharpe. |
| **12** | **Collapse 12 regimes to ≤3 and demote regime from gate to weight.** | **[S]** | §5. Daccò & Satchell: misclassification destroys even a correct regime model. |
| **13** | **Pool parameters across instruments and regimes; cut fitted parameter count to ≤4.** | **[S]** | §6. Carver's pooling evidence; PBO arithmetic. |
| **14** | **Run the regime-classifier falsification experiment** (precision/recall of STRONG_TREND_* against planted episodes). | **[I]** | One day of work; may retire the whole NVMA layer. |
| **15** | **Build the event calendar** from ALFRED vintage dates + official release-time schedules. | **[I]** | Blocks honest §14 numbers and unlocks Rank-2 strategies. |
| **16** | **Model spread as time-of-day and event dependent**, and financing with a broker markup. | **[S]** | Both biases are one-directional and flattering. |
| **17** | **Add PBO/CSCV beside DSR; audit the trial register; compute Minimum Backtest Length.** | **[I]** (gate change is **[S]**) | §6.2. Your DSR gate may be measuring an incomplete N. |
| **18** | **Add a cross-instrument holdout** (two pairs never used in fitting). | **[S]** | Cheapest genuinely-out-of-sample test you are not using. |
| **19** | **Report mean holding period and cost-drag-in-Sharpe-units in every fold**, with hard alarms. | **[I]** | You lost a falsification run to an unwatched number. |
| **20** | **Do not upgrade the optimiser.** | decision | PBO → 1 with search power. |

Actions 1–5 are independent of everything else, cost days not weeks, and are worth running before any further compute is spent. Action 6 is the one that decides what ACIS is.

---

## Where sources conflict, and my judgement

1. **Is time-series momentum real?** MOP 2012 says yes (Sharpe 1.1); Huang, Li, Wang & Zhou 2020 says the asset-by-asset evidence is weak, the pooled t-stat fails bootstraps, and a no-predictability sample-mean strategy does just as well. **My judgement:** trend-following *as an implementable strategy* is real but much weaker than MOP suggested — the 0.4/decade century figure and the 0.42 SG Trend Index figure are the numbers to plan against, not 1.1. The critique mostly demolishes the *statistical predictability* claim, not the *strategy performs* claim; but a strategy that performs no better than a no-predictability benchmark is not a reason to build a regime engine.

2. **Is technical trading still profitable in FX?** Neely/Weller/Ulrich say the simple rules died by the early 1990s; Hsu/Taylor/Wang say substantial predictability survives across 30 currencies and 21,000 rules with stepwise SPA correction. **My judgement:** both are right about different things. Hsu et al.'s results concentrate in emerging currencies with wide spreads and lean on a very large rule universe; Neely et al.'s decay finding is specifically about the majors, which is your universe. Plan against decay. And note that Hsu et al. is *daily*, which supports Rank 1 and says nothing in favour of your current intraday design.

3. **Do stops help or hurt?** Kaminski & Lo: hurt under random walk, help under momentum. Han/Zhou/Zhu: a 10% monthly stop doubles momentum Sharpe. Lei & Li: neutral on return, positive on risk. Carver: don't use them, use a continuous forecast. **My judgement:** these agree once you control for scale. A stop at the scale of the signal's own horizon is a momentum rule and helps; a stop far tighter than the signal horizon is a random-walk stop and hurts. Yours is ~25× tighter than the tightest width in Carver's published table. That is the whole disagreement resolved.

4. **Does regime switching help?** Practitioner papers report improved risk-adjusted returns; Daccò & Satchell prove even a correct model fails under small misclassification; Ang & Timmermann call it descriptively strong and predictively weak. **My judgement:** regime models earn their keep for *exposure scaling and drawdown control*, not for *strategy selection*. Use it as a weight, never as a gate.

---

## Source register

**(a) Peer-reviewed / academic**

- Allen, F. & Karjalainen, R. (1999). *Using genetic algorithms to find technical trading rules.* Journal of Financial Economics 51(2), 245–271. https://www.cs.montana.edu/courses/spring2007/536/materials/Lopez/genetic.pdf
- Andersen, T., Bollerslev, T., Diebold, F. & Vega, C. (2003). *Micro Effects of Macro Announcements: Real-Time Price Discovery in Foreign Exchange.* American Economic Review 93(1), 38–62. https://public.econ.duke.edu/~boller/Published_Papers/aer_03.pdf
- Ang, A. & Timmermann, A. (2012). *Regime Changes and Financial Markets.* Annual Review of Financial Economics 4. NBER w17182. https://www.nber.org/system/files/working_papers/w17182/w17182.pdf
- Asness, C., Moskowitz, T. & Pedersen, L. (2013). *Value and Momentum Everywhere.* Journal of Finance 68(3), 929–985. https://www.hillsdaleinv.com/uploads/Value_and_Momentum_Everywhere,_Clifford_S._Asness,_Tobias_J._Moskowitz,_Lasse_Heje_Pedersen.pdf
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2014). *Pseudo-Mathematics and Financial Charlatanism.* Notices of the AMS 61(5), 458–471. https://www.ams.org/notices/201405/rnoti-p458.pdf
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2015). *The Probability of Backtest Overfitting.* Journal of Computational Finance. https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
- Bailey, D. & López de Prado, M. (2012). *The Sharpe Ratio Efficient Frontier.* Journal of Risk 15(2), 3–44. https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf
- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio.* Journal of Portfolio Management 40(5). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Baltas, N. & Kosowski, R. (2013). *Demystifying Time-Series Momentum Strategies.* https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf
- Bergstra, J. & Bengio, Y. (2012). *Random Search for Hyper-Parameter Optimization.* JMLR 13, 281–305. https://jmlr.org/papers/v13/bergstra12a.html
- Breedon, F. & Ranaldo, A. (2013). *Intraday Patterns in FX Returns and Order Flow.* Journal of Money, Credit and Banking 45(5), 953–965. https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf
- Chague, F., De-Losso, R. & Giovannetti, B. (2019). *Day Trading for a Living?* https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101
- Daccò, R. & Satchell, S. (1999). *Why do regime-switching models forecast so badly?* Journal of Forecasting 18(1), 1–16. https://onlinelibrary.wiley.com/doi/abs/10.1002/(SICI)1099-131X(199901)18:1%3C1::AID-FOR685%3E3.0.CO;2-B
- Dai, M. et al. (2021). *Risk reduction using trailing stop-loss rules.* International Review of Finance. https://onlinelibrary.wiley.com/doi/abs/10.1111/irfi.12328
- Elaut, G., Frömmel, M. & Lampaert, K. (2018). *Intraday momentum in FX markets.* Journal of Financial Markets 37, 35–51. https://www.sciencedirect.com/science/article/abs/pii/S1386418116300313
- Evans, M. & Lyons, R. (2002). *Order Flow and Exchange Rate Dynamics.* Journal of Political Economy 110(1), 170–180. NBER w7317. https://www.nber.org/system/files/working_papers/w7317/w7317.pdf
- Gârleanu, N. & Pedersen, L. (2013). *Dynamic Trading with Predictable Returns and Transaction Costs.* Journal of Finance 68(6). https://nbgarleanu.github.io/DynTrad.pdf
- Hamed, K. (2007). *Improved finite-sample Hurst exponent estimates using rescaled range analysis.* Water Resources Research 43. https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2006WR005111
- Han, K.-H. & Kim, J.-H. (2002). *Quantum-inspired evolutionary algorithm for a class of combinatorial optimization.* IEEE Trans. Evolutionary Computation 6(6), 580–593.
- Han, Y., Zhou, G. & Zhu, Y. (2014). *Taming Momentum Crashes: A Simple Stop-Loss Strategy.* https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199
- Harvey, C. & Liu, Y. (2014). *Evaluating Trading Strategies.* Journal of Portfolio Management 40(5), 108–118. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2474755
- Harvey, C., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. & Van Hemert, O. (2018). *The Impact of Volatility Targeting.* Journal of Portfolio Management 45(1), 14–33. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538
- Hsu, P.-H., Taylor, M. & Wang, Z. (2016). *Technical trading: Is it still beating the foreign exchange market?* Journal of International Economics 102, 188–208. https://papers.ssrn.com/abstract=2765673
- Huang, D., Li, J., Wang, L. & Zhou, G. (2020). *Time-series momentum: Is it there?* Journal of Financial Economics 135(3), 774–794. https://ink.library.smu.edu.sg/context/lkcsb_research/article/7520/viewcontent/Time_series_momentum_JFE_sv.pdf
- Kaminski, K. & Lo, A. (2014). *When do stop-loss rules stop losses?* Journal of Financial Markets 18, 234–254. https://dspace.mit.edu/bitstream/handle/1721.1/114876/Lo_When%20Do%20Stop-Loss.pdf
- Lambert, N., Amos, B., Yadan, O. & Calandra, R. (2020). *Objective Mismatch in Model-based Reinforcement Learning.* PMLR 120. http://proceedings.mlr.press/v120/lambert20a.html
- Lei, A. & Li, H. (2009). *The Value of Stop Loss Strategies.* Financial Services Review 18(1), 23–51. https://www.ssrn.com/abstract=1214737
- López de Prado, M. (2018). *The 10 Reasons Most Machine Learning Funds Fail.* Journal of Portfolio Management 44(6), 120–133. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104816
- Lustig, H., Roussanov, N. & Verdelhan, A. (2011). *Common Risk Factors in Currency Markets.* Review of Financial Studies. NBER w14082. https://www.nber.org/system/files/working_papers/w14082/w14082.pdf
- Magdon-Ismail, M. & Atiya, A. (2004). *On the maximum drawdown of a Brownian motion.* Journal of Applied Probability 41(1). https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_journal.pdf
- Mancini, L., Ranaldo, A. & Wrampelmeyer, J. (2013). *Liquidity in the Foreign Exchange Market.* Journal of Finance 68(5), 1805–1841. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1447869
- Manheim, D. & Garrabrant, S. (2018). *Categorizing Variants of Goodhart's Law.* arXiv:1803.04585. https://arxiv.org/abs/1803.04585
- Meese, R. & Rogoff, K. (1983). *Empirical exchange rate models of the seventies: Do they fit out of sample?* Journal of International Economics 14(1), 3–24.
- Melvin, M. & Prins, J. (2015). *Equity hedging and exchange rates at the London 4 p.m. fix.* Journal of Empirical Finance. https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_Workshop_MELVIN_PRINS_Equity%20hedging%20and%20exchange%20rates%20Nov%202013.pdf
- Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, A. (2012). *Currency momentum strategies.* Journal of Financial Economics 106(3), 660–684. https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20(1).pdf
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. (2012). *Time series momentum.* Journal of Financial Economics 104(2), 228–250. https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- Mueller, P., Tahbaz-Salehi, A. & Vedolin, A. (2017). *Exchange Rates and Monetary Policy Uncertainty.* Journal of Finance 72(3), 1213–1252. https://www.kellogg.northwestern.edu/faculty/alirezat/FXAnnouncements.pdf
- Neely, C. & Weller, P. (2003). *Intraday technical trading in the foreign exchange market.* Journal of International Money and Finance 22(2), 223–237. https://www.ssrn.com/abstract=189495
- Neely, C. & Weller, P. (2013). *Lessons from the evolution of foreign exchange trading strategies.* Journal of Banking & Finance 37(10), 3783–3798. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1932844
- Neely, C., Weller, P. & Ulrich, J. (2009). *The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market.* Journal of Financial and Quantitative Analysis 44(2), 467–488. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1403345
- Novy-Marx, R. & Velikov, M. (2016). *A Taxonomy of Anomalies and their Trading Costs.* Review of Financial Studies 29(1). NBER w20721. https://www.nber.org/system/files/working_papers/w20721/w20721.pdf
- Park, C.-H. & Irwin, S. (2007). *What do we know about the profitability of technical analysis?* Journal of Economic Surveys 21(4), 786–826. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-6419.2007.00519.x
- *Currency carry trade: The decline in performance after the 2008 Global Financial Crisis.* (2022). Journal of International Financial Markets, Institutions & Money 76. https://www.sciencedirect.com/science/article/abs/pii/S1042443121001670
- *Downside Risk Reduction Using Regime-Switching Signals: A Statistical Jump Model Approach.* arXiv:2402.05272. https://arxiv.org/html/2402.05272v2
- *On the Effect of Alpha Decay and Transaction Costs on the Multi-period Optimal Trading Strategy.* arXiv:2502.04284. https://arxiv.org/abs/2502.04284

**(b) Credible practitioner / regulator / central bank**

- AQR (Babu, Hoffman, Levine, Ooi, Schroeder, Stamelos) (2020). *You Can't Always Trend When You Want.* Journal of Portfolio Management. https://images.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-You-Cant-Always-Trend-When-You-Want.pdf
- Bank for International Settlements (2019). *FX trade execution: complex and highly fragmented.* BIS Quarterly Review, December. https://www.bis.org/publ/qtrpdf/r_qt1912g.htm
- Carver, R. *How fast should we trade?* (2020). https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html
- Carver, R. *What is the right way to set stop losses?* (2020). https://qoppac.blogspot.com/2020/02/what-is-right-way-to-set-stop-losses.html
- Carver, R. *Fast but not furious: Do fast trading rules actually cost a lot to trade?* (2023). https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html
- Carver, R. *Jumping back in the pool(ing): testing pooling by asset class and portfolio weight distance* (2026). https://qoppac.blogspot.com/2026/07/jumping-back-in-pooling-testing-pooling.html
- Carver, R. *Trading Strategies That Are Designed Not Fitted* (Quantopian talk). https://www.slideshare.net/Quantopian/trading-strategies-that-are-designed-not-fittedby-robert-carver-independent-systematic-futures-trader-writer-and-research-consultant
- ESMA (2018). *Product intervention: binary options and CFDs* (74–89% of retail CFD accounts lose money). https://www.esma.europa.eu/sites/default/files/library/esma71-98-128_press_release_product_intervention.pdf
- FCA (2019). *Fixing the Fix? Assessing the Effectiveness of the 4pm Fix.* Occasional Paper 46. https://www.fca.org.uk/publication/occasional-papers/occasional-paper-46.pdf
- Federal Reserve Bank of St. Louis. *FRED API: series/vintagedates and real-time periods.* https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html
- Hudson & Thames. *Does Meta Labeling Add to Signal Efficacy? (Triple-Barrier Method).* https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/
- Interactive Brokers. *Margin Rates and Financing* (benchmark + tiered spread). https://www.interactivebrokers.com/en/trading/margin-rates.php
- Macrosynergy. *Detecting trends and mean reversion with the Hurst exponent.* https://macrosynergy.com/research/detecting-trends-and-mean-reversion-with-the-hurst-exponent/
- Pardo, R. (interview). *Strategy Optimization with Robert Pardo*, Better System Trader ep. 60. https://bettersystemtrader.com/060-strategy-optimization-with-robert-pardo/
- ReSolve Asset Management. *How to Replicate Trend Following Managed Futures* (SG Trend Index Sharpe 0.42). https://investresolve.com/how-to-replicate-trend-following-managed-futures/
- QuantStart. *Backtesting Systematic Trading Strategies in Python: Considerations and Open Source Frameworks.* https://www.quantstart.com/articles/backtesting-systematic-trading-strategies-in-python-considerations-and-open-source-frameworks/

**(c) Unverifiable / low-confidence — used only where flagged**

- QuantInsti / EPAT project. *FX Trend-Following: A Walk-Forward Validation Study.* https://www.quantinsti.com/articles/trend-following-strategies-major-currency-markets-epat-project/ — student project; no slippage modelling; but the method is honest walk-forward and it is the closest published analogue to ACIS's universe. Treated as indicative, not authoritative.
- Broker-review and broker-education content on OANDA spreads/commissions and retail swap markups (compareforexbrokers, bestbrokers, various). Used only for order-of-magnitude cost figures; **verify against the broker's own published pricing and swap tables before using any number in the spec.**
- *Feature Store For Live And Backtest Parity.* https://skills.himanshujangir.com/skills/feature-store-for-live-and-backtest-parity/ — useful framing of training/serving skew; unverified authorship.
- QIEA-in-finance literature generally (portfolio-optimisation and pairs-trading applications). In-sample, low-tier venues, no multiple-testing correction. No credible evidence of out-of-sample trading superiority.
- Wikipedia, *Deflated Sharpe ratio* (limitations summary). https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio

---

## Honest negatives, stated plainly

- **Nobody has shown that an evolutionary search over technical-indicator parameters produces out-of-sample profits in intraday FX net of realistic costs.** The one study that tested exactly this (Neely & Weller, genetic programming on intraday FX) found none.
- **Nobody has shown that indicator-threshold regime classification improves risk-adjusted returns in FX.** The regime literature's successes are in risk reduction and in description, and the one paper aimed at exchange rates specifically is a negative result.
- **Nobody has shown a retail-accessible FX strategy with a sustained out-of-sample Sharpe above ~1.** The best documented FX-only numbers, gross of retail frictions, cluster around 0.4–0.95, and the retail frictions are large.
- **I found no evidence for or against ACIS's specific combination** (QIEA over 11 genes per regime, six modules, ATR barriers). That is not a defence — an untested combination inherits the base rates of its components, and its components' base rates are poor.
- **The strongest documented FX predictor at your horizons is order flow, which you have excluded by design.** Everything you can do without it is second-best, and you should know that while choosing.
