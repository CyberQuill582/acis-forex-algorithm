"""Overnight carry / swap accounting for the backtest (ACIS-09 §13, master §13).

Triple-swap Wednesday: under the `tom_next` convention, a position held over
Wednesday night is charged THREE days of swap (Wed→Thu spot settles T+2 over the
weekend). A backtest that charges a flat one-day swap every night mis-prices
carry — the glitch class §13 names. Decimal, F17.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence


def swap_multiplier(night: date, swap_convention: str = "tom_next") -> int:
    """Days of swap charged for holding over `night`. Wednesday = 3 under
    tom_next (Mon=0 … Sun=6 → Wednesday is weekday 2)."""
    if swap_convention == "tom_next" and night.weekday() == 2:
        return 3
    return 1


def carry_charge(*, nights: Sequence[date], daily_swap: Decimal,
                 swap_convention: str = "tom_next") -> Decimal:
    """Total swap charged over the held nights — the Wednesday night counts triple.
    `daily_swap` is the (signed) one-night swap in account currency."""
    return sum((Decimal(swap_multiplier(n, swap_convention)) * daily_swap
                for n in nights), Decimal("0"))
