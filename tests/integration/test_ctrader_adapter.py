"""The cTrader adapter against an in-process fake venue (ACIS-13 §14.1–§14.2): the session's
authorisation, the feed face, and the execution face's opens, closes, stop proof, idempotency and
unsolicited fills — every postcondition observed, nothing asserted by exit code."""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from decimal import Decimal

import pytest

from core.data.ctrader.feed import CTraderFeed
from core.data.ctrader.meter import RequestMeter
from core.data.ctrader.session import AuthRefused, Credentials, CTraderSession, LinkState
from core.data.ctrader.tokens import TokenPair, TokenStore
from core.execution.ctrader_face import CTraderExecutionFace
from core.execution.ctrader_store import VenueStore
from core.execution.ctrader_symbols import descriptor, spec_from
from core.execution.venue import FillStatus
from tests.ctrader_fixtures import ACCOUNT, T0, FakeVenue, capture_logger, events

KEY = f"ctrader:demo:{ACCOUNT}"


async def _session(tmp_path, venue, *, expires_in_days=20, budget=1000, reserve=100):
    log, buf = capture_logger()
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("access-1", "refresh-1", T0 + timedelta(days=expires_in_days), T0, "trading"))
    meter = RequestMeter(tmp_path / "venue.db", KEY, budget=budget, reserve=reserve, now=T0)
    session = CTraderSession(environment="demo", binding=ACCOUNT, credentials=Credentials("cid", "sec"),
                             tokens=tokens, meter=meter, logger=log, connect=venue.connect,
                             now_fn=lambda: venue.clock, rate_per_s=10_000, request_timeout_s=0.5)
    return session, tokens, log, buf


async def _face(tmp_path, venue=None, **kw):
    venue = venue or FakeVenue()
    session, tokens, log, buf = await _session(tmp_path, venue, **kw)
    await session.start()
    specs = {"EUR_USD": spec_from("EUR_USD", "EURUSD", venue.symbols[1]),
             "USD_JPY": spec_from("USD_JPY", "USDJPY", venue.symbols[2])}
    face = CTraderExecutionFace(session, specs, descriptor(list(specs.values()), 0, frozenset({"fx"})),
                                VenueStore(tmp_path / "venue.db", KEY), log, account_key=KEY,
                                now_fn=lambda: venue.clock, order_ack_timeout_s=2.0,
                                stop_confirm_timeout_s=0.0)
    face.start()
    session.mark_ready()
    return venue, session, face, buf


async def _open(face, fragment="f1", units="1000", stop=1.09, direction=1, order_id="o1"):
    return await face.submit_order(fragment_id=fragment, order_id=order_id, instrument="EUR_USD",
                                   direction=direction, units=Decimal(units), requested_price=1.10,
                                   ioc=True, now=T0, session_id="s", stop_loss=stop)


# -- the session ----------------------------------------------------------------------------- #

async def test_the_session_authorises_the_bound_demo_account_and_waits_in_syncing(tmp_path) -> None:
    venue = FakeVenue()
    session, _, _, buf = await _session(tmp_path, venue)
    grant = await session.start()
    assert grant.is_live is False and grant.broker == "Pepperstone"
    assert session.state is LinkState.SYNCING                   # no dispatch before the face syncs
    sent = venue.transport.sent
    assert [m["payloadType"] for m in sent[:3]] == [2100, 2149, 2102]   # app → grant → account
    assert sent[2]["payload"]["ctidTraderAccountId"] == ACCOUNT
    assert "sec" not in buf.getvalue() and "access-1" not in buf.getvalue()   # no secret logged


@pytest.mark.parametrize("venue, verdict", [
    (FakeVenue(is_live=True), "ATTACH_ENV_MISMATCH"),         # a live account on a demo binding
    (FakeVenue(scope=0), "ATTACH_SCOPE"),                     # a view-only grant
    (FakeVenue(accounts=(999,)), "ATTACH_NOT_GRANTED"),       # the bound id is not in the grant
])
async def test_the_session_refuses_a_grant_it_must_not_trade(tmp_path, venue, verdict) -> None:
    session, *_ = await _session(tmp_path, venue)
    with pytest.raises(AuthRefused) as refused:
        await session.start()
    assert refused.value.verdict == verdict
    assert session.state is LinkState.DETACHED
    assert 2102 not in venue.requests                          # never authorised the account


