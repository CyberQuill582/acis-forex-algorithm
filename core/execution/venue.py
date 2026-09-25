"""Execution faces, fill reporting, venue quality (ACIS-06 v1.1 §4/§5/§7.5).

The §7.5 execution-face contract lives here: `ExecutionFace` (ABC) + the
mandatory `CapabilityDescriptor` (data, never code). v1 ships the mock face
fully conformant; platform faces (OANDA/MT5, then the ratified adapter order)
attach at phase 12 via ACIS-13 behind this same contract. Account/position
state flows exclusively through this face DOWNWARD to the Risk Monitor
(GAP-0013: the feed face exposes none of it).
"""

from __future__ import annotations

import asyncio
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping

from core.data.errors import DataQualityError
from core.execution.fill_store import FillReportStore  # noqa: F401 (re-export)

UNITS_PER_LOT = Decimal("100000")


class FillStatus(Enum):
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class FillReport:
    """The layer's only output edge, to Risk (ACIS-06 §4 — locked shape).
    Every outcome (incl. partials and rejections) is a FillReport; a rejection
    is never a silent drop. Decimal quantities: the F17 accounting boundary."""

    fill_id: str
    order_id: str
    fragment_id: str
    instrument: str
    direction: int
    requested_price: float
    fill_price: float
    filled_units: Decimal
    slippage_bps: float
    fill_time: datetime
    venue: str
    status: FillStatus
    remaining_units: Decimal
    session_id: str

    def __post_init__(self) -> None:
        if self.direction not in (1, -1):
            raise DataQualityError("direction", self.direction, "must be +1 or -1")
        if not isinstance(self.filled_units, Decimal) or self.filled_units < 0:
            raise DataQualityError("filled_units", self.filled_units,
                                   "must be non-negative Decimal (F17)")
        if not isinstance(self.remaining_units, Decimal) or self.remaining_units < 0:
            raise DataQualityError("remaining_units", self.remaining_units,
                                   "must be non-negative Decimal (F17)")
        if not math.isfinite(self.requested_price) or self.requested_price <= 0:
            raise DataQualityError("requested_price", self.requested_price,
                                   "must be finite > 0")
        rejected = self.status in (FillStatus.REJECTED, FillStatus.CANCELLED)
        if not rejected and (not math.isfinite(self.fill_price) or self.fill_price <= 0):
            raise DataQualityError("fill_price", self.fill_price, "must be finite > 0")
        if not math.isfinite(self.slippage_bps):
            raise DataQualityError("slippage_bps", self.slippage_bps, "must be finite")
        if self.fill_time.tzinfo is None:
            raise DataQualityError("fill_time", self.fill_time, "must be tz-aware")
        if self.status is FillStatus.FILLED and self.remaining_units != 0:
            raise DataQualityError("remaining_units", self.remaining_units,
                                   "FILLED implies zero remaining")
        if rejected and self.filled_units != 0:
            raise DataQualityError("filled_units", self.filled_units,
                                   f"{self.status.value} implies zero filled")


def slippage_bps(requested: float, fill: float, direction: int) -> float:
    """ACIS-06 §4: (fill − requested)/requested × 1e4 × direction — positive
    is always ADVERSE (paid more buying / received less selling)."""
    return (fill - requested) / requested * 1e4 * direction


@dataclass(frozen=True)
class BrokerPosition:
    instrument: str
    direction: int
    size_units: Decimal
    # §279 broker-side stop: the protective stop RESTING AT THE VENUE for this
    # position (None = no server-side stop attached). Position risk is bounded
    # even if ACIS vanishes only when this is set; the conformance suite asserts
    # a live-attachable adapter actually rests it (phase-12 gate).
    stop_loss: float | None = None


@dataclass(frozen=True)
class BrokerAccount:
    equity: Decimal
    balance: Decimal
    margin_used: Decimal


