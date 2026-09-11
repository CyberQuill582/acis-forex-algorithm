# ACIS-01 — Data Ingestion & Normalisation — Deep Specification

| | |
|---|---|
| **Document ID** | `ACIS-SPEC-DATA-001` |
| **Version** | 1.2 (LOCKED — master v2.14 local market time, 2026-09-11) |
| **Layer / DIR** | Layer 1 · `[DIR:core/data]` |
| **Consumes** | raw broker/feed payloads (external) |
| **Emits** | `MarketState` (frozen) → NVMA (ACIS-02) |
| **Depends On** | `../ACIS_SPEC.md` §3, §10, §11, §13, §16 · `ACIS-00-INDEX.md` |
| **Blocks** | ACIS-02 (NVMA), and transitively all lower layers |
| **Corrections applied** | C1 (session tagging), F16 (deep-immutable `raw`), F17 (Decimal boundary), F18 hand-off (session-median inputs), C10 (asset-class law, master §3.7: contract metadata + per-calendar sessions), C13 feed-face rule (master §7.5: no account surface) |

## Table of contents
1. Executive purpose & scope · 2. Boot/entry contract & inputs · 3. Layer architecture & responsibility · 4. Output contract · 5. Complete data schemas · 6. Algorithm & config set · 7. Core logic · 8. State machine & loop cadence · 9. Persistence & logging · 10. Store/DB schema (DDL) · 11. Interface/MCP contract · 12. Error taxonomy · 13. Logic-flaw registry · 14. Test contract · 15. Integration gate · Changelog

---

## 1. Executive purpose & scope

**Purpose.** Turn heterogeneous, unreliable broker feeds into a single, validated, immutable `MarketState` object per instrument per tick, and make it the *only* market-truth the rest of ACIS ever sees. Every quality problem in raw data is caught here or nowhere.

**IS (in scope):** feed connectors as the **feed faces of the master §7.5 platform adapters** (phase-1 gate: the mock paper feed; OANDA v20 primary + MT5 join at phase 12 conformance; IBKR/cTrader/etc. per the ACIS-13 contract) behind one interface — a feed face exposes **no account or position surface** (master §7.5, C-DATA-6); instrument contract metadata + market calendars per the asset-class law (master §3.7, `asset_classes.py`); field-level validation; staleness detection; derived fields (`spread`, `mid`, `tick_velocity`, `session`, `macro_events_imminent`); microsecond-stamped JSONL logging; async out-of-band persistence to SQLite (dev) / TimescaleDB (prod) with bounded-queue backpressure.

**IS NOT (out of scope — hard walls):** no classification (that is NVMA/ACIS-02), no signals, no sizing, no execution, no indicator computation beyond the raw derived fields above (ATR/ADX/Hurst/Bollinger live in ACIS-02), no prediction, no smoothing/interpolation that invents ticks. This layer never *repairs* data by guessing — it validates, derives, flags, or rejects.

**Done-when:** (a) `MarketStateFactory` produces a valid `MarketState` from every conformant payload of all four feeds and raises `DataQualityError` on every non-conformant one; (b) stale/duplicate/out-of-order/NaN inputs are handled per §7 with an observable outcome; (c) the async writer sustains feed rate without blocking the fast loop, emitting `DATA_BACKPRESSURE` under overload; (d) all §14 tests pass with postcondition assertions.

## 2. Boot/entry contract & inputs

**Entry point:** `core/data/feeds.py::FeedConnector.stream() -> AsyncIterator[RawTick]` and `core/data/normaliser.py::MarketStateFactory.build(raw: RawTick, ctx: FeedContext) -> MarketState`.

**Inputs at boot:**
- `system_config.yaml` (loaded once, pydantic-settings, master §9): `data.stale_threshold_ms`, `data.tick_velocity_window_s` (default 10), `data.queue_max`, `session_boundaries` (the C1 list of local `{zone, at}` times, shared), `data.macro_lookahead_min` (default 30), broker selection + credentials (from env, never in YAML).
- `instruments.yaml`: the enabled instrument universe + per-instrument **full §3.7 contract metadata** — asset class, tick size + tick value, lot/contract step + minimum, margin model, swap/financing convention, `max_plausible_spread`, and a named **market calendar** (forex 24/5 default from the C1 boundary list; exchange calendars with holidays/half-days for futures) — plus cluster membership and coupled-pair declarations. Incomplete contract metadata on an enabled instrument is fatal at boot (master §3.7).
- A macro-economic calendar source (Tier-1 events) — read-only, injected; the feed layer only computes `macro_events_imminent`, it does not fetch predictions.

