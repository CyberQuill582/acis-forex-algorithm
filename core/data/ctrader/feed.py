"""CTraderFeed — the cTrader feed face (ACIS-01 §3, ACIS-13 §4.1, §7.6): spot events → RawTick.

Invariants:
  * It reads ONLY the session's spot queue; execution, order, trader and account events never reach
    it, and it exposes no account surface (GAP-0013).
  * A tick carries the VENUE's timestamp (`subscribeToSpotTimestamp = true`, F-23). A spot without
    one is dropped and logged, never given a fabricated time (C-VEN-16).
  * Either side of a spot may be absent (F-23). The face keeps the last known bid and ask and emits
    only once both are known; `raw_payload.sides_updated` says which side this event moved, so a
    carried-forward side is visible, never silent.
  * The first event after each (re)subscription is the venue's snapshot, possibly an old closing
    print (F-23); it is flagged `snapshot = True` and keeps its real, old time, so ACIS-01's
    staleness flag makes it untradeable. An unknown `symbolId` is dropped and logged, never guessed.
  * Spot events carry no volume, so `volume` is 0.0 (RawTick requires the field); the venue profile
    declares `quote_volume = False` (§5.2). The face never reorders: venue order, venue times.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Mapping

from core.data.ctrader.schema import PRICE_SCALE, PT
from core.data.ctrader.wire import Frame
from core.data.errors import DataQualityError
from core.data.feeds import FeedConnector
from core.data.normaliser import RawTick


class CTraderFeed(FeedConnector):
    name = "ctrader"

    def __init__(self, session, symbols: Mapping[int, tuple[str, int]], logger, *,
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        """`symbols`: venue symbolId → (engine instrument, digits), from the attach (§5.1)."""
        self._session = session
        self._symbols = dict(symbols)
        self._log = logger
        self._now = now_fn
        self._sides: dict[int, dict[str, float]] = {}
        self._fresh: set[int] = set()
        self._last: dict[str, RawTick] = {}

    async def subscribe(self, *, reconnect: bool = False) -> None:
        await self._session.request(PT.SUBSCRIBE_SPOTS_REQ,
                                    {"symbolId": sorted(self._symbols),
                                     "subscribeToSpotTimestamp": True}, req_class="subscribe")
        self._fresh = set(self._symbols)
        if reconnect:
            self._log.event("FEED_RECONNECT", symbols=len(self._symbols))

    async def stream(self) -> AsyncIterator[RawTick]:
        await self.subscribe()
        while True:
            frame = await self._session.spots.get()
            try:
                tick = self.to_tick(frame, self._now())
            except DataQualityError as exc:
                self._log.event("FEED_BAD_TICK", reason=str(exc))
                continue
            if tick is not None:
                self._last[tick.instrument] = tick
                yield tick

    async def snapshot(self, instrument: str) -> RawTick:
        if instrument not in self._last:
            raise DataQualityError("instrument", instrument, "no venue quote received yet")
        return self._last[instrument]

    def to_tick(self, frame: Frame, recv_time: datetime) -> RawTick | None:
        """One spot event as a RawTick, or None while a side is still unknown."""
        p = frame.payload
        symbol_id = int(p["symbolId"])
        if symbol_id not in self._symbols:
            self._log.event("FEED_UNKNOWN_SYMBOL", symbol_id=symbol_id)
            return None
        if p.get("timestamp") is None:
            raise DataQualityError("timestamp", None, "a spot without the venue's time (C-VEN-16)")
        instrument, digits = self._symbols[symbol_id]
        known = self._sides.setdefault(symbol_id, {})
        moved = [side for side in ("bid", "ask") if p.get(side) is not None]
        for side in moved:
            price = round(int(p[side]) / PRICE_SCALE, digits)
            if price <= 0:
                raise DataQualityError(side, p[side], "a non-positive venue price")
            known[side] = price
        snapshot = symbol_id in self._fresh
        self._fresh.discard(symbol_id)
        if len(known) < 2:
            return None
        return RawTick(
            event_time=datetime.fromtimestamp(int(p["timestamp"]) / 1000, tz=timezone.utc),
            recv_time=recv_time, instrument=instrument, bid=known["bid"], ask=known["ask"],
            volume=0.0, book=None, provider="ctrader",
            raw_payload={"symbol_id": symbol_id, "snapshot": snapshot,
                         "sides_updated": "both" if len(moved) == 2 else (moved[0] if moved else "none")})
