"""The FX clock — the one DST-correct definition of market time (GAP-P12D-07/10).

Every market time in ACIS is declared in its centre's LOCAL time and resolved to UTC
per date here: the FX day rolls at 17:00 New York (22:00 UTC under EST, 21:00 UTC
under EDT), London opens 08:00 London time, Tokyo 09:00 Tokyo time. A fixed-UTC
constant is an hour wrong for half of every year.

Dependency-free and exact for the ACIS data window (2012 on): the US rule since 2007
(second Sunday of March → first Sunday of November, 02:00 local) for New York and
Chicago; the UK/EU rule since 1996 (last Sunday of March → last Sunday of October,
01:00 UTC) for London; no DST in Tokyo. Rules resolve by LOCAL DATE, which is exact
for every declared market time (all fall outside the 01:00–02:00 switch hour on the
switch Sunday). Earlier years raise rather than guess.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc
ROLLOVER = ("America/New_York", "17:00")               # the FX day boundary
_ZONES = {                                             # zone -> (standard offset h, DST rule)
    "UTC": (0, None), "Asia/Tokyo": (9, None), "Europe/London": (0, "uk"),
    "America/New_York": (-5, "us"), "America/Chicago": (-6, "us"),
}


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def _last_sunday(year: int, month: int) -> date:
    last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def us_daylight_time(day: date) -> bool:
    """True if US zones are on daylight time for local business hours on `day`."""
    if day.year < 2007:
        raise ValueError(f"{day}: US DST rule before 2007 is not modelled")
    return _nth_sunday(day.year, 3, 2) <= day < _nth_sunday(day.year, 11, 1)


def uk_summer_time(day: date) -> bool:
    """True if London is on BST for local business hours on `day`."""
    if day.year < 1996:
        raise ValueError(f"{day}: UK/EU DST rule before 1996 is not modelled")
    return _last_sunday(day.year, 3) <= day < _last_sunday(day.year, 10)


_DST_RULES = {"us": us_daylight_time, "uk": uk_summer_time}


def utc_offset(day: date, zone: str) -> timedelta:
    """The zone's UTC offset for local business hours on local date `day`."""
    try:
        std, rule = _ZONES[zone]
    except KeyError:
        raise ValueError(f"unknown market zone {zone!r}; declared: {sorted(_ZONES)}") from None
    dst = rule is not None and _DST_RULES[rule](day)
    return timedelta(hours=std + (1 if dst else 0))


def local_to_utc(day: date, hhmm: str, zone: str) -> datetime:
    """Local wall time `hhmm` on local date `day` in `zone`, as a UTC instant."""
    hh, mm = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=UTC) - utc_offset(day, zone)


def to_local(ts: datetime, zone: str) -> datetime:
    """The naive local wall time in `zone` at UTC instant `ts`."""
    ts = ts.astimezone(UTC).replace(tzinfo=None)
    guess = (ts + utc_offset(ts.date(), zone)).date()    # settle the local date first
    return ts + utc_offset(guess, zone)


def at_local_minute(ts: datetime, zone: str, hhmm: str) -> bool:
    """True if `ts` falls in the minute whose local wall time in `zone` is `hhmm`."""
    return to_local(ts, zone).strftime("%H:%M") == hhmm


def next_local(ts: datetime, zone: str, hhmm: str) -> datetime:
    """The first UTC instant strictly after `ts` at local wall time `hhmm` in `zone`."""
    day = to_local(ts, zone).date()
    today = local_to_utc(day, hhmm, zone)
    return today if today > ts else local_to_utc(day + timedelta(days=1), hhmm, zone)


def last_local(ts: datetime, zone: str, hhmm: str) -> datetime:
    """The latest UTC instant at or before `ts` at local wall time `hhmm` in `zone`."""
    day = to_local(ts, zone).date()
    today = local_to_utc(day, hhmm, zone)
    return today if today <= ts else local_to_utc(day - timedelta(days=1), hhmm, zone)


def rollover_utc(day: date) -> datetime:
    """The 17:00-New-York rollover on `day`, as a UTC instant."""
    return local_to_utc(day, ROLLOVER[1], ROLLOVER[0])


def trading_day(ts: datetime) -> date:
    """The FX trading day `ts` belongs to, labelled by the date of the rollover that
    opened it (a day runs rollover → rollover, so a loss straddling 00:00 UTC stays in
    one trading day)."""
    ts = ts.astimezone(UTC)
    return ts.date() if ts >= rollover_utc(ts.date()) else ts.date() - timedelta(days=1)


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
