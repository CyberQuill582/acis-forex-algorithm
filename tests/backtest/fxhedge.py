"""FXHEDGE's book: currencies into the month-end London 4 pm fix, against their equity markets' month
(GAP-P12D-158; Melvin & Prins, "Equity hedging and exchange rates at the London 4 p.m. fix", JFM 22 (2015)).

Mental model (each rule the paper's §5.1 eq. (3); each departure declared in the kill test's header):
  * FIX DAY T: the month's last weekday (WM/Reuters publishes every weekday but 25 Dec and 1 Jan).
  * SIGNAL: each country's index return from the cash close of its exchange's first session of the month
    to the close of its last session before T (`event_sim.Leg.anchor` on QUOTED hours, GAP-P12D-156),
    demeaned across the countries that have one. A country missing either anchor sits the month out;
    fewer than MIN_COUNTRIES skips the month. Every anchor hour ends before T begins anywhere in scope.
  * POSITION: currency c holds -SCALE x its demeaned return against the USD. The USD is itself a country,
    so the weights sum to zero: EUR_USD, GBP_USD and AUD_USD carry their currency's weight, USD_JPY minus JPY's.
  * BOOK: each pair from the ENTRY label to the EXIT label (London wall times), at the last tick at or before
    each (`event_window.window_prices`), each side paying THE C8 model at its tick's spread on |weight|.
    The P&L lands on the first 17:00 New York mark at or after the exit. A missing price skips that pair-day;
    so does, under the optional COST GATE, a predicted move (BETA x |return|) below the entry's round trip.
  * CONTROL (context, never a verdict; the paper's §5.2 control days): the same rules on the same weekday a
    week before T. Its sessions come from `exchange_days.holidays`, which is vetted only at month turns.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.event_daily import quoted
from tests.backtest.event_intraday import Session
from tests.backtest.event_sim import EventResult, Leg, marks
from tests.backtest.exchange_days import CalendarRefused, holidays, is_session
from tests.backtest.rsim import annual_sharpe

LONDON = "Europe/London"
COUNTRY = {"USD": ("US500", "XNYS"), "EUR": ("EU50", "XEUR"), "GBP": ("UK100", "XLON"),
           "JPY": ("JP225", "XTKS"), "AUD": ("AUS200", "XASX")}
PAIR = {"EUR": ("EUR_USD", 1.0), "GBP": ("GBP_USD", 1.0), "AUD": ("AUD_USD", 1.0), "JPY": ("USD_JPY", -1.0)}
MIN_COUNTRIES, SCALE = 3, 25.0           # SCALE only sizes the book: Sharpe and HAC t do not depend on it
BETA = 0.0142                            # the paper's panel slope, eq. (4): 10% outperformance, 14 bp into the fix
REFORM = date(2015, 2, 15)               # WM/Reuters widened the fix window to 5 minutes (FSB 2014)


def fix_day(y: int, m: int) -> date:
    d = date(y, m, monthrange(y, m)[1])
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d


def fix_days(start: date, end: date) -> list[date]:
    out, (y, m) = [], (start.year, start.month)
    while (y, m) <= (end.year, end.month):
        if start <= (d := fix_day(y, m)) <= end:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _session(exchange: str, d: date, vetted: bool) -> bool:
    return is_session(exchange, d) if vetted else d.weekday() < 5 and d not in holidays(exchange, d.year)


def window(exchange: str, day: date, vetted: bool = True) -> tuple[date, date]:
    """(the month's first session, the last session before `day`) on `exchange`'s calendar."""
    first, last = date(day.year, day.month, 1), day - timedelta(days=1)
    while not _session(exchange, first, vetted):
        first += timedelta(days=1)
    while not _session(exchange, last, vetted):
        last -= timedelta(days=1)
    return first, last


def legs(hourly: Mapping[str, Hourly]) -> dict[str, Leg]:
    return {name: Leg(quoted(h), np.zeros(1, np.int64)) for name, h in hourly.items()}


def signal(index_legs: Mapping[str, Leg], day: date, vetted: bool = True) -> tuple[dict[str, float], dict[str, str]]:
    """(each currency's demeaned equity return, why each missing country sat out)."""
    raw, why = {}, {}
    for ccy, (index, exchange) in COUNTRY.items():
        leg = index_legs.get(index)
        if leg is None:
            why[ccy] = "no_index"
            continue
        try:
            first, last = window(exchange, day, vetted)
        except CalendarRefused:
            why[ccy] = "calendar"
            continue
        i, j = (leg.anchor(exchange, first), leg.anchor(exchange, last)) if first < last else (None, None)
        if i is None or j is None:
            why[ccy] = "no_anchor"
            continue
        raw[ccy] = float(leg.closes[j] / leg.closes[i] - 1.0)
    if len(raw) < MIN_COUNTRIES:
        return {}, why
    mean = sum(raw.values()) / len(raw)
    return {c: r - mean for c, r in raw.items()}, why


def positions(demeaned: Mapping[str, float], sign: float = 1.0) -> dict[str, float]:
    """Each pair's units of capital: currency c's weight is -SCALE x its demeaned return (x sign)."""
    return {PAIR[c][0]: -sign * SCALE * s * PAIR[c][1] for c, s in demeaned.items() if c in PAIR}


def simulate_fix(prices: Mapping[str, Sequence[Session]], book: Mapping[date, Mapping[str, float]],
                 costs: Mapping[str, CostModel] | None, start: date, graded_from: date, end: date,
                 times: Mapping[str, time], entry: str = "entry", exit: str = "fix",
                 beta: float | None = None) -> EventResult:
    """`costs` None prices nothing; days outside [graded_from, end] are not graded. With `beta`, the COST
    GATE: a pair-day trades only if beta x |its currency's demeaned return| beats a round trip at its entry
    tick's spread (the exit's is unknown at entry), else it is skipped as `below_cost`."""
    grid = marks(start, end)
    epochs, daily, events, skipped = np.array([e for _, e in grid]), np.zeros(len(grid)), [], []
    for pair in sorted(prices):
        for s in prices[pair]:
            w = book.get(s.day, {}).get(pair)
            if w is None or not graded_from <= s.day <= end:
                continue
            if s.prices.get(entry) is None or s.prices.get(exit) is None:
                skipped.append({"day": s.day.isoformat(), "pair": pair, "reason": "no price"})
                continue
            (pin, sin), (pout, sout) = s.prices[entry], s.prices[exit]
            if beta is not None and beta * abs(w) / SCALE <= 2 * costs[pair].per_side_cost(sin) / pin:
                skipped.append({"day": s.day.isoformat(), "pair": pair, "reason": "below_cost"})
                continue
            gross = w * (pout / pin - 1.0)
            cost = abs(w) * (costs[pair].per_side_cost(sin) + costs[pair].per_side_cost(sout)) / pin if costs else 0.0
            k = int(np.searchsorted(epochs, datetime.combine(s.day, times[exit], ZoneInfo(LONDON)).timestamp()))
            if k >= len(grid):
                skipped.append({"day": s.day.isoformat(), "pair": pair, "reason": "no mark after the exit"})
                continue
            daily[k] += gross - cost
            events.append({"day": s.day.isoformat(), "pair": pair, "weight": w, "gross": gross, "net": gross - cost})
    return EventResult(tuple(d for d, _ in grid), daily, tuple(events), tuple(skipped))


def reform_split(r: EventResult, graded_from: date) -> dict:
    """Context, pre-declared before the look: the annual Sharpe before and after the 2015 fix reform."""
    days = np.array(r.days)
    part = lambda m: annual_sharpe(r.daily[m]) if m.sum() > 1 else None          # noqa: E731
    return {"before_reform": part((days >= graded_from) & (days < REFORM)), "after_reform": part(days >= REFORM)}
