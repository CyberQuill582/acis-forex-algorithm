"""Signal output contract (ACIS-04 §4, locked)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.data.errors import DataQualityError
from core.regime.regime_types import RegimeType


class StrategyType(str, Enum):
    TREND = "TREND"
    BREAKOUT = "BREAKOUT"
    MEAN_REVERSION = "MEAN_REVERSION"
    MOMENTUM_SCALP = "MOMENTUM_SCALP"
    PAIR_DIVERGENCE = "PAIR_DIVERGENCE"
    TSMOM = "TSMOM"


@dataclass(frozen=True)
class Signal:
    signal_id: str
    instrument: str
    direction: int                 # +1 long | -1 short (never 0)
    conviction: float              # [0.45, 1] for any emitted signal
    entry_price: float
    stop_loss: float
    take_profit: float | None     # None = no target (faithful TSMOM, v2.11);
    strategy_type: StrategyType   # a stop is ALWAYS required (§8.6 safety law)
    regime_at_generation: RegimeType
    param_set_id: str
    generated_at: datetime
    valid_for_seconds: int
    group_id: str | None = None    # §5.5 linked pair group — both legs share it

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not math.isfinite(self.conviction) or not (0.45 <= self.conviction <= 1.0):
            raise DataQualityError("conviction", self.conviction,
                                   "emitted conviction must be in [0.45, 1]")
        names = ("entry_price", "stop_loss") + (
            ("take_profit",) if self.take_profit is not None else ())
        for name in names:
            v = getattr(self, name)
            if not math.isfinite(v) or v <= 0:
                raise DataQualityError(name, v, "must be finite and > 0")
        if self.direction == 1:
            if not self.stop_loss < self.entry_price:
                raise DataQualityError("stop_loss", self.stop_loss,
                                       "long requires stop < entry")
            if self.take_profit is not None and not self.entry_price < self.take_profit:
                raise DataQualityError("take_profit", self.take_profit,
                                       "long requires entry < target")
        else:
            if not self.entry_price < self.stop_loss:
                raise DataQualityError("stop_loss", self.stop_loss,
                                       "short requires entry < stop")
            if self.take_profit is not None and not self.take_profit < self.entry_price:
                raise DataQualityError("take_profit", self.take_profit,
                                       "short requires target < entry")
        if self.generated_at.tzinfo is None:
            raise DataQualityError("generated_at", self.generated_at, "must be tz-aware")
        if self.valid_for_seconds <= 0:
            raise DataQualityError("valid_for_seconds", self.valid_for_seconds, "must be > 0")
        if not self.param_set_id:
            raise DataQualityError("param_set_id", self.param_set_id, "audit link required")
        if (self.group_id is not None) != (self.strategy_type is StrategyType.PAIR_DIVERGENCE):
            raise DataQualityError("group_id", self.group_id,
                                   "set iff strategy_type == PAIR_DIVERGENCE (§5.5)")
