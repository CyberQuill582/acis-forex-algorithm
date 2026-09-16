# Blind independent audit — why the engine lost on all three synthetic markets

**Run under audit:** `data/validation/falsification/20260915T231127Z/` (25 walk-forward folds ×
`{planted, null, permuted}`, 2014-03-07 → 2016-04-01, account `dev_paper`, EUR_USD + USD_JPY).
**Auditor:** independent agent, no prior context on this experiment. **Date:** 2026-09-16.
**Constraint honoured:** nothing in `core/`, `config/`, `specs/`, `ACIS_SPEC.md`, `KNOWN_GAPS.md`,
`TODO.md` or any test was modified; no full suite and no full backtest was run. All numbers below
come from the run artifacts or from short read-only scripts in a scratch directory that re-use the
repo's own modules (`core.regime.nvma`, `core.signals.indicators`, `tests.backtest.deflated_sharpe`)
and an exact re-implementation of `tests/backtest/synthetic_market._returns`.

Sections 0–7 were written before reading `KNOWN_GAPS.md` GAP-P12D-31. Section 8 was added after and
does not amend them.

---

## 0. Verdict in one paragraph

The experiment did not measure what it was designed to measure. **The `planted` market could not
have passed under any engine behaviour whatsoever** — two independent gates in
`tests/backtest/report.py` are arithmetically unreachable given the rest of the system (the Deflated
Sharpe hurdle implied by the run's own recorded trials is an *annualised* Sharpe of 19–77; the §14
average-hold band of 30 min–48 h is about twice the longest hold the evolved ATR brackets can
produce on a 1-minute bar). So "null and permuted correctly failed" is not evidence of anything:
*everything* fails. Separately, and independently, the engine really is broken in a way the run did
expose: the planted edge is enormous (a one-line rule earns an annualised Sharpe of 30–86 net of
declared costs), NVMA's own `trend_direction` field identifies the planted drift sign 71–78 % of the
time, and the engine still converts that into −0.65 Sharpe — because that field is never read by
anything, because the regime classifier calls a random walk a "strong trend" 49 % of the time, and
because the module that fires most often (mean reversion) has a *large negative* expectancy
precisely in the market where the edge exists. Both the test and the engine are broken, and each
would have to be fixed before the other's result meant anything.

---

## 1. What the run actually reports

| | planted | null | permuted |
|---|---|---|---|
| annual Sharpe (OOS) | −0.648 | −0.905 | −0.489 |
| profit factor | 0.837 | 0.827 | 0.889 |
| win rate | 0.427 | 0.386 | 0.377 |
| n trades | 2018 | 1864 | 2111 |
| avg trade duration (§14 band) | 477 s | 745 s | 621 s |
| TSMOM avg duration | 197 739 s | 195 960 s | 198 057 s |
| scalp avg duration | **0.0 s** | **0.0 s** | **0.0 s** |
| deflated Sharpe | 0.0 | 0.0 | 0.0 |
| trial count | 121 | 88 | 81 |
| rule violations | — | — | **min_hold** |
| max drawdown | 1.82 % | 0.35 % | 0.38 % |

`per_regime` is `{}` and `per_strategy` is absent from the JSON entirely — this run predates the
attribution work, so the artifact cannot say which regime or strategy lost the money. That absence
is itself part of why the failure looks mysterious.

**Trade composition, recovered exactly from the rational denominators of the duration averages**
(`Fraction(477.5061425061425) == 194345/407`, `Fraction(197739.07692307694) == 2570608/13`, etc.),
since `metrics._avg_duration` partitions the trade list into {§14 band} ∪ {TSMOM} ∪ {MOMENTUM_SCALP}:

| | §14-band trades | TSMOM | MOMENTUM_SCALP |
|---|---|---|---|
| planted | 407 | 13 | **1598 (79 %)** |
| null | 733 | 199 | **932 (50 %)** |
| permuted | 1717 | 197 | **197 (9 %)** |

Every one of those MOMENTUM_SCALP trades has a duration of exactly 0 s (their mean is exactly 0.0
over a non-empty selection). They are *not* excluded from `win_rate`, `profit_factor`, `n_trades` or
the equity curve. **In the planted run, four out of five "trades" that decide the two headline §14
ratios were held for zero seconds.** See §B8.

---

## 2. Is the planted edge real, and is it capturable net of costs? (computed independently)

`MarketSpec`: 20 s ticks, `daily_vol = 0.005`, `drift_sigma = 0.15`, episodes 1–4 h, back to back
across the whole series (the generator's `while k < n` loop leaves no gaps — *every* step of the
planted market carries a ±0.15 σ drift).

Derived scale: σ per 20 s step = 0.761 bp; drift per step = 0.114 bp; per-minute σ = 1.32 bp,
per-minute drift = 0.342 bp. Mean episode ≈ 450 steps ⇒ **mean drift per episode ≈ 51 bp against
16 bp of noise, i.e. a per-episode signal-to-noise ratio of ~3.2.**

Cost actually charged by the harness (`book.PositionModel.close_at`): `2 × slippage_per_side` only —
EUR_USD 2 × 0.00002 = **0.364 bp round trip**, filled at mid. (The synthetic 0.4 bp spread is *not*
charged; see §B6.)

Measured on the generator's own output (130 weekdays, EUR_USD seed):

```
naive rule: go with the sign of the last L ticks, hold H ticks, pay 0.364 bp round trip
  L= 45 ticks ( 15 min) H= 24 ticks (  8 min): mean  +1.366 bp/trade   ann. Sharpe  +69.2
  L= 90 ticks ( 30 min) H= 24 ticks (  8 min): mean  +1.649 bp/trade   ann. Sharpe  +86.0
  L= 90 ticks ( 30 min) H= 90 ticks ( 30 min): mean  +6.461 bp/trade   ann. Sharpe  +70.7
  L=180 ticks ( 60 min) H=180 ticks ( 60 min): mean +11.538 bp/trade   ann. Sharpe  +50.5
  L=360 ticks (120 min) H=180 ticks ( 60 min): mean  +8.393 bp/trade   ann. Sharpe  +33.5
```

**The planted market is not a fair-but-hard test; it is a giveaway.** The edge is 4–30× the
round-trip friction on every horizon from 8 minutes to an hour, and the result is insensitive to the
lookback over an 8× range. A result of −0.65 Sharpe on this market is not "the engine failed to find
a subtle edge"; it is the engine actively destroying an edge that is sitting in plain sight.

