> **Saved by the lead, verbatim.** The internal auditor's write to this path was refused by the harness ("Subagents should
> return findings as text, not write report files"), so the auditor returned the full report as its hand-back text on
> 2026-10-03, and the lead saved it here unchanged below this note.

# AUDIT (INTERNAL lens): pre-cutover, `f0d9524..9f57a6f`, 2026-10-03

**The report file was NOT written.** The harness refused my one sanctioned write to `archive/AUDIT_PRECUTOVER_INTERNAL_2026-10-03.md` ("Subagents should return findings as text, not write report files"). I did not work around the refusal. The full report is below; please save it to that path.

**Attestation.** I ran as **Claude Opus 5.5** (`claude-opus-5-5[1m]`) in a **fresh context**, launched on the owner's explicit go ("Launch both now (Recommended)").
- I am a **finder, not a clearer**. Nothing here grants ✅.
- I read the pinned brief (`git show 35fd443:archive/AUDIT_BRIEF_PRECUTOVER_2026-10-03.md`) in full before starting.
- The audited state came only from `git archive 9f57a6f`, extracted into my scratchpad.
- Every run went through `remote_audit_pc.sh internal` in my own server checkout. I made no git writes, launched no subagents, and edited nothing in the repo.

**Look discipline.** I computed no return-dependent statistic on real data outside the register. On real data I did only three things:
- decoded 8 local USD_JPY tick files P&L-blind (timestamps, and prices at given wall times);
- counted calendar days;
- re-computed the *recorded* statistics of looks 000001–000020 from their stored vectors.

Every defect below is shown on synthetic data or by `file:line` at `9f57a6f`.

## Executive summary

- **Cutover blockers: none found.** By code reading, P&L-blind checks and synthetic probes, the Tier-1 code (feed watch, report-only alpha decay, shadow book, host rates) is wired and behaves as the brief claims.
- **One cheap fix before the cutover is recommended (PC-I-01).** The feed watch is now the target path's only data check, and no test proves it is connected. Three mutants that disconnect it pass the whole suite: **1428 passed, 6 skipped**.
- **Counts:** 3 medium (PC-I-01, PC-I-06, PC-I-08), 9 low, 0 high or critical.
- **Not completed:**
  - The 24-mutant batch (A1–A24) was **killed by the local Claude Code harness for low laptop memory** while it ran over ssh. It left no output and I did not restart it, as the harness notice instructs.
  - The findings that lean on it are supported by greps instead, and each says so.

## Findings, by tier

### PC-I-01: the feed watch (the target path's only data check) is never tested as wired
**Medium · likelihood medium · Tier 1 · fix before the cutover (cheap)**

Since master v2.33 the wiring is three links:
- `core/runtime/engine.py:71` (`self.feed.observe(st)`);
- `core/runtime/target_wiring.py:62` (`feed_refusal=runtime.feed.refusal`);
- `core/runtime/target_loop.py:220` (`entry_refusal=e.feed_refusal(instrument, now)`).

No test pins any of them:
- The loop Rig sets `self.feed_refusal = None` (`tests/integration/test_target_loop.py:74`) and never sets it to a refusal.
- `_assert_the_target_wiring` (`test_target_runtime.py:115-126`) checks the clock, rates and portfolio wiring, not the feed.

**Reproduced** with `probes/mut.py`:
- `target_loop.py:220` changed to `entry_refusal=None`: SURVIVED the full suite (1428 passed, 6 skipped).
- `target_wiring.py:62` changed to `feed_refusal=lambda i, now: None`: SURVIVED the full suite (1428 passed, 6 skipped).
- `engine.py:71` replaced by `pass`: SURVIVED `tests/unit` plus `tests/integration` (977 passed). The backtest tests do not touch the runtime. This mutant would silently stop every demo entry (`no_feed` forever).

The 10 mutation-killing checks in `tests/unit/test_feed_check.py` and `test_target_path.py` exercise `FeedWatch` and `target_orders` in isolation only.

**Proposed fix:**
- In `_assert_the_target_wiring`, assert `t.engine.feed_refusal == rt.feed.refusal`.
- Add a loop test with `rig.feed_refusal = "stale_feed"` on a flip: the close is sent, the open is not, and the reason is logged.
- Add a runtime test where one tick turns `rt.feed.refusal(i, now)` from `no_feed` into `feed_warming`.

