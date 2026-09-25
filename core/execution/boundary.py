"""The venue-boundary checks each dispatch attempt runs, as REJECTED reports (ACIS-06 §4,
master §7.5). Moved out of orchestrator.py (legibility budget, GAP-P12M-01). Invariants:
  * Quantity (GAP-P12D-57): `units` go out rounded DOWN to the venue's lot step, never
    up; below the venue's minimum lot nothing goes out. What is not sent is reported.
  * Reduce-only (the close convention): a close names its position's side and may trade
    at most what THIS venue holds on that side — capped at it, refused without it. It is
    the engine's second line; the venue's own atomic close is the first (`close_position`).
"""

from __future__ import annotations

from decimal import Decimal

from core.execution.reports import ReportBook
from core.execution.venue import ExecutionFace, FillReport
from core.execution.venue_limits import reducible, venue_quantity
from core.governor.portfolio_types import SizedOrder


def side(order: SizedOrder) -> int:
    """The side traded: a close names its position's side and trades the opposite."""
    return -order.direction if order.action == "close" else order.direction


def _refuse(reports: ReportBook, order: SizedOrder, units: Decimal,
            fragment_id: str) -> list[FillReport]:
    report = reports.reject(order, side(order), units=units, fragment_id=fragment_id)
    reports.record(report)
    return [report]


def quantity_at(face: ExecutionFace, venue: str, order: SizedOrder, units: Decimal,
                tag: str, reports: ReportBook, log) -> tuple[Decimal, list[FillReport]]:
    sendable, rest = venue_quantity(units, face.descriptor)
    if rest == 0:
        return sendable, []
    kind = "EXEC_MIN_LOT_REFUSED" if sendable == 0 else "EXEC_LOT_STEP_ROUNDED"
    log.event(kind, order_id=order.order_id, venue=venue, action=order.action,
              units=str(units), sent=str(sendable), unsent=str(rest))
    return sendable, _refuse(reports, order, rest,
                             f"{tag}:{'minlot' if sendable == 0 else 'step'}")


async def reduce_only_at(face: ExecutionFace, venue: str, order: SizedOrder, units: Decimal,
                         tag: str, reports: ReportBook, log) -> tuple[Decimal, list[FillReport]]:
    held = reducible(await face.open_positions(), order)
    if held >= units:
        return units, []
    kind = "EXEC_CLOSE_REFUSED" if held == 0 else "EXEC_CLOSE_CAPPED"
    log.event(kind, order_id=order.order_id, venue=venue, units=str(units), held=str(held))
    return held, _refuse(reports, order, units - held, f"{tag}:reduce")
