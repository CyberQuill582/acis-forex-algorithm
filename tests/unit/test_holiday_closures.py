"""The pre-close entry ban and the flatten key on EVERY closure of two hours or more,
holidays included — not only the Friday close (audit X5).

FTMO forbids opening a trade "two hours or less before a relevant financial market is
closed for at least two hours" (Forbidden Trading Practices) and, on a Standard account,
requires closing before the weekend "or if the rollover (market break) lasts longer than 2
hours"; its holiday hours close FX all day on Dec 25 and Jan 1. In 2026 both fall on a
FRIDAY, so FX's last close before a three-day closure is THURSDAY 17:00 New York. The
regression cases are the audit's repro (`r5_holiday_closures.py`)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from core.governor.portfolio_types import Position
from core.signals.signal_types import StrategyType
from tests.risk_fixtures import load_cfg
from tests.signals_fixtures import mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio, mk_rulebook
from tests.unit.test_signal_types import mk_signal

UTC = timezone.utc
XMAS_EVE_1600_NY = datetime(2026, 12, 24, 21, 0, tzinfo=UTC)     # Thu, 1 h before the close
NYE_1630_NY = datetime(2026, 12, 31, 21, 30, tzinfo=UTC)         # Thu, 30 min before it
NEW_YEAR_1530_NY = datetime(2027, 1, 1, 20, 30, tzinfo=UTC)      # Fri, market shut ~22 h


def _holidays() -> list[date]:
    return load_cfg().instruments.calendars["fx_default"].holidays


def _pos(at: datetime) -> Position:
    return Position(instrument="EUR_USD", direction=1, size_units=Decimal("1000"),
                    entry_price=1.10, stop_loss=1.09, take_profit=None, opened_at=at,
                    strategy_type=StrategyType.TREND, param_set_id="ps-1", group_id=None)


def test_the_shipped_fx_calendar_declares_the_year_end_closures() -> None:
    assert {date(2026, 12, 25), date(2027, 1, 1)} <= set(_holidays())


def test_no_entry_opens_in_the_two_hours_before_a_holiday_closure() -> None:
    gov, _ = mk_governor(holidays=_holidays())                  # even a Swing account
    for at in (XMAS_EVE_1600_NY, NYE_1630_NY):
        assert gov.allocate(mk_signal(generated_at=at), mk_portfolio(), mk_regime(),
                            at).reason == "weekend_ban"
    earlier = XMAS_EVE_1600_NY - timedelta(hours=3)               # 13:00 NY: well before
    assert gov.allocate(mk_signal(generated_at=earlier), mk_portfolio(), mk_regime(),
                        earlier).reason == "formula"


def test_a_no_holding_account_is_flattened_before_a_holiday_closure() -> None:
    gov, log = mk_governor(rulebook=mk_rulebook(weekend_holding_allowed=False),
                           holidays=_holidays())
    closes = gov.weekend_flatten(mk_portfolio(open_positions=(_pos(XMAS_EVE_1600_NY),)),
                                 XMAS_EVE_1600_NY)
    assert [(c.instrument, c.action) for c in closes] == [("EUR_USD", "close")]
    assert log.events("WEEKEND_FLATTEN")


def test_a_position_still_open_inside_a_holiday_closure_is_surfaced() -> None:
    gov, log = mk_governor(rulebook=mk_rulebook(weekend_holding_allowed=False),
                           holidays=_holidays())
    gov.weekend_flatten(mk_portfolio(open_positions=(_pos(NEW_YEAR_1530_NY),)),
                        NEW_YEAR_1530_NY)
    assert log.events("WEEKEND_FLATTEN_INCOMPLETE")               # the market is SHUT
