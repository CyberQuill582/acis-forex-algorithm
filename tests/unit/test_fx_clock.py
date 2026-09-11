"""The FX clock is DST-correct (GAP-P12D-07): 17:00 New York, pinned to real
US daylight-time transition dates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from core.data.fx_clock import (business_rollovers, holds_through_weekend, in_weekend,
                                rollover_utc, us_daylight_time)

UTC = timezone.utc


@pytest.mark.parametrize("start, end", [
    (date(2012, 3, 11), date(2012, 11, 4)),      # 2nd Sun Mar / 1st Sun Nov
    (date(2020, 3, 8), date(2020, 11, 1)),
    (date(2025, 3, 9), date(2025, 11, 2)),
])
def test_daylight_time_switches_on_the_real_us_dates(start, end) -> None:
    day = timedelta(days=1)
    assert not us_daylight_time(start - day)
    assert us_daylight_time(start)                # 17:00 on the switch day is already EDT
    assert us_daylight_time(end - day)
    assert not us_daylight_time(end)


def test_rollover_is_21_utc_in_summer_and_22_utc_in_winter() -> None:
    assert rollover_utc(date(2025, 7, 15)) == datetime(2025, 7, 15, 21, tzinfo=UTC)
    assert rollover_utc(date(2025, 1, 15)) == datetime(2025, 1, 15, 22, tzinfo=UTC)
    with pytest.raises(ValueError):
        rollover_utc(date(2006, 7, 3))            # before the modelled rule


def test_summer_weekend_boundaries_follow_new_york() -> None:
    # July 2025: Friday close and Sunday open are 21:00 UTC, not 22:00
    assert not in_weekend(datetime(2025, 7, 18, 20, 59, tzinfo=UTC))    # Fri, still open
    assert in_weekend(datetime(2025, 7, 18, 21, 30, tzinfo=UTC))        # Fri, closed at 21:00
    assert in_weekend(datetime(2025, 7, 19, 12, tzinfo=UTC))            # Saturday
    assert in_weekend(datetime(2025, 7, 20, 20, 59, tzinfo=UTC))        # Sun, not yet open
    assert not in_weekend(datetime(2025, 7, 20, 21, 30, tzinfo=UTC))    # Sun, open at 21:00
    # January 2026: the same instants in winter sit an hour later
    assert not in_weekend(datetime(2026, 1, 2, 21, 30, tzinfo=UTC))     # Fri, open until 22:00
    assert in_weekend(datetime(2026, 1, 4, 21, 30, tzinfo=UTC))         # Sun, opens 22:00


def test_business_rollovers_are_weekdays_at_the_real_instant() -> None:
    # opened Tue 21:30 UTC in July — AFTER that day's 21:00 roll, so Tue does not count
    got = business_rollovers(datetime(2025, 7, 15, 21, 30, tzinfo=UTC),
                             datetime(2025, 7, 17, 21, 30, tzinfo=UTC))
    assert got == [date(2025, 7, 16), date(2025, 7, 17)]
    # Fri 12:00 → Mon 23:00 in January: Fri + Mon only, never Sat/Sun
    got = business_rollovers(datetime(2026, 1, 9, 12, tzinfo=UTC),
                             datetime(2026, 1, 12, 23, tzinfo=UTC))
    assert got == [date(2026, 1, 9), date(2026, 1, 12)]


def test_holds_through_weekend_only_when_a_friday_close_is_held() -> None:
    assert holds_through_weekend(datetime(2025, 7, 18, 10, tzinfo=UTC),
                                 datetime(2025, 7, 21, 10, tzinfo=UTC))
    assert not holds_through_weekend(datetime(2025, 7, 18, 10, tzinfo=UTC),
                                     datetime(2025, 7, 18, 20, 59, tzinfo=UTC))   # out before close
