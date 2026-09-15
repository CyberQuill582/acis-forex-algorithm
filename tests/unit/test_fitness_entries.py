"""Entry timing of the fitness mini-backtest (GAP-P12D-28 mutation-gate triage): the warm-up
boundary for each indicator that can bind it, and what counts as a fresh EMA cross.

Warm-up = max(ema_slow, rsi_period + 1, atr_period + 1). With ema_slow 20 and either RSI 21 or
ATR 21 it is 22, so a cross on bar 22 must be taken and one on bar 21 must not.
"""

from __future__ import annotations

import pytest

from core.optimizer.fitness import ema_series, rsi_series, simulate_trades
from tests.optimizer_fixtures import TEST_COSTS, bars_from_closes, make_paramset

CASES = {"rsi binds": (make_paramset(rsi_period=21), 14), "atr binds": (make_paramset(), 21)}


def _turn(against_bars: int, direction: int = 1) -> list[float]:
    """A run against `direction`, then a +6/-3 pip zigzag with it: the fast EMA crosses the slow
    one 8 bars after the run ends, with RSI mid-range (checked by `_first_cross`)."""
    closes = [1.1 - direction * 0.0002 * k for k in range(against_bars)]
    for k in range(40):
        closes.append(closes[-1] + direction * (0.0006 if k % 2 == 0 else -0.0003))
    return closes


def _emas(closes: list[float], ps) -> tuple[list[float], list[float]]:
    return ema_series(closes, ps.ema_fast), ema_series(closes, ps.ema_slow)


def _first_cross(closes: list[float], ps, direction: int = 1) -> int:
    """The spec's entry rule restated: the first EMA cross after the opening run, RSI-filtered."""
    fast, slow = _emas(closes, ps)
    rsi = rsi_series(closes, ps.rsi_period)
    for i in range(2, len(closes)):
        up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
        down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
        if up or down:
            assert (1 if up else -1) == direction, "the cross came the wrong way"
            assert rsi[i] < ps.rsi_overbought if up else rsi[i] > ps.rsi_oversold
            return i
    raise AssertionError("no cross")


@pytest.mark.parametrize("ps, atr", CASES.values(), ids=CASES.keys())
def test_a_cross_on_the_first_bar_after_warm_up_is_taken(ps, atr: int) -> None:
    closes = _turn(14)
    assert _first_cross(closes, ps) == 22
    bars = bars_from_closes(closes[:24])                        # the cross bar, then the entry bar
    assert len(simulate_trades(ps, bars, TEST_COSTS, atr_period=atr)) == 1   # marked to close


@pytest.mark.parametrize("ps, atr", CASES.values(), ids=CASES.keys())
def test_a_cross_one_bar_before_warm_up_ends_is_ignored(ps, atr: int) -> None:
    closes = _turn(13)
    assert _first_cross(closes, ps) == 21
    bars = bars_from_closes(closes[:23])
    assert simulate_trades(ps, bars, TEST_COSTS, atr_period=atr) == []


@pytest.mark.parametrize("direction", [1, -1])
def test_the_bar_after_an_ignored_cross_is_not_a_fresh_cross(direction: int) -> None:
    """The cross on bar 21 falls inside the warm-up and is ignored. The EMAs then stay crossed,
    so bar 22 — whose PREVIOUS bar is already crossed — is not a cross: no trade at all."""
    ps = make_paramset(rsi_period=21)
    closes = _turn(13, direction)
    assert _first_cross(closes, ps, direction) == 21
    fast, slow = _emas(closes, ps)
    assert all(direction * (f - s) > 0 for f, s in zip(fast[21:], slow[21:]))   # never uncrossed
    assert simulate_trades(ps, bars_from_closes(closes), TEST_COSTS, atr_period=14) == []


@pytest.mark.parametrize("direction", [1, -1])
def test_a_cross_is_decided_without_the_next_bar(direction: int) -> None:
    """A 100-pip move against the trade on the entry bar drags that bar's slow EMA past the
    previous fast EMA. The cross on bar 22 was already complete: it is traded (and stopped out),
    never re-judged with the next bar's prices."""
    ps = make_paramset()
    closes = _turn(14, direction)[:23]
    assert _first_cross(closes, ps, direction) == 22
    closes.append(closes[-1] - direction * 0.01)
    fast, slow = _emas(closes, ps)
    assert direction * (fast[21] - slow[23]) > 0               # the next bar WOULD have undone it
    pnls = simulate_trades(ps, bars_from_closes(closes), TEST_COSTS, atr_period=14)
    assert len(pnls) == 1 and pnls[0] < 0


def _pullback(direction: int = 1) -> list[float]:
    """24 bars with `direction`, a 3-bar pullback of 12 pips a bar, then a 4-pip-a-bar resumption:
    the fast EMA re-crosses the slow one on bar 32 while the slow EMA is still moving its way."""
    closes = [1.1 + direction * 0.0002 * k for k in range(24)]
    closes += [closes[-1] - direction * 0.0012 * k for k in (1, 2, 3)]
    closes += [closes[-1] + direction * 0.0004 * k for k in range(1, 11)]
    return closes


@pytest.mark.parametrize("direction", [1, -1])
def test_a_cross_compares_consecutive_bars_of_both_emas(direction: int) -> None:
    ps = make_paramset()
    closes, c = _pullback(direction), 32
    fast, slow = _emas(closes, ps)
    assert direction * (slow[c - 1] - fast[c - 1]) >= 0 and direction * (fast[c] - slow[c]) > 0   # bar 31 -> 32
    assert direction * (fast[c - 1] - slow[c - 2]) > 0         # but against bar 30's slow EMA it had crossed
    rsi = rsi_series(closes, ps.rsi_period)[c]
    assert rsi < ps.rsi_overbought if direction > 0 else rsi > ps.rsi_oversold
    # entries only from bar 31, so the pullback's own cross (near bar 25) cannot trade first
    bars = bars_from_closes(closes[: c + 2])
    assert len(simulate_trades(ps, bars, TEST_COSTS, entry_start=31, atr_period=14)) == 1


def test_no_second_entry_while_the_emas_stay_crossed() -> None:
    """Each trade lasts one bar; the fast EMA stays above the slow one after the single cross,
    so exactly one trade exists however long the zigzag runs on."""
    ps = make_paramset(max_holding_periods=1)
    closes = _turn(14)
    fast, slow = _emas(closes, ps)
    assert all(f > s for f, s in zip(fast[22:], slow[22:]))     # one cross, never undone
    assert len(simulate_trades(ps, bars_from_closes(closes), TEST_COSTS, atr_period=14)) == 1
