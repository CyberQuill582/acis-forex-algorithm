"""The tournament's input store (TOURNAMENT): files are write-once (a changed re-fetch is a revision line), a
declared hole stays a hole, minutes aggregate to the hours RSIM and the event books read, horizons stop at
the first unsettled day, and a series freezes per date. Synthetic files in temporary directories only."""

from __future__ import annotations

import csv
import lzma
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

import tests.backtest.forward_store as fs
from tests.backtest.candle_store import Hourly
from tests.backtest.candles_min import RAW
from tests.backtest.forward_store import EPOCH, SPX, InputStore, StoreGap, minute_rel, tick_rel

NOW = datetime(2026, 10, 10, 6, tzinfo=timezone.utc)
SCALE = 100_000


def _minutes(mids: np.ndarray, spread: float, volume: np.ndarray) -> tuple[bytes, bytes]:
    out = []
    for shift in (-spread / 2, spread / 2):
        r = np.zeros(1440, RAW)
        r["sec"] = np.arange(1440) * 60
        px = np.round((mids + shift) * SCALE).astype(np.uint32)
        r["open"], r["close"] = np.r_[px[0], px[:-1]], px
        r["low"], r["high"] = np.minimum(r["open"], r["close"]), np.maximum(r["open"], r["close"])
        r["volume"] = volume
        out.append(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE))
    return out[0], out[1]


def _store(tmp_path) -> InputStore:
    arch = tmp_path / "archive"
    (arch / "macro").mkdir(parents=True)
    (arch / "treasury").mkdir()
    (arch / "macro" / "spx_yahoo.csv").write_text("date,value\n2025-12-30,6900.0\n2025-12-31,6950.0\n", encoding="utf-8")
    return InputStore(tmp_path / "store", archive_candles=arch / "candles", archive_macro=arch / "macro",
                      archive_treasury=arch / "treasury", holidays_csv=arch / "holidays.csv")


def _put_day(store: InputStore, d: date, mids, volume=None, spread=0.0002) -> None:
    bid, ask = _minutes(np.asarray(mids, float), spread, np.ones(1440, np.float32) if volume is None else volume)
    store.add_file(minute_rel("EUR_USD", d, "BID"), bid, NOW)
    store.add_file(minute_rel("EUR_USD", d, "ASK"), ask, NOW)


def test_a_stored_file_is_never_replaced_and_a_changed_refetch_is_one_revision_line(tmp_path) -> None:
    s = _store(tmp_path)
    assert s.add_file("ticks/USD_JPY/2026/09/05_ticks.bi5", b"first", NOW) == "added"
    assert s.add_file("ticks/USD_JPY/2026/09/05_ticks.bi5", b"first", NOW) == "same"
    assert s.add_file("ticks/USD_JPY/2026/09/05_ticks.bi5", b"second", NOW) == "revision"
    assert s.add_file("ticks/USD_JPY/2026/09/05_ticks.bi5", b"second", NOW) == "revision"
    assert (s.root / "ticks/USD_JPY/2026/09/05_ticks.bi5").read_bytes() == b"first"
    assert sum("revision" in r for r in s.manifest()) == 1


def test_a_declared_hole_reads_as_untraded_hours_and_a_late_file_never_enters(tmp_path, monkeypatch) -> None:
    s = _store(tmp_path)
    start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    n = (EPOCH - date(2026, 1, 1)).days * 24
    pre = Hourly("EUR_USD", start + 3600 * np.arange(n, dtype=np.int64), np.full(n, 1.1), np.full(n, 1.1),
                 np.full(n, 0.0001), np.ones(n, bool))
    empty = Hourly("EUR_USD", np.zeros(0, np.int64), *(np.zeros(0),) * 3, np.zeros(0, bool))
    monkeypatch.setattr(fs, "load", lambda root, name, until, since=None: pre if since else empty)
    _put_day(s, EPOCH, 1.2 + 1e-5 * np.arange(1440))
    for side in ("BID", "ASK"):
        s.declare_hole(minute_rel("EUR_USD", EPOCH + timedelta(days=1), side), NOW, "test")
    _put_day(s, EPOCH + timedelta(days=2), np.full(1440, 1.3))
    h = s.hourly("EUR_USD", EPOCH + timedelta(days=2))
    assert len(h.start) == n + 72 and np.all(np.diff(h.start) == 3600)
    day0 = slice(n, n + 24)
    assert h.mid_open[day0][0] == pytest.approx(1.2) and h.mid_close[day0][0] == pytest.approx(1.2 + 1e-5 * 59)          # minute 59 closes the hour
    assert h.spread_open[day0][0] == pytest.approx(0.0002) and h.traded[day0].all()
    hole = slice(n + 24, n + 48)
    assert not h.traded[hole].any() and np.all(h.mid_close[hole] == h.mid_close[n + 23])
    _put_day(s, EPOCH + timedelta(days=1), np.full(1440, 9.0 / 8))                     # arrives after the hole
    assert not s.hourly("EUR_USD", EPOCH + timedelta(days=2)).traded[hole].any()
    assert len(s.hourly("EUR_USD", EPOCH).start) == n + 24                           # cut at the day asked
    with pytest.raises(StoreGap):
        s.hourly("EUR_USD", EPOCH + timedelta(days=3))


