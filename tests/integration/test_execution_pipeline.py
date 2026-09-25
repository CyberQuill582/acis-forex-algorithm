"""Phase-8 integration: AGON Signal -> Governor SizedOrder -> Execution
FillReports (ACIS-06 §14 integration, the ACIS-05 seam; the ACIS-07 seams —
position reconstruction, weekend-gap stops — land at phase 9).

GAP-P12D-57: execution sends only whole lot steps of the venue, rounded DOWN, and
reports the rest. These chains run on a venue that trades whole units (OANDA v20's
granularity), so the Governor's cent-quantised sizes arrive as whole units plus a
reported remainder of under one unit."""

from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_FLOOR, Decimal
from random import Random

from core.execution.fragmenter import plan  # noqa: F401  (import contract smoke)
from core.execution.orchestrator import ExecutionOrchestrator
from core.governor.units import usd_per_base_unit
from core.execution.venue import (
    FillReportStore,
    FillStatus,
    MockExecutionFace,
)
from core.execution.venue_quality import VenueQuality
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


def unit_venue() -> MockExecutionFace:
    face = MockExecutionFace()
    face.descriptor = replace(face.descriptor, min_lot=0.00001, lot_step=0.00001)  # 1 unit
    return face


def _sent_and_unsent(order, reports) -> tuple[Decimal, Decimal, Decimal]:
    whole = order.size_units.to_integral_value(rounding=ROUND_FLOOR)
    filled = sum((r.filled_units for r in reports), Decimal("0"))
    unsent = sum((r.remaining_units for r in reports if r.status is FillStatus.REJECTED),
                 Decimal("0"))
    return whole, filled, unsent


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
                        dispatch_budget_ms=100, max_venue_requests_per_day=1000),
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

    orch, face, _ = mk_exec(tmp_path, unit_venue())
    reports = await orch.submit(
        order, valid_for_seconds=signals[0].valid_for_seconds)
    assert any(r.status is FillStatus.FILLED for r in reports)
    # the audit chain survives every hop: signal -> order -> fills
    assert order.signal_id == signals[0].signal_id
    assert all(r.order_id == order.order_id for r in reports)
    whole, filled, unsent = _sent_and_unsent(order, reports)
    assert filled == whole                        # C-EXE-6: never more than sized
    assert filled + unsent == order.size_units    # the remainder is reported, not dropped
    positions = await face.open_positions()
    assert positions and positions[0].size_units == whole


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
    usd = [o.size_units * usd_per_base_unit(o.instrument, o.entry_price, {}) for o in (oa, ob)]
    assert min(usd) > 0 and abs(usd[0] - usd[1]) <= Decimal("0.05")   # equal USD legs (GAP-P12D-26)

    orch, face, _ = mk_exec(tmp_path, unit_venue())
    both = await orch.submit_group((oa, ob), valid_for_seconds=pair[0].valid_for_seconds)
    ra = [r for r in both if r.order_id == oa.order_id]
    rb = [r for r in both if r.order_id == ob.order_id]
    for order, reports in ((oa, ra), (ob, rb)):   # each leg fills its own size in whole units
        whole, filled, unsent = _sent_and_unsent(order, reports)
        assert filled == whole and filled + unsent == order.size_units
    assert {p.instrument for p in await face.open_positions()} == {
        "EUR_USD", "USD_JPY"}


async def test_governor_pair_exit_leaves_the_venue_flat(tmp_path) -> None:
    """Reduce-only closes (builder F1): the Governor's group-exit closes carry each
    leg's OWN direction (they name the position). Executed, they must FLATTEN both
    legs. Before the convention was enforced they were sent verbatim and DOUBLED them
    (EUR_USD −441 → −882, USD_JPY −486 → −972)."""
    from tests.unit.test_governor import _pair_signals
    gov, _ = mk_governor()
    legs = gov.allocate_group(_pair_signals(), mk_portfolio(), mk_regime(), T0)
    orch, face, _ = mk_exec(tmp_path, unit_venue())
    await orch.submit_group(legs, valid_for_seconds=300)
    opened = {p.instrument: (p.direction, p.size_units) for p in await face.open_positions()}
    assert set(opened) == {"EUR_USD", "USD_JPY"}
    closes = gov.check_group_exits({legs[0].group_id: "coupling_break"}, T0)
    assert [(c.action, c.direction) for c in closes] == [("close", leg.direction) for leg in legs]
    for close in closes:
        reports = await orch.submit(close, valid_for_seconds=300)
        traded = [r for r in reports if r.status is FillStatus.FILLED]
        assert traded and all(r.direction == -close.direction for r in traded)
    assert await face.open_positions() == ()                 # FLAT, not doubled


async def test_weekend_flatten_leaves_the_venue_flat(tmp_path) -> None:
    """Master §9.5 through the real seam: a no-weekend-holding account's positions,
    opened by the Governor and the orchestrator, are closed by the Governor's weekend
    flatten and the venue is FLAT before the Friday close."""
    from datetime import datetime, timedelta, timezone
    from core.governor.portfolio_types import Position
    from core.signals.signal_types import StrategyType
    from tests.unit.test_governor import _pair_signals, mk_rulebook
    gov, _ = mk_governor(rulebook=mk_rulebook(weekend_holding_allowed=False))
    legs = gov.allocate_group(_pair_signals(), mk_portfolio(), mk_regime(), T0)
    orch, face, _ = mk_exec(tmp_path, unit_venue())
    await orch.submit_group(legs, valid_for_seconds=300)
    book = mk_portfolio(open_positions=tuple(
        Position(instrument=p.instrument, direction=p.direction, size_units=p.size_units,
                 entry_price=leg.entry_price, stop_loss=leg.stop_loss, take_profit=None,
                 opened_at=T0, strategy_type=StrategyType.PAIR_DIVERGENCE,
                 param_set_id=leg.param_set_id, group_id=leg.group_id)
        for p, leg in zip(await face.open_positions(),
                          sorted(legs, key=lambda o: o.instrument))))
    assert len(book.open_positions) == 2                        # both legs really opened
    friday = datetime(2026, 7, 10, 20, 0, tzinfo=timezone.utc)     # 1 h before the close
    for close in gov.weekend_flatten(book, friday):
        await orch.submit(close, valid_for_seconds=300)
    assert await face.open_positions() == ()                   # flat before the weekend
    assert gov.weekend_flatten(mk_portfolio(), friday + timedelta(minutes=1)) == ()


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
