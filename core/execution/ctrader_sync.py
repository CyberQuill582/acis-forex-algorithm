"""Venue truth for the cTrader face (ACIS-13 §7.3 step 6, §7.5, §7.8): reconcile, search an order
that may or may not have reached the venue, read an order's deals, page the deals missed while
down, and prove a position's stop is resting at the venue.

Invariants:
  * Venue truth before any resend (C-VEN-1): an order whose outcome is unknown is SEARCHED for;
    if the search cannot finish, the caller learns "unknown" and nothing is resent.
  * A position ACIS opened holds a stop on its protective side at the venue, or it is repaired, or
    it is closed (C-VEN-2). ACIS never holds an unprotected position.
  * Restart order (a correction of ACIS-13 §7.8, GAP-P12D-126): fragments in flight at the crash
    are resolved FIRST, so their venue orders are known; only then are missed deals ingested,
    skipping every deal of an ACIS order. Deals-first would report a crashed open's fill twice.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Mapping

from core.data.ctrader.schema import PT, OrderType, enum_value

SEARCH_SLACK = timedelta(seconds=60)
MAX_PAGES = 10


class SearchIncomplete(ConnectionError):
    """The venue could not be searched to the end: the outcome stays unknown, nothing is resent."""


def ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


async def reconcile(session, *, req_class: str) -> tuple[list[Mapping], list[Mapping]]:
    res = await session.request(PT.RECONCILE_REQ, {"returnProtectionOrders": False},
                                req_class=req_class)
    return list(res.payload.get("position", ())), list(res.payload.get("order", ()))


async def find_order(session, match: Callable[[Mapping], bool], *, since: datetime,
                     now: datetime) -> Mapping | None:
    """The one order in [since − 60 s, now] that `match` accepts, newest pages first."""
    to_ms = ms(now)
    for _ in range(MAX_PAGES):
        res = await session.request(PT.ORDER_LIST_REQ, {"fromTimestamp": ms(since - SEARCH_SLACK),
                                                        "toTimestamp": to_ms}, req_class="query")
        orders = list(res.payload.get("order", ()))
        hits = [o for o in orders if match(o)]
        if hits:
            return hits[0]
        if not res.payload.get("hasMore") or not orders:
            return None
        to_ms = min(int(o.get("utcLastUpdateTimestamp", to_ms)) for o in orders) - 1
    raise SearchIncomplete("the order search did not finish; the outcome stays unknown")


async def order_deals(session, venue_order_id: int, *, req_class: str = "query") -> tuple[Mapping, list[Mapping]]:
    res = await session.request(PT.ORDER_DETAILS_REQ, {"orderId": venue_order_id},
                                req_class=req_class)
    return res.payload["order"], list(res.payload.get("deal", ()))


async def missed_deals(session, since_ms: int, now: datetime) -> list[Mapping]:
    """Every deal executed in (since_ms, now], oldest first, paging on `hasMore` (F-19)."""
    out, cursor = [], since_ms + 1
    for _ in range(MAX_PAGES * 10):
        res = await session.request(PT.DEAL_LIST_REQ, {"fromTimestamp": cursor,
                                                       "toTimestamp": ms(now)}, req_class="protect")
        deals = sorted(res.payload.get("deal", ()), key=lambda d: int(d["executionTimestamp"]))
        out.extend(deals)
        if not res.payload.get("hasMore") or not deals:
            return out
        cursor = int(deals[-1]["executionTimestamp"]) + 1
    raise SearchIncomplete("the deal history did not finish paging")


def _protective(stop, fill: float, direction: int) -> bool:
    return stop is not None and (float(stop) - fill) * direction < 0


async def ensure_stop(session, stops: Mapping[int, float], position_id: int, *, fill: float,
                      distance: Decimal, direction: int, digits: int, wait_s: float,
                      log) -> bool:
    """C-VEN-2 after an open fills: the venue's stop is verified, else amended, else the position is
    closed. True when a stop rests at the venue; False when the position had to be closed."""
    if _protective(stops.get(position_id), fill, direction):
        return True
    await asyncio.sleep(wait_s)
    positions, _ = await reconcile(session, req_class="protect")
    held = next((p for p in positions if int(p["positionId"]) == position_id), None)
    if held is None:
        return True                                   # already closed (a stop fired): nothing to protect
    if _protective(held.get("stopLoss"), fill, direction):
        return True
    target = round(fill - direction * float(distance), digits)
    await session.request(PT.AMEND_POSITION_SLTP_REQ, {"positionId": position_id, "stopLoss": target},
                          req_class="protect")
    log.event("VENUE_STOP_AMENDED", position_id=position_id, stop=target)
    positions, _ = await reconcile(session, req_class="protect")
    held = next((p for p in positions if int(p["positionId"]) == position_id), None)
    if held is None or _protective(held.get("stopLoss"), fill, direction):
        return True
    await session.request(PT.CLOSE_POSITION_REQ, {"positionId": position_id,
                                                  "volume": int(held["tradeData"]["volume"])},
                          req_class="close")
    log.event("VENUE_STOP_MISSING", position_id=position_id, severity="critical")
    return False


def is_close_of(order: Mapping, position_id: int) -> bool:
    """A MARKET closing order on this position: what a `ProtoOAClosePositionReq` creates."""
    return (bool(order.get("closingOrder")) and int(order.get("positionId", -1)) == position_id
            and enum_value(OrderType, order["orderType"]) is OrderType.MARKET)


async def resume_close(session, store, router, trackers, fragment_id: str, now: datetime, *,
                       forget) -> list[Mapping]:
    """The deals of every part of a close that already reached the venue (C-VEN-1). A part with
    no venue trace is marked NOT_SENT; an order already recorded as ACIS's is never re-claimed."""
    deals = []
    for part, state, pid, venue_order_id, sent in store.parts(fragment_id):
        tracker = trackers.get(part)
        if state == "NOT_SENT":
            continue
        if tracker is not None and tracker.done.done():
            venue_order_id = tracker.venue_order_id
        elif venue_order_id is None:
            known = store.ours()[0]
            found = await find_order(session, lambda o: is_close_of(o, pid) and int(o["orderId"]) not in known,
                                     since=sent, now=now)
            if found is None:
                store.not_sent(part, now)
                continue
            venue_order_id = int(found["orderId"])
        _, part_deals = await order_deals(session, venue_order_id, req_class="protect")
        router.mark_seen(part_deals)
        store.terminal(part, venue_order_id, pid, now)
        forget(part)
        deals.extend(part_deals)
    return deals


