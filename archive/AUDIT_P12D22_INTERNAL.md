# Internal-consistency audit (Lens 1) — commit 068f8b4 "Governor base-unit sizing (GAP-P12D-22) + evolve-driver steps 1–4"

Auditor: Fable 5.1, fresh context, 2026-09-15. Brief: `AUDIT_BRIEF_P12D22.md` (Lens 1 + "both lenses" items). Author ≠ auditor; I am a finder, not a clearer — nothing below is a sign-off. No repo file was changed except this report. Reproduction scripts live in the session scratchpad (`r1_…r10_*.py`); every "actual output" line below is pasted from a run on this machine. Diff audited: `git diff 99eb9f0 068f8b4` (32 files, +1,498/−331).

Counts: **0 critical · 0 high · 5 medium · 6 low** (11 findings), plus 20 honest negatives.

---

## Findings

### F-I1 — Pair-group "balance" equalises UNIT COUNTS of two different currencies, so the legs are unequal in dollars and the group carries a net USD delta (ACIS-05 §7.6 "one relationship bet, never two directional bets")
- Severity: **medium** · Likelihood: **high** (every pair group; the `eurusd_usdjpy` relationship is configured and `PAIR_DIVERGENCE` is a live strategy)
- Where: `core/governor/capital_governor.py::allocate_group` line 167 `balanced = min(leg_a.size_units, leg_b.size_units)`; the new test `tests/unit/test_governor_units.py::test_pair_legs_balance_without_the_yen_leg_shrinking_both` pins `oa.size_units == ob.size_units` (equal units).
- Failing input: the commit's own fixture `_pair_signals()` — EUR_USD short @1.10 and USD_JPY short @155, raw size $486 each.
- Reproduction `r1_pair_balance.py`, actual output:
  ```
  leg A EUR_USD: 441.82 EUR  = $486.002
  leg B USD_JPY: 441.82 USD  = $441.82
  USD notional imbalance: 44.182  (9.1%)
  net currency deltas of the 'balanced' group: {'EUR': '-486.002', 'USD': '44.182', 'JPY': '441.82'}
  ```
- Why it matters: before this commit both legs were "USD ÷ price" so `min` compared a EUR count with a 1/150-scale USD count (the group was ~140× too small — GAP-P12D-22's own words). Now that units are honest base-currency units, `min(EUR count, USD count)` is comparing apples with oranges: a USD-opposite pair that is meant to net to zero USD delta keeps a 9% directional USD bet, and for any pair with a high-priced base (a gold leg vs a USD-base leg) the imbalance would be orders of magnitude. The caps are computed correctly in USD (`notional_a`/`notional_b` per leg), so the caps see the imbalance but do not correct it — the *sizing* invariant is the broken one. The commit's test enshrines the wrong invariant.
- Minimal fix: balance in USD notional — `usd = min(units_a·per_unit_a, units_b·per_unit_b)`, `size_a = usd/per_unit_a`, `size_b = usd/per_unit_b` (quantised), then the net delta is zero for a USD-opposite pair. Requires an ACIS-05 §7.6 wording change ("min(size_A, size_B)" → "min USD notional"), so it is an **owner ruling**, not a silent change. Replace the test's equal-units assertion with an equal-notional / zero-net-USD-delta assertion.

### F-I2 — The labelled-bar cache key omits inputs that change every label: the factory/session-median config, per-instrument `max_plausible_spread`, the calendars, `data_start`, and the classifier code version
- Severity: **medium** · Likelihood: **high over the project's life** (the same class of change — GAP-0070's Hurst repair, GAP-P12D-12's `pstdev`, GAP-P12D-11's calendar — has happened repeatedly)
- Where: `tests/backtest/regime_labels.py::LabelSpec.key()` hashes `{source, bar_seconds, cycle_s, regime config, warmup_s}` only. But `build_nvma` wires `session_median=factory.session_median`, and NVMA step 1 (`core/regime/nvma.py:249-254`) emits `UNCLASSIFIED` until the median is warm; `state.session == "closed"` ⇒ `ILLIQUID` (line 278) comes from the calendars; `max_plausible_spread` decides which ticks exist; none of these is in the key. Nor is any hash of `core/regime/*.py`, `core/data/bars.py`, `core/data/normaliser.py`.
- Failing input: the shipped config vs the same config with `system.data.session_median_min_samples = 100000` (schema only requires `> 1`).
- Reproduction `r2_label_key.py` on the paper-loop `flat_ticks()` fixture, actual output:
  ```
  same cache key for both configs: True
  labels under config A (tail): ['MEAN_REVERTING', ...] | B (tail): ['UNCLASSIFIED', ...]
  bars whose label differs: 79 of 279
  ```
