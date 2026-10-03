"""The passive-first fill model (tests/backtest/passive_fill.py): fills, fallbacks, the benchmark, and the
optional-stopping anchor that a CFD limit order on a martingale saves nothing in expectation."""

from __future__ import annotations

import math

import numpy as np
import pytest

from tests.backtest.passive_fill import Outcome, Policy, Quotes, limit_price, simulate, summarise

TICK = 0.00001
T0 = 1_600_000_000_000


def _q(rows):
    """rows: (seconds after T0, bid, ask) ticks."""
    t = np.array([T0 + int(s * 1000) for s, _, _ in rows])
    return Quotes.from_ticks(t, np.array([b for _, b, _ in rows]), np.array([a for _, _, a in rows]))


def test_a_buy_at_the_touch_fills_only_when_the_ask_trades_a_tick_through_and_pays_its_limit():
    q = _q([(0, 1.10000, 1.10002), (10, 1.09999, 1.10000), (20, 1.09998, 1.09999), (30, 1.10005, 1.10007),
            (400, 1.10005, 1.10007)])
    o = simulate(q, T0, +1, Policy("touch", 60, through=1), TICK)
    assert o.filled and o.wait_s == 20                     # the ask reached the bid at 10 s, passed it at 20 s
    assert o.saving_bp == pytest.approx(0.00002 / 1.10001 * 1e4)
    assert simulate(q, T0, +1, Policy("touch", 60, through=0), TICK).wait_s == 10   # the venue's touch rule


def test_an_unfilled_buy_falls_back_to_the_deadlines_ask_and_pays_the_move():
    q = _q([(0, 1.10000, 1.10002), (30, 1.10010, 1.10012), (60, 1.10020, 1.10022)])
    o = simulate(q, T0, +1, Policy("touch", 60), TICK)
    assert not o.filled and o.wait_s == 60
    assert o.saving_bp == pytest.approx(-(1.10022 - 1.10002) / 1.10001 * 1e4)


def test_a_sell_mirrors_the_buy_on_the_bid():
    q = _q([(0, 1.10000, 1.10002), (5, 1.10003, 1.10005), (90, 1.10003, 1.10005)])
    o = simulate(q, T0, -1, Policy("touch", 60), TICK)     # the bid 1.10003 passed the ask 1.10002 by a tick
    assert o.filled and o.saving_bp == pytest.approx(0.00002 / 1.10001 * 1e4)
    assert o.drift_bp[0] == pytest.approx(0.0)             # flat after the fill: no adverse move


def test_the_mid_is_put_on_the_tick_grid_away_from_the_market():
    assert limit_price(1.10000, 1.10003, +1, "mid", TICK) == pytest.approx(1.10001)
    assert limit_price(1.10000, 1.10003, -1, "mid", TICK) == pytest.approx(1.10002)
    assert limit_price(1.10000, 1.10002, +1, "mid", TICK) == pytest.approx(1.10001)


def test_an_exit_benchmarked_at_its_deadline_saves_nothing_when_it_never_fills():
    q = _q([(0, 1.10000, 1.10002), (30, 1.10010, 1.10012), (60, 1.10020, 1.10022)])
    assert simulate(q, T0, +1, Policy("touch", 60), TICK, benchmark="deadline").saving_bp == pytest.approx(0.0)


def test_a_candle_whose_ask_low_dips_through_fills_though_its_close_does_not():
    t = np.array([T0, T0 + 60_000, T0 + 120_000])
    q = Quotes(t, np.array([1.10000, 1.10003, 1.10003]), np.array([1.10002, 1.10005, 1.10005]),
               np.array([1.10002, 1.09998, 1.10005]), np.array([1.10000, 1.10003, 1.10003]))
    o = simulate(q, T0, +1, Policy("touch", 120), TICK)
    assert o.filled and o.wait_s == 60


