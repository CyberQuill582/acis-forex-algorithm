"""The cTrader adapter's pure rules (ACIS-13 §14.1): the wire envelope and clocks, the pinned schema,
the request budget, the token store, order arithmetic, symbols and the equity derivation."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.data.ctrader import schema as s
from core.data.ctrader.meter import BudgetRefused, RequestMeter
from core.data.ctrader.tokens import TokenPair, TokenStore, pair_from_refresh
from core.data.ctrader.wire import Correlator, LinkClock, VenueError, decode, encode
from core.data.errors import DataQualityError
from core.execution.ctrader_account import derive
from core.execution.ctrader_orders import (broker_positions, fill_report, label, protocol_volume,
                                           quantize, relative_stop, unsolicited_report)
from core.execution.ctrader_symbols import (AttachFatal, cross_check, descriptor, match_symbols,
                                            spec_from)
from core.execution.venue import FillStatus
from tests.ctrader_fixtures import EURUSD, USDJPY, full_symbol

T0 = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
EU = spec_from("EUR_USD", "EURUSD", full_symbol(EURUSD, 5))
JY = spec_from("USD_JPY", "USDJPY", full_symbol(USDJPY, 3))


class _Log:
    def __init__(self) -> None:
        self.seen: list[tuple[str, dict]] = []

    def event(self, event_type: str, **data) -> None:
        self.seen.append((event_type, data))


# -- wire and schema ------------------------------------------------------------------------- #

def test_the_envelope_round_trips_and_a_bad_frame_is_refused() -> None:
    frame = decode(encode(s.PT.NEW_ORDER_REQ, {"volume": 100_000}, "m-1").encode("utf-8"))  # binary too
    assert (frame.payload_type, frame.payload, frame.client_msg_id) == (2106, {"volume": 100_000}, "m-1")
    for bad in ('{"payload": {}}', '{"payloadType": "2106"}', "not json", '{"payloadType": 1, "payload": []}'):
        with pytest.raises(DataQualityError):
            decode(bad)


async def test_a_reply_resolves_only_its_request_and_an_error_reply_raises() -> None:
    corr = Correlator("t")
    mid, future = corr.open()
    assert corr.resolve(decode(encode(s.PT.OA_ERROR_RES, {"errorCode": "MARKET_CLOSED"}, mid)))
    with pytest.raises(VenueError) as err:
        await future
    assert err.value.code == "MARKET_CLOSED"
    assert not corr.resolve(decode(encode(s.PT.SPOT_EVENT, {}, "unknown")))   # an event, not a reply
    mid2, waiter = corr.open()
    corr.fail_all(ConnectionError("down"))
    with pytest.raises(ConnectionError):
        await asyncio.wait_for(waiter, 1)


def test_the_heartbeat_is_the_strictest_source_and_liveness_is_bounded() -> None:
    with pytest.raises(DataQualityError):
        LinkClock(0.0, heartbeat_s=20, liveness_timeout_s=30)        # the SDK's 20 s is refused
    clock = LinkClock(0.0, heartbeat_s=10, liveness_timeout_s=30)
    assert not clock.heartbeat_due(8.9) and clock.heartbeat_due(9.0)   # one poll early (TAE-13)
    clock.received(25.0)
    assert not clock.dead(54.9) and clock.dead(55.0)


def test_an_enum_decodes_by_value_or_name_and_an_omitted_field_reads_its_proto_default() -> None:
    assert s.enum_value(s.TradeSide, 2) is s.enum_value(s.TradeSide, "SELL") is s.TradeSide.SELL
    with pytest.raises(DataQualityError):
        s.enum_value(s.TradeSide, "SIDEWAYS")
    assert s.field({}, "isLive") is False                              # absent: demo, never live
    assert s.field({}, "permissionScope") is s.PermissionScope.SCOPE_VIEW
    with pytest.raises(DataQualityError):
        s.field({}, "balance")                                         # no default: required
    assert (s.PT.NEW_ORDER_REQ, s.PT.SPOT_EVENT, s.PT.REFRESH_TOKEN_REQ) == (2106, 2131, 2173)


# -- the budget and the tokens --------------------------------------------------------------- #

def test_the_budget_refuses_opens_in_the_reserve_and_never_an_exit(tmp_path) -> None:
    meter = RequestMeter(tmp_path / "v.db", "k", budget=4, reserve=2, now=T0)
    for i in range(2):
        meter.admit("open", T0)
        meter.record(2106, "open", f"m{i}", T0)
    with pytest.raises(BudgetRefused, match="OPEN_EXHAUSTED"):
        meter.admit("open", T0)
    for i in range(3):                                                 # into, and past, the cap
        meter.admit("close", T0)
        meter.record(2111, "close", f"c{i}", T0)
    with pytest.raises(BudgetRefused, match="VENUE_BUDGET_EXHAUSTED"):
        meter.admit("query", T0)
    meter.admit("protect", T0)
    assert RequestMeter(tmp_path / "v.db", "k", budget=4, reserve=2, now=T0).used(T0) == 5  # restart
    assert meter.used(T0 + timedelta(hours=24, seconds=1)) == 0                           # rolling
    with pytest.raises(DataQualityError):
        RequestMeter(tmp_path / "w.db", "k", budget=1001, reserve=100, now=T0)


def test_the_token_store_rotates_atomically_and_never_prints_a_token(tmp_path) -> None:
    store = TokenStore(tmp_path / "t.json")
    pair = TokenPair("a-secret", "r-secret", T0 + timedelta(days=30), T0, "trading")
    store.write(pair)
    assert store.read() == pair and "secret" not in repr(pair)
    assert not pair.needs_refresh(T0) and pair.needs_refresh(T0 + timedelta(days=23))
    new = pair_from_refresh({"accessToken": "a2", "refreshToken": "r2", "expiresIn": 60}, T0, pair)
    assert new.scope == "trading" and new.expires_at == T0 + timedelta(seconds=60)
    assert not (tmp_path / "t.json.tmp").exists()


# -- order arithmetic ------------------------------------------------------------------------ #

def test_volumes_are_exact_and_round_down_never_up() -> None:
    assert protocol_volume(Decimal("1000")) == 100_000
    with pytest.raises(DataQualityError):
        protocol_volume(Decimal("0.001"))
    assert quantize(EU, Decimal("2999")) == Decimal("2000")            # down to the step
    assert quantize(EU, Decimal("999")) == 0                           # below the minimum: not placeable


def test_the_relative_stop_is_the_sized_distance_rounded_down_to_the_tick() -> None:
    assert relative_stop(EU, 1.10000, 1.08995, 1) == 1005               # d = 0.01005, on the tick
    assert relative_stop(EU, 1.10000, 1.089953, 1) == 1004              # 0.010047 → DOWN to 0.01004
    assert relative_stop(JY, 150.000, 150.500, -1) == 50_000            # 3 digits: a multiple of 100
    assert relative_stop(EU, 1.1, 1.1, 1) is None                       # d = 0: too close
    with pytest.raises(DataQualityError):
        relative_stop(EU, 1.10, 1.11, 1)                                # a long's stop above the entry


def test_one_venue_order_is_one_report_by_its_deals() -> None:
    deals = [{"filledVolume": 100_000, "executionPrice": 1.1, "executionTimestamp": 1_000},
             {"filledVolume": 100_000, "executionPrice": 1.2, "executionTimestamp": 2_000}]
    kw = dict(fill_id="x", order_id="o", fragment_id="f", instrument="EUR_USD", direction=1,
              requested_price=1.1, session_id="s", now=T0)
    full = fill_report(deals, requested_units=Decimal("2000"), cancelled=False, **kw)
    assert full.status is FillStatus.FILLED and full.fill_price == pytest.approx(1.15)
    part = fill_report(deals[:1], requested_units=Decimal("2000"), cancelled=True, **kw)
    assert part.status is FillStatus.PARTIAL and part.remaining_units == Decimal("1000")
    assert fill_report((), requested_units=Decimal("1"), cancelled=True, **kw).status is FillStatus.CANCELLED
    assert fill_report((), requested_units=Decimal("1"), cancelled=False, **kw).status is FillStatus.REJECTED


def test_positions_sum_per_instrument_and_an_unprotected_one_hides_no_stop() -> None:
    mine, other = label("k"), "someone"
    pos = lambda pid, vol, stop, lab=mine: {"positionId": pid, "stopLoss": stop, "tradeData": {  # noqa: E731
        "symbolId": 1, "volume": vol, "tradeSide": 1, "label": lab}}
    ours, foreign = broker_positions([pos(1, 100_000, 1.09), pos(2, 100_000, 1.08), pos(3, 5, 1.0, other)],
                                     {1: "EUR_USD"}, mine)
    assert ours[0].size_units == Decimal("2000") and ours[0].stop_loss == 1.08   # the worst case
    assert len(foreign) == 1
    unprotected, _ = broker_positions([pos(1, 100_000, 1.09), pos(2, 100_000, None)], {1: "EUR_USD"}, mine)
    assert unprotected[0].stop_loss is None


def test_an_unsolicited_deal_reports_the_gap_through_the_stop() -> None:
    deal = {"dealId": 9, "orderId": 7, "positionId": 3, "volume": 100_000, "filledVolume": 100_000,
            "executionPrice": 1.085, "executionTimestamp": 1_000, "tradeSide": "SELL"}
    fill = unsolicited_report(deal, account_key="k", instrument="EUR_USD", stop_price=1.09)
    assert (fill.order_id, fill.fragment_id, fill.direction) == ("venue:7", "venue:9", -1)
    assert fill.slippage_bps == pytest.approx((1.085 - 1.09) / 1.09 * 1e4 * -1)


# -- symbols and the account ----------------------------------------------------------------- #

def test_symbols_match_exactly_and_a_suffix_is_never_merged() -> None:
    light = [EURUSD, {**EURUSD, "symbolId": 9, "symbolName": "EURUSD.pro"}]
    assert match_symbols(light, {"EUR_USD": "EURUSD"}) == {"EUR_USD": 1}
    with pytest.raises(AttachFatal):
        match_symbols(light, {"EUR_USD": "EURUSD.raw"})
    with pytest.raises(AttachFatal):
        match_symbols([{**EURUSD, "enabled": False}], {"EUR_USD": "EURUSD"})


def test_the_contract_cross_check_refuses_a_stricter_or_different_venue(acis_config) -> None:
    meta, log = acis_config.instruments.instruments["EUR_USD"], _Log()
    cross_check(EU, meta, "USD", log)                                  # equal: passes
    coarse = spec_from("EUR_USD", "EURUSD", {**full_symbol(EURUSD, 5), "stepVolume": 1_000_000})
    for spec, quote in ((coarse, "USD"), (EU, "JPY"), (JY, "USD")):
        with pytest.raises(AttachFatal):
            cross_check(spec, meta, quote, log)
    desc = descriptor([EU, JY], "NETTED", frozenset({"fx"}))
    assert desc.account_model == "netting" and desc.min_lot == 0.01 and desc.server_side_stops


def test_the_venue_schedule_and_its_holidays_decide_closed() -> None:
    weekdays = spec_from("EUR_USD", "EURUSD", {**full_symbol(EURUSD, 5),
                         "schedule": [{"startSecond": 86400, "endSecond": 6 * 86400}],
                         "holiday": [{"holidayId": 1, "name": "x", "scheduleTimeZone": "UTC",
                                      "holidayDate": (date(2026, 12, 25) - date(1970, 1, 1)).days,
                                      "isRecurring": True}]})
    assert weekdays.is_open(T0)                                        # a Tuesday
    assert not weekdays.is_open(datetime(2026, 10, 4, 12, tzinfo=timezone.utc))   # a Sunday
    assert not weekdays.is_open(datetime(2027, 12, 25, 12, tzinfo=timezone.utc))  # recurring holiday


def test_equity_subtracts_the_closing_commission_and_a_charged_swap() -> None:
    account = derive({"balance": 1_000_000, "moneyDigits": 2},
                     {"moneyDigits": 2, "positionUnrealizedPnL": [{"netUnrealizedPnL": 500}]},
                     [{"commission": -300, "swap": -120, "usedMargin": 3_300, "moneyDigits": 2}])
    assert account.balance == Decimal("10000.00")
    assert account.equity == Decimal("10000.80")                       # +5.00 − 3.00 − 1.20
    assert account.margin_used == Decimal("33.00")
