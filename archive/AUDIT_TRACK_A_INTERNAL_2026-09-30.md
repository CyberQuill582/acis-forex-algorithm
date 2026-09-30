# Track A steps 3–5 audit, the INTERNAL lens (spec against code, code against itself). 2026-09-30

- **Brief:** `AUDIT_BRIEF_TRACK_A_2026-09-30.md`, pinned before launch (A4).
- **Under audit:** commit `86ea8d3` (the cTrader adapter, the three-loop runtime, feed reconnect). The pin commit `62a92a2` adds only the brief and a TODO line (`git diff --stat 86ea8d3 62a92a2`), so the code the server ran is byte-identical to `86ea8d3`. Line numbers below are at `86ea8d3`.
- **Auditor:** Claude Opus 5.5 (`claude-opus-5-5[1m]`), fresh context, internal lens. I launched no agents and did not use the web. I am a **finder, not a clearer** (A5): nothing here clears anything, and a clean section is not a sign-off.
- **Method:** I read the audited state from a `git archive 86ea8d3` extract (read-only). Every run went to the Google compute server (`acis-compute-1`, my own checkout, Python 3.11.2) through `remote_audit_ta.sh internal`, with `-n 8` at most. The probes are `p01`–`p20` in the session scratchpad, `…/scratchpad/audit_ta/internal/probes/` (called `<probes>/` below; `_ta.py` and `_rt.py` are shared scaffolding that builds the production classes against the repo's own fake venue, `tests/ctrader_fixtures.py`). Each finding restates its reproduction inline so it survives the scratchpad.
- **The authority:** `ACIS_SPEC.md` v2.25, `specs/ACIS-13-VENUE_ADAPTERS.md` v1.1, ACIS-05 v1.6, ACIS-06/07/08, and the `KNOWN_GAPS.md` entries the brief names.

## Executive summary

**19 findings: 4 high, 10 medium, 5 low.**

The lead's claims, re-verified:

| Claim | Verdict | Evidence |
|---|---|---|
| Full suite at `86ea8d3`: 1168 passed, 6 skipped | **Holds** | 1168 passed, 6 skipped in 188 s (`-n 8`) |
| On the phase-7 market the runtime sends ONE open, protected by its stop | **Holds** | `test_the_phase7_market_makes_one_position_with_its_stop_not_a_firehose` passes; P04 also shows one paper open |
| Paper never sends to the venue; practice reaches only a practice-eligible demo | **Holds**, one caveat | `route_to` (wiring.py:99-104) and the ModeController gate; the only venue orders in paper mode are SYNCING's protective closes of unprotected ACIS positions (ctrader_sync.py:187-192) |
| Every fill (solicited, venue-made, recovered at restart, missed while down) reaches Risk exactly once | **Refuted** | TAI-05 (restart: a recovered open counted twice, a missed stop-out becomes a phantom), TAI-08 (a late ack: the fill never reaches Risk, then is counted twice), TAI-09 (a stale close part: the fill reported twice), TAI-04 (a stop-repair error: the fill never reported) |
| The runtime's request spend stays inside ACIS-13 §6.5's feasibility budget | **Refuted** | TAI-01 (a round trip costs 4 requests, the formula budgets 2: the A9-certified day reaches the reserve), TAI-02 (reconnect and restart loops spend auth requests without bound: 1,993 used of a 20 budget) |
| No module under audit is over 300 lines; `ledger_check.py` green | **Holds, with a note** | Every new module is ≤ 297 lines. `capital_governor.py` is 434 (grandfathered, shrank 436 → 434, the ratchet passes). `ledger_check.py`: 268 entries, 0 violations. The spot-check fails: TAI-01..TAI-17 are owned by no entry, and two open entries are stale (TAI-19) |

The three most serious:

1. **TAI-01 (high): in the close reserve no orchestrated close reaches the venue, and the equity breaker goes blind.** The orchestrator's reduce-only pre-check reconciles as a `query`, which the meter refuses once `used ≥ budget − reserve`. So every exit, flatten and equity-floor flatten raises `BudgetRefused` and halts the engine. The account poll that feeds the equity breaker is a `query` too. ACIS-13 §6.5 reserves exactly those last 100 requests for closes. The reserve is reachable: A9 certifies 50 orders a day at 2 requests per round trip, and a real round trip costs 4. The repo's own test of the rule calls the face directly and skips the production path.
2. **TAI-02 (high): the request budget does not bound reconnects or restarts.** `auth` is an exit class and is never refused. A venue that refuses authorisation, or an access token invalidated server-side, makes the reconnector re-authorise forever (1,993 used against a budget of 20 in 1.5 s, no refresh, no detach), although A3 calls that fatal. In the reserve, the reconnect's own `subscribe` raises `BudgetRefused` out of the task: a stall, exit 1. The attach then raises `BudgetRefused` uncaught: exit 1 again. The engine unit restarts on exit 1 every ~5 s, and each start spends 3 unrefusable auth requests, so the count never drains.
3. **TAI-05 (medium, it refutes the exactly-once claim): a restart reconciles Risk BEFORE the recovered and missed fills reach it.** `boot()` adopts the venue's book into an empty Risk, then `run()`'s `venue_fills` task replays the queued reports on top. An open in flight at the crash is held twice (2,000 vs the venue's 1,000, at a fabricated average of 1.05, and it trips a spurious `cluster_cap` halt). A stop that fired while the engine was down becomes a phantom short the venue does not hold. ACIS-13 A7 orders the opposite: "one FillReport before reconciliation". The adapter tests stop at the face's queue, so none sees it.

The other high findings:
- **TAI-03:** `config/watchdog.yaml` still selects the MOCK flatten plugin. On silence with open positions it logs `WATCHDOG_FLATTEN` and closes nothing.
- **TAI-04:** a venue error during the stop repair leaves a filled, UNPROTECTED position that Risk never hears of. Nothing in the running engine repairs it (C-VEN-2).

## Findings

### TAI-01: in the close reserve no orchestrated close reaches the venue, and the equity breaker reads a frozen account
- **Severity:** high · **Likelihood:** medium (reachable at the A9-certified order allowance; lower for a demo that trades rarely)
- **Where:**
  - `core/execution/boundary.py:60`: `reduce_only_at` calls `face.open_positions()` before every close.
  - `core/execution/ctrader_face.py:243`: `open_positions` reconciles with `req_class="query"`.
  - `core/data/ctrader/meter.py:27,70-75`: `query` is not in `EXIT_CLASSES`, so it is refused at `used ≥ budget − reserve`.
  - `core/execution/ctrader_account.py:44-46`: the account snapshot is two `query` requests.
  - `core/runtime/executor.py:71-74`: the `BudgetRefused` becomes `EXECUTOR_ITEM_FAILED` and `halt("all", "executor_error")`.
  - `core/execution/ctrader_attach.py:77-78`: A9 counts `2 * max_orders_per_day`.
- **The authority:** ACIS-13 §6.5 (line 306): "The last `close_reserve` requests … may be spent **only** on closes, flatten, stop repair … and the reconciles those need"; (line 309) "Exits are never starved by entries". Line 315: `order_allowance` is `max_orders_per_day × 2`, "an open and a close each".
- **Reproduction (`<probes>/p01_reserve_starves_closes.py`, `p18_round_trip_cost.py`):**
  - Setup: 893 requests already in the day, then the start (3 auth), one orchestrated open (897), three polls (900).
  - `orchestrated close RAISED: BudgetRefused - VENUE_BUDGET_OPEN_EXHAUSTED: query with 900/1000 used`; `CLOSE_POSITION_REQ sent: 0`; the venue position stays open.
  - `account poll … RAISED: BudgetRefused`, so in practice mode Risk judges the last poll indefinitely (the equity floor included).
  - The same close through the Executor gives `EXECUTOR_ITEM_FAILED` and `halts: [('all', 'executor_error')]`, and it is re-issued every tick with the same result.
  - `face.close_position` called directly: FILLED 1000. That direct call is what the repo's `test_the_budget_reserve_refuses_opens_but_never_a_close` exercises, so that test is hollow for the production path (A16).
  - p18: `open: NEW_ORDER_REQ 1 | close: RECONCILE_REQ 2, CLOSE_POSITION_REQ 1`, so **one round trip = 4 requests**. A9's projection with 50 orders is 860 ≤ 900 (passes); at the real cost it is 960 > 900.
- **Proposed fix:**
  - Make the reduce-only pre-check free of budget risk: either meter the close path's reconcile as `protect`, or let `reduce_only_at` use the face's own reconcile inside `close_position` (it already caps at the holding) and drop the duplicate reconcile.
  - Decide explicitly (spec, owner) whether the account poll that feeds the equity breaker belongs in the reserve. As written, the breaker is blind exactly when the budget is tight.
  - Correct A9 to the measured cost per round trip (and per stop repair).
  - Add a test that closes through the ORCHESTRATOR in the reserve.

### TAI-02: the request budget does not bound reconnects or restarts: auth is never refused, and the loops that spend it never end
- **Severity:** high · **Likelihood:** medium (a revoked app, a token invalidated by a re-grant, or any restart once the reserve is reached)
- **Where:**
  - `core/data/ctrader/meter.py:27,70-71`: `auth` is an exit class and always admitted, even over the budget.
  - `core/execution/ctrader_reconnect.py:47-77`: every `VenueError` is retryable, forever, at the cap. `BudgetRefused` is not caught (`:64-72`), so a refused `feed.subscribe` (`:62`) or a refused `find_order` in `synchronise` ends the task with an exception, which `engine.py:186-195` treats as a stall (flatten, halt, exit 1).
  - `core/execution/ctrader_attach.py:114-120`: only `AuthRefused` is caught around `session.start()`. A `VenueError` from it, or a `BudgetRefused` from `TRADER_REQ` (`:120`), escapes `main()`: exit 1.
  - `deploy/systemd/acis-engine.service:29-33`: `Restart=always`, `RestartSec=5`, and only 2 and 3 are prevented.
  - `core/data/ctrader/session.py:178-185`: `_authorise_binding` re-raises `CH_ACCESS_TOKEN_INVALID` rather than refreshing.
  - The docstring `ctrader_reconnect.py:13` says "the persisted request budget still bounds them". It does not.
- **The authority:**
  - ACIS-13 §6.6 (line 324): "Reconnect attempts spend budget and count in the feasibility check."
  - §7.1 A3 (line 341): `CH_ACCESS_TOKEN_INVALID` or `OA_AUTH_TOKEN_EXPIRED` leads to a refresh; "Any other auth error is fatal."
  - §6.5: at or over the budget only reduce-only closes and stop repair pass, "paced by … C-EXE-8".
  - The unit's own comment: "a restart loop would only spend the venue's request budget".
- **Reproduction:**
  - `p13_auth_retry_unbounded.py`: the venue answers the application auth with `CH_CLIENT_AUTH_FAILURE` after a drop. Result: `attempts so far: 1886 | task done: False | state: APP_AUTH`, `used_24h now: 1889 of budget 20`, `VENUE_UNREACHABLE: 1`, `VENUE_ACCOUNT_DETACHED: 0`.
  - `p13b_token_invalid_retry.py`: the access token is invalidated server-side. Result: `used_24h now: 1993 of budget 20`, 2 auth requests per attempt, `REFRESH_TOKEN_REQ ever sent: False`, never detached.
  - `p02_reconnect_in_reserve.py`: at 900 used, the drop, re-auth and SYNCING spend 5 requests (905). Then `reconnect task ENDED WITH: BudgetRefused - … subscribe with 905/1000 used`: the runtime's stall path, exit 1. The session is READY with no spot subscription.
  - `p03_restart_loop_budget.py`: five real process starts of `core.runtime.__main__.cli(["--venue", …])` against the fake venue, with 900 requests already in the persisted ledger. Each start: `exit status 1 | BudgetRefused: VENUE_BUDGET_OPEN_EXHAUSTED: query …`. `used_24h` goes 903 → 906 → 909 → 912 → 915, and the ledger holds `auth 15`. Under the unit that is one start per ~5 s plus start-up, forever, because every start adds 3 to a window that therefore never drains.
- **Proposed fix:**
  - Give reconnects and starts a budget of their own: a persisted per-24 h ceiling of connects, which A9 then counts honestly.
  - Implement A3: a refresh on `CH_ACCESS_TOKEN_INVALID`/`OA_AUTH_TOKEN_EXPIRED`, and a detach (terminal) on any other auth error.
  - Catch `BudgetRefused` in the reconnector: stay down and wait for the window, do not raise.
  - Map an attach that cannot proceed for budget or venue-error reasons to a non-restarting exit status (add it to `RestartPreventExitStatus`), or add `StartLimitIntervalSec`/`StartLimitBurst` so a crash loop stops.
  - Correct the docstring.

### TAI-03: the watchdog as committed flattens nothing at the venue and records that it did
- **Severity:** high · **Likelihood:** medium (certain if the engine unit is enabled per the runbook without a further, unrecorded human edit)
- **Where:**
  - `config/watchdog.yaml:9-10`: `platform: mock`, `flatten_plugin: mock`.
  - `scripts/acis_watchdog.py` `MockFlattenPlugin.flatten_all` returns `ok=True, positions_closed=1` without contacting anything.
  - `scripts/acis_watchdog.py` `_ctrader_plugin` needs `environment` and `ctid_trader_account_id`, which the yaml lacks.
  - `docker-compose.yml:15-26`: the watchdog container mounts only `acis-logs`, so it cannot read the engine's token store (`/app/data/venue/ctrader_tokens.json`), and it has no `ACIS_CTRADER_*` environment.
  - No TODO or ledger entry owns switching the watchdog to the cTrader plugin (searched `TODO.md` and `KNOWN_GAPS.md`).
- **The authority:** master §8.6 layer 2 ("flattens via the broker API directly and records `WATCHDOG_FLATTEN`"); ACIS-13 §7.9.
- **Reproduction (`p12_watchdog_config.py`):** with the committed yaml, a beat with 2 open positions followed by silence gives `silence with open positions -> flatten` and the log `WATCHDOG_STALE {"open_positions": 2}`, then `WATCHDOG_FLATTEN {"positions": 1}` from `MockFlattenPlugin`, with no venue contacted. Setting only `flatten_plugin: ctrader` fails with `KeyError 'environment'`.
- **Proposed fix:**
  - Record the human step in TODO (the watchdog yaml keys, and its env file with the three `ACIS_CTRADER_*` variables) as a precondition of enabling the engine unit.
  - Make the watchdog REFUSE to start with the mock plugin when the engine's heartbeat reports a non-paper mode, or at least log it as a critical alert rather than a flatten.
  - Mount the token store read-only into the watchdog container.

### TAI-04: a venue error during the stop repair leaves a filled, unprotected position that Risk never hears of, and nothing in the running engine repairs it
- **Severity:** high · **Likelihood:** low (it needs the venue both to rest no stop, the [F-15] case, and to refuse the amend)
- **Where:**
  - `core/execution/ctrader_sync.py:83-109`: `ensure_stop` sends `AMEND_POSITION_SLTP_REQ` (`:98`) and the fallback `CLOSE_POSITION_REQ` (`:105`) with no error handling.
  - `core/execution/ctrader_face.py:131-133`: `_finish()` marks the fragment TERMINAL before `_protect()`, so a `VenueError` there loses the report and leaves no in-flight row for SYNCING to recover.
  - `core/runtime/venue_link.py:56-67`: the periodic reconcile adopts positions and never checks their stops. Only `synchronise` step 4 (`ctrader_sync.py:187-192`) closes an unprotected ACIS position, and that runs only at a start or a reconnect.
- **The authority:** ACIS-13 §7.3 step 6 (line 408): "ACIS never holds an unprotected position" (C-VEN-2).
- **Reproduction (`p09_stop_repair_error.py`):** practice mode, `behaviour = ["no_stop"]`, and the amend answered `TRADING_BAD_STOPS`.
  - `executor: ["VenueError('TRADING_BAD_STOPS')"]`.
  - `venue holds: [('EUR_USD', '1000', 'stop', None)]`; `Risk holds: () | in-flight rows: []`.
  - After two periodic reconciles the venue still holds it with `stop None`, `closes sent: 0`, and Risk holds `('EUR_USD', '1000', None)`, adopted.
  - The heartbeat's `open_positions` stays 0 until that adoption, so a watchdog in that window reads "stale but flat" and does not flatten.
- **Proposed fix:**
  - Make `ensure_stop` total: catch `VenueError`/`TimeoutError` on the amend, and fall through to the close.
  - If the close fails too, return the open's report anyway (it filled) and raise a flatten over the edge for that instrument.
  - Have the periodic reconcile run the same stop check as SYNCING step 4.
  - Return the fill report before, or independently of, the repair's outcome.

### TAI-05: at a restart, Risk is reconciled BEFORE the recovered and missed fills reach it: a crashed open is held twice, and a stop-out while down becomes a phantom position
- **Severity:** medium · **Likelihood:** medium (every restart with an order in flight, or with a venue fill during the downtime)
- **Where:**
  - `core/execution/ctrader_sync.py:151-182`: steps 1–2 queue the recovered and missed reports on `router.unsolicited`.
  - `core/runtime/__main__.py:82` and `core/runtime/engine.py:167-177`: `boot()` calls `risk.reconcile_on_restart(venue positions)` on an EMPTY Risk (positions are not persisted) and adopts the venue book.
  - `engine.py:160-163`: only `run()`'s `venue_fills` task drains the queue into `risk.ingest`, on top of the adoption.
- **The authority:** ACIS-13 §7.1 A7 (line 352): "a stop-out while ACIS was down becomes one `FillReport` before reconciliation and a crashed open's fill is never reported twice". The lead's exactly-once claim.
- **Reproduction (`p05_restart_order.py`):**
  - (A) The open's reply is lost and the process dies; restart. The synchronise finds the venue position (1,000) and queues 1 report. After `boot()`: Risk 1,000 (adopted). After `run()`: `Risk [('EUR_USD', 1, '2000', 1.05)]` against venue truth 1,000. Halts: `cluster_cap` (spurious, from the doubled exposure) and `restart_drift`.
  - (B) The stop fires while the engine is down; restart. The synchronise finds venue positions `[]` and queues 1 report. After `boot()`: Risk `[]`. After `run()`: `Risk [('EUR_USD', -1, '1000', 1.0885)]`, a short the venue does not hold, with no halt until the next periodic reconcile (≤ 900 s).
  - The adapter tests `test_an_open_in_flight_at_the_crash_is_reported_once_under_its_own_order` and `test_a_stop_that_fires_while_acis_is_down_reaches_risk_once_at_restart` assert only the face's queue, never Risk after boot.
- **Proposed fix:** at boot, drain the face's queued SYNCING reports before `reconcile_on_restart`, or discard them at a restart. Risk's pre-crash book is not persisted, so venue truth is the whole story, and replaying fills on top double-counts. Either way, add a runtime-level restart test asserting Risk equals venue truth after `run()` starts.

### TAI-06: paper mode on the venue's prices (the engine unit's default, and where every supervised restart returns) halts everything on its first paper position
- **Severity:** medium · **Likelihood:** high
- **Where:**
  - `core/runtime/wiring.py:111-114`: the `reconcile` task runs whenever a venue is attached, in every mode.
  - `core/runtime/venue_link.py:56-67`: it compares the VENUE's positions with Risk's, but in paper mode Risk books the PAPER venue's fills.
  - `core/risk/monitor.py:315-343`: any difference adopts the venue's book and halts all.
  - The engine unit's `ExecStart` (`acis-engine.service:27`) is exactly this mode.
- **The authority:** master §7.5 (paper mode is the paper venue's world); the declared choice "a periodic reconcile drift is adopted and halts everything" presumes Risk and the venue describe the same account.
- **Reproduction (`p04_paper_on_venue_reconcile.py`):**
  - Paper mode with the venue attached, `route_to` is the paper orchestrator, and the phase-7 market; `paper opens submitted: 1 | venue NEW_ORDER_REQ: 0`.
  - Then `RESTART_RECONCILE drift … 'broker': {}, 'internal': {'EUR_USD': [1, '1000.00']}`, and `Risk positions now: ()` while the paper venue still holds 1,000 with its resting stop at 1.08996.
  - `open halts: [('halt', 'all', 'restart_drift')]`. When that paper stop later fires, Risk books a phantom opposite position.
  - The only runtime test with a venue sets `reconcile_s=1e6`.
- **Proposed fix:** reconcile against the venue only in practice (or live) mode. In paper mode, reconcile Risk against the paper venue, or not at all.

### TAI-07: no human resume path exists in the runtime, so every halt is permanent
- **Severity:** medium · **Likelihood:** certain (every restart with a venue position writes `restart_drift`; TAI-01/04/08/09 write `executor_error`)
- **Where:**
  - The one human resume is `RuntimeControl.resume` (`core/runtime/halt_edge.py:62-65`), reached only through `ControlTools.call_tool("acis_resume")` (`monitoring/tools.py:137-139`).
  - The runtime builds `ControlTools` only inside `enter_practice` (`core/runtime/__main__.py:97-107`), for `acis_set_mode`. No transport exists (GAP-P12D-08).
  - `python -m core.runtime` has no resume option.
  - `restore_on_boot` re-applies every uncleared row at every start.
- **Contradicted:** `KNOWN_GAPS.md:159` (GAP-P12D-131 (h), "halts everything until a human resumes") and GAP-0020's residual assume a resume exists. The only way out is editing `data/runtime/risk.db` by hand, which bypasses the ledger's human-resume record (`cleared_by = human:<id>`).
- **Reproduction (`p15_no_resume_path.py`):**
  - After a halt and a restart on the same root: `{'all': 'restart_drift'}` and `open halt rows: [('halt', 'all', 'restart_drift')]`.
  - Engine CLI options: `--root, --account, --venue, --practice, --ack-guardrail, --ack-rulebook, --print-hashes, --mock-ticks`.
  - Code that can call a resume: only `halt_edge.py:63` and `monitoring/tools.py:139`.
- **Proposed fix:** a human-token resume at the engine's terminal (the `enter_practice` pattern: `getpass`, the verifier, `ControlTools.call_tool("acis_resume")`) until GAP-P12D-08's transport lands. Record the gap in GAP-P12D-131.

### TAI-08: an order-ack timeout raises `TimeoutError`, not `ConnectionError`: the orchestrator never searches, the fill is orphaned, adopted at the next reconcile, then counted twice at the next SYNCING
- **Severity:** medium · **Likelihood:** low-medium (a slow venue reply; `order_ack_timeout_s` and `request_timeout_s` are both 10 s)
- **Where:**
  - `core/execution/ctrader_face.py:119,130` and `core/data/ctrader/session.py:122-126`: the face raises `asyncio.TimeoutError`.
  - `core/execution/orchestrator.py:289`: the orchestrator catches only `ConnectionError`.
  - The executor then halts all (`executor.py:71-74`). The tracker stays registered, so the late fill event is claimed by it (`ctrader_events.py` `_claim`) and never becomes a report.
- **The authority:** ACIS-13 §7.3 step 6 (line 400): "Timeout … do not resend. Raise `ConnectionError`, as the ACIS-06 contract does. When the orchestrator retries with the same `fragment_id`, the face … first searches the venue".
- **Reproduction (`p08_ack_timeout_orphan.py`):**
  - Practice mode, reply dropped: `executor: ['TimeoutError()']`; venue holds `('EUR_USD', 1, '1000', 1.09)`; `Risk holds: () | unsolicited queued: 0`; the fragment row stays SENT.
  - After the periodic reconcile: `Risk holds: [('EUR_USD', 1, '1000', 1.0, None, None, 'unknown:reconciled')]`, halts `executor_error, restart_drift`.
  - After the reconnect's SYNCING: `Risk holds: [('EUR_USD', 1, '2000', 1.05)]` against venue 1,000.
  - `test_a_lost_reply_is_found_by_search_never_resent` calls the face twice by hand. The orchestrator never makes that second call.
- **Proposed fix:** have the face raise `ConnectionError` on an ack timeout (as §7.3 says), so the orchestrator's attempt 2 runs the face's own search. Make SYNCING's recovered report and any adoption mutually exclusive (see TAI-05).

### TAI-09: a close whose request errors stays SENT, and SYNCING later "recovers" ANOTHER close's order: the fill is reported twice
- **Severity:** medium · **Likelihood:** low (it needs a venue error on the close request, then a later close of the same position before the next SYNCING)
- **Where:**
  - `core/execution/ctrader_face.py:226-227`: the part is recorded SENT, then a `VenueError` from the request propagates uncaught.
  - `core/execution/ctrader_sync.py:153-154`: SYNCING step 1 searches a close part with `is_close_of(o, pid)` alone. `resume_close` (`:131`) also applies `int(o["orderId"]) not in known`.
  - The same uncaught `VenueError` (`POSITION_NOT_FOUND` when the stop fires between the face's reconcile and its close, `MARKET_CLOSED`, a rate limit) halts the whole engine via `executor.py:74`.
- **The authority:** ACIS-13 §7.3 step 6 (line 400): "an unknown outcome is searched as the MARKET closing order on that position, skipping any order already recorded as ACIS's".
- **Reproduction (`p06_stale_close_part.py`):**
  - Close c1 → `VenueError REQUEST_FREQUENCY_EXCEEDED`, store row `c1#0: ('SENT', None, …)`.
  - Close c2 fills 1,000 (`fill_id ct:ctrader:demo:4242:close:c2`); venue flat.
  - A reconnect's SYNCING then queues `[('oc1', -1, '1000', 'ct:ctrader:demo:4242:103')]`, logged `VENUE_RECOVERED_FILL {'fragment_id': 'c1#0'}`. Order 103 is c2's. The fill_ids differ, so the orchestrator's dedup (`reports.py:49-62`) lets it through, and Risk books a second 1,000 sell on a flat book.
- **Proposed fix:**
  - Apply the `known` filter in `synchronise` step 1 as in `resume_close`.
  - Catch `VenueError` in `_close_part`: mark the part terminal-refused, return a REJECTED report, and leave pacing to `ClosePacer`, not a global halt.

### TAI-10: a foreign position found at a restart does not halt; ACIS trades beside it
- **Severity:** medium · **Likelihood:** low-medium (a human's manual trade on the demo between two runs)
- **Where:**
  - `core/execution/ctrader_attach.py:155-164`: flat-or-decide runs only when the binding has no persisted state.
  - `core/runtime/__main__.py:82`: `positions, _ = await face.synchronise()` drops the foreign list.
  - `ctrader_orders.broker_positions` drops foreign positions at every periodic reconcile too.
- **The authority:** ACIS-13 §7.1 A7 (line 353): "A foreign position is an `AttachHalt`." Master §7.5 and GAP-0018: ACIS never trades alongside what it did not open.
- **Reproduction (`p16_foreign_position_at_restart.py`):** first attach ATTACHED; the human opens a USD/JPY short 5,000 with no ACIS label; restart. `restart attach verdict: ATTACHED | practice_eligible: True | synchronise: ours 0 foreign 1`, and after boot `open halts []`. The practice account's equity, which Risk judges, now includes the human's P&L.
- **Proposed fix:** at every start, a non-empty `foreign` from `synchronise()` returns `HALTED_OPEN_POSITIONS` (exit 2). A foreign position that appears mid-run raises a halt at the periodic reconcile.

### TAI-11: the runbook's practice procedure runs a second engine beside the supervised one; nothing prevents it, and the two undercount one budget
- **Severity:** medium · **Likelihood:** medium
- **Where:**
  - `deploy/README.md:48-56`: enable the unit (paper on the venue), then run `python -m core.runtime --venue … --practice` at a terminal. There is no step to stop the unit.
  - No single-instance lock exists (searched `core/runtime`, `scripts/ctrader_probe.py`, `deploy/`).
  - `core/data/ctrader/meter.py:56-63,82`: each meter reads the persisted log once and then counts only its own requests.
  - `core/runtime/__main__.py:64` claims "shared with the probe: one budget ledger".
- **Reproduction (`p20_two_processes_one_budget.py`):** two live meters on one ledger report `engine sees 550, probe sees 550, the ledger holds 1100 (budget 1000, open/query stop at 900); refusals: 0`. A fresh meter sees 1,100.
- **By construction, not reproduced:** the two engines share `data/runtime/risk.db`, `params.db`, `venue_fills.db` and `logs/heartbeat.json`. The paper engine's face uses the same label (it is keyed on `account_key`), so it would book the practice engine's fills as unsolicited, and the paper engine's beats can mask a hung practice engine from the watchdog. The fake venue serves one connection, so the cross-engine event delivery is unconfirmed.
- **Proposed fix:**
  - An exclusive lock per `root` (or per `account_key`) at start, refused with a non-restarting exit status.
  - Re-read the meter's persisted count at each `admit` (or share it via the DB with a transaction).
  - Correct the runbook: stop the unit, then enter practice.

### TAI-12: SYNCING and REAUTH do not gate dispatch, and a reconnect never reconciles Risk
- **Severity:** medium · **Likelihood:** low
- **Where:**
  - `core/data/ctrader/session.py:112-113`: `request` refuses only DISCONNECTED/DETACHED. Neither the face, the orchestrator nor the executor reads the link state.
  - `core/execution/ctrader_reconnect.py:61`: `await self._face.synchronise()` discards the positions it returns, so §7.8 step 3's `reconcile_on_restart` is not run at a reconnect.
  - During REAUTH (a token refresh or an `AccountDisconnectEvent` on a live link) the fast loop keeps submitting. A close then meets a venue error, which halts all (TAI-09's uncaught path).
- **The authority:** ACIS-13 §8.1 (line 475): "In `SYNCING` and `REAUTH` no new dispatch leaves." §7.8 (lines 443-446): "On every start and every reconnect … `reconcile_on_restart(ACIS-labelled positions)`".
- **Reproduction:**
  - `p07_dispatch_while_syncing.py`: `link state: SYNCING`, `open sent while SYNCING -> FILLED 1000`; `link state: REAUTH`, `open sent while REAUTH -> FILLED 1000`; `NEW_ORDER_REQ count: 2`.
  - `test_the_session_authorises_the_bound_demo_account_and_waits_in_syncing` comments "no dispatch before the face syncs" but asserts only the state.
  - `p19_static.py` (b): the reconnector's only use is `await self._face.synchronise()`.
- **Proposed fix:** the face (or the orchestrator's capability check) refuses an open unless the session is READY, and waits (bounded) for READY for a close. The reconnector passes `synchronise()`'s positions to Risk's reconcile, after the queued fills (TAI-05's ordering).

### TAI-13: a fast loop that hangs is invisible to the runtime AND to the watchdog
- **Severity:** medium · **Likelihood:** low (a spot subscription that silently stops while the link lives)
- **Where:**
  - `core/runtime/engine.py:153-158`: the heartbeat is written by Risk's timer.
  - `engine.py:186-195`: only a task that ends or raises is a stall.
  - The watchdog treats a changed `(ts_utc, fast_loop_seq)` as alive, so an advancing `ts_utc` hides a frozen `fast_loop_seq`.
- **The authority:** master §10 (line 398): "Each loop heartbeats …; a stalled Loop 3 with open positions triggers the Risk Monitor's flatten-and-halt"; §8.6 layer 2. The brief lists this as a declared choice. The declaration does not cover the consequence: no layer at all sees a hung Loop 3.
- **Reproduction (`p11_hung_fast_loop.py`):** the phase-7 market opens one paper position, then the feed blocks forever; wall-clock `now_fn`; eval cadence 0.2 s.
  - Heartbeat `{'open_positions': 1, 'fast_loop_seq': 280}` then `{'open_positions': 1, 'fast_loop_seq': 280}`, while `ts` advances from 04:49:00.7 to 04:49:03.8.
  - `LOOP_STALLED logged: False | run() still running: True`.
  - The real `Watchdog.poll` with a 1 s timeout, over 3 s: `['ok', 'ok', 'ok', 'ok', 'ok', 'ok']`.
- **Proposed fix:** Risk's timer writes `fast_loop_seq` as now, and the runtime (or the watchdog) treats "no fast-loop progress for N × the expected tick gap while the instrument's calendar says open, with positions held" as a stall. The calendars are already in the factory.

### TAI-14: the practice account's daily-loss guard is anchored on the PAPER ledger's equity
- **Severity:** medium · **Likelihood:** low for this demo (the paper NAV equals the demo's $10,000, and the lot is minimal); structural otherwise
- **Where:**
  - `core/runtime/__main__.py:133-134`: `boot()` then `enter_practice`.
  - `core/runtime/engine.py:139-151`: in paper mode `evaluate` judges the paper account.
  - `core/risk/drawdown_series.py` `_RuleAnchor.update`: engine:daily anchors on the day's first observation, and the anchors are persisted and restored.
  - Every paper-mode evaluate, at boot and for as long as a supervised restart waits for a human, feeds the same series the practice evaluates later read.
- **Reproduction (`p10_paper_anchors_practice.py`):** the demo account holds $11,000; paper starts at $10,000.
  - Boot: `engine daily anchor: {'anchor': 10000.0, …}`.
  - Practice at $11,000 gives daily drawdown 0.0. After a drop to $9,850: `measured daily drawdown % 1.500 (true intraday loss 10.45%, limit 2.0%)`, and `session halt applied: []`.
- **Proposed fix:** keep one drawdown series per account (paper and venue), keyed like the venue store, or do not evaluate the paper account when a practice-eligible venue is attached. At minimum, re-anchor engine:daily on the first practice observation.

### TAI-15: a reconcile drift fabricates Risk's view of every position: average price 1.0, no stop, no target, a fresh `opened_at`, no group
- **Severity:** low · **Likelihood:** high (every restart with a venue position, and every periodic drift)
- **Where:** `core/risk/monitor.py:331-339`. It rewrites ALL positions, not just the drifted one. The runtime newly drives this path at every boot with a venue and every 900 s.
- **Consequences:**
  - The per-instrument drawdown judges a price the position never had. A USD/JPY short adopted at 1.0 reads a ~9.9% loss against the 1% limit: a spurious instrument halt, and a taper of 0 that zeroes entries everywhere while it is held.
  - P05-A shows the blended 1.05 tripping `cluster_cap`.
  - The max hold restarts at every adoption, and take-profit exits vanish.
  - The monitor's comment "corrected on the next fill/mark" (`:328-330`) is untrue: marks never touch `avg_price`.
- **Reproduction:** P05-A (`('EUR_USD', 1, '2000', 1.05)` and `cluster_cap`); P08 (`('EUR_USD', 1, '1000', 1.0, None, None, 'unknown:reconciled')`).
- **Proposed fix:** carry the venue's entry price (cTrader positions carry `price`) and its `stopLoss` in `BrokerPosition`; adopt only the drifted instruments; keep `opened_at` from the venue's `openTimestamp`.

### TAI-16: deal paging drops a same-millisecond deal at a page boundary, and the two paging loops assume opposite orders
- **Severity:** low · **Likelihood:** low
- **Where:**
  - `core/execution/ctrader_sync.py:65-76`: the next FROM is `last executionTimestamp + 1`, and each page is sorted oldest first.
  - `find_order` (`:42-56`), over the same API family, pages newest first by moving TO backwards.
- **Reproduction (`p14_deal_paging.py`, a 2-deal page, oldest first):** venue deals `[1, 2, 3, 4]`, with 2 and 3 in the same ms; `missed_deals` returned `[1, 2, 4]`. Which order cTrader actually pages is for the external lens. The same-ms loss holds under the order the loop assumes.
- **Proposed fix:** page by `fromTimestamp = last ts` (not +1) and de-duplicate by `dealId`. Pin the venue's paging order by a recorded frame.

### TAI-17: the proactive token refresh is never called
- **Severity:** low · **Likelihood:** medium over a long uptime
- **Where:** `core/data/ctrader/session.py:136-141` `refresh_if_due` has no caller (`p19_static.py` (a)). The token is refreshed only at a connect. A 30-day token on a link that never reconnects expires in service, and then it takes the TAI-02 path.
- **The authority:** ACIS-13 §6.7 (line 328), "Refresh proactively when fewer than 7 days remain, and only at a quiet moment".
- **Proposed fix:** call it from the runtime at a quiet moment (nothing busy or queued, READY), e.g. from the reconcile task.

### TAI-18: engine parity and mode gaps in the as-built policy and sizing
- **Severity:** low · **Likelihood:** low (pairs are refused whole at one minimum lot; live is unreachable today)
- **Where:**
  - The policy's docstring says it is "the backtest book's rules … in production", yet it adds `group_exit` and `group_orphan` (`core/runtime/policy.py:79-87`), which the harness book never grades (`p19_static.py` (d): runtime-only `['group_exit', 'group_orphan']`; (f): a lone pair leg is closed 5 s after entry).
  - The runtime closes a target at the mark; the book fills at the target level.
  - The runtime's max hold runs from the fill time; the book's from `sized_at`.
  - ACIS-05 v1.6 §7 step 3b: "In live mode nothing is injected". The wiring's `min_lot` closure (`core/runtime/wiring.py:163-166,178`) never reads the mode (`p19_static.py` (c)).
- **Proposed fix:**
  - Either add the group rules to the book or declare the deviation in the policy's docstring and GAP-P12D-118.
  - Gate `fixed_units` on `mode in {paper, practice}`.

### TAI-19: ledger and read-path claims the code contradicts (A13/A15)
- **Severity:** low · **Likelihood:** certain
- **Stale open entries:**
  - `KNOWN_GAPS.md:1035` GAP-P12D-69 is still open, "what remains is wiring the report into the runtime's ModeController ([[GAP-0091b]])". That is wired (`wiring.py:216`), and GAP-0091b is fixed.
  - `KNOWN_GAPS.md:1017` GAP-P12D-70 is still open, "the runtime's periodic reconciliation remains". That is built (`venue_link.py:56-67`).
  - GAP-P12D-131, their de-facto residual, names neither (`p19_static.py` (e)).
- **Untrue claims:**
  - `KNOWN_GAPS.md:159` "until a human resumes" (TAI-07).
  - `ctrader_reconnect.py:13` "the persisted request budget still bounds them" (TAI-02).
  - The `acis-engine.service:31-33` comment implies a restart loop cannot spend the budget; exit 1 does (TAI-02).
  - `deploy/README.md:67` "the compose engine service is not yet wired", but `docker-compose.yml:31-45` defines it with the runtime command.
  - `config/system_config.yaml:153` "the unrealized-PnL poll while positions are open": the runtime polls always (`venue_link.py:51-54`). The A9 formula assumes always, so only the comment is wrong.
- **Unowned work:** TAI-01..TAI-17 have no owner in the ledger. The Residual lines written with this work (GAP-0020, GAP-0091b, GAP-0099 → GAP-P12D-131) do not own them.
- **Proposed fix:** close or re-point GAP-P12D-69/70, correct the four texts, and ledger each finding at triage.

## The declared choices, attacked

| Declared choice | Verdict |
|---|---|
| The as-built policy instead of Carver's band | Declared and owned (GAP-0075 → GAP-P12D-118). Parity is looser than claimed (TAI-18). |
| Max hold = the harness's 48 h, pinned by test | The pin holds (`test_the_runtime_max_hold_is_the_harness_one`). The clock differs (fill time vs `sized_at`), and adoption resets it (TAI-15). |
| One minimum lot, applied before the hard limits; a zero never raised | Holds: a halt or a taper of 0 still zeroes, and the lot meets every cap. A taper in (0, 1) and the ×0.25 alpha throttle have no effect on size (as ACIS-05 v1.6 says). The injection is mode-independent (TAI-18). |
| Practice equity = the last 300 s poll | Holds while the budget is healthy. In the reserve the poll is refused and the lag becomes unbounded (TAI-01). |
| The heartbeat by Risk's timer; a stall = a task that ends or raises | A hung Loop 3 is invisible to every layer (TAI-13). |
| A periodic drift is adopted and halts everything | In paper mode it fires on every paper position (TAI-06). It rewrites every position's metadata (TAI-15), and with no resume path it is permanent (TAI-07). |
| A flatten freezes EVERY orchestrator; only the human resume lifts it | Holds: `set_freeze(False)` appears only in `RuntimeControl.resume`, and a restart re-freezes through the persisted `flatten` rows (`guardrails.py` `restore_state`). But the human resume cannot be reached (TAI-07). |
| Practice needs a human at a terminal; a restart comes back in paper | Holds (`getpass`; no argv or env token). Consequences: TAI-06, TAI-11, TAI-14. |
| A link lost mid-order halts entries (GAP-P12D-131 h) | Holds, and so does a mere ack timeout with the link alive, which also orphans the fill (TAI-08). |
| The demo trades sets evolved on 2022–2023 only; ONE champion staged | The script's bounds hold (below). The run's artifacts are in GCS and were not verified. |

## Honest negatives (looked for, not found)

**Money reach:**
- Paper orders go only to the paper orchestrator (`wiring.py:99-104`, evaluated per item in `executor.py:80`).
- Practice needs `AttachReport.practice_eligible` (environment demo, `isLive` false, `account_class: practice`) at both the ModeController and `route_to`. `_check_grant` re-checks `isLive` against the environment at every (re)connect and detaches on a mismatch.
- Live is unreachable: `validation_record_ok=lambda: False`, and `route_to` returns None for live.
- No mid-run mode change path exists at this commit.
- The watchdog plugin can only close and cancel.

**Protection:**
- Every orchestrated open carries `stop_loss` (`orchestrator.py:287-288`).
- The relative stop is floored to the tick and refused if too close or on the wrong side (`ctrader_orders.py:63-72`); a stop-less open is refused by the face.
- No `priceBound`, STOP_LIMIT or guaranteed stop exists on any protective stop (the GAP-P12D-42 class is absent).
- Closes are reduce-only at three layers: the executor's flat check before a reversal's open, the orchestrator's cap, and the face's per-position close capped at the holding. I found no path that crosses through flat.

**Exactly-once, what holds:**
- Within one process, a reconnect's re-listed deals are de-duplicated (`_seen_deals`, and `record_unsolicited` by a persisted `fill_id`).
- A fill seen live is not reported again after a restart when its `fill_id` matches.
- The GAP-P12D-126 step order (fragments first) is implemented.

**The guard law:**
- No non-human path lifts a halt or the freeze. The sink has no clearing verb. `clear_halts` is reached only from `on_human_resume`, behind `Governor.resume`, behind `ControlTools`' verifier.
- The human token is typed, and it is not stored in the audit record's `args`.

**Concurrency:**
- `CTraderSession.stop()`'s gather: no deadlock found. No task that `stop()` gathers calls `stop()`, and the gather does stop an old reader's `finally` from marking the new link lost.
- Items run serially; the busy set closes the per-tick firehose.
- The synchronous fsync'd SQLite commits on the event loop measured 1.0–2.0 ms median, ≤ 3.9 ms max on the server (`p17_loop_blocking.py`: meter record 1.05 ms, venue store sent 1.04 ms, market-state write 2.02 ms). That is no starvation risk at two instruments.

**Clocks:**
- A8 is implemented per instrument on the first live, non-stale tick, and exits are never blocked by it.
- The boundary sweep is the harness's own clock.

**Secrets and untrusted input:**
- Credentials and tokens are `repr=False`; the token store is written atomically with mode 0600; the probe redacts.
- Venue text (`description`, `reason`) is logged as data only, and routing keys on payload types and enums.

**The demo evolution:**
- `evolve_demo_params.py` reads only bars that close by 2024-01-01 (`regime_labels.py:165-181`).
- The label builder refuses 2024+.
- It stages only (`evolve_step.py:113`, no promote), and writes the traceable record with `validated: false`.

**A12:** every new module is ≤ 300 lines and opens with an invariants block.

## What I could not verify
- **Real venue behaviour** (external lens): the DealList/OrderList paging order (TAI-16); whether `POSITION_NOT_FOUND` really arises in the close/stop race (TAI-09); whether a second connection can authorise the same account (OQ-06, TAI-11); how cTrader signals token expiry on a live link (TAI-17).
- **The demo evolution run** (one champion, its record) lives in GCS, not the repo.
- **Cross-engine event delivery** with two engines on one account (TAI-11): the fake venue serves one connection.
- **The demo host's disk latency** (P17 ran on `acis-compute-1`).

## Residual risk
- **The findings share one mechanism.** At a restart, a reconnect or a budget edge, the runtime mixes two sources of truth, or two accounts, into one Risk:
  - venue adoption and replayed fills (TAI-05, TAI-08, TAI-09);
  - the paper ledger and the venue (TAI-06, TAI-14);
  - two engines (TAI-11).
- **The unit tests are green because each tests one layer against the fake venue.** The composed restart, reserve and paper-on-venue paths have no runtime-level test.
- **Every failure found fails toward a halt**, and with TAI-07 that halt is permanent. So the demo's first realistic incident (a restart with a position open) ends its trading until someone edits `risk.db`.
- **The two exceptions to "fails safe":**
  - TAI-04, an unprotected position that persists;
  - TAI-01, where the equity breaker is blind and no close can leave while the budget sits in the reserve.
- **The watchdog is not a backstop for either** until TAI-03 is closed.
- **None of this touches a guardrail value, HALT/veto semantics or the equity floor as written.** TAI-01 and TAI-14 are about the INPUTS those guards read, which is where the guard-integrity law's structural protection does not reach.
