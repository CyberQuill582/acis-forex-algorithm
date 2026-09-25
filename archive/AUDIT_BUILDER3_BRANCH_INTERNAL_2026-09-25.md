# AUDIT-INTERNAL — BUILDER-3 branch (prop-safety tightening), 2026-09-25

- **Auditor:** AUDIT-INTERNAL on Opus 5.5 (`claude-opus-5-5`), in fresh context, with no subagents and no web. A finder, not a clearer (A5).
- **Brief:** `AUDIT_BRIEF_BUILDER3_2026-09-25.md` (pinned 2026-09-25). Lens: internal consistency.
- **Target:** branch `worktree-agent-a9e00713d15bb5082`, head `d8361a7`, base `bdd3a75`.
- **Method:**
  - private `git archive` exports of head and base into the session scratchpad (`audit3_internal/{tree,base}`), plus a mutant copy (`mut/`);
  - every finding reproduced by a script run against BOTH exports; the scripts are in `audit3_internal/repro/`;
  - the attack was formed from the code first, and the author's `BUILDER3_REPORT_2026-09-24.md` was read LAST (A4).
- **Status:** COMPLETE. A clean result here is not a sign-off.

## Verdict in one paragraph
**The tightening-only claim is FALSE: four inputs make head looser than base.**
- **F0 (critical):** a failed halt-ledger write drops the equity-floor flatten and HALT for good.
- **F1:** a stale session-halt row mutes every later daily-drawdown session halt after a restart.
- **F11:** lot rounding orphans a pair leg that base filled whole.
- **F3:** a restart made while the account is up reads later losses lower. This one is by design (restart invariance), but it contradicts the stated claim.

Two more findings break the branch's own stated invariants without being looser than base:
- **F4:** a reduce-only close can flip a position under concurrency, or open a hedge on a hedging venue.
- **F6:** a declared `initial_capital` can lower the static anchor.

The code under test is otherwise well built:
- the suite is green (856 passed, 6 skipped);
- A16 re-falsification kills 20 of 21 mutants;
- no guardrail, spec or ledger file is touched.

**Merge fitness:** not fit as is. Fit after the conditions in the "Merge fitness" section below are met.

## Findings, ranked by severity

### F0 — CRITICAL, LOOSER THAN BASE: one failed halt-ledger write loses the equity-floor FLATTEN and HALT for good
- **Reproduction:** `repro/r6_store_failure.py`.
  - Setup: equity goes 9,050 → 8,990, under the $9,000 floor, with no drawdown rule near its limit.
  - The risk store raises `sqlite3.OperationalError("database is locked")` on the first evaluate under the floor, then recovers.
- **Base `bdd3a75`** (the Governor sink wired direct):
  - evaluate #1 raises (from the snapshot write), but the Governor is already halted and execution frozen;
  - evaluate #2: `halt`, frozen.
- **Head `d8361a7`** (`PersistentHaltSink` over the same sink, as the branch prescribes):
  - evaluate #1: `formula`, not frozen;
  - evaluate #2, with the store healthy again: still `formula`, not frozen.
  - The equity breaker never fires again in this process.
- **Mechanism:**
  - `Guardrails.check` sets `_equity_flattened = True` BEFORE it calls `sink.flatten`.
  - `PersistentHaltSink.flatten` calls `store.record_halt` BEFORE forwarding. When that write raises, neither the flatten nor the HALT reaches the Governor or execution.
  - The latch then suppresses every retry until a human `rearm()`.
  - `_issue_halt`, `_issue_session_halt` and `_issue_flatten` use the same order (latch first, sink second), so every halt kind is exposed.
- **Why base was safe:** its sink never touched I/O. The branch put a disk write in front of the only upward edge, and that write's failure does not fail closed.
- **Brief surface 1** ("does a store write failure fail closed?"): **no**.
- **Fix direction:** a failed record must still forward the halt and then raise; or the latch is set only after the sink returns. Add a regression test with a failing store.

