# AUDIT BRIEF — R1.6: the target-position path that trades the demo from the cutover (pinned 2026-10-02)

> **Pinned before launch (constitution A4).** The owner's go, in chat on 2026-10-02, answering the
> session's standalone ask: "Launch both now (Recommended)". This is the constitution's pair (A3),
> one agent per lens, on Opus 5 in fresh context.
>
> **What is under audit:** the code at commit **`de96a75`** on `main` (the commit that pins this brief
> adds only documents). Read it with `git show de96a75:<path>`; the lead may keep working in the tree.
> R1.6 was built in commits `bb9cda0`, `92e49ee` (steps 1–2), `aa73ea0` (step 3), `e8d1ea4` (step 4) and
> `de96a75` (the owner's three rulings, master v2.28).
> - **The forecast and sizing:** `core/signals/forecast.py` (the `Forecast`, the excess-return price,
>   `d1_forecast`), `core/signals/rules.py` + `core/signals/ewm.py` (Carver's D1, read-only context),
>   `core/governor/target.py` (`banded_target`, the one lot rule, the practice cap), `core/data/rates.py`.
> - **The daily history:** `core/data/ctrader/history.py` (H1 trendbars), `core/data/ctrader/schema.py`
>   and `pacing.py` (the new payload types), `core/signals/daily.py` (decision days, closes, staleness,
>   daily bars, slots), `core/runtime/history_store.py`.
> - **The decision and the orders:** `core/runtime/target_decision.py`, `core/runtime/target_loop.py`,
>   `core/runtime/target_wiring.py`, `core/governor/target_gate.py`, `core/governor/guards.py` (the entry
>   guards extracted from `capital_governor.py`), the fast-loop changes in `core/runtime/engine.py` and
>   `core/runtime/wiring.py` (R6-3), the A9 term in `core/execution/ctrader_attach.py` and
>   `core/runtime/attach_venue.py`.
> - **Config and deploy:** `config/targets_schema.py`, `config/rulebook.py` (`vol_target_annual`),
>   `config/instruments.yaml` (13 FX enabled), `config/system_config.yaml` (`targets:`, symbol names,
>   reconcile 1,800 s), `config/platform_rules.yaml` (`pepperstone_demo`), `scripts/download_macro.py`
>   (`--live`), `deploy/systemd/acis-macro.{service,timer}`, `deploy/aws/acis-demo-prepare.sh`.
> - **The tests:** `tests/unit/test_forecast.py`, `test_target_sizing.py`, `test_target_path.py`,
>   `test_daily_series.py`, `test_download_macro_live.py`; `tests/integration/test_ctrader_history.py`,
>   `test_target_loop.py`, `test_target_runtime.py`; the fixture change in `tests/conftest.py` and
>   `tests/legacy_universe.py` (behaviour tests now run on the shipped config narrowed to EUR_USD/USD_JPY;
>   ATTACK whether that hides anything the shipped config breaks); `tests/ctrader_fixtures.py`.
>
> **The authority.**
> - The spec: master `ACIS_SPEC.md` v2.28 — §5 (D-a "validated" per mode; §5.5 forecast netting, the
>   band; §5.6 the TREND family), §2 (the conflict table: ambiguity = no trade, breach = size zero), §6
>   (hard limits), §8.6 (stops); `specs/ACIS-04-ALPHA_ARENA.md` v1.6 §4b; `specs/ACIS-05-CAPITAL_GOVERNOR.md`
>   v1.8 §6.4 and §7; `specs/ACIS-03-QIEA_OPTIMIZER.md` v2.2 (flatten-then-promote);
>   `specs/ACIS-13-VENUE_ADAPTERS.md` v1.4 §6.5; `specs/ACIS-09-BACKTEST_VALIDATION.md` (B0(d), C-BT-11 v2).
> - The research simulator RSIM is the graded book the engine must equal: `tests/backtest/rsim.py`,
>   `rsim_real.py`, `rsim_lab.py`.
> - The ledger: `KNOWN_GAPS.md` GAP-P12D-141 (declared departures), 142 (caps; ruled), 143 (budget; fixed),
>   118, 106, 108, 61, 101, 27, 140.
>
> **The lead's claims — re-verify them; they are not settled:**
> - the full suite at `e8d1ea4` gives 1330 passed, 6 skipped on the server (the rulings commit `de96a75`
>   changes config values and three tests);
> - B0(d): the engine's 17:00 decisions equal RSIM's practice book at every decision of a 620-day lab tape
>   (`test_b0d_the_engines_decisions_equal_rsims_practice_book_on_a_lab_tape`);
> - the engine's daily series (decision days, closes, staleness) equals RSIM's on the same hours;
> - a reduction is never blocked; an increase meets every entry guard and hard limit and carries a
>   10 × daily-ATR broker stop; no target-path position exceeds one venue minimum lot in paper/practice;
> - no slot runs before its decision, a missed slot is never caught up, a stopped position is not
>   re-entered before the next decision, and a restart re-derives the same target;
> - nothing after 17:00 New York moves a decision (no look-ahead);
> - the legacy modules emit nothing and the legacy max-hold closes nothing on the target universe;
> - the request budget fits at 894 of 900 with 21 instruments; history can never spend the close reserve;
> - no module under audit is over 300 lines; `python scripts/ledger_check.py` is green.
>
> **Declared choices the lead made — attack them:**
> - the history is the venue's BID trendbars where RSIM grades Dukascopy MID closes (GAP-P12D-141 (1));
> - ~3 years of history where RSIM starts in 2012, so Carver's slow vol differs (GAP-P12D-141 (3));
> - sizing reads the quote's USD rate at the decision, RSIM's at the fill (GAP-P12D-141 (4));
> - a closed-market slot is skipped where RSIM fills at the next traded slot (GAP-P12D-141 (5));
> - adding to a held position on the same side is refused (`add_unsupported`), not built;
> - an entry with no regime classified yet is refused (`no_regime`); NVMA's no-params veto reads the family's
>   provenance registration in paper/practice;
> - the slot's entries run in instrument (alphabetical) order; with the $100k demo account (owner ruling,
>   GAP-P12D-142) the caps should rarely bind — check that they cannot bias the book;
> - a first activation over held positions, or a staged family-version, flattens the universe and promotes
>   only when flat; promotion is checked once a day at the 17:00 decision;
> - `targets.idm: 1.5` is a declared prior, not an estimate (GAP-P12D-141 (7));
> - the target-path's positions are labelled `StrategyType.TREND` with the family id as `param_set_id`;
> - the 11 newly enabled FX pairs' contracts are Pepperstone's standard, checked only at attach.

## Rules for both auditors
- **Fresh context, Opus, finder not clearer (A5).** State this in your report. Launch NO subagents or agents of any kind.
- **The repo is read-only for you** except your ONE report file (below). Do not edit, stage, commit, or run git commands that write. Read the audited state with `git show de96a75:<path>`; never trust the working tree to equal it.
- **The owner's directive: NO slow runs on the laptop.** Never run the full suite or any probe that does real work locally.
  - Every run goes to the Google compute server through the helper, which uses YOUR OWN checkout of the audited commit: `bash "C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/0d6d5d35-83d8-4fa2-80c8-bd4dd3a377ce/scratchpad/remote_audit_r16.sh" <internal|external> "<command>"`.
  - Put probe scripts in `…/scratchpad/audit_r16/<internal|external>/probes/` (they ship on each call) and run them as `python probes/x.py`.
  - The venv has numpy, pytest and pytest-xdist; use `-n 8` at most, because the other auditor shares the machine.
  - Reading files and quick `grep`s locally are fine.
- **Refutation (A6).** Every finding is reproduced by a script on the server and cites `file:line` at `de96a75` (internal lens), or quotes its external source with a dated URL (external lens). An unreproduced claim is recorded as *unconfirmed*. Honest negatives are first-class results.
- **Defects only (A4).** The bar is correctness, requirement gaps against the spec, hollow or weakened tests (A16), A12 size and legibility (a module over 300 lines; a missing one-screen mental model in an invariant-bearing module), A13 hygiene (a read-path claim the code or the ledger contradicts; spent scaffolding), and ledger closure (`python scripts/ledger_check.py` green, plus a spot-check that each `Residual:` just written honestly owns what is unbuilt). Taste and wording are out.
- **The deliverable.** INTERNAL writes `archive/AUDIT_R1_6_INTERNAL_2026-10-02.md`; EXTERNAL writes `archive/AUDIT_R1_6_EXTERNAL_2026-10-02.md`. That file is your ONLY repo write. Its shape: an executive summary; findings (ID, Severity/Likelihood, reproduction, proposed fix); honest negatives; what you could not verify; residual risk. The lead triages it into the ledger.

## Attack surfaces (both lenses; weight them by your lens)
1. **Money reach and size.** Can the target path send more than one minimum lot per instrument in paper/practice, add to a position, open through flat on a flip, or trade in live mode? Can a mode change between decision and slot change the cap? Does `lots_of` read the mode at the right time?
2. **Protection.** Does every target-path open carry its 10 × ATR stop to the venue (NaN ATR, a stop on the wrong side, a stop at or below zero, the relative-stop arithmetic downstream)? Is the ATR the daily true-range ATR on daily bars the definition assumes?
3. **Guards and limits.** Can any entry bypass a §7.1 guard (halt, session drawdown halt, veto, staleness, blackout, weekend ban) or a §7.4 limit (lot cap, taper, alpha decay, cluster and currency caps with G-5 headroom)? Is a reduction ever blocked? Did the guard extraction (`guards.py`) change the signal path's behaviour in any case?
4. **Parity with the graded book (B0(d)).** Decision days, closes, staleness, the excess-return price and its carry calendar, warm-up, the band, the one lot rule, the cap: same as RSIM? Is the B0(d) test strong enough to catch a real divergence (A16)? What does RSIM model that the engine does not, beyond GAP-P12D-141's list?
5. **Look-ahead and determinism.** Can any bar, rate or tick after 17:00 New York reach a decision? Is a restart's re-derivation actually identical? Does the rate refresh break it beyond GAP-P12D-141 (8)?
6. **Clocks.** DST at 17:00 New York and at each slot's local hour (New York, London, Frankfurt, Tokyo, Sydney); Friday's decision to Monday's slot; holidays (a decision day by RSIM's rule); the settle delay; the loop's sleep and wake arithmetic around DST transitions and long sleeps.
7. **The venue history.** The trendbar decode (prices, `utcTimestampInMinutes`, the hour floor), the backward walk (termination, `hasMore`, a refused range), the cache's idempotence, the budget class and pacing, a failed fetch mid-history, a gap in the cache.
8. **Concurrency and failure.** The slow loop beside the fast loop and the executor: busy instruments, an order in flight across the slot, a reconnect between decision and slot, an exception in the loop (a stalled-loop flatten), the promotion's flatten while the executor is busy.
9. **One path per instrument (R6-3).** Can a legacy signal, the legacy max-hold, a pair-group exit or the weekend flatten interfere with a target position? What happens to positions left by the old QIEA champion at the first boot?
10. **The test-fixture change.** `acis_config` now narrows the shipped config to two pairs: does any test now pass only because of that narrowing while the shipped 13-pair config would fail it? Is anything that should test the shipped config testing the narrowed one?
11. **Deploy.** The rates timer and `download_macro.py --live` (freshness, the SNB TLS path on Linux, a partial failure leaving mixed files), the prepare script, the rulebook hash change at practice entry.

