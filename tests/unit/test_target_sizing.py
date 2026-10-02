"""R1.6's shared sizing (ACIS-05 v1.7 §6.4; master §5.5 v2.26, §5 C8, D-a): Carver's average
position and band, the one lot rule, the paper/practice one-lot cap, and RSIM trading through the
very same function the Governor uses (B0(d) by identity)."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

import core.governor.target as gt
from core.optimizer.costs import CostModel
from core.signals import rules
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.rsim import BookSpec, Lots, panel, run
from tests.backtest.rsim_lab import carver_pct_vol, lab_market

ONE = Decimal("1")
KW = dict(cash_vol=1_000.0, weight=1.0, idm=1.0, buffer=0.10, step=ONE, minimum=ONE)


def _a(pct_vol=0.01, close=1.0, q=1.0) -> float:
    return 1_000.0 / (pct_vol * close * q)                          # A = cash_vol / (σ% · close · q)


def test_the_average_position_and_optimum_are_carvers() -> None:
    a = _a()                                                         # 100,000 units
    assert gt.banded_target(0.0, 10.0, 0.01, 1.0, 1.0, **KW) == Decimal(str(int(0.9 * a)))   # to the band's edge
    assert gt.banded_target(a, 10.0, 0.01, 1.0, 1.0, **KW) == Decimal(str(int(a)))          # at the optimum: kept
    assert gt.banded_target(0.0, 10.0, 0.02, 1.0, 1.0, **KW) == Decimal(str(int(0.9 * a / 2)))   # double vol: half


def test_the_band_keeps_a_position_inside_and_trades_one_outside_to_the_nearest_edge() -> None:
    a = _a()
    assert gt.banded_target(0.95 * a, 10.0, 0.01, 1.0, 1.0, **KW) == Decimal(str(int(0.95 * a)))   # inside
    assert gt.banded_target(1.5 * a, 10.0, 0.01, 1.0, 1.0, **KW) == Decimal(str(int(1.1 * a)))     # above: upper edge
    assert gt.banded_target(-0.5 * a, 10.0, 0.01, 1.0, 1.0, **KW) == Decimal(str(int(0.9 * a)))    # below: lower edge


def test_the_lot_rule_rounds_toward_zero_and_flattens_below_the_minimum() -> None:
    lots = dict(KW, buffer=0.0, step=Decimal("1000"), minimum=Decimal("1000"))      # no band: the rounding alone
    assert gt.banded_target(0.0, 0.15, 0.01, 1.0, 1.0, **lots) == Decimal("1000")    # 1,500 -> 1,000 (toward zero)
    assert gt.banded_target(0.0, -0.15, 0.01, 1.0, 1.0, **lots) == Decimal("-1000")
    assert gt.banded_target(0.0, 0.05, 0.01, 1.0, 1.0, **lots) == Decimal("0")       # 500 < the minimum -> flat
    assert gt.banded_target(0.0, 0.25, 0.01, 1.0, 1.0, **dict(lots, buffer=0.10)) == Decimal("0")   # the band keeps flat
    with pytest.raises(ValueError):
        gt.target_on_lots(Decimal("5000"), Decimal("1000"), Decimal("500"))


def test_the_practice_cap_holds_at_most_one_lot_keeps_the_sign_and_never_raises_a_flat_target() -> None:
    capped = dict(KW, step=Decimal("1000"), minimum=Decimal("1000"), cap=Decimal("1000"))
    assert gt.banded_target(0.0, 20.0, 0.01, 1.0, 1.0, **capped) == Decimal("1000")
    assert gt.banded_target(1000.0, -20.0, 0.01, 1.0, 1.0, **capped) == Decimal("-1000")   # a flip, still one lot
    assert gt.banded_target(0.0, 0.05, 0.01, 1.0, 1.0, **capped) == Decimal("0")           # flat stays flat


def test_no_forecast_or_no_volatility_targets_flat() -> None:
    for f, v in ((float("nan"), 0.01), (10.0, float("nan")), (10.0, 0.0)):
        assert gt.banded_target(5_000.0, f, v, 1.0, 1.0, **KW) == Decimal("0")
    with pytest.raises(ValueError):
        gt.banded_target(0.0, 10.0, 0.01, 1.0, 1.0, **dict(KW, idm=2.6))


def test_rsim_trades_through_the_governors_function_and_its_practice_book_never_exceeds_one_lot() -> None:
    import tests.backtest.rsim as rsim
    assert rsim.banded_target is gt.banded_target                    # one implementation, by identity
    m = lab_market(generate(LabSpec(n_inst=3, days=600, seed=4, effect=Effect(trend_sharpe=1.0))))
    f, v = panel(m, rules.d1), carver_pct_vol(m)
    lot = 1_000.0
    spec = BookSpec(costs={n: CostModel(0.0, 0.0) for n in m.names}, capital=10_000.0, vol_target=0.10,
                    lots={n: Lots(lot, lot) for n in m.names}, lot_cap={n: lot for n in m.names})
    book = run(m, f, v, spec)
    assert np.abs(book.units).max() <= lot and np.abs(book.units).max() == lot     # capped, and it does trade
    weight, cash_vol = 1.0 / len(m.names), spec.capital * spec.vol_target / gt.VOL_DAYS
    for i in range(len(m.names)):                                    # the same sequence, by hand
        held = 0.0
        for t in range(len(m.days)):
            held = float(gt.banded_target(held, f[t, i], v[t, i], m.close[t, i], m.q[t, i], cash_vol=cash_vol,
                                          weight=weight, idm=1.0, buffer=0.10, step=Decimal("1000"),
                                          minimum=Decimal("1000"), cap=Decimal("1000")))
            assert book.units[t, i] == held
