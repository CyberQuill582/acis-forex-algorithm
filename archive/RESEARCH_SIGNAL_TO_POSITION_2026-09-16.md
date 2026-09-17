# Research: converting a continuous per-bar signal into held positions

**Scope**: how production systematic trading systems turn a continuous per-bar signal into actual positions while minimising transaction-cost drag without destroying the edge — target-position vs event-based entry, no-trade buffers, minimum holding periods, signal smoothing/hysteresis, netting across strategies, turnover-aware optimisation, and signal-half-life matching.

**Date**: 2026-09-16. **Status**: complete. **Nature**: external research only — no ACIS spec, config, code or ledger content is changed or proposed here. Findings are inputs for the owner to triage, not decisions.

**Source grading**
- **[A]** — academic: peer-reviewed journal, NBER/SSRN working paper, or arXiv preprint.
- **[P]** — credible practitioner: named author with a track record, or production open-source code read directly.
- **[U]** — unverifiable: claim encountered but no primary source located.

All URLs below were fetched and read in preparing this document unless explicitly marked otherwise in §9.

---

## 0. Executive answer

The literature is unanimous in one direction: **compute a continuous *target* position every bar, then trade only part of the way to it, and only when you are far enough away.** No credible source recommends discrete entry/exit events as the primary position-formation mechanism; an entry/exit rule is a degenerate target rule (target ∈ {−1, 0, +1}) that discards the magnitude of the signal.

"Only part of the way" has two canonical shapes, and they come from two different cost models:

- **Linear / proportional costs ⇒ a no-trade band** around the target, with **trade-to-the-nearest-edge** when you leave it. (Constantinides, Davis–Norman, Guasoni; and, mechanically, the KKT conditions of an L1 penalty.)
- **Quadratic / impact costs ⇒ a fixed partial-adjustment fraction** toward the target. (Gârleanu–Pedersen.)

Real costs are both (a spread term plus an impact term), so production systems run **both**: a cost penalty in the objective *and* a band. Measured results put the saving at **40–70% of turnover for a ~5% or smaller give-up in gross return**.

Two further results dominate everything else in effect size:
- **Netting across signals/instruments before execution** is the single largest free saving: **−72% turnover, measured** [A].
- **Time-based throttling** (minimum hold, reduced rebalance frequency, trades-per-day cap) is the one technique with *negative* measured evidence: it batches trades rather than removing them, and is dominated by a state band at equal cost [A].

---

## 1. Target-position (state) vs event-based entry

### 1.1 Theory

Every optimal-control treatment of the problem — Constantinides (1986), Davis & Norman (1990), Gârleanu & Pedersen (2013, 2016), Boyd et al. (2017) — formulates the control variable as **the position, or the trade in the position**, never as an entry/exit event. The event formulation does not appear in the literature at all except as a special case.

### 1.2 Rob Carver / pysystemtrade [P]

pysystemtrade computes an **unrounded notional target position** every day and buffers it. The production order generator is literally a band comparison against the live position:

`sysexecution/strategies/classic_buffered_positions.py`
```python
if actual_for_instrument < lower_for_instrument:
    required_position = round(lower_for_instrument)
elif actual_for_instrument > upper_for_instrument:
    required_position = round(upper_for_instrument)
else:
    required_position = actual_for_instrument

trade_required = required_position - actual_for_instrument
```

The signal pipeline upstream of it: raw rule output → **forecast scalar** so that E|forecast| = 10 → **cap at ±20** → weighted combination across rules → × **forecast diversification multiplier** → × volatility scalar, instrument weight, IDM → target position → buffer → order.

Shipped defaults (`sysdata/config/defaults.yaml`):
```yaml
forecast_scalar: 1.0
forecast_cap: 20.0
average_absolute_forecast: 10.0
forecast_div_multiplier: 1.0
percentage_vol_target: 16.0
# buffering / position inertia
buffer_method: forecast
buffer_size: 0.10
buffer_trade_to_edge: True
```

Docs (`docs/backtesting.md`): *"Position inertia, or buffering, is a way of reducing trading costs. The idea is that we avoid trading if our optimal position changes only slightly by applying a 'no trade' buffer around the current position."*

### 1.3 Man AHL [P]

*The Need for Speed in Trend-Following Strategies* (Man Institute). AHL describe **drip-feeding into a continuously-updated target** rather than discrete entries: *"trades can mostly be dripped slowly and passively into the market, and only aggress when deemed necessary"* — justified because "trends last at least several days". They state their execution platform reduces transaction costs by **~50% versus standard bank algorithms**. Their speed study reports that risk-adjusted returns after costs are materially lower for faster models over the long term, while skewness properties survive costs largely intact.

### 1.4 AQR [P]

Israel, Jiang & Ross, *Craftsmanship Alpha: An Application to Style Investing* (JPM 2018) frame implementation as continuous rebalancing toward an "ideal portfolio" with a deliberate deviation tolerance:

> *"if a manager has decided to rebalance daily, he may still reduce trading costs by allowing some deviation to the ideal portfolio. It turns out that the effect of varying the deviation is similar to that of changing the rebalance frequency: A higher deviation induces greater style drift and therefore greater performance degradation, but also less turnover and, thus, lower transaction costs."*

And on the framing of the whole problem: *"A simplistic implementation is to build theoretical portfolios and trade directly to them, without weighing the expected benefit of trading to the ideal portfolio against the expected trading cost of doing so."*

### 1.5 Production frameworks [P]

- **QuantConnect / LEAN** — `PortfolioTarget("IBM", 1200)`, `PortfolioTarget.Percent(algorithm, "IBM", 0.1)`. Docs: *"A `PortfolioTarget` provides the number of units of an asset to hold."* State-based by construction. LEAN also ships a built-in micro-band, in `Common/AlgorithmSettings.cs`:
  ```csharp
  // Because the free portfolio value has a trailing behavior by default, let's add a default
  // minimum order margin portfolio percentage to avoid tiny trades when rebalancing,
  // defaulting to 0.1% of the TPV
  MinimumOrderMarginPortfolioPercentage = 0.001m;
  ```
  Also `ClearFulfilled()` (drop already-achieved targets) and `OrderByMarginImpact()` (position-reducing orders first).
- **Zipline** — `order_target`, `order_target_value`, `order_target_percent` (`zipline/algorithm.py`, lines 1685 / 1758 / 1826). Target-based.
- **cvxportfolio** — solves for the trade vector `z` each period against a cost-penalised objective; target-based.

### 1.6 Verdict

Target-position is the established design across theory, named practitioners, and every production framework examined. Event-based entry survives only where a venue or broker forces it, or where the signal is genuinely binary. **A per-bar continuous signal should produce a per-bar continuous target, and the cost control belongs between the target and the order — not in the signal.**

---

## 2. No-trade bands / rebalancing bands / buffering

### 2.1 The canonical proportional-cost result [A]

Guasoni & Muhle-Karbe, *Portfolio Choice with Transaction Costs: a User's Guide* (arXiv:1207.7330), **Theorem 4.7**, verbatim:

> A long-run optimal policy — both for the frictionless market with price S̃ and in the market with bid-ask prices ((1−ε)S, S) — is to keep the risky weight π̃ in the **no-trade region**
>
> **[π−, π+] = [ (μ−λ)/(γσ²) , (μ+λ)/(γσ²) ]**
>
> As ε ↓ 0, its boundaries have the asymptotics
>
> **π± = μ/(γσ²) ± ( (3/(4γ)) · (μ/(γσ²))² · (1 − μ/(γσ²))² )^(1/3) · ε^(1/3) + O(ε)**
>
> The corresponding equivalent safe rate is
>
> **r + β = r + μ²/(2γσ²) − (γσ²/2) · ( (3/(4γ)) (μ/(γσ²))² (1 − μ/(γσ²))² )^(2/3) · ε^(2/3) + O(ε^(4/3))**

