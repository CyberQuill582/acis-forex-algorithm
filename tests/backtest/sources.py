"""File-backed historical tick sources for the §14 OOS run (ACIS-09 §5, master §13).

Each adapter maps one vendor's on-disk files (written by scripts/download_*.py|js)
to the feed-agnostic `RawTick`, in UTC, as a STREAM — a multi-year window is never
held in memory here. The adapter's `name` is its declared provenance for
`BacktestDataLoader`; §3 filtering (NaN / crossed / non-positive / spread / weekend)
stays in the loader, so every vendor passes the same gate.

A missing file inside the requested window raises `MissingDataError` — a silent gap
would make the backtest quietly trade through a hole in the data.

    histdata   data/histdata/<INSTR>/<YYYY>/HISTDATA_COM_ASCII_<PAIR>_T<YYYYMM>.zip
               "YYYYMMDD HHMMSSNNN,bid,ask,vol". HistData documents "EST without DST", but
               its clock is Frankfurt time − 6 h — it switches on the EU summer-time dates
               (GAP-P12D-13) — i.e. London time − 5 h; one file per month on that clock.
               Carries no tick volume (0).
    dukascopy  data/dukascopy/<INSTR>/<YYYY>/<MM0>/<DD>_ticks.bi5 — a mirror of Dukascopy's
               official S3 archive (month ZERO-based), decoded by bi5.py. A missing day
               inside a year the downloader marked `SYNCED` means "no ticks" (holiday);
               a year with no marker was never downloaded and raises.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from core.data.fx_clock import naive_local_to_utc, to_local, utc_offset
from core.data.normaliser import RawTick
from tests.backtest import bi5
from tests.backtest.data_loader import TickSource

UTC = timezone.utc
HD_TO_LONDON = timedelta(hours=5)       # HistData clock + 5 h = London wall time (P12D-13)


def histdata_naive_to_utc(hd: datetime) -> datetime:
    """HistData's clock (Frankfurt − 6 h, measured against Dukascopy UTC) → UTC."""
    return naive_local_to_utc(hd + HD_TO_LONDON, "Europe/London")


def utc_to_histdata(ts: datetime) -> datetime:
    """A UTC instant as HistData's naive clock (which monthly file holds it)."""
    return to_local(ts, "Europe/London") - HD_TO_LONDON


class MissingDataError(Exception):
    """A file the requested window needs is not on disk."""


def _check_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start/end must be tz-aware (UTC)")
    if end <= start:
        raise ValueError(f"empty window {start} .. {end}")


def _tick(ts: datetime, instrument: str, bid: float, ask: float, vol: float,
          provider: str) -> RawTick:
    return RawTick(event_time=ts, recv_time=ts, instrument=instrument, bid=bid, ask=ask,
                   volume=vol, book=None, provider=provider, raw_payload={})


class HistDataTickSource(TickSource):
    name = "histdata"
    provenance = "real"

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def path(self, instrument: str, year: int, month: int) -> Path:
        pair = instrument.replace("_", "")
        return (self._root / instrument / str(year)
                / f"HISTDATA_COM_ASCII_{pair}_T{year}{month:02d}.zip")

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        _check_window(start, end)
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        pair = instrument.replace("_", "")
        # the UTC window, seen on HistData's clock, spans these monthly files
        first_hd = utc_to_histdata(start)
        last_hd = utc_to_histdata(end) - timedelta(microseconds=1)
        y, m = first_hd.year, first_hd.month
        offsets: dict = {}                                 # London offset per local date
        while (y, m) <= (last_hd.year, last_hd.month):
            p = self.path(instrument, y, m)
            if not p.exists():
                raise MissingDataError(f"histdata {instrument} {y}-{m:02d}: {p}")
            member = f"DAT_ASCII_{pair}_T_{y}{m:02d}.csv"
            with zipfile.ZipFile(p) as zf, zf.open(member) as raw:
                for line in io.TextIOWrapper(raw, encoding="ascii"):
                    if not line.strip():
                        continue
                    ts, bid, ask, vol = line.rstrip("\r\n").split(",")[:4]
                    local = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]), int(ts[9:11]),
                                     int(ts[11:13]), int(ts[13:15]),
                                     int(ts[15:18]) * 1000) + HD_TO_LONDON
                    off = offsets.get(local.date())
                    if off is None:
                        off = offsets[local.date()] = utc_offset(local.date(), "Europe/London")
                    t = (local - off).replace(tzinfo=UTC)
                    # no early exit on t >= end: the downloader COUNTS out-of-order
                    # ticks rather than rejecting them, so keep scanning the file
                    if start <= t < end:
                        yield _tick(t, instrument, float(bid), float(ask), float(vol), self.name)
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)


class DukascopyTickSource(TickSource):
    name = "dukascopy"
    provenance = "real"

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def path(self, instrument: str, day: datetime) -> Path:
        return (self._root / instrument / str(day.year) / f"{day.month - 1:02d}"
                / f"{day.day:02d}_ticks.bi5")

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        _check_window(start, end)
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day < end:
            if not (self._root / instrument / str(day.year) / "SYNCED").exists():
                raise MissingDataError(f"dukascopy {instrument} {day.year}: year not "
                                       f"downloaded (no SYNCED marker)")
            p = self.path(instrument, day)
            if p.exists():                       # absent inside a SYNCED year = no ticks
                for t in bi5.decode(p.read_bytes(), instrument, day):
                    if start <= t.ts < end:
                        yield _tick(t.ts, instrument, t.bid, t.ask,
                                    t.ask_volume + t.bid_volume, self.name)
            day += timedelta(days=1)
