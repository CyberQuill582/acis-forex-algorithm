"""Overnight carry / swap accounting for the backtest (ACIS-09 §13, master §13).

Rollovers happen on BUSINESS days only (Mon–Fri); nothing rolls on Saturday or
Sunday. The weekend is paid for inside the week instead, which is exactly why the
§13 "triple-swap Wednesday" glitch class exists:

  tom_next         (spot FX, T+2) the Wednesday rollover moves the value date
                   Fri→Mon, so it is charged THREE days; Mon/Tue/Thu/Fri one each
                   (7 days per week). Charging Sat/Sun as well would bill the
                   weekend twice.
  financing_daily  (CFD-style daily financing — declared for XAU_USD in
                   config/instruments.yaml; not defined by the spec) the weekend is
                   billed on FRIDAY instead: Friday ×3, Mon–Thu ×1 (7 days per week),
                   per OANDA's published CFD financing convention.

An undeclared convention is an error — silently charging one night would
under-price every weekend hold. Decimal, F17.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Sequence

from core.data.rates import swap_multiplier  # noqa: F401  (moved, R1.6)

_DAYS_PER_YEAR = Decimal("365")                          # OANDA: value × rate × 1/365

# (instrument, business-day rollover date, direction) -> annualised % for THAT side:
# the rate differential net of the broker fee, so a long and a short never share a sign
# (GAP-P12D-06). Built by tests/backtest/financing.py from dated overnight rates.
FinancingRate = Callable[[str, date, int], Decimal]


def financing_charge(*, instrument: str, direction: int, value: Decimal,
                     nights: Sequence[date], rate: FinancingRate,
                     swap_convention: str = "tom_next") -> Decimal:
    """Financing over the held business-day rollovers, in the QUOTE currency:
    Σ value × rate(side, night)/100/365 × the convention's multiplier. `value` is the
    position value (units × price) at the rollover — entry price stands in for it
    (a declared approximation; holds are capped at 48 h)."""
    total = Decimal("0")
    for night in nights:
        r = Decimal(str(rate(instrument, night, direction)))
        total += value * r / Decimal("100") / _DAYS_PER_YEAR \
            * Decimal(swap_multiplier(night, swap_convention))
    return total


def carry_charge(*, nights: Sequence[date], daily_swap: Decimal,
                 swap_convention: str = "tom_next") -> Decimal:
    """Total financing over the held business-day rollovers for a constant one-day
    amount `daily_swap` (signed, account currency) — the triple day counts ×3."""
    return sum((Decimal(swap_multiplier(n, swap_convention)) * daily_swap
                for n in nights), Decimal("0"))
