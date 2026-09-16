# Code-grounded diagnosis of the falsification failure, and what the outside evidence says to build instead

**Date:** 2026-09-16 · **Scope:** GAP-P12D-31 · **Evidence:** `data/validation/falsification/20260915T231127Z` (25 folds, 2014-03-07 → 2016-04-01, EUR_USD + USD_JPY), the source at HEAD, and six read-only experiments run for this report.
**Status of this document:** a finder's report (CLAUDE.md audit law — a subordinate is a finder, never a clearer). Nothing here was applied. No engine code, config, spec or ledger file was modified.

---

## 0. Verdict in one paragraph

The engine does not fail because its optimiser is weak, because its costs are too high, or because its trades are too short. It fails because **the layer the whole architecture is built around — the NVMA regime label — carries essentially no information about the phenomenon it is supposed to detect**, and because **the optimiser's objective function is a different trading system from the one that trades**. On the planted market the regime label recovers **3.7 %** of the available directional signal for `STRONG_TREND_UP` and **the wrong sign** for `STRONG_TREND_DOWN` (§1.3). The optimiser's own rule, measured directly, *does* capture the planted edge (+1.28 pips/trade, 22 of 24 random parameter sets profitable, §1.4) — and that rule is one of six live modules and is scored on 8 of 11 genes. Meanwhile the module that is *not* scored and is gated only by the uninformative label — mean reversion — trades 8.7× more often than the trend rule at **−2.17 pips/trade with a 9.3 % win rate** (§1.5, §1.6) and eats the portfolio. Because there is no position policy, which of 1,425,326 signals becomes one of 2,018 trades is decided by a dedup branch in the backtest book (§1.7). Two harness defects (a 7-day backward clock jump at every fold boundary, and a cost model that silently omits the spread) corrupt the grade on top (§1.9).

**Two things cannot be repaired and must be replaced:** (a) the regime engine as a *sovereign gate and parameter selector*; (b) the stateless signal→order path. Both replacements are well-documented in the literature and in one open-source retail engine (§2, §3).

---

# HALF 1 — Mechanical diagnosis

## 1.1 What the experiment actually says

From the three report files in the run directory:

| | trades | annual Sharpe | profit factor | win rate | avg trade duration¹ | positive months | max DD | Deflated Sharpe |
|---|---|---|---|---|---|---|---|---|
| **planted** (edge present) | 2,018 | **−0.648** | 0.837 | 42.7 % | 477.5 s | 48 % | 1.82 % | 0.0 |
| **null** (no edge) | 1,864 | −0.905 | 0.827 | 38.6 % | 745.2 s | 28 % | 0.35 % | 0.0 |
| **permuted** (edge destroyed) | 2,111 | −0.489 | 0.889 | 37.7 % | 620.8 s | 28 % | 0.38 % | 0.0 |

¹ `avg_trade_duration_s` excludes TSMOM and MOMENTUM_SCALP by the §14 carve-outs (`tests/backtest/metrics.py:19`). `scalp_avg_duration_s = 0.0` on all three markets — **MOMENTUM_SCALP never traded at all**.

The three markets are separated by 0.42 Sharpe and the market *with* the edge is not the best of the three. Realised trading is statistically independent of whether an edge exists.

**How large is the planted edge?** From `tests/backtest/synthetic_market.py:66-84` with `MarketSpec` defaults: tick 20 s, 4,320 ticks per weekday, `daily_vol = 0.005` ⇒ σ_step = 7.607 × 10⁻⁵; `drift_sigma = 0.15` ⇒ every step inside an episode carries ±1.141 × 10⁻⁵ of drift, and the episode generator covers the *entire* series (`k += length` until `k ≥ n`). Reconstructing the generator deterministically: **5,247 episodes, mean length 149.3 minutes, median 149.7 minutes.**

A sign-oracle earns 0.15 σ per step at 4,320 steps/day: **daily Sharpe 9.86, annualised ≈ 157.** This is not a marginal edge the engine narrowly missed. It is roughly 100× the largest Sharpe ever claimed for a real strategy, and the engine converted it into −0.65.

---

## 1.2 Reading order of the causes

Ordered by contribution, each with the file:line evidence and a bug/design-choice classification.

| # | Cause | Classification | Evidence |
|---|---|---|---|
| 1 | Regime label carries ~no information; it is nonetheless the sovereign gate, the parameter key, and a sizing factor | **design choice, wrong for the objective** | §1.3 |
| 2 | Optimiser scores a different system than the one that trades | **design choice, wrong** (already logged as GAP-0035) | §1.4 |
| 3 | The unscored, uninformatively-gated mean-reversion module dominates the trade set and has a 9.3 % win rate | **consequence of 1 + 2** | §1.5, §1.6 |
| 4 | No position policy; the book's same-side dedup *is* the policy | **design gap** (GAP-0075) | §1.7 |
| 5 | Evolved parameters almost never reach the fast loop | **design interaction bug** | §1.8 |
| 6a | Harness replays the clock **backwards 7 days** at every fold boundary | **bug** | §1.9 |
| 6b | Backtest book omits the spread from friction, violating master §5 C8 | **bug** | §1.9 |

---

## 1.3 CAUSE 1 — the regime label is noise (the dominant cause)

### The measurement

The planted market's drift is deterministic and reconstructible. I rebuilt the per-step drift from the same generator, aggregated it to the 1-minute bars in the run's own label cache (`data/validation/falsification/20260915T231127Z/labels/synthetic-planted/EUR_USD/2014.csv.gz`, 363,359 bars), and grouped by the label NVMA assigned:

| regime | bars | mean drift (in step-σ) | P(drift > 0) | fraction of the signal recovered |
|---|---|---|---|---|
| ILLIQUID | 142,660 | −0.0049 | 0.484 | — |
| STRONG_TREND_DOWN | 77,571 | **+0.0033** | **0.511** | **−2.2 % (wrong sign)** |
| STRONG_TREND_UP | 45,520 | +0.0055 | 0.518 | **+3.7 %** |
| RANGING_TIGHT | 34,140 | +0.0034 | 0.511 | — |
| BREAKOUT_IMMINENT | 20,372 | +0.0035 | 0.512 | — |
| WEAK_TREND_DOWN | 15,038 | +0.0039 | 0.513 | — |
| RANGING_WIDE | 11,868 | +0.0043 | 0.514 | — |
| WEAK_TREND_UP | 11,622 | +0.0050 | 0.517 | — |
| MEAN_REVERTING | 3,600 | −0.0107 | 0.464 | — |
| *baseline (all bars)* | | 0.000 | 0.501 | |

True drift magnitude is **0.15 step-σ**. `STRONG_TREND_UP` reads +0.0055 — 3.7 % of it. `STRONG_TREND_DOWN` reads **+0.0033, i.e. positive drift under a "strong down-trend" label**. The two strongest directional labels in the taxonomy differ by 0.0022 σ: **1.5 % of the signal they are supposed to separate.** A `RANGING_TIGHT` bar and a `STRONG_TREND_DOWN` bar have statistically identical forward drift.

This is not a tuning problem. It is a time-base problem.

### Why the label is noise — the arithmetic

`NVMAEngine.window()` (`core/regime/nvma.py:373`) builds `RegimeInputWindow(maxlen=cfg.max_lookback)` and `observe()` pushes **one tick** per call. Every NVMA indicator is therefore computed on a **tick-count** window, not a time window:

- `adx_proxy(mids, cfg.adx_period)` with `adx_period = 14` (`config/system_config.yaml:18`) — 14 ticks ≈ **4.7 minutes** at 20 s ticks.
- `mean_abs_delta(mids, 14/50/200)` — 4.7 / 16.7 / 66.7 minutes.
- `hurst_exponent(mids, 200)` — 66.7 minutes.

The directional index that decides UP vs DOWN sees 14 steps. Cumulative drift over 14 steps = 14 × 0.15 σ = 2.1 σ; cumulative noise = √14 σ = 3.74 σ. **t = 0.56.** The gate is structurally incapable of seeing the drift; it is reading noise and labelling it.

Two further consequences fall out of the same fact:

**(a) The label churns.** Contiguous-run census on the same 363,359 bars:

| regime | contiguous runs | median run (min) | mean | p90 | max |
|---|---|---|---|---|---|
| STRONG_TREND_DOWN | 11,989 | **4** | 6.5 | 14 | 50 |
| STRONG_TREND_UP | 9,827 | **4** | 4.6 | 10 | 40 |
| RANGING_TIGHT | 10,311 | **2** | 3.3 | 6 | 24 |
| BREAKOUT_IMMINENT | 6,920 | **2** | 2.9 | 6 | 14 |
| WEAK_TREND_UP/DOWN | 11,626 | **2** | 2.3 | 4 | 12 |

The median regime episode is **2–4 minutes** against a phenomenon that lasts **149 minutes**. The label changes ~37 times inside one planted trend. The run's own log confirms it at scale: `REGIME_SHIFT` fired **245,434** times, i.e. the regime changed on roughly **one third of all 120-second classification cycles**.

**(b) The churn silently shrinks every position.** The Governor's regime factor is `regime.regime_stability_score * regime.confidence` (`core/governor/capital_governor.py:271`). A sampled `SIZED` record from the run:

```json
{"conviction": 0.810, "liquidity": 0.8, "correlation": 1.0, "regime": 0.141,
 "marginal_alpha": 1.0, "marginal_alpha_pinned": true, "vol_norm": 1.0, "taper": 1.0,
 "base_unit_usd": 1000.0}   →  size_units 91.23
```

`regime = 0.141` is the stability tracker reporting that ~3 of the last 20 classifications agreed. Position sizes are being cut to 14 % of intent by an instability that is an artefact of the lookback, not a property of the market. (`MARGINAL_ALPHA_PINNED` fired on all 1,425,326 sizings — the C6 term never varied either, so sizing is effectively `conviction × 0.8 × regime_churn`.)

### Why this is cause #1

The regime label is not an advisory input. Per master §4 it is *the sovereign gatekeeper*, and in code it does four separate jobs:

1. **Module routing** — `AGON._module_gate` (`core/signals/agon.py:245-263`) decides which of six strategies may fire purely from regime-set membership.
2. **Master veto** — `regime.tradeable` (`agon.py:192`); `DISCARD_VETOED_REGIME` fired 2,221,512 times, ~50 % of ticks.
3. **Parameter selection** — `self.params.get_active(ctx.regime)` (`tests/integration/paper_loop.py:125`); a different parameter set every few minutes.
4. **Sizing** — the 0.141 factor above.

Four load-bearing decisions, all keyed on a variable whose measured mutual information with the tradeable phenomenon is ~0. **A gate that cannot discriminate cannot protect the modules it gates**, which is exactly what §1.5 shows happening.

---

## 1.4 CAUSE 2 — the optimiser scores a different system from the one that trades

This is logged as **GAP-0035** ("v1 harness doesn't select-for momentum/breakout/zscore genes"). The falsification run lets it be quantified.

### The gene ledger

`GENE_SPECS` (`core/optimizer/param_types.py:17-29`) declares 11 genes. `simulate_trades` (`core/optimizer/fitness.py:82-160`) — the *entire* fitness evaluation — reads 8 of them:

| gene | scored by fitness? | used by the engine? | who uses it |
|---|---|---|---|
| `ema_fast` | ✅ | ✅ | `_trend` (agon.py:368), `_momentum_scalp` (agon.py:441) |
| `ema_slow` | ✅ | ✅ | `_trend` |
| `rsi_period`, `rsi_overbought`, `rsi_oversold` | ✅ | ✅ | `_trend`, `_mean_reversion` |
| `atr_multiplier_sl` | ✅ | ✅ | every module's stop (agon.py:291) |
| `atr_multiplier_tp` | ✅ | ✅ | every module's target (agon.py:282) |
| `max_holding_periods` | ✅ | ❌ **never** | only `fitness.py:126`; `grep` finds no other consumer |
| `momentum_lookback` | ❌ **never** | ✅ | `_breakout` channel width (agon.py:386) |
| `breakout_atr_threshold` | ❌ **never** | ✅ | `_breakout` trigger (agon.py:394) |
| `mean_rev_zscore_entry` | ❌ **never** | ✅ | `_mean_reversion` (agon.py:413), `_pair_divergence` (agon.py:468) |

**Three genes that drive two live modules are never scored by any objective.** Their values are whatever the Q-bit collapse happened to produce and the rotation gate drifted toward *for unrelated reasons* — they are literally random draws that the engine then trades on. One gene that *is* scored is never used, so part of the measured fitness comes from an exit the engine does not possess.

More fundamentally: `simulate_trades` is a dual-EMA-cross system with ATR SL/TP and a bar-count hold limit. That is **one of six live modules**. The other five — breakout, mean reversion, momentum scalp, pair divergence, TSMOM — are never evaluated by the function that selects the parameters they run on.

### The optimiser is not the broken part — measured

I ran the *real* `core.optimizer.fitness.simulate_trades` over the run's own labelled bars for planted EUR_USD 2014, with 24 randomly drawn ParamSets:

| series | positive-expectancy sets | mean fitness |
|---|---|---|
| stitched (only `STRONG_TREND_UP` bars, what QIEA reads) | 19 / 24 | 0.137 |
| contiguous raw tape (all bars) | **22 / 24** | **0.358** |

And an exit-reason census over 12 more parameter sets (120,000 bars):