## Lens-specific
- **INTERNAL (no web):** spec against code, and code against itself. Construct the failing input. Prioritise surfaces 1, 2, 3, 5, 6, 8 and 10.
- **EXTERNAL (WebSearch capped at 20 calls, then WebFetch only):** the design and the implementation against the outside world.
  - Carver: pysystemtrade at `a62269d27707806ba61f516791b71a9cd14cf268` (`systems/positionsizing.py`, `systems/portfolio.py`, buffering with `buffer_method: forecast`, `buffer_trade_to_edge`; `sysquant/estimators/vol.py`); *Systematic Trading* (2015) and *Leveraged Trading* (2019) on the average position, the IDM and its cap, and the minimum-lot problem for small accounts. Is the engine's sizing Carver's, faithfully, and is every departure declared?
  - Spotware's cTrader Open API: `ProtoOAGetTrendbarsReq`/`Res` (the proto at commit `3fd8bddfbe0cfc2ecfda079623dc4e498af11e66`, help.ctrader.com/open-api, the forum): bid or mid bars, `utcTimestampInMinutes` semantics, the per-period range limit and the 14,000-bar cap, `hasMore`, the historical rate limit.
  - The excess-return price for spot FX: tom-next rollover conventions (the Wednesday triple), which overnight rate proxies each currency, whether RSIM's carry calendar matches the market's.
  - The ATR's definition (Wilder 1978) on daily bars, and disaster stops in trend-following practice.
  - Pepperstone's cTrader demo: the 13 FX symbols' contract (lot size, minimum, step, digits), the schedule and holidays, demo account balances.
  - Does anything the spec or code assumes about the venue, the rates or the literature contradict the world? A spec that is wrong about the world is a finding.
