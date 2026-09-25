"""The oracle keeps the account's evaluable rules (audit F2), and the book honours a close order.

On a weekend-flat account (FTMO, prop_demo) the harness books any hold across Friday's rollover as
`weekend_holding`, and every stage-1 run VOIDed whatever the grade did, while null and permuted were
"refused" by that same rule, vacuously. The oracle now flattens before the weekend and never
reverses or closes a position younger than `min_hold_seconds`.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config.schemas import AccountRulebook, NewsRules
from core.data.fx_clock import rollover_utc
from tests.backtest.book import BookState, PositionModel
from tests.backtest.oracle_loop import FLATTEN_LEAD, OracleLoop, OracleTick
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, episodes
from tests.backtest.test_harness_regressions import _ms, _order
from tests.optimizer_fixtures import TEST_COSTS

UTC = timezone.utc
START = datetime(2014, 1, 6, tzinfo=UTC)                     # a Monday
FRIDAY = datetime(2014, 1, 10, tzinfo=UTC)
PRICES = (("EUR_USD", 1.10),)


def _rulebook(**over) -> AccountRulebook:
    base = dict(platform="dev", news=NewsRules(restricted=False), min_hold_seconds=60, max_lots=None,
                weekend_holding_allowed=False, drawdown_rules=[])
    return AccountRulebook(**{**base, **over})


def _tick(ts: datetime, mid: float = 1.10) -> OracleTick:
    return OracleTick(ts, "EUR_USD", mid - 2e-5, mid + 2e-5, 4e-5, mid)


def _actions(loop: OracleLoop) -> list[tuple[str, datetime]]:
    return [(o.action, o.sized_at) for o in loop.book.orders]


def test_a_weekend_flat_oracle_is_flat_before_fridays_rollover_and_reopens_after_it() -> None:
    loop = OracleLoop(SyntheticMarket(MarketSpec("planted", START, 14, PRICES)), Decimal("10000"), _rulebook())
    cutoff = rollover_utc(FRIDAY.date())                              # 22:00 UTC in January (EST)
    flat_at = cutoff - FLATTEN_LEAD
    for ts in (cutoff - timedelta(hours=1), flat_at - timedelta(seconds=20), flat_at,
               flat_at + timedelta(minutes=10), START + timedelta(days=7)):
        loop.on_state(_tick(ts))
    assert [a for a, _ in _actions(loop)] == ["open", "close", "open"]
    assert _actions(loop)[1][1] == flat_at and _actions(loop)[2][1] == START + timedelta(days=7)
    allowed = OracleLoop(SyntheticMarket(MarketSpec("planted", START, 14, PRICES)), Decimal("10000"),
                         _rulebook(weekend_holding_allowed=True))
    for ts in (cutoff - timedelta(hours=1), flat_at):
        allowed.on_state(_tick(ts))
    assert [a for a, _ in _actions(allowed)] == ["open"]              # weekend allowed: it holds


def test_nothing_opens_in_the_wind_down_before_the_flatten() -> None:
    """A position opened in the last `min_hold` before the flatten would be closed too young."""
    loop = OracleLoop(SyntheticMarket(MarketSpec("planted", START, 14, PRICES)), Decimal("10000"), _rulebook())
    flat_at = rollover_utc(FRIDAY.date()) - FLATTEN_LEAD
    loop.on_state(_tick(flat_at - timedelta(seconds=40)))             # inside the 60 s wind-down
    loop.on_state(_tick(flat_at))
    assert loop.book.orders == []


def test_a_flip_waits_until_the_position_is_min_hold_old() -> None:
    market = SyntheticMarket(MarketSpec("planted", START, 7, PRICES))
    ticks = list(market.load("EUR_USD", START, START + timedelta(hours=20)))
    flip = next(ep.start for a, ep in zip(episodes(market.spec, 0), episodes(market.spec, 0)[1:])
                if ep.sign != a.sign)                                  # first sign change (20 s ticks)
    loop = OracleLoop(market, Decimal("10000"), _rulebook(weekend_holding_allowed=True))
    for t in ticks[flip - 1:flip + 3]:                                # opened 20 s before the flip
        loop.on_state(_tick(t.event_time))
    opened, reversed_ = loop.book.orders
    assert reversed_.direction == -opened.direction
    assert reversed_.sized_at - opened.sized_at == timedelta(seconds=60)   # not at 20 s or 40 s


def test_the_book_closes_on_a_close_order_at_the_ticks_mid_and_ignores_one_with_nothing_open() -> None:
    model, book = PositionModel(costs={"EUR_USD": TEST_COSTS}, max_hold_s=86400), BookState()
    t0 = datetime(2026, 1, 6, 10, tzinfo=UTC)
    model.apply_order(_order(t0, 1, 1.10, 1.05, None), _ms(t0, 1.10), book)
    close = dataclasses.replace(_order(t0 + timedelta(hours=1), 1, 1.10, 1.05, None), action="close")
    model.apply_order(close, _ms(t0 + timedelta(hours=1), 1.12), book)
    (trade,) = book.trades
    assert book.open_by_inst == {} and trade.exit_ts == t0 + timedelta(hours=1)
    assert trade.pnl > Decimal("19")                                  # filled at 1.12, not the order's 1.10
    model.apply_order(close, _ms(t0 + timedelta(hours=2), 1.13), book)
    assert len(book.trades) == 1 and book.open_by_inst == {}          # nothing open: a no-op