Calibration check: the identical measurement on the `null` market returns −0.25 to −0.36 bp per trade
for every rule tried — exactly the round-trip friction, which is what theory demands and which
validates the measurement apparatus.

---

## 3. PART A — the TEST is broken. Independent showstoppers.

### A1. The `passed` gate is arithmetically unreachable. (Decisive; alone invalidates the run.)

`report.build_report` requires `deflated_sharpe >= 0.95`. `harness.Backtest.run` computes it as

```
trials        = every candidate champion's holdout PER-TRADE Sharpe (from a ~5–15-trade holdout
                of QIEA's dual-EMA mini-backtest)
graded series = the engine's OOS PER-TRADE returns (T ≈ 2000)
SR0           = sqrt(Var[trials]) * ((1-γ)·Φ⁻¹(1-1/N) + γ·Φ⁻¹(1-1/(N·e)))
```

Feeding the run's **own recorded** `holdout_trade_sharpe` values back through the repo's own
`tests.backtest.deflated_sharpe.sharpe_threshold`:

| market | N | mean trial SR | sd of trials | **SR0 (per trade)** | implied annualised Sharpe hurdle |
|---|---|---|---|---|---|
| planted | 121 | 0.779 | 0.932 | **2.430** | **≈ 76** |
| null | 88 | 0.305 | 0.247 | **0.617** | **≈ 19** |
| permuted | 81 | 0.245 | 0.263 | **0.649** | **≈ 21** |

To clear `DSR ≥ 0.95` the engine's out-of-sample per-trade Sharpe must exceed
`SR0 + 1.645/√(T−1)`, i.e. **an annualised Sharpe of 19.7 (null), 21.9 (permuted), 77.0 (planted)**.
§14's own target is 1.5. The gate is unreachable by a factor of 13–50.

Two root causes, both wiring rather than mathematics (the DSR implementation itself is faithful to
Bailey & López de Prado 2014 Eq. 2 and has a test pinning the paper's own numbers — *academic source,
correctly implemented*):

1. **Incommensurable estimators.** `V[{SR_n}]` in the paper is the dispersion of trial Sharpes
   *estimated on comparable samples*. Here the trials are Sharpes of 5–15-trade holdouts, whose
   estimation noise alone is sd ≈ 1/√10 ≈ 0.32; the observed sd is 0.25–0.93. That dispersion is
   almost entirely small-sample noise, not genuine strategy dispersion, and it inflates SR0 without
   bound. The graded Sharpe, meanwhile, is estimated on T ≈ 2000. Mixing the two is the classic DSR
   misuse, and the docstring's declared deviations (3) and (4) badly understate it: this is not
   "the selection correction is approximate", it is "the hurdle is off by an order of magnitude".
2. **The hurdle is perversely anti-correlated with the truth.** In `planted` — the one market where
   a real edge exists — the trial Sharpes are higher and far more dispersed (sd 0.93 vs 0.25), so
   SR0 rises to 2.43 and the hurdle to ≈ 76. **The better the market, the harder the gate.** A gate
   with that property can never confirm an edge; it can only ever confirm its absence.

**Consequence: `EXPECT_PASS = {"planted": True}` in `scripts/falsify_engine.py` was unsatisfiable
before the first tick was generated.** The run's verdict carries no information about the engine.

### A2. The §14 average-duration band is unreachable given the declared bar base and gene ranges.

`report.grade_out_of_sample` requires `1800 s ≤ avg_trade_duration_s ≤ 172800 s`. Position exits in
`book.PositionModel.maybe_close` are only: stop touch, target touch, opposite order, 48 h max hold.
Stop and target are `entry ∓ mult × ATR(14 on 1-minute bars)` with
`atr_multiplier_sl ∈ [1.0, 3.5]`, `atr_multiplier_tp ∈ [1.5, 5.0]`, `tp > sl` enforced.

Measured median ATR(14) on 1-minute bars of this market: **1.48 bp of price**. Expected first-passage
time to a barrier at distance `a` with per-minute σ = 1.32 bp is ≈ `(a/σ)²` minutes:

| SL multiple | barrier | expected minutes to touch |
|---|---|---|
| 1.0 × ATR | 1.48 bp | 1.3 |
| 1.5 × ATR | 2.22 bp | 2.8 |
| 2.5 × ATR | 3.71 bp | 7.9 |
| 3.5 × ATR (gene max) | 5.19 bp | **15.5** |

The *widest legal stop in the entire gene space* produces an expected hold of ~15 minutes — half the
§14 floor. Observed: 477 s ≈ 8 min, squarely in the predicted range. To reach a 30-minute mean hold
the stop would have to sit at ≈ 4.2 × ATR(1-min), outside `GENE_SPECS`.

This is **not** an artifact of the synthetic market: real EUR_USD has a comparable 1-minute ATR
(~2 pips) and the same arithmetic gives ~10 minutes at a typical 2× multiplier. **§14's duration band
and §5's gene ranges on a 1-minute bar base are mutually contradictory in the spec itself.** All
three markets failed `avg_duration`, and always will, on any data.

*Corollary, attacking a builder premise directly:* "does a 1-minute bar base suit multi-hour intent?"
— no, and the contradiction is quantifiable rather than aesthetic. The bar base does not merely make
multi-hour capture *hard*; combined with ATR-multiple brackets it makes holds longer than ~15 minutes
structurally impossible, so the system cannot hold a 1–4 h trend episode even when it correctly
identifies one. The planted market's edge lives at exactly the horizon the exit geometry forbids.

### A3. The fold plan makes the "embargo" overlap the previous fold's graded test window.

`scripts/falsify_engine.plan()`:

```python
first_test = START + timedelta(days=train_days) + EMBARGO      # EMBARGO = 7 days
test_start = first_test + k * timedelta(days=test_days)        # test windows are CONTIGUOUS
train_end  = test_start - EMBARGO
```

Test windows are back to back (`test_end_k == test_start_{k+1}`), while each fold's warm-up stream is
`stream(train_end, test_start) = [test_start_k − 7 d, test_start_k)`. **For folds 1…24 that interval
lies entirely inside the previous fold's graded test window.** The harness feeds it through
`_replay` → `_tick(trade=False)`, and `_tick` *unconditionally*:

* runs `maybe_close` on open positions,
* crosses session boundaries and promotes staged params,
* moves the daily-loss anchor,
* marks the intraday drawdown high-water,
* **appends to `book.equity` whenever `st.timestamp.date() != book.last_day`.**

