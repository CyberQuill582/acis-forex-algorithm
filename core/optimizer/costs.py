"""C8 shared cost model (ACIS-03 §5/§6.1, master §5 C8).

This is THE cost model: the fitness mini-backtest applies it, and the ACIS-09
backtest harness must import this same module — never re-implement it. That is
how "unit-tested identical in both places" is achieved: one module, one
pinned-semantics test (tests/unit/test_fitness.py::test_cost_model_semantics).
Phase 11 calibrates the per-instrument parameters against OANDA practice-feed
spreads (master §13, v2.9).

Invariants:
  * `per_side_cost` is the ONLY place friction is priced. Both callers (QIEA's
    selection fitness and the harness's graded book) must hold the SAME instance
    per instrument, or selection is scored against a different world than grading
    — the GAP-P12D-36 defect class.
  * The stress knob (GAP-P12D-46) can only make friction WORSE than declared:
    `stress >= 1.0`, `spread_floor >= 0`. A knob that could cheapen the world
    would let a run be flattered into a §14 pass, so the asymmetry is enforced in
    `__post_init__`, not in the caller's discipline.
  * Stress multiplies the WHOLE per-side cost (half-spread + commission +
    slippage), because the destination's cost is what is being stressed, not one
    of its components. It is a stress ladder, never a calibration: the hybrid
    overlay GAP-P12D-46 describes is additive-and-floored per session and state,
    and a flat multiplier must never be mistaken for it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.data.errors import DataQualityError


@dataclass(frozen=True)
class CostModel:
    """Per-instrument friction in price units, declared in instruments.yaml.

    `stress` and `spread_floor` are RUN properties, not instrument properties: they
    are never read from instruments.yaml, and a run that carries either non-default
    must say so in its report (GAP-P12D-46).
    """

    commission_per_side: float
    slippage_per_side: float
    stress: float = 1.0            # 1.0 = the declared world; >1 = the cost-stress ladder
    spread_floor: float = 0.0      # price units; the ladder's "p95 as a constant" rung

    def __post_init__(self) -> None:
        for name in ("commission_per_side", "slippage_per_side", "spread_floor"):
            v = getattr(self, name)
            if not math.isfinite(v) or v < 0:
                raise DataQualityError(name, v, "must be finite and >= 0")
        if not math.isfinite(self.stress) or self.stress < 1.0:
            raise DataQualityError(
                "stress", self.stress,
                "must be finite and >= 1.0 — the cost-stress knob may only make friction "
                "worse than declared (GAP-P12D-46)")

    @property
    def stressed(self) -> bool:
        """True when this model prices a world harsher than the declared one."""
        return self.stress != 1.0 or self.spread_floor > 0.0

    def per_side_cost(self, spread: float) -> float:
        """Cost of one fill side: half the quoted spread plus declared friction."""
        if not math.isfinite(spread) or spread < 0:
            raise DataQualityError("spread", spread, "must be finite and >= 0")
        return self.stress * (max(spread, self.spread_floor) / 2.0
                              + self.commission_per_side + self.slippage_per_side)

    def round_trip_cost(self, entry_spread: float, exit_spread: float) -> float:
        return self.per_side_cost(entry_spread) + self.per_side_cost(exit_spread)
