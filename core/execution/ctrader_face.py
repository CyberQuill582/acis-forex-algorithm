"""CTraderExecutionFace — the cTrader execution face (ACIS-06 §7.5, ACIS-13 §7.3–§7.5, §7.7).

Invariants:
  * Idempotent by fragment id (C-EXE-4/5, C-VEN-1): a fragment is recorded SENT before it leaves;
    an unknown outcome is SEARCHED for (an open by `clientOrderId`, a close as the market closing
    order on its recorded position) and resent only when the venue has no trace of it.
  * An open carries a relative stop, is refused without one, and its fill is proven to hold a stop
    at the venue, or the stop is repaired, or the position is closed (C-VEN-2). One ACIS position
    per instrument: fragments of one order may add to it, nothing opens against it (C-VEN-9).
  * A close is reduce-only and atomic at the venue (C-EXE-7): one `ProtoOAClosePositionReq` per
    venue position, oldest first, never more than held, never a hedge.
  * Every refusal that never contacted the venue is a REJECTED report, logged; nothing is dropped.
  * Fills the venue makes on its own reach `venue_fills()` (ACIS-06 v1.4) through the router.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator, Callable, Mapping

from core.data.ctrader.link import LinkState
from core.data.ctrader.meter import BudgetRefused
from core.data.ctrader.schema import (PT, OrderStatus, OrderType, TimeInForce, TradingMode,
                                      enum_value)
from core.data.ctrader.wire import VenueError
from core.data.errors import DataQualityError
from core.execution import ctrader_sync as sync
from core.execution.ctrader_close import CloseMixin, _acked, _Order
from core.execution.ctrader_account import snapshot
from core.execution.ctrader_events import EventRouter, Tracker
from core.execution.ctrader_orders import (broker_positions, direction_of, fill_report, label, venue_costs,
                                           protocol_volume, quantize, relative_stop, side)
from core.execution.ctrader_store import VenueStore
from core.execution.ctrader_symbols import VenueSymbolSpec
from core.execution.venue import (BrokerAccount, BrokerPosition, CapabilityDescriptor,
                                  ExecutionFace, FillReport)

WINDOW = timedelta(hours=24)




class CTraderExecutionFace(CloseMixin, ExecutionFace):
    name = "ctrader"

    def __init__(self, session, specs: Mapping[str, VenueSymbolSpec],
                 descriptor: CapabilityDescriptor, store: VenueStore, logger, *,
                 account_key: str, now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 order_ack_timeout_s: float = 10.0, stop_confirm_timeout_s: float = 3.0,
                 max_orders_per_day: int = 35,
                 spread_of: Callable[[str], Decimal | None] | None = None) -> None:
        self.descriptor = descriptor
        self._s, self._store, self._log, self._now = session, store, logger, now_fn
        self._specs = dict(specs)
        self._label = label(account_key)
        self._key = account_key
        self._ack, self._stop_wait, self._max_opens = order_ack_timeout_s, stop_confirm_timeout_s, max_orders_per_day
        self._spread_of = spread_of              # the feed's live spread (D3); None: offline tests only
        self.router = EventRouter(account_key=account_key, own_label=self._label, logger=logger,
                                  instruments={spec.symbol_id: n for n, spec in self._specs.items()})
        self.router.acis_positions = store.ours()[1]
        self._reports: dict[str, FillReport] = {}
        self._trackers: dict[str, Tracker] = {}
        self._opens: deque[datetime] = deque()
        self._costed: set[int] = set()              # deals whose VENUE_COSTS is logged (once each)

    def start(self) -> asyncio.Task:
        """Begin consuming the session's execution events."""
        return asyncio.create_task(self._consume())

    async def synchronise(self) -> tuple[tuple[BrokerPosition, ...], tuple]:
        """SYNCING (§7.8): our own orders, then missed deals, then venue truth; READY after."""
        return await sync.synchronise(self._s, self._store, self.router, account_key=self._key,
                                      own_label=self._label, now=self._now(), log=self._log)

    async def _consume(self) -> None:
        while True:
            frame = await self._s.events.get()
            try:
                self.router.route(frame)
            except (DataQualityError, KeyError, TypeError, ValueError) as exc:   # TAE-08: an enum the
                # pinned proto lacks, or a malformed event: logged critical, and the consumer lives on
                self._log.event("VENUE_EVENT_UNROUTABLE", severity="critical",
                                payload_type=int(frame.payload_type), reason=repr(exc)[:200])

    # -- opens ----------------------------------------------------------------------------- #

    async def submit_order(self, *, fragment_id: str, order_id: str, instrument: str,
                           direction: int, units: Decimal, requested_price: float,
                           ioc: bool, now: datetime, session_id: str,
                           stop_loss: float | None = None) -> FillReport:
        if fragment_id in self._reports:
            return self._reports[fragment_id]
        if len(fragment_id) > 50:
            raise DataQualityError("fragment_id", fragment_id, "clientOrderId is at most 50 chars (F-13)")
        o = _Order(fragment_id, order_id, instrument, direction, units, requested_price, session_id)
        known = self._store.lookup(fragment_id)
        if known is not None and known[0] != "NOT_SENT":
            return await self._recover_open(o, known, stop_loss, now)
        return await self._send_open(o, stop_loss, now)

    async def _send_open(self, o: _Order, stop_loss, now: datetime) -> FillReport:
        spec = self._specs.get(o.instrument)
        spread = self._spread(o.instrument)
        reason = self._refuse_open(spec, o, stop_loss, now) or (None if spread is not None else "VENUE_NO_QUOTE")
        rel = None if reason else relative_stop(spec, o.requested_price, stop_loss, o.direction, spread)
        if reason is None and rel is None:
            reason = "VENUE_STOP_TOO_CLOSE"
        if reason is not None:
            return self._refused(reason, o, now)
        tracker = self._trackers[o.fragment_id] = self.router.open_tracker(o.fragment_id)
        self._store.sent(o.fragment_id, o.order_id, now)
        body = {"symbolId": spec.symbol_id, "orderType": int(OrderType.MARKET),
                "tradeSide": side(o.direction), "volume": protocol_volume(o.units),
                "timeInForce": int(TimeInForce.IMMEDIATE_OR_CANCEL), "relativeStopLoss": rel,
                "clientOrderId": o.fragment_id, "label": self._label, "comment": o.order_id}
        try:
            frame = await self._s.request(PT.NEW_ORDER_REQ, body, req_class="open")
        except BudgetRefused as exc:
            self._store.not_sent(o.fragment_id, now)
            self._forget(o.fragment_id)
            return self._refused(exc.reason, o, now)
        except VenueError as exc:
            self._store.terminal(o.fragment_id, None, None, now)
            self._forget(o.fragment_id)
            return self._refused(exc.code, o, now)
        except asyncio.TimeoutError:                   # §7.3 step 6: unknown, kept, searched on retry
            raise ConnectionError("the open's reply timed out; it is searched, never resent") from None
        self.router.route(frame, reply_to=tracker)
        self._opens.append(now)
        await _acked(tracker, self._ack)
        report = self._finish(tracker.deals.values(), tracker.venue_order_id, tracker.position_id,
                              tracker.outcome == "cancelled", o)
        await self._protect(report, tracker.position_id, spec, rel)
        return report

    async def _recover_open(self, o: _Order, known, stop_loss, now: datetime) -> FillReport:
        _, venue_order_id, sent = known
        tracker = self._trackers.get(o.fragment_id)
        if tracker is not None and tracker.done.done():
            position_id = tracker.position_id
            report = self._finish(tracker.deals.values(), tracker.venue_order_id,
                                  position_id, tracker.outcome == "cancelled", o)
        else:
            if venue_order_id is None:
                found = await sync.find_order(self._s, lambda x: x.get("clientOrderId") == o.fragment_id,
                                              since=sent, now=self._now())
                if found is None:                   # it never reached the venue: only now resend
                    self._store.not_sent(o.fragment_id, now)
                    self._forget(o.fragment_id)
                    return await self._send_open(o, stop_loss, now)
                venue_order_id = int(found["orderId"])
            order, deals = await sync.order_deals(self._s, venue_order_id)
            self.router.mark_seen(deals)
            cancelled = enum_value(OrderStatus, order["orderStatus"]) is not OrderStatus.ORDER_STATUS_REJECTED
            position_id = order.get("positionId")
            report = self._finish(deals, venue_order_id, position_id, cancelled, o)
        spec = self._specs[o.instrument]
        await self._protect(report, position_id, spec, relative_stop(
            spec, o.requested_price, stop_loss, o.direction, self._spread(o.instrument) or Decimal(0)))
        return report

    def _spread(self, instrument: str) -> Decimal | None:
        return Decimal(0) if self._spread_of is None else self._spread_of(instrument)

    async def _protect(self, report: FillReport, position_id, spec, rel) -> None:
        if report.filled_units <= 0 or position_id is None or rel is None:
            return
        await sync.ensure_stop(self._s, self.router.stops, int(position_id), fill=report.fill_price,
                               distance=Decimal(rel) / 100_000, direction=report.direction,
                               digits=spec.digits, wait_s=self._stop_wait, log=self._log)

    def _refuse_open(self, spec, o: _Order, stop_loss, now: datetime) -> str | None:
        if self._s.state is not LinkState.READY:        # §8.1: no dispatch outside READY (TAI-12)
            return "VENUE_NOT_READY"
        if spec is None:
            return "VENUE_SYMBOL_UNMAPPED"
        if spec.trading_mode is not TradingMode.ENABLED:
            return "VENUE_CLOSE_ONLY"
        if o.units <= 0 or quantize(spec, o.units) != o.units:
            return "VENUE_VOLUME_INVALID"
        if stop_loss is None:
            self._log.event("VENUE_UNPROTECTED_OPEN_REFUSED", order_id=o.order_id)
            return "VENUE_UNPROTECTED_OPEN_REFUSED"
        if not spec.is_open(now):
            return "MARKET_CLOSED_PRECHECK"
        held = [p["tradeData"] for p in self.router.positions.values()
                if p["tradeData"].get("label") == self._label
                and int(p["tradeData"]["symbolId"]) == spec.symbol_id]
        if held and any(direction_of(t["tradeSide"]) != o.direction or t.get("comment") != o.order_id
                        for t in held):
            return "VENUE_ONE_POSITION_PER_INSTRUMENT"
        while self._opens and self._opens[0] <= now - WINDOW:
            self._opens.popleft()
        return "VENUE_ORDER_ALLOWANCE_SPENT" if len(self._opens) >= self._max_opens else None

    # -- the rest of the face ------------------------------------------------------------- #

    async def cancel(self, fragment_id: str) -> bool:
        """Market IOC orders never rest at the venue, so a fragment with no fill is 'guaranteed
        unfilled' (ACIS-06) and a filled one cannot be cancelled."""
        report = self._reports.get(fragment_id)
        return report is None or report.filled_units == 0

    async def open_positions(self) -> tuple[BrokerPosition, ...]:
        # "protect": ACIS-06's reduce-only pre-check reads it before every close, and the close reserve
        # is kept for exactly those (§6.5, GAP-P12D-132 TAI-01); the runtime's periodic reconcile skips
        # the reserve itself
        positions, _ = await sync.reconcile(self._s, req_class="protect")
        self.router.seed(positions)
        return broker_positions(positions, self.router.instruments, self._label)[0]

    async def resting_stops(self) -> Mapping[str, float]:
        return {p.instrument: p.stop_loss for p in await self.open_positions() if p.stop_loss is not None}

    async def account_snapshot(self) -> BrokerAccount:
        return await snapshot(self._s, self.router.positions.values())

    async def venue_fills(self) -> AsyncIterator[FillReport]:
        while True:
            yield await self.router.unsolicited.get()

    # -- helpers --------------------------------------------------------------------------- #

    def _finish(self, deals, venue_order_id, position_id, cancelled: bool, o: _Order, *,
                fill_id: str | None = None) -> FillReport:
        report = fill_report(deals, fill_id=fill_id or f"ct:{self._key}:{venue_order_id}",
                             order_id=o.order_id, fragment_id=o.fragment_id, instrument=o.instrument,
                             direction=o.direction, requested_units=o.units,
                             requested_price=o.requested_price, session_id=o.session_id,
                             now=self._now(), cancelled=cancelled)
        for deal in deals:                          # ACIS-13 §7.3 step 7: each deal's costs, once
            if int(deal["dealId"]) not in self._costed:
                self._costed.add(int(deal["dealId"]))
                self._log.event("VENUE_COSTS", **venue_costs(deal))
        if fill_id is None:
            self._store.terminal(o.fragment_id, venue_order_id, position_id, self._now())
            if position_id is not None:
                self.router.acis_positions.add(int(position_id))
            self._forget(o.fragment_id)
        self._reports[o.fragment_id] = report
        return report

    def _forget(self, fragment_id: str) -> None:
        tracker = self._trackers.pop(fragment_id, None)
        if tracker is not None:
            self.router.release(tracker)

    def _refused(self, reason: str, o: _Order, now: datetime) -> FillReport:
        self._log.event("VENUE_REFUSED", reason=reason, fragment_id=o.fragment_id, order_id=o.order_id)
        report = fill_report((), fill_id=f"ct:{self._key}:refused:{o.fragment_id}", order_id=o.order_id,
                             fragment_id=o.fragment_id, instrument=o.instrument, direction=o.direction,
                             requested_units=o.units, requested_price=o.requested_price,
                             session_id=o.session_id, now=now, cancelled=False)
        self._reports[o.fragment_id] = report
        return report
