"""RSIM, the research simulator (R1.3; master §5 C8 v2.21/v2.22, §5.6; ACIS-09 C-BT-11 v2).

It turns daily forecasts into target positions, fills them on the execution clock, and books a
daily net P&L per instrument, whose portfolio sum is the series a verdict grades (GAP-P12D-98/100).

Mental model:
  * A MARKET has one row per decision day (the 17:00 New York close) and one column per instrument:
    - `price`: the EXCESS-return price the rules read (carry-inclusive, GAP-P12D-71);
    - `close`: the tradeable mid at the decision close, which sizing reads;
    - `fill`, `spread`: the mid and quoted spread at the fill that executes day t's decision on
      the symbol's pre-registered execution clock (GAP-P12D-95), never before the close;
    - `carry`: a long's FAIR financing, as a fraction of value, over the rollovers between fill t
      and fill t+1 (the rate differential × the calendar's multiple / 365);
    - `nights`: how many days of financing those rollovers charge (the swap calendar, E17);
    - `q`: USD per unit of the quote currency at fill t.
  * A BOOK sizes Carver's way. The position at forecast 10 is
    A = capital·(vol_target/16)/(σ%·close·q) · weight · IDM, and the optimum is forecast/10 · A.
    The 10% buffer is a band of ±0.1·A around the OPTIMUM; a position outside it trades to the
    band's nearest edge (pysystemtrade `buffer_method: forecast`, `buffer_trade_to_edge`; the
    spec's wording is GAP-P12D-118's). The result is put on the venue's lots by THE one lot rule
    (`target_on_lots`). A NaN forecast or vol (warm-up) targets flat.
  * Every fill pays THE C8 model, called once per fill: per_side_cost(spread)·|order|·q. There is
    no vectorised cost twin, so the GAP-P12D-36 class is excluded by identity.
  * Financing by declared world: "fair" books u·fill·q·carry; "swap_free" books nothing; "markup"
    books fair minus |u|·fill·q·markup%·nights/36500 for the side held (the venue's swap table,
    GAP-P12D-93). The world is a run property, recorded with the result.
  * Window t (t >= 1) runs from fill t-1 to fill t: P&L = u[t-1]·(fill[t] − fill[t-1])·q[t-1]
    + financing over it − the cost of fill t. Capital is fixed (no compounding), Carver's
    convention, so the daily return is P&L / capital.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Mapping, Sequence

import numpy as np

from core.execution.venue_limits import target_on_lots
from core.optimizer.costs import CostModel

WORLDS = ("fair", "swap_free", "markup")
VOL_DAYS = 16.0                      # Carver: annual vol target / 16 = daily (256 business days)
IDM_CAP = 2.5                        # master §5.5 / OOS_VALIDATION (Carver)


@dataclass(frozen=True)
class Market:
    names: tuple[str, ...]
    days: tuple[date, ...]
    price: np.ndarray
    close: np.ndarray
    fill: np.ndarray
    spread: np.ndarray
    carry: np.ndarray
    nights: np.ndarray
    q: np.ndarray

    def __post_init__(self) -> None:
        shape = (len(self.days), len(self.names))
        for name in ("price", "close", "fill", "spread", "carry", "nights", "q"):
            a = getattr(self, name)
            if a.shape != shape or not np.all(np.isfinite(a)):
                raise ValueError(f"{name}: shape {a.shape} != {shape} or not finite")
        if (self.price <= 0).any() or (self.close <= 0).any() or (self.fill <= 0).any() or (self.q <= 0).any():
            raise ValueError("prices and q must be > 0")
        if (self.spread < 0).any() or (self.nights < 0).any():
            raise ValueError("spread and nights must be >= 0")


@dataclass(frozen=True)
class Lots:
    step: float = 1.0                # units
    minimum: float = 1.0


@dataclass(frozen=True)
class BookSpec:
    costs: Mapping[str, CostModel]
    capital: float = 1_000_000.0
    vol_target: float = 0.20         # annual
    idm: float = 1.0
    weights: Mapping[str, float] | None = None       # None: equal
    buffer: float = 0.10
    lots: Mapping[str, Lots] = field(default_factory=dict)        # default Lots() per instrument
    world: str = "fair"
    markup: Mapping[str, tuple[float, float]] = field(default_factory=dict)   # name -> (long %, short %)

    def __post_init__(self) -> None:
        if self.world not in WORLDS:
            raise ValueError(f"world {self.world!r} not in {WORLDS}")
        if not (0 < self.idm <= IDM_CAP) or self.capital <= 0 or self.vol_target <= 0 or self.buffer < 0:
            raise ValueError("need 0 < idm <= 2.5, capital > 0, vol_target > 0, buffer >= 0")
        if self.world == "markup" and not self.markup:
            raise ValueError("the markup world needs the venue's table")


@dataclass(frozen=True)
class BookResult:
    world: str
    capital: float
    units: np.ndarray                # position after fill t
    gross: np.ndarray                # price P&L per window
    financing: np.ndarray
    cost: np.ndarray
    fills: int

    @property
    def pnl(self) -> np.ndarray:
        return self.gross + self.financing - self.cost

    @property
    def daily(self) -> np.ndarray:
        """The portfolio's daily net return on fixed capital (window t ends at fill t)."""
        return self.pnl.sum(axis=1) / self.capital