- Consequence: `LabelledBarCache.has()` reports the year as valid, `scripts/build_labelled_bars.py` skips it ("already cached under the current spec"), and QIEA evolves on labels NVMA would no longer produce — the invariant "the cache serves bars only under the exact labelling spec that wrote them" is false. A classifier code change is the silent case: the key never changes.
- Minimal fix: fold into `LabelSpec` a canonical JSON of `cfg.system.data`, of each labelled instrument's spec (`max_plausible_spread`, `calendar`) and of `cfg.instruments.calendars`, plus `data_start` and a sha256 of the labelling code path (`core/regime/`, `core/data/bars.py`, `core/data/normaliser.py`, `tests/backtest/regime_labels.py`); add a test that a changed `session_median_min_samples` changes the key.

### F-I3 — Cache commit order can leave OLD meta + NEW csv, and the old-spec reader then serves the new spec's labels as valid
- Severity: **medium** (silent wrong labels) · Likelihood: **low** (needs the rebuild to die between the two `os.replace` calls — but this is the 2-core laptop where long jobs are killed, and `ProcessPoolExecutor` workers die with the parent)
- Where: `regime_labels.py::LabelledBarCache.write` — `os.replace(tmp, csv)` then `write_text(meta_tmp)` then `os.replace(meta_tmp, meta)`. The docstring's "a year is committed by its meta file, written last" only protects a *first* write; on a rebuild under a new spec the CSV is overwritten in place while the previous spec's meta (with the previous key) survives until the last step.
- Reproduction `r3_cache_commit.py` (patches `os.replace` to raise on the meta replace), actual output:
  ```
  rebuild died: simulated kill between the CSV replace and the meta replace
  cache under spec A still claims the year: True
  labels served under spec A: ['STRONG_TREND_UP', 'STRONG_TREND_UP', 'STRONG_TREND_UP']   # spec B's bars
  ```
- Minimal fix: `self._meta(...).unlink(missing_ok=True)` before replacing the CSV (invalidate first, commit last), or name the CSV/meta by spec key so specs never share a path. Test: crash between the replaces ⇒ `has()` is False.

### F-I4 — `begin_final` writes the once-only marker BEFORE anything can fail, `Fold` has no construction invariant, and neither guard checks fold ordering or the embargo — a malformed final plan burns the single holdout grade and the correct plan is then refused
- Severity: **medium** · Likelihood: **medium** (the runner that will call this does not exist yet; the first real call is the risky one)
- Where: `tests/backtest/oos_plan.py::HoldoutGuard.begin_final` (checks only `test_start ≥ HOLDOUT_START` and `test_end ≤ HOLDOUT_END`), `check_development` (checks only `test_end`/`train_end` against the holdout), `tests/backtest/walk_forward.py::Fold` (plain frozen dataclass, no `__post_init__` — rule 2 "validate on construction").
- Failing input: `Fold(0, HOLDOUT_START, HOLDOUT_END, HOLDOUT_START, HOLDOUT_END)` (trains on its own test window, no embargo).
- Reproduction `r4_holdout_marker.py`, actual output:
  ```
  marker written for a fold that trains on its own test window: True
  …and the harness then refuses the run: fold 0: train→test gap -63158400 s is shorter than the 172800 s max hold — an embargo is required (GAP-SP12E-03)
  the CORRECT final plan is now refused: the holdout was already graded (marker …holdout_graded.json); it is graded once
  Fold with train_start > train_end > test_start > test_end constructs: True
  check_development accepts it too
  ```
