"""Hand-worked values for the fitness components, the expectancy edges and the RSI entry filter
(GAP-P12D-28 mutation-gate triage). Each number is worked in the comment beside it."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from core.data.errors import DataQualityError
from core.optimizer.costs import CostModel
from core.optimizer.fitness import (evaluate_fitness, expectancy_r, max_drawdown_penalty,
                                    mean_sigma_component, profit_factor_component,
                                    simulate_trades)
from tests.optimizer_fixtures import TEST_COSTS, bars_from_closes, make_paramset, opt_cfg

CFG = opt_cfg()                                              # 5 trades minimum, E_R > 0


def test_mean_sigma_component_hand_worked() -> None:
    # [2, -1, 2, -1]: mean 0.5, population sd 1.5, s = 1/3 -> (1/3 + 3) / 6
    assert mean_sigma_component([2.0, -1.0, 2.0, -1.0]) == pytest.approx((1 / 3 + 3) / 6)


def test_mean_sigma_component_without_dispersion_takes_the_sign() -> None:
    assert mean_sigma_component([1.0, 1.0]) == 1.0            # s = +3 -> 6/6
    assert mean_sigma_component([-1.0, -1.0]) == 0.0          # s = -3 -> 0/6
    assert mean_sigma_component([0.0, 0.0]) == 0.5            # s = 0  -> 3/6


def test_mean_sigma_component_clamps_both_ends() -> None:
    # [-1, -1.1]: mean -1.05, sd 0.05, s = -21 -> -3 before the clamp; mirrored for +21
    assert mean_sigma_component([-1.0, -1.1]) == 0.0
    assert mean_sigma_component([1.0, 1.1]) == 1.0


def test_profit_factor_component_hand_worked() -> None:
    assert profit_factor_component([1.5, -1.0]) == 0.5        # PF 1.5 / 3
    assert profit_factor_component([6.0, -1.0]) == 1.0        # PF 6 / 3 = 2, clamped
    assert profit_factor_component([0.0]) == 0.0              # no win and no loss
    assert profit_factor_component([0.0, -1.0]) == 0.0        # PF 0


def test_max_drawdown_penalty_hand_worked() -> None:
    assert max_drawdown_penalty([2.0, -0.5, 3.0]) == pytest.approx(0.1)        # equity 2 1.5 4.5: 0.5 of 5
    assert max_drawdown_penalty([2.0, -1.0, -1.0, 3.0]) == pytest.approx(0.4)  # equity 2 1 0 3: 2 of 5
    assert max_drawdown_penalty([-1.0, 2.0]) == pytest.approx(0.5)             # below the zero start: 1 of 2


def test_expectancy_r_divides_by_the_average_loss() -> None:
    res = expectancy_r([4.0, -2.0])                          # E 1, average loss 2
    assert res.expectancy == 1.0 and res.e_r == 0.5


def test_zero_pnl_trades_are_not_losses() -> None:
    assert expectancy_r([2.0, 0.0, -1.0]).e_r == pytest.approx(1 / 3)   # E 1/3 over the one loss of 1


def test_no_losses_and_no_profit_has_no_expectancy_ratio() -> None:
    assert math.isnan(expectancy_r([0.0, 0.0]).e_r)


def test_expectancy_result_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        expectancy_r([1.0]).n_trades = 2


def test_evaluate_fitness_hand_worked() -> None:
    # [2, -1, 2, 0, 2]: E 1, one loss of 1 -> E_R 1 passes.
    # mean 1, population variance (1+4+1+1+1)/5 = 1.6, s = 1/sqrt(1.6) = 0.7905694 -> 0.6317616
    # win rate 3/5 (a zero is not a win); PF 6/1 -> 1.0; equity 2 1 3 3 5: drawdown 1 of 6 wins
    # 0.4·0.6317616 + 0.2·0.6 + 0.2·1.0 - 0.2·(1/6) = 0.5393713
    assert evaluate_fitness([2.0, -1.0, 2.0, 0.0, 2.0], CFG) == pytest.approx(0.5393713, abs=1e-7)


@pytest.mark.parametrize("closes", [[1.1] * 30 + [1.101] * 20, [1.1] * 30 + [1.099] * 20])
def test_a_cross_against_an_exhausted_rsi_is_not_taken(closes) -> None:
    # the flat run holds RSI at 100 (no losses); a jump keeps it at 100 (not < 75), a drop sends
    # it to 0 (not > 25) — both EMA crosses are filtered out, so no trade exists
    assert simulate_trades(make_paramset(), bars_from_closes(closes), TEST_COSTS, atr_period=14) == []


def test_profit_factor_component_with_pnls_under_one_unit() -> None:
    assert profit_factor_component([0.5, -1.0]) == pytest.approx(0.5 / 3)     # a win under 1 still counts
    assert profit_factor_component([0.5, 1.5, -1.0]) == pytest.approx(2 / 3)  # and is never a loss
    assert profit_factor_component([0.5]) == 1.0                             # a small win, no losses
    assert profit_factor_component([3.0, -2.0]) == 0.5                       # PF 3/2: a ratio, not a product


def test_evaluate_fitness_hand_worked_below_the_clamps() -> None:
    # [0.75, -0.5, 0.75, -0.5, 0.75]: E 0.25 over an average loss of 0.5 -> E_R 0.5 passes; every PnL < 1
    # mean 0.25, population variance 1.875/5 = 0.375, s = 0.25/0.6123724 = 0.4082483 -> 0.5680414
    # win rate 3/5; PF 2.25/1.0 -> 0.75 (under the clamp); equity .75 .25 1 .5 1.25: drawdown 0.5 of 2.25
    # 0.4·0.5680414 + 0.2·0.6 + 0.2·0.75 - 0.2·(0.5/2.25) = 0.4527721
    assert evaluate_fitness([0.75, -0.5, 0.75, -0.5, 0.75], CFG) == pytest.approx(0.4527721, abs=1e-7)


def test_the_cost_model_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        TEST_COSTS.slippage_per_side = 0.0


def test_a_zero_spread_costs_only_the_declared_friction() -> None:
    assert CostModel(0.00003, 0.00002).per_side_cost(0.0) == pytest.approx(0.00005)


def test_a_bad_spread_is_reported_against_the_spread_field() -> None:
    with pytest.raises(DataQualityError) as err:
        TEST_COSTS.per_side_cost(-0.0001)
    assert err.value.field == "spread"
