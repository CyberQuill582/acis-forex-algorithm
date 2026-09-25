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

from core.optimizer.fitness import Trade, atr_series, ema_series, rsi_series, simulate_trades, trade_path
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


def _trade_bars(direction: int, suffix):
    """40 bars against `direction`, a zigzag turn, entry; then `suffix(entry, sl, tp)` -> [(high, low, close)].
    The turn zigzags (+6, -3 pips) so RSI sits mid-range at the cross (65 long / 35 short, bar 50):
    a straight run pushes RSI past the 75/25 filter before the slow EMA is crossed.
    Returns (bars, signal bar index, entry, sl, tp)."""
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
    return bars, i, entry, sl, tp


def _trade(direction: int, suffix):
    bars, _, entry, sl, tp = _trade_bars(direction, suffix)
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
def test_the_trade_path_records_when_each_decision_was_taken(direction: int) -> None:
    """GAP-P12D-65: the leakage suite compares decisions by WHEN they were taken, so every field
    of `Trade` is pinned: the signal bar, the fill at the next open, the exit bar and price, and
    whether a decision or the window-end mark closed it. `simulate_trades` is its PnLs."""
    def decided(entry, sl, tp):
        edge = (tp, entry) if direction > 0 else (entry, tp)
        return [(edge[0], edge[1], entry)] + _quiet(entry, sl, tp, 2)
    bars, i, entry, sl, tp = _trade_bars(direction, decided)
    first, = trade_path(PS, bars, TEST_COSTS, atr_period=ATR)
    assert first == Trade(signal_bar=i, direction=direction, entry_price=bars[i + 1].open, exit_bar=i + 1,
                          exit_price=tp, pnl=first.pnl, exit_kind="target")
    assert first.marked is False
    assert first.pnl == simulate_trades(PS, bars, TEST_COSTS, atr_period=ATR)[0]

    def held(entry, sl, tp):
        return _quiet(entry, sl, tp, 2)                                     # 2 bars < max hold 4
    bars, i, entry, sl, tp = _trade_bars(direction, held)
    marked, = trade_path(PS, bars, TEST_COSTS, atr_period=ATR)
    assert marked == Trade(signal_bar=i, direction=direction, entry_price=entry, exit_bar=len(bars) - 1,
                           exit_price=bars[-1].close, pnl=marked.pnl, exit_kind="mark")
    assert marked.marked is True
    assert marked.pnl == pytest.approx(-_cost(0) - _cost(1), abs=1e-15)


def _gap(direction: int, open_at, reach: float = 0.0, gap_spread: float | None = None):
    """Entry, one quiet bar, then a bar that OPENS at `open_at(entry, sl, tp)` and stays within a
    tenth of a band step of it — or also reaches `reach` band steps toward the target."""
    bars, i, entry, sl, tp = _trade_bars(direction, lambda e, s, t: _quiet(e, s, t, 1))
    o, step = open_at(entry, sl, tp), _band_step(entry, sl, tp)
    near = (o + step / 10, o - step / 10)
    far = tp + direction * reach * step
    high, low = (max(near[0], far), near[1]) if direction > 0 else (near[0], min(near[1], far))
    # the close differs from the open, so an exit at the wrong one of the two cannot pass
    bars.append(LabelledBar(ts=bars[-1].ts + timedelta(minutes=1), open=o, high=high if reach else near[0],
                            low=low if reach else near[1], close=o + direction * step / 20,
                            spread=_spread(1) if gap_spread is None else gap_spread,
                            regime=bars[-1].regime))
    first, = trade_path(PS, bars, TEST_COSTS, atr_period=ATR)
    return first, i, entry, sl, tp, o


@pytest.mark.parametrize("direction", [1, -1])
def test_a_bar_that_opens_through_the_stop_exits_at_the_open_not_the_stop(direction: int) -> None:
    """T6 (GAP-P12D-65, VALIDATOR §7.3): the first price after the gap is the open. Filling at
    the stop there would credit a price the market never offered. The graded tick book fills
    at the gapped tick too since GAP-P12D-84; before that fix it filled at the stop.
    The fill happens at the open, so it pays the prior bar's closing spread (X2)."""
    t, i, entry, sl, tp, o = _gap(direction, lambda e, s, p: s - direction * 3 * _band_step(e, s, p))
    assert direction * (o - sl) < 0                                     # beyond the stop, against us
    assert t == Trade(signal_bar=i, direction=direction, entry_price=entry, exit_bar=i + 2, exit_price=o,
                      pnl=t.pnl, exit_kind="gap")
    assert t.pnl == pytest.approx(direction * (o - entry) - _cost(0) - _cost(0), abs=1e-15)


