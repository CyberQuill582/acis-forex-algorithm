# BUILDER-3 report — prop-account tightening batch (2026-09-24/25)

**Status: AUDITED ONCE (2026-09-25); THE AUDIT FIXES ARE BUILT — PENDING THE LEAD'S TRIAGE.** A builder is a
finder, not a clearer. The fixes below answer the two audits; they have not themselves been audited. Nothing here is
✅, and nothing here is merged: it lives on this branch only.

- **Branch:** `worktree-agent-a9e00713d15bb5082`, at `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a9e00713d15bb5082`.
- **Base:** `main` at `bdd3a75`. The worktree was created at `7695ed0` and fast-forwarded to `bdd3a75` before any work.
- **Authority:** the owner's in-chat delegation, relayed by the lead ("proceed with the recommendations").
- **What the branch delivers, corrected after the audits:**
  - **Restart-invariant** drawdown readings: a restart changes no reading.
  - **Tightening elsewhere.**
- **The earlier "tightening-only" claim was FALSE.** The two audits of 2026-09-25 found inputs that made the branch
  looser than main:
  - F0: one failed ledger write dropped the equity breaker;
  - F1: a stale session row muted later daily halts;
  - F11: rounding orphaned a pair leg.

  All three are fixed below.
- **Accepted by the lead, as a delegated decision: F3.** After a restart made while the account is up, a later loss
  reads LOWER than main's accidental re-anchor would. This is faithful to the firm's static rule.
- **The same property from a declared `initial_capital` (F6).** Its values are now validated at load.
- **Untouched:** every guardrail value, the equity floor, `config/platform_rules.yaml`, the DSR/`passed` gate, the
  §14 targets, `ACIS_SPEC.md`, `specs/`, `KNOWN_GAPS.md`, `TODO.md`, the baseline tag and `data/`.
- **Config:** `config/system_config.yaml` gains one key, `execution.max_venue_requests_per_day: 1000`, as the brief
  directed. It is a new hard cap: a tightening.

## Setup

- The baseline run at `bdd3a75` was **808 passed, 6 skipped**. The read path's "814 green" counts passed plus skipped.
- `scripts/ledger_check.py` passed: 204 entries, 0 violations. It still passes at the end of the batch.
- Free memory stayed between 1.1 and 2.7 GB. It was checked before every full run.

## Outcome by stage

| Stage | Gap | Commit | New tests | A16 reverts caught | Full suite |
|---|---|---|---|---|---|
| 1. A restart never relaxes a drawdown limit | GAP-P12D-55 | `c54c0d1` | 6 | 3 of 3 | 814 passed, 6 skipped |
| 2. Venue lot step, minimum lot, request cap | GAP-P12D-57 | `3c2aee9` | 14 | 4 of 4 | 828 passed, 6 skipped |
| 3. Pre-close entry ban on every account | GAP-P12D-58 | `57fc40f` | 2 (+1 inverted) | 1 of 1 | 830 passed, 6 skipped |
| 4. Daily-reset rules and a declared initial capital | GAP-P12D-54 / -59 | `713a84e` | 11 | 5 of 5 | 841 passed, 6 skipped |
| 2b. The budget exemption checks the venue position | GAP-P12D-57 (+ F1 below) | `272e2f6` | 1 | 1 of 1 | 842 passed, 6 skipped |
| 6. Explicit HALTs survive a restart | lead's P12D-75 (F2 below) | `34d3f77` | 5 | 5 of 5 | 847 passed, 6 skipped |
| 7. Reduce-only closes trade the opposite side | lead's P12D-74 (F1 below) | `16150bb` | 4 (+1 made stricter) | 4 of 4 | 850 passed, 6 skipped |
| 5. Weekend flatten, built after stage 7 fixed the close path | master §9.5 | `f23e73d` | 6 | 5 of 5 | 856 passed, 6 skipped |

### The audit round (2026-09-25): both constitutional audits, then 11 fixes, each committed on its own

The audits' repro scripts became the regression tests.

| # | Finding (the lead's ID) | Commit | New tests | A16 reverts caught | Full suite |
|---|---|---|---|---|---|
| 1 | F0/X2: the guard acts first; recording never gates it (P12D-79) | `be59c96` | 5 | 5 of 5 | 861 passed, 6 skipped |
| 2 | F2 + F1/X1: the session latch re-arms at the boundary; lapsed rows are never re-latched (P12D-80, P12D-78) | `6826085` | 3 | 4 of 4 | 864 passed, 6 skipped |
| 3 | F11: a pair group is both legs or neither in execution (P12D-81) | `2efb7bb` | 4 | 3 of 3 | 868 passed, 6 skipped |
| 4 | X3/F4: the close intent crosses the face as the venue's atomic close | `ab4b6df` | 7 | 4 of 4 | 875 passed, 6 skipped |
| 5 | X4: WAL + synchronous=FULL for the risk store and the fill log | `4e1e9be` | 2 | 3 of 3 | 877 passed, 6 skipped |
| 6 | X5: the ban and flatten key on every closure of 2 h or more, holidays included | `4b5f150` | 4 | 3 of 3 | 881 passed, 6 skipped |
| 7 | X6/F5: a close the venue keeps refusing is paced, never blocked | `5d00372` | 4 | 4 of 4 | 885 passed, 6 skipped |
| 8 | F6: `initial_capital` is finite and > 0; a typo is fatal at load | `52c0aef` | 7 | 2 of 2 | 892 passed, 6 skipped |
| 9 | F7: a store-backed monitor evaluates only after its restore | `9e39d32` | 2 | 2 of 2 | 894 passed, 6 skipped |
| 10 | F8: exactly one human-resume path, and it clears the ledger | `da09bf7` | 2 | 2 of 2 | 896 passed, 6 skipped |
| 11 | X9/F10 random resume id, F9 unique halt ids, F12 claim drift | `4f3ed0a` | 3 | 3 of 3 | **898 passed, 6 skipped** (final) |

The details are in "The audit round" section after Stage 5, and every finding's disposition is in "Findings for
the lead to file".
- **Open: X7.** FTMO 1-Step's end-of-day trailing max loss needs a rule type the schema does not have (R4-7).
- **Fixed as documentation: X8.** The FTMO page is cited at `dateModified` 2026-09-24, here and in
  `tests/unit/test_platform_daily_rules.py`.
- Residuals are listed per item.

The lead's new ledger IDs are written without the `GAP-` prefix in this report and in the code: this branch's
`KNOWN_GAPS.md` predates them, and `scripts/ledger_check.py` fails on an ID the branch's ledger does not define. The
code cites the spec section instead (ACIS-07 §7; the close convention in `venue_limits.py`).

**How each revert was run:** each A16 revert used a scratch helper. It applied one text mutation that undoes one
fix, ran the named tests, restored the file from its original bytes, and compared sha256 before and after. The
output below is quoted from those runs; every restore printed `RESTORED <same hash>`.

---

## Stage 1: a restart never relaxes a drawdown limit (GAP-P12D-55, critical)

### What changed

**Persistence.** Every drawdown anchor is persisted after every evaluate, in one SQLite transaction, in the
existing `restrictive_state` table under the key `anchor:<rule_key>`. No DDL changes. Three kinds of anchor are
covered:
- the static inception anchor;
- the trailing high-water mark;
- the engine's daily day-open anchor, with its day.

The same transaction also writes `alpha_armed` and `taper_factor`, so a crash never pairs a taper from one
evaluate with anchors from another. `core/risk/store.py` holds `save_restrictive_state(..., anchors=)`,
`load_anchors()` and `restore_on_boot()`. `load_restrictive_state()` no longer returns the anchor rows.

**Restore.** `restore_on_boot(store, monitor)` runs before the first evaluate. It restores the anchors and the
alpha throttle, and it **re-pushes the persisted taper** to the fresh Governor. The taper had always been saved but
never loaded, and ACIS-07 §7 already required it back. The new hook is `Guardrails.restore_state`.

**Semantics after a restart:**
- **Same trading day:** the daily anchor is restored exactly.
- **Across a missed rollover:** the new day anchors on the LARGER of two samples: the last persisted observation and
  the first new one. The engine never saw the rollover, so it keeps the stricter of the two observations that
  bracket it. A loss taken while the engine was down is never forgotten.
- **In-process rollover:** unchanged, and still ratified: the first observation of the day.

**Duplicate keys.** Two rules may no longer share a rule key. They would share one anchor and one persisted record.
`build_drawdown_series` now raises `DataQualityError` on a duplicate.

