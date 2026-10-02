"""The daily decision clock and the per-instrument daily series (ACIS-04 v1.6 §4b; ACIS-05 v1.7 §6.4).

RSIM's real-data rules (tests/backtest/rsim_real.py) in core, so the engine decides on the series
the family was graded on; `tests/unit/test_daily_series.py` pins the two equal on the same hours.

Mental model:
  * DECISION: each New York weekday at 17:00 America/New_York (the FX rollover, `rollover_utc`). A
    weekday on which no instrument of the universe has an hour ending in the 24 h before it
    (Christmas, New Year) is not a decision day.
  * CLOSE: the close of the instrument's last complete hour ending at or before the decision, if it
    ended within `STALE` (4 days). Otherwise the previous close carries forward and the day is
    marked not FRESH, so it gives no forecast (R6-1). The series starts at the first fresh close
    (RSIM's `first_valid`).
  * DAILY BAR: the hours ending in (previous decision, this decision], as one OHLC `Bar` opened at
    the previous decision; a day without hours is a flat bar at the carried close. They feed the
    disaster stop's true-range ATR (R6-2).
  * SLOT: the instrument's execution slot (RSIM's SLOTS): the first weekday instant at the slot's
    local hour strictly after the decision. A slot is never before its decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from core.data.bars import Bar
from core.data.fx_clock import rollover_utc

STALE = timedelta(days=4)
DAY = timedelta(days=1)
SLOTS = {"fx": ("America/New_York", 8), "metal": ("America/New_York", 8), "energy": ("America/New_York", 10),
         "US500": ("America/New_York", 10), "US30": ("America/New_York", 10), "US100": ("America/New_York", 10),
         "UK100": ("Europe/London", 9), "EU50": ("Europe/Berlin", 9), "GER40": ("Europe/Berlin", 9),
         "JP225": ("Asia/Tokyo", 10), "AUS200": ("Australia/Sydney", 11)}


@dataclass(frozen=True)
class DailySeries:
    instrument: str
    days: tuple[date, ...]           # the decision days since the instrument's first close
    closes: tuple[float, ...]        # carried forward through stale days
    fresh: tuple[bool, ...]          # the close's hour ended within STALE of its decision
    bars: tuple[Bar, ...]            # one daily OHLC per day (the ATR's input)


def decision_days(hours: Mapping[str, Sequence[Bar]], start: date, end: date) -> list[date]:
    """Weekdays in [start, end] on which some instrument has an hour ending in the prior 24 h."""
    ends = sorted({_end(b) for bars in hours.values() for b in bars})
    out, d, k = [], start, 0
    while d <= end:
        if d.weekday() < 5:
            at = rollover_utc(d)
            while k < len(ends) and ends[k] <= at - DAY:
                k += 1
            if k < len(ends) and ends[k] <= at:
                out.append(d)
        d += DAY
    return out


def series(instrument: str, hours: Sequence[Bar], days: Sequence[date]) -> DailySeries:
    """The instrument's daily series on the given decision days (see the mental model)."""
    bars = sorted(hours, key=lambda b: b.ts_open)
    out_days, closes, fresh, daily = [], [], [], []
    k, prev_at, last = 0, None, None
    for d in days:
        at = rollover_utc(d)
        window = []
        while k < len(bars) and _end(bars[k]) <= at:
            if prev_at is None or _end(bars[k]) > prev_at:
                window.append(bars[k])
            last = bars[k]
            k += 1
        is_fresh = last is not None and at - _end(last) <= STALE
        if not closes and not is_fresh:
            prev_at = at
            continue                                  # before the instrument's first fresh close
        close = last.close if is_fresh else closes[-1]
        out_days.append(d)
        closes.append(close)
        fresh.append(is_fresh)
        daily.append(_daily_bar(window, close, prev_at or at - DAY, at))
        prev_at = at
    return DailySeries(instrument, tuple(out_days), tuple(closes), tuple(fresh), tuple(daily))


def slot_after(decision: datetime, slot: tuple[str, int]) -> datetime:
    """The first weekday instant at the slot's local hour strictly after `decision`."""
    zone = ZoneInfo(slot[0])
    local = decision.astimezone(zone)
    day = local.date()
    while True:
        candidate = datetime(day.year, day.month, day.day, slot[1], tzinfo=zone)
        if candidate > local and candidate.weekday() < 5:
            return candidate.astimezone(timezone.utc)
        day += DAY


def slot_of(instrument: str, asset_class: str) -> tuple[str, int]:
    return SLOTS.get(instrument) or SLOTS[asset_class]


def _end(bar: Bar) -> datetime:
    return bar.ts_open + timedelta(seconds=bar.duration_s)


def _daily_bar(window: Sequence[Bar], close: float, opened: datetime, at: datetime) -> Bar:
    seconds = max(1, int((at - opened).total_seconds()))
    if not window:
        return Bar(ts_open=opened, open=close, high=close, low=close, close=close, spread=0.0, duration_s=seconds)
    return Bar(ts_open=opened, open=window[0].open, high=max(b.high for b in window),
               low=min(b.low for b in window), close=window[-1].close, spread=0.0, duration_s=seconds)
