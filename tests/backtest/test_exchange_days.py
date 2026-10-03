"""The month-turn exchange calendars D3 reads (GAP-P12D-154): each exchange's own holidays, never the
CFD's hours, and a refusal outside the vetted scope."""

from __future__ import annotations

from datetime import date, time

import pytest

from tests.backtest.exchange_days import CalendarRefused, easter, hours, is_session, month_turn


def test_easter_matches_the_published_dates() -> None:
    assert [easter(y) for y in (2012, 2016, 2019, 2024)] == [date(2012, 4, 8), date(2016, 3, 27),
                                                            date(2019, 4, 21), date(2024, 3, 31)]


@pytest.mark.parametrize("exchange, closed", [
    ("XNYS", [date(2021, 5, 31), date(2019, 7, 4), date(2020, 9, 7), date(2012, 10, 29), date(2018, 12, 5),
              date(2017, 1, 2), date(2022, 12, 26), date(2018, 3, 30)]),
    ("XLON", [date(2019, 5, 6), date(2020, 5, 8), date(2012, 6, 4), date(2012, 6, 5), date(2022, 6, 3),
              date(2015, 8, 31), date(2021, 12, 27), date(2021, 12, 28), date(2023, 5, 8)]),
    ("XEUR", [date(2019, 5, 1), date(2019, 12, 31), date(2019, 12, 26), date(2018, 4, 2)]),
    ("XTKS", [date(2019, 1, 2), date(2019, 1, 3), date(2019, 4, 30), date(2019, 5, 2), date(2019, 5, 6),
              date(2018, 1, 8), date(2018, 9, 24), date(2021, 8, 9), date(2020, 10, 1), date(2020, 2, 24),
              date(2018, 12, 31)]),
    ("XASX", [date(2021, 1, 26), date(2020, 1, 27), date(2019, 4, 25), date(2019, 6, 10), date(2020, 12, 28)]),
])
def test_each_exchange_closes_on_its_own_holidays(exchange, closed) -> None:
    """Measured 2026-10-03: the CFDs trade on most of these days, so only the calendar can close them."""
    assert [d for d in closed if is_session(exchange, d)] == []


@pytest.mark.parametrize("exchange, open_", [
    ("XNYS", [date(2021, 12, 31), date(2019, 11, 29), date(2019, 7, 3)]),     # Jan 1 on a Saturday; half days
    ("XLON", [date(2020, 5, 4), date(2012, 5, 28), date(2022, 5, 30)]),       # the moved bank holidays
    ("XEUR", [date(2015, 5, 25), date(2018, 10, 3), date(2017, 10, 31)]),     # Xetra shut, Eurex and Paris open
    ("XASX", [date(2021, 4, 26), date(2020, 12, 31)]),                        # no Anzac substitute
])
def test_the_exchange_is_open_where_a_neighbour_or_a_moved_holiday_is_not(exchange, open_) -> None:
    assert all(is_session(exchange, d) for d in open_)


def test_a_month_turn_is_t_minus_2_to_t_plus_3_on_the_exchanges_own_sessions() -> None:
    assert month_turn("XNYS", 2021, 5) == (date(2021, 5, 27), date(2021, 5, 28), date(2021, 6, 1),
                                           date(2021, 6, 2), date(2021, 6, 3))          # Memorial Day skipped
    assert month_turn("XTKS", 2019, 4) == (date(2019, 4, 25), date(2019, 4, 26), date(2019, 5, 7),
                                           date(2019, 5, 8), date(2019, 5, 9))           # Golden Week 2019
    assert month_turn("XEUR", 2019, 12) == (date(2019, 12, 27), date(2019, 12, 30), date(2020, 1, 2),
                                            date(2020, 1, 3), date(2020, 1, 6))
    assert month_turn("XTKS", 2017, 12)[2:] == (date(2018, 1, 4), date(2018, 1, 5), date(2018, 1, 9))


def test_a_day_outside_the_vetted_scope_or_years_is_refused() -> None:
    with pytest.raises(CalendarRefused, match="scope"):
        is_session("XNYS", date(2019, 7, 15))                  # mid-month: no rule vets it
    with pytest.raises(CalendarRefused, match="scope"):
        is_session("XTKS", date(2026, 1, 5))                   # past the vetted years
    with pytest.raises(CalendarRefused, match="scope"):
        month_turn("XNYS", 2025, 12)                            # the next month is past the calendar
    with pytest.raises(CalendarRefused, match="no calendar"):
        is_session("XHKG", date(2019, 7, 1))


def test_the_2024_25_extension_keeps_its_one_off_closures_and_tokyos_longer_session() -> None:
    """Vetted against exchange_calendars 4.13.2 on every in-scope day of 2024-11..2025-12 (GAP-P12D-158)."""
    assert not is_session("XNYS", date(2025, 1, 9))            # the national day of mourning for J. Carter
    assert not is_session("XTKS", date(2025, 11, 24))          # Labour Thanksgiving, observed from a Sunday
    assert not is_session("XTKS", date(2025, 2, 24))           # the Emperor's birthday, observed
    assert not is_session("XASX", date(2025, 1, 27))           # Australia Day, observed
    assert is_session("XTKS", date(2024, 11, 5))
    assert hours("XTKS", date(2024, 11, 1))[2] == time(15, 0) and hours("XTKS", date(2024, 11, 5))[2] == time(15, 30)
