# PARTIAL — BUILDER checkpoint (five-agent edge pass, 2026-09-24, GAP-P12D-52)

**Asked by:** the lead (Opus 5.5 session), under `FIVE_AGENT_BRIEF_2026-09-24.md` §0 + §5.
**Who:** BUILDER, running in fresh context on Opus, in an isolated worktree. I launch no subagents.
**Status:** checkpoint only. The final report, `BUILDER_REPORT_2026-09-24.md` at the worktree root,
replaces this file. Everything here is **BUILT — PENDING AUDIT** or not yet started.

## Setup (done)
- The branch `worktree-agent-a128ab904780ce593` was cut at `e00fdd3`, 84 commits behind local `main`.
  It was fast-forwarded to `7695ed0` (`git merge --ff-only main`). `main` was not touched.
- Baseline: **808 passed, 6 skipped** (data-absent `skipif`s) in 176.8 s. Ledger: 187 entries, 0 violations.

## Stage 1: oracle positive control (committed `77ac588`, falsified F1–F4)
- `tests/backtest/oracle.py`, `test_oracle_control.py` (8 tests; the positive control runs ~40 s).
  Suite 816 passed.
- A16 falsification: F1 (inverted oracle), F2 (null carries the drift), F3 (void gate off) and F4
  (a `non_dsr_failures` clause dropped) each went red for their stated reason. Each was restored
  with git, and the diff was verified empty.
- Full §14 record (EUR_USD, `plan(60, 30, 25)`) is running.

## Stage 2: GAP-P12D-38 (in progress; the finding is REFUTED)
- There are no zero-duration trades. On a synthetic tape tick velocity equals its session median
  on every tick, so the surge ratio is exactly 1.0 and MOMENTUM_SCALP can never fire. Its
  population is empty, and `_avg_duration` reported an empty mean as 0.0.
- Exact 20 s-grid arithmetic on the 2026-09-15 run confirms it. The planted band is 1628 trades,
  not 407, and 407 is impossible because its sum would be 194,345 s, not a multiple of 20.
  Permuted's ONLY feasible split is (1717 band, 394 TSMOM, 0 SCALP). Every attributed synthetic
  run (8 reports) has 0 MOMENTUM_SCALP trades.
- The fix is NaN for an empty mean. The test is written; it runs and commits next.

## Stage 3: TSMOM (analysis so far)
- There are no per-trade records on disk. Free memory has been 0.83–1.47 GB, under 2 GB, so the
  engine diagnostic is BLOCKED.
- Reproduced with AGON fixtures: TSMOM's standing vote vetoes every opposite-direction signal
  (DISCARD_OPPOSITE) and outranks same-direction ones.

## Remaining
- Stage 3 write-up.
- Stage 4: the plateau law (`core/optimizer/plateau.py`, drafted).
- Stage 5 (optional).
- The final report.
