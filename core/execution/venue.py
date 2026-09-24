"""Execution faces, fill reporting, venue quality (ACIS-06 v1.1 §4/§5/§7.5).

The §7.5 execution-face contract lives here: `ExecutionFace` (ABC) + the
mandatory `CapabilityDescriptor` (data, never code). v1 ships the mock face
fully conformant; platform faces (OANDA/MT5, then the ratified adapter order)
attach at phase 12 via ACIS-13 behind this same contract. Account/position
state flows exclusively through this face DOWNWARD to the Risk Monitor
(GAP-0013: the feed face exposes none of it).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
        behaviour = self._behaviour()
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


class AttachHalt(Exception):
    """GAP-0018 flat-or-decide: the account holds open positions at attach —
    a HUMAN must decide (flatten via platform, or manage manually until flat).
    Never caught-and-continued by any agent path."""

    def __init__(self, positions: tuple[BrokerPosition, ...]) -> None:
        self.positions = positions
        super().__init__(
            f"attach halted: {len(positions)} open position(s) on the account — "
            "human decision required (flatten first, or manage manually until flat)")


async def verify_attach(face: ExecutionFace, enabled_symbols: set[str],
                        logger) -> None:
    """§7.5 attach protocol, the phase-8 contract half: (1) the capability
    descriptor's symbol map must cover the enabled universe (the §13 suffix
    problem dies here, once); (2) flat-or-decide (GAP-0018). Rulebook loading
    is the §9.5 config layer's job and precedes this call; paper-always mode
    start follows it."""
    missing = enabled_symbols - set(face.descriptor.symbol_map)
    if missing:
        raise DataQualityError("symbol_map", sorted(missing),
                               "descriptor must map every enabled instrument")
    positions = await face.open_positions()
    if positions:
        logger.event("ATTACH_HALTED_OPEN_POSITIONS", venue=face.name,
                     count=len(positions))
        raise AttachHalt(positions)
    logger.event("ATTACH_VERIFIED", venue=face.name,
                 symbols=sorted(enabled_symbols))


class VenueQuality:
    """Per-(venue, instrument) rolling execution quality (ACIS-06 §5). Fed by
    this layer's own FillReports — internal feedback, never upstream. Score is
    deterministic and monotone: higher fill rate raises it, adverse slippage
    and rejects lower it."""

    def __init__(self, window: int = 50) -> None:
        self._window = window
        self._records: dict[tuple[str, str], list[tuple[bool, float]]] = {}

    def update(self, report: FillReport) -> None:
        key = (report.venue, report.instrument)
        rows = self._records.setdefault(key, [])
        rejected = report.status in (FillStatus.REJECTED, FillStatus.CANCELLED)
        rows.append((not rejected, 0.0 if rejected else report.slippage_bps))
        if len(rows) > self._window:
            del rows[0]

    def score(self, venue: str, instrument: str) -> float:
        rows = self._records.get((venue, instrument))
        if not rows:
            return 0.5                       # unknown venue: neutral prior
        fill_rate = sum(1 for ok, _ in rows if ok) / len(rows)
        fills = [s for ok, s in rows if ok]
        avg_adverse = max(0.0, sum(fills) / len(fills)) if fills else 0.0
        return fill_rate / (1.0 + avg_adverse / 10.0)
