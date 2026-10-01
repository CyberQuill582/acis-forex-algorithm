"""The R1 research universe as code (R1-D5, owner-ratified 2026-09-25; tests/backtest/OOS_VALIDATION.md).

Thirty instruments: FX 16, metals 3, indices 8, energy 3. Seven are HELD OUT and LOCKED (drawn by
sha256("ACIS-R1-holdout-2026-09-25|" + symbol); re-salting after any real-data look is forbidden):
they are never explored, graded once per assembled portfolio, raw and kill-only (stage C).

Each row pins the Dukascopy archive symbol and its point scale (an integer price ÷ scale), both
verified 2026-10-01 against the archive: every symbol's December-2025 hourly candles decode to its
known level (EUR/USD 1.160, gold 4,222, US500 6,841, Nikkei 50,274, copper 5.31, natural gas 4.81),
and `first` is the first month (YYYY-MM) with hourly candles, all <= 2013 as R1-D5 requires.
"""

from __future__ import annotations

from typing import NamedTuple


class Instrument(NamedTuple):
    name: str           # ACIS name
    duka: str           # Dukascopy archive symbol
    scale: int          # price = integer / scale
    first: str          # first month with hourly candles, YYYY-MM
    asset_class: str    # fx | metal | index | energy
    quote: str          # quote currency
    held_out: bool      # LOCKED: never explored (stage C only)
    plausible: tuple[float, float]   # a SCALE check, wide on purpose: a wrong scale lands 10x-100x outside,
                                     # while real 2012-2025 extremes (the 2015 SNB de-peg, silver at $84,
                                     # WTI at $130) must land inside


def _fx(name: str, lo: float, hi: float, held_out: bool = False) -> Instrument:
    base, quote = name.split("_")
    return Instrument(name, base + quote, 1_000 if quote == "JPY" else 100_000, "2012-01", "fx", quote,
                      held_out, (lo, hi))


UNIVERSE: tuple[Instrument, ...] = (
    _fx("EUR_USD", 0.8, 1.7), _fx("USD_JPY", 70.0, 170.0), _fx("GBP_USD", 1.0, 2.2),
    _fx("AUD_USD", 0.5, 1.2), _fx("USD_CAD", 0.9, 1.6), _fx("USD_CHF", 0.6, 1.3),
    _fx("EUR_GBP", 0.6, 1.0), _fx("EUR_JPY", 90.0, 200.0), _fx("GBP_JPY", 110.0, 230.0),
    _fx("AUD_JPY", 55.0, 120.0), _fx("EUR_CHF", 0.7, 1.8), _fx("EUR_AUD", 1.1, 2.1),
    _fx("CHF_JPY", 75.0, 210.0), _fx("AUD_NZD", 0.8, 1.6, True), _fx("NZD_USD", 0.5, 0.95, True),
    _fx("CAD_JPY", 60.0, 125.0, True),
    Instrument("XAU_USD", "XAUUSD", 1_000, "2012-01", "metal", "USD", False, (800.0, 9000.0)),
    Instrument("XAG_USD", "XAGUSD", 1_000, "2012-01", "metal", "USD", False, (8.0, 200.0)),
    Instrument("XCU_USD", "COPPERCMDUSD", 10_000, "2012-03", "metal", "USD", True, (1.0, 15.0)),
    Instrument("US500", "USA500IDXUSD", 1_000, "2012-01", "index", "USD", False, (1100.0, 8000.0)),
    Instrument("US30", "USA30IDXUSD", 1_000, "2013-09", "index", "USD", False, (12000.0, 55000.0)),
    Instrument("UK100", "GBRIDXGBP", 1_000, "2012-01", "index", "GBP", False, (4500.0, 11000.0)),
    Instrument("JP225", "JPNIDXJPY", 1_000, "2012-01", "index", "JPY", False, (7500.0, 60000.0)),
    Instrument("EU50", "EUSIDXEUR", 1_000, "2012-01", "index", "EUR", False, (1800.0, 7000.0)),
    Instrument("AUS200", "AUSIDXAUD", 1_000, "2013-01", "index", "AUD", False, (3800.0, 10000.0)),
    Instrument("GER40", "DEUIDXEUR", 1_000, "2013-09", "index", "EUR", True, (7000.0, 27000.0)),
    Instrument("US100", "USATECHIDXUSD", 1_000, "2012-01", "index", "USD", True, (2000.0, 30000.0)),
    Instrument("UKOIL", "BRENTCMDUSD", 1_000, "2012-01", "energy", "USD", False, (10.0, 250.0)),
    Instrument("NATGAS", "GASCMDUSD", 10_000, "2012-08", "energy", "USD", False, (0.5, 25.0)),
    Instrument("USOIL", "LIGHTCMDUSD", 1_000, "2012-01", "energy", "USD", True, (5.0, 250.0)),
)
BY_NAME = {i.name: i for i in UNIVERSE}
HELD_OUT = frozenset(i.name for i in UNIVERSE if i.held_out)
EXPLORED = tuple(i.name for i in UNIVERSE if not i.held_out)
