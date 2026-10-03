"""AUCTION's books: Treasury yields around note auctions (GAP-P12D-158; Lou, Yan & Zhang, "Anticipated and
Repeated Shocks in Liquid Markets", RFS 26(8) (2013); FMG DP684).

Mental model (each rule the paper's §IV and Table V; each departure declared in the kill test's header):
  * CURVE: the Treasury's daily par yields (`raw/<year>.csv`), one row per Treasury business day. A tenor's
    daily return on curve date d is carry y(d-1) x days/365 minus its modified duration at y(d-1) times the
    yield change (`rebal.par_duration`; the 6-month bill's is 0.5 / (1 + y/2)). No rolldown (declared).
  * EVENTS: fixed-rate nominal note auctions (no FRN, no TIPS) by term; a 10-year reopening is a 10-year
    auction. An auction on a day with no curve row is skipped with its reason.
  * POSITION on curve date d is what is held from close d to close d+1; overlapping windows add. PRE = the
    t closes before the auction's close (held into it), POST = the t closes after it.
  * BUTTERFLY (v1a, the paper's): long the duration-matched 6-month + 10-year wings and short the 2-year
    note (w6 + w10 = 1, w6 D6 + w10 D10 = D2 at the previous close), +1 PRE and -1 POST each 2-year auction.
  * OUTRIGHT (v1b, the micro yield futures' form): per auctioned tenor, long its yield (+1 per unit DV01,
    P&L = the yield change in bp / 1e4) PRE and short it POST; no carry (a yield future has none).
  * COST: each change of position pays `per_side` per unit (v1a: the paper's 1.46 bp round trip, halved).
    The P&L of curve date d lands on the 17:00 New York mark of d (`event_sim.marks`).
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from tests.backtest.event_sim import EventResult, marks
from tests.backtest.rebal import par_duration

TENORS = {"6m": "6 Mo", "2y": "2 Yr", "5y": "5 Yr", "10y": "10 Yr"}
YEARS = {"2y": 2, "5y": 5, "10y": 10}
TERM = {"2-Year": "2y", "5-Year": "5y", "10-Year": "10y"}           # plus "9-Year N-Month": 10-year reopenings


def load_curve(raw: Path) -> tuple[list[date], dict[str, np.ndarray]]:
    rows = {}
    for f in sorted(Path(raw).glob("*.csv")):
        with f.open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                vals = {k: r.get(col, "").strip() for k, col in TENORS.items()}
                if all(vals.values()):
                    rows[datetime.strptime(r["Date"], "%m/%d/%Y").date()] = {k: float(v) for k, v in vals.items()}
    days = sorted(rows)
    return days, {k: np.array([rows[d][k] for d in days]) for k in TENORS}


def auctions(path: Path, tenors: Sequence[str]) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {t: [] for t in tenors}
    with Path(path).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["floating_rate"] != "No" or r["inflation_index_security"] != "No":
                continue
            term = r["security_term"]
            tenor = TERM.get(term, "10y" if term.startswith("9-Year") else None)
            if tenor in out:
                out[tenor].append(date.fromisoformat(r["auction_date"]))
    return {t: sorted(set(v)) for t, v in out.items()}


def duration(tenor: str, y: np.ndarray) -> np.ndarray:
    if tenor == "6m":
        return 0.5 / (1 + y / 200)
    return np.array([par_duration(v / 100, YEARS[tenor]) for v in y])


def returns(days: Sequence[date], curve: Mapping[str, np.ndarray], tenor: str) -> np.ndarray:
    y = curve[tenor]
    gap = np.r_[0.0, np.diff([d.toordinal() for d in days])]
    return np.r_[0.0, y[:-1] / 100 * gap[1:] / 365 - duration(tenor, y[:-1]) * np.diff(y) / 100]


def windows(days: Sequence[date], events: Sequence[date], t: int) -> tuple[np.ndarray, list[dict]]:
    """+1 on the t closes before each event's close, -1 on the t closes from it; skipped events listed."""
    at, pos, skipped = {d: k for k, d in enumerate(days)}, np.zeros(len(days)), []
    for e in events:
        a = at.get(e)
        if a is None or a - t < 0 or a + t >= len(days):
            skipped.append({"auction": e.isoformat(), "reason": "no curve row" if a is None else "edge"})
            continue
        pos[a - t:a] += 1.0
        pos[a:a + t] -= 1.0
    return pos, skipped


def butterfly(days: Sequence[date], curve: Mapping[str, np.ndarray]) -> np.ndarray:
    """Each curve date's return on long the duration-matched 6m + 10y wings, short the 2-year."""
    d6, d2, d10 = (duration(k, curve[k]) for k in ("6m", "2y", "10y"))
    w10 = np.r_[0.0, ((d2 - d6) / (d10 - d6))[:-1]]
    r6, r2, r10 = (returns(days, curve, k) for k in ("6m", "2y", "10y"))
    return (1 - w10) * r6 + w10 * r10 - r2


def book(days: Sequence[date], pos: np.ndarray, daily_return: np.ndarray, per_side: float,
         start: date, graded_from: date, end: date) -> EventResult:
    """`pos[k]` is held from close k to close k+1, earning daily_return[k+1]; positions start at graded_from."""
    pos = np.where(np.array([graded_from <= d <= end for d in days]), pos, 0.0)
    pnl = np.r_[0.0, pos[:-1] * daily_return[1:]] - np.abs(np.diff(np.r_[0.0, pos])) * per_side
    grid = marks(start, end)
    at = {d: k for k, (d, _) in enumerate(grid)}
    daily = np.zeros(len(grid))
    for k, d in enumerate(days):
        if d in at:
            daily[at[d]] += pnl[k]
    return EventResult(tuple(d for d, _ in grid), daily, (), ())
