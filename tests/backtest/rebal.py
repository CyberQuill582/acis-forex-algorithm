"""REBAL's signals and position (Harvey, Mazzoleni & Melone, "The Unintended Consequences of Rebalancing",
NBER w33554 / SSRN 5122748, version 2026-01-14, Appendix B and §4; GAP-P12D-157).

Mental model (each equation the paper's; each departure declared):
  * Two simulated 60/40 portfolios drift with daily S&P 500 and 10-year note returns:
    w' = w(1 + rs) / (w(1 + rs) + (1 - w)(1 + rb)). THRESHOLD(delta) resets to 60% the day after its
    weight is at least delta from target (B.1); CALENDAR resets the day after each month's last
    business day (B.2). Each signal is the drifted weight - 60% at the day's close.
  * The Threshold signal averages delta = 0%, 0.1%, ..., 2.5% (eq. 2). The position for the NEXT day
    is the mean of -Threshold/1.5% and the Calendar term: sign(-Calendar) in the month's last 5
    business days, sign(Calendar at day -4) on the next month's first business day, else 0 (§4).
  * Business days are the S&P closes' dates (NYSE sessions). Declared: S&P CASH closes stand in for
    E-mini futures returns, and the note futures' return is the 7-year par yield's move times that par
    note's modified duration (the 10-year contract's cheapest-to-deliver is a 6.5-7.75-year note);
    carry and the futures basis are omitted (under 1 bp a day). A missing yield repeats the last one.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping, Sequence

import numpy as np

TARGET = 0.60
DELTAS = tuple(i / 1000 for i in range(26))       # 0%, 0.1%, ..., 2.5%
THRESHOLD_SCALE = 0.015
WEEK4, REVERSAL_DAY = 5, 4


def drift(w: float, rs: float, rb: float) -> float:
    return w * (1 + rs) / (w * (1 + rs) + (1 - w) * (1 + rb))


def par_duration(y: float, years: int = 7) -> float:
    """Modified duration of a semi-annual par bond at yield y (a fraction)."""
    return (1 - (1 + y / 2) ** (-2 * years)) / y if y > 1e-9 else float(years)


def note_returns(days: Sequence[date], y7: Mapping[date, float]) -> np.ndarray:
    """The note futures' daily return on each business day from the 7-year par yield (in percent)."""
    out, last = np.zeros(len(days)), None
    for k, d in enumerate(days):
        y = y7.get(d, last)
        if y is not None and last is not None:
            out[k] = -par_duration(last / 100) * (y - last) / 100
        last = y
    return out


def threshold_signal(rs: np.ndarray, rb: np.ndarray) -> np.ndarray:
    out = np.zeros(len(rs))
    for delta in DELTAS:
        w = TARGET
        for k in range(len(rs)):
            drifted = drift(w, rs[k], rb[k])
            out[k] += drifted - TARGET
            w = TARGET if abs(w - TARGET) >= delta else drifted
    return out / len(DELTAS)


def month_ends(days: Sequence[date]) -> np.ndarray:
    """True on each month's last business day of the grid; the grid's final day only if the next
    weekday starts a new month (a grid ending mid-month has no month end there)."""
    after = lambda d: d + timedelta(days=3 if d.weekday() == 4 else 1)        # noqa: E731
    nxt = [*days[1:], after(days[-1])] if len(days) else []
    return np.array([(n.year, n.month) != (d.year, d.month) for d, n in zip(days, nxt)])


def calendar_signal(rs: np.ndarray, rb: np.ndarray, last: np.ndarray) -> np.ndarray:
    out, w = np.zeros(len(rs)), TARGET
    for k in range(len(rs)):
        drifted = drift(w, rs[k], rb[k])
        out[k] = drifted - TARGET
        w = TARGET if k > 0 and last[k - 1] else drifted
    return out


def position(days: Sequence[date], threshold: np.ndarray, calendar: np.ndarray) -> np.ndarray:
    """The paper's w_t, held from day t's close to day t+1's."""
    last = month_ends(days)
    to_end, after = np.zeros(len(days), int), 10 ** 6   # business days to the month's end: 1 on the last;
    for k in range(len(days) - 1, -1, -1):              # a trailing partial month never reaches week 4
        to_end[k] = after = 1 if last[k] else after + 1
    cal = np.zeros(len(days))
    for k in range(len(days)):
        if to_end[k] <= WEEK4:
            cal[k] = np.sign(-calendar[k])
        elif k > 0 and last[k - 1] and k >= REVERSAL_DAY:
            cal[k] = np.sign(calendar[k - REVERSAL_DAY])
    return 0.5 * (-threshold / THRESHOLD_SCALE + cal)


def signals(days: Sequence[date], spx: Mapping[date, float], y7: Mapping[date, float]) -> dict[str, np.ndarray]:
    """Everything REBAL reads, on the S&P's business days (`days` must all have an S&P close)."""
    closes = np.array([spx[d] for d in days])
    rs = np.r_[0.0, closes[1:] / closes[:-1] - 1.0]
    rb = note_returns(days, y7)
    thr, cal = threshold_signal(rs, rb), calendar_signal(rs, rb, month_ends(days))
    return {"rs": rs, "rb": rb, "threshold": thr, "calendar": cal, "position": position(days, thr, cal)}
