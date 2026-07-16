"""End-to-end data-layer integration (ACIS-01 §14): mock feed -> factory ->
emit + persist, backpressure under a slow writer, idempotent restart replay,
and the SPEC §11 JSONL envelope."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.data.feeds import MockPaperFeed
from core.data.ingestion import IngestionPipeline
from core.data.jsonl_logging import JsonlEventLogger
from core.data.normaliser import MarketState, RawTick
from core.data.store import AsyncBoundedWriter, MarketStateStore

T0 = datetime(2026, 7, 14, 8, 0, 0, tzinfo=timezone.utc)  # Tuesday


def scripted_ticks(n: int) -> list[RawTick]:
    out = []
    for i in range(n):
        ts = T0 + timedelta(seconds=i)
        bid = 1.10 + i * 1e-5
        out.append(
            RawTick(
                event_time=ts,
                recv_time=ts + timedelta(milliseconds=5),
                instrument="EUR_USD",
                bid=round(bid, 6),
                ask=round(bid + 0.00012, 6),
                volume=5.0,
                book=None,
                provider="mock",
                raw_payload={"i": i},
            )
        )
    return out


def make_stack(tmp_path: Path, factory, feed, queue_max: int = 1000, sample_rate: int = 1):
    store = MarketStateStore(tmp_path / "acis.sqlite")
    logger = JsonlEventLogger(tmp_path / "system_log.jsonl", layer="data", session_id="itest")
    data_logger = JsonlEventLogger(tmp_path / "data_log.jsonl", layer="data", session_id="itest")
    writer = AsyncBoundedWriter(store, queue_max=queue_max, session_id="itest", logger=logger)
    seen: list[MarketState] = []
    pipeline = IngestionPipeline(
        feed, factory, writer, logger,
        subscribers=[seen.append], data_logger=data_logger, log_sample_rate=sample_rate,
    )
    return store, logger, writer, pipeline, seen


async def test_end_to_end_mock_feed_persists_and_emits(tmp_path: Path, factory) -> None:
    feed = MockPaperFeed({"EUR_USD": 1.10, "USD_JPY": 155.0}, n_ticks=30, start=T0)
    store, logger, writer, pipeline, seen = make_stack(tmp_path, factory, feed)
    drain = asyncio.create_task(writer.run())
    await pipeline.run()
    await writer.stop()
    await drain
    assert pipeline.emitted == 60  # 30 ticks x 2 instruments
    assert len(seen) == 60
    assert store.row_count() == 60  # observable outcome: rows, not exit codes
    assert {ms.instrument for ms in seen} == {"EUR_USD", "USD_JPY"}
    assert all(ms.session == "overlap" for ms in seen)
    # GAP-0024: every emitted MarketState reaches the §11 data_log stream.
    data_lines = (tmp_path / "data_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(l) for l in data_lines]
    assert len(records) == 60
    assert all(r["event_type"] == "MARKET_STATE" for r in records)
    assert max(r["data"]["seq"] for r in records) == 30  # per-instrument seq preserved
    logger.close()
    store.close()


async def test_data_log_sampling_preserves_seq(tmp_path: Path, factory) -> None:
    feed = MockPaperFeed({"EUR_USD": 1.10}, scripted=scripted_ticks(50))
    store, logger, writer, pipeline, _ = make_stack(tmp_path, factory, feed, sample_rate=10)
    drain = asyncio.create_task(writer.run())
    await pipeline.run()
    await writer.stop()
    await drain
    records = [json.loads(l) for l in
               (tmp_path / "data_log.jsonl").read_text(encoding="utf-8").strip().splitlines()]
    assert [r["data"]["seq"] for r in records] == [10, 20, 30, 40, 50]  # gaps prove sampling
    assert all(r["data"]["sample_rate"] == 10 for r in records)
    logger.close()
    store.close()


async def test_malformed_book_tick_never_kills_the_loop(tmp_path: Path, factory) -> None:
    # GAP-0027: one hostile/broken payload rejects and the stream continues.
    ticks = scripted_ticks(10)
    bad = RawTick(
        event_time=T0 + timedelta(seconds=20),
        recv_time=T0 + timedelta(seconds=20, milliseconds=5),
        instrument="EUR_USD",
        bid=1.10, ask=1.10012, volume=5.0,
        book={"bids": ((1.0999,),), "asks": ()},  # wrong arity — the repro
        provider="mock", raw_payload={},
    )
    feed = MockPaperFeed({"EUR_USD": 1.10}, scripted=[*ticks[:5], bad, *ticks[5:]])
    store, logger, writer, pipeline, seen = make_stack(tmp_path, factory, feed)
    drain = asyncio.create_task(writer.run())
    await pipeline.run()
    await writer.stop()
    await drain
    assert pipeline.rejected == 1
    assert pipeline.emitted == 10          # the loop survived and finished the stream
    assert store.row_count() == 10
    lines = (tmp_path / "system_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert any(json.loads(l)["event_type"] == "DATA_QUALITY_REJECT" for l in lines)
    logger.close()
    store.close()


async def test_slow_writer_backpressure_never_blocks_fast_loop(tmp_path: Path, factory) -> None:
    feed = MockPaperFeed({"EUR_USD": 1.10}, n_ticks=50, start=T0, scripted=scripted_ticks(50))
    store, logger, writer, pipeline, seen = make_stack(tmp_path, factory, feed, queue_max=5)
    # Writer NOT draining while the feed runs — the queue must overflow, not block.
    await pipeline.run()
    assert pipeline.emitted == 50          # fast loop never blocked
    assert writer.dropped == 45            # drop_oldest applied
    drain = asyncio.create_task(writer.run())
    await writer.stop()
    await drain
    assert store.row_count() == 5
    lines = (tmp_path / "system_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    backpressure = [json.loads(l) for l in lines if json.loads(l)["event_type"] == "DATA_BACKPRESSURE"]
    assert len(backpressure) == 45
    logger.close()
    store.close()


async def test_restart_replay_is_idempotent(tmp_path: Path, factory) -> None:
    ticks = scripted_ticks(20)
    store = MarketStateStore(tmp_path / "acis.sqlite")
    logger = JsonlEventLogger(tmp_path / "system_log.jsonl", layer="data", session_id="itest")
    for attempt in range(2):  # restart: same ticks, fresh pipeline, same store
        writer = AsyncBoundedWriter(store, queue_max=100, session_id="itest", logger=logger)
        feed = MockPaperFeed({"EUR_USD": 1.10}, scripted=ticks)
        pipeline = IngestionPipeline(feed, factory, writer, logger)
        drain = asyncio.create_task(writer.run())
        await pipeline.run()
        await writer.stop()
        await drain
    assert store.row_count() == 20  # PK dedupe: byte-identical logical rows, once
    logger.close()
    store.close()


async def test_jsonl_envelope_is_exact(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    logger = JsonlEventLogger(path, layer="data", session_id="s-1")
    logger.event("FEED_RECONNECT", instrument="EUR_USD", gap_s=12.5)
    logger.close()
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert set(record) == {"timestamp", "event_type", "layer", "data", "session_id"}
    assert record["event_type"] == "FEED_RECONNECT"
    assert record["layer"] == "data"
    assert record["session_id"] == "s-1"
    assert record["data"] == {"instrument": "EUR_USD", "gap_s": 12.5}