**Boot preconditions (fail fast, refuse to start):** config schema valid; every enabled instrument has `pip_size` + `min_lot`; `session_boundaries` non-empty, duplicate-free, and cross-checked against the fx session opens (GAP-0025/0033); broker credentials present for the selected broker. A missing required value is fatal — no defaults for anything that affects correctness (master §9).

## 3. Layer architecture & responsibility

Single responsibility: **normalise and validate**. The layer has exactly two units:
- `FeedConnector` (abstract) with concrete `OandaV20Feed`, `MT5Feed`, `IBKRFeed`, `MockPaperFeed` — all expose the identical async `stream()` and `snapshot(instrument)` interface. Broker quirks are absorbed here and nowhere else.
- `MarketStateFactory` — pure function from `RawTick` → `MarketState`, plus the small rolling state needed for `tick_velocity` and staleness (per-instrument ring buffers). It holds **no** portfolio, regime, or signal state.

**What it must NOT do:** import anything from `core/regime`, `core/optimizer`, `core/signals`, `core/governor`, `core/execution`, `core/risk` (downward-only law, master §2; enforced by the import-linter contract). It must not block on the DB writer. It must not mutate a `MarketState` after construction.

## 4. Output contract — `MarketState` (locked first)

```python
@dataclass(frozen=True)
class MarketState:
    timestamp: datetime          # feed event time, tz-aware UTC, microsecond precision
    instrument: str              # canonical symbol, e.g. "EUR_USD"
    bid: float
    ask: float
    spread: float                # ask - bid, in price units (derived, validated ≥ 0)
    mid: float                   # (bid + ask) / 2 (derived)
    volume: float                # tick/bar volume as reported (≥ 0)
    order_book_depth: Mapping[str, Tuple[Tuple[float, float], ...]]
                                 # {"bids": ((px,vol),...), "asks": (...)} — immutable tuples
    tick_velocity: float         # ticks/sec, rolling window (default 10s), ≥ 0
    session: str                 # london | new_york | tokyo | overlap | closed
    macro_events_imminent: bool  # Tier-1 event within data.macro_lookahead_min
    ingest_ts: datetime          # local receipt time (for clock-skew detection, §13)
    is_stale: bool               # timestamp delta > stale_threshold_ms
    raw: Mapping                 # original payload, DEEP-IMMUTABLE (F16)
```

**Contract rules:** frozen; constructed only by `MarketStateFactory`; every field validated (§6); `order_book_depth` and `raw` are immutable mappings/tuples (not `dict`/`list`) so the frozen guarantee is deep, not shallow (F16). Consumers (NVMA) read; they never mutate. `session == "closed"` ⇒ downstream treats the instrument as untradeable. Note: `is_stale` is exposed on the object (not silently dropped) so NVMA can veto on it and the monitor can report it.

## 5. Complete data schemas

**`RawTick`** (feed-agnostic normalised input to the factory; each connector maps its native payload to this): `event_time`, `recv_time`, `instrument`, `bid`, `ask`, optional `volume`, optional `book`, `provider`, `raw_payload`.

**`FeedContext`** (small rolling state per instrument, held by the factory): `velocity_ring: Deque[datetime]`, `last_event_time: datetime | None`, `session_calendar`, `session_median_cache` (spread + velocity medians, feeds F18 in ACIS-02 — computed here, consumed there).

**Field validity table (enforced on construction; violation ⇒ `DataQualityError`):**
| Field | Rule |
|---|---|
| `timestamp` | tz-aware UTC; not in the future beyond `clock_skew_tolerance_ms`; ≥ `last_event_time` unless flagged out-of-order (§7) |
| `bid`,`ask` | finite (`math.isfinite`), > 0; `ask ≥ bid` |
| `spread` | `== ask - bid`, ≥ 0, ≤ `max_plausible_spread[instrument]` else flag ILLIQUID input |
| `mid` | `== (bid+ask)/2` |
| `volume` | finite, ≥ 0 |
| `order_book_depth` | monotone price ladders; each `(px,vol)` finite, px>0, vol≥0 |
| `tick_velocity` | finite, ≥ 0 |
| `session` | ∈ enum; derived from the instrument's calendar (local-time windows) + `timestamp` |

