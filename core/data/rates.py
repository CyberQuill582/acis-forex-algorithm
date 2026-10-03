"""Dated overnight rates and the swap calendar (master §13; R1.6 moved them here from the harness).

One implementation for the research simulator, the harness and the runtime: the TREND family
reads the EXCESS-return price (closes compounded with the dated carry differential), so the
engine needs the same rates and the same rollover calendar RSIM graded with (ACIS-04 v1.6 §4b).

Mental model:
  * A `RateTable` holds daily overnight rates (% p.a.) per currency, forward-filled across
    non-publication days, but a gap longer than its currency's limit RAISES (never a stale rate).
    The limit follows the source's publication cadence (R6-1 as amended by GAP-P12D-146): the
    daily overnight rates allow `max_stale_days`, the weekly sources (`WEEKLY_SOURCES`) their own.
    `load_rate_table` reads the normalised CSVs scripts/download_macro.py writes; the per-
    currency proxies are declared in tests/backtest/financing.py's docstring. A MISSING file leaves
    its currency without a series, so only the pairs that read it are stale (R16I-08).
  * `swap_multiplier`: rollovers happen on business days only; tom_next (spot FX, T+2) charges
    the Wednesday rollover three days, financing_daily (CFD-style) charges Friday three days.
    An undeclared convention is an error. Declared simplifications (R16E-05): USD/CAD's T+1
    Thursday triple is treated as Wednesday, holiday value dates add no days, and every rate is
    divided by 365 although USD, EUR and CHF money markets count ACT/360.
"""

from __future__ import annotations

import bisect
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

CCY_SERIES: dict[str, tuple[str, str | None]] = {
    "USD": ("usd_effr", None),
    "EUR": ("eur_dfr", None),
    "GBP": ("gbp_sonia", None),
    "JPY": ("jpy_tona", None),
    "CHF": ("chf_saron", None),
    "CAD": ("cad_corra", None),
    "AUD": ("bis_policy", "AU"),
}
WEEKLY_SOURCES = frozenset({"bis_policy", "chf_saron"})   # BIS and the SNB cube publish weekly
OANDA_MAJOR_FEE_PCT = Decimal("1.00")
DEFAULT_GOLD_LEASE_PCT = Decimal("0.25")


class StaleRateError(Exception):
    """No rate for a currency within `max_stale_days` of the requested day."""


class RateTable:
    """Daily overnight rates (% p.a.) per currency, forward-filled up to a limit."""

    def __init__(self, series: Mapping[str, Sequence[tuple[date, float]]],
                 max_stale_days: int = 10, per_ccy: Mapping[str, int] | None = None) -> None:
        self._days: dict[str, list[date]] = {}
        self._vals: dict[str, list[Decimal]] = {}
        for ccy, pts in series.items():
            pts = sorted(pts)
            self._days[ccy] = [d for d, _ in pts]
            self._vals[ccy] = [Decimal(str(v)) for _, v in pts]
        self._max_stale = max_stale_days
        self._per_ccy = dict(per_ccy or {})

    def rate(self, ccy: str, day: date) -> Decimal:
        days = self._days.get(ccy)
        if not days:
            raise StaleRateError(f"no rate series for {ccy}")
        i = bisect.bisect_right(days, day) - 1
        if i < 0:
            raise StaleRateError(f"{ccy}: {day} is before the series starts ({days[0]})")
        limit = self._per_ccy.get(ccy, self._max_stale)
        if (day - days[i]).days > limit:
            raise StaleRateError(f"{ccy}: last rate {days[i]} is {(day - days[i]).days} days "
                                 f"before {day} (> {limit})")
        return self._vals[ccy][i]


def stale_days(source: str, daily_days: int, weekly_days: int) -> int:
    """A rate source's freshness limit in days: its publication cadence decides (GAP-P12D-146)."""
    return weekly_days if source in WEEKLY_SOURCES else daily_days


def load_rate_table(macro_dir: Path, max_stale_days: int = 10,
                    weekly_stale_days: int | None = None) -> RateTable:
    """Read the normalised CSVs written by scripts/download_macro.py. With `weekly_stale_days`,
    the currencies read from a weekly source get that limit instead (GAP-P12D-146)."""
    series: dict[str, list[tuple[date, float]]] = {}
    for ccy, (sid, area) in CCY_SERIES.items():
        path = Path(macro_dir) / f"{sid}.csv"
        if not path.exists():
            continue                     # that currency is stale (R6-1 per instrument, R16I-08)
        with path.open(newline="", encoding="utf-8") as f:
            rows = csv.DictReader(f)
            series[ccy] = [(date.fromisoformat(r["date"]), float(r["value"])) for r in rows
                           if area is None or r.get("area") == area]
    weekly = {} if weekly_stale_days is None else {
        ccy: stale_days(sid, max_stale_days, weekly_stale_days) for ccy, (sid, _) in CCY_SERIES.items()}
    return RateTable(series, max_stale_days, weekly)


_TRIPLE_DAY = {"tom_next": 2, "financing_daily": 4}     # Mon=0 … Fri=4
_DAYS_PER_YEAR = Decimal("365")                          # OANDA: value × rate × 1/365


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


def carry_rate_pct(asset_class: str, instrument: str, quote: str, rates: RateTable, day: date) -> float:
    """A long's fair carry rate (% p.a.) on `day`, as RSIM grades it: FX the base rate minus the
    quote's; metals the declared lease minus the quote's; indices minus the quote's (the funding
    cost only: dividends are not on disk, a declared understatement of a long's carry)."""
    q = float(rates.rate(quote, day))
    if asset_class == "fx":
        return float(rates.rate(instrument.split("_")[0], day)) - q
    if asset_class == "metal":
        return float(DEFAULT_GOLD_LEASE_PCT) - q
    return -q


def accrual(asset_class: str, instrument: str, quote: str, rates: RateTable, day: date) -> float:
    """The carry one rollover on business day `day` adds to the excess-return price."""
    convention = "tom_next" if asset_class == "fx" else "financing_daily"
    return carry_rate_pct(asset_class, instrument, quote, rates, day) / 100.0 * swap_multiplier(day, convention) / 365.0