### F1 — HIGH, LOOSER THAN BASE: a stale session-halt row mutes every later daily-drawdown session halt after a restart
- **Reproduction:** `repro/r2_stale_session_latch.py`.
  - Day 1: 10,000 → 9,790 (−2.1%) → a session halt, which auto-lifts at the boundary. A session halt never needs a human resume, so its row is never cleared.
  - Restart on day 3. Day 3: 10,000 → 9,790 → 9,990. Entry attempted 3 minutes after the breach.
- **Result:**
  - base `bdd3a75`: `drawdown_halt` (the master §8 session halt holds until the next boundary);
  - head `d8361a7`: `formula`, so the order is sized.
- **Mechanism:**
  - `Guardrails.restore_state` sets `_session_halted = True` for every uncleared `session` row.
  - The Governor lifts the stale halt at once, because its boundary is in the past.
  - The Risk latch stays set, and `_issue_session_halt` returns early while it is set.
- It violates the conflict-table row "daily drawdown limit hit → halt new positions for session".
- Rows also pile up forever: every session halt is re-applied at every boot until a human resume.

### F2 — HIGH, PRE-EXISTING in base and head, the root of F1: only the first daily-drawdown breach in a process's life session-halts
- **Reproduction:** `repro/r2b_inprocess_latch.py`. One process, a day-1 breach, then a day-3 breach: both trees return `formula` on day 3.
- **Mechanism:** `_session_halted` is set in `_issue_session_halt` and reset only in `rearm()`, the human resume. Nothing resets it when the Governor's session halt lapses at its boundary.
- The taper (0 at a distance ≥ 0.8) blocks entries only while the drawdown persists. Once equity recovers within the session, trading resumes.
- **Not branch-introduced.** It is HALT semantics, so it is RAISED to the owner: the fix belongs with GAP-P12D-59's daily-halt decision. A new ledger ID is needed.

### F11 — HIGH, LOOSER THAN BASE on the shipped mock, partly pre-existing: lot rounding orphans a pair leg and leaves directional exposure
- **Reproduction:** `repro/r9_pair_leg_rounding.py`.
  - A pair group on the shipped `MockExecutionFace`, which declares a minimum lot of 0.01 (1,000 units) and the same step.
  - Legs: EUR_USD +1,500 and USD_JPY −900.
- **Result:**
  - base: both legs fill in full;
  - head: EUR_USD fills +1,000, USD_JPY is refused below the minimum, and the venue holds ONE directional leg.
- **Mechanism:**
  - Each leg is rounded and checked against the minimum independently. Nothing in execution enforces ACIS-05 §5.5 "both legs or neither".
  - Nothing completes or flattens the orphan, although master §13 says a pair leg is "never left directional".
  - Rounding each leg independently also breaks the GAP-P12D-26 USD balance.
- **Pre-existing part:** on a venue that enforces its own minimum, base's leg would be REJECTED by the venue into the same orphan. The branch makes the orphan deterministic, and very likely at prop sizes (typical orders of 332–926 units against a 1,000 minimum, per GAP-P12D-57).
- **Test gap:** `test_pair_group_executes_both_legs` and the pair-exit tests were moved to a 1-unit venue, so no test runs a pair on a coarse-step venue.

### F4 — HIGH, breaks the stage-7 invariant but not looser than base: a "reduce-only" close can FLIP a position, and OPENS a hedge on a hedging venue
- **Reproduction:** `repro/r3_close_race_and_hedging.py`.
  - (a) Concurrent closes: long 100,000 on a mock whose calls yield to the event loop, as any network adapter's do. Two closes run under `asyncio.gather`. Head leaves the venue SHORT 100,000; base left it long 300,000.
  - (b) Hedging venue: a venue declaring `account_model="hedging"`, where an opposite market order opens a new position. Long 100,000, then three closes, as the weekend flatten's every-tick re-emission produces. Head ends net SHORT 200,000 with gross 400,000; base ended net long 400,000.