No field may be `NaN`/`inf` — a NaN anywhere is a hard reject (F/NaN-leakage glitch class), never coerced to 0.

## 6. Algorithm & config set

- **Derived fields:** `spread = ask - bid`; `mid = (bid+ask)/2`. Computed with the instrument's `pip_size` awareness only for logging/threshold comparison, never rounded into the stored price.
- **`tick_velocity`:** count of ticks in the trailing `tick_velocity_window_s`, divided by the window; ring buffer per instrument. Cold start (fewer ticks than window): report the partial rate and set a `warming` flag in `raw`-adjacent metadata, do not fabricate.
- **Staleness:** `is_stale = (ingest_ts - timestamp) > stale_threshold_ms`. Stale does not reject; it flags. NVMA vetoes on it.
- **Session tagging (C1, generalised per C10):** map `timestamp` against the instrument's declared **market calendar** (`asset_classes.py`); for forex instruments the calendar is the C1 `session_boundaries` list + session windows, each window read in its own centre's local time (master §3.7 v2.14) (overlaps → `overlap`; outside all → `closed`); exchange calendars resolve open sessions, holidays, and half-days (a declared early close is the session end, not a feed outage — §13 glitch class). This is the *only* session logic in the system; ACIS-02/03 reference it.
- **`macro_events_imminent`:** true if any Tier-1 calendar event for the instrument's currencies falls within `macro_lookahead_min`. Calendar is injected data, not a prediction.
- **Config block (`system_config.yaml → data:`):** `stale_threshold_ms`, `clock_skew_tolerance_ms`, `tick_velocity_window_s`, `queue_max`, `queue_overflow_policy: drop_oldest`, `macro_lookahead_min`, `session_boundaries` (top-level), `max_plausible_spread` (per-instrument). All required; no correctness default.

## 7. Core logic (step by step)

1. `FeedConnector.stream()` yields a native payload → connector maps to `RawTick` (`recv_time = now()`).
2. **Duplicate detection:** if `(instrument, event_time, bid, ask)` matches the last accepted tick → drop, log `DUP_TICK`, do not emit (idempotent ingest; glitch class).
3. **Out-of-order detection:** if `event_time < last_event_time - reorder_tolerance` → do not rewrite history; emit the tick flagged `out_of_order=True` in `raw` metadata and log `OUT_OF_ORDER`; NVMA/monitor decide. Within tolerance, accept and update `last_event_time`.
4. **Validation:** apply §5 table. Any violation → raise `DataQualityError(field, value, reason)`; the connector logs `DATA_QUALITY_REJECT` and continues the stream (one bad tick never kills the loop).
5. **Derive** spread/mid/velocity/session/macro/staleness.
6. **Construct** the frozen `MarketState` (deep-immutable `raw`/`book`).
7. **Emit** to the fast loop (in-process) *and* enqueue for the async writer (§9). If the writer queue is full → apply `drop_oldest`, log `DATA_BACKPRESSURE{dropped, queue_max}`. The fast loop is never blocked by persistence.
8. **Reconnect:** on feed disconnect, connector enters backoff-reconnect; on resume it calls `snapshot()` to re-baseline and logs `FEED_RECONNECT`; the gap is logged, not interpolated (weekend-gap / reconnect glitch classes).

## 8. State machine & loop cadence

This layer feeds **Loop 3 FAST (tick–5s)** (master §10). Connector states: `DISCONNECTED → CONNECTING → STREAMING → (DEGRADED) → DISCONNECTED`. `DEGRADED` = staleness or reorder rate over threshold; it is reported to `monitoring/` but the layer keeps emitting flagged states (NVMA vetoes downstream). The factory itself is stateless per tick except the per-instrument ring buffers. The layer heartbeats to `acis://status` every ≤10 s (fast-loop SLA, master §12); a stalled feed with open positions is what ultimately triggers the Risk Monitor's flatten-and-halt (master §10) — but this layer only reports; it never halts.

