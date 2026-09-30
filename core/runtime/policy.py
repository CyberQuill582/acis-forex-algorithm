"""The position policy (GAP-0075): what a sized order does to what is already held.

The backtest book's rules (tests/backtest/book.py `PositionModel`) in production, so the engine
the demo runs is the engine the harness grades. Invariants:
  * One position per instrument. A same-side repeat of a held position is ignored.
  * An opposite order REVERSES: a reduce-only close of the whole holding, then the open, as
    two orders, never one (ACIS-13 §7.3). The executor opens only if the close filled whole.
  * A busy instrument (an order in flight) takes nothing new. Risk's positions lag a submit,
    so without this every tick would route the same open again: the per-tick firehose.
  * A pair opens only when every leg is flat and idle. A leg's exit closes its whole group,
    and a leg left alone (its partner closed or never filled) is closed (GAP-0040).
  * Exits the venue does not make are made here: a take-profit touch and the max hold, each a
    reduce-only close of the whole holding at the mark. The stop is NOT one: it rests at the
    venue (§279) and comes back as a venue fill.
  * This module creates only reduce-only closes of whole holdings. It never creates or
    resizes an open: every open is the Governor's own order, passed through or dropped.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from types import MappingProxyType
from typing import Collection, Mapping, Sequence

from core.governor.portfolio_types import SizedOrder
from core.risk.risk_types import RiskPosition

Held = Mapping[str, RiskPosition]


def close_of(pos: RiskPosition, *, reason: str, price: float, now: datetime) -> SizedOrder:
    """A reduce-only close naming `pos` (ACIS-05 step 10: its side, its whole size)."""
    return SizedOrder(
        order_id=str(uuid.uuid4()), signal_id=f"exit:{reason}:{pos.instrument}",
        instrument=pos.instrument, direction=pos.direction, size_units=pos.size_units,
        entry_price=price, stop_loss=pos.stop_loss if pos.stop_loss is not None else price,
        take_profit=None, reason=reason, factors_snapshot=MappingProxyType({"exit": reason}),
        sized_at=now, param_set_id=pos.param_set_id, group_id=pos.group_id, action="close")


def route(order: SizedOrder, held: Held, busy: Collection[str],
          now: datetime) -> tuple[SizedOrder, ...]:
    """The venue work one Governor order makes, in order; () when it changes nothing."""
    if order.size_units <= 0 or order.instrument in busy:
        return ()
    pos = held.get(order.instrument)
    if order.action == "close":          # a Governor close (weekend flatten) names its position
        return (order,) if pos is not None and pos.direction == order.direction else ()
    if pos is None:
        return (order,)
    if pos.direction == order.direction:
        return ()                         # same-side repeat: the book's dedup
    return (close_of(pos, reason="reverse", price=order.entry_price, now=now), order)


def route_group(legs: Sequence[SizedOrder], held: Held,
                busy: Collection[str]) -> tuple[SizedOrder, ...]:
    """Both legs or neither: a pair opens only onto flat, idle instruments."""
    if any(leg.size_units <= 0 or leg.instrument in held or leg.instrument in busy
           for leg in legs):
        return ()
    return tuple(legs)


def exits_due(held: Held, marks: Mapping[str, float], busy: Collection[str], now: datetime,
              max_hold_s: float) -> tuple[SizedOrder, ...]:
    """The closes the engine owes this tick: target, max hold, and whole-group exits."""
    due: dict[str, str] = {}
    for inst, pos in held.items():
        mark = marks.get(inst)
        if inst in busy or mark is None:
            continue
        if pos.take_profit is not None and (mark - pos.take_profit) * pos.direction >= 0:
            due[inst] = "target"
        elif (now - pos.opened_at).total_seconds() >= max_hold_s:
            due[inst] = "max_hold"
    legs = Counter(p.group_id for p in held.values() if p.group_id is not None)
    exiting = {held[i].group_id for i in due} - {None}
    for inst, pos in held.items():
        if inst in due or inst in busy or inst not in marks or pos.group_id is None:
            continue
        if pos.group_id in exiting:
            due[inst] = "group_exit"
        elif legs[pos.group_id] == 1:
            due[inst] = "group_orphan"
    return tuple(close_of(held[i], reason=r, price=marks[i], now=now)
                 for i, r in sorted(due.items()))