@pytest.mark.parametrize("direction", [1, -1])
def test_a_gap_exit_never_pays_the_gap_bars_own_closing_spread(direction: int) -> None:
    """X2 (GAP-P12D-83): the gap bar's closing spread is known only after its open, when the
    fill has already happened, so changing it must not move the trade's PnL."""
    at = lambda e, s, p: s - direction * 3 * _band_step(e, s, p)  # noqa: E731
    t, *_ = _gap(direction, at)
    wide, *_ = _gap(direction, at, gap_spread=0.01)
    assert wide.exit_kind == "gap" and wide.pnl == t.pnl


@pytest.mark.parametrize("direction", [1, -1])
def test_a_bar_that_opens_exactly_at_the_stop_exits_at_the_stop(direction: int) -> None:
    t, i, entry, sl, tp, o = _gap(direction, lambda e, s, p: s)
    assert (t.exit_bar, t.exit_price, t.exit_kind) == (i + 2, sl, "stop")
    assert t.pnl == pytest.approx(direction * (sl - entry) - _cost(0) - _cost(1), abs=1e-15)


@pytest.mark.parametrize("direction", [1, -1])
def test_a_gap_through_the_stop_is_not_rescued_by_a_rally_to_the_target(direction: int) -> None:
    """Stop before target (§6.1) holds on a gap bar: it exits at the gapped open even when the
    same bar's range later reaches the target."""
    t, i, entry, sl, tp, o = _gap(direction, lambda e, s, p: s - direction * 3 * _band_step(e, s, p), reach=1.0)
    assert (t.exit_bar, t.exit_price) == (i + 2, o)


@pytest.mark.parametrize("direction", [1, -1])
def test_a_bar_that_opens_beyond_the_target_fills_there_at_the_open(direction: int) -> None:
    """X3 (GAP-P12D-83): a take-profit fills at the first price equal to or better than its level
    (OANDA v20 TakeProfitOrder; backtrader Limit), and a bar's first price is its open. It pays
    the prior bar's closing spread, the latest known at the fill."""
    t, i, entry, sl, tp, o = _gap(direction, lambda e, s, p: p + direction * 3 * _band_step(e, s, p))
    assert direction * (o - tp) > 0
    assert (t.exit_bar, t.exit_price, t.exit_kind) == (i + 2, o, "target_gap")
    assert t.pnl == pytest.approx(direction * (o - entry) - _cost(0) - _cost(0), abs=1e-15)


@pytest.mark.parametrize("direction", [1, -1])
def test_a_bar_that_opens_beyond_the_target_is_not_booked_as_a_later_stop(direction: int) -> None:
    """The audit's X3 repro: the bar opens beyond the target, then its range runs back past the
    stop. The open already settled the order at the target side; the stop cannot come first."""
    bars, i, entry, sl, tp = _trade_bars(direction, lambda e, s, t: _quiet(e, s, t, 1))
    step = _band_step(entry, sl, tp)
    o, far = tp + direction * 2 * step, sl - direction * step
    high, low = (o + step / 10, far) if direction > 0 else (far, o - step / 10)
    bars.append(LabelledBar(ts=bars[-1].ts + timedelta(minutes=1), open=o, high=high, low=low,
                            close=(o + far) / 2, spread=_spread(1), regime=bars[-1].regime))
    t, = trade_path(PS, bars, TEST_COSTS, atr_period=ATR)
    assert (t.exit_bar, t.exit_price, t.exit_kind) == (i + 2, o, "target_gap")


@pytest.mark.parametrize("direction", [1, -1])
def test_an_intrabar_stop_and_a_max_hold_close_name_their_kind(direction: int) -> None:
    """The kind decides the leakage suite's stamp (a gap at the open, the rest at the close)."""
    def touched(entry, sl, tp):
        both = (tp, sl) if direction > 0 else (sl, tp)
        return [(both[0], both[1], entry)]

    def neither(entry, sl, tp):
        step = _band_step(entry, sl, tp)
        return [(entry + step, entry - step, entry)] * 4
    for suffix, kind in ((touched, "stop"), (neither, "hold")):
        bars, *_ = _trade_bars(direction, suffix)
        assert [t.exit_kind for t in trade_path(PS, bars, TEST_COSTS, atr_period=ATR)] == [kind]


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
