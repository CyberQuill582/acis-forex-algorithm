"""The runtime's position policy (GAP-0075): the backtest book's rules, in production."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from core.governor.portfolio_types import SizedOrder
from core.risk.risk_types import RiskPosition
from core.runtime.policy import exits_due, route, route_group

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
HOLD = 48 * 3600


def order(instrument="EUR_USD", direction=1, units="1000", action="open", group=None) -> SizedOrder:
    return SizedOrder(order_id=f"o-{instrument}-{direction}", signal_id="s", instrument=instrument,
                      direction=direction, size_units=Decimal(units), entry_price=1.10,
                      stop_loss=1.09 if direction == 1 else 1.11, take_profit=None,
                      reason="formula", factors_snapshot=MappingProxyType({}), sized_at=T0,
                      param_set_id="ps", group_id=group, action=action)


def held(instrument="EUR_USD", direction=1, tp=None, opened=T0, group=None) -> RiskPosition:
    return RiskPosition(instrument=instrument, direction=direction, size_units=Decimal("1000"),
                        avg_entry_price=1.10, opened_at=opened, param_set_id="ps", group_id=group,
                        stop_loss=1.09 if direction == 1 else 1.11, take_profit=tp)


def test_a_signal_repeated_every_tick_becomes_one_open_not_a_firehose() -> None:
    book: dict[str, RiskPosition] = {}
    busy: set[str] = set()
    sent = []
    for tick in range(20):                               # the phase-7 loop re-sized every tick
        work = route(order(), book, busy, T0 + timedelta(seconds=tick))
        sent.extend(work)
        if tick == 0:
            busy.add("EUR_USD")                          # in flight: Risk has not seen the fill
        if tick == 3:
            busy.clear()
            book["EUR_USD"] = held()                     # the fill lands; now it is held
    assert [o.action for o in sent] == ["open"]


def test_an_opposite_order_reverses_as_a_whole_close_then_the_open() -> None:
    work = route(order(direction=-1), {"EUR_USD": held(direction=1)}, set(), T0)
    close, opened = work
    assert (close.action, close.direction, close.size_units, close.reason) == (
        "close", 1, Decimal("1000"), "reverse")          # names the held side, whole holding
    assert (opened.action, opened.direction) == ("open", -1)


def test_a_zero_order_and_a_close_onto_nothing_change_nothing() -> None:
    assert route(order(units="0"), {}, set(), T0) == ()
    assert route(order(action="close"), {}, set(), T0) == ()
    assert route(order(action="close", direction=-1), {"EUR_USD": held(direction=1)}, set(), T0) == ()
    governor_close = order(action="close")
    assert route(governor_close, {"EUR_USD": held()}, set(), T0) == (governor_close,)


def test_a_pair_opens_only_onto_flat_idle_instruments() -> None:
    legs = (order(group="g"), order("USD_JPY", -1, group="g"))
    assert route_group(legs, {}, set()) == legs
    assert route_group(legs, {"USD_JPY": held("USD_JPY")}, set()) == ()
    assert route_group(legs, {}, {"EUR_USD"}) == ()
    assert route_group((legs[0], order("USD_JPY", -1, units="0", group="g")), {}, set()) == ()


def test_target_and_max_hold_exit_the_whole_holding_but_the_stop_is_the_venues() -> None:
    long_ = {"EUR_USD": held(tp=1.12)}
    assert exits_due(long_, {"EUR_USD": 1.119}, set(), T0, HOLD) == ()
    (hit,) = exits_due(long_, {"EUR_USD": 1.1205}, set(), T0, HOLD)
    assert (hit.reason, hit.action, hit.direction, hit.entry_price) == ("target", "close", 1, 1.1205)
    assert exits_due(long_, {"EUR_USD": 1.05}, set(), T0, HOLD) == ()      # through the stop: venue's
    (short_hit,) = exits_due({"EUR_USD": held(direction=-1, tp=1.08)}, {"EUR_USD": 1.08}, set(), T0, HOLD)
    assert short_hit.reason == "target"
    later = T0 + timedelta(seconds=HOLD)
    (aged,) = exits_due({"EUR_USD": held()}, {"EUR_USD": 1.10}, set(), later, HOLD)
    assert aged.reason == "max_hold"
    assert exits_due({"EUR_USD": held()}, {"EUR_USD": 1.10}, {"EUR_USD"}, later, HOLD) == ()
    assert exits_due({"EUR_USD": held()}, {}, set(), later, HOLD) == ()   # no mark, no guess


def test_a_legs_exit_closes_its_whole_group_and_an_orphan_leg_is_closed() -> None:
    pair = {"EUR_USD": held(tp=1.12, group="g"), "USD_JPY": held("USD_JPY", -1, group="g")}
    marks = {"EUR_USD": 1.121, "USD_JPY": 150.0}
    assert [(o.instrument, o.reason) for o in exits_due(pair, marks, set(), T0, HOLD)] == [
        ("EUR_USD", "target"), ("USD_JPY", "group_exit")]
    alone = {"USD_JPY": held("USD_JPY", -1, group="g")}
    assert [o.reason for o in exits_due(alone, marks, set(), T0, HOLD)] == ["group_orphan"]
    assert exits_due(alone, marks, {"USD_JPY"}, T0, HOLD) == ()           # its partner in flight
