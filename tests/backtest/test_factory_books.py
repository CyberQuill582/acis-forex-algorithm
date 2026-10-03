"""The factory's index books (GAP-P12D-158): sessions sit on each home cash close, a session earns the
position set at the previous close and pays C8 on each change, IREV trades against its own last four
returns with the paper's 4/3/2/1 weights, and HALLOWEEN's contrast flips at each half-year, sized once."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest import halloween, irev
from tests.backtest.event_multi import LEG_RISK, VOL_SESSIONS, Sessions, book, sessions, trailing_vol
from tests.backtest.test_event_sim import _close_at, _hourly, _linear

START, GRADED, END = date(2021, 3, 1), date(2021, 3, 8), date(2021, 4, 30)


def _synthetic(days: list[date], closes: list[float], spread: float = 0.0, name: str = "US500") -> Sessions:
    return Sessions(name, "XNYS", tuple(days), np.asarray(closes, float), np.full(len(days), spread))


def _weekdays(a: date, n: int) -> list[date]:
    out, d = [], a
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_sessions_anchor_on_the_home_cash_close_and_the_book_earns_the_previous_closes_position() -> None:
    h = _hourly(date(2021, 2, 1), date(2021, 5, 3), _linear, spread=1.0)
    s = sessions(h, "US500", START, END)
    assert s.days[0] == START and s.closes[0] == pytest.approx(_close_at(h, START))
    target = np.where(np.array(s.days) >= date(2021, 3, 15), -0.5, 0.5)
    r = book({"US500": s}, {"US500": target}, {"US500": CostModel(0.0, 0.25)}, START, GRADED, END)
    p = dict(zip(s.days, s.closes))
    mark = lambda d: r.daily[r.days.index(d)]                                     # noqa: E731
    assert mark(GRADED) == pytest.approx(-0.5 * 0.75 / p[GRADED])                 # the entry: cost only
    assert mark(date(2021, 3, 9)) == pytest.approx(0.5 * (p[date(2021, 3, 9)] / p[GRADED] - 1))
    flip = date(2021, 3, 15)
    assert mark(flip) == pytest.approx(0.5 * (p[flip] / p[date(2021, 3, 12)] - 1) - 1.0 * 0.75 / p[flip])
    assert (r.daily[: r.days.index(GRADED)] == 0).all()


def test_trailing_vol_reads_only_the_returns_ending_at_the_session() -> None:
    r = np.r_[np.nan, np.tile([0.01, -0.01], 50)]
    v = trailing_vol(r)
    assert np.isnan(v[VOL_SESSIONS // 2 - 1]) and np.isfinite(v[VOL_SESSIONS // 2])
    shocked = r.copy()
    shocked[80] = 0.5
    assert np.array_equal(trailing_vol(shocked)[:80], v[:80], equal_nan=True)                    # a later return never leaks back


def test_irev_holds_minus_four_three_two_one_of_its_last_four_standardised_returns_capped_at_two() -> None:
    r = np.r_[np.nan, np.zeros(10), [0.01, 0.0, 0.0, 0.0]]
    sigma = np.full(len(r), 0.01)
    u = irev.unit_signal(r, sigma)
    assert u[11] == pytest.approx(4.0 / np.sqrt(30)) and u[14] == pytest.approx(1.0 / np.sqrt(30))
    days = _weekdays(date(2021, 1, 4), 120)
    closes = 100.0 * np.exp(np.cumsum(np.r_[0.0, np.tile([0.004, -0.004], 59), [0.10]]))
    t = irev.target(_synthetic(days, closes.tolist()))
    assert t[-1] < 0                                                              # after a rally: short
    sd = trailing_vol(_synthetic(days, closes.tolist()).returns)[-1]
    assert t[-1] == pytest.approx(-LEG_RISK / sd * irev.CAP)                      # the cap binds on a shock


def test_halloween_is_long_into_winter_sessions_short_into_summer_and_sized_once_a_season() -> None:
    days = _weekdays(date(2020, 9, 1), 200)
    rng = np.random.default_rng(3)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    t = halloween.target(_synthetic(days, closes.tolist()))
    k_oct = max(k for k, d in enumerate(days) if d.month == 10)                   # held into 1 November
    assert t[k_oct] > 0 > t[k_oct - 1]
    winter = [t[k] for k, d in enumerate(days) if k >= k_oct and days[min(k + 1, len(days) - 1)].month in (11, 12, 1, 2, 3, 4)]
    assert len(set(np.round(winter, 12))) == 1                                    # one size all season
    k_apr = max(k for k, d in enumerate(days) if d.month == 4)
    assert t[k_apr] < 0 < t[k_apr - 1]


def test_a_planted_reversal_earns_net_under_irev_and_a_flat_market_only_pays_costs() -> None:
    days = _weekdays(date(2019, 1, 1), 700)
    rng = np.random.default_rng(7)
    e = rng.normal(0, 0.01, len(days))
    rev = e.copy()
    for k in range(1, len(e)):
        rev[k] = e[k] - 0.3 * e[k - 1]                                            # a planted negative autocorrelation
    cost = {"US500": CostModel(0.0, 0.0)}
    planted = _synthetic(days, (1000.0 * np.exp(np.cumsum(rev))).tolist(), spread=0.1)
    r = book({"US500": planted}, {"US500": irev.target(planted)}, cost, days[0], days[100], days[-1])
    assert r.daily.sum() > 0
    flat = _synthetic(days, [1000.0] * len(days), spread=0.1)
    f = book({"US500": flat}, {"US500": np.full(len(days), 0.5)}, cost, days[0], days[100], days[-1])
    assert f.daily.sum() == pytest.approx(-0.5 * 0.05 / 1000.0)                   # one entry, half the spread
