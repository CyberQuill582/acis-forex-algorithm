"""The weekend flatten (master §9.5: on a no-weekend-holding account, "positions flattened
before the ban window by policy, surfaced if impossible"). It starts with the pre-close
entry ban (`weekend_entry_buffer_s`, 2 h) and emits reduce-only closes naming each open
position — its own side and size (the close convention built in stage 7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.governor.portfolio_types import Position
from core.signals.signal_types import StrategyType
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import _pair_signals, mk_governor, mk_portfolio, mk_rulebook

NO_WEEKEND = dict(weekend_holding_allowed=False)


def _pos(instrument="EUR_USD", direction=1, units="1000", group_id=None, price=1.10):
    return Position(instrument=instrument, direction=direction, size_units=Decimal(units),
                    entry_price=price, stop_loss=price * (0.99 if direction == 1 else 1.01),
                    take_profit=None, opened_at=T0, strategy_type=StrategyType.TREND,
                    param_set_id="ps-1", group_id=group_id)


def _close(month: int) -> datetime:                        # Friday 17:00 New York
    return (datetime(2026, 7, 10, 21, tzinfo=timezone.utc) if month == 7
            else datetime(2026, 1, 9, 22, tzinfo=timezone.utc))


@pytest.mark.parametrize("month", [7, 1])                  # EDT and EST
def test_flatten_starts_with_the_entry_ban_and_names_each_position(month) -> None:
    gov, log = mk_governor(rulebook=mk_rulebook(**NO_WEEKEND))
    book = mk_portfolio(open_positions=(_pos(), _pos("USD_JPY", -1, "2500", price=150.0)))
    ban = _close(month) - timedelta(hours=2)
    assert gov.weekend_flatten(book, ban - timedelta(seconds=1)) == ()
    closes = gov.weekend_flatten(book, ban)
    assert [(c.instrument, c.direction, c.size_units, c.action, c.reason) for c in closes] == [
        ("EUR_USD", 1, Decimal("1000"), "close", "weekend_flatten"),
        ("USD_JPY", -1, Decimal("2500"), "close", "weekend_flatten")]
    assert log.events("WEEKEND_FLATTEN")[0]["data"]["instruments"] == ["EUR_USD", "USD_JPY"]


def test_an_account_that_may_hold_over_the_weekend_is_never_flattened() -> None:
    gov, _ = mk_governor()                                  # weekend holding allowed
    book = mk_portfolio(open_positions=(_pos(),))
    assert gov.weekend_flatten(book, _close(7) - timedelta(minutes=30)) == ()
    assert gov.weekend_flatten(book, _close(7) + timedelta(hours=5)) == ()


def test_a_position_still_open_after_the_close_is_surfaced() -> None:
    gov, log = mk_governor(rulebook=mk_rulebook(**NO_WEEKEND))
    book = mk_portfolio(open_positions=(_pos(),))
    closes = gov.weekend_flatten(book, _close(7) + timedelta(minutes=1))
    assert len(closes) == 1                                 # still tried, every tick
    assert log.events("WEEKEND_FLATTEN_INCOMPLETE")[0]["data"]["instruments"] == ["EUR_USD"]
    assert gov.weekend_flatten(mk_portfolio(), _close(7) + timedelta(minutes=2)) == ()


def test_both_legs_of_a_pair_are_flattened_and_the_group_retired() -> None:
    gov, _ = mk_governor(rulebook=mk_rulebook(**NO_WEEKEND))
    a, b = gov.allocate_group(_pair_signals(), mk_portfolio(), mk_regime(), T0)
    assert gov.open_groups() == (a.group_id,)
    book = mk_portfolio(open_positions=tuple(
        _pos(o.instrument, o.direction, str(o.size_units), o.group_id, o.entry_price)
        for o in (a, b)))
    closes = gov.weekend_flatten(book, _close(7) - timedelta(hours=1))
    assert {(c.instrument, c.group_id) for c in closes} == {(a.instrument, a.group_id),
                                                           (b.instrument, b.group_id)}
    assert gov.open_groups() == ()                          # never one leg alone