- **Mechanism:**
  - `_reduce_only` reads `open_positions()` and then awaits `submit_order`, with no lock or reservation between them (check-then-act).
  - `reducible` sums only the named side, so on a hedging venue the long still counts as closable after every hedge.
  - `ExecutionFace.submit_order` has no close, reduce-only or position-id argument, so no adapter can tell a close from an open.
  - Nothing reads `descriptor.account_model` or `descriptor.partial_close`.
- **Contradictions:**
  - `venue_limits.py` says a close "can shrink |position| but never open, add to, or flip one".
  - Main's ACIS-13 v0.1 C-VEN-9 (a reduce is `ClosePositionReq{positionId}`) cannot be implemented behind this face signature.
- **Author's coverage:** R2-5 and R7-2 name the hedging case, but assign it to ACIS-13, which the face contract then blocks. The concurrency race is not mentioned.

### F3 — MEDIUM, LOOSER THAN BASE by design; the claim as worded is false: a restart while the account is UP reads a later loss lower
- **Reproduction:** `repro/r1_restart_while_up.py`, with `r1b_no_restart.py` as the control.
  - 10,000 → 10,500 intraday, restart the same day, then 10,500 → 10,280.
- **Result:**
  - base: engine:daily 2.095%, static 2.095%, taper 0.0, a session halt;
  - head: 0.0%, 0.0%, taper 1.0, no halt.
  - Without a restart both trees read 0.0%. Head makes the restart path equal the declared day-open / inception semantics; base's re-anchoring on restart was an artifact that happened to be stricter here.
- **Verdict:** the property the branch delivers is "restart-INVARIANT", not "tightening-only".
  - `Guardrails.restore_state` says "it cannot loosen one", and the report says "No guard loosened". Both are false relative to base.
  - The owner must ratify the property that was actually delivered.

### F5 — MEDIUM: closes can exceed the request budget without bound, and a restart forgets some attempts
- **Reproduction:** `repro/r4_budget.py` (head only; base has no budget).
  - (b) Budget of 5 per 24 h and a venue that rejects every close. Re-emitting the close 20 times gives 21 venue submits (`budget.used = 21`), plus 20 `open_positions()` reads that are never counted.
  - (a) Six ConnectionError attempts are counted in memory; after a restart the seed reads 3.
- **Why it matters:**
  - The close exemption is by design, but `weekend_flatten` re-emits every tick with no backoff.
  - A venue that rejects closes (market shut, a CLOSE_ONLY or NO_TRADING account, a stale portfolio) therefore turns the flatten into a request flood past the firm's hard 2,000/day cap: the breach GAP-P12D-57 exists to prevent.
- **Already acknowledged:** part (a) is the author's R2-2, and the uncounted reads are R2-1. The unbounded re-emission is new.

### F6 — MEDIUM, latent and config-gated: an `initial_capital` below the attach balance lowers the static rule; a typo disables it
- **Reproduction:** `repro/r5_initial_capital.py`. The `ftmo` rules, attached at 11,000, then 9,950. The static max-loss rule reads:
  - 9.55% with no capital declared (base semantics);
  - 0.50% with 10,000;
  - 0.00% with 6,000 or with 600 (a dropped zero kills the rule).
- **Contradictions:**
  - `config/rulebook.py` says a declared capital "can only make a rule stricter than the first observed basis would".
  - The report says "The initial capital only raises anchors".
  - Both are contradicted by the branch's own `test_ftmo_max_loss_is_static_on_equity_at_initial_minus_10pct`, where an attach at 110,000 reads 0%.
- 10,000 is the FTMO-faithful value, but nothing checks the declared capital against the balance seen at attach.
- No shipped rulebook declares `initial_capital` (a test pins that), so nothing changes today.

### F7 — MEDIUM: restoring before the first evaluate is a convention, not a construction
- **Reproduction:** `repro/r7_restore_ordering_and_collision.py`, part (a).
  - An equity-floor flatten and HALT are recorded.
  - A fresh process evaluates and allocates without calling `restore_on_boot`.
  - Both rows are open on disk, yet the Governor returns `formula`.
