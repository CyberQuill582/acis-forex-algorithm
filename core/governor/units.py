"""Base-currency units for a USD-sized order (ACIS-05 §4 `size_units`, §7 step 3; GAP-P12D-22).

The Governor decides a size in US dollars, but an order is expressed in units of the
instrument's BASE currency. Invariants:

  * One base unit is worth `usd_per_base_unit` dollars: the price when USD is the quote
    currency (EUR/USD, XAU/USD); exactly 1 when USD is the base (USD/JPY); for a cross
    (EUR/GBP) the price times the quote currency's USD rate, read from the last completed
    signal bar of its USD leg (GBP_USD, or 1 / USD_GBP).
  * A cross with no USD leg seen yet has no rate: the answer is None, and the Governor
    sizes the order zero ("no_usd_rate"). A size is never guessed.
  * `units × usd_per_base_unit` is the order's USD notional — the quantity the cluster
    and single-currency caps compare with NAV.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from core.data.bars import Bar

ACCOUNT_CCY = "USD"


def usd_per_base_unit(instrument: str, price: float,
                      bars: Mapping[str, Sequence[Bar]]) -> Decimal | None:
    base, _, quote = instrument.partition("_")
    if base == ACCOUNT_CCY:
        return Decimal("1")
    p = Decimal(str(price))
    if quote == ACCOUNT_CCY:
        return p
    for leg, invert in ((f"{quote}_{ACCOUNT_CCY}", False), (f"{ACCOUNT_CCY}_{quote}", True)):
        window = bars.get(leg)
        if window:
            rate = Decimal(str(window[-1].close))
            return p / rate if invert else p * rate
    return None
