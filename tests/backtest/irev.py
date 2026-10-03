"""IREV's position: trading against index serial dependence (FACTORY, GAP-P12D-158; Baltussen, van Bekkum &
Da, "Indexing and stock market serial dependence around the world", JFE 132(1) (2019) 26-48, eq. (20)).

Mental model:
  * The paper's MAC(5) strategy holds 4r(t-1) + 3r(t-2) + 2r(t-3) + r(t-4) through day t, which replicates
    the first four autocovariances; "trading against" it holds the negative. Since about 2000 index
    returns reverse, so the negative earns (gross Sharpe 0.63 on all its indexes, 0.67 on the S&P 500
    alone, 1999-03 to 2016-12; no costs).
  * Here each index's session returns r are its own cash-close anchors (`event_multi.sessions`); the
    position held from session s to s+1 is
        target[s] = -LEG_RISK / sigma[s] * clip(u[s], -2, 2),  u = (4z(s) + 3z(s-1) + 2z(s-2) + z(s-3)) / sqrt(30),
    with z = r / sigma[s] and sigma the trailing session vol, so u has unit variance under independence
    and every index carries about LEG_RISK of daily risk.
  * DECLARED departures: the CFD's anchored mid for the cash index close; equal risk per index and over
    time (the paper's raw positions weight volatile days by their variance); u capped at 2 standard
    deviations (Carver's forecast cap); C8 costs on every change; swap-free.
"""

from __future__ import annotations

import numpy as np

from tests.backtest.event_multi import LEG_RISK, Sessions, trailing_vol

WEIGHTS = (4.0, 3.0, 2.0, 1.0)                    # MAC(5): lags 1..4 of the strategy, i.e. r(s)..r(s-3) at s
CAP = 2.0


def unit_signal(r: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """u[s] from the returns ending at s, each standardised by sigma[s]; NaN until all four exist."""
    u = np.full(len(r), np.nan)
    norm = float(np.sqrt(sum(w * w for w in WEIGHTS)))
    for s in range(len(WEIGHTS) - 1, len(r)):
        past = r[s - len(WEIGHTS) + 1:s + 1][::-1]               # r(s), r(s-1), r(s-2), r(s-3)
        if np.all(np.isfinite(past)) and np.isfinite(sigma[s]) and sigma[s] > 0:
            u[s] = float(np.dot(WEIGHTS, past / sigma[s])) / norm
    return u


def target(s: Sessions) -> np.ndarray:
    r = s.returns
    sigma = trailing_vol(r)
    return -LEG_RISK / sigma * np.clip(unit_signal(r, sigma), -CAP, CAP)
