"""Dukascopy 1-minute candles (IMOM and REBAL-live's timing look, GAP-P12D-158/157; master §13 primary source).

A day's file `SYMBOL/YYYY/MM/DD/{BID,ASK}_candles_min_1.bi5` (MM zero-based, DD one-based) is a raw LZMA
stream of the hourly file's 24-byte big-endian records, one per minute of the UTC day:
    uint32 seconds from the day's start · uint32 open · uint32 close · uint32 low · uint32 high · float32 volume
The checks are the hourly decoder's (`candles.py`): 1,440 minutes, in order; OPEN and CLOSE inside the
instrument's plausible envelope; low <= open, close <= high. A failing file raises, never yields a
partial day. Decoding is vectorised (numpy), since a decade of days is ~60,000 files.
"""

from __future__ import annotations

import lzma
from datetime import date, datetime, timezone

import numpy as np

from tests.backtest.candles import CandleError
from tests.backtest.universe import BY_NAME

MINUTES = 1440
RAW = np.dtype([("sec", ">u4"), ("open", ">u4"), ("close", ">u4"), ("low", ">u4"), ("high", ">u4"), ("volume", ">f4")])
DAY = np.dtype([("ts", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8"), ("volume", "f8")])


def decode_day(raw: bytes, instrument: str, day: date) -> np.ndarray:
    """The day's 1,440 minutes as a structured array (`DAY`: ts = each minute's start, epoch s) or a CandleError."""
    inst = BY_NAME[instrument]
    where = f"{instrument} {day}"
    try:
        data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as e:
        raise CandleError(f"{where}: bad LZMA stream: {e}") from e
    if len(data) != MINUTES * RAW.itemsize:
        raise CandleError(f"{where}: {len(data)} bytes, the day's {MINUTES} minutes need {MINUTES * RAW.itemsize}")
    r = np.frombuffer(data, RAW)
    if not np.array_equal(r["sec"], np.arange(MINUTES, dtype=np.uint32) * 60):
        raise CandleError(f"{where}: the minutes are not whole and in order")
    out = np.empty(MINUTES, DAY)
    out["ts"] = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()) + r["sec"].astype("i8")
    for f in ("open", "high", "low", "close"):
        out[f] = r[f] / inst.scale
    out["volume"] = r["volume"]
    lo, hi = inst.plausible
    bad = ~((lo <= out["open"]) & (out["open"] <= hi) & (lo <= out["close"]) & (out["close"] <= hi))
    if bad.any():
        k = int(np.argmax(bad))
        raise CandleError(f"{where} minute {k}: open {out['open'][k]} / close {out['close'][k]} outside {inst.plausible}")
    order = (out["low"] <= np.minimum(out["open"], out["close"])) & (np.maximum(out["open"], out["close"]) <= out["high"])
    if not order.all():
        raise CandleError(f"{where} minute {int(np.argmax(~order))}: OHLC out of order")
    return out
