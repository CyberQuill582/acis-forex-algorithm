"""Phase-8 integration: AGON Signal -> Governor SizedOrder -> Execution
FillReports (ACIS-06 §14 integration, the ACIS-05 seam; the ACIS-07 seams —
position reconstruction, weekend-gap stops — land at phase 9)."""

from __future__ import annotations

from decimal import Decimal
from random import Random

from core.execution.fragmenter import plan  # noqa: F401  (import contract smoke)
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import (
    FillReportStore,
    FillStatus,
    MockExecutionFace,
    VenueQuality,
)
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import CapturingLogger, make_paramset
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


def mk_exec(tmp_path, face=None):
    from config.schemas import ExecutionConfig

    log = CapturingLogger()
    face = face or MockExecutionFace()

    async def instant(_s: float) -> None:
        return None

    orch = ExecutionOrchestrator(
        ExecutionConfig(fragment_threshold_lots=1.0,
                        fragment_size_jitter=(0.85, 1.15),
                        fragment_time_jitter_s=(0.5, 3.0), min_fragment_lots=0.10,
                        vwap_threshold_lots=5.0, vwap_window_s=300,
                        fast_decay_seconds=30, signature_lot_variance=0.15,
                        dispatch_budget_ms=100),
        {"mock": face}, VenueQuality(), FillReportStore(tmp_path / "fills.db"),
        slippage_alert_bps=8.0, rng=Random(7), logger=log, session_id="xint",
        now_fn=lambda: T0, sleep_fn=instant)
    return orch, face, log


async def test_signal_to_fill_full_audit_chain(tmp_path) -> None:
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    signals = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    assert signals
    gov, _ = mk_governor()
    order = gov.allocate(signals[0], mk_portfolio(), mk_regime(), T0)
    assert order.size_units > 0

    orch, face, _ = mk_exec(tmp_path)
    reports = await orch.submit(
        order, valid_for_seconds=signals[0].valid_for_seconds)
    assert reports and all(r.status is FillStatus.FILLED for r in reports)
    # the audit chain survives every hop: signal -> order -> fills
    assert order.signal_id == signals[0].signal_id
    assert all(r.order_id == order.order_id for r in reports)
    filled = sum((r.filled_units for r in reports), Decimal("0"))
    assert filled == order.size_units            # C-EXE-6 at the seam
    positions = await face.open_positions()
    assert positions and positions[0].size_units == order.size_units


async def test_pair_group_executes_both_legs(tmp_path) -> None:
    a, b = pair_divergence_series()
    agon, _, _ = make_agon(tmp_path)
    feed_pair(agon, "EUR_USD", a, "USD_JPY", b)
    ps = make_paramset(mean_rev_zscore_entry=1.5)
    signals = agon.generate(mk_state(mid=a[-1]),
                            mk_regime(RegimeType.MEAN_REVERTING), ps, T0)
    pair = tuple(s for s in signals if s.group_id is not None)
    assert len(pair) == 2
    gov, _ = mk_governor()
    oa, ob = gov.allocate_group(pair, mk_portfolio(),
                                mk_regime(RegimeType.MEAN_REVERTING), T0)
    assert oa.size_units == ob.size_units > 0

    orch, face, _ = mk_exec(tmp_path)
    ra = await orch.submit(oa, valid_for_seconds=pair[0].valid_for_seconds)
    rb = await orch.submit(ob, valid_for_seconds=pair[1].valid_for_seconds)
    assert (sum((r.filled_units for r in ra), Decimal("0"))
            == sum((r.filled_units for r in rb), Decimal("0"))
            == oa.size_units)                    # the relationship trade is intact
    assert {p.instrument for p in await face.open_positions()} == {
        "EUR_USD", "USD_JPY"}


async def test_zero_sized_order_never_reaches_a_venue(tmp_path) -> None:
    """The Governor's zero IS the veto — execution must not resurrect it."""
    agon, _, _ = make_agon(tmp_path)
    feed_mids(agon, "EUR_USD", trend_cross_up_mids())
    ps = make_paramset()
    signals = agon.generate(mk_state(mid=1.101), mk_regime(), ps, T0)
    gov, _ = mk_governor()
    hot = mk_portfolio(daily_drawdown_pct=2.1)   # drawdown halt -> size 0
    order = gov.allocate(signals[0], hot, mk_regime(), T0)
    assert order.size_units == 0

    orch, face, log = mk_exec(tmp_path)
    assert await orch.submit(
        order, valid_for_seconds=signals[0].valid_for_seconds) == ()
    assert face.submissions == 0                 # the venue never saw it
    assert log.events("EXEC_NOOP")
