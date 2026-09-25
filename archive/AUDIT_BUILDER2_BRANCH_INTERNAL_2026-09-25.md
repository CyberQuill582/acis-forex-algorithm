# AUDIT (INTERNAL lens) — BUILDER-2 branch `577d882..5d96570` (2026-09-25)

**Auditor:** AUDIT-INTERNAL. I ran in fresh context on Opus 5.5 (claude-opus-5-5), with no subagents and no web.
I am a finder, not a clearer (A5), and this report is not a sign-off.

**Brief:** `AUDIT_BRIEF_BUILDER2_2026-09-25.md` (pinned). I formed the attack from the code first and read
`BUILDER2_REPORT_2026-09-24.md` last (A4).

**Method:**
- Private exports: `<SCRATCH>/audit2_internal/{tree, tree2 = 5d96570, base = 577d882}`, where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
- Every finding below has a script in `<SCRATCH>/audit2_internal/repro/`.
- I did not modify the worktree or the main tree. This file is my only repo write.
- No real data was read. A stand-in source *named* `dukascopy` plays the part of the mirror, because a real-data grade by an auditor would itself be an uncounted look.

**Status:** COMPLETE (see the suite count in §4).

## 1. Findings, ranked

### HIGH-1 — The look register can be bypassed by a normal code pattern (GAP-P12D-64)
Script: `repro/r_look_register.py`. Every run below went through `run_walk_forward` and graded to completion.

- **L1 — the register can be any directory.** A validation-tier (`dukascopy`, test windows in 2014) look registered in a temp directory passes `verify_look`, and the grade completes. The canonical `data/validation/looks` stays empty. A fresh directory also has no "previous" look, so the "say what changed" rule never fires.
  - The repo already uses this pattern: `synthetic_grade.grade` registers in `out/"looks"` and `leakage_engine` in `work/"looks"` (R7 calls this "by design" for tier 0).
  - Any real-data helper modelled on them produces looks that are never counted.
- **L2 — the tier comes from a caller-supplied string.** `data_tier(source, …)` reads the loader key. The loader never checks that key against its source object's `.name`. A source whose `name == "dukascopy"`, registered under the key `synthetic`, grades as tier 0 "synthetic": unlimited looks, no `changed` required. So the report's line "derived and never claimed" is false: the tier is claimed by the caller.
- **L3 — one line can be used for many grades.** One line graded two runs (the declared world, then 3x cost stress), and the register counts 1. Nothing consumes the line at grade time. The line also does not bind `cost_stress`, `spread_floor`, `account` or the code state.
- **L4 — a hand-written line on disk passes.** A forged `Look` (new id, fake commit) whose JSON is written next to it passes `verify_look`. So the claim "a hand-built Look … is refused" holds only when the file is absent.
- **Beyond R6.** The author's R6 discloses only a direct `Backtest.run`. L1, L2 and L4 go through `run_walk_forward` itself.
- **Fix:**
  - For tier > 0, require `Path(look.path).parent` to be the one canonical register.
  - Derive the tier from the declared source object (key == `src.name`, a real-source class).
  - Consume the line at grade time with an exclusive-create `<id>.graded`.
  - Bind the run properties in the line.

### MEDIUM-1 — A whole-file cache hides a whole-sample leak from both T1 and T2
Script: `repro/r_whole_file_memo2.py`. It runs the author's labeller sweep over all 129 cuts, with one change: each bar's label is normalised by the WHOLE file's median mid.

| threshold | T2 | T1 |
|---|---|---|
| recomputed per run | flags 129/129 cuts | — |
| memoised on the source name | 0/129 | 0/129 |

The memoised leak is hidden completely. Why:
- `PerturbedMarket` deliberately keeps the reference's name.
- Every component variant runs in one pytest process.
- `scripts/leakage_suite.py` builds its `ProcessPoolExecutor` AFTER the reference run, with no spawn context and no `max_tasks_per_child`. On Linux (fork) every worker inherits a memo the reference filled. Elsewhere, workers are reused across variants.

