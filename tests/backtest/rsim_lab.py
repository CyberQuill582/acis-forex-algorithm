"""The daily lab as an RSIM market (R1.3; ACIS-09 C-BT-12: synthetic markets grade MACHINERY).

Mental model:
  * The lab has one bar per weekday and no intraday clock here, so day t's decision fills AT
    its close (declared: the 17:00 New York decision and its fill coincide; the real execution
    clock, GAP-P12D-95, needs intraday data and is the real-data source's).
  * The fill precedes the day's rollover, so the position chosen at close t is financed by
    `accrual[t]` and then earns spot[t+1] = r[t+1] − accrual[t]: a financed long earns exactly
    the excess return r[t+1] (lab_market's FINANCING contract).
  * The rules read the excess-return price cumprod(1 + r); sizing reads the tradeable mid.
  * Costs are the C-7 shim's: every lab instrument carries a declared template's C8 costs, and
    the quoted spread is a declared fraction of the mid (`LAB_SPREAD`), so no second cost model
    exists. q = 1: the lab quotes in USD.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from config.schemas import AcisConfig
from core.optimizer.costs import cost_model
from core.signals import rules
from core.signals.ewm import diff, mixed_vol
from tests.backtest.carry import swap_multiplier
from tests.backtest.lab_market import LabPath
from tests.backtest.lab_source import LAB_SWAP_CONVENTION, lab_config, lab_names
from tests.backtest.rsim import BookResult, BookSpec, Market, panel, run

LAB_SPREAD = 0.00005        # quoted spread as a fraction of the mid: ~0.5 pip on EUR/USD (declared)


def lab_market(path: LabPath, names: Sequence[str] | None = None) -> Market:
    names = tuple(names or lab_names(path.r.shape[1]))
    days = tuple(d.astype(object) for d in path.dates)
    mids = path.mids()
    nights = np.array([[swap_multiplier(d, LAB_SWAP_CONVENTION)] * len(names) for d in days], float)
    return Market(names=names, days=days, price=np.cumprod(1.0 + path.r, axis=0), close=mids, fill=mids,
                  spread=mids * LAB_SPREAD, carry=np.asarray(path.accrual, float), nights=nights,
                  q=np.ones_like(mids))


def carver_pct_vol(market: Market) -> np.ndarray:
    """Carver's normaliser as a fraction of price: the sizing vol of every EWMAC/breakout book."""
    return np.column_stack([np.asarray(mixed_vol(diff(market.price[:, i].tolist())), float) / market.price[:, i]
                            for i in range(len(market.names))])


def mop_pct_vol(market: Market) -> np.ndarray:
    return np.column_stack([np.asarray(rules.mop_vol(market.price[:, i].tolist()), float)
                            for i in range(len(market.names))])


MEMBERS: dict[str, tuple[Callable, Callable]] = {
    "D1": (rules.d1, carver_pct_vol),
    **{f"EWMAC{f}_{s}": ((lambda f, s: lambda p: rules.ewmac(p, f, s))(f, s), carver_pct_vol)
       for f, s in rules.EWMAC_SCALARS},
    **{f"BREAKOUT{n}": ((lambda n: lambda p: rules.breakout(p, n))(n), carver_pct_vol)
       for n in rules.BREAKOUT_SCALARS},
    "PASSIVE_LONG": (lambda p: [10.0] * len(p), carver_pct_vol),
}


def lab_costs(cfg: AcisConfig, names: Sequence[str], template: str = "EUR_USD", stress: float = 1.0) -> dict:
    lab = lab_config(cfg, names, template)
    return {n: cost_model(lab, n, stress=stress) for n in names}


def run_member(path: LabPath, member: str, cfg: AcisConfig, *, stress: float = 1.0,
               d1_params: dict | None = None, **spec) -> BookResult:
    """One registered member's standalone book on a lab path (MOP needs the path's dates).
    `stress` is the C8 run property (2.0 = stage A's 2x cost); `d1_params` builds a plateau
    neighbour of D1 (its sizing vol stays Carver's default normaliser)."""
    market = lab_market(path)
    if d1_params is not None:
        forecast, vol = panel(market, lambda p: rules.d1(p, **d1_params)), carver_pct_vol(market)
    elif member == "MOP12":
        forecast = np.column_stack([np.asarray(rules.mop_12m(market.price[:, i].tolist(), market.days), float)
                                    for i in range(len(market.names))])
        vol = mop_pct_vol(market)
    else:
        rule, vol_of = MEMBERS[member]
        forecast, vol = panel(market, rule), vol_of(market)
    return run(market, forecast, vol, BookSpec(costs=lab_costs(cfg, market.names, stress=stress), **spec))
