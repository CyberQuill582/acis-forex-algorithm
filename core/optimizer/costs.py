"""C8 shared cost model (ACIS-03 §5/§6.1, master §5 C8).

This is THE cost model: the fitness mini-backtest applies it, and the ACIS-09
backtest harness must import this same module — never re-implement it. That is
how "unit-tested identical in both places" is achieved: one module, one
pinned-semantics test (tests/unit/test_fitness.py::test_cost_model_semantics).
Phase 11 calibrates the per-instrument parameters against OANDA practice-feed
spreads (master §13, v2.9).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.data.errors import DataQualityError


@dataclass(frozen=True)
class CostModel:
    """Per-instrument friction in price units, declared in instruments.yaml."""

    commission_per_side: float
    slippage_per_side: float

    def __post_init__(self) -> None:
        for name in ("commission_per_side", "slippage_per_side"):
            v = getattr(self, name)
            if not math.isfinite(v) or v < 0:
                raise DataQualityError(name, v, "must be finite and >= 0")

    def per_side_cost(self, spread: float) -> float:
        """Cost of one fill side: half the quoted spread plus declared friction."""
        if not math.isfinite(spread) or spread < 0:
            raise DataQualityError("spread", spread, "must be finite and >= 0")
        return spread / 2.0 + self.commission_per_side + self.slippage_per_side

    def round_trip_cost(self, entry_spread: float, exit_spread: float) -> float:
        return self.per_side_cost(entry_spread) + self.per_side_cost(exit_spread)
