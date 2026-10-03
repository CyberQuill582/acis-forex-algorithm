"""The event simulator's tick-window form: GOTOBI, USD/JPY into the 09:55 Tokyo fix (GAP-P12D-158;
Bessho, Sugimoto & Suzuki, arXiv 2301.13204 (2023); Ito & Yamada, JIE 109 (2017)).

Mental model:
  * PRICES at a day's local wall times come from the Dukascopy TICKS (`bi5.decode_arrays`): the price at
    T is the mid of the last tick at or before T, if it came within STALE_S seconds of T; its spread is
    that tick's ask - bid. No tick can come from after T, so a price never looks ahead. A missing price
    skips the day, with its reason.
  * LEGS: each holds `side` units from its entry label to its exit label, each side paying THE C8 model's
    `per_side_cost` at that tick's spread. A GATED leg trades only if the mid rose from its gate's first
    label to its second (Bessho §3.2: the sell after 09:55 only when the anomaly occurred by 09:00).
    Legs meeting at one label (out of a long, into a short) pay both sides there.
  * The days are the caller's (the gotobi days, or the control days for the benchmark). Each day's P&L
    lands on the first 17:00 New York mark at or after its last exit (`event_sim.marks`): RSIM's vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.bi5 import SYMBOLS, decode_arrays
from tests.backtest.event_intraday import Session
from tests.backtest.event_sim import EventResult, marks

STALE_S = 300
UTC = timezone.utc


@dataclass(frozen=True)
class Leg:
    entry: str
    exit: str
    side: float                                   # +1 long, -1 short
    gate: tuple[str, str] | None = None           # trade only if mid(gate[1]) > mid(gate[0])


def _ticks(root: Path, name: str, utc_day: date) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """One UTC day's ticks as (epoch ms, mid, spread), or None if the day has no file."""
    f = Path(root) / name / str(utc_day.year) / f"{utc_day.month - 1:02d}" / f"{utc_day.day:02d}_ticks.bi5"
    if not f.exists():
        return None
    ms, bid, ask = decode_arrays(f.read_bytes(), name, datetime(utc_day.year, utc_day.month, utc_day.day, tzinfo=UTC))
    return ms, (bid + ask) / 2, np.maximum(ask - bid, 0.0)


def window_prices(root: Path, name: str, days: Sequence[date], zone: str, times: Mapping[str, time]) -> list[Session]:
    """Each day's (mid, spread) at each labelled local wall time: the last tick at or before it."""
    if name not in SYMBOLS:
        raise ValueError(f"{name} has no tick symbol")
    tz, cache, out = ZoneInfo(zone), {}, []
    for d in days:
        prices = {}
        for label, t in times.items():
            at_ms = int(datetime.combine(d, t, tzinfo=tz).timestamp()) * 1000
            utc_day = datetime.fromtimestamp((at_ms - 1) / 1000, UTC).date()
            if utc_day not in cache:
                if len(cache) > 3:
                    cache.clear()
                cache[utc_day] = _ticks(root, name, utc_day)
            m = cache[utc_day]
            k = int(np.searchsorted(m[0], at_ms, side="right")) - 1 if m is not None else -1
            ok = k >= 0 and at_ms - m[0][k] <= STALE_S * 1000
            prices[label] = (float(m[1][k]), float(m[2][k])) if ok else None
        out.append(Session(d, prices))
    return out


def simulate_window(sessions: Sequence[Session], cost: CostModel | None, start: date, graded_from: date, end: date,
                    legs: Sequence[Leg], zone: str, times: Mapping[str, time]) -> EventResult:
    """`cost` None prices nothing; days outside [graded_from, end] are not graded."""
    grid = marks(start, end)
    epochs = np.array([e for _, e in grid])
    tz, daily, events, skipped = ZoneInfo(zone), np.zeros(len(grid)), [], []
    needed = list(dict.fromkeys(lbl for leg in legs for lbl in (leg.entry, leg.exit, *(leg.gate or ()))))
    for s in sessions:
        if not graded_from <= s.day <= end:
            continue
        missing = [lbl for lbl in needed if s.prices.get(lbl) is None]
        if missing:
            skipped.append({"day": s.day.isoformat(), "reason": "no " + missing[0]})
            continue
        pnl, last_exit, traded = 0.0, None, []
        for leg in legs:
            if leg.gate is not None and not s.prices[leg.gate[1]][0] > s.prices[leg.gate[0]][0]:
                continue
            (pin, sin), (pout, sout) = s.prices[leg.entry], s.prices[leg.exit]
            pnl += leg.side * (pout / pin - 1.0)
            if cost is not None:
                pnl -= cost.per_side_cost(sin) / pin + cost.per_side_cost(sout) / pin
            exit_at = int(datetime.combine(s.day, times[leg.exit], tzinfo=tz).timestamp())
            last_exit, traded = max(last_exit or exit_at, exit_at), traded + [f"{leg.entry}->{leg.exit}"]
        if last_exit is None:
            continue                                                     # every leg gated off: flat by rule
        k = int(np.searchsorted(epochs, last_exit, side="left"))
        if k >= len(grid):
            skipped.append({"day": s.day.isoformat(), "reason": "no mark after the exit"})
            continue
        daily[k] += pnl
        events.append({"day": s.day.isoformat(), "legs": traded})
    return EventResult(tuple(d for d, _ in grid), daily, tuple(events), tuple(skipped))
