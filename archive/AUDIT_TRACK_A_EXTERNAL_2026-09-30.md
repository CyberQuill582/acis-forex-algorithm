# AUDIT — Track A steps 3–5, EXTERNAL-REFERENT lens (2026-09-30)

**Auditor:** Opus 5.5, fresh context, external-referent lens (SPEC_CONSTITUTION A3). **I am a finder, not a clearer (A5).** A clean section here is not a sign-off. I launched no agents.
**Brief:** `AUDIT_BRIEF_TRACK_A_2026-09-30.md` (pinned). **Audited code:** `86ea8d3`, read with `git show`. My server checkout sits at `62a92a2`, whose diff from `86ea8d3` touches only `AUDIT_BRIEF_TRACK_A_2026-09-30.md` and `TODO.md`, so the code is identical.
**Evidence rules (A6).** Every external fact below is quoted with its URL and was fetched on **2026-09-30**. Every code claim is reproduced by a probe that ran on `acis-compute-1` against the repo's own fake venue (`tests/ctrader_fixtures.py`), cited `file:line` at `86ea8d3`. The probes stay in the auditor's scratchpad (`audit_ta/external/probes/`), outside the repo. Venue text was treated as data. Web budget: 9 WebSearch calls, the rest WebFetch.

## Executive summary

The adapter is faithful to the venue on the **happy path**:
- the relative-stop units and precision;
- the market-order stop rule;
- the endpoints and the demo/live separation;
- volume units;
- `clientOrderId` limits;
- hedging semantics;
- server-side stop persistence;
- Brooker full jitter, implemented exactly.

It is **wrong or fragile about the venue's unhappy paths**, and those decide whether an unattended demo stays up:

1. **A venue refusal during the attach, or a spent budget, becomes an endless systemd restart loop.** Auth requests are counted but never refused, so the rolling 24-hour ledger can never drain once it passes 900, and the loop is then self-sustaining (TAE-01).
2. **The venue's `ProtoOAAccountDisconnectEvent` ("a new session must be authorized") is handled by an in-place re-auth.** That re-auth never re-subscribes spots and never re-syncs. An unanswered re-auth leaves the session stuck in `ACCOUNT_AUTH` forever, and neither the reconnector nor the watchdog can see it (TAE-02, TAE-04).
3. **The link-liveness timeout (30 s) equals the server's reported heartbeat period (30 s).** Every quiet link (weekends, holidays) therefore has a knife-edge false-disconnect window, and reconnect churn feeds TAE-01 (TAE-03).
4. **Practice-mode stops trigger one spread earlier (in mid terms) than the backtest and paper stops.** The venue triggers a long's stop on the bid, and the stop is set relative to the ask fill. So "the demo is the engine the harness grades" is not true of exits (TAE-05).

**Counts:** 14 findings, **2 High, 8 Medium, 4 Low.**

**The lead's claims:**
- **Confirmed:** 1168 passed and 6 skipped; the ledger is green; no audited module exceeds 300 lines.
- **Contradicted:**
  - "every fill reaches Risk exactly once": TAE-02, TAE-07, TAE-08 and TAE-10;
  - "the request spend stays inside §6.5": TAE-01 and TAE-03;
  - GAP-P12D-126 (c), "an application refused on the reconnect's authorisation detaches": TAE-09.

## Findings

