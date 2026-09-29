# ACIS-13 — Venue Adapters & the Attach Protocol — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-VENUE-013` |
| **Version** | 1.0 (**LOCKED** 2026-09-29 — the review pass, §15.3, by the lead) · 0.2 (2026-09-29 — the three BLOCKING questions ruled and folded in; first venue a Pepperstone cTrader demo) · 0.1 (authored 2026-09-24/25 by SPEC-AUTHOR) |
| **Status** | **LOCKED 2026-09-29** after the review pass (§15.3; the record is the v1.0 changelog). The BLOCKING rulings (OQ-01, OQ-02, OQ-03a) are folded in. Every question left open is a probe or attach-gating, and none blocks the build (TODO Track A step 3). |
| **Layer / DIR** | Platform adapters — `[DIR:core/data]` (shared transport+auth session, feed face) + `[DIR:core/execution]` (execution face) + `[DIR:scripts]` (the watchdog's cTrader flatten plugin) + `[DIR:tests/integration]` / `[DIR:tests/unit]` |
| **Consumes** | the cTrader Open API (first adapter); `config/platform_rules.yaml` (the active account's rulebook); `config/instruments.yaml` (enabled universe + §3.7 contract metadata); `config/system_config.yaml` (`active_account` + the new `venue:` block, §6.1); venue credentials from the environment / secret store (never YAML) |
| **Emits** | `RawTick` → ACIS-01 `MarketStateFactory`; `FillReport` / `BrokerPosition` / `BrokerAccount` / resting stops → ACIS-06 orchestrator and, downward, ACIS-07 Risk; `CapabilityDescriptor` + `AttachReport` → `acis://venues/adapters`; conformance verdicts |
| **Depends On** | `../ACIS_SPEC.md` §3, §3.5, §3.7, §7.5, §8.5, §8.6, §9, §9.5, §10, §12, §13, §15, §16, §18 · `ACIS-01` (feed-face contract, `RawTick`) · `ACIS-06` §4/§7.5/§8/§9 (`ExecutionFace`, `CapabilityDescriptor`, `FillReport`, `verify_attach`, the conformance suite) · `ACIS-07` (restart reconciliation, platform-measured drawdown) · `ACIS-12` §2–§4 (watchdog plugin surface) |
| **Blocks** | TODO Track A step 3 (the first real adapter build) and therefore the phase-12 demo run |
| **Corrections applied** | C-VEN-1…16 (§13); v1.0: the reconciliation with ACIS-06 v1.3/v1.4 (§5.2, §6.3, §6.5, §7.3), the mode-to-face rule (§7.1 A11), and the evidence re-fetch (Appendix A) |
| **Ledger IDs served** | GAP-0013 (session = transport+auth only), GAP-0018 (flat-or-decide), GAP-0020 (reconnect/backoff), GAP-P12D-42 (a stop must never be voidable), GAP-P12D-43 (the venue the owner can use), GAP-P12D-57 (lot step, minimum lot, request budget); interfaces to GAP-0075 (position policy), GAP-P12D-55 (restart anchors), GAP-P12D-58 (pre-close ban), GAP-P12D-59 (daily semantics), GAP-P12D-51 (host clock) |
| **Research base** | `../archive/RESEARCH_PROP_VENUES_2026-09-24.md` §3, §5, §7, §8; primary sources fetched 2026-09-24, quoted in Appendix A |

## Table of contents
1. Executive purpose & scope · 2. Boot/entry contract & inputs · 3. Architecture & responsibility · 4. Output contract · 5. Complete data schemas · 6. Algorithm & config set · 7. Core logic · 8. State machines & loop cadence · 9. Persistence & logging · 10. Store schema (DDL) · 11. Interface / MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Appendix A — Evidence register · Appendix B — Open questions · Changelog

**Citation convention.** `[F-nn]` points to a quoted, dated primary source in Appendix A. `[OQ-nn]` points to an open question in Appendix B. A fact without an `[F-nn]` is ACIS's own design, traced to a master § or a ledger ID. Anything the sources do not settle is written as an open question, never assumed.

---

## 1. Executive purpose & scope

**Purpose.** Attach ACIS to a real trading platform through the one master-§7.5 contract, so that the engine can trade a **demo account** (owner directive 2026-09-24) and, later, the owner's prop account on the same platform. The first concrete adapter is the **cTrader Open API**, for three reasons:
- cTrader is **first in the ratified §7.5 adapter order** after the v1 trio (master §7.5, GAP-0012);
- it is the platform of both prop firms that pass the automation filter, **FTMO and E8 Markets** (research §6);
- it serves the **first demo venue** (master v2.23, owner's delegation 2026-09-29): a **Pepperstone cTrader demo** (Pepperstone Markets Kenya, CMA licence 128), which expires only after 90 days of inactivity (trading or logging in resets it), unlike the 14-day FTMO Free Trial (§7.2) [F-43]. OANDA v20 is out: it excludes OANDA Global Markets, the division a Kenyan resident onboards to (GAP-P12D-43, re-verified 2026-09-24). The FTMO trial and a paid FTMO account attach later through the same protocol, behind the §15.2 preconditions.

cTrader's Open API works for demo and live accounts [F-36], serves every cTrader-affiliated broker's accounts by default [F-36], and is advertised by FTMO for its accounts [F-31].

**IS (in scope):**
- the **generic attach protocol** of master §7.5, made concrete step by step (§7.1), including the re-attach that account churn forces (§7.2);
- the **cTrader adapter package**: one shared session constrained to transport + authentication (GAP-0013), a feed face (`RawTick` producer, ACIS-01), an execution face (`ExecutionFace`, ACIS-06 §7.5), and a capability descriptor derived from venue data at attach time;
- the **prop-safety mechanics that live at the venue boundary**: a hard daily request budget (≤1,000, half the firm cap), lot-step rounding **down** with a minimum-lot refusal, a venue-schedule pre-check, and the rulebook load (§9.5);
- **reconnect/backoff** (GAP-0020), **restart reconciliation** input for ACIS-07, **unsolicited-fill ingestion** (server-side stop hits), and **server-side stop proof** (master §8.6 layer 1);
- the watchdog's **cTrader flatten plugin** (ACIS-12's `flatten_all` surface);
- the **conformance-suite extension** that a real venue needs.

**IS NOT (hard walls):**
- It does not size, signal, or decide *whether* to trade. It never changes `size_units` upward; it may only round down to the venue's lot step or refuse (C-EXE-6, §6.3).
- It does not write, draft, or change any rulebook value, guardrail, the equity floor, or HALT/veto semantics. The rulebook drafts in research §8 are **not applied**. Where the demo needs an owner ruling on those, this spec names the dependency and stops (Appendix B).
- It does not change the §9.5 rulebook schema. GAP-P12D-54/-58/-59 own that. §15 lists the ones that gate an FTMO attach.
- It builds no other platform adapter. DXtrade, TradeLocker, Match-Trader, IBKR and futures gateways attach later through the same generic protocol (§7.1); only cTrader is concrete here. MT5 stays in master §15; OANDA v20 is not pursued (GAP-P12D-43).
- It does not automate the OAuth consent screen, register an application, or create any account. Those are **human, out-of-band steps** (§2.3). Spotware's terms require the trader's explicit prior approval for trading on his behalf [F-33]; the owner's OAuth grant with `trading` scope plus his §12 mode arming is that approval.
- No depth-of-market subscription, no trend-bar subscription, no market-data product: the feed face streams top-of-book spots only (lean-build, master §18). The venue's tick history (at most one week per request, historical rate limit 5/s [F-24][F-05]) could later calibrate the C8 cost model to the destination feed (GAP-P12D-41). Fetching it is not part of the demo path, and it would spend request budget.
- No web server, no dashboard (master §17).

**Done-when (all must hold):**
1. Every `ACIS-06` conformance case passes against a cTrader **demo** account, plus the real-venue cases of §14.2, in one recorded session.
2. The attach protocol is proven end to end, including: flat-or-decide refusing a pre-populated account; an environment mismatch refusing to attach; a churned account re-attaching only after a human re-grant.
3. The request budget is proven to refuse opens at `budget − reserve` and to leave the close/flatten reserve usable.
4. A position opened by ACIS carries a stop that **the venue** reports, and the stop survives the engine process being killed (§14.2, C-VEN-2).
5. The watchdog plugin flattens a demo position while the engine is dead (§14.2), or [OQ-06] is ruled.
6. Every glitch class of §14.3 has a test.
7. Appendix B's BLOCKING questions are ruled and folded back into this text (done 2026-09-29).

## 2. Boot/entry contract & inputs

### 2.1 Entry points
- `core/data/ctrader/session.py::CTraderSession` — one per venue connection; transport + authentication only (§3.2).
- `core/data/feeds.py` registers `core/data/ctrader/feed.py::CTraderFeed(FeedConnector)` — the feed face (ACIS-01 §3).
- `core/execution/venue.py` registers `core/execution/ctrader_face.py::CTraderExecutionFace(ExecutionFace)` — the execution face (ACIS-06 §7.5).
- `core/execution/venue.py::verify_attach(...)` — ACIS-06's phase-8 half of the attach, extended by the phase-12 checks of §7.1. This extension adds checks; it removes none.
- `scripts/watchdog_plugins/ctrader_flatten.py::CTraderFlattenPlugin` — registered in `scripts/acis_watchdog.py::_PLUGINS`. It has zero `core/` imports (ACIS-12 §3).

### 2.2 Inputs at boot
- `system_config.yaml`:
  - `active_account` (exists today) — names the rulebook in `platform_rules.yaml`.
  - The new `venue:` block (§6.1): adapter, environment, the explicit account binding, the budget, and the timers. It is schema-validated and a bad block refuses to start (master §9).
- `platform_rules.yaml[active_account]` — **a missing rulebook is fatal** (master §7.5, §9.5). Its `platform` field must equal `ctrader`, or attach is fatal (`ATTACH_PLATFORM_MISMATCH`).
- `instruments.yaml` — the enabled universe and its §3.7 contract metadata, cross-checked against the venue (§6.4).
- **Credentials**, from the environment or a secret store and never from YAML (ACIS-01 §2):
  - `clientId` and `clientSecret` of the owner's registered Open API application;
  - the token store file (§5.5), whose path comes from an environment variable. It holds the access token and the refresh token.

### 2.3 Human preconditions (outside ACIS; attach refuses if any is missing)
1. **An Open API application is registered and approved.** A new application is "submitted" and "reviewed by Spotware", which contacts the owner by email [F-11]. The lead time is unknown [OQ-13].
2. **An OAuth grant with `trading` scope exists for the exact account.**
   - `accounts` scope is view-only; `trading` is required to trade [F-08].
   - For development and demo, the Open API **Playground** issues a token for the owner's own cTID [F-10].
   - For production, a redirect URI of the owner's own is needed. The default URI "must never be used for a production application" [F-10], and whether a headless single-user deployment may use a local redirect is [OQ-13].
3. **The account's `ctidTraderAccountId` is committed** to `system_config.yaml → venue.ctid_trader_account_id` by a human. ACIS **never** picks an account from the list by position (C-VEN-5). Spotware's own samples do exactly that (`ctidTraderAccount[0]`) [F-08], and that pattern is forbidden here.
4. **Accounts created after a grant are not covered by it.** Per Spotware, such accounts "will not be authorised inside the application", and the user must repeat the consent [F-09]. Every new FTMO Free Trial is a new account [F-30], so **every trial renewal repeats precondition 2** (§7.2).

### 2.4 Boot preconditions checked by ACIS (fail fast, refuse to start)
- The config schema is valid; `venue.daily_request_budget ≤ 1000` (schema maximum, §6.5).
- The token store is readable **and writable by this process only** (the refresh token rotates, §6.7).
- **Host clock sanity (GAP-P12D-51).** The first spot event carries the venue's timestamp [F-23]. If `|venue_ts − local_now|` exceeds `data.clock_skew_tolerance_ms` (ACIS-01 §6), attach is **fatal** (`ATTACH_CLOCK_SKEW`). The development laptop has been measured 16 minutes slow (GAP-P12D-51). On such a host every tick would read as stale or future, so ACIS refuses rather than trade on a lying clock.
- The request-budget **feasibility check** of §6.5 passes.

## 3. Architecture & responsibility

### 3.1 Package layout (lean: five production modules, each ≤ 300 lines per A12)
```
core/data/ctrader/                [DIR:core/data]
  __init__.py
  wire.py        framing + serialisation + clientMsgId correlation + heartbeat (§6.2)
  session.py     CTraderSession: connect → app auth → account auth → token refresh →
                 backoff → request-budget gate. Transport + auth ONLY (GAP-0013).
  schema.py      the message model, from Spotware's .proto at a pinned commit [F-28]
  feed.py        CTraderFeed (FeedConnector): spots → RawTick
core/execution/ctrader_face.py    [DIR:core/execution]  CTraderExecutionFace
scripts/watchdog_plugins/ctrader_flatten.py  [DIR:scripts]  self-contained; zero core/ imports
tests/unit/test_ctrader_*.py      recorded-frame protocol mapping (no network)
tests/integration/test_adapter_conformance.py   + a "ctrader" entry, env-gated (§14.2)
```

**Why the session lives in `core/data`.** The import contract gives `data` no imports, and `execution` may import `data` (`tests/unit/test_import_contract.py::ALLOWED`). So the shared session and the message model must sit in `core/data`, and the execution face imports them downward-legally. The feed face never imports `core/execution`.

### 3.2 The GAP-0013 constraint, made structural
`CTraderSession` owns exactly the following, and nothing else:
- the socket;
- authentication state (application authorised, account authorised, token expiry);
- the pending-request map keyed by `clientMsgId`;
- the outbound request ledger that feeds the budget (§6.5);
- the backoff counters.

It carries **no market, account, or position state**. Inbound frames are **routed by `payloadType` without being interpreted**:
- `ProtoOASpotEvent` goes to the feed face's queue.
- `ProtoOAExecutionEvent`, `ProtoOAOrderErrorEvent`, `ProtoOATraderUpdatedEvent`, `ProtoOAMarginChangedEvent`, `ProtoOAAccountDisconnectEvent`, `ProtoOAAccountsTokenInvalidatedEvent` and `ProtoOAClientDisconnectEvent` go to the execution face's queue and to the session's own auth-state machine (the last three only).
- Responses resolve their pending future by `clientMsgId`.

The conformance suite extends `test_gap0013_feed_face_still_exposes_no_account_surface` to the session: no public member of `CTraderSession` or `CTraderFeed` may match `account|position|equity|margin|balance|order` (§14.1). The execution face's own reads of account and position state flow only downward to Risk (master §7.5).

### 3.3 Transport choice — DECIDED: route C, JSON over WebSocket via `aiohttp` [OQ-02, resolved 2026-09-29]
Three routes exist. The adapter's internal model is the same in all three: field names and enums from the pinned `.proto` [F-28]. So switching routes touches only `wire.py`.

| Route | Evidence | Dependency cost | Verdict |
|---|---|---|---|
| **A. Official Python SDK `ctrader-open-api` (OpenApiPy)** | MIT. Built on **Twisted**, and it pins `Twisted==24.3.0`, `pyOpenSSL==24.1.0`, `protobuf==3.20.1`, `requests==2.32.3` and `inputimeout==1.0.4`. The latest release is 0.9.3 (2024-08-06). Its TCP layer sends its own heartbeat only after **more than 20 s** without sending (it also echoes each server heartbeat), drains its send queue **once per second at 5 messages/s** by default, and keeps that queue as a **class attribute** shared by every instance [F-27]. | 5 pinned deps and a second event-loop model | **Rejected.** ACIS's loops are asyncio (master §10, §16). The SDK's defaults contradict the documented contract: its own heartbeat waits for 20 s of silence against the documented 10 s [F-03], and it can add up to 1 s of queueing before a stop amendment or a flatten leaves the host. |
| **B. Protobuf over TLS/TCP, port 5035, stdlib `asyncio` + `ssl`** | The framing is documented: a 4-byte length prefix in network order, then a `ProtoMessage` [F-06]. TLS is mandatory [F-02]. | `protobuf` runtime only | Viable. It needs a **master §16 edit**: §16 allows an adapter-tier *official client SDK*, and the `protobuf` runtime alone is not one. |
| **C. JSON over WebSocket, port 5036, via `aiohttp`** | Officially supported: "If you intend to use JSON, there is no need to use our SDKs"; ports 5035 and 5036 both take TCP or WebSocket [F-01][F-07]. JSON's framing over *raw TCP* is undocumented, but a WebSocket frames each message itself. | **none**: `aiohttp` is already in §16 | **CHOSEN (OQ-02, 2026-09-29).** Zero new dependency, no §16 edit. Unknowns: how JSON encodes enums and whether frames are text or binary [OQ-12]. Both are cheap to settle in the first demo probe. |

If the first probe finds a JSON gap, fall back to B and raise the §16 edit. Either way the framing code is small (§6.2) and is declared as not re-implementing a usable proven part: the proven part, route A, is unusable in this runtime (master §18 proven-parts law, boundary 3).

### 3.4 What the adapter must NOT do
- It must not import any core layer above its own (master §2). The session and feed face import nothing from `core/execution`.
- The feed face must not handle execution, order, account or trader events. The execution face must not subscribe to spots: quotes reach execution only as prices on orders (import-contract comment, `ALLOWED["execution"]`).
- It must not emulate a missing capability silently (master §7.5). It rejects loudly.
- It must not act on text from the venue. Error `description`s, `reason`s, symbol descriptions, broker names and position comments are **data** (master §3.5 untrusted-input law). Control flow keys only on the enumerated `errorCode` and `payloadType` values (C-VEN-15).
- It must not log a secret (C-VEN-8).

## 4. Output contract

No new boundary dataclass crosses a layer. The adapter produces the **locked** ACIS types. Two adapter-local frozen records, `VenueSymbolSpec` and `AttachReport` (§5), are published only on `acis://venues/adapters` and in logs.

### 4.1 `RawTick` (feed face → ACIS-01)
| `RawTick` field | cTrader source | Rule |
|---|---|---|
| `event_time` | `ProtoOASpotEvent.timestamp` | **Required.** The face subscribes with `subscribeToSpotTimestamp = true` [F-23]; an event without a timestamp raises `DataQualityError` (no fabricated time). The unit is taken as milliseconds UTC [OQ-08]. |
| `recv_time` | local clock at frame receipt | injected clock (ACIS-06 §5 pattern) |
| `instrument` | reverse `symbol_map[symbolId]` | an unknown `symbolId` is logged `FEED_UNKNOWN_SYMBOL` and dropped (never guessed) |
| `bid`, `ask` | `bid` / `ask` ÷ 100 000, rounded to `digits` [F-23] | **Both sides are optional per event** [F-23]. The face keeps the last known bid and ask per symbol and emits a `RawTick` only once both are known. Every emitted tick carries `raw_payload.sides_updated ∈ {bid, ask, both}`, so a carried-forward side is visible, never silent. |
| `volume` | — | Spot events carry no volume. The field is omitted, and the descriptor declares `quote_volume = False` (§5.2). This interacts with GAP-P12D-47: volume-reading modules have no venue volume here. |
| `book` | — | not subscribed (`quote_depth = False`) |
| `provider` | `"ctrader"` | |
| `raw_payload` | the decoded event plus `snapshot: bool` | `snapshot = True` on the first ("technical") event after each subscription, which carries "latest spot prices even if market is closed" [F-23]. ACIS-01's staleness flag then does its job. |

### 4.2 `FillReport` (execution face → orchestrator → Risk), ACIS-06 §4, unchanged shape
One `submit_order` call returns **one** `FillReport` for the whole venue order. A cTrader order can produce several execution events (`ORDER_ACCEPTED`, then `ORDER_PARTIAL_FILL`, then `ORDER_FILLED`, or `ORDER_CANCELLED` for an IOC remainder) [F-17], and the face aggregates them into that one report.

| `FillReport` field | Mapping |
|---|---|
| `fill_id` | `f"ct:{account_key}:{orderId}"`: one per venue order, stable across restarts |
| `order_id`, `fragment_id`, `requested_price`, `session_id` | passed in by the orchestrator; `fragment_id` is also sent as `clientOrderId` (§7.3) |
| `instrument` | reverse `symbol_map` |
| `direction` | `BUY → +1`, `SELL → −1` (`tradeSide`) |
| `fill_price` | the volume-weighted mean of `deal.executionPrice` over the order's deals, weighted by `deal.filledVolume` [F-38]. It is 0.0 on REJECTED or CANCELLED (the ACIS-06 invariant). |
| `filled_units` | `Decimal(Σ deal.filledVolume) / 100`: the protocol volume is in 0.01 units [F-13]. Exact Decimal, no float (F17). |
| `remaining_units` | `requested_units − filled_units` |
| `slippage_bps` | the existing `slippage_bps(requested, fill, direction)` helper |
| `fill_time` | the last deal's `executionTimestamp` (ms UTC) → tz-aware `datetime` |
| `venue` | `descriptor.venue` (`"ctrader"`) |
| `status` | `FILLED` if filled == requested · `PARTIAL` if 0 < filled < requested and the remainder is terminal (IOC-cancelled) · `REJECTED` on `ORDER_REJECTED`, `ProtoOAOrderErrorEvent` or `ProtoOAErrorRes` with nothing filled · `CANCELLED` on `ORDER_CANCELLED`/`ORDER_EXPIRED` with nothing filled |

**Venue costs are not a `FillReport` field** (ACIS-06 §4 is locked). Each deal's `commission`, and on closing deals the `swap`, `grossProfit`, `pnlConversionFee` and resulting `balance` [F-38], are logged as `VENUE_COSTS` on `trade_log` for the C8 cost calibration (GAP-P12D-41/-46). They reach Risk through `account_snapshot()` (§4.4).

### 4.3 `BrokerPosition` and resting stops
- Source: `ProtoOAReconcileReq(returnProtectionOrders = false)`, so `position.stopLoss` carries the venue-held stop [F-18].
- `instrument` comes from the reverse map; `direction` from `tradeData.tradeSide`; `size_units = Decimal(tradeData.volume) / 100`; `stop_loss = position.stopLoss` (`None` if absent).
- Positions whose `tradeData.label` does not carry this binding's ACIS label (§7.3) are **foreign**. At attach they trigger flat-or-decide. At runtime they are surfaced as reconciliation drift to Risk (ACIS-07 C-RSK-5), and are never adopted silently.
- `resting_stops()` returns `{instrument: position.stopLoss}` for ACIS positions from a **fresh** venue query, never from a cache. The conformance gate needs a query that an engine restart could reproduce (ACIS-06 §7.5).

### 4.4 `BrokerAccount`
- `balance = Decimal(trader.balance) / 10**trader.moneyDigits` [F-21].
- `equity`: cTrader has **no equity field** [F-40]. So `equity = balance + Σ netUnrealizedPnL / 10**moneyDigits` (`ProtoOAGetPositionUnrealizedPnLReq`) **− Σ estimated closing commission**. `netUnrealizedPnL` "does not include potential closing commission" [F-25], while FTMO tests equity as "Balance + Open Positions P/L ± Swaps – Commissions" (research §2.1).
- Whether `netUnrealizedPnL` already includes swaps and the opening commission is [OQ-15]. Until it is ruled, the face subtracts **both** estimated closing commission and accrued swap (`position.swap`) when their sign is adverse.
- The binding rule is C-VEN-12: **equity is never overstated.** It is guardrail-adjacent, since it feeds the equity breaker and the §9.5 platform-measured series.
- `margin_used = Σ position.usedMargin / 10**position.moneyDigits` [F-37].
- Each snapshot costs **two requests**, so its cadence is budgeted (§6.5).

## 5. Complete data schemas

### 5.1 `VenueSymbolSpec` (frozen, adapter-local; one per enabled instrument, rebuilt at every attach)
| Field | Type | Source [F-20] | Validation |
|---|---|---|---|
| `engine_symbol` | str | `instruments.yaml` key | enabled |
| `venue_name` | str | `ProtoOALightSymbol.symbolName` matched **exactly** against `venue.symbol_names[engine_symbol]` | exactly one match, and `enabled = true`; else fatal |
| `symbol_id` | int | `symbolId` | **per server**: "Different servers have different IDs". Never cached across accounts or servers. |
| `digits` | int | `digits` | `10**-digits == instruments.tick_size`; else fatal |
| `pip_position` | int | `pipPosition` | recorded |
| `lot_size_units` | Decimal | `lotSize / 100` | FX: must equal `UNITS_PER_LOT` (100 000, `core/execution/venue.py`); else fatal (C-VEN-11) |
| `min_volume_units` / `step_volume_units` / `max_volume_units` | Decimal | `minVolume` / `stepVolume` / `maxVolume` ÷ 100 ("in cents") | > 0; the §6.4 cross-check |
| `sl_distance`, `distance_set_in` | int, enum | `slDistance`, `distanceSetIn` | converted to a price distance by §6.3 (points ÷ 10^digits, or hundredths of a percent of price) [F-41]; confirmed by probe [OQ-09] |
| `trading_mode` | enum | `tradingMode` | must be `ENABLED`; `CLOSE_ONLY_MODE` means opens are refused and `acis://venues/adapters` says so |
| `schedule`, `schedule_tz`, `holidays` | tuple, str, tuple | `schedule` (seconds from Sunday 00:00 in `scheduleTimeZone`), `holiday` | recorded; used for the §7.3 closed-market pre-check |
| `swap_long`, `swap_short`, `swap_calc`, `swap_3day`, `swap_time_min`, `swap_period_h` | — | swap fields | logged for the C8 carry calibration (GAP-P12D-05) |
| `commission_rate`, `commission_type`, `min_commission` | — | `preciseTradingCommissionRate`, `commissionType`, `preciseMinCommission` | logged; feeds the §4.4 closing-commission estimate |
| `pnl_conversion_fee_rate` | int (1 = 0.01%) | `pnlConversionFeeRate`: charged when the quote asset ≠ the deposit asset | **surfaced at attach**. Whether this field is how FTMO applies its 0.7% currency adjustment (T&C 5.3.4) is [OQ-11]. The cost model owns the consequence (GAP-P12D-52 item 12). |

### 5.2 `CapabilityDescriptor` values for cTrader (ACIS-06 §7.5; derived at attach, declared as data)
| Field | Value | Basis |
|---|---|---|
| `venue` | `"ctrader"` | |
| `order_types` | `{"market"}` | v1 uses market orders only. "A declared capability must work" (ACIS-06 conformance), so LIMIT and STOP are not declared until something uses and tests them. |
| `supports_ioc` | `True` | `timeInForce = IMMEDIATE_OR_CANCEL` exists [F-35]. That a MARKET order honours it is [OQ-17], proven in conformance. |
| `account_model` | `"hedging"` if `ProtoOATrader.accountType == HEDGED`; `"netting"` if `NETTED` | `SPREAD_BETTING` is attach-fatal [F-21] |
| `partial_close` | `True` | `ProtoOAClosePositionReq(positionId, volume)` [F-13] |
| `min_lot`, `lot_step`, `max_order_lots` | the **strictest** across enabled symbols: max of minima, the coarsest step, min of maxima (in lots of `lot_size_units`) | The descriptor is per venue but cTrader's limits are **per symbol** [F-20]. The orchestrator rounds to these venue-wide values before dispatch (ACIS-06 v1.3 C-EXE-8, `venue_quantity`), and the face enforces the exact per-symbol values at submit, so no per-symbol descriptor field is needed (OQ-03b resolved). |
| `symbol_map` | `{engine_symbol: venue_name}` from §5.1 | the §13 suffix law, solved once |
| `quote_depth` | `False` | not subscribed (lean) |
| `asset_classes` | the classes of the enabled symbols (`{"fx"}` for the demo universe) | |
| `server_side_stops` | `True` | "server-side protections … remain active after your session ends" [F-16] |

**Adapter-local venue profile**, published on `acis://venues/adapters` next to the descriptor. These fields are not ACIS-06 descriptor fields and stay adapter-local: above the face, only the conformance suite's relative-stop variant reads one (ACIS-06 v1.4):
- `stop_semantics = "relative_on_market"`: an absolute `stopLoss` is "Not supported for MARKET orders", and only `relativeStopLoss` rides on a market order [F-13].
- `quote_volume = False`.
- `environment ∈ {demo, live}`.
- `request_budget`, `close_reserve`.

### 5.3 `AttachReport` (frozen; logged and published)
`venue`, `environment`, `host`, `ctid_trader_account_id`, `trader_login`, `broker_name`, `is_live` (from the account list [F-22]), `account_type`, `deposit_asset`, `money_digits`, `access_rights`, `is_limited_risk`, `leverage_in_cents`, `registration_ts`, `initial_balance_observed` (`balance` at the first-ever attach of this binding; recorded for GAP-P12D-55, whose anchor policy stays owner-owned), `symbols: tuple[VenueSymbolSpec]`, `rulebook_key`, `rulebook_hash` (§9.5), `account_class` (the rulebook's, §7.1 A2), `open_positions`, `pending_orders`, `clock_skew_ms`, `verdict ∈ {ATTACHED, HALTED_OPEN_POSITIONS, FATAL}`, `reason`, `attached_at`.

### 5.4 Account key
`account_key = f"ctrader:{environment}:{ctid_trader_account_id}"`. Every piece of persisted adapter state is keyed by it (§10), so nothing leaks from a dead account into its successor (§7.2, C-VEN-5). Position ids can collide across brokers [F-37], so they are never used without this key.

### 5.5 Token store (secret; not in the DB, not in the repo)
- One JSON file at `$ACIS_CTRADER_TOKEN_STORE`, mode 0600: `{access_token, refresh_token, expires_at_utc, obtained_at_utc, scope}`.
- **Single writer:** the engine's session. Readers: the watchdog plugin, read-only (§7.9).
- Writes go to a temporary file, then `fsync`, then an atomic rename (C-VEN-8).

## 6. Algorithm & config set

### 6.1 Config block (`system_config.yaml → venue:`; schema-fatal if missing or invalid when `adapter != mock`)
```yaml
venue:
  adapter: ctrader                 # mock | ctrader
  environment: demo                # demo | live — must equal the account's isLive (§7.1 A2)
  ctid_trader_account_id: 0        # HUMAN-committed per account; never auto-selected (C-VEN-5)
  symbol_names: {EUR_USD: "EURUSD", USD_JPY: "USDJPY"}   # exact venue names; verified at attach [OQ-11]
  transport: json_ws               # json_ws (OQ-02, chosen) | protobuf_tcp (fallback, needs a §16 edit)
  daily_request_budget: 1000       # schema max 1000 (half the FTMO/E8 cap, GAP-P12D-57)
  close_reserve: 100               # requests only closes/flatten/stop-repair may spend
  max_orders_per_day: 50           # the §6.5 order allowance; the 51st open in any rolling 24 h is refused
  heartbeat_s: 10                  # documented cadence [F-03]; schema max 10
  liveness_timeout_s: 30           # no inbound frame for this long = dead link
  order_ack_timeout_s: 10          # then reconcile by clientOrderId — never blind resubmit
  stop_confirm_timeout_s: 3        # §7.3 step 6
  equity_poll_s: 300               # unrealized-PnL poll while positions are open (§6.5)
  reconcile_interval_s: 900        # periodic venue-truth reconcile while positions are open
  backoff: {base_s: 1, factor: 2, cap_s: 60, max_consecutive: 10}
  rate_limit_per_s: {general: 25, historical: 2}   # half the documented 50 / 5 [F-05]
```
Endpoints are constants, not config: demo `demo.ctraderapi.com`, live `live.ctraderapi.com`; port 5035 for Protobuf, 5036 for JSON [F-01]. They are selected by `environment`, so the config cannot aim a demo binding at the live host.

### 6.2 Wire rules
- **Envelope:** `ProtoMessage{payloadType, payload, clientMsgId}` [F-06]. JSON uses the same three keys [F-07]. Every request carries a fresh `clientMsgId`, and responses are matched by it.
- **Framing:** for B, a 4-byte big-endian length followed by the bytes [F-06]; for C, one message per WebSocket frame.
- **Heartbeat:** send `ProtoHeartbeatEvent` whenever nothing has been sent for `heartbeat_s` (10 s). The docs say "every 10 seconds" [F-03]; the proto says "longer than 30 seconds"; the SDK waits 20 s [F-27]. **The strictest source wins** (C-VEN-10). Heartbeats are events, not requests, and are excluded from the budget (§6.5, [OQ-04]).
- **Liveness:** no inbound frame of any kind for `liveness_timeout_s` means the link is dead, and the reconnect path of §8.1 starts. The server's own heartbeat cadence is undocumented [OQ-08].
- **Local rate limit:** token buckets at 25/s for general requests and 2/s for historical ones, half the documented per-connection limits [F-05]. A `REQUEST_FREQUENCY_EXCEEDED` or `BLOCKED_PAYLOAD_TYPE` reply pauses that payload type for `retryAfter` seconds when given [F-05].

### 6.3 Units, rounding and stops (exact; `Decimal` throughout)
- **Volume:** `protocol_volume = int(units × 100)`, which must be exact; a non-integral result is a `DataQualityError`. `units = Decimal(protocol_volume) / 100` [F-13].
- **Lot-step rounding (GAP-P12D-57): down, never up.**
  - `quantize(sym, units) = floor(units / step) × step`, capped at `max_volume_units`.
  - A result below `min_volume_units` is **0**, which means "not placeable here". It is never rounded up, because rounding up breaks the Governor's clamp-only-downward law and C-EXE-6.
  - The orchestrator already rounds down to the descriptor's strictest-of step before fragmenting and dispatching (ACIS-06 v1.3 C-EXE-8, `venue_quantity`; OQ-03b resolved). The face's `quantize()` applies the exact per-symbol values, so no request is spent on a volume the venue will refuse.
  - The face **also** validates on submit. A non-quantized or below-minimum volume returns a `REJECTED` `FillReport` with reason `VENUE_VOLUME_INVALID` **without contacting the venue**.
  - Every downward rounding is logged `VENUE_LOT_ROUNDED{requested, placed}`.
- **Prices:** absolute prices sent to the venue are rounded to `digits` [F-14].
- **Relative stop on a market open:**
  - `d = |requested_price − stop_loss|`, rounded **down** to the tick (`10**-digits`), so the stop is never further away than the Governor sized.
  - `relativeStopLoss = int(d × 100 000)`, which must satisfy `relativeStopLoss % 10**(5 − digits) == 0`. Spotware's staff give the formula `Round(entry − stop, digits) × 100000`, and the venue rejects anything else with "Relative stop loss has invalid precision" [F-14].
  - **The minimum stop distance as a price distance.** In points mode it is `slDistance / 10**digits`. In percentage mode it is `slDistance / 100` percent of the current price. The docs define both modes this way for `gslCharge`, and `distanceSetIn` governs `slDistance` with the same unit [F-41]. The probe of [OQ-09] confirms this before the pre-check is trusted.
  - `d = 0` or `d <` that minimum returns `REJECTED`, reason `VENUE_STOP_TOO_CLOSE`, **without contacting the venue**. If the probe disproves the unit, the pre-check is disabled (the venue rejects with `TRADING_BAD_STOPS`, which is safe) until the spec is corrected.
  - **Why relative is risk-faithful.** The venue sets `stop = fill ∓ d` [F-13]. The per-unit loss from the fill to the stop therefore equals the distance the Governor sized, whatever the entry slippage. With an absolute stop kept at the Governor's level, adverse slippage would add to the loss.
  - **The consequence for the conformance gate.** On this venue the resting stop equals `fill ∓ d`, not the Governor's `stop_loss` value. The ACIS-06 suite asserts exact equality (`test_server_side_stop_rests_at_broker`), so this venue runs its relative variant (ACIS-06 v1.4; OQ-03d resolved).

### 6.4 Contract cross-check against `instruments.yaml` (master §3.7: "incomplete contract metadata ⇒ not tradeable")
| Check | Rule |
|---|---|
| tick | `10**-digits == tick_size`; else **fatal** (a pip assumption that lies is a bug, §3.7) |
| lot size | FX `lot_size_units == 100000`; else **fatal**. The orchestrator's lot arithmetic hardcodes `UNITS_PER_LOT` (C-VEN-11). |
| minimum and step | If the venue is **stricter** than `instruments.yaml` (a larger minimum, a coarser step), attach is **fatal** until a human commits the venue's values, so the sizing and cost models do not lie. A looser venue is logged only. |
| quote currency | `quoteAssetId` → asset name must equal `quote_ccy`; else fatal |
| deposit currency | `depositAssetId` must be **USD**; else fatal. ACIS accounting and the harness are USD (GAP-P12D-05). |
| schedule | venue trading intervals vs the instrument's calendar: disagreements are logged `CALENDAR_VENUE_DISAGREEMENT` and published. The venue's "closed" always wins for entries (§7.3). |

### 6.5 The daily request budget (GAP-P12D-57; prop-safety)
- **Scope (conservative until [OQ-04] is answered).** FTMO's text counts requests on trades or orders "being opened, modified, or closed", and its FAQ counts "2000 max positions per day" (research §1) [F-32]. Neither says whether data or account queries count. So ACIS counts **every outbound request except `ProtoHeartbeatEvent`**. If heartbeats counted, no connection could comply at all (8,640 a day at the documented cadence).
- **The window is a rolling 24 hours.** A cap of N over every rolling 24-hour window implies at most N in every calendar day in every time zone. That makes the rule independent of whose "day" the firm means (cf. GAP-P12D-59).
- **The cap:** `daily_request_budget ≤ 1000`, half the FTMO and E8 cap of 2,000 (GAP-P12D-57; the SCOUT's recommendation, repeated in the brief). The schema maximum is 1,000; a human may set it lower, never higher (C-VEN-4).
- **The close reserve.** The last `close_reserve` requests (default 100) may be spent **only** on closes, flatten, stop repair (§7.3 step 6) and the reconciles those need.
  - When `used ≥ budget − close_reserve`, every **open** is refused with `EXEC_CAPABILITY_REJECT`, reason `VENUE_BUDGET_OPEN_EXHAUSTED`, and surfaced.
  - When `used ≥ budget`, opens, queries and subscriptions stop and `VENUE_BUDGET_EXHAUSTED` is raised as a health event. **Reduce-only closes and stop repair still pass, paced by ACIS-06 v1.3 C-EXE-8**: exits are never blocked (the v1.0 review resolved the draft's "all venue requests stop" in the locked spec's favour). The pacing bounds them (100 attempts, then one per 300 s: at most 388 in 24 h), so the budget, the paced closes and the watchdog's flatten (§7.9, outside this counter by design) stay inside the firm's 2,000. Positions stay protected by their server-side stops (C-VEN-2).
  - Exits are never starved by entries.
- **Two meters, one rule (reconciled with ACIS-06 v1.3 C-EXE-8).** The orchestrator's `max_venue_requests_per_day` meters trading submits; this adapter meters every request. For a cTrader venue the orchestrator's limit is set ≤ `daily_request_budget − close_reserve`, checked at boot (A9), so the orchestrator refuses an open before the adapter has to.
- **Fragments count.** Every fragment is its own `ProtoOANewOrderReq`. The orchestrator's fragmentation above `fragment_threshold_lots` multiplies requests (GAP-P12D-57).
- **Feasibility check at boot** (deterministic; boot-fatal if it fails):
  `projected = connect_overhead × (1 + max_reconnects_per_day) + 86400 / equity_poll_s × 2 + 86400 / reconcile_interval_s + order_allowance`, which must be ≤ `budget − close_reserve`.
  - `connect_overhead` is about 8 requests: application auth, account list, account auth, trader, symbols list, symbol-by-id, reconcile, subscribe.
  - `order_allowance` is `venue.max_orders_per_day × 2`: an open and a close each. The face refuses the (N+1)-th open in any rolling 24 h (`VENUE_ORDER_ALLOWANCE_SPENT`), so the check certifies without waiting on the position policy's own rate. **Still no venue attach before GAP-0075's firehose fix** (TODO Track A preconditions), whatever the check says.
  - Defaults: 8 × 11 + 576 + 96 = 760 leaves 140 requests for orders, 70 round trips a day, and `max_orders_per_day = 50` uses 100 of them. **Re-derived by the v1.0 review:** under the ratified R-1 direction (daily rules behind Carver's no-trade band, GAP-P12D-118) the order rate is a few round trips a day, so the defaults stand. What FTMO counts stays [OQ-04].
- The budget state (`used_24h`, `cap`, `reserve`, `projected`) is published on `acis://venues/adapters` and persisted (§10), so a restart does not reset it. **A restart is never a relaxation** (GAP-0050 principle, GAP-P12D-55).

### 6.6 Reconnect and backoff (GAP-0020)
- The delay is exponential with **full jitter**: `delay = uniform(0, min(cap_s, base_s × factor**attempt))`. The RNG is injected: `SystemRandom` in production, seeded in tests (the ACIS-06 §5 pattern).
- `ProtoErrorRes.maintenanceEndTimestamp` or `SERVER_IS_UNDER_MAINTENANCE` means: sleep until the stated end plus jitter, logged `VENUE_MAINTENANCE{until}`. Spotware does maintenance "during weekends" [F-26].
- After `max_consecutive` failures: `VENUE_UNREACHABLE` health event, surfaced. **It is not a HALT by itself.** A stalled fast loop with open positions is Risk's flatten-and-halt (master §10). If the venue is unreachable, that flatten cannot execute; the resting server-side stops and the watchdog remain the defence (master §8.6).
- **Every successful reconnect passes through `SYNCING` (§8.1)** before any new dispatch. SYNCING means reconcile against venue truth, ingest the deals executed while down (§7.8), re-subscribe spots, and re-baseline the feed with a logged `FEED_RECONNECT`, gap logged and not interpolated (ACIS-01 §7 step 8).
- Reconnect attempts spend budget and count in the feasibility check.

### 6.7 Token lifecycle
- The access token lives 2,628,000 s (about 30 days). The refresh token does not expire until it is used, or until the user re-authorises [F-08].
- **Refresh proactively** when fewer than 7 days remain, and only at a quiet moment (no working order, no pending request). A refresh returns a **new pair**, and "the old values … are automatically invalidated" [F-08]. The server then emits `ProtoOAAccountsTokenInvalidatedEvent`, whose reasons include "token was refreshed" [F-12], and the account must be re-authorised on the connection.
- **Order of operations:** persist the new pair (§5.5 atomic write) → re-authorise the account → only then resume dispatch.
- If a refresh fails or the refresh token is rejected, `token_state = DEAD` and the binding goes `DETACHED` (§8.1): no new opens; stops still rest at the venue. The recovery is a **human** re-grant (§2.3).

## 7. Core logic

### 7.1 The attach protocol — generic steps (master §7.5), with cTrader specifics
Each step logs `ATTACH_STEP{n, result}`. Any failure stops the attach with a named verdict. Nothing downstream starts until A11.

- **A1 — Select the adapter and load the rulebook.** `active_account` → `platform_rules.yaml` entry. Missing means fatal (§9.5). `platform` must be `ctrader`. Compute `rulebook_hash`.
- **A2 — Environment and mode gate.** The host is chosen by `venue.environment`. After A3, the bound `ctidTraderAccountId` must appear in `ProtoOAGetAccountListByAccessTokenRes`, and its `isLive` must equal `environment == live` [F-22]; else fatal (`ATTACH_ENV_MISMATCH`). Demo and live are "fully separated" [F-01]. **OQ-01 RESOLVED 2026-09-29 (owner-ratified, master v2.23):** orders to a demo account are permitted in the new `practice` mode only. In `practice`, `venue.environment` must be `demo`, the bound account's `isLive` must be `false`, AND the active rulebook must declare `account_class: practice` (clause (ii) of the proposed ruling: a paid challenge also reports `isLive = false` [F-30][OQ-10]); any miss is fatal (`ATTACH_ENV_MISMATCH`), so practice can never reach money. `paper` keeps no venue order path at all. `live` needs `environment: live` and `isLive = true`.
- **A3 — Connect, then authorise.** TLS connect [F-02] → `ProtoOAApplicationAuthReq` → `ProtoOAGetAccountListByAccessTokenReq` (scope must be `SCOPE_TRADE` [F-08]) → `ProtoOAAccountAuthReq` for the bound id.
  - `ALREADY_LOGGED_IN` on this connection counts as success. The proto defines it as "When client tries to authorize after it was already authorized" [F-34]. Its behaviour across two different connections is [OQ-06].
  - `CH_ACCESS_TOKEN_INVALID` or `OA_AUTH_TOKEN_EXPIRED` leads to a refresh (§6.7). Any other auth error is fatal.
- **A4 — Trader state** (`ProtoOATraderReq`) [F-21]:
  - `accessRights` must be `FULL_ACCESS`. `CLOSE_ONLY` gives verdict `FATAL: close-only account`.
  - `isLimitedRisk` must be `false`: such accounts require a guaranteed stop on every position, which v1 does not support.
  - The deposit asset must be USD (§6.4). `accountType` feeds §5.2. `moneyDigits` is recorded.
- **A5 — Symbol discovery and contract check.** `ProtoOASymbolsListReq` → exact-name match (§5.1) → `ProtoOASymbolByIdReq` → `VenueSymbolSpec` → the §6.4 cross-check → the descriptor (§5.2) → ACIS-06's existing `verify_attach` symbol-map check.
- **A6 — Flat-or-decide (GAP-0018)**, for a binding with no persisted ACIS state:
  - `ProtoOAReconcileReq(returnProtectionOrders = true)` [F-18].
  - **Any** position **or pending order** raises `AttachHalt`. A pending order is a position in waiting.
  - The human decides: flatten on the platform, or manage manually until flat. ACIS never trades alongside positions it did not open.
- **A7 — Restart instead of attach**, for a binding **with** persisted ACIS state:
  - Deal ingestion (§7.8) runs **first**, so that stop-outs while ACIS was down become `FillReport`s before reconciliation.
  - Then `reconcile_on_restart` (ACIS-07 C-RSK-5) receives the ACIS-labelled positions. A foreign position is an `AttachHalt`.
  - Every ACIS position must show a stop, else the §7.3 step-6 repair runs.
- **A8 — Subscribe to spots and check the clock.**
  - `ProtoOASubscribeSpotsReq(symbolId = [...], subscribeToSpotTimestamp = true)` [F-23].
  - Await the first (technical) event per symbol.
  - Clock check (§2.4): refuse if the skew is out of tolerance. **Caveat:** the first event may be an old closing print when the market is closed [F-23]. The skew check therefore uses only events received while the venue schedule says the market is open. On a closed-market attach it is deferred to the first live tick, and entries stay blocked until it passes.
- **A9 — The budget feasibility check** (§6.5).
- **A10 — The prop-safety preconditions** (§15.2). An FTMO or E8 rulebook with any precondition unmet refuses to attach, with its reason.
- **A11 — Report and start.** Emit the `AttachReport` and `ATTACH_VERIFIED`, publish on `acis://venues/adapters`, and start in **paper mode, always** (master §7.5). Only a human token changes mode (§12): to `practice` with the dual-hash attestation (master v2.23), to `live` with rung 2 as well. **The mode selects the face:** in `paper` the orchestrator dispatches to the paper face and the venue face sends nothing. `acis_set_mode(practice)` is refused unless this attach's `AttachReport` shows `environment = demo`, `is_live = false` and `account_class = practice` (A2). A mode switch never re-binds the account.

### 7.2 Account churn and re-attach (the FTMO Free Trial case)
- **The facts.**
  - FTMO connects its simulated accounts to the owner's single cTrader registration (cTID) [F-29].
  - A Free Trial lasts 14 days; only one exists at a time, and it can be deleted and restarted [F-30].
  - An account created after an OAuth grant is **not** covered by that grant until the user re-consents [F-09].
  - Trade press reports that FTMO's cTrader trial is Spotware's "free prop trial" account type: "time-limited demo access", flagged "FREE", which "expire[s] automatically after the trial period", with "algorithmic trading" available [F-42].
- **The consequence.** Each renewal is a new trading account, so it has a **new `ctidTraderAccountId`** (an inference from the above; the first renewal confirms it). It needs a **human** re-grant plus a human commit of the new id (§2.3). No agent path can bind ACIS to a different account. The account id is config, never discovered.
- **The end of an account.** Expiry, a breach, or deletion reaches the API in one of these forms (which one FTMO uses is [OQ-18]):
  - a `ProtoOATraderUpdatedEvent` with `accessRights ≠ FULL_ACCESS`;
  - `ProtoOAAccountDisconnectEvent`, `ProtoOAAccountsTokenInvalidatedEvent` ("account was deleted") [F-12];
  - the error codes `RET_ACCOUNT_DISABLED`, `RET_NO_SUCH_LOGIN` or `CH_CTID_TRADER_ACCOUNT_NOT_FOUND` [F-34].

  On any of them the binding goes **`DETACHED`**:
  - no new opens;
  - health event `VENUE_ACCOUNT_DETACHED{reason_code}`;
  - Risk is informed through the execution face's account state (the account is unreadable, so `account_snapshot()` raises and the stalled-state path applies).
- **Re-attach is a full A1–A11** on the new binding. Per-account state (budget ledger, order map, deal cursor, and GAP-P12D-55's anchors once they persist) is keyed by `account_key` (§5.4), so **nothing carries over**. In particular, a new account's drawdown anchors must never inherit the old account's (C-VEN-5).
- **The cadence cost.** One human step roughly every 14 days. Acceptable for a demo; recorded as operational load.

### 7.3 `submit_order` (the execution face)
1. **The intent is carried, never inferred** (ACIS-06 v1.3 C-EXE-7; OQ-03c resolved). `submit_order` is an **open**; `close_position` is a **reduce**, reduce-only.
   - A reduce larger than the ACIS holding on that side is **refused** (`VENUE_CROSS_THROUGH_FLAT`). A reversal is two ACIS orders, a close then an open, never one.
   - An open on an instrument that already holds an ACIS position is refused (`VENUE_ONE_POSITION_PER_INSTRUMENT`) unless it is the same direction and carries the same `order_id`: fragments of one order are allowed. An open against an opposite ACIS position is refused too, so a hedging account never holds both sides and a netting account never nets by accident. This is the adapter's half of the GAP-0075 position policy (C-VEN-9).
2. **Validate:** the symbol is mapped and `ENABLED`; the volume equals `quantize()` and is ≥ the minimum (§6.3); the venue schedule says the market is open, so no request is spent to learn `MARKET_CLOSED`.
   - **An open needs `stop_loss`.** An open without one is refused (`VENUE_UNPROTECTED_OPEN_REFUSED`). Master §8.6 says every `SizedOrder` carries a broker-side stop.
   - A reduce carries none.
3. **Spend budget** (§6.5): an open spends general budget, a reduce may spend the reserve. Refusal returns a `REJECTED` report without contacting the venue.
4. **Idempotency (C-EXE-4/5, C-VEN-1).** `clientOrderId = fragment_id`, at most 50 characters [F-13]; longer raises `DataQualityError`. If `fragment_id` is in `venue_order_map` (§10), the original report is returned or rebuilt from venue truth, and nothing is sent. Whether cTrader itself deduplicates `clientOrderId` is undocumented [OQ-14]; **ACIS assumes it does not.**
5. **Send.**
   - An **open** is `ProtoOANewOrderReq{orderType = MARKET, tradeSide, volume, timeInForce = IMMEDIATE_OR_CANCEL, relativeStopLoss, clientOrderId, label = "ACIS:" + the first 8 hex digits of sha256(account_key), comment = order_id}` [F-13]. The label is how §4.3 and §7.8 tell ACIS's positions from foreign ones.
     - No absolute stop, which is unsupported on MARKET [F-13].
     - No `MARKET_RANGE` or `STOP_LIMIT` for anything protective (C-VEN-14).
     - No `guaranteedStopLoss` (§7.1 A4).
     - No take-profit: exits are engine-driven. `SizedOrder.take_profit` is not on the ACIS-06 face.
   - A **reduce** (`close_position`) is `ProtoOAClosePositionReq{positionId, volume}` [F-13], on hedging **and** netting accounts. On a hedging account each fragment of an open is its own venue position, so a reduce spanning several sends one request per position, oldest first, each budgeted, and returns one aggregated `FillReport`. An explicit close can never open an opposite hedge by accident (C-VEN-9).
   - The `fragment_plan` was logged before dispatch (ACIS-06 §9). Record `venue_order_map` with state `SENT` before the frame leaves.
6. **Await the terminal outcome** (§4.2), correlated by `clientMsgId` for the immediate response and by `orderId`/`clientOrderId` for the execution events.
   - **Timeout** (`order_ack_timeout_s`) or a **disconnect before the terminal event**: do **not** resend. Raise `ConnectionError`, as the ACIS-06 contract does. When the orchestrator retries with the same `fragment_id`, the face, now in `SYNCING` or `READY`, first searches the venue: `ProtoOAOrderListReq` over `[sent_ts − 60 s, now]`, filtered on `order.clientOrderId == fragment_id` [F-19]; then `ProtoOAOrderDetailsReq` for its deals.
     - **If found:** return the report built from venue truth.
     - **If not found:** the order never reached the venue, and only then is it sent.
     - Either way it is exactly once (C-EXE-5).
   - **Stop verification (C-VEN-2)**, after an **open** fills (fully or partly):
     - The position in the execution event, or the reconcile within `stop_confirm_timeout_s`, must show `stopLoss` on the protective side of the fill.
     - **Missing:** send `ProtoOAAmendPositionSLTPReq{positionId, stopLoss = fill ∓ d}` from the reserve.
     - **Still missing:** close the position from the reserve and log `VENUE_STOP_MISSING` (critical, `risk_log`).
     - **ACIS never holds an unprotected position.** One developer reported an order accepted "but the SL has not been set" (forum, grade c) [F-15], and whether the stop is atomic with the fill is [OQ-07].
7. **Emit** the `FillReport`, update `venue_order_map` to `TERMINAL`, and log `FILL`/`PARTIAL`/`REJECT` with the venue ids (`orderId`, `positionId`, `dealId`s) and `VENUE_COSTS`.

### 7.4 `cancel(fragment_id)`
Look up the order by `clientOrderId` (map first, then venue):
- **pending** (`ORDER_STATUS_ACCEPTED`, not filled): `ProtoOACancelOrderReq` → `True` on `ORDER_CANCELLED`;
- **filled**, fully or partly: `False`;
- **no venue trace** after a reconcile and an order-list search: `True`, which is ACIS-06's "guaranteed unfilled".

Market IOC orders make this path rare. It must still be exact.

### 7.5 `open_positions()`, `resting_stops()`, `account_snapshot()`
- The first two issue a fresh `ProtoOAReconcileReq`, venue-authoritative (§4.3); `account_snapshot()` issues `ProtoOATraderReq` plus `ProtoOAGetPositionUnrealizedPnLReq` (§4.4).
- Between calls, the face keeps an **event-sourced** view built from execution events (`ProtoOATraderUpdatedEvent` pushes balance changes [F-21]). The runtime reads that view without spending requests.
- The **callers' cadence** belongs to the runtime (Track A step 4) and is bounded by the §6.5 feasibility check: `equity_poll_s`, `reconcile_interval_s`, and each Risk evaluate reading the event-sourced view.

### 7.6 The feed face (`CTraderFeed.stream()` / `snapshot()`)
- `stream()` yields `RawTick`s per §4.1.
- `snapshot(instrument)` returns the last emitted tick. After a reconnect, the re-subscription's technical event re-baselines it (`FEED_RECONNECT`).
- The first technical event after subscription contains the latest prices "even if market is closed" [F-23]. With markets closed, the face receives "a single spot event with the closing prices" [F-23]. That tick is emitted with `snapshot = True` and its real, old timestamp, and ACIS-01's staleness flag makes it untradeable. **Weekend quiet is not an outage:** the venue schedule says closed, so there is no `DEGRADED` state.
- ACIS-01's existing duplicate, out-of-order and NaN handling applies unchanged. The face adds none of its own. It does not reorder; it forwards venue order with venue timestamps.
- Unsubscribe on detach (`ProtoOAUnsubscribeSpotsReq`) is best effort and not budget-critical.

### 7.7 Unsolicited fills: stop hits, stop-outs and manual actions (C-VEN-7)
A server-side stop that triggers produces a `ProtoOAExecutionEvent` that ACIS did not request. It can be a stop-loss fill, a stop-out marked `isServerEvent` [F-17], or a manual close by the human in the cTrader UI.

Before v1.4 the locked ACIS-06 `ExecutionFace` had **no channel for it**: `submit_order` returns only solicited reports. Without one, the next reconcile shows a position gone that Risk still holds. `reconcile_on_restart` treats that as drift and HALTs (`restart_drift`), and in-session accounting is wrong until then.

This spec therefore requires [OQ-03a, RESOLVED 2026-09-29: ACIS-06 v1.4 adds the channel, owner-ratified]:
- `ExecutionFace.venue_fills() -> AsyncIterator[FillReport]`, which the orchestrator forwards to Risk;
- mapping: `order_id = f"venue:{orderId}"`, `fragment_id = f"venue:{dealId}"`, `status = FILLED` (or `PARTIAL`), `direction` = the closing side, `requested_price` = the order's stop price, `fill_price = deal.executionPrice`. The slippage against the stop level is then the **measured gap-through-stop cost**, the §8.5 gap-law evidence and the GAP-P12D-42 class, logged to `OPERATIONS_LEDGER.md` by the operational pass.

The mock face must gain a way to trigger its resting stop, so that the shared suite can test this path.

### 7.8 Restart reconciliation and deal ingestion (feeds ACIS-07 C-RSK-5)
On every start and every reconnect (`SYNCING`):
1. **Deals missed while down.** `ProtoOADealListReq(from = deal_cursor, to = now)` [F-19], paging on `hasMore`. For each deal not already covered by a `FillReport` (`fill_report` PK, ACIS-06 §10), emit it through `venue_fills()` (§7.7). Advance `deal_cursor` (persisted per `account_key`).
2. **Fragments in flight at the crash.** Every `FRAGMENT_PLAN` fragment without a terminal `venue_order_map` row is resolved by the §7.3 step-6 search. Anything found is reported; anything absent is marked `NOT_SENT`. **Nothing is resubmitted automatically**; the orchestrator decides afresh.
3. **Positions.** `ProtoOAReconcileReq` → `reconcile_on_restart(ACIS-labelled positions)`. Any residual drift is a genuine surprise, and ACIS-07 HALTs as it already does.
4. **Stops.** Every ACIS position must show a stop, else the §7.3 step-6 repair runs.
5. **Balance history, for GAP-P12D-55.** The face can supply the venue's balance path: closing deals carry `closePositionDetail.balance` [F-38], and `ProtoOACashFlowHistoryListReq` returns deposits and withdrawals in windows of at most one week [F-39], from `registrationTimestamp` [F-21]. That is a **provision**, one of the fix options GAP-P12D-55 names ("reconstruct them from the broker's balance history at boot"). Choosing it is the owner's call. The intraday equity high-water mark cannot be rebuilt from balance history.

### 7.9 The watchdog flatten plugin (master §8.6 layer 2; ACIS-12 surface)
`CTraderFlattenPlugin.flatten_all(credentials) -> FlattenResult`, self-contained, with **zero `core/` imports**. It reuses no adapter code, a deliberate duplication of roughly 100 lines, justified by §8.6 "no imports from `core/`":
1. Open **its own** TLS connection to the host for the configured environment. Its inputs come only from `config/watchdog.yaml` (human-commit, ACIS-12 §2): `platform: ctrader`, `flatten_plugin: ctrader`, the environment, the bound `ctid_trader_account_id`, and a `credentials_ref` naming the environment variables for `clientId`/`clientSecret` and the token-store path. No secret lives in the file.
2. Application auth → account auth with the access token **read** from the token store. If the token is rejected, re-read the store once, since the engine may have just refreshed it (§6.7).
3. `ProtoOAReconcileReq` → `ProtoOAClosePositionReq(positionId, full volume)` for **every** position on the bound account, and `ProtoOACancelOrderReq` for every pending order.
4. Verify with a second reconcile. `ok = no positions remain`.

Its requests are outside the engine's counter by design (§6.5): an emergency flatten of fewer than 20 requests sits inside the remaining 1,000 of the firm's cap. Whether a **second connection may authorise the same account while the engine's connection is still alive** (a hung engine keeps its socket until the server drops it) is undocumented [OQ-06]:
- Spotware recommends "at most … two connections: one for demo accounts and one for live accounts" [F-04].
- `CONNECTIONS_LIMIT_EXCEEDED` exists [F-34].
- Spotware's 2019 documentation, as a user quoted it on the forum, allowed "25 concurrent connections per application" (grade c, superseded) [F-04].

The conformance case of §14.2 settles it. A failure is `WATCHDOG_FLATTEN_FAILED` (ACIS-12). Server-side stops remain layer 1.

## 8. State machines & loop cadence

### 8.1 Session / binding
```
DISCONNECTED → CONNECTING → APP_AUTH → ACCOUNT_AUTH → SYNCING → READY
READY → DEGRADED   (rate-limited, budget below reserve, or a symbol CLOSE_ONLY) → READY
any → DISCONNECTED (link dead, ProtoOAClientDisconnectEvent, AccountDisconnect) → backoff → CONNECTING
READY/SYNCING → REAUTH (token refreshed or invalidated) → ACCOUNT_AUTH
any → DETACHED     (account disabled or deleted, token DEAD, access rights lost) — terminal; human re-grant + re-attach
```
- In `SYNCING` and `REAUTH` no new dispatch leaves. ACIS-06's `RECONCILING` maps onto both.
- In `DEGRADED`, opens are refused while closes and stop repair proceed.
- In `DETACHED`, nothing but the watchdog path exists.
- Every transition is logged (§9).

### 8.2 Order lifecycle, ACIS-06 §8 ↔ cTrader
| ACIS-06 state | cTrader evidence [F-17] |
|---|---|
| `DISPATCHING` | request sent; `venue_order_map.state = SENT` |
| accepted | `ORDER_ACCEPTED` |
| `PARTIAL ↺` | `ORDER_PARTIAL_FILL` |
| `FILLED` | `ORDER_FILLED` (executed volume = requested) |
| `PARTIAL` (terminal) | `ORDER_PARTIAL_FILL` then `ORDER_CANCELLED`/`ORDER_EXPIRED` for the remainder |
| `REJECTED` | `ORDER_REJECTED`, `ProtoOAOrderErrorEvent`, or `ProtoOAErrorRes` for the `clientMsgId` |
| `CANCELLED` | `ORDER_CANCELLED` with nothing filled |

### 8.3 Loop placement
The session runs as tasks inside the engine's asyncio runtime (master §10; the three-loop runtime is Track A step 4). Heartbeat and liveness are **independent of tick processing**, so a slow fast-loop iteration can never starve the heartbeat, and a starved heartbeat means a disconnect. The feed face feeds Loop 3 (FAST). Loop 1 (SLOW) and Loop 2 (MEDIUM) never touch the venue; they cannot trigger execution anyway (master §10).

## 9. Persistence & logging
Every record uses the §11 envelope `{timestamp, event_type, layer, data, session_id}`, with `layer = data` for the session and feed and `layer = execution` for the face. No `print`.

- **`system_log`:**
  - connection: `VENUE_CONNECT`, `VENUE_APP_AUTH`, `VENUE_ACCOUNT_AUTH`, `VENUE_DISCONNECT{reason_code}`, `VENUE_BACKOFF{attempt, delay_s}`, `VENUE_MAINTENANCE{until}`, `VENUE_RATE_LIMITED{payload_type, retry_after_s}`, `VENUE_UNREACHABLE`;
  - tokens: `VENUE_TOKEN_REFRESHED{expires_at}`, `VENUE_TOKEN_INVALIDATED{reason_code}`;
  - state and budget: `VENUE_STATE{from, to}`, `VENUE_BUDGET{used_24h, cap, reserve}`, `VENUE_BUDGET_EXHAUSTED`;
  - feed: `FEED_UNKNOWN_SYMBOL`, `FEED_RECONNECT`, `CALENDAR_VENUE_DISAGREEMENT`;
  - attach: `ATTACH_STEP`, `ATTACH_VERIFIED`, `ATTACH_HALTED_OPEN_POSITIONS`, `ATTACH_ENV_MISMATCH`, `ATTACH_CLOCK_SKEW`, `ATTACH_PLATFORM_MISMATCH`, `VENUE_ACCOUNT_DETACHED{reason_code}`.
- **`trade_log`:** ACIS-06's events plus `VENUE_LOT_ROUNDED`, `VENUE_COSTS{commission, swap, gross_profit, pnl_conversion_fee, balance_after}`, `VENUE_UNSOLICITED_FILL{is_server_event, order_type}` and `VENUE_STOP_AMENDED`.
- **`risk_log`:** `VENUE_STOP_MISSING` (critical), `VENUE_UNPROTECTED_OPEN_REFUSED`, `VENUE_CROSS_THROUGH_FLAT`.
- **Never logged:** `clientSecret`, access token, refresh token, the authorisation code. A test greps every emitted record for the token-store values (§14.1).
- **Raw execution events** are appended verbatim, decoded, to `logs/venue_events.jsonl`. They are the operational-referent evidence (CLAUDE.md guard 3; GAP-P12D-44). Spot events are not persisted raw (volume); ACIS-01's `data_log` covers them.

## 10. Store schema (DDL)
```sql
-- every outbound request (heartbeats excluded): the rolling-24 h budget and the evidence
-- if a firm disputes "hyperactivity" (§6.5)
CREATE TABLE venue_request_log (
    ts            TIMESTAMPTZ NOT NULL,
    account_key   TEXT NOT NULL,
    payload_type  INTEGER NOT NULL,
    req_class     TEXT NOT NULL CHECK (req_class IN ('open','close','protect','query','auth','subscribe')),
    client_msg_id TEXT NOT NULL
);
CREATE INDEX ON venue_request_log (account_key, ts);

-- fragment_id ⇄ venue order: idempotency across reconnect and restart (C-VEN-1)
CREATE TABLE venue_order_map (
    fragment_id     TEXT PRIMARY KEY,       -- = clientOrderId (≤ 50 chars)
    account_key     TEXT NOT NULL,
    order_id        TEXT NOT NULL,          -- ACIS SizedOrder id
    venue_order_id  BIGINT,                 -- ProtoOAOrder.orderId, NULL until known
    position_id     BIGINT,
    state           TEXT NOT NULL CHECK (state IN ('SENT','TERMINAL','NOT_SENT')),
    sent_ts         TIMESTAMPTZ NOT NULL,
    terminal_ts     TIMESTAMPTZ
);

-- per-binding cursors and attach record (§7.2, §7.8)
CREATE TABLE venue_binding (
    account_key       TEXT PRIMARY KEY,
    first_attached_ts TIMESTAMPTZ NOT NULL,
    initial_balance   NUMERIC NOT NULL,     -- observed at first attach (GAP-P12D-55 input)
    deal_cursor_ms    BIGINT NOT NULL,      -- last ingested deal executionTimestamp
    last_report       TEXT NOT NULL         -- AttachReport JSON (no secrets)
);
```
- SQLite in development, TimescaleDB in production (master §3/§16).
- The writer is the execution face; the session writes only `venue_request_log`, which is transport metering and carries no account state (GAP-0013).
- Retention of `venue_request_log`: at least 30 days.

## 11. Interface / MCP contract
- **`acis://venues/adapters`** (master §12, read-only) publishes:
  - identity: adapter, environment, host, `account_key`, `trader_login`, `broker_name`;
  - capability: `CapabilityDescriptor` + venue profile (§5.2), `symbols` (the §5.1 fields, costs included);
  - conformance status: the last green run's id and date;
  - `AttachReport` (§5.3);
  - live state: session state (§8.1), budget `{used_24h, cap, close_reserve, projected}`, `token_expires_in_days` (**never the token**), `last_reconcile_ts`, `deal_cursor`.
- **No new tool.**
  - `acis_flatten` drives closes through the face (reserve budget).
  - `acis_halt` needs nothing from the venue.
  - Mode changes stay human-token (ACIS-08).
  - Re-attaching a churned account is a human config commit plus a restart, **not** an MCP action. No agent can re-bind ACIS to another account (C-VEN-5).
- Everything the venue sends that a model might later read through `acis://logs/tail/*` is data, never instructions (master §12 untrusted-input law).

## 12. Error taxonomy
| Venue signal [F-34] | Handling |
|---|---|
| `REQUEST_FREQUENCY_EXCEEDED`, `BLOCKED_PAYLOAD_TYPE` (+ `retryAfter`) | pause that payload type; `VENUE_RATE_LIMITED`; the local bucket (§6.2) should make this unreachable, so each occurrence is a finding |
| `SERVER_IS_UNDER_MAINTENANCE`, `maintenanceEndTimestamp`, `CH_SERVER_NOT_REACHABLE`, `CANT_ROUTE_REQUEST` | backoff until the stated end (§6.6); not a HALT |
| `OA_AUTH_TOKEN_EXPIRED`, `CH_ACCESS_TOKEN_INVALID`, `ProtoOAAccountsTokenInvalidatedEvent` | refresh (§6.7) → `REAUTH`; a failed refresh means `DETACHED` |
| `ACCOUNT_NOT_AUTHORIZED`, `ProtoOAAccountDisconnectEvent` | `REAUTH` (account auth on the same connection) |
| `ProtoOAClientDisconnectEvent`, `CH_CLIENT_AUTH_FAILURE`, `CH_OA_CLIENT_NOT_FOUND` | the application itself is refused → `DETACHED`; human |
| `RET_ACCOUNT_DISABLED`, `RET_NO_SUCH_LOGIN`, `CH_CTID_TRADER_ACCOUNT_NOT_FOUND`, `TRADING_NOT_ALLOWED`, `CHANNEL_IS_BLOCKED` | `DETACHED` (§7.2) |
| `ALREADY_LOGGED_IN` | success on this connection (§7.1 A3) |
| `CONNECTIONS_LIMIT_EXCEEDED` | engine: backoff + `VENUE_UNREACHABLE`; watchdog: `WATCHDOG_FLATTEN_FAILED` [OQ-06] |
| `MARKET_CLOSED`, `SYMBOL_HAS_HOLIDAY`, `TRADING_DISABLED`, `NO_QUOTES` | `REJECTED` report; the schedule pre-check (§7.3) should prevent the first two, so each occurrence is logged as a pre-check miss |
| `TRADING_BAD_VOLUME`, `TRADING_BAD_STOPS`, `PROTECTION_IS_TOO_CLOSE_TO_MARKET`, `TRADING_BAD_PRICES` | `REJECTED`; client-side validation (§6.3) should prevent them, so each is a finding against the validator |
| `NOT_ENOUGH_MONEY`, `MAX_EXPOSURE_REACHED`, `TOO_MANY_POSITIONS`, `SHORT_SELLING_NOT_ALLOWED` | `REJECTED`; the orchestrator's bounded reroute or giveup (ACIS-06 §7) |
| `POSITION_NOT_FOUND`, `POSITION_NOT_OPEN` on a close | reconcile first: the position may have been stopped out (§7.7). Not an error if venue truth shows it closed. |
| `PENDING_EXECUTION`, `CONCURRENT_MODIFICATION`, `POSITION_LOCKED` | bounded retry (≤ 3, jittered) for protective amends and closes only; never for opens |
| `TIMEOUT_ERROR` (deal execution timed out, rejected) | `REJECTED` |
| a timeout with no response | §7.3 step 6: search the venue, never blind-resend |
| stop missing after an open | §7.3 step 6: amend → close → `VENUE_STOP_MISSING` |
| a foreign position or pending order | attach: `AttachHalt`; runtime: drift → Risk |
| unknown `errorCode` string | `REJECTED` + `VENUE_UNKNOWN_ERROR{code}`; the description is logged as data, never parsed |

## 13. Logic-flaw registry
- **C-VEN-1 — Venue truth before any resubmit.** A fragment is resent only after the venue has been searched for its `clientOrderId` and nothing was found. Test: kill the link after send and before the terminal event; the retry must produce one venue order (§14.2).
- **C-VEN-2 — No unprotected open, ever.** An open carries a relative stop. The fill is verified to hold a venue-side stop, or it is repaired, or it is closed. An open without `stop_loss` is refused.
- **C-VEN-3 — No rounding up.** The volume rounds down to the step; below the minimum it is refused, not placed (GAP-P12D-57).
- **C-VEN-4 — The budget is hard, and exits are never starved.** A rolling-24 h cap ≤ 1,000 with a close reserve. It persists across restarts and cannot be raised above 1,000 by config.
- **C-VEN-5 — The account binding is explicit and per-account.** No selection by list position. The environment must match `isLive`. Churn means a full re-attach after a human re-grant. All state is keyed by `account_key`; no state crosses accounts.
- **C-VEN-6 — The GAP-0013 structure.** The session holds transport + auth + metering only and routes by payload type without interpreting. It is asserted by attribute scan and import contract.
- **C-VEN-7 — Unsolicited fills are reported.** A stop hit is a `FillReport` through `venue_fills()` (ACIS-06 v1.4), never drift.
- **C-VEN-8 — Secret hygiene.** No secret in YAML or logs. The rotated refresh token is persisted atomically **before** the new access token is used.
- **C-VEN-9 — Hedging-account safety.** Closes use `ClosePositionReq`, so no accidental hedge. There is one ACIS position per instrument. A reduce can never cross through flat.
- **C-VEN-10 — The strictest liveness source wins.** Heartbeat at 10 s (docs), not 20 s (SDK) or 30 s (proto).
- **C-VEN-11 — Lot-size consistency.** `lotSize == UNITS_PER_LOT` is verified at attach, or the attach fails. The orchestrator's lot arithmetic must never mis-size silently.
- **C-VEN-12 — Equity is never overstated.** Closing commission and adverse swap are subtracted until [OQ-15] rules.
- **C-VEN-13 — Weekend and maintenance are expected.** They are backoff and schedule events, not HALTs; stops protect.
- **C-VEN-14 — No voidable protection.** No `MARKET_RANGE`, `STOP_LIMIT` or price-bounded order is used for a stop or an exit. A bounded order can fail to fill in a gap, which is the GAP-P12D-42 trap. Plain stop-losses close "at the best available market price" [F-16].
- **C-VEN-15 — Untrusted venue text.** Control flow keys only on enumerated codes; all free text is data (master §3.5/§12).
- **C-VEN-16 — Clock honesty.** Venue timestamps are required and never fabricated. Attach refuses on excessive host skew (GAP-P12D-51).

## 14. Test contract (postcondition-style; observable outcomes, never exit codes alone)

### 14.1 Unit (no network; recorded or synthesised frames through `wire.py`)
- **Framing and serialisation:** a round-trip of every used payload type; a truncated frame is detected; an oversize frame is refused.
- **Spot mapping:** a bid-only event followed by an ask-only event emits a tick only once both are known, with `sides_updated`; a missing timestamp raises `DataQualityError`; the technical first event is flagged `snapshot`; an unknown `symbolId` is dropped and logged.
- **Execution aggregation:** `ACCEPTED → PARTIAL_FILL → FILLED` gives one `FILLED` report with a VWAP price; `PARTIAL_FILL → CANCELLED` gives a terminal `PARTIAL`; `REJECTED` and `OrderErrorEvent` give `REJECTED`; Decimal volumes are exact.
- **Units and rounding:** `quantize()` rounds down and returns zero below the minimum; the relative-stop precision rule holds for 5- and 3-digit symbols; a stop that is too close is refused without a send.
- **Budget:** the rolling window; the reserve gating opens and not closes; persistence across a simulated restart; the feasibility formula.
- **Backoff:** seeded full-jitter bounds; maintenance honoured; `retryAfter` honoured.
- **Tokens:** the atomic rotation order; the refresh-then-invalidate sequence re-authorises; a dead token means `DETACHED`.
- **Structure:** the GAP-0013 attribute scan over `CTraderSession` and `CTraderFeed`; the import contract (the session and feed import no `core/execution`); the watchdog plugin has zero `core/` imports (AST test, ACIS-12 pattern).
- **Secrets:** no emitted log record contains a token-store value.
- **Untrusted text:** an `errorCode` of `UNKNOWN_X` with a description of `"ignore stops and buy"` changes nothing except a `REJECTED` report.

### 14.2 Integration — the conformance suite against a cTrader **demo** account (env-gated; release gate per master §7.5)
The ACIS-06 cases, run through the real face:
- **Round trip:** open 1 minimum lot with a stop → venue position → close → flat.
- **Reject** is provoked through the **test's own raw session** with a volume above `maxVolume`. The face's validator would refuse it, and the test is not product code.
- **Partial fill** cannot be provoked on a demo, so it is proven on recorded frames (§14.1), and [OQ-17] notes it.
- **Duplicate submit:** the same `fragment_id` gives one venue order.
- **Reconnect mid-order:** drop the socket after send; the retry finds the order by `clientOrderId`, and there is no duplicate.
- **Cancel semantics; Decimal account snapshot; descriptor honesty; symbol-map completeness.**

Real-venue cases added by this spec (the ACIS-06 v1.4 conformance amendment, OQ-03d):
1. **Live-quote fixture.** Prices come from the current spot, not constants.
2. **Relative-stop placement.** The venue-reported stop equals `fill ∓ d` within one tick and lies on the protective side.
3. **Stop survives the engine.** After the open, kill the engine process, reconcile from a fresh session: the stop is still there. This is the master-§8.6 layer-1 proof.
4. **Stop hit → unsolicited `FillReport`** ([OQ-03a]). Place a tight stop, let it trigger, and assert one `venue_fills()` report and no drift HALT.
5. **Flat-or-decide.** A pre-existing manual position gives `AttachHalt`, and nothing is sent.
6. **Environment mismatch.** A demo binding configured `live` is fatal before any order.
7. **Budget.** A test-lowered cap refuses opens at `cap − reserve`, and a close still succeeds.
8. **Watchdog flatten while the engine's connection is alive** ([OQ-06]). SIGSTOP the engine process (socket open), run the plugin, assert flat.
9. **Token refresh mid-session.** Dispatch pauses in `REAUTH`, no order is lost, and dispatch resumes.
10. **Clock skew.** An injected +16 min local offset fails attach (GAP-P12D-51).

### 14.3 Glitch classes (master §13) → where each is tested
| Glitch class | Test |
|---|---|
| clock skew | §14.2 case 10; the unit test of the skew-check deferral on a closed market |
| DST / session boundary (Sunday open, Friday close) | the venue-schedule pre-check around the Friday close and Sunday open (unit, recorded schedule); the technical-event staleness at the weekend |
| duplicate / out-of-order ticks | recorded spot sequences with a repeated and a regressed timestamp → ACIS-01's `DUP_TICK`/`OUT_OF_ORDER` fire through the real face |
| NaN / inf | a malformed price field → `DataQualityError`, stream continues |
| float drift | volumes and money are exact Decimal end to end (unit) |
| partial fills and rejects | §14.1 aggregation + §14.2 reject |
| feed reconnect mid-position | socket drop with an open position → `SYNCING` → deal ingestion → reconcile → `FEED_RECONNECT` with the gap logged, nothing interpolated |
| weekend gap through a stop | observational: the first Sunday-open stop fill on the demo, with its slippage recorded (§7.7) in `OPERATIONS_LEDGER.md`. The deterministic proof stays ACIS-07's joint test. |
| racing HALTs | unchanged (ACIS-07); a flatten racing a stop hit gives `POSITION_NOT_OPEN` → reconcile → no error (§12) |
| restart with open positions | §7.8: kill with a position open → restart → no drift HALT, the stop is verified |
| symbol suffix mismatch | `EURUSD` vs `EURUSD.pro` in `symbol_names` → fatal, never fuzzy-merged |
| pair leg orphaned | unchanged (ACIS-05/06); the face's one-position rule does not block the second leg (different instrument) |

## 15. Integration gate

### 15.1 What consumes this, and done-when
- **ACIS-01** consumes `RawTick`s from `CTraderFeed`, with no change to its factory.
- **ACIS-06** consumes `CTraderExecutionFace`, as amended by ACIS-06 v1.3 (C-EXE-7/8) and v1.4 (`venue_fills()`, the conformance variant).
- **ACIS-07** consumes `FillReport`s (solicited, plus unsolicited via `venue_fills()`), `BrokerAccount` and `BrokerPosition`, plus the restart deal ingestion.
- **ACIS-08** publishes `acis://venues/adapters`.
- **ACIS-12's watchdog** loads the cTrader plugin.

**Conflict-table rows owned:** none. The face executes; it never sizes, vetoes or halts. **Done-when:** §1's list.

### 15.2 Prop-safety preconditions: attach refuses an FTMO or E8 rulebook until all hold (§7.1 A10)
| # | Precondition | Owner | Ledger |
|---|---|---|---|
| 1 | a position-aware open policy exists (no per-tick firehose) | Track A step 4 | GAP-0075 |
| 2 | request budget ≤ 1,000 per rolling 24 h with a close reserve, live in this adapter | this spec | GAP-P12D-57 |
| 3 | lot-step rounding down + minimum-lot refusal wired through `quantize()` | this spec + ACIS-06 v1.3 C-EXE-8 | GAP-P12D-57 |
| 4 | the pre-close (2 h) and scheduled-news entry bans are **always on**, not tied to `weekend_holding_allowed` | Governor + owner | GAP-P12D-58 |
| 5 | drawdown anchors survive a restart and are keyed per account | owner (guardrail-adjacent) | GAP-P12D-55 |
| 6 | a correct `ftmo` rulebook, human-committed | owner | GAP-P12D-54 |
| 7 | an equity floor set for this account | owner (guardrail) | GAP-P12D-56 |
| 8 | FTMO has not refused unattended Open API use (email Q1) | owner | research §9.1 |
| 9 | the VPS does not geolocate to the US | owner | research §6 |

Items 2 and 3 are machine-checked by the attach. The others are checked by the review pass and recorded in the `AttachReport` reason when refused. A **non-prop demo rulebook** (for example a cTrader demo at a broker, research §7 option C — the Pepperstone demo is this case) needs only 1–3 and 7, plus `account_class: practice`.

### 15.3 Before LOCK: what the review pass must do — DONE 2026-09-29 (v1.0; the record is the changelog)
1. Rule every BLOCKING question in Appendix B, and fold the rulings into §§3–7. (Done 2026-09-29 for OQ-01, OQ-02, OQ-03a; the pass verifies the folding.)
2. Re-derive the §6.5 defaults from the GAP-0075 policy's real order rate. (Done: the defaults stand under R-1's rate, and `max_orders_per_day` makes the check certifiable now.)
3. Confirm the ACIS-06 amendments ([OQ-03a–d]) with ACIS-06's owner. ACIS-06 is LOCKED, so this is a versioned amendment, not an edit by stealth. (OQ-03a done: ACIS-06 v1.4.)
4. Re-fetch every `[F-nn]` URL. A changed source is a finding. (Done for the demo path; see Appendix A. The FTMO sources are re-fetched before an FTMO attach.)
5. Verify that no requirement lacks a master § or ledger ID. (Done: the v1.0 additions cite ACIS-06 C-EXE-7/8, master v2.23 and GAP-P12D-118.)

---

## Appendix A — Evidence register
All fetched **2026-09-24** unless stated (F-41 and F-42 on 2026-09-25). Grades follow the research convention:
- **(a)** the platform's or firm's own primary document or source code;
- **(b)** a forum answer by someone who was then on the platform's support staff (Spotware's community team: `amusleh`, `PanagiotisCharalampous`), or credible trade press;
- **(c)** a user report, or a forum post whose author cannot be shown to speak for the platform.

A forum answer is never an official document. It is used only where the docs are silent, and each such point is re-checked by a probe. The `.proto` quotes are from `spotware/openapi-proto-messages`, branch `main`, whose last commit is **2025-11-13** ("Fix typo in modelmessages") [F-28]. The docs pages were checked against it and agree on every field quoted; the one difference is that the docs describe `gslCharge` in more detail than the proto (F-41).

| ID | Fact (verbatim where quoted) | Source | Grade |
|---|---|---|---|
| F-01 | Endpoints: live `live.ctraderapi.com:5035` (Protobuf) / `:5036` (JSON); demo `demo.ctraderapi.com:5035` / `:5036`. "Demo and live environments are fully separated. If you connect to a live endpoint, you cannot use demo accounts in your application, and vice versa." "ports 5035 and 5036 both support TCP and WebSocket connections." | https://help.ctrader.com/open-api/proxies-endpoints/ | a |
| F-02 | "The TCP client connection must use SSL, otherwise you will not be able to connect or interact with the API." | https://help.ctrader.com/open-api/connection/ | a |
| F-03 | "To keep a connection alive, keep sending a heartbeat event (ProtoHeartbeatEvent) every 10 seconds." · FAQ: "Applications are disconnected by the server after a period of inactivity … send a heartbeat to the server at least once every 10 seconds." · proto: "Open API client can send this message when he needs to keep the connection open for a period without other messages longer than 30 seconds." | /open-api/connection/ ; /open-api/faq/ ; `OpenApiCommonMessages.proto` | a |
| F-04 | "At most, you should create two connections: one for demo accounts and one for live accounts. Each connection can support an unlimited number of accounts of a certain type." · `amusleh` (Spotware community team, 2022-02-01): "for each connection you can only use one API application … your connection environment must match with account type" · a user (2019) quoting the then-current docs: "25 concurrent connections per application." | /open-api/connection/ ; https://community.ctrader.com/forum/connect-api-support/37539/ ; …/21640/ | a ; b ; c (superseded) |
| F-05 | "a maximum of 50 requests per second per connection for any non-historical data requests … a maximum of 5 requests per second per connection for any historical data requests." · `ProtoOAErrorRes.retryAfter`: "When you hit rate limit with errorCode=BLOCKED_PAYLOAD_TYPE, this field will contain amount of seconds until related payload type will be unlocked." · forum answer (2023-06-26, by `PanagiotisChar`, signed "Aieden Technologies", so not shown to be Spotware): "There limits are per connection, no matter how many users are authorized through it" | https://help.ctrader.com/open-api/ ; `OpenApiMessages.proto` ; forum …/41177/ | a ; a ; c |
| F-06 | Protobuf framing: "Get the length of the array … Create a new byte array from this integer. Reverse the new byte array. Concatenate…"; on receipt, "Receive the first four bytes … Reverse these four bytes and change them to an integer." The SDK reads with Twisted `Int32StringReceiver`. `ProtoMessage{payloadType, payload, clientMsgId}`. | https://help.ctrader.com/open-api/sending-receiving-protobuf/ ; OpenApiPy `tcpProtocol.py` | a |
| F-07 | JSON messages carry `"clientMsgId"`, `"payloadType"`, `"payload"`; "When working with JSON, you can use either a TCP connection or a WebSocket connection." · "If you intend to use JSON, there is no need to use our SDKs". The page documents no framing for JSON over raw TCP (an observed absence). | https://help.ctrader.com/open-api/sending-receiving-json/ ; /open-api/ | a |
| F-08 | OAuth 2.0: "An authorisation code … Its expiration period is one minute." "The expiration period of an access token is 2,628,000 seconds (approximately 30 days)." "The refresh token does not have an expiration period." FAQ: "valid forever until you use it to refresh an access token or if you re-authorise". Scopes: `accounts` ("View only access") and `trading` ("Full access"). Token endpoint `https://openapi.ctrader.com/apps/token`. After a refresh: "You can safely use these new values while the old values of the same keys are automatically invalidated." The sample binds `ctidTraderAccount[0]`. | https://help.ctrader.com/open-api/account-authentication/ ; /open-api/faq/ | a |
| F-09 | "If a user creates additional accounts after completing the actions described above, these accounts will not be authorised inside the application. Instead, the user would need to be redirected back to the URL provided above so that they could give the application access to any additional accounts". | /open-api/account-authentication/ | a |
| F-10 | "The Playground provides a quick means for attaining an access token for your own cTID". "The very first redirect URI is for the Playground service … It must never be used for a production application." | /open-api/account-authentication/ ; /open-api/api-application/ | a |
| F-11 | "Its status will be set to 'submitted'. After the application is reviewed by Spotware, you will be contacted via email." | https://help.ctrader.com/open-api/api-application/ | a |
| F-12 | `ProtoOAAccountsTokenInvalidatedEvent`: "Reasons to trigger: account was deleted, cTID was deleted, token was refreshed, token was revoked." · `ProtoOAClientDisconnectEvent`: "All the sessions for the traders' accounts will be terminated." · `ProtoOAAccountDisconnectEvent`: "A new session must be authorized for the account." | `OpenApiMessages.proto` | a |
| F-13 | `ProtoOANewOrderReq`: `volume` "represented in 0.01 of a unit (e.g. 1000 in protocol means 10.00 units)"; `stopLoss` "The absolute Stop Loss price … Not supported for MARKET orders."; `relativeStopLoss` "Specified in 1/100000 of unit of a price … For BUY stopLoss = entryPrice - relativeStopLoss, for SELL stopLoss = entryPrice + relativeStopLoss."; `clientOrderId` "MaxLength = 50"; `label` "MaxLength = 100"; `timeInForce` default `GOOD_TILL_CANCEL`. `ProtoOAClosePositionReq{positionId, volume}`. `ProtoOAAmendPositionSLTPReq{positionId, stopLoss, …}`. | `OpenApiMessages.proto` ; https://help.ctrader.com/open-api/messages/ | a |
| F-14 | Spotware staff: "To change relative stop loss or take profit to price levels you should divide the relative value to 100000 and then round it to symbol digits"; "stopLossInRelative = Round(2537 - 2500, symbol.Digits) * 100000"; the venue error "Relative stop loss has invalid precision". Absolute: "The decimal places of your stop price must much with symbol digits." | https://community.ctrader.com/forum/connect-api-support/37262/ (2021–22) ; …/37007/ (2021) | b |
| F-15 | User report: with `relativeStopLoss = 1000` "it accept the order, but the SL has not been set" (unresolved in the thread). The same thread, staff: "For Marker Orders you need to set the relativeStopLoss. stopPrice is not supported for Market orders." | https://community.ctrader.com/forum/connect-api-support/38778/ (2022) | c ; b |
| F-16 | "cTrader provides server-side protections out of the box … All protections work across cTrader apps and remain active after your session ends." · "When the price hits the chosen stop-loss level, the position is closed at the best available market price, limiting further losses." | https://help.ctrader.com/ctrader-web/trading/protections/ ; https://help.ctrader.com/trading-with-ctrader/orders/ | a |
| F-17 | `ProtoOAExecutionEvent` "Acts as response to the ProtoOANewOrderReq, ProtoOACancelOrderReq, ProtoOAAmendOrderReq, ProtoOAAmendPositionSLTPReq, ProtoOAClosePositionReq requests"; `isServerEvent` "If TRUE then the event generated by the server logic instead of the trader's request. (e.g. stop-out)". `ProtoOAExecutionType`: ORDER_ACCEPTED, ORDER_FILLED, ORDER_REPLACED, ORDER_CANCELLED, ORDER_EXPIRED, ORDER_REJECTED, ORDER_CANCEL_REJECTED, SWAP, DEPOSIT_WITHDRAW, ORDER_PARTIAL_FILL, BONUS_DEPOSIT_WITHDRAW. `ProtoOAOrderErrorEvent` "sent when errors occur during the order requests". | `OpenApiMessages.proto` ; `OpenApiModelMessages.proto` | a |
| F-18 | `ProtoOAReconcileReq.returnProtectionOrders`: "If TRUE, then current protection orders are returned separately, otherwise you can use position.stopLoss and position.takeProfit fields." The response carries "open positions" and "pending orders". | `OpenApiMessages.proto` | a |
| F-19 | `ProtoOAOrderListReq` ("Trader's orders filtered by timestamp"), `ProtoOADealListReq` (`maxRows`, `hasMore`), `ProtoOAOrderDetailsReq` ("Order and its related Deals"), `ProtoOADealListByPositionIdReq`; `ProtoOAOrder.clientOrderId` "Max Length = 50 chars". | `OpenApiMessages.proto` ; `OpenApiModelMessages.proto` | a |
| F-20 | `ProtoOASymbol`: `symbolId` "Different servers have different IDs"; `minVolume`/`stepVolume`/`maxVolume` "in cents"; `lotSize` "(in cents)"; `digits`, `pipPosition`; `slDistance` + `distanceSetIn` (`SYMBOL_DISTANCE_IN_POINTS`/`…_IN_PERCENTAGE`); `schedule` "in seconds starting from SUNDAY 00:00 in specified time zone", `scheduleTimeZone`, `holiday`; `tradingMode` (`ENABLED`, `CLOSE_ONLY_MODE`, …); `pnlConversionFeeRate` "Percentage (1 = 0.01%) of the realized Gross Profit, which will be paid by the Trader for any trade if the Quote Asset of the traded Symbol is not matched with the Deposit Asset"; the swap and commission fields. | `OpenApiModelMessages.proto` | a |
| F-21 | `ProtoOATrader`: `balance`, `moneyDigits`, `accessRights` (`FULL_ACCESS`/`CLOSE_ONLY`/`NO_TRADING`/`NO_LOGIN`), `accountType` (`HEDGED`/`NETTED`/`SPREAD_BETTING`), `isLimitedRisk` ("Such accounts are require to have guaranteed stop loss on all positions"), `depositAssetId`, `registrationTimestamp` ("Should be used as minimal date in historical data requests"). `ProtoOATraderUpdatedEvent` "sent when a Trader is updated on Server side". | `OpenApiModelMessages.proto` ; `OpenApiMessages.proto` | a |
| F-22 | `ProtoOACtidTraderAccount.isLive`: "If TRUE then the account is belong to Live environment and live host must be used to authorize it". | `OpenApiModelMessages.proto` | a |
| F-23 | "As the bid and ask fields are optional, you may not necessarily see ProtoOASpotEvent messages where both are specified." · Spot prices "Specified in 1/100000 of unit of a price". `subscribeToSpotTimestamp`: "If TRUE you will also receive the timestamp in ProtoOASpotEvent"; `timestamp` "The Unix time for spot" (unit unstated). "First event, received after subscription will contain latest spot prices even if market is closed." FAQ: "If the markets are closed, you will only receive a single spot event with the closing prices." | https://help.ctrader.com/open-api/symbol-data/ ; `OpenApiMessages.proto` ; /open-api/faq/ | a |
| F-24 | Tick history: "It is impossible to request historical tick data for a period larger than one week"; the tick limit per response "depends on the configuration of the cTrader backend"; `hasMore`. FAQ: "trend bars are only created if there are incoming ticks." | /open-api/symbol-data/ ; /open-api/faq/ | a |
| F-25 | `ProtoOAPositionUnrealizedPnL.netUnrealizedPnL`: "The net unrealized PnL of the position denoted in the account deposit currency. It does not include potential closing commission." | `OpenApiModelMessages.proto` ; https://help.ctrader.com/open-api/profit-loss-calculation/ | a |
| F-26 | "Sometimes we do maintenance and upgrades during weekends, and the API is inaccessible during the maintenance period." · `ProtoErrorRes.maintenanceEndTimestamp`; `SERVER_IS_UNDER_MAINTENANCE`. | /open-api/faq/ ; `OpenApiCommonMessages.proto` ; `OpenApiModelMessages.proto` | a |
| F-27 | OpenApiPy: license MIT; `requires_dist` = `Twisted==24.3.0, pyOpenSSL==24.1.0, protobuf==3.20.1, requests==2.32.3, inputimeout==1.0.4`; latest release 0.9.3, uploaded 2024-08-06; repo last pushed 2024-08-07. `TcpProtocol`: sends its own `ProtoHeartbeatEvent` only when the queue is empty and the last send was `> 20` s ago, and echoes every server heartbeat on receipt; `LoopingCall(self._sendStrings)` every 1 s sending `min(size, numberOfMessagesToSendPerSecond)` (default 5); `_send_queue = deque([])` declared at class level. "The Python SDK does not support the WebSocket standard." | https://github.com/spotware/OpenApiPy (`pyproject.toml`, `ctrader_open_api/client.py`, `tcpProtocol.py`) ; https://pypi.org/pypi/ctrader-open-api/json ; /open-api/connection/ | a |
| F-28 | The proto repository and its pin: `spotware/openapi-proto-messages`, `main`, last commit 2025-11-13T15:50:08Z "Fix typo in modelmessages". | https://github.com/spotware/openapi-proto-messages | a |
| F-29 | FTMO: "When using a cTrader, you do not log in with each trading account individually. You log in with your own cTrader registration, and we only connect our simulated trading accounts to your own cTrader registration." | https://ftmo.com/en/faq/how-do-i-log-in-to-ctrader/ (modified 2026-03-23) | a |
| F-30 | FTMO Free Trial: "Traders can use our Free Trial demo account for 14 days. After this period, they can create a new one." "Each trader is permitted only one Free Trial at a time (you can delete it and start a new one)". The 2-Step trial: "The Profit Target is reduced from 10% to 5%. The Minimum Trading Days requirement is reduced from 4 to 2." "all accounts we provide to our clients are demo accounts with fictitious funds". | https://ftmo.com/en/ftmo-free-trial/ (modified 2026-05-12) ; https://ftmo.com/en/faq/how-about-a-free-trial/ (modified 2026-05-05) | a |
| F-31 | FTMO: "Developers can also integrate apps using the Open API." | https://ftmo.com/en/trading-platforms/ (modified 2026-08-31) | a |
| F-32 | FTMO's cap: "an excessive number of more than 2,000 server requests per day on individual simulated trades or pending orders being opened, modified, or closed"; FAQ: "2000 max positions per day". | research §1 (ftmo.com/en/forbidden-trading-practices/, modified 2026-02-02), lead-verified in GAP-P12D-57 | a |
| F-33 | Spotware terms: "you should not provide or embed in the application functionality that results in the execution of trading actions on behalf of the trader, without his/her explicit prior approval." Fair use: "In case of misuse of the API, Spotware Systems Ltd reserves the right to restrict or remove access to your application." | https://help.ctrader.com/open-api/terms-of-use/ | a |
| F-34 | `ProtoOAErrorCode` / `ProtoErrorCode` values as used in §12, e.g. `REQUEST_FREQUENCY_EXCEEDED = 108`, `CONNECTIONS_LIMIT_EXCEEDED = 67` ("Limit of connections is reached for this Open API client"), `ALREADY_LOGGED_IN = 14`, `TRADING_BAD_STOPS = 126`, `MARKET_CLOSED = 9`, `BLOCKED_PAYLOAD_TYPE = 11`. | `OpenApiModelMessages.proto` ; `OpenApiCommonModelMessages.proto` | a |
| F-35 | `ProtoOATimeInForce`: GOOD_TILL_DATE, GOOD_TILL_CANCEL, IMMEDIATE_OR_CANCEL, FILL_OR_KILL, MARKET_ON_OPEN; `ProtoOAOrder.timeInForce` default `IMMEDIATE_OR_CANCEL`. | `OpenApiModelMessages.proto` | a |
| F-36 | "the API can be accessed by anyone with a cTID, and, by default, it is supported by all trading accounts of any cTrader-affiliated brokers." "You can use cTrader Open API to trade on behalf of both demo and live accounts." | https://help.ctrader.com/open-api/ | a |
| F-37 | `ProtoOAPosition.stopLoss` "Current stop loss price"; `positionId` "Note: trader might have two positions with the same id if positions are taken from accounts from different brokers."; `usedMargin`, `swap`, `moneyDigits`. | `OpenApiModelMessages.proto` | a |
| F-38 | `ProtoOADeal`: `filledVolume` "in cents", `executionPrice`, `executionTimestamp`, `commission`, `closePositionDetail`; `ProtoOAClosePositionDetail`: `grossProfit`, `swap`, `commission`, `balance` ("Account balance after closing deal execution"), `pnlConversionFee`. | `OpenApiModelMessages.proto` | a |
| F-39 | `ProtoOACashFlowHistoryListReq`: "Validation: toTimestamp - fromTimestamp <= 604800000 (1 week)." | `OpenApiMessages.proto` | a |
| F-40 | `ProtoOATrader` carries `balance` and no equity field (an observed absence across the model). Equity must be derived. | `OpenApiModelMessages.proto` | a |
| F-41 | Docs model page (newer wording than the proto): `distanceSetIn` — "Whether slDistance, tpDistance, gslDistance and gslCharge are expressed in points or as a percentage of the price." `gslCharge` — "In points mode it is a price distance per unit of volume: divide by 10^digits … In percentage mode it is hundredths of a percent (100 means 1%)". `slDistance` — "Minimum allowed distance between stop loss and current market price." (no unit stated). | https://help.ctrader.com/open-api/model-messages/ (fetched 2026-09-25) | a |
| F-42 | Finance Magnates, 2025-10-22: Spotware "has introduced free prop trial accounts for proprietary trading firms. The new account type provides time-limited demo access"; "Several firms, including FTMO … have already adopted the new accounts"; they run "in a controlled demo environment", "carry a 'FREE' flag … and expire automatically after the trial period"; "Traders have access to the full cTrader environment, including … algorithmic trading". | https://www.tradingview.com/news/financemagnates:eb90bf57c094b:0-ftmo-instant-funding-begin-using-spotware-demo-accounts-for-prop-firms-on-ctrader/ (fetched 2026-09-25) | b (trade press) |

| F-43 | Pepperstone: "[c]Trader and TradingView demo accounts expire after 90 days of inactivity. Pepperstone, MT4 and MT5 demo accounts expire after 60 days of creation." (the fetched text dropped the leading "c"); for cTrader, "top up your virtual funds at any time". CMA register of licensees: "Pepperstone Markets Kenya Limited", licence number 128. | https://pepperstone.com/en/ways-to-trade/demo-accounts/ ; https://licensees.cma.or.ke/licenses/5/?q=Pepperstone (both fetched 2026-09-29) | a |

**Re-fetched 2026-09-29 by the review pass (§15.3 step 4).** F-01, F-02, F-03, F-07, F-08, F-11, F-16, F-27, F-28, F-33 and F-36 read as quoted (F-28's last commit is still 2025-11-13). F-07's page adds that the envelope's `payloadType` is an integer in JSON (its example: `"payloadType": 2100`), half of OQ-12. F-10's page now words the Playground redirect as "As it does not work outside the playground environment, you cannot use it in your code"; the substance holds. The FTMO sources (F-29–F-32, F-42) were not re-fetched: they gate an FTMO attach, not the demo, and are re-fetched before one.

## Appendix B — Open questions
**BLOCKING** means the spec cannot LOCK until it is ruled. **Attach-gating** means the spec can lock, but no attach to the named venue until it is ruled. **Probe** means the first recorded demo session settles it (it cannot be settled from documents).

| ID | Question | Why it matters | Class | Resolver |
|---|---|---|---|---|
| OQ-01 | **May ACIS send orders to a venue *demo/practice* account while in `paper` mode?** Master §7.5 says "paper mode is never granted a real-order path", and ACIS-11 defines PAPER as "live data, no real orders". Yet master §15 phase 12 orders "OANDA practice account first … live only after §14 minimums met and human sign-off", which puts practice trading **before** live. As written, a demo run needs either a "real-order path" in paper mode or `live` mode, and `live` needs §14, which the engine fails (GAP-P12D-49). **Proposed ruling (for the owner, not applied):** "Paper mode may route orders to a platform adapter only when (i) the venue reports the bound account as non-live (`isLive = false` on cTrader), **and** (ii) the account's human-committed rulebook declares `account_class: practice` (no fee, no deposit, nothing of value at risk); any other account requires `live` mode with the §12 human token and the §14 gates." Clause (ii) matters because FTMO's *paid* challenges are also "demo accounts with fictitious funds" [F-30] and could sit on the same environment as the trial, which trade press places in "a controlled demo environment" [F-42][OQ-10]. `isLive` alone therefore cannot tell a free trial from a paid challenge. | Mode semantics are human-only (CLAUDE.md). Without a ruling, Track A has no lawful mode to run in. | **RULED 2026-09-29** — owner chose a new `practice` mode (master v2.23; ACIS-08 v1.4), with clause (ii) kept as `account_class: practice` | Owner (master §7.5/§12/§15 amendment) |
| OQ-02 | **Transport and dependency:** JSON over WebSocket via `aiohttp` (no new dependency), Protobuf over TLS/TCP with the `protobuf` runtime (a §16 edit), or the official SDK (rejected, §3.3)? | §16: "nothing without a spec edit". | **RULED 2026-09-29** — route C, JSON over WebSocket via `aiohttp` (the owner delegated the setup; no §16 edit) | Owner / review; confirmed by the first probe |
| OQ-03 | **ACIS-06 amendments this adapter needs** (ACIS-06 is LOCKED): (a) `venue_fills()`, an unsolicited-fill channel, so stop hits reach Risk and do not read as drift (§7.7) — **blocking**; (b) per-symbol quantity constraints and a `quantize()` call in the orchestrator before fragmenting (§6.3); (c) `action` (open or close) on `submit_order` instead of the face's inference (§7.3 step 1); (d) conformance-suite changes for real venues: a live-quote fixture, the relative-stop assertion, recorded-frame partial fills, a triggerable mock stop (§14.2). | Without (a), the first stop-out HALTs the engine as restart drift, and in-session accounting is wrong. | (a) **RULED 2026-09-29** — owner-ratified, ACIS-06 v1.4 `venue_fills()`; (b) and (c) **resolved** by ACIS-06 v1.3 (C-EXE-8 rounds before dispatch, C-EXE-7 `close_position` carries the intent); (d) **resolved** by the v1.0 review as ACIS-06 v1.4's conformance variant (test contract only) | ACIS-06 owner via the review pass |
| OQ-04 | **Which messages count toward FTMO's (and E8's) 2,000/day?** ACIS assumes every request except heartbeats (§6.5). The §6.5 defaults need re-deriving from the GAP-0075 policy's real order rate. | Too loose risks "hyperactivity"; too tight starves the demo. | Attach-gating (FTMO/E8) | FTMO email Q2 (research §9.1), E8 Q4 |
| OQ-05 | **Does FTMO permit unattended Open API trading on its accounts, the Free Trial included, and does the trial use the same servers and feed as paid products?** | Standing risk at the destination firm (T&C 7.9, research §2.1). | Attach-gating (FTMO) | FTMO email Q1, Q5 |
| OQ-06 | **Can a second connection (the watchdog) authorise the same account while the engine's connection is alive?** And does an engine token refresh break the watchdog mid-flatten? Also for the review pass: the account binding now lives in two human-committed files (`system_config.yaml` and `watchdog.yaml`, §7.9), and ACIS-12 forbids the engine to read `watchdog.yaml`, so neither side can detect a mismatch. The review must choose where the single binding lives. | Master §8.6 layer 2 depends on it; a binding mismatch would make the watchdog flatten the wrong account, or none. | Probe (§14.2 case 8); a live gate if it fails | First demo session; Spotware support if negative |
| OQ-07 | **Is the relative stop attached atomically with the market fill?** Does the `ORDER_FILLED` event's position already carry `stopLoss`? | Sets how often the §7.3 step-6 repair spends reserve requests; one user report of a missing stop exists [F-15]. | Probe | First demo session |
| OQ-08 | **The spot `timestamp` unit** (ms assumed); whether the technical first event carries **both** sides; **the server's heartbeat cadence.** | Clock-skew and staleness correctness (ACIS-01). | Probe | First demo session |
| OQ-09 | **Confirm that `slDistance` in points mode means `slDistance / 10**digits` of price.** The docs define points mode this way for `gslCharge` and say `distanceSetIn` governs `slDistance` too [F-41]; `slDistance`'s own row states no unit. | The client-side "stop too close" pre-check (§6.3). A wrong unit only costs a venue-side reject, never an unprotected position. | Probe (non-blocking) | First demo session |
| OQ-10 | **Which host (`isLive`) do FTMO Free Trial accounts and paid challenge accounts sit on?** Trade press reports that the FTMO trial on cTrader is Spotware's "free prop trial" account, run "in a controlled demo environment" [F-42], so the trial very likely reports `isLive = false`. Paid challenges are "simulated" too [F-30]; their environment is unknown. | Feeds OQ-01's criterion and §7.1 A2. | Probe + FTMO | Account list on the first grant |
| OQ-11 | **FTMO's cTrader symbol names, `minVolume`/`stepVolume`/`lotSize`, commission, and whether its 0.7% currency adjustment (T&C 5.3.4) is `pnlConversionFeeRate = 70`.** Is the trial Swing or Standard? | The symbol map, lot rounding, the C8 cost model (GAP-P12D-52 item 12). | Attach reads them; FTMO email Q6 | First attach + email |
| OQ-12 | **The JSON encoding of enums (names or integers) and WebSocket frame type (text or binary)**; OQ-02 picked JSON. Half answered 2026-09-29: the envelope's `payloadType` is an integer [F-07]; enums inside `payload` and the frame type remain. | `wire.py` correctness. | Probe | First demo session |
| OQ-13 | **Spotware's application approval lead time**, and a **production redirect URI** for a headless single-user deployment (Playground tokens are for development [F-10]). | Track A's calendar; production auth. | Attach-gating (live only) | Owner registers the app (human) |
| OQ-14 | **Does cTrader deduplicate `clientOrderId`?** ACIS assumes not (§7.3 step 4). | Only a defence-in-depth question; ACIS does not rely on it. | Non-blocking | Probe |
| OQ-15 | **Does `netUnrealizedPnL` include swap and the opening commission?** | The equity definition (§4.4, C-VEN-12). | Probe | Compare against the cTrader UI on the demo |
| OQ-16 | **How does FTMO's simulated server fill a stop that is gapped through** (fill worse, as cTrader documents [F-16], or something else)? | The §8.5 gap law and GAP-P12D-42. Observational only. | Non-blocking (operational) | `OPERATIONS_LEDGER.md` after the first weekend |
| OQ-17 | **Does a MARKET order honour `timeInForce = IMMEDIATE_OR_CANCEL`, and do demo servers ever partial-fill?** | Descriptor honesty for `supports_ioc`; the partial-fill conformance path. | Probe | First demo session |
| OQ-18 | **How does an expiring or breached FTMO trial account present on the API?** (Access rights? A disconnect event? An error code?) Spotware's trial accounts "expire automatically after the trial period" and carry a "FREE" flag [F-42]; the flag is not in the Open API model, and the API-side signal of expiry is undocumented. | The §7.2 `DETACHED` trigger. | Probe (day 14 or first breach) | First trial cycle |

## Changelog
- **1.0 (LOCKED — 2026-09-29).** The review pass by the lead, who did not author the draft (§15.3; the `_SPEC_REVIEW_PASS.md` checks 3A–3F):
  - **Reconciled with ACIS-06 v1.3, merged after the draft was written:** `close_position` carries the close intent (OQ-03c resolved; §7.3 no longer infers it); the orchestrator rounds lots down before dispatch (OQ-03b resolved); the request budget no longer stops exits: at `used ≥ budget` closes and stop repair pass, paced by C-EXE-8, where the draft stopped everything. A hedging-account reduce spanning several fragment positions is specified (§7.3 step 5).
  - **OQ-03d resolved** as ACIS-06 v1.4's conformance variant (relative stop within one tick, live-quote fixture, recorded-frame partials, the stop-hit case).
  - **Added:** the mode-to-face rule and the practice-mode refusal (§7.1 A11), `account_class` in the `AttachReport`, and `venue.max_orders_per_day`, so the §6.5 feasibility check certifies now; the §6.5 defaults re-derived under R-1.
  - **Evidence:** the demo-path sources re-fetched and unchanged; F-43 added (Pepperstone: CMA licence 128; its cTrader demo expires after 90 days of inactivity, so v0.2's "does not expire" is corrected); OQ-12 half answered.
  - No guardrail, HALT/veto semantics, equity floor or rulebook value changed.
- **0.2 (DRAFT, NOT LOCKED — 2026-09-29).** The three BLOCKING questions ruled and folded in: OQ-01 (the owner chose a new `practice` mode, master v2.23; §7.1 A2 keeps the proposed clause (ii) as `account_class: practice`), OQ-02 (route C, JSON over WebSocket via `aiohttp`, the lead's choice under the owner's delegation), OQ-03a (ACIS-06 v1.4 `venue_fills()`, owner-ratified). First venue: a Pepperstone cTrader demo (non-expiring); OANDA v20 dropped (GAP-P12D-43). No guardrail, HALT/veto semantics, equity floor or rulebook value changed.
- **0.1, continued (DRAFT, NOT LOCKED — 2026-09-25, after a session-limit break).** The same draft, corrected before hand-off:
  - Source grades tightened: two forum posts were downgraded to (c) because their authors cannot be shown to speak for Spotware (F-04, F-05). The `ALREADY_LOGGED_IN` citation was re-pointed to the proto; a third-party repository had been summarised as Spotware.
  - The SDK heartbeat wording was made exact (F-27).
  - New evidence: F-41 (the points and percentage units of `distanceSetIn`, which narrows OQ-09 to a confirmation probe, now non-blocking) and F-42 (FTMO's trial is Spotware's time-limited "free prop trial" demo account, which informs OQ-01, OQ-10 and OQ-18).
  - Explicit Status and Corrections-applied rows added to the metadata; the watchdog's configuration inputs (§7.9) specified; a two-file binding-mismatch risk added to OQ-06.
- **0.1 (DRAFT, NOT LOCKED — 2026-09-24).** First draft by SPEC-AUTHOR, in fresh context, from master §7.5/§8.6/§9.5/§13/§16, ACIS-01/-06/-07/-12, the 2026-09-24 prop-venue research, and primary cTrader sources fetched the same day (Appendix A).
  - **Scope:** the generic attach protocol (A1–A11) plus account churn; the cTrader Open API adapter (session / feed / execution face / watchdog plugin); the prop-safety mechanics at the venue boundary (a rolling-24 h budget ≤ 1,000 with a close reserve, lot-step rounding down, a venue-schedule pre-check, the rulebook load).
  - **Findings raised to Appendix B rather than decided:** 18 open questions, 3 BLOCKING. The most material:
    - the paper-mode / venue-demo contradiction (OQ-01);
    - the transport dependency (OQ-02);
    - ACIS-06's missing unsolicited-fill channel, without which the first stop-out reads as restart drift (OQ-03a).
  - No guardrail, HALT/veto semantics, equity floor, rulebook value or other spec was changed.
