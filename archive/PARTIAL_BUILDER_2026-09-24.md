# PARTIAL — BUILDER checkpoint (five-agent edge pass, 2026-09-24, GAP-P12D-52)

**Asked by:** the lead (Opus 5.5 session), under `FIVE_AGENT_BRIEF_2026-09-24.md` §0 + §5.
**Who:** BUILDER, running in fresh context on Opus, in an isolated worktree. I launch no subagents.
**Status:** checkpoint only. The final report, `BUILDER_REPORT_2026-09-24.md` at the worktree root,
replaces this file. Everything here is **BUILT — PENDING AUDIT** or not yet started.

## Setup (done)
- The worktree branch `worktree-agent-a128ab904780ce593` was cut at `e00fdd3`, 84 commits behind local
  `main`, because it was an ancestor with no unique commits. It was fast-forwarded (`git merge --ff-only
  main`) to `7695ed0`. Only my branch moved; `main` was not touched.
- Baseline: `python -m pytest -q` gave **808 passed, 6 skipped** (814 collected) in **176.8 s**. The 6
  skips are `skipif` markers for data absent from the worktree (`test_financing.py:55`,
  `test_sources.py:172/187`).
- `python scripts/ledger_check.py` gave **187 entries, 0 violations**.

## Findings so far
- Stage 3 (TSMOM attribution): **no per-trade records exist on disk** for the ladder's 1x rung.
  - `engine/rung_1x/acis.sqlite` has 0 `market_state` rows.
  - The replay logger keeps only the first 200 events of each sampled type: `SIZED` has 1,575,748
    counted and 200 kept, and there is no close event at all.
  - The aggregate is in `rung_1x.json`: TSMOM has 455 trades, net −152.49, and
    **avg_duration_s 192,318.8 (53.4 h)**, against planted episodes of 1–4 h and a 48 h max hold.
  - The bounded diagnostic needs ≥ 2 GB free, and only 1.43 GB was free at the start.

## Remaining
1. Oracle positive control, with its test and the `falsify_engine` stage (GAP-P12D-37).
2. Zero-duration artifacts (GAP-P12D-38).
3. TSMOM attribution, by diagnostic or BLOCKED.
4. §5.6 plateau law (GAP-P12D-34).
5. (Optional) QIEA evaluation logging.