### TAE-01 — High · Likelihood: possible — venue refusals and a spent budget turn into an unbounded restart loop that the budget ledger can never drain
- **External referents:**
  - Spotware maintenance. "Sometimes we do maintenance and upgrades during weekends, and the API is inaccessible during the maintenance period" (ACIS-13 F-26, https://help.ctrader.com/open-api/faq/). The re-fetch on 2026-09-30 returned only the FAQ's heartbeat answer, so this wording was not re-confirmed.
  - systemd start-rate limits. "DefaultStartLimitIntervalSec= defaults to 10s. DefaultStartLimitBurst= defaults to 5." (https://man7.org/linux/man-pages/man5/systemd-system.conf.5.html). With `RestartSec=5` there are at most 2–3 starts per 10 s, so the limit never trips.
  - Spotware's terms. "In case of misuse of the API, Spotware Systems Ltd reserves the right to restrict or remove access to your application" (F-33). The pinned proto's own example reason for `ProtoOAClientDisconnectEvent` is "The application access was blocked by cTrader Administrator." (https://raw.githubusercontent.com/spotware/openapi-proto-messages/3fd8bddf…/OpenApiMessages.proto).
- **Code at 86ea8d3:**
  - `attach()` catches only `AuthRefused` (`core/execution/ctrader_attach.py:113-116`). A `VenueError` or `BudgetRefused` escapes.
  - `core/runtime/__main__.py:125-128` returns 2 only for a refusal verdict, so an exception exits 1.
  - `deploy/systemd/acis-engine.service:29-33` sets `Restart=always`, `RestartSec=5` and `RestartPreventExitStatus=2 3`. Its own comment says exit 2 exists because "a restart loop would only spend the venue's request budget".
  - `meter.py:27,70-71`: `auth` is an exit class, recorded and never refused.
  - `ctrader_reconnect.py:64-72` does not catch `BudgetRefused`.
- **Reproduction** (probes `test_tae_attach_crash.py`, `test_tae_reconnect_budget.py`, `test_tae_app_refused.py`):
  - `SERVER_IS_UNDER_MAINTENANCE` at app auth, `CH_ACCESS_TOKEN_INVALID` at the grant, and `CH_CLIENT_AUTH_FAILURE` at app auth each make `attach()` raise `VenueError`, which exits 1, not 2.
  - After 900 recorded auth requests in 24 h, `attach()` raises `BudgetRefused(VENUE_BUDGET_OPEN_EXHAUSTED)` at its `TRADER_REQ` query, which exits 1 again. Each boot adds three more auth records first, so the window never drains.
  - A reconnect with 905/1000 used raises `BudgetRefused` out of `Reconnector.run`. The runtime reads that as a stalled loop: flatten, halt, exit 1.
  - An application refused on reconnect retries without end. With the test's instant sleep there were 1,084 attempts in 1 s, and `used_24h` = **1,088 against a cap of 1,000**, which contradicts C-VEN-4 ("the budget is hard") and the `ctrader_reconnect.py` docstring ("the persisted request budget still bounds them").
- **Effect:** a weekend maintenance window during any engine exit (maintenance-time boots record one auth each, about 12 a minute, so about 75 minutes of them fill the ledger), a revoked grant, or reconnect churn (TAE-03) produces a crash loop every 5 s. The loop hammers Spotware's auth endpoints (the misuse clause) and never re-attaches without a human. Positions are left to their venue stops.
- **Fix:** treat every attach failure as a refusal verdict (exit 2) and every budget refusal as a verdict too. Cap auth requests: give reconnects and boots their own bounded allowance inside the reserve, and count them in A9. Catch `BudgetRefused` in the reconnector as terminal-until-window. Add `StartLimitIntervalSec`/`StartLimitBurst` to the unit.

### TAE-02 — High · Likelihood: possible — `ProtoOAAccountDisconnectEvent` gets an in-place re-auth with no SYNCING and no re-subscribe, and an unanswered re-auth wedges the session for good
- **External referents:**
  - The proto on `ProtoOAAccountDisconnectEvent`: "A new session must be authorized for the account" (F-12). `ProtoOAAccountsTokenInvalidatedEvent`: "Reasons to trigger: account was deleted, cTID was deleted, token was refreshed, token was revoked."
  - User report (grade c, fgnm.dev, 2024-12-03, unresolved by support after "almost 6 months"): after this event "the TCP socket become unresponsive to ANY new message I sent", yet it "still continue to receive ProtoOASpotEvent" (https://community.ctrader.com/forum/connect-api-support/45671/).
- **Code:**
  - `session.py:223-245`: `_on_auth_event` → `_recover` → `_authorise_binding` → `_set(prior)`, straight back to READY.
  - `_recover` catches only `VenueError` and `AuthRefused` (`:242`).
  - `request()` refuses only DISCONNECTED and DETACHED (`:112`).
  - The reconnector watches only `DOWN = (DISCONNECTED, DETACHED)` (`ctrader_reconnect.py:27`).
- **Reproduction** (`test_tae_reauth.py`):
  - After the event, the only request sent is `ACCOUNT_AUTH_REQ`: no `SUBSCRIBE_SPOTS_REQ`, no `DEAL_LIST_REQ`, no `RECONCILE_REQ`, and no `VENUE_RECONNECTED`.
  - With the venue silent and spots still streaming, the session sits in **`ACCOUNT_AUTH` for good**. The recover task is dead on `TimeoutError`, the reconnector is alive but idle, and a later `RECONCILE_REQ` is still **sent** (then times out).
  - This contradicts ACIS-13 §8.1: "In SYNCING and REAUTH no new dispatch leaves"; ACCOUNT_AUTH → SYNCING → READY.
- **Effect:**
  - Under the documented semantics (a new session, so the old spot subscription goes with it; this is inferred, and the first demo session should confirm it), the feed goes silent while the server's heartbeats keep the link "alive". No ticks means no target or max-hold exits.
  - A stop that fires in the gap is never ingested (there is no deal sync), so the next periodic reconcile halts everything as drift.
  - Under the reported failure, every request times out: orders fail and the executor halts entries.
  - Both states are invisible to the reconnector, and to the watchdog (TAE-04).
- **Fix:** handle `ProtoOAAccountDisconnectEvent` and token invalidation as a link loss. Close the socket and let the reconnector run the full start → SYNCING → re-subscribe. Bound `_recover` with a timeout that falls back to a reconnect. Make `request()` refuse non-auth requests outside READY and SYNCING.

### TAE-03 — Medium (High in combination with TAE-01) · Likelihood: likely — the liveness timeout equals the server's reported heartbeat period
- **External referents:**
  - Server heartbeat "usually comes every 30 secconds" (olegchubukov, 2021-09-20, https://community.ctrader.com/forum/connect-api-support/36909/).
  - In 2023 a client sending heartbeats every 5 s still saw the server's `ProtoHeartbeatEvent` "every 30 seconds", and its own heartbeats got no visible response. Spotware staff replied "OnProtoHeartbeatEvent checks for incoming heartbeats" (https://community.ctrader.com/forum/connect-api-support/42264/, 2023-11-08).
  - The proto on `ProtoHeartbeatEvent`: "keep the connection open for a period without other messages longer than 30 seconds" (OpenApiCommonMessages.proto, pinned).
  - ACIS-13 OQ-08 itself lists the server cadence as unknown.
- **Code:**
  - The link is dead when `now − received >= liveness_timeout_s` (`wire.py:141-142`), checked about once a second (`session.py:247-256`), with `liveness_timeout_s: 30` (`system_config.yaml:150`).
  - The config value is **not wired**: `attach_venue` builds the session without it (`__main__.py:67-69`), so raising it in config changes nothing (see also TAE-11).
- **Reproduction:**
  - `tae_liveness_real.py`, the real session with the server's heartbeat every 30.25 s and no spots: `VENUE_DISCONNECT{reason_code: 'liveness timeout'}` after 151 s. At 29.75 s: no disconnect in 125 s.
  - `tae_liveness_seeds.py` (the real `LinkClock`, a 48 h quiet weekend, lateness |N(0,σ)|): mean false disconnects of 5.2 (σ = 1 ms), 26 (5 ms), 99 (20 ms), 79 (50 ms, a phase-locking artefact) and 873 (200 ms). **Zero at a 45 s timeout.**
- **Effect:** each false disconnect is a full reconnect of about 6 recorded requests (3 auth and 2 protect, never refused, plus 1 subscribe). A9's feasibility assumes at most `max_consecutive` (10) reconnects a day. At about 150 reconnects in 24 h, TAE-01's lockout begins.
- **Fix:** set liveness at ≥ 1.5× the observed server cadence (45–60 s), wire the config value, and measure the real cadence and jitter in the first demo session (OQ-08).

### TAE-04 — Medium · Likelihood: likely — the dead-man's switch attests a timer, not the decision loop
- **External referent:** Jack Ganssle, *Great Watchdog Timers for Embedded Systems* (http://www.ganssle.com/watchdogs.htm):
  - "Any system that uses an ISR or a special task to tickle the watchdog but that does not examine the health of all other tasks is not robust."
  - "If your watchdog tickler stays alive as the world collapses around the rest of the code, then the watchdog serves no useful purpose."
- **Code:**
  - The heartbeat is written by Risk's own timer task (`engine.py:153-158`).
  - The watchdog's staleness signature is `(ts_utc, fast_loop_seq)` (`scripts/acis_watchdog.py:128-130`), and `ts_utc` changes on every write. So a frozen `fast_loop_seq` (no ticks, no decisions) is never stale.
  - The runtime detects only tasks that *end* (`engine.py:186-195`).
- **Effect:** TAE-02's wedged or unsubscribed session, a reconnector looping on TAE-09's app refusal, and a dead event consumer (TAE-08) all leave a fresh heartbeat. Layer 2 never acts, and nothing flattens or alerts. The declared rationale ("a quiet weekend is never read as silence") is legitimate, but it is met by the wrong mechanism.
- **Fix:** beat per-task progress (last venue frame, last spot while the venue schedule says open, the executor queue's age, the consumer task alive), and have the watchdog judge `fast_loop_seq` progress during scheduled open hours.

### TAE-05 — Medium · Likelihood: certain (structural) — practice stops trigger one spread earlier than the backtest and paper stops
- **External referents:**
  - The pinned proto: `relativeStopLoss` "For BUY stopLoss = entryPrice - relativeStopLoss".
  - `ProtoOAOrderTriggerMethod.TRADE`: "Stop Loss Order: for buy position is triggered by bid and for sell position by ask". `ProtoOAPosition.stopLossTriggerMethod [default = TRADE]`.
  - help.ctrader.com: "Trade side (default): 'Bid' for buy orders, 'Ask' for sell orders" (https://help.ctrader.com/ctrader-web/trading/protections/).
- **Code:**
  - The Governor's stop is `mid − k·ATR`, with the entry at the mid (`core/signals/agon.py:290-291`, the entry is `state.mid`).
  - The face sends `d = |mid − stop|` as relative (`ctrader_orders.py:63-72`), so the venue stop is `ask_fill − d`, triggered on the bid.
  - The backtest triggers on the mid (`tests/backtest/book.py:123-127`), and so does paper (`core/runtime/paper.py:48-56`).
- **Reproduction** (`tae_stop_parity.py`, real `relative_stop`), the adverse mid move needed to trigger:
  - 0.2-pip spread, 5-pip stop: 4.80 vs 5.00 pips (4% closer);
  - 1.0-pip spread (Pepperstone Standard: "1 pip mark up on the raw spread", https://pepperstone.com/en-eu/trading/accounts), 5-pip stop: 4.00 vs 5.00 (20% closer);
  - 1.0-pip spread, 3-pip stop: 2.00 vs 3.00 (33%);
  - 1.2-pip spread, 2-pip stop: 0.80 vs 2.00 (60%).
- **Effect:**
  - Live stops hit more often, each losing about `d` rather than the backtest's `d + spread`. ACIS-13 §6.3's "risk-faithful" argument is right about the loss per stop and silent about the hit rate.
  - Also unconfirmed: if the demo is a Razor account, "$3.50 per lot, per side" commission applies while `instruments.yaml` declares `commission_per_side: 0.0`. The account type is not recorded anywhere.
- **Fix:** declare the divergence in the ledger. Either model trade-side triggering in the book and the paper venue (trigger on the bid for longs, with the stop measured from the side's fill), or send the stop so its bid-trigger equals the Governor's mid level. Record the demo account type.

### TAE-06 — Medium · Likelihood: certain when maintenance meets a reconnect — `maintenanceEndTimestamp` is in seconds on `ProtoOAErrorRes`, and the code and its test assume milliseconds
- **External referents:**
  - `ProtoOAErrorRes.maintenanceEndTimestamp`: "The Unix time in **seconds** when the current maintenance session will be ended".
  - `ProtoErrorRes.maintenanceEndTimestamp`: "The Unix time in **milliseconds** of the end of the…" (both from the pinned proto).
- **Code:** `wire.py:79` stores either as `maintenance_end_ms`, and `ctrader_reconnect.py:69` divides by 1000. The repo test `test_a_maintenance_window_is_slept_through_to_its_end` (`tests/integration/test_ctrader_reconnect.py:152-160`) sends **milliseconds inside a ProtoOAErrorRes**, so it pins the wrong unit (a hollow test against the referent).
- **Reproduction** (`test_tae_maintenance_units.py`): a ProtoOAErrorRes carrying seconds gives `until = 1970-01-21T17:24:39Z` and a sleep of 1.088 s, not 3,600 s. A ProtoErrorRes in milliseconds is honoured (3,601 s).
- **Fix:** convert per payload type (2142 → ×1000) and correct the test. It feeds TAE-01 (maintenance-time polling).

### TAE-07 — Medium · Likelihood: low (demo volumes); impact: high — the two history pagers assume opposite chunk orders, and the venue documents neither
- **External referent:** `ProtoOADealListRes` and `ProtoOAOrderListRes` define `hasMore` only as "If TRUE then the number of records by filter is larger than chunkSize, the response contains the number of records that is equal to chunkSize". No sort order is stated (pinned proto). A search found no primary source for the order.
- **Code:** `missed_deals` pages **forward** from the newest deal it received (`ctrader_sync.py:65-76`), while `find_order` pages **backward** from the oldest (`:42-56`). The fake venue always answers `hasMore: false` (`tests/ctrader_fixtures.py:139-150`), so paging is untested.
- **Reproduction** (`test_tae_paging.py`, real functions, chunk of 5):
  - A newest-first venue: `missed_deals` ingests 5 of 12 deals (7–11). The older ones, missed stop-outs, never reach Risk, and the cursor passes them for good.
  - An oldest-first venue: `find_order` returns `None` for the newest order, which the caller reads as "never reached the venue" and **resends**, a C-VEN-1 duplicate.
- **Fix:** page by a window that is correct under either order (shrink `[from, to]` on the side the chunk did not cover and de-duplicate by id), pin `maxRows`, record the observed order in the first demo session, and make the fake venue page.

### TAE-08 — Medium · Likelihood: low · impact: high — the face's event consumer is unsupervised, so one unknown enum silences every later venue fill
- **External referent:** the protocol evolves. The pinned proto is a 2025-11-13 snapshot, and Spotware staff referred to demo environment "version 92" in 2024 (https://community.ctrader.com/forum/connect-api-support/44069/). The schema raises `DataQualityError` on any enum value outside the pin (`schema.py:178-183`).
- **Code:** `face.start()`'s task is discarded (`__main__.py:81`). `_consume` (`ctrader_face.py:84-86`) has no guard around `router.route` (`ctrader_events.py:120`).
- **Reproduction** (`test_tae_consume.py`): one `EXECUTION_EVENT{executionType: 13}` kills the consumer with `DataQualityError`. A stop that then fires is **never delivered** to `venue_fills()`, which breaks exactly-once.
- **Fix:** log and skip an unroutable event, supervise the task in `Parts.tasks` (its end is a stall), and treat unknown enum values as data.

### TAE-09 — Medium · Likelihood: likely over a long run — the token lifecycle and ACIS-13 §12's error taxonomy are largely unimplemented, and a ledger claim says otherwise
- **External referents:**
  - The access token lives 2,628,000 s (F-08).
  - The error codes `OA_AUTH_TOKEN_EXPIRED`, `CH_ACCESS_TOKEN_INVALID`, `CH_CLIENT_AUTH_FAILURE`, `POSITION_NOT_FOUND`/`POSITION_NOT_OPEN` (120/122), `POSITION_LOCKED` (123) and `retryAfter` are defined in the pinned proto.
- **Code:**
  - `refresh_if_due` (`session.py:136`) has **no caller** in `core/`, `scripts/` or `tests/` (grep at 86ea8d3). §6.7's proactive refresh therefore happens only at boot.
  - The code branches on exactly two error codes: `ALREADY_LOGGED_IN` (`session.py:184`) and the rate-limit pair, which it only logs (`:128-130`; no `retryAfter` pause).
  - So token errors never refresh (A3), a refused application never detaches, `POSITION_NOT_OPEN` from a close racing a stop halts entries through `EXECUTOR_ITEM_FAILED` instead of "reconcile → no error" (§12, §14.3), and there is no bounded retry for `PENDING_EXECUTION`/`POSITION_LOCKED`.
- **Reproduction** (`test_tae_app_refused.py`): `CH_CLIENT_AUTH_FAILURE` on reconnect leaves state `APP_AUTH`, retrying without end and never DETACHED. That **contradicts GAP-P12D-126 (c)** (`KNOWN_GAPS.md:248`, "an application refused on the reconnect's authorisation detaches"), an A13 read-path falsehood.
- **Fix:** implement the §12 table as a code map with a test per row, schedule `refresh_if_due` at quiet moments, and correct GAP-P12D-126 (c).

### TAE-10 — Medium · Likelihood: low — C-VEN-2 hole: a refused or unanswered stop amend leaves a naked position whose fill never reaches Risk
- **External referents:**
  - A relative stop can be accepted without being set: "it accept the order, but the SL has not been set" (F-15). Spotware staff's resolution was a units fix: "set relativeStopLoss to 10 * 100000" (https://community.ctrader.com/forum/connect-api-support/38778/).
  - `TRADING_BAD_STOPS` on an SL/TP change arrives as `ProtoOAOrderErrorEvent` with `order_id: 0`, `position_id: 0`. Spotware: "The team confirmed this is a bug" (2024-08-19, https://community.ctrader.com/forum/connect-api-support/44069/). Correlation by `clientMsgId` is therefore the only link.
- **Code:** `ensure_stop` does not inspect the amend reply and logs `VENUE_STOP_AMENDED` either way (`ctrader_sync.py:98-100`). The close (`:105-108`) is reached only if the amend call *returned*. A `VenueError` or `TimeoutError` propagates through `_protect` (`ctrader_face.py:162-167`), the orchestrator (which catches only `ConnectionError`, `orchestrator.py:289`) and the executor.
- **Reproduction** (`test_tae_amend.py`):
  - With the refusal as ProtoOAErrorRes: `submit_order` raises `TRADING_BAD_STOPS`, no report is returned, the venue position stays at `(101, stopLoss None)`, and **no close is sent**.
  - With the refusal as a correlated OrderErrorEvent: the close is sent (safe), but after a false `VENUE_STOP_AMENDED`.
- **Fix:** wrap amend→verify→close so that any exception still reaches the close branch, and return the open's report to Risk in every case.

### TAE-11 — Low · Likelihood: low — deal-list requests (history) are paced at 25/s against a documented 5/s, and the venue timers in config are dead keys
- **External referents:**
  - "a maximum of 5 requests per second per connection for any historical data requests" (https://help.ctrader.com/open-api/).
  - `ProtoOADealListReq`: "Request for getting Trader's deals historical data (execution details)" (pinned proto).
- **Code:**
  - One pacing gap for everything (`session.py:59`). `rate_limit_per_s.historical` (§6.2's 2/s bucket), `general`, `heartbeat_s` and `liveness_timeout_s` (`system_config.yaml:149-156`) are read by nothing: `attach_venue` (`__main__.py:67-69`) and `scripts/ctrader_probe.py` use the constructor defaults.
  - `retryAfter` is logged, never obeyed.
- **Reproduction** (`test_tae_rate.py`): 12 `DEAL_LIST_REQ` in 0.445 s (24.7/s), all 12 inside the first second.
- **Fix:** add a per-type bucket for history, wire the config values, and honour `retryAfter`.

### TAE-12 — Low · Likelihood: certain — demo evidence is not live evidence
- **External referents:** Pepperstone, https://pepperstone.com/en-af/ways-to-trade/demo-accounts/: "We don't charge demo accounts for interest, dividend adjustments, or out-of-hours price movements." and "Demo accounts are for testing execution and may not reflect live trading conditions."
- **Where this bites:**
  - ACIS-13 §4.2 and §5.1 log `VENUE_COSTS` swap and fees "for the C8 cost calibration" and the "C8 carry calibration (GAP-P12D-05)".
  - CLAUDE.md's operational-referent pass checks "Does the financing table match real swap charges?"
  - On this demo, realised swap is zero while the harness charges carry on every rollover (`tests/backtest/book.py:140-149`), another practice-vs-harness gap.
- **Fix:** declare that demo fills and costs may not calibrate C8 or satisfy the operational pass (the symbols' published swap *rates* remain usable), and exclude carry when comparing practice P&L with the harness.

### TAE-13 — Low · Likelihood: certain — the client heartbeat interval always exceeds the documented 10 s
- **External referent:** "make sure that you send a heartbeat to the server at least once every 10 seconds" (https://help.ctrader.com/open-api/faq/).
- **Code:** a heartbeat is due at `now − sent >= 10` (`wire.py:138-139`), polled every 1 s (`session.py:247-256`).
- **Reproduction** (`tae_heartbeat_gap.py`): send-to-send gaps of 10.932, 10.011, 10.012, 10.011 and 10.011 s. The server seems to tolerate at least 30 s (the proto), so the impact is small, but C-VEN-10 ("the strictest source wins") is not met.
- **Fix:** send once `now − sent >= heartbeat_s − poll`.

### TAE-14 — Low · Likelihood: certain for the demo as configured — layer 2 cannot act on the demo, and nothing tracks it
- **Referent:** dead-man's-switch practice (TAE-04's source) requires the switch to be able to act. ACIS-13 §1 done-when 5 reads "The watchdog plugin flattens a demo position while the engine is dead".
- **Code:** `config/watchdog.yaml` is `platform: mock`, `flatten_plugin: mock`, and lacks the `environment` and `ctid_trader_account_id` keys the cTrader plugin requires (`scripts/watchdog_plugins/ctrader_flatten.py:62-63`). TODO's demo steps do not mention the watchdog. OQ-06 (a second connection while the engine's is alive; Spotware: "At most, you should create two connections", F-04) is still unresolved.
- **Fix:** add a TODO/ledger item: commit the cTrader watchdog config and run §14.2 case 8 before any unattended practice run.

## Honest negatives (checked against the referent; no defect found)
- **Backoff is full jitter, faithfully.** Brooker (AWS Architecture Blog, 2015-03-04, https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) gives "sleep = random_between(0, min(cap, base * 2 ** attempt))". Code: `uniform(0, min(cap_s, base_s·factor^attempt))` with factor 2, attempt from 0, the RNG injected, the exponent capped at 64 against overflow (`ctrader_reconnect.py:50-51`).
- **Relative stop:** units of 1/100000 of price, measured from the entry, and a multiple of 10^(5−digits), matching the proto and the staff formula (F-14). No absolute stop on MARKET orders ("Not supported for MARKET orders"). IOC is sent explicitly, which matters because the `ProtoOANewOrderReq.timeInForce` default is GOOD_TILL_CANCEL.
- **Endpoints:** `wss://{demo|live}.ctraderapi.com:5036`, the host chosen from constants, and "Demo and live environments are fully separated" (F-01). With A2's `isLive` check, a practice binding cannot reach a live account through this code. Paper routes only to the paper venue (`wiring.py:99-104`).
- **Units:** volume in 0.01 units, spot prices in 1/100000, `clientOrderId` ≤ 50 characters (ACIS fragment ids are ≤ about 42), label ≤ 100, comment ≤ 512.
- **Reconcile:** `ProtoOAReconcileReq(returnProtectionOrders=false)` exposes `position.stopLoss` (proto, verbatim).
- **Hedging:** HEDGED "Allows multiple positions on a trading account for a symbol" (proto). The face's one-position rule plus `ClosePositionReq` for every close is the correct defence, and a reversal is close then open.
- **Server-side stops persist:** "All protections work across cTrader apps and remain active after your session ends" (re-fetched). Layer 1 holds while ACIS is down.
- **No window limit** on `ProtoOADealListReq` or `ProtoOAOrderListReq` in the pinned proto (only the cash-flow history has a one-week limit), so the single-window missed-deal query is valid.
- **Pepperstone:** hedging is allowed (https://pepperstone.com/en-eu/trading/accounts). The cTrader demo expires "after 90 days of inactivity", and the engine's logins reset that. The stop-out is "Equity falls below 50% of the required margin" with Smart Stop Out partial closes (https://pepperstone.com/en-af/help-and-support/new-to-trading/when-does-a-margin-call-and-stop-out-occur/); partial deals are de-duplicated by `dealId`, and at one minimum lot a stop-out is immaterial. Minimum lot and step are verified against the venue at attach, which fails closed if the venue is stricter.
- **Lead's claims confirmed on the server:** `1168 passed, 6 skipped in 186.55s`; `ledger_check.py`: 268 entries, 0 violations; every audited module is ≤ 300 lines (max 297), and each read opens with a mental model.

## What I could not verify
- The server's real heartbeat cadence and jitter (OQ-08; forum only, grade b/c). The JSON enum encoding (OQ-12; the docs' only example is app auth). Whether `netUnrealizedPnL` includes swap and commission (OQ-15; https://help.ctrader.com/open-api/profit-loss-calculation/ defines neither).
- The deal and order list chunk order and default chunk size. Whether `ProtoOAOrderErrorEvent` echoes `clientMsgId`. Whether spot subscriptions survive an in-place account re-auth. MARKET+IOC partial behaviour (OQ-17). A second-connection authorisation (OQ-06).
- Pepperstone's exact EURUSD and USDJPY `minVolume`/`stepVolume` on cTrader (only a secondary "0.01 lots"). The owner's demo account type (Razor or Standard), and whether demo commission is charged.
- Not assessed (outside this lens): the as-built position policy versus Carver's band, the minimum-lot sizing order, the demo evolution's date hygiene, and the "ONE open on the phase-7 market" claim. These belong to the internal lens.

## Residual risk
Money on the demo is protected by the venue-held stops, which persist without ACIS (F-16). The exposure is **availability and accounting**. The venue's unhappy paths (maintenance, account-session drops, quiet links, refusals, protocol drift) all lead either to self-sustaining restart loops or to zombie states that neither the reconnector nor the watchdog can see, and exactly-once fill delivery depends on undocumented paging order. The first demo session should measure OQ-08, the paging order and the re-auth semantics before any unattended run. Demo results are not evidence of live costs, carry or fills (TAE-12), and practice exits diverge from the graded harness (TAE-05).