Symbols: μ = excess drift; σ = volatility; γ = relative risk aversion; ε = proportional (one-way) transaction cost / relative bid-ask spread; π = fraction of wealth in the risky asset; μ/(γσ²) = the frictionless Merton weight.

**The two design numbers:**

| Quantity | Scaling | Consequence |
|---|---|---|
| Band half-width | **∝ ε^(1/3)** | Costs 8× ⇒ band only 2× wider. A single band constant is defensible across instruments of differing cost. |
| Welfare loss | **∝ ε^(2/3)** | Sub-linear. **Wide bands are nearly free.** |

Heuristic derivation given in the same review: total loss ≈ C·x² (displacement from optimum) + λ/x (trading), minimised at x ∝ λ^(1/3) with loss ∝ λ^(2/3).

Guasoni's framing of the economics:

> *"optimal portfolios entail a no-trade region, in which it is optimal to keep existing holdings in all assets. Optimal portfolios always remain within this region, and hence trading should merely take place at its boundaries. **The no-trade region is wide, even for small transaction costs**, implying that investors should accept wide fluctuations around the frictionless target. Second, **the large no-trade region has a small welfare impact** (Constantinides, 1986), because the displacement loss is small near the frictionless optimum, and the wide no-trade region minimizes the effect of transaction costs."*

**Lineage** (cited in the review, not separately fetched): Magill & Constantinides (1976); **Constantinides (1986)**, *Capital Market Equilibrium with Transaction Costs*, JPE 94(4):842–862 — numerical no-trade region, small welfare cost; **Davis & Norman (1990)**, *Portfolio Selection with Transaction Costs*, Math. of OR — first rigorous free-boundary solution: inaction region plus reflection to the **nearer** boundary; Dumas & Luciano (1991), JF 46(2):577–595 — exact solution; Shreve & Soner (1994) and Rogers (2004) — the O(ε^(1/3)) / O(ε^(2/3)) orders; Janeček & Shreve (2004) — leading-order coefficients; **Liu (2004)**, *Optimal consumption and investment with transaction costs and multiple risky assets*, JF 59(1):289–338 — CARA separation across assets.

Novy-Marx & Velikov [A] make the same connection explicitly, naming banding an **sS rule** after Arrow, Harris & Marschak (1951) inventory control, and noting via Abel & Eberly (1996) that *"the size of this region is proportional to the cube-root of the price wedge for small wedges, which makes its derivative with respect to the wedge infinite"* — **even a tiny cost justifies a non-trivial band.**

### 2.2 Multi-asset caveat — bands get WIDER, not narrower [A]

Guasoni §5 (following Law et al. 2007). With CRRA utility, bands do **not** separate across assets even with zero correlation. Two-asset width for asset 1:

> **H₁ = ( (3ε / 2σ₁²) · [ ((1/2)·μ′Σ⁻¹μ + σ₁²)·π₁² − μ₁π₁² ] )^(1/3)**
>
> vs the single-asset width **h₁ = ( (3ε/4) · π₁²(1−π₁)² )^(1/3)**
>
> and, if correlation ϱ = 0: **H₁³ − h₁³ = (1/2σ₁⁴)·(μ₁μ₂/σ₁σ₂)²  ≥ 0**

> *"the no-trade region in the larger market is always wider than the no-trade region with one asset, and they coincide only if either asset is useless… the presence of an independent asset increases the no-trade region of the others, presumably because the variation of the position in each asset becomes less important for the overall welfare of the investor than with a single asset."*

**Design consequence: a diversified book should buffer *more* than a per-instrument calculation suggests.** This runs against the frictionless fund-separation intuition and is easy to get backwards.

### 2.3 Gârleanu–Pedersen: partial adjustment toward an "aim" [A]

**Gârleanu & Pedersen (2013), "Dynamic Trading with Predictable Returns and Transaction Costs", Journal of Finance 68(6):2309–2340.**

Objective (eq. 4):

> max E₀ Σ_t [ (1−ρ)^(t+1) · ( xₜ′r_{t+1} − (γ/2)·xₜ′Σxₜ ) − ((1−ρ)^t / 2) · Δxₜ′ΛΔxₜ ]

with Δxₜ = xₜ − x_{t−1}; ρ ∈ (0,1) the discount factor; γ absolute risk aversion; Λ the symmetric quadratic cost matrix — *"Λ (actually ½Λ, for convenience) is a multi-dimensional version of Kyle's lambda"*. Signals follow Δf^k_{t+1} = −φ_k·f^k_t + ε^k_{t+1}; expected return is Bfₜ.

**Assumption A: Λ = λΣ** — cost proportional to risk.

**Proposition 2 (Trade Partially Towards the Aim), verbatim:**

> (i) The optimal portfolio is
> **xₜ = x_{t−1} + Λ⁻¹A_xx (aimₜ − x_{t−1})**  … (7)
> which implies trading at a proportional rate given by the matrix Λ⁻¹A_xx towards the "aim portfolio,"
> **aimₜ = A_xx⁻¹ A_xf fₜ**  … (8)
> (ii) Under Assumption A, the optimal trading rate is the scalar **a/λ < 1**, where
>
> **a = [ −(γ + λρ) + √( (γ+λρ)² + 4γλ(1−ρ) ) ] / ( 2(1−ρ)λ )**  … (9)
>
> The trading rate is decreasing in transaction costs λ and increasing in risk aversion γ.

Equivalently (eq. 10):

> **xₜ = (1 − a/λ)·x_{t−1} + (a/λ)·aimₜ**

> *"Interestingly, the optimal portfolio always rebalances by fixed fraction towards the aim (i.e., the trading rate is independent of the current portfolio x_{t−1} or past portfolios)."*

**Proposition 3 (Aim in Front of the Target):** with the frictionless portfolio Markowitzₜ = (γΣ)⁻¹Bfₜ (eq. 11), and letting **z = γ/(γ+a)**:

> **aimₜ = z·Markowitzₜ + (1−z)·Eₜ(aim_{t+1})**  … (12)
> **aimₜ = Σ_{τ=t..∞} z(1−z)^(τ−t) · Eₜ(Markowitz_τ)**  … (13)
> The weight z of the current Markowitz portfolio decreases with transaction costs λ and increases in risk aversion γ.

The aim is an **exponentially-weighted average of the current and all expected future frictionless portfolios.**

**Proposition 5 (Position Homing In):**

> **xₜ = Σ_{τ=−∞..t} (a/λ)·(1 − a/λ)^(t−τ) · aim_τ**  … (17)

The realised position is an EWMA of past aims. **Partial adjustment is mathematically identical to EWMA-smoothing the aim.** Design consequence: if you already EWMA-smooth the position, you have implemented GP — do not also apply a separate partial-adjustment coefficient, or you will double-lag.

**Continuous-time version** — Gârleanu & Pedersen, *Dynamic Portfolio Choice with Frictions* (JET), **Proposition 1**:

> τₜ = dxₜ/dt = **M̄_rate · ( M̄_aim(fₜ) − xₜ )**,  M̄_rate = Λ⁻¹A_xx
> A_xx = −(ρ/2)Λ + Λ^(1/2)·( γ·Λ^(−1/2)ΣΛ^(−1/2) + (ρ²/4)·I )^(1/2)·Λ^(1/2)
> (iv) Under Assumption A: A_xx = aΣ and
> **M̄_rate = a/λ = ½·( √(ρ² + 4γ/λ) − ρ )**
> *"for a patient agent with ρ ≈ 0, we see that the trading rate is approximately **√(γ/λ)**."*

**This is the most usable single formula in the literature: trading rate ≈ √(risk aversion / cost). Quadruple the cost ⇒ halve the trading rate.**

### 2.4 Gârleanu–Pedersen's measured results [A]

Calibration — commodity futures, 1996-01-01 to 2009-01-23:

- Signals with deliberately different persistence:
  Δf^5D = −0.2519·f^5D + ε (**half-life 2.4 days**)
  Δf^1Y = −0.0034·f^1Y + ε (**206 days**)
  Δf^5Y = −0.0010·f^5Y + ε (**700 days**)
  (half-life computed as log(0.5)/log(1−φ))
- γ = 10⁻⁹ — *"a relative risk aversion of 1 for an agent with 1 billion dollars under management"*; ρ = 1 − exp(−0.02/260) (2% p.a.); Σ = empirical covariance of price changes with correlations shrunk 50% toward zero.
- λ from Engle, Ferstenberg & Russell (2008): *"trades amounting to 1.59% of the daily volume in a stock have a price impact of about 0.10%"*. Per-commodity calibration gives **median λ = 5.0×10⁻⁷, mean 8.4×10⁻⁷, sd 1.0×10⁻⁶**; the high-cost case uses 10×10⁻⁷.

**Table 2 — annualised Sharpe ratio, gross and net of trading costs:**

| Strategy | Panel A gross | Panel A **net** | Panel B gross | Panel B **net** |
|---|---|---|---|---|
| Markowitz (ignore costs) | 0.83 | **−9.84** | 0.83 | **−10.11** |
| **Dynamic optimisation (GP)** | 0.62 | **0.58** | 0.58 | **0.53** |
| Static, weight on Markowitz 10% | 0.63 | −0.41 | 0.63 | −1.45 |
| Static, 9% | 0.62 | −0.24 | 0.62 | −1.10 |
| Static, 8% | 0.62 | −0.08 | 0.62 | −0.78 |
| Static, 7% | 0.62 | 0.07 | 0.62 | −0.49 |
| Static, 6% | 0.62 | 0.20 | 0.62 | −0.22 |
| Static, 5% | 0.61 | 0.31 | 0.61 | 0.00 |
| Static, 4% | 0.60 | 0.40 | 0.60 | 0.19 |
| Static, **3%** (best, Panel A) | 0.58 | **0.46** | 0.58 | 0.33 |
| Static, **2%** (best, Panel B) | 0.52 | 0.46 | 0.52 | **0.39** |
| Static, 1% | 0.36 | 0.33 | 0.36 | 0.31 |

Read-outs:

1. **Trading the raw signal is catastrophic.** SR 0.83 gross → **−9.84** net. The cost drag is ~10.7 SR units — an order of magnitude larger than the edge.
2. Correct partial adjustment retains **70% of gross SR as net** (0.58 / 0.83), at a cost of 25% of gross (0.83 → 0.62).
3. **Half-life-aware weighting beats speed-only control by ~26%** net SR (0.58 vs best static 0.46). GP's explanation: *"The key to the out-performance is that the dynamic strategy gives less weight to the 5-day signal because of its fast alpha decay. The static strategy simply tries to control the overall trading speed, but this is not sufficient: it either incurs large trading costs due to its 'fleeting' target… or it trades so slowly it is difficult to capture the return."*
4. **The rate is knife-edge.** 10% → net −0.41; 3% → net +0.46, in the same market with the same signals. Get the adjustment rate wrong by 3× and the edge is gone. There is no safe default; it must be derived.

### 2.5 Boyd et al. / cvxportfolio — the convex-optimisation form [A/P]

Boyd, Busseti, Diamond, Kahn, Koh, Nystrup & Speth, *Multi-Period Trading via Convex Optimization*, Foundations and Trends in Optimization 3(1):1–76, 2017.

**Cost model (eq. 2.2)**, implemented verbatim in cvxportfolio:

> **φ_trade(x) = a·|x| + b·σ·|x|^(3/2) / V^(1/2) + c·x**

where x is the dollar trade; a = half the bid-ask spread plus proportional fees; b ≈ 1 — *"According to a standard rule of thumb, trading one day's volume moves the price by about one day's volatility, which suggests that the value of the number b is around one"*; σ = recent price volatility in dollars; V = dollar volume traded over the period; c = an asymmetry term (e.g. the negative of the open-to-close return). *"This 3/2 power transaction cost model is widely known and employed by practitioners."* Normalised form (eq. 2.3): aᵢ|zᵢ| + bᵢσᵢ|zᵢ|^(3/2)/(Vᵢ/v)^(1/2) + cᵢzᵢ.

cvxportfolio `cvxportfolio/costs.py`, `class TransactionCost`, default `exponent=1.5`, with a guard: *"Exponent should be >=1, otherwise the transaction cost model is not convex."*

**Turnover** is defined as **‖(zₜ)₁:ₙ‖₁ / 2**; the turnover limit is ‖z‖₁/2 ≤ δ.

**Trading aversion.** The objective carries **γ_trade · φ_trade(z)**:

> *"Increasing the trading aversion parameter will deter trading or reduce turnover; decreasing it will increase trading and turnover. We can even think of **1/γ_trade as the number of periods over which we will amortize the transaction cost we incur**."*

**Measured (SPO back-test, §7.3).** Grid search over γ_risk ∈ [0.1, 1000], γ_trade ∈ {1, 2, 5, 10, 20}, then {4…8}, then {5.5…8}; 410 runs in total.

> *"the choice of trading aversion parameter is critical: for some values of γ_trade the results are so poor that the resulting curve does not even fit in the plotting area. Values of γ_trade around 5 seem to give the best results… A value around **γ_trade = 6** seems to be best."*

Every Pareto-optimal point in their Table 7.2 sits at γ_trade between 6.0 and 8.0. **So: penalise the *modelled* cost at roughly 5–8× its nominal size.** This is the cleanest quantitative answer available to "how hard should I penalise turnover".

**Table 7.1 — rebalancing frequency (index tracking, annualised):**

| Frequency | Active risk | Turnover | Cost @ $100M | Cost @ $10B |
|---|---|---|---|---|
| Daily | 0.00% | 220.53% | 0.07% | 0.25% |
| Weekly | 0.09% | 105.67% | 0.04% | 0.16% |
| Monthly | 0.21% | 52.71% | 0.02% | 0.10% |
| Quarterly | 0.35% | 29.98% | 0.01% | 0.07% |
| Annually | 0.63% | 12.54% | 0.01% | 0.04% |
| Hold | 1.53% | 0.00% | 0.00% | 0.00% |

**When multi-period (MPO) beats single-period (SPO):** only when you have *foreknowledge* — known future volatility/risk changes ("In MPO, trading towards a lower risk position starts well before the increase in risk… In SPO, (larger) trading to a lower risk position occurs only once the risk has increased"), known future liquidity/volume changes ("Market volumes have much better predictability than market returns"), changing constraints (planned de-leveraging), and portfolio set-up/shutdown/transfer. Absent those, **SPO with a cost penalty captures the benefit** at 1/H the compute.

### 2.6 Carver's production band [P]

`systems/buffering.py`:

```python
def apply_buffers_to_position(position, buffer):
    top_position = position.ffill() + buffer.ffill()
    bottom_position = position.ffill() - buffer.ffill()

def get_position_method_buffer(position, config):        # "position inertia", book 1
    buffer = abs(position) * config.buffer_size          # 10% of CURRENT position

def _calculate_forecast_buffer_method(position, buffer_size, vol_scalar, idm, instr_weight_this_code):
    average_position = abs(vol_scalar_indexed * instr_weight_this_code_indexed * idm_indexed)
    buffer = average_position * buffer_size              # 10% of AVERAGE position  <-- recommended
```

- **Band half-width B = 0.10 × |average position|**, where average position = volatility scalar × instrument weight × IDM — i.e. **the position you would hold at a forecast of +10**, the average absolute forecast. The band is symmetric: [target − B, target + B].
- The **forecast** method is preferred over the **position** method because *"the buffer doesn't shrink as we get to zero"* — a band proportional to the *current* position collapses at the sign flip, producing maximal churn exactly where trading matters most. This is a real and easily-made design error.
- `buffer_trade_to_edge: True` — *"if outside the buffer we trade to the nearest edge of the buffer, rather than going to the optimal position. This further reduces transaction costs."* This is Davis–Norman reflection to the nearer boundary, arrived at independently.
- Rounding: *"In the case of rounded positions we round the lower limit of the buffer, and the upper limit."*
- `buffer_method: none` still leaves `EPSILON_POSITION = 0.001` to avoid float noise.
- Honest about the parameter: *"the buffering width I use is the same for all instruments (10% of an average position); actually in theory it should be wider for expensive instruments and narrower for cheaper instruments."* The ε^(1/3) law in §2.1 explains why one constant nonetheless works acceptably.

