# BUILDER-3 report — prop-account tightening batch (2026-09-24/25)

**Status: BUILT — PENDING AUDIT.** A builder is a finder, not a clearer. Nothing here is ✅ until the two audits
have run and been triaged, and nothing here is merged: it lives on this branch only.

- **Branch:** `worktree-agent-a9e00713d15bb5082`, at `C:\Users\USER\Documents\Private\ClaudeInsights\Knowledgevault\acis\.claude\worktrees\agent-a9e00713d15bb5082`.
- **Base:** `main` at `bdd3a75`. The worktree was created at `7695ed0` and fast-forwarded to `bdd3a75` before any work.
- **Authority:** the owner's in-chat delegation, relayed by the lead ("proceed with the recommendations"). Every
  change is TIGHTENING-ONLY.
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
| 5. Weekend flatten | master §9.5 | not built: **design only**, see §5 | — | — | — |

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
- `guardrails.py` (236 lines) leaves the grandfather list;
- `monitor.py`'s cap drops from 378 to 368;
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
  Owner: GAP-0091b / GAP-0075.
- **R1-2: the downtime bracket is conservative, not exact.** It is never below either known sample, but the true
  value at the rollover is unknowable without the broker's balance history (GAP-P12D-55's other candidate fix). The
  ACIS-13 adapter can make it exact.
- **R1-3 (F2 below): active halts were not re-applied at boot. Addressed by stage 6.**
- **R1-4: the per-evaluate write cost is unmeasured.** It is one small transaction per evaluate (10 s cadence). The
  backtest replay does not construct a `RiskStore`, so it pays nothing.

**No guard loosened.** Every restored value is the dead process's own restriction, or stricter. The in-process
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
- **R2-5: the exemption assumes a netting account.** On a hedging account (cTrader can be one), closing is by
  position ID, which is the ACIS-13 adapter's job.

**No guard loosened.** Every new path refuses or shrinks; none adds size or requests. The one exemption, for closes,
is narrower than the brief's wording: only a position-verified de-risking close is exempt.

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

They follow FTMO's page (trading-objectives, modified 2026-05-13) exactly:
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

**No guard loosened.** The rule type is new, and it HALTs at 1.0 exactly like existing platform rules. The initial
capital only raises anchors. No shipped rulebook changes meaning, which a test proves.

---

## Stage 6: explicit HALTs survive a restart (lead's P12D-75, from F2)

### What changed

Nothing wrote or read `halt_event` before: `RiskStore.record_halt` had no caller. ACIS-07 §7 lists "active halts"
among the restrictive state a restart must restore before the first evaluate.

**Write path** (`core/risk/halt_ledger.py`). `PersistentHaltSink` wraps the single upward edge. Every `apply_halt`,
`apply_session_halt` and `flatten` is written to `halt_event` BEFORE it is forwarded, so a crash between the two can
only leave a recorded halt not yet applied, never the reverse. The DDL is unchanged: the kind rides in the opaque
`halt_id` as `<kind>|ts|scope|reason`, and the reason is part of the id so two halts at one instant never collide.

**Boot** (`restore_on_boot` → `Guardrails.restore_state`). Every uncleared row is re-applied through the same edge,
same scope and reason, before the first evaluate, and the coalescing latches are set so the first check does not
re-issue. Two kinds need care:
- **A session halt** is re-applied with its ORIGINAL instant, so it lifts at the boundary it would have.
- **A flatten** is re-applied, so positions are closed again if the dead process had not finished.

Re-applying writes nothing new.

**Clear path** (`RiskMonitor.on_human_resume(human_token, now)`). Only this clears rows. It refuses a blank token
and signs `cleared_by` with a sha256 fingerprint of the token, never the token itself. The sink has no clearing
verb: an agent that can reach it can halt, never unhalt.

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
- `test_the_ledger_is_signed_by_a_token_fingerprint_never_the_token`.

### Falsification (A16)

| Revert | Result |
|---|---|
| boot restores no halts | 3 failed |
| the sink persists nothing | 5 failed |
| a human resume does not clear the ledger | 2 failed |
| a session halt is restored as a plain halt | 1 failed |
| restore writes every halt again | at first **survived**: the test's clock was constant, so a re-written row had an identical id. The test now restarts at later clocks, as real restarts do, and the revert fails 1 |

### Residuals

- **R6-1: the production wiring is not built.** The runtime must wrap its edge adapter in `PersistentHaltSink`,
  route the MCP control target's `apply_halt`/`flatten` through it, and call `on_human_resume(token, now)` on the
  human resume path next to `Governor.resume`. Owner: GAP-0091b.
- **R6-2: one resume clears every row.** This mirrors `Governor.resume`, which clears every scope. ACIS-07 §7's
  "a resume clears exactly the scope it names" is not what the Governor does today; that is pre-existing and unchanged.
- **R6-3: `on_human_resume` gained required parameters.** Its only caller is a test.

**No guard loosened.** Every restored halt is the dead process's own; clearing needs a human token.

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
capability filtering moved to `venue_limits.capable_venues`; the orchestrator is at 300 lines.

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

**No guard loosened.** Every change refuses or shrinks a close; nothing adds exposure.

---

## §5 — Weekend flatten (master §9.5): DESIGN ONLY, deliberately not built

