"""The harness as a runtime for the evolve-driver: per-instrument friction (GAP-P12D-19),
session-boundary promotion gated on the backtest's own book (ACIS-03 §7 C2), one-shot tick
streams, and per-fold Sharpe ratios as Deflated Sharpe trials (GAP-P12D-16/18)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from config.schemas import ZonedTime
from core.optimizer.costs import CostModel
from tests.backtest.book import BookState, OpenPos, PositionModel
from core.runtime.boundaries import BoundaryClock
from tests.backtest.harness import Backtest, FoldData
from tests.backtest.test_harness_regressions import _FakeLoop, _fold, _ms, _order
from tests.optimizer_fixtures import TEST_COSTS

UTC = timezone.utc
NY_ROLL = ZonedTime(zone="America/New_York", at="17:00")


def _pos(inst: str, entry: float, ts: datetime) -> OpenPos:
    return OpenPos(instrument=inst, direction=1, entry_price=entry, size_units=Decimal("10000"),
                   entry_ts=ts, stop_loss=0.0, take_profit=None, strategy_type="TREND")


def test_each_instrument_pays_its_own_friction() -> None:
    """Costs are in price units. USD/JPY's 0.002 slippage applied to EUR/USD would be 100×
    too much, and EUR/USD's applied to USD/JPY 100× too little."""
    t = datetime(2026, 1, 6, 10, tzinfo=UTC)
    model = PositionModel(costs={"EUR_USD": CostModel(commission_per_side=0.0, slippage_per_side=0.00002),
                                 "USD_JPY": CostModel(commission_per_side=0.0, slippage_per_side=0.002)},
                          max_hold_s=3600)
    eur = model.close_at(_pos("EUR_USD", 1.10, t), 1.10, t, "flat", BookState())
    jpy = model.close_at(_pos("USD_JPY", 150.0, t), 150.0, t, "flat", BookState())
    assert eur.pnl == pytest.approx(-Decimal("0.00004") * 10000)            # $0.40
    assert jpy.pnl == pytest.approx(-Decimal("0.004") * 10000 / Decimal("150"))  # ¥40 → $0.27
    with pytest.raises(ValueError, match="cost model"):
        model.close_at(_pos("GBP_USD", 1.25, t), 1.25, t, "flat", BookState())


def test_boundary_clock_reports_each_crossed_instant_across_dst_and_weekends() -> None:
    clock = BoundaryClock([NY_ROLL])
    assert clock.crossed(datetime(2025, 3, 7, 12, tzinfo=UTC)) == []            # Friday, first tick
    crossed = clock.crossed(datetime(2025, 3, 11, 12, tzinfo=UTC))              # Tuesday
    assert crossed == [datetime(2025, 3, 7, 22, tzinfo=UTC),                   # Fri 17:00 EST
                       datetime(2025, 3, 8, 22, tzinfo=UTC),                   # Sat
                       datetime(2025, 3, 9, 21, tzinfo=UTC),                   # Sun 17:00 EDT (DST began)
                       datetime(2025, 3, 10, 21, tzinfo=UTC)]
    assert clock.crossed(datetime(2025, 3, 11, 20, 59, tzinfo=UTC)) == []


class _ParamsStub:
    def __init__(self, gate) -> None:
        self.gate = gate
        self.sweeps: list[tuple[datetime, int]] = []

    def on_boundary(self, now: datetime) -> list[str]:
        self.sweeps.append((now, self.gate.open_position_count()))
        return []


