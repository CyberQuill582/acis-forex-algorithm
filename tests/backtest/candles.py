"""Dukascopy hourly candles (R1.5; master §13 primary source; the archive's `*_candles_hour_1.bi5`).

A month's file `SYMBOL/YYYY/MM/{BID,ASK}_candles_hour_1.bi5` (MM zero-based) is a raw LZMA stream
of 24-byte big-endian records, verified against the archive 2026-10-01:
    uint32 seconds from the month's start (UTC) · uint32 open · uint32 close · uint32 low ·
    uint32 high · float32 volume
one per hour of the month, weekend hours included (flat, volume 0). Prices are integers ÷ the
instrument's scale (`universe.py`); a wrong scale is silent, so every price is bounded by the
instrument's plausible envelope, every hour must be present and in order, and low <= open,
close <= high. A file that fails any check raises, never yields a partial month.
"""

from __future__ import annotations

import calendar
import lzma
import struct
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from tests.backtest.universe import BY_NAME

UTC = timezone.utc
RECORD = struct.Struct(">IIIIIf")


class Candle(NamedTuple):
    ts: datetime         # the hour's start, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleError(ValueError):
    """A candle file that cannot be trusted."""


def decode_month(raw: bytes, instrument: str, year: int, month: int) -> list[Candle]:
    """Every hour of the month (`month` is 1-based here) or a CandleError."""
    inst = BY_NAME[instrument]
    where = f"{instrument} {year}-{month:02d}"
    try:
        data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as e:
        raise CandleError(f"{where}: bad LZMA stream: {e}") from e
    if len(data) % RECORD.size:
        raise CandleError(f"{where}: {len(data)} bytes is not a whole number of {RECORD.size}-byte records")
    hours = calendar.monthrange(year, month)[1] * 24
    rows = list(RECORD.iter_unpack(data))
    if len(rows) != hours:
        raise CandleError(f"{where}: {len(rows)} hourly candles, the month has {hours}")
    start, lo, hi = datetime(year, month, 1, tzinfo=UTC), *inst.plausible
    out = []
    for k, (sec, o, c, l, h, v) in enumerate(rows):
        if sec != k * 3600:
            raise CandleError(f"{where}: candle {k} starts at second {sec}, not {k * 3600}")
        o, c, l, h = (x / inst.scale for x in (o, c, l, h))
        if not (l <= min(o, c) and max(o, c) <= h):
            raise CandleError(f"{where} hour {k}: OHLC out of order {o} {h} {l} {c}")
        if not (lo <= l and h <= hi):
            raise CandleError(f"{where} hour {k}: {l}..{h} outside {lo}..{hi}: wrong point scale?")
        out.append(Candle(start + timedelta(seconds=sec), o, h, l, c, v))
    return out
