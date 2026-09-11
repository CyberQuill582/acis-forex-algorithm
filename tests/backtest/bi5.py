"""Dukascopy `.bi5` tick decoding (master §13 primary source; Dukascopy data-export docs).

A `.bi5` file is a raw LZMA stream of 20-byte big-endian records:
    uint32 ms offset · uint32 ask · uint32 bid · float32 ask volume · float32 bid volume
The ms offset counts from the start of the file's period: the start of the UTC DAY for
the official S3 archive (`SYMBOL/YYYY/MM/DD_ticks.bi5`, month zero-based), the start of
the UTC HOUR for the public feed (`…/HHh_ticks.bi5`). Prices are integers ÷ the
instrument's point scale — 100 000 for most FX, 1 000 for JPY pairs — and Dukascopy
warns that a wrong scale produces wrong prices SILENTLY, so `PLAUSIBLE` bounds every
decoded price. Volumes are in millions of base units. An empty file means no ticks.
"""

from __future__ import annotations

import lzma
import struct
from datetime import datetime, timedelta, timezone
from typing import Iterator, NamedTuple

UTC = timezone.utc
RECORD = struct.Struct(">IIIff")

# ACIS instrument -> (Dukascopy symbol, price scale). XAU's scale is verified against
# HistData prices before the first bulk download (TODO.md, S3 first test).
SYMBOLS = {
    "EUR_USD": ("EURUSD", 100_000), "GBP_USD": ("GBPUSD", 100_000),
    "AUD_USD": ("AUDUSD", 100_000), "USD_CHF": ("USDCHF", 100_000),
    "USD_CAD": ("USDCAD", 100_000), "EUR_GBP": ("EURGBP", 100_000),
    "USD_JPY": ("USDJPY", 1_000),   "XAU_USD": ("XAUUSD", 1_000),
}
# Wide sanity envelopes for 2012–2025: a wrong scale is off by 10×–100×, never inside.
PLAUSIBLE = {
    "EUR_USD": (0.8, 1.7), "GBP_USD": (1.0, 2.2), "AUD_USD": (0.5, 1.2),
    "USD_CHF": (0.6, 1.3), "USD_CAD": (0.9, 1.6), "EUR_GBP": (0.6, 1.0),
    "USD_JPY": (70.0, 170.0), "XAU_USD": (1000.0, 5000.0),
}


class Tick(NamedTuple):
    ts: datetime
    ask: float
    bid: float
    ask_volume: float
    bid_volume: float


class Bi5Error(ValueError):
    """A .bi5 file that cannot be trusted: bad LZMA, torn record, or implausible price."""


def decode(raw: bytes, instrument: str, period_start: datetime) -> Iterator[Tick]:
    """Decode one `.bi5` file whose ms offsets count from `period_start` (UTC)."""
    if not raw:
        return
    try:
        data = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError as e:
        raise Bi5Error(f"{instrument} {period_start:%Y-%m-%d %H}h: bad LZMA stream: {e}") from e
    if len(data) % RECORD.size:
        raise Bi5Error(f"{instrument} {period_start:%Y-%m-%d %H}h: {len(data)} bytes is not "
                       f"a whole number of {RECORD.size}-byte records")
    scale = SYMBOLS[instrument][1]
    lo, hi = PLAUSIBLE[instrument]
    for ms, ask_i, bid_i, ask_v, bid_v in RECORD.iter_unpack(data):
        ask, bid = ask_i / scale, bid_i / scale
        if not (lo <= bid <= hi and lo <= ask <= hi):
            raise Bi5Error(f"{instrument}: price {bid}/{ask} outside {lo}–{hi} — wrong point scale?")
        yield Tick(period_start + timedelta(milliseconds=ms), ask, bid, ask_v, bid_v)
