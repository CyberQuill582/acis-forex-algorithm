"""Frozen portfolio/order dataclasses for the Governor (ACIS-05 §4/§5).

F17 accounting boundary starts here: every size/NAV/exposure/delta quantity is
Decimal; prices may be float.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Mapping

from core.data.errors import DataQualityError
from core.signals.signal_types import StrategyType


@dataclass(frozen=True)
class Position:
    instrument: str
    direction: int                 # +1 | -1
    size_units: Decimal
    entry_price: float
    stop_loss: float               # broker-side stop (also GAP-0052 rebuild input)
    take_profit: float
    opened_at: datetime
    strategy_type: StrategyType
    param_set_id: str
    group_id: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not isinstance(self.size_units, Decimal) or self.size_units <= 0:
            raise DataQualityError("size_units", self.size_units, "must be positive Decimal")
        for name in ("entry_price", "stop_loss", "take_profit"):
            v = getattr(self, name)
            if not math.isfinite(v) or v <= 0:
                raise DataQualityError(name, v, "must be finite > 0")
        if self.opened_at.tzinfo is None:
            raise DataQualityError("opened_at", self.opened_at, "must be tz-aware")
        if not self.param_set_id:
            raise DataQualityError("param_set_id", self.param_set_id, "audit link required")


@dataclass(frozen=True)
class PortfolioState:
    nav: Decimal
    open_positions: tuple[Position, ...]
    per_currency_delta: Mapping[str, Decimal]   # signed, USD-notional terms
    per_cluster_exposure: Mapping[str, Decimal]  # USD-notional per cluster
    daily_drawdown_pct: float
    as_of: datetime
    stale: bool

    def __post_init__(self) -> None:
        if not isinstance(self.nav, Decimal) or self.nav <= 0:
            raise DataQualityError("nav", self.nav, "must be positive Decimal")
        for name in ("per_currency_delta", "per_cluster_exposure"):
            m = getattr(self, name)
            if not isinstance(m, MappingProxyType):
                raise DataQualityError(name, type(m), "must be immutable Mapping")
            for k, v in m.items():
                if not isinstance(v, Decimal):
                    raise DataQualityError(f"{name}[{k}]", v, "must be Decimal (F17)")
        if not math.isfinite(self.daily_drawdown_pct) or self.daily_drawdown_pct < 0:
            raise DataQualityError("daily_drawdown_pct", self.daily_drawdown_pct,
                                   "must be finite >= 0")
        if self.as_of.tzinfo is None:
            raise DataQualityError("as_of", self.as_of, "must be tz-aware")


@dataclass(frozen=True)
class SizedOrder:
    order_id: str
    signal_id: str
    instrument: str
    direction: int
    size_units: Decimal
    entry_price: float
    stop_loss: float
    take_profit: float | None    # None = no target (faithful TSMOM, v2.11)
    reason: str
    factors_snapshot: Mapping
    sized_at: datetime
    param_set_id: str
    group_id: str | None = None
    action: Literal["open", "close"] = "open"

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not isinstance(self.size_units, Decimal) or self.size_units < 0:
            raise DataQualityError("size_units", self.size_units,
                                   "must be non-negative Decimal (F17)")
        if not self.reason:
            raise DataQualityError("reason", self.reason, "every size needs its reason")
        if not isinstance(self.factors_snapshot, MappingProxyType):
            raise DataQualityError("factors_snapshot", type(self.factors_snapshot),
                                   "must be immutable Mapping")
        if self.sized_at.tzinfo is None:
            raise DataQualityError("sized_at", self.sized_at, "must be tz-aware")