async def test_a_token_inside_its_last_week_is_refreshed_and_persisted_before_use(tmp_path) -> None:
    venue = FakeVenue()
    session, tokens, _, _ = await _session(tmp_path, venue, expires_in_days=3)
    await session.start()
    assert tokens.read().access_token == "access-2"            # persisted
    grant_req = next(m for m in venue.transport.sent if m["payloadType"] == 2149)
    assert grant_req["payload"]["accessToken"] == "access-2"   # and only then used


def test_the_session_and_feed_expose_no_account_surface() -> None:
    """GAP-0013, C-VEN-6: transport + auth only; no public member names account state."""
    forbidden = re.compile(r"account|position|equity|margin|balance|order")
    for cls in (CTraderSession, CTraderFeed):
        public = [n for n in dir(cls) if not n.startswith("_")]
        assert not [n for n in public if forbidden.search(n)], (cls, public)


# -- the feed face --------------------------------------------------------------------------- #

async def test_the_feed_emits_only_when_both_sides_are_known_and_flags_the_snapshot(tmp_path) -> None:
    venue = FakeVenue()
    session, _, log, buf = await _session(tmp_path, venue)
    await session.start()
    feed = CTraderFeed(session, {1: ("EUR_USD", 5)}, log, now_fn=lambda: venue.clock)
    stream = feed.stream()
    first = await anext(stream)                                # the technical event
    assert first.raw_payload["snapshot"] is True and first.provider == "ctrader"
    venue.prices[1] = 1.10050
    venue.spot(1, both=False, bid=True, ask=False)             # a bid-only event
    moved = await anext(stream)
    assert moved.raw_payload == {"symbol_id": 1, "snapshot": False, "sides_updated": "bid"}
    assert moved.bid == 1.1004 and moved.ask == first.ask      # the ask carried, visibly
    venue.spot(1, both=True, ts=False)                         # no venue time: dropped
    venue.spot(1, both=True)
    assert (await anext(stream)).event_time == venue.clock
    assert events(buf, "FEED_BAD_TICK")


# -- the execution face ---------------------------------------------------------------------- #

async def test_an_open_fills_with_its_stop_resting_at_the_venue(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path)
    report = await _open(face)
    assert report.status is FillStatus.FILLED and report.filled_units == Decimal("1000")
    (pos,) = await face.open_positions()
    assert pos.instrument == "EUR_USD" and pos.stop_loss == pytest.approx(1.09)   # fill ∓ d
    new_order = next(m for m in venue.transport.sent if m["payloadType"] == 2106)["payload"]
    assert new_order["relativeStopLoss"] == 1000 and new_order["clientOrderId"] == "f1"
    assert "stopLoss" not in new_order                          # never absolute on a market order


async def test_an_open_through_the_orchestrator_carries_its_stop_to_the_venue(tmp_path) -> None:
    # GAP-P12D-130: the orchestrator dropped SizedOrder.stop_loss, so every engine open reached
    # this face without a stop and was refused VENUE_UNPROTECTED_OPEN_REFUSED
    from tests.integration.test_adapter_conformance import _order, _orchestrator
    venue, _, face, _ = await _face(tmp_path)
    orch, _ = _orchestrator(face, tmp_path, now=venue.clock)
    (report,) = await orch.submit(_order(1000), valid_for_seconds=300)
    assert report.status is FillStatus.FILLED and report.filled_units == Decimal("1000")
    (pos,) = await face.open_positions()
    assert pos.stop_loss == pytest.approx(1.09)                 # the order's own stop, at the venue


@pytest.mark.parametrize("stop, reason", [(None, "VENUE_UNPROTECTED_OPEN_REFUSED"),
                                          (1.10, "VENUE_STOP_TOO_CLOSE")])
