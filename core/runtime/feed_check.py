"""The target path's own data check (owner ruling 2026-10-03, "Replace before the cutover"; master v2.33).
It replaces NVMA on the money path for daily target entries (R-1: NVMA leaves the money paths).

Mental model:
  * `FeedWatch.observe(state)` keeps, per instrument, the last tick (its time, quoted spread, late-tick
    flag and macro flag) and the last `window` quoted spreads. The spread's yardstick is the median of
    those RECENT spreads, not a per-session median: the FX slot (08:00 New York) sits on a session
    boundary, where a per-session window would be empty.
  * `FeedWatch.refusal(instrument, now)` says why a daily target ENTRY may not go out now, or None:
    `no_feed` (no tick yet), `stale_feed` (the last tick is older than `max_age_s`, or arrived late:
    a silent or lagging feed), `feed_warming` (fewer than `min_ticks` spreads seen), `wide_spread` (the
    last spread above `spread_mult` x the recent median), `macro_event` (the feed's macro flag; inert
    until the event calendar is wired, GAP-P12D-03). An exit never asks (C-EXE-7).
  * It reads only the tick feed: no regime, confidence, label or indicator.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from statistics import median

from core.data.normaliser import MarketState


class FeedWatch:
    def __init__(self, *, max_age_s: float, spread_mult: float, window: int = 600, min_ticks: int = 50) -> None:
        self._max_age, self._mult, self._window, self._min = max_age_s, spread_mult, window, min_ticks
        self._last: dict[str, tuple[datetime, float, bool, bool]] = {}
        self._spreads: dict[str, deque[float]] = {}

    def observe(self, st: MarketState) -> None:
        self._last[st.instrument] = (st.timestamp, st.spread, st.is_stale, st.macro_events_imminent)
        self._spreads.setdefault(st.instrument, deque(maxlen=self._window)).append(st.spread)

    def refusal(self, instrument: str, now: datetime) -> str | None:
        last = self._last.get(instrument)
        if last is None:
            return "no_feed"
        at, spread, late, macro = last
        if late or (now - at).total_seconds() > self._max_age:
            return "stale_feed"
        spreads = self._spreads[instrument]
        if len(spreads) < self._min:
            return "feed_warming"
        if spread > self._mult * median(spreads):
            return "wide_spread"
        return "macro_event" if macro else None