### PC-I-02: the feed watch's spread yardstick follows a slow widening, ignores the normaliser's implausible-spread flag, and fails on a zero median
**Low · likelihood medium · Tier 1**

`feed_check.py:46-47` refuses only when `spread > 3 × median(last 600 spreads)`. This is exactly the window-median design that GAP-0028 removed from NVMA, because "a window-median centre would self-track a widening spread" (ACIS-02 §4).

The normaliser still sets `implausible_spread` when a spread exceeds `max_plausible_spread` (`core/data/normaliser.py:226-228`). Since v2.33 nothing on the target path reads that flag.

**Reproduced** with `probes/feed_spread.py`:
- **(a)** A 1-pip EUR_USD feed widens to 10 pips over 600 ticks. A 10-pip quote, twice the declared 0.0005 ceiling and flagged implausible, gets refusal `None`.
- **(b)** On a feed quoting a 0.0 spread on 60% of ticks, the median is 0, so every positive spread (0.1 pip) is refused `wide_spread`. This is plausible on raw-spread venues, but unconfirmed for the demo account.
- **(c)** Control: a sudden 4x jump is refused, as intended.

The code matches the v2.33 text literally. The defect is in the yardstick the spec chose.

**Proposed fix:** an absolute ceiling (refuse when the tick carries `implausible_spread`, or when `spread > max_plausible_spread`), and a floor on the median (for example one price tick).

### PC-I-03: the shadow book is not the "forward twin of the book RSIM grades"
**Low · likelihood high · Tier 1, the forward record**

- `scripts/demo_report.py:9-13,66-67` marks the shadow position from one 17:00 decision close to the next.
- RSIM books each window from fill to fill (`tests/backtest/rsim.py:29`, "Window t runs from fill t-1 to fill t"), and so does the engine, at the 08:00 New York slot.
- So the shadow book earns the ~15 hours between the close and the slot, which neither real book can capture.

**Reproduced** with `probes/shadow_timing.py`. A long that rises from each 08:00 fill to the 17:00 close and gives it back overnight books +10, +10, +10 in the shadow book against 0, 0, 0 in RSIM's arithmetic. A second path gives 0 against +5, −5, +5.

Also, `demo_report.py:58` drops every `boot=True` decision. If the engine was down at 17:00 and decided that day at boot, the day vanishes and the next mark spans two days at a stale size.

**Proposed fix:** either log the slot's mark and mark the shadow fill to fill, or declare the close-to-close convention and stop calling it RSIM's twin. Keep the first decision of each day whatever its `boot` flag.

### PC-I-04: the spec still routes Tier-G shocks and the "spread-explosion / tick-velocity" defence through NVMA, which target entries no longer read (unowned)
**Low · likelihood low (inert today) · Tier 1 / spec**

The master still says:
- §3.6 (`ACIS_SPEC.md:131`): "A Tier-G match sets a shock flag consumed by NVMA (§4) exactly like `macro_events_imminent`".
- §8.5 (`:361`): "spread-explosion and tick-velocity anomalies already veto via NVMA (§4)".

In the code, Tier-G reaches only `nvma.py:268`. The feed watch reads only `macro_events_imminent`.

v2.33 amended §2, §4 and §6 but not §3.6 or §8.5. When the news layer is wired (today `wiring.py:186` passes `tierg_shock=lambda…: False` and `:168` passes `macro_imminent=False`), a single-source Tier-G shock will no longer block a target entry. §3.6's rule that "a headline can only ever make ACIS more conservative" will not reach the money path.

No ledger entry owns this: GAP-P12D-03, 152 and 153 do not mention Tier-G.

**Proposed fix:** an owner ruling before the calendar or news wiring (GAP-P12D-03), plus a ledger owner now.

### PC-I-05: two modules' mental models say only opens are in flight; the code now counts closes
**Low · certain · Tier 1 hygiene, invariant density (b)**

- `core/runtime/portfolio.py:15-16` says "Opens IN FLIGHT … count in every exposure".
- `core/runtime/executor.py:4-6` says "Its opens are IN FLIGHT".
- Since PR16I-04 the code counts closes too (`executor.py:61`, `portfolio.py:43-46`).

There is also an undeclared consequence. A close read as filled that the venue then rejects lets a later entry in the same slot be judged against exposure that never materialised. The likelihood is unconfirmed. No mutant result is available (A6 and A7 were lost).

**Proposed fix:** correct both docstrings, and declare the rejected-close case in GAP-P12D-150's PR16I-04 line.

