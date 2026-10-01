"""RSIM, the research simulator (R1.3): its books are exact, its buffer is Carver's, its lots are
the one lot rule, its financing worlds differ only in financing, and it never reads ahead."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from core.signals import rules
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.rsim import BookSpec, Lots, Market, annual_sharpe, buffered, panel, run
from tests.backtest.rsim_lab import carver_pct_vol, lab_market, run_member

FREE = {"X_USD": CostModel(commission_per_side=0.0, slippage_per_side=0.0)}


def market(fill, *, carry=0.0, spread=0.0001, nights=1.0) -> Market:
    fill = np.asarray(fill, float).reshape(-1, 1)
    days = tuple(date(2026, 1, 5) + timedelta(days=i) for i in range(len(fill)))
    full = lambda v: np.full_like(fill, v)                                   # noqa: E731
    return Market(names=("X_USD",), days=days, price=fill, close=fill, fill=fill, spread=full(spread),
                  carry=full(carry), nights=full(nights), q=full(1.0))


def test_a_long_book_books_price_carry_and_cost_exactly() -> None:
    m = market([1.00, 1.01, 1.02, 1.00], carry=0.0001)
    # capital 1e6 at 16% a year -> 10,000 a day; 1% daily vol at a price of 1 -> 1,000,000 units at
    # forecast 10. From flat the buffer fills to its near edge, 900,000, which then stays inside
    # every later band (Carver's trade-to-edge), so there is one fill
    spec = BookSpec(costs=FREE, capital=1e6, vol_target=0.16, lots={"X_USD": Lots(1000, 1000)})
    res = run(m, np.full((4, 1), 10.0), np.full((4, 1), 0.01), spec)
    assert res.fills == 1 and res.units[:, 0].tolist() == [900_000.0] * 4
    assert res.cost[:, 0].tolist() == pytest.approx([45.0, 0, 0, 0])          # half of 0.0001 a unit
    assert res.gross[:, 0].tolist() == pytest.approx([0, 9_000, 9_000, -18_000])
    assert res.financing[:, 0].tolist() == pytest.approx([0, 90.0, 90.9, 91.8])   # value x carry
    assert res.daily.tolist() == pytest.approx([-45e-6, 0.00909, 0.0090909, -0.0179082])


def test_the_buffer_keeps_inside_the_band_and_trades_to_its_nearest_edge() -> None:
    assert buffered(95.0, 100.0, 10.0) == 95.0                 # inside: no trade
    assert buffered(50.0, 100.0, 10.0) == 90.0                 # below: up to the lower edge only
    assert buffered(130.0, 100.0, 10.0) == 110.0               # above: down to the upper edge only
    assert buffered(0.0, -100.0, 10.0) == -90.0


def test_positions_sit_on_the_venues_lots() -> None:
    m = market([1.0] * 3)
    spec = BookSpec(costs=FREE, capital=1e6, vol_target=0.16, lots={"X_USD": Lots(100_000, 100_000)})
    res = run(m, np.full((3, 1), 2.5), np.full((3, 1), 0.01), spec)      # optimum 250,000 units
    # from flat the buffer trades only to its near edge, 150,000; toward zero on 100,000 lots
    assert set(res.units[:, 0]) == {100_000.0}


@pytest.mark.parametrize("world, expected", [("fair", 90.0), ("swap_free", 0.0),
                                              ("markup", 90.0 - 9e5 * 2.5 / 36500 * 3)])
def test_the_worlds_differ_only_in_financing(world, expected) -> None:
    m = market([1.0, 1.0], carry=0.0001, nights=3.0)
    spec = BookSpec(costs=FREE, capital=1e6, vol_target=0.16, world=world,
                    markup={"X_USD": (2.5, 1.0)} if world == "markup" else {})
    res = run(m, np.full((2, 1), 10.0), np.full((2, 1), 0.01), spec)
    assert res.financing[1, 0] == pytest.approx(expected)
    assert res.gross[1, 0] == 0.0 and res.world == world


def test_a_nan_forecast_or_vol_is_flat() -> None:
    m = market([1.0] * 3)
    f = np.array([[np.nan], [10.0], [10.0]])
    v = np.array([[0.01], [np.nan], [0.01]])
    res = run(m, f, v, BookSpec(costs=FREE, capital=1e6, vol_target=0.16))
    assert res.units[:2, 0].tolist() == [0.0, 0.0] and res.units[2, 0] > 0


def test_rsim_never_reads_past_the_decision_day(acis_config) -> None:
    path = generate(LabSpec(n_inst=3, days=900, seed=4, effect=Effect(trend_sharpe=1.0)))
    a = lab_market(path)
    k = 600
    later = lambda x: np.vstack([x[:k + 1], x[k + 1:] * 1.05])        # noqa: E731  rewrite the future
    b = Market(names=a.names, days=a.days, price=later(a.price), close=later(a.close), fill=later(a.fill),
               spread=later(a.spread), carry=a.carry, nights=a.nights, q=a.q)
    spec = BookSpec(costs={n: CostModel(0.0, 0.00002) for n in a.names})
    ra = run(a, panel(a, rules.d1), carver_pct_vol(a), spec)
    rb = run(b, panel(b, rules.d1), carver_pct_vol(b), spec)
    assert np.array_equal(ra.units[:k + 1], rb.units[:k + 1])
    assert not np.array_equal(ra.units[k + 1:], rb.units[k + 1:])


def test_a_planted_trend_pays_d1_and_the_null_does_not(acis_config) -> None:
    # one seed each: a smoke check of direction only; the calibration across seeds is the lab run
    planted = generate(LabSpec(seed=11, effect=Effect(trend_sharpe=2.0)))
    null = generate(LabSpec(seed=11, effect=Effect(trend_sharpe=2.0)), null=True)
    assert annual_sharpe(run_member(planted, "D1", acis_config).daily[300:]) > 2.0
    assert abs(annual_sharpe(run_member(null, "D1", acis_config).daily[300:])) < 1.0
