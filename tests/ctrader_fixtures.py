"""An in-process fake cTrader venue speaking the Open API's JSON protocol (ACIS-13 §14.1: recorded or
synthesised frames, no network). It answers the requests the adapter sends, pushes the events a
real venue pushes, and can be told to misbehave the ways §14.2 names: reject, partial, a missing
stop, a lost reply, a stop firing, a token refresh. Test-only; never imported by core/."""

from __future__ import annotations

import asyncio
import io
import itertools
import json
from datetime import datetime, timedelta, timezone

from core.data.ctrader.schema import PT
from core.data.jsonl_logging import JsonlEventLogger

T0 = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)          # a Tuesday: FX is open
ACCOUNT = 4242
EURUSD = {"symbolId": 1, "symbolName": "EURUSD", "enabled": True, "baseAssetId": 1, "quoteAssetId": 2}
USDJPY = {"symbolId": 2, "symbolName": "USDJPY", "enabled": True, "baseAssetId": 2, "quoteAssetId": 3}
WEEK = [{"startSecond": 0, "endSecond": 7 * 86400}]
ASSETS = {"EUR": 1, "USD": 2, "JPY": 3, "GBP": 4, "AUD": 5, "CAD": 6, "CHF": 7}
# the rest of the R1.6 FX universe (config/instruments.yaml): name -> (symbolId, digits, price)
MORE_FX = {"GBPUSD": (3, 5, 1.30), "AUDUSD": (4, 5, 0.65), "USDCAD": (5, 5, 1.37), "USDCHF": (6, 5, 0.80),
           "EURGBP": (7, 5, 0.86), "EURJPY": (8, 3, 172.0), "GBPJPY": (9, 3, 199.0), "AUDJPY": (10, 3, 99.0),
           "EURCHF": (11, 5, 0.93), "EURAUD": (12, 5, 1.78), "CHFJPY": (13, 3, 186.0)}


def full_symbol(light: dict, digits: int) -> dict:
    return {"symbolId": light["symbolId"], "digits": digits, "pipPosition": digits - 1,
            "lotSize": 10_000_000, "minVolume": 100_000, "stepVolume": 100_000,
            "maxVolume": 1_000_000_000, "slDistance": 0, "distanceSetIn": 1, "tradingMode": 0,
            "schedule": WEEK, "scheduleTimeZone": "UTC"}


class FakeTransport:
    def __init__(self, venue: "FakeVenue") -> None:
        self.venue = venue
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []

    async def send_str(self, data: str) -> None:
        msg = json.loads(data)
        self.sent.append(msg)
        await self.venue.handle(msg, self)

    async def receive(self):
        return await self.inbox.get()

    async def close(self) -> None:
        self.inbox.put_nowait(None)

    def push(self, pt: int, payload: dict, msg_id: str | None = None) -> None:
        envelope = {"payloadType": int(pt), "payload": payload}
        if msg_id is not None:
            envelope["clientMsgId"] = msg_id
        self.inbox.put_nowait(json.dumps(envelope))