def annual_sharpe(daily: np.ndarray, periods: float = 252.0) -> float:
    sd = daily.std(ddof=1)
    return float(daily.mean() / sd * math.sqrt(periods)) if sd > 0 else 0.0


def buffered(current: float, optimum: float, band: float) -> float:
    """Carver's buffer: inside optimum ± band, keep; outside, trade to the nearest edge."""
    lo, hi = optimum - band, optimum + band
    return lo if current < lo else hi if current > hi else current


def run(market: Market, forecast: np.ndarray, pct_vol: np.ndarray, spec: BookSpec) -> BookResult:
    """Simulate one book. `forecast[t, i]` and `pct_vol[t, i]` (daily, fraction of price) must
    read nothing after day t's close; a NaN in either targets flat."""
    T, N = len(market.days), len(market.names)
    if forecast.shape != (T, N) or pct_vol.shape != (T, N):
        raise ValueError("forecast and pct_vol must match the market's shape")
    weights = spec.weights or {n: 1.0 / N for n in market.names}
    cash_vol = spec.capital * spec.vol_target / VOL_DAYS
    units = np.zeros((T, N))
    gross, fin, cost = np.zeros((T, N)), np.zeros((T, N)), np.zeros((T, N))
    fills = 0
    for i, name in enumerate(market.names):
        cm, lots = spec.costs[name], spec.lots.get(name, Lots())
        step, minimum = Decimal(str(lots.step)), Decimal(str(lots.minimum))
        long_mu, short_mu = spec.markup.get(name, (0.0, 0.0))
        held = 0.0
        for t in range(T):
            if t:                                               # the window from fill t-1 to fill t
                q0, f0 = market.q[t - 1, i], market.fill[t - 1, i]
                gross[t, i] = held * (market.fill[t, i] - f0) * q0
                fin[t, i] = _financing(spec.world, held, f0 * q0, market.carry[t - 1, i],
                                       market.nights[t - 1, i], long_mu, short_mu)
            f, v = forecast[t, i], pct_vol[t, i]
            if f != f or v != v or v <= 0:
                optimum, band = 0.0, 0.0
            else:
                average = cash_vol / (v * market.close[t, i] * market.q[t, i]) * weights[name] * spec.idm
                optimum, band = f / 10.0 * average, spec.buffer * average
            target = float(target_on_lots(Decimal(str(float(buffered(held, optimum, band)))), step, minimum))
            if target != held:
                cost[t, i] = cm.per_side_cost(float(market.spread[t, i])) * abs(target - held) * market.q[t, i]
                fills += 1
                held = target
            units[t, i] = held
    return BookResult(spec.world, spec.capital, units, gross, fin, cost, fills)


def _financing(world: str, held: float, value_per_unit: float, carry: float, nights: float,
               long_mu: float, short_mu: float) -> float:
    if world == "swap_free" or held == 0.0:
        return 0.0
    fair = held * value_per_unit * carry
    if world == "fair":
        return fair
    markup = (long_mu if held > 0 else short_mu) / 36500.0 * nights
    return fair - abs(held) * value_per_unit * markup


def panel(market: Market, member: Callable[[Sequence[float]], list[float]]) -> np.ndarray:
    """A member's forecast for every instrument, each from its own price column."""
    return np.column_stack([np.asarray(member(market.price[:, i].tolist()), float)
                            for i in range(len(market.names))])
