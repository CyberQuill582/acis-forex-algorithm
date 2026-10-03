"""The target-position path's orders (ACIS-05 v1.7 §6.4): a banded target becomes SizedOrders.

Mental model:
  * delta = target − held. A reduction, or a flip's closing leg, is a reduce-only close NAMING the
    held position (§7 step 10). It passes no guard, because a reduction is never blocked (C-EXE-7).
  * An opening leg is an ENTRY. It meets every §7.1 guard (core/governor/guards.py) except NVMA's
    confidence and label vetoes (`target=True`, GAP-P12D-147), then §7.4's hard limits in order:
    - the account's lot cap: zero, never clamp;
    - the Risk edge's taper and the alpha-decay ×0.25: each only shrinks, and the result goes back on
      the lots toward zero, so a throttled one-lot order is zero;
    - the cluster and currency caps, with G-5's headroom.
    Every zero is returned with its reason.
  * The open carries the broker-side disaster stop at `stop_mult` × the daily true-range ATR from the
    slot's mark (R6-2), and no take-profit. Carver uses neither; the stop is a declared deviation.
  * Adding to a held position on the same side is not built: practice holds at most one lot, so it
    cannot arise, and live is closed until rung 1. It is refused (`add_unsupported`) and nothing is sent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Protocol

from core.governor.exposure import delta_contributions, exposure_breach
from core.governor.portfolio_types import PortfolioState, SizedOrder
from core.governor.target import target_on_lots
from core.governor.units import usd_per_base_unit
from core.regime.regime_types import RegimeContext

LOT_UNITS = Decimal("100000")        # the account lot cap's unit; FX only until GAP-P12D-27


class Held(Protocol):
    """What the gate reads of a held position (Risk's `RiskPosition` has it; the Governor imports no Risk type)."""
    instrument: str
    direction: int
    size_units: Decimal
    stop_loss: float | None
    param_set_id: str
    group_id: str | None


@dataclass(frozen=True)
class _Close:
    close: float


@dataclass(frozen=True)
class _Side:
    instrument: str
    direction: int


@dataclass(frozen=True)
class GateResult:
    orders: tuple[SizedOrder, ...]
    reason: str          # hold | reduce | flat | flip | open | add_unsupported | an entry's zero-reason


def target_orders(gov, *, limits, rules, clusters: Mapping, instrument: str, held: Held | None,
                  target: Decimal, mark: float, atr: float, stop_mult: float, step: Decimal, minimum: Decimal,
                  portfolio: PortfolioState, regime: RegimeContext | None, marks: Mapping[str, float], now: datetime,
                  family: str, snapshot: Mapping, logger) -> GateResult:
    """The orders that move `held` to `target` now, the close first (see the mental model)."""
    current = Decimal(held.direction) * held.size_units if held is not None else Decimal("0")
    if target == current:
        return GateResult((), "hold")
    if current and target and (target > 0) == (current > 0):
        if abs(target) > abs(current):
            logger.event("TARGET_ADD_REFUSED", instrument=instrument, held=str(current), target=str(target))
            return GateResult((), "add_unsupported")
        return GateResult((_close(held, abs(current) - abs(target), mark, now, "target_reduce"),), "reduce")
    closes = (_close(held, held.size_units, mark, now, "target_flat" if not target else "target_flip"),) if held else ()
    if not target:
        return GateResult(closes, "flat")
    direction = 1 if target > 0 else -1
    size, why = _entry_size(gov, limits, rules, clusters, instrument, direction, abs(target), mark, step, minimum,
                            portfolio, regime, marks, now, logger)
    stop = mark - direction * stop_mult * atr
    if size and not (atr > 0 and stop > 0):
        size, why = Decimal("0"), "stop_invalid"
    if not size:
        logger.event("TARGET_ENTRY_ZERO", instrument=instrument, reason=why, target=str(target))
        return GateResult(closes, why)
    opened = SizedOrder(
        order_id=str(uuid.uuid4()), signal_id=f"target:{family}:{instrument}:{now.isoformat()}",
        instrument=instrument, direction=direction, size_units=size, entry_price=mark, stop_loss=stop,
        take_profit=None, reason="target_open", sized_at=now, param_set_id=family,
        factors_snapshot=MappingProxyType({**snapshot, "atr": atr, "stop_mult": stop_mult}))
    return GateResult(closes + (opened,), "flip" if closes else "open")


def _entry_size(gov, limits, rules, clusters, instrument, direction, size: Decimal, mark, step, minimum,
                portfolio, regime, marks, now, logger) -> tuple[Decimal, str]:
    if regime is None:                               # no tick classified yet: no entry
        return Decimal("0"), "no_regime"
    guard = gov.guards.check(instrument, portfolio, regime, now, target=True)   # GAP-P12D-147
    if guard is not None:
        return Decimal("0"), guard
    if rules.max_lots is not None and size / LOT_UNITS > Decimal(str(rules.max_lots)):
        return Decimal("0"), "lot_cap"
    taper, decay = gov.throttle
    scaled = size * Decimal(str(taper)) * (Decimal("0.25") if decay else Decimal("1"))
    if scaled < size:
        size = target_on_lots(scaled, step, minimum)
        if not size:
            return Decimal("0"), "alpha_decay" if decay else "taper"
    per_unit = usd_per_base_unit(instrument, mark, {s: (_Close(p),) for s, p in marks.items()})
    if per_unit is None:
        return Decimal("0"), "no_usd_rate"
    notional = size * per_unit
    breach = exposure_breach(limits, portfolio, {c: notional for c, m in clusters.items() if instrument in m},
                             delta_contributions(_Side(instrument, direction), notional), instrument, logger)
    return (Decimal("0"), breach) if breach is not None else (size, "open")


def _close(pos: Held, size: Decimal, mark: float, now: datetime, reason: str) -> SizedOrder:
    return SizedOrder(
        order_id=str(uuid.uuid4()), signal_id=f"{reason}:{pos.instrument}", instrument=pos.instrument,
        direction=pos.direction, size_units=size, entry_price=mark,
        stop_loss=pos.stop_loss if pos.stop_loss is not None else mark, take_profit=None, reason=reason,
        factors_snapshot=MappingProxyType({"exit": reason}), sized_at=now, param_set_id=pos.param_set_id,
        group_id=pos.group_id, action="close")
