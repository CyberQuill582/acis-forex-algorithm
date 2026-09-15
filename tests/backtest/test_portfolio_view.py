"""The Governor's portfolio snapshot from the backtest book (GAP-P12D-21) and strategy
attribution on real engine trades (GAP-P12D-20)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.data.errors import DataQualityError
from core.signals.signal_types import StrategyType
from tests.backtest.book import BookState, OpenPos
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.portfolio_view import build_portfolio_state
from tests.backtest.test_harness_regressions import _FakeLoop, _fold, _ms, _order
from tests.backtest.walk_forward import Fold
from tests.integration.test_paper_trading_pipeline import flat_portfolio, flat_ticks, make_loop
from tests.optimizer_fixtures import TEST_COSTS

UTC = timezone.utc
T = datetime(2026, 1, 6, 10, tzinfo=UTC)
CLUSTERS = {"usd_short": ["EUR_USD"], "yen_carry": ["USD_JPY"], "usd_bloc": ["EUR_USD", "USD_JPY"]}


def _pos(inst: str, direction: int, entry: float, units: str, strategy: str = "TREND") -> OpenPos:
    return OpenPos(instrument=inst, direction=direction, entry_price=entry, size_units=Decimal(units),
                   entry_ts=T, stop_loss=entry * 0.9, take_profit=None, strategy_type=strategy,
                   param_set_id="ps-1")


def test_exposure_and_currency_delta_are_the_governors_usd_arithmetic() -> None:
    book = BookState(open_by_inst={"EUR_USD": _pos("EUR_USD", 1, 1.10, "1000"),     # $1,100 long EUR
                                   "USD_JPY": _pos("USD_JPY", -1, 150.0, "500")},   # $500 short USD
                     last_price={"EUR_USD": 1.10, "USD_JPY": 150.0})
    p = build_portfolio_state(book=book, nav=Decimal("10000"), clusters=CLUSTERS, as_of=T)
    assert p.per_cluster_exposure == {"usd_short": Decimal("1100.00"), "yen_carry": Decimal("500"),
                                      "usd_bloc": Decimal("1600.00")}
    assert p.per_currency_delta == {"EUR": Decimal("1100.00"), "USD": Decimal("-1600.00"),
                                    "JPY": Decimal("500")}
    assert {x.strategy_type for x in p.open_positions} == {StrategyType.TREND}
    assert p.stale is False and p.nav == Decimal("10000")


def test_daily_drawdown_runs_from_the_trading_day_anchor() -> None:
    book = BookState(day_anchor=Decimal("10000"))
    assert build_portfolio_state(book=book, nav=Decimal("9790"), clusters={}, as_of=T).daily_drawdown_pct \
        == pytest.approx(2.1)
    assert build_portfolio_state(book=book, nav=Decimal("10300"), clusters={}, as_of=T).daily_drawdown_pct == 0.0


def test_an_unattributed_position_is_refused() -> None:
    book = BookState(open_by_inst={"EUR_USD": _pos("EUR_USD", 1, 1.10, "1000", strategy="UNKNOWN")},
                     last_price={"EUR_USD": 1.10})
    with pytest.raises(DataQualityError):
        build_portfolio_state(book=book, nav=Decimal("10000"), clusters={}, as_of=T)


def test_the_day_anchor_resets_at_the_new_york_rollover() -> None:
    """A long loses before 17:00 New York; after the rollover the new day starts from the
    lower equity, so the daily drawdown resets to 0."""
    d0 = datetime(2026, 1, 6, 15, tzinfo=UTC)                        # Tue 10:00 EST
    states = [_ms(d0, 1.10), _ms(d0 + timedelta(hours=6), 1.09),     # 21:00 UTC, before the roll
              _ms(d0 + timedelta(hours=8), 1.09)]                    # 23:00 UTC, after it
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS), clusters=CLUSTERS)
    seen = []

    class _Loop(_FakeLoop):
        def on_state(self, st) -> None:
            super().on_state(st)
            seen.append(bt.portfolio_state().daily_drawdown_pct)

    loop = _Loop({d0: [_order(d0, 1, 1.10, 1.00, 1.30)]})
    bt.run(loop=loop, folds=[FoldData(_fold(0, d0), states)], evolve_fn=lambda lp, fd: None,
           spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")
    # before the loss 0; after it (1000 × 0.01 on ~$10,000) ≈ 0.1%; the next trading day starts over
    assert seen[0] == 0.0 and seen[1] == pytest.approx(0.1, abs=0.01) and seen[2] == 0.0


def test_real_engine_trades_carry_their_strategy(tmp_path, acis_config, factory) -> None:
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    states = [s for s in (factory.build(r).state for r in flat_ticks()) if s is not None]
    first = states[0].timestamp
    bt = Backtest(account="dev_paper", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=300)
    fold = FoldData(Fold(0, first - timedelta(days=2), first - timedelta(days=1), first,
                         states[-1].timestamp), states)
    bt.run(loop=loop, folds=[fold], evolve_fn=lambda lp, fd: None, spx_closes={},
           guardrail_hash="GH", expected_guardrail_hash="GH")
    strategies = {t.strategy_type for t in bt._active.trades}
    assert strategies and "UNKNOWN" not in strategies and "TSMOM" in strategies
