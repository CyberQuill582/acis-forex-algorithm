"""A close carries its intent across the face boundary (audits X3 / F4).

The engine's reduce-only pre-check reads the venue position and then sends: a check-then-
act that a concurrent close or a venue-side stop can race, and that a hedging venue turns
into a new opposite position. The close now reaches the venue as `close_position`, which
the adapter maps to the venue's own atomic close; the mock does it under a lock. Tests from
the audits' repros (`r3_close_race_and_hedging.py`, `r3_close_races.py`)."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal

from core.execution.venue import BrokerPosition, FillReport, FillStatus
from core.execution.mock_face import MockExecutionFace
from tests.unit.test_execution import T0, mk_order, mk_orchestrator

LOT = Decimal("100000")


class YieldingFace(MockExecutionFace):
    """Every venue call yields to the event loop first, like a network round-trip."""

    async def open_positions(self):
        await asyncio.sleep(0)
        return await super().open_positions()

    async def close_position(self, **kw):
        await asyncio.sleep(0)
        return await super().close_position(**kw)


class StopFiresAfterRead(MockExecutionFace):
    """The venue's resting stop closes the long right after the engine reads it."""
    armed = True

    async def open_positions(self):
        held = await super().open_positions()
        if self.armed and held:
            self.armed = False
            self._net["EUR_USD"] = Decimal("0")
        return held


class HedgingFace(MockExecutionFace):
    """A hedging venue: an opposite ORDER opens a second position; only a close reduces."""

    def __init__(self) -> None:
        super().__init__()
        self.descriptor = replace(self.descriptor, account_model="hedging")
        self.book: list[list] = []                            # [direction, units]

    async def submit_order(self, *, direction, units, fragment_id, **kw):
        self.book.append([direction, units])
        return FillReport(fill_id=f"{fragment_id}:f", order_id=kw["order_id"],
                          fragment_id=fragment_id, instrument=kw["instrument"],
                          direction=direction, requested_price=kw["requested_price"],
                          fill_price=kw["requested_price"], filled_units=units,
                          slippage_bps=0.0, fill_time=kw["now"], venue=self.name,
                          status=FillStatus.FILLED, remaining_units=Decimal("0"),
                          session_id=kw["session_id"])

    async def close_position(self, *, direction, units, fragment_id, **kw):
        async with self._lock:
            take = units
            for pos in self.book:
                if pos[0] == direction and take > 0:
                    cut = min(pos[1], take)
                    pos[1] -= cut
                    take -= cut
            self.book = [p for p in self.book if p[1] > 0]
            filled = units - take
            return FillReport(
                fill_id=f"{fragment_id}:c", order_id=kw["order_id"], fragment_id=fragment_id,
                instrument=kw["instrument"], direction=-direction,
                requested_price=kw["requested_price"],
                fill_price=kw["requested_price"] if filled else 0.0, filled_units=filled,
                slippage_bps=0.0, fill_time=kw["now"], venue=self.name,
                status=FillStatus.FILLED if filled == units else
                FillStatus.REJECTED if filled == 0 else FillStatus.PARTIAL,
                remaining_units=take, session_id=kw["session_id"])

    async def open_positions(self):
        return tuple(BrokerPosition(instrument="EUR_USD", direction=d, size_units=u)
                     for d, u in self.book)


async def test_two_concurrent_closes_never_flip_the_position(tmp_path) -> None:
    face = YieldingFace()
    orch, _, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    await orch.submit(mk_order(str(LOT), order_id="long"), valid_for_seconds=300)
    await asyncio.gather(
        orch.submit(mk_order(str(LOT), action="close", order_id="c1"), valid_for_seconds=300),
        orch.submit(mk_order(str(LOT), action="close", order_id="c2"), valid_for_seconds=300))
    assert await face.open_positions() == ()                   # flat — was SHORT 100,000


async def test_a_venue_stop_between_read_and_close_opens_nothing(tmp_path) -> None:
    face = StopFiresAfterRead()
    face._net["EUR_USD"] = Decimal("50000")
    orch, _, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("50000", action="close", order_id="c"),
                                valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.REJECTED]  # nothing left to close
    assert await face.open_positions() == ()                   # was SHORT 50,000, no stop


async def test_a_hedging_venue_never_ends_net_opposite(tmp_path) -> None:
    face = HedgingFace()
    orch, _, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    await orch.submit(mk_order(str(LOT), order_id="long"), valid_for_seconds=300)
    for i in range(3):                  # e.g. the weekend flatten re-emitting each tick
        await orch.submit(mk_order(str(LOT), action="close", order_id=f"c{i}"),
                          valid_for_seconds=300)
    net = sum(d * u for d, u in face.book)
    assert face.book == [] and net == 0                        # was net SHORT 200,000


async def test_close_position_is_reduce_only_on_the_shipped_mock() -> None:
    face = MockExecutionFace()
    flat = await face.close_position(fragment_id="f0", order_id="o", instrument="EUR_USD",
                                     direction=1, units=LOT, requested_price=1.1, now=T0,
                                     session_id="s")
    assert flat.status is FillStatus.REJECTED and await face.open_positions() == ()
    await face.submit_order(fragment_id="o1", order_id="o", instrument="EUR_USD", direction=1,
                            units=LOT, requested_price=1.1, ioc=False, now=T0, session_id="s")
    big = await face.close_position(fragment_id="f1", order_id="o", instrument="EUR_USD",
                                    direction=1, units=LOT * 3, requested_price=1.1, now=T0,
                                    session_id="s")
    assert (big.status, big.filled_units, big.direction) == (FillStatus.PARTIAL, LOT, -1)
    assert await face.open_positions() == ()                   # flat, never short