def test_the_chase_rule_crosses_at_the_first_tick_the_bid_moves_up_and_otherwise_rests_like_the_touch():
    up = _q([(0, 1.10000, 1.10002), (10, 1.10001, 1.10003), (20, 1.09998, 1.09999), (90, 1.09998, 1.09999)])
    o = simulate(up, T0, +1, Policy("chase", 60), TICK)
    assert not o.filled and o.wait_s == 10                 # Carver: cross when the market moves away
    assert o.saving_bp == pytest.approx(-0.00001 / 1.10001 * 1e4)
    down = _q([(0, 1.10000, 1.10002), (10, 1.09999, 1.10000), (20, 1.09998, 1.09999), (90, 1.09998, 1.09999)])
    chase, touch = (simulate(down, T0, +1, Policy(lv, 60), TICK) for lv in ("chase", "touch"))
    assert (chase.filled, chase.wait_s, chase.saving_bp) == (touch.filled, touch.wait_s, touch.saving_bp) == (True, 20, chase.saving_bp)


def test_the_delay_control_never_rests_and_saves_half_the_spread_that_narrowed_while_it_waited():
    q = _q([(0, 1.10000, 1.10010), (10, 1.09990, 1.09995), (60, 1.10004, 1.10006)])   # wide, dip, narrow
    buy, sell = (simulate(q, T0, s, Policy("delay", 60), TICK) for s in (+1, -1))
    assert not buy.filled and not sell.filled and buy.wait_s == 60
    assert (buy.saving_bp + sell.saving_bp) / 2 == pytest.approx((0.00010 - 0.00002) / 2 / 1.10005 * 1e4)
    assert buy.arrival_mid == pytest.approx(1.10005)


def test_a_stale_arrival_or_an_unknown_benchmark_gives_no_outcome():
    q = _q([(0, 1.10000, 1.10002), (1000, 1.10000, 1.10002)])
    assert simulate(q, T0 + 400_000, +1, Policy("touch", 60), TICK) is None
    assert simulate(q, T0, +1, Policy("touch", 60), TICK, benchmark="mid") is None
    with pytest.raises(ValueError):
        Policy("inside", 60)


def _walk(rng, n=400, spread_ticks=2):
    steps = rng.choice([-1, 1], n)
    mid_ticks = 110_000 + np.concatenate([[0], np.cumsum(steps)])
    bid = (mid_ticks - spread_ticks // 2) * TICK
    return _q([(i * 2, b, b + spread_ticks * TICK) for i, b in enumerate(bid)])


def test_on_a_martingale_the_venues_touch_rule_saves_nothing_and_one_tick_through_loses():
    rng = np.random.default_rng(7)
    touch, chase, through = [], [], []
    for _ in range(3000):
        q, side = _walk(rng), int(rng.choice([-1, 1]))
        touch.append(simulate(q, T0, side, Policy("touch", 300, through=0), TICK).saving_bp)
        chase.append(simulate(q, T0, side, Policy("chase", 300, through=0), TICK).saving_bp)
        through.append(simulate(q, T0, side, Policy("touch", 300, through=1), TICK).saving_bp)
    for rule in (touch, chase):                              # optional stopping: no stopping rule has an edge
        assert abs(np.mean(rule)) < 3 * np.std(rule) / math.sqrt(len(rule))
    assert np.mean(through) < np.mean(touch)                # the conservative rule only removes fills


def test_a_summary_takes_the_day_as_its_unit_and_reads_fill_drift_only_from_fills():
    a = Outcome(True, 10, 0.2, 0.3, (-0.1,))
    b = Outcome(False, 60, -0.4, 0.3, (0.5,))
    s = summarise([[a, b], [a, a]])
    assert s.days == 2 and s.fill_rate == pytest.approx(0.75)
    assert s.saving_bp == pytest.approx((-0.1 + 0.2) / 2)
    assert s.fill_drift_bp == (pytest.approx(-0.1),)
    assert summarise([]) is None
