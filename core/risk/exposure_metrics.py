"""Portfolio VaR and correlated-cluster exposure for the RiskSnapshot (ACIS-07 §4, master §8).
Moved unchanged out of core/risk/monitor.py (legibility budget, GAP-P12M-01). Invariants:
  * VaR is delta-normal and UNDIVERSIFIED (no correlation credit: a conservative sum of
    per-position 1% VaR). σ is the rolling log-return of marks scaled by
    √(var_horizon_seconds / eval_cadence_s) to the DECLARED horizon (GAP-P9E-03); the 3%
    cap is ratified against the 1-day horizon (GAP-0103); in-loop wiring is GAP-0091b.
  * A position with fewer than 3 marks (2 returns) adds nothing: not enough data.
  * Cluster exposure is the largest cluster's summed USD notional, as a % of NAV.
"""

from __future__ import annotations

import math
from statistics import NormalDist, stdev
from typing import Mapping, Sequence

_Z_99 = NormalDist().inv_cdf(0.99)      # ≈ 2.326 — 1% VaR z-score


def portfolio_var_pct(notional: Mapping[str, float], marks: Mapping[str, Sequence[float]],
                      nav: float, *, var_horizon_seconds: float, eval_cadence_s: float) -> float:
    horizon_scale = math.sqrt(var_horizon_seconds / eval_cadence_s)
    total = 0.0
    for inst, usd in notional.items():
        hist = marks.get(inst)
        if hist is None or len(hist) < 3:
            continue
        rets = [math.log(hist[i] / hist[i - 1]) for i in range(1, len(hist))
                if hist[i - 1] > 0 and hist[i] > 0]
        if len(rets) < 2:
            continue
        total += usd * _Z_99 * stdev(rets) * horizon_scale    # sample σ, horizon-scaled
    return total / nav * 100.0


def max_cluster_pct(notional: Mapping[str, float], clusters: Mapping[str, Sequence[str]],
                    nav: float) -> float:
    worst = 0.0
    for members in clusters.values():
        worst = max(worst, sum(notional[i] for i in members if i in notional) / nav * 100.0)
    return worst
