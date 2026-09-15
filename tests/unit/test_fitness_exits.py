"""Exact exit geometry of the fitness mini-backtest (GAP-P12D-28 mutation-gate triage).

The first mutation-gate run showed the stop/target comparisons, the stop-before-target order,
the holding counter and the mark-to-close in `simulate_trades` could be altered without a test
failing. Each test enters one trade on a fixture, then feeds hand-built bars that touch the
stop or target EXACTLY (so `<=` vs `<` matters) or stay inside them, and checks the one PnL.
Suffix bar k carries spread 0.0003 + 0.0001·k, so the entry (which fills at bar 0's open and
pays bar 0's spread) and a later exit pay visibly different costs.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.optimizer.fitness import atr_series, ema_series, rsi_series, simulate_trades
from core.optimizer.param_types import LabelledBar
from tests.optimizer_fixtures import TEST_COSTS, bars_from_closes, make_paramset

ATR = 14
PS = make_paramset(atr_multiplier_sl=2.0, atr_multiplier_tp=3.0, max_holding_periods=4)


def _spread(k: int) -> float:
    return 0.0003 + 0.0001 * k


def _cost(k: int) -> float:
    return TEST_COSTS.per_side_cost(_spread(k))


def _entry_index(bars, direction: int) -> int:
    """The spec's dual-EMA entry rule, restated: the first cross (after warm-up) with the RSI filter."""
    closes = [b.close for b in bars]
    fast, slow = ema_series(closes, PS.ema_fast), ema_series(closes, PS.ema_slow)
    rsi = rsi_series(closes, PS.rsi_period)
    for i in range(max(PS.ema_slow, PS.rsi_period + 1, ATR + 1), len(bars) - 1):
        up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i] and rsi[i] < PS.rsi_overbought
        down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i] and rsi[i] > PS.rsi_oversold
        if up or down:
            assert (1 if up else -1) == direction, "fixture entered the wrong way first"
            return i
    raise AssertionError("fixture never entered")


def _trade(direction: int, suffix):
    """40 bars against `direction`, a zigzag turn, entry; then `suffix(entry, sl, tp)` -> [(high, low, close)].
    The turn zigzags (+6, -3 pips) so RSI sits mid-range at the cross (65 long / 35 short, bar 50):
    a straight run pushes RSI past the 75/25 filter before the slow EMA is crossed."""
    closes = [1.1 - direction * 0.0002 * k for k in range(40)]
    for k in range(40):
        closes.append(closes[-1] + direction * (0.0006 if k % 2 == 0 else -0.0003))
    bars = list(bars_from_closes(closes))
    i = _entry_index(bars, direction)
    bars = bars[: i + 1]
    a = atr_series(bars, ATR)[i]
    entry = bars[i].close                   # the next bar opens at this close
    sl = entry - direction * PS.atr_multiplier_sl * a
    tp = entry + direction * PS.atr_multiplier_tp * a
    prev = entry
    for k, (high, low, close) in enumerate(suffix(entry, sl, tp)):
        bars.append(LabelledBar(ts=bars[-1].ts + timedelta(minutes=1), open=prev, high=high, low=low,
                                close=close, spread=_spread(k), regime=bars[-1].regime))
        prev = close
    return simulate_trades(PS, bars, TEST_COSTS, atr_period=ATR), entry, sl, tp


def _band_step(entry: float, sl: float, tp: float) -> float:
    return min(abs(tp - entry), abs(entry - sl)) / 10


def _quiet(entry, sl, tp, n):
    """n bars strictly inside the stop/target band, closing at the entry."""
    inner = 5 * _band_step(entry, sl, tp)
    return [(entry + inner, entry - inner, entry)] * n


@pytest.mark.parametrize("direction", [1, -1])
def test_a_target_touched_exactly_exits_at_the_target(direction: int) -> None:
    def suffix(entry, sl, tp):
        edge = (tp, entry) if direction > 0 else (entry, tp)   # (high, low): only the target is touched
        return [(edge[0], edge[1], entry)] + _quiet(entry, sl, tp, 2)
    pnls, entry, sl, tp = _trade(direction, suffix)
    assert pnls == [pytest.approx(direction * (tp - entry) - _cost(0) - _cost(0), abs=1e-15)]


@pytest.mark.parametrize("direction", [1, -1])
def test_a_stop_touched_exactly_exits_at_the_stop_even_when_the_target_is_touched_too(direction: int) -> None:
    def suffix(entry, sl, tp):
        both = (tp, sl) if direction > 0 else (sl, tp)          # the bar spans stop AND target
        return [(both[0], both[1], entry)] + _quiet(entry, sl, tp, 2)
    pnls, entry, sl, tp = _trade(direction, suffix)
    assert pnls == [pytest.approx(direction * (sl - entry) - _cost(0) - _cost(0), abs=1e-15)]


@pytest.mark.parametrize("direction", [1, -1])
def test_a_trade_open_at_the_window_end_is_marked_at_the_last_close(direction: int) -> None:
    def suffix(entry, sl, tp):
        step = _band_step(entry, sl, tp)
        return [(entry + 2 * step, entry - 2 * step, entry + direction * step)] * 2   # 2 bars < max hold 4
    pnls, entry, sl, tp = _trade(direction, suffix)
    step = _band_step(entry, sl, tp)
    assert pnls == [pytest.approx(step - _cost(0) - _cost(1), abs=1e-15)]


@pytest.mark.parametrize("direction", [1, -1])
def test_a_trade_that_touches_neither_exits_on_its_fourth_bar_close(direction: int) -> None:
    def suffix(entry, sl, tp):
        step = _band_step(entry, sl, tp)
        closes = [entry + direction * step * k for k in (1, 2, 3, 4, 5, 6)]
        return [(max(c, p) + step / 2, min(c, p) - step / 2, c) for p, c in zip([entry] + closes, closes)]
    pnls, entry, sl, tp = _trade(direction, suffix)
    step = _band_step(entry, sl, tp)
    # held 1 on the entry bar (suffix 0), so the fourth bar is suffix 3, closing 4 steps out
    assert pnls == [pytest.approx(4 * step - _cost(0) - _cost(3), abs=1e-15)]
