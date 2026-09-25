# BUILDER-2 report — the no-ratification "D" batch (2026-09-24/25)

**Branch** `worktree-agent-a8937e82f9a7a5391` · **worktree** `acis/.claude/worktrees/agent-a8937e82f9a7a5391`
**Base** `bdd3a75` (fast-forwarded from `7695ed0`), plus the BUILDER branch merged (`9b9ec80`, merge `577d882`).
**Authority** the owner's ratification in chat, "i ratify the whole of step 1". The work covers:
- GAP-P12D-65, the structural leakage suite;
- GAP-P12D-64, the look register;
- T6, the gap-through exit.

It follows the VALIDATOR's §3/§5/§7 (`archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md`).

**Untouched:** every threshold and gate, `ACIS_SPEC.md` and `specs/`, `KNOWN_GAPS.md` and `TODO.md`, the guardrail and platform configs, and `data/`. Drafts that belong in those files are in §7 below.

**Every stage is BUILT — PENDING AUDIT.**

| stage | commit | tests | A16 cases |
|---|---|---|---|
| 1+2 T2 + T1 | `e6293c4` (+ `62163fe` path fix, `1cd13d4` 60 s default tape) | 6 component sweeps, 7 script smoke tests, 2 `Trade` pins | 4, all red for their stated reason |
| 3 T7 | `341115c` | 8 controls | 4, all red |
| 4 look register | `97591b2` | 5 register tests, plus 2 updated runner tests | 4, all red |
| 5 T6 | `e51e5cc` | 8 gap tests (4 × long/short) | 2, all red; 5 hand mutants all killed |
| 6 T4 / T8 | not built | — | — (see §6) |

- **Suite:** 828 passed / 6 skipped at setup, then 856 / 6 after stage 4 and **864 / 6 after stage 5** (+36 tests).
- **Ledger:** `scripts/ledger_check.py` reports 204 entries and 0 violations.
- **Module budget:** green. Every new module is under 300 lines (the largest is 169) and opens with a mental model. `fitness.py` is 282 lines.
- **Power cut:** a power cut hit during stage 4. All uncommitted files were re-verified (py_compile, the JSON parses, every diff read end to end). The stage-4 suite and all four stage-4 A16 cases were then re-run before committing.

Falsification (A16) used the constitution's engine, `node specs_constitution/checks/falsify.mjs --root . --only <id>`: it reverts one guard, requires the named test to go red, then restores the file with a sha256 check. All 14 new cases are registered in `falsify.cases.json` as single-line anchors. The red failure lines below come from re-running each mutation with `--tb=line`; each file was restored and `git status` confirmed clean after every run.

## 1. Stages 1–2: T2 future-perturbation and T1 truncation, at every decision point

**Design** (`tests/backtest/leakage.py`, with the mental model in its docstring). Every decision carries two stamps:
- a **horizon**, the latest datum it may use;
- an **emission**, when the system can first produce it.

The two tests use them differently:
- **T2** perturbs every datum at or after the cut, and compares the decisions whose *horizon* precedes the cut.
- **T1** deletes every datum at or after the cut, and compares the decisions *emitted* before it.

Emission is needed because a bar whose completing tick was deleted is legitimately never emitted.

The perturbation reverses, negates and doubles every later return. Every later price moves, and so does the future's scale, which catches whole-sample statistics. Comparison is byte-identical: a multiset of `(kind, repr(payload))`. Random uuid4 ids are stripped, and group membership is kept as an ordinal.

**Component sweeps** (`tests/backtest/test_leakage_components.py`, ~15 s). There is one cut per decision point, never a sample.

| component | tape | cuts | notes |
|---|---|---|---|
| `BarAggregator` (60 s) | 160 irregular ticks | every tick | |
| `DailyBarAggregator` | 150 ticks, 2400–10800 s gaps | every tick | |
| regime labeller | real factory + NVMA, 130 ticks | every tick | schema-minimum windows (hurst 100); window lengths do not change causality |
| AGON | two instruments, 64 ticks each | every tick | crosses the 21:00 UTC rollover so a live daily bar forms; regime schedule and tick rate are perturbed too |
| `fitness.trade_path` | 240 bars | every open **and** every close (479 cuts) | the half-bar cut is what makes T1 able to see a next-close peek |
| `evolve_fold` | cache holding bars after the train end | at the train end, and +1 h | |

