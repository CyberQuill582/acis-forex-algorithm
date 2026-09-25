# AUDIT BRIEF — the BUILDER-2 branch: leakage suite, look register, T6 (pinned 2026-09-25)

> **Pinned before launch (A4).** These are the constitution's TWO lenses only (owner directive 2026-09-24).
>
> **What is under audit.** Branch `worktree-agent-a8937e82f9a7a5391`, head `5d96570`. Audit ONLY BUILDER-2's
> own work: the diff `577d882..5d96570`. `577d882` is its merge of the BUILDER branch, which is audited
> separately (GAP-P12D-72). Worktree:
> `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a8937e82f9a7a5391`.
> The author's account is `BUILDER2_REPORT_2026-09-24.md` in that worktree. Read it LAST (A4).
>
> **What the lead has checked.** Treat each as a claim to re-verify:
> - `tests/backtest/report.py` gains only one informational field, and the `passed` gate is byte-identical;
> - no guard, spec or ledger file is touched;
> - the author's suite count is 864 passed, 6 skipped.
>
> **Ledger:** GAP-P12D-64 (the look register), -65 (the structural leakage suite), -82 (pre-existing leak paths),
> -83 (this audit), in the MAIN tree.

## Why this branch matters
It is the firewall against false encouragement. It has two jobs:
- **The leakage suite (T1/T2/T7)** must catch look-ahead that every statistical gate misses (GAP-P12D-65).
- **The look register** must count every look at real data (GAP-P12D-64).

**A guard that cannot fail is worse than none (A16).** Your first job is to make each guard miss what it
claims to catch, or pass what it should refuse.

## Rules for both auditors
- **Fresh context and model.** You run in fresh context on Opus, as a finder, not a clearer (A5). Attest to it. No subagents.
- **Never modify the worktree or the main tree.** Export private copies with `git archive` of `5d96570` and
  of `577d882` into `<SCRATCH>/<your-name>/{tree,base}`, where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
- **Laptop limits.** Use `python -m pytest -p no:cacheprovider`, and check that ≥1 GB is free before any full run. Never run
  `scripts/leakage_suite.py` at its full default (about 2 h); use short tapes. The laptop loses power without
  warning (GAP-P12D-76), so write your report early and keep updating it.
- **Refutation (A6).** Reproduce every finding with a script (internal lens), or quote it with a dated URL (external lens).
- **Your only repo write** is your report: `archive/AUDIT_BUILDER2_BRANCH_{INTERNAL,EXTERNAL}_2026-09-25.md`.

## Attack surfaces
1. **T2 (future-perturbation) and T1 (truncation).**
   - Does the comparison really cover EVERY decision point in each component: bars, labeller, AGON, the fitness simulator, `evolve_fold`, and the engine path?
   - Can the decision capture miss a decision type, e.g. orders versus signals versus evolution records?
   - Does the perturbation really change every later price, while leaving the past bit-identical?
   - Construct a leak each test misses: a cache keyed on a whole file, a statistic over the whole sample, a DST- or time-zone-shifted read, a leak below the daily grid (the author's own R1).
2. **T7.** Do the positive controls for the guard actually exercise the production code paths? Could the test pass with the sweep disabled?
3. **The look register.**
   - Can a real-data grade run without a line: another entry point, a direct `Backtest.run`, a script?
   - Can a line be forged, reused, or registered for a different run?
   - Is exclusive create atomic on Windows?
   - Is tier derivation robust? Try a mislabelled source, a window straddling tiers, the 2024–25 holdout, and forward dates.
   - Is a look recorded even when the grade later crashes? It must be.
4. **T6, the gap-through exit.**
   - Does a bar that opens through the stop exit at the open for longs and shorts, and for stops and targets alike?
   - Are the hand-worked tests exact? Does anything change in the fitness numbers beyond the intended semantics?
   - `fitness.py` is in the mutation-gate scope: do the new tests kill the obvious mutants?
5. **Defaults.** The leakage suite's default tick changed from 5 min to 60 s. Is any verdict now vacuous, i.e. no champion evolved, so nothing compared?
6. **Constitution items:** the 300-line budget, the invariant headers, `ledger_check`, the comment shape, and the falsification cases in `falsify.cases.json` (do they match exactly once, and go red for their stated reason?).

## Lens-specific
- **INTERNAL (no web):** code against itself and against GAP-P12D-64/65 and the VALIDATOR's protocol
  (`archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` §3, §5, §7). Prioritise surfaces 1, 3 and 6.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch):**
  - Leakage testing against the 2026 literature: Fonseca, "Look-Ahead-Freedom as Temporal Non-Interference", arXiv 2607.04958; Zhang et al., "When Alpha Disappears", arXiv 2605.23959; Gençay, arXiv 2608.27734 §3.2/§6.1.
  - Is T1/T2 a sound implementation of temporal non-interference? Which channels does the literature say empirical sweeps miss?
  - The look register against research-registry practice (pre-registration; counting trials for the DSR/PBO).
  - T6 against the standard gap-through-stop fill convention in backtesting literature and practice.
