"""The deterministic paper venue: the v1 conformant adapter (ACIS-06 §7.5). Moved out of
core/execution/venue.py (legibility budget, GAP-P12M-01).

Invariants:
  * Idempotent by `fragment_id`: a duplicate submit returns the ORIGINAL FillReport and
    never hits the venue twice (C-EXE-4/5).
  * A close is reduce-only and atomic: read-and-act under one lock, capped at the holding
    on the named side, REJECTED with nothing held (C-EXE-7).
  * A stop rests AT the venue, set atomically with the fill and retired when flat (§279).
    When it fires (`trigger_stop`, the shared suite's hook, ACIS-06 v1.4) the whole
    position closes at the price given — a gap fills through the stop, never at it — and
    the fill arrives only on `venue_fills()`, unsolicited, never as a reply to a request.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import AsyncIterator, Mapping

from core.data.errors import DataQualityError
from core.execution.venue import (BrokerAccount, BrokerPosition, CapabilityDescriptor,
                                  ExecutionFace, FillReport, FillStatus, slippage_bps)


# the shipped FX universe (config/instruments.yaml, R1.6): the paper descriptor maps every enabled pair
MOCK_SYMBOLS = ("EUR_USD", "USD_JPY", "GBP_USD", "AUD_USD", "USD_CAD", "USD_CHF", "EUR_GBP", "EUR_JPY",
                "GBP_JPY", "AUD_JPY", "EUR_CHF", "EUR_AUD", "CHF_JPY")


class MockExecutionFace(ExecutionFace):
    """`script` is a per-submission behaviour queue consumed in call order:
    "fill" (default when exhausted) · "partial:<fraction>" · "reject" ·
    "disconnect" (raises ConnectionError once — the orchestrator must
    reconcile; the submission did NOT reach the venue)."""

    def __init__(self, descriptor: CapabilityDescriptor | None = None, *,
                 fill_offset: float = 0.0, script: list[str] | None = None) -> None:
        self.name = "mock"
        self.descriptor = descriptor or CapabilityDescriptor(
            venue="mock",
            order_types=frozenset({"market", "limit", "stop"}),
            supports_ioc=True,
            account_model="netting",
            partial_close=True,
            min_lot=0.01,
            lot_step=0.01,
            max_order_lots=100.0,
            symbol_map={s: s for s in MOCK_SYMBOLS},
            quote_depth=True,
            asset_classes=frozenset({"fx"}),
            server_side_stops=True,
        )
        self._offset = fill_offset          # adverse price offset per fill
        self._script = list(script or [])
        self._by_fragment: dict[str, FillReport] = {}
        self._net: dict[str, Decimal] = {}
        self._stops: dict[str, float] = {}  # instrument -> stop RESTING at the venue
        self._unsolicited: asyncio.Queue[FillReport] = asyncio.Queue()
        self._deals = 0                     # venue-side deal counter (unsolicited ids)
        self.submissions = 0                # physical venue hits (idempotency proof)
        self._lock = asyncio.Lock()

    def _behaviour(self) -> str:
        return self._script.pop(0) if self._script else "fill"

    async def submit_order(self, *, fragment_id: str, order_id: str, instrument: str,
                           direction: int, units: Decimal, requested_price: float,
                           ioc: bool, now: datetime, session_id: str,
                           stop_loss: float | None = None) -> FillReport:
        if fragment_id in self._by_fragment:            # duplicate: same report,
            return self._by_fragment[fragment_id]       # no second venue hit
        if stop_loss is not None and not self.descriptor.server_side_stops:
            raise DataQualityError(                     # never accept unprotected
                "stop_loss", stop_loss,
                f"venue {self.name} does not hold server-side stops (§279)")
        return self._execute(self._behaviour(), fragment_id, order_id, instrument, direction,
                             units, requested_price, now, session_id, stop_loss)

    async def close_position(self, *, fragment_id: str, order_id: str, instrument: str,
                             direction: int, units: Decimal, requested_price: float,
                             now: datetime, session_id: str) -> FillReport:
        async with self._lock:                          # read-and-act as ONE step
            if fragment_id in self._by_fragment:
                return self._by_fragment[fragment_id]
            net = self._net.get(instrument, Decimal("0"))
            held = abs(net) if net * direction > 0 else Decimal("0")
            await asyncio.sleep(0)           # the venue's round-trip; the lock keeps it one step
            behaviour = self._behaviour() if held > 0 else "reject"   # nothing to close
            report = self._execute(behaviour, fragment_id, order_id, instrument, -direction,
                                   min(units, held) if held > 0 else units,
                                   requested_price, now, session_id, None)
            if held and held < units and report.filled_units > 0:
                report = replace(report, status=FillStatus.PARTIAL,
                                 remaining_units=units - report.filled_units)
                self._by_fragment[fragment_id] = report
            return report

    def _execute(self, behaviour: str, fragment_id: str, order_id: str, instrument: str,
                 direction: int, units: Decimal, requested_price: float, now: datetime,
                 session_id: str, stop_loss: float | None) -> FillReport:
        if behaviour == "disconnect":
            raise ConnectionError("mock venue: connection lost before submission")
        self.submissions += 1
        fill_price = requested_price + direction * self._offset
        if behaviour == "reject":
            report = FillReport(
                fill_id=f"{fragment_id}:r", order_id=order_id,
                fragment_id=fragment_id, instrument=instrument,
                direction=direction, requested_price=requested_price,
                fill_price=0.0, filled_units=Decimal("0"), slippage_bps=0.0,
                fill_time=now, venue=self.name, status=FillStatus.REJECTED,
                remaining_units=units, session_id=session_id)
        else:
            fraction = Decimal("1")
            if behaviour.startswith("partial:"):
                fraction = Decimal(behaviour.split(":", 1)[1])
            filled = (units * fraction).quantize(Decimal("0.01"))
            status = FillStatus.FILLED if filled == units else FillStatus.PARTIAL
            report = FillReport(
                fill_id=f"{fragment_id}:f", order_id=order_id,
                fragment_id=fragment_id, instrument=instrument,
                direction=direction, requested_price=requested_price,
                fill_price=fill_price, filled_units=filled,
                slippage_bps=slippage_bps(requested_price, fill_price, direction),
                fill_time=now, venue=self.name, status=status,
                remaining_units=units - filled, session_id=session_id)
            self._net[instrument] = (self._net.get(instrument, Decimal("0"))
                                     + direction * filled)
            if stop_loss is not None and filled > 0:    # rest the stop AT the venue,
                self._stops[instrument] = stop_loss     # atomically with the fill
            if self._net.get(instrument) == 0:          # flat again → stop retires
                self._stops.pop(instrument, None)
        self._by_fragment[fragment_id] = report
        return report

    def trigger_stop(self, instrument: str, price: float, now: datetime) -> FillReport:
        """The resting stop on `instrument` fires and closes the whole position at `price`."""
        if instrument not in self._stops:
            raise DataQualityError("instrument", instrument, "no stop is resting there")
        stop = self._stops.pop(instrument)
        net = self._net.pop(instrument)
        side = -1 if net > 0 else 1                     # the side traded to close
        self._deals += 1
        deal = f"venue:{self.name}:{self._deals}"
        report = FillReport(
            fill_id=deal, order_id=deal, fragment_id=deal, instrument=instrument,
            direction=side, requested_price=stop, fill_price=price,
            filled_units=abs(net), slippage_bps=slippage_bps(stop, price, side),
            fill_time=now, venue=self.name, status=FillStatus.FILLED,
            remaining_units=Decimal("0"), session_id="venue")
        self._unsolicited.put_nowait(report)
        return report

    async def venue_fills(self) -> AsyncIterator[FillReport]:
        while True:
            yield await self._unsolicited.get()

    async def cancel(self, fragment_id: str) -> bool:
        return fragment_id not in self._by_fragment

    async def open_positions(self) -> tuple[BrokerPosition, ...]:
        return tuple(
            BrokerPosition(instrument=inst, direction=1 if net > 0 else -1,
                           size_units=abs(net), stop_loss=self._stops.get(inst))
            for inst, net in sorted(self._net.items()) if net != 0)

    async def account_snapshot(self) -> BrokerAccount:
        return BrokerAccount(equity=Decimal("10000"), balance=Decimal("10000"),
                             margin_used=Decimal("0"))

    async def resting_stops(self) -> Mapping[str, float]:
        # a COPY of the venue-held stops — the caller sees broker state, never a
        # live handle into engine memory (§279).
        return dict(self._stops)
