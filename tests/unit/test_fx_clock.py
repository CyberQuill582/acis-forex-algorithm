"""The FX clock is DST-correct (GAP-P12D-07): 17:00 New York, pinned to real
US daylight-time transition dates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from core.data.fx_clock import (business_rollovers, holds_through_weekend, in_weekend,
                                local_to_utc, rollover_utc, to_local, trading_day,
                                uk_summer_time, us_daylight_time)

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


@pytest.mark.parametrize("start, end", [(date(2012, 3, 25), date(2012, 10, 28)),
                                        (date(2025, 3, 30), date(2025, 10, 26))])
def test_uk_summer_time_switches_on_the_real_dates(start, end) -> None:
    day = timedelta(days=1)
    assert not uk_summer_time(start - day) and uk_summer_time(start)
    assert uk_summer_time(end - day) and not uk_summer_time(end)


def test_each_centre_opens_at_its_own_local_time_all_year() -> None:
    jan, jul = date(2025, 1, 15), date(2025, 7, 15)
    assert local_to_utc(jan, "08:00", "Europe/London") == datetime(2025, 1, 15, 8, tzinfo=UTC)
    assert local_to_utc(jul, "08:00", "Europe/London") == datetime(2025, 7, 15, 7, tzinfo=UTC)
    assert local_to_utc(jan, "08:00", "America/New_York") == datetime(2025, 1, 15, 13, tzinfo=UTC)
    assert local_to_utc(jul, "08:00", "America/New_York") == datetime(2025, 7, 15, 12, tzinfo=UTC)
    assert local_to_utc(jul, "09:00", "Asia/Tokyo") == datetime(2025, 7, 15, 0, tzinfo=UTC)
    assert local_to_utc(jul, "08:30", "America/Chicago") == datetime(2025, 7, 15, 13, 30, tzinfo=UTC)
    # the gap between the two US/UK switch dates: US already on EDT, London still GMT
    gap = date(2025, 3, 20)
    assert local_to_utc(gap, "08:00", "America/New_York") == datetime(2025, 3, 20, 12, tzinfo=UTC)
    assert local_to_utc(gap, "08:00", "Europe/London") == datetime(2025, 3, 20, 8, tzinfo=UTC)
    with pytest.raises(ValueError):
        local_to_utc(jan, "08:00", "Mars/Olympus")


def test_to_local_round_trips() -> None:
    for zone in ("America/New_York", "Europe/London", "Asia/Tokyo", "America/Chicago", "UTC"):
        for d in (date(2025, 1, 15), date(2025, 7, 15)):
            ts = local_to_utc(d, "08:00", zone)
            assert to_local(ts, zone) == datetime(d.year, d.month, d.day, 8, 0)


def test_trading_day_starts_at_the_real_rollover() -> None:
    # summer: Tue 21:30 UTC is already Tuesday's trading day (roll at 21:00)
    assert trading_day(datetime(2025, 7, 15, 21, 30, tzinfo=UTC)) == date(2025, 7, 15)
    assert trading_day(datetime(2025, 7, 15, 20, 59, tzinfo=UTC)) == date(2025, 7, 14)
    # winter: 21:30 UTC is still the previous trading day (roll at 22:00)
    assert trading_day(datetime(2026, 1, 13, 21, 30, tzinfo=UTC)) == date(2026, 1, 12)
    assert trading_day(datetime(2026, 1, 13, 22, 0, tzinfo=UTC)) == date(2026, 1, 13)


def test_config_zones_are_exactly_the_modelled_zones() -> None:
    # config/calendars.py's Zone literal must never name a zone fx_clock cannot resolve
    from typing import get_args
    from config.calendars import Zone
    from core.data import fx_clock
    assert set(get_args(Zone)) == set(fx_clock._ZONES)


def test_next_local_is_strictly_after() -> None:
    from core.data.fx_clock import at_local_minute, next_local
    jul = datetime(2025, 7, 15, 21, 0, tzinfo=UTC)                  # 17:00 EDT exactly
    assert at_local_minute(jul, "America/New_York", "17:00")
    assert next_local(jul, "America/New_York", "17:00") == datetime(2025, 7, 16, 21, tzinfo=UTC)
    assert next_local(jul, "Asia/Tokyo", "09:00") == datetime(2025, 7, 16, 0, tzinfo=UTC)
