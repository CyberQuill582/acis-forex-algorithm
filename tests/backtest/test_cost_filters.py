"""Master §5.6's two cost filters (GAP-P12D-115): Carver's speed limit and swap viability."""

from __future__ import annotations

import pytest

from tests.backtest.cost_filters import (SPEED_LIMIT_SR, SWAP_LIMIT_SR, admit, forecast_turnover,
                                         sr_cost_per_trade, time_in_market)


def test_turnover_is_carvers_mean_absolute_change_of_f_over_10_annualised() -> None:
    assert forecast_turnover([0, 10, 0, 10, 0]) == pytest.approx(256.0)        # one average position a day
    assert forecast_turnover([10.0] * 50) == 0.0
    assert forecast_turnover([float("nan"), 0, 5, 5]) == pytest.approx(0.25 * 256)   # NaN pairs skipped
    assert time_in_market([10, -10, 5, float("nan")]) == pytest.approx(25 / 30)


def test_cost_per_trade_is_risk_adjusted_by_annual_price_vol() -> None:
    # Carver's blog example: 0.005 SR a trade allows (0.13 / 0.005) - 4 rolls = 22 turnovers a year
    assert sr_cost_per_trade(0.0005, 0.00625) == pytest.approx(0.005)           # 0.0005 / (0.00625 × 16)
    assert (0.13 / 0.005) - 4 == 22


def test_the_speed_limit_admits_at_or_below_point_ten() -> None:
    ok = admit("X", "EWMAC64_256", turnover=7.5, cost_per_trade_sr=0.01, annual_vol_pct=10.0)
    assert ok.trading_cost_sr == pytest.approx(0.075) and ok.admitted
    fast = admit("X", "EWMAC16_64", turnover=16.3, cost_per_trade_sr=0.01, annual_vol_pct=10.0)
    assert fast.trading_cost_sr > SPEED_LIMIT_SR and not fast.admitted
    rolled = admit("X", "EWMAC64_256", turnover=7.5, cost_per_trade_sr=0.01, rolls=4, annual_vol_pct=10.0)
    assert not rolled.admitted                                                   # (7.5 + 4) × 0.01


def test_swap_viability_divides_the_markup_by_vol_at_the_time_in_market() -> None:
    # EUR/USD at FTMO: markup 1.42%/yr, a trend member in the market ~all the time, vol ~7%: 0.20 SR
    eur = admit("EUR_USD", "D1", turnover=5.0, cost_per_trade_sr=0.001, markup_pct=1.42,
                member_time_in_market=1.0, annual_vol_pct=7.0)
    assert eur.swap_cost_sr == pytest.approx(0.2029, abs=1e-3) and not eur.admitted
    free = admit("EUR_USD", "D1", turnover=5.0, cost_per_trade_sr=0.001, annual_vol_pct=7.0)
    assert free.swap_cost_sr == 0.0 and free.admitted                           # the swap-free world
    assert SWAP_LIMIT_SR == pytest.approx(0.10)
