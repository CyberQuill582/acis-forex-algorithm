"""RATES (GAP-P12D-161): trend on the Treasury par curve, the books of its kill-only looks.

Mental model:
  * The legs are the 2-, 5-, 10- and 30-year constant-maturity par yields, traded as yield (the micro yield
    futures' quote): a position of 1 earns the yield's change in decimal per unit DV01, so long a leg is long
    the yield (short the bond). No carry or rolldown: the micro contract settles to the on-the-run yield.
  * The forecast is the registered TREND rule run on the yield itself (`rules.d1`: Carver's three EWMACs, FDM,
    cap 20) for v1a, or MOP's 12-month sign (`rules.mop_12m`) for v1b. A rising yield gives a long-yield
    position, which is the bond-price trend sign-flipped.
  * Sizing (Carver): position = forecast/10 x TAU / sigma, sigma the 35-day mixed volatility of the yield's daily
    change (D1's own normaliser), averaged over the four tenors (class-equal). A day with no sigma or no
    forecast is flat. The control is the passive long-duration book: short every yield at the same sizing.
  * Causal: the position set at close k uses yields through k and is held to close k+1 (`ust_auction.book`).
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from core.signals import rules
from core.signals.ewm import diff, ffill, mixed_vol

TENORS = {"2y": "2 Yr", "5y": "5 Yr", "10y": "10 Yr", "30y": "30 Yr"}
TAU = 0.0001                                    # one bp of yield a day per leg at forecast 10: a scale, never a result
VOL_DAYS = 35


def load_yields(raw: Path) -> tuple[list[date], dict[str, np.ndarray]]:
    """Every Treasury business day on which all four tenors are published, in percent."""
    rows = {}
    for f in sorted(Path(raw).glob("*.csv")):
        with f.open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                vals = {k: r.get(col, "").strip() for k, col in TENORS.items()}
                if all(vals.values()):
                    rows[datetime.strptime(r["Date"], "%m/%d/%Y").date()] = {k: float(v) for k, v in vals.items()}
    days = sorted(rows)
    return days, {k: np.array([rows[d][k] for d in days]) for k in TENORS}


def d1_on_yield(y: np.ndarray, days: Sequence[date]) -> list[float]:
    return rules.d1(list(y))


def mop_on_yield(y: np.ndarray, days: Sequence[date]) -> list[float]:
    return rules.mop_12m(list(y), list(days))


FORECASTS: dict[str, Callable] = {"d1": d1_on_yield, "mop": mop_on_yield}


def sigma(y: np.ndarray) -> np.ndarray:
    """The daily volatility of the yield's change in decimal (D1's normaliser span), forward-filled."""
    dec = list(np.asarray(y, float) / 100)
    return np.array(ffill(mixed_vol(diff(dec), days=VOL_DAYS)), float)


def positions(days: Sequence[date], curve: dict[str, np.ndarray], forecast: Callable,
              passive: bool = False) -> dict[str, np.ndarray]:
    """{tenor: position per unit DV01}; `passive` is the control: short every yield at the same sizing."""
    out = {}
    for t, y in curve.items():
        s = sigma(y)
        f = np.full(len(y), -10.0) if passive else np.array(forecast(y, days), float)
        p = f / 10.0 * TAU / s / len(curve)
        out[t] = np.where(np.isfinite(p), p, 0.0)
    return out


def yield_changes(y: np.ndarray) -> np.ndarray:
    return np.r_[0.0, np.diff(np.asarray(y, float))] / 100
