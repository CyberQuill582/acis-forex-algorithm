"""OPEX's position (GAP-P12D-158; Stivers & Sun 2013): the OE week holds the month's third Friday, the book is
long from the last close before that week to its last close, the contrast nets a constant drift to zero, and
segments grade only their own days."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from tests.backtest.event_sim import EventResult
from tests.backtest.opex import oe_week, segments, target, third_friday


def _weekdays(a: date, b: date, closed=()) -> list[date]:
    return [a + timedelta(days=k) for k in range((b - a).days + 1)
            if (a + timedelta(days=k)).weekday() < 5 and a + timedelta(days=k) not in closed]


def test_the_oe_week_is_monday_to_friday_around_the_third_friday() -> None:
    assert third_friday(2024, 3) == date(2024, 3, 15)
    assert third_friday(2023, 9) == date(2023, 9, 15)                  # the 1st is a Friday
    assert third_friday(2025, 4) == date(2025, 4, 18)                  # Good Friday: expiry moves, the week stays
    assert [oe_week(d) for d in (date(2025, 4, 11), date(2025, 4, 14), date(2025, 4, 18), date(2025, 4, 21))] == [
        False, True, True, False]


def test_the_book_is_long_from_the_close_before_the_week_to_the_weeks_last_close() -> None:
    days = _weekdays(date(2025, 4, 7), date(2025, 4, 25), closed={date(2025, 4, 18)})
    t = target(days)
    held = {days[s].isoformat() for s in range(len(days)) if t[s] == 1.0}
    assert held == {"2025-04-11", "2025-04-14", "2025-04-15", "2025-04-16"}   # Friday's close through Wednesday's
    assert t[-1] == 0.0


def test_the_contrast_nets_a_constant_drift_to_zero() -> None:
    days = _weekdays(date(2019, 1, 2), date(2019, 12, 31))
    t = target(days, contrast=True)
    assert t[:-1].sum() == pytest.approx(0.0)
    assert set(np.round(t[:-1], 6)) == {1.0, round(t[:-1].min(), 6)} and t[:-1].min() < 0


def test_segments_grade_only_their_own_days() -> None:
    days = tuple(_weekdays(date(2014, 10, 1), date(2015, 3, 31)))
    daily = np.array([(0.002 if d < date(2015, 1, 1) else -0.002) + 0.001 * (k % 2) for k, d in enumerate(days)])
    daily[0] = -50.0                                                     # before graded_from: never read
    s = segments(EventResult(days, daily, (), ()), [date(2015, 1, 1)], days[1])
    assert s["2014-10-02..2014-12-31"] > 0 > s["2015-01-01..end"]