Each sweep also asserts how many decisions it compared (up to 18,499 per test), so a green result cannot come from an empty run.

**Observable.** `simulate_trades` returns PnLs, which cannot show *when* a decision was taken. `fitness.trade_path` now returns `Trade(signal_bar, direction, entry_price, exit_bar, exit_price, pnl, marked)`, and `simulate_trades` is its PnLs, with behaviour unchanged. Every field is pinned in `tests/unit/test_fitness_exits.py::test_the_trade_path_records_when_each_decision_was_taken`, which is in the mutation gate's test set.

**Engine level** (`scripts/leakage_suite.py`, `tests/backtest/leakage_engine.py`, `tests/backtest/leakage_markets.py`).

What the script runs:
- **Stage 1: the T7 controls.** The oracle positive control runs through the REAL harness (Backtest, book, C8 costs), once honest and once with a next-tick peek. If T1 and T2 do not both catch the peek, the run is VOID (exit 4) and the engine is never run.
- **Stage 2: the production path.** Labeller, evolve_fold, NVMA, AGON, Governor and book run through `run_walk_forward`, unmodified. The only addition is a tap that wraps `build_paper_loop` for one run.
- **The sweep.** One cut per decision day, for each of T2 and T1. Each variant gets a fresh directory, so no label cache is shared.
- **Exit codes:** 0 clean, 1 leak, 5 VACUOUS (the reference staged nothing or ordered nothing).

How the data is changed: `PerturbedMarket` changes the future at the SOURCE (`returns`), so side channels see it too. That is pinned by `test_the_market_variants_leave_the_past_bit_identical_and_change_every_later_tick`.

Wiring and defaults:
- It is wired like the other slow gates (A16), with a fast smoke test: `tests/backtest/test_leakage_suite.py`. Stage 1 runs for real there; stage 2 is stubbed.
- The default tape is 12/2/3 (train days / test days / folds) over 24 days. It was first probed at 5-minute ticks (10,222 labels, 4,560 regimes, 3 evolution records, and 3 signals, orders and trades each). After T6 that tape is VACUOUS (§5), so the default is now 60 s ticks: 51,118 labels, 22,800 regimes, 3 evolution records, 1 champion, and 20 signals, orders and trades each.
- `--out` keeps run paths short under Windows MAX_PATH. The first real run died with WinError 206; fixed in `62163fe`.

**Red lines (stage 1–2 A16 cases):**

| mutation | red line |
|---|---|
| bar close = the completing tick (`core/data/bars.py`) | `T2 future-perturbation: 159 cuts, 4390 decisions compared, 57 violating cut(s)` (T1: no violation) |
| label read after the completing tick (`regime_labels.py`) | `T2 …: 129 cuts, 18499 decisions compared, 35 violating cut(s)` (T1: no violation) |
| fitness cross decided on `ema[i+1]` | `T2 … at cut 50.5: 2 decision(s) lost [signal@49.5: (49, 1); fill@50.0: …]` |
| evolution window `train_end + 2h` (`evolve_step.py`) | `T1 truncation: 2 cuts, 2 decisions compared, 2 …` |

A further ad-hoc mutation fed AGON the next tick's mid; it gave `T2 …: 63 cuts, 3639 decisions compared, 63 violating cut(s)`.

**Engine-level evidence run** (2026-09-25; `python scripts/leakage_suite.py --workers 2`, from a clean `git archive 97591b2` snapshot at 5-minute ticks):
- **Stage 1 held.** The honest oracle was clean under T2 and T1 (6 cuts, 55 decisions each). The next-tick peek was caught by T2 (2 violating cuts, 1,723 decisions) and by T1 (1 cut).
- **Reference:** 10,222 labels, 4,560 regimes, 3 evolution records, and 3 signals, orders and trades each (114 s).
- **Result:** `T2 future-perturbation: 17 cuts, 102998 decisions compared, no violation`; `T1 truncation: 17 cuts, 102961 decisions compared, no violation`; verdict "clean". Total wall time was about 33 min.
- **Exit codes, as run:**
  - the first attempt died at MAX_PATH (fixed in `62163fe`);
  - a rerun was lost to the power cut;
  - a run on the post-T6 snapshot `e51e5cc` at 5-minute ticks correctly exited 5 (VACUOUS: no champion, no order; §5).

