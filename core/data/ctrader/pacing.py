"""Local pacing of venue requests beyond the general rate (ACIS-13 §6.2, §12; GAP-P12D-132 TAE-11).

Invariants:
  * History requests (deal list, order list, order details, trendbars) are spaced at `history_per_s`, below
    the venue's documented "maximum of 5 requests per second per connection for any historical
    data requests" — the general bucket in the session's `_send` still applies on top.
  * A payload type the venue answered with `retryAfter` (REQUEST_FREQUENCY_EXCEEDED,
    BLOCKED_PAYLOAD_TYPE) waits out that pause before it is sent again; other types are not held.
  * Time is the injected monotonic clock; waiting is `asyncio.sleep`.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from core.data.ctrader import schema as s

HISTORY = frozenset({s.PT.DEAL_LIST_REQ, s.PT.ORDER_LIST_REQ, s.PT.ORDER_DETAILS_REQ,
                     s.PT.GET_TRENDBARS_REQ})


class Pacer:
    def __init__(self, *, history_per_s: float, mono: Callable[[], float]) -> None:
        self._gap = 1.0 / history_per_s
        self._mono = mono
        self._last_history = float("-inf")
        self._paused: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def before(self, pt: int) -> None:
        wait = self._paused.get(int(pt), float("-inf")) - self._mono()
        if wait > 0:
            await asyncio.sleep(wait)
        if pt not in HISTORY:
            return
        async with self._lock:
            wait = self._last_history + self._gap - self._mono()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_history = self._mono()

    def pause(self, pt: int, retry_after_s: float | None) -> None:
        if retry_after_s:
            self._paused[int(pt)] = self._mono() + float(retry_after_s)
