# BUILDER REPORT — five-agent edge pass, 2026-09-24

**Ledger pointer.** This pass's ledger entry is the one the brief assigns, and the lead writes it.
It is not in this branch's `KNOWN_GAPS.md`, so the ID is deliberately not written here.
`ledger_check` L2 correctly refuses a citation that resolves to nothing on the branch. Add the ID
back when the entry lands.

**Status of everything below: BUILT — PENDING AUDIT (A5).** I am a finder, not a clearer. Nothing
here is merged, nothing is in `KNOWN_GAPS.md`/`TODO.md`, and every claim is reproducible from a
test, a commit or a script named below.

- **Who:** BUILDER, running in fresh context on Opus 5.5, in an isolated worktree.
- **Scope:** `FIVE_AGENT_BRIEF_2026-09-24.md` §0 and §5.
- **Independence:** I launched no subagents and used no web access (§5 grants none).
- **Branch:** `worktree-agent-a128ab904780ce593`.
- **Worktree:** `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a128ab904780ce593`.
- **Scratch** (all diagnostic scripts and run outputs): `SCRATCH/BUILDER/`, with
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.

## Executive summary
1. **The grader now recognises a known-good strategy.**
   - An oracle that knows the planted episode sign clears **every non-DSR clause of `passed`** on
     the ladder's fold plan (25 folds, 2.53 graded years, EUR_USD): Sharpe 10.2, DD 0.94%, win 99.3%,
     PF 555, 100% positive months, SPX 0.07, avg duration 7.1 h, 2,656 trades.
   - On null the same logic fails 5 §14 rows (Sharpe −1.21, PSR 0.023).
   - Evidence: the scratch script is reproducible, and the fast test (`test_the_harness_recognises_the_oracle_on_planted_and_refuses_it_on_null`, ~40 s) pins the shape.
2. **The ratified DSR gate cannot pass the oracle.** *(Corrected after audit E4; see "Fixes after
   dual audit".)*
   - With no trials the oracle cannot pass by construction (`trial_count` 0 < 2). The gate was not
     touched.
   - The engine's recorded planted trial sets demand a per-trade **SR0 hurdle** of 5.654 (ladder
     1x, 106 trials) and 2.430 (2026-09-15, 121 trials, reproducing GAP-P12D-37).
   - **Withdrawn:** my earlier "the oracle scores DSR 0.000 under both" was not a Deflated Sharpe in
     Bailey & López de Prado's sense, and neither was "the oracle's per-trade Sharpe is only 1.273":
     - the oracle is not a member of the trial set;
     - the trial Sharpes come from roughly 5-trade holdouts, against the oracle's roughly 2,600-trade
       record. Against a like-for-like SR0 (about 0.05) the oracle's DSR is 1.0.
   - The conclusion stands; the mechanism was wrong. The gate as fed refuses everything because of
     that T-mismatch, not because the oracle is weak.
3. **`falsify_engine.py` now runs the oracle as stage 1.**
   - A full run is VOID (exit 4) and the engine never runs unless the planted oracle clears every
     non-DSR clause and the null/permuted oracles clear none.
   - What the engine run grades is unchanged.
   - Evidence: tests with stubbed stages.
4. **GAP-P12D-38 is REFUTED: there are no zero-duration trades.**
   - On the uniform 20 s synthetic tape, tick velocity always equals its session median. The
     surge ratio is exactly 1.0, so MOMENTUM_SCALP **can never fire on any synthetic market**.
   - The "zero duration" was `_avg_duration` reporting an empty population's mean as 0.0.
   - Exact 20 s-grid arithmetic puts the planted §14 band at **1,628 trades, not 407**. 407 is
     impossible, since its sum would be 194,345 s, not a multiple of 20.
   - Fixed: an empty mean is now NaN.
   - Evidence: `test_momentum_scalp_can_never_fire_on_a_uniform_synthetic_tape`.
5. **TSMOM holds straight through the edge (aggregate evidence; per-trade bucketing is BLOCKED).**
   - The mean TSMOM trade lasts 53.4 h, against 1–4 h planted episodes. A 48 h hold crosses at
     least 11 episode boundaries.
   - Its 63–252-day vote has no edge on any synthetic market at its hold horizon (measured, 16 paths).
   - About 96% of its loss is direction.
6. **The engine's TSMOM is not Moskowitz–Ooi–Pedersen**, mainly because of the *harness*.
   - The backtest book force-closes every position at 48 h (`Backtest(max_hold_s=48*3600)`) and
     TSMOM re-enters, so the "2.3-day hold" is that cap.
   - MOP hold for a month on a single 12-month signal. The signal itself is a declared 3/6/12-month
     vote variant.
   - Evidence: grade (a) for the literature, recalled not re-fetched; the code reference is exact.
7. **TSMOM's standing vote vetoes the rest of the arena.**
   - It emits on every tradeable tick, so every opposite-direction signal on its instrument dies in
     `DISCARD_OPPOSITE` (real-AGON fixture).
   - All 360 promotion stalls in the ladder run begin exactly when TSMOM first had 260 daily closes
     (2015-02-03); there were 0 stalls in 2014.
   - Evidence: on-disk rare-event log.
8. **The §5.6 plateau law is in the optimizer's staging path.**
   - Every gene is perturbed by **±10% of its declared range** (with rounding, clamping and invariant
     repair). That step is the lead's delegated ruling on audit E6; it was 10% of the value until then.
   - A neighbour "dies" if it fails C9 on the same train window, and any death refuses the champion.
   - A refused champion still counts as a Deflated Sharpe trial (audit F3).
   - Cost: **2.61 s per champion, 3.4% of an evolution run** (production config).
   - It refuses 9–10 of 30 champions on the repo's zigzag fixtures (it was 11–14 at 10% of the value),
     mostly on `ema_fast` or `rsi_period`.
   - The reading of "dies" interprets spec prose, so it is **owner-ratification-flagged**.
9. **Every QIEA evaluation is now logged, including gated-out runs** (logging only). This
   enables PBO/CSCV later, at about 45 KB per evolve call.
10. **Suite: 808 → 828 passed at the first hand-off; 847 passed after the audit fixes (+6
    data-absent skips); ledger 187 entries, 0 violations.**
    - All 12 falsification mutants of the first batch are dead:
      - F6 was an equivalent mutant; its docstring now names the second barrier;
      - F12 exposed a blind spot, killed by a new test.
    - Every audit fix has its own falsification record, below.

## Fixes after dual audit (2026-09-25) — each BUILT — PENDING AUDIT
**Sources.** The two constitutional audits of this branch at `9b9ec80`:
- `archive/AUDIT_BUILDER_BRANCH_INTERNAL_2026-09-24.md` (F1–F9);
- `archive/AUDIT_BUILDER_BRANCH_EXTERNAL_2026-09-24.md` (E1–E9).

Both are in the main tree. The lead triaged them into ten fixes.