That leaves one gap in the evidence: a full sweep at the new 60 s default on the final code (1.5–2 h) was **not** run. The final code's reference at 60 s was probed as non-vacuous. T6's own causality is covered by the every-open-and-close component sweep, which is green on the final code.

**Costs.**
- The component sweeps take about 15 s.
- The script's controls take about 3 s.
- One engine variant takes about 90–100 s at 5-minute ticks, and about 5–7 min at the 60 s default.
- A full day-grid sweep is 34 variants (17 cuts × 2 tests): about 30 min with 2 workers at 5-minute ticks, about 1.5–2 h at 60 s.
- The NVMA classify cost (~3 ms each, production windows) bounds everything.

**Residuals (for the ledger):**
- **R1 — the engine grid is a day.** A sub-day peek is caught there only where it crosses midnight; this is pinned by `test_a_daily_grid_cannot_see_a_sparse_intraday_peek`. Per-decision coverage exists only for the swept components. The Governor and the harness book are covered end to end, but only at the day grid. `--step-hours` refines the grid at linear cost.
- **R2 — the component NVMA sweep uses schema-minimum windows.** The engine run uses production windows.
- **R3 — the engine sweep uses a small optimizer by default** (population 8, generations 8, minimum bars 100, minimum trades 5), so a short tape stages anything at all. `--production-optimizer` exists, and exits VACUOUS on a short tape.
- **R4 — the channel T1 cannot see.** A peek that is emitted together with the datum it peeks at is invisible to T1 by construction. T2 catches it; see §3.

## 2. Findings surfaced by stages 1–2 (not fixed; each needs an owner or ledger decision)

- **F1 — the fitness fill pays the entry bar's CLOSING spread.** `trade_path` charges `per_side_cost(bars[i+1].spread)` for a fill at bar i+1's OPEN. `LabelledBar.spread` is the spread at the bar's closing tick (`core/data/bars.py`), so the fill's cost uses a datum from after the fill: a small cost look-ahead, which could flatter or penalise. It is already pinned exactly by the existing exit tests (e.g. `test_a_trade_open_at_the_window_end_is_marked_at_the_last_close`). The leakage suite deliberately keeps the cost out of the fill decision so as not to false-alarm. **Proposal:** charge the signal bar's closing spread, the latest spread known at decision time. That changes fitness numbers, so it is not tightening-only. It is a T5-class convention decision.
- **F2 — QIEA's `fitness_window` bounds only the start of the span.** QIEA evolves on any bar after `now` that a caller hands it. The production caller never does: `LabelledBarCache.history(end=train_end)`, checked afterwards by `refuse_lookahead` and now by the evolution sweep. The fix is a one-line tightening in `core/optimizer/qiea.py`: keep only `b.ts + bar_seconds <= now`. This is the T8 precursor.
- **F3 — materialising the tick stream leaks the future into NVMA.** NVMA's session medians are a live callback into the `MarketStateFactory`, so a caller that does `list(market_states(...))` before labelling hands NVMA end-of-tape medians. Every current path is lazy. I found it in my own timing script. T8 (an accessor) would make it structural.
- **F5 — regime-sliced fitness windows are full of synthetic gaps** (surfaced by T6, see §5). QIEA evolves each regime on that regime's bars only, concatenated across time, so every junction between two regime stretches is a price jump the fitness simulator treats as one bar to the next. Before T6 a stop crossed at a junction filled at the stop price (optimistic); now it fills at the open after the jump, which is realistic for the series as simulated, but the series itself is an artefact. Measured on the leakage tape at 5-minute ticks: the one marginal champion that cleared C9 before T6 no longer does. **Owner/[spec]:** simulate each contiguous stretch separately (flat at every junction), or accept and declare it.
- **F4 — two portability notes:**
  - `scripts/governance_gate.py` resolves the checks folder as `REPO.parent / "specs_constitution"`, which is wrong inside a `.claude/worktrees/*` checkout;
  - the three pre-existing multi-line A16 guardrail cases cannot match on a CRLF checkout (this worktree). The main tree is LF and unaffected.

## 3. Stage 3: T7, the guard bites (`tests/backtest/test_leakage_controls.py`, ~10–14 s)

