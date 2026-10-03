"""REBAL's close-to-close book (GAP-P12D-157): marked and traded at each US cash close, the next day
earns the position set the evening before, costs book on the trade, and a feed hole moves nothing."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.event_daily import simulate_daily
from tests.backtest.event_sim import NY
from tests.backtest.test_event_sim import _close_at, _hourly, _linear

START, GRADED, END = date(2021, 3, 1), date(2021, 3, 8), date(2021, 4, 30)


def _sessions(h):
    return [d for d in sorted({date.fromordinal(o) for o in range(START.toordinal(), END.toordinal() + 1)})
            if d.weekday() < 5]


def _mark(r, d):
    return r.daily[r.days.index(d)]


def test_each_session_earns_the_position_set_at_the_previous_close_and_pays_on_the_trade() -> None:
    h = _hourly(date(2021, 2, 1), date(2021, 5, 3), _linear, spread=1.0)
    days = _sessions(h)
    target = np.where(np.array(days) >= date(2021, 3, 15), -0.5, 0.5)
    r = simulate_daily(h, days, target, CostModel(0.0, 0.25), START, GRADED, END)
    p = {d: _close_at(h, d) for d in days}
    assert _mark(r, GRADED) == pytest.approx(-0.5 * 0.75 / p[GRADED])          # the entry: cost only
    tue = date(2021, 3, 9)
    assert _mark(r, tue) == pytest.approx(0.5 * (p[tue] / p[GRADED] - 1))      # no trade, no cost
    flip, before = date(2021, 3, 15), date(2021, 3, 12)
    assert _mark(r, flip) == pytest.approx(0.5 * (p[flip] / p[before] - 1) - 1.0 * 0.75 / p[flip])
    assert (r.daily[: r.days.index(GRADED)] == 0).all() and not r.skipped


def _zero_volume(h, day: date, frozen: bool):
    """`day` reported with zero volume (New York date); `frozen`: its quotes also stop moving."""
    on = np.array([datetime.fromtimestamp(int(s), NY).date() == day for s in h.start])
    h = replace(h, traded=h.traded & ~on)
    return replace(h, mid_close=np.where(on, h.mid_open, h.mid_close)) if frozen else h


def test_a_session_without_an_anchor_neither_marks_nor_trades_and_the_next_books_its_move() -> None:
    hole = date(2021, 3, 17)
    h = _zero_volume(_hourly(date(2021, 2, 1), date(2021, 5, 3), _linear), hole, frozen=True)
    days = _sessions(h)
    r = simulate_daily(h, days, np.full(len(days), 1.0), None, START, GRADED, END)
    assert _mark(r, hole) == 0.0 and r.skipped == ({"index": "US500", "session": "2021-03-17", "reason": "no_anchor"},)
    nxt = date(2021, 3, 18)
    assert _mark(r, nxt) == pytest.approx(_close_at(h, nxt) / _close_at(h, date(2021, 3, 16)) - 1)


def test_the_spread_version_is_short_the_compounded_note_between_anchors() -> None:
    h = _hourly(date(2021, 2, 1), date(2021, 5, 3), _linear)
    days = _sessions(h)
    note = np.full(len(days), 0.001)
    eq = simulate_daily(h, days, np.full(len(days), 1.0), None, START, GRADED, END)
    both = simulate_daily(h, days, np.full(len(days), 1.0), None, START, GRADED, END, note=note)
    tue = date(2021, 3, 9)
    assert _mark(both, tue) == pytest.approx(_mark(eq, tue) - 0.001)
    paid = simulate_daily(h, days, np.full(len(days), 1.0), CostModel(0.0, 0.0), START, GRADED, END,
                          note=note, note_cost=0.0002)
    assert _mark(paid, GRADED) == pytest.approx(-1.0 * 0.0002)                 # spread 0: the note's cost only



def test_a_moving_quote_with_zero_volume_counts_as_a_price() -> None:
    """Owner ruling 2026-10-03 (GAP-P12D-156): Dukascopy recorded moving US500 quotes with zero volume."""
    h = _zero_volume(_hourly(date(2021, 2, 1), date(2021, 5, 3), _linear), date(2021, 3, 17), frozen=False)
    days = _sessions(h)
    assert not simulate_daily(h, days, np.ones(len(days)), None, START, GRADED, END).skipped
