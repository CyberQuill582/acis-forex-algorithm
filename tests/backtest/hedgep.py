"""HEDGEP's signal: speculators pay hedgers for liquidity (FACTORY, GAP-P12D-158; Kang, Rouwenhorst & Tang, "A
tale of two premiums", JF 75(1) (2020) 377-417: a commodity hedgers bought last week outperforms in the
weeks after; 26 commodities, 1994-2014; panel slope 8.9 bp a week per 3.5% of open interest).

Mental model:
  * Q(k) = (commercial net long(k) - net long(k-1)) / open interest(k-1), the hedgers' net trading in
    report k (as of a Tuesday). z(k) = Q(k) over the sd of the 52 Q's ending at k (26 needed).
  * RELEASE: the CFTC publishes report k after 15:30 Eastern on the Friday of its as-of week; a federal
    holiday or closure from the as-of day to that Friday moves it to the next business Monday (the
    CFTC's schedule, "delayed release date due to a federal holiday"). It is usable at the 17:00 New
    York decision of its release day. Reports measured during the 2013 and 2018-19 shutdowns, released
    late in catch-up batches, are never used (declared).
  * FORECAST on each decision day: 10 x clip(z, -2, 2) of the latest usable report, if it is at most
    STALE_DAYS old; otherwise flat. The paper sorts 26 commodities against each other; this is the
    time-series form on one market (declared).
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np

WINDOW, MIN_WINDOW, CAP, STALE_DAYS = 52, 26, 2.0, 14
SHUTDOWN = ((date(2013, 10, 1), date(2013, 11, 26)), (date(2018, 12, 24), date(2019, 2, 26)))
CLOSURES = frozenset({date(2012, 10, 29), date(2012, 10, 30), date(2012, 12, 24), date(2014, 12, 26),
                      date(2015, 12, 24), date(2018, 12, 5), date(2018, 12, 24), date(2019, 12, 24),
                      date(2020, 12, 24), date(2025, 1, 9)})            # executive orders, mourning, Sandy


def _nth(y: int, m: int, weekday: int, n: int) -> date:
    first = date(y, m, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _observed(d: date) -> date:
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def federal_holidays(y: int) -> frozenset[date]:
    fixed = [date(y, 1, 1), date(y, 7, 4), date(y, 11, 11), date(y, 12, 25), date(y + 1, 1, 1)]
    if y >= 2021:
        fixed.append(date(y, 6, 19))
    last_may = date(y, 5, 31) - timedelta(days=date(y, 5, 31).weekday())
    moving = [_nth(y, 1, 0, 3), _nth(y, 2, 0, 3), last_may, _nth(y, 9, 0, 1), _nth(y, 10, 0, 2), _nth(y, 11, 3, 4)]
    return frozenset({_observed(d) for d in fixed} | set(moving) | {d for d in CLOSURES if d.year == y})


def _holiday(d: date) -> bool:
    return d in federal_holidays(d.year) or d in federal_holidays(d.year - 1)


def release(as_of: date) -> date | None:
    """The day report `as_of` became public, by 15:30 Eastern; None for a shutdown report."""
    if any(a <= as_of <= b for a, b in SHUTDOWN):
        return None
    friday = as_of + timedelta(days=(4 - as_of.weekday()) % 7)
    if not any(_holiday(as_of + timedelta(days=k)) for k in range((friday - as_of).days + 1)):
        return friday
    d = friday + timedelta(days=3)
    while _holiday(d) or d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def load(path: Path) -> list[tuple[date, int, int, int]]:
    with Path(path).open(encoding="utf-8") as f:
        return [(date.fromisoformat(r["as_of"]), int(r["open_interest"]), int(r["commercial_long"]),
                 int(r["commercial_short"])) for r in csv.DictReader(f)]


def zscores(reports: Sequence[tuple[date, int, int, int]]) -> list[tuple[date, float, float]]:
    """(as_of, Q, z) for every report after the first; z NaN until MIN_WINDOW Q's exist."""
    q = [((l1 - s1) - (l0 - s0)) / oi0 for (_, oi0, l0, s0), (_, _, l1, s1) in zip(reports, reports[1:])]
    out = []
    for k, (d, *_) in enumerate(reports[1:]):
        past = np.asarray(q[max(0, k - WINDOW + 1):k + 1])
        sd = float(np.std(past, ddof=1)) if len(past) >= MIN_WINDOW else 0.0
        out.append((d, q[k], q[k] / sd if sd > 0 else np.nan))
    return out


def panel(days: Sequence[date], reports: Sequence[tuple[date, int, int, int]]) -> np.ndarray:
    """forecast[t] on each decision day from the latest report public by then and fresh."""
    usable = sorted((r, d, z) for d, _, z in zscores(reports) if (r := release(d)) is not None)
    out, k = np.full(len(days), np.nan), -1
    for t, day in enumerate(days):
        while k + 1 < len(usable) and usable[k + 1][0] <= day:
            k += 1
        if k >= 0 and (day - usable[k][1]).days <= STALE_DAYS and np.isfinite(usable[k][2]):
            out[t] = 10.0 * float(np.clip(usable[k][2], -CAP, CAP))
    return out