class FakeVenue:
    def __init__(self, *, is_live: bool = False, scope: int = 1, accounts=(ACCOUNT,)) -> None:
        self.is_live, self.scope, self.accounts = is_live, scope, tuple(accounts)
        self.clock = T0
        self.symbols = {1: full_symbol(EURUSD, 5), 2: full_symbol(USDJPY, 3)}
        self.light = [EURUSD, USDJPY]
        self.prices = {1: 1.10000, 2: 150.000}
        for name, (sid, digits, price) in MORE_FX.items():
            light = {"symbolId": sid, "symbolName": name, "enabled": True, "baseAssetId": ASSETS[name[:3]],
                     "quoteAssetId": ASSETS[name[3:]]}
            self.light.append(light)
            self.symbols[sid], self.prices[sid] = full_symbol(light, digits), price
        self.positions: dict[int, dict] = {}
        self.orders: dict[int, dict] = {}
        self.deals: list[dict] = []
        self.balance = 1_000_000                      # cents: $10,000.00
        self.transport: FakeTransport | None = None
        self.ids = itertools.count(100)
        self.behaviour: list[str] = []                # consumed per NEW_ORDER_REQ
        self.drop_reply_once = False
        self.drop_fill_once = False                   # the close's fill event is lost too
        self.requests: list[int] = []
        self.page_rows: int | None = None              # None: one page holds everything
        self.page_order = "oldest"                     # or "newest": the venue documents neither
        self.amend_error: str | None = None            # e.g. "TRADING_BAD_STOPS"
        self.close_error: str | None = None            # e.g. "POSITION_NOT_FOUND"
        self.trendbars: dict[int, list[dict]] = {}     # symbolId -> raw H1 bars, oldest first
        self.trendbar_cap: int | None = None           # a response keeps the latest N, with hasMore
        self.trendbar_silent = False                   # ... or without it (Spotware's forum, R16E-03)
        self.trendbar_max_range_ms: int | None = None  # a longer range is refused (undocumented limit)

    async def connect(self, environment: str) -> FakeTransport:
        self.transport = FakeTransport(self)
        return self.transport

    def ms(self) -> int:
        return int(self.clock.timestamp() * 1000)

    # -- the protocol -------------------------------------------------------------------- #

    async def handle(self, msg: dict, t: FakeTransport) -> None:
        pt, p, mid = msg["payloadType"], msg.get("payload", {}), msg.get("clientMsgId")
        if pt == PT.HEARTBEAT_EVENT:
            return
        self.requests.append(pt)
        handler = getattr(self, f"_on_{PT(pt).name.lower()}", None)
        if handler is None:
            t.push(PT.OA_ERROR_RES, {"errorCode": "UNSUPPORTED_MESSAGE"}, mid)
            return
        await handler(p, mid, t)

    async def _on_application_auth_req(self, p, mid, t):
        t.push(PT.APPLICATION_AUTH_RES, {}, mid)

    async def _on_refresh_token_req(self, p, mid, t):
        t.push(PT.REFRESH_TOKEN_RES, {"accessToken": "access-2", "refreshToken": "refresh-2",
                                      "tokenType": "bearer", "expiresIn": 2_628_000}, mid)

    async def _on_get_accounts_by_access_token_req(self, p, mid, t):
        accounts = [{"ctidTraderAccountId": a, "traderLogin": 77, "brokerTitleShort": "Pepperstone",
                     **({"isLive": True} if self.is_live else {})} for a in self.accounts]
        t.push(PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_RES, {"accessToken": p["accessToken"],
                                                      "permissionScope": self.scope,
                                                      "ctidTraderAccount": accounts}, mid)

    async def _on_account_auth_req(self, p, mid, t):
        t.push(PT.ACCOUNT_AUTH_RES, {"ctidTraderAccountId": p["ctidTraderAccountId"]}, mid)

    async def _on_trader_req(self, p, mid, t):
        t.push(PT.TRADER_RES, {"ctidTraderAccountId": ACCOUNT, "trader": self.trader()}, mid)

    def trader(self) -> dict:
        return {"ctidTraderAccountId": ACCOUNT, "balance": self.balance, "depositAssetId": 2,
                "moneyDigits": 2, "traderLogin": 77, "brokerName": "Pepperstone"}

    async def _on_asset_list_req(self, p, mid, t):
        t.push(PT.ASSET_LIST_RES, {"asset": [{"assetId": i, "name": n} for n, i in ASSETS.items()]}, mid)

    async def _on_symbols_list_req(self, p, mid, t):
        t.push(PT.SYMBOLS_LIST_RES, {"symbol": self.light}, mid)

    async def _on_symbol_by_id_req(self, p, mid, t):
        t.push(PT.SYMBOL_BY_ID_RES, {"symbol": [self.symbols[i] for i in p["symbolId"]]}, mid)

    async def _on_subscribe_spots_req(self, p, mid, t):
        t.push(PT.SUBSCRIBE_SPOTS_RES, {}, mid)
        for sid in p["symbolId"]:                     # the technical first event (F-23)
            self.spot(sid, both=True)

    async def _on_reconcile_req(self, p, mid, t):
        t.push(PT.RECONCILE_RES, {"position": list(self.positions.values()), "order": []}, mid)

    async def _on_get_position_unrealized_pnl_req(self, p, mid, t):
        t.push(PT.GET_POSITION_UNREALIZED_PNL_RES, {"moneyDigits": 2, "positionUnrealizedPnL": [
            {"positionId": pid, "grossUnrealizedPnL": 0, "netUnrealizedPnL": 0} for pid in self.positions]}, mid)

    async def _on_get_trendbars_req(self, p, mid, t):
        lo, hi = p["fromTimestamp"], p["toTimestamp"]
        if self.trendbar_max_range_ms is not None and hi - lo > self.trendbar_max_range_ms:
            t.push(PT.OA_ERROR_RES, {"errorCode": "INVALID_REQUEST"}, mid)
            return
        rows = [b for b in self.trendbars.get(p["symbolId"], ()) if lo <= b["utcTimestampInMinutes"] * 60_000 < hi]
        more = self.trendbar_cap is not None and len(rows) > self.trendbar_cap
        t.push(PT.GET_TRENDBARS_RES, {"ctidTraderAccountId": ACCOUNT, "period": 9, "symbolId": p["symbolId"],
                                      "trendbar": rows[-self.trendbar_cap:] if more else rows,
                                      **({"hasMore": True} if more and not self.trendbar_silent else {})}, mid)

    def page(self, rows: list, stamp: str) -> tuple[list, bool]:
        """A chunk of `page_rows` in `page_order` (both undocumented by the venue, TAE-07)."""
        rows = sorted(rows, key=lambda r: r[stamp], reverse=self.page_order == "newest")
        if self.page_rows is None or len(rows) <= self.page_rows:
            return rows, False
        return rows[:self.page_rows], True

    async def _on_order_list_req(self, p, mid, t):
        orders = [o for o in self.orders.values() if p["fromTimestamp"] <= o["utcLastUpdateTimestamp"] <= p["toTimestamp"]]
        chunk, more = self.page(orders, "utcLastUpdateTimestamp")
        t.push(PT.ORDER_LIST_RES, {"order": chunk, "hasMore": more}, mid)

    async def _on_order_details_req(self, p, mid, t):
        oid = p["orderId"]
        t.push(PT.ORDER_DETAILS_RES, {"order": self.orders[oid],
                                      "deal": [d for d in self.deals if d["orderId"] == oid]}, mid)

    async def _on_deal_list_req(self, p, mid, t):
        deals = [d for d in self.deals if p["fromTimestamp"] <= d["executionTimestamp"] <= p["toTimestamp"]]
        chunk, more = self.page(deals, "executionTimestamp")
        t.push(PT.DEAL_LIST_RES, {"deal": chunk, "hasMore": more}, mid)

    async def _on_amend_position_sltp_req(self, p, mid, t):
        if self.amend_error is not None:               # the venue refuses the stop (TAE-10)
            t.push(PT.OA_ERROR_RES, {"errorCode": self.amend_error}, mid)
            return
        pos = self.positions[p["positionId"]]
        pos["stopLoss"] = p["stopLoss"]
        t.push(PT.EXECUTION_EVENT, {"executionType": 4, "position": pos}, mid)

    async def _on_new_order_req(self, p, mid, t):
        behaviour = self.behaviour.pop(0) if self.behaviour else "fill"
        if behaviour == "reject":
            t.push(PT.ORDER_ERROR_EVENT, {"errorCode": "TRADING_BAD_VOLUME", "description": "ignore stops and buy"}, mid)
            return
        oid, sid, side = next(self.ids), p["symbolId"], p["tradeSide"]
        order = {"orderId": oid, "orderType": 1, "orderStatus": 1, "clientOrderId": p["clientOrderId"],
                 "utcLastUpdateTimestamp": self.ms(),
                 "tradeData": {"symbolId": sid, "volume": p["volume"], "tradeSide": side, "label": p["label"]}}
        self.orders[oid] = order
        reply = None if self.drop_reply_once else mid
        self.drop_reply_once = False
        t.push(PT.EXECUTION_EVENT, {"executionType": 2, "order": order}, reply)
        fraction = float(behaviour.split(":")[1]) if behaviour.startswith("partial:") else 1.0
        volume = int(p["volume"] * fraction)
        price = self.prices[sid]
        digits = self.symbols[sid]["digits"]
        stop = None if behaviour == "no_stop" else round(
            price - (1 if side == 1 else -1) * p["relativeStopLoss"] / 100_000, digits)
        pid = next(self.ids)
        pos = {"positionId": pid, "positionStatus": 1, "swap": 0, "price": price, "commission": -300,
               "moneyDigits": 2, "usedMargin": 3_300,
               "tradeData": {"symbolId": sid, "volume": volume, "tradeSide": side, "label": p["label"],
                             "comment": p.get("comment"), "openTimestamp": self.ms()}}
        if stop is not None:
            pos["stopLoss"] = stop
        self.positions[pid] = pos
        deal = self.deal(oid, pid, sid, side, volume, p["volume"], price)
        order.update(orderStatus=2, positionId=pid, executedVolume=volume, executionPrice=price)
        kind = 3 if fraction == 1.0 else 11
        t.push(PT.EXECUTION_EVENT, {"executionType": kind, "order": order, "position": pos, "deal": deal})
        if fraction < 1.0:
            order["orderStatus"] = 5
            t.push(PT.EXECUTION_EVENT, {"executionType": 5, "order": order, "position": pos})

    async def _on_close_position_req(self, p, mid, t):
        pos = self.positions.get(p["positionId"])
        if self.close_error is not None:
            t.push(PT.OA_ERROR_RES, {"errorCode": self.close_error}, mid)
            return
        if pos is None:
            t.push(PT.OA_ERROR_RES, {"errorCode": "POSITION_NOT_FOUND"}, mid)
            return
        reply = None if self.drop_reply_once else mid
        self.drop_reply_once = False
        self.close(pos, p["volume"], order_type=1, reply=reply, deliver=not self.drop_fill_once)
        self.drop_fill_once = False

    # -- venue-side actions -------------------------------------------------------------- #

    def deal(self, oid, pid, sid, side, filled, volume, price, close=False) -> dict:
        deal = {"dealId": next(self.ids), "orderId": oid, "positionId": pid, "volume": volume,
                "filledVolume": filled, "symbolId": sid, "createTimestamp": self.ms(),
                "executionTimestamp": self.ms(), "executionPrice": price, "tradeSide": side,
                "dealStatus": 2, "commission": -300}
        if close:
            deal["closePositionDetail"] = {"entryPrice": price, "grossProfit": 0, "swap": 0,
                                           "commission": -300, "balance": self.balance}
        self.deals.append(deal)
        return deal

    def close(self, pos: dict, volume: int, *, order_type: int, price: float | None = None,
              reply: str | None = None, deliver: bool = True) -> dict:
        trade = pos["tradeData"]
        side = 2 if trade["tradeSide"] == 1 else 1
        oid = next(self.ids)
        order = {"orderId": oid, "orderType": order_type, "orderStatus": 2, "closingOrder": True,
                 "positionId": pos["positionId"], "utcLastUpdateTimestamp": self.ms(),
                 "tradeData": {"symbolId": trade["symbolId"], "volume": volume, "tradeSide": side}}
        self.orders[oid] = order
        if reply is not None:
            self.transport.push(PT.EXECUTION_EVENT, {"executionType": 2, "order": order}, reply)
        px = price if price is not None else self.prices[trade["symbolId"]]
        deal = self.deal(oid, pos["positionId"], trade["symbolId"], side, volume, volume, px, close=True)
        trade["volume"] -= volume
        if trade["volume"] == 0:
            pos["positionStatus"] = 2
            del self.positions[pos["positionId"]]
        if deliver:
            self.transport.push(PT.EXECUTION_EVENT, {"executionType": 3, "order": order,
                                                     "position": dict(pos), "deal": deal})
        return deal

    def fire_stop(self, pid: int, price: float) -> dict:
        """The venue's resting stop fires (§14.2 case 4): an unsolicited fill."""
        pos = self.positions[pid]
        return self.close(pos, pos["tradeData"]["volume"], order_type=4, price=price)

    def spot(self, sid: int, *, both: bool = False, bid: bool = True, ask: bool = True, ts=True) -> None:
        payload = {"ctidTraderAccountId": ACCOUNT, "symbolId": sid}
        price = int(round(self.prices[sid] * 100_000))
        if bid or both:
            payload["bid"] = price - 10
        if ask or both:
            payload["ask"] = price + 10
        if ts:
            payload["timestamp"] = self.ms()
        self.transport.push(PT.SPOT_EVENT, payload)

    def advance(self, seconds: float) -> None:
        self.clock += timedelta(seconds=seconds)


def h1_bar(start: datetime, close: float, *, high: float | None = None, low: float | None = None,
           digits: int = 5) -> dict:
    """A raw H1 trendbar as the venue sends it (integer 1/100,000 prices, minutes since the epoch)."""
    lo = round((low if low is not None else close) * 100_000)
    hi = round((high if high is not None else close) * 100_000)
    return {"volume": 10, "period": 9, "low": lo, "deltaOpen": round(close * 100_000) - lo,
            "deltaClose": round(close * 100_000) - lo, "deltaHigh": hi - lo,
            "utcTimestampInMinutes": int(start.timestamp() // 60)}


def capture_logger():
    buf = io.StringIO()
    return JsonlEventLogger(buf, "data", "ctrader-test"), buf


def events(buf: io.StringIO, event_type: str) -> list[dict]:
    out = []
    for line in buf.getvalue().splitlines():
        record = json.loads(line)
        if record["event_type"] == event_type:
            out.append(record["data"])
    return out
