"""Phase-12 tests for the dated financing model (GAP-P12D-03/06)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests.backtest.financing import (RateTable, StaleRateError, load_rate_table,
                                      make_financing)

MACRO = Path(__file__).resolve().parents[2] / "data" / "macro"


def _table(**series) -> RateTable:
    return RateTable({k: v for k, v in series.items()})


def test_long_and_short_get_opposite_differential_and_both_pay_the_fee() -> None:
    t = _table(EUR=[(date(2023, 6, 1), 3.25)], USD=[(date(2023, 6, 1), 5.08)])
    fin = make_financing(t, broker_fee_pct=Decimal("1.0"))
    # EUR yields less than USD: the long pays the gap, the short earns it; fee hits both
    assert fin("EUR_USD", date(2023, 6, 1), 1) == Decimal("3.25") - Decimal("5.08") - 1
    assert fin("EUR_USD", date(2023, 6, 1), -1) == Decimal("5.08") - Decimal("3.25") - 1


def test_usd_jpy_carry_trade_sign() -> None:
    t = _table(USD=[(date(2023, 6, 1), 5.08)], JPY=[(date(2023, 6, 1), -0.07)])
    fin = make_financing(t)
    assert fin("USD_JPY", date(2023, 6, 1), 1) > 3            # the famous positive carry
    assert fin("USD_JPY", date(2023, 6, 1), -1) < -6


def test_forward_fill_over_weekend_but_stale_gap_raises() -> None:
    t = _table(USD=[(date(2023, 6, 2), 5.0)], EUR=[(date(2023, 6, 2), 3.0)])
    fin = make_financing(t, broker_fee_pct=Decimal("0"))
    assert fin("EUR_USD", date(2023, 6, 4), 1) == Decimal("-2.0")        # Sunday → Friday's
    with pytest.raises(StaleRateError):
        fin("EUR_USD", date(2023, 6, 20), 1)                             # 18 days stale
    with pytest.raises(StaleRateError):
        fin("EUR_USD", date(2023, 6, 1), 1)                              # before series start
    with pytest.raises(StaleRateError):
        fin("EUR_GBP", date(2023, 6, 2), 1)                              # no GBP series at all


def test_gold_uses_the_declared_lease_assumption() -> None:
    t = _table(USD=[(date(2023, 6, 1), 5.0)])
    fin = make_financing(t, broker_fee_pct=Decimal("1.0"), gold_lease_pct=Decimal("0.5"))
    assert fin("XAU_USD", date(2023, 6, 1), 1) == Decimal("0.5") - 5 - 1   # long gold pays
    assert fin("XAU_USD", date(2023, 6, 1), -1) == Decimal("5") - Decimal("0.5") - 1


@pytest.mark.skipif(not (MACRO / "usd_effr.csv").exists(), reason="macro data not downloaded")
def test_real_rates_reproduce_known_regimes() -> None:
    """Sanity against history: ZIRP-era USD ≈ 0, 2023 USD ≈ 5, JPY negative-rate era,
    and a mid-2023 long USD_JPY that EARNED carry."""
    t = load_rate_table(MACRO)
    assert t.rate("USD", date(2013, 6, 3)) < Decimal("0.25")
    assert Decimal("4.5") < t.rate("USD", date(2023, 9, 1)) < Decimal("5.6")
    assert t.rate("JPY", date(2020, 6, 1)) < 0
    assert t.rate("CHF", date(2020, 6, 1)) < Decimal("-0.5")
    assert make_financing(t)("USD_JPY", date(2023, 9, 1), 1) > 3