**Portfolio-level band (dynamic optimisation).** `systems/provided/dynamic_small_system_optimise/buffering.py`:

```python
def calculate_adjustment_factor(speed_control, tracking_error_of_prior):
    if tracking_error_of_prior <= 0:
        return 0.0
    excess_tracking_error = tracking_error_of_prior - speed_control.tracking_error_buffer
    adj_factor = max(excess_tracking_error / tracking_error_of_prior, 0.0)
    return adj_factor
```

with the objective in `optimisation.py`:

```python
def evaluate(self, weights):
    return (self.tracking_error_against_optimal(weights)
            + self.calculate_costs(weights)          # shadow_cost * sum(|cost_per_contract * trade|)
            + self.constraint_function_value(weights))
```

and defaults `small_system: {shadow_cost: 50, cost_multiplier: 1.0, tracking_error_buffer: 0.0125, shrink_instrument_returns_correlation: 0.5}`.

**This is a band and a partial adjustment in one expression**: inside the band, do nothing; outside, execute exactly the fraction of the trade that returns you to the band edge. It is the discrete, portfolio-level analogue of GP's (a/λ) with a dead zone.

Carver's calibration reasoning ("Mr Greedy… part two"):

> *"with an average target risk of 25%, a 10% buffer around that means our dynamic buffer size should be around 1.25% (not 2.5% as you might expect as this buffer is expressed differently)."*

> *"Tracking error is measured in units of annualised standard deviation… Now bear in mind the utility function subtracts the cost from a given optimisation; which is probably a daily cost, we need to annualise this. **So a shadow cost of 250 would annualise costs and put them in the same units as the tracking error.**"*

(The shipped default was later recalibrated to 50.)

**Measured** — 114 futures, $500k capital, dynamic optimisation vs a 34-instrument static benchmark:

| | Gross SR | Net SR | Portfolio turnover | Actual cost |
|---|---|---|---|---|
| Dynamic optimised (114 instruments) | 1.336 | **1.287** | 51.1 /yr | **1.7%/yr** |
| Static benchmark (34 instruments) | 1.322 | **1.275** | 37.5 /yr | 1.45%/yr (≈**2%/yr over the last 15 years**) |
| Unrounded ideal (unachievable) | 1.359 | — | — | — |

Return correlation between the optimised portfolio and the unrounded ideal: **0.986**. Note the direction of travel — the static system's costs *rose* over time while the cost-penalised dynamic system's did not.

### 2.7 The unifying result: linear ⇒ band, quadratic ⇒ shrinkage

Minimising  (γ/2)·(x − x*)′Σ(x − x*) + c·‖x − x_prev‖₁  has the closed form

> **x = x_prev + sign(x* − x_prev) · max( |x* − x_prev| − band, 0 )**

