"""Session tagging per market calendar (C1 generalised, C-DATA-3/7)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.data.asset_classes import build_calendars


def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


@pytest.fixture()
def calendars(acis_config):
    return build_calendars(acis_config.instruments.calendars)


class TestFxCalendar:
    def test_single_sessions_and_overlaps(self, calendars) -> None:
        fx = calendars["fx_default"]
        assert fx.session_at(_utc(2026, 7, 14, 8)) == "overlap"      # tokyo+london
        assert fx.session_at(_utc(2026, 7, 14, 10)) == "london"
        assert fx.session_at(_utc(2026, 7, 14, 13)) == "overlap"     # london+ny
        assert fx.session_at(_utc(2026, 7, 14, 17)) == "new_york"
        assert fx.session_at(_utc(2026, 7, 14, 2)) == "tokyo"
        assert fx.session_at(_utc(2026, 7, 14, 21, 30)) == "sydney"  # GAP-0023: no dead window

    def test_weekend_boundaries(self, calendars) -> None:
        fx = calendars["fx_default"]
        assert fx.session_at(_utc(2026, 7, 18, 12)) == "closed"       # Saturday
        assert fx.session_at(_utc(2026, 7, 17, 22, 30)) == "closed"   # Friday post-close
        assert fx.session_at(_utc(2026, 7, 19, 20, 59)) == "closed"   # Sunday pre-open
        assert fx.session_at(_utc(2026, 7, 20, 2)) == "tokyo"         # Monday
        # winter: New York trades until 22:00 UTC on Friday (17:00 EST)
        assert fx.session_at(_utc(2026, 1, 16, 21, 30)) == "new_york"
        assert fx.session_at(_utc(2026, 1, 16, 22, 0)) == "closed"

    def test_windows_follow_each_centres_dst(self, calendars) -> None:
        # GAP-P12D-10: sessions are local wall time, so their UTC windows MOVE.
        fx = calendars["fx_default"]
        # London opens 08:00 London: 08:00 UTC in January, 07:00 UTC in July
        assert fx.session_at(_utc(2026, 1, 14, 7, 30)) == "tokyo"
        assert fx.session_at(_utc(2026, 7, 14, 7, 30)) == "overlap"
        # 2026-03-08 → 03-29 the US is on EDT while London is still on GMT: New York
        # opens 12:00 UTC on 10 March but 13:00 UTC on 6 March
        assert fx.session_at(_utc(2026, 3, 6, 12, 30)) == "london"
        assert fx.session_at(_utc(2026, 3, 10, 12, 30)) == "overlap"

    def test_sydney_fills_new_york_close_to_tokyo_open(self, calendars) -> None:
        # GAP-0023: the old dead window is the Sydney session, all year, and it
        # never overlaps Tokyo (the overlap baseline stays London–New York)
        fx = calendars["fx_default"]
        for h in (21, 22, 23):                                        # July: NY closes 21:00 UTC
            assert fx.session_at(_utc(2026, 7, 14, h, 30)) == "sydney"
        assert fx.session_at(_utc(2026, 1, 13, 21, 30)) == "new_york"  # January: NY until 22:00
        assert fx.session_at(_utc(2026, 1, 13, 22, 30)) == "sydney"
        assert fx.session_at(_utc(2026, 7, 15, 0, 30)) == "tokyo"      # Tokyo open ends it
        assert fx.session_at(_utc(2026, 7, 19, 21, 30)) == "sydney"    # Sunday reopen

    def test_naive_timestamp_rejected(self, calendars) -> None:
        with pytest.raises(ValueError):
            calendars["fx_default"].session_at(datetime(2026, 7, 14, 8))


class TestExchangeCalendar:
    def test_open_holiday_weekend(self, calendars) -> None:
        cme = calendars["cme_metals"]
        assert cme.session_at(_utc(2026, 7, 15, 14)) == "exchange"   # Wed 09:00 Chicago
        assert cme.session_at(_utc(2026, 7, 15, 21)) == "closed"     # 16:00 Chicago, after close
        assert cme.session_at(_utc(2026, 1, 14, 14)) == "closed"     # 08:00 CST, pre-open
        assert cme.session_at(_utc(2026, 1, 14, 20, 30)) == "exchange"  # 14:30 CST
        assert cme.session_at(_utc(2026, 7, 3, 14)) == "closed"      # declared holiday
        assert cme.session_at(_utc(2026, 7, 18, 14)) == "closed"     # Saturday

    def test_half_day_early_close_is_session_end(self, calendars) -> None:
        cme = calendars["cme_metals"]
        assert cme.session_at(_utc(2026, 11, 27, 15)) == "exchange"  # 09:00 CST, before 11:00
        assert cme.session_at(_utc(2026, 11, 27, 17, 30)) == "closed"  # 11:30 CST, after


class TestSpotMetalsCalendar:
    """GAP-P12D-11: spot gold is OTC 24/5 with a daily 17:00–18:00 New York break."""

    def test_trades_around_the_clock_except_the_daily_break(self, calendars) -> None:
        gold = calendars["spot_metals"]
        assert gold.session_at(_utc(2026, 7, 15, 3)) == "tokyo"        # was "closed" on CME hours
        assert gold.session_at(_utc(2026, 7, 15, 21, 30)) == "closed"   # 17:30 EDT: daily break
        assert gold.session_at(_utc(2026, 7, 15, 22, 30)) == "sydney"   # 18:30 EDT: reopened
        assert gold.session_at(_utc(2026, 1, 14, 22, 30)) == "closed"   # 17:30 EST: break moves

    def test_week_opens_an_hour_after_fx(self, calendars) -> None:
        gold, fx = calendars["spot_metals"], calendars["fx_default"]
        sunday_1730_edt = _utc(2026, 7, 19, 21, 30)
        assert fx.session_at(sunday_1730_edt) == "sydney"
        assert gold.session_at(sunday_1730_edt) == "closed"
        assert gold.session_at(_utc(2026, 7, 19, 22, 30)) == "sydney"   # Sunday 18:30 EDT


def test_gold_is_on_the_spot_metals_calendar(acis_config) -> None:
    assert acis_config.instruments.instruments["XAU_USD"].calendar == "spot_metals"
