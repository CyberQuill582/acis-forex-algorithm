"""Governor sizes in BASE-currency units (ACIS-05 §4/§7 step 3; GAP-P12D-22).

The formula's raw size is 486 USD for every signal below (1000 × 0.6 conviction ×
0.81 regime). A unit of base currency is worth the price when USD is the quote, exactly
$1 when USD is the base, and the price × the quote leg's USD rate for a cross.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import MappingProxyType

from core.data.bars import Bar
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import BASELINE_UNITS, _pair_signals, mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal

RAW_USD = Decimal("486")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"))


def test_usd_base_instrument_is_sized_in_dollars_not_divided_by_the_yen_price() -> None:
    gov, _ = mk_governor()
    jpy = mk_signal(instrument="USD_JPY", entry_price=155.0, stop_loss=154.5, take_profit=156.0)
    order = gov.allocate(jpy, mk_portfolio(), mk_regime(), T0)
    assert order.reason == "formula" and order.size_units == _q(RAW_USD)   # was 486 / 155 = 3.14


def test_usd_quote_and_gold_divide_by_the_price() -> None:
    gov, _ = mk_governor()
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).size_units == BASELINE_UNITS
    gold = mk_signal(instrument="XAU_USD", entry_price=2000.0, stop_loss=1990.0, take_profit=2020.0)
    assert gov.allocate(gold, mk_portfolio(), mk_regime(), T0).size_units == _q(RAW_USD / Decimal("2000"))


def test_a_cross_converts_through_its_quote_leg_or_sizes_zero() -> None:
    gov, log = mk_governor()
    cross = mk_signal(instrument="EUR_GBP", entry_price=0.86, stop_loss=0.855, take_profit=0.87)
    blind = gov.allocate(cross, mk_portfolio(), mk_regime(), T0)
    assert blind.size_units == 0 and blind.reason == "no_usd_rate"     # never guessed
    gov.observe_bar("GBP_USD", Bar(ts_open=T0 - timedelta(minutes=1), open=1.25, high=1.2501,
                                   low=1.2499, close=1.25, spread=0.0001, duration_s=60))
    sized = gov.allocate(cross, mk_portfolio(), mk_regime(), T0)
    assert sized.size_units == _q(RAW_USD / (Decimal("0.86") * Decimal("1.25")))


def test_usd_base_notional_meets_the_currency_cap_in_dollars() -> None:
    """A long USD/JPY adds +486 USD of USD delta: with 2,600 already on, it crosses the
    3,000 cap (30% of 10,000 NAV)."""
    gov, log = mk_governor()
    jpy = mk_signal(instrument="USD_JPY", entry_price=155.0, stop_loss=154.5, take_profit=156.0)
    heavy_usd = mk_portfolio(per_currency_delta=MappingProxyType({"USD": Decimal("2600")}))
    assert gov.allocate(jpy, heavy_usd, mk_regime(), T0).reason == "currency_delta_cap"
    light_usd = mk_portfolio(per_currency_delta=MappingProxyType({"USD": Decimal("2400")}))
    assert gov.allocate(jpy, light_usd, mk_regime(), T0).reason == "formula"


def test_pair_legs_balance_without_the_yen_leg_shrinking_both() -> None:
    """EUR/USD 486/1.1 = 441.82 EUR against USD/JPY 486 USD: both legs take 441.82. Before
    the fix the yen leg was 3.14 units, which shrank the whole pair ~140×."""
    gov, _ = mk_governor()
    oa, ob = gov.allocate_group(_pair_signals(), mk_portfolio(), mk_regime(), T0)
    assert oa.size_units == ob.size_units == BASELINE_UNITS
