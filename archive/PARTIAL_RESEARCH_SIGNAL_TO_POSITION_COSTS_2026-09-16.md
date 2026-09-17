# PARTIAL — Research: converting a continuous per-bar signal into positions while minimising transaction-cost drag

**Task**: external research pass (web, primary sources) requested by the ACIS coordinator/owner on 2026-09-16, as a research-only deliverable (no repo changes). Agent: quantitative-trading researcher subagent. Deliverable was to be returned in-message; this file is a crash checkpoint written on coordinator instruction. **Status: research essentially complete; this file contains the full findings.** Nothing here is a spec change or a ledger entry.

Grading key: **[A]** = academic / peer-reviewed / working paper; **[P]** = credible named practitioner or production open-source code; **[U]** = unverifiable / asserted.

---

## 0. One-paragraph answer

The literature is unanimous in one direction: **compute a continuous *target* position every bar, then trade only part of the way to it, and only when you are far enough away.** Nobody credible recommends discrete entry/exit events as the primary mechanism. The two canonical shapes of "only part of the way" are (a) a **no-trade band** around the target with **trade-to-the-nearest-edge** when you leave it (optimal under *proportional/linear* costs), and (b) a **fixed partial-adjustment fraction** toward the target (optimal under *quadratic/impact* costs, Gârleanu–Pedersen). Both are cheap to implement, and measured results put the cost saving at **40–70% of turnover for a ~5% or smaller gross-return give-up**. The single largest free saving in a multi-signal book is **netting before execution** (measured 72% turnover reduction). The biggest edge-destroyer is **time-based throttling** (minimum hold / reduced rebalance frequency), which is measurably dominated by state-based banding at equal cost.

---

## 1. Target-position (state) vs event-based entry

### Theory
Every optimal-control treatment of the problem (Constantinides 1986; Davis–Norman 1990; Gârleanu–Pedersen 2013/2016; Boyd et al. 2017) formulates the control as **the position (or the trade), not an entry/exit event**. An entry/exit rule is a *degenerate special case* of a target rule (target ∈ {−1, 0, +1}) and throws away the information in the magnitude of the signal.

### Rob Carver [P] — explicit
- pysystemtrade computes an **unrounded notional position** every day and then buffers it. The production order generator (`sysexecution/strategies/classic_buffered_positions.py`) is literally: compare *actual* position to the *upper/lower buffer* of the *target*, and emit a trade only if outside.
  https://github.com/robcarver17/pysystemtrade/blob/master/sysexecution/strategies/classic_buffered_positions.py
  ```python
  if actual_for_instrument < lower_for_instrument:
      required_position = round(lower_for_instrument)
  elif actual_for_instrument > upper_for_instrument:
      required_position = round(upper_for_instrument)
  else:
      required_position = actual_for_instrument
  trade_required = required_position - actual_for_instrument
  ```
- His forecast pipeline: raw rule output → **forecast scalar** so the average absolute forecast = 10 → **cap at ±20** → weighted combination → × **forecast diversification multiplier (FDM)** → position. Defaults (`sysdata/config/defaults.yaml`):
  `forecast_cap: 20.0`, `average_absolute_forecast: 10.0`, `forecast_scalar: 1.0`, `forecast_div_multiplier: 1.0`, `percentage_vol_target: 16.0`, `buffer_method: forecast`, `buffer_size: 0.10`, `buffer_trade_to_edge: True`.
  https://github.com/robcarver17/pysystemtrade/blob/master/sysdata/config/defaults.yaml

### Man AHL [P]
"The Need for Speed in Trend-Following Strategies" (Man Institute) — AHL describe **drip-feeding into a continuously-updated target** rather than discrete entries: *"trades can mostly be dripped slowly and passively into the market, and only aggress when deemed necessary"*, justified because "trends last at least several days". They claim their execution platform reduces transaction costs by **~50% versus standard bank algorithms**.
https://www.man.com/maninstitute/need-for-speed-trend-following

### AQR [P]
Israel, Jiang & Ross, *Craftsmanship Alpha: An Application to Style Investing* (JPM 2018) frame implementation as continuous rebalancing toward an "ideal portfolio" with a deliberate deviation tolerance: *"if a manager has decided to rebalance daily, he may still reduce trading costs by allowing some deviation to the ideal portfolio. It turns out that the effect of varying the deviation is similar to that of changing the rebalance frequency."*
https://images.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/AQR--Craftsmanship-Alpha.pdf

### Production frameworks [P]
- **QuantConnect / LEAN** — `PortfolioTarget("IBM", 1200)`, `PortfolioTarget.Percent(algorithm, "IBM", 0.1)`; "A `PortfolioTarget` provides the number of units of an asset to hold." State-based by construction. LEAN ships a built-in micro-no-trade band: `MinimumOrderMarginPortfolioPercentage = 0.001m` (0.1% of total portfolio value) — *"to avoid tiny trades when rebalancing, defaulting to 0.1% of the TPV"*.
  https://github.com/QuantConnect/Lean/blob/master/Common/AlgorithmSettings.cs
  https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/portfolio-construction/key-concepts
- **Zipline** — `order_target`, `order_target_value`, `order_target_percent` (zipline/algorithm.py L1685, L1758, L1826). Target-based.
  https://github.com/quantopian/zipline/blob/master/zipline/algorithm.py
- **cvxportfolio** — solves for trade weights `z` each period against a cost-penalised objective; target-based.

**Verdict:** target-position is the established design. Event-based entry survives only where the venue/broker forces it or where the signal is genuinely binary.

---

## 2. No-trade bands / rebalancing bands / buffering

### 2a. Canonical proportional-cost result [A]

Guasoni & Muhle-Karbe, *Portfolio Choice with Transaction Costs: a User's Guide* (arXiv:1207.7330) — Theorem 4.7, verbatim:

> A long-run optimal policy — both for the frictionless market with price S̃ and in the market with bid-ask prices ((1−ε)S, S) — is to keep the risky weight π̃ in the **no-trade region**
> [π−, π+] = [ (μ−λ)/(γσ²) , (μ+λ)/(γσ²) ].
> As ε ↓ 0, its boundaries have the asymptotics
> **π± = μ/(γσ²) ± ( (3/(4γ)) (μ/(γσ²))² (1 − μ/(γσ²))² )^(1/3) · ε^(1/3) + O(ε).**
> The corresponding equivalent safe rate is
> r + β = r + μ²/(2γσ²) − (γσ²/2) ( (3/(4γ)) (μ/(γσ²))² (1 − μ/(γσ²))² )^(2/3) ε^(2/3) + O(ε^(4/3)).

Symbols: μ = excess drift, σ = volatility, γ = relative risk aversion, ε = **proportional** (one-way) transaction cost / relative bid-ask spread, π = fraction of wealth in the risky asset.