**Why not built.** The brief allows the design instead when the loop-owner seam is not ready, and it is not:
- no production loop owner exists yet (the three-loop runtime is GAP-0091b / GAP-0075);
- the flatten wiring (`HaltSink.flatten`) exists only test-side;
- the existing Governor close path is **defective** (F1 below).

A weekend flatten built on that path would, today, double the positions it means to close.

### The design, precise enough to build once F1 is settled

1. **Owner.** The Governor. §9.5 files weekend-holding bans among the downward, config-driven Governor overrides,
   not the Risk Monitor's upward flatten edge.
2. **Trigger.** Add a pure `weekend_flatten_due(now, week_close, week_open, lead_s) -> bool` in
   `core/governor/calendar_gates.py`. It is true from `close − lead_s` through the closed window until the Sunday
   open, in local `{zone, at}` terms.
3. **Lead time.** Add a new required key `governor.weekend_flatten_lead_s` (suggested 1,800 s). The schema enforces
   `0 < weekend_flatten_lead_s <= weekend_entry_buffer_s`, so no entry can open after the flatten starts.
4. **Orders.** Add `CapitalGovernor.weekend_flatten(portfolio, now) -> tuple[SizedOrder, ...]`. It emits orders only
   when `not rules.weekend_holding_allowed` and the flatten is due:
   - one `action="close"` order per open position, carrying the full position size;
   - both legs of a pair group, never one;
   - `reason="weekend_flatten"`, logged as `WEEKEND_FLATTEN{instrument, units}`;
   - emitted on every tick while positions remain, so a rejected close is retried. Retries are bounded by the stage-2
     request budget, which never blocks a verified close.
   `capital_governor.py` is at its cap (447), so the logic belongs in `calendar_gates.py` or a new module, with a
   thin method.
5. **Surfaced if impossible (§9.5).** If a position is still open 60 s before the close, or at the close, log
   `WEEKEND_FLATTEN_INCOMPLETE{instruments}` and surface it on `acis://status` for the human. It changes no HALT
   semantics.
6. **Loop owner.** On each fast-loop tick, submit `governor.weekend_flatten(portfolio, now)` through
   `ExecutionOrchestrator.submit`. Closes pass the execution freeze and the request budget.
7. **Tests.** A no-weekend account with a position:
   - at `close − lead − 1 s`: no orders;
   - at `close − lead`: a close for each position;
   - at the close with the position unfilled: INCOMPLETE is logged.
   Also: a weekend-allowed account gets none; a pair group closes both legs; EDT and EST; a seam test that the
   positions are **flat** at the venue after execution (this is what F1 breaks today).
8. **Spec.** Master §9.5 already mandates the flatten. ACIS-05 §7 needs a step (draft below).

---

## Findings for the lead to file

Chat is not a record, and this builder may not edit `KNOWN_GAPS.md`.

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

**Blocks:** the weekend flatten (§5 above) and any Governor-originated close.

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
- **GAP-P12D-58:** stage 3 [impl] part. The [spec] rulebook field, the news blackout and the weekend flatten stay
  open (R3-1, §5).
- **GAP-P12D-54:** the schema half (stage 4). The config half is the owner's commit of the draft (R4-3).
- **GAP-P12D-59:** the per-account day boundary is expressible and enforced for platform daily rules (stage 4). The
  pre-breach flatten and the engine daily-halt semantics stay owner-owned (R4-1, R4-2).

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
   - Add step 9 (the weekend flatten, §5 above) once F1 is ruled on.
4. **ACIS-06:**
   - §5 config gains `max_venue_requests_per_day` (required; per venue; rolling 24 h; every submit attempt).
   - §7 gains: *"quantities are sent in whole venue lot steps, rounded down; a sub-step remainder and any quantity
     below the venue's minimum lot are `REJECTED` FillReports; once the request budget is spent, opens are refused
     and only a close that shrinks the venue position is exempt"*.
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
   - **ACIS-06 §13:** a new C-EXE-7 with that contract, proven at the seam by
     `test_governor_pair_exit_leaves_the_venue_flat`.
6. **ACIS-07 §7 (stage 6):** *"Every halt, session halt and flatten crossing the upward edge is persisted in
   `halt_event` before it is forwarded, re-applied at boot through the same edge (same scope and reason; a session
   halt with its original instant) before the first evaluate, and cleared only by a human resume, which signs it with
   a token fingerprint."* §10: `halt_event.cleared_by` is `human:<fingerprint>`, never the token.

## Governance notes

- **The gate needs its sibling directory.** `python scripts/governance_gate.py` resolves its checks from
  `../specs_constitution/checks/`, which is not inside a worktree. This batch ran the code-shape check directly by
  absolute path; after every stage it shows only F3's pre-existing violations. Falsification was done by hand per
  stage (evidence above), not by `falsify.mjs`.
- **Module budget (a tightening of the ratchet):**
  - `guardrails.py` leaves the grandfather list;
  - caps are lowered: `monitor.py` 368, `venue.py` 342, `capital_governor.py` 447, `schemas.py` 581;
  - new modules, all under 300 lines and each opening with its invariants: `drawdown_series.py`,
    `usd_conversion.py`, `fill_store.py`, `venue_limits.py`, `config/rulebook.py`;
  - `orchestrator.py` is at 299, near the 300-line budget.