Confirmed from the artifacts: the 100 `BACKTEST_LOAD` events split into 50 warm-up loads of
21 060–21 240 ticks (5 weekdays each) and 50 test loads of 84 k–94 k ticks. **18.9 % of all ticks fed
to the engine are warm-up ticks, and 24 of 25 of those windows replay five already-graded weekdays
backwards in time.**

Consequences, all of which corrupt the graded record:

* ~120 of ~525 graded days (≈ 23 %) appear twice and out of order in `book.equity`, so
  `_returns_from_equity` manufactures spurious jumps that feed `annual_sharpe`,
  `positive_months_pct`, `max_drawdown_pct` and `rolling_var_breach_rate`.
* Positions open at a fold boundary get their stops re-tested against prices from 7 days earlier and
  are closed with `exit_ts < entry_ts`. **That is exactly the `rule_violations: ["min_hold"]` on
  `permuted`**: `dev_paper.min_hold_seconds = 0`, so `t.duration_s < 0` is the *only* way to trip
  that rule. A negative-duration trade is proof of the defect, not a strategy problem.
* `RolloverMarker` marks for those dates are overwritten with stale equity, degrading the SPX
  correlation metric.
* `harness.py`'s stated invariant — "the fold's TEST ticks replay into ONE continuous out-of-sample
  book" — is false under this fold plan.

Note that the production plan (`tests/backtest/oos_plan.plan_folds`) does **not** have this defect —
its embargo sits *after* the previous test window. The bug is in the falsification script's own
bespoke `plan()`. It was introduced by the one piece of code written specifically to check the
others, which is the most dangerous place for it to live.

### A4. Three of the six strategy modules are inert or degenerate in these markets by construction.

* **MOMENTUM_SCALP** gates on `tick_velocity / session_median_velocity ≥ 1.5`. The generator emits
  ticks on an exact 20 s grid while `tick_velocity_window_s = 10.0`, so the velocity series is a
  quantisation artifact (0 or 1 tick per window), not a liquidity signal. Whatever the module does
  here, it is not what it does on real data.
* **PAIR_DIVERGENCE** trades EUR_USD vs USD_JPY, which the generator draws from *independent* RNG
  streams (`seed*1000 + instrument_index`). Their true correlation is zero. The module's
  `stability_floor = 0.40` on a 50-sample Pearson correlation admits |r| ≥ 0.4 roughly 0.5 % of the
  time by chance; evaluated on ~1.4 M ticks that is thousands of spurious firings of a relationship
  that does not exist. (This is also a live-fire finding: a 50-sample correlation floor is far too
  weak a multiple-testing defence for a gate evaluated millions of times.)
* **TSMOM** needs `tsmom_min_history_days = 260` daily closes, seeded from fold 0's *60-day* train
  window — about 43 days. It therefore cannot fire for roughly the first year of the graded record,
  and when it does the harness's hard `max_hold_s = 48 h` closes it (observed mean 197 739 s ≈ 55 h,
  i.e. 48 h plus weekend gaps). **A 48-hour maximum hold is not time-series momentum.** The one
  module the spec calls "required canonical for v1" on the strength of Moskowitz–Ooi–Pedersen (2012)
  is reduced to 13 trades in two years, each truncated at two days. Its declared §14 duration
  conflict was "raised for owner ratification"; the harness silently resolves it by truncation.

So the run graded a three-module engine (TREND, BREAKOUT, MEAN_REVERSION) plus noise, not the
six-module engine the spec describes.

### A5. The experiment has no positive control.

The suite tests {no edge, no edge, edge}. It never establishes that the *measurement apparatus* can
report a pass at all. A fourth arm — or simply a hard-coded oracle strategy replayed through the same
`run_walk_forward` — would have caught A1 and A2 in one run, before the compute was spent.
**A falsification suite with no positive control cannot distinguish "the engine has no skill" from
"the scoreboard is broken".** Here the scoreboard was broken, and the suite reported "2 of 3
correct", which is the most misleading possible summary of that state.

---

## 4. PART B — the ENGINE is also broken. Why it loses where the edge is huge.

### B1. The regime classifier has essentially no skill at detecting trend.

`core/regime/nvma.adx_proxy(mids, 14)` decides STRONG_TREND (≥ 25) / WEAK_TREND (≥ 20). Running the
repo's own function over a **pure random walk** (8 543 windows of 200 mids):

```
mean 27.2   median 24.6   p10 12.6   p90 45.3
P(ADX ≥ 25, "STRONG_TREND")                              = 48.8 %
P(ADX ≥ 20, "at least a weak trend")                     = 64.9 %
P(ADX ≥ 22.5, TREND conviction survives the 0.45 discard) = 56.7 %
direction +1 / −1 / 0                                     = 50.3 / 49.7 / 0.0 %
```

This matches the run's own labels almost exactly. On `null` — a market with *no* trend by
construction — the labeller assigned **26.4 % STRONG_TREND_DOWN + 20.6 % STRONG_TREND_UP = 47 %
"strong trend"**, and 61 % trend of some kind. On `permuted` the shares are identical to within
0.1 pp. On `planted` STRONG_TREND_DOWN rises only from 26.4 % to 34.9 %.

**The state that is supposed to gate the entire strategy set fires half the time on noise and moves
by ~8 pp when a large real trend is inserted.** A 12-state classifier whose flagship state has a
~49 % false-positive rate is not a gate; it is a coin flip with twelve faces. Two further
consequences:

* AGON's TREND conviction is `adx/50` with a 0.45 discard, i.e. `ADX ≥ 22.5` — the *same statistic*
  that chose the regime. The regime gate and the conviction filter are not two independent filters;
  they are one filter applied twice, so the system's apparent defence-in-depth is illusory here.
* Indicator "periods" in NVMA are **tick counts, not time** (`atr_periods [14,50,200]`,
  `adx_period 14`, `bb_window 100`, `hurst_window 200` all index `window.mids`, pushed once per
  tick). On this synthetic market one tick = 20 s, so ADX(14) spans ~5 minutes. On real Dukascopy
  ticks the same 14 ticks can be 2 seconds at the London open and 10 minutes at 03:00. v2.11 moved
  AGON onto bars and explicitly left NVMA on ticks with an honesty rename. The rename is honest;
  **the time base is still wrong, and it is the layer that decides what every other layer may do.**
  A side-effect worth noting: regime statistics computed on tick counts are a function of data rate,
  so the same market at two tick densities is two different "regimes".

