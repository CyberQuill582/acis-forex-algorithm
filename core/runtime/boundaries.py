"""Session-boundary instants crossed by a stream of ticks (ACIS-03 §7 C1/C2, ACIS-09 §5).

Staged params promote only at a declared session boundary, and only when flat. Neither a
replay nor the live runtime is guaranteed a tick inside the boundary minute, so this clock
reports each declared boundary instant the ticks step over, and both sweep
`ParamLibrary.on_boundary` with it: one clock, the harness and the engine (moved here from
tests/backtest/boundary_clock.py with the runtime, master v2.25).

Invariants: every boundary strictly after the first observed tick and at or before the
current tick is reported exactly once, in time order — including every boundary inside a
weekend or holiday gap. Each instant is the exact local wall time in its zone, so it
follows DST (`core/data/fx_clock.py`) and satisfies `is_session_boundary`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from config.schemas import ZonedTime
from core.data.fx_clock import next_local


class BoundaryClock:
    def __init__(self, boundaries: Sequence[ZonedTime]) -> None:
        if not boundaries:
            raise ValueError("a boundary clock needs at least one declared boundary")
        self._boundaries = tuple(boundaries)
        self._next: datetime | None = None

    def _after(self, ts: datetime) -> datetime:
        return min(next_local(ts, b.zone, b.at) for b in self._boundaries)

    def crossed(self, ts: datetime) -> list[datetime]:
        if self._next is None:
            self._next = self._after(ts)
            return []
        out: list[datetime] = []
        while ts >= self._next:
            out.append(self._next)
            self._next = self._after(self._next)
        return out
