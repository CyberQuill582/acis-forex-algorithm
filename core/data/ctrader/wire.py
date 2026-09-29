"""cTrader wire rules (ACIS-13 §6.2, route C): one JSON envelope per WebSocket frame, responses
matched to requests by `clientMsgId`, and the heartbeat and liveness clocks. No socket code here.

Invariants:
  * The envelope is exactly {clientMsgId, payloadType, payload} (F-07); a frame missing
    `payloadType`, or whose payload is not an object, is a DataQualityError, never guessed.
  * A text or a binary frame decodes the same way (the frame type is unconfirmed, OQ-12).
  * Every request carries a fresh `clientMsgId`, and a response resolves only the request that
    carries its id. An unmatched frame is an EVENT, routed by payload type (§3.2).
  * A heartbeat is due when nothing has been SENT for `heartbeat_s` (the strictest source, 10 s,
    C-VEN-10); the link is dead when nothing has been RECEIVED for `liveness_timeout_s`.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from dataclasses import dataclass
from typing import Mapping

from core.data.ctrader.schema import ERRORS, PT
from core.data.errors import DataQualityError

MAX_FRAME_BYTES = 4 * 1024 * 1024      # a larger frame is refused, not parsed


@dataclass(frozen=True)
class Frame:
    payload_type: int
    payload: Mapping
    client_msg_id: str | None


class VenueError(Exception):
    """The venue answered a request with an error: `code` is its enumerated name (C-VEN-15);
    `description` is venue text, kept as data and never parsed."""

    def __init__(self, code: str, description: str = "", *, retry_after_s: float | None = None,
                 maintenance_end_ms: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.description = description
        self.retry_after_s = retry_after_s
        self.maintenance_end_ms = maintenance_end_ms


def encode(payload_type: int, payload: Mapping, client_msg_id: str | None = None) -> str:
    envelope: dict = {"payloadType": int(payload_type), "payload": dict(payload)}
    if client_msg_id is not None:
        envelope["clientMsgId"] = client_msg_id
    return json.dumps(envelope, separators=(",", ":"))


def decode(raw: str | bytes) -> Frame:
    if len(raw) > MAX_FRAME_BYTES:
        raise DataQualityError("frame", len(raw), "frame larger than the adapter accepts")
    try:
        envelope = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataQualityError("frame", str(raw)[:80], "not a JSON envelope") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payloadType"), int):
        raise DataQualityError("payloadType", envelope, "missing or not an integer")
    payload = envelope.get("payload", {})
    if not isinstance(payload, dict):
        raise DataQualityError("payload", payload, "not an object")
    msg_id = envelope.get("clientMsgId")
    return Frame(envelope["payloadType"], payload, msg_id if isinstance(msg_id, str) else None)


def error_of(frame: Frame) -> VenueError | None:
    """The error an error frame carries, or None for any other frame."""
    if frame.payload_type not in ERRORS:
        return None
    p = frame.payload
    retry = p.get("retryAfter")
    return VenueError(str(p.get("errorCode", "UNKNOWN_ERROR")), str(p.get("description", "")),
                      retry_after_s=float(retry) if retry is not None else None,
                      maintenance_end_ms=p.get("maintenanceEndTimestamp"))


class Correlator:
    """Pending requests by `clientMsgId`: `open` before the frame leaves, `resolve` on arrival."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._ids = itertools.count(1)
        self._pending: dict[str, asyncio.Future] = {}

    def open(self) -> tuple[str, asyncio.Future]:
        msg_id = f"{self._prefix}-{next(self._ids)}"
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        return msg_id, future

    def resolve(self, frame: Frame) -> bool:
        future = self._pending.pop(frame.client_msg_id, None) if frame.client_msg_id else None
        if future is None:
            return False
        if not future.done():
            error = error_of(frame)
            if error is None:
                future.set_result(frame)
            else:
                future.set_exception(error)
        return True

    def forget(self, msg_id: str) -> None:
        self._pending.pop(msg_id, None)

    def fail_all(self, exc: BaseException) -> None:
        """The link died: every waiter learns it, none waits for a reply that cannot come."""
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()


class LinkClock:
    """Heartbeat and liveness timing on an injected monotonic clock (seconds)."""

    def __init__(self, now: float, *, heartbeat_s: float, liveness_timeout_s: float) -> None:
        if not 0 < heartbeat_s <= 10:
            raise DataQualityError("heartbeat_s", heartbeat_s, "must be in (0, 10] (F-03)")
        if liveness_timeout_s <= heartbeat_s:
            raise DataQualityError("liveness_timeout_s", liveness_timeout_s,
                                   "must exceed heartbeat_s")
        self.heartbeat_s = heartbeat_s
        self.liveness_timeout_s = liveness_timeout_s
        self._sent = self._received = now

    def sent(self, now: float) -> None:
        self._sent = now

    def received(self, now: float) -> None:
        self._received = now

    def heartbeat_due(self, now: float) -> bool:
        return now - self._sent >= self.heartbeat_s

    def dead(self, now: float) -> bool:
        return now - self._received >= self.liveness_timeout_s


HEARTBEAT = encode(PT.HEARTBEAT_EVENT, {})
