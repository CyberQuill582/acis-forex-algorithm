"""RATES' books (GAP-P12D-161): the sign, the sizing, the control and causality on synthetic yields."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from tests.backtest.ust_auction import book
from tests.backtest.ust_trend import FORECASTS, TAU, positions, sigma, yield_changes


def _curve(n: int = 700, drift: float = 0.002, seed: int = 3):
    days = [date(2011, 1, 3) + timedelta(days=k) for k in range(n)]
    rng = np.random.default_rng(seed)
    y = 2.0 + np.cumsum(drift + 0.03 * rng.standard_normal(n))
    return days, {"2y": y, "5y": y + 0.5, "10y": y + 1.0, "30y": y + 1.5}


def test_a_rising_yield_is_held_long_and_the_control_is_short_every_yield_at_the_same_size() -> None:
    days, curve = _curve()
    for name in ("d1", "mop"):
        pos = positions(days, curve, FORECASTS[name])
        assert all((pos[t][-200:] > 0).mean() > 0.9 for t in curve)
    ctrl = positions(days, curve, None, passive=True)
    s = sigma(curve["10y"])
    k = len(days) - 1
    assert ctrl["10y"][k] < 0 and np.isclose(-ctrl["10y"][k], TAU / s[k] / len(curve))


def test_a_position_never_reads_a_later_yield() -> None:
    days, curve = _curve()
    cut = 500
    later = {t: np.r_[y[:cut], y[cut:] + 5.0] for t, y in curve.items()}     # a regime jump after the cut
    for name in ("d1", "mop"):
        a, b = positions(days, curve, FORECASTS[name]), positions(days, later, FORECASTS[name])
        assert all(np.array_equal(a[t][:cut], b[t][:cut]) for t in curve)


def test_the_book_earns_the_next_change_and_pays_a_side_on_each_trade() -> None:
    days = [date(2012, 2, 1) + timedelta(days=k) for k in range(3)]
    y = np.array([2.0, 2.1, 2.05])
    r = book(days, np.array([1.0, -1.0, 0.0]), yield_changes(y), 0.001, days[0], days[0], days[-1])
    pnl = {d: v for d, v in zip(r.days, r.daily)}
    assert np.isclose(pnl[days[0]], -0.001)                                  # open long: one side
    assert np.isclose(pnl[days[1]], 0.001 - 0.002)                           # earned +10 bp, flipped: two sides
    assert np.isclose(pnl[days[2]], 0.0005 - 0.001)                          # short earned the fall, then closed