I also note an unexplained asymmetry: STRONG_TREND_DOWN exceeds STRONG_TREND_UP by ~6 pp in all
three markets, including `null` and `permuted`, where the generator is symmetric. My random-walk
control shows `adx_proxy` direction is unbiased (50.3/49.7), so this is either a property of these
particular seeds (the folds overlap, so the effective sample is far smaller than 2.2 M bars suggests)
or a real path-dependency worth a look. I flag it rather than claim it.

### B2. `RegimeContext.trend_direction` — the one field that carries the information — is never read.

`grep -rn trend_direction --include=*.py` over the whole repo returns exactly four sites: it is *set*
in `nvma.py:236`, *validated* in `regime_types.py:52/64-65`, and *used in one test fixture*
(`tests/signals_fixtures.py:60`). **No strategy module, no governor, no risk path ever consumes it.**

That matters enormously here, because I measured what the field is worth on the planted market:

```
NVMA adx_proxy direction vs the TRUE planted drift sign
  all windows                       : 70.8 % agree   (n = 51 035)
  windows with ADX ≥ 25 ("strong")  : 78.0 % agree   (n = 28 563)
  mean 8-minute forward return, long minus short, conditioned on that direction: +2.197 bp
  (round-trip friction: 0.364 bp)
```

**A 6:1 edge-to-cost ratio is computed every 120 seconds by the regime layer, carried across the
layer boundary in a frozen dataclass — and thrown away.** Every module re-derives direction from
scratch: TREND from an EMA crossover, BREAKOUT from a channel break, MEAN_REVERSION from a Bollinger
z-score *with the opposite sign*. This is the single largest unforced error I found in the engine,
and it is also the cheapest to test.

### B3. The dominant module bets against the edge, and loses more the stronger the edge is.

I re-implemented AGON's `_trend` (EMA cross + RSI filter) and `_mean_reversion` (Bollinger z
threshold) entry rules with the real ATR(14)-on-1-minute brackets and the harness's own friction,
over 187 200 one-minute bars of each market:

```
=== planted
   trend    sl1.5/tp2.5  n= 1414  mean +0.267 bp  win 49.5 %  hold  6.0 min  annSharpe   +5.52
   trend    sl2.0/tp3.0  n= 1324  mean +0.500 bp  win 53.2 %  hold  8.3 min  annSharpe   +8.02
   trend    sl3.0/tp4.5  n= 1117  mean +1.351 bp  win 57.3 %  hold 14.5 min  annSharpe  +13.35
   meanrev  sl1.5/tp2.5  n=11946  mean -1.261 bp  win 20.5 %  hold  5.5 min  annSharpe  -92.22
   meanrev  sl2.0/tp3.0  n=10491  mean -1.749 bp  win 19.0 %  hold  7.6 min  annSharpe  -98.62
   meanrev  sl3.0/tp4.5  n= 8098  mean -2.912 bp  win 14.3 %  hold 12.8 min  annSharpe -107.93
=== null
   trend    sl2.0/tp3.0  n= 4279  mean -0.275 bp  win 41.2 %  hold  9.2 min  annSharpe   -7.54
   meanrev  sl2.0/tp3.0  n= 9024  mean -0.322 bp  win 40.6 %  hold  9.4 min  annSharpe  -12.67
```

Three things fall out:

1. **TREND works.** On the planted market the engine's own trend rule is profitable at every bracket
   setting tried. The machinery is not incapable.
2. **MEAN_REVERSION is a disaster, and specifically a disaster *because* there is an edge.** It loses
   −1.26 bp/trade on planted versus −0.30 bp/trade (≈ pure friction) on null: **the planted edge
   makes mean reversion four to eight times more expensive.** Its win rate collapses to 14–21 %.
3. **It fires 6–9× more often than TREND.** A z-score threshold is satisfied continuously; a
   crossover is a rare event. The engine's portfolio is therefore dominated by the one module that is
   short the edge.

The two effects very nearly cancel, which is the direct explanation of the headline puzzle:
**the engine's aggregate P&L is nearly independent of whether an edge exists because its trend book
gains roughly what its mean-reversion book loses extra.** That is not a coincidence to be explained
away — it is a structural property of running a trend module and a counter-trend module off the same
gate, with the counter-trend one firing an order of magnitude more often. In the sampled
`SIGNAL_EMITTED` lines of the planted run, MEAN_REVERSION accounts for 102 of the first 200 emissions.

The regime gate was supposed to prevent exactly this — mean reversion is gated to
{RANGING_TIGHT, RANGING_WIDE, MEAN_REVERTING}. But per B1 the classifier puts **23 % of a
wall-to-wall trending market into those states**, and 23 % is more than enough.

### B4. QIEA evolves a strategy that does not exist at runtime.

`evolve_step.evolve_fold` → `LabelledBarCache.history(instrument, regime, …)` returns *only the bars
whose label equals the target regime*, concatenated. `fitness.simulate_trades` then computes
`ema_series`, `rsi_series` and `atr_series` **across that stitched series**, in which two adjacent
"bars" can be hours or days apart.

* The EMA crossover being optimised is a crossover of a fictional price series. At runtime AGON
  computes its EMAs on the *contiguous* bar window regardless of regime. In-sample and out-of-sample
  are not the same strategy — this is a train/serve skew of the first order, not a sampling nuance.
* Stops and targets are evaluated bar-to-bar on a path with holes, so `bar.low <= sl` fires with a
  frequency bearing no relation to a real first-passage.
* `max_holding_periods` counts stitched bars, so `12` can mean twelve minutes or twelve days.
* **The fitness harness only ever evaluates the dual-EMA core.** Three of the eleven genes —
  `momentum_lookback`, `breakout_atr_threshold`, `mean_rev_zscore_entry` — never enter
  `simulate_trades`. The QIEA rotation gate therefore receives *zero gradient* on them; they hitchhike
  on whatever bits the best individual happened to observe. **The entry threshold of the module that
  does most of the trading and all of the damage (B3) is an unoptimised random draw from
  [1.5, 2.5].** The fidelity caveat calls this "not the full engine (GAP-0035)"; that phrasing badly
  undersells what it means in practice.
* Champion selection is `best["holdout_e_r"]` — the holdout is the *selection* criterion *and* the
  gate *and* the DSR trial. Three uses of one 5–15-trade sample.

This also answers the premise about per-regime evolution being "sample-fragmenting". It is worse than
fragmenting: it *reorders* the sample. Fragmenting merely reduces n; stitching changes what is being
measured.