def test_promotion_sweeps_see_the_backtest_book_not_the_loop_order_list() -> None:
    """The loop's order list only grows (GAP-0075), so it can never read flat. The sweep
    must see the harness book: open at the first rollover, flat after the target is hit."""
    d0 = datetime(2026, 1, 6, 15, tzinfo=UTC)                   # Tue 10:00 EST
    states = [_ms(d0, 1.10),
              _ms(d0 + timedelta(hours=8), 1.101),               # 23:00 UTC: crossed Tue 17:00, still open
              _ms(d0 + timedelta(hours=20), 1.11),               # Wed 11:00 UTC: target hit, closed
              _ms(d0 + timedelta(hours=32), 1.105)]              # Wed 23:00 UTC: crossed Wed 17:00, flat
    loop = _FakeLoop({d0: [_order(d0, 1, 1.10, 1.05, 1.11)]})
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS),
                  session_boundaries=[NY_ROLL])
    loop.params = _ParamsStub(bt)
    bt.run(loop=loop, folds=[FoldData(_fold(0, d0), states)], evolve_fn=lambda lp, fd: None,
           spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")
    assert loop.params.sweeps == [(datetime(2026, 1, 6, 22, tzinfo=UTC), 1),
                                  (datetime(2026, 1, 7, 22, tzinfo=UTC), 0)]


def _daily_fold(index: int, start: datetime, closes: list[float]) -> FoldData:
    """One long opened on day 0 and marked daily, so the fold has varied daily returns."""
    states = [_ms(start + timedelta(days=i), c) for i, c in enumerate(closes)]
    return FoldData(_fold(index, start), (s for s in states))   # a one-shot stream


def test_candidate_champion_sharpes_are_the_trials_and_the_registry_raises_n() -> None:
    a = datetime(2026, 2, 2, 10, tzinfo=UTC)
    b = datetime(2026, 3, 2, 10, tzinfo=UTC)
    script = {a: [_order(a, 1, 1.10, 1.00, 1.20)], b: [_order(b, 1, 1.10, 1.00, 1.20)]}
    folds = [_daily_fold(0, a, [1.10, 1.103, 1.101, 1.106, 1.104, 1.109]),
             _daily_fold(1, b, [1.10, 1.098, 1.102, 1.099, 1.104, 1.100])]
    records = [{"fold": 0, "champions": 2, "trial_sharpes": [0.12, 0.30]},
               {"fold": 1, "champions": 1, "trial_sharpes": [0.05]}]
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS), max_hold_s=5 * 86400,
                  session_boundaries=[NY_ROLL])
    loop = _FakeLoop(script)
    loop.params = _ParamsStub(bt)
    r = bt.run(loop=loop, folds=folds, evolve_fn=lambda lp, fd: records[fd.fold.index],
               spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH", min_trials=7)
    assert r.trial_count == 3 + 7                                 # 3 candidate champions + 7 registry entries
    assert r.in_sample_evolution == tuple(records)
    assert r.in_sample.n_trades == 0 and any("not replayed" in c for c in r.fidelity_caveats)
    assert all(t.notional_usd > 0 for t in bt._active.trades)     # every trade has a return basis


class _WarmLoop(_FakeLoop):
    def __init__(self, script) -> None:
        super().__init__(script)
        self.observed: list[datetime] = []
        self.decided: list[datetime] = []

    def observe_only(self, st) -> None:
        self.observed.append(st.timestamp)

    def on_state(self, st) -> None:
        self.decided.append(st.timestamp)
        super().on_state(st)


def test_warm_up_ticks_feed_the_engine_but_never_trade() -> None:
    first = datetime(2026, 2, 9, 10, tzinfo=UTC)
    warm = [_ms(first - timedelta(days=6, hours=i), 1.10) for i in (2, 1)]
    test = [_ms(first, 1.10), _ms(first + timedelta(minutes=1), 1.11)]
    # an order scripted at a warm-up instant must never be placed
    loop = _WarmLoop({warm[0].timestamp: [_order(warm[0].timestamp, 1, 1.10, 1.05, 1.11)]})
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS))
    fold = FoldData(_fold(0, first), test, warmup_states=warm)
    r = bt.run(loop=loop, folds=[fold], evolve_fn=lambda lp, fd: None, spx_closes={},
               guardrail_hash="GH", expected_guardrail_hash="GH")
    assert loop.observed == [s.timestamp for s in warm]
    assert loop.decided == [s.timestamp for s in test]
    assert r.out_of_sample.n_trades == 0


def test_a_position_closed_on_a_tick_frees_that_tick_s_boundary_sweep() -> None:
    d0 = datetime(2026, 1, 6, 15, tzinfo=UTC)                   # Tue 10:00 EST
    states = [_ms(d0, 1.10), _ms(d0 + timedelta(hours=30), 1.10)]   # past Tue 17:00, max hold 1 h
    loop = _FakeLoop({d0: [_order(d0, 1, 1.10, 1.05, 1.20)]})
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS), max_hold_s=3600,
                  session_boundaries=[NY_ROLL])
    loop.params = _ParamsStub(bt)
    bt.run(loop=loop, folds=[FoldData(_fold(0, d0), states)], evolve_fn=lambda lp, fd: None,
           spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")
    assert loop.params.sweeps == [(datetime(2026, 1, 6, 22, tzinfo=UTC), 0)]   # closed first, then swept


def test_staged_params_without_session_boundaries_are_refused() -> None:
    a = datetime(2026, 2, 2, 10, tzinfo=UTC)
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS))
    with pytest.raises(ValueError, match="never promote"):
        bt.run(loop=_FakeLoop({}), folds=[FoldData(_fold(0, a), [_ms(a, 1.10)])],
               evolve_fn=lambda lp, fd: {"champions": 1}, spx_closes={},
               guardrail_hash="GH", expected_guardrail_hash="GH")


def test_fewer_than_two_trial_sharpes_cannot_claim_n() -> None:
    a = datetime(2026, 2, 2, 10, tzinfo=UTC)
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS), max_hold_s=5 * 86400,
                  session_boundaries=[NY_ROLL])
    loop = _FakeLoop({a: [_order(a, 1, 1.10, 1.00, 1.20)]})
    loop.params = _ParamsStub(bt)
    r = bt.run(loop=loop, folds=[_daily_fold(0, a, [1.10, 1.103, 1.101, 1.106])],
               evolve_fn=lambda lp, fd: {"champions": 1, "trial_sharpes": [0.2]}, spx_closes={},
               guardrail_hash="GH", expected_guardrail_hash="GH", min_trials=50)
    assert r.trial_count == 1 and r.passed is False               # no trial variance, no N
    assert any("fewer than 2 candidate-champion" in c for c in r.fidelity_caveats)
