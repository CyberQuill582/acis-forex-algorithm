"""Regime stability score + advisory half-life estimator (ACIS-02 §6, C3/C-REG-3)."""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime


class RegimeStabilityTracker:
    """Per-instrument recent-classification history.

    stability = fraction of the last `window` classifications equal to the
    current regime. half-life = ln(2) x mean observed dwell time of completed
    regime episodes (advisory only — logged/exposed, never a sizing factor).
    """

    def __init__(self, window: int, default_half_life_s: int) -> None:
        self._labels: deque = deque(maxlen=window)
        self._default_half_life = default_half_life_s
        self._dwells_s: deque = deque(maxlen=window)
        self._current: str | None = None
        self._current_since: datetime | None = None

    def record(self, regime: str, ts: datetime) -> None:
        self._labels.append(regime)
        if regime != self._current:
            if self._current is not None and self._current_since is not None:
                dwell = (ts - self._current_since).total_seconds()
                if dwell > 0:
                    self._dwells_s.append(dwell)
            self._current = regime
            self._current_since = ts

    def stability(self, regime: str) -> float:
        if not self._labels:
            return 0.0
        return sum(1 for r in self._labels if r == regime) / len(self._labels)

    def half_life_seconds(self) -> int:
        if not self._dwells_s:
            return self._default_half_life  # cold start: advisory floor, never fabricated precision
        mean_dwell = sum(self._dwells_s) / len(self._dwells_s)
        return int(math.log(2) * mean_dwell)
