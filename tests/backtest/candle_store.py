"""An instrument's verified hourly candles as arrays (R1.5; read by rsim_real.py).

Mental model:
  * One row per hour from the instrument's first month to 2025-12, BID and ASK decoded by
    candles.py (which refuses a bad month whole). The mid is (bid + ask)/2 at the open and at the
    close; the spread is ask − bid at the open, floored at 0 (a crossed quote is recorded by the
    downloader, never a negative cost).
  * `traded` marks hours with any volume: weekend and closed-session hours are flat, volume 0,
    and must never be read as a price observation.
  * Times are epoch seconds (UTC) of each hour's START; the hour ends 3,600 s later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tests.backtest.candles import decode_month
from tests.backtest.universe import BY_NAME

LAST = (2025, 12)


@dataclass(frozen=True)
class Hourly:
    name: str
    start: np.ndarray        # int64 epoch seconds, ascending
    mid_open: np.ndarray
    mid_close: np.ndarray
    spread_open: np.ndarray
    traded: np.ndarray       # bool


def load(root: Path, name: str, until: tuple[int, int] = LAST) -> Hourly:
    inst = BY_NAME[name]
    fy, fm = (int(x) for x in inst.first.split("-"))
    rows = []
    y, m = fy, fm
    while (y, m) <= until:
        month = Path(root) / inst.duka / str(y) / f"{m - 1:02d}"
        bid = decode_month((month / "BID_candles_hour_1.bi5").read_bytes(), name, y, m)
        ask = decode_month((month / "ASK_candles_hour_1.bi5").read_bytes(), name, y, m)
        rows.extend((int(b.ts.timestamp()), (b.open + a.open) / 2, (b.close + a.close) / 2,
                     max(a.open - b.open, 0.0), b.volume > 0 or a.volume > 0) for b, a in zip(bid, ask))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    arr = list(zip(*rows))
    start = np.asarray(arr[0], np.int64)
    if np.any(np.diff(start) != 3600):
        raise ValueError(f"{name}: hours are not contiguous")
    return Hourly(name, start, np.asarray(arr[1], float), np.asarray(arr[2], float),
                  np.asarray(arr[3], float), np.asarray(arr[4], bool))
