"""FXHEDGE's book on synthetic candles and prices (GAP-P12D-158; Melvin & Prins, JFM 2015): the fix day is the
month's last weekday, the signal runs from each exchange's first session to its last before the fix day on its
own calendar and reads nothing later, the weights sum to zero with USD_JPY flipped, costs book on both sides,
and the P&L lands on the 17:00 New York mark of the fix day."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.event_intraday import Session
from tests.backtest.event_sim import NY, EventResult
from tests.backtest.fxhedge import BETA, REFORM, SCALE, fix_day, legs, positions, reform_split, signal, simulate_fix

UTC = timezone.utc
TIMES = {"open": time(8, 0), "entry": time(15, 0), "fix": time(16, 0)}


def _utc(y, m, d, h=0) -> int:
    return int(datetime(y, m, d, h, tzinfo=UTC).timestamp())


def _hourly(name: str, jumps: dict[int, float]) -> Hourly:
    """Every hour of 2019-04-25..06-05 quoted at 1000, times (1 + r) for each jump at or after its epoch."""
    start = np.arange(_utc(2019, 4, 25), _utc(2019, 6, 5), 3600, dtype=np.int64)
    c = np.full(len(start), 1000.0)
    for at, r in jumps.items():
        c[start >= at] *= 1.0 + r
    return Hourly(name, start, np.r_[c[0], c[:-1]], c, np.zeros(len(start)), np.ones(len(start), bool))


def test_the_fix_day_is_the_months_last_weekday() -> None:
    assert fix_day(2020, 2) == date(2020, 2, 28)          # the 29th is a Saturday
    assert fix_day(2015, 8) == date(2015, 8, 31)          # a UK bank holiday: WM still fixes (declared)
    assert fix_day(2023, 12) == date(2023, 12, 29)


def test_the_signal_runs_on_each_exchanges_calendar_reads_nothing_later_and_is_demeaned() -> None:
    T = fix_day(2019, 5)                                   # Friday 31 May 2019
    hourly = {"US500": _hourly("US500", {_utc(2019, 5, 15): 0.02,      # inside the window: counts
                                         _utc(2019, 5, 31): 0.50}),    # after the 30 May US close: never read
              "EU50": _hourly("EU50", {_utc(2019, 5, 1, 16): 0.05}),   # after 1 May's close, but 1 May is an XEUR
              "UK100": _hourly("UK100", {_utc(2019, 5, 20): -0.01})}   # holiday: the window starts 2 May's close
    s, why = signal(legs(hourly), T)
    raw = {"USD": 0.02, "EUR": 0.0, "GBP": -0.01}
    mean = sum(raw.values()) / 3
    assert s == pytest.approx({c: r - mean for c, r in raw.items()})
    assert sum(s.values()) == pytest.approx(0.0)
    assert why == {"JPY": "no_index", "AUD": "no_index"}


def test_fewer_than_three_countries_skip_the_month() -> None:
    hourly = {n: _hourly(n, {_utc(2019, 5, 15): 0.01}) for n in ("US500", "UK100")}
    assert signal(legs(hourly), fix_day(2019, 5))[0] == {}


def test_each_currency_holds_minus_its_weight_against_the_usd_and_usd_jpy_flips() -> None:
    p = positions({"USD": 0.01, "EUR": 0.02, "JPY": -0.03})
    assert p == pytest.approx({"EUR_USD": -SCALE * 0.02, "USD_JPY": -SCALE * 0.03})
    currency = {"EUR": p["EUR_USD"], "JPY": -p["USD_JPY"]}
    assert sum(currency.values()) - SCALE * 0.01 == pytest.approx(0.0)   # the USD's own weight closes the sum


def test_each_side_pays_c8_on_the_weight_and_the_pnl_lands_on_the_fix_days_new_york_mark() -> None:
    T, cost = date(2019, 5, 31), CostModel(0.00001, 0.00002)
    prices = {"EUR_USD": [Session(T, {"open": (1.1150, 0.0001), "entry": (1.1160, 0.0001), "fix": (1.1170, 0.0002)})],
              "USD_JPY": [Session(T, {"open": (108.0, 0.01), "entry": None, "fix": (108.2, 0.01)})]}
    book = {T: {"EUR_USD": 0.5, "USD_JPY": -0.3}}
    r = simulate_fix(prices, book, {p: cost for p in prices}, date(2019, 5, 27), date(2019, 5, 28), date(2019, 6, 4),
                     TIMES, "entry")
    k = r.days.index(T)
    want = 0.5 * (1.1170 / 1.1160 - 1) - 0.5 * (cost.per_side_cost(0.0001) + cost.per_side_cost(0.0002)) / 1.1160
    assert r.daily[k] == pytest.approx(want)
    assert np.count_nonzero(r.daily) == 1
    assert r.skipped == ({"day": "2019-05-31", "pair": "USD_JPY", "reason": "no price"},)
    early = simulate_fix(prices, book, None, date(2019, 5, 27), date(2019, 5, 28), date(2019, 6, 4), TIMES, "open")
    assert early.daily[k] == pytest.approx(0.5 * (1.1170 / 1.1150 - 1) - 0.3 * (108.2 / 108.0 - 1))
    fix_at = datetime.combine(T, TIMES["fix"], ZoneInfo("Europe/London"))
    assert fix_at < datetime.combine(T, time(17), NY)                   # 16:00 London is before that mark


def test_the_cost_gate_drops_a_pair_day_whose_predicted_move_cannot_beat_its_entry_round_trip() -> None:
    T, cost = date(2019, 5, 31), CostModel(0.0, 0.00002)
    pin, spread = 1.1200, 0.0001
    breakeven = 2 * cost.per_side_cost(spread) / pin / BETA * SCALE        # the |weight| whose move equals the cost
    prices = {"EUR_USD": [Session(T, {"entry": (pin, spread), "fix": (1.1190, spread)})]}
    args = ({"EUR_USD": cost}, date(2019, 5, 27), date(2019, 5, 28), date(2019, 6, 4), TIMES)
    small = simulate_fix(prices, {T: {"EUR_USD": -0.9 * breakeven}}, *args, beta=BETA)
    big = simulate_fix(prices, {T: {"EUR_USD": -1.1 * breakeven}}, *args, beta=BETA)
    assert small.skipped == ({"day": "2019-05-31", "pair": "EUR_USD", "reason": "below_cost"},) and not small.events
    assert len(big.events) == 1 and not big.skipped
    assert len(simulate_fix(prices, {T: {"EUR_USD": -0.9 * breakeven}}, *args).events) == 1   # no beta, no gate


def test_the_reform_split_grades_each_side_of_15_february_2015_and_never_before_the_graded_window() -> None:
    days = tuple(date(2014, 12, 1) + timedelta(days=k) for k in range(120))
    daily = np.array([(1.0 if d < REFORM else -1.0) * (0.001 + 0.0005 * (k % 3)) for k, d in enumerate(days)])
    daily[0] = -90.0                                                     # before graded_from: never read
    split = reform_split(EventResult(days, daily, (), ()), days[1])
    assert split["before_reform"] > 0 > split["after_reform"]


def test_a_planted_fix_flow_earns_net_and_a_flat_market_loses_only_its_costs() -> None:
    T, cost = date(2019, 5, 31), CostModel(0.0, 0.00002)
    book = {T: {"EUR_USD": -0.4}}                          # EUR's equity outperformed: hedgers sell EUR
    flow = {"EUR_USD": [Session(T, {"entry": (1.1200, 0.0001), "fix": (1.1180, 0.0001)})]}
    flat = {"EUR_USD": [Session(T, {"entry": (1.1200, 0.0001), "fix": (1.1200, 0.0001)})]}
    args = ({"EUR_USD": cost}, date(2019, 5, 27), date(2019, 5, 28), date(2019, 6, 4), TIMES)
    assert simulate_fix(flow, book, *args).daily.sum() > 0
    assert simulate_fix(flat, book, *args).daily.sum() == pytest.approx(
        -0.4 * 2 * cost.per_side_cost(0.0001) / 1.1200)
