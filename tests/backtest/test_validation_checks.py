"""The independent Dukascopy validation checks (GAP-P12D-14): fast day lookups, the ECB
comparison, the EUR/GBP triangle, and the clock-mark checks that catch a shifted clock."""

from __future__ import annotations

import lzma
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.backtest.bi5 import RECORD, Bi5Error
from tests.backtest.validation_checks import (ECB_PRICE, day_metrics, ecb_fixing_utc,
                                              summarise_instrument_year, summarise_triangle,
                                              triangle_samples)
from tests.backtest.validation_ticks import DayTicks, day_path

UTC = timezone.utc


def _write_day(root, instrument, day, records) -> None:
    """records: (ms offset, ask integer, bid integer) — volumes fixed at 1.0."""
    p = day_path(root, instrument, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(RECORD.pack(ms, ask, bid, 1.0, 1.0) for ms, ask, bid in records)
    p.write_bytes(lzma.compress(raw, format=lzma.FORMAT_ALONE))


def test_day_ticks_point_lookups(tmp_path) -> None:
    day = date(2024, 1, 15)
    _write_day(tmp_path, "EUR_USD", day, [(0, 110010, 110000), (60_000, 110020, 110010), (120_000, 110030, 110020)])
    t = DayTicks(tmp_path, "EUR_USD", day)
    at = datetime(2024, 1, 15, 0, 1, 30, tzinfo=UTC)
    assert t.last_at_or_before(at, max_age_s=60) == (1.1001, 1.1002)
    assert t.last_at_or_before(at, max_age_s=10) is None                 # too stale
    assert t.count(t.start, t.start + timedelta(minutes=2)) == 2           # [0, 120 s)
    assert DayTicks(tmp_path, "EUR_USD", date(2024, 1, 16)).last_at_or_before(at, 60) is None  # no file
    _write_day(tmp_path, "EUR_USD", date(2024, 1, 17), [(0, 11001, 11000)])   # 10x too small: wrong scale
    with pytest.raises(Bi5Error):
        DayTicks(tmp_path, "EUR_USD", date(2024, 1, 17)).quote(0)


def test_ecb_fixing_is_1415_frankfurt_in_both_seasons() -> None:
    assert ecb_fixing_utc(date(2024, 1, 15)) == datetime(2024, 1, 15, 13, 15, tzinfo=UTC)   # CET
    assert ecb_fixing_utc(date(2024, 7, 15)) == datetime(2024, 7, 15, 12, 15, tzinfo=UTC)   # CEST


def test_ecb_cross_rates_are_built_from_per_euro_quotes() -> None:
    r = {"USD": 1.10, "GBP": 0.85, "JPY": 160.0, "CHF": 0.95, "CAD": 1.45, "AUD": 1.65}
    assert ECB_PRICE["EUR_USD"](r) == 1.10
    assert ECB_PRICE["GBP_USD"](r) == pytest.approx(1.10 / 0.85)
    assert ECB_PRICE["USD_JPY"](r) == pytest.approx(160.0 / 1.10)
    assert ECB_PRICE["AUD_USD"](r) == pytest.approx(1.10 / 1.65)


def test_day_metrics_ecb_gap_and_weekend_ticks(tmp_path) -> None:
    mon = date(2024, 1, 15)                                      # fixing 13:15 UTC
    fix_ms = 13 * 3_600_000 + 15 * 60_000
    _write_day(tmp_path, "EUR_USD", mon, [(fix_ms - 1_000, 110120, 110100)])     # mid 1.1011
    m = day_metrics(tmp_path, "EUR_USD", mon, {"USD": 1.1000})
    assert m["ecb_bps"] == pytest.approx(10.0, abs=0.01) and m["weekend_ticks"] == 0
    sat = date(2024, 1, 20)
    _write_day(tmp_path, "EUR_USD", sat, [(1_000, 110010, 110000), (2_000, 110010, 110000), (3_000, 110010, 110000)])
    assert day_metrics(tmp_path, "EUR_USD", sat, None)["weekend_ticks"] == 3


def _roll_day(tmp_path, spike_hour_utc: int) -> dict:
    """July Monday: 1-pip spreads every 10 s from 19:30 to 23:30 UTC, 10 pips for five
    minutes from `spike_hour_utc`:00. The real 17:00-New-York roll is 21:00 UTC (EDT)."""
    day = date(2024, 7, 15)
    recs = []
    for s in range(19 * 3600 + 1800, 23 * 3600 + 1800, 10):
        spike = spike_hour_utc * 3600 <= s < spike_hour_utc * 3600 + 300
        recs.append((s * 1000, 110000 + (100 if spike else 10), 110000))
    _write_day(tmp_path, "EUR_USD", day, recs)
    return day_metrics(tmp_path, "EUR_USD", day, None)


def test_rollover_spike_found_at_the_real_instant(tmp_path) -> None:
    m = _roll_day(tmp_path, spike_hour_utc=21)
    assert m["roll_spread"]["true"] >= 5 and m["roll_spread"]["late"] <= 1.5
    assert not [f for f in summarise_instrument_year([m])["flags"] if f.startswith("CLOCK")]


def test_a_clock_shifted_by_an_hour_is_flagged(tmp_path) -> None:
    m = _roll_day(tmp_path, spike_hour_utc=22)                   # the spike sits an hour late
    flags = summarise_instrument_year([m])["flags"]
    assert any(f.startswith("CLOCK: rollover") for f in flags)


def test_triangle_flags_an_inconsistent_cross() -> None:
    eurusd, gbpusd = {12: (1.10000, 1.10002)}, {12: (1.27000, 1.27002)}
    implied = 1.10001 / 1.27001
    good = triangle_samples(eurusd, gbpusd, {12: (implied - 0.00001, implied + 0.00001)}, "2024-01-15")
    bad = triangle_samples(eurusd, gbpusd, {12: (implied * 1.002, implied * 1.002 + 0.00002)}, "2024-01-15")
    assert not good[0]["flagged"] and bad[0]["flagged"] and abs(bad[0]["dev_bps"]) > 15
    assert summarise_triangle(bad, 2024)["flags"] and not summarise_triangle(good, 2024)["flags"]


def test_summary_flags_ecb_outliers_gold_break_and_jobs_report_shift() -> None:
    base = {"instrument": "XAU_USD", "day": "2024-03-04", "ticks": 1000, "weekend_ticks": 0}
    ok = summarise_instrument_year([base | {"gold_break": {"true": 0, "early": 900, "late": 800},
                                            "nfp_burst": {"true": 4.0, "early": 1.0, "late": 1.1}}])
    assert ok["flags"] == []
    shifted = summarise_instrument_year([base | {"gold_break": {"true": 850, "early": 0, "late": 900},
                                                 "nfp_burst": {"true": 1.0, "early": 1.1, "late": 4.0}}])
    assert any("gold daily break" in f for f in shifted["flags"])
    assert any("jobs-report" in f for f in shifted["flags"])
    eur = {"instrument": "EUR_USD", "day": "2015-01-15", "ticks": 5, "weekend_ticks": 0, "ecb_bps": 180.0}
    assert any(f.startswith("ECB") for f in summarise_instrument_year([eur])["flags"])