## 9. Persistence & logging

- **JSONL (`logs/`, master §11):** every emitted `MarketState` → `data_log` (or sampled at high tick rates per `data.log_sample_rate`, with counts preserved so no silent loss); every reject/dup/reorder/backpressure/reconnect → `system_log` with the standard `{timestamp, event_type, layer:"data", data, session_id}` envelope. No `print`.
- **Async writer:** a dedicated task drains the bounded queue into the store. Slow DB ⇒ queue grows ⇒ `drop_oldest` + `DATA_BACKPRESSURE`; it must **never** apply backpressure up into the feed/fast loop. Decimal is used for any persisted price aggregates that later feed accounting (F17); raw tick prices persist as provided.

## 10. Store/DB schema (DDL)

Dev = SQLite, prod = TimescaleDB hypertable (master §3/§16). Logical schema (Timescale DDL shown; SQLite mirrors without `create_hypertable`):

```sql
CREATE TABLE market_state (
    ts            TIMESTAMPTZ   NOT NULL,   -- MarketState.timestamp (event time)
    ingest_ts     TIMESTAMPTZ   NOT NULL,
    instrument    TEXT          NOT NULL,
    bid           DOUBLE PRECISION NOT NULL,
    ask           DOUBLE PRECISION NOT NULL,
    spread        DOUBLE PRECISION NOT NULL,
    mid           DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION NOT NULL,
    tick_velocity DOUBLE PRECISION NOT NULL,
    session       TEXT          NOT NULL,
    macro_imminent BOOLEAN      NOT NULL,
    is_stale      BOOLEAN       NOT NULL,
    book          JSONB,                    -- order_book_depth snapshot
    raw           JSONB,                    -- original payload
    session_id    TEXT          NOT NULL,
    PRIMARY KEY (instrument, ts, ingest_ts)
);
SELECT create_hypertable('market_state', 'ts', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX ON market_state (instrument, ts DESC);
```
`(instrument, ts, ingest_ts)` PK makes duplicate writes idempotent (restart/replay safe). Retention/compression policy is an ops concern, config-driven, out of this spec.

## 11. Interface / MCP contract

This layer exposes **no MCP tools** (it controls nothing). It contributes read-only signals surfaced by `monitoring/` (ACIS-08): feed connection state + last-tick age per instrument on `acis://status`; `DATA_BACKPRESSURE`/`FEED_RECONNECT` counts on `acis://logs/tail/system`. It consumes no MCP input. The fast loop reads `MarketState` in-process from the data path (not via MCP).

## 12. Error taxonomy

| Error / event | Type | Handling |
|---|---|---|
| `DataQualityError(field,value,reason)` | raised | reject tick, log `DATA_QUALITY_REJECT`, continue stream |
| NaN/inf in any field | `DataQualityError` | hard reject (never coerce) |
| `FeedAuthError` | raised at boot | fatal — refuse to start |
| `FeedDisconnected` | handled | backoff-reconnect, `FEED_RECONNECT`, re-baseline via snapshot |
| duplicate tick | event | drop, `DUP_TICK` |
| out-of-order tick | event | emit flagged, `OUT_OF_ORDER` |
| queue overflow | event | `drop_oldest`, `DATA_BACKPRESSURE` |
| clock skew > tolerance | event | flag `MarketState`, `CLOCK_SKEW`, do not adjust time |

No error in this layer escapes upward to halt trading directly — it reports; NVMA/Governor/Risk react to flags. The one exception path is boot-time fatals (refuse to start).

