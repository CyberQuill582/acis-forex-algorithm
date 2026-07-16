"""Ingestion pipeline: FeedConnector -> MarketStateFactory -> emit + persist.

One bad tick never kills the loop (DATA_QUALITY_REJECT + continue); persistence
is enqueue-only (never blocks); every event is structured JSONL (SPEC §11).
"""

from __future__ import annotations

from typing import Callable

from core.data.errors import DataQualityError
from core.data.feeds import FeedConnector
from core.data.jsonl_logging import JsonlEventLogger
from core.data.normaliser import MarketState, MarketStateFactory
from core.data.store import AsyncBoundedWriter

Subscriber = Callable[[MarketState], None]


class IngestionPipeline:
    def __init__(
        self,
        feed: FeedConnector,
        factory: MarketStateFactory,
        writer: AsyncBoundedWriter,
        logger: JsonlEventLogger,
        subscribers: list[Subscriber] | None = None,
        data_logger: JsonlEventLogger | None = None,
        log_sample_rate: int = 1,
    ) -> None:
        self._feed = feed
        self._factory = factory
        self._writer = writer
        self._log = logger
        self._subscribers = subscribers or []
        # GAP-0024: SPEC §11 data_log stream — every emitted MarketState, or
        # sampled per data.log_sample_rate with per-instrument seq preserved
        # (a seq gap proves sampling; nothing is silently lost).
        self._data_log = data_logger
        self._sample = log_sample_rate
        self._seq: dict[str, int] = {}
        self.emitted = 0
        self.rejected = 0

    def _log_market_state(self, ms: MarketState) -> None:
        seq = self._seq.get(ms.instrument, 0) + 1
        self._seq[ms.instrument] = seq
        if self._data_log is None or seq % self._sample != 0:
            return
        self._data_log.event(
            "MARKET_STATE",
            instrument=ms.instrument,
            seq=seq,
            sample_rate=self._sample,
            event_time=ms.timestamp.isoformat(),  # microsecond precision
            bid=ms.bid,
            ask=ms.ask,
            spread=ms.spread,
            mid=ms.mid,
            volume=ms.volume,
            tick_velocity=ms.tick_velocity,
            session=ms.session,
            macro_events_imminent=ms.macro_events_imminent,
            is_stale=ms.is_stale,
        )

    async def run(self) -> None:
        async for raw in self._feed.stream():
            try:
                result = self._factory.build(raw)
            except DataQualityError as exc:
                self.rejected += 1
                self._log.event(
                    "DATA_QUALITY_REJECT",
                    instrument=raw.instrument,
                    field=exc.field,
                    reason=exc.reason,
                )
                continue
            for event_type, data in result.events:
                self._log.event(event_type, **data)
            if result.state is None:
                continue  # duplicate — dropped and logged above
            self.emitted += 1
            self._log_market_state(result.state)
            for sub in self._subscribers:
                sub(result.state)
            self._writer.enqueue(result.state)
