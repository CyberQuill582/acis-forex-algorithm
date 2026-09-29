"""The socket the cTrader session speaks through (ACIS-13 §3.3, route C): one TLS WebSocket to the
JSON port. The only module that imports aiohttp; tests swap in an in-process fake venue.

Invariants: the host is chosen by the environment from constants, never from config, so a demo
binding cannot be aimed at the live host (§6.1); the connection is always TLS (`wss`, F-02).
"""

from __future__ import annotations

from typing import Protocol

from core.data.ctrader.schema import HOSTS, JSON_PORT


class Transport(Protocol):
    async def send_str(self, data: str) -> None: ...

    async def receive(self) -> str | bytes | None:
        """The next frame's data, or None once the link is closed."""
        ...

    async def close(self) -> None: ...


class WebSocketTransport:
    def __init__(self, http, ws) -> None:
        self._http = http
        self._ws = ws

    async def send_str(self, data: str) -> None:
        await self._ws.send_str(data)

    async def receive(self) -> str | bytes | None:
        import aiohttp
        msg = await self._ws.receive()
        if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
            return msg.data
        return None                                    # CLOSE, CLOSING, CLOSED, ERROR

    async def close(self) -> None:
        await self._ws.close()
        await self._http.close()


async def open_websocket(environment: str) -> Transport:
    import aiohttp
    http = aiohttp.ClientSession()
    try:
        ws = await http.ws_connect(f"wss://{HOSTS[environment]}:{JSON_PORT}", heartbeat=None,
                                   max_msg_size=4 * 1024 * 1024)
    except BaseException:
        await http.close()
        raise
    return WebSocketTransport(http, ws)
