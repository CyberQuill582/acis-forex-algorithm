"""The FX clock — the one DST-correct definition of the forex day (GAP-P12D-07).

The FX day rolls at 17:00 New York. That is 22:00 UTC under EST but 21:00 UTC under
EDT (≈ March–November), so a fixed-UTC anchor is an hour wrong for half the year.
The week closes at Friday's rollover and reopens at Sunday's.

Dependency-free and exact for 2007 onward (the US rule since the Energy Policy Act of
2005): daylight time runs from the second Sunday of March to the first Sunday of
November, switching at 02:00 local — so 17:00 on either switch day already uses the
new offset. Earlier dates raise rather than guess (ACIS data starts 2012).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc
ROLLOVER_LOCAL_HOUR = 17                     # 5pm New York
_EST, _EDT = timedelta(hours=-5), timedelta(hours=-4)


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def us_daylight_time(day: date) -> bool:
    """True if New York is on EDT at 17:00 local on `day`."""
    if day.year < 2007:
        raise ValueError(f"{day}: US DST rule before 2007 is not modelled")
    return _nth_sunday(day.year, 3, 2) <= day < _nth_sunday(day.year, 11, 1)


def rollover_utc(day: date) -> datetime:
    """The 17:00-New-York rollover on `day`, as a UTC instant."""
    offset = _EDT if us_daylight_time(day) else _EST
    return datetime(day.year, day.month, day.day, ROLLOVER_LOCAL_HOUR, tzinfo=UTC) - offset


def in_weekend(ts: datetime) -> bool:
    """True inside the closed window: Friday's rollover (inclusive) → Sunday's (exclusive)."""
    ts = ts.astimezone(UTC)
    wd = ts.weekday()                        # Mon=0 … Sun=6 (UTC date)
    if wd == 5:
        return True
    if wd == 4:
        return ts >= rollover_utc(ts.date())
    if wd == 6:
        return ts < rollover_utc(ts.date())
    return False


def business_rollovers(start: datetime, end: datetime) -> list[date]:
    """Mon–Fri dates whose rollover instant falls within (start, end]. Nothing rolls on
    Saturday or Sunday (the weekend is billed inside the week — carry.py)."""
    out = []
    day = start.astimezone(UTC).date() - timedelta(days=1)   # a UTC date may hold the prior NY day's roll
    last = end.astimezone(UTC).date() + timedelta(days=1)
    while day <= last:
        if day.weekday() < 5 and start < rollover_utc(day) <= end:
            out.append(day)
        day += timedelta(days=1)
    return out


def holds_through_weekend(start: datetime, end: datetime) -> bool:
    """True if a position open over (start, end] is held across a Friday close."""
    return any(d.weekday() == 4 for d in business_rollovers(start, end))
