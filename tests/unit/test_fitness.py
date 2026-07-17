"""Fitness + C8 cost model + C9 expectancy gate (ACIS-03 Â§6.1â€“Â§6.2, C-QIEA-6/7)."""

from __future__ import annotations

import math

import pytest

from core.data.errors import DataQualityError
from core.optimizer.costs import CostModel
from core.optimizer.fitness import (
    WORST_FITNESS,
    evaluate_fitness,
    expectancy_r,
    max_drawdown_penalty,
    passes_expectancy_gate,
    profit_factor_component,
    mean_sigma_component,
    simulate_trades,
)
from tests.optimizer_fixtures import (
    TEST_COSTS,
    bars_from_closes,
    make_paramset,
    opt_cfg,
    zigzag_closes,
)

CFG = opt_cfg()


# ---------------------------- C8 cost model ---------------------------------- #

def test_cost_model_semantics_pinned() -> None:
    """THE shared C8 semantics (ACIS-09 imports this same module â€” one model)."""
    cm = CostModel(commission_per_side=0.00003, slippage_per_side=0.00002)
    assert cm.per_side_cost(0.0001) == pytest.approx(0.0001 / 2 + 0.00003 + 0.00002)
    assert cm.round_trip_cost(0.0001, 0.0003) == pytest.approx(
        cm.per_side_cost(0.0001) + cm.per_side_cost(0.0003)
    )


def test_cost_model_rejects_negative_or_nan() -> None:
    with pytest.raises(DataQualityError):
        CostModel(commission_per_side=-0.1, slippage_per_side=0.0)
    with pytest.raises(DataQualityError):
        CostModel(commission_per_side=0.0, slippage_per_side=float("nan"))
    with pytest.raises(DataQualityError):
        CostModel(0.0, 0.0).per_side_cost(-0.1)


def test_c8_gross_profitable_net_losing_cannot_win() -> None:
    """C-QIEA-6: profitable on mid-prices, dead net of friction => WORST_FITNESS."""
    params = make_paramset()
    bars = bars_from_closes(zigzag_closes(500))
    gross = simulate_trades(params, bars, CostModel(0.0, 0.0), atr_period=14)
    assert len(gross) >= CFG.fitness_min_trades and sum(gross) > 0  # a real gross edge
    heavy = CostModel(commission_per_side=0.01, slippage_per_side=0.0)  # friction >> legs
    net = simulate_trades(params, bars, heavy, atr_period=14)
    assert sum(net) < 0
    assert evaluate_fitness(net, CFG) == WORST_FITNESS
    assert evaluate_fitness(gross, CFG) > WORST_FITNESS


def test_every_fill_pays_costs() -> None:
    """Same trades, same bars: each round trip is poorer by exactly the added friction."""
    params = make_paramset()
    bars = bars_from_closes(zigzag_closes(500))
    free = simulate_trades(params, bars, CostModel(0.0, 0.0), atr_period=14)
    paid = simulate_trades(params, bars, CostModel(0.0001, 0.0), atr_period=14)
    assert len(free) == len(paid) != 0
    for f, p in zip(free, paid):
        assert p == pytest.approx(f - 2 * 0.0001)


# ---------------------------- C9 expectancy ---------------------------------- #

def test_expectancy_exact_values() -> None:
    """C-QIEA-7: E and E_R on a hand-computed series."""
    res = expectancy_r([2.0, -1.0, 2.0, -1.0])
    assert res.n_trades == 4
    assert res.expectancy == pytest.approx(0.5)   # (2-1+2-1)/4
    assert res.e_r == pytest.approx(0.5)          # E / avgLoss = 0.5/1.0


def test_high_win_rate_negative_expectancy_is_gated_out() -> None:
    """C-QIEA-7: 90% win rate, negative expectancy â€” the mirage cannot win."""
    pnls = [1.0] * 9 + [-10.0]
    res = expectancy_r(pnls)
    assert res.expectancy == pytest.approx(-0.1)
    assert not passes_expectancy_gate(res, min_trades=5, min_e_r=0.0)
    assert evaluate_fitness(pnls, CFG) == WORST_FITNESS


