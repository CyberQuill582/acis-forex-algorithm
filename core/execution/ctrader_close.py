"""The cTrader close path (ACIS-13 §7.3 "reduce", C-EXE-7, C-VEN-9): a mixin of the execution face.

Invariants:
  * A close is reduce-only and atomic at the venue: one `ProtoOAClosePositionReq` per ACIS venue
    position on the named side, oldest first, never more than held, never a hedge.
  * A close carries no `clientOrderId`, so each part is recorded per venue position BEFORE it
    leaves; an unknown outcome is searched as the market closing order on that position, skipping
    orders already recorded as ACIS's (§7.3 step 6), never resent blind.
  * A part the venue refuses (§12: the position closed by a stop meanwhile, the market closed, a
    rate limit) closed nothing: it is marked NOT_SENT and the report says what was not closed;
    it never escapes as an error that halts the engine (GAP-P12D-132 TAI-09).
  * A reply that times out is ConnectionError: the outcome is unknown and searched on the retry
    (GAP-P12D-132 TAI-08).
  * Nothing leaves a link that is not READY (§8.1, TAI-12): a close waits, bounded by the ack
    timeout, for a re-syncing link, else it is a REJECTED report.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from core.data.ctrader.link import LinkState
from core.data.ctrader.schema import PT, VOLUME_SCALE
from core.data.ctrader.wire import VenueError
from core.execution import ctrader_sync as sync
from core.execution.ctrader_orders import direction_of, protocol_volume
from core.execution.venue import FillReport


@dataclass(frozen=True)
class _Order:
    fragment_id: str
    order_id: str
    instrument: str
    direction: int                   # the side TRADED
    units: Decimal
    requested_price: float
    session_id: str


async def _acked(tracker, timeout_s: float) -> None:
    """The terminal execution event, or ConnectionError: ACIS-06's retry then searches (§7.3 step 6)."""
    try:
        await asyncio.wait_for(asyncio.shield(tracker.done), timeout_s)
    except asyncio.TimeoutError:
        raise ConnectionError("no terminal event before the ack timeout; the outcome is searched") from None


class CloseMixin:
    """The face's reduce path; the face supplies the session, store, router and report helpers."""

    async def close_position(self, *, fragment_id: str, order_id: str, instrument: str,
                             direction: int, units: Decimal, requested_price: float,
                             now: datetime, session_id: str) -> FillReport:
        if fragment_id in self._reports:
            return self._reports[fragment_id]
        o = _Order(fragment_id, order_id, instrument, -direction, units, requested_price, session_id)
        if not await self._ready():                    # §8.1: nothing leaves a SYNCING/REAUTH link
            return self._refused("VENUE_NOT_READY", o, now)
        spec = self._specs.get(instrument)
        if spec is None:
            return self._refused("VENUE_SYMBOL_UNMAPPED", o, now)
        deals = await sync.resume_close(self._s, self._store, self.router, self._trackers,
                                        fragment_id, now, forget=self._forget)
        remaining = units - sum((Decimal(int(d["filledVolume"])) for d in deals), Decimal(0)) / VOLUME_SCALE
        positions, _ = await sync.reconcile(self._s, req_class="protect")
        self.router.seed(positions)
        held = sorted((p for p in positions if p["tradeData"].get("label") == self._label
                       and int(p["tradeData"]["symbolId"]) == spec.symbol_id
                       and direction_of(p["tradeData"]["tradeSide"]) == direction),
                      key=lambda p: int(p["tradeData"].get("openTimestamp", 0)))
        if not held and not deals:
            return self._refused("VENUE_NOTHING_HELD", o, now)
        for position in held:
            if remaining <= 0:
                break
            volume = min(remaining, Decimal(int(position["tradeData"]["volume"])) / VOLUME_SCALE)
            deals.extend(await self._close_part(fragment_id, order_id, int(position["positionId"]),
                                                volume, now))
            remaining -= volume
        return self._finish(deals, None, None, False, o, fill_id=f"ct:{self._key}:close:{fragment_id}")

    async def _ready(self) -> bool:
        """A close waits, bounded by the ack timeout, for a link that is re-syncing to be READY."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._ack
        while self._s.state is not LinkState.READY:
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(0.05)
        return True

    async def _close_part(self, fragment_id: str, order_id: str, pid: int, volume: Decimal,
                          now: datetime) -> list[Mapping]:
        part = f"{fragment_id}#{len(self._store.parts(fragment_id))}"
        tracker = self._trackers[part] = self.router.close_tracker(part, pid)
        self._store.sent(part, order_id, now, position_id=pid)
        try:
            frame = await self._s.request(PT.CLOSE_POSITION_REQ, {
                "positionId": pid, "volume": protocol_volume(volume)}, req_class="close")
        except VenueError as exc:                      # §12: raced a stop, or refused: nothing closed
            self._store.not_sent(part, self._now())
            self._forget(part)
            self._log.event("VENUE_CLOSE_REFUSED", part=part, position_id=pid, code=exc.code)
            return []
        except asyncio.TimeoutError:
            raise ConnectionError("the close's reply timed out; it is searched, never resent") from None
        self.router.route(frame, reply_to=tracker)
        await _acked(tracker, self._ack)
        self._store.terminal(part, tracker.venue_order_id, pid, self._now())
        self._forget(part)
        return list(tracker.deals.values())
