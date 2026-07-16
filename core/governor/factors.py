"""Pure sizing factors: liquidity, correlation, C16 vol-norm (ACIS-05 §6)."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Mapping, Sequence

from core.data.errors import DataQualityError
from core.regime.regime_types import LiqState

_LIQUIDITY_FACTOR = {
    LiqState.DEEP: 1.0,
    LiqState.NORMAL: 0.8,
    LiqState.THIN: 0.4,
    LiqState.ILLIQUID: 0.0,   # also a §7.1 hard guard
}


def liquidity_factor(liq: LiqState) -> float:
    return _LIQUIDITY_FACTOR[liq]


def correlation_factor(
    instrument_clusters: Sequence[str],
    per_cluster_exposure: Mapping[str, Decimal],
    nav: Decimal,
    cap_pct: float,
) -> float:
    """clamp01(1 - max_cluster_fraction / cap_fraction): 1.0 with no correlated
    exposure, 0.0 at the cap (the hard cap zeroes there anyway)."""
    if not instrument_clusters:
        return 1.0
    cap_fraction = cap_pct / 100.0
    worst = 0.0
    for cluster in instrument_clusters:
        exposure = per_cluster_exposure.get(cluster, Decimal("0"))
        fraction = float(exposure / nav)
        worst = max(worst, fraction / cap_fraction)
    return max(0.0, min(1.0, 1.0 - worst))


def vol_norm(v: float, v_target: float) -> float:
    """C16 exact function: 1.0 at/below the declared target, v*/v above —
    dampen-only, monotone decreasing in excess vol, never NaN for finite v>0."""
    if not math.isfinite(v) or v <= 0:
        raise DataQualityError("v", v, "realized vol must be finite > 0")
    if not math.isfinite(v_target) or v_target <= 0:
        raise DataQualityError("v_target", v_target, "declared target must be finite > 0")
    return 1.0 if v <= v_target else v_target / v
