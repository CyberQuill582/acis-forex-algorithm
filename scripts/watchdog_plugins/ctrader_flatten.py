"""The watchdog's cTrader flatten plugin (master §8.6 layer 2, ACIS-13 §7.9, ACIS-12 surface).

Invariants:
  * ZERO imports from `core/` (guard-integrity law, §8.6): the breaker must not share a failure with
    the engine it guards, so it re-implements the ~100 lines of protocol it needs, deliberately.
  * It can only CLOSE: every position on the bound account is closed at full volume and every
    pending order is cancelled; it never opens, sizes, resumes or writes config.
  * It reads the token store read-only (the engine is the single writer); a rejected token is
    re-read once, since the engine may have just refreshed it.
  * `ok` means a second reconcile found the account flat — observed, never assumed.
  * Its inputs are human-committed config (`config/watchdog.yaml`) and environment variables;
    no secret lives in a file it owns, and none is logged.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
from pathlib import Path

HOSTS = {"demo": "demo.ctraderapi.com", "live": "live.ctraderapi.com"}   # ACIS-13 F-01
PORT = 5036
APP_AUTH, ACCOUNT_AUTH, CANCEL, CLOSE, RECONCILE = 2100, 2102, 2108, 2111, 2124
ERRORS = {50, 2142}
TOKEN_REJECTED = {"CH_ACCESS_TOKEN_INVALID", "OA_AUTH_TOKEN_EXPIRED"}


async def _websocket(environment: str):
    import aiohttp

    class _Link:
        async def send_str(self, data):
            await ws.send_str(data)

        async def receive(self):
            msg = await ws.receive()
            return msg.data if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY) else None

        async def close(self):
            await ws.close()
            await http.close()

    http = aiohttp.ClientSession()
    ws = await http.ws_connect(f"wss://{HOSTS[environment]}:{PORT}", heartbeat=None)
    return _Link()


class _Refused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CTraderFlattenPlugin:
    name = "ctrader"

    def __init__(self, cfg: dict, *, result_type, connect=_websocket, timeout_s: float = 10.0) -> None:
        """`result_type` is the watchdog's FlattenResult, handed in so this file imports nothing."""
        self._result = result_type
        self._env = cfg["environment"]
        self._account = int(cfg["ctid_trader_account_id"])
        self._connect = connect
        self._timeout = timeout_s
        self._ids = itertools.count(1)

    def flatten_all(self, credentials: str):
        """`credentials` is unused: the application keys and the token store come from the
        environment (ACIS_CTRADER_CLIENT_ID / _CLIENT_SECRET / _TOKEN_STORE)."""
        try:
            closed = asyncio.run(self._flatten())
        except Exception as exc:                            # noqa: BLE001 — loud, never silent
            return self._result(ok=False, positions_closed=0, error=f"{type(exc).__name__}: {exc}")
        return self._result(ok=True, positions_closed=closed)

    async def _flatten(self) -> int:
        link = await self._connect(self._env)
        try:
            await self._ask(link, APP_AUTH, {"clientId": os.environ["ACIS_CTRADER_CLIENT_ID"],
                                             "clientSecret": os.environ["ACIS_CTRADER_CLIENT_SECRET"]})
            await self._authorise(link)
            book = await self._ask(link, RECONCILE, {"ctidTraderAccountId": self._account})
            for position in book.get("position", ()):
                await self._ask(link, CLOSE, {"ctidTraderAccountId": self._account,
                                              "positionId": position["positionId"],
                                              "volume": position["tradeData"]["volume"]})
            for order in book.get("order", ()):
                await self._ask(link, CANCEL, {"ctidTraderAccountId": self._account,
                                               "orderId": order["orderId"]})
            after = await self._ask(link, RECONCILE, {"ctidTraderAccountId": self._account})
            if after.get("position"):
                raise RuntimeError(f"{len(after['position'])} position(s) still open after the flatten")
            return len(book.get("position", ()))
        finally:
            await link.close()

    async def _authorise(self, link) -> None:
        for attempt in (1, 2):                              # re-read once: the engine may have refreshed
            token = json.loads(Path(os.environ["ACIS_CTRADER_TOKEN_STORE"]).read_text("utf-8"))["access_token"]
            try:
                await self._ask(link, ACCOUNT_AUTH, {"ctidTraderAccountId": self._account,
                                                     "accessToken": token})
                return
            except _Refused as exc:
                if exc.code == "ALREADY_LOGGED_IN":
                    return
                if exc.code not in TOKEN_REJECTED or attempt == 2:
                    raise

    async def _ask(self, link, payload_type: int, payload: dict) -> dict:
        msg_id = f"wd-{next(self._ids)}"
        await link.send_str(json.dumps({"clientMsgId": msg_id, "payloadType": payload_type,
                                        "payload": payload}))
        while True:
            raw = await asyncio.wait_for(link.receive(), self._timeout)
            if raw is None:
                raise ConnectionError("the venue closed the link")
            frame = json.loads(raw)
            if frame.get("clientMsgId") != msg_id:
                continue                                    # an event or a heartbeat: not ours
            if frame["payloadType"] in ERRORS:
                raise _Refused(str(frame.get("payload", {}).get("errorCode", "UNKNOWN_ERROR")))
            return frame.get("payload", {})
