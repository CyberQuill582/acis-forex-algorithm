"""Time-ordered MarketStates for a historical window, streamed (ACIS-09 §5/§7).

Invariants:
  * Ticks come only from a declared source, through `BacktestDataLoader`'s §3 filtering
    (bad ticks and the FX weekend are dropped and logged).
  * Instruments are merged by event time, and every tick passes through the REAL
    `MarketStateFactory` (the engine's own validation is never bypassed); ticks the
    factory drops (duplicates) are skipped.
  * Nothing is held beyond one pending tick per instrument, so a year of ticks streams.
"""

from __future__ import annotations

import heapq
from datetime import datetime
from typing import Callable, Iterator, Sequence

from config.schemas import AcisConfig
from core.data.asset_classes import build_calendars
from core.data.normaliser import FactoryConfig, MarketState, MarketStateFactory
from tests.backtest.data_loader import BacktestDataLoader


def build_factory(cfg: AcisConfig, instruments: Sequence[str],
                  macro_imminent: Callable[[str, datetime], bool] | None = None) -> MarketStateFactory:
    """The production factory for `instruments` (enabled or not — labelling may run ahead
    of onboarding). With no event calendar, `macro_imminent` is always False (GAP-P12D-03)."""
    d = cfg.system.data
    calendars = build_calendars(cfg.instruments.calendars)
    specs = {s: cfg.instruments.instruments[s] for s in instruments}
    return MarketStateFactory(
        cfg=FactoryConfig(stale_threshold_ms=d.stale_threshold_ms,
                          clock_skew_tolerance_ms=d.clock_skew_tolerance_ms,
                          reorder_tolerance_ms=d.reorder_tolerance_ms,
                          tick_velocity_window_s=d.tick_velocity_window_s,
                          session_median_window=d.session_median_window,
                          session_median_min_samples=d.session_median_min_samples),
        calendars_by_instrument={s: calendars[sp.calendar] for s, sp in specs.items()},
        max_plausible_spread={s: sp.max_plausible_spread for s, sp in specs.items()},
        macro_imminent=macro_imminent or (lambda instrument, ts: False))


def market_states(*, cfg: AcisConfig, loader: BacktestDataLoader, factory: MarketStateFactory,
                  source: str, instruments: Sequence[str], start: datetime,
                  end: datetime) -> Iterator[MarketState]:
    streams = [loader.stream(source=source, instrument=i, start=start, end=end,
                             max_plausible_spread=cfg.instruments.instruments[i].max_plausible_spread)
               for i in instruments]
    for raw in heapq.merge(*streams, key=lambda t: t.event_time):
        state = factory.build(raw).state
        if state is not None:
            yield state
