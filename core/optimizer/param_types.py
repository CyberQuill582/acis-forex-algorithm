"""Frozen boundary dataclasses for the QIEA optimizer (ACIS-03 §4/§5).

`GENE_SPECS` is the single source for every gene's range — ParamSet validation
and the QIEA fixed-point decoder both read it, so the ranges cannot drift.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import datetime

from core.data.errors import DataQualityError
from core.regime.regime_types import RegimeType

# gene name -> (lo, hi, is_int)  — master §5 ranges (extend only with spec edit)
GENE_SPECS: dict[str, tuple[float, float, bool]] = {
    "ema_fast": (5, 50, True),
    "ema_slow": (20, 200, True),
    "rsi_period": (7, 21, True),
    "rsi_overbought": (65.0, 80.0, False),
    "rsi_oversold": (20.0, 35.0, False),
    "atr_multiplier_sl": (1.0, 3.5, False),
    "atr_multiplier_tp": (1.5, 5.0, False),
    "momentum_lookback": (5, 50, True),
    "breakout_atr_threshold": (0.5, 2.0, False),
    "mean_rev_zscore_entry": (1.5, 2.5, False),
    "max_holding_periods": (1, 48, True),
}


@dataclass(frozen=True)
class ParamSet:
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    atr_multiplier_sl: float
    atr_multiplier_tp: float
    momentum_lookback: int
    breakout_atr_threshold: float
    mean_rev_zscore_entry: float
    max_holding_periods: int
    regime: RegimeType
    param_set_id: str
    fitness_score: float
    evolved_at: datetime

    def __post_init__(self) -> None:
        for name, (lo, hi, is_int) in GENE_SPECS.items():
            v = getattr(self, name)
            if is_int and not isinstance(v, int):
                raise DataQualityError(name, v, "must be int")
            if not math.isfinite(float(v)) or not (lo <= v <= hi):
                raise DataQualityError(name, v, f"out of range [{lo}, {hi}]")
        if not self.ema_slow > self.ema_fast:
            raise DataQualityError("ema_slow", self.ema_slow, "must exceed ema_fast")
        if not self.rsi_oversold < self.rsi_overbought:
            raise DataQualityError("rsi_oversold", self.rsi_oversold, "must be < rsi_overbought")
        if not self.atr_multiplier_tp > self.atr_multiplier_sl:
            raise DataQualityError(
                "atr_multiplier_tp", self.atr_multiplier_tp, "must exceed atr_multiplier_sl"
            )
        if not math.isfinite(self.fitness_score):
            raise DataQualityError("fitness_score", self.fitness_score, "must be finite")
        if self.evolved_at.tzinfo is None:
            raise DataQualityError("evolved_at", self.evolved_at, "must be tz-aware")

    def gene_values(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in GENE_SPECS}


@dataclass(frozen=True)
class ActiveParamSet:
    regime: RegimeType
    params: ParamSet
    promoted_at: datetime
    source_pending_id: str


@dataclass(frozen=True)
class PendingEntry:
    pending_id: str
    regime: RegimeType
    params: ParamSet
    staged_at: datetime
    boundaries_skipped: int


@dataclass(frozen=True)
class LabelledBar:
    """One OHLC bar of regime-labelled history; spread carries the C8 friction."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    spread: float
    regime: RegimeType

    def __post_init__(self) -> None:
        for f in fields(self):
            if f.type == "float":
                v = getattr(self, f.name)
                if not math.isfinite(v):
                    raise DataQualityError(f.name, v, "must be finite")
        if self.ts.tzinfo is None:
            raise DataQualityError("ts", self.ts, "must be tz-aware")
        if self.spread < 0:
            raise DataQualityError("spread", self.spread, "must be >= 0")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise DataQualityError("high/low", (self.high, self.low), "OHLC shape violated")


@dataclass(frozen=True)
class RegimeLabelledHistory:
    instrument: str
    bars: tuple[LabelledBar, ...]
