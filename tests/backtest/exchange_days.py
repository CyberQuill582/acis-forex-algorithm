"""Exchange sessions at the month turns, 2012-01 to 2024-10 (D3's event harness, GAP-P12D-154).

Mental model:
  * D3 reads only a month's last two sessions (T-2, T-1) and the next month's first three (T+1..T+3),
    so each calendar here is complete only INSIDE ITS SCOPE: the last 7 and the first 10 days of a
    month. `is_session` refuses a day outside the scope or the years, so an unvetted day can never
    decide a window; `month_turn` refuses a turn whose sessions the scope cannot hold.
  * Index CFDs trade through exchange holidays (measured on the candles 2026-10-03: US500 on 4 July
    until 13:00 New York, JP225 on 2-3 January and through Golden Week, UK100 on bank holidays, EU50
    on 1 May), so a CFD's traded hours cannot say whether the cash market was open.
  * A session is a weekday in the exchange's own date that is not a holiday; half days are sessions.
    The rules are each exchange's published regular holidays that can fall inside the scope, plus
    SPECIAL one-off closures. Eurex (XEUR) stands for EU50's home: its cash index and futures share
    Eurex's trading days. Tokyo closes at 15:00 until 2024-11-04, so the years stop at 2024-10.
  * Verified on every in-scope day against an outside calendar library (GAP-P12D-154 records the run).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, time, timedelta
from functools import lru_cache

FIRST, LAST = date(2012, 1, 1), date(2024, 10, 31)
SCOPE_HEAD, SCOPE_TAIL = 10, 7            # the first 10 and the last 7 days of every month
SESSION = {"XNYS": ("America/New_York", time(9, 30), time(16, 0)),
           "XLON": ("Europe/London", time(8, 0), time(16, 30)),
           "XEUR": ("Europe/Berlin", time(9, 0), time(17, 30)),
           "XTKS": ("Asia/Tokyo", time(9, 0), time(15, 0)),
           "XASX": ("Australia/Sydney", time(10, 0), time(16, 0))}
SPECIAL = {"XNYS": {date(2012, 10, 29), date(2012, 10, 30), date(2018, 12, 5)},   # Sandy; G. H. W. Bush
           "XLON": {date(2023, 5, 8)},                                            # the coronation
           "XEUR": set(), "XASX": set(),
           "XTKS": {date(2019, 4, 30), date(2019, 5, 1), date(2019, 5, 2),        # the 2019 enthronement
                    date(2020, 10, 1)}}                                           # the TSE system outage


class CalendarRefused(Exception):
    """A day or month turn this calendar does not vouch for."""


def easter(y: int) -> date:
    """Gregorian Easter Sunday (the anonymous algorithm)."""
    a, (b, c) = y % 19, divmod(y, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7       # noqa: E741 (the algorithm's own name)
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(y, month, day + 1)


def _nth(y: int, m: int, weekday: int, n: int) -> date:
    first = date(y, m, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last(y: int, m: int, weekday: int) -> date:
    end = date(y, m, monthrange(y, m)[1])
    return end - timedelta(days=(end.weekday() - weekday) % 7)


def _observed(d: date, taken: set[date]) -> date:
    """A weekend holiday's substitute: the next weekday not already a holiday."""
    while d.weekday() >= 5 or d in taken:
        d += timedelta(days=1)
    return d


def _christmas_pair(y: int) -> set[date]:
    """Christmas and Boxing Day with the British/Australian substitute rule."""
    out: set[date] = set()
    for d in (date(y, 12, 25), date(y, 12, 26)):
        out.add(_observed(d, out))
    return out


