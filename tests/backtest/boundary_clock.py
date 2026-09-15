"""Session-boundary instants crossed by a historical replay (ACIS-03 §7 C1/C2, ACIS-09 §5).

In production the medium loop sweeps `ParamLibrary.on_boundary(now)` at every declared
session boundary; staged params promote only there, and only when flat. A replay has no
wall clock, so this clock reports each declared boundary instant that the replay's ticks
step over.

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