- **Instrument tests.** The perturbation moves every later price and doubles the future's scale. The market variants leave the past bit-identical and cut the side channels too. A decision cannot be stamped as emitted before its own horizon.
- **A centered EMA inside the real fitness simulator** (reading the next close): caught by BOTH T1 and T2.
- **A 5% sparse peek** (1 bar in 20; fast EMA += 3 × the next return): caught by both, but only at 6 of 479 cuts (T2) and 1 of 479 (T1). The test asserts that the violating fraction is under 5%. A 30-cut random sample would catch it about 31% (T2) or 6% (T1) of the time: the VALIDATOR's point, reproduced.
- **A labeller that reads the completing tick:** T2 catches it and T1 is blind to it, which is why both tests exist. The honest labeller at the same every-tick cadence raises nothing.
- **Through the real harness:** the next-tick-peek oracle is caught by T1 and T2, and the honest oracle raises nothing (55 decisions compared, 6 cuts).
- **Pinned limitation (R1):** the daily grid cannot see a peek on 1 tick in 20.

**Red lines (A16, blinding the instrument itself):**

| mutation | red line |
|---|---|
| T2 compares reference to reference | `('T2 future-perturbation: 479 cuts, 7647 decisions compared, no violation', 'T1 …')` |
| T1 compares reference to reference | `(…, 'T1 truncation: 479 cuts, 7636 decisions compared, no violation')` |
| `perturb_returns` returns its input | `E assert False` (the "every later price moved" assertion) |
| `PerturbedMarket` keeps the base returns | `('T2 future-perturbation: 6 cuts, 1723 decisions compared, no violation', …)` |

## 4. Stage 4: the look register (GAP-P12D-64)

**What a look is** (`tests/backtest/look_register.py`). There is one exclusively created file per look, `<register>/<seq:06d>.json`, opened with `open("x")` in the `HoldoutGuard.begin_final` pattern:
- a number already claimed is skipped, never overwritten;
- no code path deletes a look.

Each line records:
- the registration timestamp;
- the git commit, plus a dirty-tree flag;
- a sha256 of the full config;
- the hypothesis family;
- the data tier, derived and never claimed. A source that is not a declared real source (`dukascopy`, `histdata`) is tier 0, synthetic. Real data is tiered by its test windows: exploration before 2012, validation 2012–2023, holdout 2024–25, forward from 2026. A window that straddles two tiers is refused.
- the source, instruments, and date span;
- what changed since the family's previous look. This is required for a real re-look, and the line names that previous look's id, commit and config hash.
- the operator.

**The refusal.** `oos_runner.run_walk_forward` calls `verify_look` first, before any compute. A grade is refused unless its `Look` is:
- on disk, exactly as registered;
- for exactly this run: the same source, instruments, fold span, config hash and tier.

A hand-built `Look`, or one registered for another run, is refused. `RunInputs.look` is a required field, so no caller can forget it. The report gains `look = {look_id, family, tier, family_looks}`: the per-family look counts, by tier.

**Every entry point:**
- `scripts/run_oos_validation.py` is the only real-data grader. It requires `--family`, and takes `--changed` and `--operator`. It writes the line before the holdout marker and before the grade. It prints the per-family counts, and they go into `report.json`.
- The synthetic callers register tier-0 looks: `synthetic_grade.grade` (behind `falsify_engine` and the cost ladder) and the leakage engine.
- `grade_oracle` and the scripted `Backtest.run` tests are harness self-tests on synthetic tapes. They do not go through `run_walk_forward` and do not register.

**No threshold or gate changed.**
- `git diff` on `report.py` shows only one import and one new field, `look: Mapping = field(default_factory=dict)`, commented "no clause of `passed` reads it".
- `build_report`, `grade_out_of_sample`, `DSR_MIN`, `_MIN_*` and the `passed` expression are byte-identical.
- `oos_runner` attaches the look with `dataclasses.replace` after `build_report` has computed `passed`.

**Red lines (A16):**

| mutation | red line |
|---|---|
| verification bypassed | `AttributeError: 'NoneType' object has no attribute 'has'` (the grade ran into the engine instead of refusing) |
| `open("x")` → `open("w")` | `assert ('000001', '000003') == ('000001', '000004')` (a claimed number was overwritten) |
| tier forced to synthetic | `assert 0 == 2` |
| what-changed not required | `Failed: DID NOT RAISE LookRefused` |