## 13. Logic-flaw registry (corrections this layer owns)
- **C-DATA-1 (F16):** `raw` and `order_book_depth` stored as deep-immutable structures (`MappingProxyType` + nested tuples, or frozen model). The immutability test asserts a nested-mutation attempt fails — attribute-reassignment failing is not sufficient.
- **C-DATA-2 (F17):** any persisted aggregate that later feeds PnL/accounting uses `Decimal`; raw prices stay float; the float→Decimal boundary is explicit and tested (no float PnL accumulation).
- **C-DATA-3 (F6/C1):** session tagging resolves only against the declared calendars and `session_boundaries`; every time is local and resolved per date by `core/data/fx_clock.py`, so DST moves the UTC windows (tested on both sides of the US and UK switch dates and in the 2–3 week gap between them), and the Sunday-open/Friday-close edges are the 17:00 New York rollover.
- **C-DATA-4 (F18 hand-off):** session-median (spread, tick velocity) estimator lives here as `session_median_cache`; ACIS-02 consumes it. Cold-start (no median yet) is exposed as a warming flag, not a fabricated value.
- **C-DATA-5:** duplicate/out-of-order/reconnect/weekend-gap never cause silent history rewrite or interpolation; each has an explicit flag + log + test.
- **C-DATA-6 (master §7.5 / GAP-0013):** the feed face exposes no account, position, equity, or margin surface — the import-contract test asserts this structurally, not just import direction.
- **C-DATA-7 (master §3.7 / C10):** session tagging is per-instrument-calendar; incomplete contract metadata on an enabled instrument is boot-fatal; holiday half-day = session end, tested.

## 14. Test contract (postcondition-style; `[DIR:tests/unit]` + `[DIR:tests/integration]`)

**Unit:**
- valid payload from each of the 4 feeds → a `MarketState` with every field populated and validated (assert the object + a persisted row, not a return code).
- every field-validity rule (§5) has a violating input that raises `DataQualityError` and leaves no row written.
- NaN/inf in bid/ask/volume/velocity → reject; assert no emission.
- duplicate tick → exactly one accepted, `DUP_TICK` logged.
- out-of-order tick → emitted flagged, history not rewritten (assert store ordering).
- staleness flag flips exactly at `stale_threshold_ms`.
- session tagging correct across a DST boundary and at Sunday open / Friday close (seeded clock).
- deep-immutability: mutating `ms.raw[...]`/`ms.order_book_depth` raises.
- `tick_velocity` cold-start reports partial rate with warming flag, never fabricates.

**Integration:**
- mock feed at N ticks/s with a deliberately slow writer → fast loop keeps emitting; `DATA_BACKPRESSURE` emitted; drop count == expected; no fast-loop stall (assert timing).
- feed reconnect mid-stream → `FEED_RECONNECT`, re-baseline via snapshot, gap logged not interpolated.
- clock-skew injection → `CLOCK_SKEW` flag, timestamps unaltered.
- restart with the same replayed ticks → idempotent store (PK dedupe), byte-identical logical rows.

## 15. Integration gate

**What NVMA (ACIS-02) consumes:** a stream of validated `MarketState` plus the `session_median_cache` for spread/velocity. NVMA must be able to compute ATR/ADX/Hurst/Bollinger from the price series and read `session`, `is_stale`, `macro_events_imminent` directly.

**Done-when (phase 1, master §15):** all §14 tests green; the import-linter contract test exists and passes (no upward imports); mock feed drives an end-to-end tick without any lower layer present. **Conflict-table rows owned:** none directly, but this layer *supplies* the `is_stale`/`session`/`macro` inputs that NVMA turns into `tradeable=False` — so its correctness is a precondition for the "NVMA veto" and "regime shift" rows.

## Changelog
- **1.2 (2026-09-11)** — Master v2.14 (GAP-P12D-10): calendars and `session_boundaries` are declared in LOCAL time (`{zone, at}`; fx sessions `{zone, open, close}`; exchange calendars carry a `zone`) and resolved to UTC per date by `core/data/fx_clock.py`. C-DATA-3 restated; the boundary list moves out of the `data:` block wording (it was always top-level).
- **1.1 (LOCKED, 2026-07-15)** — v2.5 master consistency pass: asset-class law (contract metadata, per-calendar sessions, `asset_classes.py`), feed-face rule (adapters §7.5, no account surface — C-DATA-6), v1 feed set corrected to mock-first with OANDA/MT5 at phase-12 conformance. Status → LOCKED for the phase-1 build.
- **1.0 (DRAFT)** — Initial deep spec from master §3 + `ACIS_Agent_Prompt.md` §3.1; corrections C-DATA-1..5 wired from `SPEC_AUDIT.md`.
