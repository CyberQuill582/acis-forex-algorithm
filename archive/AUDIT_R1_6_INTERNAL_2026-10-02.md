# AUDIT — R1.6 internal-consistency lens (constitution A3, lens 1) — 2026-10-02

- **Audited commit:** `de96a75` (read with `git show de96a75:<path>`; every run on `acis-compute-1` in this lens's own checkout of `de96a75`).
- **Brief:** `AUDIT_BRIEF_R1_6_2026-10-02.md` (pinned before launch, A4).
- **Auditor:** fresh context, Opus 5.5. **A finder, not a clearer (A5):** a finding binds only after the lead's triage survives refutation (A6). This report is not a sign-off, and its honest negatives are not one either.
- **Probes:** `…/scratchpad/audit_r16/internal/probes/` in the lead's session scratchpad (`C:/Users/USER/AppData/Local/Temp/claude/C--Users-USER-Documents-Private-ClaudeInsights-Knowledgevault-acis/0d6d5d35-83d8-4fa2-80c8-bd4dd3a377ce/scratchpad/audit_r16/internal/probes/`). Run each with `remote_audit_r16.sh internal "python probes/<name>.py"` (the `.sh` probes: `bash probes/<name>.sh`).
- **Baseline re-verified on the server:** full suite at `de96a75`: **1330 passed, 6 skipped** (245 s, `-n 4`); `python scripts/ledger_check.py`: **281 entries checked; 0 violations**.

## Executive summary

The target path's sizing, band, lot rule, practice cap, gate and slot clock match their specs decision by decision, and B0(d) is stronger than it looks: it kills 8 of 10 engine-side mutants (see honest negatives). The defects sit in what surrounds the decision: the rate window, the slot's batch admission, the restart path, a disabled clock guard, and tests that are narrower than the claims made for them.

**The most severe findings:**

1. **R16I-01 (High, certain). The target path goes permanently silent about 100 days after its first seeding.** `download_macro.py --live` keeps a rolling 1,200-day rate window. The history cache is seeded with 1,100 days and is never trimmed. `decide()` computes an accrual for every cached day. Once the cache's first day predates the rate file, every instrument returns `no_target:stale_rates`, every day, for good.
   - For a 2026-10-15 first boot this starts on **2027-01-25** (reproduced).
   - Positions are then kept on their disaster stops, and nothing ever trades again.
   - The log reason is the same one a dead rate timer produces, so an operator would chase the wrong cause.
2. **R16I-05 (High while the $10k account is bound; latent after).** Every entry in a slot is checked against the same pre-slot portfolio, so G-5's per-entry cap check never sees the other entries in its own batch.
   - On the $10k demo NAV, the first post-cutover slot admits all 13 one-lot opens.
   - Four clusters then exceed the Risk Monitor's 20% line, which issues a human-only global HALT (reproduced).
   - GAP-P12D-142's description ("each cluster holds about one position … the slot order decides which … its caps truncate the book") describes behaviour the code does not have.
3. **R16I-02 (Medium).** ACIS-13 A8's clock check never runs on the target universe, and target-path entries are never gated on it. `_clock_ok` is only called when legacy signals exist, and those are always empty on the universe. A target open goes out with `_clock_verified` empty (reproduced). A host clock that runs fast by more than `settle_s` makes the 17:00 fetch cache a still-forming bar as if it were complete, permanently.
4. **R16I-03 (Medium).** A restart between a disaster stop-out and the next slot re-derives the decision against the now-flat book and re-enters. This breaks ACIS-05 §6.4 ("not re-entered before the next decision") (reproduced).
5. **R16I-06 (Medium, grows with time).** The 17:00 decision blocks the event loop for **3.4 s** at first boot (13 instruments, 1,100 days, on the 16-vCPU compute server). That becomes 6.7 s at 2,200 days and **11.1 s** at 3,650 days, because the cache is never trimmed. The watchdog flattens at a heartbeat older than 30 s, and the AWS host is a burstable t3.small.

**Test-strength findings (A16).** Inverting the quote→USD conversion that sizes 10 of the 13 shipped pairs (R16I-07) leaves all 1,330 tests green. So does deleting the R6-3 filter that keeps the legacy 48-hour max hold off target positions (R16I-09). The ledger cites a test for the second that does not exercise it.

**The lead's claims, re-checked:**

| Claim | Status |
|---|---|
| Suite count | Holds |
| B0(d) parity | Holds |
| Daily series equals RSIM's | Holds |
| Never more than one lot | Holds today; latent gap R16I-10 |
| No slot before its decision | Holds |
| No catch-up | Holds |
| No same-day re-entry | **Fails across a restart** (R16I-03) |
| A restart re-derives the same target | **Only on an unchanged book and a complete fetch** (R16I-03, R16I-04) |
| No look-ahead from bars | Holds; a fast host clock is the exception (R16I-02) |
| Legacy silent on the universe | Holds in code, untested for the max hold (R16I-09) |
| Budget 894/900 | Holds arithmetically |
| ≤ 300 lines | Holds (capital_governor.py is grandfathered and shrank 434 → 401) |
| Ledger green | Holds |
| "Every entry guard" | **Fails for A8** (R16I-02) **and for batched caps** (R16I-05) |

---

## Findings

### R16I-01 — The live rate window (1,200 days, rolling) is shorter than the never-trimmed history cache: every target stops ~100 days after the first seeding
- **Severity:** High · **Likelihood:** certain (a calendar fact: about 2027-01-25 for a 2026-10-15 first boot).
- **Where (de96a75):**
  - `scripts/download_macro.py:249-251`: `--live` fetches `series(today - timedelta(days=1200), today)`.
  - `deploy/systemd/acis-macro.service` (ExecStart `--live data/macro_live`) and `deploy/aws/acis-demo-prepare.sh:40-44`.
  - `config/system_config.yaml:166` (`history_days: 1100`).
  - `core/runtime/history_store.py:7-8` ("append-mostly and never trimmed").
  - `core/runtime/target_loop.py:132-138`: every cached bar → `decision_days` from the first cached day → `series`.
  - `core/runtime/target_decision.py:98-101`: `accruals = [accrual(...) for d in s.days]`; `StaleRateError` → `no_target:stale_rates`.
  - `core/data/rates.py:60-62`: a day before the series' first row raises `StaleRateError`.
- **Reproduction:** `probes/p01_rate_window.py`. It uses a real `HistoryStore` and the real `TargetLoop`, with rates shaped exactly as `--live` writes them on each day. Output:
  ```
  +  0d 2026-10-15 target           cache_first_bar 2023-10-11  rate_first_row 2023-07-03
  + 99d 2027-01-22 target           cache_first_bar 2023-10-11  rate_first_row 2023-10-10
  +101d 2027-01-25 no_target:stale_rates                         rate_first_row 2023-10-13
  +200d 2027-05-03 no_target:stale_rates                         rate_first_row 2024-01-19
  ```
- **Why it matters:**
  - The demo's forward record stops accruing after about three months.
  - Positions are kept, with only their disaster stops (R6-1: no new target).
  - The reason string is the one a dead macro timer produces.
  - `validate()` in live mode checks only the series' END (`ends_by`), never that it reaches back to the cache's first day (`download_macro.py:250`, `first_by` set to `None` at :251). So a source that silently returns a shorter span would fail the same way, from day one.
- **Proposed fix:**
  - Make `--live` fetch from a fixed early start (the non-live `START`, 2011-01-01; the files are tens of KB).
  - Or, at least, fetch from `history start − margin`, and keep the window ≥ the cache span forever.
  - In `--live`, validate that each series starts on or before the cache's first decision day.
  - Add a postcondition test: a loop seeded 1,100 days and advanced ≥ 400 days with a rolling `--live`-shaped table still decides `target`.
  - Do NOT trim the series to the rate span instead without re-proving B0(d): the EWM initialisation would change.

### R16I-05 — A slot's entries are admitted against one stale portfolio; G-5's headroom is per entry, not per batch, so the batch can cross Risk's human-only HALT line
- **Severity:** High while the bound demo account holds $10k (the owner's $100k step is still outstanding, GAP-P12D-142); Low but latent afterwards.
- **Likelihood:** certain on the first post-cutover slot at $10k NAV. The defect stays in the code at any NAV, and binds again when the universe grows to 21, the cap exceeds one lot, or NAV falls.
- **Where (de96a75):**
  - `core/runtime/target_loop.py:98-99`: every due slot executes synchronously inside one `tick`, so no fill can land in between.
  - `core/runtime/target_loop.py:185-189`: `portfolio=e.portfolio()` per execute.
  - `core/runtime/engine.py:136-150`: the portfolio is built from Risk's FILLED positions only.
  - `core/governor/target_gate.py:112-118`: the cap check runs against that portfolio.
  - `core/governor/exposure.py:8-10, 35-40`: G-5's 90% headroom.
  - `core/risk/guardrails.py:240-243`: a cluster above 20% → `_issue_halt("all", "cluster_cap")`.
- **Reproduction:** `probes/p07_slot_batch_caps.py` (shipped guardrails and clusters; the first decision after the cutover, all flat, 13 one-lot targets):
  ```
  NAV $10000: 13 opens sent at one slot; Risk's cluster HALT line $2000
     european $6018 BREACH   usd_long $3000 BREACH   usd_short $3170 BREACH   yen_carry $5420 BREACH
     zeroed: []
  NAV $100000: 13 opens sent; no cluster above $20000
  ```
- **Also wrong in the ledger (A13):** `KNOWN_GAPS.md:161`, `:163` and `:1357` (GAP-P12D-142, and the GAP-P12D-61 progress line) say that at $10k each cluster "holds about one position", that "the slot order decides which" ("AUD_JPY, AUD_USD and CHF_JPY win the cap systematically"), and that "until then … its caps truncate the book as described". The code admits the whole batch, and the Risk Monitor then halts everything. That makes the "alphabet bias" moot and the consequence worse: a halt that only a human can lift, not a truncated book.
- **Proposed fix:**
  - Accumulate each admitted entry's notional into the cluster and currency maps across the slot's batch. One option is a running `PortfolioState` threaded through `execute`; another is executing entries one at a time and yielding to the executor between them.
  - Or have the executor's open path re-check the caps against Risk plus in-flight work.
  - Add a test: N same-slot entries into one cluster never exceed 90% of the cap.
  - Correct GAP-P12D-142's description. Until the fix ships, the $100k account step is a hard precondition of the cutover, not only a book-shape preference.

### R16I-02 — ACIS-13 A8 ("entries stay blocked until it passes") is dead on the target universe, and target entries never consult it
- **Severity:** Medium · **Likelihood:** Low (it needs a skewed host clock; the AWS host syncs its clock).
- **Where (de96a75):**
  - `core/runtime/engine.py:82-85`: `signals = () if st.instrument in p.target_universe …`, then `if signals and not self._clock_ok(st)`. With the universe equal to the enabled set, `_clock_ok` is never called, so neither `CLOCK_VERIFIED` nor `CLOCK_CHECK_FAILED` is ever logged.
  - `core/runtime/target_loop.py:58-67` (`EngineView` carries no clock state) and `:174-193` (`execute` has no clock gate).
  - The rule: `specs/ACIS-13-VENUE_ADAPTERS.md:357-360`, together with ACIS-05 §6.4 ("an increase is an ENTRY and meets every entry gate").
- **Reproduction:** `probes/p02_clock_gate.py`. It builds a runtime from the SHIPPED config (pepperstone_demo, the fake venue, the target loop wired) and feeds it only late ticks (2 s; tolerance 1.5 s, the case `test_no_entry_until_a_live_tick_proves_the_host_clock` uses to prove A8 fails). It then executes a pending EUR_USD target:
  ```
  clock_verified: [] clock_failed: []        # A8 never even ran
  TARGET_EXECUTED reason "open" orders [["open", 1, "1000"]]
  risk positions after the executor ran: [('EUR_USD', 1, '1000.00')]
  ```
- **The concrete harm the guard exists for:** the decision runs on the host clock (`target_loop.py:101-107`), and the completeness filter trusts the REQUESTED end (`core/data/ctrader/history.py:81`, `end_of(bar) <= end`). A host clock that runs fast by more than `settle_s` (120 s) therefore fetches the 16:00 bar while it is still forming. It caches the bar as complete, and `last_end` moves past it, so it is never re-fetched. A restart then re-derives the same wrong close.
- **Proposed fix:**
  - Run `_clock_ok` on every live tick of every instrument, not only when legacy signals exist.
  - Expose `clock_verified(instrument)` through `EngineView`, and refuse target ENTRIES until it passes. Reductions are never blocked.
  - Optionally, refuse to decide while no instrument has passed A8.

### R16I-03 — A restart between a disaster stop-out and the slot re-enters the stopped position before the next decision
- **Severity:** Medium · **Likelihood:** Low–medium. It needs a practice restart (a human, a deploy) inside the gap; supervised restarts come back in paper.
- **Where (de96a75):**
  - `core/runtime/target_loop.py:93-97` and `142-161`: boot re-decides the latest day against `held` as it is NOW.
  - `:158`: only a passed slot is dropped.
  - The guard for this case (`position_changed`, `:179`) lives only in the in-memory `Pending`, which a restart loses.
  - The rule: `specs/ACIS-05-CAPITAL_GOVERNOR.md:117`, "A position its disaster stop closed is not re-entered before the next decision."
- **Reproduction:** `probes/p03_restart_reentry.py`. The day-D decision holds a long whose target equals the holding, so nothing is pending. The stop fires overnight.
  ```
  no restart            -> []                     # correct: nothing until the next decision
  restart at 04:00 NY   -> [('open', 1, '1000')]  # re-entered at 08:00 on D+1, before D+1's decision
  ```
- **The same mechanism also falsifies the claim "a restart re-derives the same target"** whenever the book changed after the decision: a stop, an MCP or edge flatten, or a reconcile adoption. `test_a_restart_re_derives_the_same_target_and_drops_a_slot_already_passed` covers only an unchanged book, and `test_a_position_changed_since_the_decision_is_not_re_entered_the_same_day` only covers no restart (A16).
- **Proposed fix:** persist the day's decision in `HistoryStore.meta`: `held` at the decision, the target, and the inputs hash. At boot, re-use it; if the current `held` differs from the decision's `held`, take no action until the next decision, exactly like `position_changed`. Add the restart case to the test.

### R16I-06 — The 17:00 decision blocks the event loop for seconds, growing without bound with the never-trimmed cache
- **Severity:** Medium · **Likelihood:** Medium over months. It is already seconds today.
- **Where (de96a75):**
  - `core/runtime/target_loop.py:118-140`. After the awaits, the decision is fully synchronous: it reads every cached bar of every instrument from SQLite as `Bar` objects, builds a sorted set of all bar ends, and computes 13 full-history series, forecasts and accrual lists.
  - It shares the loop with the fast loop, the Risk heartbeat (`config/system_config.yaml:109-111`, every 10 s) and the venue heartbeats.
  - `config/watchdog.yaml:7`: `watchdog_timeout_s: 30`, so the watchdog flattens a "silent" engine.
- **Reproduction:** `probes/p06_decide_cost.py` (13 shipped pairs, synthetic H1 cache, on `acis-compute-1`, c2d-standard-16):
  ```
  cache 1100 days: decide() blocked the loop  3.38 s
  cache 2200 days:                            6.65 s
  cache 3650 days:                           11.07 s
  ```
- **Unconfirmed extrapolation:**
  - The AWS demo host is a burstable **t3.small**. If its CPU credits run out it is throttled to its baseline, so the same work could take several times longer.
  - With 21 instruments, ×1.6.
  - Once a block exceeds ~20 s (the heartbeat may already be up to 10 s old when the block starts), the watchdog flattens everything at 17:00. A block over 60 s risks the venue liveness timeout.
- **Proposed fix:**
  - Keep per-instrument daily series incrementally (append one day per decision) instead of rebuilding from H1 every day.
  - Or bound the window read to what the family needs: WARMUP plus the 2,560-day slow vol, and only with a B0(d) re-proof.
  - Or run the pure part in a worker thread or executor.
  - Measure on the t3.small before the cutover.

### R16I-07 — A16: the quote→USD conversion that sizes 10 of the 13 shipped pairs is untested; inverting it leaves the whole suite green
- **Severity:** Low–Medium (the code at `de96a75` is correct) · **Likelihood:** certain that a regression would go unseen.
- **Where:**
  - `core/runtime/target_decision.py:78-85` (`usd_per_quote`).
  - B0(d) uses a USD-quoted instrument only (`tests/unit/test_target_path.py:172`).
  - `test_no_target_on_stale_rates_a_stale_close_warm_up_or_no_usd_rate` asserts only the `no_usd_rate` reason.
- **Reproduction:** `probes/p05b_full.sh`, mutant M8: swap `s.closes[-1]` and `1.0 / s.closes[-1]` at `target_decision.py:85`. Full suite: **1330 passed, 6 skipped**.
- **Effect if it regressed:** for the five JPY-quoted pairs, `close·q` grows from ~1 to ~22,500. The average position falls from ~2,900 units to ~0.13, so USD_JPY, EUR_JPY, GBP_JPY, AUD_JPY and CHF_JPY would never trade, silently.
- **Proposed fix:**
  - Add a decision test on a JPY-quoted and a GBP-quoted pair that pins `q`, and the resulting target, against hand arithmetic.
  - Add a B0(d) case with a non-USD quote and RSIM's `q`.

### R16I-09 — A16: "the legacy max-hold closes nothing on the target universe" is untested, and the ledger cites a test that does not exercise it
- **Severity:** Low–Medium · **Likelihood:** certain that a regression would go unseen.
- **Where:**
  - `core/runtime/engine.py:73-74`: the `legacy = {… if i not in p.target_universe}` filter.
  - `KNOWN_GAPS.md:516` (the GAP-P12D-118 R1.6 record) says "its max-hold and legacy signals are off there (R6-3, `test_a_runtime_from_the_shipped_config_wires_the_target_loop_and_silences_legacy`)". That test holds no position, so it cannot see an exit.
- **Reproduction:** `probes/p09_r63_mutants.sh`.
  - **M11:** replace the filter with `legacy = dict(held)`, so every target position is closed after 48 h. Full suite: **1330 passed, 6 skipped**.
  - **M12** (the legacy signals on the universe) is killed by that test, so the signals half of the claim is genuinely covered.
- **Proposed fix:** a runtime test that holds a target-universe position past `max_hold_s` and asserts that no close is submitted. Repoint the ledger's proof to it.

### R16I-04 — A failed fetch for one instrument does not give "no target": the decision proceeds on yesterday's close (false docstring, hollow test)
- **Severity:** Low · **Likelihood:** Medium (any `TRENDBARS_FAILED` while another instrument fetched).
- **Where (de96a75):**
  - `core/runtime/target_loop.py:4-6` claims "a failed fetch leaves that day without a close, so no target".
  - `:163-170`: a failed fetch is logged and skipped.
  - `core/signals/daily.py:76`: the previous day's 16:00 bar is "fresh" (≤ 4 days).
  - `tests/integration/test_target_loop.py:159-168`: the test named "…a_failed_fetch_gives_no_target" fails the fetch on an EMPTY cache, the only case where the claim is true.
- **Reproduction:** `probes/p04_failed_fetch.py` (two instruments; EUR_USD's fetch raises on day D after a good day D−1):
  ```
  TRENDBARS_FAILED: ['EUR_USD']
    EUR_USD day=2026-09-30 reason=target target=1000      # last cached bar ends 2026-09-29T21:00Z
  pending: ['EUR_USD', 'USD_JPY']
  ```
- The behaviour conforms to R6-1's 4-day rule. The defect is the false claim and the hollow test.
  - The decision treats a 24-hour-old close as day D's close; RSIM never does.
  - A late venue bar has the same effect: a missing 16:00 bar at 17:02 makes the decision use the 15:00 close. A restart after the bar arrives then re-derives a different target.
- **Proposed fix:** either make it true (no target for an instrument whose fetch failed or whose last bar does not end at the decision instant), or correct the docstring and the test name and add a populated-cache case.

### R16I-08 — One missing rate file stops every instrument, though R6-1 is per instrument
- **Severity:** Low–Medium · **Likelihood:** Low (a series that never fetched on a fresh host; the prepare step tolerates a failed first run, `deploy/aws/acis-demo-prepare.sh:44`).
- **Where:**
  - `core/data/rates.py:69-78`: all seven files are opened, and any missing one raises.
  - `core/runtime/target_loop.py:127-131`: `TARGETS_NO_RATES`, then return before deciding any instrument.
  - The rule: `specs/ACIS-04-ALPHA_ARENA.md:97` ("gives THAT instrument no forecast").
- **Reproduction:** `probes/p08_one_missing_series.py`:
  ```
  CHF file missing  : load_rate_table raised FileNotFoundError -> no instrument decided at all
  CHF 30 days stale : decided [EUR_USD, USD_JPY, AUD_USD]; no_target:stale_rates [EUR_CHF, USD_CHF, CHF_JPY]
  ```
  (A stale file is handled per currency, as specified. A missing one is not.)
- **Proposed fix:** load the series that exist; a missing series makes its currency stale, so only its pairs give no target. Add a test.

### R16I-10 — Latent: the one-lot cap is applied at the decision and never re-applied at the slot
- **Severity:** Low · **Likelihood:** Unlikely today. The engine changes mode only at startup (`core/runtime/__main__.py:122`), with no runtime MCP transport.
- **Where:**
  - `core/runtime/target_wiring.py:8-9` promises "read from the mode at decision time, so a mode change applies"; the cap is read at `:48-53`.
  - `core/runtime/target_loop.py:184-189`: the slot re-reads only `step`/`minimum` and sends `d.target` as decided.
  - `monitoring/tools.py:142-152` and `monitoring/mode.py:64-81` accept `backtest`/`paper` without preconditions.
- **Reproduction:** `probes/p10_mode_between.py`. Decided in `backtest` (cap None) → target 8000; human switch to `practice` → `executed in practice -> [('open', '8000')]`.
- **Proposed fix:** in `execute`, clamp `d.target` to `lots_of(instrument).cap` (sign kept, never raised), or drop a pending decision whose mode-cap differs from the current one. It is one line plus a test, and closes the hole before any runtime mode control exists.

### R16I-11 — Undeclared engine-vs-RSIM departures beyond GAP-P12D-141's list
- **Severity:** Low · **Likelihood:** Low for the stale-close case (FX rarely goes dark for more than 4 days); unmeasured for the guards.
- **Where:**
  - `tests/backtest/rsim_real.py:118-120` and `:168-173` carry a stale close forward and mask only the warm-up, so RSIM forecasts and trades on stale days.
  - The engine makes no target there (`core/runtime/target_decision.py:96-97`, R6-1).
  - `KNOWN_GAPS.md:167-173` (GAP-P12D-141) lists (1)–(8) and not this. `KNOWN_GAPS.md:516` says "Remaining departures: [[GAP-P12D-141]]".
- **Reproduction:** `probes/p11_stale_parity.py` (a lab tape with a 10-decision dark stretch; the engine is fresh only for ≤ 4 days):
  ```
  seed 2, stale decisions 440..449: RSIM moves +0 -> +1000 at t=442; engine: no_target:stale_close (keeps +0)
  ```
- **The same class, not reproduced here:** RSIM's practice book models none of the entry guards the engine applies (NVMA `tradeable`, `confidence < 0.55`, ILLIQUID, halts, the closure buffer, taper/alpha decay, `no_regime`), nor the slot skips (`busy`, `no_mark`, `position_changed`). The ledger declares only the caps (GAP-P12D-142). The share of 08:00 slots the NVMA veto or low confidence removes is unmeasured; it could be large.
- **Proposed fix:**
  - Add (9), "RSIM forecasts on carried closes; the engine does not (R6-1)", to GAP-P12D-141, or make RSIM mask non-fresh days.
  - Add (10), "entry guards and slot skips are not in RSIM", with a measurement from the demo's own `regime_log` and `target_log` at the 08:00 slot.

### R16I-12 — The disaster stop is not declared in `trend_d1_v1`'s provenance record, though the spec says it is
- **Severity:** Low · **Likelihood:** certain.
- **Where:**
  - `specs/ACIS-05-CAPITAL_GOVERNOR.md:117`: the stop is "a declared deviation in the TREND provenance records".
  - `core/governor/target_gate.py:13-14`: "the stop is a declared deviation".
  - `core/signals/families.py:44-55`: `trend_d1_v1.declared_deviations` holds seven items, none about the stop.
- **Reproduction:** `probes/p12_provenance_stop.py`. Over the 7 declared deviations, none mentions "stop", "ATR" or "disaster", nor the practice one-lot cap, the BID trendbars, or the stale-close rule.
- **Note:** `register_family` (`families.py` `register_family`) registers only MISSING records, so a corrected record would not reach a provenance store that already holds `trend_d1_v1`. The correction needs a new version id, or a declared re-registration path.
- **Proposed fix:** add the stop (and the venue-side departures the runtime makes) to the record under a new family-version id. That also exercises flatten-then-promote.

### R16I-13 — Surface 10: the shipped-config narrowing hides one release-gate failure; the other six failures are benign
- **Severity:** Low · **Likelihood:** certain.
- **Reproduction:**
  - `probes/shipped_suite.sh` makes `acis_config` the shipped config; unit + integration: **7 failed, 937 passed**.
  - `probes/shipped_detail.sh` classifies the failures.
  - `probes/shipped_demo.sh` reruns the runtime files on the shipped config with `active_account: pepperstone_demo`, as deployed: **19 passed, 1 failed**. The failure is the legacy practice open, as R6-3 intends.
- **Real:** `tests/integration/test_adapter_conformance.py:169-174` (`test_symbol_map_covers_enabled_universe[mock]`), the "§7.5 RELEASE GATE", passes only on the narrowed pair.
  - The mock face, which is the paper descriptor whenever no venue is attached (`core/runtime/wiring.py:190`), maps 2 of the 13 enabled pairs. 11 are missing: USD_CHF, AUD_USD, GBP_JPY, ….
  - `python -m core.runtime` (paper, mock feed) runs the shipped 13 with `target_universe` empty, because there is no venue, so the LEGACY engine trades all 13 on a descriptor that does not map them.
- **Benign:**
  - `test_a_practice_demo_attaches_verified_and_eligible_for_practice` hard-codes the two symbols.
  - Five runtime tests raise `ValueError: dev_paper: the target path needs initial_capital and vol_target_annual`, because the shipped default `active_account: dev_paper` is incompatible with the shipped `targets:` block. Under `--account pepperstone_demo` they pass.
  - Note: through `__main__`, a cTrader rulebook without those fields would surface the same `ValueError` as a traceback (exit 1), not a named exit-2 refusal. This is unconfirmed end to end.
- **Proposed fix:** either extend the mock descriptor to the enabled universe, or make the gate test read `shipped_config` and assert explicitly which face serves which mode. Make `check_targets` a named refusal in `__main__`.

---

## Honest negatives (searched, not found)

**Money reach and size**
- No target-path open exceeds one venue minimum lot in paper or practice.
  - The cap is applied after the lot rule (`core/governor/target.py:55-58`).
  - Same-side increases are refused (`add_unsupported`).
  - A flip closes the whole holding and opens ≤ cap; the executor holds the open unless the close left the instrument flat (`core/runtime/executor.py:95-98`).
- Live mode sends nothing: `route_to` returns `None` for live and backtest (`core/runtime/wiring.py:117-122`).
- `lots_of` cannot return `None` at the slot after a non-`None` decision, because `Attached` is frozen at attach and never re-bound.

**Protection**
- Every open carries `stop = mark ∓ 10·ATR`. NaN or non-positive ATR, and a stop ≤ 0, give `stop_invalid` (`target_gate.py:83-86`).
- The ATR is Wilder's true range over the daily bars `series()` builds.
- The face sends a relative distance widened by the spread and floored to the tick, from the fill (`core/execution/ctrader_orders.py:63-74`).
- `SizedOrder` does not validate stop sides, so a close with `stop_loss = mark` cannot crash the loop.

**Guards and limits**
- The guard extraction is faithful: `git diff 2fbe40b aa73ea0 -- core/governor/capital_governor.py` moves §7.1 verbatim into `EntryGuards.check`, and nothing else reads the moved halt state.
- Reductions never pass a guard.
- Taper and alpha decay shrink, then re-round toward zero.
- `max_lots` zeroes.

**Parity and mutants (B0(d) strength)**
- Engine-side mutants killed by the R1.6 parity tests:
  - excess price without carry;
  - `pct_vol` ×2 and ÷2;
  - `price_basis` ×2;
  - the carry sign flipped;
  - WARMUP 260→200;
  - buffer 0;
  - `cash_vol` ×4.
- The Friday-triple swap-calendar mutant survives the parity tests (the B0(d) test builds its rates through the same `swap_multiplier`), but the full suite kills it: 5 tests in `test_harness_regressions`, `test_glitch_classes` and `test_rsim_real`.
- `probes/p05_b0d_mutants.py` and `probes/p05b_full.sh` hold these runs.
- The legacy-signal filter mutant (M12) is killed.

**Clocks**
- `slot_after` is strictly after the decision at every DST edge tested.
- Sleeps are capped at 300 s, so a DST transition or a long sleep cannot skip a wake.
- `_latest_day` and `_next_wake` handle the UTC-midnight and weekend cases. The UTC date of the 17:00 NY rollover equals the NY date in both seasons.
- Friday's decision goes to Monday's slot.

**Exceptions in the loop**
- Every venue failure path reaches `FETCH_ERRORS`:
  - `ConnectionError` from link loss (`session.py:250`);
  - send on a closed socket (`OSError`);
  - `asyncio.TimeoutError`;
  - `VenueError`;
  - `BudgetRefused`;
  - decode `DataQualityError`.
- Rate-file errors (`OSError`, `ValueError`, `KeyError`) are caught.
- The 13 shipped quotes are all in `TO_USD`, and their bases are all in `CCY_SERIES`.
- No reachable exception was found that would turn the loop into a `LOOP_STALLED` flatten. A full disk (SQLite) would, and the JSONL logs are full by then anyway.

**Weekend boot and the closed market**
- A promotion flatten on a closed market is a refused close, not an exception (`core/execution/ctrader_close.py` invariants). It waits for the next decision.

**R6-3**
- Legacy signals and the legacy exits are filtered on the universe.
- The weekend flatten would act on target positions only under a rulebook with `weekend_holding_allowed: false`. `pepperstone_demo` allows weekend holding, so it is latent on the demo.

**Budget**
- 8·11 + 576 + 48 + 140 + 2·21 = 894 ≤ 900.
- History is a metered query, refused inside the reserve.
- A failed fetch stores nothing (all or nothing), so it leaves no gap.
- `INSERT OR REPLACE` is idempotent.

**Rates**
- Per-series atomic writes (`write_atomic`) and per-currency staleness, so mixed-age files are handled correctly. The exception is a missing file (R16I-08).

**Deploy and config**
- The AWS runbook runs the engine from `/opt/acis/repo`, consistent with the macro unit's `data/macro_live`.
- The runtime imports no numpy (the AWS venv has none).
- `pepperstone_demo`'s `initial_capital` anchors no limit: it is used only for `origin == "platform"` rules, and there are none.

**A12 / A13**
- No production module under audit exceeds 300 lines; `capital_governor.py` is grandfathered and shrank.
- Every new invariant-bearing module opens with its mental model.
- The suite count and the ledger check hold.

## What I could not verify (internal lens; for the external auditor or the cutover)
- The venue's `hasMore` truncation direction for trendbars. The code assumes "latest N kept" (`history.py:12-15, 84`). If the venue keeps the OLDEST N instead, the walk skips a span silently and permanently, because the cache appends only after its max. The 365-day window keeps H1 under 14,000 bars, so this matters only if the venue's real limit is lower.
- R16I-06's timing on the actual t3.small (the measurement was on c2d-standard-16).
- Whether SARON's TLS path succeeds from the AWS host (R16I-08's trigger).
- The NVMA veto and low-confidence rate at the 08:00 New York slot on real ticks (R16I-11).
- Rate publication times. RSIM grades with each day's rate as-of that day, while EFFR, SONIA, TONA and CORRA publish on the next business day. That is a one-day look-ahead of negligible size on RSIM's side; the engine's side is declared as GAP-P12D-141 (8).

## Residual risk
- **Before the cutover:**
  - R16I-05 makes the $100k account a hard precondition. Without it, the first slot halts everything.
  - R16I-01 is a dated failure about 100 days later; it is cheap to fix now.
- **Over the demo's life:**
  - R16I-06's blocking time grows with every day of cache. Together with the watchdog's 30-second silence rule, it becomes a nightly flatten risk on a throttled host.
  - R16I-03 turns routine human restarts into occasional rule-breaking re-entries.
- **The forward record:** R16I-11 means the demo's realised book differs from RSIM's graded book in ways the ledger does not yet name. Measure that before reading the record as the graded family.
- **Test debt (A16):** R16I-07 and R16I-09 leave two load-bearing R1.6 claims (the sizing rate for ten pairs, and R6-3's exit half) guarded by nothing.