| configuration | trades | mean E/trade | median duration | positive sets |
|---|---|---|---|---|
| with `max_holding_periods` (fitness as written) | 4,108 | **+0.943 pips** | 8 min | 11 / 12 |
| without it (the engine's actual configuration) | 4,023 | **+1.418 pips** | 8 min | **12 / 12** |

**The optimiser's own rule captures the planted edge robustly, with 8-minute trades, net of costs, at almost any parameter values.** Whatever is wrong, it is not the fitness function's ability to find the edge — it is that the thing it found never reaches the tape.

> **Honest negative (and it surprised me):** I expected `LabelledBarCache.history` (`tests/backtest/regime_labels.py:165-181`), which concatenates only the target-regime bars into a time-discontiguous series that EMA/RSI/ATR are then computed across as if contiguous, to be a major distortion. It is a real correctness defect — indicators are computed across ~9,827 disjoint fragments averaging 4.6 bars each — but the measurement says the stitched world is *harder*, not easier (mean fitness 0.137 vs 0.358). It flatters nothing. Record it as a defect; do not blame it for the loss.

---

## 1.5 CAUSE 3 — the unscored module wins the trade count and loses the money

### Ablation: the same rule with and without the regime gate

Same dual-EMA rule, same tape, 12 random parameter sets, entries permitted only when the bar's own NVMA label is in `_TREND_REGIMES`:

| | total trades | mean E/trade | positive sets |
|---|---|---|---|
| ungated | 3,677 | **+1.284 pips** | 11 / 12 |
| regime-gated (AGON's rule) | 1,995 | **+1.271 pips** | 11 / 12 |
| **AGON's mean-reversion rule** (ranging regimes, Bollinger-z fade, same ATR SL/TP) | **17,282** | **−2.172 pips** | **0 / 12** |

Read those three rows together. The regime gate **halves the trend rule's sample and changes its edge by 0.013 pips** — exactly what a zero-information filter does. It neither helps nor hurts; it just throws away half the good trades. And the module it routes to the *other* half of the tape trades **8.7× more often** than the gated trend rule, at a negative expectancy, on a gene nobody optimised.

The arithmetic is decisive: 17,282 × (−2.172) = −37,536 pips against 1,995 × (+1.271) = +2,536 pips. The loser out-trades the winner by an order of magnitude.

### Confirmation from the real composed loop

To remove every doubt that this is an artefact of my clones, I ran the **actual production wiring** — `build_paper_loop` (`tests/integration/paper_loop.py:202`) with the real `MarketStateFactory`, `NVMAEngine`, `ParamLibrary`, `AGON`, `CapitalGovernor` and `tests/backtest/book.PositionModel` — over 45 days of the planted market on EUR_USD, with one fixed mid-range ParamSet promoted for every tradeable regime (so parameter evolution is held constant and only the architecture is under test):

```
ticks=140,400  orders_generated=522  booked_trades=161
ORDERS by strategy: BREAKOUT 210, TREND 162, MEAN_REVERSION 150

strategy            trades      net USD   USD/trade   win%   medDur(min)
BREAKOUT                65       0.6351     0.00977   73.8          7.7
TREND                   53       0.7291     0.01376   64.2          6.7
MEAN_REVERSION          43      -0.8573    -0.01994    9.3          5.7
TOTAL realised 0.5069 USD over 161 trades
AGON skips: {'vetoed_regime': 70,428, 'subthreshold': 183}
NVMA vetoes: {'LOW_CONFIDENCE': 1,758, 'NO_PARAMS_FOR_REGIME': 164, 'REGIME_WARMING': 54}
```

**MEAN_REVERSION wins 9.3 % of its trades** and loses 1.45× per trade what TREND makes per trade, wiping out 63 % of the other two modules' combined gain. Net result over 45 days on a market containing a ~157-Sharpe oracle edge: **+0.5069 USD on a 10,000 USD NAV — +0.005 %.**

That is the architecture's actual conversion efficiency.

### Is it the exit geometry? No — honest negative

`ParamSet.__post_init__` (`core/optimizer/param_types.py:61`) *requires* `atr_multiplier_tp > atr_multiplier_sl` for every module, and `AGON._pipeline` (`agon.py:282`) applies that geometry to mean-reversion trades too. That looked like a structural bug — a mean-reverting entry wants a *near* target and a *far* stop, and the contract forbids it. I tested 18 combinations, including six the ParamSet contract refuses:

| z entry | SL×ATR | TP×ATR | legal today? | trades | E/trade (pips) | target-hit % |
|---|---|---|---|---|---|---|
| 1.5 | 1.2 | 3.5 | LEGAL | 2,597 | −1.485 | 15.5 |
| 1.5 | 3.0 | 3.2 | LEGAL | 2,097 | −2.916 | 24.6 |
| 1.5 | 3.0 | 1.0 | refused | 2,660 | −2.213 | 50.5 |
| 1.5 | 2.0 | 0.8 | refused | 2,900 | −1.606 | 52.2 |
| 2.5 | 1.2 | 3.5 | LEGAL | 504 | −1.653 | 13.1 |
| 2.5 | 2.0 | 0.8 | refused | 506 | −1.726 | 49.4 |

Every configuration loses, −1.49 to −3.12 pips. Reversing the geometry lifts the hit rate from ~15 % to ~50 % and still loses. **The mean-reversion signal is simply on the wrong side of a trending market**, and the regime gate that exists to prevent exactly this cannot do so because its label is uninformative (§1.3). The `tp > sl` constraint remains a real design defect for convergent strategies — it just is not what is costing the money here.

---

## 1.6 Why "the trades are too short" is the wrong diagnosis

The obvious story — 8-minute trades cannot hold a 149-minute trend — is intuitive and **the data contradicts it**. The optimiser's rule also holds for a median of 8 minutes (§1.4) and earns +1.42 pips/trade. An 8-minute hold captures 24 steps × 1.141 × 10⁻⁵ = 2.74 × 10⁻⁴ ≈ **3.0 pips** of drift when it is on the right side, against 0.4–0.84 pips of round-trip friction. Short trades are profitable *on this tape* provided the direction is right.

The duration does have a mechanical explanation worth recording. At 20 s ticks, σ per 1-minute bar ≈ 1.32 × 10⁻⁴; ATR(14) of those bars ≈ 1.5–2 × 10⁻⁴ in price. A 2 × ATR stop is ≈ 3–4 × 10⁻⁴, and the median first-passage time of a driftless walk to ±b is (b/0.674 σ₁ₘᵢₙ)² ≈ **8–12 minutes**. The observed 477.5 s mean and 8-minute median are exactly what the ATR-on-1-minute-bars geometry implies. **The stop distance *is* the holding period** (§2.1) — but on this synthetic tape, with cheap costs, that holding period still pays. On real data at realistic spreads it will not (§2.3).

So: duration is a *design flaw that will bite on real data* (and the external evidence in §2.1 is emphatic about it), but it is **not** what made the falsification run lose.

---

## 1.7 CAUSE 4 — there is no position policy; a dedup branch is the policy

From the run's `REPLAY_LOG_SUMMARY` (planted):

| event | count |
|---|---|
| `DISCARD_VETOED_REGIME` | 2,221,512 |
| `SIGNAL_EMITTED` | **1,425,326** |
| `SIZED` | **1,425,326** |
| … booked trades | **2,018** |

`orders_zeroed` was 0 in my controlled run: the Governor sized *every* signal to a non-zero order. **1,425,326 orders produced 2,018 positions.** The selector is four lines in the backtest book:

```python
# tests/backtest/book.py:96-100
existing = book.open_by_inst.get(order.instrument)
if existing is not None:
    if existing.direction == order.direction:
        return                                   # same-side dedup (GAP-0075)
    book.book_close(self.close_at(existing, order.entry_price, ...,"reverse", book), ...)
```

Nothing in `core/` holds a *desired position*. `AGON.generate` is a pure function of the current tick and the current window; `CapitalGovernor.allocate` is a pure function of the signal and the portfolio snapshot. No layer asks "what am I already holding, and how far is that from what I want?". The engine has exactly two position states per instrument — flat, or ±1 unit whose size was frozen at whatever the churning regime factor happened to be at entry.

In the full run this is compounded by TSMOM: `_module_gate` returns `True` for TSMOM in **every** tradeable regime (`agon.py:261-262`) and `_tsmom` emits whenever the three daily lookback signs do not cancel — conviction 0.67 or 1.00, both above the 0.45 discard. Once its 260-day history is warm, TSMOM emits on nearly every tick. That is the source of the 1.43 M signals, and it means TSMOM holds a near-permanent position on every instrument, which the other five modules can only act on by *reversing* it (and which starves parameter promotion, §1.8).

The literature has a precise name and a precise price for this pattern (§2.2): it is Gârleanu–Pedersen's **"Markowitz strategy"** — recompute the desired position from scratch every period and go there — and in their own commodity-futures data it converts a **+0.83 gross Sharpe into −9.84 net**.

---

## 1.8 CAUSE 5 — evolved parameters almost never reach the fast loop

| event | planted | null | permuted |
|---|---|---|---|
| `PARAM_STAGED` | 91 | 74 | 72 |
| `PARAM_PROMOTED` | **39** | 32 | 21 |
| `PARAM_PROMOTION_STALLED` | **11,638** | 12,495 | 12,363 |
| `EVOLUTION_REJECTED_OOS` | 247 | 310 | 317 |

25 folds × 7 tradeable regimes = 175 opportunities; 91 champions were staged and **39 promoted (22 %)**. The C2 safety rule — never promote while any position is open (`core/optimizer/param_library.py`, wired through `Backtest.open_position_count`, `harness.py:113-115`) — is correct in isolation, but it interacts fatally with §1.7: TSMOM holds a position essentially always, so the book is essentially never flat at a boundary. **The safety rule and the always-on module together make the optimiser mostly decorative.** This is a design interaction, not a bug in either part.

---

## 1.9 CAUSE 6 — two harness defects that corrupt the grade

### 6a. The clock runs backwards 7 days at every fold boundary — **bug**

`scripts/falsify_engine.py:41-49` builds contiguous 30-day test windows with `train_end = test_start − EMBARGO` (7 days, `tests/backtest/oos_plan.py:28`):

```
fold 0: train_end=2014-03-07  test=[2014-03-14, 2014-04-13)  warmup=[2014-03-07, 2014-03-14)
fold 1: train_end=2014-04-06  test=[2014-04-13, 2014-05-13)  warmup=[2014-04-06, 2014-04-13)
```

`oos_runner.py:108` then builds `warmup_states = stream(f.train_end, f.test_start)` and `harness.py:128-130` replays it. **Fold 1's warmup window is the last 7 of fold 0's 30 graded days.** At each of the 24 fold boundaries the tick clock jumps backward 7 days and those days are replayed a second time. Consequences, all real:

- `Backtest._tick` manages open positions on every warmup tick (`harness.py:140-143`), so any position open at a boundary is marked and possibly stopped out against **7-day-stale prices**.
- `(st.timestamp − pos.entry_ts)` goes negative, so `max_hold` is suspended for the duration. **Corroborated by the artifact itself: `tsmom_avg_duration_s = 197,739 s = 54.9 h`, which exceeds the 48 h `max_hold_s` cap and is impossible under a forward-only clock.**
- `book.equity` (`harness.py:166-169`) gains out-of-order dates, and `_returns_from_equity` differences that series to produce the annual Sharpe the verdict turns on.

Note the ratified plan (`oos_plan.plan_folds`, calendar-year test windows with `train_end = 1 January`) does **not** have this overlap. The defect is specific to `scripts/falsify_engine.py::plan`, plus a missing invariant: `Fold.__post_init__` (`walk_forward.py:23-29`) checks intra-fold ordering only, and nothing checks that fold *k*'s warmup does not reach back into fold *k−1*'s test window.

### 6b. The book charges less than the C8 cost model — **bug**, and it violates master §5 C8

```python
# core/optimizer/costs.py:32-36  — the declared C8 model
def per_side_cost(self, spread): return spread / 2.0 + self.commission_per_side + self.slippage_per_side

# tests/backtest/book.py:142-143 — what the backtest actually charges
friction = Decimal(str(cost.slippage_per_side * 2 + cost.commission_per_side * 2)) * pos.size_units
```

The spread term is missing, and fills are taken at `order.entry_price` = `state.mid` with closes at the stop/target/mid — **there is no bid/ask anywhere in the book**. Master §5 C8 is explicit that the two must be "unit-tested identical in both places"; `book.py`'s own docstring claims "minus the instrument's OWN C8 friction". Magnitudes:

| tape | C8 round trip | book round trip | book charges |
|---|---|---|---|
| synthetic (spread = 0.44 pip) | 8.4 × 10⁻⁵ | 4.0 × 10⁻⁵ | **48 %** |
| real EUR/USD (spread ≈ 1 pip) | 1.4 × 10⁻⁴ | 4.0 × 10⁻⁵ | **29 %** |

This makes the backtest **optimistic**, so it is not a cause of the loss — but it means every §14 number this harness produces is flattered, by roughly 0.3–0.6 Sharpe units at the observed turnover (§2.3).

---

## 1.10 The turnover arithmetic (for the record)

2,018 trades ÷ 2.07 years ÷ 2 instruments = **487 round trips per instrument-year ≈ 1.93 per day**. Annualised vol of the synthetic tape = 0.005 × √252 = 7.94 %.

| cost assumption | round trip | annual drag | in Sharpe units |
|---|---|---|---|
| book as written (slippage only) | 0.36 bp | 1.8 % | 0.22 |
| declared C8 on the synthetic spread | 0.76 bp | 3.7 % | 0.47 |
| declared C8 on a real 1-pip EUR/USD spread | 1.27 bp | 6.2 % | **0.78** |
| realistic retail round trip (≈1.5 pips all-in) | 13.6 bp | 66 % | **8.3** |

**Honest negative: costs did not cause this loss** — on the synthetic tape they are worth 0.2–0.5 Sharpe against an observed −0.65 with a +157 oracle available. But the last row is the warning for real data: at this turnover and realistic retail friction, the strategy is unviable by an order of magnitude before any signal question is asked. Carver's published cost budget is **0.13 Sharpe units** (§2.3); this engine is spending 6–60× that.

---

## 1.11 Two attribution limits to state honestly

- The run's `per_regime` is `{}` and it has no `per_strategy` block. Those were added *after* this run (GAP-P12D-31 closure, ACIS-09 v1.6). The strategy attribution in §1.5 therefore comes from my own 45-day run of the real composed loop, not from the graded artifact. **A short re-run with the new attribution should be the first confirmation step** — and per §1.5 it should show mean reversion as the largest single loss bucket.
- My 45-day run is EUR_USD only, 45 days, and too short for TSMOM (260-day history) or MOMENTUM_SCALP to fire. It isolates the TREND / BREAKOUT / MEAN_REVERSION triangle cleanly; it says nothing directly about TSMOM's contribution in the full run.

---

# HALF 2 — What the outside evidence says

Three parallel research passes were run for this report. Grades: **(a)** peer-reviewed, **(b)** credible practitioner with a published book or verifiable public record, **(c)** unverifiable / marketing / folklore. Where a primary PDF could not be retrieved this is stated.

## 2.1 Exits: a stop is a holding-period choice, not a risk control

- **Kaminski & Lo, "When Do Stop-Loss Rules Stop Losses?", *Journal of Financial Markets* 18 (2014) 234–254 — (a).** The controlling result: *"under the Random Walk Hypothesis, simple 0/1 stop-loss rules always decrease a strategy's expected return, but in the presence of momentum, stop-loss rules can add value."* Empirically, stop-loss rules added 50–100 bp/month **during stop-out periods** on monthly US equity data 1950–2004, via a "stopping premium" that exists only when conditional drift after the trigger is negative. **A stop tripped by bar-level noise is by construction the random-walk case — a pure expected-return tax.**
- **Clare, Seaton, Smith & Thomas, *Journal of Asset Management* 14 (2013) 182–194 — (a)** (publisher abstract; PDF would not extract): popular stop-loss rules **do not add value** on the S&P 500, and **lower-frequency (monthly) decision rules beat higher-frequency ones**. The exit that works is the slow signal reversing.
- **Lei & Li, *Financial Services Review* 18 (2009) 23–51 — (a):** fixed and trailing stops "neither reduce nor increase investors' losses relative to buy-and-hold"; the value, where any exists, is risk reduction, not return.
- **Han, Zhou & Zhu (SSRN 2407199, 2016) — (a):** a **10 % stop** (multi-week distance) on momentum cuts the worst month from −49.8 % to −11.4 % and lifts Sharpe 0.165 → 0.399. Note the distance and the regime condition.
- **Carver, "What is the right way to set stop losses?" (qoppac, 2020) — (b).** Stop distance = X × **annualised volatility**, and his published X → trades/year map *is* the equivalence argument: X = 0.025 → 97.5 trades/yr (~2.6-day holds); X = 0.5 → 5.4/yr (~9 weeks); X = 1.0 → 1.7/yr (~7 months). *"A trailing stop is a trend-following rule, and X is its speed parameter."* He reports his own stop-based trades last **6 months to a year**.
- **Carr & López de Prado, "Determining Optimal Trading Rules without Backtesting" (arXiv:1408.1159) — (a):** profit-take/stop pairs are calibrated from an OU process indexed by **half-life**; structured optima exist only for sufficiently mean-reverting processes and **there is no stable optimum as the process approaches a random walk.** An exit threshold is only well-defined relative to the half-life of the signal that generated the trade.
- **Take-profits.** Be blunt: **there is no peer-reviewed experiment showing a fixed take-profit improving a trend system's Sharpe out-of-sample.** The evidence is structural and indirect — Lempérière/Deremble/Seager/Potters/Bouchaud, "Two centuries of trend following" (arXiv:1404.3274) **(a)**, t ≈ 5 since 1960 and ≈ 10 since 1800 after removing market drift, with the payoff generated by letting winners run and shorter trends having "significantly withered"; Man AHL, "Trend-Following: A Different Point of Skew" **(b)**, "small losses, followed by large gains". With published trend hit rates of 30–45 %, a cap on the right tail removes the part that pays for the losses. Treat "fixed TPs destroy skew" as well-motivated theory plus strong indirect evidence, **not** a cited experimental result.

**Derived arithmetic, EUR/USD-like (σ_annual ≈ 7 %):** daily σ = 44.1 bp; 1-minute σ = 1.16 bp; ATR(14) on 1-minute bars ≈ 1.5–2.5 bp. A 2 × ATR stop ≈ 4 bp = 0.09 daily σ = **X ≈ 0.006 — five times tighter than the tightest stop Carver even tabulates.** Median time to touch on pure noise: **26 minutes**. Probability of being stopped out inside a 4-hour hold with zero drift: **2Φ(−4/18) = 82 %**. To keep that below 25 % you need **≈ 20.7 bp ≈ 10–12 × the 1-minute ATR ≈ 0.47 daily σ**.

## 2.2 Signal → position: nothing credible uses a stateless threshold

- **Moskowitz, Ooi & Pedersen (2012), *JFE* 104(2) 228–250 — (a).** The academic baseline is a **binary** signal with **continuous volatility scaling**: ex-ante variance with a 60-day centre of mass (δ ≈ 0.9836), position = 40 % / σ_{t−1}. Continuity comes from 1/σ, not from signal strength. Best cells: 9–12 month lookback, 1–3 month hold.
- **Gârleanu & Pedersen (2013), "Dynamic Trading with Predictable Returns and Transaction Costs", *Journal of Finance* 68(6) 2309–2340 — (a). The single most relevant source.** Optimal policy: `x_t = (1 − a/λ)·x_{t−1} + (a/λ)·aim_t` — the held position is an exponentially weighted average of past aim portfolios, with each signal shrunk by its own alpha-decay speed, `aim_t = (γΣ)⁻¹B·(f^k_t /(1+φ_k a/γ))`. Their Table II, commodity futures:

  | strategy | gross SR | net SR (base costs) |
  |---|---|---|
  | Markowitz — recompute each period and go there | 0.83 | **−9.84** |
  | Dynamic optimal (aim + partial adjustment) | 0.62 | **0.58** |
  | Best static partial adjustment (3–4 %/day) | 0.58–0.60 | 0.46 |
  | Static, 10 %/day toward Markowitz | 0.63 | −0.41 |

  **This is the named price of ACIS's current design.** *Derived (not theirs):* a 5 %/day adjustment rate is an EWMA half-life of ~13.5 days; on 1-minute bars the equivalent per-bar rate is 1 − 0.95^(1/1440) ≈ **0.0036 % of the gap per bar** — a full re-decision per bar is roughly four orders of magnitude too fast.
- **No-trade regions — (a), settled since 1976.** Magill & Constantinides (1976), Constantinides (1986), Davis & Norman (1990); synthesis verified in Gerhold, Guasoni, Muhle-Karbe & Schachermayer (arXiv:1207.7330 §2): *"optimal portfolios entail a no-trade region… trading should merely take place at its boundaries. The no-trade region is wide, even for small transaction costs… the large no-trade region has a small welfare impact."* Band width scales as **cost^(1/3)**, utility loss as cost^(2/3): a 100× cost increase widens the band only ~4.6×. Bands should be far wider than intuition suggests and the penalty for sitting inside one is second-order.
- **Baltas & Kosowski (SSRN 2140091) — (a/b), verified.** Turnover decomposes into `|Δ(1/σ)|` and `|ΔX_t|/σ`, and *"for a trading rule that takes only two values, such as the sign of the past return, |ΔX_t| = 2 when the position switches sign."* That is the formal statement of ACIS's failure mode. Replacing sign() with a significance-gated continuous rule cuts **total turnover by roughly two-thirds**; a Yang–Zhang range vol estimator cuts the vol channel ~10 % without exception across 75 contracts. **Their own honest negative: the turnover reduction did not significantly raise net risk-adjusted performance under the Frazzini–Israel–Moskowitz cost model.** Turnover reduction is cost survival, not alpha.
- **Carver / `pysystemtrade` — (b), source-verified.** `forecast_cap: 20.0`, `average_absolute_forecast: 10.0`, `buffer_method: forecast`, `buffer_size: 0.10`, `buffer_trade_to_edge: True`, `percentage_vol_target: 16.0`. Position: `subsystem_position_raw = vol_scalar * forecast / 10`, i.e. a **linear response function, not a gate**. Buffering (`systems/buffering.py`, `sysexecution/strategies/classic_buffered_positions.py`): buffer = 10 % of the **average absolute** position; if outside, trade **only to the nearest edge**, else do nothing. His own note: *"This is more theoretically correct; since the buffer doesn't shrink as we get to zero… we trade to the nearest edge of the buffer, rather than going to the optimal position."* This is the Constantinides no-trade region implemented at retail scale. His vol estimator is deliberately de-chattered: 35-day span blended 35 % toward a 20-year vol, with an absolute floor and a 5th-percentile/500-day floor.
- **López de Prado, *AFML* ch. 10 — (a/b)** (recalled, not fetched): bet size `m = 2·Z(z) − 1` from a classifier probability, with **averaging of active bets** and **discretised bet sizes specifically to prevent overtrading on small probability changes** — hysteresis by another name.
- **Honest caveat:** essentially all of this is **daily or monthly** evidence. There is no peer-reviewed intraday equivalent. The structural results are horizon-agnostic in *form*; every parameter value is not. And **Kim, Tse & Wald (2016), *JFM* 30, 103–124 — (a)** argue the large TSMOM alpha is driven by the volatility scaling rather than the momentum signal, with TSMOM and buy-and-hold statistically indistinguishable without vol scaling. That is a live falsification hazard for any vol-targeted rebuild.

## 2.3 Optimisation: objective mismatch and trial accounting

- **The proxy-objective problem has no settled name in finance.** Closest rigorous framing: **Elmachtoub & Grigas, "Smart 'Predict, then Optimize'", *Management Science* 68(1) 2022 — (a)**: minimising *prediction* error does not minimise *decision* regret; they define an SPO loss precisely because the two differ. Equity-quant version: Grinold–Kahn's **transfer coefficient**, the loss between the research signal and the implemented portfolio.
- **The historical precedent is exact.** **Allen & Karjalainen, *JFE* 51(2) 1999 — (a):** GA-evolved rules on the S&P 500, 1928–1995 — *"after transaction costs, the rules do not earn consistent excess returns over a simple buy-and-hold strategy in the out-of-sample test periods,"* despite genuine forecasting content. **Neely, Weller & Dittmar, *JFQA* 32(4) 1997 — (a)** found GP-evolved FX rules profitable out-of-sample; **Neely, Weller & Ulrich, *JFQA* 44(2) 2009 — (a)**, same lead author, found those profits *"had disappeared by the early 1990s."* There is a paper literally titled *Forecasting Ability But No Profitability: An Empirical Evaluation of Genetic Algorithm-Optimised Technical Trading Rules* **(a)**.
- **Surrogate-assisted evolutionary algorithms — (a)** prescribe the direct fix: **mandatory re-evaluation of survivors under the true expensive fitness each generation**, with the cheap proxy used only to prune.
- **Trial accounting.** **Bailey, Borwein, López de Prado & Zhu, *Notices of the AMS* 61(5) 2014 — (a):** with **5 years of data, no more than ~45 independent configurations** may be tried before the expected out-of-sample Sharpe of an in-sample SR = 1 is **zero** (and negative, given memory effects). **Bailey & López de Prado, Deflated Sharpe (SSRN 2460551) — (a):** `E[max SR_N] ≈ E[SR] + √V[SR]·((1−γ)Z⁻¹[1−1/N] + γZ⁻¹[1−1/(Ne)])`, γ = 0.5772; **N = 1000 trials gives E[max SR] = 3.26 with zero true skill.** With a 5-year window (SE ≈ 0.45) the luck-only maximum is ≈ 1.14 at 100 trials and ≈ 1.47 at 1000. **Harvey, Liu & Zhu, *RFS* 29(1) 2016 — (a):** t > 3.0, not 2.0.
- **Walk-forward is not enough.** **Arian, Norouzi M. & Seco, *Knowledge-Based Systems* 305 (2024) — (a)**, synthetic controlled environment with known ground truth: Combinatorial Purged CV dominated on both PBO and DSR, while *"Walk-Forward exhibits notable shortcomings in false discovery prevention."* WFA controls look-ahead; it does not control multiple testing. **Re-optimising per detected regime multiplies the trial count by the regime count while dividing the sample per fold** — the worst direction on both axes.
- **Regime-conditional parameters specifically.** The supportive literature is about **exposure switching**, not parameter conditioning. Best case found: Shu, Yu & Mulvey (arXiv:2402.05272) **(a-preprint)**, online/filtered inference, 10 bp costs, one-day delay — jump-model Sharpe 0.68 vs buy-and-hold 0.48 on the S&P 500, drawdown −26.6 % vs −55.2 %; regime-identification latency ~2 weeks. **I found no peer-reviewed study showing that re-optimising strategy *parameters* per detected regime beats a single parameter set out of sample.** A published reproduction ladder **(c, but with code)** reports the same strategy scoring **Sharpe 0.78 with causal filtered probabilities vs 1.74 with smoothed** — a 2.2× inflation from look-ahead alone.
- **What the people with records actually do — Carver, (b), with numbers.** Out-of-sample Sharpe of forecast weights, with his speed limit applied: by-instrument 0.545, by-group 0.546, pooled 0.587, blended 0.587, **equal weights 0.726**. *"You'd be mad not to use equal weights."* Ensembling across parameter variations rather than selecting one: *"by far the best approach is just to take an average."* His combined carry + trend system reaches **Sharpe 0.749** vs **0.294** for fast trend alone — **+0.45 from rule diversification, dwarfing anything fitting delivered.** His taxonomy of overfitting — explicit, implicit, **tacit** (restricting the parameter space using prior knowledge, which nobody counts) — and his process: develop on synthetic data, fit on fake data, use real data for sensitivity checks only.

## 2.4 What a realistic net Sharpe is — and what §14 asks for

| source | grade | net Sharpe |
|---|---|---|
| SG Trend Index (10 largest trend CTAs), since 2000 | (b) | **≈ 0.25–0.30** (CAGR 5.33 %, max DD 20.6 %) |
| BTOP50 since 2000 | (b) | CAGR 4.08 %, max DD 15.9 % |
| DB Currency Momentum USD Index | (b) | **0.30** (7.61 % p.a., 10.22 % vol, max DD −45.9 %); OOS extension slightly negative |
| FX carry, G10 USD 1990–2007 | (a) | 0.88; but **0.2–0.4** over 1900–2012, 20 currencies |
| Menkhoff, Sarno, Schmeling & Schrimpf, *JFE* 106 (2012) | (a) | FX momentum spread up to 10 % p.a., "fairly sensitive to transaction costs" |
| Carver's stated expectation for an experienced retail trader, **30+ instruments**, many rules | (b) | **≈ 1.0**, with 0.24 → 0.5 for a new trader |
| Carver's published book system | (b) | **0.749** |
| Cross-currency LOB predictability, *Int. J. Forecasting* (2025) | (a) | *"it does not seem possible to predict FX returns at any frequency ranging from one minute to one day using limit order book information"* |
| ESMA / ASIC / FCA on retail CFD-FX accounts | (a-equivalent, regulator) | **74–89 % lose money** |

**Grinold at 1-minute frequency, derived.** `IR = IC·√breadth`. Breadth is **not** bar count — consecutive 1-minute signals are ~0.99 autocorrelated, so effective breadth ≈ the number of *position changes* (Ding & Martin, *J. Empirical Finance* 2017 — (a)). With a cost-feasible 90–250 independent bets/year and a realistic per-bet IC of 0.02–0.05: gross SR 0.19–0.79 per instrument; net of a 0.13 cost budget, 0.06–0.66; over 8 instruments at ρ̄ = 0.3 (multiplier 1.61), **portfolio SR ≈ 0.3–1.0, centred near 0.5.**

**Cost budget, derived.** Annual cost in Sharpe units = (round-trips/day × 252 × round-trip cost) / σ_annual. At σ = 7 %:

| round trips/day | annual cost | Sharpe units |
|---|---|---|
| 0.36 (1 per 2.8 days) | 0.91 % | **0.13** — exactly Carver's stated limit |
| 1 | 2.52 % | 0.36 |
| 5 | 12.6 % | 1.80 |
| 10 | 25.2 % | 3.60 |

**At 1 bp round trip an honest budget permits ~90 round trips per year — one trade every ~3 days.** ACIS's falsification run did **487 per instrument-year**. Also: 1 bp ≈ 0.86 × the standard deviation of a single 1-minute EUR/USD bar. Any signal whose per-trade edge is smaller than one bar of noise cannot pay for itself.

> **This bears directly on master §14.** The spec's *minimum* is annual Sharpe **> 1.5** and its stretch is **> 2.5**, out-of-sample, on an account's own universe — here 2 instruments. Nothing in the verifiable public record — trend CTAs at 0.25–0.30, published FX momentum at 0.30, FX carry at 0.2–0.9, Carver's 30-instrument expectation of ~1.0 — reaches 1.5 on a small FX universe. The Deflated Sharpe machinery already in the repo (`tests/backtest/deflated_sharpe.py`) says the same thing from the other side: with a 2-year graded window and 121 trials, the luck-only maximum Sharpe is already ~1.8. **A §14 target above the luck-only ceiling of your own trial budget cannot be cleared honestly.** That is a spec-level finding and needs the owner.

---

# HALF 3 — Reconciliation and recommendations

Each item is tagged **[implementation fix]** (buildable under the current spec) or **[spec-level change requiring human ratification]**. Ordered by expected effect.

## R1 — Demote the regime from sovereign gate to (at most) a sizing weight · **[spec-level change requiring human ratification]**

**Evidence:** §1.3 (3.7 % signal recovery; wrong sign on `STRONG_TREND_DOWN`; 2–4-minute median label runs against a 149-minute phenomenon; 245,434 regime shifts) and §1.5 (the gate halves the trend rule's sample and changes its edge by 0.013 pips). **Outside evidence:** no peer-reviewed study shows per-regime *parameter* conditioning beating a single parameter set out of sample; regime-conditioning multiplies the trial count while dividing the per-regime sample (Bailey et al. MinBTL); the supportive regime literature is about 0/1 exposure switching with ~2-week latency, not minute-scale routing; QuantConnect practitioners' stated conclusion is to feed market conditions in as *features of one model*, not as a switch between separately-fitted parameter sets.

**Concretely:**
1. **Keep** `tradeable` as a pure *safety* veto — stale state, spread blow-out, dead market, macro event, session closed. Those are measurable facts and NVMA computes them correctly.
2. **Stop using `RegimeType` as the module router** (`core/signals/agon.py:245-263`) and **as the `ParamLibrary` key** (`tests/integration/paper_loop.py:125`, `core/optimizer/param_library.py`). One parameter set per instrument, or better, pooled across instruments.
3. If a regime notion survives at all, collapse it to ≤ 3 states on a **time-based lookback matched to the trade horizon** — not a 14-tick window — and use it as a *weight*, never a gate.
4. **Remove `regime_stability_score × confidence` from the sizing formula** (`core/governor/capital_governor.py:271`) or replace it with something that is not a proxy for the classifier's own instability. Today it silently cuts every position to ~14 % of intent.

This is spec-level: master §4 declares NVMA "the sovereign gatekeeper" and §6 hard-codes the regime factor into the Governor formula.

## R2 — Make the optimiser's objective the system's own PnL · **[spec-level change requiring human ratification]** (partly [implementation fix])

**Evidence:** §1.4 — three genes drive live modules and are scored by nothing; one scored gene is used by nothing; `simulate_trades` is 1 of 6 live modules. This is GAP-0035, now quantified. **Outside evidence:** Elmachtoub & Grigas (prediction loss ≠ decision loss); Allen & Karjalainen (real forecasting ability, no post-cost profit); surrogate-assisted EA practice (mandatory re-evaluation of survivors under the true expensive fitness).

**Concretely, in increasing order of cost:**
1. **[implementation fix]** Delete `max_holding_periods` from `GENE_SPECS` (`core/optimizer/param_types.py:28`) *or* wire it into the engine's exit. Today it is scored and unused, so part of every fitness score is earned by an exit the engine does not have. (§1.4 measured: removing it *raises* measured expectancy from +0.94 to +1.42 pips, so the engine's absence of it is not itself harmful — but scoring a phantom exit is dishonest selection.)
2. **[implementation fix]** Refuse to evolve a gene no objective scores. Either add `momentum_lookback`, `breakout_atr_threshold` and `mean_rev_zscore_entry` to a fitness that exercises the corresponding modules, or **freeze them at a declared constant** and remove them from the chromosome. Shipping randomly-drawn values to live modules is not a defensible design.
3. **[spec-level]** Replace the `simulate_trades` proxy with the **engine's own decision path** as the fitness evaluator — the surrogate-assisted-EA discipline: use the cheap proxy to prune, then re-score survivors with the real `AGON → Governor → book` loop. GAP-P12D-30 already shows the compute cost is the obstacle; that is a resourcing decision, not a design one. The alternative — Carver's — is to **stop fitting parameters altogether**, use √2-spaced round-number ladders, ensemble across them, and spend the effort on rule diversification (+0.45 Sharpe in his measured case, versus equal weights beating every fitting method by up to 0.18).

## R3 — Give the engine a position policy · **[spec-level change requiring human ratification]**

**Evidence:** §1.7 — 1,425,326 signals → 2,018 trades, selected by `tests/backtest/book.py:96-100`. **Outside evidence:** Gârleanu & Pedersen's Markowitz row, gross +0.83 → net **−9.84**; Baltas & Kosowski's `|ΔX_t| = 2` at every sign flip; Constantinides/Davis–Norman no-trade regions with cost^(1/3) width; Carver's source-verified `buffer_size: 0.10`, `buffer_trade_to_edge: True`.

**Concretely — this is the single most mechanical, best-evidenced change in the report:**
1. Add a **desired-position** concept to the Governor. `CapitalGovernor.allocate` currently returns a fresh `SizedOrder` per signal; it should return a **target position** for the instrument.
2. Make the target a **continuous function of a capped, scaled forecast**, Carver-style: `position = (clip(forecast, −20, +20) / 10) × vol_scalar`, where `vol_scalar = cash_vol_target / instrument_value_volatility`. `Signal.conviction ∈ [0.45, 1]` (`core/signals/signal_types.py`) is already a forecast in disguise — it is just being used as a gate multiplier instead of a response function.
3. Wrap it in a **no-trade band** of ~10 % of the *average absolute* position and trade only to the near edge. This replaces `book.apply_order`'s dedup/reverse branch with a designed rule and is where the whipsaw goes away.
4. Combine the six modules by **weighted average of forecasts** (with a diversification multiplier capped at ~2.5), not by the §2 conflict table's "opposite ⇒ discard both". Today two modules disagreeing produces *silence*; averaging produces a small position, which is the correct answer.
5. De-chatter the sizing input: blend/floor the volatility estimator rather than reading a raw ATR that flips every bar (Carver's `mixed_vol_calc`; Baltas–Kosowski's Yang–Zhang finding).

This is spec-level: master §5.5 makes AGON stateless by law ("AGON does NOT know capital, portfolio state") and §2's conflict table mandates discard-on-disagreement. Both would need owner ratification. Note the safety architecture is *unaffected* — a target-position Governor still clamps only downward, and the Risk Monitor's upward edge stays risk-restrictive.

## R4 — Match exit distance to the signal's horizon · **[spec-level change requiring human ratification]**

**Evidence:** §1.6 — ATR(14) on 1-minute bars gives a median noise-survival time of 8–12 minutes. **Outside evidence:** Kaminski–Lo (a 0/1 stop against a random walk always lowers expected return); Carr & López de Prado (no stable optimum near a random walk); the derived 82 % probability of being stopped inside a 4-hour hold at 2 × 1-minute ATR; Carver's X-to-holding-period table; Clare et al. (stops do not add value, lower decision frequency wins).

**Concretely:**
1. Set stop distance from **annualised or daily volatility**, not from an ATR of the decision bar: for a multi-hour horizon, ~0.5 daily σ (≈ 20 bp on EUR/USD, ≈ 10–12 × the 1-minute ATR). `atr_multiplier_sl ∈ [1.0, 3.5]` on a 1-minute ATR cannot express that; the range must change or the ATR base must.
2. **Remove the fixed take-profit from divergent (trend/breakout/momentum) modules.** TSMOM already does this correctly and honestly (`agon.py:498-501`, declared deviation). The ATR-multiple TP on trend and breakout truncates the right tail those strategies are paid from. Exit on the forecast crossing back, not on a target.
3. **Drop the `atr_multiplier_tp > atr_multiplier_sl` invariant** (`core/optimizer/param_types.py:61`). It is a trend-following assumption imposed on convergent strategies that need the opposite geometry. §1.5 shows reversing it does not rescue mean reversion on *this* tape — but the constraint is wrong on principle and will be wrong on tapes where convergent strategies do work.
4. Raise the decision clock. A 1-minute decision bar with a multi-hour edge is 150× oversampled; every extra crossing is a round trip and no extra information.

## R5 — Decide what to do with the mean-reversion and pair-divergence modules · **[spec-level change requiring human ratification]**

**Evidence:** §1.5 — mean reversion trades 8.7× more often than the gated trend rule at −2.17 pips/trade, 0/12 parameter sets positive, and in the real composed loop **wins 9.3 % of its trades** and erases 63 % of the other two modules' gain. Its gate is uninformative and its gene is unoptimised.

Options, in order of conservatism: (a) **disable `MEAN_REVERSION` and `PAIR_DIVERGENCE` in `config/system_config.yaml` until they have an objective that scores them** and a gate that can tell a trending tape from a ranging one; (b) keep them but give them their own fitness evaluation and their own exit geometry; (c) fold them into the forecast average of R3, where a losing module costs weight rather than trade count. I recommend (a) as the immediate step and (c) as the destination. Separately, the external-referent point already raised in the ledger stands: on a two-instrument EUR/USD × USD/JPY universe the configured pair relationship is `EUR/USD × USD/JPY = EUR/JPY` exactly, so the pair-divergence "relationship" is an identity, not a coupling.

## R6 — Fix the two harness defects before any further run · **[implementation fix]**

1. **`scripts/falsify_engine.py::plan`** — make test windows non-overlapping with the *previous* fold's warmup, e.g. `test_start_k = train_end_k + EMBARGO` with `train_end_k ≥ test_end_{k−1}`. Add the missing invariant in `tests/backtest/walk_forward.Fold` or in `Backtest.run`: **fold *k*'s warmup start must not precede fold *k−1*'s test end.** Regression test: assert the tick timestamps delivered to `Backtest._tick` are monotonically non-decreasing across the whole run. (The `tsmom_avg_duration_s = 54.9 h > 48 h max_hold` in the artifact is a ready-made failing assertion.)
2. **`tests/backtest/book.py:142`** — include the spread: `cost.per_side_cost(entry_spread) + cost.per_side_cost(exit_spread)`, using the `MarketState.spread` at entry and exit, exactly as `core/optimizer/fitness.py:129` does. This is what master §5 C8 already mandates; the pinned-semantics test (`tests/unit/test_fitness.py::test_cost_model_semantics`) should be extended to cover the book, not just fitness. **Until this is fixed, every §14 number the harness produces is flattered by ~0.3–0.6 Sharpe units at the observed turnover.**
3. **`tests/backtest/regime_labels.py:165-181`** — `history()` returns a time-discontiguous series that `simulate_trades` runs EMA/RSI/ATR across as if contiguous (median fragment 4.6 bars). Either evolve on contiguous bars with regime used as an entry *mask*, or make the discontinuity explicit and reset the indicators at each fragment boundary. (Lower priority — §1.4 shows it flatters nothing — but it is a correctness defect and it is the thing R1 would remove anyway.)

## R7 — Re-examine the §14 targets against the trial budget · **[spec-level change requiring human ratification]**

**Evidence:** §2.4. The verifiable public record tops out near 0.75–1.0 net Sharpe for diversified, 30+-instrument systematic programmes; trend CTAs realise 0.25–0.30; published FX momentum 0.30. The falsification run itself declared **121 trials**; with a 2-year graded window the Deflated-Sharpe luck-only ceiling at that trial count is ~1.8, i.e. **barely above the §14 minimum of 1.5**. A target that a coin-flip search can almost reach is not a bar. Recommend the owner consider a band of **0.5–1.0 net, with the Deflated Sharpe ≥ 0.95 gate (already ratified, GAP-P12D-16) doing the real work**, and the §14 minimum restated as a *deflated* quantity rather than a raw one.

## R8 — Re-run the falsification with attribution, as the first confirmation step · **[implementation fix]**

`per_regime`/`per_strategy` attribution landed after the failed run (GAP-P12D-31 closure, ACIS-09 v1.6). A short re-run with it will either confirm §1.5's prediction — **mean reversion is the largest single loss bucket, and breakout/trend are mildly positive** — or falsify this report's central claim. Do that before implementing anything. Prediction, recorded here so it can be checked: on the planted market the per-strategy table should show `MEAN_REVERSION` with a win rate under ~20 % and the largest negative net PnL, `TREND` and `BREAKOUT` positive or near flat, and `TSMOM` with a trade count in the low single digits and durations exceeding the 48 h cap (the R6-1 bug).

---

## Appendix — what I tested that was *not* the cause (honest negatives)

| hypothesis | verdict | evidence |
|---|---|---|
| The fitness function can't find the edge | **False** — it finds it easily | 22/24 random ParamSets profitable on the raw tape; 12/12 without `max_holding_periods` |
| Regime-stitched fitness bars inflate the score | **False** — stitching makes it *harder* (mean fitness 0.137 vs 0.358) | §1.4 |
| Trades are too short to hold the trend | **False on this tape** — the profitable optimiser rule also holds 8 minutes | §1.4, §1.6 |
| Costs caused the loss | **False** — 0.2–0.5 Sharpe units on the synthetic tape against a +157 oracle | §1.10 |
| The regime gate destroys the trend rule's edge | **False** — it halves the sample and moves the edge 0.013 pips. It is *useless*, not *harmful*, to the trend rule; the harm is that it fails to screen the mean-reversion rule | §1.5 |
| The `tp > sl` constraint is what breaks mean reversion | **False** — all 18 geometries lose, −1.49 to −3.12 pips | §1.5 |
| The Governor's hard overrides are starving the engine | **False** — `orders_zeroed = 0` in the controlled run; the Governor zeroed nothing | §1.5 |

## Appendix — reproduction

Six read-only scripts were written to a session scratch directory (not the repo) and are reproducible from this document's descriptions. Each imports the production functions under test (`core.optimizer.fitness.simulate_trades`, `core.signals.indicators.bollinger_z`, `tests.integration.paper_loop.build_paper_loop`, `tests.backtest.book.PositionModel`) rather than re-implementing them, except for the exit-reason census, which is an instrumented clone of `simulate_trades` whose only change is recording the exit reason and bar count. No engine code, config, spec or ledger file was modified; nothing was committed; the full test suite was not run.