### B5. `tp > sl` is a hard gene invariant, which fights §14's win-rate row.

`ParamSet.__post_init__` refuses `atr_multiplier_tp <= atr_multiplier_sl`, and `repair_invariants`
forces `tp = sl + 0.1` when QIEA observes otherwise. Every bracket therefore has a target further away
than its stop, so on any driftless path the win rate is structurally below 50 %. §14 demands win rate
> 48 % **and** profit factor > 1.4 simultaneously, which pins the admissible region to `tp/sl ≳ 1.52`
at a near-50 % hit rate — requiring an edge before costs of roughly 25 % of the bracket width. It is
attainable, but the spec's own §5.6 doctrine ("published trend-following wins ~35–48 % of trades yet
profits through R:R") argues *against* the 48 % floor §14 then imposes. The two are in tension.

### B6. The harness charges a different cost than the fitness function it is required to share.

`core/optimizer/costs.CostModel.per_side_cost` = `spread/2 + commission + slippage`, and its module
docstring states: *"This is THE cost model: the fitness mini-backtest applies it, and the ACIS-09
backtest harness must import this same module — never re-implement it."*

`tests/backtest/book.PositionModel.close_at` re-implements it inline and **drops the spread term**:

```python
friction = Decimal(str(cost.slippage_per_side * 2 + cost.commission_per_side * 2)) * pos.size_units
```

It never calls `per_side_cost` or `round_trip_cost`. On this market that under-charges the graded run
by the full 0.4 bp spread — the OOS result is roughly **half price** relative to in-sample, i.e.
flattered, and it still loses. A stated single-source-of-truth invariant is violated in the direction
that makes results look better. It also means the C8 calibration against OANDA spreads — the whole
point of §13 v2.9 — does not reach the graded number at all.

### B7. Every adaptive feedback loop is switched off inside the harness.

`MARGINAL_ALPHA_PINNED` fires on **every single sized order** — 1 425 326 of 1 425 326 in planted,
1 646 490 of 1 646 490 in null, 1 683 257 of 1 683 257 in permuted, every one with detail
`cold_start:0<20`. The `MarginalAlphaEstimator` is fed by closed trades, but the harness books closes
in its own `PositionModel` and never routes them back through the Governor. So the C6 marginal-alpha
factor is pinned at NEUTRAL for the entire two years, in all three markets. The same is true of alpha
decay and of the whole Risk Monitor (acknowledged as GAP-0091b/0099/0075).

**§14 is therefore being graded on a system with its adaptation switched off.** That is defensible as
a conservative choice, but it is not in `fidelity_caveats`, and it means the run cannot distinguish
"the strategy has no edge" from "the parts meant to find the edge were not running".

### B8. 79 % of the planted run's trades were held for zero seconds.

Derived in §1 from exact rational arithmetic: 1598 of 2018 planted trades (932/1864 null, 197/2111
permuted) carry `strategy_type == "MOMENTUM_SCALP"` and their durations sum to exactly zero. They are
included in `n_trades`, `win_rate` and `profit_factor` — two of the seven §14 rows. Since the overall
win rate is 0.427, these zero-duration trades do *not* all return −friction; they carry non-zero P&L,
which means the book is realising gains and losses on positions that were never held.

I could not pin the mechanism by static reading alone and will not guess in a report. The two
candidates worth a targeted reproduction, in order:

1. **Same-timestamp reverse closes.** `heapq.merge` gives EUR_USD and USD_JPY identical event times on
   this exact 20 s grid, and `PaperLoop.on_state` allocates solo signals and then group legs within
   one tick; `apply_order` closes an opposite position at `st.timestamp` while `entry_ts =
   order.sized_at`. A close at the same timestamp as the entry gives duration 0, and because a
   pair-divergence leg's `entry_price` is a *bar close* (`b_col[-1]`) while a solo's is the *tick
   mid*, the P&L manufactured by such a close is non-zero.
2. **The A3 backwards warm-up**, which certainly produces `exit_ts ≤ entry_ts` closes at fold
   boundaries (it is the only possible source of a `min_hold` violation at `min_hold_seconds = 0`),
   though at ~48 boundaries it cannot account for 1598 trades on its own.

Either way: **the two §14 ratios this run reports are computed over a trade population that is
majority artifact.** No conclusion about strategy quality survives that, in any direction.

### B9. The regime flickers every few minutes; the parameters change every few days.

`REGIME_SHIFT` fires 245 434 (planted) / 339 639 (null) / 342 210 (permuted) times. With
`cycle_seconds = 120` and two instruments over ~525 trading days there are ≈ 756 000 classifications,
so **32–45 % of classifications change the regime label** — a new "regime" roughly every 4–6 minutes.
Against that:

* `PARAM_STAGED` 91 / `PARAM_PROMOTED` 39, with `PARAM_PROMOTION_STALLED` 11 638. Promotion needs a
  session boundary (4/day) *and* a flat book, so staged parameters wait days.
* `fitness_span_days = 730` — parameters are evolved over a two-year recency span.
* `regime_stability_score` (the fraction of the last 20 classifications matching) multiplies order
  size directly: `raw_usd = base_unit × conviction × liq × corr × (stability × confidence) × ma ×
  vol_norm × taper`. A flickering classifier therefore also **shrinks every position by roughly 3×**;
  observed notional is ~$100 on a $10 000 NAV, i.e. ~1 % gross exposure.

Five orders of magnitude separate the state's dwell time (minutes) from the parameter's refresh
period (days) from the evidence window (years). **This is the sharpest attack I can make on the
"evolve parameters per regime" premise: the object being conditioned on is not stable long enough to
be a conditioning variable.** A state you re-enter 300 times a day is a noise label, not a regime.