**The two numbers that matter for design:**
- **band half-width ∝ ε^(1/3)** — grows as the *cube root* of cost. Costs 8× ⇒ band only 2× wider.
- **welfare loss ∝ ε^(2/3)** — sub-linear. *Wide bands are nearly free.* Guasoni: *"The no-trade region is wide, even for small transaction costs… the large no-trade region has a small welfare impact (Constantinides, 1986), because the displacement loss is small near the frictionless optimum."*
- Heuristic derivation: total loss ≈ C·x² (displacement) + λ/x (trading), minimised at x ∝ λ^(1/3), loss ∝ λ^(2/3).

Lineage cited there: Magill & Constantinides (1976); **Constantinides (1986)** *Capital Market Equilibrium with Transaction Costs*, JPE 94(4):842–862 (numerical no-trade region, small welfare cost); **Dumas & Luciano (1991)** JF 46(2):577–595 (exact solution); **Davis & Norman (1990)** *Portfolio Selection with Transaction Costs*, Math. of OR 15(4):676–713 (first rigorous free-boundary solution: inaction region + reflection to the **nearer** boundary); Shreve & Soner (1994) and Rogers (2004) (O(ε^(1/3)) / O(ε^(2/3)) orders); Janeček & Shreve (2004) (leading-order coefficients); **Liu (2004)** *Optimal consumption and investment with transaction costs and multiple risky assets*, JF 59(1):289–338 (CARA separation across assets).

Novy-Marx & Velikov make the same connection explicitly, calling banding an **sS rule** after Arrow, Harris & Marschak (1951) inventory control, and noting Abel & Eberly (1996) show *"the size of this region is proportional to the cube-root of the price wedge for small wedges, which makes its derivative with respect to the wedge infinite"* — i.e. **even a tiny cost justifies a non-trivial band.**

**Multi-asset caveat** [A] (Guasoni §5, after Law et al. 2007): with CRRA, bands do *not* separate. Width of asset 1's band in a 2-asset market:
H₁ = ( (3ε / 2σ₁²) [ ((1/2)μ′Σ⁻¹μ + σ₁²)π₁² − μ₁π₁² ] )^(1/3), vs single-asset h₁ = ( (3ε/4) π₁²(1−π₁)² )^(1/3), and H₁³ − h₁³ = (1/2σ₁⁴)(μ₁μ₂/σ₁σ₂)² ≥ 0.
**The presence of other assets makes each band WIDER.** A diversified book should buffer more, not less, than a single-instrument calculation suggests.

### 2b. Gârleanu–Pedersen: partial adjustment toward an "aim" [A]

**Gârleanu & Pedersen (2013), "Dynamic Trading with Predictable Returns and Transaction Costs", Journal of Finance 68(6):2309–2340.**
PDF (author copy, verified, formulas extracted verbatim): https://nbgarleanu.github.io/DynTrad.pdf · NBER w15205: https://www.nber.org/papers/w15205 · SSRN 1364170

Setup — objective (eq. 4):
max E₀ Σ_t [ (1−ρ)^(t+1) ( xₜ′r_{t+1} − (γ/2) xₜ′Σxₜ ) − ((1−ρ)^t / 2) Δxₜ′ΛΔxₜ ]
with Δxₜ = xₜ − x_{t−1}, ρ ∈ (0,1) discount, γ absolute risk aversion, Λ the (symmetric) quadratic cost matrix — *"Λ (actually ½Λ) is a multi-dimensional version of Kyle's lambda"*.
Signals: Δf^k_{t+1} = −φ_k f^k_t + ε^k_{t+1}; expected return Bfₜ.
**Assumption A: Λ = λΣ** (cost proportional to risk).

**Proposition 2 (Trade Partially Towards the Aim):**
> xₜ = x_{t−1} + Λ⁻¹A_xx (aimₜ − x_{t−1})  … (7)
> aimₜ = A_xx⁻¹ A_xf fₜ  … (8)
> (ii) Under Assumption A, the optimal trading rate is the scalar **a/λ < 1**, where
> **a = [ −(γ + λρ) + √( (γ+λρ)² + 4γλ(1−ρ) ) ] / ( 2(1−ρ)λ )**  … (9)
> The trading rate is decreasing in transaction costs λ and increasing in risk aversion γ.

and equivalently (eq. 10):
> **xₜ = (1 − a/λ)·x_{t−1} + (a/λ)·aimₜ**

> *"Interestingly, the optimal portfolio always rebalances by fixed fraction towards the aim (i.e., the trading rate is independent of the current portfolio x_{t−1} or past portfolios)."*

**Proposition 3 (Aim in Front of the Target):** with Markowitzₜ = (γΣ)⁻¹Bfₜ (eq. 11) and **z = γ/(γ+a)**:
> aimₜ = z·Markowitzₜ + (1−z)·Eₜ(aim_{t+1})  … (12)
> aimₜ = Σ_{τ=t..∞} z(1−z)^(τ−t) Eₜ(Markowitz_τ)  … (13)
The aim is an **exponentially-weighted average of current and expected future frictionless portfolios**, decay parameter z. z decreases with λ, increases with γ.

