"""HALLOWEEN's position: the "Sell in May" contrast (FACTORY, GAP-P12D-158; Bouman & Jacobsen, "The Halloween
indicator, 'Sell in May and go away': another puzzle", AER 92(5) (2002) 1618-1635, 37 markets 1970-1998;
out of sample, Andrade, Chhaochharia & Fuerst, FAJ 69(4) (2013), 1998-2012: November-April returns beat
May-October in all 37 markets, by about 10 percentage points a half-year).

Mental model:
  * WINTER is November to April, SUMMER May to October, by the month of the session the position is held
    INTO: target[s] (held from session s to s+1) is long when session s+1 falls in winter, short when it
    falls in summer. The paper's rule holds equities in winter and bills in summer; the CONTRAST is short
    in summer instead, so the equity premium nets out and only the seasonal can earn (declared).
  * SIZE: LEG_RISK over the trailing session vol read at the season's FIRST position (the switch), held
    as a fixed fraction of capital until the next switch: two trades a season, never a vol-driven churn.
  * Each index is traded at its own cash close (`event_multi.book`), C8 costs, swap-free.
"""

from __future__ import annotations

import numpy as np

from tests.backtest.event_multi import LEG_RISK, Sessions, trailing_vol

WINTER = frozenset({11, 12, 1, 2, 3, 4})


def season(s: Sessions) -> np.ndarray:
    """+1 when the session held into is a winter one, -1 in summer; the last session repeats its own."""
    into = [s.days[k + 1] for k in range(len(s.days) - 1)] + [s.days[-1]]
    return np.array([1.0 if d.month in WINTER else -1.0 for d in into])


def target(s: Sessions) -> np.ndarray:
    sign, sigma = season(s), trailing_vol(s.returns)
    out, size = np.full(len(sign), np.nan), np.nan
    for k in range(len(sign)):
        if k == 0 or sign[k] != sign[k - 1] or not np.isfinite(size):
            size = LEG_RISK / sigma[k] if np.isfinite(sigma[k]) and sigma[k] > 0 else np.nan
        out[k] = sign[k] * size
    return out
