"""Quote → account currency conversion for backtest PnL (GAP-P12D-05).

`Δprice × units` is an amount in the instrument's QUOTE currency: a USD_JPY move is
yen, and booking it as dollars inflates it ~100–150×. Every quote-currency amount
(gross, friction, financing, marks) is converted once before it reaches realised PnL
or the equity curve: XXX_USD ×1; USD_XXX ÷price; a cross (EUR_GBP) through its quote
leg's last-seen price (GBP_USD). A run lacking that leg raises rather than silently
booking pounds as dollars.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

ACCOUNT_CCY = "USD"


class ConversionUnavailable(Exception):
    """A quote-currency amount has no route to the account currency in this run."""


def quote_to_account(instrument: str, price: float, last_price: Mapping[str, float]) -> Decimal:
    """Factor converting a QUOTE-currency amount of `instrument` to ACCOUNT_CCY at
    `price` (that instrument's own price) or via a cross's quote leg."""
    base, _, quote = instrument.partition("_")
    if quote == ACCOUNT_CCY:
        return Decimal("1")
    if base == ACCOUNT_CCY:
        return Decimal("1") / Decimal(str(price))
    leg = last_price.get(f"{quote}_{ACCOUNT_CCY}")
    if leg:
        return Decimal(str(leg))
    leg = last_price.get(f"{ACCOUNT_CCY}_{quote}")
    if leg:
        return Decimal("1") / Decimal(str(leg))
    raise ConversionUnavailable(
        f"{instrument}: no {quote}_{ACCOUNT_CCY} or {ACCOUNT_CCY}_{quote} price seen yet — "
        f"a cross needs its conversion leg in the same run")
