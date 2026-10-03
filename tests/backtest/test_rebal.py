"""REBAL's signals against the paper's own equations and worked example (GAP-P12D-157)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from tests.backtest.rebal import (DELTAS, calendar_signal, drift, month_ends, note_returns, par_duration, position,
                                  threshold_signal)


def _weekdays(first: date, n: int) -> list[date]:
    out, d = [], first
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_the_papers_worked_example_a_10pct_equity_day_moves_the_weight_by_2_26pct() -> None:
    assert drift(0.6, 0.10, 0.0) - 0.6 == pytest.approx(0.66 / 1.06 - 0.6) == pytest.approx(0.0226, abs=1e-4)


def test_threshold_resets_the_day_after_a_breach_and_averages_26_bands() -> None:
    """One +10% day then flat days: each band <= 2.26% resets on day 2, the three wider ones never (B.1)."""
    rs, rb = np.array([0.10, 0.0, 0.0, 0.0]), np.zeros(4)
    dev = 0.66 / 1.06 - 0.6
    assert len(DELTAS) == 26 and DELTAS[-1] == pytest.approx(0.025)
    assert threshold_signal(rs, rb) == pytest.approx([dev, 25 / 26 * dev, 3 / 26 * dev, 3 / 26 * dev])


def test_calendar_resets_the_day_after_the_months_last_business_day() -> None:
    days = _weekdays(date(2021, 1, 25), 10)                      # Jan 25..29, Feb 1..5
    rs = np.array([0.0, 0.10, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    cal = calendar_signal(rs, np.zeros(10), month_ends(days))
    dev = 0.66 / 1.06 - 0.6
    assert month_ends(days)[4] and days[4] == date(2021, 1, 29)
    assert cal[1:6] == pytest.approx([dev] * 5) and cal[6:] == pytest.approx([0.0] * 4)   # Feb 1 still drifted


def test_the_position_is_the_mean_of_the_scaled_threshold_and_the_week4_and_reversal_signs() -> None:
    days = _weekdays(date(2021, 1, 4), 30)                       # all of January, then Feb 1..12
    thr = np.full(30, 0.003)
    cal = np.linspace(-0.01, 0.02, 30)
    pos = position(days, thr, cal)
    jan = [k for k, d in enumerate(days) if d.month == 1]
    first_feb = jan[-1] + 1
    for k in range(30):
        if k in jan[-5:]:
            want = np.sign(-cal[k])
        elif k == first_feb:
            want = np.sign(cal[k - 4])                            # day -4 of January
        else:
            want = 0.0
        assert pos[k] == pytest.approx(0.5 * (-0.003 / 0.015 + want))


def test_the_note_leg_moves_by_the_7_year_par_duration_and_a_missing_yield_repeats() -> None:
    assert par_duration(0.02) == pytest.approx((1 - 1.01 ** -14) / 0.02) == pytest.approx(6.50, abs=0.01)
    days = _weekdays(date(2021, 3, 1), 3)
    r = note_returns(days, {days[0]: 2.00, days[2]: 2.10})       # day 2 has no print
    assert r[0] == 0.0 and r[1] == 0.0 and r[2] == pytest.approx(-par_duration(0.02) * 0.001)
