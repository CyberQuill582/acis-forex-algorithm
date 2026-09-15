"""Engine warm-up for a cold walk-forward start (GAP-P12D-24, F-E3).

TSMOM needs `tsmom_min_history_days` completed daily bars. A cold engine would build them
from observed ticks only, so it could not trade TSMOM for most of its first test year (or
for 2024 of a holdout run). Invariants:
  * `daily_closes` keeps one close per FX trading day (17:00 New York → 17:00 New York,
    `fx_clock.trading_day`) — the close of that day's last 1-minute bar that CLOSES by `end`,
    so nothing after the training end is read.
  * `seed_tsmom` feeds them oldest first through AGON's history-seeding path.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from core.data.fx_clock import trading_day
from core.optimizer.param_types import LabelledBar


def daily_closes(bars: Iterable[LabelledBar], end: datetime,
                 bar_seconds: int) -> list[tuple[date, float]]:
    span = timedelta(seconds=bar_seconds)
    last: dict[date, float] = {}
    for b in bars:
        if b.ts + span <= end:
            last[trading_day(b.ts)] = b.close
    return sorted(last.items())


def seed_tsmom(agon, instrument: str, closes: Iterable[tuple[date, float]]) -> int:
    n = 0
    for _, close in closes:
        agon.observe_daily_close(instrument, close)
        n += 1
    return n