def test_gate_boundary_e_zero_fails() -> None:
    """Master C9: E <= 0 cannot win â€” exactly zero fails."""
    res = expectancy_r([1.0, -1.0] * 5)
    assert res.e_r == pytest.approx(0.0)
    assert not passes_expectancy_gate(res, min_trades=5, min_e_r=0.0)


@pytest.mark.parametrize("pnls", [
    [],                                  # zero trades
    [1.0, 2.0, -1.0],                    # below min_trades
    [1.0, float("nan"), 2.0, -1.0, 1.0], # NaN leakage
])
def test_degenerate_series_score_worst(pnls: list[float]) -> None:
    assert evaluate_fitness(pnls, CFG) == WORST_FITNESS


def test_no_losses_positive_e_passes_capped() -> None:
    res = expectancy_r([1.0] * 6)
    assert res.e_r == 10.0  # reporting cap
    assert passes_expectancy_gate(res, min_trades=5, min_e_r=0.0)


# ---------------------------- components ------------------------------------- #

def test_fitness_monotone_in_sharpe() -> None:
    """Same mean/win-rate/PF/MDD, lower dispersion => strictly higher fitness."""
    tight = [2.0, 2.0, 2.0, 2.0, -1.0]
    loose = [3.0, 1.0, 3.0, 1.0, -1.0]
    assert mean_sigma_component(tight) > mean_sigma_component(loose)
    assert evaluate_fitness(tight, CFG) > evaluate_fitness(loose, CFG)


def test_components_bounded_01() -> None:
    for pnls in ([5.0, -0.1, 4.0], [-1.0, -2.0, 0.5], [1.0, 1.0, 1.0]):
        assert 0.0 <= mean_sigma_component(pnls) <= 1.0
        assert 0.0 <= profit_factor_component(pnls) <= 1.0
        assert 0.0 <= max_drawdown_penalty(pnls) <= 1.0


def test_profit_factor_degenerates() -> None:
    assert profit_factor_component([1.0, 2.0]) == 1.0      # no losses, gross win > 0
    assert profit_factor_component([-1.0, -2.0]) == 0.0    # no wins
    assert profit_factor_component([3.0, -1.0]) == 1.0     # PF 3 caps at 1


def test_max_drawdown_penalty_monotone_in_drawdown() -> None:
    smooth = [1.0, 1.0, 1.0, 1.0, -0.5]
    jagged = [1.0, -2.0, 1.0, -2.0, 6.0]
    assert max_drawdown_penalty(jagged) > max_drawdown_penalty(smooth)
    assert max_drawdown_penalty([-1.0, -1.0]) == 1.0       # gross_win == 0 => worst


def test_fitness_range_bounds() -> None:
    pnls = [2.0, 2.0, 2.0, -1.0, 2.0]
    f = evaluate_fitness(pnls, CFG)
    assert -0.2 <= f <= 0.8
    assert WORST_FITNESS < -0.2  # the gate sentinel sits strictly below the floor


# ---------------------------- mini-backtest ---------------------------------- #

def test_simulate_no_trades_on_flat_series() -> None:
    bars = bars_from_closes([1.1] * 300)
    assert simulate_trades(make_paramset(), bars, TEST_COSTS, atr_period=14) == []


def test_simulate_produces_closed_trades_on_zigzag() -> None:
    pnls = simulate_trades(make_paramset(), bars_from_closes(zigzag_closes(500)),
                           TEST_COSTS, atr_period=14)
    assert len(pnls) >= CFG.fitness_min_trades
    assert all(math.isfinite(p) for p in pnls)


# ---------------- phase-4 audit triage regression (GAP-0039) ---------------- #

def test_gap0039_open_position_at_window_end_is_marked_to_close() -> None:
    """A trade still open at the window end is closed at the final bar's close â€”
    never silently discarded from the fitness/expectancy series."""
    ps = make_paramset(atr_multiplier_sl=3.5, atr_multiplier_tp=5.0, max_holding_periods=48)
    bars = bars_from_closes(zigzag_closes(500))
    assert simulate_trades(ps, bars[:48], TEST_COSTS, atr_period=14) == []          # not yet entered
    marks = [simulate_trades(ps, bars[:k], TEST_COSTS, atr_period=14) for k in (49, 50, 51)]
    assert all(len(m) == 1 for m in marks)                           # accounted, not dropped
    assert marks[0][0] < marks[1][0] < marks[2][0]                   # the mark follows the close
