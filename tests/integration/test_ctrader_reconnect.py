"""Reconnect with backoff against the fake venue (ACIS-13 §6.6, §8.1, §14.2 "feed reconnect
mid-position"; GAP-0020): every postcondition is read off the venue, the feed and the logs."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from random import Random

from config.venue import BackoffConfig
from core.data.ctrader.feed import CTraderFeed
from core.data.ctrader.link import LinkState
from core.data.ctrader.meter import RequestMeter
from core.data.ctrader.schema import PT
from core.data.ctrader.session import Credentials, CTraderSession
from core.data.ctrader.tokens import TokenPair, TokenStore
from core.execution.ctrader_face import CTraderExecutionFace
from core.execution.ctrader_reconnect import Reconnector
from core.execution.ctrader_store import VenueStore
from core.execution.ctrader_symbols import descriptor, spec_from
from tests.ctrader_fixtures import ACCOUNT, T0, FakeVenue, capture_logger, events

KEY = f"ctrader:demo:{ACCOUNT}"
BACKOFF = BackoffConfig(base_s=1, factor=2, cap_s=60, max_consecutive=10)


async def link(tmp_path, venue=None):
    venue = venue or FakeVenue()
    log, buf = capture_logger()
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("access-1", "refresh-1", T0 + timedelta(days=20), T0, "trading"))
    fails = [0]

    async def connect(environment):                  # `fails[0]` connects are refused first
        if fails[0]:
            fails[0] -= 1
            raise ConnectionError("venue host down")
        return await venue.connect(environment)

    session = CTraderSession(environment="demo", binding=ACCOUNT, credentials=Credentials("cid", "sec"),
                             tokens=tokens, meter=RequestMeter(tmp_path / "v.db", KEY, budget=1000,
                                                               reserve=100, now=T0),
                             logger=log, connect=connect, now_fn=lambda: venue.clock,
                             rate_per_s=10_000, request_timeout_s=0.5)
    await session.start()
    VenueStore(tmp_path / "v.db", KEY).bind(T0, "10000.00", int(T0.timestamp() * 1000) - 60_000,
                                            "{}")                # the first attach's record (A6)
    specs = {"EUR_USD": spec_from("EUR_USD", "EURUSD", venue.symbols[1]),
             "USD_JPY": spec_from("USD_JPY", "USDJPY", venue.symbols[2])}
    face = CTraderExecutionFace(session, specs, descriptor(list(specs.values()), 0, frozenset({"fx"})),
                                VenueStore(tmp_path / "v.db", KEY), log, account_key=KEY,
                                now_fn=lambda: venue.clock, order_ack_timeout_s=2.0,
                                stop_confirm_timeout_s=0.0)
    face.start()
    session.mark_ready()
    feed = CTraderFeed(session, {1: ("EUR_USD", 5), 2: ("USD_JPY", 3)}, log, now_fn=lambda: venue.clock)
    delays: list[float] = []

    async def sleep(s: float) -> None:              # instant, but every delay is recorded
        delays.append(s)
        await asyncio.sleep(0)

    reconnector = Reconnector(session=session, face=face, feed=feed, backoff=BACKOFF, rng=Random(3),
                              logger=log, now_fn=lambda: venue.clock, sleep=sleep, poll_s=0.001)
    return venue, session, face, feed, reconnector, buf, delays, fails


async def until(condition, timeout: float = 2.0) -> None:
    async def wait():
        while not condition():
            await asyncio.sleep(0.001)
    await asyncio.wait_for(wait(), timeout)


async def test_a_dropped_link_comes_back_through_syncing_and_the_feed_resumes(tmp_path) -> None:
    venue, session, face, feed, rc, buf, delays, _ = await link(tmp_path)
    ticks = []

    async def consume():
        async for tick in feed.stream():
            ticks.append(tick)

    reader, task = asyncio.create_task(consume()), asyncio.create_task(rc.run())
    await until(lambda: 2127 in venue.requests and len(ticks) >= 2)       # both technical events
    old = venue.transport
    await old.close()                                                    # the socket dies
    await until(lambda: venue.transport is not old and session.state is LinkState.READY)
    sent = [m["payloadType"] for m in venue.transport.sent]
    assert sent[:3] == [PT.APPLICATION_AUTH_REQ, PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                        PT.ACCOUNT_AUTH_REQ]                             # re-authorised...
    assert sent.index(PT.RECONCILE_REQ) < sent.index(PT.SUBSCRIBE_SPOTS_REQ)   # ...synced, then fed
    assert events(buf, "FEED_RECONNECT") and events(buf, "VENUE_RECONNECTED")
    assert delays and 0 <= delays[0] <= 1                                # attempt 0: uniform(0, 1)
    before = len(ticks)
    venue.spot(1, both=True)
    await until(lambda: len(ticks) > before)                             # the same stream goes on
    for t in (reader, task):
        t.cancel()
    await session.stop()


async def test_a_stop_that_fires_while_down_reaches_risk_once_after_the_reconnect(tmp_path) -> None:
    venue, session, face, feed, rc, buf, _, _ = await link(tmp_path)
    await face.submit_order(fragment_id="f1", order_id="o1", instrument="EUR_USD", direction=1,
                            units=Decimal("1000"), requested_price=1.10, ioc=True, now=T0,
                            session_id="s", stop_loss=1.09)
    task = asyncio.create_task(rc.run())
    await venue.transport.close()                                        # the socket dies, and...
    venue.advance(60)
    venue.fire_stop(next(iter(venue.positions)), 1.0885)                 # ...its event is never read
    await until(lambda: session.state is LinkState.READY and events(buf, "VENUE_RECONNECTED"))
    fill = await asyncio.wait_for(anext(face.venue_fills()), 1)
    assert (fill.instrument, fill.direction, fill.fill_price) == ("EUR_USD", -1, 1.0885)
    assert fill.order_id.startswith("venue:")
    assert face.router.unsolicited.empty()                               # once, never twice
    task.cancel()
    await session.stop()


async def test_a_stop_reported_live_is_not_reported_again_by_the_reconnect(tmp_path) -> None:
    venue, session, face, feed, rc, buf, _, _ = await link(tmp_path)
    await face.submit_order(fragment_id="f1", order_id="o1", instrument="EUR_USD", direction=1,
                            units=Decimal("1000"), requested_price=1.10, ioc=True, now=T0,
                            session_id="s", stop_loss=1.09)
    venue.advance(60)
    venue.fire_stop(next(iter(venue.positions)), 1.0885)                 # while connected
    live = await asyncio.wait_for(anext(face.venue_fills()), 1)
    task = asyncio.create_task(rc.run())
    await venue.transport.close()
    await until(lambda: session.state is LinkState.READY and events(buf, "VENUE_RECONNECTED"))
    assert live.fill_price == 1.0885 and face.router.unsolicited.empty()   # the deal is known
    task.cancel()
    await session.stop()


async def test_failures_back_off_with_full_jitter_and_raise_unreachable_once(tmp_path) -> None:
    venue, session, face, feed, rc, buf, delays, fails = await link(tmp_path)
    task = asyncio.create_task(rc.run())
    fails[0] = 12                                                        # 12 refused connects
    await venue.transport.close()
    await until(lambda: session.state is LinkState.READY and events(buf, "VENUE_RECONNECTED"))
    assert len(delays) >= 13
    for attempt, delay in enumerate(delays[:13]):
        assert 0 <= delay <= min(60, 2 ** attempt)
    assert len(events(buf, "VENUE_UNREACHABLE")) == 1                    # a health event, once
    assert not events(buf, "HALT_APPLIED")                               # never a halt by itself
    task.cancel()
    await session.stop()


async def test_a_maintenance_window_is_slept_through_to_its_end(tmp_path) -> None:
    venue, session, face, feed, rc, buf, delays, _ = await link(tmp_path)
    original, first = venue._on_application_auth_req, [True]

    async def maintenance(p, mid, t):
        if first[0]:
            first[0] = False
            t.push(PT.OA_ERROR_RES, {"errorCode": "SERVER_IS_UNDER_MAINTENANCE",
                                     "maintenanceEndTimestamp": venue.ms() // 1000 + 3_600}, mid)   # SECONDS on
            # ProtoOAErrorRes, per the pinned proto (GAP-P12D-132 TAE-06; this test once sent ms)
            return
        await original(p, mid, t)

    venue._on_application_auth_req = maintenance
    task = asyncio.create_task(rc.run())
    await venue.transport.close()
    await until(lambda: session.state is LinkState.READY and events(buf, "VENUE_RECONNECTED"))
    assert delays[1] >= 3600                                             # slept to the stated end
    assert events(buf, "VENUE_MAINTENANCE")
    task.cancel()
    await session.stop()


async def test_a_grant_lost_while_down_detaches_and_ends_the_task(tmp_path) -> None:
    venue, session, face, feed, rc, buf, _, _ = await link(tmp_path)
    task = asyncio.create_task(rc.run())
    venue.scope = 0                                                      # the grant is view-only now
    await venue.transport.close()
    await asyncio.wait_for(task, 2)                                      # the task ENDS (a stall)
    assert session.state is LinkState.DETACHED
    assert events(buf, "VENUE_RECONNECT_ABANDONED")
    assert PT.NEW_ORDER_REQ not in venue.requests
