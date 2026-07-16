"""Bar aggregation — the v2.11 declared time base (core/data/bars.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.data.bars import Bar, BarAggregator
from core.data.errors import DataQualityError

T0 = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)


def test_ohlc_from_multiple_ticks_in_one_bucket() -> None:
    agg = BarAggregator(60)
    assert agg.add(T0, 1.10, 0.0002) is None
    assert agg.add(T0 + timedelta(seconds=20), 1.12, 0.0002) is None
    assert agg.add(T0 + timedelta(seconds=40), 1.09, 0.0002) is None
    assert agg.add(T0 + timedelta(seconds=59), 1.11, 0.0003) is None
    bar = agg.add(T0 + timedelta(seconds=60), 1.115, 0.0002)   # next bucket opens
    assert bar is not None
    assert (bar.open, bar.high, bar.low, bar.close) == (1.10, 1.12, 1.09, 1.11)
    assert bar.spread == 0.0003 and bar.duration_s == 60
    assert bar.ts_open == T0


def test_gap_across_empty_buckets_completes_one_bar() -> None:
    agg = BarAggregator(60)
    agg.add(T0, 1.10, 0.0002)
    bar = agg.add(T0 + timedelta(seconds=600), 1.11, 0.0002)  # 9 empty buckets later
    assert bar is not None and bar.close == 1.10             # no phantom bars


def test_stale_tick_into_closed_bucket_is_dropped_and_counted() -> None:
    agg = BarAggregator(60)
    agg.add(T0, 1.10, 0.0002)
    agg.add(T0 + timedelta(seconds=60), 1.11, 0.0002)
    assert agg.add(T0 - timedelta(seconds=120), 1.05, 0.0002) is None
    assert agg.stale_ticks_dropped == 1


def test_daily_bars_anchor_at_rollover() -> None:
    agg = BarAggregator(86_400, anchor_utc="22:00")
    agg.add(datetime(2026, 7, 6, 23, 0, tzinfo=timezone.utc), 1.10, 0.0002)
    bar = agg.add(datetime(2026, 7, 7, 22, 1, tzinfo=timezone.utc), 1.12, 0.0002)
    assert bar is not None
    assert bar.ts_open == datetime(2026, 7, 6, 22, 0, tzinfo=timezone.utc)  # 22:00 UTC


def test_bar_shape_and_input_validation() -> None:
    with pytest.raises(DataQualityError):
        Bar(ts_open=T0, open=1.1, high=1.0, low=1.0, close=1.1, spread=0.0,
            duration_s=60)
    agg = BarAggregator(60)
    with pytest.raises(DataQualityError):
        agg.add(datetime(2026, 7, 6, 10, 0), 1.1, 0.0002)   # naive ts
    with pytest.raises(DataQualityError):
        agg.add(T0, float("nan"), 0.0002)
