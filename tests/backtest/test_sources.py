"""Phase-12 tests for the file-backed tick sources (ACIS-09 §5, master §13) and the
cross-source matcher (GAP-P12D-04)."""

from __future__ import annotations

import lzma
import random
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.data.normaliser import RawTick
from tests.backtest.bi5 import RECORD
from tests.backtest.data_loader import BacktestDataLoader, _nearest
from tests.backtest.sources import (DukascopyTickSource, HistDataTickSource,
                                    MissingDataError)
from tests.optimizer_fixtures import CapturingLogger

UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]


def _histdata_zip(root: Path, instrument: str, y: int, m: int, rows: list[str]) -> None:
    pair = instrument.replace("_", "")
    d = root / instrument / str(y)
    d.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(d / f"HISTDATA_COM_ASCII_{pair}_T{y}{m:02d}.zip", "w") as z:
        z.writestr(f"DAT_ASCII_{pair}_T_{y}{m:02d}.csv", "\r\n".join(rows) + "\r\n")


def _dukascopy_day(root: Path, instrument: str, day: datetime, records, synced=True) -> None:
    """Write one official-S3-layout day file (month ZERO-based) + the year's SYNCED marker."""
    d = root / instrument / str(day.year) / f"{day.month - 1:02d}"
    d.mkdir(parents=True, exist_ok=True)
    raw = lzma.compress(b"".join(RECORD.pack(*r) for r in records), format=lzma.FORMAT_ALONE)
    (d / f"{day.day:02d}_ticks.bi5").write_bytes(raw)
    if synced:
        (root / instrument / str(day.year) / "SYNCED").write_text("test")


# ------------------------------------------------------------------ HistData
def test_histdata_clock_is_frankfurt_minus_six_hours(tmp_path) -> None:
    # GAP-P12D-13: HistData documents "EST without DST", but its clock switches on the EU
    # summer-time dates (measured against Dukascopy UTC: 100% tick match either side)
    _histdata_zip(tmp_path, "EUR_USD", 2012, 1, ["20120101 170000123,1.29315,1.29335,0"])  # winter
    _histdata_zip(tmp_path, "EUR_USD", 2012, 7, ["20120701 170000000,1.26600,1.26620,0"])  # EU summer
    _histdata_zip(tmp_path, "EUR_USD", 2024, 3, ["20240311 070000000,1.09,1.0901,0",       # US on EDT, EU not
                                                  "20240329 070000000,1.08,1.0801,0"])      # Fri before EU switch
    _histdata_zip(tmp_path, "EUR_USD", 2024, 4, ["20240401 080000000,1.07,1.0701,0"])       # Mon after EU switch
    src = HistDataTickSource(tmp_path)
    # windows start at 05:00 UTC = 00:00/01:00 on HistData's clock, so each needs only its own file
    jan = list(src.load("EUR_USD", datetime(2012, 1, 1, 5, tzinfo=UTC), datetime(2012, 1, 2, tzinfo=UTC)))
    jul = list(src.load("EUR_USD", datetime(2012, 7, 1, 5, tzinfo=UTC), datetime(2012, 7, 2, tzinfo=UTC)))
    with pytest.raises(MissingDataError):     # 00:00 UTC = 19:00 the previous day -> December's file
        list(src.load("EUR_USD", datetime(2012, 1, 1, tzinfo=UTC), datetime(2012, 1, 2, tzinfo=UTC)))
    assert jan[0].event_time == datetime(2012, 1, 1, 22, 0, 0, 123000, tzinfo=UTC)
    assert jul[0].event_time == datetime(2012, 7, 1, 21, 0, tzinfo=UTC)          # EU summer: -4 h
    mar = list(src.load("EUR_USD", datetime(2024, 3, 11, 5, tzinfo=UTC), datetime(2024, 3, 30, tzinfo=UTC)))
    apr = list(src.load("EUR_USD", datetime(2024, 4, 1, 5, tzinfo=UTC), datetime(2024, 4, 2, tzinfo=UTC)))
    assert [t.event_time for t in mar] == [datetime(2024, 3, 11, 12, tzinfo=UTC),  # EU rule, not US
                                           datetime(2024, 3, 29, 12, tzinfo=UTC)]
    assert apr[0].event_time == datetime(2024, 4, 1, 12, tzinfo=UTC)
    t = jan[0]
    assert (t.bid, t.ask, t.volume, t.provider, t.instrument) == (1.29315, 1.29335, 0.0,
                                                                  "histdata", "EUR_USD")