async def synchronise(session, store, router, *, account_key: str, own_label: str, now: datetime,
                      log) -> tuple[tuple, tuple]:
    """SYNCING after every start and reconnect (§7.8, corrected order, GAP-P12D-126). Returns
    (ACIS positions for Risk's `reconcile_on_restart`, foreign positions)."""
    from core.execution.ctrader_orders import broker_positions, direction_of, fill_report

    for fragment_id, order_id, sent in store.in_flight():           # 1. our own orders first
        pid = next((p for f, _, p, _, _ in store.parts(fragment_id.split("#")[0]) if f == fragment_id), None)
        match = ((lambda o: is_close_of(o, pid)) if "#" in fragment_id
                 else (lambda o: o.get("clientOrderId") == fragment_id))
        found = await find_order(session, match, since=sent, now=now)
        if found is None:
            store.not_sent(fragment_id, now)
            continue
        order, deals = await order_deals(session, int(found["orderId"]), req_class="protect")
        router.mark_seen(deals)
        store.terminal(fragment_id, int(found["orderId"]), order.get("positionId"), now)
        trade = order["tradeData"]
        instrument = router.instruments.get(int(trade["symbolId"]))
        if deals and instrument is not None:
            report = fill_report(deals, fill_id=f"ct:{account_key}:{found['orderId']}", order_id=order_id,
                                 fragment_id=fragment_id, instrument=instrument,
                                 direction=direction_of(trade["tradeSide"]),
                                 requested_units=Decimal(int(trade["volume"])) / 100,
                                 requested_price=float(deals[0]["executionPrice"]), session_id="venue",
                                 now=now, cancelled=True)
            log.event("VENUE_RECOVERED_FILL", fragment_id=fragment_id, fill_id=report.fill_id)
            router.unsolicited.put_nowait(report)

    ours_orders, ours_positions = store.ours()                      # 2. then the deals missed
    router.acis_positions |= ours_positions
    binding = store.binding()
    cursor = binding[2] if binding else ms(now)
    for deal in await missed_deals(session, cursor, now):
        if int(deal["orderId"]) not in ours_orders:
            router.ingest(deal, ours=int(deal["positionId"]) in router.acis_positions)
        cursor = max(cursor, int(deal["executionTimestamp"]))
    store.advance(cursor)

    positions, _ = await reconcile(session, req_class="protect")    # 3. venue truth
    router.seed(positions)
    ours, foreign = broker_positions(positions, router.instruments, own_label)
    for p in positions:                                             # 4. never unprotected
        if p["tradeData"].get("label") == own_label and p.get("stopLoss") is None:
            await session.request(PT.CLOSE_POSITION_REQ, {"positionId": int(p["positionId"]),
                                                          "volume": int(p["tradeData"]["volume"])},
                                  req_class="close")
            log.event("VENUE_STOP_MISSING", position_id=int(p["positionId"]), severity="critical")
    session.mark_ready()
    return ours, foreign