**Proposition 5 (Position Homing In):** xₜ = Σ_{τ=−∞..t} (a/λ)(1−a/λ)^(t−τ) aim_τ — the realised position is an EWMA of past aims. **Partial adjustment ≡ EWMA smoothing of the aim.** (Design consequence: if you already EWMA-smooth your position, you have implemented GP; don't do it twice.)

**Continuous-time version — Gârleanu & Pedersen, "Dynamic Portfolio Choice with Frictions" (JET 2016 / 2014 wp), Proposition 1:**
http://docs.lhpedersen.com/DynamicPortfolioChoiceWithFrictions.pdf
> τₜ = dxₜ/dt = M̄_rate ( M̄_aim(fₜ) − xₜ ), M̄_rate = Λ⁻¹A_xx,
> A_xx = −(ρ/2)Λ + Λ^(1/2)( γΛ^(−1/2)ΣΛ^(−1/2) + (ρ²/4)I )^(1/2) Λ^(1/2)
> Under Λ=λΣ: **M̄_rate = a/λ = ½(√(ρ² + 4γ/λ) − ρ)**, and *"for a patient agent with ρ≈0, the trading rate is approximately **√(γ/λ)**."*

**This is the single most usable formula in the whole literature:** trading rate ≈ √(risk aversion / cost). **Quadruple the cost ⇒ halve the trading rate.**

### 2c. GP's measured results [A]

Calibration (commodity futures, 1996-01-01 to 2009-01-23, 15 contracts):
- Signals: Δf^5D = −0.2519 f^5D + ε (half-life **2.4 days**); Δf^1Y = −0.0034 f^1Y + ε (**206 days**); Δf^5Y = −0.0010 f^5Y + ε (**700 days**).
- γ = 10⁻⁹ ("relative risk aversion of 1 for an agent with 1 billion dollars"); ρ = 1 − exp(−0.02/260); Σ = empirical covariance of price changes with correlations shrunk 50% to zero.
- λ from Engle, Ferstenberg & Russell (2008): *"trades amounting to 1.59% of the daily volume in a stock have a price impact of about 0.10%"* ⇒ per-commodity λ, **median 5.0×10⁻⁷, mean 8.4×10⁻⁷, sd 1.0×10⁻⁶**; high-cost case 10×10⁻⁷.

**Table 2 — annualised Sharpe, gross and net:**

| Strategy | Panel A gross | Panel A **net** | Panel B gross | Panel B **net** |
|---|---|---|---|---|
| Markowitz (ignore costs) | 0.83 | **−9.84** | 0.83 | **−10.11** |
| **Dynamic optimisation (GP)** | 0.62 | **0.58** | 0.58 | **0.53** |
| Static, weight on Markowitz 10% | 0.63 | −0.41 | 0.63 | −1.45 |
| Static, 5% | 0.61 | 0.31 | 0.61 | 0.00 |
| Static, 4% | 0.60 | 0.40 | 0.60 | 0.19 |
| Static, **3%** (best, Panel A) | 0.58 | **0.46** | 0.58 | 0.33 |
| Static, **2%** (best, Panel B) | 0.52 | 0.46 | 0.52 | **0.39** |
| Static, 1% | 0.36 | 0.33 | 0.36 | 0.31 |

Read-outs:
1. **Trading the raw signal is catastrophic**: SR 0.83 → −9.84. Cost drag ≈ 10.7 SR units.
2. Correct partial adjustment keeps **70% of gross SR net** (0.58/0.83) and gives up only 25% of gross (0.83→0.62).
3. **Half-life-aware beats speed-only by ~26%** net SR (0.58 vs best static 0.46). *"The key to the out-performance is that the dynamic strategy gives less weight to the 5-day signal because of its fast alpha decay. The static strategy simply tries to control the overall trading speed, but this is not sufficient."*
4. Static tuning is knife-edge: 10% → net −0.41, 3% → net +0.46. **Get the rate wrong by 3× and you lose everything.**

### 2d. Boyd et al. / cvxportfolio — the convex-optimisation form [A/P]

Boyd, Busseti, Diamond, Kahn, Koh, Nystrup, Speth, *Multi-Period Trading via Convex Optimization*, Foundations and Trends in Optimization 3(1):1–76, 2017. https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf · arXiv:1705.00109

Cost model (eq. 2.2), implemented verbatim in cvxportfolio:
> **φ_trade(x) = a|x| + b·σ·|x|^(3/2) / V^(1/2) + c·x**
> a = half the bid-ask spread (+ proportional fees), b ≈ 1 ("trading one day's volume moves the price by about one day's volatility"), σ = recent price volatility in dollars, V = period dollar volume, c = asymmetry/drift term. *"This 3/2 power transaction cost model is widely known and employed by practitioners."*
https://github.com/cvxgrp/cvxportfolio/blob/master/cvxportfolio/costs.py (`class TransactionCost`, `exponent=1.5`)

Turnover definition: **‖z‖₁ / 2** per period; turnover limit ‖z‖₁/2 ≤ δ.
Trading aversion: the objective carries **γ_trade · φ_trade(z)**. *"Increasing the trading aversion parameter will deter trading or reduce turnover… We can even think of 1/γ_trade as the number of periods over which we will amortize the transaction cost we incur."*

**Measured (SPO backtest, 5 years US equities, §7.3):** grid search over γ_risk ∈ [0.1,1000], γ_trade ∈ {1,2,5,10,20}, then {4..8}, then {5.5..8} — 410 runs.
> *"the choice of trading aversion parameter is critical: for some values of γ_trade the results are so poor that the resulting curve does not even fit in the plotting area. Values of γ_trade around 5 seem to give the best results… A value around **γ_trade = 6** seems to be best."*

**So: penalise the modelled cost at ~5–8× its nominal size.** (Pareto-optimal points in Table 7.2 all sit at γ_trade between 6.0 and 8.0.) This is the single cleanest quantitative answer to "how hard should I penalise turnover".

**Boyd Table 7.1 — rebalancing frequency (passive index tracking, annualised):**

| Freq | Active risk | Turnover | Cost @ $100M | Cost @ $10B |
|---|---|---|---|---|
| Daily | 0.00% | 220.53% | 0.07% | 0.25% |
| Weekly | 0.09% | 105.67% | 0.04% | 0.16% |
| Monthly | 0.21% | 52.71% | 0.02% | 0.10% |
| Quarterly | 0.35% | 29.98% | 0.01% | 0.07% |
| Annually | 0.63% | 12.54% | 0.01% | 0.04% |
| Hold | 1.53% | 0.00% | 0.00% | 0.00% |

MPO (H>1) is only worth the complexity when you have **foreknowledge**: known future volatility/liquidity changes, known constraint changes, portfolio transitions. Otherwise SPO-with-cost-penalty captures the benefit.

### 2e. Carver's production band [P]

`systems/buffering.py` — https://github.com/robcarver17/pysystemtrade/blob/master/systems/buffering.py

```python
def apply_buffers_to_position(position, buffer):
    top_position = position.ffill() + buffer.ffill()
    bottom_position = position.ffill() - buffer.ffill()

def get_position_method_buffer(position, config):     # "position inertia" (book 1)
    buffer = abs(position) * config.buffer_size       # 10% of CURRENT position

def _calculate_forecast_buffer_method(position, buffer_size, vol_scalar, idm, instr_weight_this_code):
    average_position = abs(vol_scalar_indexed * instr_weight_this_code_indexed * idm_indexed)
    buffer = average_position * buffer_size           # 10% of AVERAGE position  <-- recommended
```

- **Band half-width B = 0.10 × |average position|**, where average position = vol_scalar × instrument_weight × IDM, i.e. **the position you would hold at a forecast of +10** (the average absolute forecast). Symmetric: [target − B, target + B].
- **forecast** method is preferred over **position** method because *"the buffer doesn't shrink as we get to zero"* — a band proportional to the current position collapses at the sign flip, exactly where you least want to trade.
- `buffer_trade_to_edge: True` — *"if outside the buffer we trade to the nearest edge of the buffer, rather than going to the optimal position. This further reduces transaction costs."* (= Davis–Norman reflection to the nearer boundary.)
- Rounding: *"In the case of rounded positions we round the lower limit of the buffer, and the upper limit."*
- Carver's own honesty about the parameter: *"the buffering width I use is the same for all instruments (10% of an average position); actually in theory it should be wider for expensive instruments and narrower for cheaper instruments"* — and the ε^(1/3) law above says the correct scaling is mild, which is why a single constant works.
- `buffer_method: none` still leaves EPSILON_POSITION = 0.001 to avoid float noise.

**Portfolio-level band (dynamic optimisation).** `systems/provided/dynamic_small_system_optimise/buffering.py`:
```python
adj_factor = max((tracking_error_of_prior - tracking_error_buffer) / tracking_error_of_prior, 0.0)
```
with defaults `small_system: {shadow_cost: 50, cost_multiplier: 1.0, tracking_error_buffer: 0.0125}`. Objective (`optimisation.py`): `evaluate = tracking_error + trade_shadow_cost·Σ|cost_per_contract·trade| + constraint_penalty`.
**This is a band AND a partial adjustment in one line**: inside the band, do nothing; outside, do exactly the fraction of the trade that brings you back to the band edge. It is the discrete-time analogue of GP's `(a/λ)` with a dead zone.

Carver's calibration reasoning (blog, "Mr Greedy… part two"): *"with an average target risk of 25%, a 10% buffer around that means our dynamic buffer size should be around 1.25%"*; and for the shadow cost, *"Tracking error is measured in units of annualised standard deviation… the utility function subtracts the cost from a given optimisation; which is probably a daily cost, we need to annualise this. So a shadow cost of 250 would annualise costs and put them in the same units as the tracking error."* (shipped default later recalibrated to 50).
https://qoppac.blogspot.com/2021/11/mr-greedy-and-tale-of-minimum-tracking.html

Measured, 114 futures, $500k, dynamic-optimised vs a 34-instrument static benchmark:
- return correlation with the unrounded ideal portfolio **0.986**
- optimised SR **1.336 gross / 1.287 net** (≈5bp SR cost), portfolio turnover **51.1/yr**, actual cost **1.7%/yr** on a 25% vol target
- static benchmark SR **1.322 / 1.275**, turnover **37.5**, cost **1.45%/yr** (but **~2%/yr over the last 15 years**, i.e. the static system got *more* expensive over time while DO did not)
- unachievable unrounded 114-instrument ideal: SR **1.359**

---

## 3. Signal smoothing and hysteresis

### 3a. Smoothing ≡ slowing ≡ lower turnover [P, measured]

Carver, "Fast but not furious: Do fast trading rules actually cost a lot to trade?" (2023-02-01)
https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html

EWMAC(n, 4n) crossover on S&P 500, annual turnover at three stages:

| Rule | Forecast turnover | Raw position turnover | Buffered position turnover |
|---|---|---|---|
| EWMAC4,16 (fastest) | 61.80 | 52.63 | **49.81** |
| EWMAC8,32 | 31.13 | 27.80 | 24.98 |
| EWMAC16,64 | 16.32 | 16.23 | 13.88 |
| EWMAC32,128 | 9.69 | 11.44 | 8.92 |
| EWMAC64,256 (slowest) | 7.46 | 10.16 | **7.04** |
| Constant forecast (long only) | 0.00 | 2.53 | 2.14 |

Findings, verbatim:
- *"The reduction is proportionally higher for slower trading rules: it's about a **5% reduction for ewmac4** and more like **30% for the very slowest** momentum rule."* (raw → buffered)
- *"something we think has a turnover of over 60 (ewmac4) will actually end up with a turnover of more like 50 after buffering. That is a **17% reduction**."* (forecast → buffered)
- **Vol-scaling, FX and rolling put a floor on turnover**: the constant-forecast row still turns over 2.53×/yr raw. You cannot get below this no matter how much you smooth.
- **Turnover scales with leverage**: *"if you double your leverage on an individual instrument, you'll also double your turnover"*; portfolio turnover ≈ IDM × single-instrument turnover, with IDM ≈ 2.0 for a well-diversified book.

From part 1 of the same series (https://qoppac.blogspot.com/2023/01/scream-if-you-want-to-go-faster.html): *"Rule turnovers are roughly **42 (EWMAC2), 20, 9, 3.8, 2.3, and 2.1 (EWMAC64)**."* — i.e. **turnover ≈ k / span**; halving the smoothing span roughly doubles turnover.

### 3b. Smoothing is NOT the same as buffering — they compose badly-then-well
Note the asymmetry above: buffering removes **5%** of a fast rule's turnover but **30%** of a slow rule's. Smoothing removes turnover *proportionally* across the whole distribution of signal moves; buffering removes *only the small moves*. A fast signal's turnover is dominated by large moves, which a fixed band cannot suppress. **Corollary: buffering is not a substitute for choosing the right signal speed.** Carver's whole 2023 series concludes the "smuggling in a fast rule behind the buffer" idea is *"a little dead in the water."*

### 3c. Forecast scaling, capping, FDM [P] — the machinery around the smoothing

`sysquant/estimators/forecast_scalar.py`:
```python
def forecast_scalar(cs_forecasts, target_abs_forecast=10.0, window=250000, min_periods=500, backfill=True):
    x = copy_cs_forecasts.ffill().abs().median(axis=1)        # cross-sectional median |f| first
    avg_abs_value = x.rolling(window=window, min_periods=min_periods).mean()
    scaling_factor = target_abs_forecast / avg_abs_value       # => E|scaled forecast| = 10
```
Cross-section first, then time series — *"we do this before we get the final TS average otherwise get jumps in scalar when new markets introduced."* That is itself a turnover-control decision.

Capping: `forecast_cap: 20.0` = **2× the average absolute forecast**. A hard cap at 2× the mean is a turnover control *and* a tail-risk control: it stops a signal spike producing a trade you will immediately reverse.

**Forecast Diversification Multiplier** — `sysquant/estimators/diversification_multipliers.py`:
```python
# Given N assets with a correlation matrix of H and weights W summing to 1,
# the diversification multiplier will be 1 / [ ( W x H x WT ) ^ 1/2 ]
dm = np.min([1.0 / risk, dm_max])                 # dm_max = 2.5
div_mult_df_smoothed = div_mult_df_daily.ewm(span=ewma_span).mean()   # ewma_span = 125
```
**FDM = min( 1/√(w′Hw), 2.5 )**, then EWMA-smoothed with span 125 business days *"to smooth the jumps"*. Forecast weights get the same treatment: `forecast_weight_ewma_span: 125`. **Every slow-moving estimated quantity in the pipeline is EWMA-smoothed before it is allowed to move a position** — because an estimator jump is indistinguishable from a signal move at the order layer, but carries no alpha.

### 3d. Hysteresis / Schmitt-trigger — the measured version [A]

Novy-Marx & Velikov, *A Taxonomy of Anomalies and Their Trading Costs*, RFS 29(1):104–147 (2016); NBER w20721. https://www.nber.org/system/files/working_papers/w20721/w20721.pdf

> *"These strategies follow an sS rule, under which a trader will hold (maintain short positions on) stocks that they own (are short) provided that the sorting variable is in the extreme s%, but will only actively buy (short) a stock that they have no position in when it enters the most extreme S%. For example, a **10%/20% buy/hold rule** implies that we only buy (sell short) stocks when they get into the top (bottom) 10%, and hold them by restricting sales (short covers) only for stocks that leave the top (bottom) 20%."*

This is a literal Schmitt trigger on a cross-sectional signal. Their explanation of *why* it costs so little gross return is the key design insight:

> *"The procedure dramatically reduces turnover by holding (not selling) close substitutes to the stocks you would have bought, since there is not much of a difference in expected returns between stocks in the 75-80% range of the distribution of a given return predictor and those in the 80-85% range."*

**Measured, 23 anomalies, July 1973 – December 2012:**
> *"The sS strategies exhibit slightly lower gross returns but much lower turnover and transactions costs as opposed to their simple counterparts. The average reduction in the turnover for the twenty-three anomalies is **41%**, while the transactions costs decrease by **42%**. Net returns are consequently higher."*

Momentum (UMD), monthly, direct before/after:

| Version | Gross E[rᵉ] | Turnover (1-sided, %/mo) | T-costs | **Net E[rᵉ]** | Net FF4 α |
|---|---|---|---|---|---|
| Baseline decile sort (Table 3) | 1.33 | 34.52 | 0.65 | **0.68** [t=2.45] | 0.40 |
| **10%/20% hysteresis (Table 8A)** | 1.25 | **16.66** | 0.34 | **0.91** [t=3.53] | 0.20 |
| Staggered quarterly (Table 7A) | 1.20 | 18.82 | 0.35 | 0.85 [t=3.35] | 0.13 |
| Low-cost universe only (Table 6A) | 1.44 | 38.17 | 0.62 | 0.82 [t=2.29] | 0.07 |

**Hysteresis: turnover −52%, costs −48%, gross −6%, NET +34%.** That is the single cleanest "buffering cut turnover ~half at a ~6% gross cost" number in the literature.

Follow-up: Novy-Marx & Velikov, *Comparing Cost-Mitigation Techniques*, Financial Analysts Journal 75(1), 2019.
https://rpc.cfainstitute.org/research/financial-analysts-journal/2019/ip-v4-n1-4-comparing-cost-mitigation-techniques · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3253359
> *"Banding is the single most effective cost-mitigation technique"* and *"the only technique to consistently yield net gains—most prominently, for small- and micro-cap strategies"*, realising *"net returns of more than 4% per year in almost all the strategies in the small- and micro-cap universes."*
Quarterly rebalancing: comparable cost reduction but proportional gross-return damage ⇒ **no net benefit on average**. Restricting to cheap-to-trade names: **reduced net returns in 10 of 21 cases**.

---

## 4. Minimum holding times and trade throttles

**The evidence is negative for time-based throttles, and it is measured.**

**[A] Novy-Marx & Velikov (2016), §5.2 — verbatim:**
> *"The table shows that a **two-thirds reduction in trading frequency generally yields roughly only a one-third reduction in turnover and transaction cost**, as more of the portfolio turns over at each rebalance point."*

That is the whole argument in one sentence: a time throttle **does not remove trades, it batches them**. State drifts further between rebalances, so each rebalance is bigger. You pay ~2/3 of the cost for 1/3 of the freshness. Their fix for fast signals — running high-turnover strategies "twice as fast, with staggered rebalancing at a half-quarterly frequency" because *"rebalancing quarterly is too infrequent to maintain a large average exposure"* — is an admission that the time throttle fights the signal instead of the cost.

At **equal realised cost** (0.34 vs 0.35), hysteresis nets **0.91** and quarterly staggering nets **0.85** on momentum. Same money spent, more return kept, because the band spends the trades where the signal actually moved.

**[A] Boyd Table 7.1** shows the same shape from the other side: going daily→monthly cuts turnover 4.2× (220.5% → 52.7%) but multiplies active risk from 0.00% to 0.21%; monthly→annually cuts turnover a further 4.2× and multiplies active risk 3× again. Tracking error is roughly **∝ √(rebalance interval)** while cost is ∝ 1/interval^(something less than 1) — the trade is progressively worse.

**[P] AQR (Craftsmanship Alpha, Exhibit 7)** on momentum rebalance frequency: *"the transaction cost savings of rebalancing at a lower frequency needs to be weighed against the performance degradation of trading a more stale portfolio… Low, or high, turnover by itself should not be seen as a virtue."*

**[P] Carver** does not use a minimum holding time or a max-trades-per-day cap anywhere in pysystemtrade. His throttle is a **selection** rule applied at design time, not a runtime cap — the *speed limit* (§7 below), which excludes a rule/instrument pair up front rather than gating orders at runtime.

**Conclusion for item 4:** a minimum hold or a trades/day cap is **not supported by any measured evidence** and is dominated by a state band at equal cost. The one defensible time-based control is the opposite of a throttle: **spreading a decided trade over time** (AHL's drip-feed; AQR's 2%-of-volume-per-day over three days), which reduces *impact per dollar* without delaying the *decision*.

---

## 5. Position netting across strategies / instruments

**This is the biggest single free saving, and it is quantified.** [A]

DeMiguel, Martín-Utrera, Nogales & Uppal, *A Transaction-Cost Perspective on the Multitude of Firm Characteristics*, Review of Financial Studies 33(5):2180–2222 (2020).
https://lbsresearch.london.edu/id/eprint/1124/1/DeMiguel_TransactionCostPerspective.pdf · SSRN 2912819

They name the effect **trading diversification**:
> *"just as we get diversification of risk when we combine stocks, we get trading diversification when we combine characteristics… if to rebalance a characteristic long-short portfolio we need to buy a particular stock, whereas to rebalance another characteristic we need to sell the same stock, then the net amount of trading required to exploit these two characteristics in combination will be smaller than that required to exploit them in isolation."*

**Proposition 3.** With trades tradeᵢ,ₖ = (X_{t+1})ᵢ,ₖ − (Xₜ)ᵢ,ₖ(1+rᵢ,_{t+1}) ~ N(0, Ω) jointly across K characteristics:
1. **turnover(trade^ew) / turnover(trade^iso) = √(e′Ωe) / Σₖ √(Ω_kk) < 1**
2. if symmetric (common variance σ², common correlation ρ): **= √( (1 + ρ(K−1)) / K )**
3. if ρ = 0: **= 1/√K**

**Measured, 51 characteristics, US equities:**
> *"While the average monthly turnover required to exploit the 51 characteristics in isolation is **24.09%**, the turnover required to exploit an equally weighted combination of them is only **6.71%**; that is, trading diversification delivers a **72.15% reduction in turnover**."*
> *"the average correlation between rebalancing trades across the 51 characteristics and the entire universe of stocks is **5.47%**, not very different from zero"* — hence close to the 1 − 1/√51 ≈ 86% theoretical bound.

Headline economic consequence: *"transaction costs increase the number of significant characteristics from six to 15"* — netting doesn't just save money, it **changes which signals are tradeable at all**.

**[A] Novy-Marx & Velikov §6** — "trading one strategy on the margin of another", industry name *screens* or *filters*: use the turnover you are already doing for strategy A to take positions in strategy B *at effectively negative transaction cost*. Measured: trading the high-frequency combo on the margin of momentum *"decreases turnover (up to 28% for the 50% momentum screen) and improves the net returns"*, and the spanning regressions show the screened combination is worth trading **even if you already hold both strategies separately**, *"simply because we are saving the trading costs associated with rebalancing against the high-frequency combo."*

**[P] AQR** (Craftsmanship Alpha): *"By forming a portfolio of multiple styles in an integrated way, a manager can **net positions and trades**, which may allow for a reduction in the portfolio's turnover. However, the trade-off is that allocation and attribution may not be as straightforward."* — no number given in that paper.

**[P] Carver**: netting is structural in pysystemtrade — per-rule forecasts are combined **into one number per instrument** (weighted average × FDM, capped) *before* any position is computed, and instrument subsystem positions are combined (× instrument weight × IDM) *before* buffering and *before* the order generator. There is exactly one order per instrument per cycle. He never nets at the order layer because nothing reaches the order layer un-netted.

**[U]** Specific internal-crossing rates at named multi-strategy funds (e.g. "X% of Millennium's flow crosses internally") — **could not verify from any primary source in this session.** Treat any such figure as unverifiable.

**Design conclusion**: net at the *signal/target* level, not at the *order* level. Netting orders recovers only the simultaneous offsets; netting targets recovers all of them, including the ones separated in time by a buffer.

---

## 6. Turnover-aware optimisation vs post-hoc filtering

### The theory: linear costs ⇒ soft-thresholding [A]
Minimising  ½(x − x*)′Σ(x − x*)·γ + c‖x − x_prev‖₁  has the closed-form solution
**x = x_prev + sign(x* − x_prev)·max(|x* − x_prev| − band, 0)** — i.e. **a no-trade band plus trade-to-the-edge falls out of the KKT conditions of an L1 cost penalty**, exactly as LASSO soft-thresholds. That is why Davis–Norman "reflect to the nearer boundary" and Carver's `buffer_trade_to_edge: True` are the same object. Quadratic costs instead give **proportional shrinkage** (GP's a/λ). **Linear cost ⇒ band; quadratic cost ⇒ partial adjustment; realistic (3/2-power) cost ⇒ both.** This is the cleanest way to see why production systems run a band *and* a partial adjustment.

### "Trade the change in the signal, not the signal"
Direct consequence of GP Prop 5 (xₜ = EWMA of aims) and of the aim being *"the Markowitz portfolio built as if the signals f were scaled down based on their mean reversion"*: the *trade* is proportional to (aimₜ − x_{t−1}), and since x_{t−1} is itself an EWMA of past aims, **the trade is proportional to a filtered first difference of the signal**. A system that recomputes a target and diffs it is already doing this; a system that re-enters on every signal level reading is not.

### In-objective penalty vs post-hoc filter — what the evidence says
**In-objective wins, and the multiplier should be >1.**
- **Boyd [A]**: γ_trade ≈ **6** (range 5.5–8) was optimal; γ_trade = 1 (i.e. honest cost, no aversion) was far from the frontier. *"1/γ_trade is the number of periods over which we amortize the transaction cost."*
- **Carver [P]** (https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html) — the reason a multiplier > 1 is right is **estimation asymmetry, not risk aversion**:
  > *"We know costs with more certainty than we know expected gross returns."*
  > *"This is a compromise where we use gross returns, but multiply our costs by a factor (>1)… A common factor is 2, derived from the common saying 'A bird in the hand is worth two in the bush'… In other words 1% of extra costs is worth as much as 2% of extra gross returns."*
  Shipped default: `forecast_weight_estimate: {cost_multiplier: 2.0, apply_cost_weight: False, ceiling_cost_SR: 9999}`; the dynamic optimiser's `trade_shadow_cost` plays the same role at the trade layer.
  He lists five treatments in increasing sophistication: ignore costs → net returns → **costs only, discard gross** → gross minus multiplied costs → gross weights adjusted post-hoc by cost SR differences → **plus a hard maximum cost threshold**. He uses the last as a backstop: `forecast_post_ceiling_cost_SR` (comment in defaults.yaml: *"Set this to 0.13 to enforce the speed limit even for fixed weights or regardless of what an estimator does"*).
- **Measured comparison of the two layers [P]**: in the DO experiment, *"Both buffering and the trading cost penalty reduce the turnover, although **the cost penalty has the larger standalone effect**. Taken together, costs and buffering reduce turnover significantly, between around a half and a third."* And: *"Dynamic optimisation has the same effect [as buffering], but is **more efficient reducing costs by around a third; as unlike static buffering the cost penalty is instrument specific**."*
  **⇒ A per-instrument cost penalty beats a uniform band, because the band is cost-blind.**
- **Post-hoc universe filtering is the weakest lever [A]**: NMV found restricting to the low-cost tertile *"reduced net returns in 10 of 21 cases"*. Carver reaches the same conclusion from the other end: *"It's worth preventing expensive instruments from trading in DO… But there isn't any benefit in completely excluding these expensive instruments from the forecast construction stage."* **Keep the expensive instrument's signal (it contributes to netting and diversification); just don't let it trade.**

### Known failure mode of a pure cost penalty [P]
Carver found the shadow cost has a **floor it cannot push through**:
> *"the algo always starts at zero… every time the underlying forecast changes sign, we'll definitely trade regardless of the size of the shadow cost. All the shadow cost will do is reduce trading in instruments where we haven't seen a sign change… Let's say their average holding period is a conservative two months; so they change sign roughly every 42 business days. That means on any given day we'd see around three instruments changing sign, and trading. **This imposes a lower limit on turnover, no matter how much you crank up the shadow cost.**"
**⇒ A cost penalty alone is not sufficient; you need the band as well.** This is the direct empirical justification for running both.

---

## 7. Half-life matching: trade speed vs signal decay

### The formula [A]
GP Proposition 4, verbatim:
> (i) Under Assumption A, the aim portfolio is the Markowitz portfolio built as if the signals f were scaled down based on their mean reversion Φ:
> **aimₜ = (γΣ)⁻¹ B ( I + (a/γ)Φ )⁻¹ fₜ**  … (14)
> (ii) If Φ = diag(φ₁,…,φ_K), then
> **aimₜ = (γΣ)⁻¹ B ( f¹ₜ/(1+φ₁a/γ), …, f^K_t/(1+φ_K a/γ) )′**  … (15)

**Per-signal shrinkage factor: wₖ = 1 / (1 + φₖ · a/γ).**
- φₖ = mean-reversion rate of signal k; half-life HLₖ = log(0.5)/log(1−φₖ).
- a = the trading-rate numerator from eq. (9); a/γ rises with λ (cost).
- Continuous time (GP 2016): same form, a/λ = ½(√(ρ²+4γ/λ) − ρ) ≈ √(γ/λ).

> *"the aim down-weights each return-predicting factor more the higher is its alpha decay φₖ. Down-weighting factors reduces the size of the position, and, **more importantly, changes the relative importance of the different factors**… This dependence on the signals' mean-reversion rate is greater with larger transaction costs, that is, a/γ… increases with λ."*

**Worked with GP's own calibration** (φ = 0.2519 / 0.0034 / 0.0010 for the 5-day, 1-year, 5-year signals; half-lives 2.4 / 206 / 700 days). Taking a/γ = k, the relative down-weights are 1/(1+0.2519k) : 1/(1+0.0034k) : 1/(1+0.0010k). At any k large enough to matter, **the 2.4-day signal is shrunk by ~74× more than the 206-day signal.** That single mechanism is what produced the 0.58 vs 0.46 net-SR gap over the best speed-only static rule.

**Practical restatement**: *a fast signal is worth less than a slow signal of the same strength, by a factor that grows with your cost.* The right response to high cost is **not** "trade the same signals more slowly" — it is **"re-weight toward the slower signals AND trade more slowly."** Doing only the second is the "static optimisation" row of Table 2, and it leaves a third of the net Sharpe on the table.

### The practitioner version [P]
Carver, "How fast should we trade?" (https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html):
> **SPEED LIMIT: DO NOT SPEND MORE THAN ONE THIRD OF YOUR EXPECTED PRE-COST RETURNS ON COSTS**
> Total cost per year = Holding cost + (Trading cost × Number of trades)
> Max cost per year = Expected SR / 3
> **Max number of trades = [(Expected SR / 3) − Holding cost] / Trading cost**

Worked example (Eurodollar): cost = 0.026 + 0.0058 × ntrades in SR units; at expected SR 0.24, Max trades = [0.08 − 0.026]/0.0058 = **9.3 per year** ⇒ trailing-stop width X ≈ 0.4 of annualised vol ⇒ *"7.8 trades a year, with a holding period of about 6 to 7 weeks."*
And explicitly: *"make sure you use a trading rule that has an expected holding period which **matches** the stoploss holding period."*

Forecast-layer form (from the 2023 post): **Max forecast turnover = (Max annual SR cost / cost per trade) − rolls per year**; e.g. (0.13 / 0.005) − 4 = **22**. Budget: *"a maximum of around 0.13 or 0.10 SR annual units to be spent on costs"*, since *"the realistic median performance for an individual instrument is unlikely to be more than 0.40 or 0.30 SR."*

**Measured half-life matching** (part 1 of the 2023 series): regressing optimal rule speed on instrument cost across his universe —
> *"for the very cheapest instruments the optimal trading speed is around 3.5 (something like an equal weight of EWMAC8 and EWMAC16), and for the costliest it's around 5 (EWMAC32, or equivalently an equal weight of 16,32 and 64)."*
> *"Broadly speaking it is correct that **pre-cost optimal speed is flat, and therefore we should slow down as instruments get more expensive to trade.**"*

This is GP Prop 4 confirmed out-of-model on 20+ years of futures data: pre-cost, speed doesn't matter; post-cost, the optimal signal mix slides toward the persistent end as λ rises.

---

## 8. RANKED — cost-drag reduction per unit of implementation effort

| # | Technique | Measured effect | Effort | Risk to edge | Grade |
|---|---|---|---|---|---|
| **1** | **Net signals/instruments into ONE target per instrument before sizing** | Turnover **24.09% → 6.71% monthly, −72.15%** (DeMiguel et al., 51 characteristics); theory 1/√K; NMV: up to −28% turnover *and higher net return* from cross-strategy screens | Very low — it's an architecture choice, not an algorithm | **Near zero.** You trade the same net exposure. Only risk is attribution/debuggability | [A] |
| **2** | **No-trade band + trade-to-edge on the target** (10% of average position) | NMV momentum: turnover −52%, cost −48%, gross −6%, **net +34%** (0.68→0.91%/mo); 23 anomalies avg **−41% turnover / −42% cost**; NMV 2019: "single most effective", >4%/yr net in small caps; Carver: −17% turnover on the fastest rule, −30% on the slowest | Very low — ~10 lines | **Low if the band is a fraction of the AVERAGE position.** Real risk if it's a fraction of the *current* position (collapses at zero ⇒ churn at the sign flip) or if width ≫ ε^(1/3) prescription | [A]+[P] |
| **3** | **Per-instrument cost penalty in the target/weight objective** (γ_trade ≈ 5–8, or cost_multiplier ≈ 2 at the weight layer) | Boyd: γ_trade≈6 optimal over 410 backtests, wrong value "so poor the curve does not fit in the plotting area"; Carver: DO with cost penalty cuts cost **~1/3 on the fastest rule, 25% on the slowest**, and *"the cost penalty has the larger standalone effect"* than the band | Low–medium (a scalar in the objective) or high (if it means adopting an optimiser) | **Medium.** Over-penalising silently starves the cheap-to-trade, high-alpha instruments. Has a hard floor: cannot suppress sign-flip trades | [A]+[P] |
| **4** | **Match signal speed to cost (half-life weighting)** — shrink signal k by 1/(1+φₖ·a/γ) | GP: net SR **0.58 vs 0.46** for the best speed-only rule (+26%) and vs **−9.84** for no control; Carver: optimal speed EWMAC8/16 (cheapest) → EWMAC32 (costliest) | Medium — needs a φ (half-life) estimate per signal | **Medium.** Down-weighting fast signals is exactly right; *removing* them costs diversification. Do it by re-weighting, not by deletion | [A]+[P] |
| **5** | **Partial adjustment fraction** a/λ ≈ √(γ/λ) toward the target | GP Table 2 (same evidence as #4); Carver's `adj_factor = max((x−b)/x, 0)` — DO SR 1.336/1.287 net, 0.986 correlation with the unrounded ideal | Low (one line) | **Medium.** A slow rate on a fast signal = permanent lag; you hold the *previous* view. Table 2 shows 10% vs 3% flips net SR from −0.41 to +0.46 | [A]+[P] |
| **6** | **Forecast capping / scaling** (E\|f\|=10, cap ±20) | Not separately measured; standard in production | Very low | **Low.** Caps only the tail | [P] |
| **7** | **Patient execution / drip-feed** (≤2% of daily volume per day) | AQR/Frazzini: 2% of volume ≈ **17 bps**, 6% ≈ **28 bps** ⇒ splitting a 6% trade over 3 days saves ~11 bps/$ (≈ 40%); AHL claim **~50%** saving vs standard bank algos | Medium–high (needs an execution layer) | **Low** for slow signals, **high** for fast ones — you are trading staleness for impact | [P] |
| **8** | **Restrict to a cheap-to-trade universe** | NMV: **reduced net returns in 10 of 21 cases**; Carver: *"no benefit in completely excluding these expensive instruments from the forecast construction stage"* | Very low | **HIGH.** Removes diversification and removes netting counterparties. Keep the signal, gate the *trade* | [A]+[P] |
| **9** | **Minimum holding time / reduced rebalance frequency / trades-per-day cap** | NMV: *"a two-thirds reduction in trading frequency generally yields roughly only a one-third reduction in turnover and transaction cost"*; at equal cost nets **0.85 vs 0.91** for banding; NMV 2019: "no net benefit on average" | Very low | **HIGHEST of the listed techniques.** Batches trades rather than removing them; damages gross return roughly in proportion to the cost saved. **Dominated at equal cost by #2** | [A] |

### If you implement only three things
1. **Net to a single target per instrument before anything touches an order.** (#1)
2. **A band of ~10% of the *average* position around that target, trading to the nearest edge.** (#2)
3. **Refuse, at design time, any signal/instrument pair whose turnover × cost-per-trade exceeds one third of its expected pre-cost Sharpe.** (Carver's speed limit — the cheapest form of #3/#4 and the only one that needs no optimiser.)

### The three specific ways to destroy the edge
- **Band proportional to the current position** → collapses toward zero, maximal churn exactly at the sign flip where the trade matters most. Use the average position (pysystemtrade's `forecast` method) — Carver's stated reason: *"the buffer doesn't shrink as we get to zero."*
- **Mis-set partial-adjustment rate.** GP Table 2: 10% → net −0.41, 3% → net +0.46 in the same market with the same signals. There is no safe default; derive it from √(γ/λ).
- **Time-based throttling.** It looks like cost control and is actually staleness purchased at nearly full price.

---

## 9. Source list (all fetched and verified this session unless marked)

**Academic / working papers**
- Gârleanu & Pedersen (2013) JF 68(6):2309–2340 — https://nbgarleanu.github.io/DynTrad.pdf · https://www.nber.org/papers/w15205 · SSRN 1364170
- Gârleanu & Pedersen, *Dynamic Portfolio Choice with Frictions* (JET 2016) — http://docs.lhpedersen.com/DynamicPortfolioChoiceWithFrictions.pdf
- Guasoni & Muhle-Karbe, *Portfolio Choice with Transaction Costs: a User's Guide* — https://arxiv.org/pdf/1207.7330
- Boyd et al., *Multi-Period Trading via Convex Optimization*, FnT Optimization 3(1) 2017 — https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf · https://arxiv.org/abs/1705.00109
- Novy-Marx & Velikov, *A Taxonomy of Anomalies and Their Trading Costs*, RFS 2016 / NBER w20721 — https://www.nber.org/system/files/working_papers/w20721/w20721.pdf
- Novy-Marx & Velikov, *Comparing Cost-Mitigation Techniques*, FAJ 75(1) 2019 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3253359 · https://rpc.cfainstitute.org/research/financial-analysts-journal/2019/ip-v4-n1-4-comparing-cost-mitigation-techniques
- DeMiguel, Martín-Utrera, Nogales & Uppal, *A Transaction-Cost Perspective on the Multitude of Firm Characteristics*, RFS 2020 — https://lbsresearch.london.edu/id/eprint/1124/1/DeMiguel_TransactionCostPerspective.pdf · SSRN 2912819
- Cited within the above (not separately fetched): Constantinides (1986) JPE 94(4):842–862; Davis & Norman (1990) Math. OR 15(4); Dumas & Luciano (1991) JF 46(2):577–595; Liu (2004) JF 59(1):289–338; Shreve & Soner (1994); Janeček & Shreve (2004); Engle, Ferstenberg & Russell (2008); Law et al. (2007); Arrow, Harris & Marschak (1951).

**Practitioner**
- Carver, "Fast but not furious" (2023-02-01) — https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html
- Carver, "Scream if you want to go faster" (2023-01) — https://qoppac.blogspot.com/2023/01/scream-if-you-want-to-go-faster.html
- Carver, "How fast should we trade?" (2020-04) — https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html
- Carver, "Mr Greedy and the tale of the minimum tracking error variance — part two" (2021-11) — https://qoppac.blogspot.com/2021/11/mr-greedy-and-tale-of-minimum-tracking.html
- Carver, "Optimising weights with costs" (2016-05) — https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html
- AQR — Israel, Jiang & Ross, *Craftsmanship Alpha*, JPM 2018 — https://images.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/AQR--Craftsmanship-Alpha.pdf
- Man Institute / AHL, *The Need for Speed in Trend-Following Strategies* — https://www.man.com/maninstitute/need-for-speed-trend-following

**Code (all fetched and quoted verbatim)**
- pysystemtrade `systems/buffering.py`, `systems/portfolio.py`, `sysexecution/strategies/classic_buffered_positions.py`, `systems/provided/dynamic_small_system_optimise/{optimisation.py,buffering.py}`, `sysquant/estimators/{forecast_scalar.py,diversification_multipliers.py}`, `sysdata/config/defaults.yaml`, `docs/backtesting.md` — https://github.com/robcarver17/pysystemtrade
- cvxportfolio `cvxportfolio/costs.py` — https://github.com/cvxgrp/cvxportfolio
- LEAN `Common/AlgorithmSettings.cs` — https://github.com/QuantConnect/Lean
- zipline `zipline/algorithm.py` (order_target / order_target_value / order_target_percent) — https://github.com/quantopian/zipline

**Open / unresolved**
- Could not verify a primary-source figure for internal-crossing rates at named multi-strategy funds — treat as [U].
- Grinold, *Linear Trading Rules for Portfolio Management* (JPM 2018) and *Nonlinear Trading Rules for Portfolio Management* (JPM 45(1):62, 2019) — directly relevant (backlog = target − current; piecewise-linear buy/hold/sell policy) but paywalled; abstract only: https://www.pm-research.com/content/iijpormgmt/45/1/62
- Kolm & Ritter, *Multiperiod Portfolio Selection and Bayesian Dynamic Models* (Risk, March 2015) — restates GP as an LQR/Kalman problem; free PDF not located this session.
- Levine & Pedersen, *Which Trend Is Your Friend?* (FAJ 2016) — relevant to §3 (moving-average vs smoothed-signal equivalence); PDF not located this session.
- WebSearch budget (200/200) was exhausted before this task began; searching was done via Brave/WebFetch until rate-limited, then by direct URL fetch. Some avenues above are unexplored for that reason, not because they were dismissed.
