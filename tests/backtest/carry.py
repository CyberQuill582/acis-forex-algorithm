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
from typing import Sequence

_TRIPLE_DAY = {"tom_next": 2, "financing_daily": 4}     # Mon=0 … Fri=4


def swap_multiplier(night: date, swap_convention: str = "tom_next") -> int:
    """Days of financing charged for the rollover on business day `night`."""
    try:
        triple = _TRIPLE_DAY[swap_convention]
    except KeyError:
        raise ValueError(f"unknown swap_convention {swap_convention!r}; "
                         f"declared: {sorted(_TRIPLE_DAY)}") from None
    if night.weekday() >= 5:
        raise ValueError(f"{night} is a weekend day — no rollover happens then")
    return 3 if night.weekday() == triple else 1


def carry_charge(*, nights: Sequence[date], daily_swap: Decimal,
                 swap_convention: str = "tom_next") -> Decimal:
    """Total financing over the held business-day rollovers for a constant one-day
    amount `daily_swap` (signed, account currency) — the triple day counts ×3."""
    return sum((Decimal(swap_multiplier(n, swap_convention)) * daily_swap
                for n in nights), Decimal("0"))
