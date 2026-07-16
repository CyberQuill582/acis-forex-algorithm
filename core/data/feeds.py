"""Feed connectors — the FEED FACES of the SPEC §7.5 platform adapters.

Phase-1 gate (ACIS-01 §1): the mock paper feed. OANDA v20 / MT5 feed faces
join at phase 12 behind this same interface. A feed face exposes NO account,
position, equity, or margin surface (C-DATA-6 / GAP-0013) — quotes only.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Mapping, Sequence

from core.data.normaliser import RawTick


class FeedConnector(ABC):
    """Identical async interface for every feed face (ACIS-01 §3)."""

    name: str

    @abstractmethod
    def stream(self) -> AsyncIterator[RawTick]:
        """Yield normalised RawTicks until the feed ends or disconnects."""

    @abstractmethod
    async def snapshot(self, instrument: str) -> RawTick:
        """Current quote for one instrument (used to re-baseline on reconnect)."""


class MockPaperFeed(FeedConnector):
    """Deterministic seeded random-walk feed, or a scripted tick sequence."""

    name = "mock"

    def __init__(
        self,
        instruments: Mapping[str, float],  # symbol -> starting mid price
        *,
        seed: int = 7,
        n_ticks: int = 100,
        start: datetime | None = None,
        tick_interval_s: float = 1.0,
        spread: float = 0.0002,
        recv_latency_ms: float = 5.0,
        scripted: Sequence[RawTick] | None = None,
    ) -> None:
        self._instruments = dict(instruments)
        self._rng = random.Random(seed)
        self._n_ticks = n_ticks
        self._start = start or datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
        self._interval = tick_interval_s
        self._spread = spread
        self._latency = timedelta(milliseconds=recv_latency_ms)
        self._scripted = list(scripted) if scripted is not None else None
        self._last: dict[str, RawTick] = {}

    def _make_tick(self, instrument: str, mid: float, ts: datetime) -> RawTick:
        bid = mid - self._spread / 2.0
        ask = mid + self._spread / 2.0
        tick = RawTick(
            event_time=ts,
            recv_time=ts + self._latency,
            instrument=instrument,
            bid=round(bid, 6),
            ask=round(ask, 6),
            volume=float(self._rng.randint(1, 50)),
            book={"bids": ((round(bid, 6), 100.0),), "asks": ((round(ask, 6), 100.0),)},
            provider=self.name,
            raw_payload={"provider": self.name, "mid": mid},
        )
        self._last[instrument] = tick
        return tick

    async def stream(self) -> AsyncIterator[RawTick]:
        if self._scripted is not None:
            for tick in self._scripted:
                self._last[tick.instrument] = tick
                yield tick
            return
        prices = dict(self._instruments)
        ts = self._start
        for _ in range(self._n_ticks):
            for instrument in prices:
                prices[instrument] *= 1.0 + self._rng.gauss(0.0, 0.0001)
                yield self._make_tick(instrument, prices[instrument], ts)
            ts += timedelta(seconds=self._interval)

    async def snapshot(self, instrument: str) -> RawTick:
        if instrument in self._last:
            return self._last[instrument]
        return self._make_tick(
            instrument,
            self._instruments[instrument],
            datetime.now(timezone.utc),
        )
