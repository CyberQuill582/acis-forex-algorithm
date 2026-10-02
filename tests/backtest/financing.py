"""Dated overnight-financing model for the backtest (GAP-P12D-03/06, master §13).

Builds the harness's `financing(instrument, night, direction) -> annualised %` hook
from the daily overnight-rate series fetched by scripts/download_macro.py.

    rate(side) = direction × (r_base − r_quote) − broker_fee

— OANDA's published method: position value × funding rate × 1/365, where the funding
rate is the tom-next (≈ overnight money-market) differential adjusted by an annual
admin fee (1.00% for the majors) that is charged to BOTH sides. A long earns the
differential when the base currency yields more; the short pays it; both pay the fee.

Per-currency overnight series (declared proxies in parentheses):

    USD  effective fed funds (DFF)          GBP  SONIA          JPY  TONA (BoJ call rate)
    EUR  ECB deposit facility (overnight     CHF  SARON          CAD  CORRA
         euro rates traded at ~DFR from     AUD  RBA cash-rate target (BIS) — the RBA
         2015; slightly above it before)         steers the overnight rate onto it
    XAU  an ASSUMED gold lease rate (default 0.25%/yr): LBMA stopped publishing
         GOFO in 2015 and no free lease series exists — run a 0–1% sensitivity band.

A series is forward-filled across non-publication days (weekends, holidays), but a
gap longer than `max_stale_days` raises rather than silently carrying a stale rate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from core.data.rates import (CCY_SERIES, DEFAULT_GOLD_LEASE_PCT, RateTable,  # noqa: F401  (moved, R1.6)
                             StaleRateError, load_rate_table)

OANDA_MAJOR_FEE_PCT = Decimal("1.00")


def make_financing(table: RateTable, *, broker_fee_pct: Decimal = OANDA_MAJOR_FEE_PCT,
                   gold_lease_pct: Decimal = DEFAULT_GOLD_LEASE_PCT
                   ) -> Callable[[str, date, int], Decimal]:
    """The harness `financing` hook: annualised % for holding `direction` on
    `instrument` over the rollover on `night` (positive = the position is paid)."""
    fee = Decimal(str(broker_fee_pct))
    lease = Decimal(str(gold_lease_pct))

    def financing(instrument: str, night: date, direction: int) -> Decimal:
        base, _, quote = instrument.partition("_")
        r_base = lease if base == "XAU" else table.rate(base, night)
        r_quote = table.rate(quote, night)
        return Decimal(direction) * (r_base - r_quote) - fee

    return financing
