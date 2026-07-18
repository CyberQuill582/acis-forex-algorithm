"""Frozen boundary dataclasses for the Risk Monitor (ACIS-07 §4/§5).

`RiskSnapshot` is the LOCKED output shape. `daily_pnl`/`equity` are Decimal —
the F17 accounting boundary. `PlatformDrawdownState` carries each §9.5 rule's
drawdown measured under the PLATFORM's own semantics, never merged numerically
with engine measures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.data.errors import DataQualityError


def _finite(name: str, v: float, lo: float | None = None) -> None:
    if not math.isfinite(v):
        raise DataQualityError(name, v, "must be finite")
    if lo is not None and v < lo:
        raise DataQualityError(name, v, f"must be >= {lo}")


@dataclass(frozen=True)
class Trade:
    """A closed round-trip reconstructed from FillReports (ACIS-07 §5).
    `pnl` is realised, in account (USD) terms, Decimal (F17)."""

    instrument: str
    direction: int                 # of the position that was closed
    units: Decimal
    entry_price: float
    exit_price: float
    opened_at: datetime
    closed_at: datetime
    pnl: Decimal
    param_set_id: str

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not isinstance(self.units, Decimal) or self.units <= 0:
            raise DataQualityError("units", self.units, "must be positive Decimal")
        for name in ("entry_price", "exit_price"):
            v = getattr(self, name)
            if not math.isfinite(v) or v <= 0:
                raise DataQualityError(name, v, "must be finite > 0")
        if not isinstance(self.pnl, Decimal):
            raise DataQualityError("pnl", self.pnl, "must be Decimal (F17)")
        if self.opened_at.tzinfo is None or self.closed_at.tzinfo is None:
            raise DataQualityError("opened_at/closed_at", self, "must be tz-aware")
        if self.closed_at < self.opened_at:
            raise DataQualityError("closed_at", self.closed_at, "before opened_at")
        if not self.param_set_id:
            raise DataQualityError("param_set_id", self.param_set_id, "audit link required")


@dataclass(frozen=True)
class RiskPosition:
    """The monitor's broker-truth position view (one net position per
    instrument, netting accounts — ACIS-06 §7.5 v1). Metadata is carried from
    `note_order` when known; a reconciled-from-broker position has none."""

    instrument: str
    direction: int
    size_units: Decimal
    avg_entry_price: float
    opened_at: datetime
    param_set_id: str              # "unknown:<origin>" when reconciled without meta
    group_id: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not isinstance(self.size_units, Decimal) or self.size_units <= 0:
            raise DataQualityError("size_units", self.size_units,
                                   "must be positive Decimal")
        if not math.isfinite(self.avg_entry_price) or self.avg_entry_price <= 0:
            raise DataQualityError("avg_entry_price", self.avg_entry_price,
                                   "must be finite > 0")
        if self.opened_at.tzinfo is None:
            raise DataQualityError("opened_at", self.opened_at, "must be tz-aware")
        if not self.param_set_id:
            raise DataQualityError("param_set_id", self.param_set_id, "required")


@dataclass(frozen=True)
class PlatformDrawdownState:
    """One per rule in the §9.5 stricter-of set."""

    rule_key: str                  # e.g. "prop_demo:trailing:intraday:equity"
    measured_pct: float            # under the PLATFORM's semantics
    limit_pct: float
    distance_fraction: float       # measured/limit ∈ [0, ∞)
    taper_factor: float            # this rule's §9.5 taper ∈ [0, 1]

    def __post_init__(self) -> None:
        if not self.rule_key:
            raise DataQualityError("rule_key", self.rule_key, "required")
        _finite("measured_pct", self.measured_pct, lo=0.0)
        _finite("limit_pct", self.limit_pct)
        if self.limit_pct <= 0:
            raise DataQualityError("limit_pct", self.limit_pct, "must be > 0")
        _finite("distance_fraction", self.distance_fraction, lo=0.0)
        _finite("taper_factor", self.taper_factor, lo=0.0)
        if self.taper_factor > 1.0:
            raise DataQualityError("taper_factor", self.taper_factor, "must be <= 1")


@dataclass(frozen=True)
class RiskSnapshot:
    """ACIS-07 §4 — LOCKED shape."""

    timestamp: datetime
    daily_pnl: Decimal
    daily_drawdown_pct: float
    open_drawdown_pct: float
    total_drawdown_pct: float          # daily + open
    portfolio_var_1pct: float          # 1% VaR as % NAV
    max_correlated_cluster_pct: float
    rolling_sharpe_50t: float
    rolling_win_rate_50t: float
    alpha_decay_flag: bool
    alpha_decay_state: str             # inactive_warming | active | flagged  (C5)
    slippage_slope_alert: bool
    equity: Decimal
    equity_floor_breached: bool
    instruments_halted: tuple[str, ...]
    platform_drawdown: tuple[PlatformDrawdownState, ...]
    taper_factor: float                # min across limits; 1.0 = far from every wall
    session_id: str

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise DataQualityError("timestamp", self.timestamp, "must be tz-aware")
        if not isinstance(self.daily_pnl, Decimal) or not isinstance(self.equity, Decimal):
            raise DataQualityError("daily_pnl/equity", self, "must be Decimal (F17)")
        for name in ("daily_drawdown_pct", "open_drawdown_pct", "total_drawdown_pct",
                     "portfolio_var_1pct", "max_correlated_cluster_pct"):
            _finite(name, getattr(self, name), lo=0.0)
        for name in ("rolling_sharpe_50t", "rolling_win_rate_50t"):
            _finite(name, getattr(self, name))
        if self.alpha_decay_state not in ("inactive_warming", "active", "flagged"):
            raise DataQualityError("alpha_decay_state", self.alpha_decay_state,
                                   "must be inactive_warming|active|flagged (C5)")
        _finite("taper_factor", self.taper_factor, lo=0.0)
        if self.taper_factor > 1.0:
            raise DataQualityError("taper_factor", self.taper_factor, "must be <= 1")
        if not self.session_id:
            raise DataQualityError("session_id", self.session_id, "required")
