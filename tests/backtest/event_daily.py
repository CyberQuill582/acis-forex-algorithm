"""REBAL's book: a position set at each US cash close and held to the next (GAP-P12D-157; the event
simulator's daily form, master v2.34).

Mental model:
  * SESSIONS are the business days the signal reads. At each session's ANCHOR (event_sim's: the close
    mid of the last traded hour ending by the 16:00 New York close, inside the session) the book marks
    its held fraction of capital to the anchor, then trades to the session's target. A session with no
    anchor (a feed hole) neither marks nor trades: the next anchor books the move at the held position,
    and the session is listed as skipped. A QUOTED hour counts: traded, or its price moved (owner ruling
    2026-10-03, GAP-P12D-156: Dukascopy recorded moving US500 quotes with zero volume in 2013).
  * EQUITY LEG: the US500 CFD. Each trade pays THE C8 model's `per_side_cost` at the anchor hour's
    spread on the change in units. NOTE LEG (v1b only): minus the position on the modelled note
    futures (`rebal.note_returns` compounded between anchors) at a declared per-side cost.
    Swap-free (R1-D9): no financing. Positions start at `graded_from`; before it the book is flat.
  * Each session's P&L lands on its 17:00 New York mark (`event_sim.marks`): RSIM's kind of vector.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Sequence

import numpy as np

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.event_sim import EventResult, Leg, marks

EXCHANGE = "XNYS"


def quoted(h: Hourly) -> Hourly:
    """The hours with a price: traded, or moved with zero volume reported; a frozen flat hour is not."""
    return replace(h, traded=h.traded | (h.mid_open != h.mid_close))


def simulate_daily(us500: Hourly, sessions: Sequence[date], target: np.ndarray, cost: CostModel | None,
                   start: date, graded_from: date, end: date, note: np.ndarray | None = None,
                   note_cost: float = 0.0) -> EventResult:
    """`cost` None prices nothing (the passive benchmark); `note` gives v1b its short note leg."""
    grid = marks(start, end)
    at = {d: k for k, (d, _) in enumerate(grid)}
    leg = Leg(quoted(us500), np.array([t for _, t in grid], np.int64))
    daily, skipped = np.zeros(len(grid)), []
    held, p_last, note_acc = 0.0, None, 1.0
    for s, d in enumerate(sessions):
        if not start <= d <= end:
            continue
        note_acc *= 1.0 + (note[s] if note is not None else 0.0)
        j = leg.anchor(EXCHANGE, d)
        if j is None:
            if d >= graded_from:
                skipped.append({"index": "US500", "session": d.isoformat(), "reason": "no_anchor"})
            continue
        p = float(leg.closes[j])
        if p_last is not None and held:
            daily[at[d]] += held * ((p - p_last) / p_last - (note_acc - 1.0))
        new = float(target[s]) if d >= graded_from else 0.0
        if cost is not None:
            daily[at[d]] -= abs(new - held) * (cost.per_side_cost(float(leg.spreads[j])) / p
                                               + (note_cost if note is not None else 0.0))
        held, p_last, note_acc = new, p, 1.0
    return EventResult(tuple(d for d, _ in grid), daily, (), tuple(skipped))
