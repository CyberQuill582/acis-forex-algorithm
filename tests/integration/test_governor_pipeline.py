"""Phase-6 integration: AGON signal -> Governor sizing; atomic pair groups end
to end; drawdown session halt (ACIS-05 §14 integration, jointly with ACIS-04)."""

from __future__ import annotations

from datetime import timedelta

from core.regime.regime_types import RegimeType
from core.signals.signal_types import StrategyType
from tests.optimizer_fixtures import make_paramset
from tests.signals_fixtures import (
    T0,
    feed_mids,
    feed_pair,
    make_agon,
    mk_regime,
    mk_state,
    pair_divergence_series,
    trend_cross_up_mids,
)
from tests.unit.test_governor import mk_governor, mk_portfolio


def test_agon_signal_is_sized_with_full_audit_chain(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    assert len(sigs) >= 1
    gov, log = mk_governor()
    order = gov.allocate(sigs[0], mk_portfolio(), mk_regime(), T0)
    assert order.size_units > 0 and order.reason == "formula"
    assert order.param_set_id == ps.param_set_id          # audit chain intact
    assert order.signal_id == sigs[0].signal_id


def test_pair_group_atomic_from_agon_to_close(tmp_path) -> None:
    a, b = pair_divergence_series()
    agon, _, _ = make_agon(tmp_path)
    feed_pair(agon, "EUR_USD", a, "USD_JPY", b)
    ps = make_paramset(mean_rev_zscore_entry=1.5)
    sigs = agon.generate(mk_state(mid=a[-1]), mk_regime(RegimeType.MEAN_REVERTING),
                         ps, T0)
    pair = tuple(s for s in sigs if s.strategy_type is StrategyType.PAIR_DIVERGENCE)
    assert len(pair) == 2
    gov, _ = mk_governor()
    ranging = mk_regime(RegimeType.MEAN_REVERTING)
    oa, ob = gov.allocate_group(pair, mk_portfolio(), ranging, T0)
    assert oa.size_units == ob.size_units > 0
    assert gov.open_groups() == (pair[0].group_id,)
    closes = gov.check_group_exits({pair[0].group_id: "reconvergence"},
                                   T0 + timedelta(hours=2))
    assert len(closes) == 2 and all(o.action == "close" for o in closes)
    assert gov.open_groups() == ()


def test_drawdown_limit_blocks_new_orders_for_session(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    gov, _ = mk_governor()
    hot = mk_portfolio(daily_drawdown_pct=2.1)
    assert gov.allocate(sigs[0], hot, mk_regime(), T0).size_units == 0
    calm = mk_portfolio(daily_drawdown_pct=0.0)
    later = T0 + timedelta(minutes=30)
    sigs2 = agon.generate(mk_state(mid=1.101), mk_regime(), ps, later)
    if sigs2:  # same cross still present in the window
        assert gov.allocate(sigs2[0], calm, mk_regime(), later).size_units == 0
