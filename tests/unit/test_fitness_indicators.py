"""Hand-worked values for the fitness indicators (GAP-P12D-28 mutation-gate triage).

The first mutation-gate run showed the Wilder RSI and ATR recursions, their warm-up guards and
the EMA seed could all be altered without a single test failing. Each value below is worked
by hand in the comment beside it, so a changed operator, index or constant changes a number.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.optimizer.fitness import WORST_FITNESS, atr_series, ema_series, rsi_series
from core.optimizer.param_types import LabelledBar
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import T0


def _bar(i: int, high: float, low: float, close: float) -> LabelledBar:
    return LabelledBar(ts=T0 + timedelta(minutes=i), open=close, high=high, low=low, close=close,
                       spread=0.0001, regime=RegimeType.STRONG_TREND_UP)


# true ranges (period 2): each of the three TR terms wins on some bar
BARS = (
    _bar(0, 10.5, 9.5, 10.4),
    _bar(1, 11.0, 10.0, 10.8),   # high-low 1.0 beats |11-10.4| 0.6, |10-10.4| 0.4   -> 1.0
    _bar(2, 11.5, 10.9, 11.2),   # |11.5-10.8| 0.7 beats high-low 0.6, |10.9-10.8| 0.1 -> 0.7
    _bar(3, 11.0, 9.8, 10.0),    # |9.8-11.2| 1.4 beats high-low 1.2, |11-11.2| 0.2   -> 1.4
    _bar(4, 10.2, 9.0, 9.1),     # high-low 1.2 beats |9-10| 1.0, |10.2-10| 0.2       -> 1.2
)


def test_wilder_atr_hand_worked() -> None:
    # seed at bar 2: (1.0 + 0.7) / 2 = 0.85; then (0.85·1 + 1.4) / 2 = 1.125; (1.125 + 1.2) / 2 = 1.1625
    assert atr_series(BARS, 2) == pytest.approx([0.0, 0.0, 0.85, 1.125, 1.1625])


def test_atr_is_all_warm_up_until_a_full_period_of_ranges_exists() -> None:
    assert atr_series(BARS[:2], 2) == [0.0, 0.0]
    assert atr_series(BARS[:3], 2) == pytest.approx([0.0, 0.0, 0.85])


def test_wilder_rsi_hand_worked_gains_first() -> None:
    # moves +1 +2 -1 +3 -1. Seed: gain 3/2 = 1.5, loss 0 -> 100.
    # bar 3 (-1): gain 1.5/2 = 0.75, loss 1/2 = 0.5, RS 1.5 -> 100 - 100/2.5 = 60
    # bar 4 (+3): gain (0.75+3)/2 = 1.875, loss 0.25, RS 7.5 -> 100 - 100/8.5
    # bar 5 (-1): gain 0.9375, loss (0.25+1)/2 = 0.625, RS 1.5 -> 60
    assert rsi_series([10, 11, 13, 12, 15, 14], 2) == pytest.approx(
        [50.0, 50.0, 100.0, 60.0, 100 - 100 / 8.5, 60.0])


def test_wilder_rsi_hand_worked_loss_in_the_seed_window() -> None:
    # moves -1 +2 -1. Seed: gain 2/2 = 1, loss 1/2 = 0.5, RS 2 -> 100 - 100/3
    # bar 3 (-1): gain 1/2 = 0.5, loss (0.5+1)/2 = 0.75, RS 2/3 -> 100 - 100/(5/3) = 40
    assert rsi_series([10, 9, 11, 10], 2) == pytest.approx([50.0, 50.0, 100 - 100 / 3, 40.0])


def test_rsi_is_neutral_until_a_full_period_of_moves_exists() -> None:
    assert rsi_series([10, 11], 2) == [50.0, 50.0]


def test_ema_is_seeded_with_the_first_close() -> None:
    # k = 2/(3+1) = 0.5: 2, then 4·0.5 + 2·0.5 = 3, then 6·0.5 + 3·0.5 = 4.5
    assert ema_series([2.0, 4.0, 6.0], 3) == pytest.approx([2.0, 3.0, 4.5])


def test_the_gated_out_score_is_the_declared_sentinel() -> None:
    assert WORST_FITNESS == -1.0                               # ACIS-03 §6.2
