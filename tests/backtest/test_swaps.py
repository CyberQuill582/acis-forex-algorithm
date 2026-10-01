"""The FTMO swap table as C8 data (GAP-P12D-93): the markup decomposition, its scale against the
published ranges, and a charge calendar that refuses what no source states."""

from __future__ import annotations

from datetime import date

import pytest

from tests.backtest.swaps import UnverifiedCalendar, acis_name, load_ftmo

TABLE = load_ftmo()


def test_the_snapshot_is_dated_and_named_for_acis() -> None:
    assert TABLE.fetched == date(2026, 9, 25) and TABLE.venue == "ftmo"
    assert acis_name("EUR/USD") == "EUR_USD" and acis_name("US500.cash") == "US500"
    eu = TABLE.entry("EUR_USD")
    assert (eu.swap_long, eu.swap_short, eu.point) == (-9.49, 0.36, 1e-05)


def test_the_markup_is_the_rate_free_half_sum() -> None:
    eu = TABLE.entry("EUR_USD")
    assert eu.markup_points == pytest.approx(4.565)
    # a fair differential f moves both sides oppositely and leaves the markup unchanged
    assert -((eu.swap_long + 3.0) + (eu.swap_short - 3.0)) / 2 == pytest.approx(eu.markup_points)


@pytest.mark.parametrize("name, price, lo, hi", [
    ("EUR_USD", 1.17, 0.9, 2.6), ("USD_JPY", 148.0, 0.9, 2.6),     # PLAN_R1: 0.9–2.6%/yr on FX
    ("XAU_USD", 3700.0, 3.5, 6.0),                                   # ~4.8% on gold
    ("US500", 6600.0, 3.6, 5.0),                                     # 3.6–5.0% on index CFDs
])
def test_markups_land_in_the_published_ranges(name, price, lo, hi) -> None:
    assert lo <= TABLE.entry(name).markup_pct(price) <= hi


def test_the_calendar_charges_forex_three_nights_on_wednesday_and_refuses_unverified_classes() -> None:
    assert [TABLE.nights("EUR_USD", date(2026, 9, d)) for d in (28, 29, 30)] == [1, 1, 3]   # Mon..Wed
    assert TABLE.nights("EUR_USD", date(2026, 10, 2)) == 1                                # Friday
    with pytest.raises(UnverifiedCalendar):
        TABLE.nights("US500", date(2026, 9, 30))
    with pytest.raises(ValueError):
        TABLE.nights("EUR_USD", date(2026, 10, 3))