A further wrinkle this run exposes: the falsification plan uses `train_days = 60`, so
`window_start = max(fold.train_start, train_end − 730 d)` collapses to 60 days. **The v2.18 fix that
this entire run existed to validate (GAP-P12D-29, "fitness reads every target-regime bar in a 730-day
span") was never exercised** — the fold's own train window truncated it to 60 days.

---

## 5. Ranked hypotheses

Ranked by (certainty × explanatory power), highest first.

| # | Hypothesis | Status | Evidence |
|---|---|---|---|
| **H1** | The DSR gate is unreachable by 1–2 orders of magnitude, so `planted` could never pass. **The experiment's stated expectation was unsatisfiable a priori.** | **Proven** (arithmetic on the run's own recorded trials) | §A1 |
| **H2** | The §14 30-min duration floor is unreachable given ATR(1-min) brackets and the gene ranges. A second, independent unreachable gate. | **Proven** (first-passage arithmetic + observed 477 s) | §A2 |
| **H3** | The regime classifier has ~zero trend skill: `adx_proxy ≥ 25` on 48.8 % of random-walk windows; 47 % of the *null* market is labelled "strong trend". | **Proven** (simulation using the repo's own function; matches the run's own label shares) | §B1 |
| **H4** | The engine loses on `planted` because MEAN_REVERSION fires 6–9× more often than TREND and its expectancy is 4–8× *more* negative when a real trend exists; the two books cancel, making P&L edge-independent. | **Strongly supported** (module-level simulation with the real bracket geometry) | §B3 |
| **H5** | `RegimeContext.trend_direction`, which is 71–78 % accurate about the planted drift sign, is dead code — never read by any consumer. | **Proven** (repo-wide grep + measurement of the field's information content) | §B2 |
| **H6** | 79 % of planted trades are zero-duration artifacts that nonetheless carry P&L, so `win_rate` and `profit_factor` describe a synthetic trade population. | **Proven as arithmetic; mechanism unresolved** | §B8, §1 |
| **H7** | The falsification fold plan replays 23 % of graded days backwards through the book, corrupting the equity curve, drawdown, VaR rate, and producing negative-duration trades. | **Proven** (fold arithmetic + 50 warm-up loads of 5 weekdays each + the otherwise-impossible `min_hold` violation) | §A3 |
| **H8** | QIEA optimises a stitched, non-contiguous price series and never evaluates 3 of 11 genes, including the mean-reversion entry threshold that does the damage in H4. | **Proven by reading; effect size not measured** | §B4 |
| **H9** | Half the strategy set is inert or degenerate in this test (scalp velocity is a grid artifact, pair legs are independent by construction, TSMOM is starved then truncated at 48 h). | **Proven** | §A4 |
| **H10** | The graded run undercharges costs relative to the fitness function it is required to share, flattering OOS. | **Proven by reading** | §B6 |
| **H11** | Regime dwell (~5 min) vs parameter promotion (~days) vs fitness span (2 yr) is an unworkable hierarchy, and `regime_stability_score` additionally shrinks size ~3× because of the flicker. | **Strongly supported** | §B9 |
| **H12** | The §14 target set is internally inconsistent: `positive_months > 70 %` implies an annualised Sharpe of ≈ 1.82 (since P(month>0) = Φ(SR/√12)), stricter than the `Sharpe > 1.5` row beside it; with only 24 monthly transitions, binomial noise pushes the effective requirement to ≈ 2.4. | **Proven** (arithmetic) | — |
| **H13** | `PAIR_DIVERGENCE`'s 50-sample, 0.40-correlation stability floor is too weak a multiple-testing defence for a gate evaluated millions of times, and will trade spurious relationships on real data too. | Supported | §A4 |

**Hypotheses I tested and rejected:**

* *"The Deflated Sharpe maths is wrong."* No — `deflated_sharpe.py` faithfully implements Bailey &
  López de Prado (2014) Eq. 2, with the paper's own numbers pinned by test. The defect is entirely in
  what is fed to it.
* *"There is look-ahead in the evolution."* `refuse_lookahead` genuinely checks the recorded bar spans,
  and `LabelledBarCache.history` genuinely bounds by `b.ts + bar <= end`. I found no leak.
* *"The costs are unrealistically punitive."* The opposite (§B6).
* *"Walk-forward is faked."* `Fold.__post_init__` enforces ordering, test windows really are
  non-overlapping, and the in-sample block really is never graded (`build_report` routes only
  `out_of_sample` into `grade_out_of_sample`). The *fold plan* is wrong (A3) but the *discipline* is
  real and well tested.
* *"The synthetic market carries a net drift a buy-and-hold could harvest."* No — `_returns` demeans,
  and the residual log-to-price convexity drift is ~1e-5 %/day. Fair.

---

## 6. Premises I was asked to attack, and what survived

| Premise | Verdict |
|---|---|
| A 12-state regime classifier is the right gate | **Fails.** 49 % false-positive rate on its flagship state; 32–45 % of classifications flip the label; the one informative output is unused. It is not gating, it is dithering. |
| Evolving parameters per regime is sound rather than sample-fragmenting | **Fails, and worse than fragmenting.** The per-regime bar set is *stitched*, so indicators run on a fictional path; three genes get no gradient at all; the conditioning variable is unstable at ~5-minute scale. |
| A 1-minute bar base suits multi-hour intent | **Fails, quantifiably.** ATR(1-min) × the legal gene range caps expected holds at ~15 minutes against a §14 floor of 30. Multi-hour intent is unrepresentable in the exit geometry. |
| The "planted" market is a fair test | **Fair but trivially easy** — annualised Sharpe 30–86 for a one-line rule, 4–30× friction. That the engine fails it is damning, not exculpatory. But the *suite* around it is not fair: no positive control, degenerate modules, a broken fold plan. |
| The §14 performance targets are attainable | **Not as a set.** `avg_duration ≥ 30 min` is unreachable by construction (A2); `positive_months > 70 %` is stricter than `Sharpe > 1.5` (H12); and with the DSR gate as wired nothing is reachable at all (A1). |
| Walk-forward and Deflated-Sharpe gating are implemented as claimed | **DSR: implemented correctly, wired incorrectly** (A1). **Walk-forward: the discipline is real; this run's fold plan is not** (A3). |

---

## 7. What I would do next, in order

1. **Add a positive control and make it the first gate of the suite.** Replay a hard-coded oracle
   ("hold the sign of the last 30 minutes") through `run_walk_forward` on the planted market. It must
   pass. Until it does, no other result from this harness means anything. This one change would have
   saved the entire run.
2. **Fix or suspend the DSR gate.** Either estimate trial Sharpes on a sample comparable to the graded
   one, or cluster correlated trials as the paper's Appendix 3 requires, or gate on something
   defensible (PSR against SR0 = 0 plus an explicit documented trial count). Recompute SR0 on the
   *existing* artifacts first — it is a two-line check and it reprices every past "failed" run.
3. **Fix the fold plan** in `scripts/falsify_engine.plan()` so the embargo sits *between* test windows,
   and add an assertion in `Backtest._replay` that `st.timestamp` is non-decreasing across the whole
   book, so this class of bug dies loudly instead of silently corrupting metrics.
4. **Reproduce the zero-duration trades** (B8) on a 3-day single-fold run with a trade dump, and assert
   `duration_s > 0` for every `ClosedTrade` in `book.book_close`.
5. **Resolve the §14 duration contradiction at the spec level**, not in code: either the signal bar
   moves up (5 or 15 minutes), or the SL gene range widens well past 3.5 × ATR, or the §14 band comes
   down. Right now the spec asks for something the spec forbids.
6. **Read `trend_direction`.** The cheapest experiment in this repo: gate every module's direction on
   `regime.trend_direction` — or at minimum forbid MEAN_REVERSION from firing against a non-zero
   `trend_direction` — and re-run the planted market. My measurement says that alone flips the sign of
   the mean-reversion book.
7. **Make the fitness harness evaluate the module it is parameterising**, or split the ParamSet so each
   module owns genes its own objective actually scores. A gene with no gradient is worse than a
   constant, because it *looks* optimised.
8. **Re-examine the ADX thresholds against a referent.** 25/20 are Wilder's (1978, *New Concepts in
   Technical Trading Systems*) and were "empirically tuned against this proxy" in phase 3 — tuned
   against what target? A threshold with a 49 % false-positive rate on noise needs either a different
   statistic or a different job.

