"""RegimeContext + enums (ACIS-02 §4, locked output contract)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from core.data.errors import DataQualityError


class RegimeType(str, Enum):
    STRONG_TREND_UP = "STRONG_TREND_UP"
    STRONG_TREND_DOWN = "STRONG_TREND_DOWN"
    WEAK_TREND_UP = "WEAK_TREND_UP"
    WEAK_TREND_DOWN = "WEAK_TREND_DOWN"
    RANGING_TIGHT = "RANGING_TIGHT"
    RANGING_WIDE = "RANGING_WIDE"
    BREAKOUT_IMMINENT = "BREAKOUT_IMMINENT"
    POST_BREAKOUT = "POST_BREAKOUT"
    MEAN_REVERTING = "MEAN_REVERTING"
    MACRO_EVENT = "MACRO_EVENT"      # † always tradeable=False
    ILLIQUID = "ILLIQUID"            # †
    UNCLASSIFIED = "UNCLASSIFIED"    # †


NEVER_TRADEABLE = frozenset(
    {RegimeType.MACRO_EVENT, RegimeType.ILLIQUID, RegimeType.UNCLASSIFIED}
)
# NVMA's judgement vetoes, as opposed to its data-integrity gates (GAP-P12D-147)
CONFIDENCE_VETOES = frozenset({"LOW_CONFIDENCE", "NO_PARAMS_FOR_REGIME"})


class VolClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class LiqState(str, Enum):
    DEEP = "DEEP"
    NORMAL = "NORMAL"
    THIN = "THIN"
    ILLIQUID = "ILLIQUID"


@dataclass(frozen=True)
class RegimeContext:
    regime: RegimeType
    trend_direction: int              # -1 | 0 | +1
    volatility_class: VolClass
    liquidity_state: LiqState
    tradeable: bool                   # master veto flag (conflict priority #2)
    regime_stability_score: float     # 0..1
    estimated_half_life_seconds: int  # advisory (C3) — never a sizing factor
    confidence: float                 # 0..1
    timestamp: datetime
    instrument: str
    inputs_snapshot: Mapping          # audit: the values that produced this call

    def __post_init__(self) -> None:
        if self.trend_direction not in (-1, 0, 1):
            raise DataQualityError("trend_direction", self.trend_direction, "must be -1|0|+1")
        for name in ("regime_stability_score", "confidence"):
            v = getattr(self, name)
            if not math.isfinite(v) or not 0.0 <= v <= 1.0:
                raise DataQualityError(name, v, "must be finite in [0,1]")
        if self.estimated_half_life_seconds < 0:
            raise DataQualityError("estimated_half_life_seconds", self.estimated_half_life_seconds, ">= 0")
        if self.timestamp.tzinfo is None:
            raise DataQualityError("timestamp", self.timestamp, "must be tz-aware")
        if self.regime in NEVER_TRADEABLE and self.tradeable:
            raise DataQualityError("tradeable", True, f"{self.regime.value} is never tradeable")
        if not isinstance(self.inputs_snapshot, MappingProxyType):
            raise DataQualityError("inputs_snapshot", type(self.inputs_snapshot), "must be immutable Mapping")

    def integrity_tradeable(self) -> bool:
        """Tradeable for a daily target entry (ACIS-05 §6.4, GAP-P12D-147): every data-integrity
        gate holds (no gate state: warm-up, NaN indicators, macro event, illiquid; no stale,
        spread or dead-market veto), while the confidence and label vetoes do not apply. A veto
        whose reasons were not recorded stays a veto."""
        if self.tradeable:
            return True
        reasons = self.inputs_snapshot.get("veto_reasons")
        return (self.regime not in NEVER_TRADEABLE and bool(reasons)
                and set(reasons) <= CONFIDENCE_VETOES)
