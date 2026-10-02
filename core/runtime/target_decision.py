"""The 17:00 New York decision for the target-position path (ACIS-04 v1.6 §4b, ACIS-05 v1.7 §6.4; R1.6).

Mental model:
  * Per instrument: its daily series (the venue's H1 bars through core/signals/daily.py), the dated
    carry of each decision day (core/data/rates.py `accrual`), then `d1_forecast`, the registered
    TREND D1 at the last decision with its inputs hash, then the banded target from the ONE sizing
    function RSIM grades (`banded_target`): at most one minimum lot in paper and practice (D-a).
  * NO NEW TARGET (the position is kept, R6-1) when any of these hold. Each is logged by its reason;
    nothing defaults:
    - the rate table is stale;
    - the last close is not fresh;
    - the family is still warming up;
    - the quote currency's USD leg has no fresh close.
  * Sizing reads the quote's USD rate at the DECISION close; RSIM's `q` is the fill's (declared in
    GAP-P12D-118's R1.6 record: a few hours apart, sizing only).
  * Deterministic: the same bars, rates and position give the same target and the same
    `inputs_hash`, so a restart re-derives it (idempotent) and a replay can prove it (B0(d)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping

from core.data.fx_clock import rollover_utc
from core.data.rates import RateTable, StaleRateError, accrual
from core.governor.target import VOL_DAYS, banded_target
from core.signals.daily import DailySeries
from core.signals.forecast import Forecast, d1_forecast
from core.signals.indicators import wilder_atr

TO_USD = {"EUR": ("EUR_USD", 1), "GBP": ("GBP_USD", 1), "AUD": ("AUD_USD", 1), "NZD": ("NZD_USD", 1),
          "JPY": ("USD_JPY", -1), "CAD": ("USD_CAD", -1), "CHF": ("USD_CHF", -1)}     # RSIM's


@dataclass(frozen=True)
class BookSizing:
    capital_ref: float               # the account's declared initial capital (its rulebook)
    vol_target: float                # annual, the account's declared target
    idm: float                       # fixed at registration
    buffer: float                    # Carver's band, a fraction of the average position
    weights: Mapping[str, float]     # class-equal, then equal within a class

    @property
    def cash_vol(self) -> float:
        return self.capital_ref * self.vol_target / VOL_DAYS


@dataclass(frozen=True)
class Lots:
    step: Decimal
    minimum: Decimal
    cap: Decimal | None              # paper and practice: one venue minimum lot (D-a)


@dataclass(frozen=True)
class Decision:
    instrument: str
    day: date
    held: Decimal                    # signed units at the decision
    target: Decimal | None           # None: no new target, the position is kept
    reason: str
    forecast: Forecast | None
    atr: float                       # the daily true-range ATR (the disaster stop's unit)


def class_equal_weights(classes: Mapping[str, str]) -> dict[str, float]:
    """Equal across asset classes, then equal across a class's instruments."""
    counts: dict[str, int] = {}
    for c in classes.values():
        counts[c] = counts.get(c, 0) + 1
    return {name: 1.0 / len(counts) / counts[c] for name, c in classes.items()}


def usd_per_quote(quote: str, day: date, series: Mapping[str, DailySeries]) -> float | None:
    if quote == "USD":
        return 1.0
    leg, sign = TO_USD[quote]
    s = series.get(leg)
    if s is None or not s.days or s.days[-1] != day or not s.fresh[-1]:
        return None
    return s.closes[-1] if sign > 0 else 1.0 / s.closes[-1]


def decide(instrument: str, asset_class: str, quote: str, s: DailySeries, day: date, held: Decimal, *,
           rates: RateTable, series: Mapping[str, DailySeries], sizing: BookSizing, lots: Lots,
           atr_period: int) -> Decision:
    def none(reason: str, f: Forecast | None = None, atr: float = math.nan) -> Decision:
        return Decision(instrument, day, held, None, f"no_target:{reason}", f, atr)

    if not s.days or s.days[-1] != day:
        return none("no_close_today")
    if not s.fresh[-1]:
        return none("stale_close")
    try:
        accruals = [accrual(asset_class, instrument, quote, rates, d) for d in s.days]
    except StaleRateError:
        return none("stale_rates")
    f = d1_forecast(instrument, s.closes, accruals, decision_day=day, decided_at=rollover_utc(day))
    if f is None:
        return none("warming_up")
    q = usd_per_quote(quote, day, series)
    if q is None:
        return none("no_usd_rate", f)
    atr = wilder_atr(s.bars, atr_period)
    target = banded_target(float(held), f.value, f.pct_vol, f.price_basis, q, cash_vol=sizing.cash_vol,
                           weight=sizing.weights[instrument], idm=sizing.idm, buffer=sizing.buffer,
                           step=lots.step, minimum=lots.minimum, cap=lots.cap)
    return Decision(instrument, day, held, target, "target", f, atr)