*Source grading: Bailey & López de Prado (2014) and Moskowitz–Ooi–Pedersen (2012) are **academic** and
are correctly cited by the code; I could not re-verify them online in this session (the web-search
budget was exhausted), so I relied on the repo's own citations plus my own computation. Wilder (1978)
is a **historical practitioner source**, widely reproduced, with no peer-reviewed validation of the
20/25 thresholds. Every numeric claim in §2–§4 is my own computation from the repo's code or its
artifacts, not a citation.*

---

## 8. Against the builders' own diagnosis (written after reading GAP-P12D-31 and its links)

Read: `KNOWN_GAPS.md` GAP-P12D-31, GAP-P12D-32, GAP-P12D-33, GAP-P12D-34. Sections 0–7 above are
unchanged.

### 8.1 Where I AGREE (independently reached)

* **GAP-P12D-33 — the DSR gate is broken.** We converged from different directions on the same root
  cause: the trials (per-trade Sharpes of 5–15-trade holdouts) and the graded record (per-trade
  Sharpe over thousands of trades) are not draws from the same null, so `V[{SR_n}]` is estimation
  noise and SR0 is meaningless. Their numerical demonstration (2 near-identical trials ⇒ DSR 0.9979
  PASS; 180 honest trials ⇒ DSR 0.0000) is the *inversion* argument. Mine is the *magnitude*
  argument on this run's own recorded trials: SR0 = 0.617 / 0.649 / 2.430 per trade, i.e. an
  annualised hurdle of 19 / 21 / 77. Both are right and they reinforce each other.
* **§14 internal inconsistency.** Identical arithmetic, reached independently: `positive_months > 70 %`
  implies annualised Sharpe ≈ 1.82 and silently binds harder than the `> 1.5` row.
