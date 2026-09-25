# AUDIT BRIEF — the BUILDER-3 branch: prop-safety tightening (pinned 2026-09-25)

> **Pinned before launch (A4).** These are the constitution's TWO lenses, and ONLY those two (owner directive
> 2026-09-24). The work was built under the owner's delegation. It touches the most safety-critical code in
> ACIS: HALT persistence, drawdown anchors, the execution freeze, close semantics and the weekend flatten.
>
> **What is under audit.** Branch `worktree-agent-a9e00713d15bb5082`, head `d8361a7`: 11 commits on top of
> `bdd3a75`, touching 35 files. Worktree:
> `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a9e00713d15bb5082`.
> The author's account is `BUILDER3_REPORT_2026-09-24.md` in that worktree. Read it LAST (A4).
>
> **The lead has already checked two things.** Treat them as claims to re-verify:
> - no guardrail, `platform_rules.yaml`, spec or ledger file is touched;
> - the suite on the branch passes (the author reports 856 passed, 6 skipped).
>
> **Ledger:** GAP-P12D-54, -55, -57, -58, -59, -74 and -75, all defined in the MAIN tree's `KNOWN_GAPS.md`.
> The branch's ledger predates -74/-75.

## The law this branch must obey (the finding bar is highest here)
CLAUDE.md: **"Never touch without a human: `config/guardrail_limits.yaml`, the equity-floor value, and
HALT/veto semantics. No code path, config flag, MCP tool, or 'temporary' test hook may weaken them… Halts
are cheap; resumes are human-only."** The branch claims to be TIGHTENING-ONLY. Your first job is to try to
break that claim. Construct any input under which the branch is LOOSER than main:
- a halt that clears without a human;
- an order that passes a gate it used to fail;
- a drawdown that reads lower;
- a budget that resets;
- a close that increases exposure;
- a flatten that doubles a position.

Any such input is the most severe class of finding.

## Rules for both auditors
- **Fresh context and model.** You run in fresh context on Opus, as a finder, not a clearer (A5). Attest to it. No subagents.
- **Never modify the worktree or the main tree.** Export a private copy first:
  `git -C "<worktree>" archive HEAD | tar -x -C "<SCRATCH>/<your-name>/tree"`, where
  `SCRATCH = C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\75c0b09c-58e4-45d3-8918-2ac09096071f\scratchpad`.
  The base for comparison is `bdd3a75`; export it the same way into `.../base`.
- **Laptop limits.** Use `python -m pytest -p no:cacheprovider`, and check that ≥1 GB is free before any full run.
  This laptop loses power without warning (GAP-P12D-76), so write your report to disk early and keep
  updating it.
- **Refutation (A6).** Reproduce every finding (internal) or quote it with a dated URL (external).
  Unreproduced claims are marked *unconfirmed*. Honest negatives are first-class.
- **Your only repo write** is your report: `archive/AUDIT_BUILDER3_BRANCH_{INTERNAL,EXTERNAL}_2026-09-25.md`.

## Attack surfaces
1. **Stage 1 (GAP-P12D-55): persisted drawdown anchors.**
   - Restart at a drawdown, across a trading-day boundary, across DST, and with a corrupt or missing store.
   - Does a store write failure fail closed?
   - Can a stale persisted anchor ever make a rule read LOWER than main would?
2. **Stage 2/2b (GAP-P12D-57): lot rounding, the request budget, and the close exemption.**
   - Round-DOWN only, and REJECTED FillReports are never silent.
   - Does the rolling 24-hour budget survive a restart? Does it count every submit, modify and cancel?
   - Can the "close exemption" be abused by an order labelled close that increases exposure?
3. **Stage 3 (GAP-P12D-58): the pre-close ban on every account.** Check the ban window's time zone and DST
   (weekly close at 17:00 New York; `{zone, at}`).
4. **Stage 4 (GAP-P12D-54/-59): the daily-reset rule type and `initial_capital`.**
   - Reproduce FTMO's published semantics exactly (the Trading Objectives page, modified 2026-05-13): the
     daily floor is the balance at 00:00 CE(S)T minus 5% of initial capital, measured on equity; the max
     loss is static on equity. Use `Europe/Prague` DST boundaries.
   - What happens if `initial_capital` is absent, or a rule references it inconsistently?
5. **Stage 6 (GAP-P12D-75): halts restored at boot.**
   - Is every halt kind recorded BEFORE it takes effect?
   - Is restore ordering airtight: before the first evaluate, and before any order can pass?
   - Does a human resume clear exactly what it should?
   - How is the token "fingerprinted"? Is any secret written in the clear?
   - Can a halt be lost, or duplicated?
6. **Stage 7 (GAP-P12D-74): reduce-only closes and the freeze.**
   - A close against a flat or same-side venue must be REJECTED; an oversized close is capped.
   - Check partial fills, and races between two closes.
   - Is the venue position used in the check stale?
   - Does the freeze now admit ONLY genuinely reducing closes?
7. **Stage 5: the weekend flatten.**
   - Does it fire exactly once per window? What about pair legs, partial fills, and a restart inside the window?
   - Does it interact safely with the budget, the freeze and halts? Can it double a position?
8. **Test integrity (A16).** Re-falsify the key tests in your own copy. For each existing test the branch
   changed, check it is not weaker. The author says `test_frozen_blocks_opens_allows_closes` is now
   STRICTER: verify it.
9. **Constitution items:** the 300-line budget and its ratchet; the invariant headers; `ledger_check`; the
   comment shape (`node ../specs_constitution/checks/code-shape.mjs`); hygiene (the root report and the
   PARTIAL files must be relocated at merge).

## Lens-specific
- **INTERNAL (no web):** code against itself and against the spec (master §7.5, §8, §9.5; ACIS-05/06/07).
  Prioritise the "looser than main" hunt, and surfaces 5, 6 and 1.
- **EXTERNAL (WebSearch capped at 25 calls, then WebFetch):**
  - FTMO's and E8's primary rules pages, for stage 4 semantics and stage 3/5's gap-trading and weekend
    rules.
  - Reduce-only and close-position semantics in real venue APIs: cTrader Open API (`ProtoOAClosePositionReq`,
    position ids); FIX `ExecInst` reduce-only; broker practice.
  - The literature on crash-safe persistence (write ordering, fsync, SQLite WAL durability on Windows) as it
    applies to the anchor and halt store.
  - Known bug classes of order-management and risk-halt systems (double-fills on retry, stale-position
    races, unsolicited fills: see GAP-P12D-70), and whether the branch is exposed to them.
