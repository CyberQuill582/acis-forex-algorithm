"""File-backed historical tick sources for the §14 OOS run (ACIS-09 §5, master §13).

Each adapter maps one vendor's on-disk files (written by scripts/download_*.py|js)
to the feed-agnostic `RawTick`, in UTC, as a STREAM — a multi-year window is never
held in memory here. The adapter's `name` is its declared provenance for
`BacktestDataLoader`; §3 filtering (NaN / crossed / non-positive / spread / weekend)
stays in the loader, so every vendor passes the same gate.

A missing file inside the requested window raises `MissingDataError` — a silent gap
would make the backtest quietly trade through a hole in the data.

    histdata   data/histdata/<INSTR>/<YYYY>/HISTDATA_COM_ASCII_<PAIR>_T<YYYYMM>.zip
               "YYYYMMDD HHMMSSNNN,bid,ask,vol", fixed EST (UTC-5, NO daylight saving);
               one file per EST calendar month. Carries no tick volume (0).
    dukascopy  data/dukascopy/<INSTR>/<YYYY>/<sym>-<YYYY-MM-DD>.csv.gz
               "timestamp(ms UTC),askPrice,bidPrice,askVolume,bidVolume"; one file per
               UTC day, Saturdays never written (market closed).
"""

from __future__ import annotations

import csv
import gzip
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from core.data.normaliser import RawTick
from tests.backtest.data_loader import TickSource

UTC = timezone.utc
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
EST_OFFSET = timedelta(hours=5)                 # HistData EST (fixed) -> UTC


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
        # the UTC window, seen in HistData's fixed EST, spans these EST months
        first_est, last_est = start - EST_OFFSET, end - EST_OFFSET - timedelta(microseconds=1)
        y, m = first_est.year, first_est.month
        while (y, m) <= (last_est.year, last_est.month):
            p = self.path(instrument, y, m)
            if not p.exists():
                raise MissingDataError(f"histdata {instrument} {y}-{m:02d}: {p}")
            member = f"DAT_ASCII_{pair}_T_{y}{m:02d}.csv"
            with zipfile.ZipFile(p) as zf, zf.open(member) as raw:
                for line in io.TextIOWrapper(raw, encoding="ascii"):
                    if not line.strip():
                        continue
                    ts, bid, ask, vol = line.rstrip("\r\n").split(",")[:4]
                    t = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]), int(ts[9:11]),
                                 int(ts[11:13]), int(ts[13:15]), int(ts[15:18]) * 1000,
                                 tzinfo=UTC) + EST_OFFSET
                    # no early exit on t >= end: the downloader COUNTS out-of-order
                    # ticks rather than rejecting them, so keep scanning the file
                    if start <= t < end:
                        yield _tick(t, instrument, float(bid), float(ask), float(vol), self.name)
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)


class DukascopyTickSource(TickSource):
    name = "dukascopy"

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def path(self, instrument: str, day: datetime) -> Path:
        sym = instrument.replace("_", "").lower()
        d = day.strftime("%Y-%m-%d")
        return self._root / instrument / d[:4] / f"{sym}-{d}.csv.gz"

    def load(self, instrument: str, start: datetime, end: datetime) -> Iterator[RawTick]:
        _check_window(start, end)
        start, end = start.astimezone(UTC), end.astimezone(UTC)
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day < end:
            if day.weekday() != 5:               # Saturday files are never written
                p = self.path(instrument, day)
                if not p.exists():
                    raise MissingDataError(f"dukascopy {instrument} {day:%Y-%m-%d}: {p}")
                with gzip.open(p, "rt", encoding="ascii", newline="") as f:
                    rows = csv.reader(f)
                    next(rows, None)             # header
                    for ms, ask, bid, askv, bidv in rows:
                        t = EPOCH + timedelta(milliseconds=int(ms))    # exact, no float
                        if start <= t < end:
                            yield _tick(t, instrument, float(bid), float(ask),
                                        float(askv) + float(bidv), self.name)
            day += timedelta(days=1)
