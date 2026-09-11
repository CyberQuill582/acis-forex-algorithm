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

import bisect
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping, Sequence

CCY_SERIES: dict[str, tuple[str, str | None]] = {
    "USD": ("usd_effr", None),
    "EUR": ("eur_dfr", None),
    "GBP": ("gbp_sonia", None),
    "JPY": ("jpy_tona", None),
    "CHF": ("chf_saron", None),
    "CAD": ("cad_corra", None),
    "AUD": ("bis_policy", "AU"),
}
OANDA_MAJOR_FEE_PCT = Decimal("1.00")
DEFAULT_GOLD_LEASE_PCT = Decimal("0.25")


class StaleRateError(Exception):
    """No rate for a currency within `max_stale_days` of the requested day."""


class RateTable:
    """Daily overnight rates (% p.a.) per currency, forward-filled up to a limit."""

    def __init__(self, series: Mapping[str, Sequence[tuple[date, float]]],
                 max_stale_days: int = 10) -> None:
        self._days: dict[str, list[date]] = {}
        self._vals: dict[str, list[Decimal]] = {}
        for ccy, pts in series.items():
            pts = sorted(pts)
            self._days[ccy] = [d for d, _ in pts]
            self._vals[ccy] = [Decimal(str(v)) for _, v in pts]
        self._max_stale = max_stale_days

    def rate(self, ccy: str, day: date) -> Decimal:
        days = self._days.get(ccy)
        if not days:
            raise StaleRateError(f"no rate series for {ccy}")
        i = bisect.bisect_right(days, day) - 1
        if i < 0:
            raise StaleRateError(f"{ccy}: {day} is before the series starts ({days[0]})")
        if (day - days[i]).days > self._max_stale:
            raise StaleRateError(f"{ccy}: last rate {days[i]} is {(day - days[i]).days} days "
                                 f"before {day} (> {self._max_stale})")
        return self._vals[ccy][i]


def load_rate_table(macro_dir: Path, max_stale_days: int = 10) -> RateTable:
    """Read the normalised CSVs written by scripts/download_macro.py."""
    series: dict[str, list[tuple[date, float]]] = {}
    for ccy, (sid, area) in CCY_SERIES.items():
        path = Path(macro_dir) / f"{sid}.csv"
        with path.open(newline="", encoding="utf-8") as f:
            rows = csv.DictReader(f)
            series[ccy] = [(date.fromisoformat(r["date"]), float(r["value"])) for r in rows
                           if area is None or r.get("area") == area]
    return RateTable(series, max_stale_days)


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
