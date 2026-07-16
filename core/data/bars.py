"""Tick -> OHLC bar aggregation — the DECLARED time base (SPEC §1, v2.11).

The v2.11 ruling is BARS: every signal-layer indicator period means "N bars of
`signal_bar_seconds`", never "N ticks". This module is the single place ticks
become bars: uniform signal bars plus rollover-anchored daily bars (TSMOM).
A bar completes when a tick arrives in a later bucket; ticks belonging to an
already-completed bucket are dropped and counted (upstream ordering flags own
the reordering policy — a closed bar is immutable history).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.data.errors import DataQualityError


@dataclass(frozen=True)
class Bar:
    ts_open: datetime      # bucket start, tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    spread: float          # spread at the closing tick
    duration_s: int

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close"):
            v = getattr(self, name)
            if not math.isfinite(v) or v <= 0:
                raise DataQualityError(name, v, "must be finite > 0")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise DataQualityError("high/low", (self.high, self.low), "OHLC shape violated")
        if not math.isfinite(self.spread) or self.spread < 0:
            raise DataQualityError("spread", self.spread, "must be finite >= 0")
        if self.ts_open.tzinfo is None:
            raise DataQualityError("ts_open", self.ts_open, "must be tz-aware")
        if self.duration_s <= 0:
            raise DataQualityError("duration_s", self.duration_s, "must be > 0")


class BarAggregator:
    """One instrument, one duration. `add()` returns the COMPLETED bar (or None)
    when the incoming tick opens a later bucket. `anchor_utc` fixes the bucket
    grid's phase — "22:00" gives rollover-anchored daily bars (master §5 C1)."""

    def __init__(self, duration_s: int, anchor_utc: str = "00:00") -> None:
        if duration_s <= 0:
            raise DataQualityError("duration_s", duration_s, "must be > 0")
        hh, mm = map(int, anchor_utc.split(":"))
        self._duration = duration_s
        self._anchor = datetime(1970, 1, 5, hh, mm, tzinfo=timezone.utc)  # a Monday
        self._bucket: int | None = None
        self._o = self._h = self._l = self._c = 0.0
        self._spread = 0.0
        self.stale_ticks_dropped = 0

    def _bucket_of(self, ts: datetime) -> int:
        return int((ts.astimezone(timezone.utc) - self._anchor).total_seconds()
                   // self._duration)

    def add(self, ts: datetime, mid: float, spread: float) -> Bar | None:
        if ts.tzinfo is None:
            raise DataQualityError("ts", ts, "must be tz-aware")
        if not math.isfinite(mid) or mid <= 0:
            raise DataQualityError("mid", mid, "must be finite > 0")
        bucket = self._bucket_of(ts)
        if self._bucket is None:
            self._open_bucket(bucket, mid, spread)
            return None
        if bucket < self._bucket:
            self.stale_ticks_dropped += 1   # closed bars are immutable history
            return None
        if bucket == self._bucket:
            self._h = max(self._h, mid)
            self._l = min(self._l, mid)
            self._c = mid
            self._spread = spread
            return None
        completed = Bar(
            ts_open=self._anchor + timedelta(seconds=self._bucket * self._duration),
            open=self._o, high=self._h, low=self._l, close=self._c,
            spread=self._spread, duration_s=self._duration,
        )
        self._open_bucket(bucket, mid, spread)
        return completed

    def _open_bucket(self, bucket: int, mid: float, spread: float) -> None:
        self._bucket = bucket
        self._o = self._h = self._l = self._c = mid
        self._spread = spread
