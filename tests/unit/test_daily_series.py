"""The engine's daily series equals RSIM's on the same hours (core/signals/daily.py; ACIS-04 v1.6 §4b):
the decision days, the closes and their staleness, the daily bars, and the execution slots."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

import numpy as np

from core.data.bars import Bar
from core.data.fx_clock import rollover_utc
from core.signals.daily import SLOTS, STALE, decision_days, series, slot_after, slot_of
from tests.backtest import rsim_real
from tests.backtest.candle_store import Hourly

UTC = timezone.utc
START, END = date(2025, 11, 3), date(2026, 3, 20)
CLOSED = {date(2025, 12, 25), date(2026, 1, 1)}                       # everything shut
GAP = {date(2026, 2, 2) + timedelta(days=k) for k in range(6)}       # one instrument dark for a week


def _hours(dark: set[date], seed: int) -> list[Bar]:
    rng, out, px = random.Random(seed), [], 1.10
    t = datetime(2025, 10, 26, tzinfo=UTC)
    while t < datetime(2026, 3, 21, tzinfo=UTC):
        ny = t.astimezone(rsim_real.NY)
        fx_day = (ny + timedelta(hours=7)).date()                    # the trading day 17:00 -> 17:00 closes
        if fx_day.weekday() < 5 and fx_day not in CLOSED | dark:
            px *= 1 + rng.gauss(0, 0.001)
            hi, lo = px * 1.0005, px * 0.9995
            out.append(Bar(ts_open=t, open=px, high=hi, low=lo, close=px, spread=0.0, duration_s=3600))
        t += timedelta(hours=1)
    return out


def _as_hourly(name: str, bars: list[Bar]) -> Hourly:
    by = {int(b.ts_open.timestamp()): b for b in bars}
    lo, hi = min(by), max(by)
    start = np.arange(lo, hi + 3600, 3600, dtype=np.int64)
    close = np.asarray([by[s].close if s in by else 1.0 for s in start])
    return Hourly(name, start, close.copy(), close, np.zeros(len(start)), np.asarray([s in by for s in start]))


def test_decision_days_closes_and_staleness_equal_rsims_rules() -> None:
    hours = {"A": _hours(set(), 1), "B": _hours(GAP, 2)}
    days = decision_days(hours, START, END)
    rsim_days = [d for d, at in rsim_real._decisions(START, END)
                 if any((c := rsim_real._Closes(_as_hourly(n, h)).at(at)) and at - c[1] < 86400
                        for n, h in hours.items())]
    assert days == rsim_days and not CLOSED & set(days)
    for name, bars in hours.items():
        s, closes = series(name, bars, days), rsim_real._Closes(_as_hourly(name, bars))
        expected = []
        for d in days:
            c = closes.at(int(rollover_utc(d).timestamp()))
            fresh = c is not None and int(rollover_utc(d).timestamp()) - c[1] <= rsim_real.STALE_S
            expected.append((c[0] if fresh else expected[-1][0], fresh))
        assert list(zip(s.closes, s.fresh)) == expected
    assert rsim_real.STALE_S == STALE.total_seconds()
    b = series("B", hours["B"], days)
    assert not all(b.fresh) and any(not f for f, d in zip(b.fresh, b.days) if d in GAP)


def test_a_daily_bar_spans_the_hours_since_the_previous_decision() -> None:
    bars = _hours(set(), 3)
    s = series("A", bars, decision_days({"A": bars}, START, END))
    for prev, d, bar in zip(s.days, s.days[1:], s.bars[1:]):
        inside = [h for h in bars if rollover_utc(prev) < h.ts_open + timedelta(hours=1) <= rollover_utc(d)]
        assert (bar.high, bar.low, bar.close) == (max(h.high for h in inside), min(h.low for h in inside),
                                                  inside[-1].close)
        assert bar.ts_open == rollover_utc(prev)


def test_slots_equal_rsims_and_follow_dst_never_before_their_decision() -> None:
    assert SLOTS == rsim_real.SLOTS
    summer, winter = rollover_utc(date(2026, 7, 1)), rollover_utc(date(2026, 1, 7))
    assert slot_after(summer, slot_of("EUR_USD", "fx")) == datetime(2026, 7, 2, 12, tzinfo=UTC)   # 08:00 EDT
    assert slot_after(winter, slot_of("EUR_USD", "fx")) == datetime(2026, 1, 8, 13, tzinfo=UTC)   # 08:00 EST
    assert slot_after(rollover_utc(date(2026, 7, 3)), ("America/New_York", 8)).weekday() == 0     # Friday -> Monday
    assert slot_after(winter, slot_of("AUS200", "index")) == datetime(2026, 1, 8, 0, tzinfo=UTC)  # 11:00 AEDT
    assert slot_after(winter, slot_of("JP225", "index")) == datetime(2026, 1, 8, 1, tzinfo=UTC)   # 10:00 JST
    for d in (date(2026, 3, 6), date(2026, 3, 9), date(2026, 10, 30), date(2026, 11, 2)):         # DST edges
        decision = rollover_utc(d)
        for key, slot in SLOTS.items():
            assert slot_after(decision, slot) > decision, key
