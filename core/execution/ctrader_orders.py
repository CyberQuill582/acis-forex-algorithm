"""cTrader order arithmetic and report mapping (ACIS-13 §4.2, §4.3, §6.3, §7.3, §7.7) — pure functions,
no I/O, so every rule is unit-pinned.

Invariants:
  * Volumes are exact: units × 100 must be an integer (F-13), else DataQualityError; money and
    size are Decimal end to end (F17).
  * Quantity rounds DOWN to the symbol's step, is capped at its maximum, and below its minimum is 0 —
    "not placeable here", never rounded up (C-VEN-3, C-EXE-6).
  * A stop rides a market open as a RELATIVE distance d = |price − stop|, rounded DOWN to the tick,
    so the venue's stop (fill ∓ d) is never further than the Governor sized (§6.3). It must sit on
    the protective side and at least the venue's minimum distance away, else the open is refused
    without contacting the venue.
  * One venue order → one FillReport: the volume-weighted price over its deals, the exact filled
    Decimal, FILLED / PARTIAL / REJECTED / CANCELLED by the ACIS-06 invariants (§4.2).
  * ACIS's own positions carry the binding's label; anything else on the account is foreign.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal
from typing import Iterable, Mapping

from core.data.ctrader.schema import PRICE_SCALE, VOLUME_SCALE, TradeSide, enum_value
from core.data.errors import DataQualityError
from core.execution.ctrader_symbols import VenueSymbolSpec
from core.execution.venue import BrokerPosition, FillReport, FillStatus, slippage_bps


def label(account_key: str) -> str:
    return "ACIS:" + hashlib.sha256(account_key.encode("utf-8")).hexdigest()[:8]


def protocol_volume(units: Decimal) -> int:
    scaled = units * VOLUME_SCALE
    if scaled != scaled.to_integral_value():
        raise DataQualityError("units", units, "not a whole number of 0.01 units (F-13)")
    return int(scaled)


def quantize(spec: VenueSymbolSpec, units: Decimal) -> Decimal:
    steps = (units / spec.step_units).to_integral_value(rounding=ROUND_FLOOR)
    placed = min(steps * spec.step_units, spec.max_units)
    return placed if placed >= spec.min_units else Decimal("0")


def side(direction: int) -> int:
    return int(TradeSide.BUY if direction > 0 else TradeSide.SELL)


def direction_of(raw_side) -> int:
    return 1 if enum_value(TradeSide, raw_side) is TradeSide.BUY else -1


def min_stop_distance(spec: VenueSymbolSpec, price: Decimal) -> Decimal:
    """The venue's minimum stop distance as a price distance (F-41; confirmed by probe, OQ-09)."""
    if spec.distance_in_percent:
        return price * Decimal(spec.sl_distance) / Decimal(10_000)   # hundredths of a percent
    return Decimal(spec.sl_distance) * spec.tick                      # points


def relative_stop(spec: VenueSymbolSpec, requested_price: float, stop_loss: float,
                  direction: int) -> int | None:
    """`relativeStopLoss` for a market open, or None when the stop is too close to place."""
    price, stop = Decimal(str(requested_price)), Decimal(str(stop_loss))
    if (stop - price) * direction > 0:                 # beyond the entry: a stop on the wrong side
        raise DataQualityError("stop_loss", stop_loss, "not on the protective side of the entry")
    d = (abs(price - stop) / spec.tick).to_integral_value(rounding=ROUND_FLOOR) * spec.tick
    if d <= 0 or d < min_stop_distance(spec, price):
        return None
    return int(d * PRICE_SCALE)          # a multiple of 10^(5 − digits) by construction (F-14)