This is exactly the channel the VALIDATOR names for T2 ("caches or normalisers keyed on whole files"). The suite guards only on-disk caches, through fresh directories.

**Fix:**
- Give each variant a distinct source name.
- Run each engine variant in a fresh spawned process.
- Add a T7 control that plants a name-keyed memo.

### MEDIUM-2 — The sweep cannot see a look-ahead inside the T6 exit itself
Scripts: `repro/r_fitness_gap_leak2.py` (seed 22) and `repro/r_fitness_gap_leak3.py` (seeds 32, 33).

- **The planted leak:** a gap exit that reads its own bar's CLOSE, filling at the stop when the close recovers above it. It changes a decision and raises the PnL (seed 22: 0.02390 → 0.02435).
- **The result:** the author's exhaustive fitness sweep (479 cuts) reports T1 = T2 = 0 violations.
- **The cause:** `trade_path_decisions` stamps every exit at j + 0.5. For a fill at bar j's open that is the PERMISSIVE direction, although the docstring calls it "conservative".
- **What it refutes:** the report's claim that "T6's own causality is covered by the every-open-and-close component sweep".
- **Coverage:** the author's tape exercises the gap branch in only 2 of 12 exits.
- **Fix:** stamp a gap exit at j, with horizon j and emission j. Only an intrabar exit takes j + 0.5.

### MEDIUM-3 — T2 has never bitten on evolution; its only control goes red through T1 alone
Scripts: `repro/r_evolution_t2.py` and `r_evolution_t2_m{5,20,60}.py`. The planted leak is the author's own falsification mutation (reading 2 h past the train end), plus peeks of 5, 20 and 60 min.

- **T2 reports 0 violations** under both the test's x1.5 perturbation and the suite's `perturb_path`.
- **Only T1 goes red,** through the record's bar count and `last_bar`. That is the channel `refuse_lookahead` already reads.
- **Why T2 is blind:**
  - the honest record is saturated: fitness 0.8 (the formula maximum), holdout E_R 10.0 (the cap), Sharpe None;
  - every leaky reference stages NO champion, so T2 compares two empty records.
- **Fix:** use a tape whose record is not at the caps, and a control whose leaky reference still stages a champion.

### MEDIUM-4 — The AGON sweep cannot fail on look-ahead in AGON's own code
- **Why it cannot fail:** in `_agon`, the test's loop feeds AGON one tick at a time, so AGON holds no later datum when it decides. The sweep certifies the test's own loop. The production loop that feeds AGON (`build_paper_loop`, under the harness) is swept only at the day grid (R1).
  - The author's ad-hoc bite ("fed AGON the next tick's mid") mutated that feeding loop, not AGON.
- **The perturbation can be switched off unnoticed.** With `tick_tape_variant` disabled (it returns the tape unchanged), the AGON sweep, both bar-builder sweeps and every T7 control still pass: 11 passed. Only the `bars.py` falsification case, which runs at the phase gate, would notice.

### LOW
- **L5 — a power cut can brick the register.** An empty numbered file (the power cut lands between `open("x")` and the write) makes both `register` and `verify_look` raise `JSONDecodeError`, not `LookRefused`. The script's `except` misses it, so the only recovery is deleting a look. There is also no fsync.
- **Race.** `repro/r_look_race.py`: two concurrent real looks by one family both become "first look", and neither states what changed.
- **The dirty flag is noise, and the commit pins no code.** `git_state` counts an untracked file as dirty; this report alone makes the main tree "dirty". The commit is also never re-checked at grade time, so the recorded commit does not identify the code that graded. Hash the tracked `core/`, `tests/`, `scripts/` and `config/` diff instead.
- **Durability.** The register sits under the git-ignored `/data/`, one copy per checkout. It is as durable as this laptop (GAP-P12D-50/76), and per-worktree.
- **T6 is inexact (pessimistic, not a leak).** `repro/r_t6_target_gap.py`: a bar that opens BEYOND the target and later touches the stop books the STOP, for long and short. The open already resolves the sequence: the target was hit first.
- **A locked-spec departure awaits its amendment.** T6 departs from the locked ACIS-03 §6.1 ("exit … at ATR-multiple SL/TP") until the amendment the author drafted lands. GAP-P12D-82 requires an ACIS-03 amendment for F1/F5 because they "change fitness numbers". T6 is the same class.
- **The engine tap has no default-suite test.** `engine_decisions`, `_Tap` and `vacuity` are exercised only by hand runs of the script, and `vacuity` checks only for champions and orders.
- **Key coverage.** Order payloads carry no timestamp, so a pure timing shift with an identical payload is invisible. The `PerturbedMarket` perturbation never moves tick times or volume, which are also constant on the synthetic tape.

