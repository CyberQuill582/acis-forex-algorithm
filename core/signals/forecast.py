"""The target-position path's forecast (ACIS-04 v1.6 §4b; master §5.5; R1.6).

Mental model:
  * A `Forecast` is what AGON hands the Governor for ONE instrument at ONE 17:00 New York decision:
    the combined, FDM-scaled, capped value, the registered family-versions netted into it, the
    decision close (sizing's `price_basis`), the family's sizing vol, and a sha256 of every input
    read, so a replay or a restart re-derives the same target (B0(d)). It validates on
    construction; an instrument without a forecast emits nothing, never a NaN.
  * `excess_prices` compounds the closes with the dated carry exactly as RSIM's real-data source
    does (p_t = p_{t−1} · close_t / close_{t−1} · (1 + accrual_t)), so the engine reads the price
    the family was graded on (`trend_d1_v1`'s declared deviation).
  * `d1_forecast` is the registered TREND D1 at the LAST decision: `rules.d1`'s last value and
    Carver's normaliser over the price (RSIM's `carver_pct_vol`). Fewer than WARMUP decisions
    after the first close (RSIM's `masked`, the same constant), or a NaN, gives None.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

from core.data.errors import DataQualityError
from core.signals import rules
from core.signals.ewm import diff, mixed_vol

D1_FAMILY = "trend_d1_v1"
WARMUP = 260            # decisions of own data before a forecast counts (RSIM masks the same)


@dataclass(frozen=True)
class Forecast:
    instrument: str
    value: float
    family_ids: tuple[str, ...]
    decision_day: date
    decided_at: datetime
    price_basis: float
    pct_vol: float
    inputs_hash: str

    def __post_init__(self) -> None:
        if not self.instrument:
            raise DataQualityError("instrument", self.instrument, "a forecast names its instrument")
        if not (math.isfinite(self.value) and abs(self.value) <= rules.CAP):
            raise DataQualityError("value", self.value, f"finite and |value| <= {rules.CAP}")
        if not self.family_ids or not all(isinstance(f, str) and f for f in self.family_ids):
            raise DataQualityError("family_ids", self.family_ids, "the netted family-versions, non-empty")
        if not (math.isfinite(self.price_basis) and self.price_basis > 0):
            raise DataQualityError("price_basis", self.price_basis, "a positive decision close")
        if not (math.isfinite(self.pct_vol) and self.pct_vol > 0):
            raise DataQualityError("pct_vol", self.pct_vol, "a positive sizing vol")
        if self.decided_at.tzinfo is None:
            raise DataQualityError("decided_at", self.decided_at, "must be tz-aware")
        if len(self.inputs_hash) != 64:
            raise DataQualityError("inputs_hash", self.inputs_hash, "a sha256 hex digest")


def excess_prices(closes: Sequence[float], accruals: Sequence[float]) -> list[float]:
    """The excess-return price from 1.0: each decision's close-to-close move times its rollover's carry."""
    if len(closes) != len(accruals) or not closes or any(not (c > 0) for c in closes):
        raise DataQualityError("closes", len(closes), "one positive close per accrual")
    out = [1.0]
    for t in range(1, len(closes)):
        out.append(out[-1] * closes[t] / closes[t - 1] * (1.0 + accruals[t]))
    return out


def inputs_hash(instrument: str, closes: Sequence[float], accruals: Sequence[float], family: str) -> str:
    payload = {"instrument": instrument, "family": family, "closes": [float(c) for c in closes],
               "accruals": [float(a) for a in accruals]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()


def d1_forecast(instrument: str, closes: Sequence[float], accruals: Sequence[float], *,
                decision_day: date, decided_at: datetime) -> Forecast | None:
    """The TREND D1 forecast for the last decision, or None while the family warms up."""
    if len(closes) <= WARMUP:
        return None
    prices = excess_prices(closes, accruals)
    value = rules.d1(prices)[-1]
    vol = mixed_vol(diff(prices))[-1]
    if value != value or vol != vol or not vol > 0:
        return None
    return Forecast(instrument=instrument, value=float(value), family_ids=(D1_FAMILY,), decision_day=decision_day,
                    decided_at=decided_at, price_basis=float(closes[-1]), pct_vol=float(vol / prices[-1]),
                    inputs_hash=inputs_hash(instrument, closes, accruals, D1_FAMILY))