**How they were made.** Each fix is its own commit on this branch: green in a full run, falsified
per A16 (the fix reverted or mutated, red for its stated reason, then restored and re-verified),
then committed. A power cut and a session limit hit mid-batch. Afterwards every uncommitted file
was compile-checked and read in full before it was committed.

**Suite.** 828 → **847 passed, 6 skipped** (data-absent). Ledger: 187 entries, 0 violations.

| # | Finding | Commit | What changed | Test (the red line under the reverted fix) |
|---|---|---|---|---|
| 1 | **F3** (MUST FIX): the plateau law shrank the DSR trial set | `6c8bb50` | `QIEA.evolve_outcome()` returns `(champion, candidate)`. A holdout-passed candidate the plateau law refuses stays a DSR trial, marked `plateau_refused`. `evolve()` is unchanged for callers. | `test_a_plateau_refused_candidate_stays_a_deflated_sharpe_trial`: base (law off) and head count the same trials. Red: `assert ([] == [12.772798952055345]` |
| 2 | **F1** the 2-fold control missed the defect class | `9dd274d` | Full-scale fast test: `plan(1,30,25)`, 300 s tape, EUR_USD, dev_paper; ~70 s. | `test_the_planted_oracle_clears_every_non_dsr_clause_at_full_fold_scale`. Red under `DURATION_MAX_S = 4 h`: `assert ('section-14 avg_duration',) == ()` |
| 2 | **E1** the oracle is saturated; no power near the cut-off | `9dd274d` | The oracle's `sign_error` makes it wrong on a hash-chosen share of whole episodes (`SyntheticMarket.episode_at`). **Profit factor 1.4 is the clause that binds first**; the Sharpe cut never does. Stage 1 grades `oracle.RUNGS` and VOIDs unless near-pass passes and near-fail is refused by a §14 row. | Coarse tape: p = 0.42 gives PF 1.46 (pass) and p = 0.45 gives PF 1.29 (fails exactly `section-14 profit_factor`). Red under a perfect-oracle mutant: `assert () == ('section-14 profit_factor',)`; dropping the stage-1 rungs: `assert 0 == 4` |
| 3 | **F2** stage 1 always VOIDed on weekend-flat accounts | `3412f54` | `tests/backtest/oracle_loop.py` (split from `oracle.py`) keeps the rules: flat 30 min before Friday's rollover, and before each fold's test end; nothing opened in the preceding `min_hold`; never reverses or closes a position younger than `min_hold`. `book.py` honours `action="close"` at the tick's mid. `void_reasons`: any oracle rule violation VOIDs, and a control counts as refused only by a §14 row. | `test_on_a_weekend_flat_min_hold_account_the_oracle_keeps_the_rules_and_the_grade_decides` (prop_demo), plus 4 unit tests. Five mutants all red, e.g. weekend rule ignored `(('weekend_holding',) == ()`, fold-end deadline dropped (same line), min hold ignored (flip after 20 s, not 60 s) |
| 4 | **E3 + F4** `--kinds` without planted "held" | `7d1d972` | A full run needs planted AND at least one control; otherwise NO VERDICT, exit 5, before anything runs. The held message names only the markets graded. | `test_no_verdict_without_the_positive_control_and_a_control`. Red: `assert 0 == 5` |
| 5 | **E2** a DSR-only planted failure was charged to the engine | `11fbe54` | The grade row carries `non_dsr_failed`. When planted is the only wrong answer and that list is empty: GATE-LIMITED, exit 6, "uninterpretable, NOT an engine verdict". Exit codes are documented in the script docstring. | `test_a_planted_refusal_only_by_the_dsr_gate_is_gate_limited_not_an_engine_failure`. Red: `assert 1 == 6` |
| 6 | **E4** "oracle DSR 0.000" was not a DSR | `4b1e723` | `oracle_deflation.json` and its print are removed. Each engine run reports the per-trade **SR0 hurdle** (`sharpe_threshold` over the harness's own trial filter and N), labelled as a hurdle. `OracleGrade.trade_returns` and `per_trade_returns` (stage-1 scaffolding) are removed. | Handover test pins no file and two labelled hurdle lines. Red: `assert not True` |
| 7 | **E6** (the lead's delegated decision) value-relative step | `b842214` | A neighbour moves each gene by **±10% of its GENE_SPECS range**; rounding, clamping and repair are unchanged. | Hand-worked table, bounds and trench pins recomputed. Red under the value step: `Mismatched elements: 20 / 22` |
| 8 | **F5** a repaired move logged with its intended direction | `bb18730` | `Neighbour.direction` is the ACTUAL move after repair; duplicate neighbours are skipped. | `test_a_repair_that_carries_the_move_past_the_champion_is_logged_as_it_happened`. Red: `[(-1, 2.1), (1, 2.4)] == [(1, 2.1), (1, 2.4)]` |
| 8 | **F9** the registry omitted the plateau neighbours | `bb18730` | `EVOLUTION_EVALUATIONS.neighbours` records each neighbour's genome and train fitness. | `test_the_plateau_neighbours_are_recorded_too`. Red: `assert (None is None and 0 == 22)` |
| 9 | **F6 + E7** bare `NaN` in JSON | `76f2ce7` | `oos_runner.strict_json` (non-finite → null, `allow_nan=False`) now writes every report, `ladder.json` (new `ladder_document`) and the data-validation `report.json`. | `tests/backtest/test_strict_json.py`, whose parser refuses NaN and Infinity. Red: `ValueError: non-RFC-8259 constant NaN` |
| 10 | **E9** 10,000 units = $18M of gold | `039a687` | The oracle sizes whole units to one NAV of USD notional per instrument via `money.quote_to_account`. | `test_the_oracle_sizes_one_nav_of_notional_on_every_instrument` (EUR 9,090 / JPY 10,000 / XAU 5). Red: `assert (10000 * 1.1) <= 10000` |

**Measured along the way.**
- **Stage-1 rung calibration** (the falsification default: `plan(60, 30, 25)`, 20 s tape, dev_paper;
  `SCRATCH/BUILDER/rung_scan.py`):
  - p = 0.42 on EUR_USD + USD_JPY: Sharpe 6.09, **PF 1.593**, win 0.585, positive months 100%, every
    clause met (1,380 s).
  - p = 0.46: **PF 1.251** on EUR_USD alone and 1.316 on USD_JPY alone, both failing only
    `section-14 profit_factor`. The oracle decides per instrument, so the pooled PF lies between the
    two and fails too.
  - Not run: the two-instrument grade at p = 0.46 was not run end-to-end. The pooled figure is
    inferred from the two single-instrument grades (a pooled PF is a mediant of the two, so it lies
    between them).
  - Coarse-tape curve (EUR_USD), PF by p: 13.5 (0.00), 3.98 (0.20), 2.44 (0.30), 1.98 (0.35),
    1.60 (0.40), 1.46 (0.42), 1.43 (0.43), 1.36 (0.44), 1.29 (0.45), 1.25 (0.46).
- **Weekend-flat accounts on the coarse full-scale tape** (`SCRATCH/BUILDER/coarse_accounts.py`):
  - prop_demo and ftmo: planted `()`; null and permuted fail §14 rows only; no rule violations;
    `void_reasons == []`.
  - dev_paper is unchanged.
- **Plateau refusals under the range step** (unit config, seeds 1–30): trend zigzag **10/30** (was
  14/30) and ranging-25 **9/30** (was 11/30).
  - `rsi_overbought` now kills in 2 and 3 of those; `ema_fast` in 8 of each.
  - Cost is unchanged: at most 22 neighbours.

**New findings the fixes surfaced** (for the lead; I changed nothing beyond the fixes).
- **The harness carries open positions through the observe-only embargo** (7 days, always spanning
  a weekend), where no strategy can act and orders emitted on warm-up ticks are never applied.
  - On a weekend-flat account, any ENGINE position open at a fold's test end is therefore booked as
    `weekend_holding`, whatever the engine does.
  - The oracle now avoids it by flattening before each fold's end. The engine cannot.
  - Proposed Status: open, Severity high on weekend-flat accounts (FTMO), [impl].
- **The range step (E6) makes large RELATIVE moves on period genes near their floor.**
  - Example: seed 42's zigzag champion has `ema_fast = 6`. Its +4.5 neighbour rounds to 10, a +67%
    move, and dies there.
  - The range step is uniform on the search-range scale, not on a log scale. That matters for EMA
    periods, whose effect scales with the ratio.
  - Owner note: a log-scale step for period genes is the natural alternative.
- **Test-fixture churn from E6.** Six tests that only need *a* staged champion moved from seed 42
  or 9 to seed 5:
  - `test_evolve_returns_valid_paramset_and_logs_run`;
  - `test_same_seed_same_history_identical_champion`;
  - `test_evolves_on_every_bar_inside_the_span_not_a_bar_count`;
  - the promotion-cycle integration test, plus the registry and trench tests.

  Their intent is unchanged, and the refusals themselves are pinned.

**Updated ACIS-03 v1.5 draft** (it supersedes the §6.4 wording in the Stage 4 section below): "…
the neighbour is the champion with g ← g + d·0.10·(hi_g − lo_g) …; `direction` records the gene's
actual move after repair; a candidate the law refuses is not staged but remains a Deflated Sharpe
trial (it consulted the holdout); `EVOLUTION_EVALUATIONS` also lists the plateau neighbours." The
open owner questions on "dies" (the C9 cliff vs relative degradation), joint vs one-at-a-time
moves, and GAP-0035's unread genes stand.

**Left for the lead, per the triage:**
- F7: land the ACIS-03 amendment at merge;
- F8: relocate this report and the PARTIAL pointer, and cite a gap ID in `plateau.py`;
- E8: the research-simulator design note.

E5 (TSMOM's declared spot-return deviation rests on wrong premises) was outside my list. It also
corrects my Stage 3 claim: the deviation **is** declared, at `core/signals/canonical.py:101-102`
(GAP-0073, closed). What E5 disputes is its premise ("excess over risk-free", "immaterial").

## Setup
- **Branch base.** My worktree branch was cut at `e00fdd3`, 84 commits behind local `main`, most
  likely from a stale remote ref. It had no unique commits, so I fast-forwarded **my branch**
  (`git merge --ff-only main`) to `7695ed0`. `main` was not touched.
- **Baseline.** `python -m pytest -q` gave **808 passed, 6 skipped (814 collected) in 176.8 s**.
  The skips are `skipif` markers for data absent from the worktree (`test_financing.py:55`,
  `test_sources.py:172/187`). `scripts/ledger_check.py` gave 187 entries, 0 violations.
- **Commits** (all on my branch):
  - `1d40ed0` checkpoint
  - `77ac588` stage 1
  - `2fcf3d1`, `533b202` stage 2
  - `904b409` stage 4
  - `fbae9e1`, `445198e` stage 5

  Stage 3 is report-only.
- **Checkpoint.** `archive/PARTIAL_BUILDER_2026-09-24.md` is superseded by this report.
- **Machine limits.** Free memory ran between 0.83 and 1.85 GB all session, with other agents'
  Python jobs running. Every simulation was run one at a time, only after checking at least 1 GB was
  free.

---

## Stage 1 — Oracle positive control (GAP-P12D-37) — BUILT — PENDING AUDIT
**What was built.**
- `tests/backtest/oracle.py` (188 lines):
  - `OracleLoop` holds 10,000 units (one NAV of USD notional since E9; now in `oracle_loop.py`, F2)
    in the direction of the planted episode *in force*. It reads
    `SyntheticMarket.episode_sign`, never the next episode, and never sees the noise. It reverses
    when the state changes and re-asserts at the first graded tick of each UTC day, so a max-hold
    close does not leave it flat.
  - `grade_oracle` drives it through the **same** `Backtest`, `PositionModel` book,
    `evolve_step.cost_model` C8 map, rulebook, swap conventions, session boundaries, clusters,
    `compute_metrics` and `build_report` as `oos_runner.run_walk_forward`. Only the decision layers
    are replaced.
  - `oracle_ticks` skips the `MarketStateFactory`, which costs about 1 ms/tick (session calendars
    and velocity rings), and carries only the six fields the harness reads.
    `test_oracle_ticks_equal_the_factory_path` pins those fields equal to the factory's, in the same
    merged order and across the weekend cut.
  - `non_dsr_failures` is every clause of the ratified `passed` except the trial count and the DSR,
    read from `report.py`'s own constants. `test_non_dsr_failures_is_every_clause_of_passed_but_the_trials`
    pins that this mirrors `passed`.
- `synthetic_market.py`:
  - The episode schedule is now ONE source (`_draw`/`episodes`/`index_of`/`episode_sign`), applied
    by `_returns` and read by the oracle.
  - **Every market is bit-identical to before.** sha256 fingerprints were taken of the returns and
    of sample ticks for 3 specs × 3 kinds, before and after (`SCRATCH/BUILDER/market_fingerprint.py`).
- `harness.py`:
  - ~~`per_trade_returns` extracted~~ (reverted by E4: it only fed the withdrawn deflation; the
    harness expression is verbatim again).
  - A read-only `graded_trades()` accessor. Grading is unchanged.
- `synthetic_grade.py`:
  - `oracle_row`, the worker behind stage 1.
  - The engine row now also returns its `trial_sharpes`.
- `scripts/falsify_engine.py`:
  - Stage 1 grades the oracle on every market. `void_reasons` returns exit 4 before any labelling
    or engine compute unless planted is recognised and null/permuted are refused.
  - ~~After the engine stage, it writes `oracle_deflation.json`~~ (removed by E4; each run now
    reports the gate's per-trade SR0 hurdle).
  - A `--quick` run prints stage 1 and never voids, because its span is too short for any verdict.

**The oracle's full §14 record** (scratch `oracle_record.py`; EUR_USD; the ladder's exact plan `plan(60, 30, 25)`, 25 folds, 985 days; account `dev_paper`; declared 1x costs).

| row | planted | null | §14 bar |
|---|---|---|---|
| annual Sharpe | **10.20** ✓ | −1.21 ✗ | > 1.5 |
| max drawdown | **0.94%** ✓ | 28.44% ✗ | < 15% |
| win rate | **0.993** ✓ | 0.480 ✗ | > 0.48 |
| profit factor | **555.5** ✓ | 0.901 ✗ | > 1.4 |
| positive months | **100%** ✓ | 33.3% ✗ | > 70% |
| SPX correlation | 0.074 ✓ | −0.046 ✓ | < 0.25 |
| avg duration (band) | 25,468 s = 7.1 h ✓ | 7.1 h ✓ | 30 min – 48 h |
| trades / years / folds | 2,656 / 2.53 / 25 ✓ | same ✓ | ≥ 30 / ≥ 2 / ≥ 2 |
| rule violations, guardrail hash | none, matches ✓ | none, matches ✓ | — |
| net PnL (NAV $10k) | +$310,846 | −$2,538 | — |
| per-trade Sharpe (skew, raw kurtosis) | 1.273 (1.65, 6.42) | −0.039 | — |
| **`trial_count`** | **0 ✗** (needs ≥ 2) | 0 ✗ | ratified |
| **DSR as reported** (no trials, so it is the PSR against 0) | 1.000 | 0.023 | ≥ 0.95 |
| ~~DSR under the ladder-1x planted trial set~~ — **WITHDRAWN (E4)**: the per-trade SR0 **hurdle** of that set is 5.654 (106 trials) | ~~0.000~~ | ~~0.000~~ | — |
| ~~DSR under the 2026-09-15 planted trial set~~ — **WITHDRAWN (E4)**: SR0 hurdle 2.430 (121 trials) | ~~0.000~~ | ~~0.000~~ | — |

Reading the table:
- The null oracle's loss is friction plus noise. The declared per-trade cost is about $0.84, and
  × 2,656 trades that is about $2,231 of the $2,538.
- The planted PnL is huge because perfect knowledge of a 0.15σ-per-step drift is worth a great deal.
  **The oracle is an upper bound, not a target.**
- **Refusal evidence for GAP-P12D-33/37** *(corrected after audit E4)*:
  - No trials means no pass by construction.
  - The hurdle the engine's own trial sets demand is set by roughly 5-trade holdout estimates. A
    per-trade Sharpe over thousands of trades is not commensurate with it, so the "oracle DSR 0.000"
    and the "4.4× / 1.9×" ratios I gave here were withdrawn: they measured that T-mismatch, not the
    oracle.
  - As fed, the gate refuses everything; the VALIDATOR and both auditors agree. I did not modify the
    gate.

**Tests** (`tests/backtest/test_oracle_control.py`, 8):
- the schedule is exactly the planted drift;
- `episode_sign` returns the state in force, with no foresight;
- oracle ticks equal the factory path;
- `non_dsr_failures` mirrors `passed`;
- `void_reasons`;
- a failed oracle voids the run before any engine compute (0 engine calls, exit 4);
- a recognised oracle hands over to the unchanged engine stage and writes `oracle_deflation.json`;
- **the positive control:** 2 folds, 29 days, EUR_USD, ~40 s. Planted net +4,802, Sharpe 14.8,
  PSR ≥ 0.95. Null PSR 0.084, less than a tenth of planted's PnL, and at least one §14 failure.

**Falsification (A16).** Each mutant was applied to the committed code, run, then restored with
`git checkout`, and the diff verified empty.
- **F1** inverts the oracle's sign → `AssertionError ... assert (Decimal('-4906.22721973487903750000') > 0)`.
- **F2** gives null the drift →
  - `assert -1.141088661469096e-05 == 1.141088661469096e-05 ± 1.0e-15` (schedule test);
  - `AssertionError: 0.9999999999999997 ... assert 0.9999999999999997 < 0.95` (null PSR).
- **F3** disables the void gate → `IndexError: list index out of range` and `AssertionError: assert 0 == 4`.
- **F4** drops the rule-violation clause → `AssertionError: (False, ())`.

**Measured cost.**
- Positive-control test: ~40 s.
- One market over the full 25-fold plan: 353 s (planted) and 370 s (null), EUR_USD only, under load.
- Stage 1 of a real `falsify_engine` run, with 2 instruments and 3 markets, is therefore about
  10–20 min per market per worker.

**Residuals.**
- The CLI's stage 1 has not run end-to-end on the real synthetic markets. That is a full
  falsification run, which is off-limits. The wiring is tested with stubs, and the grading ran
  through the scratch script, on EUR_USD only.
- The oracle was not graded on permuted, though `falsify_engine` stage 1 covers it.
- The oracle's holds straddle weekends. On an account with `weekend_holding_allowed: false` it would
  log rule violations, so the positive control is account-dependent. Run stage 1 on `dev_paper`, or
  make the oracle flatten before the weekend.
- `non_dsr_failures` imports report.py's private `_MIN_*` constants. That is one source, but it
  couples to underscore names.

## Stage 2 — The zero-duration artifacts (GAP-P12D-38) — BUILT — PENDING AUDIT
**Root cause (a harness reporting defect plus a coverage hole; not an open-and-close on the same tick).**
1. **MOMENTUM_SCALP is dead on every synthetic market.**
   - Ticks arrive every 20 s. The factory's velocity window is 10 s
     (`system_config.yaml: tick_velocity_window_s: 10.0`), so every tick's velocity is 0.1 and
     equals its own session median.
   - `ratio = 1.0 < momentum_scalp_surge_ratio` (1.5, schema-floored above 1), so the module is gated off.
   - A second, independent barrier: at ratio 1.0 its conviction `clamp01(1/3) = 0.333` is below
     `conviction_discard` (0.45, which is also its stageable floor).
2. **The empty mean read as zero.** `metrics._avg_duration` returned **0.0 for an empty
   population**, the same number a population of zero-duration trades gives. The finder read the
   empty scalp carve-out's 0.0 as about 1,598 zero-duration trades.

**Proof.**
- Real `MarketStateFactory` + real AGON (wired as `build_paper_loop` wires them) on 4 h of planted
  ticks: the surge ratio is **exactly 1.0 on every tick** and the scalp fires 0 times. The same bars
  with doubled velocity fire it 666 times, so the module is alive and the tape is dead.
- Exact arithmetic on the 2026-09-15 run's own averages (`SCRATCH/BUILDER/gap38_arith.py`): every
  timestamp is on the 20 s grid, so every duration sum is a multiple of 20 s.
  - **Planted:** the band count must be **1,628**. The ledger's 407 gives 194,345 s, and 194,345 mod 20 = 5.
  - **Permuted:** the ONLY feasible split is **1,717 band / 394 TSMOM / 0 SCALP**.
  - **Null:** feasible splits include (1,466 / 398 / 0).
- Every attributed synthetic report on disk (8) has **0 MOMENTUM_SCALP trades**.
- So about 81% of graded trades were in the §14 band, the reverse of the finding.

**Fix.** An empty population's mean is NaN (null in every report JSON), never 0.0.
- The §14 band grade is unchanged: an empty band failed the 30-min floor at 0.0, and NaN fails
  every comparison.
- The one assertion that pinned the old 0.0 (`test_duration_averages_hand_worked`) now pins NaN.
- `metrics.py` is exactly 300 lines, within the budget.

**Tests** (`tests/backtest/test_zero_duration_artifacts.py`, 2):
- `test_momentum_scalp_can_never_fire_on_a_uniform_synthetic_tape`
- `test_an_empty_carve_out_has_no_mean_duration_never_zero` (a real 0.0 stays visible)

**Falsification.**
- **F5** reverts to `return 0.0` → `assert (False) ... isnan(0.0)` in both tests.
- **F6** loosens the surge gate only → **stayed green: an equivalent mutant.** The conviction floor
  also blocks. The fixture docstring now names that barrier (`533b202`).
- **F6′** removes both barriers → `assert 666 == 0`. Killed.

**Residuals.**
- **Coverage hole:** the whole falsification suite never exercises MOMENTUM_SCALP. **Proposed**
  (owner or design decision; it changes the positive-control market): give the synthetic tape a
  varying arrival rate, such as Poisson arrivals with session intensity, or clustering inside
  episodes, so velocity surges exist. Or grade the scalp on a separate tape.
- Report consumers that format `avg_duration_s` now print `nan` for an empty population.

## Stage 3 — TSMOM attribution — REPORT ONLY; per-trade bucketing BLOCKED
**Per-trade records are not on disk.**
- `engine/rung_1x/acis.sqlite` holds 0 `market_state` rows.
- The replay log keeps only the first 200 of each sampled type (SIZED: 1,575,748 counted, 200 kept),
  and has **no close/trade event type at all**.
- `rung_1x.json` holds aggregates only.

**The bounded diagnostic is BLOCKED.** Free memory was 1.13 GB when I checked (peak 1.85 GB all
session), against the brief's ≥ 2 GB rule.

**Run spec for the lead**, written, compiled and not executed: `SCRATCH/BUILDER/tsmom_diag.py`.
- Copy the ladder's label cache, read-only:
  `data/validation/cost_stress/20260917T083216Z/labels/` → `<OUT>/labels/`. It is 69 MB, and its
  key `14c1b3e4…` equals the current `LabelSpec`, verified.
- Run with `--workers 1` equivalent (a single process):
  `python tsmom_diag.py <worktree> <OUT> 9,10`.
- Folds 9–10 (tests 2015-02-10 → 2015-04-18) are the first folds with TSMOM live.
- It uses the ladder's exact `MarketSpec` and fold plan, the 1x costs and the production config.
- TSMOM's daily history is seeded from all labels up to fold 9's train end, so TSMOM is live from
  the first graded tick.
- It patches `close_at` to record, for every closed trade: strategy, direction, entry/exit, **exit
  reason** (stop/target/reverse/max_hold), duration, PnL, return, the planted sign at entry, and
  **the planted episode boundaries crossed**.
- Estimate: about 10–12 min per fold (evolution on 60-day windows plus ~228k ticks).
- Outputs `tsmom_diag.json`. Bucket its `trades` by `duration_h` and `boundaries_crossed`.

**What the on-disk evidence and fixtures already establish.**
- **Aggregate:**
  - TSMOM made 455 trades, net −152.49, win 0.468, PF 0.771.
  - **avg 192,318.8 s = 53.4 h**, against planted episodes of 1–4 h (mean 2.5 h).
  - The ladder's rungs move TSMOM only −152.49 → −175.41 for 4× the friction, so friction is about
    5.7 per 1x. **About 96% of TSMOM's loss is direction.**
- **The 48 h cap.** The harness book closes EVERY position at 48 h (`tests/backtest/harness.py:93`,
  `max_hold_s: float = 48 * 3600`, passed to `PositionModel`; `book.py:132`), TSMOM included.
  - A mean of 53.4 h > 48 h fits max-hold exits extended over the synthetic weekend gap (no ticks
    Fri 21:00 → Mon 00:00 UTC). If starts are uniform, max-hold trades average about 59 h, so
    roughly 85–90% of TSMOM trades are 48 h truncations. That is inference, not measured.
  - A 48 h hold crosses **at least 11** planted episode boundaries (48 h / 4 h maximum episode),
    and about 19 on average.
- **No edge at TSMOM's horizon.**
  - Script: `SCRATCH/BUILDER/tsmom_bridge.py`, 8 seeds × 2 instruments, the ladder's `MarketSpec`,
    the 63/126/252-day vote, non-overlapping 2-day holds.
  - Direction edge per hold (mean/sd) with the markets as generated (whole-path demeaned):
    planted −0.044 (path sd 0.052), null −0.041 (0.069), permuted −0.028 (0.068).
  - Without the demeaning: −0.011, −0.026, +0.090.
  - On the ladder's own path (seed 7): t = −1.69 (EUR_USD) and −0.97 (USD_JPY).
  - Demeaning a whole path makes it a bridge, which drifts back toward its start and so tilts
    long-horizon trend votes slightly negative. The evidence for that is moderate: −3.4 SE on planted
    and −2.4 SE on null, and the kinds share noise, so they are not independent.
  - TSMOM's −146.8 gross directional loss sits about −2.1 sd from a zero-edge sum (per-trade sd
    ≈ 3.24, inferred from the gross win + loss) and about −1.2 sd from the bridge-tilted expectation
    (≈ −65).
  - **Nothing requires a TSMOM code bug.** The loss is a no-edge 2-day trend vote on an unfavourable,
    bridge-tilted path.
- **Arena interaction** (`SCRATCH/BUILDER/tsmom_blocking.py`, real AGON fixtures).
  - A TREND up-cross with no TSMOM history emits TREND.
  - With TSMOM voting UP, it emits TSMOM only: the same-direction duplicate loses the conviction dedup.
  - With TSMOM voting DOWN, it emits nothing: `DISCARD_OPPOSITE` kills both.
  - TSMOM emits on every tradeable tick once 260 daily closes exist, so from then on no module can
    trade against its vote on that instrument.
- **On-disk corroboration** (rare events are logged in full):
  - `PARAM_PROMOTION_STALLED` shows **0 events for staging in 2014 and all 360 from staging
    2015-02-03 on**. That date is fold 9's train end. Fold 0 seeds about 45 daily closes, and about
    215 more accrue live, which makes TSMOM live in early January 2015, during fold 8.
  - Up to 13 boundaries were skipped.
  - Promotions continued: 35 in 2014 and 55 in 2015–16 (`params.db`). So TSMOM delays promotion
    rather than blocking it.

**Verdicts.**
- **Does TSMOM hold straight through the edge and out the other side?** Yes, by its horizon and by
  the aggregate.
  - A 63–252-day vote cannot see a 1–4 h episode.
  - Its trades average 53.4 h, and a typical 48 h trade spans 11 or more random-sign episodes.
  - The per-bucket P&L split is the one thing still unmeasured (BLOCKED run above).
- **Is `_tsmom` faithful to Moskowitz–Ooi–Pedersen (2012)?** **No.**
  - (i) *Signal:* a sign vote over 63/126/252 trading days with conviction = agreement/3
    (`core/signals/agon.py:482-506`; ACIS-04 §6.6 "faithfully-simple").
    - MOP's headline rule is the sign of the past 12-month *excess* return, rebalanced monthly and
      held one month, with each position sized to 40% ex-ante volatility using an EWMA σ.
    - The 3/6/12-month blend is a declared variant.
    - Using **spot returns instead of excess/forward returns (carry omitted)**: ~~does not appear in
      the declared deviations I read~~ **REFUTED by audit E5:** it is declared at
      `core/signals/canonical.py:101-102` (GAP-0073, closed). E5 disputes the declaration's premises.
    - Grade: (a), recalled from the paper and not re-fetched this pass.
  - (ii) *Holding:* the engine re-evaluates every tick, and in the backtest the **book truncates
    every TSMOM position at 48 h** and re-enters.
    - The realised hold is about 2.2 days against MOP's month, with roughly 10× the turnover and friction.
    - This contradicts ACIS-09's own carve-out rationale, which calls TSMOM "multi-month by design".
    - Grade: exact code reference.
  - (iii) The planted market is the wrong positive control for TSMOM: by construction it has no edge
    at TSMOM's horizon.
- **Proposals** (owner decisions; nothing was changed):
  - a per-strategy max hold in the book (TSMOM exits on vote flip or after about 1 month). This
    forces the embargo to be at least that long, per GAP-SP12E-03's rule;
  - OR grading TSMOM on its own daily-bar harness;
  - AND a multi-month-drift synthetic control for TSMOM;
  - AND reviewing the arena conflict rule, under which a standing slow signal vetoes every fast
    module on its instrument.

## Stage 4 — The §5.6 parameter-plateau law (GAP-P12D-34) — BUILT — PENDING AUDIT
**What was built.**
- `core/optimizer/plateau.py` (76 lines; `neighbours`, `check_plateau`, `PlateauVerdict`,
  `PLATEAU_STEP = 0.10`).
- Wired into `QIEA.evolve` **after** the C9 train gate and the §6.3 holdout gate, because the
  holdout gate is the cheaper filter (265 `EVOLUTION_REJECTED_OOS` against 106 runs in the ladder).
  It runs **before** `EVOLUTION_RUN`, so a refused champion is never returned and never staged.
- A refusal logs `EVOLUTION_REJECTED_PLATEAU{regime, seed, neighbours, champion, dead[{gene, direction, value}]}`.
- `repair_invariants` moved to `param_types.py` (next to `GENE_SPECS`; the decoder and the plateau
  share it) and remains importable from `qiea`.
- **`GENE_SPECS` is unchanged. `test_baseline_paramset.py` is green.**

**Operationalisation of "dies" — FLAGGED FOR OWNER RATIFICATION (it interprets spec prose).**
> **Superseded in part after the dual audit.** The step is now ±10% of the gene's RANGE (E6). A
> refused candidate stays a DSR trial (F3). `direction` is the actual post-repair move (F5).
> Refusal counts are 10/30 and 9/30; the seeds are 5 and fold 1. See "Fixes after dual audit". The
> text below records the first hand-off.

- **Neighbour:** ONE gene × (1 ± 0.10) of its own value. Integer genes are rounded as `decode_gene`
  rounds (half-to-even), clamped to the `GENE_SPECS` range, and repaired with `repair_invariants`
  (ema_slow > ema_fast; tp > sl).
  - The neighbour is therefore exactly what QIEA itself would emit.
  - A repair may move a second gene (for example, ema_fast 25 → 28 lifts ema_slow 26 → 29).
- **No neighbour on a side** when the move lands back on the champion: the gene sits on its bound,
  10% is below an integer's resolution (e.g. `max_holding_periods` 3), or the repair undoes it.
- **Dies:** the neighbour fails the **C9 gate on the champion's own train window**, i.e. its train
  fitness is `WORST_FITNESS` (fewer than `fitness_min_trades` trades, or E_R ≤ `expectancy_min_r`).
  **Any** dead neighbour refuses the champion.
- **Choices the owner should rule on:**
  1. "Dies" as a C9 failure is parameter-free but lenient. It catches cliffs, not steep slopes.
     - A stricter option would require each neighbour to keep a fraction of the champion's
       fitness, but that invents a threshold.
     - Using the holdout gate instead is noisy (5-trade holdouts).
  2. The step: 10% of the *value* (chosen, a literal reading of "±10%") versus 10% of the *range*,
     which is a far larger move near a range's floor.
  3. One-at-a-time moves (22 neighbours) versus joint corners (2¹¹).
  4. The three genes fitness does not read (GAP-0035) are perturbed. They cannot die until that gap
     closes, and bind automatically afterwards.
  5. **Interaction with GAP-P12D-33.** Refused champions left the DSR trial set, and under the
     inverted gate fewer recorded trials make it EASIER to pass. **Fixed after audit F3:** a refused
     candidate stays a trial.

**Measured.**
- Production config (20 × 30 = 600 evaluations), 20,000 one-minute bars: **20.8 neighbours and
  2.61 s per check = 3.4% of one 77 s evolution run**. The ceiling is 22/600 = 3.7%, and the cost is
  paid only by champions that already cleared both C9 gates.
- **Impact on the repo's own fixtures** (unit config, seeds 1–30):
  - trend zigzag: **14/30** refused;
  - ranging-25 zigzag: **11/30** refused;
  - production config on 20k bars: 3/4 refused.
  - The dead gene is almost always `rsi_period`, `rsi_overbought` or `rsi_oversold`: the RSI filter
    is a knife-edge on a deterministic sawtooth.
  - **The rate on the planted market's real evolution is UNMEASURED.** It could leave regimes
    param-less, which is the safe default (NVMA `tradeable=False`), but it could starve the engine.
    Measure it before any paid run.
- **Existing tests adjusted** (their intent is unchanged; only seeds and fixtures changed):
  - `test_same_seed_same_history_identical_champion`: seed 7 → 9;
  - `test_gap0036_same_seed_different_params_get_different_ids`: seed 42 → 5;
  - `test_best_holdout_is_staged_and_nothing_after_the_train_end_is_read`: fold index 0 → 1. The
    index only seeds QIEA, and fold 1 was chosen by a scan so that every other assertion still holds.
  - Seed 7's refusal is pinned by its own test.

**Tests** (`tests/unit/test_plateau_law.py`, **5**; commit `904b409`'s message wrongly says 7):
- a hand-worked ±10% table for all 22 neighbours;
- bounds, resolution, half-to-even rounding and both invariant repairs, hand-worked;
- one dead neighbour on a synthetic cliff refuses the champion and is named;
- the **trench test:** seed 42's champion holds, then its two `max_holding_periods` ±10% neighbours
  are made to fail. QIEA reaches the **same** champion, clears C9 on train and holdout, and the law
  alone refuses it, naming exactly those two;
- the real knife-edge (seed 7, `rsi_period`) is refused.

**Falsification.**
- **F7** unwires the gate → the trench and knife-edge tests fail: `assert ParamSet(...) is None`.
- **F8** stops recording dead neighbours → the cliff, trench and knife-edge tests fail.
- **F9** uses a 20% step → the table, bounds, cliff and trench tests fail.
- **F10** drops the invariant repair → `assert 26 == 29`.

**Draft ACIS-03 amendment (v1.5). For the owner; NOT written to `specs/`.** *The step, `direction`,
refused-candidate and registry wording is superseded by the updated draft in "Fixes after dual audit".*
> **§6 step 5 (append):** "…then pass the §6.3 holdout gate **and the §6.4 plateau law** before it may be staged."
>
> **§6.4 Parameter plateau (master §5.6 anti-overfitting law; closes GAP-P12D-34).** After the champion clears C9 on train (GAP-0038) and the §6.3 holdout gate, QIEA evaluates its ±10% neighbourhood on the **same train window**. For each gene g in `GENE_SPECS` and each direction d ∈ {−1, +1}, the neighbour is the champion with g ← g·(1 + 0.10·d): an integer gene is rounded as the decoder rounds (half-to-even), the value is clamped to g's range, and the cross-field invariants are repaired as §6 step 2 repairs them. A move that returns the champion is not a neighbour. A neighbour **dies** iff its train fitness is `WORST_FITNESS` (it fails C9: fewer than `fitness_min_trades` closed trades, or E_R ≤ `expectancy_min_r`). **Any dead neighbour ⇒ the champion is not staged**; `EVOLUTION_REJECTED_PLATEAU` is logged and the regime stays param-less (safe; NVMA holds `tradeable=False`). Genes the v1 fitness harness does not exercise (GAP-0035) are perturbed like every other; their neighbours cannot die until module-gene fitness exists. Cost: ≤ 2 × 11 train evaluations per surviving champion (≤ 3.7% of a 20 × 30 run).
>
> **§9 (add):** `EVOLUTION_REJECTED_PLATEAU{regime, seed, neighbours, champion, dead[{gene, direction, value}]}`; `EVOLUTION_EVALUATIONS{regime, seed, outcome, genes, evaluated[[genome…, train_fitness, draws]], holdout_trades, holdout_e_r}` (stage 5, logging only).
>
> **§12 (add row):** "champion's ±10% neighbourhood fails C9 on train | not staged; `EVOLUTION_REJECTED_PLATEAU`; regime stays param-less (safe)".
>
> **§13 (add) C-QIEA-9 (§5.6 plateau):** a champion on a peak cannot be staged; test: the same champion with its two neighbours in a single gene made to fail C9 is refused, naming both, while it is staged when they hold.
>
> **§14 (add):** hand-worked neighbour table incl. bound clamp, sub-resolution integer, half-to-even rounding and both invariant repairs; the trench test; a real-landscape knife-edge refusal.
>
> **Changelog 1.5:** §5.6 plateau law implemented as §6.4 (GAP-P12D-34); "dies" = fails C9 on the train window (owner-ratified operationalisation — record the ruling). Selection tightened only; no guardrail, HALT, veto or staging semantics changed.

## Stage 5 — Record every QIEA evaluation (GAP-P12D-33 [impl]) — BUILT — PENDING AUDIT
**What was built.** `QIEA.evolve` keeps an in-run registry of each distinct genome, its train
fitness and its draw count.
- At each of the four post-evolution exits (rejected on train, holdout or plateau, or staged) it logs
  `EVOLUTION_EVALUATIONS{regime, seed, outcome, genes, evaluated, holdout_trades, holdout_e_r}`.
- Runs rejected for insufficient data evaluate nothing and log nothing.
- It is logging only: no gate reads it.
- Previously a gated-out run left no trace of what it tried, which truncates the attempt count
  (survivorship).

**Measured.** At the production config there are about 310 distinct genomes per 600 draws (322 in
the test), and **about 45 KB per evolve call**. For a ladder-sized graded run, 400 evaluating calls
come to about 18 MB of JSONL. It is not a sampled type, so it is written in full.

**Tests** (`tests/unit/test_evaluation_registry.py`, 5):
- a staged run records all 64 draws, and 5 rows re-simulate to their logged fitness, which is what
  makes later PBO/CSCV possible;
- a train-gated run still records 64 draws, all `WORST_FITNESS`;
- holdout-rejected and plateau-rejected runs record theirs;
- **at the production population, repeats exist (322 < 600) and are counted (Σ draws = 600)**;
- an insufficient-data run records nothing.

**Falsification.**
- **F11** drops the train-exit log → `ValueError: not enough values to unpack (expected 1, got 0)`.
- **F12** stops counting repeats → **it survived** the first 4 tests, because the 8 × 8 fixtures
  never repeat an 88-bit genome. I added the production-population test, which kills it:
  `assert 322 == 600` (`445198e`).

**Residuals.**
- The plateau neighbours' 22 evaluations are not in the registry, and only the dead ones are logged.
- No PBO/CSCV computation exists yet. Per-sub-period performance must be re-simulated from the genomes.

---

## What I could not verify
- Per-trade TSMOM duration and boundary-crossing buckets. Records are absent and the diagnostic was
  blocked by memory; the run spec is above.
- The plateau law's refusal rate on the planted market's real evolution. I measured it only on the
  repo's fixtures.
- `falsify_engine.py` stage 1 end-to-end through its CLI on the real synthetic markets, and the
  oracle on permuted. Both are heavy runs, which are off-limits.
- Moskowitz–Ooi–Pedersen's exact wording, and whether "spot vs excess return" is declared anywhere
  I did not read (for example ACIS-11 `declared_deviations`). I had no web access, so the literature
  is recalled.
- Whether the demeaning (bridge) effect is theory-exact. The evidence is measured and moderate, and
  it is not independent across kinds.

## Residual risk
- **Stage 4 changes selection for every future run**, backtest and live, since QIEA is production
  code. If the planted or real refusal rate is high, regimes go param-less. That is safe, but it could
  make the next ladder or falsification run look starved. **Measure first.**
- The stage-4 edits to three existing tests are fixture and seed changes, justified above. An auditor
  should confirm that the intent is unchanged.
- The oracle bypasses the factory. Equivalence is pinned for the six fields read today; if the
  harness ever reads another field, the oracle's `OracleTick` raises `AttributeError`, which is loud
  and not silent.
- The DSR verdicts in stage 1 are per-trade, following the ratified basis. They inherit every caveat
  of GAP-P12D-25 and GAP-P12D-33.

## Ledger items this pass should generate
(No IDs; the lead assigns them. [impl] = implementation, [spec — owner ratification] = needs a ruling.)
1. **Oracle positive control built; the ratified DSR gate cannot pass it** (no trials by construction; the engine's trial sets demand per-trade SR0 hurdles of 5.654 / 2.430 — a T-mismatched hurdle, not an "oracle DSR", after audit E4) — Severity critical · Likelihood high · proposed Status: GAP-P12D-37 → *mitigated* (control exists and is stage 1), GAP-P12D-33 → *open, now evidenced* — [impl] for the control; [spec — owner ratification] for any gate change.
2. **GAP-P12D-38 refuted — empty-population mean reported as 0.0; no zero-duration trades exist** — Severity medium · Likelihood high · proposed Status: *fixed* (`test_an_empty_carve_out_has_no_mean_duration_never_zero`, `test_momentum_scalp_can_never_fire_on_a_uniform_synthetic_tape`); the band count in the ledger text (407) should be corrected to 1,628 — [impl].
3. **MOMENTUM_SCALP is never exercised by any synthetic market (uniform 20 s tape)** — Severity high · Likelihood high · proposed Status: open — [spec — owner ratification] (changes the positive-control market design).
4. **The backtest book truncates TSMOM at 48 h (every strategy shares one max hold), contradicting ACIS-09's multi-month carve-out** — Severity high · Likelihood high · proposed Status: open — [spec — owner ratification] (per-strategy max hold forces a longer embargo, GAP-SP12E-03).
5. ~~`_tsmom` uses spot returns — possibly undeclared deviation from MOP~~ **Corrected by audit E5:** the deviation IS declared (`core/signals/canonical.py:101-102`, GAP-0073 closed); what fails is its premise ("excess over risk-free", "immaterial") — the external auditor owns that finding.
6. **TSMOM's standing vote vetoes every opposite-direction signal on its instrument (DISCARD_OPPOSITE on every tradeable tick) and stalls promotions from the day it goes live** — Severity high · Likelihood high · proposed Status: open — [spec — owner ratification] (arena conflict rule, ACIS-04 §2 table).
7. **The planted market has no edge at TSMOM's horizon, and whole-path demeaning tilts long-horizon trend votes negative** — Severity medium · Likelihood medium · proposed Status: open — [spec — owner ratification] (a TSMOM-appropriate control).
8. **TSMOM per-trade bucketing BLOCKED on memory; run spec written** — Severity medium · Likelihood — · proposed Status: open (lead to run `SCRATCH/BUILDER/tsmom_diag.py`, folds 9–10, ≥ 2 GB free) — [impl].
9. **§5.6 plateau law implemented; "dies" = fails C9 on train** — Severity high · Likelihood high · proposed Status: GAP-P12D-34 → *fixed pending ratification*, residual: the operationalisation ruling + the planted-market refusal rate — [spec — owner ratification] for the reading; ACIS-03 v1.5 amendment drafted above.
10. **Plateau refusals shrink the DSR trial set; under the inverted gate that makes passing easier** — Severity high · Likelihood medium · proposed Status: open, owned by GAP-P12D-33 — [spec — owner ratification].
11. **Every QIEA evaluation now logged (EVOLUTION_EVALUATIONS)** — Severity medium · proposed Status: GAP-P12D-33 secondary finding *mitigated* (registry exists; PBO/CSCV not computed) — [impl].
12. **Worktree isolation cuts branches from a stale ref (84 commits behind local `main`)** — Severity low · Likelihood high · proposed Status: open (process note for future builder passes) — [impl].
13. **(From the audit fixes.) The harness carries open positions through the observe-only embargo, where no strategy can act and orders are never applied; on a weekend-flat account every ENGINE position open at a fold's test end is booked `weekend_holding`, whatever the engine does** — Severity high (FTMO/prop_demo) · Likelihood high · proposed Status: open — [impl] (e.g. flatten at test end, or grade the embargo's closes as the harness's) — the oracle avoids it by flattening before each fold's end (`oracle_loop.py`).
14. **(From the audit fixes.) The E6 range step is uniform on the search range but moves period genes near their floor by large RATIOS (`ema_fast` 6 → 10, +67%)** — Severity low · Likelihood medium · proposed Status: open, owner note — [spec — owner ratification] (a log-scale step for period genes).
15. **(From the audit fixes.) Audit-fix batch: F3, F1+E1, F2, E3+F4, E2, E4, E6, F5+F9, F6+E7, E9 built on the branch** — proposed Status: each *fixed pending audit*; residuals: F7/F8/E8 with the lead at merge; E5 with the external auditor's entry.

## Sources
- **Code** (exact): `tests/backtest/harness.py:93` (max hold); `tests/backtest/book.py:132`; `core/signals/agon.py:430-448` (scalp), `:482-506` (TSMOM), `:306-318` (DISCARD_OPPOSITE); `core/data/normaliser.py:234-243` (velocity window); `config/system_config.yaml:41,52,82` (conviction_discard, surge ratio, velocity window); `specs/ACIS-09-BACKTEST_VALIDATION.md:76` (TSMOM "multi-month by design"); `ACIS_SPEC.md:207` (§5.6 law); `specs/ACIS-03-QIEA_OPTIMIZER.md` §6/§9/§12–§14.
- **Data** (read-only; copies in `SCRATCH/BUILDER/ladder_copy/`): `data/validation/cost_stress/20260917T083216Z/{rung_1x.json, ladder.json, logs/run_rung_1x.jsonl, engine/rung_1x/*.db}`; `data/validation/falsification/20260915T231127Z/{planted,null,permuted}.json`.
- **Scripts:** `SCRATCH/BUILDER/{oracle_record.py, oracle_record_*_EUR_USD.json, gap38_arith.py, market_fingerprint.py, tsmom_blocking.py, tsmom_bridge.py, tsmom_bridge_8.log, tsmom_diag.py, plateau_seed_scan.py, plateau_cost.py, evolve_step_scan.py}`.
- **Literature** (grade a; recalled, not re-fetched, no web access): Moskowitz, Ooi & Pedersen, "Time series momentum", *Journal of Financial Economics* 104(2), 2012; Hurst, Ooi & Pedersen, "A Century of Evidence on Trend-Following Investing", 2017; Bailey & López de Prado, "The Deflated Sharpe Ratio", *JPM* 40(5), 2014 (as pinned in `deflated_sharpe.py`).
