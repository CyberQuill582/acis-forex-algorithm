"""Gold cross-check against HistData (GAP-P12D-14 check 4)."""

from __future__ import annotations

import lzma
import zipfile
from datetime import date

from tests.backtest.bi5 import RECORD
from tests.backtest.validation_gold import gold_day, second_wednesday, summarise_gold
from tests.backtest.validation_ticks import day_path

DAY = date(2024, 7, 10)              # second Wednesday of July 2024; EU summer: HistData = UTC − 4 h


def _dukascopy_gold(root, day, price_int: int) -> None:
    """Ticks every second from 12:00 to 16:00 UTC at a fixed price (scale 1000) — real gold
    ticks about twice a second, so every HistData tick has a Dukascopy tick ≤ 2 s before it."""
    p = day_path(root, "XAU_USD", day)
    p.parent.mkdir(parents=True, exist_ok=True)
    recs = [RECORD.pack(s * 1000, price_int + 300, price_int, 1.0, 1.0)
            for s in range(12 * 3600, 16 * 3600)]
    p.write_bytes(lzma.compress(b"".join(recs), format=lzma.FORMAT_ALONE))


def _histdata_gold(root, day, bid: float, ask: float) -> None:
    """Ticks every 7 s across 08:00–12:00 on HistData's clock (= 12:00–16:00 UTC in July)."""
    d = root / "XAU_USD" / str(day.year)
    d.mkdir(parents=True, exist_ok=True)
    rows = [f"{day:%Y%m%d} {s // 3600:02d}{s % 3600 // 60:02d}{s % 60:02d}000,{bid},{ask},0"
            for s in range(8 * 3600, 12 * 3600, 7)]
    rows.append(f"{day.year}{day.month:02d}{day.day + 1:02d} 120000000,{bid},{ask},0")   # next day: stops the scan
    with zipfile.ZipFile(d / f"HISTDATA_COM_ASCII_XAUUSD_T{day.year}{day.month:02d}.zip", "w") as z:
        z.writestr(f"DAT_ASCII_XAUUSD_T_{day.year}{day.month:02d}.csv", "\n".join(rows) + "\n")


def test_second_wednesday() -> None:
    assert second_wednesday(2024, 7) == date(2024, 7, 10)
    assert second_wednesday(2024, 5, ) == date(2024, 5, 8)        # May 1 2024 was a Wednesday


def test_agreeing_sources_pass(tmp_path) -> None:
    _dukascopy_gold(tmp_path / "duk", DAY, 2400_000)              # 2400.000 / 2400.300
    _histdata_gold(tmp_path / "hd", DAY, 2400.01, 2400.29)
    row = gold_day(tmp_path / "duk", tmp_path / "hd", DAY)
    assert row["coverage"] > 0.99 and row["median_bps"] < 0.1
    assert summarise_gold([row], 2024)["flags"] == []


def test_a_price_disagreement_is_flagged(tmp_path) -> None:
    _dukascopy_gold(tmp_path / "duk", DAY, 2400_000)
    _histdata_gold(tmp_path / "hd", DAY, 2405.00, 2405.30)        # ~21 bps higher
    row = gold_day(tmp_path / "duk", tmp_path / "hd", DAY)
    assert row["median_bps"] > 20
    assert any("median" in f for f in summarise_gold([row], 2024)["flags"])


def test_a_clock_shift_shows_as_missing_overlap(tmp_path) -> None:
    _dukascopy_gold(tmp_path / "duk", DAY, 2400_000)
    _histdata_gold(tmp_path / "hd", DAY.replace(day=9), 2400.01, 2400.29)   # wrong day entirely
    assert gold_day(tmp_path / "duk", tmp_path / "hd", DAY)["histdata_ticks"] == 0


def test_month_not_downloaded_is_skipped_not_passed(tmp_path) -> None:
    assert gold_day(tmp_path / "duk", tmp_path / "hd", DAY) is None