def test_histdata_window_spans_est_month_boundary(tmp_path) -> None:
    # 2012-01-31 23:30 on HistData's (winter) clock lives in the JANUARY file = 2012-02-01 04:30 UTC
    _histdata_zip(tmp_path, "EUR_USD", 2012, 1, ["20120131 233000000,1.3,1.3002,0"])
    _histdata_zip(tmp_path, "EUR_USD", 2012, 2, ["20120201 010000000,1.31,1.3102,0"])
    got = list(HistDataTickSource(tmp_path).load(
        "EUR_USD", datetime(2012, 2, 1, tzinfo=UTC), datetime(2012, 2, 1, 12, tzinfo=UTC)))
    assert [t.event_time.hour for t in got] == [4, 6]           # both files were read


def test_histdata_missing_month_raises_instead_of_silent_gap(tmp_path) -> None:
    _histdata_zip(tmp_path, "EUR_USD", 2012, 1, ["20120102 120000000,1.3,1.3002,0"])
    with pytest.raises(MissingDataError):
        list(HistDataTickSource(tmp_path).load(
            "EUR_USD", datetime(2012, 1, 20, tzinfo=UTC), datetime(2012, 2, 10, tzinfo=UTC)))


def test_histdata_out_of_order_tick_is_not_dropped(tmp_path) -> None:
    # a tick past the window END followed by an in-window one: no early exit
    _histdata_zip(tmp_path, "EUR_USD", 2012, 1, [
        "20120102 120000000,1.3,1.3002,0",
        "20120102 130000000,1.3,1.3002,0",     # 18:00 UTC, past the window end
        "20120102 121000000,1.3,1.3002,0",     # 17:10 UTC, in window, out of order
    ])
    got = list(HistDataTickSource(tmp_path).load(
        "EUR_USD", datetime(2012, 1, 2, 17, tzinfo=UTC), datetime(2012, 1, 2, 17, 30, tzinfo=UTC)))
    assert [t.event_time.minute for t in got] == [0, 10]


# ----------------------------------------------------------------- Dukascopy
def test_dukascopy_s3_layout_decodes_bid_ask_and_summed_volume(tmp_path) -> None:
    day = datetime(2025, 12, 31, tzinfo=UTC)                 # stored under 2025/11/31 (Dec = 11)
    _dukascopy_day(tmp_path, "EUR_USD", day, [(164, 117459, 117455, 0.12, 0.9)])
    assert (tmp_path / "EUR_USD" / "2025" / "11" / "31_ticks.bi5").exists()
    t = list(DukascopyTickSource(tmp_path).load("EUR_USD", day, day + timedelta(days=1)))[0]
    assert t.event_time == datetime(2025, 12, 31, 0, 0, 0, 164000, tzinfo=UTC)
    assert (t.bid, t.ask, t.provider) == (1.17455, 1.17459, "dukascopy")
    assert t.volume == pytest.approx(1.02)


def test_dukascopy_missing_day_is_holiday_only_inside_a_synced_year(tmp_path) -> None:
    fri, sun = datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 4, 22, tzinfo=UTC)
    _dukascopy_day(tmp_path, "EUR_USD", fri, [(0, 110000, 109990, 1.0, 1.0)])
    _dukascopy_day(tmp_path, "EUR_USD", sun.replace(hour=0), [(79_200_000, 110000, 109990, 1.0, 1.0)])
    src = DukascopyTickSource(tmp_path)
    # Mon 5-Jan has no file, but 2026 is SYNCED → "no ticks", not an error
    got = list(src.load("EUR_USD", fri, datetime(2026, 1, 6, tzinfo=UTC)))
    assert [t.event_time for t in got] == [fri, sun]
    # a year the downloader never finished (no SYNCED marker) must raise
    _dukascopy_day(tmp_path, "EUR_USD", datetime(2024, 3, 4, tzinfo=UTC),
                   [(0, 108000, 107990, 1.0, 1.0)], synced=False)
    with pytest.raises(MissingDataError):
        list(src.load("EUR_USD", datetime(2024, 3, 4, tzinfo=UTC), datetime(2024, 3, 5, tzinfo=UTC)))


def test_naive_or_empty_window_rejected(tmp_path) -> None:
    src = DukascopyTickSource(tmp_path)
    with pytest.raises(ValueError):
        list(src.load("EUR_USD", datetime(2026, 1, 2), datetime(2026, 1, 3)))
    with pytest.raises(ValueError):
        list(src.load("EUR_USD", datetime(2026, 1, 3, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)))


