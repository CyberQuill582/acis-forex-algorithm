"""Japanese bank business days and gotobi days, 2011-2025 (GOTOBI's calendar, GAP-P12D-158).

Mental model:
  * A BANK DAY is a weekday that is neither a national holiday (the Cabinet Office's own list,
    `scripts/download_jp_holidays.py`) nor 31 December, 2 or 3 January, when Japanese banks close by
    the Banking Act's enforcement order (art. 5). The TTM fix at 09:55 JST is set only on bank days.
  * A GOTOBI DAY is a nominal settlement day of the month moved, when it is not a bank day, to the
    previous bank day (Bessho, Sugimoto & Suzuki 2023 §2, after Akiyama et al. 2021). The nominal days
    are 5, 10, 15, 20, 25 and a last day: `last="30"` is the 30th, or the month's last day when the
    month is shorter (Bessho's "5, 10, 15, 20, 25, and 30"); `last="month_end"` is the month's last
    calendar day, an alternative reading (Ito & Yamada 2017 use 5..30 AND the month's last trading day:
    not built; GAP-P12D-159 PCE-04). Two nominal days that move onto the same bank day count once.
  * Outside 2011-2025 the calendar refuses: an unvetted year can never decide a trade.
"""

from __future__ import annotations

import csv
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

FIRST, LAST = date(2011, 1, 1), date(2025, 12, 31)
NOMINAL = (5, 10, 15, 20, 25)
BANK_CLOSED = ((12, 31), (1, 2), (1, 3))


class CalendarRefused(Exception):
    """A day this calendar does not vouch for."""


def load_holidays(path: Path) -> frozenset[date]:
    with Path(path).open(encoding="utf-8") as f:
        return frozenset(date.fromisoformat(r["date"]) for r in csv.DictReader(f))


def is_bank_day(d: date, holidays: frozenset[date]) -> bool:
    if not FIRST <= d <= LAST:
        raise CalendarRefused(f"{d} is outside the vetted years {FIRST.year}-{LAST.year}")
    return d.weekday() < 5 and d not in holidays and (d.month, d.day) not in BANK_CLOSED


def previous_bank_day(d: date, holidays: frozenset[date]) -> date:
    while not is_bank_day(d, holidays):
        d -= timedelta(days=1)
    return d


def gotobi_days(first: date, last: date, holidays: frozenset[date], *, last_day: str = "30") -> list[date]:
    """Every gotobi bank day in [first, last], in order."""
    if last_day not in ("30", "month_end"):
        raise ValueError(f"last_day must be '30' or 'month_end', not {last_day!r}")
    out, y, m = set(), first.year, first.month
    while (y, m) <= (last.year, last.month):
        length = monthrange(y, m)[1]
        final = min(30, length) if last_day == "30" else length
        for n in (*NOMINAL, final):
            g = previous_bank_day(date(y, m, n), holidays)
            if first <= g <= last:
                out.add(g)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return sorted(out)