def fill_report(deals: Iterable[Mapping], *, fill_id: str, order_id: str, fragment_id: str,
                instrument: str, direction: int, requested_units: Decimal,
                requested_price: float, session_id: str, now: datetime,
                cancelled: bool) -> FillReport:
    """One venue order's deals as ONE report. `cancelled`: the venue ended the order unfilled or
    with an IOC remainder (ORDER_CANCELLED/EXPIRED) rather than rejecting it."""
    deals = list(deals)
    filled_raw = sum(int(d["filledVolume"]) for d in deals)
    filled = Decimal(filled_raw) / VOLUME_SCALE
    if filled == 0:
        status = FillStatus.CANCELLED if cancelled else FillStatus.REJECTED
        return FillReport(fill_id=fill_id, order_id=order_id, fragment_id=fragment_id,
                          instrument=instrument, direction=direction,
                          requested_price=requested_price, fill_price=0.0,
                          filled_units=Decimal("0"), slippage_bps=0.0, fill_time=now,
                          venue="ctrader", status=status, remaining_units=requested_units,
                          session_id=session_id)
    vwap = sum(float(d["executionPrice"]) * int(d["filledVolume"]) for d in deals) / filled_raw
    last = max(int(d["executionTimestamp"]) for d in deals)
    return FillReport(
        fill_id=fill_id, order_id=order_id, fragment_id=fragment_id, instrument=instrument,
        direction=direction, requested_price=requested_price, fill_price=vwap,
        filled_units=filled, slippage_bps=slippage_bps(requested_price, vwap, direction),
        fill_time=datetime.fromtimestamp(last / 1000, tz=timezone.utc), venue="ctrader",
        status=FillStatus.FILLED if filled >= requested_units else FillStatus.PARTIAL,
        remaining_units=max(requested_units - filled, Decimal("0")), session_id=session_id)


def unsolicited_report(deal: Mapping, *, account_key: str, instrument: str,
                       stop_price: float | None) -> FillReport:
    """A deal ACIS did not request (a stop firing, a stop-out, a manual close): ACIS-06 v1.4 ids,
    the side traded, and the stop level as the requested price, so the slippage is the measured
    gap-through-stop cost (§7.7). A close with no stop (a manual one) reports zero slippage."""
    price = float(deal["executionPrice"])
    direction = direction_of(deal["tradeSide"])
    requested = stop_price if stop_price is not None else price
    filled = Decimal(int(deal["filledVolume"])) / VOLUME_SCALE
    volume = Decimal(int(deal["volume"])) / VOLUME_SCALE
    return FillReport(
        fill_id=f"ct:{account_key}:deal:{deal['dealId']}", order_id=f"venue:{deal['orderId']}",
        fragment_id=f"venue:{deal['dealId']}", instrument=instrument, direction=direction,
        requested_price=requested, fill_price=price, filled_units=filled,
        slippage_bps=slippage_bps(requested, price, direction),
        fill_time=datetime.fromtimestamp(int(deal["executionTimestamp"]) / 1000, tz=timezone.utc),
        venue="ctrader", status=FillStatus.FILLED if filled >= volume else FillStatus.PARTIAL,
        remaining_units=max(volume - filled, Decimal("0")), session_id="venue")


def broker_positions(positions: Iterable[Mapping], symbols: Mapping[int, str],
                     own_label: str) -> tuple[tuple[BrokerPosition, ...], tuple[Mapping, ...]]:
    """ACIS's positions per instrument, and the foreign ones. Fragments of one order are separate
    venue positions on a hedging account; they sum. The stop is the one FURTHEST from the entry
    (the worst case), and None if any of them is unprotected, so a missing stop is never hidden."""
    ours: dict[str, list[Mapping]] = {}
    foreign = []
    for p in positions:
        trade = p["tradeData"]
        if trade.get("label") != own_label or int(trade["symbolId"]) not in symbols:
            foreign.append(p)
            continue
        ours.setdefault(symbols[int(trade["symbolId"])], []).append(p)
    out = []
    for instrument, group in sorted(ours.items()):
        directions = {direction_of(p["tradeData"]["tradeSide"]) for p in group}
        if len(directions) != 1:
            raise DataQualityError("positions", instrument, "ACIS holds both sides (C-VEN-9)")
        (direction,) = directions
        units = sum((Decimal(int(p["tradeData"]["volume"])) / VOLUME_SCALE for p in group), Decimal(0))
        stops = [p.get("stopLoss") for p in group]
        stop = None if any(x is None for x in stops) else (min(stops) if direction > 0 else max(stops))
        out.append(BrokerPosition(instrument=instrument, direction=direction, size_units=units,
                                  stop_loss=stop))
    return tuple(out), tuple(foreign)