* **Exit geometry / horizon mismatch** (their hypothesis 3, and GAP-P12D-32's verified note). Agreed,
  and I have quantified it into a hard impossibility (§A2) rather than a mismatch.
* **GAP-0075 entry spam.** 1 425 326 signals vs 2 018 trades; the book's same-side dedup is the de
  facto position policy. Same observation.
* **`MARGINAL_ALPHA_PINNED` on every sizing.** Same observation; I add that the same is true of alpha
  decay and the entire Risk Monitor, and that none of it is disclosed in `fidelity_caveats` (§B7).
* **GAP-P12D-32's REFUTATION of the "synthetic is ~9× more volatile" claim.** I computed the same
  numbers independently (per-minute σ = 1.32 bp synthetic vs ~1.16–1.27 bp real) before reading it.
  That other agent's claim is wrong and the author's refutation is correct.
* **"Demote the regime from a gate to a weight, collapse to ≤3 states"** (listed as UNVERIFIED in
  GAP-P12D-32). My §B1 is the missing evidence for it: 48.8 % false-positive rate for STRONG_TREND on
  a pure random walk, and 47 % of the *null* market labelled strong-trend by the run's own labeller.

### 8.2 Where I DISAGREE

1. **GAP-P12D-31's headline premise is not established.** The title says "a market whose planted
   trend **its own fitness code finds easily**", evidenced by "80–90 of 100 random ParamSets
   profitable **on contiguous bars**". But evolution never sees contiguous bars: `evolve_fold` →
   `LabelledBarCache.history(instrument, regime, …)` hands `fitness.simulate_trades` the
   *regime-filtered, stitched* bar sequence, where adjacent "bars" can be days apart (§B4). The
   diagnostic was run on a different input than the production path uses, so it does not show what it
   is cited for. This matters because it is the premise that makes the whole result look paradoxical.
2. **"Two of three markets answered correctly."** No — the correct reading is that **all three
   answered uninformatively**, because `passed` was unreachable for any strategy on any market
   (§A1 + §A2). Recording it as 2/3 overstates the suite's health and, worse, it is exactly the shape
   of result that makes a broken scoreboard look like a working one. The owner's standing rule ("if
   planted fails, that is a finding, not a reason to tune the test") is the right instinct, but here
   the test was *already* untuned in a way that made the pre-registered answer unsatisfiable. That is
   not tuning the test to taste; it is fixing a test that cannot return the value it was asked for.
3. **GAP-P12D-32 treats "does realised cost drag match the trade count and sizes?" as unanswered.**
   It is answerable now and the answer is that the graded run charges **half** the declared cost: the
   harness re-implements the C8 model inline and drops the `spread/2` term that the fitness function
   applies (§B6). Any cost-drag reasoning on either side of that debate is currently comparing two
   different cost models.
4. **GAP-P12D-32's verified note calls the `max_holding_periods` mismatch "selection and execution
   disagree on horizon by ~60×".** It is worse and simpler than that: `grep -rn max_holding_periods
   --include=*.py` returns **three hits, all in `core/optimizer/`** — the gene spec, the dataclass
   field, and `fitness.py:126`. **No runtime path reads it at all.** It is not a 60× disagreement; the
   gene is unimplemented in the engine while still shaping selection.

### 8.3 What the builders have MISSED or assumed without checking

Ordered by what I think each is worth.

1. **The falsification run's own fold plan replays 23 % of the graded record backwards through the
   book (§A3).** Not in the ledger anywhere. The tell is already sitting in the artifact and was read
   past: `permuted` reports `rule_violations: ["min_hold"]` while `dev_paper.min_hold_seconds = 0`.
   `t.duration_s < 0` is the *only* way that line can appear. A negative-duration trade is a proof of
   a harness defect, and it was recorded as a strategy result. The equity curve, drawdown,
   positive-months and VaR-breach numbers quoted in GAP-P12D-31 are all computed over that corrupted
   series.
2. **79 % of the planted run's trades were held for zero seconds (§B8, §1).** GAP-P12D-31 quotes
   "profit factor 0.84, win rate 42.7 %" as evidence about the strategy. Both ratios are computed over
   a trade population in which 1598 of 2018 entries are `MOMENTUM_SCALP` trades with duration exactly
   0 s — recoverable from the report's own numbers by exact rational arithmetic, no rerun needed.
   Until that is explained, no ratio in that report means anything.
3. **`RegimeContext.trend_direction` is dead code, and it is 71–78 % accurate about the planted drift
   (§B2).** Not in the ledger. This inverts the framing of the whole investigation: the engine is not
   failing to *find* the edge — its regime layer finds it, computes it every 120 seconds, puts it in a
   frozen dataclass, ships it across the layer boundary, and no consumer reads the field. The
   conditional 8-minute forward return is +2.20 bp against 0.36 bp of friction. This is the cheapest
   high-value experiment available and nobody has run it.
4. **The actual mechanism of "near-independent of whether an edge exists" (§B3).** GAP-P12D-31 calls
   that independence "the finding" and then lists three hypotheses, none of which is the mechanism I
   measured: MEAN_REVERSION fires 6–9× more often than TREND, and its expectancy is 4–8× *more*
   negative on `planted` (−1.26 bp/trade) than on `null` (−0.30 bp/trade ≈ pure friction), while TREND
   is genuinely profitable on `planted` (+0.27 to +1.35 bp/trade). The trend book's gain and the
   counter-trend book's extra loss cancel. **The independence is not mysterious; it is arithmetic.**
   And note the direction: a market with *more* edge makes the engine lose *more* on its dominant
   module. Any fix that improves regime accuracy without fixing that asymmetry will move the result
   less than expected.
5. **Only 7 of 11 genes are both optimised and used (§B4 + §8.2 item 4).** `momentum_lookback`,
   `breakout_atr_threshold` and `mean_rev_zscore_entry` are used at runtime but *never enter*
   `simulate_trades`, so QIEA's rotation gate gets zero gradient on them — they hitchhike. Conversely
   `max_holding_periods` is scored but never used. GAP-0035 names the proxy-vs-engine mismatch
   generically; the specific consequence is that **the entry threshold of the module doing the damage
   in item 4 is an unoptimised random draw from [1.5, 2.5]**. This also undercuts GAP-P12D-34: a
   ±10 % parameter-plateau test is meaningless on a gene the objective never scores, so the plateau
   law must be built *after* the gene/objective coverage hole is closed, not before.
6. **The suite has no positive control (§A5).** This is the methodological root cause of a wasted run.
   Given A1 and A2, a single oracle replay ("hold the sign of the last 30 minutes") through
   `run_walk_forward` would have shown in minutes that `passed` is unreachable. A falsification suite
   that can only ever report "fail" is not a falsification suite. I would make this the first item on
   the remediation list, above every strategy question, because it is the thing that decides whether
   any future answer can be believed.
7. **Nobody has quantified how easy the planted market is (§2).** GAP-P12D-31 says the edge is one
   "the fitness harness captures easily". It is far stronger than that: a one-line rule earns an
   annualised Sharpe of **30–86** net of the declared friction, robustly across lookbacks from 15 to
   120 minutes. That reframes the severity: the engine is not slightly short of a subtle edge, it is
   converting a ~+70 Sharpe opportunity into −0.65. A loss of that size against that opportunity
   almost has to be a structural defect (items 1–5), not a parameterisation problem.
8. **This run never exercised the fix it was built to validate (§B9).** `scripts/falsify_engine.py`
   uses `train_days = 60`, so `window_start = max(train_start, train_end − 730 d)` collapses to
   60 days and `fitness_span_days = 730` — the whole content of the GAP-P12D-29 v2.18 ruling — had no
   effect. GAP-P12D-31 says "It does NOT invalidate the GAP-P12D-29 fix"; true, but only because the
   run did not test it, which is a different and less comfortable statement.
9. **Half the strategy set is degenerate in these markets (§A4), unremarked.** `MOMENTUM_SCALP`'s
   velocity gate reads a 20 s/10 s quantisation artifact; `PAIR_DIVERGENCE` trades two *independently
   generated* series, so every pair trade is a spurious correlation (and 0.40 on 50 samples is far too
   weak a floor for a gate evaluated ~1.4 M times — a live-fire risk, not just a synthetic one); TSMOM
   is starved by the 60-day seed window and then truncated at the harness's hard 48 h `max_hold_s`,
   giving 13 trades in two years. Conclusions about "the engine" from this run are really conclusions
   about a three-module subset.
10. **The DSR gate is hardest exactly where the edge is real (§A1, point 2).** GAP-P12D-33 documents
    the inversion with respect to the *number* of trials. The sharper problem is with respect to their
    *dispersion*: in `planted`, real edge lifts and spreads the trial Sharpes (sd 0.93 vs 0.25), so
    SR0 quadruples to 2.43 and the hurdle rises to ≈ 76. A selection-bias correction whose threshold
    rises with genuine signal cannot ever certify signal. Whichever remedy is chosen — (a)
    commensurate trials or (b) PBO/CSCV — this property should be stated explicitly in the ratification
    note, because it is the reason the current gate is not merely mis-calibrated but structurally
    unable to do its job.
11. **A process observation.** GAP-P12D-31's evidence list is drawn almost entirely from event
    *counts* in `REPLAY_LOG_SUMMARY`. Four of the findings above (the backwards folds, the
    zero-duration trades, the halved cost model, the dead `trend_direction`) are invisible in counts
    and visible in ten minutes of arithmetic on the report JSON and three greps. The instinct to reach
    for the log summary is the same instinct that produced `ReplayEventLogger` — but the graded
    artifact, not the log, is where the falsifying evidence was. Worth adding to the audit brief: *the
    report's own numbers must be reconciled arithmetically before any narrative is written about them.*