- **Why it matters:** GAP-P12D-75 recurs the moment a runtime forgets one call, while ACIS-07 (line 119) requires a start in a halted state.
- **Suggested fix:** a store-backed monitor refuses `evaluate()` until it has been restored, or the Governor boots halted.
- The author names the wiring gap (R1-1, R6-1); the missing structural guard is this finding.

### F8 — MEDIUM, tightening but operationally harmful: two resume verbs, only one clears the ledger
- **Reproduction:** `repro/r8_resume_split.py`.
  - Equity floor → `CapitalGovernor.resume(token)`, the verb MCP drives today → trading resumes.
  - The rows stay open, so the next restart re-applies the `halt`, freezes execution and flattens the book.
- A restart after a legitimate human resume therefore liquidates every position opened since.
- `monitoring/tools.py` `ControlTarget.resume` does not require `on_human_resume`. The author's R6-1 notes the wiring is owed; the contract should state it.

### F9 — LOW: a halt re-issued at the instant of a CLEARED row is not persisted
- **Reproduction:** `repro/r7_restore_ordering_and_collision.py`, part (b).
- **Mechanism:** `record_halt` is `INSERT OR IGNORE` on `halt_id = kind|at|scope|reason`. The re-issued halt is live in memory but absent on disk, so a restart forgets it.
- **Likelihood:** it needs a repeated instant: a simulated clock reused on one store, or a wall clock stepped back.

### F10 — LOW: `cleared_by` carries 48 bits of the same unsalted SHA-256 the MCP verifier holds
- `clear_halts` writes `human:` plus `sha256(token)[:12]`. `monitoring/auth.py` verifies the token against the full unsalted `sha256(token)`.
- The risk DB therefore gives an offline dictionary oracle against a low-entropy token.
- `on_human_resume` accepts any non-blank string. That is the same standard as base's `Governor.resume`, so it is not a loosening.

### F12 — LOW: test gaps and claim drift
- **A16 survivor:** `RiskStore.clear_halts`'s own blank-token refusal is untested; the identical check in `on_human_resume` masks it.
- **Claim drift:**
  - the orchestrator docstring now says "Every refusal is a FillReport", but a frozen open still returns `()` (pre-existing behaviour);
  - the report says `guardrails.py` is 236 lines; the export has 253;
  - a missing or empty risk store boots silently with fresh anchors, which is base behaviour and is logged only as empty restores.

## "Looser than base" hunt: summary
| Brief item | Found loosening? |
|---|---|
| A halt that clears without a human | **No clear**, but the halts are MUTED or DROPPED instead: F0, F1. |
| An order that passes a gate it used to fail | **Yes (F1):** after a restart, a daily breach no longer session-halts. **Yes, on the shipped mock (F11):** a pair's larger leg trades alone. |
| A drawdown that reads lower | **Yes:** F3 (by design) and F6 (config-gated). |
| A budget that resets | Partially (F5a, documented as R2-2); base had no budget. |
| A close that increases exposure | Not versus base (base was worse), but yes versus the branch's own invariant: F4. |
| A flatten that doubles a position | On a netting venue with sequential dispatch, no. Under concurrency, or on a hedging venue, it flips or accumulates (F4). |

## Honest negatives (no loosening found)
- **Halt clearing:** no path clears a halt row without a non-blank token. A restored session halt lifts only at its own original boundary. Restore re-applies every open row with its own scope and reason, and restoring writes no duplicate rows.
- **Lot rounding:** it never rounds up or sends more than the Governor sized. C-EXE-6 holds, fragments are whole steps, the last fragment is never negative, and the A16 mutant that rounds UP is killed.
- **Sequential closes on a netting venue** never grow |position|:
  - a close against a flat venue is refused;
  - a close naming the other side is refused;
  - an oversized close is capped;
  - after a partial fill, the check is redone against the venue's holding.
- **The freeze** admits only `action == "close"`, and every close passes the reduce-only check before each attempt.
- **Without a restore or a declared `initial_capital`,** head's drawdown series is numerically identical to base (checked by reasoning and by `r1b`).
  - The `exposure.py` and `usd_conversion.py` moves are verbatim.
  - The drawdown-series refactor keeps base semantics for `static` and `trailing`.
