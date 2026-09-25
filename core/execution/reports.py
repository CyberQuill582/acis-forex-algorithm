"""Every execution outcome becomes a recorded FillReport (ACIS-06 §4). Moved out of
orchestrator.py (legibility budget, GAP-P12M-01). Invariants:
  * A boundary refusal (no capable venue, lot step, minimum lot, request budget,
    reduce-only, pair group) is a REJECTED FillReport — never a silent drop — whose
    `remaining_units` is what went unsent, on the side the engine would have traded.
  * Every report updates venue quality, is written to the fill log and is logged; a fill
    worse than the slippage alert level raises SLIPPAGE_ALERT and nothing more (F10).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from core.execution.venue import FillReport, FillReportStore, FillStatus
from core.execution.venue_quality import VenueQuality
from core.governor.portfolio_types import SizedOrder

_EVENT = {FillStatus.FILLED: "FILL", FillStatus.PARTIAL: "PARTIAL",
          FillStatus.REJECTED: "REJECT", FillStatus.CANCELLED: "CANCEL"}


class ReportBook:
    def __init__(self, quality: VenueQuality, store: FillReportStore, logger,
                 alert_bps: float, session_id: str, now_fn: Callable) -> None:
        self._quality = quality
        self._store = store
        self._log = logger
        self._alert_bps = alert_bps
        self._session = session_id
        self._now = now_fn

    def record(self, report: FillReport) -> None:
        self._quality.update(report)
        self._store.write(report)
        self._log.event(_EVENT[report.status], fill_id=report.fill_id,
                        order_id=report.order_id, fragment_id=report.fragment_id,
                        venue=report.venue, filled_units=str(report.filled_units),
                        fill_px=report.fill_price, slippage_bps=round(report.slippage_bps, 4),
                        remaining=str(report.remaining_units))
        if (report.status in (FillStatus.FILLED, FillStatus.PARTIAL)
                and report.slippage_bps > self._alert_bps):
            self._log.event("SLIPPAGE_ALERT", fill_id=report.fill_id,
                            instrument=report.instrument,
                            slippage_bps=round(report.slippage_bps, 4),
                            alert_bps=self._alert_bps)

    def reject(self, order: SizedOrder, side: int, *, fragment_id: str = "",
               venue: str = "none", units: Decimal | None = None) -> FillReport:
        """A boundary refusal as a REJECTED report; `units` is what went unsent
        (default: the whole order)."""
        return FillReport(
            fill_id=f"{order.order_id}:{fragment_id or 'cap'}:rej",
            order_id=order.order_id, fragment_id=fragment_id or "none",
            instrument=order.instrument, direction=side,
            requested_price=order.entry_price, fill_price=0.0,
            filled_units=Decimal("0"), slippage_bps=0.0, fill_time=self._now(),
            venue=venue, status=FillStatus.REJECTED,
            remaining_units=order.size_units if units is None else units,
            session_id=self._session)
