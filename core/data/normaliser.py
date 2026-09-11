"""MarketStateFactory — RawTick -> validated, frozen, deep-immutable MarketState.

ACIS-01 §4–§7. Every quality problem in raw data is caught here or nowhere.
No repair-by-guessing: validate, derive, flag, or reject (DataQualityError).
"""

from __future__ import annotations

import bisect
import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Callable, Mapping

from core.data.asset_classes import MarketCalendar
from core.data.errors import DataQualityError

SESSIONS = frozenset(
    {"sydney", "tokyo", "london", "new_york", "overlap", "closed", "exchange"}
)


def deep_freeze(obj: object) -> object:
    """Recursively convert dict/list into MappingProxyType/tuples (F16)."""
    if isinstance(obj, Mapping):
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(deep_freeze(v) for v in obj)
    return obj


def thaw(obj: object) -> object:
    """Inverse of deep_freeze, for JSON persistence."""
    if isinstance(obj, Mapping):
        return {k: thaw(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [thaw(v) for v in obj]
    return obj


@dataclass(frozen=True)
class RawTick:
    """Feed-agnostic normalised input (each connector maps its payload to this)."""

    event_time: datetime
    recv_time: datetime
    instrument: str
    bid: float
    ask: float
    volume: float
    book: Mapping | None
    provider: str
    raw_payload: Mapping


@dataclass(frozen=True)
class MarketState:
    timestamp: datetime
    instrument: str
    bid: float
    ask: float
    spread: float
    mid: float
    volume: float
    order_book_depth: Mapping[str, tuple[tuple[float, float], ...]]
    tick_velocity: float
    session: str
    macro_events_imminent: bool
    ingest_ts: datetime
    is_stale: bool
    raw: Mapping

    def __post_init__(self) -> None:  # validate on construction (SPEC §3)
        for name in ("timestamp", "ingest_ts"):
            ts = getattr(self, name)
            if not isinstance(ts, datetime) or ts.tzinfo is None:
                raise DataQualityError(name, ts, "must be tz-aware datetime")
        for name in ("bid", "ask", "spread", "mid", "volume", "tick_velocity"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                raise DataQualityError(name, v, "must be finite (NaN/inf hard-rejected)")
        if self.bid <= 0 or self.ask <= 0:
            raise DataQualityError("bid/ask", (self.bid, self.ask), "must be > 0")
        if self.ask < self.bid:
            raise DataQualityError("ask", self.ask, f"ask < bid ({self.bid})")
        if abs(self.spread - (self.ask - self.bid)) > 1e-12:
            raise DataQualityError("spread", self.spread, "spread != ask - bid")
        if abs(self.mid - (self.bid + self.ask) / 2.0) > 1e-12:
            raise DataQualityError("mid", self.mid, "mid != (bid+ask)/2")
        if self.volume < 0 or self.tick_velocity < 0:
            raise DataQualityError("volume/velocity", (self.volume, self.tick_velocity), "must be >= 0")
        if self.session not in SESSIONS:
            raise DataQualityError("session", self.session, f"not in {sorted(SESSIONS)}")
        if not isinstance(self.raw, MappingProxyType):
            raise DataQualityError("raw", type(self.raw), "must be deep-immutable Mapping (F16)")
        if not isinstance(self.order_book_depth, MappingProxyType):
            raise DataQualityError("order_book_depth", type(self.order_book_depth), "must be immutable (F16)")
        for side, ladder in self.order_book_depth.items():
            if side not in ("bids", "asks"):
                raise DataQualityError("order_book_depth", side, "sides are 'bids'/'asks'")
            if not isinstance(ladder, tuple):
                raise DataQualityError("order_book_depth", ladder, "ladder must be a tuple")
            prices = []
            for level in ladder:
                # GAP-0027: malformed shapes must reject as DataQualityError,
                # never escape as ValueError/TypeError and kill the loop.
                if (
                    not isinstance(level, tuple)
                    or len(level) != 2
                    or not all(isinstance(x, (int, float)) for x in level)
                ):
                    raise DataQualityError("order_book_depth", level, "level must be (price, volume)")
                px, vol = level
                if not (math.isfinite(px) and math.isfinite(vol)) or px <= 0 or vol < 0:
                    raise DataQualityError("order_book_depth", level, "invalid level")
                prices.append(px)
            ordered = sorted(prices, reverse=(side == "bids"))
            if prices != ordered:
                raise DataQualityError("order_book_depth", side, "ladder not monotone")


@dataclass
class FeedContext:
    """Per-instrument rolling state (velocity ring, dedupe, session medians)."""

    velocity_ring: list = field(default_factory=list)  # kept sorted (GAP-0022)
    last_event_time: datetime | None = None
    last_accepted_key: tuple | None = None
    spread_by_session: dict[str, deque] = field(default_factory=dict)
    velocity_by_session: dict[str, deque] = field(default_factory=dict)


@dataclass(frozen=True)
class FactoryConfig:
    stale_threshold_ms: int
    clock_skew_tolerance_ms: int
    reorder_tolerance_ms: int
    tick_velocity_window_s: float
    session_median_window: int
    session_median_min_samples: int


@dataclass(frozen=True)
class BuildResult:
    state: MarketState | None  # None => dropped (duplicate)
    events: tuple[tuple[str, dict], ...]  # (event_type, data) for the pipeline to log


class MarketStateFactory:
    """Pure per-tick construction plus the small rolling state ACIS-01 §3 allows."""

    def __init__(
        self,
        cfg: FactoryConfig,
        calendars_by_instrument: Mapping[str, MarketCalendar],
        max_plausible_spread: Mapping[str, float],
        macro_imminent: Callable[[str, datetime], bool],
    ) -> None:
        self._cfg = cfg
        self._calendars = dict(calendars_by_instrument)
        self._max_spread = dict(max_plausible_spread)
        self._macro = macro_imminent
        self._ctx: dict[str, FeedContext] = {}

    def context(self, instrument: str) -> FeedContext:
        if instrument not in self._ctx:
            self._ctx[instrument] = FeedContext()
        return self._ctx[instrument]

    def session_median(self, instrument: str, session: str, kind: str) -> float | None:
        """C-DATA-4 (F18 hand-off): None while warming — never a fabricated value."""
        ctx = self.context(instrument)
        store = ctx.spread_by_session if kind == "spread" else ctx.velocity_by_session
        samples = store.get(session)
        if samples is None or len(samples) < self._cfg.session_median_min_samples:
            return None
        return statistics.median(samples)

    def build(self, raw: RawTick) -> BuildResult:
        events: list[tuple[str, dict]] = []
        cfg = self._cfg

        if raw.instrument not in self._calendars:
            raise DataQualityError("instrument", raw.instrument, "not in enabled universe")
        for name, ts in (("event_time", raw.event_time), ("recv_time", raw.recv_time)):
            if not isinstance(ts, datetime) or ts.tzinfo is None:
                raise DataQualityError(name, ts, "must be tz-aware datetime")
        event_time = raw.event_time.astimezone(timezone.utc)
        recv_time = raw.recv_time.astimezone(timezone.utc)

        skew = timedelta(milliseconds=cfg.clock_skew_tolerance_ms)
        if event_time > recv_time + skew:
            raise DataQualityError(
                "timestamp", event_time.isoformat(), "in the future beyond clock_skew_tolerance_ms"
            )

        ctx = self.context(raw.instrument)

        # Duplicate detection (idempotent ingest): drop, log, do not emit.
        key = (event_time, raw.bid, raw.ask)
        if ctx.last_accepted_key == key:
            events.append(("DUP_TICK", {"instrument": raw.instrument, "ts": event_time.isoformat()}))
            return BuildResult(None, tuple(events))

        # Out-of-order: never rewrite history — emit flagged.
        meta: dict[str, object] = {}
        reorder = timedelta(milliseconds=cfg.reorder_tolerance_ms)
        if ctx.last_event_time is not None and event_time < ctx.last_event_time - reorder:
            meta["out_of_order"] = True
            events.append(("OUT_OF_ORDER", {"instrument": raw.instrument, "ts": event_time.isoformat()}))

        # Clock skew (lag direction): flag, never adjust the timestamp.
        if (recv_time - event_time) > skew:
            meta["clock_skew"] = True
            events.append(("CLOCK_SKEW", {
                "instrument": raw.instrument,
                "lag_ms": (recv_time - event_time) / timedelta(milliseconds=1),
            }))

        # Derived fields.
        spread = raw.ask - raw.bid
        mid = (raw.bid + raw.ask) / 2.0
        max_spread = self._max_spread.get(raw.instrument)
        if max_spread is not None and spread > max_spread:
            meta["implausible_spread"] = True  # flagged ILLIQUID input; NVMA vetoes

        # Tick velocity over the trailing window (partial rate while warming).
        # GAP-0022: sorted insert + latest-anchor pruning keeps the window
        # correct when out-of-order ticks arrive (front-only pruning on an
        # unsorted ring overcounts and can flip the NVMA dead-market veto).
        window = timedelta(seconds=cfg.tick_velocity_window_s)
        ring = ctx.velocity_ring
        bisect.insort(ring, event_time)
        anchor = ring[-1]
        cutoff = anchor - window
        while ring and ring[0] < cutoff:
            ring.pop(0)
        tick_velocity = len(ring) / cfg.tick_velocity_window_s
        if len(ring) < 2 or (anchor - ring[0]) < window:
            meta["velocity_warming"] = True

        session = self._calendars[raw.instrument].session_at(event_time)
        is_stale = (recv_time - event_time) > timedelta(milliseconds=cfg.stale_threshold_ms)
        macro = bool(self._macro(raw.instrument, event_time))

        book = raw.book if raw.book is not None else {"bids": (), "asks": ()}
        state = MarketState(
            timestamp=event_time,
            instrument=raw.instrument,
            bid=float(raw.bid),
            ask=float(raw.ask),
            spread=float(spread),
            mid=float(mid),
            volume=float(raw.volume),
            order_book_depth=deep_freeze(book),  # type: ignore[arg-type]
            tick_velocity=tick_velocity,
            session=session,
            macro_events_imminent=macro,
            ingest_ts=recv_time,
            is_stale=is_stale,
            raw=deep_freeze({**dict(raw.raw_payload), "_acis_meta": meta}),  # type: ignore[arg-type]
        )

        # Accept: update rolling state only after successful construction.
        ctx.last_accepted_key = key
        if ctx.last_event_time is None or event_time > ctx.last_event_time:
            ctx.last_event_time = event_time
        maxlen = cfg.session_median_window
        ctx.spread_by_session.setdefault(session, deque(maxlen=maxlen)).append(spread)
        ctx.velocity_by_session.setdefault(session, deque(maxlen=maxlen)).append(tick_velocity)
        return BuildResult(state, tuple(events))