- **DST:**
  - The pre-close ban is correct in EDT and EST.
  - Prague midnight was checked against `zoneinfo` every 30 minutes from 2012 to 2026. All 1,440 mismatches fall on the local date of the two switch Sundays, at Saturday-night UTC instants inside the FX weekend, as the fx_clock docstring declares.
- **A corrupt persisted anchor** (NaN, negative, bad JSON) refuses boot, which fails closed.
- **A missed-rollover bracket** is never below either sample, so it can only be stricter.
- **The weekend flatten** fires only on no-weekend accounts, starts exactly at the ban, retires both pair legs, and surfaces `WEEKEND_FLATTEN_INCOMPLETE`.
- **The lead's two claims are re-verified:**
  - no guardrail, `platform_rules.yaml`, `ACIS_SPEC.md`, `specs/`, `KNOWN_GAPS*` or `TODO.md` is touched;
  - the head suite passes: **856 passed, 6 skipped** (448 s, private export).

## Test integrity (A16) and constitution items
- **Re-falsification:** `repro/a16_mutations.py` ran 21 hand mutants on the branch's key lines in a private copy. **20 were killed and 1 survived (F12).**
  - Killed: close sent on its own side; reduce-only check skipped; halts not restored; anchors not restored; budget never refuses; no restart seed; lot step rounded UP; platform daily never resets; pre-close ban re-tied to the weekend flag; ledger records nothing; resume leaves rows; dedupe removed; restored static not clamped to capital; missed-rollover bracket removed; flatten ignores the weekend flag; Prague without DST; taper not re-pushed; initial capital not the static anchor; daily limit sized on its anchor; frozen opens admitted.
- **`test_frozen_blocks_opens_allows_closes` is STRICTER, as claimed.** Base asserted that a close into a flat venue FILLS. Head asserts it is REJECTED, and that a real close trades the other side and leaves the venue flat. Mutants M1, M2 and M21 each fail it.
- **Other changed tests:**
  - the `test_governor` weekend line is inverted to the stricter outcome;
  - the fixtures only gained the new required key;
  - the two pipeline tests are not weaker in net effect (filled equals the whole units, and filled plus unsent equals the size), but moving them to a 1-unit venue hides F11.
- **Budget ratchet:**
  - every touched module is ≤ 300 lines, and `orchestrator.py` sits at exactly 300;
  - grandfather ceilings only fell (schemas 581, capital_governor 437, monitor 368, venue 342), and `guardrails.py` left the list;
  - every new module opens with its invariants.
- **`ledger_check`:** 204 entries, 0 violations. The branch's ledger predates GAP-P12D-74 and -75.
- **Code shape:**
  - the touched files are within baseline;
  - the gate's 4 NEW violations (`core/optimizer/costs.py`, `scripts/cost_stress_ladder.py`) are identical on base `bdd3a75`, so they are inherited;
  - the `feeds.py|HISTORY` burn-down is also inherited.
- **Hygiene:** `BUILDER3_REPORT_2026-09-24.md` sits at the repo root and must be `git mv`'d to `archive/` at merge. No PARTIAL file was added at the root.

## Merge fitness
**Not fit as is.** It becomes fit to merge after:
1. **F0 is fixed**, with a regression test that uses a failing store.
2. **F1 is fixed**, so that a restored session row never sets a latch that outlives its own boundary. Its root cause, F2, is filed and raised to the owner as HALT semantics.
3. **The claims are corrected to what is delivered:** F3 "restart-invariant" (owner ratifies), F6's docstring, and F4's invariant.
4. **F4 and F11 are fixed or filed as owned residuals that block any demo or live attach:**
   - serialise closes per (venue, instrument);
   - carry close intent (a position id) through `ExecutionFace.submit_order`;
   - refuse or handle `account_model == "hedging"`;
   - make pair groups atomic in execution.
5. **F5, F7 and F8 are filed** with the runtime wiring gap (GAP-0091b).
