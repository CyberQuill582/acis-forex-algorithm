# AUDIT — BUILDER branch, INTERNAL-consistency lens (2026-09-24/25)

**Attestation (A5).** AUDIT-INTERNAL, fresh context, Opus 5.5, no web, no subagents. I am a finder, not
a clearer: this report is not a sign-off. The brief is `AUDIT_BRIEF_BUILDER_2026-09-24.md`, pinned
before launch. Under A4 I formed the attack from the code and from observed behaviour first, and read
`BUILDER_REPORT_2026-09-24.md` last.

**Under audit.** Branch `worktree-agent-a128ab904780ce593`, head `9b9ec80`, base `7695ed0`, 8 commits
and 18 files. Nothing in the worktree or the main tree was modified. This file is the only repo write.
- All runs used private exports: `<SCRATCH>/audit_internal/tree` (head), `.../base` (base) and `.../mut`
  (a mutation copy, restored after each mutant).
- Every script named below is in `<SCRATCH>/audit_internal/scripts/`.
- `SCRATCH` = `C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.

## Executive summary
The core of the branch holds up under attack.
- **Tape.** The synthetic tape the engine is graded on is byte-identical before and after the branch.
- **Oracle knowledge.** `episode_sign` names exactly the drift that was applied, with no foresight.
- **Stage 1 at full scale.** On the real plan (25 folds, both enabled instruments, dev_paper), the
  planted oracle clears every non-DSR clause. Null and permuted each fail five clauses.
- **Plateau law.** It is deterministic and consumes no RNG. It changes QIEA only by refusing champions:
  across 208 base-vs-head runs, 0 other differences.
- **Suite and ledger.** 828 passed, 6 skipped; `ledger_check` gives 187 entries and 0 violations.
- **The NaN change.** It flips no gate.

I found **3 Medium and 6 Low** defects. None is a guardrail, HALT or veto defect.
- **The Mediums:**
  - **F1:** the oracle file does not pin the GAP-P12D-37 defect class. A §14 change that VOIDs every
    real stage-1 run leaves the whole suite green.
  - **F2:** stage 1 is structurally VOID on any weekend-flat account, FTMO included, and there its
    null/permuted refusal is vacuous.
  - **F3:** the plateau law silently removes about 22% of trial Sharpes from the ratified DSR
    selection set.
- **Verdict:** **fit to merge once F1–F3 are fixed or explicitly owner-accepted and F7–F8 are done at
  merge.** F4–F6 and F9 may ride as ledger items.

## Findings

### F1 — The positive-control test does not pin the defect class it was written for (A16)
- Severity **medium** · Likelihood **medium**
- **What.** The `tests/backtest/test_oracle_control.py` docstring says the file closes the gap in which
  "an unsatisfiable gate and a 30-minute duration floor went unnoticed". But no test asserts
  `non_dsr_failures(planted oracle) == ()`.
  - The positive-control test runs 2 folds × 7 days. It asserts only net > 0, Sharpe > 5 and PSR ≥ 0.95.
  - So a §14 change that only the planted oracle cannot meet is invisible to the suite.
  - The runtime stage 1 still catches such a change, but only after about 20 min of compute and a VOID.
- **Reproduction** (`scripts/mutate.py`, mutant `M2_duration_cap_4h`). Set
  `report.DURATION_MAX_S = 4 * 3600`.
  - `test_oracle_control.py`: **8 passed**.
  - The whole suite: **828 passed, 6 skipped**. The mutant survives everywhere.
  - Under the same mutant, the real-scale oracle fails `section-14 avg_duration`: the planted average
    is 7.2 h, so stage 1 would VOID every full run.
- **Proposed fix (measured feasible).** Add a test on the real fold count with a coarse tape:
  `plan(1, 30, 25)`, `MarketSpec(..., tick_seconds=300)`, EUR_USD, dev_paper.
  - It asserts `non_dsr_failures(planted) == ()` and `void_reasons({planted, null}) == []`.
  - It takes about 21 s (`scripts/oracle_coarse.py`: planted `()`, null 4 failures).
  - Under the M2 mutant it returns `the planted oracle failed: section-14 avg_duration`, so it kills
    the mutant (`scripts/oracle_coarse_mut.py`).

### F2 — Stage 1 is account-dependent, and structurally VOID on weekend-flat accounts
- Severity **medium** · Likelihood **high** whenever `--account` names a weekend-flat account
- **What.** `OracleLoop` holds through weekends, and the harness books those holds as §9.5
  `weekend_holding` rule violations. `non_dsr_failures` counts rule violations. Therefore:
  - On `prop_demo` and `ftmo`, `void_reasons` reports "the planted oracle failed" on every run, and
    `falsify_engine.py --account ftmo` exits 4 whatever the harness does. FTMO is one of the two
    automation-viable venues on the owner's shortlist.
  - On the same accounts, null and permuted are "refused" by that same rule violation whatever their
    metrics. The negative half of the control becomes vacuous. The BUILDER report discloses the account
    dependence (Stage 1, Residuals) but not this vacuity, and nothing in the code guards either.
- **Reproduction** (`scripts/oracle_account.py`). Six accounts × {planted, null}.
  - `prop_demo` and `ftmo` give `rule_violations ['weekend_holding']` for BOTH kinds.
  - The four weekend-allowed accounts give `[]`.
- **Proposed fix.** Either one of:
  - make the oracle obey the rulebook: flatten before the account's weekend cut, and honour
    `min_hold_seconds` (`prop_demo`: 60 s; a day re-assert followed within 60 s by an episode flip is
    reachable);
  - or have `falsify_engine.py` refuse stage 1, with an explicit message, on an account whose rulebook
    the oracle does not model.

### F3 — The plateau law shrinks the ratified DSR trial set
- Severity **medium** · Likelihood **high**
- **What.** `QIEA.evolve` runs the plateau check AFTER the §6.3 holdout gate (`core/optimizer/qiea.py:198-209`).
  - A champion that was scored on, and passed, the holdout is then refused and returned as `None`.
  - `evolve_fold` records a trial Sharpe only for returned champions (`tests/backtest/evolve_step.py:95-101`).
  - So configurations that consulted the holdout drop out of the GAP-P12D-25 selection set. Before this
    branch, "candidate champion" meant exactly "passed the holdout".
  - Fewer trials lower SR0 and loosen the DSR gate, with no ledger entry on the branch.
  - The BUILDER report discloses this (item 10), but routes it to GAP-P12D-33 as an owner question.
- **Reproduction** (`scripts/trial_set.py`, base vs head, 24 fold-runs on noisy zigzag):
  - champions 24 → 18;
  - **trial Sharpes 23 → 18**: 5 holdout-scored champions vanish from N.
- **Proposed fix.** Pick one:
  - (a) Run the plateau check BEFORE the holdout gate. A refused champion then never touches the
    holdout, and "trial = every champion that saw and passed the holdout" is preserved exactly. The cost:
    plateau checks for holdout-rejected champions too, roughly 3× more checks at ≈ 3 s each.
  - (b) Have `evolve` expose the refused champion's holdout Sharpe, so that `evolve_fold` still counts it.
  - Whichever is chosen, record it in the ledger before merge.

### F4 — `--kinds` without `planted` skips the positive control, yet exits 0 and says "planted passes"
- Severity **low** · Likelihood **low**
- `void_reasons` only checks the kinds that ran (`tests/backtest/oracle.py:181-188`).
  `falsify_engine.py:108-113` then prints "falsification held: null and permuted fail, planted passes"
  and exits 0.
- **Repro** (`scripts/kinds_subset.py`, stubbed stages): `--kinds null permuted` gives exit code 0, and
  only null and permuted are graded.
- **Fix:** a full run requires `planted` in `--kinds`, or reports "no positive control" as a non-zero
  exit.

### F5 — Some `atr_multiplier_tp` "−10%" neighbours are repaired UPWARD and logged as direction −1
- Severity **low** · Likelihood **low**
- **What.** When the champion's tp is within 0.1 of its sl, the −10% move is ≤ sl. `repair_invariants`
  then sets tp = sl + 0.1, which is above the champion's value.
  - The downside of tp goes untested.
  - `EVOLUTION_REJECTED_PLATEAU` would name direction −1 for an upward move.
- **Repro** (brute force over 100k random decoded champions): 2,137,292 neighbours, 0 invalid, and
  **2,247 direction-inverted**. Example: tp 2.749 → 2.845 with sl 2.745.
- **Fix:** treat a repair that reverses the move as "no neighbour on that side" (as `plateau.py`
  already does when a repair returns the champion), or record the actual signed move.

### F6 — The empty-mean NaN reaches non-standard JSON in `ladder.json`
- Severity **low** · Likelihood **medium**
- **What.** In the `synthetic_grade.grade` row, `avg_duration_s` is now NaN whenever the §14 band is
  empty: a zero-trade run, or a run whose trades are all TSMOM or scalp. `scripts/cost_stress_ladder.py:153`
  `json.dumps` then writes a bare `NaN`, which is not RFC 8259 JSON.
  - The same path already existed for `dsr`.
  - `report_json` is safe, because `MetricBlock.as_dict` maps NaN to null.
- **Repro:** `json.dumps({"avg_duration_s": math.nan})` → `{"avg_duration_s": NaN}`.
- **Fix:** route ladder and oracle-deflation rows through the same NaN → null mapping, or pass
  `allow_nan=False` and map explicitly.

### F7 — Code ahead of the LOCKED ACIS-03 spec and the ledger (merge precondition)
- Severity **low** · Likelihood **certain** if merged as-is
- `specs/ACIS-03` §6 step 5 (line 94), the §9 event list (line 142) and the §12 table (line 184) still
  say "holdout gate, then staged". They list neither `EVOLUTION_REJECTED_PLATEAU` nor
  `EVOLUTION_EVALUATIONS`.
- The v1.5 amendment exists only inside the BUILDER report.
- None of GAP-P12D-33/34/37/38 is updated on the branch.
- **Fix:** land the ACIS-03 amendment (or record the owner ruling) and the ledger entries with the
  merge (CLAUDE.md: "spec wins").

### F8 — Pointers that dangle once the report is relocated (A13)
- Severity **low** · Likelihood **certain** at relocation
- Two files point at the root `BUILDER_REPORT_2026-09-24.md`, which the brief requires be moved before
  merge:
  - `core/optimizer/plateau.py:5`, which is production code and cites the report for the "pending
    ratification" state;
  - `archive/PARTIAL_BUILDER_2026-09-24.md`, via `../BUILDER_REPORT_2026-09-24.md`.
- **Fix:** repoint both when moving, and in `plateau.py` cite the ACIS-03 section or gap ID instead of
  a report.

### F9 — The registry claims "EVERY genome this run evaluated", but omits the plateau neighbours
- Severity **low** · Likelihood **certain**
- `qiea.py:222-224` makes that claim, yet the 22 neighbour evaluations are not recorded (the BUILDER
  report discloses this as a residual). An attempt count or PBO pass that trusts the docstring would
  undercount.
- **Fix:** record neighbours with their own outcome tag, or correct the docstring.

## Honest negatives (each reproduced)
- **Tape identity (surface 1).** Base vs head `_returns` bytes and loaded ticks were compared for 81
  (spec, instrument) tapes: 3 kinds × 3 seeds × 3 shapes, including 60 s ticks and sub-tick episodes.
  **0 differ** (`tape_identity.py`). The RNG order (noise, then `randint`/`choice` per episode, then the
  permuted shuffle) is unchanged.
- **Oracle knowledge.** `episode_sign` matches the sign of (planted − null − offset) on 196,308 ticks,
  including mid-day partial windows: **0 mismatches** (`episode_sign_check.py`). It shows the state in
  force, never the next one.
- **`non_dsr_failures` mirrors `passed`.** It mirrors `passed` minus the two trial clauses exactly
  (`report.py:112-121` vs `oracle.py:159-173`). Mutants that drop the guardrail clause, the void
  control check, or foresight are killed.
- **Same grading path.** The oracle is graded through the same `Backtest`, `PositionModel`,
  `cost_model(cfg, i)` C8 map, rulebook, swap conventions, session boundaries, clusters, NAV, max hold,
  ppy, financing (None) and SPX series as `synthetic_grade.grade`. `oracle_ticks` equals the factory
  path. The only difference is duplicate-drop, and synthetic ticks have no duplicates.
- **Full-scale stage 1** (`oracle_full.py`: 25 folds, EUR_USD + USD_JPY, dev_paper). This goes beyond
  the builder's EUR_USD-only record, and includes permuted.
  - Planted: `non_dsr = []` (Sharpe 8.49, DD 0.78%, win 0.993, PF 374, positive months 100%, avg 7.2 h).
  - Null and permuted: 5 failures each.
  - Planted cannot pass for any reason other than the knowledge: null and permuted run identical trade
    timing (5,222 trades each) and lose.
- **Oracle deflation.** It uses the harness's own trial filter and `trial_count`. SR0 recomputed from
  disk: ladder 1x = **5.654** (106 trials) and 2026-09-15 planted = **2.430** (121). Both match the
  report.
  - Whether per-trade holdout Sharpes of 5-trade holdouts (range 0.00–19.40) are faithful DSR inputs is
    an external-lens and GAP-P12D-25/33 question. It is informational only; no gate reads
    `oracle_deflation.json`.
- **NaN (surface 2).** It flips no gate: `avg_duration` failed at 0.0 and fails at NaN.
  - The carve-outs are not graded.
  - `report_json` maps NaN to null.
  - No code or test compares MetricBlocks or reports by equality.
  - `monitoring/` reads none of these fields.
- **Plateau (surface 3).**
  - `repair_invariants` is a verbatim extraction. The body is identical, and `qiea` still exports it.
  - `check_plateau` never touches the RNG.
  - Across 208 runs (fixture 8×8 and production 20×30, 4 histories, `qiea_determinism.py`): 147 have
    identical champions, ids and events; 12 have identical refusals; 49 are plateau refusals of
    **exactly** base's champion; **0 other differences**.
  - 2.1 M neighbours give 0 invalid ParamSets.
  - Cost: 3.3 s per check against 76–124 s runs at 20×30 on 15k bars, about 3–4%, consistent with the
    claimed 2.6 s / 3.4%.
- **Registry (surface 4).** Logging only; no reader exists (grep). Insertion-ordered, so deterministic.
  45–49 KB per call at 20×30. No store or DDL change.
- **Harness refactors (surface 5).** `per_trade_returns` is the same expression. `graded_trades` is a
  read-only tuple of the continuous OOS book.
- **Test integrity (surface 6).** Every reverted fix went red for the stated reason:
  - M1 anti-oracle;
  - M3 no plateau;
  - M4 NaN → 0.0;
  - M5 void ignores controls;
  - M6 guardrail clause dropped;
  - M7 foresight;
  - M8 draw count dropped.

  The three changed tests still test what they claim. Seed 7 is refused on head and staged on base;
  seeds 9 and 5 stage on both; fold 1 only re-seeds. No assertion is weakened: `== 0.0` → `isnan` is a
  semantic change, pinned both ways by `test_an_empty_carve_out_has_no_mean_duration_never_zero`.
- **Constitution (surface 7).**
  - Every touched module is ≤ 300 lines. `metrics.py` is at exactly 300, up from 299.
  - `oracle.py` and `plateau.py` open with invariant models.
  - `ledger_check` is green.
  - The diff touches no config, guardrail, spec or ledger file.
  - Beyond the two files the brief names and F8's pointers, nothing else is left behind.

## What I could not verify
- The plateau refusal rate on the planted market's real evolution. It needs a labelled full run, and
  the builder also left it unmeasured.
- Whether the engine's own fills use the mid, the same basis as the oracle's `entry_price=st.mid`.
  Both go through the same book friction, so the grading path is shared either way.
- Faithfulness of the DSR inputs and of MOP (TSMOM) against the literature. That is the external lens.

## Residual risk
- `metrics.py` sits at the 300-line budget, so its next edit must extract.
- `EVOLUTION_EVALUATIONS` is unsampled (about 45 KB per call), and `JsonlEventLogger` has no rotation.
  When the three-loop runtime runs QIEA on its 4 h cycle live, that is on the order of 5 MB/day in the
  optimizer log. There is no live caller yet.
- The oracle is a perfect-knowledge control (win 0.993, PF 374). It proves the grader recognises an
  enormous edge, not a modest one. Graded-strength controls are an external-lens question.
- F3's direction (a looser DSR) compounds with GAP-P12D-33's degenerate trial Sharpes. Until both are
  ruled on, a DSR pass is not interpretable.