def _japan(y: int) -> set[date]:
    out = {date(y, 1, 1), date(y, 1, 2), date(y, 1, 3), date(y, 12, 31), _nth(y, 1, 0, 2)}
    gw = {date(y, 5, 3), date(y, 5, 4), date(y, 5, 5)}
    out |= gw | ({date(y, 5, 6)} if any(d.weekday() == 6 for d in gw) else set())
    named = [date(y, 4, 29), date(y, 11, 3), date(y, 11, 23)]
    named.append(date(y, 9, int(23.2488 + 0.242194 * (y - 1980) - (y - 1980) // 4)))   # autumn equinox
    if y >= 2020:
        named.append(date(y, 2, 23))                                                  # the Emperor's birthday
    if y >= 2016:                                                                     # Mountain Day
        named.append({2020: date(2020, 8, 10), 2021: date(2021, 8, 8)}.get(y, date(y, 8, 11)))
    if y not in (2020, 2021):                                                         # Sports Day moved to July
        out.add(_nth(y, 10, 0, 2))
    for d in named:
        out.add(d)
        if d.weekday() == 6:
            out.add(_observed(d + timedelta(days=1), out))
    return out


@lru_cache(maxsize=None)
def holidays(exchange: str, y: int) -> frozenset[date]:
    gf, em = easter(y) - timedelta(days=2), easter(y) + timedelta(days=1)
    if exchange == "XNYS":
        jan1 = date(y, 1, 1)
        out = {gf, _last(y, 5, 0), _nth(y, 9, 0, 1), _nth(y, 11, 3, 4)}
        out |= {jan1 + timedelta(days=1)} if jan1.weekday() == 6 else ({jan1} if jan1.weekday() < 5 else set())
        for d in (date(y, 7, 4), date(y, 12, 25)):          # Saturday -> Friday, Sunday -> Monday
            out.add(d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d)
    elif exchange == "XLON":
        spring = {2012: {date(2012, 6, 4), date(2012, 6, 5)}, 2022: {date(2022, 6, 2), date(2022, 6, 3)}}
        out = {_observed(date(y, 1, 1), set()), gf, em, _last(y, 8, 0)} | _christmas_pair(y)
        out |= {date(2020, 5, 8)} if y == 2020 else {_nth(y, 5, 0, 1)}
        out |= spring.get(y, {_last(y, 5, 0)})
    elif exchange == "XEUR":
        out = {date(y, 1, 1), gf, em, date(y, 5, 1), date(y, 12, 24), date(y, 12, 25), date(y, 12, 26), date(y, 12, 31)}
    elif exchange == "XTKS":
        out = _japan(y)
    elif exchange == "XASX":
        out = {_observed(date(y, 1, 1), set()), _observed(date(y, 1, 26), set()), gf, em, date(y, 4, 25),
               _nth(y, 6, 0, 2)} | _christmas_pair(y)
    else:
        raise CalendarRefused(f"no calendar for exchange {exchange!r}")
    return frozenset(out | {d for d in SPECIAL[exchange] if d.year == y})


def in_scope(d: date) -> bool:
    return d.day <= SCOPE_HEAD or d.day > monthrange(d.year, d.month)[1] - SCOPE_TAIL


def is_session(exchange: str, d: date) -> bool:
    if not (FIRST <= d <= LAST and in_scope(d)):
        raise CalendarRefused(f"{d} is outside the calendar's scope (month turns, {FIRST}..{LAST})")
    return d.weekday() < 5 and d not in holidays(exchange, d.year)


def month_turn(exchange: str, y: int, m: int) -> tuple[date, date, date, date, date]:
    """(T-2, T-1, T+1, T+2, T+3): month (y, m)'s last two sessions, the next month's first three."""
    end = monthrange(y, m)[1]
    tail = [date(y, m, d) for d in range(end, end - SCOPE_TAIL, -1) if is_session(exchange, date(y, m, d))][:2]
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    head = [date(ny, nm, d) for d in range(1, SCOPE_HEAD + 1) if is_session(exchange, date(ny, nm, d))][:3]
    if len(tail) < 2 or len(head) < 3:
        raise CalendarRefused(f"{exchange} {y}-{m:02d}: the month turn's sessions fall outside the scope")
    return tail[1], tail[0], head[0], head[1], head[2]