def test_file_sources_pass_through_the_loaders_section3_gate(tmp_path) -> None:
    _histdata_zip(tmp_path, "EUR_USD", 2012, 1, [
        "20120102 120000000,1.30000,1.30020,0",
        "20120102 120001000,1.30030,1.30010,0",     # crossed -> rejected by the loader
    ])
    ldr = BacktestDataLoader({"histdata": HistDataTickSource(tmp_path)}, CapturingLogger())
    res = ldr.load(source="histdata", instrument="EUR_USD",
                   start=datetime(2012, 1, 2, tzinfo=UTC), end=datetime(2012, 1, 3, tzinfo=UTC))
    assert len(res.ticks) == 1 and res.rejected == 1


# ------------------------------------------------- cross-source matcher (P12D-04)
def _old_nearest(sorted_ticks, ts, tol_s):
    best, best_gap = None, tol_s
    for t in sorted_ticks:
        gap = abs((t.event_time - ts).total_seconds())
        if gap <= best_gap:
            best, best_gap = t, gap
    return best


def test_bisect_nearest_matches_the_old_linear_scan_exactly() -> None:
    rng = random.Random(7)
    t0 = datetime(2026, 1, 5, 8, tzinfo=UTC)
    # coarse 250 ms grid forces many exact duplicates and exact midpoint ties
    sec = sorted((RawTick(event_time=t0 + timedelta(milliseconds=250 * rng.randint(0, 400)),
                          recv_time=t0, instrument="EUR_USD", bid=1.1 + i * 1e-6,
                          ask=1.1002 + i * 1e-6, volume=0.0, book=None, provider="x",
                          raw_payload={}) for i in range(600)), key=lambda t: t.event_time)
    times = [t.event_time for t in sec]
    for i in range(3000):
        ts = t0 + timedelta(milliseconds=125 * rng.randint(-40, 840))
        for tol in (0.0, 0.1, 1.0, 5.0):
            assert _nearest(sec, times, ts, tol) is _old_nearest(sec, ts, tol), (ts, tol)


# ------------------------------------------------- real downloaded files (smoke)
HD_REAL = REPO / "data" / "histdata" / "EUR_GBP" / "2012" / "HISTDATA_COM_ASCII_EURGBP_T201201.zip"


@pytest.mark.skipif(not HD_REAL.exists(), reason="real HistData month not downloaded")
def test_real_histdata_month_hour_is_sane() -> None:
    src = HistDataTickSource(REPO / "data" / "histdata")
    got = list(src.load("EUR_GBP", datetime(2012, 1, 10, 8, tzinfo=UTC),
                        datetime(2012, 1, 10, 9, tzinfo=UTC)))    # London morning
    assert len(got) > 500
    assert all(0.70 < t.bid < 0.90 and t.ask >= t.bid for t in got)   # EUR/GBP Jan-2012 range
    assert all(a.event_time <= b.event_time for a, b in zip(got, got[1:]))


REAL_DUK_2024 = REPO / "data" / "dukascopy" / "EUR_USD" / "2024" / "SYNCED"
REAL_HD_2024 = [REPO / "data" / "histdata" / "EUR_USD" / "2024" / f"HISTDATA_COM_ASCII_EURUSD_T2024{m:02d}.zip"
                for m in (3, 4, 10)]


@pytest.mark.skipif(not (REAL_DUK_2024.exists() and all(p.exists() for p in REAL_HD_2024)),
                    reason="real 2024 EUR_USD Dukascopy + HistData months not downloaded")
@pytest.mark.parametrize("start", [datetime(2024, 3, 29, 12, tzinfo=UTC), datetime(2024, 4, 1, 12, tzinfo=UTC),
                                   datetime(2024, 10, 25, 12, tzinfo=UTC), datetime(2024, 10, 28, 12, tzinfo=UTC)])
def test_real_histdata_ticks_land_on_dukascopy_utc_across_eu_switches(start) -> None:
    # GAP-P12D-13 regression on the REAL files, both sides of each EU switch: the same ticks at
    # the same UTC millisecond, and the drift check sees full overlap (never a silent clear)
    end = start + timedelta(minutes=10)

    def key(t):
        return (round(t.event_time.timestamp() * 1000), round(t.bid, 5), round(t.ask, 5))

    duk = list(DukascopyTickSource(REPO / "data" / "dukascopy").load("EUR_USD", start, end))
    hd = list(HistDataTickSource(REPO / "data" / "histdata").load("EUR_USD", start, end))
    assert len(hd) > 100
    dk = {key(t) for t in duk}
    assert sum(1 for t in hd if key(t) in dk) / len(hd) > 0.99
    rep = BacktestDataLoader({}, CapturingLogger()).cross_source_drift(
        instrument="EUR_USD", primary=hd, secondary=duk, threshold_bps=5.0)
    assert not rep.flagged and rep.coverage > 0.99 and rep.max_bps == 0.0
