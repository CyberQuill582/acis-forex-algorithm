"""Gold cross-check: Dukascopy XAU/USD vs HistData XAU/USD (GAP-P12D-14 check 4).

Unlike its FX files, HistData's gold ticks are NOT Dukascopy's (different prices, timings
and counts — GAP-P12D-13), so they are a genuinely independent second opinion on the gold
price. The ECB publishes no gold rate. Sampling keeps it cheap: the 12:00–16:00 UTC London/
New-York overlap on the second Wednesday of each month. For each HistData tick, the latest
Dukascopy tick at or before it (≤ 2 s old) gives an absolute mid difference in bps; a day
FLAGS when its median difference is large or too few ticks align. Never averages (C-BT-9).

HistData's monthly file is read only up to the sample day (rows are time-ordered; the
downloader counts the rare out-of-order row, which a sample may skip).
"""

from __future__ import annotations

import io
import statistics
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tests.backtest.sources import histdata_naive_to_utc
from tests.backtest.validation_ticks import DayTicks

UTC = timezone.utc
GOLD_MEDIAN_FLAG_BPS = 5.0
MIN_COVERAGE = 0.5
MIN_TICKS = 100


def second_wednesday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(2 - first.weekday()) % 7 + 7)


def histdata_window(root: Path, day: date, t0: datetime, t1: datetime) -> list[tuple[datetime, float, float]] | None:
    """HistData XAU ticks with t0 <= UTC time < t1 on `day`, or None if the month is not on disk.
    A 12:00–16:00 UTC window falls on the same calendar date on HistData's clock (UTC−4/−5)."""
    path = Path(root) / "XAU_USD" / str(day.year) / f"HISTDATA_COM_ASCII_XAUUSD_T{day.year}{day.month:02d}.zip"
    if not path.exists():
        return None
    want = day.strftime("%Y%m%d")
    out = []
    with zipfile.ZipFile(path) as zf, zf.open(f"DAT_ASCII_XAUUSD_T_{day.year}{day.month:02d}.csv") as raw:
        for line in io.TextIOWrapper(raw, encoding="ascii"):
            stamp = line[:8]
            if stamp < want:
                continue
            if stamp > want:
                break
            ts, bid, ask = line.split(",")[:3]
            t = histdata_naive_to_utc(datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]), int(ts[9:11]),
                                               int(ts[11:13]), int(ts[13:15]), int(ts[15:18]) * 1000))
            if t0 <= t < t1:
                out.append((t, float(bid), float(ask)))
    return out


def gold_day(root_dukascopy: Path, root_histdata: Path, day: date, max_age_s: float = 2.0) -> dict | None:
    """One sample day's comparison, or None if HistData has no file for that month."""
    t0 = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    hd = histdata_window(root_histdata, day, t0, t0 + timedelta(hours=4))
    if hd is None:
        return None
    duk = DayTicks(root_dukascopy, "XAU_USD", day)
    diffs = []
    for t, bid, ask in hd:
        q = duk.last_at_or_before(t, max_age_s)
        if q is not None:
            ref = (q[0] + q[1]) / 2
            diffs.append(abs((bid + ask) / 2 - ref) / ref * 1e4)
    row = {"day": day.isoformat(), "histdata_ticks": len(hd), "dukascopy_ticks": len(duk),
           "matched": len(diffs), "coverage": round(len(diffs) / len(hd), 4) if hd else 0.0}
    if diffs:
        diffs.sort()
        row |= {"median_bps": round(statistics.median(diffs), 3),
                "p95_bps": round(diffs[min(len(diffs) - 1, int(0.95 * len(diffs)))], 3)}
    return row


def summarise_gold(rows: list[dict], year: int) -> dict:
    s = {"year": year, "days": len(rows), "flags": []}
    medians = [r["median_bps"] for r in rows if "median_bps" in r]
    if medians:
        s |= {"median_of_medians_bps": round(statistics.median(medians), 3), "worst_median_bps": max(medians)}
    for r in rows:
        why = []
        if r["histdata_ticks"] < MIN_TICKS:
            why.append(f"only {r['histdata_ticks']} HistData ticks")
        if r["coverage"] < MIN_COVERAGE:
            why.append(f"only {r['coverage']:.0%} aligned")
        if r.get("median_bps", 0.0) > GOLD_MEDIAN_FLAG_BPS:
            why.append(f"median {r['median_bps']} bps > {GOLD_MEDIAN_FLAG_BPS}")
        if why:
            s["flags"].append(f"GOLD {r['day']}: " + "; ".join(why))
    return s
