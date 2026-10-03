"""The factory's FX signals (GAP-P12D-158): FXVALUE's 5-year PPP change and AMP's rank weights, and DCARRY's
average forward discount, each read only from data dated before the month it trades."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from core.data.rates import RateTable
from tests.backtest import dollar_carry, fx_value


def _days(a: date, b: date) -> list[date]:
    return [a + timedelta(days=k) for k in range((b - a).days + 1) if (a + timedelta(days=k)).weekday() < 5]


def _spot(level: dict[str, callable], a=date(2005, 1, 3), b=date(2013, 3, 29)) -> dict:
    return {c: {d: f(d) for d in _days(a, b)} for c, f in level.items()}


def _cpi(growth: dict[str, float]) -> dict:
    months = [(y, m) for y in range(2004, 2014) for m in range(1, 13)]
    return {a: {mo: 100.0 * (1 + g) ** k for k, mo in enumerate(months)} for a, g in growth.items()}


FLAT = {a: 0.0 for a in fx_value.AREA.values()}


def test_value_is_the_5_year_fall_of_the_spot_net_of_relative_inflation_read_4_months_late() -> None:
    halving = lambda d: 2.0 if d < date(2009, 6, 1) else 1.0                       # noqa: E731
    spot = _spot({c: (halving if c == "JPY" else (lambda d: 1.0)) for c in fx_value.CCYS})
    assert fx_value.value("JPY", (2012, 1), spot, _cpi(FLAT)) == pytest.approx(math.log(2.0))
    hot = dict(FLAT, JP=0.01)                                                       # 1% a month more inflation
    assert fx_value.value("JPY", (2012, 1), spot, _cpi(hot)) == pytest.approx(math.log(2.0) - 60 * math.log(1.01))
    late = _cpi(FLAT)
    late["JP"][(2011, 12)] = 999.0                                                   # month m-1: not yet read
    assert fx_value.value("JPY", (2012, 1), spot, late) == pytest.approx(math.log(2.0))


def test_ranks_put_the_cheapest_at_seven_usd_at_zero_and_usd_pairs_take_the_opposite_sign() -> None:
    step = {"EUR": 0.9, "JPY": 0.5, "GBP": 1.2, "AUD": 0.8, "CAD": 1.1, "CHF": 1.5}  # now / old spot
    spot = _spot({c: (lambda d, k=k: 1.0 if d < date(2010, 1, 1) else k) for c, k in step.items()})
    r = fx_value.ranks((2012, 1), spot, _cpi(FLAT))
    assert r["JPY"] == 7 and r["CHF"] == 1 and r["USD"] == 4                         # 3 cheaper, 3 dearer
    assert fx_value.pair_forecast("EUR_USD", r) == pytest.approx(5.0 * (r["EUR"] - 4))
    assert fx_value.pair_forecast("USD_JPY", r) == -15.0


def test_the_panel_holds_month_ms_ranks_through_month_m_plus_1_and_nothing_before() -> None:
    spot = _spot({c: (lambda d: 1.0 if d < date(2010, 1, 1) else 0.9) for c in fx_value.CCYS})
    days = _days(date(2012, 1, 2), date(2012, 3, 30))
    f = fx_value.panel(days, ["EUR_USD", "USD_JPY"], spot, _cpi(FLAT), (2012, 1))
    jan = [t for t, d in enumerate(days) if d.month == 1]
    assert np.isnan(f[jan]).all() and np.isfinite(f[[t for t, d in enumerate(days) if d.month > 1]]).all()


def _rates(foreign: float, usd: float, a=date(2011, 12, 1), b=date(2012, 4, 30)) -> RateTable:
    pts = {c: [(d, foreign) for d in _days(a, b)] for c in dollar_carry.FOREIGN}
    pts["USD"] = [(d, usd if d < date(2012, 2, 20) else foreign + 1.0) for d in _days(a, b)]
    return RateTable(pts)


def test_dcarry_is_long_foreign_when_the_average_foreign_rate_is_higher_and_reads_rates_3_days_back() -> None:
    days = _days(date(2012, 1, 2), date(2012, 3, 30))
    rates = _rates(foreign=2.0, usd=0.5)
    assert dollar_carry.afd(rates, date(2012, 1, 31)) == pytest.approx(1.5)
    f = dollar_carry.panel(days, ["EUR_USD", "USD_JPY"], rates, (2012, 1))
    feb = [t for t, d in enumerate(days) if d.month == 2]
    mar = [t for t, d in enumerate(days) if d.month == 3]
    assert (f[feb] == [10.0, -10.0]).all() and (f[mar] == [-10.0, 10.0]).all()      # USD above from 20 February
    assert np.isnan(f[[t for t, d in enumerate(days) if d.month == 1]]).all()
    edge = _rates(foreign=2.0, usd=0.5)
    assert dollar_carry.afd(edge, date(2012, 2, 22)) == pytest.approx(1.5)          # 19 February's rates: still below