i.e. **a no-trade band plus trade-to-the-edge falls directly out of the KKT conditions of an L1 cost penalty**, exactly as LASSO soft-thresholds. Quadratic costs instead give **proportional shrinkage** (GP's a/λ).

**Linear cost ⇒ band. Quadratic cost ⇒ partial adjustment. Realistic 3/2-power cost ⇒ both.** This is the clean reason production systems run a band *and* a cost penalty, and why neither alone is adequate (see §6 for the empirical confirmation of exactly that).

---

## 3. Signal smoothing and hysteresis

### 3.1 Smoothing ≡ slowing ≡ lower turnover [P, measured]

Carver, *"Fast but not furious: Do fast trading rules actually cost a lot to trade?"* (2023-02-01). EWMAC(n, 4n) crossover on the S&P 500, annual turnover at three stages of the pipeline:

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
- **There is a turnover floor.** The constant-forecast row still turns over 2.53×/yr before buffering, from *"the effect of rolling, scaling positions for volatility, changes in price and movement in FX rates"*. No amount of smoothing gets below it: *"this imposes a lower bound on turnover no matter how slow your forecasts are."*
- **Turnover scales with leverage.** *"as a rule of thumb, if you double your leverage on an individual instrument, you'll also double your turnover"*; portfolio turnover ≈ IDM × single-instrument turnover, with IDM ≈ 2.0 for a diversified book. **A single-instrument turnover budget understates the portfolio's cost by the IDM.**

From part 1 of the same series: *"Rule turnovers are roughly **42 (EWMAC2), 20, 9, 3.8, 2.3, and 2.1 (EWMAC64)**."* — turnover ≈ k / span; **halving the smoothing span roughly doubles turnover.**

### 3.2 Smoothing is not a substitute for buffering, and vice versa

Note the asymmetry in the table above: buffering removes **5%** of a *fast* rule's turnover but **30%** of a *slow* rule's. Smoothing reduces turnover *proportionally* across the whole distribution of signal moves; a fixed band removes *only the small moves*. A fast signal's turnover is dominated by large moves, which no reasonable band can suppress.

**Corollary: you cannot buffer your way out of an over-fast signal.** Carver's entire 2023 series set out to test whether a fast rule could be "smuggled in" behind the buffering and optimisation layers, and concluded: *"it does seem that my original idea of just trading more fast momentum, in the hope of 'smuggling in' some more diversifying trading rules, is a little dead in the water."*

### 3.3 Forecast scaling, capping, and the diversification multiplier [P]

`sysquant/estimators/forecast_scalar.py`:

```python
def forecast_scalar(cs_forecasts, target_abs_forecast=10.0, window=250000, min_periods=500, backfill=True):
    # Take CS average first — we do this before we get the final TS average
    # otherwise get jumps in scalar when new markets introduced
    x = copy_cs_forecasts.ffill().abs().median(axis=1)
    avg_abs_value = x.rolling(window=window, min_periods=min_periods).mean()
    scaling_factor = target_abs_forecast / avg_abs_value      # => E|scaled forecast| = 10
```

Cross-section first, then time series — explicitly to avoid scalar jumps when a new market is added. That ordering is itself a turnover-control decision.

**Capping** at `forecast_cap: 20.0` = **2× the average absolute forecast**. A hard cap at 2× the mean is simultaneously a turnover control and a tail-risk control: it prevents a signal spike from producing a large position you will immediately have to reverse.

**Forecast Diversification Multiplier** — `sysquant/estimators/diversification_multipliers.py`:

```python
def diversification_mult_single_period(corrmatrix, weights, dm_max=2.5):
    """
    Given N assets with a correlation matrix of H and weights W summing to 1,
    the diversification multiplier will be 1 / [ ( W x H x WT ) 1/2 ]
    """
    risk = weights.portfolio_stdev(corrmatrix)
    dm = np.min([1.0 / risk, dm_max])

# and, at the series level:
div_mult_df_smoothed = div_mult_df_daily.ewm(span=ewma_span).mean()   # ewma_span = 125
```

**FDM = min( 1/√(w′Hw), 2.5 )**, then EWMA-smoothed over 125 business days *"to smooth the jumps"*. Forecast weights get identical treatment (`forecast_weight_ewma_span: 125`).

**The general principle visible in the code: every slow-moving *estimated* quantity in the pipeline is EWMA-smoothed before it is allowed to move a position.** An estimator jump is indistinguishable from a signal move at the order layer, but carries no alpha — so it is smoothed at source rather than filtered downstream.

### 3.4 Hysteresis / Schmitt trigger — the measured version [A]

Novy-Marx & Velikov, *A Taxonomy of Anomalies and Their Trading Costs*, RFS (2016); NBER w20721.

> *"These strategies follow an sS rule, under which a trader will hold (maintain short positions on) stocks that they own (are short) provided that the sorting variable is in the extreme s%, but will only actively buy (short) a stock that they have no position in when it enters the most extreme S%. For example, a **10%/20% buy/hold rule** implies that we only buy (sell short) stocks when they get into the top (bottom) 10%, and hold them by restricting sales (short covers) only for stocks that leave the top (bottom) 20%."*

This is a literal Schmitt trigger on a cross-sectional signal. Their explanation of *why the gross give-up is small* is the key design insight, and it generalises to any continuous signal:

> *"The procedure dramatically reduces turnover by holding (not selling) close substitutes to the stocks you would have bought, since **there is not much of a difference in expected returns between stocks in the 75-80% range of the distribution of a given return predictor and those in the 80-85% range**."*

The same argument applies to a scalar signal: the expected-return difference between a forecast of 9.5 and 10.5 is negligible, so refusing to trade across it costs almost nothing.

**Measured, 23 anomalies, July 1973 – December 2012:**

> *"The sS strategies exhibit slightly lower gross returns but much lower turnover and transactions costs as opposed to their simple counterparts. **The average reduction in the turnover for the twenty-three anomalies is 41%, while the transactions costs decrease by 42%.** Net returns are consequently higher."*

Momentum (UMD), monthly percentages, direct before/after across all four treatments:

| Version | Gross E[rᵉ] | Turnover (1-sided, %/mo) | T-costs | **Net E[rᵉ]** | Net FF4 α |
|---|---|---|---|---|---|
| Baseline decile sort (Table 3) | 1.33 | 34.52 | 0.65 | **0.68** [t=2.45] | 0.40 |
| **10%/20% hysteresis (Table 8A)** | 1.25 | **16.66** | 0.34 | **0.91** [t=3.53] | 0.20 |
| Staggered quarterly (Table 7A) | 1.20 | 18.82 | 0.35 | 0.85 [t=3.35] | 0.13 |
| Low-cost universe only (Table 6A) | 1.44 | 38.17 | 0.62 | 0.82 [t=2.29] | 0.07 |

**Hysteresis on momentum: turnover −52%, costs −48%, gross −6%, NET +34%** (0.68 → 0.91 %/month). This is the cleanest published "banding cut turnover by half at a ~6% gross cost" figure available.

Follow-up: Novy-Marx & Velikov, *Comparing Cost-Mitigation Techniques*, Financial Analysts Journal 75(1), 2019:

> *"Banding is the single most effective cost-mitigation technique"* and it was *"the only technique to consistently yield net gains—most prominently, for small- and micro-cap strategies"*, realising *"net returns of more than 4% per year in almost all the strategies in the small- and micro-cap universes."*

Quarterly rebalancing achieved comparable cost reduction but damaged gross returns proportionally, yielding **no net benefit on average**. Restricting to cheap-to-trade stocks **reduced net returns in 10 of 21 cases**.

---

## 4. Minimum holding times and trade throttles

**The evidence here is negative, and it is measured.**

### 4.1 The core finding [A]

Novy-Marx & Velikov (2016), §5.2 on staggered partial rebalancing, verbatim:

> *"The table shows that **a two-thirds reduction in trading frequency generally yields roughly only a one-third reduction in turnover and transaction cost**, as more of the portfolio turns over at each rebalance point."*

That is the whole argument in one sentence: **a time throttle does not remove trades, it batches them.** State drifts further between rebalances, so each rebalance is larger. You pay roughly two-thirds of the cost for one-third of the freshness.

Their own workaround is an admission of the problem: for high-turnover strategies, *"rebalancing quarterly is too infrequent to maintain a large average exposure to the underlying anomaly"*, so they *"run these strategies twice as fast, with staggered rebalancing at a half-quarterly frequency"* — the throttle fights the signal instead of the cost.

**At equal realised cost** (0.34 vs 0.35 %/month on momentum), hysteresis nets **0.91** and quarterly staggering nets **0.85**. Same money spent, more return retained, because the band spends trades where the signal actually moved rather than where the calendar said so.

### 4.2 Corroboration from the other direction [A]

Boyd Table 7.1 (§2.5) shows the same shape: daily → monthly cuts turnover 4.2× (220.5% → 52.7%) but moves active risk from 0.00% to 0.21%; monthly → annually cuts turnover a further 4.2× and triples active risk again. Tracking error grows roughly as √(rebalance interval) while the cost saving is progressively less than proportional. The trade-off gets monotonically worse as you slow down.

### 4.3 Practitioner position [P]

AQR (*Craftsmanship Alpha*): *"the transaction cost savings of rebalancing at a lower frequency needs to be weighed against the performance degradation of trading a more stale portfolio (i.e., there is a trade-off between the cost of trading versus the opportunity cost of not trading)… **Low, or high, turnover by itself should not be seen as a virtue.** Ultimately, net returns, judged over a long-enough sample period, provide a better way to compare different strategies."*

Carver uses **no** minimum holding time and **no** max-trades-per-day cap anywhere in pysystemtrade. His throttle is a **design-time selection rule** — the speed limit (§7) — which excludes a rule/instrument pairing up front, rather than a runtime gate on orders. That is a materially different object: it changes *which* signal is traded, not *when* a decided trade is allowed out.

### 4.4 The one defensible time-based control

Spreading a **decided** trade over time — which delays *execution*, not the *decision*. AQR, quoting Frazzini et al. (2012) execution data: *"trading 2% of a stock's daily volume results in roughly **17 basis points** of market impact; in contrast, trading 6% costs roughly **28 bps** per dollar traded, on average… Rather than completing the trades in one day, they may spread them out across three days (utilizing roughly 2% of trading volume per day)."* Man AHL's drip-feed is the same idea, with a claimed ~50% saving versus standard bank algorithms.

**Verdict for §4:** a minimum hold, a max-trades-per-day cap, or a fixed reduced rebalance frequency is **not supported by any measured evidence found**, and is dominated at equal cost by a state-based band. Patient *execution* of an already-decided trade is a different and well-supported technique.

---

## 5. Netting across strategies and instruments

**The largest single saving available, and it is quantified.** [A]

DeMiguel, Martín-Utrera, Nogales & Uppal, *A Transaction-Cost Perspective on the Multitude of Firm Characteristics*, Review of Financial Studies (2020).

They name the effect **trading diversification**:

> *"just as we get diversification of risk when we combine stocks, we get trading diversification when we combine characteristics. To see this, note that rebalancing the long-short portfolio associated with each characteristic requires trading in the same set of underlying stocks. Thus, exploiting multiple characteristics allows one to **cancel out** some of the trades in the underlying stocks… if to rebalance a characteristic long-short portfolio we need to buy a particular stock, whereas to rebalance another characteristic we need to sell the same stock, then the net amount of trading required to exploit these two characteristics in combination will be smaller than that required to exploit them in isolation."*

**Proposition 3.** With per-stock rebalancing trades tradeᵢ,ₖ = (X_{t+1})ᵢ,ₖ − (Xₜ)ᵢ,ₖ(1 + rᵢ,_{t+1}) for k = 1…K, jointly N(0, Ω):

1. **turnover(tradeᵉʷ) / turnover(tradeⁱˢᵒ) = √(e′Ωe) / Σₖ √(Ω_kk)  < 1**
2. if Ω is symmetric across characteristics (common variance σ², common correlation ρ):
   **= √( (1 + ρ(K−1)) / K )**
3. if additionally ρ = 0:
   **= 1/√K**

**Measured — 51 characteristics, US equities:**

> *"While the average monthly turnover required to exploit the 51 characteristics in isolation is **24.09%**, the turnover required to exploit an equally weighted combination of them is only **6.71%**; that is, **trading diversification delivers a 72.15% reduction in turnover**."*

> *"the average correlation between rebalancing trades across the 51 characteristics and the entire universe of stocks is **5.47%**, not very different from zero"* — close enough to independence that the realised 72% sits near the theoretical 1 − 1/√51 ≈ 86% bound.

Headline economic consequence: *"transaction costs increase the number of significant characteristics from six to 15."* **Netting does not merely save money — it changes which signals are tradeable at all.**

### 5.1 Cross-strategy netting as a return source [A]

Novy-Marx & Velikov §6, "trading one strategy on the margin of another" (industry names: *screens*, *filters*) — use turnover you are *already* doing for strategy A to acquire exposure to strategy B at **effectively negative transaction cost**. Measured: trading the high-frequency combo on the margin of momentum *"decreases turnover (up to 28% for the 50% momentum screen) and improves the net returns"*, and the spanning regressions show the screened combination is worth trading **even if you already hold both strategies separately**, *"simply because we are saving the trading costs associated with rebalancing against the high-frequency combo."*

### 5.2 Practitioner [P]

AQR (*Craftsmanship Alpha*), on integrated vs "portfolio mix" multi-style construction:

> *"an additional benefit of an integrated approach is the potential reduction in transaction and other costs. By forming a portfolio of multiple styles in an integrated way, **a manager can net positions and trades, which may allow for a reduction in the portfolio's turnover**. However, the trade-off is that allocation and attribution may not be as straightforward."*

No figure is given in that paper.

Carver / pysystemtrade: netting is **structural**, not an execution-layer optimisation. Per-rule forecasts are combined into **one number per instrument** (weighted average × FDM, capped) *before* any position is computed; subsystem positions are combined (× instrument weight × IDM) *before* buffering and *before* the order generator. Exactly one order per instrument per cycle reaches the venue. Nothing arrives at the order layer un-netted, so there is nothing left for an order-layer netting step to do.

### 5.3 Unverified

**[U]** Specific internal-crossing rates at named multi-strategy funds (e.g. "X% of fund Y's flow crosses internally") — **no primary source located**. Any such figure should be treated as unverifiable.

### 5.4 Design conclusion

**Net at the *target* level, not at the *order* level.** Order-level netting recovers only offsets that happen to be simultaneous. Target-level netting recovers all of them, including offsets separated in time by a buffer — which, given that a buffer exists precisely to delay trades, is most of them.

---

## 6. Turnover-aware optimisation vs post-hoc filtering

### 6.1 "Trade the change in the signal, not the signal"

This follows directly from GP Proposition 5 (xₜ is an EWMA of past aims) combined with Proposition 2 (the trade is proportional to aimₜ − x_{t−1}). Since x_{t−1} is itself a filtered history of aims, **the trade is proportional to a filtered first difference of the signal.** A system that recomputes a target each bar and diffs it against the held position is already doing this. A system that re-enters on every reading of the signal *level* is not, and pays for the difference.

### 6.2 In-objective penalty beats post-hoc filtering — and the multiplier should exceed 1

**[A] Boyd**: γ_trade ≈ **6** (range 5.5–8) was optimal across 410 back-tests; γ_trade = 1 — i.e. the honest modelled cost with no aversion — was far off the efficient frontier. *"1/γ_trade is the number of periods over which we amortize the transaction cost."*

**[P] Carver** gives the reason the multiplier should exceed 1, and it is **estimation asymmetry, not risk aversion**:

> *"We know costs with more certainty than we know expected gross returns."*

> *"This is a compromise where we use gross returns, but multiply our costs by a factor (>1) before calculating net costs. **A common factor is 2**, derived from the common saying 'A bird in the hand is worth two in the bush'… In other words 1% of extra costs is worth as much as 2% of extra gross returns."*

His own numbers for the asymmetry: *"My costs for last year came in at 1.39% versus a backtested 1.5%. I am pretty confident they will be between 1% and 2% most years I trade"* — against a gross return whose 1-sd interval is roughly −5% to +45%.

Shipped defaults: `forecast_weight_estimate: {cost_multiplier: 2.0, apply_cost_weight: False, ceiling_cost_SR: 9999}`; `small_system: {shadow_cost: 50}` at the trade layer; and a hard backstop `forecast_post_ceiling_cost_SR: 999` with the comment *"Set this to 0.13 to enforce the speed limit even for fixed weights or regardless of what an estimator does"*.

He enumerates five treatments in increasing sophistication — ignore costs → subtract costs (net returns) → **discard gross returns, optimise on costs only** → gross minus multiplied costs → gross weights adjusted post-hoc by cost Sharpe differences — plus a hard maximum-cost threshold as a backstop over whichever is chosen.

### 6.3 Which layer does more work — measured [P]

From the DO experiment:

> *"Both buffering and the trading cost penalty reduce the turnover, although **the cost penalty has the larger standalone effect**. Taken together, costs and buffering reduce turnover significantly, between around a half and a third."*

> *"Buffering in a static system reduces turnover, and thus costs, by **17%** on a very fast strategy… **Dynamic optimisation has the same effect, but is more efficient reducing costs by around a third; as unlike static buffering the cost penalty is instrument specific.**"*

> *"Even with the slowest of our EWMA we still see a **25% reduction** in costs."*

**A per-instrument cost penalty beats a uniform band, because the band is cost-blind.** But see §6.5 — it does not replace the band.

### 6.4 Post-hoc universe filtering is the weakest lever

**[A]** Novy-Marx & Velikov: restricting to the low-cost tertile *"reduced net returns in 10 of 21 cases"*.

**[P]** Carver reaches the same conclusion from the opposite end: *"It's worth preventing expensive instruments from trading in DO, as the cost penalty doesn't seem to be 100% efficient in preventing them from trading. But **there isn't any benefit in completely excluding these expensive instruments from the forecast construction stage.**"*

**Keep the expensive instrument's signal — it contributes to netting and to the diversification multiplier. Gate the *trade*, not the *signal*.**

A related surprise from the same study: *"allowing expensive instruments to trade quicker trading rules actually makes a strategy **less** correlated to a faster trading strategy. It also increases costs by around 50% versus the conditional approach."*

### 6.5 The known failure mode of a pure cost penalty [P]

Carver found the shadow cost has a floor it cannot push through:

> *"the algo always starts at zero (in the absence of corner case constraints) and then starts changing position with the sign of the optimal unrounded position. So it will always end up with the same sign of position as the underlying optimal position. To put it another way, **every time the underlying forecast changes sign, we'll definitely trade regardless of the size of the shadow cost.** All the shadow cost will do is reduce trading in instruments where we haven't seen a sign change."*

> *"Let's say their average holding period is a conservative two months; so they change sign roughly every 42 business days. That means on any given day we'd see around three instruments changing sign, and trading. **This imposes a lower limit on turnover, no matter how much you crank up the shadow cost.**"*

This is the direct empirical justification for running a band *as well as* a cost penalty — which is also what §2.7 predicts from the cost model. The band catches the sign-flip churn that a smooth penalty cannot.

---

## 7. Half-life matching: trading speed vs signal decay

### 7.1 The formula [A]

Gârleanu–Pedersen, **Proposition 4 (Weight Signals Based on Alpha Decay)**, verbatim:

> (i) Under Assumption A, the aim portfolio is the Markowitz portfolio built as if the signals f were scaled down based on their mean reversion Φ:
>
> **aimₜ = (γΣ)⁻¹ B ( I + (a/γ)·Φ )⁻¹ fₜ**  … (14)
>
> (ii) If the matrix Φ is diagonal, Φ = diag(φ₁,…,φ_K), then the aim portfolio simplifies as the Markowitz portfolio with each factor f^k scaled down based on its own alpha decay φ_k:
>
> **aimₜ = (γΣ)⁻¹ B ( f¹ₜ/(1+φ₁a/γ), … , f^K_t/(1+φ_K a/γ) )′**  … (15)

**Per-signal shrinkage weight: wₖ = 1 / (1 + φₖ · a/γ)** where φₖ is signal k's mean-reversion rate (half-life HLₖ = log 0.5 / log(1−φₖ)), and a is the trading-rate numerator from eq. (9). In continuous time a/λ = ½(√(ρ²+4γ/λ) − ρ) ≈ √(γ/λ).

> *"the aim down-weights each return-predicting factor more the higher is its alpha decay φₖ. Down-weighting factors reduces the size of the position, and, **more importantly, changes the relative importance of the different factors**… This dependence on the signals' mean-reversion rate is greater with larger transaction costs, that is, a/γ (which multiplies the mean-reversion Φ) increases with λ."*

> *"giving more weight to the more persistent factors means that the investor trades towards a portfolio that not only has a high expected return now, but also is expected to have a high expected return for a longer time in the future."*

**Worked with GP's own calibration.** φ = 0.2519 / 0.0034 / 0.0010 (half-lives 2.4 / 206 / 700 days). Writing k = a/γ, the relative down-weights are

1/(1 + 0.2519k) : 1/(1 + 0.0034k) : 1/(1 + 0.0010k)

At any k large enough to matter, **the 2.4-day signal is shrunk roughly 74× more than the 206-day signal.** That single mechanism produced the 0.58 vs 0.46 net-Sharpe gap over the best speed-only static rule in Table 2.

**Practical restatement: a fast signal is worth less than a slow signal of the same strength, by a factor that grows with your cost.** The right response to high cost is *not* "trade the same signals more slowly" — it is **"re-weight toward the slower signals AND trade more slowly."** Doing only the second is precisely the "static optimisation" row of Table 2, and it leaves roughly a quarter of the achievable net Sharpe unclaimed.

### 7.2 The practitioner version [P]

Carver, *"How fast should we trade?"*:

> **SPEED LIMIT: DO NOT SPEND MORE THAN ONE THIRD OF YOUR EXPECTED PRE-COST RETURNS ON COSTS**
>
> Total cost per year = Holding cost + (Trading cost × Number of trades)
> Max cost per year = Expected SR / 3
> **Max number of trades = [ (Expected SR / 3) − Holding cost ] / Trading cost**

Costs are measured **in Sharpe units** — execution cost divided by annual standard deviation, treated as *"a negative Sharpe Ratio"*.

Worked example (Eurodollar): Total cost/yr = 0.026 + 0.0058 × ntrades (SR units). At an expected SR of 0.24:
**Max trades = [0.08 − 0.026] / 0.0058 = 9.3 per year**, implying a trailing-stop width X ≈ 0.4 of annualised volatility ⇒ *"7.8 trades a year, with a holding period of about 6 to 7 weeks."*

And the matching rule, stated explicitly:

> *"You also need to make sure your stop loss is consistent with your forecast horizon… For systematic traders, **make sure you use a trading rule that has an expected holding period which matches the stoploss holding period.**"*

Forecast-layer form (2023 post):

> Annual cost, SR units = (forecast turnover + rolls per year) × cost per trade
> **Maximum forecast turnover = (Maximum annual cost / cost per trade) − rolls per year**
> e.g. **(0.13 / 0.005) − 4 = 22**

Budget: *"a maximum of around **0.13 or 0.10 SR annual units** to be spent on costs, depending on which of my books you are reading… The logic is that the realistic median performance for an individual instrument is unlikely to be more than 0.40 or 0.30 SR."*

### 7.3 Half-life matching, measured out-of-model [P]

Carver, part 1 of the 2023 series, regressing optimal rule speed on instrument cost across his futures universe:

> *"Roughly speaking, for the very cheapest instruments the optimal trading speed is around 3.5 (something like an equal weight of EWMAC8 and EWMAC16), and for the costliest it's around 5 (EWMAC32, or equivalently an equal weight of 16,32 and 64)."*

> *"Broadly speaking it is correct that **pre-cost optimal speed is flat, and therefore we should slow down as instruments get more expensive to trade.**"*

This is GP Proposition 4 confirmed out-of-model on 20+ years of futures data: **pre-cost, signal speed does not matter; post-cost, the optimal signal mix slides toward the persistent end as λ rises.**

---

## 8. Ranked: cost-drag reduction per unit of implementation effort

| # | Technique | Measured effect | Effort | Risk to edge | Grade |
|---|---|---|---|---|---|
| **1** | **Net all signals/instruments into ONE target per instrument before sizing** | Turnover **24.09% → 6.71% monthly, −72.15%** (DeMiguel et al., 51 characteristics); theory 1/√K; NMV: up to −28% turnover *with higher* net return from cross-strategy screens | Very low — an architecture choice, not an algorithm | **Near zero.** You trade the same net exposure. Only cost is attribution/debuggability | [A] |
| **2** | **No-trade band + trade-to-edge on the target** (≈10% of *average* position) | NMV momentum: turnover **−52%**, cost −48%, gross **−6%**, **net +34%** (0.68→0.91 %/mo); 23 anomalies avg **−41% turnover / −42% cost**; NMV 2019: "single most effective", >4%/yr net in small caps; Carver: −17% on the fastest rule, −30% on the slowest | Very low — ~10 lines | **Low** if sized off the *average* position. **Real** if sized off the *current* position (collapses at zero ⇒ churn at the sign flip), or if width ≫ the ε^(1/3) prescription | [A]+[P] |
| **3** | **Per-instrument cost penalty in the target/weight objective** (γ_trade ≈ 5–8; cost_multiplier ≈ 2 at the weight layer) | Boyd: γ_trade ≈ 6 optimal over 410 back-tests, wrong value *"so poor the curve does not fit in the plotting area"*; Carver: DO cost penalty cuts cost **~1/3 (fastest rule), 25% (slowest)**, and *"the cost penalty has the larger standalone effect"* than the band | Low (a scalar) to high (if it means adopting an optimiser) | **Medium.** Over-penalising silently starves cheap, high-alpha instruments. Has a hard floor: cannot suppress sign-flip trades (§6.5) | [A]+[P] |
| **4** | **Match signal speed to cost** — shrink signal k by 1/(1 + φₖ·a/γ) | GP: net SR **0.58 vs 0.46** for the best speed-only rule (+26%), vs **−9.84** for no control at all; Carver: optimal speed EWMAC8/16 (cheapest) → EWMAC32 (costliest) | Medium — needs a half-life estimate per signal | **Medium.** Down-weighting fast signals is right; *deleting* them costs diversification. Re-weight, don't remove | [A]+[P] |
| **5** | **Partial adjustment fraction** a/λ ≈ √(γ/λ) toward the target | GP Table 2 (same evidence as #4); Carver's `adj_factor = max((x−b)/x, 0)` — DO SR 1.336 gross / 1.287 net, **0.986** correlation with the unrounded ideal | Low (one line) | **Medium.** A slow rate on a fast signal = permanent lag; you hold yesterday's view. Table 2: 10% → net −0.41, 3% → net +0.46 | [A]+[P] |
| **6** | **Forecast scaling + capping** (E\|f\| = 10, cap ±20 = 2× mean) | Not separately measured; universal in production | Very low | **Low.** Caps only the tail | [P] |
| **7** | **Patient execution / drip-feed** (≤2% of daily volume per day) | AQR/Frazzini: 2% of volume ≈ **17 bps**, 6% ≈ **28 bps** ⇒ splitting a 6% trade over 3 days saves ~11 bps/$ (≈40%); AHL claim **~50%** vs standard bank algos | Medium–high (needs an execution layer) | **Low** for slow signals; **high** for fast ones — you trade staleness for impact | [P] |
| **8** | **Restrict to a cheap-to-trade universe** | NMV: **reduced net returns in 10 of 21 cases**; Carver: *"no benefit in completely excluding these expensive instruments from the forecast construction stage"* | Very low | **HIGH.** Destroys diversification and removes netting counterparties. Keep the signal, gate the trade | [A]+[P] |
| **9** | **Minimum holding time / reduced rebalance frequency / trades-per-day cap** | NMV: *"a two-thirds reduction in trading frequency generally yields roughly only a one-third reduction in turnover and transaction cost"*; at equal cost nets **0.85 vs 0.91** for banding; NMV 2019: no net benefit on average | Very low | **HIGHEST of the listed techniques.** Batches trades rather than removing them; damages gross return roughly in proportion to the cost saved. **Dominated at equal cost by #2** | [A] |

### 8.1 If only three things are implemented

1. **Net to a single target per instrument before anything touches an order.** (#1 — largest effect, lowest risk, lowest effort.)
2. **A band of ~10% of the *average* position around that target, trading to the nearest edge.** (#2)
3. **Refuse, at design time, any signal/instrument pair whose turnover × cost-per-trade exceeds one third of its expected pre-cost Sharpe.** (Carver's speed limit — the cheapest form of #3/#4, and the only one needing no optimiser.)

### 8.2 The three specific ways to destroy the edge

- **Band sized off the *current* position.** It collapses toward zero and produces maximal churn exactly at the sign flip, where the trade matters most. Carver's stated reason for preferring the forecast method: *"the buffer doesn't shrink as we get to zero."*
- **Mis-set partial-adjustment rate.** GP Table 2: 10% → net −0.41; 3% → net +0.46, same market, same signals. There is no safe default; derive it from √(γ/λ) and sanity-check the resulting holding period against the signal's half-life.
- **Time-based throttling.** It looks like cost control and is in fact staleness purchased at nearly full price.

### 8.3 Two second-order findings worth remembering

- **Turnover has a floor** set by volatility scaling, FX revaluation, rolls and capital changes (Carver: 2.53/yr on a constant forecast, before buffering). Any turnover budget must be net of that floor, or it will be silently overspent.
- **Portfolio turnover ≈ IDM × single-instrument turnover.** A per-instrument cost budget understates the portfolio's realised cost by roughly the diversification multiplier (≈2.0 for a diversified futures book).

---

## 9. Sources

### Academic [A]

| Work | URL |
|---|---|
| Gârleanu & Pedersen (2013), *Dynamic Trading with Predictable Returns and Transaction Costs*, JF 68(6):2309–2340 | https://nbgarleanu.github.io/DynTrad.pdf · https://www.nber.org/papers/w15205 · SSRN 1364170 |
| Gârleanu & Pedersen, *Dynamic Portfolio Choice with Frictions* (JET) | http://docs.lhpedersen.com/DynamicPortfolioChoiceWithFrictions.pdf |
| Guasoni & Muhle-Karbe, *Portfolio Choice with Transaction Costs: a User's Guide* | https://arxiv.org/pdf/1207.7330 |
| Boyd, Busseti, Diamond, Kahn, Koh, Nystrup & Speth (2017), *Multi-Period Trading via Convex Optimization*, FnT Optimization 3(1):1–76 | https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf · https://arxiv.org/abs/1705.00109 |
| Novy-Marx & Velikov (2016), *A Taxonomy of Anomalies and Their Trading Costs*, RFS / NBER w20721 | https://www.nber.org/system/files/working_papers/w20721/w20721.pdf |
| Novy-Marx & Velikov (2019), *Comparing Cost-Mitigation Techniques*, FAJ 75(1) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3253359 · https://rpc.cfainstitute.org/research/financial-analysts-journal/2019/ip-v4-n1-4-comparing-cost-mitigation-techniques |
| DeMiguel, Martín-Utrera, Nogales & Uppal (2020), *A Transaction-Cost Perspective on the Multitude of Firm Characteristics*, RFS | https://lbsresearch.london.edu/id/eprint/1124/1/DeMiguel_TransactionCostPerspective.pdf · SSRN 2912819 |

Cited **within** the above and relied on only through those citations (not fetched independently): Magill & Constantinides (1976); Constantinides (1986) JPE 94(4):842–862; Davis & Norman (1990) Math. OR; Dumas & Luciano (1991) JF 46(2):577–595; Liu (2004) JF 59(1):289–338; Shreve & Soner (1994); Rogers (2004); Janeček & Shreve (2004); Engle, Ferstenberg & Russell (2008); Law, Lee, Howison & Dewynne (2007); Arrow, Harris & Marschak (1951); Abel & Eberly (1996); Frazzini, Israel & Moskowitz (2012).

### Practitioner [P]

| Work | URL |
|---|---|
| Carver, *Fast but not furious: Do fast trading rules actually cost a lot to trade?* (2023-02-01) | https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html |
| Carver, *Scream if you want to go faster* (2023-01) | https://qoppac.blogspot.com/2023/01/scream-if-you-want-to-go-faster.html |
| Carver, *How fast should we trade?* (2020-04) | https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html |
| Carver, *Mr Greedy and the tale of the minimum tracking error variance — part two* (2021-11) | https://qoppac.blogspot.com/2021/11/mr-greedy-and-tale-of-minimum-tracking.html |
| Carver, *Optimising weights with costs* (2016-05) | https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html |
| Israel, Jiang & Ross, *Craftsmanship Alpha: An Application to Style Investing*, JPM 2018 (AQR) | https://images.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/AQR--Craftsmanship-Alpha.pdf |
| Man Institute / AHL, *The Need for Speed in Trend-Following Strategies* | https://www.man.com/maninstitute/need-for-speed-trend-following |

### Production code read directly [P]

| File | Repository |
|---|---|
| `systems/buffering.py`, `systems/portfolio.py`, `sysexecution/strategies/classic_buffered_positions.py`, `systems/provided/dynamic_small_system_optimise/{optimisation.py, buffering.py}`, `sysquant/estimators/{forecast_scalar.py, diversification_multipliers.py}`, `sysdata/config/defaults.yaml`, `docs/backtesting.md` | https://github.com/robcarver17/pysystemtrade |
| `cvxportfolio/costs.py` (`class TransactionCost`, exponent 1.5) | https://github.com/cvxgrp/cvxportfolio |
| `Common/AlgorithmSettings.cs` (`MinimumOrderMarginPortfolioPercentage = 0.001m`) | https://github.com/QuantConnect/Lean |
| `zipline/algorithm.py` (`order_target`, `order_target_value`, `order_target_percent`) | https://github.com/quantopian/zipline |
| QuantConnect portfolio-construction docs (`PortfolioTarget`, `PortfolioTarget.Percent`, `IsRebalanceDue`) | https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/portfolio-construction/key-concepts |

### Unverified / not located [U]

- Internal-crossing rates at named multi-strategy funds — no primary source found; treat any such figure as unverifiable.
- **Grinold**, *Linear Trading Rules for Portfolio Management* (JPM 2018) and *Nonlinear Trading Rules for Portfolio Management* (JPM 45(1):62, 2019). Directly on topic — the policy driver is the **backlog** (target minus current position), and the 2019 paper gives a **piecewise-linear buy / hold / sell policy**, i.e. a band with partial adjustment outside it. Paywalled; abstract only: https://www.pm-research.com/content/iijpormgmt/45/1/62 · https://www.researchgate.net/publication/326123246_Linear_Trading_Rules_for_Portfolio_Management
- **Kolm & Ritter**, *Multiperiod Portfolio Selection and Bayesian Dynamic Models* (Risk, March 2015) — restates Gârleanu–Pedersen as an LQR / Kalman-filter problem. No free PDF located.
- **Levine & Pedersen**, *Which Trend Is Your Friend?* (FAJ 2016) — relevant to §3 (equivalence of moving-average and smoothed-signal trend measures). Not located.

### Method note

The session's WebSearch budget (200/200) was already exhausted before this task began. Research proceeded by Brave/WebFetch search until rate-limited, then by direct URL fetch of primary sources with local PDF text extraction. Every formula and number quoted above was extracted from the fetched primary document, not from a search snippet. The four items under "Unverified / not located" are unexplored for access reasons, not because they were judged unimportant — Grinold in particular is the closest published analogue to the band-plus-partial-adjustment design and would be worth acquiring.
