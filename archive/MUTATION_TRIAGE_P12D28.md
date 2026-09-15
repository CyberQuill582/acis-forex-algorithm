# Mutation-gate triage — GAP-P12D-28 (2026-09-15)

`python scripts/mutation_gate.py` (mutmut 2.5.1) on `core/optimizer/fitness.py`, `core/optimizer/costs.py`,
`tests/backtest/metrics.py`, `tests/backtest/deflated_sharpe.py`. Mutant ids are cache-specific and change
between runs, so survivors are recorded by file, code and mutation.

## Runs

| Run | Runner | Mutants | Survived | What it showed |
|---|---|---|---|---|
| 0 | plain pytest | — | — | mutmut crashed reading UTF-8 sources with cp1252; the gate reported the crash as "surviving mutants" |
| 1 | plain pytest, 3 test files | 630 | 272 | inflated: mutmut 2 kills only on exit code 1; pytest's 2 (collection error, an import-breaking mutant) counted as survived |
| 2 | `--run-tests` shim, 9 test files | 626 | 81 | still 2 false survivors: same-size mutants ran a stale `.pyc` (fixed: no bytecode written) |
| 3 | shim, no bytecode, 10 test files | 626 | 43 | re-tested only run 2's survivors (mutmut 2 keeps cached kills), so not yet the verdict |
| 4 | same, from an EMPTY cache | 626 | 44 | **the verdict**: 529 killed, 53 killed but slow ("suspicious"), 44 survived — every one in a class below (the extra one is the `continue` → `break` of the unreachable `a <= 0` guard) |

## Why each class of survivor is not a test gap

**Equivalent — no observable behaviour differs.**
- fitness `simulate_trades`: the initial `entry_mid = sl = tp = 0.0`, `entry_cost = 0.0`, `bars_held = 0`
  (→ 1.0 / None) are overwritten at entry before any use; `exit_mid: float | None` → `float & None` is a
  local annotation, never evaluated; `direction > 0` → `>= 0` inside the in-position branch, where direction
  is never 0; `break` → `continue` on the last bar ends the loop either way; `entry_start` default 0 → 1 and
  `n <= warmup + 1` → `n < warmup + 1` / `n <= warmup - 1` return the same empty list (`ema_slow` ≥ 20
  dominates the default, and at `n = warmup + 1` the loop breaks before any entry).
- fitness `if a <= 0.0: continue` (→ `a < 0.0`, `break`): unreachable. A cross needs the EMAs to move, the
  bar's true range is then > 0, and a Wilder ATR that includes it is > 0.
- fitness `_clamp01`: `x < 0.0` → `<=`, `x > 1.0` → `>=` return the same boundary value.
- fitness `mean_sigma_component`: zero-variance `s = ±3.0` → `±4.0` is clamped to the same 1.0 / 0.0.
- fitness sums `p > 0` → `>= 0` (gross win, drawdown gross win) and `p < 0` → `<= 0` (gross loss) only add
  zero; `equity = peak = 0.0` → `1.0` shifts both equally, so every drawdown is unchanged.
- costs: the two `DataQualityError` reason strings (`"must be finite and >= 0"` → `"XX…XX"`) are
  human-readable text, not behaviour; the field name is pinned
  (`test_a_bad_spread_is_reported_against_the_spread_field`).
- metrics: `notional_usd: Decimal | None` → `Decimal & None` is a string annotation under
  `from __future__ import annotations`; drawdown `f > peak` → `>=` and `peak > 0` → `>= 0` after a
  truthiness test change nothing; `peak and …` → `peak or …` only admits negative peaks, whose drawdowns are
  ≤ 0 and clamped by `max(worst, dd)`; `p > 0` → `>= 0` and `p < 0` → `<= 0` add zero.
- metrics `spx_correlation`: `± 1.0` → `± 2.0` / `+ 1.0` shifts a whole return series by a constant, which
  leaves a Pearson correlation unchanged; `(x - ma)` → `(x + ma)` in the covariance adds
  `2·ma·Σ(y − mb) = 0`.
- metrics `rolling_var_breach_rate`: `if days else 0.0` → `1.0` is unreachable (`days ≥ 1` once three
  returns exist).
- deflated_sharpe: `trial_variance <= 0.0` → `< 0.0` computes `sqrt(0)·… = 0.0`, the same threshold;
  `n_trials or 0` → `or 1` cannot beat `len(t) ≥ 2`.

**Tie-only — behaviour differs only on an exact floating-point tie; accepted.**
- fitness entry: `ema_f[i-1] <= ema_s[i-1]` → `<` (and `>=` → `>` for shorts), `ema_f[i] > ema_s[i]` → `>=`,
  `rsi < rsi_overbought` → `<=`, `rsi > rsi_oversold` → `>=`. Two EMAs are exactly equal only on a flat
  history, where RSI is pinned at 100 (or 0 after a drop) and the filter blocks the entry anyway
  (`test_a_cross_against_an_exhausted_rsi_is_not_taken`); an RSI of exactly 75.0 / 25.0 at a cross needs an
  exact float ratio of Wilder averages.

**False survivors — the tests fail, the gate did not see it (fixed in the gate, not in the tests).**
- exit code 2 read as a pass (run 1): `test_every_failing_test_run_counts_as_a_kill`.
- stale bytecode (run 2): the shim runs pytest with `PYTHONDONTWRITEBYTECODE=1`; both survivors were
  confirmed killed by hand (`mutmut apply`, run the shim, restore).

## Killed by the tests this triage added

Every one confirmed by hand-applying the mutant and running the shim:
`tests/unit/test_fitness_indicators.py` (Wilder RSI/ATR recursions and warm-up guards, EMA seed),
`tests/unit/test_fitness_exits.py` (exact stop / target / stop-before-target / max-hold / mark-to-close),
`tests/unit/test_fitness_components.py` (components, expectancy edges, RSI filter, cost model),
`tests/unit/test_fitness_entries.py` (warm-up boundary per binding indicator, fresh-cross definition, no
next-bar look-ahead, consecutive-bar comparison), `tests/backtest/test_metrics_exact.py`,
`tests/backtest/test_deflated_sharpe_exact.py`. One unreachable branch was deleted instead of tested:
`metrics._avg_duration`'s all-trades branch.