def test_the_minute_and_tick_horizons_stop_at_the_first_unsettled_day(tmp_path) -> None:
    s = _store(tmp_path)
    for k in range(3):
        _put_day(s, EPOCH + timedelta(days=k), np.full(1440, 1.1))
    assert s.minute_horizon(("EUR_USD",), EPOCH + timedelta(days=10)) == EPOCH + timedelta(days=2)
    assert s.minute_horizon(("EUR_USD",), EPOCH + timedelta(days=1)) == EPOCH          # never today or later
    s.add_file(tick_rel("EUR_USD", EPOCH), b"", NOW)
    _put_day(s, EPOCH + timedelta(days=1), np.full(1440, 1.1), volume=np.zeros(1440, np.float32))  # no-op: stored
    assert s.tick_horizon("EUR_USD", EPOCH + timedelta(days=10)) == EPOCH             # day 1 traded: no tick file
    s.declare_hole(tick_rel("EUR_USD", EPOCH + timedelta(days=1)), NOW, "test")
    assert s.tick_horizon("EUR_USD", EPOCH + timedelta(days=10)) == EPOCH + timedelta(days=1)


def test_a_day_with_no_volume_all_day_settles_the_ticks_without_a_file(tmp_path) -> None:
    s = _store(tmp_path)
    _put_day(s, EPOCH, np.full(1440, 1.1), volume=np.zeros(1440, np.float32))
    assert s.tick_horizon("EUR_USD", EPOCH + timedelta(days=5)) == EPOCH


def test_a_series_freezes_only_dates_after_its_frozen_day_and_a_changed_print_is_logged(tmp_path) -> None:
    s = _store(tmp_path)
    rows = [(date(2026, 1, 2), None, 6000.0), (date(2026, 1, 5), None, 6010.0), (date(2026, 1, 6), None, 6020.0)]
    assert s.freeze_series(SPX, rows, date(2026, 1, 5), NOW) == 2
    assert s.through(SPX) == date(2026, 1, 5)
    assert s.freeze_series(SPX, [(date(2026, 1, 5), None, 6011.0), *rows[2:]], date(2026, 1, 6), NOW) == 1
    assert s.closes(SPX, date(2026, 1, 6)) == {date(2025, 12, 30): 6900.0, date(2025, 12, 31): 6950.0,
                                               date(2026, 1, 2): 6000.0, date(2026, 1, 5): 6010.0, date(2026, 1, 6): 6020.0}
    revs = [r for r in s.manifest() if r.get("revision") == f"series/{SPX}"]
    assert len(revs) == 1 and revs[0]["frozen"] == 6010.0 and revs[0]["seen"] == 6011.0
    with (s.root / "series" / f"{SPX}.csv").open(encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 3


def test_the_state_hash_moves_with_every_stored_input(tmp_path) -> None:
    s = _store(tmp_path)
    h0 = s.state_hash()
    s.add_file("ticks/USD_JPY/2026/09/05_ticks.bi5", b"x", NOW)
    h1 = s.state_hash()
    s.freeze_series(SPX, [(date(2026, 1, 2), None, 6000.0)], date(2026, 1, 2), NOW)
    assert len({h0, h1, s.state_hash()}) == 3
