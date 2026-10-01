"""Master §5.6's two cost filters (v2.22, owner-ratified D-g; GAP-P12D-115): admission per instrument
and per member, each against a FIXED expectation, never a realised Sharpe.

  1. CARVER'S SPEED LIMIT. Annual cost in SR units = (forecast turnover + rolls a year) × the cost
     per trade in SR units, admitted at <= 0.10 SR: the stricter of Carver's two published figures
     ("Fast but not furious", qoppac 2023-02: "0.13 or 0.10 SR annual units ... depending on which
     of my books"). Definitions are pysystemtrade's at `CARVER_COMMIT`:
       forecast turnover = mean |Δ(forecast / 10)| per business day × 256
                           (`syscore/pandas/strategy_functions.turnover(forecast, 10)`);
       cost per trade, SR = cost of one trade in price units / (daily price vol × 16)
                           (`instrumentCosts.calculate_sr_cost`, annual vol = daily × sqrt(256)).
     Spot FX and cash CFDs do not roll, so rolls = 0 for this universe. (Carver's code charges
     2 × rolls as holding cost and his blog writes + rolls; with no rolls the two agree.)
  2. SWAP VIABILITY. The venue's annual swap MARKUP (swaps.py) × the member's expected time in
     market (mean |forecast| / 10) ÷ the instrument's annual vol, admitted at <= 0.10 SR: one third
     of a DECLARED expected pre-cost Sharpe of 0.30. In the swap-free world it is 0 and admits.

The member's turnover and time in market are measured on the synthetic NULL (`r1_lab_turnover.py`):
P&L-blind, so they spend no real-data look; Carver's S&P 500 figures cross-check them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from core.signals.ewm import BUSINESS_DAYS_IN_YEAR

SPEED_LIMIT_SR = 0.10
EXPECTED_PRE_COST_SR = 0.30
SWAP_LIMIT_SR = EXPECTED_PRE_COST_SR / 3.0
ROOT_DAYS = math.sqrt(BUSINESS_DAYS_IN_YEAR)          # 16


# member -> (turnover on the lab null, median of 1,000 instrument-paths: `r1_lab_turnover.py` at `81ecb8a`,
#            seeds 1-50; Carver's published forecast turnover on the S&P 500, "Fast but not furious" 2023, or None;
#            time in market on the null). The FILTER uses the larger turnover: the lab runs 25-35% below Carver.
MEMBER_INPUTS: dict[str, tuple[float, float | None, float]] = {
    "D1": (7.95, None, 0.80),
    "EWMAC16_64": (12.24, 16.32, 0.77), "EWMAC32_128": (7.21, 9.69, 0.80), "EWMAC64_256": (4.90, 7.46, 0.82),
    "BREAKOUT40": (17.97, None, 0.77), "BREAKOUT80": (8.96, None, 0.77), "BREAKOUT160": (4.43, None, 0.76),
    "MOP12": (3.07, None, 1.00),
}


def filter_turnover(member: str) -> float:
    lab, carver, _ = MEMBER_INPUTS[member]
    return lab if carver is None else max(lab, carver)


def forecast_turnover(forecast: Sequence[float], average_abs: float = 10.0) -> float:
    """Carver's `turnover(forecast, 10)`: annual mean |Δ(f/10)| over business days (NaN-skipping)."""
    steps = [abs(b - a) / average_abs for a, b in zip(forecast, forecast[1:]) if a == a and b == b]
    return sum(steps) / len(steps) * BUSINESS_DAYS_IN_YEAR if steps else float("nan")


def time_in_market(forecast: Sequence[float], average_abs: float = 10.0) -> float:
    """Mean |forecast| / 10: the average position held, in units of the average position."""
    xs = [abs(f) / average_abs for f in forecast if f == f]
    return sum(xs) / len(xs) if xs else float("nan")


def sr_cost_per_trade(cost_price_units: float, daily_vol_price: float) -> float:
    if not (cost_price_units >= 0 and daily_vol_price > 0):
        raise ValueError("need cost >= 0 and a positive daily price vol")
    return cost_price_units / (daily_vol_price * ROOT_DAYS)


@dataclass(frozen=True)
class Admission:
    instrument: str
    member: str
    trading_cost_sr: float
    swap_cost_sr: float

    @property
    def admitted(self) -> bool:
        return self.trading_cost_sr <= SPEED_LIMIT_SR and self.swap_cost_sr <= SWAP_LIMIT_SR


def admit(instrument: str, member: str, *, turnover: float, cost_per_trade_sr: float, rolls: float = 0.0,
          markup_pct: float = 0.0, member_time_in_market: float = 1.0, annual_vol_pct: float) -> Admission:
    """Both filters for one (instrument, member). `markup_pct` is 0 in the swap-free world."""
    if annual_vol_pct <= 0:
        raise ValueError("annual vol must be > 0")
    return Admission(instrument, member, (turnover + rolls) * cost_per_trade_sr,
                     markup_pct * member_time_in_market / annual_vol_pct)