**Costs:** negligible (one small file per grade, one git call).

**Residuals:**
- **R5.** The register COUNTS looks. Deflating by them is the VALIDATOR's option B/C (GAP-P12D-33), which is the owner's decision.
- **R6.** Nothing yet stops someone grading real data outside `run_walk_forward`, for example a new script that drives `Backtest.run` directly. The contract is enforced at `run_walk_forward` only.
- **R7.** Each synthetic run keeps its own register under its run directory, so tier-0 counts are per run, by design.

## 5. Stage 5: T6, the gap-through exit

**The fix** (`core/optimizer/fitness.py`). A long stopped out exits at `min(bar.open, sl)`, a short at `max(bar.open, sl)`. It tightens only:
- a stop touched intrabar still fills at the stop;
- stop-before-target holds on a gap bar, even when the bar's range later reaches the target;
- a bar that opens BEYOND the target still fills at the target, never at the better open.

**Tests** (`tests/unit/test_fitness_exits.py`, in the mutation gate's test set), each hand-worked, long and short:
- `…_opens_through_the_stop_exits_at_the_open_not_the_stop` pins the whole `Trade` and the PnL;
- `…_opens_exactly_at_the_stop_exits_at_the_stop`;
- `…_gap_through_the_stop_is_not_rescued_by_a_rally_to_the_target`;
- `…_gap_through_the_target_is_not_credited`.

The gap bar's close differs from its open, so reading the wrong price cannot pass.

**Pinned exactly (mutation scope).** Five hand mutants were all killed:
- `bar.open` → `bar.close`, long and short;
- min ↔ max, long and short;
- the target credited at the open.

**Red before the fix:** `assert (52, 1.092805249724446) == (52, 1.0923568246417799)`, the exit at the stop instead of the gapped open. **A16:** reverting either direction gives `AssertionError: assert Trade(signal_... marked=False) == Trade(...)`.

**Costs:** none measurable.

**Residual:** fitness scores change wherever bars gap through stops, so champions selected before and after `e51e5cc` are not comparable. This is expected, and tightening only.

The effect is larger than "slightly" wherever bars hold one tick: at 5-minute ticks every 60 s bar is O = H = L = C, so every stop exit is a gap exit. On that tape the leakage suite's reference went from one champion to none and exited 5 (VACUOUS) rather than report a clean sweep over nothing. `1cd13d4` moves the script's default to 60 s ticks, which stages a champion and places 20 orders under T6 (probed). See F5 for why the junctions matter.

**Draft ACIS-03 §6.1 wording** (for the lead; `specs/` untouched). Replace "exit intrabar at ATR-multiple SL/TP (SL checked before TP on the same bar — conservative)" with:

> exit intrabar at ATR-multiple SL/TP (SL checked before TP on the same bar — conservative); **a bar that opens through the stop exits at that open, the first price after the gap, and a bar that opens beyond the target still exits at the target (v1.x, GAP-P12D-65 T6 — tightening only)**

## 6. Stage 6 (T4 / T8): not built

It was skipped deliberately. The power cut cost the session its margin, and the engine evidence run had the better claim on the remaining compute.

Concrete next steps:
- **T8:** a decision-time accessor on `LabelledBarCache`, e.g. `bars_until(instrument, end)`, used by `oos_runner`'s TSMOM seeding, which today reads whole years and filters by `train_end` itself. Then a lint test that forbids `cache.read(` outside `regime_labels.py` and the leakage extractor, plus F2's `fitness_window` upper bound.
- **T4:** a `calibrated_on: {start, end}` field on calibrated config values, and a check in `HoldoutGuard.check_development` / `begin_final` that refuses a fold whose test window overlaps one.

## 7. For the lead (ledger items to write; `KNOWN_GAPS.md` untouched)

- **GAP-P12D-65:**
  - T1, T2 and T7 are built, with commits and tests as above;
  - T6 is built;
  - T3, T4, T5 and T8 remain open;
  - residuals R1–R4;
  - findings F1–F3 need IDs.
- **GAP-P12D-64:** the register is built (`97591b2`), with residuals R5–R7. The [spec] half (raising the gate per look) stays with the owner.
- **F4:** two small tooling tickets: the gate path inside worktrees, and CRLF-proof A16 anchors.
