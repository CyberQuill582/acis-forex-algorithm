"""A research simulator for scheduled-window rules: D3, the turn-of-month index long (owner ruling
2026-10-03, "Faithful event harness"). It grades on RSIM's daily clock, so the register, the HAC kill
rule and stage D read one kind of series.

Mental model (each choice declared; D3 as the R1-B slate specifies it):
  * TRADING DAYS per index are its home market's weekdays with at least one traded hour inside its
    cash session (`CASH`). A month's T-1 is its last such day; T+3 is the next month's third.
  * ENTRY: the open mid of the first traded hour starting at or after 14:30 New York on the calendar
    date of T-1. For the European and Asian indices that instant falls after their cash close: a
    consequence of the US-centred spec, declared, not repaired. EXIT: the close mid of the last traded
    hour ending at or before the home cash close of T+3. Each side pays half its quoted spread (the
    exit side uses its hour's open spread) plus the declared C8 slippage. Swap-free: no financing.
  * MARKS: every New York weekday at 17:00 New York (RSIM's decision clock). Between entry and exit a
    position is marked at the last traded close at or before each mark, so an event's return splits
    into daily returns: entry to the first mark, mark to mark, the last mark to the exit (booked on
    the first mark after the exit). Each side's cost is booked on its day.
  * SIZING: equal risk: a leg's weight is 1% over its trailing 60-mark daily return volatility, read
    before the entry (no look-ahead). The kill rule's HAC t does not depend on the 1%.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from tests.backtest.candle_store import Hourly, load

NY = ZoneInfo("America/New_York")
CASH = {"US500": ("America/New_York", time(9, 30), time(16, 0)), "US30": ("America/New_York", time(9, 30), time(16, 0)),
        "UK100": ("Europe/London", time(8, 0), time(16, 30)), "EU50": ("Europe/Berlin", time(9, 0), time(17, 30)),
        "JP225": ("Asia/Tokyo", time(9, 0), time(15, 0)), "AUS200": ("Australia/Sydney", time(10, 0), time(16, 0))}
ENTRY_NY = time(14, 30)
VOL_MARKS, LEG_RISK = 60, 0.01


@dataclass(frozen=True)
class EventResult:
    days: tuple[date, ...]           # every New York weekday mark in the graded window
    daily: np.ndarray                # the portfolio's net daily return on each
    events: tuple[dict, ...]         # one per index per month: entry, exit, gross and net return


def _epoch(d: date, t: time, zone: ZoneInfo) -> int:
    return int(datetime.combine(d, t, tzinfo=zone).timestamp())


def trading_days(h: Hourly, name: str) -> list[date]:
    zone, open_, close = CASH[name]
    tz, out = ZoneInfo(zone), set()
    for s in h.start[h.traded]:
        lt = datetime.fromtimestamp(int(s), tz)
        if lt.weekday() < 5 and open_ <= lt.time() < close:
            out.add(lt.date())
    return sorted(out)


def windows(days: Sequence[date]) -> list[tuple[date, date]]:
    """(T-1, T+3) for every month whose next month has three trading days."""
    by_month: dict[tuple[int, int], list[date]] = {}
    for d in days:
        by_month.setdefault((d.year, d.month), []).append(d)
    keys = sorted(by_month)
    return [(by_month[a][-1], by_month[b][2]) for a, b in zip(keys, keys[1:])
            if (b[0] * 12 + b[1]) - (a[0] * 12 + a[1]) == 1 and len(by_month[b]) >= 3]


def marks(start: date, end: date) -> list[tuple[date, int]]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append((d, _epoch(d, time(17, 0), NY)))
        d += timedelta(days=1)
    return out


def simulate(root: Path, names: Sequence[str], slippage: Mapping[str, float], start: date, end: date) -> EventResult:
    grid = marks(start, end)
    stamps = np.array([t for _, t in grid])
    daily = np.zeros(len(grid))
    events = []
    for name in names:
        h = load(root, name, (end.year, end.month))
        starts, ends = h.start[h.traded], h.start[h.traded] + 3600
        opens, closes, spreads = h.mid_open[h.traded], h.mid_close[h.traded], h.spread_open[h.traded]
        price_at = lambda t: closes[k] if (k := int(np.searchsorted(ends, t, side="right")) - 1) >= 0 else np.nan  # noqa: E731
        mark_px = np.array([price_at(t) for t in stamps])
        rets = mark_px[1:] / mark_px[:-1] - 1.0
        zone, _, cash_close = CASH[name]
        for t1, t3 in windows(trading_days(h, name)):
            e0, e1 = _epoch(t1, ENTRY_NY, NY), _epoch(t3, cash_close, ZoneInfo(zone))
            i = int(np.searchsorted(starts, e0, side="left"))
            j = int(np.searchsorted(ends, e1, side="right")) - 1
            if not (start <= t1 and t3 <= end) or i >= len(starts) or j < i:
                continue
            first = int(np.searchsorted(stamps, starts[i], side="left"))        # the first mark after entry
            past = rets[max(0, first - 1 - VOL_MARKS):max(0, first - 1)]
            past = past[np.isfinite(past)]
            if len(past) < VOL_MARKS // 2 or not np.std(past) > 0:
                continue
            w = LEG_RISK / float(np.std(past, ddof=1))
            pin, pout = float(opens[i]), float(closes[j])
            c_in = (spreads[i] / 2 + slippage[name]) / pin
            c_out = (spreads[j] / 2 + slippage[name]) / pout
            path, k, prev = [], first, pin
            while k < len(stamps) and stamps[k] <= ends[j]:
                px = mark_px[k]
                if np.isfinite(px):
                    path.append((k, px / prev - 1.0))
                    prev = px
                k += 1
            if k < len(stamps):
                path.append((k, pout / prev - 1.0))
            if not path:
                continue
            for n, (k, r) in enumerate(path):
                cost = (c_in if n == 0 else 0.0) + (c_out if n == len(path) - 1 else 0.0)
                daily[k] += w * (r - cost)
            gross = pout / pin - 1.0
            events.append({"index": name, "t_minus_1": t1.isoformat(), "t_plus_3": t3.isoformat(),
                           "gross": gross, "net": gross - c_in - c_out, "weight": w})
    return EventResult(tuple(d for d, _ in grid), daily, tuple(events))
