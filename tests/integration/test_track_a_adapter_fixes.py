"""Regression tests for the Track A dual audit's adapter findings (GAP-P12D-132), against the fake
venue. Each names the finding it pins; each fails on the code the audit read (`86ea8d3`)."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal

import pytest

from core.data.ctrader.link import AuthRefused, LinkState
from core.data.ctrader.meter import BudgetRefused, RequestMeter
from core.data.ctrader.pacing import Pacer
from core.data.ctrader.schema import PT
from core.data.ctrader.wire import LinkClock, decode, error_of
from core.execution import ctrader_sync as sync
from core.execution.ctrader_orders import broker_positions
from core.execution.venue import BrokerPosition, FillStatus
from tests.ctrader_fixtures import ACCOUNT, FakeVenue, events
from tests.integration.test_adapter_conformance import _order, _orchestrator
from tests.integration.test_ctrader_adapter import _face, _open, _session
from tests.integration.test_ctrader_reconnect import link, until


def pad(session, venue, until_used: int) -> None:
    """Spend the budget down to `until_used` requests (the meter's persisted log)."""
    while session.budget()["used_24h"] < until_used:
        session._meter.record(0, "query", "pad", venue.clock)


# -- TAI-01: closes still reach the venue in the close reserve ---------------------------- #

async def test_a_close_through_the_orchestrator_reaches_the_venue_in_the_close_reserve(tmp_path) -> None:
    venue, session, face, buf = await _face(tmp_path, budget=40, reserve=10)
    orch, _ = _orchestrator(face, tmp_path, now=venue.clock)
    (opened,) = await orch.submit(_order(1000), valid_for_seconds=300)
    assert opened.status is FillStatus.FILLED
    pad(session, venue, 30)                                          # in the reserve: 30 ≥ 40 − 10
    refused = await orch.submit(_order(1000, order_id="o-two"), valid_for_seconds=300)
    assert all(r.filled_units == 0 for r in refused)                 # opens stop in the reserve
    reports = await orch.submit(_order(1000, action="close", order_id="o-close"), valid_for_seconds=300)
    assert sum(r.filled_units for r in reports) == Decimal("1000")   # ...but the exit leaves
    assert venue.positions == {} and PT.CLOSE_POSITION_REQ in venue.requests
    await session.stop()


# -- TAI-04 / TAE-10: a stop the venue will not rest ------------------------------------- #

async def test_a_refused_stop_amend_closes_the_position_and_still_reports_the_fill(tmp_path) -> None:
    venue = FakeVenue()
    venue.behaviour, venue.amend_error = ["no_stop"], "TRADING_BAD_STOPS"
    _, session, face, buf = await _face(tmp_path, venue)
    report = await _open(face)                                       # no exception escapes
    assert report.status is FillStatus.FILLED and report.filled_units == Decimal("1000")
    assert venue.positions == {}                                     # never left unprotected
    assert events(buf, "VENUE_STOP_MISSING")[-1]["closed"] is True
    assert not events(buf, "VENUE_STOP_AMENDED")                     # never logged unverified
    await session.stop()


async def test_a_stop_that_can_be_neither_rested_nor_closed_is_reported_critical(tmp_path) -> None:
    venue = FakeVenue()
    venue.behaviour, venue.amend_error, venue.close_error = ["no_stop"], "TRADING_BAD_STOPS", "POSITION_LOCKED"
    _, session, face, buf = await _face(tmp_path, venue)
    report = await _open(face)
    assert report.filled_units == Decimal("1000")                    # Risk still hears the fill
    missing = events(buf, "VENUE_STOP_MISSING")[-1]
    assert missing["closed"] is False and missing["severity"] == "critical"
    (held,) = await face.open_positions()
    assert held.stop_loss is None                                    # the runtime's check flattens it
    await session.stop()


# -- TAI-08: an ack timeout is searched, and its fill reported once ----------------------- #

async def test_an_ack_timeout_through_the_orchestrator_is_searched_and_reported_once(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path)
    face._ack = 0.2
    venue.drop_reply_once = True
    orch, _ = _orchestrator(face, tmp_path, now=venue.clock)
    reports = await orch.submit(_order(1000), valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.FILLED]        # found by search, not orphaned
    assert venue.requests.count(PT.NEW_ORDER_REQ) == 1               # never resent
    await session.stop()


# -- TAI-09: a close the venue refuses is a report, never an escaping error ---------------- #

async def test_a_close_the_venue_refuses_is_a_report_and_leaves_nothing_in_flight(tmp_path) -> None:
    venue, session, face, buf = await _face(tmp_path)
    await _open(face)
    venue.close_error = "POSITION_NOT_FOUND"                          # raced a stop, say
    report = await face.close_position(fragment_id="c1", order_id="oc", instrument="EUR_USD", direction=1,
                                       units=Decimal("1000"), requested_price=1.10, now=venue.clock,
                                       session_id="s")
    assert report.filled_units == 0 and events(buf, "VENUE_CLOSE_REFUSED")
    assert face._store.in_flight() == []                              # SYNCING claims nothing later
    await session.stop()


# -- TAI-12: nothing leaves a link that is not READY -------------------------------------- #

async def test_no_order_leaves_a_link_that_is_re_syncing(tmp_path) -> None:
    venue, session, face, buf = await _face(tmp_path)
    session._set(LinkState.SYNCING)
    opened = await _open(face)
    assert opened.status is FillStatus.REJECTED and PT.NEW_ORDER_REQ not in venue.requests
    assert events(buf, "VENUE_REFUSED")[-1]["reason"] == "VENUE_NOT_READY"
    session._set(LinkState.REAUTH)
    with pytest.raises(ConnectionError):
        await session.request(PT.RECONCILE_REQ, {}, req_class="query")   # only authorisation leaves
    await session.stop()


# -- TAE-02: an account session the venue ends is a full reconnect ------------------------- #

async def test_an_account_disconnect_is_a_full_reconnect_with_sync_and_spots(tmp_path) -> None:
    venue, session, face, feed, rc, buf, _, _ = await link(tmp_path)
    reader = asyncio.create_task(anext(feed.stream()))
    task = asyncio.create_task(rc.run())
    await until(lambda: PT.SUBSCRIBE_SPOTS_REQ in venue.requests)
    old = venue.transport
    old.push(PT.ACCOUNT_DISCONNECT_EVENT, {"ctidTraderAccountId": ACCOUNT})
    await until(lambda: venue.transport is not old and session.state is LinkState.READY
                and bool(events(buf, "VENUE_RECONNECTED")))
    sent = [m["payloadType"] for m in venue.transport.sent]
    assert PT.DEAL_LIST_REQ in sent and PT.SUBSCRIBE_SPOTS_REQ in sent   # re-synced, re-fed
    for t in (reader, task):
        t.cancel()
    await session.stop()


# -- TAE-09 / TAI-02: A3 authorisation — refusals detach, stale tokens refresh -------------- #

async def test_an_application_refused_on_reconnect_detaches_and_ends_the_task(tmp_path) -> None:
    venue, session, face, feed, rc, buf, _, _ = await link(tmp_path)

    async def refused(p, mid, t):
        t.push(PT.OA_ERROR_RES, {"errorCode": "CH_CLIENT_AUTH_FAILURE"}, mid)

    task = asyncio.create_task(rc.run())
    venue._on_application_auth_req = refused
    await venue.transport.close()
    await asyncio.wait_for(task, 2)                                  # it ENDS: never a forever loop
    assert session.state is LinkState.DETACHED
    assert venue.requests.count(PT.APPLICATION_AUTH_REQ) == 2         # the start, then one refusal


async def test_a_stale_token_at_the_grant_is_refreshed_once(tmp_path) -> None:
    venue = FakeVenue()
    original, first = venue._on_get_accounts_by_access_token_req, [True]

    async def stale_once(p, mid, t):
        if first[0]:
            first[0] = False
            t.push(PT.OA_ERROR_RES, {"errorCode": "CH_ACCESS_TOKEN_INVALID"}, mid)
            return
        await original(p, mid, t)

    venue._on_get_accounts_by_access_token_req = stale_once
    session, *_ = await _session(tmp_path, venue)
    await session.start()
    assert session.state is LinkState.SYNCING and PT.REFRESH_TOKEN_REQ in venue.requests
    await session.stop()


def test_the_budget_is_hard_for_authorisation_but_never_for_a_close(tmp_path) -> None:
    from datetime import datetime, timezone
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    meter = RequestMeter(tmp_path / "m.db", "k", budget=5, reserve=2, now=now)
    for _ in range(5):
        meter.record(0, "query", "x", now)
    with pytest.raises(BudgetRefused):
        meter.admit("auth", now)                                     # no loop spends past the cap
    meter.admit("close", now)                                        # an exit always may
    other = RequestMeter(tmp_path / "m.db", "k", budget=5, reserve=2, now=now)
    other.record(0, "query", "y", now)
    assert meter.used(now) == 6                                      # two processes, one count (TAI-11)


async def test_a_reconnect_in_the_close_reserve_waits_for_the_window_and_lives(tmp_path) -> None:
    venue, session, face, feed, rc, buf, delays, _ = await link(tmp_path)
    task = asyncio.create_task(rc.run())
    pad(session, venue, 950)                                         # budget 1000, reserve 100
    await venue.transport.close()
    await until(lambda: bool(events(buf, "VENUE_BUDGET_WAIT")))
    assert not task.done()                                           # waits; never a stall (TAI-02)
    assert any(d >= 900 for d in delays)
    task.cancel()
    await session.stop()


# -- TAE-07 / TAI-16: history paging is complete whatever the venue's order ------------------ #

@pytest.mark.parametrize("order", ["oldest", "newest"])
async def test_history_paging_is_complete_in_either_order(tmp_path, order) -> None:
    venue, session, face, _ = await _face(tmp_path)
    venue.page_rows, venue.page_order = 3, order
    t0 = venue.ms()
    for i, dt in enumerate([1, 2, 3, 3, 5, 8, 8, 9]):               # pairs sharing a page boundary's ms
        venue.deals.append({"dealId": 9000 + i, "orderId": 1, "positionId": 1, "executionTimestamp": t0 + dt})
    for i in range(6):
        venue.orders[7000 + i] = {"orderId": 7000 + i, "utcLastUpdateTimestamp": t0 + i, "clientOrderId": f"f{i}"}
    venue.advance(1)
    got = await sync.missed_deals(session, t0, venue.clock)
    assert sorted(d["dealId"] for d in got) == list(range(9000, 9008))
    venue.deals += [{"dealId": 9100 + i, "orderId": 1, "positionId": 1, "executionTimestamp": t0 + 4}
                    for i in range(4)]                               # more in one ms than a page holds:
    with pytest.raises(sync.SearchIncomplete):                       # unknown, never silently short
        await sync.missed_deals(session, t0, venue.clock)
    for wanted in ("f0", "f5"):                                       # the oldest and the newest
        found = await sync.find_order(session, lambda o, w=wanted: o.get("clientOrderId") == w,
                                      since=venue.clock, now=venue.clock)
        assert found is not None and found["clientOrderId"] == wanted
    await session.stop()


# -- TAE-08: one unknown enum never silences later fills ---------------------------------- #

async def test_an_unknown_event_enum_does_not_silence_later_venue_fills(tmp_path) -> None:
    venue, session, face, buf = await _face(tmp_path)
    await _open(face)
    venue.transport.push(PT.EXECUTION_EVENT, {"executionType": 13})    # not in the pinned proto
    venue.advance(60)
    venue.fire_stop(next(iter(venue.positions)), 1.0885)
    fill = await asyncio.wait_for(anext(face.venue_fills()), 2)
    assert fill.fill_price == 1.0885 and events(buf, "VENUE_EVENT_UNROUTABLE")
    await session.stop()


# -- TAE-06, TAE-13, TAE-11, TAE-03: the wire, the heartbeat, pacing, the declared cadences -- #

def test_maintenance_end_is_seconds_on_oa_error_res_and_milliseconds_on_error_res() -> None:
    oa = error_of(decode('{"payloadType": 2142, "payload": {"errorCode": "SERVER_IS_UNDER_MAINTENANCE", '
                         '"maintenanceEndTimestamp": 1800000000}}'))
    common = error_of(decode('{"payloadType": 50, "payload": {"errorCode": "SERVER_IS_UNDER_MAINTENANCE", '
                             '"maintenanceEndTimestamp": 1800000000000}}'))
    assert oa.maintenance_end_ms == common.maintenance_end_ms == 1_800_000_000_000


def test_the_heartbeat_goes_out_before_its_interval_ever_passes() -> None:
    clock = LinkClock(0.0, heartbeat_s=10, liveness_timeout_s=60)
    assert not clock.heartbeat_due(8.9) and clock.heartbeat_due(9.0)   # polled each 1 s: gap ≤ 10 s


async def test_history_requests_are_paced_below_the_documented_rate() -> None:
    pacer = Pacer(history_per_s=20, mono=time.monotonic)
    t0 = time.monotonic()
    await pacer.before(PT.RECONCILE_REQ)
    assert time.monotonic() - t0 < 0.02                              # not a history request
    for _ in range(3):
        await pacer.before(PT.DEAL_LIST_REQ)
    assert time.monotonic() - t0 >= 0.1                              # 3 history requests, 50 ms apart


def test_the_session_takes_the_declared_cadences(acis_config, tmp_path) -> None:
    from core.data.ctrader.session import Credentials, CTraderSession
    from core.data.ctrader.tokens import TokenStore
    from tests.ctrader_fixtures import T0
    v = acis_config.system.venue
    session = CTraderSession.from_venue(v, credentials=Credentials("c", "s"),
                                        tokens=TokenStore(tmp_path / "t.json"),
                                        meter=RequestMeter(tmp_path / "m.db", "k", budget=1000, reserve=100,
                                                           now=T0), logger=None)
    assert (session._hb, session._live_s) == (v.heartbeat_s, v.liveness_timeout_s) == (10, 60)
    assert session._gap == pytest.approx(1 / v.rate_limit_per_s.general)


# -- TAI-15: an adopted position is marked at the venue's entry price ----------------------- #

def test_an_adopted_position_carries_the_venues_entry_price_and_stop(acis_config) -> None:
    positions = [{"positionId": 1, "price": 150.2, "stopLoss": 151.0,
                  "tradeData": {"symbolId": 2, "volume": 100_000, "tradeSide": 2, "label": "L"}}]
    (pos,), _ = broker_positions(positions, {2: "USD_JPY"}, "L")
    assert (pos.entry_price, pos.stop_loss) == (150.2, 151.0)
    from datetime import datetime, timezone
    from tests.risk_fixtures import build_monitor, load_cfg
    from tests.integration.test_risk_pipeline import GovernorHaltSink, PaperBook
    from tests.unit.test_governor import mk_governor
    mon, *_ = build_monitor(load_cfg(), GovernorHaltSink(mk_governor()[0], None, PaperBook()))
    mon.reconcile_on_restart((pos,), datetime(2026, 9, 30, tzinfo=timezone.utc))
    (adopted,) = mon.positions()
    assert (adopted.avg_entry_price, adopted.stop_loss) == (150.2, 151.0)    # never a 1.0 placeholder


# -- GAP-P12D-132 D1 (owner ruling): A9 counts the measured 4 requests a round trip ------------ #

def test_the_order_allowance_counts_four_requests_a_round_trip(acis_config) -> None:
    from core.execution.ctrader_attach import feasible
    v = acis_config.system.venue
    assert v.max_orders_per_day == 35 and feasible(v, 900) is None      # 760 + 4 × 35 = 900
    assert "projected" in feasible(v.model_copy(update={"max_orders_per_day": 36}), 900)
    with pytest.raises(ValueError):                                     # 4 × 226 > 1000 − 100
        type(v).model_validate({**v.model_dump(), "max_orders_per_day": 226})


# -- GAP-P12D-132 D3 (owner ruling): the sent stop is widened by the live spread ---------------- #

async def test_the_sent_stop_is_widened_by_the_live_spread(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path)
    face._spread_of = lambda instrument: Decimal("0.00012")
    await _open(face, stop=1.09)                                        # the Governor's distance 0.01
    (order,) = [m["payload"] for m in venue.transport.sent if m["payloadType"] == PT.NEW_ORDER_REQ]
    assert order["relativeStopLoss"] == 1012                            # (0.01 + 0.00012) × 100 000
    await session.stop()


async def test_no_live_quote_means_no_open(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path)
    face._spread_of = lambda instrument: None
    report = await _open(face)
    assert report.filled_units == 0 and PT.NEW_ORDER_REQ not in venue.requests
    await session.stop()
