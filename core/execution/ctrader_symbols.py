"""cTrader symbols at attach (ACIS-13 §5.1, §5.2, §6.4, §7.3 step 2): the venue's own contract for
each enabled instrument, cross-checked against instruments.yaml, and the descriptor derived from it.

Invariants:
  * A symbol is matched by its EXACT venue name (`venue.symbol_names`); none, two, or a disabled
    one is fatal — the §13 suffix law, solved once, never fuzzy. symbolIds are per server (F-20)
    and are rebuilt at every attach, never cached across accounts or servers.
  * The venue's tick must equal instruments.yaml's, an FX lot must be UNITS_PER_LOT (C-VEN-11), and
    the quote asset must be the declared quote currency. A venue STRICTER than instruments.yaml (a
    larger minimum, a coarser step) is fatal until a human commits its values; a looser one is
    logged only, so the sizing and cost models never lie.
  * The descriptor is the strictest across enabled symbols (largest minimum, coarsest step, smallest
    maximum); the face still enforces each symbol's own values at submit.
  * The venue's schedule decides "closed" for entries: seconds from Sunday 00:00 in its own zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Mapping
from zoneinfo import ZoneInfo

from core.data.ctrader.schema import (VOLUME_SCALE, AccountType, DistanceType, TradingMode,
                                      enum_value, field)
from core.execution.venue import UNITS_PER_LOT, CapabilityDescriptor


class AttachFatal(Exception):
    """An attach step failed; `verdict` names it (ACIS-13 §9)."""

    def __init__(self, verdict: str, reason: str) -> None:
        super().__init__(f"{verdict}: {reason}")
        self.verdict = verdict
        self.reason = reason


@dataclass(frozen=True)
class VenueSymbolSpec:
    engine_symbol: str
    venue_name: str
    symbol_id: int
    digits: int
    lot_size_units: Decimal
    min_units: Decimal
    step_units: Decimal
    max_units: Decimal
    sl_distance: int
    distance_in_percent: bool
    trading_mode: TradingMode
    schedule: tuple[tuple[int, int], ...]        # (startSecond, endSecond) from Sunday 00:00
    schedule_tz: str
    holidays: tuple[tuple[date, bool, int, int, str], ...]   # (date, recurring, start s, end s, zone)
    pnl_conversion_fee_rate: int

    @property
    def tick(self) -> Decimal:
        return Decimal(1).scaleb(-self.digits)

    def is_open(self, now: datetime) -> bool:
        local = now.astimezone(ZoneInfo(self.schedule_tz))
        second = (local.isoweekday() % 7) * 86400 + local.hour * 3600 + local.minute * 60 + local.second
        if not any(start <= second < end for start, end in self.schedule):
            return False
        for day, recurring, start, end, zone in self.holidays:     # each holiday in its own zone
            there = now.astimezone(ZoneInfo(zone))
            same = day == there.date() or (recurring and (day.month, day.day) == (there.month, there.day))
            if same and start <= there.hour * 3600 + there.minute * 60 + there.second < end:
                return False
        return True


def match_symbols(light: list[Mapping], names: Mapping[str, str]) -> dict[str, int]:
    """engine instrument → symbolId, by exact venue name, each enabled and unique."""
    out = {}
    for engine, venue_name in names.items():
        hits = [s for s in light if s.get("symbolName") == venue_name]
        if len(hits) != 1 or not field(hits[0], "enabled"):
            raise AttachFatal("ATTACH_SYMBOL", f"{engine}: {len(hits)} enabled match(es) for "
                                               f"venue name {venue_name!r}")
        out[engine] = int(hits[0]["symbolId"])
    return out


def _units(raw) -> Decimal:
    return Decimal(int(raw)) / VOLUME_SCALE          # "in cents" (F-20)


def spec_from(engine: str, venue_name: str, sym: Mapping) -> VenueSymbolSpec:
    holidays = tuple((date(1970, 1, 1) + timedelta(days=int(h["holidayDate"])),
                      bool(h.get("isRecurring", False)), int(h.get("startSecond", 0)),
                      int(h.get("endSecond", 86400)), str(h["scheduleTimeZone"]))
                     for h in sym.get("holiday", ()))
    return VenueSymbolSpec(
        engine_symbol=engine, venue_name=venue_name, symbol_id=int(sym["symbolId"]),
        digits=int(sym["digits"]), lot_size_units=_units(sym["lotSize"]),
        min_units=_units(sym["minVolume"]), step_units=_units(sym["stepVolume"]),
        max_units=_units(sym["maxVolume"]), sl_distance=int(sym.get("slDistance", 0)),
        distance_in_percent=enum_value(DistanceType, field(sym, "distanceSetIn"))
        is DistanceType.SYMBOL_DISTANCE_IN_PERCENTAGE,
        trading_mode=enum_value(TradingMode, field(sym, "tradingMode")),
        schedule=tuple((int(i["startSecond"]), int(i["endSecond"])) for i in sym.get("schedule", ())),
        schedule_tz=str(sym.get("scheduleTimeZone", "UTC")), holidays=holidays,
        pnl_conversion_fee_rate=int(sym.get("pnlConversionFeeRate", 0)))


def cross_check(spec: VenueSymbolSpec, meta, quote_asset: str, log) -> None:
    """§6.4 against the instrument's instruments.yaml entry (`meta`)."""
    if spec.tick != Decimal(str(meta.tick_size)):
        raise AttachFatal("ATTACH_CONTRACT", f"{spec.engine_symbol}: venue tick {spec.tick} "
                                             f"!= instruments.yaml {meta.tick_size}")
    if meta.asset_class == "fx" and spec.lot_size_units != UNITS_PER_LOT:
        raise AttachFatal("ATTACH_CONTRACT", f"{spec.engine_symbol}: lot {spec.lot_size_units}")
    if quote_asset != meta.quote_ccy:
        raise AttachFatal("ATTACH_CONTRACT", f"{spec.engine_symbol}: quote {quote_asset}")
    declared_min = Decimal(str(meta.min_lot)) * UNITS_PER_LOT
    declared_step = Decimal(str(meta.lot_step)) * UNITS_PER_LOT
    if spec.min_units > declared_min or declared_step % spec.step_units != 0:
        raise AttachFatal("ATTACH_CONTRACT", f"{spec.engine_symbol}: the venue is stricter "
                                             "(minimum or step); a human commits its values")
    if spec.min_units < declared_min or spec.step_units < declared_step:
        log.event("VENUE_LOOSER_THAN_DECLARED", instrument=spec.engine_symbol,
                  min_units=str(spec.min_units), step_units=str(spec.step_units))


def descriptor(specs: list[VenueSymbolSpec], account_type,
               asset_classes: frozenset[str]) -> CapabilityDescriptor:
    kind = enum_value(AccountType, account_type)
    if kind is AccountType.SPREAD_BETTING:
        raise AttachFatal("ATTACH_ACCOUNT_TYPE", "spread-betting accounts are not supported")
    lots = lambda units: float(units / UNITS_PER_LOT)                 # noqa: E731
    return CapabilityDescriptor(
        venue="ctrader", order_types=frozenset({"market"}), supports_ioc=True,
        account_model="hedging" if kind is AccountType.HEDGED else "netting", partial_close=True,
        min_lot=lots(max(s.min_units for s in specs)), lot_step=lots(max(s.step_units for s in specs)),
        max_order_lots=lots(min(s.max_units for s in specs)),
        symbol_map={s.engine_symbol: s.venue_name for s in specs}, quote_depth=False,
        asset_classes=asset_classes, server_side_stops=True)
