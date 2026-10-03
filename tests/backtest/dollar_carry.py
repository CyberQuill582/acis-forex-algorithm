"""DCARRY's signal: the dollar carry trade, spot only (FACTORY, GAP-P12D-158; Lustig, Roussanov & Verdelhan,
"Countercyclical currency risk premia", JFE 111(3) (2014) 527-553, sec. 2: long a basket of foreign
currencies against the dollar when the average foreign interest rate is above the US rate, short otherwise).

Mental model:
  * AFD(m), the average forward discount: the mean over EUR, JPY, GBP, AUD, CAD and CHF of (that
    currency's overnight rate - USD's), from the dated rates on disk (`core.data.rates.RateTable`,
    forward-filled, a stale one raises), read LAG_DAYS calendar days before month m's last decision
    day so every fixing was published by then. The paper uses 1-month forward discounts (declared).
  * Month m's sign holds from the first decision day of month m+1: forecast +10 on XXX_USD pairs and
    -10 on USD_XXX pairs when AFD > 0, the opposite otherwise.
  * SWAP-FREE (R1-D9): the book earns only the spot leg, the part the paper attributes to "the
    fluctuations in the signed position in the U.S. dollar" (3.77% of 5.60% a year, developed basket).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import numpy as np

from core.data.rates import RateTable

FOREIGN = ("EUR", "JPY", "GBP", "AUD", "CAD", "CHF")
LAG_DAYS = 3


def afd(rates: RateTable, day: date) -> float:
    at = day - timedelta(days=LAG_DAYS)
    us = float(rates.rate("USD", at))
    return float(np.mean([float(rates.rate(c, at)) - us for c in FOREIGN]))


def month_ends(days: Sequence[date]) -> dict[tuple[int, int], date]:
    """Each month's last decision day."""
    out: dict[tuple[int, int], date] = {}
    for d in days:
        out[(d.year, d.month)] = d
    return out


def panel(days: Sequence[date], names: Sequence[str], rates: RateTable, first: tuple[int, int]) -> np.ndarray:
    """forecast[t, i] from the previous month's AFD sign; NaN before `first`'s month is signalled."""
    ends, out, sign = month_ends(days), np.full((len(days), len(names)), np.nan), {}
    flip = np.array([1.0 if n.endswith("_USD") else -1.0 if n.startswith("USD_") else np.nan for n in names])
    if np.isnan(flip).any():
        raise ValueError(f"every instrument is a dollar pair: {names}")
    for t, d in enumerate(days):
        m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
        if m < first or m not in ends:
            continue
        if m not in sign:
            sign[m] = 1.0 if afd(rates, ends[m]) > 0 else -1.0
        out[t] = 10.0 * sign[m] * flip
    return out
