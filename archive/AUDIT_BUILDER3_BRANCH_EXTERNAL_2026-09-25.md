# AUDIT — BUILDER-3 branch, EXTERNAL-REFERENT lens (2026-09-25)

**Status: COMPLETE (findings reproduced or quoted; triage is the lead's, A6).**

- **Auditor:** AUDIT-EXTERNAL on Opus 5.5 (`claude-opus-5-5`). Fresh context. A finder, not a clearer (A5). No subagents.
- **Brief:** `AUDIT_BRIEF_BUILDER3_2026-09-25.md`, pinned 2026-09-25. Read before the author's report (A4).
- **Under audit:** branch `worktree-agent-a9e00713d15bb5082`:
  - head `d8361a7`, base `bdd3a75`;
  - 11 commits, 35 files.
- **Private copies:** made with `git archive` into the scratchpad folder `audit3_external/`:
  - `tree` (at `d8361a7`) and `base` (at `bdd3a75`);
  - the reproduction scripts are in `audit3_external/repro/`: `r1_stale_session_latch.py`, `r1b_inprocess.py`, `r2_store_failure.py`, `r3_close_races.py` and `r5_holiday_closures.py`.
- **Sanity check:** the branch's new and touched test files pass in the private copy (73 passed). The full suite was not re-run; the internal lens owns that.
- **Web budget:** 6 of 25 WebSearch calls used; the rest were WebFetch calls on primary URLs.

## Sources (all fetched 2026-09-25)

| ID | Source | Date |
|---|---|---|
| S1 | FTMO Trading Objectives, https://ftmo.com/en/trading-objectives/ | page `dateModified` **2026-09-24T14:03:34** |
| S2 | FTMO Forbidden Trading Practices, https://ftmo.com/en/forbidden-trading-practices/ | `dateModified` 2026-02-02 |
| S3 | FTMO FAQ on overnight and weekend holding, https://ftmo.oanda.com/faq/do-i-have-to-close-my-positions-overnight-or-before-weekend | `dateModified` 2026-08-16 |
| S4 | FTMO Trading Update, holiday hours, https://ftmo.com/en/blog/trading-updates/trading-update-18-dec-2025/ | published 18 Dec 2025 |
| S5 | cTrader Open API messages, https://help.ctrader.com/open-api/messages/ | undated |
| S6 | cTrader glossary, https://help.ctrader.com/knowledge-base/glossary/trading/ | undated |
| S7 | OANDA v20 order definitions, https://developer.oanda.com/rest-live-v20/order-df/ | undated |
| S8 | FIX 5.0 SP2 PositionEffect(77), https://www.b2bits.com/fixopaedia/fixdic50-sp2/tag_77_PositionEffect.html | — |
| S9 | FIX 5.0 ExecInst(18), https://www.onixs.biz/fix-dictionary/5.0/tagnum_18.html | — |
| S10 | SQLite PRAGMA documentation (`synchronous`, `journal_mode`), https://www.sqlite.org/pragma.html | — |
| S11 | E8: help.e8markets.com returns **HTTP 403** to fetch. The only substitute is a third-party page, https://tradetanto.com/learn/e8-markets-rules | "Last updated: August 11, 2026" |

---

## Findings, ranked by severity

### X1 — HIGH, reproduced: after a restart the engine's daily-loss session halt no longer fires (LOOSER THAN MAIN)

**What happens.** `Guardrails.restore_state` sets `_session_halted = True` for every uncleared `session` row in `halt_event`. Two facts make that permanent:
- Only a human resume clears rows (`clear_halts`).
- Only `rearm()` resets the latch, and only a human resume calls `rearm()`.

A session halt that has already lifted at its boundary therefore stays "open" in the ledger. After every later restart it re-latches the flag, so `_issue_session_halt` suppresses every NEW daily-drawdown breach until a human resumes.

**Reproduction.** `repro/r1_stale_session_latch.py` runs the same script on both trees:
1. Day 1: a 2.1% loss, and the session halt fires.
2. A restart on day 2, followed by a fresh 2.15% loss from the day-2 open. `PLATFORM_DD_BREACH engine:daily` is logged in both trees.
3. Equity then recovers within the same session.

| Tree | Entry result after the recovery |
|---|---|
| **base** (bdd3a75) | `drawdown_halt`: the session halt binds until the boundary |
| **branch** (d8361a7) | `formula`: entries are open again, and no session halt was issued on day 2 |

**Root cause, and how the branch changes it.**
- **Already on main:** the latch is process-lifetime. `repro/r1b_inprocess.py` shows the same suppression on base within ONE process spanning two days. That half is not in the ledger either.
- **What the branch adds:** it carries the latch across restarts and makes it permanent until a human resumes. Before the branch, a restart was the one path that cleared it.

**External referent.** Master §8 and CLAUDE.md define a daily-loss halt that auto-clears at the next boundary and fires again on the next breach. A firm's daily rule does the same: FTMO's "Maximum Daily Loss Limit is recalculated daily at 00:00 CE(S)T" (S1). A halt that fires only once per human resume does not implement a *daily* limit.

**Fix direction.** Either:
- clear a session row, or treat it as spent, once its boundary has passed; or
- make `_session_halted` a per-boundary latch rather than a process latch.

Pair the fix with a test that the day-2 breach halts after a restart.

### X2 — HIGH severity, LOW likelihood, reproduced: one failed `halt_event` write permanently loses the equity-floor breaker (a new failure mode versus main)

**What happens.** Two ordering choices combine:
- `Guardrails` sets its idempotency latch BEFORE calling the sink: `_equity_flattened = True`, and `_halted_scopes.add` inside `_issue_halt`.
- `PersistentHaltSink` writes the row BEFORE forwarding the halt.

If that single write raises (`database is locked`, disk full or an I/O error), then:
- the exception leaves `evaluate`;
- the halt, flatten and freeze never reach the Governor or the orchestrator;
- the latch stops every later evaluate from re-issuing them.

**Reproduction.** `repro/r2_store_failure.py`:
1. The first `record_halt` raises `sqlite3.OperationalError('database is locked')`, with equity at 8,900 against the $9,000 floor.
2. The loop carries on, and two more evaluates run below the floor.
3. Result: `EQUITY_FLOOR_BREACH` was logged once, the entry result is **`formula`**, the orchestrator is **not frozen**, and there are **0** halt rows.

On main the sink had no store, so this path did not exist.

**Referent.**
- Write-ahead ordering (log, then apply) is the right rule for making a *recorded* state recoverable.
- For a *protective* action, the fail-safe default is the opposite: a failure of the bookkeeping must not suppress the protection.
- The exposure depends on the not-yet-built runtime. If it catches the exception and continues, the breaker is lost. If it crashes, the next boot re-fires the breaker, because no row was written.

**Fix direction.** Either:
- apply the halt even when the write fails, then escalate the write failure as its own halt or alert; or
- set the latches only after the sink returns.

### X3 — HIGH: "reduce-only" is an engine-side check-then-act, and the venue receives a plain opposite-side order. Real venue APIs carry the close intent atomically, and the branch drops it at the face boundary

**What the branch does.**
- `_reduce_only` reads `face.open_positions()`.
- `_submit_once` then sends `submit_order(direction=_side(order))`.
- `ExecutionFace.submit_order` has no `action` parameter. The ACIS-13 draft (main tree, §7.3 step 1) therefore makes the face **infer** close intent from its own position view: "if an ACIS position exists on `instrument` with direction `−direction`, the order is a **reduce**; otherwise it is an **open**."

**What real venues provide.**
- **cTrader:** `ProtoOAClosePositionReq` "positionId: The unique ID of the position to close." `ProtoOANewOrderReq.positionId`: "Reference to the existing position if the Order is intended to modify it." (S5)
- **OANDA v20:** `REDUCE_ONLY`: "When the Order is filled, only reduce an existing Position." `DEFAULT`: "use REDUCE_FIRST behaviour for non-client hedging Accounts, and **OPEN_ONLY behaviour for client hedging Accounts**." (S7)
- **FIX:** PositionEffect(77) 'C' = Close, "Used for omnibus accounting - where accounts are held on a gross basis instead of being netted together." (S8) ExecInst(18) has only 'E' "Do not increase - DNI" and 'F' "Do not reduce - DNR" (S9); FIX has no generic reduce-only ExecInst.
- **cTrader hedging accounts:** they "allow traders to open multiple positions for the same instrument in opposite directions (buy and sell) simultaneously" (S6).

In every one of these, a venue-enforced close fails safe when the position is already gone. A plain opposite-side order opens exposure instead.

**Reproduced in `repro/r3_close_races.py`:**
- **(a) Venue-initiated fill.** The server-side stop (master §279) fills between ACIS's read and its send (GAP-P12D-70). The "close" of a 0.5-lot long FILLS as a sell and leaves a **0.5-lot SHORT with `stop_loss=None`**, an unprotected position.
- **(b) Two concurrent closes** of the same 0.5-lot long, against a face with network latency: both read 50,000 held, both fill, and the venue ends **short 0.5 lot, unprotected**.

**Why it matters.**
- These are the textbook stale-position and double-close bug classes.
- The venue_limits invariant, "can shrink |position| but never open, add to, or flip one", is false under both interleavings.
- Several close sources can emit a close for the same position on the same tick: the weekend flatten, group exits and the Risk flatten. So case (b) needs only a runtime that dispatches them concurrently.

**It is not looser than main.** Main added to the position on every close (GAP-P12D-74 F1). The residual belongs to the design.

**Fix direction.**
- Carry `action` (and a venue position id where the venue has one) through `ExecutionFace.submit_order` (OQ-03c), and map it to the venue-native atomic close:
  - cTrader: ClosePositionReq(positionId);
  - OANDA: `positionFill: REDUCE_ONLY`;
  - FIX: PositionEffect=C.
- Serialize closes per instrument in the orchestrator.

The builder's R2-5 and R7-2 name the hedging half. The race half, which also applies to netting accounts, is not in the ledger.

### X4 — MEDIUM-HIGH, quoted and verified: the halt ledger, the anchors and the fill log are not power-loss durable in their current SQLite mode (GAP-P12D-76 makes this live)

**Current mode.** `RiskStore` and `FillReportStore` open with the default rollback journal, verified in the private copy: `journal_mode=delete`, `synchronous=2` (FULL), SQLite 3.45.1 on win32.

**SQLite's documentation for that mode (S10):**
- "FULL is not necessarily durable across a power loss in rollback mode, so if durability is desired, it is best to set the synchronous mode to EXTRA."
- "Without EXTRA, depending on the underlying filesystem, it is possible that a single transaction that commits right before a power loss might get rolled back upon reboot … the last transaction might go missing".
- "FULL is atomic, consistent, isolated, and durable (ACID) in WAL mode".

**What this breaks.** `halt_ledger.py` claims a crash "can only leave a recorded halt not yet applied (restored at boot), never the reverse". That holds for process crashes: "Transactions are durable across application crashes regardless of the synchronous setting" (S10). It does not hold for a power loss. On this laptop, a halt, anchor or budget row committed just before a hard power-off can vanish.

**Fix direction.**
- Open these stores in WAL mode with synchronous FULL. The repo already has `core/data/sqlite_wal.open_store`, whose docstring says FULL is kept.
- Or set EXTRA. Whether EXTRA's directory sync does anything on the Windows VFS is *unconfirmed*; WAL+FULL is the documented durable choice.

### X5 — MEDIUM, quoted and reproduced: the pre-close entry ban (stage 3) and the weekend flatten (stage 5) key only on the Friday close. FTMO's rules bind at ANY closure of two hours or more, holidays included

**FTMO's rules.**
- **Gap trading (S2),** on every account: "opening simulated trades … two hours or less before a relevant financial market is closed for at least two hours".
- **Standard FTMO Rewards account (S3):** "you are required to close your positions shortly before the markets close for the weekend **or if the rollover (market break) lasts longer than 2 hours**."
- **Holiday hours (S4):** "Forex & Exotics … Closed" on Dec 25 and Jan 1. Metals: "Close Early at 20:45" on Dec 24. US indices: "Close Early at 20:15" (GMT+2 platform time).

**The 2026 calendar.** In 2026 both holidays fall on a **Friday**. The FX market's last close before a three-day closure is then **Thursday 17:00 New York**.

**Reproduced (`repro/r5_holiday_closures.py`), on a no-weekend-holding rulebook:**

| Time | Allocate result | `weekend_flatten` result |
|---|---|---|
| Thu 2026-12-24 16:00 NY | `formula`: the entry is allowed | 0 closes |
| Thu 2026-12-31 16:30 NY | `formula` | 0 closes |
| Fri 2027-01-01 15:30 NY (market shut about 22 h) | — | logs `WEEKEND_FLATTEN`, not `WEEKEND_FLATTEN_INCOMPLETE` |

**Consequences.**
- On any FTMO account, this is gap trading.
- On a Standard account, positions are held through a three-day closure.
- Both dates fall inside the planned demo period.
- Daily breaks longer than 2 h on non-FX symbols (index CFDs) are also uncovered once they are enabled.

**Fix direction.** Drive the ban and the flatten from each instrument's next closure of two hours or more, taken from a holiday-aware calendar. `cme_metals` already carries `holidays`; `fx_default` has none.

*Caveat:* FTMO's 2026 holiday table is not yet published. The finding assumes FTMO repeats its 2025 schedule, which follows the interbank convention.

### X6 — LOW-MEDIUM, quoted: FTMO counts closes toward its 2,000-request line, but the close exemption has no ceiling and a failing close is re-emitted every tick with no backoff

**FTMO's rule (S2).** Forbidden: "an excessive number of more than 2,000 server requests per day **on individual simulated trades** or pending orders". Closing or amending a trade is such a request.

**What the branch does.**
- `RequestBudget.admit(closing=True)` always admits.
- `weekend_flatten` "is called every tick, so a close that fails is re-emitted".
- Each attempt also triggers an `open_positions()` read.

**What caps the exposure.** Only the 1,000 margin between the engine's open cap and FTMO's line. A venue that keeps rejecting a close (for example a symbol that is trading-disabled or already closed) produces one submit per tick.

**Also on record:**
- The restart seed is only a lower bound (the builder's R2-2).
- The seed stamps are venue fill times, while `now` is the local clock. The laptop runs 16 minutes slow (GAP-P12D-51), so an ahead-of-venue local clock would expire stamps early by the skew.

**Fix direction:** a separate close sub-budget or a backoff, kept below the firm's hard line.

### X7 — LOW, quoted: FTMO 1-Step's max loss cannot be approximated safely with the current trailing type

**FTMO's rule (S1).** "The Maximum Loss rule establishes an **end-of-day trailing** limit … recalculated daily at 00:00 CE(S)T as the difference between: the highest **account balance** achieved at 00:00 CE(S)T of any preceding trading day or, if higher, the amount of Initial Simulated Capital, and the Maximum Loss Amount, which is 10% of the Initial Simulated Capital", measured on **equity**.

**Why no current encoding is safe.** The branch's `trailing` type uses one `basis` both to set the anchor and to measure against it. Both encodings are LOOSER than FTMO in reachable states:
- **`basis: equity`.** Realise +10k on one trade while another position floats at −5k over midnight. The balance anchor is 110k, but the equity high-water mark is only 105k. The engine's floor is 95k against FTMO's 100k.
- **`basis: balance`.** Floating losses are never measured.

The builder states that 1-Step is "not expressible". The addition here: neither near-miss encoding should be used as a stand-in.

### X8 — LOW (a documentation fix): the FTMO citation date is stale

The brief and the builder's report pin FTMO's Trading Objectives at "modified 2026-05-13". The live page now carries `dateModified` 2026-09-24 (S1). The 2-Step semantics are unchanged (see N1), but tests and rulebook comments should cite the re-verified date.

### X9 — LOW, conditional, quoted: the resume "fingerprint" makes `risk.db` an offline guessing oracle for a human-chosen token

**What is stored.** `clear_halts` writes `human:` + the first 12 hex digits (48 bits) of the *unsalted* SHA-256 of the resume token. `monitoring/auth.py` authenticates the same token against the *unsalted* SHA-256 digest. So the database, readable by any process on the host, holds a 48-bit prefix of the credential's verifier.

**OWASP Password Storage Cheat Sheet** (https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html, fetched 2026-09-25):
- "Fast hashing algorithms such as SHA‑256 are not suitable for password storage because they allow attackers to perform large numbers of guesses quickly."
- "A unique salt must be added to each password".

**When it matters.** This is harmless if the token is a long random secret, and it becomes a finding if the token is human-memorable.

**Fix direction.** Either:
- record a non-secret token *id* rather than a digest of the secret; or
- use a keyed HMAC whose key is not in the database.

No secret is written in the clear: the brief's direct question is answered **no**.

---

## Honest negatives (checked against the outside world and found to hold)

- **N1. FTMO 2-Step semantics are reproduced exactly (stage 4).**
  - **What was replayed:** FTMO's worked example (S1), through `build_drawdown_series` with the builder's draft rule (`daily`, `reset` Europe/Prague 00:00, `reset_basis: balance`, `limit_of: initial`, 5%), plus `static`/equity/`limit_of: initial` at 10%.
  - **What FTMO says:** the limit is "the account balance recorded at 00:00 CE(S)T of the current day and the Maximum Daily Loss Amount, which is 5% of the Initial Simulated Capital". Its example gives Day 1 $95,000; Day 2 "$102,000 … Limit for Day 2 = $97,000"; Day 3 "$101,000 … Limit for Day 3 = $96,000".
  - **What the engine returned:** measured 5.00% on the daily rule at exactly 95,000, 97,000 and 96,000 on days 1–3, and 10.00% on the static rule at 90,000. FTMO's max loss is "the Initial Simulated Capital and the Maximum Loss Amount, which is 10%", measured on equity.
  - **Strictness:** the engine halts at equality, while FTMO breaches only below the line. That is stricter, as allowed.
- **N2. The Europe/Prague zone and the EU DST rule are correct.**
  - **Method:** compared against `zoneinfo`, every 15 minutes over 2025–2027.
  - **Where they disagree:** only on the six DST-switch weekends (Saturday 22:00/23:00 UTC to Sunday 22:00/23:00 UTC).
  - **Why it is harmless:** the disagreement changes only which identity string names the Sunday. Every day-key CHANGE still happens while the FX market is closed, so no anchor moves in open-market time.
  - **Wording:** the docstring's "an hour off at 00:00 on the switch Sundays" understates the window (it is the whole Sunday), but the conclusion holds.
- **N3. The rolling 24-hour budget is at least as strict as any calendar-day cap.** Any calendar day is a 24-hour window, so the claim "stricter than a firm's 'per day' cap whatever its day boundary" is sound for opens.
- **N4. Round-DOWN-only lot quantisation matches venue practice.**
  - `venue_quantity` never returns more than it was given, and refuses whatever falls below `min_lot`.
  - cTrader volumes are "represented in 0.01 of a unit" (S5); the conversion is the adapter's job.
  - Latent, not a finding: `UNITS_PER_LOT = 100000` is FX-only. It would mis-size metals and indices, but XAU is `enabled: false`, and the failure mode refuses the order (fail-closed).
- **N5. Retrying on a lost response is designed for.** The ACIS-13 draft (C-VEN-1, §7.3 step 6) searches the venue by `clientOrderId` before any resend, and assumes cTrader does not deduplicate it (OQ-14). The branch's retry path does not repeat the reduce-only check on attempt 2; it relies on that face idempotency (C-EXE-4/5). This is recorded, not raised.
- **N6. The E8 draft agrees with the only evidence reachable,** third-party, S11: "The daily drawdown is measured against the balance you start the day with … at midnight server time (5 PM Eastern …)", and "Equity and balance both count against the floor". The builder's two-rules-per-basis E8 draft matches that. It is **unconfirmed** against E8's own help centre, which returns 403.
- **N7. Already known, so not raised again.** FTMO's clause on "hedging or holding opposing positions on the same or highly correlated instruments" (S2) versus pair trading is already covered in `archive/RESEARCH_PROP_VENUES_2026-09-24.md`.
- **N8. A stale persisted anchor never reads lower than main.**
  - At worst, persistence lags by the one evaluate in flight: the snapshot and the restrictive state commit after `check`.
  - Main re-anchored from scratch at restart, so the branch is never looser here.
  - This excludes X4's power-loss durability gap.
- **N9. The lead's first claim re-verified.** `git diff --stat bdd3a75..d8361a7` touches none of these:
  - `config/guardrail_limits.yaml`;
  - `config/platform_rules.yaml`;
  - `specs/`, `ACIS_SPEC.md`, `KNOWN_GAPS.md`.

  The FTMO and E8 rulebooks are drafts in the report, not commits.

## Do the design choices hold against the outside world?

| Choice | Verdict |
|---|---|
| Daily-reset rule type, `initial_capital` and the Prague clock | **Hold** for FTMO 2-Step (N1, N2) |
| Rolling request budget | **Holds** for opens; the close exemption needs a ceiling (X6) |
| Round-down lot rounding | **Holds** (N4) |
| Weekly-only pre-close ban and flatten | **Do not hold** against FTMO's actual trigger, any closure of 2 h or more including holidays (X5) |
| Reduce-only closes | **Do not hold** as an engine-side check-then-act. Real venues provide atomic close semantics, and without them a venue-initiated stop or a concurrent close turns a "close" into an unprotected opposite position (X3) |
| Halt persistence | **Direction right; two defects.** Durability under power loss is short of SQLite's own guidance (X4); the latch-before-persist ordering can lose the equity breaker (X2); and restoring stale session rows makes the daily-loss halt one-shot per human resume, looser than main (X1) |
