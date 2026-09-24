# AUDIT BRIEF — the BUILDER branch of the five-agent edge pass (pinned 2026-09-24)

> **Pinned before launch (constitution A4).** Owner-ratified in chat, 2026-09-24: "i ratify the whole of
> step 1", which includes this dual audit.
>
> **What is under audit.** Branch `worktree-agent-a128ab904780ce593`, head `9b9ec80`: 8 commits on top of
> `7695ed0`, across 18 files. Worktree:
> `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a128ab904780ce593`.
> The author's account of its own work is `BUILDER_REPORT_2026-09-24.md` in that worktree. Read it LAST
> (A4: form your attack from the code and observed behaviour first).
>
> **The lead has already checked three things.** Treat them as claims to re-verify, not as settled:
> - the full suite on the branch gives 828 passed, 6 skipped;
> - the diff touches no config, guardrail, spec or ledger file;
> - the three seed/fold-index test changes are legitimate.
>
> **Ledger context.** GAP-P12D-37 (oracle), -38 (refuted zero-duration trades), -34 (plateau law),
> -33 (DSR gate), -49 (TSMOM), -63 (MOMENTUM_SCALP never fires on synthetic tape). Pass entry: GAP-P12D-52.

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** Attest to it in your report. Launch no subagents.
- **Never modify the builder's worktree.** To run or mutate anything, export a private copy first:
  `git -C "<worktree>" archive HEAD | tar -x -C "<SCRATCH>/<your-name>/tree"`, where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
  - Run pytest there with `-p no:cacheprovider`.
  - Before a full-suite run, check that at least 1 GB of memory is free. Other agents share the laptop
    (7.9 GB); prefer targeted test runs.
- **The main tree is read-only:** the repo root, including `data/`.
- **Refutation (A6).** Every finding is reproduced by a script, or cites `file:line` (internal lens), or
  quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as
  *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps, A12 size and complexity, A13 hygiene,
  and A16 hollow tests. Taste and wording are out.
- **Deliverable.** The internal lens writes `archive/AUDIT_BUILDER_BRANCH_INTERNAL_2026-09-24.md`; the
  external lens writes `archive/AUDIT_BUILDER_BRANCH_EXTERNAL_2026-09-24.md`. That file is the ONLY repo
  write either of you makes. Use this shape: an executive summary; findings (Severity/Likelihood,
  reproduction, proposed fix); honest negatives; what you could not verify; residual risk.

## Attack surfaces (both lenses; weight them by your lens)
1. **The oracle positive control:** `tests/backtest/oracle.py`, `test_oracle_control.py`,
   `synthetic_grade.oracle_row`, and the stage-1 VOID logic in `scripts/falsify_engine.py` (exit 4).
   - Did the changes to `synthetic_market.py` alter the price paths the ENGINE is graded on? The same
     `MarketSpec` and seed must produce a byte-identical tape before and after. Check the RNG
     consumption order.
   - Does `void_reasons` reproduce `report.passed`'s non-DSR clauses EXACTLY? A drift between the two
     would void or pass a run wrongly.
   - Is the oracle graded through the same book, the same C8 spread and costs, and the same metrics?
   - Can it pass for a reason other than knowing the drift?
   - Is the deflation of the oracle's returns against the engine's trial sets a faithful use of the
     DSR inputs?
2. **The empty-population NaN in `metrics._avg_duration`.** Trace NaN through `targets_met`, the §14
   gate, JSON writers and readers (`json.dumps` emits the non-standard `NaN`), the MCP resources,
   `cost_stress_ladder.py`, `falsify_engine.py`, and any sum, comparison or equality. Can a NaN flip a
   gate?
3. **The §5.6 plateau law:** the new `core/optimizer/plateau.py`, `qiea.py`, and
   `param_types.repair_invariants`.
   - Is `repair_invariants` a behaviour-preserving extraction? `decode` must produce identical genes
     for identical qubits.
   - Does plateau checking consume the RNG or shift the evolution stream? It must be deterministic
     per seed.
   - Does it interact with the holdout gate, staging, promotion and logging as intended?
   - Is the 2.6 s / 3.4% cost claim true?
   - Is the operationalisation of "dies" (a one-gene ±10% neighbour failing C9 on the train window;
     any death refuses the champion) internally consistent?
4. **The evaluation registry** (stage 5). Is it logging-only, with no gate reading it? Is it
   deterministic, and what are its size and speed? Does it alter any LOCKED store schema (ACIS-03
   DDL)?
5. **Harness refactors:** `per_trade_returns` and `graded_trades`. Is the behaviour identical?
6. **Test integrity (A16).** Re-falsify at least the oracle control, the plateau tests and the NaN
   test: revert each fix in YOUR copy, confirm red for the stated reason, restore. Are the three
   changed existing tests (seed or fold index) still testing what they claim? Is any assertion
   weakened anywhere?
7. **Constitution items:**
   - (a) the 300-line module budget (`tests/unit/test_module_budget.py`);
   - (b) a one-screen invariant model atop each invariant-bearing new module;
   - (c) `scripts/ledger_check.py` green on the branch;
   - (d) hygiene: `BUILDER_REPORT_2026-09-24.md` at the root and `archive/PARTIAL_BUILDER_2026-09-24.md`
     must be relocated before merge. Is anything else left behind?

## Lens-specific
- **INTERNAL (no web):** spec against code and code against itself. Construct the failing input.
  Prioritise surfaces 1, 3 and 6.
- **EXTERNAL (WebSearch capped at 25 calls, then WebFetch):** the implementation AND the design against
  the outside world.
  - Is a *perfect-sign* oracle a meaningful positive control, or is it so strong that it proves only
    that the harness recognises an enormous edge? The VALIDATOR measured power at modest edges; see
    `archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md` §2. Should the control be graded in strength?
  - Does the plateau law's operationalisation match the robustness and parameter-stability
    literature (e.g. Pardo; Bailey et al.)? The VALIDATOR measured the plateau test alone passing
    noise 93–99% of the time.
  - The NaN convention for an empty population, and NaN in JSON (RFC 8259).
  - The BUILDER report's TSMOM claims against Moskowitz, Ooi & Pedersen (2012)'s actual method:
    lookback, holding period, excess versus spot returns, volatility scaling.
  - The DSR's intended inputs, per Bailey & López de Prado (2014).