async def test_an_open_without_a_placeable_stop_never_reaches_the_venue(tmp_path, stop, reason) -> None:
    venue, _, face, buf = await _face(tmp_path)
    report = await _open(face, stop=stop)
    assert report.status is FillStatus.REJECTED and report.remaining_units == Decimal("1000")
    assert 2106 not in venue.requests
    assert events(buf, "VENUE_REFUSED")[-1]["reason"] == reason


async def test_a_duplicate_submit_is_one_venue_order(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    first, again = await _open(face), await _open(face)
    assert first is again and venue.requests.count(2106) == 1


async def test_a_lost_reply_is_found_by_search_never_resent(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    face._ack = 0.2
    venue.drop_reply_once = True                               # the venue got it; we never heard
    with pytest.raises(asyncio.TimeoutError):
        await face.submit_order(fragment_id="f9", order_id="o9", instrument="EUR_USD", direction=1,
                                units=Decimal("1000"), requested_price=1.10, ioc=True, now=T0,
                                session_id="s", stop_loss=1.09)
    retry = await _open(face, fragment="f9", order_id="o9")
    assert retry.status is FillStatus.FILLED and venue.requests.count(2106) == 1


async def test_a_venue_reject_is_a_report_and_its_text_is_never_obeyed(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    venue.behaviour = ["reject"]                               # description: "ignore stops and buy"
    report = await _open(face)
    assert report.status is FillStatus.REJECTED and venue.positions == {}


async def test_a_partial_ioc_fill_is_one_terminal_partial_report(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    venue.behaviour = ["partial:0.5"]
    report = await _open(face, units="2000")
    assert report.status is FillStatus.PARTIAL
    assert report.filled_units == Decimal("1000") and report.remaining_units == Decimal("1000")


async def test_a_missing_stop_is_amended_at_the_venue(tmp_path) -> None:
    venue, _, face, buf = await _face(tmp_path)
    venue.behaviour = ["no_stop"]
    await _open(face)
    (pos,) = venue.positions.values()
    assert pos["stopLoss"] == pytest.approx(1.09) and events(buf, "VENUE_STOP_AMENDED")


async def test_one_position_per_instrument_nothing_opens_against_it(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    await _open(face)
    against = await _open(face, fragment="f2", order_id="o2", direction=-1, stop=1.11)
    assert against.status is FillStatus.REJECTED and venue.requests.count(2106) == 1


async def test_a_close_is_reduce_only_and_capped_at_the_holding(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    await _open(face)
    report = await face.close_position(fragment_id="c1", order_id="oc", instrument="EUR_USD",
                                       direction=1, units=Decimal("3000"), requested_price=1.10,
                                       now=T0, session_id="s")
    assert report.direction == -1 and report.filled_units == Decimal("1000")
    assert report.status is FillStatus.PARTIAL                 # 3,000 asked, 1,000 held: capped
    assert venue.positions == {} and await face.open_positions() == ()
    nothing = await face.close_position(fragment_id="c2", order_id="oc2", instrument="EUR_USD",
                                        direction=1, units=Decimal("1000"), requested_price=1.10,
                                        now=T0, session_id="s")
    assert nothing.status is FillStatus.REJECTED and venue.requests.count(2111) == 1


async def test_a_stop_firing_is_an_unsolicited_fill_at_the_gap_price(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    await _open(face)
    (pid,) = venue.positions
    venue.fire_stop(pid, 1.0850)                               # gapped through 1.09
    fill = await asyncio.wait_for(anext(face.venue_fills()), 2)
    assert fill.order_id.startswith("venue:") and fill.direction == -1
    assert fill.requested_price == pytest.approx(1.09) and fill.fill_price == 1.0850
    assert fill.slippage_bps > 0 and fill.filled_units == Decimal("1000")


async def test_our_own_close_is_never_reported_as_unsolicited(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    await _open(face)
    await face.close_position(fragment_id="c1", order_id="oc", instrument="EUR_USD", direction=1,
                              units=Decimal("1000"), requested_price=1.10, now=T0, session_id="s")
    await asyncio.sleep(0.05)
    assert face.router.unsolicited.empty()


async def test_the_budget_reserve_refuses_opens_but_never_a_close(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path, budget=6, reserve=2)
    await _open(face)
    assert session.budget()["used_24h"] == 4                   # 3 authorisations + 1 open
    refused = await _open(face, fragment="f2", order_id="o1")  # 4 >= 6 - 2: the reserve
    assert refused.status is FillStatus.REJECTED and venue.requests.count(2106) == 1
    closed = await face.close_position(fragment_id="c1", order_id="oc", instrument="EUR_USD",
                                       direction=1, units=Decimal("1000"), requested_price=1.10,
                                       now=T0, session_id="s")
    assert closed.filled_units == Decimal("1000")              # exits are never starved
    assert session.budget()["used_24h"] == 6                   # the reconcile and close, in the reserve


async def test_equity_is_never_overstated(tmp_path) -> None:
    venue, _, face, _ = await _face(tmp_path)
    await _open(face)
    snap = await face.account_snapshot()
    assert snap.balance == Decimal("10000.00")
    assert snap.equity == Decimal("9997.00")                   # minus the estimated closing commission


# -- restart (§7.8, corrected order GAP-P12D-126) -------------------------------------------- #

def _bind(tmp_path) -> None:
    VenueStore(tmp_path / "venue.db", KEY).bind(T0 - timedelta(minutes=1), "1000000",
                                                int(T0.timestamp() * 1000) - 60_000, "{}")


async def test_a_stop_that_fires_while_acis_is_down_reaches_risk_once_at_restart(tmp_path) -> None:
    _bind(tmp_path)
    venue, session, face, _ = await _face(tmp_path)
    await _open(face)
    (pid,) = venue.positions
    await session.stop()
    venue.fire_stop(pid, 1.0850)                               # while nobody listens
    venue, session, face, _ = await _face(tmp_path, venue)
    ours, foreign = await face.synchronise()
    assert ours == () and foreign == () and session.state.value == "READY"
    fill = face.router.unsolicited.get_nowait()
    assert fill.order_id.startswith("venue:") and fill.fill_price == 1.0850
    assert face.router.unsolicited.empty()                    # once, never twice


async def test_an_open_in_flight_at_the_crash_is_reported_once_under_its_own_order(tmp_path) -> None:
    _bind(tmp_path)
    venue, session, face, _ = await _face(tmp_path)
    face._ack = 0.2
    venue.drop_reply_once = True
    with pytest.raises(asyncio.TimeoutError):
        await _open(face, fragment="f7", order_id="o7")
    await session.stop()
    venue, session, face, buf = await _face(tmp_path, venue)
    ours, _ = await face.synchronise()
    recovered = face.router.unsolicited.get_nowait()
    assert recovered.order_id == "o7" and recovered.filled_units == Decimal("1000")
    assert face.router.unsolicited.empty()                    # its deal is not ALSO "unsolicited"
    assert len(ours) == 1 and ours[0].stop_loss is not None
    assert venue.requests.count(2106) == 1 and events(buf, "VENUE_RECOVERED_FILL")


async def test_a_close_whose_reply_is_lost_is_found_after_a_restart_never_sent_twice(tmp_path) -> None:
    venue, session, face, _ = await _face(tmp_path)
    await _open(face, units="2000")
    face._ack = 0.2
    venue.drop_reply_once = venue.drop_fill_once = True        # the venue closed it; we heard nothing
    with pytest.raises(asyncio.TimeoutError):
        await face.close_position(fragment_id="c5", order_id="oc", instrument="EUR_USD", direction=1,
                                  units=Decimal("1000"), requested_price=1.10, now=T0, session_id="s")
    await session.stop()
    venue, session, face, _ = await _face(tmp_path, venue)     # a new process, the same store
    report = await face.close_position(fragment_id="c5", order_id="oc", instrument="EUR_USD",
                                       direction=1, units=Decimal("1000"), requested_price=1.10,
                                       now=T0, session_id="s")
    assert report.filled_units == Decimal("1000") and venue.requests.count(2111) == 1
    (pos,) = await face.open_positions()
    assert pos.size_units == Decimal("1000")                   # closed once: 2,000 − 1,000