### PC-I-06: `anchored()` checks only the last anchored head, so a tail rollback-and-rewrite re-anchors cleanly
**Medium · likelihood low (needs deliberate tampering) · Tier 2**

`tests/backtest/look_anchor.py:69-72` compares only `lines[-1]` with the register's current head.

**Reproduced** with `probes/anchor_rewrite.py` (temporary repo and bare remote, audited code):
1. Three lines are written and anchored; `anchored` is True.
2. Line 3 is deleted; `broken` is empty and `anchored` is False.
3. A different line 3 is appended and anchored; `anchored` is True again.

The pushed `LOOK_ANCHOR.txt` then holds two `000003` entries with different heads. That is forensic evidence, but no code reads it, and `begin_grade` (`look_gate.py:50`) passes.

GAP-P12D-86's purpose ("tail deletion is undetectable without an outside anchor") is therefore met only for a human who inspects the branch.

**Proposed fix:** `anchored()` must check that the anchor file's sequence numbers run strictly 1..N and that every `(seq, head)` equals the register's chain head after line `seq` (prefix heads, computed in `scan`).

### PC-I-07: "an event look is kill-only" is enforced by a helper, not by the register or the grade gate
**Low · likelihood low · Tier 2/3**

The rule lives only in `register_event_look` (`evaluate_events.py:67`). It is not in `LookRegister.register` (`look_register.py:211`) or in `begin_grade` (`look_gate.py:19-56`).

