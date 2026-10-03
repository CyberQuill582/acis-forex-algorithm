"""GOTOBI's calendar (GAP-P12D-158): bank days close on weekends, national holidays and 31 Dec - 3 Jan;
a gotobi day that is not a bank day moves to the previous one, counted once; the two last-day rules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.backtest.jp_days import CalendarRefused, gotobi_days, is_bank_day

GW_2019 = frozenset(date(2019, 4, 29) + timedelta(days=k) for k in range(8))     # 4-29 .. 5-06


def test_a_bank_day_is_a_weekday_off_the_holiday_list_and_outside_the_new_year_closure() -> None:
    hol = frozenset({date(2021, 1, 1), date(2021, 11, 23)})
    assert is_bank_day(date(2021, 11, 22), hol) and not is_bank_day(date(2021, 11, 23), hol)
    assert not is_bank_day(date(2021, 11, 27), hol)                       # a Saturday
    for d in (date(2020, 12, 31), date(2021, 1, 1), date(2020, 1, 2), date(2020, 1, 3)):     # Thu, Fri, Thu, Fri
        assert not is_bank_day(d, hol)
    assert is_bank_day(date(2021, 1, 4), hol)
    with pytest.raises(CalendarRefused):
        is_bank_day(date(2010, 12, 30), hol)


def test_a_gotobi_day_off_the_bank_calendar_moves_back_and_two_that_meet_count_once() -> None:
    days = gotobi_days(date(2019, 4, 1), date(2019, 5, 31), GW_2019)
    # 4-30 (holiday) and 5-05 (holiday) both move to Friday 4-26; 5-25 (Saturday) to 5-24
    assert days == [date(2019, 4, 5), date(2019, 4, 10), date(2019, 4, 15), date(2019, 4, 19),
                    date(2019, 4, 25), date(2019, 4, 26), date(2019, 5, 10), date(2019, 5, 15),
                    date(2019, 5, 20), date(2019, 5, 24), date(2019, 5, 30)]


def test_the_30th_rule_falls_to_february_end_and_the_month_end_rule_takes_the_31st() -> None:
    none = frozenset()
    feb = gotobi_days(date(2023, 2, 1), date(2023, 2, 28), none)
    assert feb[-1] == date(2023, 2, 28)
    march_30 = gotobi_days(date(2023, 3, 1), date(2023, 3, 31), none)
    march_end = gotobi_days(date(2023, 3, 1), date(2023, 3, 31), none, last_day="month_end")
    assert march_30[-1] == date(2023, 3, 30) and march_end[-1] == date(2023, 3, 31)
    with pytest.raises(ValueError):
        gotobi_days(date(2023, 3, 1), date(2023, 3, 31), none, last_day="31")