**Legibility.** The drawdown series moved to `core/risk/drawdown_series.py`, which carries the mental model.
`guardrails.py` re-exports the moved names. The quote→USD factor moved to `core/risk/usd_conversion.py`. As a result:
- `guardrails.py` leaves the grandfather list. It was 236 lines at stage 1; the audit counted 253 at `d8361a7`
  (F12). It is 283 now, still under the 300-line budget;
- `monitor.py`'s cap drops from 378 to 368 (343 after the audit round);
- the code-shape baseline loses the two BLOCK entries the move burned down.

### Tests (`tests/unit/test_restart_anchors.py`)

- `test_restart_at_a_drawdown_still_reads_it_on_every_rule` is the lead's case: 10,000 → 9,400, then everything is
  rebuilt. Afterwards:
  - `engine:daily`, `ftmo:trailing:intraday:equity` and `ftmo:static:eod:balance` all read 6.0%;
  - the taper is 0.0, re-pushed before the first evaluate;
  - the platform HALT and the session halt fire again.
- `test_restart_across_a_trading_day_boundary_reanchors_the_daily_rule`: the daily rule reads 0% on the new day,
  while the static and trailing rules still read 6%.
- `test_a_loss_taken_while_the_engine_was_down_is_not_forgotten`: the rule reads (9,400 − 9,300)/9,400, and the
  next in-process rollover re-anchors normally.
- `test_store_keeps_anchors_apart_from_the_legacy_restrictive_keys`.
- `test_restore_refuses_a_corrupt_anchor_and_skips_a_retired_rule`: NaN or a negative value is refused; a key the
  rulebook no longer declares is ignored.
- `test_two_rules_may_not_share_one_anchor`.

### Falsification (A16)

| Revert | Result |
|---|---|
| `restore_on_boot` restores only the alpha flag | 3 failed (restart at a drawdown: `IndexError` on the taper re-push; boundary and downtime: 0.0 ≠ 6.0 / 1.06) |
| taper restored, anchors not (`anchors={}`) | 3 failed (`0.0 == 6.0` on every rule) |
| no downtime bracket (`bracket = False`) | 1 failed: `test_a_loss_taken_while_the_engine_was_down_is_not_forgotten` (0.0 ≠ 1.0638) |

### Residuals

- **R1-1: nothing in production calls `restore_on_boot` yet.** The three-loop runtime has no boot sequence to call
  it from; the tests call it. The runtime must call it before the first evaluate, beside `reconcile_on_restart`.
  A store-backed monitor now refuses to evaluate until it has (audit F7, item 9). Owner: GAP-0091b / GAP-0075.
- **R1-2: the downtime bracket is conservative, not exact.** It is never below either known sample, but the true
  value at the rollover is unknowable without the broker's balance history (GAP-P12D-55's other candidate fix). The
  ACIS-13 adapter can make it exact.
- **R1-3 (F2 below): active halts were not re-applied at boot. Addressed by stage 6.**
- **R1-4: the per-evaluate write cost is unmeasured.** It is one small transaction per evaluate (10 s cadence). The
  backtest replay does not construct a `RiskStore`, so it pays nothing.

**Corrected claim (audit F3): restart-INVARIANT, not "never looser".** Every restored value is the dead process's own
reading, so a restart changes no reading. That is not always stricter than main. Main re-anchored at the first
equity seen after a restart, an artifact that happened to be stricter when the account was UP at restart: 10,000 →
10,500, then a restart, then 10,280 reads 0% here and 2.1% on main. The lead accepted F3 as a delegated decision,
because the delivered reading is the declared semantics and is faithful to the firm's static rule. The in-process
rollover semantics are unchanged.

---

## Stage 2: the venue's quantity and request limits (GAP-P12D-57)

### What changed

The engine previously read only `max_order_lots` from the `CapabilityDescriptor`
(`core/execution/orchestrator.py`, `core/execution/venue_limits.py`).

**Lot step: round DOWN, never up.** Every quantity sent to a venue is rounded DOWN to a whole number of the venue's
lot steps: the order, each fragment, a reroute and a partial-fill remainder. It is never rounded up, because the
Governor clamps only downward. The unsent remainder becomes a `REJECTED` FillReport, logged as
`EXEC_LOT_STEP_ROUNDED`; it is never a silent drop. The fragmenter plans in whole lot steps (`plan(..., quantum=)`,
rounding down with the last fragment absorbing the rest), and C-EXE-1 still holds on what is sent.

**Minimum lot: refuse.** A quantity below the venue's `min_lot` is refused: a `REJECTED` FillReport logged as
`EXEC_MIN_LOT_REFUSED`. It never reaches the venue.

**Request budget, rolling 24 hours.** A hard budget of trading requests per venue applies over **any rolling 24 hours**:
- **What counts:** every `submit_order` attempt, including reconnect retries, reroutes and partial remainders.
- **The limit:** `execution.max_venue_requests_per_day`, a required key (schema-fatal if missing), set to 1000,
  half of FTMO's and E8's 2,000/day.
- **Why rolling:** a rolling window is stricter than any calendar-day reading, whatever the firm's day boundary.
  It allows ≤ 1,000 requests in any 24 h, and so ≤ 2,000 across a 25-hour DST day.
- **When spent:** opens are refused (`EXEC_REQUEST_BUDGET_REFUSED`). A close that truly shrinks the venue position
  still goes through, and the exception is logged (`EXEC_REQUEST_BUDGET_DERISK`).

**Restart.** The budget is seeded from the persisted fill log (`FillReportStore.request_times`), so a restart cannot
reset it.

**Descriptor and legibility.** `CapabilityDescriptor` now refuses `lot_step <= 0` or `lot_step > min_lot`.
`FillReportStore` moved to `core/execution/fill_store.py` (re-exported), which takes `venue.py` from 378 to 342 lines.

**Hardening (2b).** In the first commit the budget exemption trusted the `close` label. Finding F1 below shows that
label can lie: a Governor close currently ADDS to the position. The exemption now applies only when the venue
holds one position on that instrument, in the opposite direction, at least as large as the close. Opens never
trigger that position read, because reads may count against a firm's cap.

### Test changes that encode the new, stricter contract