@dataclass(frozen=True)
class CapabilityDescriptor:
    """§7.5: what the platform can actually do, declared as DATA. A SizedOrder
    needing an absent capability is rejected loudly at the boundary
    (EXEC_CAPABILITY_REJECT), never emulated silently."""

    venue: str
    order_types: frozenset[str]          # {"market", "limit", "stop"}
    supports_ioc: bool
    account_model: str                   # "netting" | "hedging"
    partial_close: bool
    min_lot: float
    lot_step: float
    max_order_lots: float
    symbol_map: Mapping[str, str]        # engine symbol -> venue symbol (§13 suffix law)
    quote_depth: bool
    asset_classes: frozenset[str]
    # §279 (master, "already law"): can the venue hold a protective stop-loss
    # ON ITS SERVER, so position risk is bounded even if ACIS/the VPS vanishes?
    # Declared DATA like every other capability. A venue that cannot is NOT
    # live-attachable — the phase-12 conformance gate asserts placement per
    # adapter (`test_server_side_stop_*`).
    server_side_stops: bool

    def __post_init__(self) -> None:
        if self.account_model not in ("netting", "hedging"):
            raise DataQualityError("account_model", self.account_model,
                                   "must be netting or hedging")
        if not (0 < self.lot_step <= self.min_lot):       # GAP-P12D-57: the step rounds
            raise DataQualityError("lot_step", (self.lot_step, self.min_lot),
                                   "0 < lot_step <= min_lot required")
        if not (0 < self.min_lot <= self.max_order_lots):
            raise DataQualityError("min_lot/max_order_lots",
                                   (self.min_lot, self.max_order_lots),
                                   "0 < min_lot <= max_order_lots required")
        if "market" not in self.order_types:
            raise DataQualityError("order_types", self.order_types,
                                   "a venue without market orders is not attachable")


class ExecutionFace(ABC):
    """§7.5 execution face. Async; idempotent by fragment_id. The shared
    platform session (transport+auth only, GAP-0013) is owned by the adapter
    package — never passed through core layers."""

    name: str
    descriptor: CapabilityDescriptor

    @abstractmethod
    async def submit_order(self, *, fragment_id: str, order_id: str, instrument: str,
                           direction: int, units: Decimal, requested_price: float,
                           ioc: bool, now: datetime, session_id: str,
                           stop_loss: float | None = None) -> FillReport:
        """`stop_loss`, when supplied, is placed as a protective stop RESTING AT
        THE VENUE (master §279) atomically with the fill — never emulated in the
        engine. A face whose descriptor declares `server_side_stops=False` must
        reject an order carrying a stop, never accept it unprotected."""
        ...

    @abstractmethod
    async def close_position(self, *, fragment_id: str, order_id: str, instrument: str,
                             direction: int, units: Decimal, requested_price: float,
                             now: datetime, session_id: str) -> FillReport:
        """REDUCE-ONLY, atomically (audit X3/F4): take up to `units` off the `direction`
        position; never open, add to or flip one (nothing held: REJECTED). Adapters map it
        to the venue's close: cTrader ClosePositionReq(positionId), OANDA REDUCE_ONLY, FIX
        PositionEffect=C. The report's `direction` is the side traded (the opposite)."""
        ...

    @abstractmethod
    async def cancel(self, fragment_id: str) -> bool: ...

    @abstractmethod
    async def open_positions(self) -> tuple[BrokerPosition, ...]: ...

    @abstractmethod
    async def account_snapshot(self) -> BrokerAccount: ...

    @abstractmethod
    async def resting_stops(self) -> Mapping[str, float]:
        """instrument -> stop price for every protective stop CURRENTLY RESTING
        AT THE VENUE. The conformance gate queries this to prove the stop lives
        on the broker's server (survives an engine/VPS death), not in engine
        memory (master §279)."""
        ...


class MockExecutionFace(ExecutionFace):
    """Deterministic paper venue (v1 conformant adapter, ACIS-06 §7.5).

    `script` is a per-submission behaviour queue consumed in call order:
    "fill" (default when exhausted) · "partial:<fraction>" · "reject" ·
    "disconnect" (raises ConnectionError once — the orchestrator must
    reconcile; the submission did NOT reach the venue). Duplicate submits of a
    fragment_id return the ORIGINAL FillReport (idempotency, C-EXE-4/5)."""

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
            symbol_map={"EUR_USD": "EUR_USD", "USD_JPY": "USD_JPY"},
            quote_depth=True,
            asset_classes=frozenset({"fx"}),
            server_side_stops=True,
        )
        self._offset = fill_offset          # adverse price offset per fill
        self._script = list(script or [])
        self._by_fragment: dict[str, FillReport] = {}
        self._net: dict[str, Decimal] = {}
        self._stops: dict[str, float] = {}  # instrument -> stop RESTING at the venue
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