- The brief's question "can a failed start consume the single grade?" — **yes**: any failure after the marker (a malformed plan, `ConversionUnavailable` for a cross, `StaleLabelsError`, an OOM on this laptop) leaves a marker that says "graded" over a run that produced no grade, and "no code path deletes the marker" means only a human can tell the two apart — the marker records nothing that would let them.
- Minimal fix: (1) `Fold.__post_init__`: `train_start < train_end <= test_start < test_end`; (2) `begin_final` validates the plan before creating the marker — the folds must be exactly `plan_folds(2024, 2025)`'s windows (or at least well-formed with `test_start − train_end ≥ EMBARGO`); (3) the marker carries `status: started` and the harness appends `status: completed` + the report hash, so a crashed start is distinguishable (the reset remains human-only). Also note the marker is a plain untracked file: a fresh clone (e.g. the AWS server) has no marker — "graded once" is per-checkout, which should be stated in OOS_VALIDATION.md or the marker committed by the human after the grade.

### F-I5 — `history()` filters on the bar OPEN and never looks at `train_start`: a bar straddling a non-aligned `end` is served, a fold declared to train 2022→2024 evolves on 2012 bars, and a final-run fold whose training year is unlabelled silently trains on older years
- Severity: **low** (calendar-year `end`s are bucket-aligned, and older bars are still pre-`train_end`, so no test-window leak in the ratified plan) · Likelihood: **medium** (the in-sample record cannot show it: `candidates[*].bars` is a count, not a span)
- Where: `regime_labels.py::LabelledBarCache.history` (`b.ts < end`, years `≤ end.year`, no lower bound); `evolve_step.py::evolve_fold` never passes `fd.fold.train_start`; `build_labelled_bars.py` refuses `--years 2024`, but `plan_folds(2024, 2025)`'s second fold trains 2023→2025.
- Reproduction `r5_history_end.py`, actual output:
  ```
  end=00:04:30 last bar open=00:04:00 close instant=00:05:00      # (a) served, straddles end
  bars returned for a 2022→2024 training window: [2012, 2023] (8 bars; no error, no span in the record)
  ```