## 2. Can each guard be made to miss? Yes
| guard | missed by | finding |
|---|---|---|
| T2 | whole-file memo | MEDIUM-1 |
| T2 | T6 close-peek | MEDIUM-2 |
| T2 | every evolution peek tried | MEDIUM-3 |
| T2 | sub-day engine peek | R1, the author's |
| T1 | memo, T6 close-peek | MEDIUM-1, MEDIUM-2 |
| look register | temp-directory register, mislabelled key, reused line, forged line | HIGH-1 |

## 3. Honest negatives (checked; held)
- **The engine path bites.** `repro/r_engine_f3.py` plants F3 (a materialised replay stream) in `run_walk_forward`. The production tap plus T1/T2 catch it at the 2014-01-10 cut: T2 lost 2,200 decisions and T1 lost 1,704. The honest path at the same cut is clean, with 14,401 compared.
- **The 60 s default is not vacuous.** `repro/r_engine_probe.py` reproduced the author's 12/2/3 reference at 60 s exactly, in 371 s:
  - 51,118 labels, 22,800 regimes, 3 evolution records;
  - 20 signals, 20 orders and 20 trades;
  - `vacuity` is empty.

  Orders exist only in the three test windows, from 2014-01-20 on. So the signal, order and trade channels are compared at about 7 of the 17 day cuts.
- **The oracle controls bite.** Honest is clean, and the peek is caught. All 14 new falsification cases went red for their stated reason on the export (`falsify.mjs`), and each anchor matches exactly once.
  - The 3 old multi-line guardrail cases fail as ANCHOR_NOT_UNIQUE on a CRLF checkout. This is the author's disclosed F4, not BUILDER-2 code.
- **The T6 hand-worked tests are exact.** All 10 of my hand mutants of the T6 lines and `Trade` fields were killed. A gap through the stop exits at the open for long and short, and a touch exactly at the stop fills at the stop.
- **The perturbation leaves the past bit-identical.** `perturb_path` and `PerturbedMarket` keep every earlier datum bit-identical and move every later price. Truncation also cuts the `returns` side channel.
- **No unauthorised touches.** `report.py` gains only the informational `look` field, and `passed` is byte-identical. No config, spec, ledger or guardrail file is touched.
- **Governance checks.**
  - Exclusive create (`open("x")`) is atomic on Windows.
  - The straddle and the multi-tier refusals hold.
  - The holdout derives tier 3, and 2026 derives tier 4.
  - A look is written before the grade, and before the holdout marker.
  - The module budget, `ledger_check` (204 entries, 0 violations) and the invariant headers all hold.
  - No BUILDER-2 file adds a comment-shape violation. The 5 new ratchet violations are inherited from `577d882`.
- **What I could not construct.** In the causal replay, I found no DST or time-zone leak that T1/T2 could see. That leak class (availability versus reference time) needs T3, which is out of this branch.

## 4. Suite count and merge verdict
- **Suite:** the full suite on the `5d96570` export gave **864 passed, 6 skipped** (402 s), which matches the author's count.
- **Verdict:** NOT fit to merge as is. It is fit after fixes:
  - HIGH-1: pin the register, derive the tier from the source object, and consume the line;
  - MEDIUM-1: distinct variant names, and spawned per-variant processes;
  - MEDIUM-2: stamp the gap exit at j;
  - MEDIUM-3 and MEDIUM-4: give the evolution and AGON sweeps a control that bites.

  Each fix needs a regression test, and the ACIS-03 §6.1 amendment should land with T6.