**Reproduced** with `probes/event_bypass.py` (temporary canonical register; git and the anchor stubbed as the repo's own fixtures stub them):
- A tier-2, human-origin event look (boundary None, so never kill-only) is refused by the helper.
- The same look is admitted by `register.register` and graded by `grade_event_look`. Its outcome is chained at HAC t 5.45, and `kill_verdict` judges it.

No false pass is possible, because the verdict counts only looks that name a cycle (`verdict.py:83`, `look_cycles.py:37`). It does contradict the register's own law: "complete by construction, not by caller diligence".

The same pattern applies to costs. The book's `CostModel`s are supplied by the caller; `begin_grade` checks only stress and floor (`_stress`) and the config hash, never that they equal the claim's `cost_map_hash`. This was already true of RSIM's `evaluate()`.

**Proposed fix:** check kill-only in `begin_grade` when `simulator == "event"`, and build the cost models inside the grader from `cfg`.

### PC-I-08: GOTOBI's control cannot separate a gotobi effect from a weekday effect
**Medium · likelihood unconfirmed · Tier 3, decision-relevant**

P&L-blind count (`local/weekday_mix.py`, using the script's own `days_of`):
- the 740 traded days are **49% Fridays** (365), because weekend gotobi days move to Friday;
- the 1,638 control days are **14% Fridays**;
- overlap is 0, which confirms the brief's claim.

**Synthetic counter-example** (`probes/gotobi_friday.py`: GOTOBI's own day sets, price reader and book, no costs). A market with **no gotobi effect at all**, only a +6 bp Friday drift between 03:00 and 09:55 JST, gives:
- gotobi Sharpe **+0.81 (HAC t 2.78)**;
- control **−0.00**.

For contrast, the null gives −0.35 / −0.51, and a gotobi-only drift gives +1.96 (t 6.75) / −0.51.

So the recorded control (−0.07 / +0.08) cannot carry the claim that the edge is gotobi-specific, and the live draft (G-1..G-6) leans on that claim. The kill verdict itself is unaffected. I did not and cannot measure the split on real data without an unregistered look.

**Proposed fix:** before the live build, register a weekday-stratified control (gotobi Fridays against non-gotobi Fridays, Tue–Thu likewise) as a kill-only look.

### PC-I-09: the kill-test scripts hold look-defining logic that no test touches
**Low · likelihood medium · Tier 3, A16**

`grep` over `tests/` finds no reference to any of `r1_gotobi_kill_test.py`, `r1_rebal_kill_test.py`, `r1_imom_kill_test.py`, `r1_d3_kill_test.py` or `r1_d1_kill_test.py` (only `demo_report` is referenced). Untested logic that decides the graded numbers includes:
- `days_of`, which builds the control (`r1_gotobi_kill_test.py:73-81`);
- `WEEKDAYS` (`:49`);
- the version-to-book mapping (`r1_rebal_kill_test.py`: `note = sig["rb"] if family.endswith("spread")`).

The mutants A16, A17 and A18 that would have shown this were in the killed batch. This finding is therefore supported by grep, not by mutant survival.

I checked the current behaviour P&L-blind:
- 740 days, reproduced independently by `local/cal.py`;
- 0 control overlap;
- the late-binding lambdas in all three scripts bind their loop variables correctly.

**Proposed fix:** unit tests for `days_of` and for each script's version table.

### PC-I-10: the "quoted price" rule differs across the event books
**Low · likelihood low · Tier 3**

- `event_daily.py:35` (REBAL) counts an hour if its mid moved.
- `event_intraday.py:54` (IMOM) counts a minute only if its **bid** moved, or if either side traded.
- `event_sim.py:74` (D3) counts traded hours only; it was graded before the GAP-P12D-156 ruling.

The ledger calls this outcome-neutral, but one ruling should mean one rule. A minute where only the ask moves is a price for REBAL and not for IMOM.

**Proposed fix:** one shared `quoted()` predicate, applied to all three.

### PC-I-11: read-path claims contradicted by the code or the ledger
**Low · certain · A13 hygiene**

- `STATUS.md:38` says "`passed` gated at a Deflated Sharpe ≥ 0.95". The code makes the Deflated Sharpe informational: `report.py:47` (`DSR_MIN … now an informational column`) and the `passed` clause at `:133-141`.
- `STATUS.md:37` says ACIS-09 v1.11; it is v1.12.
- STATUS says "Full suite 1416"; TODO's START HERE says 1420; the measured count is 1428.
- STATUS's "Next" item 3 still lists GAP-0091b/0099/0075, which STATUS's own 2026-09-30 block says are fixed.
- TODO's START HERE data bullet says the register holds 000001–000010 with the anchor at 000010. It holds 20 lines, anchored at 000020.
- The CLAUDE.md status narrative repeats the DSR-gate claim.

**Proposed fix:** a hygiene pass on STATUS and TODO, and a dated note on the CLAUDE.md line.

### PC-I-12: no test pins the owner-ruled 28-day weekly rate limit, and both weekly tests hard-code 21
**Low · likelihood low · tests**

- `tests/unit/test_target_path.py:232` (`…stays_fresh_for_21_days…`) and `test_download_macro_live.py:36` (`stale_days(sid, 10, 21)`) both use 21.
- No test reads `rate_max_stale_days_weekly: 28` from the shipped config.
- The main-level wiring is untested too: the test re-implements `main`'s rule rather than calling `main`.

My probe shows the live code applies 28 correctly (see the negatives). Mutant A19 (config back to 21) was lost with the batch.

**Proposed fix:** assert the shipped value, rename the two tests, and drive `main()` with a stubbed `fetch`, as `probes/macro_live.py` does.

## Honest negatives (attacked, found sound)

**Signal path unchanged.** `guards.check(target=False)` is boolean-equivalent to f0d9524 at `guards.py:53`, `65` and `67`. `capital_governor.py` has no diff and its only call site (`:352`) passes no `target`.

**Exits are never refused by the feed watch.**
- Reductions, flats and flip closes return before `_entry_size` (`target_gate.py:71-81`).
- `test_a_refused_entry_still_sends_its_exit` covers this.
- Flattens never pass through the target loop.

**HALT and the other guards still bind target entries.** Halt, the drawdown halt, a stale portfolio, the blackout and the closure buffer all apply through `guards.check(target=True)`. Any of them zeroes the entry. Only the *logged* reason order differs (the feed refusal is logged before the halt), the same veto-before-halt order as the signal path.

**Alpha decay is report-only on the demo.** Only the ×0.25 is skipped when `lots.cap` is set (`target_gate.py:108-110`, `target_loop.py:221`). Arming, persistence of the arming baseline, restart restore and the human-only clear are unchanged. `test_only_the_human_resume_reaches_the_throttles_clear` pins the single call path.

**The shadow book never feeds an order.** `Decision.shadow` is used only in the log at `target_loop.py:183`.

**Host rates.**
- `download_macro.py --live` reaches its fetch loop from a clean checkout. With every fetch stubbed to fail it returns 1 and writes no files.
- It applies the engine's 28-day weekly limit: a BIS file 20 or 27 days old is saved, 29 days old is rejected (`probes/macro_live.py`).
- A missing file makes only its own currency stale.
- I could not exercise the systemd sandbox (`ProtectSystem=strict`).

**Register integrity.**
- The chain holds 20 lines, 0 broken, 0 torn.
- Every recorded outcome number reproduces exactly from the stored vectors (`local/register_check.py`).
- Every number in the 7 `r1_kill_test/*.json` files reproduces: 0 mismatches (`local/json_check.py`).
- The anchor branch carries 000001–000020; the last head is `e5ed71d0…`, equal to the register head.
- Every graded marker is later than its head's anchor.
- Both lines of each pair were registered before either was graded: 000007/8, 000011/12, 000015/16. v1c (000019) is a later single line, as declared.
- `begin_grade`'s refusal of an unanchored head is tested (`test_a_real_data_grade_refuses_an_unanchored_head`).

**GOTOBI.**
- The tick files are UTC days: the Sunday open is at 21:00 UTC under US daylight time and 22:00 UTC otherwise, switching on 2019-03-10 and 2019-11-03 (`local/utcday.py`).
- `window_prices` matches an independent scan of the scalar decoder at 03:00, 09:00 and 09:55 JST on two real days, to the tick (`local/price_check.py`).
- The 09:00 JST lookup (00:00 UTC) reads the previous UTC day's file correctly, and that case is tested.
- `jp_days` agrees with `exchange_days` XTKS on every in-scope day 2012–2023 except 2020-10-01.
- The count of 740 days reproduces independently; the control has 0 overlap; Mondays are excluded (114).
- The sign is right; both sides pay C8.
- Booking on the next 17:00 mark is a consistent one-mark shift with a single P&L per mark, so it cannot change the Sharpe or the HAC t.

**HAC.** On a synthetic sparse series shaped like GOTOBI's (`probes/hac_sparse.py`; 3,108 marks, 740 trades, mean 5.3 bp, sd 22 bp), the Newey–West t is stable across lags: 6.78 / 6.68 / 6.53 / 7.44 / 7.28 at lags 0 / 8 / 30 / 100 / 300. The recorded t is also consistent with the Sharpe (1.81/√252·√3108 ≈ 6.4). The kill rule at t < −0.5 kills only 34.5% of zero-edge families and 0% at half GOTOBI's edge. As designed, survival is weak evidence.

**Module budget and gates.**
- Every new module is under 300 lines and each opens with a mental model.
- The lead's claim that "no module under audit is over 300 lines" is literally false: `core/risk/monitor.py` is 332 and changed in `48663d3`. It is grandfathered and its size is unchanged, and the ratchet is green.
- `ledger_check`: 296 entries, 0 violations.
- code-shape: no new violations against the baseline.
- constitution-drift: red only on the v0.9→v0.10 pin (GAP-C10-01).

## What I could not verify

- **The 24-mutant batch (A1–A24):** killed by the local harness for low memory, not restarted. It covered alpha-decay persistence, the in-flight close sign, the downloader's due date, the simulator check, the second-outcome refusal, the certifying-boundary filter, the script mutants, the quoted-price rules and the feed watch's defaults and age limit.
- **`governance_gate.py`:** node is missing on the server; I ran its checks locally on the extracted tree instead.
- **Venue facts:** the demo venue's real spread distribution (PC-I-02 b) and cTrader's quote cadence.
- **The systemd sandbox** for `acis-macro.service`.
- **Real-data sensitivity:** GOTOBI's weekday split and HAC lag sensitivity on the real vectors. Look discipline forbids both.
- **The GitHub remote:** I read only the local remote-tracking ref.

## Residual risk

- The demo's money path now rests on one small module (the feed watch) with no wiring test (PC-I-01) and a relative-only spread ceiling (PC-I-02).
- The strongest research result (GOTOBI) has a control confounded by its weekday mix (PC-I-08).
- The register's outside anchor deters tail rewrites only forensically (PC-I-06).

## Evidence locations

All under `C:\Users\USER\AppData\Local\Temp\claude\C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis\5bfd3abc-d062-49c8-82c5-18c2305e8ba8\scratchpad\audit_pc\internal\`:
- server probes in `probes\`: `mut.py`, `mutbatch.py`, `anchor_rewrite.py`, `event_bypass.py`, `feed_spread.py`, `shadow_timing.py`, `gotobi_friday.py`, `hac_sparse.py`, `macro_live.py`;
- local P&L-blind checks in `local\`: `utcday.py`, `cal.py`, `weekday_mix.py`, `price_check.py`, `register_check.py`, `json_check.py`.

The report path the brief names, for the lead to write: `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\archive\AUDIT_PRECUTOVER_INTERNAL_2026-10-03.md`.
