"""Routing the venue's execution events (ACIS-13 §4.2, §7.3 step 6, §7.7): each event goes to the
ACIS order waiting for it, or — a deal nobody asked for on an ACIS position — becomes an unsolicited
FillReport (ACIS-06 v1.4). Pure state over events; no I/O.

Invariants:
  * An open is matched by `clientOrderId` (= its fragment id); a close, whose request carries no
    such id, by its position, registered BEFORE the request leaves — so its fill can never arrive
    first and be mistaken for a stop hit. A close is a MARKET closing order; a stop firing is not.
  * Deals are counted once each, by `dealId`: a repeated event never double-fills.
  * A deal on an ACIS-labelled position that no waiting order claims is unsolicited: a server-side
    stop, a stop-out or a manual close. Its report's requested price is the stop the venue held,
    so the slippage is the measured gap through it. A deal on a foreign position is logged, never
    adopted (drift surfaces at reconciliation).
  * Venue text is data: routing keys only on payload types, ids and enumerated values (C-VEN-15).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Mapping

from core.data.ctrader.schema import PT, ExecutionType, OrderType, PositionStatus, enum_value
from core.data.ctrader.wire import Frame
from core.execution.ctrader_orders import unsolicited_report, venue_costs

FINISH = {ExecutionType.ORDER_FILLED: "filled", ExecutionType.ORDER_CANCELLED: "cancelled",
          ExecutionType.ORDER_EXPIRED: "cancelled", ExecutionType.ORDER_REJECTED: "rejected"}
DEALT = frozenset({ExecutionType.ORDER_FILLED, ExecutionType.ORDER_PARTIAL_FILL})


@dataclass
class Tracker:
    """One ACIS order in flight; `done` resolves with its outcome."""
    fragment_id: str
    done: asyncio.Future
    venue_order_id: int | None = None
    position_id: int | None = None
    outcome: str | None = None                      # "filled" | "cancelled" | "rejected"
    error_code: str | None = None
    deals: dict[int, Mapping] = field(default_factory=dict)

    def feed(self, frame: Frame) -> None:
        p = frame.payload
        if frame.payload_type == PT.ORDER_ERROR_EVENT:
            self._finish("rejected", str(p.get("errorCode", "ORDER_ERROR")))
            return
        order = p.get("order") or {}
        if "orderId" in order:
            self.venue_order_id = int(order["orderId"])
        position = p.get("position") or {}
        if "positionId" in position or "positionId" in order:
            self.position_id = int(position.get("positionId", order.get("positionId")))
        deal = p.get("deal")
        if deal is not None:
            self.deals[int(deal["dealId"])] = deal
        kind = enum_value(ExecutionType, p["executionType"])
        if kind in FINISH:
            self._finish(FINISH[kind], p.get("errorCode"))

    def _finish(self, outcome: str, error_code) -> None:
        self.outcome = outcome
        self.error_code = None if error_code is None else str(error_code)
        if not self.done.done():
            self.done.set_result(outcome)


class EventRouter:
    def __init__(self, *, account_key: str, own_label: str, instruments: Mapping[int, str],
                 logger) -> None:
        self._key = account_key
        self._label = own_label
        self.instruments = dict(instruments)         # symbolId -> engine instrument
        self._log = logger
        self._by_client: dict[str, Tracker] = {}
        self._by_position: dict[int, Tracker] = {}
        self._by_order: dict[int, Tracker] = {}
        self._seen_deals: set[int] = set()
        self.stops: dict[int, float] = {}            # positionId -> the stop the venue holds
        self.positions: dict[int, Mapping] = {}      # positionId -> the venue's open position
        self.trader: Mapping | None = None           # the event-sourced trader (balance) view
        self.acis_positions: set[int] = set()       # venue position ids ACIS opened (from the store)
        self.unsolicited: asyncio.Queue = asyncio.Queue()

    def open_tracker(self, fragment_id: str) -> Tracker:
        tracker = Tracker(fragment_id, asyncio.get_running_loop().create_future())
        self._by_client[fragment_id] = tracker
        return tracker

    def close_tracker(self, fragment_id: str, position_id: int) -> Tracker:
        tracker = Tracker(fragment_id, asyncio.get_running_loop().create_future(),
                          position_id=position_id)
        self._by_position[position_id] = tracker
        return tracker

    def release(self, tracker: Tracker) -> None:
        self._by_client.pop(tracker.fragment_id, None)
        self._by_order.pop(tracker.venue_order_id, None)
        if tracker.position_id is not None and self._by_position.get(tracker.position_id) is tracker:
            del self._by_position[tracker.position_id]
        self._seen_deals.update(tracker.deals)

    def route(self, frame: Frame, *, reply_to: Tracker | None = None) -> None:
        """`reply_to`: the frame is the venue's REPLY to that tracker's request (correlated by
        `clientMsgId`), so it is that order's whatever it names."""
        p = frame.payload
        if frame.payload_type == PT.TRADER_UPDATE_EVENT:
            self.trader = p.get("trader")
            return
        if frame.payload_type not in (PT.EXECUTION_EVENT, PT.ORDER_ERROR_EVENT):
            return
        position = p.get("position") or {}
        self.observe(position)
        tracker = reply_to or self._claim(frame)
        if tracker is not None:
            tracker.feed(frame)
            if tracker.venue_order_id is not None:
                self._by_order[tracker.venue_order_id] = tracker
            return
        if frame.payload_type != PT.EXECUTION_EVENT or enum_value(ExecutionType, p["executionType"]) not in DEALT:
            return
        deal = p.get("deal")
        if deal is not None:
            ours = (position.get("tradeData") or {}).get("label") == self._label
            self.ingest(deal, ours=ours or int(deal["positionId"]) in self.acis_positions)

    def observe(self, position: Mapping) -> None:
        """Keep the event-sourced position view (§7.5): open positions by id, their stops."""
        if "positionId" not in position:
            return
        pid = int(position["positionId"])
        if position.get("stopLoss") is not None:
            self.stops[pid] = float(position["stopLoss"])
        status = enum_value(PositionStatus, position.get("positionStatus", 1))
        if status is PositionStatus.POSITION_STATUS_OPEN and int(position["tradeData"]["volume"]) > 0:
            self.positions[pid] = position
        else:
            self.positions.pop(pid, None)

    def seed(self, positions: list[Mapping]) -> None:
        """Replace the view with a fresh reconcile (venue truth wins)."""
        self.positions = {}
        for position in positions:
            self.observe(position)

    def mark_seen(self, deals) -> None:
        """Deals of ACIS's own orders, found by search: never reported as unsolicited."""
        self._seen_deals.update(int(d["dealId"]) for d in deals)

    def ingest(self, deal: Mapping, *, ours: bool) -> None:
        """A deal no ACIS order claims: unsolicited if it is on an ACIS position (§7.7)."""
        deal_id = int(deal["dealId"])
        if deal_id in self._seen_deals:
            return
        self._seen_deals.add(deal_id)
        instrument = self.instruments.get(int(deal["symbolId"]))
        if not ours or instrument is None:
            self._log.event("VENUE_FOREIGN_EXECUTION", deal_id=deal_id)
            return
        pid = int(deal["positionId"])
        report = unsolicited_report(deal, account_key=self._key, instrument=instrument,
                                    stop_price=self.stops.get(pid))
        self._log.event("VENUE_UNSOLICITED_FILL", deal_id=deal_id, position_id=pid,
                        fill_px=report.fill_price, stop_px=report.requested_price)
        self._log.event("VENUE_COSTS", **venue_costs(deal))
        self.unsolicited.put_nowait(report)

    def _claim(self, frame: Frame) -> Tracker | None:
        p = frame.payload
        order = p.get("order") or {}
        tracker = (self._by_client.get(order.get("clientOrderId"))
                   or self._by_order.get(int(order.get("orderId", p.get("orderId", -1)))))
        if tracker is not None:
            return tracker
        if frame.payload_type == PT.ORDER_ERROR_EVENT:
            pid = p.get("positionId")
        elif order.get("closingOrder") and enum_value(OrderType, order.get("orderType", 1)) is OrderType.MARKET:
            pid = order.get("positionId", (p.get("position") or {}).get("positionId"))
        else:
            return None
        return None if pid is None else self._by_position.get(int(pid))
