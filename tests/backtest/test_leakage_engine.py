"""The engine tap, in the default suite (GAP-P12D-83 LOW): `engine_decisions`, `_Tap` and
`vacuity` were exercised only by hand runs of scripts/leakage_suite.py (minutes per variant).
Here a tiny tape runs the production path end to end in seconds, and a stub loop pins what the
tap records from signals and orders, which a tape this short never produces."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from core.regime.regime_types import LiqState, RegimeType, VolClass
from core.signals.signal_types import StrategyType
from tests.backtest.leakage import Decision, future_perturbation, truncation
from tests.backtest.leakage_engine import _Tap, engine_decisions, leak_config, vacuity
from tests.backtest.leakage_markets import decision_cuts
from tests.backtest.synthetic_grade import FIRST_MID, START, plan
from tests.backtest.synthetic_market import MarketSpec

ROOT = Path(__file__).resolve().parents[2]
T = datetime(2014, 1, 7, 10, 0, tzinfo=timezone.utc)


def test_the_production_path_is_tapped_end_to_end_on_a_tiny_tape(tmp_path) -> None:
    cfg = leak_config(ROOT, small_optimizer=True)
    folds = plan(3, 1, 1, embargo=timedelta(days=2))
    spec = MarketSpec("planted", START, (folds[-1].test_end - START).days,
                      tuple((i, FIRST_MID[i]) for i in sorted(cfg.instruments.enabled)), tick_seconds=600)
    ref = engine_decisions(spec, cfg, "dev_paper", folds, tmp_path / "ref")
    kinds = Counter(d.kind for d in ref)
    assert kinds["label"] > 500 and kinds["regime"] > 200 and kinds["evolution"] == 1
    assert vacuity(ref) == ["no fold staged a champion", "the engine placed no order"]
    cut = decision_cuts(spec, folds)[2]
    t2 = future_perturbation(ref, lambda t: engine_decisions(spec, cfg, "dev_paper", folds, tmp_path / "p",
                                                             cut=t, mode="perturb"), [cut])
    t1 = truncation(ref, lambda t: engine_decisions(spec, cfg, "dev_paper", folds, tmp_path / "t",
                                                    cut=t, mode="truncate"), [cut])
    assert t2.silent and t1.silent and t2.compared > 300, (t2.summary(), t1.summary())


def test_vacuity_is_empty_only_when_a_champion_was_staged_and_an_order_placed() -> None:
    staged = Decision(T, T, "evolution", ('{"champions": 1}',))
    order = Decision(T, T, "order", ("EUR_USD",))
    assert vacuity([staged, order]) == []
    assert vacuity([staged]) == ["the engine placed no order"]


class _StubLoop:
    """The loop surface the tap wraps: one signal and one order per graded tick."""

    def __init__(self, signal, order, ctx) -> None:
        self.book = SimpleNamespace(orders=[], strategy_of={}, regime_of={})
        self.agon = SimpleNamespace(generate=lambda state, regime, params, now: (signal,))
        self.last_context, self._order = ctx, order

    def on_state(self, st) -> None:
        self.agon.generate(st, None, None, st.timestamp)
        self.book.orders.append(self._order)
        self.book.strategy_of[self._order.order_id] = "TREND"
        self.book.regime_of[self._order.order_id] = "STRONG_TREND_UP"

    def observe_only(self, st) -> None:
        return None


def test_the_tap_records_signals_orders_and_regimes_and_passes_them_through() -> None:
    signal = SimpleNamespace(instrument="EUR_USD", direction=1, conviction=0.6, entry_price=1.1, stop_loss=1.09,
                             take_profit=None, strategy_type=StrategyType.TREND,
                             regime_at_generation=RegimeType.STRONG_TREND_UP, param_set_id="p", generated_at=T,
                             valid_for_seconds=300, group_id="uuid-a")
    order = SimpleNamespace(order_id="uuid-o", instrument="EUR_USD", direction=1, size_units=Decimal("1000"),
                            entry_price=1.1, stop_loss=1.09, take_profit=None, reason="sized", param_set_id="p",
                            action="open", group_id=None, sized_at=T)
    ctx = SimpleNamespace(timestamp=T, regime=RegimeType.STRONG_TREND_UP, trend_direction=1,
                          volatility_class=VolClass.HIGH, liquidity_state=LiqState.DEEP, tradeable=True,
                          confidence=0.9, regime_stability_score=0.8, estimated_half_life_seconds=600)
    stub = _StubLoop(signal, order, ctx)
    tap = _Tap(lambda *a, **kw: stub)
    loop = tap.build("work", position_gate="the backtest")
    st = SimpleNamespace(timestamp=T, instrument="EUR_USD")
    loop.on_state(st)
    loop.observe_only(st)
    by_kind = {k: [d for d in tap.decisions if d.kind == k] for k in ("signal", "order", "regime")}
    assert tap.backtest == "the backtest" and [len(v) for v in by_kind.values()] == [1, 1, 2]
    assert by_kind["signal"][0].payload[-1] == 0 and "uuid-a" not in repr(by_kind["signal"][0].payload)
    assert by_kind["order"][0].payload[-3:] == ("TREND", "STRONG_TREND_UP", None)
    assert "uuid-o" not in repr(by_kind["order"][0].payload) and stub.book.orders == [order]