- Minimal fix: `b.ts + timedelta(seconds=bar_seconds) <= end` (a bar is "before end" when it has *closed*); take `start=fold.train_start` (or at least record `first_bar_ts`/`last_bar_ts` per candidate so the in-sample transparency record is honest about what QIEA saw); and either label 2024 for the final run's 2025 fold in a guarded step or state in the plan that the final 2025 fold evolves on ≤2023 bars.
- Related observation (spec-conformant, for the owner's awareness): with `fitness_bars: 500` and 60-s bars, QIEA sees the last 500 bars *of that regime* — typically the last few days — so the plan's "2-yr train window" is nominal; `train_start` bounds nothing.

### F-I6 — A `Backtest` built without `session_boundaries` never sweeps `on_boundary`; everything the evolve step stages stays pending for the whole run, with no error and a report that shows champions
- Severity: **low** · Likelihood: **medium** (the constructor default is `()`, every scripted test uses it, and the runner is unwritten)
- Where: `harness.py::Backtest.__init__` `self._clock = BoundaryClock(session_boundaries) if session_boundaries else None`; `_replay` skips promotion when `_clock is None`.
- Reproduction `r6_no_clock.py`, actual output:
  ```
  evolve staged: ['champion'] | boundary sweeps performed: []
  report in_sample_evolution says champions were evolved: ({'fold': 0, 'champions': 1},)
  R6 REPRODUCED: staged params can never promote, no error raised
  ```
- Minimal fix: raise in `run()` when `evolve_fn` returned a record with `champions > 0` and there is no clock (or make `session_boundaries` a required argument and let the scripted tests pass the config's list). The failure mode today is a zero-trade OOS record that "cannot pass" — true, but it is a silent misconfiguration rather than a refused one.

### F-I7 — The `BoundaryClock` persists across folds, so fold k+1's first tick replays every boundary inside the embargo gap as a separate sweep BEFORE that tick's max-hold close; with a position carried over, the real `ParamLibrary` would count ~40 skipped boundaries in one instant and raise a spurious stall alert
- Severity: **low** · Likelihood: **low** (needs an open position at the last tick of a fold; the stop/target/48 h max-hold usually close earlier)
- Where: `harness.py::_replay` — the `for boundary in self._clock.crossed(...)` loop runs before `maybe_close`; `param_library.py::on_boundary` increments `boundaries_skipped` per call and logs `PARAM_PROMOTION_STALLED stalled=True` at `param_stall_alert_boundaries: 3`.
- Reproduction `r10_sweeps_and_real_library.py` (a), actual output:
  ```
  (a) sweeps replayed on fold 1's FIRST tick: 40, all with open_position_count={1} (the max-hold close of that position happens after the sweeps on the same tick)
  ```
- Minimal fix: run `maybe_close` for the tick before the boundary sweeps (a stop/max-hold that has already been hit by this tick's price/time should count as flat at the boundary), or collapse gap boundaries to the last one crossed. Either way the promotion just slips to the next boundary, so this is observability, not safety.

### F-I8 — ACIS-05 v1.3 contradicts itself on the delta unit: §5 says `per_currency_delta` is "signed, base-ccy units"; §7 step 3 (new) and `portfolio_types.py` say USD-notional; the code accumulates USD
- Severity: **low** (documentation) · Likelihood: **high** (a reader of §5 alone builds the GAP-P12D-21 snapshot in the wrong unit)
- Where: `specs/ACIS-05-CAPITAL_GOVERNOR.md` §5 vs §7 step 3; `core/governor/portfolio_types.py:54` ("signed, USD-notional terms"); `_delta_contributions` returns `{base: ±notional_usd, quote: ∓notional_usd}`.
- Minimal fix: §5 wording → "signed, USD-notional (units × the USD value of one base unit, `core/governor/units.py`)". Directly relevant to the open GAP-P12D-21 builder, which must produce the snapshot "exactly as the Governor accumulates them".

### F-I9 — A cross's USD-leg rate has no staleness bound: a 30-day-old leg bar sizes the cross with `reason=formula` and no event
- Severity: **low** (no cross is enabled; the spec literally says "last completed signal bar", so code = spec) · Likelihood: **medium once a cross is enabled** (a feed gap or a disabled leg is exactly the case)
- Reproduction `r9_units_props.py`, actual output: `cross sized off a 30-day-old leg bar: reason=formula units=452.09; events about staleness: []`.
- Minimal fix (owner ruling, it tightens ACIS-05 §7 step 3): size zero with a new reason (`stale_usd_rate`) when the leg bar's `ts_open + duration` is older than, say, the signal's `valid_for_seconds` or `stale_threshold_ms`; log it. Also note the Governor now has a cross route that the Risk Monitor lacks (`_usd_factor` → `None` → quote currency booked as USD with `CONVERSION_UNAVAILABLE`), so for a future cross the two layers would disagree on the same order's USD value — GAP-0092's residual should say so explicitly.

### F-I10 — Ledger closure: the new `Residual:` pointers name owners that do not own the work as written
- Severity: **low** · Likelihood: n/a
- GAP-P12D-18 and GAP-P12D-16 close with "Residual: GAP-P12D-03 — the evolve-driver itself (labelled-bar cache, per-instrument evolution, runner, holdout guard)". GAP-P12D-03's own text owns *the three non-tick inputs* (SPX, event calendar, financing); the runner (`scripts/run_oos_validation.py`, step 5) is recorded only in `TODO.md`'s "Evolve-driver — BUILDING" item. `ledger_check.py` passes (157 entries, 0 violations) because a pointer to a real ID satisfies the rule, but the pointer is not TRUE. GAP-P12D-22's residual points to GAP-0092, whose description ("treats quote as account currency") has been stale since GAP-P9E-04 (`_usd_factor` converts USD-base); the remaining Risk-Monitor gap is crosses only.
- Minimal fix: repoint the two residuals to the TODO runner item (or widen GAP-P12D-03's Area/Description to own the runner), and add one line to GAP-0092 stating the residual is crosses only and that the Governor now has a cross route the monitor lacks (F-I9).

### F-I11 — Ratified-design hazard (owner decision, GAP-P12D-18 (3)): the Deflated Sharpe's deflation is proportional to the SPREAD of the fold Sharpes, so two agreeing folds neutralise any N
- Severity: **low** (the gate is a tightening; the dev plan has 10 folds) · Likelihood: **medium** (the `_MIN_TRIALS = 2` floor in `report.py` is exactly where it is weakest, and folds of one strategy are far more alike than independent trials)
- Where: `deflated_sharpe.py::sharpe_threshold` (V = sample variance of the fold Sharpes; N only enters through `Zinv[1−1/N]·sqrt(V)`); docstring deviation (1) claims "over-counting N … is conservative", which holds only through V.
- Reproduction `r7_dsr_variance.py` (500 daily returns, per-period SR 0.195), actual output:
  ```
  fold sharpes [0.11, 0.1100001] N=1000000: SR0=0.0000  DSR=1.0000
  fold sharpes [0.11, 0.111]     N=1000000: SR0=0.0034  DSR=1.0000
  fold sharpes [0.11, 0.05]      N=1000000: SR0=0.2065  DSR=0.3992
  ```
- This is internal-consistency only insofar as the code does what the ruling says; whether fold-to-fold variance of one strategy is a valid stand-in for cross-trial variance is Lens 2's item 2. Recorded so the owner sees the numbers: N from champions + registry can be made irrelevant by fold agreement. Minimal mitigation if the owner wants one: require a variance floor (e.g. V ≥ the OOS Sharpe's own standard error²) or raise `_MIN_TRIALS`/fold count for the gate.

---

## Honest negatives (attacked, survived, how)

1. **Calendar-gate move is behaviour-identical.** `r8_gate_identity.py` exec'd the pre-commit module from `git show 99eb9f0:…` and compared `_within_weekend_buffer`/`_next_boundary` against `calendar_gates.within_weekend_buffer`/`next_boundary` every 7 minutes across the 2025 US/UK DST weeks, both `week_open` variants (17:00 and gold's 18:00), buffers 0 and 7200 s: `identical on 32916 instants x 2 gates`.
2. **`usd_per_base_unit` matches ACIS-05 §7 step 3 in every branch** (`r9_units_props.py`): XXX_USD → price, XAU_USD → price, USD_JPY/USD_CHF → 1, EUR_GBP via `GBP_USD` (×) or `USD_GBP` (÷) → 1.075, EUR_JPY via USD_JPY → 1.1, no leg → `None`, and a malformed symbol (`EURUSD`) → `None` (sizes zero, never guesses). `units × per_unit` reproduces the raw USD within the 0.01-unit quantisation.
3. **Caps use USD notional in every path.** Single order: `notional = size_units * per_unit`; group: `balanced * per_unit_x` per leg, cluster counted once at `max(notional_a, notional_b)`, deltas netted in USD; `test_usd_base_notional_meets_the_currency_cap_in_dollars` pins the USD/JPY case. Consistent with `portfolio_types.py` ("USD-notional"). (The *balance* is not in USD — F-I1.)
4. **`allocate_group`'s `usd_per_base_unit(...)` cannot be `None`**: both legs reached the balanced branch only by passing `_allocate_one`'s `per_unit is None → no_usd_rate` check against the same `self._bars`.
5. **Risk Monitor already assumes base units** (`core/risk/monitor.py` `_usd_factor`, GAP-P9E-04): realised/unrealised PnL, per-instrument drawdown and the VaR notional (`|units| × mark × factor`) are all correct under the new sizing. Side-effect worth recording: before this commit the monitor's USD/JPY VaR notional was 150× *understated* (6.67 units × 155 × 1/155), so the fix also repaired the in-loop VaR input for USD/JPY.
6. **Execution assumes base units**: `UNITS_PER_LOT = 100000` on `size_units` is the FX lot convention, so `total_lots` for USD/JPY is now right (was 150× small). Pre-existing and out of this commit's scope: that constant is also applied to XAU_USD (100-oz lots) — gold is disabled; not ledgered as far as I can find.
7. **MCP surfaces**: no module under `monitoring/` reads `size_units`, `entry_price`, exposure or notional.
8. **Lot cap** `size_units / 100000 > max_lots` is consistent with base units.
9. **Labeller has no look-ahead**: `label_bars` reads `engine.regime_store` BEFORE `observe`/`classify` of the completing tick; the completing tick's price enters neither the bar (closed by `BarAggregator` on bucket change) nor the label. `test_a_bar_gets_the_regime_from_before_the_tick_that_closed_it` pins it with `cycle_s=0`. Note (not a leak): this is one tick *staler* than the live loop, which classifies on the tick before AGON completes the bar — conservative.
10. **Year warm-up and cut**: the stream starts at `max(start − 3 d, data_start)`, bars are cut at `b.ts >= start`, and `test_a_year_job_warms_up_before_the_year_and_keeps_only_its_bars` shows the first bar of the year present. (Whether 3 days is *enough* warm-up is Lens 2 item 3.)
11. **`end` is exclusive everywhere it matters**: `DukascopyTickSource.load` uses `day < end` and `start <= t.ts < end`, so fold 2023's test window and 2023's labelling never read a 2024 tick; `check_development` refuses `test_end`/`train_end` past 2024-01-01; `build_labelled_bars.py` refuses `--years ≥ 2024`; `begin_final` refuses test windows outside the holdout; the marker is `open("x")` (exclusive create). (Marker weaknesses: F-I4.)
12. **Embargo on real data**: `require_embargo(fold.train_end, first test state, max_hold)` fires on the first emitted state of every fold; an empty stream yields no equity and cannot pass.
13. **Promotion only through `on_boundary` when THIS book is flat**: `open_position_count()` reads `_active.open_by_inst`; the sweep precedes the tick's `on_state`; `test_promotion_sweeps_see_the_backtest_book_not_the_loop_order_list` pins open→stall, flat→promote. `r10_sweeps_and_real_library.py` (b): the real `ParamLibrary.on_boundary` accepted all 36 `BoundaryClock` instants across the US DST week (each is an exact `at_local_minute`).
14. **`n_trials` rules as ruled**: `max(len(fold_sharpes), min_trials + champions)` only with ≥2 fold Sharpes, else `len(fold_sharpes)` (0/1 → `trial_count < 2` → cannot pass); `sharpe_threshold(…, n_trials)` never lowers N below the supplied Sharpes; NaN DSR fails `passed`.
15. **Fold Sharpes are per-period** (`moments` on daily returns), matching the DSR docstring's "never annualised".
16. **Evolve step reads only bars before `train_end`**: `test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read` compares a 600-bar and a 500-bar cache and gets identical records and `param_set_id`. Seeds derive from `(fold, regime, instrument)` via sha256 — reproducible. Staging only (`loop.params.stage`), never `promote`.
17. **Holdout tail matches QIEA's own gate**: `holdout_expectancy` recomputes `n_hold = max(1, round(len(bars)·holdout_fraction))` and `entry_start = len(bars) − n_hold`, which equals QIEA's `entry_start=len(train)`; the same `CostModel` object is used.
18. **NaN holdout E_R cannot poison best-champion selection**: `passes_expectancy_gate` requires `isfinite(e_r)`, so a champion always has a finite `holdout_e_r` and the `>` comparison is well-defined; ties keep instrument order as documented.
19. **Module budget**: `capital_governor.py` 448 = its lowered ratchet; every new/changed module is under 300 (`harness.py` 195, `data_loader.py` 226, `regime_labels.py` 176, `book.py` 160); `tests/backtest` and `scripts` are inside `PRODUCTION`. Each new module opens with an invariants block (GAP-P12M-02).
20. **Ledger**: `python scripts/ledger_check.py` → `157 entries checked; 0 violation(s)`; every new closed entry carries a `Residual:` line (precision issues: F-I10).

**Full suite** (`python -m pytest -q -p no:cacheprovider`, run once, in the background): `687 passed in 252.95s (0:04:12)` — green as the commit claims. None of the findings above is caught by the suite (F-I1 is *pinned the wrong way* by `test_pair_legs_balance_without_the_yen_leg_shrinking_both`), which is the point of each proposed regression test.

---

## Notes outside the brief's questions (not findings)
- `PositionModel.apply_order` books `strategy_type` from `factors_snapshot` (GAP-P12D-20, open) and `portfolio_fn` is a flat snapshot (GAP-P12D-21, open) — both already ledgered; nothing new.
- The Governor's `size_units.quantize(0.01)` rounds to nearest, which can round *up* past the formula for very high-priced bases (a $60k base would give 0.0081 → 0.01, +23%); pre-existing, not introduced here, gold rounds down at today's prices.
- `Backtest._seen_orders` is a per-instance watermark over `loop.book.orders`; reusing one `Backtest` for a second `run()` on a different loop would replay stale orders — the harness is single-use today.