- **`tests/integration/test_execution_pipeline.py`.** `test_signal_to_fill_full_audit_chain` and
  `test_pair_group_executes_both_legs` asserted that a Governor order of ~691 units fills *exactly*, on a mock venue
  that declares a 1,000-unit minimum. That is the GAP-P12D-57 defect itself. They now run on a whole-unit venue
  (OANDA v20's granularity) and assert that filled equals whole units, and that filled plus the reported remainder
  equals the sized quantity.
- **Config fixtures.** Three `ExecutionConfig(...)` test fixtures gained the new required key.

### New tests

**Conformance** (`tests/integration/test_adapter_conformance.py`, run over every adapter through the real
orchestrator):
- `test_sub_minimum_order_is_refused_and_never_reaches_the_venue`;
- `test_quantity_is_rounded_down_to_the_lot_step_never_up`;
- `test_spent_request_budget_refuses_opens_but_never_a_close`;
- `test_spent_budget_refuses_a_close_that_would_add_to_the_position`;
- `test_request_budget_survives_a_restart` (spent 1 h later; open again after 25 h).

**Unit** (`tests/unit/test_venue_limits.py`):
- exact vectors: 332 → refused; 999.99 → refused; 1,926.40 → 1,000 plus 926.40 unsent;
- a coarse minimum with a fine step;
- descriptor validation;
- the rolling window;
- a close is counted even when admitted;
- fragments are whole lot steps and still sum exactly.

### Falsification (A16)

| Revert | Result |
|---|---|
| `venue_quantity` sends everything | 6 failed (both conformance quantity tests, 4 unit vectors) |
| the budget never refuses | 3 failed (conformance spent-budget, restart; unit rolling window) |
| the budget also blocks closes | 2 failed (conformance close-goes-through; unit close admitted) |
| no restart seed (`seed=()`) | 1 failed: `test_request_budget_survives_a_restart` |
| 2b: trust the `close` label again | 1 failed: `test_spent_budget_refuses_a_close_that_would_add_to_the_position` |

### Residuals

- **R2-1: the budget counts only submits.** Reads (`open_positions`, `account_snapshot`) are not counted.
  `ExecutionFace` has no modify method, and core never calls `cancel`. If FTMO counts reads (its wording is "server
  requests"), the budget under-counts; ask FTMO in email Q. The ACIS-13 adapter must count its own cancels, modifies
  and stop edits against this same budget.
- **R2-2: a restart can under-count slightly.** The seed counts fill-log rows per venue. A double disconnect writes
  one row for two attempts, so a restart can under-count by one per such event in the last 24 h. The margin is half
  the cap.
- **R2-3: most Governor orders are now refused, as intended.** Examples are the SCOUT's 332 units against a
  1,000-unit minimum. Until NAV-relative prop sizing is ratified (owner, GAP-P12D-57 part 1 / GAP-P12D-61), **expect a
  demo to refuse most orders loudly**. This is the honest outcome that replaces un-placeable orders.
- **R2-4: other venue caps are still unenforced.** Open-order caps (FTMO 200, E8 100) and E8's 2,000 positions a day
  are not enforced, and the §9.5 schema cannot express them (§5.3 item 4).
- **R2-5: the exemption assumed a netting account.** Addressed in the audit round:
  - items 4 and 7: `close_position` is the venue's own atomic close, and a refused close is paced;
  - item 3: a pair group is atomic.
  Closing by position ID on a real hedging venue remains the ACIS-13 adapter's mapping.

**Not looser on sequential single-leg flow.** Every new path refuses or shrinks; none adds size or requests. The audit
found one path where it WAS looser: rounding each pair leg alone orphaned the larger leg (F11). That is fixed by item 3.

---

## Stage 3: the pre-close entry ban binds every account (GAP-P12D-58)

### What changed and why

The ~2-hour pre-weekly-close entry ban (`weekend_entry_buffer_s`, value unchanged) no longer depends on
`weekend_holding_allowed` (`core/governor/capital_governor.py`, `core/governor/calendar_gates.py`).

FTMO forbids opening a trade "two hours or less before a relevant financial market is closed for at least two
hours" on every account type, Swing included. The ban is therefore now stricter everywhere, and looser nowhere.

### Tests

- **Inverted assertion.** `test_weekend_entry_buffer_blocks_no_weekend_accounts` asserted that a weekend-allowed
  account IS sized at the Friday close, which is the defect. It now asserts `weekend_ban`, and a comment says so.
- **New:** `test_swing_account_refuses_an_entry_an_hour_before_the_friday_close[7-21 | 1-22]`, covering EDT and EST.
  It checks 1 h before the close (banned), exactly 2 h before (banned: the fence post) and 2 h 1 min before (sized).

### Falsification (A16)

Restoring the `not weekend_holding_allowed and …` coupling fails 3 tests: the inverted assertion
(`'formula' == 'weekend_ban'`) and both parametrizations of the new test.

### Residuals

- **R3-1: only the Friday FX close is covered.** Other closes of two hours or more are not: exchange holidays, index
  CFD or metals holiday closures, and non-FX calendars. The news half of "gap trading" (a scheduled-news entry
  blackout on Swing) is still the [spec] part of GAP-P12D-58 plus GAP-P12D-03.
- **R3-2: ACIS-05 still describes the old rule.** §5/§7 scope the buffer to no-weekend-holding accounts. The
  amendment is drafted below.

**No guard loosened.** A ban was widened; the buffer value is unchanged.

---

## Stage 4: daily-reset platform rules and a declared initial capital (GAP-P12D-54 / -59)

### What changed

**Schema** (`config/rulebook.py`, moved out of `config/schemas.py`, re-exported; `schemas.py` 617 → 581). The
`DrawdownRule` changes:
- it gains `type: daily`;
- `reset` is a local `{zone, at}` (a `ZonedTime`, like every market time);
- `reset_basis` is `balance | equity | max`;
- `limit_of` is `anchor | initial`.

Validation:
- a daily rule must declare `reset` and `reset_basis`; a static or trailing rule must declare neither;
- `limit_of` defaults to `anchor`, so every existing rule keeps its meaning.

`AccountRulebook` gains an optional `initial_capital`. A rule with `limit_of: initial` is a schema error without it.

**Risk series** (`core/risk/drawdown_series.py`):
- **Measurement:** measured % = (anchor − basis) / denominator. The denominator is the initial capital for
  `limit_of: initial`.
- **Static rules** anchor on the declared initial capital.
- **Trailing rules** seed their high-water mark there. That is only ever stricter than the first observed basis.
- **Platform daily rules** anchor their `reset_basis` on the LARGER of the last observation before the reset and the
  first after it. FTMO reads the balance AT 00:00; a stop that books a loss two seconds later must not lower the day.
- **Restore:** a restored static or trailing anchor never sits below the declared capital.
- **Anchors** are persisted through stage 1's path.

**Clock.** `Europe/Prague` (CE(S)T) joins the modelled zones: standard offset +1 under the EU rule (`config/calendars.py`,
`core/data/fx_clock.py`). Resolution by local date is an hour off at 00:00 on the two switch Sundays. Both the
resolved and the true instant fall inside the FX weekend, and a test proves it.

### Tests (`tests/unit/test_platform_daily_rules.py`)

They follow FTMO's page exactly. The page is ftmo.com/en/trading-objectives; the audit re-fetched it on 2026-09-25,
when its `dateModified` was **2026-09-24** (X8: earlier drafts cited 2026-05-13). The 2-Step semantics are unchanged.
- day 1 floor $95,000 on equity;
- day 2 floor $97,000 after a day that closes at $102,000;
- the static max loss at initial − 10% on equity, including for an account attached while in profit.

**The lead's $6,000 case.** At the 17:00 New York rollover the balance is 6,000 with −240 floating. FTMO's line is
5,700, from 00:00 CEST. The results:
- at 5,701: no breach;
- at 5,699: `PLATFORM_DD_BREACH` on the daily rule, while the engine's 2% sits at distance 0.53.

The test also records `("all", "equity_floor")`: the absolute $9,000 floor halts any $6k account (GAP-P12D-56,
owner-owned), and later halts coalesce under it.

**Other tests:**
- the loss just after the reset;
- `reset_basis: max`;
- initial-capital anchoring of static and trailing rules;
- a restart that keeps the FTMO day anchor and refuses a tampered-low static anchor on disk;
- schema explicitness;
- the shipped rulebooks keep their meaning;
- `test_central_european_midnight_follows_eu_summer_time` (in `tests/unit/test_fx_clock.py`).

### Falsification (A16)

| Revert | Result |
|---|---|
| platform rules never reset daily | 3 failed (day-2 floor, max basis, restart) |
| the limit is always a % of the anchor | 2 failed (day-2 floor, restart) |
| static rules ignore the declared capital | 2 failed (max loss, initial anchoring) |
| no reset bracket for platform days | 1 failed (loss just after the reset) |
| restore takes whatever is on disk | 1 failed (restart with the tampered anchor) |

### Drafts for the owner to commit — `config/platform_rules.yaml` is NOT edited

**Corrected `ftmo` entry.** It models FTMO Challenge 2-Step, **Swing**, $10,000 USD, cTrader Open API. Verify every
value on purchase day.
```yaml
  ftmo:                             # FTMO Challenge 2-Step, SWING, $10,000 USD, cTrader Open API
    platform: ctrader               # ftmo.com/en/trading-platforms/ (2026-08-31)
    news:                           # Swing: no +-2 min rule, but "gap trading" forbids OPENING when
      restricted: true              # major scheduled news may move the market, on every account.
      window_before_s: 3600         # PLACEHOLDER pending FTMO email Q3 (the stricter side kept)
      window_after_s: 120
    min_hold_seconds: 0             # no hold-time rule published
    weekend_holding_allowed: true   # Swing only; the 2 h pre-close entry ban now binds regardless (GAP-P12D-58)
    initial_capital: 10000.0        # the "Initial Simulated Capital" both limits are sized on
    drawdown_rules:
      - type: daily                 # Maximum Daily Loss: equity may not drop below
        anchor: intraday            #   balance at 00:00 CE(S)T − 5% of the initial capital
        basis: equity
        reset: {zone: Europe/Prague, at: "00:00"}
        reset_basis: balance
        limit_of: initial
        limit_pct: 5.0
      - type: static                # Maximum Loss: equity may not drop below initial − 10%
        anchor: intraday
        basis: equity
        limit_of: initial
        limit_pct: 10.0
    min_trading_days: 4             # 2-Step (enforced nowhere yet: GAP-P12D-60)
    # taper_start_fraction: 0.50    # OPTIONAL stricter override (SCOUT suggestion): a breach is terminal
    # entry_halt_fraction: 0.70
```
On a **Standard** funded account, set `weekend_holding_allowed: false` and `news: {restricted: true,
window_before_s: 120, window_after_s: 120}`. The SCOUT found Standard incompatible with §279 server-side stops
(a stop inside ±2 min is a breach). FTMO 1-Step's end-of-day trailing max loss is **not expressible** yet (§5.3 item 3).

**New `e8` entry.** It models E8 Markets "E8 Pro", $10,000, cTrader. **Do not commit until E8's server-time zone is
verified** (email §9.2).
```yaml
  e8:                               # E8 Markets "E8 Pro", $10,000, cTrader (+$10 if the account costs < $100)
    platform: ctrader               # help.e8markets.com 9799834 (2026-09-23)
    news:
      restricted: false             # E8 Pro: news trading allowed (13106558)
    min_hold_seconds: 0             # E8's HFT rule is distributional (<= 50% of trades under 60 s): not expressible
    max_lots: 50.0                  # "Max ticket size (most symbols): 50 lots" (XAUUSD 20: not expressible)
    weekend_holding_allowed: true
    initial_capital: 10000.0
    drawdown_rules:                 # E8 fails the account if "equity OR balance" reaches a level: one rule per basis
      - type: daily                 # 2.5% of initial below the day's starting balance, at 00:00 SERVER TIME
        anchor: intraday
        basis: equity
        reset: {zone: America/New_York, at: "17:00"}   # PLACEHOLDER: assumes the NY-close-aligned server
        reset_basis: balance                           # clock (00:00 server = 17:00 New York). VERIFY.
        limit_of: initial
        limit_pct: 2.5
      - type: daily
        anchor: intraday
        basis: balance
        reset: {zone: America/New_York, at: "17:00"}   # same PLACEHOLDER
        reset_basis: balance
        limit_of: initial
        limit_pct: 2.5
      - type: static                # 8% static of initial ("never moves, except when a first payout is
        anchor: intraday            #   processed": the payout move is not expressible)
        basis: equity
        limit_of: initial
        limit_pct: 8.0
      - type: static
        anchor: intraday
        basis: balance
        limit_of: initial
        limit_pct: 8.0
    consistency_max_day_profit_pct: null   # E8 Pro: "No consistency rules"
```
Also not expressible: the 2% daily profit cap for target counting, 2,000 positions a day, 100 open orders, 60-day
inactivity, and E8 One's closed-balance trailing max loss that locks at the initial balance.

### Residuals

- **R4-1: a platform breach still HALTs without flattening.** Master §9.5 says "Open positions and their stops are
  untouched", and under FTMO a breach is terminal. A pre-breach flatten is the owner's [spec] part of GAP-P12D-59.
- **R4-2: the engine's own daily limit is unchanged.** It is still a session halt anchored at 17:00 New York (HALT
  semantics: GAP-P12D-59 points 1–2).
- **R4-3: until the owner commits the draft,** the shipped `ftmo` entry still carries the wrong semantics
  (GAP-P12D-54 points 1–2). No backtest or demo on it is faithful to FTMO.
- **R4-4: a rulebook's content hash now changes.** `rulebook_hash` covers `model_dump()`, which now includes the new
  default fields, so every existing rulebook's hash changes. A human re-attests before live. No hash is pinned in the
  repo.
- **R4-5: GAP-P12D-56 is untouched.** The $9,000 absolute floor still halts any account under $9k; the $6k test shows
  it.
- **R4-6: the daily rule also tapers early, like every other limit.** With the default 0.60/0.80 fractions, the §9.5
  pre-limit taper starts cutting entries at 3% and stops them at 4% of initial capital, on FTMO's 5% daily limit.
  That is stricter than the firm, by design.
- **R4-7 (audit X7), OPEN: FTMO 1-Step's max loss needs a rule type the schema lacks.**
  - **FTMO's rule:** an END-OF-DAY trailing limit, anchored on the highest BALANCE at 00:00 CE(S)T of any preceding
    day (or the initial capital, if higher), minus 10% of initial, and measured on EQUITY.
  - **Why no current encoding is safe.** Today's `trailing` type sets its anchor and measures with ONE basis, so
    both near-misses are looser than FTMO in reachable states:
    - `basis: equity`: a realised gain beside a floating loss over midnight leaves the equity high-water mark below
      the balance anchor;
    - `basis: balance`: floating losses are never measured.
  - **Owed:** a rule type (or a trailing `reset`/`reset_basis`) that captures the BALANCE high-water at each daily
    reset and measures EQUITY against it.
  - **Until it exists:** no FTMO 1-Step account may be attached.

**Corrected claim (audit F6): a declared capital anchors on the firm's line, which is not always stricter.**
- The rule type is new, and it HALTs at 1.0 exactly like existing platform rules. No shipped rulebook changes
  meaning, which a test proves.
- Attached ABOVE its declared capital, a static rule reads lower than a first-observed anchor would. That is faithful
  to the firm's static rule, and the lead accepted it with F3.
- The declared value is validated at load (item 8).

---

## Stage 6: explicit HALTs survive a restart (lead's P12D-75, from F2)

### What changed

Nothing wrote or read `halt_event` before: `RiskStore.record_halt` had no caller. ACIS-07 §7 lists "active halts"
among the restrictive state a restart must restore before the first evaluate.

**Write path** (`core/risk/halt_ledger.py`). `PersistentHaltSink` wraps the single upward edge. Every `apply_halt`,
`apply_session_halt` and `flatten` is written to `halt_event`. The DDL is unchanged: the kind rides in the opaque
`halt_id` as `<kind>|ts|scope|reason|<random>`.
- **Superseded by audit item 1 (F0/X2):** this stage first wrote BEFORE forwarding, so a failed write lost the halt
  itself. The guard now acts first and the write follows.
- **Superseded by audit item 11 (F9):** the id first ended at the reason, so a halt re-issued at the instant of a
  cleared row collided and was dropped.

**Boot** (`restore_on_boot` → `Guardrails.restore_state`). Every uncleared row is re-applied through the same edge,
same scope and reason, before the first evaluate, and the coalescing latches are set so the first check does not
re-issue. Two kinds need care:
- **A session halt** is re-applied with its ORIGINAL instant, so it lifts at the boundary it would have.
- **A flatten** is re-applied, so positions are closed again if the dead process had not finished.

Re-applying writes nothing new.

**Clear path** (`RiskMonitor.on_human_resume(human_token, now)`). Only this clears rows. It refuses a blank token.
The sink has no clearing verb: an agent that can reach it can halt, never unhalt.
- **Superseded by audit item 11 (X9/F10):** `cleared_by` was first a sha256 fingerprint of the token. It is now
  `human:<random resume id>`, with no bit derived from the token.
- **Superseded by audit item 10 (F8):** `Governor.resume` now reaches this path through its `resume_gate`, so a human
  resume is ONE call.

### Tests (`tests/integration/test_halt_restore.py`, real Governor behind the test-side edge)

- `test_equity_floor_halt_survives_a_restart_until_a_human_resumes`:
  - a fresh Governor is sized; after `restore_on_boot` it is halted and the orchestrator is frozen;
  - recovered equity does not lift the halt;
  - a blank token is refused;
  - a human resume clears it exactly as today;
  - a restart after the resume restores nothing.
- `test_an_agent_halt_is_reapplied_with_its_own_scope_and_reason`.
- `test_a_session_halt_lifts_at_its_own_boundary_after_a_restart`.
- `test_restoring_writes_nothing_twice_and_keeps_distinct_reasons`.
- `test_the_ledger_is_signed_with_a_random_resume_id_never_token_bits` (former
  `test_the_ledger_is_signed_by_a_token_fingerprint_never_the_token`, rewritten by audit item 11).

### Falsification (A16)

| Revert | Result |
|---|---|
| boot restores no halts | 3 failed |
| the sink persists nothing | 5 failed |
| a human resume does not clear the ledger | 2 failed |
| a session halt is restored as a plain halt | 1 failed |
| restore writes every halt again | at first **survived**: the test's clock was constant, so a re-written row had an identical id. The test now restarts at later clocks, as real restarts do, and the revert fails 1 |

### Residuals

- **R6-1: the production wiring is not built.** The runtime must:
  - wrap its edge adapter in `PersistentHaltSink`;
  - route the MCP control target's `apply_halt`/`flatten` through it;
  - build the Governor with `resume_gate=lambda token: monitor.on_human_resume(token, now)` (audit item 10).

  Owner: GAP-0091b.
- **R6-2: one resume clears every row.** This mirrors `Governor.resume`, which clears every scope. ACIS-07 §7's
  "a resume clears exactly the scope it names" is not what the Governor does today; that is pre-existing and unchanged.
- **R6-3: `on_human_resume` gained required parameters.** Its only production caller is the Governor's `resume_gate`.

**As first built, this stage LOOSENED two guards (audits F0/X2 and F1/X1).** A failed ledger write dropped the
equity breaker, and a stale session row muted later daily halts. Audit items 1, 2, 9 and 11 fix both. Every
restored halt is now the dead process's own, applied before it is recorded; clearing needs a human token.

---

## Stage 7: reduce-only closes trade the opposite side (lead's P12D-74, from F1)

**The convention** (the lead's delegated decision under the owner's delegation):
- a `SizedOrder` with `action="close"` NAMES the position to close; its `direction` is the position's side, exactly
  as the Governor emits it today;
- the orchestrator trades the OPPOSITE side, and fills and refusals carry that traded side;
- at every dispatch attempt, at the venue the attempt goes to, a close is checked against that venue's holding on the
  side it names:
  - it is capped at the holding (`EXEC_CLOSE_CAPPED`; the rest is a REJECTED report);
  - it is REFUSED when the venue is flat or holds the other side (`EXEC_CLOSE_REFUSED`).

A close can shrink |position|; it can never open, add to, or flip one. So the execution freeze admits only
reduce-only closes, and the spent-budget exemption needs no extra read (stage 2b's `_shrinks` is gone). Venue
capability filtering moved to `venue_limits.capable_venues`.

**Superseded by audit item 4 (X3/F4):** this stage's check read the holding and then sent a plain order, so two
concurrent closes could both pass the read and flip the position. Closes now go through the face's own atomic
`close_position` (see the audit round).

**Stricter, stated:** `test_frozen_blocks_opens_allows_closes` asserted that a "close" into a flat venue FILLED,
which meant a flatten could OPEN a position. That close is now REJECTED. The test also proves that a real close
under the freeze trades the other side and leaves the venue flat.

### Tests

- **Seam:** `test_governor_pair_exit_leaves_the_venue_flat` (real Governor and orchestrator; the pair exit that used
  to double both legs now flattens them).
- **Conformance, every adapter:**
  - `test_a_close_into_a_flat_venue_is_refused`;
  - `test_a_close_naming_the_other_side_is_refused_not_added`;
  - `test_a_close_larger_than_the_position_is_capped_never_flips`;
  - `test_spent_request_budget_refuses_opens_but_never_a_close`, updated to the convention.

### Falsification (A16)

| Revert | Result |
|---|---|
| a close is sent verbatim | 4 failed, incl. the seam test and the freeze test |
| no reduce-only check | 4 failed |
| no cap at the holding | 1 failed |
| `reducible` ignores the named side | 1 failed |

### Residuals

- **R7-1: one extra read per close attempt.** The reduce-only check calls `open_positions()` on each close attempt.
  The watchdog's direct broker flatten does not pass through it (it has no core imports).
- **R7-2: a hedging account must close by position ID.** A hedging account (cTrader can be one) holding both sides
  sums the named side; closing by position ID there is the ACIS-13 adapter's job.
- **R7-3: an unclosable remainder is reported, not closed.** A position that is not a whole number of lot steps
  (opened outside ACIS) keeps its sub-step remainder, reported as REJECTED. A close-by-position-ID adapter can close
  it fully (ACIS-13).

**No guard loosened versus `main`.** Every change refuses or shrinks a close. Under concurrency or on a hedging
venue, the check-then-act could still flip or open a position, which breaks this stage's own invariant (F4/X3).
Audit item 4 fixes it.

---

## Stage 5: the weekend flatten (master §9.5), built on stage 7's close path

**Why it waited.** The first pass left this stage as a design. The Governor's close path doubled positions (F1), and
a flatten built on it would have done the same. Stage 7 fixed that path, and this stage uses it.

### What changed

`CapitalGovernor.weekend_flatten(portfolio, now)` (logic in `core/governor/calendar_gates.py`):
- **Who.** It acts only on an account that may not hold over the weekend; an account allowed to hold is never touched.
- **When.** From the start of the pre-close entry ban until the Sunday open, through the closed window. The ban is
  the existing `weekend_entry_buffer_s`, 2 h; no new config key.
- **What.** Every open position gets an `action="close"` order naming it: its own side and size, with
  `reason="weekend_flatten"`. Both legs of a pair are closed and the group is retired from the registry.
- **Retries.** It is called every tick, so a close that fails is re-emitted. The stage-2 request budget never blocks
  a reduce-only close.
- **Surfaced.** A position still open once the market has closed is logged as `WEEKEND_FLATTEN_INCOMPLETE`, never
  ignored.

The exposure caps moved unchanged to `core/governor/exposure.py`, taking `capital_governor.py` from 447 to 437 (the
ratchet is lowered; 436 after the audit round).

**A narrower design choice than first drafted.** The first design proposed a separate `weekend_flatten_lead_s` key.
Reusing the entry ban's 2 h is leaner and stricter: positions close at the moment new entries stop, so no entry can
open after the flatten starts. A shorter, separate lead remains an owner option.

### Tests

- **`tests/unit/test_weekend_flatten.py`:**
  - it starts exactly at the ban, not a second earlier, in EDT and EST;
  - a weekend-allowed account is never flattened;
  - a position still open after the close is surfaced;
  - both legs of a pair are closed and the group retired.
- **Seam:** `test_weekend_flatten_leaves_the_venue_flat` (real Governor and orchestrator: the venue is FLAT an hour
  before the close).

### Falsification (A16)

| Revert | Result |
|---|---|
| it never flattens | 5 failed |
| closes carry the traded side instead of the position's | 3 failed, incl. the seam test (stage 7 refuses them, so the venue stays open) |
| the pair group stays registered | 1 failed |
| an unclosed position is never surfaced | 1 failed |
| the weekend-holding flag is ignored | 1 failed |

### Residuals

- **R5-1: nothing calls it yet.** The runtime's fast loop must call `governor.weekend_flatten(portfolio, now)` each
  tick and submit the closes (GAP-0091b). `WEEKEND_FLATTEN_INCOMPLETE` still needs surfacing on `acis://status`
  (ACIS-08).
- **R5-2: only FX closures are covered.** At this stage that meant only the Friday close; audit item 6 (X5) added
  the declared FX holidays. Per-instrument exchange calendars (index CFDs, metals holidays, daily breaks over 2 h on
  non-FX symbols) are not covered (same scope as R3-1).
- **R5-3: FTMO Standard's "shortly before the markets close" is met with a 2 h lead,** which is stricter. It is the
  same window as the entry ban.

**No guard loosened.** It only closes positions, through reduce-only closes, on accounts that may not hold them.

---

## The audit round (2026-09-25): eleven fixes, in the lead's order

Each item was falsified per A16. The scratch specs are `i1.json`…`i11.json`, in the scratchpad next to the audit
repros. Every revert was caught except one, and that survivor made its test stricter (item 4).

### 1. The guard acts first; recording never gates it (F0/X2; the lead's P12D-79), `be59c96`

- **Order.** `PersistentHaltSink` forwards the halt, session halt or flatten to the edge FIRST, then writes the
  row. A failed write is retried up to 3 times. It then stays pending in memory, is logged as
  `HALT_LEDGER_WRITE_FAILED` and is re-tried by `flush()` at the start of every `Guardrails.check`.
- **Latching.** The Guardrails latches are set only after the edge call returns. An edge call that raises is
  re-issued at the next check, never latched as done.
- **Bookkeeping.** `RiskStore.persist_evaluate` catches store errors after the guard has acted and logs
  `RISK_STORE_WRITE_FAILED`. The next evaluate writes the whole state again.
- **Tests:**
  - `test_the_equity_breaker_holds_when_any_store_write_fails`, at each of four write points: `record_halt`,
    `open_halts`, `write_snapshot`, `save_restrictive_state`;
  - `test_an_edge_call_that_fails_is_reissued_not_latched`.
- **Reverts caught (5 of 5):**
  - a failed write raises into the guard;
  - the row is written before forwarding (the old order);
  - the breaker latches before the edge;
  - the bookkeeping raises;
  - pending rows are never flushed.
- **Residual A1.** If the process dies while a row is still pending, that halt is not restored. A measured breach
  re-fires on the first evaluate; an explicit agent halt does not. The alarm must reach `acis://status` (ACIS-08, with
  GAP-0091b).

### 2. The session latch re-arms at the boundary; lapsed rows are never re-latched (F2 + F1/X1; P12D-80, P12D-78), `6826085`

- **In process.** A session halt latches until the next declared session boundary after its instant
  (`_session_until`, from `session_boundaries`). A breach after that boundary halts again.
  - On main, the latch lasts the process's life: the pre-existing F2.
- **At boot.** `restore_state(..., halts, now)` returns every session row whose boundary has already passed. The
  monitor closes each with `cleared_by = auto:session_boundary`, so it is never re-latched (F1).
  - An unexpired row is restored with its original instant, and so with its original expiry.
- **Tests:** in `tests/integration/test_session_halt_rearm.py`:
  - `test_a_breach_on_a_later_day_halts_again_in_one_process`;
  - `test_after_a_restart_the_next_day_a_fresh_breach_halts`;
  - `test_a_restart_inside_the_session_keeps_the_halt_until_its_boundary`.
- **Reverts caught (4 of 4):**
  - a process-lifetime latch;
  - a lapsed row re-latched at boot;
  - an expired row left open;
  - a restored row with no expiry.
- **Residual A2.** P12D-80 is pre-existing on `main`, which keeps the once-per-process latch until this branch merges.

### 3. A pair group is both legs or neither in execution (F11; P12D-81), `2efb7bb`

- **Groups.** `submit_group(legs, valid_for_seconds)` pre-checks every leg AFTER lot-step rounding:
  - a capable venue;
  - the minimum lot;
  - request budget for the whole group.

  If any leg fails, it sends none (`EXEC_GROUP_REFUSED`).
- **Lone legs.** `submit` refuses a pair leg sent alone (`EXEC_GROUP_LEG_ALONE`), so the runtime cannot bypass the
  group path.
- **Tests:** in `tests/integration/test_pair_group_atomicity.py`:
  - `test_a_leg_below_the_minimum_refuses_the_whole_group`: the audit's 1,500 + 900 legs leave the venue FLAT;
  - `test_a_pair_leg_sent_alone_is_refused`;
  - `test_a_group_the_venue_can_take_opens_both_legs`;
  - `test_a_group_is_refused_when_the_budget_cannot_send_both_legs`.
- **Reverts caught (3 of 3).**
- **Residual A3.** The pre-check covers what execution can know before sending. A venue that rejects the second leg
  AFTER the first filled still leaves one leg. The compensating close belongs to the runtime (GAP-0091b) and is not
  built here.

### 4. The close intent crosses the face as the venue's atomic close (X3/F4), `ab4b6df`

- **Contract.** `ExecutionFace.close_position(...)` is abstract, and every adapter must implement it. It is
  REDUCE-ONLY and atomic: it takes up to `units` off the named side's position and never opens, adds to or flips one.
  Nothing held gives `REJECTED`.
- **The mock** reads and acts as ONE step under an `asyncio.Lock`.
- **The orchestrator** sends every close through it. The engine-side cap and refusal stay as a second check.
- **Tests:**
  - in `tests/integration/test_atomic_close.py`:
    - `test_two_concurrent_closes_never_flip_the_position`;
    - `test_a_venue_stop_between_read_and_close_opens_nothing`;
    - `test_a_hedging_venue_never_ends_net_opposite`;
    - `test_close_position_is_reduce_only_on_the_shipped_mock`;
  - conformance, run for every adapter:
    - `test_close_position_on_a_flat_venue_opens_nothing`;
    - `test_close_position_naming_the_other_side_opens_nothing`;
    - `test_close_position_larger_than_the_holding_never_flips`.
- **Reverts caught (4 of 4).**
  - The first run of "no lock" SURVIVED, because the mock never yielded inside its critical section.
  - The mock now awaits once there, standing in for the venue round-trip, and the revert fails.
- **Residual A4.** The real mapping is ACIS-13's:
  - cTrader: `ProtoOAClosePositionReq` by `positionId`;
  - OANDA: `positionFill=REDUCE_ONLY`, or the position-close endpoint;
  - FIX: `PositionEffect=C`.

  The conformance tests bind each new adapter. Draft ACIS-06 wording is below.

### 5. WAL + synchronous=FULL for the risk store and the fill log (X4), `4e1e9be`

- **Stores.** Both stores open through `core/data/sqlite_wal.open_store`, which sets `journal_mode=WAL` and
  `synchronous=FULL`. A committed halt row, anchor or fill survives a power cut (the lead's P12D-76: the laptop's
  hard power-offs).
- **Tests:** `test_the_risk_store_is_wal_with_full_sync`, `test_the_fill_log_is_wal_with_full_sync`.
- **Reverts caught (3 of 3):** no WAL; synchronous NORMAL; the risk store opened directly.
- **Residual A5: the cost is not measured here.**
  - The parameter library and the provenance store already opened through this helper. On this Python build
    SQLite's default is already FULL (probed: `PRAGMA synchronous` = 2, before and after WAL), so for them the
    pragma pins the level rather than changing it.
  - The risk store and the fill log move from the rollback journal to WAL, with one fsync per commit.

### 6. The ban and the flatten key on every closure of 2 h or more, holidays included (X5), `4b5f150`

- **Calendar.** `FxCalendar` gains `holidays`. `config/instruments.yaml` `fx_default` declares 2025-12-25,
  2026-01-01, 2026-12-25 and 2027-01-01.
  - A holiday D is closed from the FX close on the day before D until the FX close on D.
  - `within_closure_buffer` applies the 2 h pre-close ban and the closed window to each holiday, as it does to the
    weekend.
  - `weekend_flatten` uses the same window.
- **The Governor** requires `holidays`.
- **Tests:** in `tests/unit/test_holiday_closures.py`:
  - `test_the_shipped_fx_calendar_declares_the_year_end_closures`;
  - `test_no_entry_opens_in_the_two_hours_before_a_holiday_closure`, which includes the audit's Thu 2026-12-24
    16:00 NY;
  - `test_a_no_holding_account_is_flattened_before_a_holiday_closure`;
  - `test_a_position_still_open_inside_a_holiday_closure_is_surfaced`, which includes Fri 2027-01-01.
- **Reverts caught (3 of 3).**
- **Residual A6.**
  - The holiday list is declared by hand. A year left undeclared silently has no holiday ban. A load check that the
    calendar covers the coming year would make that structural; it is not built.
  - FTMO's 2026 table is unpublished, so the audit's caveat applies.
  - Non-FX calendars are still R5-2.

### 7. A close the venue keeps refusing is paced, never blocked (X6/F5), `5d00372`

- **The pacer** is `core/execution/close_pacing.ClosePacer`. It keys each close on its (venue, instrument):
  - after n consecutive failures, the next close waits min(2 s · 2^(n−1), 300 s) after the last one;
  - a filled close resets n;
  - past 100 attempts in a rolling 24 h, every close waits the full 300 s.
- **Visibility.** A paced attempt is a `REJECTED` report and an `EXEC_CLOSE_PACED` log line.
- **Persistence.** Attempts go to an additive `close_attempt` table in the fill log and are re-read at boot.
- **Tests:** in `tests/integration/test_close_pacing.py`:
  - `test_a_refused_close_is_paced_not_resent_every_tick`;
  - `test_a_close_is_never_blocked_outright`;
  - `test_the_pace_survives_a_restart`;
  - `test_past_the_daily_ceiling_closes_go_at_the_slowest_pace`.
- **Reverts caught (4 of 4).**
- **Residual A7.**
  - The pacing constants are code constants, not guardrail values; the owner may move them to config.
  - At the 300 s floor, one (venue, instrument) adds at most 288 requests a day.
  - The open budget's restart seed is still a lower bound (R2-2).

### 8. `initial_capital` is finite and > 0; a typo is fatal at load (F6), `52c0aef`

- **Schema.** `Field(gt=0, allow_inf_nan=False)`. The `rulebook.py` docstring no longer claims a declared capital
  is always stricter.
- **Tests:**
  - `test_a_valid_initial_capital_loads`;
  - `test_a_typo_in_initial_capital_is_fatal_at_load`, over inf, nan, 0, a negative, a letter O for a zero and a
    misspelt key.
- **Reverts caught (2 of 2).**
- **Residual A8.** A positive but wrong value (600 for 6,000) still loads. Nothing checks the declared capital
  against the balance seen at attach. The owner's review of the rulebook commit is the check (R4-3). F6's "below
  the attach balance" part is accepted with F3.

### 9. A store-backed monitor evaluates only after its restore (F7), `9e39d32`

- **Guard.** `RiskMonitor.evaluate` raises `DataQualityError("boot", …)` until `restore_restrictive_state` has run,
  whenever a store is configured. Forgetting `restore_on_boot` now fails closed.
- **Tests:**
  - `test_a_store_backed_monitor_refuses_to_evaluate_before_its_restore`;
  - `test_a_monitor_without_a_store_evaluates_at_once`.
- **Reverts caught (2 of 2).**
- **Residual A9.** The runtime must call `restore_on_boot` (GAP-0091b).

### 10. Exactly one human-resume path, and it clears the ledger (F8), `da09bf7`

- **The Governor** requires a `resume_gate`. `CapitalGovernor.resume(token)` runs it BEFORE lifting anything. The
  production gate is `monitor.on_human_resume(token, now)`, which clears the ledger and re-arms the monitor. If the
  gate raises, nothing lifts.
- **Tests:**
  - `test_a_governor_resume_clears_the_ledger_so_a_restart_restores_nothing`;
  - `test_a_resume_whose_ledger_clear_fails_lifts_nothing`.
- **Reverts caught (2 of 2).**
- **Residual A10.** The test fixtures `mk_governor` and `paper_loop` pass a no-op gate; production has no default.
  The runtime's adapter behind the `ControlTarget.resume` protocol in `monitoring/tools.py` must call the Governor's
  resume and nothing else (GAP-0091b).

### 11. A random resume id (X9/F10), unique halt ids (F9), the claim drift (F12), `4f3ed0a`

- **X9/F10.** `cleared_by` is `human:<random 12-hex resume id>`, with no bit derived from the token.
- **F9.** Every `halt_id` ends in a random suffix. A halt re-issued at the instant of a cleared row is persisted. The
  open-row dedupe on (kind, scope, reason) is unchanged.
- **F12:**
  - the store's own blank-token refusal has a direct test;
  - the orchestrator docstring is corrected;
  - the `guardrails.py` line count is corrected in this report.
- **Tests:**
  - `test_the_ledger_is_signed_with_a_random_resume_id_never_token_bits`;
  - `test_the_store_itself_refuses_a_blank_resume_token`;
  - `test_a_halt_reissued_at_the_instant_of_a_cleared_row_is_persisted`.
- **Reverts caught (3 of 3).**
- **Residual A11.** F12's third point is base behaviour and stays unchanged: a missing or empty risk store boots
  with fresh anchors. Refusing to boot a funded account on an empty store is a runtime decision (GAP-0091b).

### 12. This report (X8 and the claims)

- **The claims:** the corrected claims are at the top and in stages 1, 2 and 4.
- **X8:** the FTMO date is fixed.
- **X7:** recorded as open (R4-7).

---

## Findings for the lead to file

Chat is not a record, and this builder may not edit `KNOWN_GAPS.md`.

**Two numbering schemes.** F1–F3 in the first three subsections are this builder's own first-pass findings. The
lead's messages and the stage headings cite them. The audits' F0–F12 (internal) and X1–X9 (external) are a separate
series, dispositioned in the last subsection.

### F1 (HIGH): Governor close orders ADDED to the position when executed. **Fixed by stage 7**

The close-direction contract is unspecified between ACIS-05 and ACIS-06.
- `CapitalGovernor.check_group_exits` (GAP-0040) emits `action="close"` orders that carry each leg's **own**
  direction.
- `ExecutionOrchestrator.submit` sends `order.direction` verbatim.

**Reproduction** (scratch script, real Governor and orchestrator, whole-unit mock venue): allocate a pair group, then
execute the group-exit closes.

| | EUR_USD | USD_JPY |
|---|---|---|
| after the opens | −441 | −486 |
| after the closes | **−882** | **−972** |

Both legs doubled instead of flattening. The same "close" also passes the post-flatten execution freeze, which
allows `action == "close"`: a group exit during a freeze would add exposure. The seam has never run, because no
runtime exists; `test_frozen_blocks_opens_allows_closes` submits a `close` with direction +1 into a flat venue and
only checks that it FILLED.

**Needed:**
- an owner/spec ruling on the convention (a close carries the position's direction and execution inverts it, or it
  carries the trade's direction and the Governor inverts it);
- the fix;
- a seam test asserting the venue is FLAT afterwards.

Mitigated here only where this batch had reach: the stage-2b budget exemption checks the venue position. The freeze
path was not changed (HALT-adjacent, human-owned).

**Blocked** the weekend flatten and any Governor-originated close, until stages 7 and 5 were built.

### F2 (MEDIUM): active halts were not restored at boot. **Fixed by stage 6**

ACIS-07 §7 lists "active halts" among the restrictive state a restart must restore. Explicit HALTs are written to
`halt_event` by `RiskStore.record_halt`, but nothing reads them back. After this batch, every *measured* breach
re-fires on the first evaluate. An explicit MCP/agent HALT and a latched session halt do not come back, which fits
GAP-0050's "a restart is never a relaxation" principle poorly.

### F3 (pre-existing): the code-shape gate is red on `main`

`core/optimizer/costs.py` (HEADER, BLOCK) and `scripts/cost_stress_ladder.py` (HEADER, BLOCK) are new violations
against `code-shape.baseline.json` at `bdd3a75`. This batch did not touch those files.
`core/data/feeds.py|HISTORY` can burn down 1→0 (left for its owner).

### Ledger map for this batch's gaps

- **GAP-P12D-55:** stage 1. Residuals R1-1 (GAP-0091b), R1-2 (ACIS-13). R1-3 was addressed by stage 6.
- **The lead's P12D-75 (F2):** stage 6. Residuals R6-1 (GAP-0091b), R6-2, R6-3.
- **The lead's P12D-74 (F1):** stage 7. Residuals R7-1, R7-2 and R7-3 (ACIS-13).
- **GAP-P12D-57:** stage 2 [impl] parts. The [spec] NAV-relative sizing stays open (GAP-P12D-61). Residuals R2-1,
  R2-2, R2-4, R2-5.
- **GAP-P12D-58:** stage 3 [impl] part, plus the weekend flatten (stage 5). The [spec] rulebook field and the news
  blackout stay open (R3-1). Residuals R5-1 (GAP-0091b, ACIS-08) and R5-2.
- **GAP-P12D-54:** the schema half (stage 4). The config half is the owner's commit of the draft (R4-3).
- **GAP-P12D-59:** the per-account day boundary is expressible and enforced for platform daily rules (stage 4). The
  pre-breach flatten and the engine daily-halt semantics stay owner-owned (R4-1, R4-2).
- **The lead's P12D-79:** audit item 1. Residual A1.
- **The lead's P12D-78 and P12D-80:** audit item 2. Residual A2, since P12D-80 is pre-existing on `main`.
- **The lead's P12D-81:** audit item 3. Residual A3 (GAP-0091b).
- **The lead's P12D-77 (the dual audit):** every finding is dispositioned below.

### The audits' findings (2026-09-25): dispositions

| Finding | Disposition | Where |
|---|---|---|
| F0 / X2: one failed ledger write lost the equity breaker | **Fixed** | item 1; residual A1 |
| F1 / X1: a stale session row muted later daily halts after a restart | **Fixed** | item 2 |
| F2: the session halt fired once per process (pre-existing) | **Fixed on this branch** | item 2; residual A2 |
| F3: after a restart while up, a later loss reads lower than main | **Accepted** by the lead as a delegated decision; faithful to the firm's static rule; the claim is corrected to "restart-invariant" | stage 1 and the top of this report |
| F4 / X3: a "reduce-only" close could flip, or open a hedge | **Fixed** | item 4; residual A4 (ACIS-13) |
| F5 / X6: closes could exceed the request budget without bound | **Fixed** (paced, never blocked) | item 7; residual A7 |
| F6: a declared capital below the attach balance lowers the static rule; a typo disabled it | **The typo is fixed** (fatal at load). **The lower reading is accepted** with F3; the docstring claim is corrected | item 8; residual A8 |
| F7: restore-before-evaluate was a convention | **Fixed** (fails closed) | item 9; residual A9 |
| F8: two resume verbs, only one cleared the ledger | **Fixed** (one path) | item 10; residual A10 |
| F9: a re-issued halt colliding with a cleared row's id was dropped | **Fixed** | item 11 |
| F10 / X9: `cleared_by` leaked 48 bits of the token hash | **Fixed** (random resume id) | item 11 |
| F11: rounding orphaned a pair leg | **Fixed** (both legs or neither) | item 3; residual A3 |
| F12: test gaps and claim drift | **Fixed**, except the empty-store boot, which is base behaviour and unchanged | item 11; residual A11 |
| X4: the stores were not power-loss durable | **Fixed** | item 5; residual A5 |
| X5: the ban and the flatten keyed only on the Friday close | **Fixed for FX** (declared holidays) | item 6; residual A6, R5-2 |
| X7: FTMO 1-Step's max loss has no safe encoding | **OPEN**: a rule type is owed; no 1-Step account may be attached until it exists | R4-7 |
| X8: the FTMO citation date was stale | **Fixed** (2026-09-24) | stage 4 and the test docstring |

---

## Spec amendment drafts (owner-owned: nothing in `ACIS_SPEC.md` or `specs/` was edited)

1. **Master §9, the `platform_rules.yaml` sentence.** In "drawdown limits with their exact measurement semantics
   (static vs trailing, intraday vs end-of-day anchor, balance- vs equity-based)", add: *"… or daily-reset at a
   declared local instant with the anchor's basis captured there; each limit a percentage of its anchor or of the
   account's declared initial capital"*.
2. **ACIS-07 §5 and §7:**
   - (a) A platform `daily` rule anchors its `reset_basis` at each local reset, on the larger of the observations
     that bracket it.
   - (b) Restart: *"the drawdown anchors (static, trailing high-water, daily day-open with its day)"* join the
     restored state. A rollover missed while down is bracketed the same way.
   - (c) A declared `initial_capital` anchors static rules and seeds trailing ones.
3. **ACIS-05 §5 and §7 step 1:**
   - §5: `weekend_entry_buffer_s` becomes *"no new entries this close to the weekend close, on every account, weekend
     holding allowed or not (GAP-P12D-58)"*.
   - §7.1: the guard becomes *"any account within `weekend_entry_buffer_s` of the weekend close, or inside the closed
     window → `(0,"weekend_ban")`"*.
   - Add step 9 (stage 5): *"On an account without weekend holding, from the start of the `weekend_entry_buffer_s`
     window until the Sunday open, `weekend_flatten(portfolio, now)` emits an `action="close"` order naming every open
     position (both legs of a pair; the group retired), every tick until flat. A position still open after the close
     logs `WEEKEND_FLATTEN_INCOMPLETE` for the human."*
4. **ACIS-06:**
   - §5 config gains `max_venue_requests_per_day` (required; per venue; rolling 24 h; every submit attempt).
   - §7 gains: *"quantities are sent in whole venue lot steps, rounded down; a sub-step remainder and any quantity
     below the venue's minimum lot are `REJECTED` FillReports; once the request budget is spent, opens are refused
     and only a close that shrinks the venue position is exempt"*.
   - §7 also gains, from audit item 7: *"a close is never blocked, but it is PACED. After n consecutive failed closes
     of one (venue, instrument), the next waits min(2 s · 2^(n−1), 300 s); past 100 attempts in a rolling 24 h,
     every close waits 300 s. Each paced attempt is a `REJECTED` report and an `EXEC_CLOSE_PACED` line."*
   - §10: the fill log gains an additive `close_attempt(venue, instrument, at, ok)` table, re-read at boot.
   - §7 also gains, from audit item 3: *"the legs of a pair group are sent by `submit_group`, all or none: every leg
     is checked after rounding (capable venue, minimum lot, request budget for the whole group) before any is sent.
     A pair leg sent alone is refused."*
   - C-EXE-6 becomes *"total filled ≤ sized; equal to sized less the reported sub-step remainder on a full fill"*.
   - Master §7.5's "rejected loudly, never emulated silently" then reads as satisfied by the reported remainder.
5. **The close convention (F1, built in stage 7).**
   - **ACIS-05 §4:** *"`action="close"` names the position to close: `direction` is that position's side and
     `size_units` the quantity to take off it. The Governor never emits the trade's side for a close."*
   - **ACIS-06 §2 guard, §7 and §8:** *"A close is REDUCE-ONLY. Execution trades the side opposite to the order's
     `direction`, and at each dispatch caps the quantity at the venue's holding on the named side, refusing it
     (`REJECTED`) when the venue is flat or holds the other side. A close can shrink |position| but never open, add
     to or flip one. The execution freeze admits only such closes."*
   - **ACIS-06 §4:** a FillReport's `direction` is the side TRADED; for a close it is opposite to the order's.
   - **ACIS-06 §3, the face (audit item 4):** *"`ExecutionFace.close_position(instrument, direction, units, …)` is
     the ONLY path a close takes to a venue. It is REDUCE-ONLY at the venue and atomic: it takes up to `units` off the
     position on the `direction` side and never opens, adds to or flips one; with nothing held on that side it
     returns `REJECTED`. Adapters carry the intent to the venue, never as a plain opposite-side order:
     - cTrader Open API: `ProtoOAClosePositionReq` by `positionId`;
     - OANDA v20: `positionFill=REDUCE_ONLY`, or the position-close endpoint;
     - FIX: `PositionEffect=C` (Close)."*
   - **ACIS-06 §13:** a new C-EXE-7 with the whole close contract, proven at the seam by
     `test_governor_pair_exit_leaves_the_venue_flat`, and per adapter by the three `test_close_position_*`
     conformance tests.
6. **ACIS-07 §7 (stage 6, as amended by audit items 1, 2, 9 and 11):** *"Every halt, session halt and flatten
   crossing the upward edge is applied FIRST and then persisted in `halt_event`. A failed write is retried and
   alarmed (`HALT_LEDGER_WRITE_FAILED`) and never undoes or delays the halt. A store-backed monitor refuses to
   evaluate until the ledger has been restored. At boot, every open row is re-applied through the same edge, with
   the same scope and reason, before the first evaluate. A session halt is restored with its original instant and
   lapses at its own session boundary; a row whose boundary has already passed is closed
   `cleared_by = auto:session_boundary`, never re-applied. Only a human resume clears any other row."*
   - §10: `halt_event.cleared_by` is `human:<random resume id>` or `auto:session_boundary`. No bit of it derives
     from the token. The opaque `halt_id` is `<kind>|ts|scope|reason|<random>`.
   - The risk store opens in WAL with `synchronous=FULL` (audit item 5), as the fill log does.
7. **ACIS-07 §7, the daily session halt (audit item 2, pre-existing F2):** *"a daily-drawdown session halt latches
   until the next declared session boundary after it fired; a breach after that boundary halts again."* Today's
   text implies this; the code on `main` latches for the process's life.
8. **ACIS-05 §7, one resume path (audit item 10):** *"`CapitalGovernor.resume(human_token)` is the only resume. It
   runs the Risk Monitor's `on_human_resume` first, which clears the halt ledger. If that raises, nothing
   lifts."* ACIS-08's `ControlTarget.resume` maps to it and to nothing else.
9. **Master §3.7 and ACIS-05 §7 step 1, holidays (audit item 6):** *"an FX calendar declares `holidays`. A holiday
   D is closed from the FX close on the day before D until the FX close on D. The pre-close entry ban and the
   no-holding flatten apply before, and through, every such closure exactly as at the weekend."* An annual
   obligation goes with it: declare the coming year's holidays before it starts (residual A6).
10. **Master §9, `platform_rules.yaml` (audit X7, not built):** a drawdown rule type that captures the BALANCE
    high-water at each daily reset and measures EQUITY against it, for FTMO 1-Step (R4-7).

## Governance notes

- **The gate needs its sibling directory.** `python scripts/governance_gate.py` resolves its checks from
  `../specs_constitution/checks/`, which is not inside a worktree. This batch ran the code-shape check directly by
  absolute path; after every stage it shows only F3's pre-existing violations. Falsification was done by hand per
  stage (evidence above), not by `falsify.mjs`.
- **Module budget (a tightening of the ratchet):**
  - `guardrails.py` leaves the grandfather list (283 lines at the end of the audit round);
  - caps are lowered from their values at `bdd3a75`: `monitor.py` 378 → 343, `venue.py` 378 → 318,
    `capital_governor.py` 448 → 436, `schemas.py` 622 → 581;
  - new modules, all under 300 lines and each opening with its invariants:
    - from the stages: `drawdown_series.py`, `usd_conversion.py`, `fill_store.py`, `venue_limits.py`,
      `config/rulebook.py`, `halt_ledger.py`, `core/governor/exposure.py`;
    - from the audit round: `core/risk/exposure_metrics.py`, `core/execution/reports.py`,
      `core/execution/boundary.py`, `core/execution/attach.py`, `core/execution/venue_quality.py`,
      `core/execution/close_pacing.py`;
  - `orchestrator.py` is at 293 lines. Stage 7 left it at exactly 300; the audit round extracted `reports.py` and
    `boundary.py` before adding the group and pacing paths;
  - the code-shape baseline lost `monitor.py`'s last BLOCK and HISTORY entries (stage 6). After the audit round the
    check still shows only F3's two pre-existing files.
- **Resumed after a power cut** (2026-09-25). The uncommitted stage-7 files were checked before continuing: each
  compiled, each diff was read end to end and found complete, and the stage-7 falsification and full suite were
  re-run before the commit.
