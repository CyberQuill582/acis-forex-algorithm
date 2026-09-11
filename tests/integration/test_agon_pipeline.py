"""Phase-5 integration: NVMA veto -> AGON silence; QIEA params -> signal audit
link; provenance freeze mid-stream (ACIS-04 §14 integration, jointly with
ACIS-02/03/11)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.schemas import ZonedTime
from core.optimizer.param_library import ParamLibrary
from core.regime.regime_types import RegimeType
from core.signals.signal_types import StrategyType
from tests.optimizer_fixtures import make_paramset
from tests.signals_fixtures import (
    T0,
    feed_mids,
    make_agon,
    mk_regime,
    mk_state,
    trend_cross_up_mids,
)

BOUNDARY = datetime(2026, 7, 6, 21, 0, tzinfo=timezone.utc)   # 17:00 EDT rollover


class FlatGate:
    def open_position_count(self) -> int:
        return 0


def test_veto_window_produces_zero_signals(tmp_path) -> None:
    """NVMA no-trade => zero signals reach the Governor across the vetoed window."""
    agon, log, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    vetoed = mk_regime(RegimeType.MACRO_EVENT, tradeable=False)
    for i in range(5):
        assert agon.generate(mk_state(mid=1.101), vetoed, ps,
                             T0 + timedelta(seconds=i)) == ()
    assert len(log.events("DISCARD_VETOED_REGIME")) == 5
    assert log.events("SIGNAL_EMITTED") == []


def test_signal_param_set_id_traces_to_promoted_active_set(tmp_path) -> None:
    """End-to-end audit link: QIEA stages -> boundary+flat promotes -> AGON emits
    with the promoted set's param_set_id (jointly with ACIS-03)."""
    from tests.optimizer_fixtures import CapturingLogger

    lib = ParamLibrary(tmp_path / "params.db",
                       [ZonedTime(zone="America/New_York", at="17:00")], 3, FlatGate(),
                       CapturingLogger())
    staged = make_paramset(regime=RegimeType.STRONG_TREND_UP)
    lib.stage(staged)
    lib.promote(BOUNDARY)
    active = lib.get_active(RegimeType.STRONG_TREND_UP)
    assert active is not None

    agon, log, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), active.params, T0)
    assert len(sigs) >= 1
    assert all(s.param_set_id == staged.param_set_id for s in sigs)
    emitted = log.events("SIGNAL_EMITTED")
    assert all(e["data"]["param_set_id"] == staged.param_set_id for e in emitted)
    lib.close()


def test_provenance_demotion_freezes_new_entries_then_completes_flat(tmp_path) -> None:
    """GAP-0019 across layers: a demoted strategy stops emitting instantly; its
    staged Arena removal completes only at a flat boundary (jointly with ACIS-11)."""
    agon, log, store = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()

    assert len(agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)) >= 1

    store.promote_one_rung("trend_following_v1", "paper evidence", T0)
    store.demote("trend_following_v1", "failed re-validation", T0)
    sigs = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    assert all(s.strategy_type is not StrategyType.TREND for s in sigs)

    assert store.on_boundary("trend_following_v1", open_positions=1, now=BOUNDARY) is False
    assert store.on_boundary("trend_following_v1", open_positions=0,
                             now=BOUNDARY + timedelta(days=1)) is True
    stalls = log.events("STRATEGY_REMOVAL_STALLED")
    assert [e["data"]["boundaries_skipped"] for e in stalls] == [1]


def test_regime_shift_switches_module_set(tmp_path) -> None:
    """The same windows produce trend signals in a trend regime and none from the
    trend module in a ranging regime — module gating follows the RegimeContext."""
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    trend_sigs = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    ranging_sigs = agon.generate(mk_state(mid=1.101),
                                 mk_regime(RegimeType.RANGING_TIGHT), ps, T0)
    assert any(s.strategy_type is StrategyType.TREND for s in trend_sigs)
    assert all(s.strategy_type is not StrategyType.TREND for s in ranging_sigs)
