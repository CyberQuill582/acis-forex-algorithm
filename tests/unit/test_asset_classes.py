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
        assert fx.session_at(_utc(2026, 7, 14, 21, 30)) == "closed"  # outside all windows

    def test_weekend_boundaries(self, calendars) -> None:
        fx = calendars["fx_default"]
        assert fx.session_at(_utc(2026, 7, 18, 12)) == "closed"       # Saturday
        assert fx.session_at(_utc(2026, 7, 17, 22, 30)) == "closed"   # Friday post-close
        assert fx.session_at(_utc(2026, 7, 19, 21, 0)) == "closed"    # Sunday pre-open
        assert fx.session_at(_utc(2026, 7, 20, 2)) == "tokyo"         # Monday

    def test_dst_shift_does_not_move_utc_windows(self, calendars) -> None:
        # US DST changed 2026-03-08; the boundary list is UTC — tagging must not move.
        fx = calendars["fx_default"]
        assert fx.session_at(_utc(2026, 3, 6, 13)) == fx.session_at(_utc(2026, 3, 10, 13)) == "overlap"

    def test_naive_timestamp_rejected(self, calendars) -> None:
        with pytest.raises(ValueError):
            calendars["fx_default"].session_at(datetime(2026, 7, 14, 8))


class TestExchangeCalendar:
    def test_open_holiday_weekend(self, calendars) -> None:
        cme = calendars["cme_metals"]
        assert cme.session_at(_utc(2026, 7, 15, 14)) == "exchange"   # Wednesday, in session
        assert cme.session_at(_utc(2026, 7, 15, 21)) == "closed"     # after close
        assert cme.session_at(_utc(2026, 7, 3, 14)) == "closed"      # declared holiday
        assert cme.session_at(_utc(2026, 7, 18, 14)) == "closed"     # Saturday

    def test_half_day_early_close_is_session_end(self, calendars) -> None:
        cme = calendars["cme_metals"]
        assert cme.session_at(_utc(2026, 11, 27, 14)) == "exchange"  # before early close
        assert cme.session_at(_utc(2026, 11, 27, 17, 30)) == "closed"  # after early close
