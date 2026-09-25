"""Phase-8 unit contract (ACIS-06 v1.1 §13/§14): fragment invariants,
seeded jitter distributions, path classification, capability rejection,
partial/reject/reconnect handling, freeze semantics, F10 no-resize, budget
observability, store idempotency."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random
from types import MappingProxyType

import pytest

from config.schemas import ExecutionConfig
from core.data.errors import DataQualityError
from core.execution import orchestrator as orch_mod
from core.execution.fragmenter import plan
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.attach import AttachHalt, verify_attach
from core.execution.venue import (
    CapabilityDescriptor,
    FillReportStore,
    FillStatus,
    MockExecutionFace,
    slippage_bps,
)
from core.execution.venue_quality import VenueQuality
from core.governor.portfolio_types import SizedOrder
from tests.optimizer_fixtures import CapturingLogger

T0 = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)


def exec_cfg(**overrides) -> ExecutionConfig:
    base = dict(fragment_threshold_lots=1.0, fragment_size_jitter=(0.85, 1.15),
                fragment_time_jitter_s=(0.5, 3.0), min_fragment_lots=0.10,
                vwap_threshold_lots=5.0, vwap_window_s=300, fast_decay_seconds=30,
                signature_lot_variance=0.15, dispatch_budget_ms=100,
                max_venue_requests_per_day=1000)
    base.update(overrides)
    return ExecutionConfig(**base)


def mk_order(units="250000", action="open", instrument="EUR_USD",
             order_id="ord-1", direction=1) -> SizedOrder:
    return SizedOrder(
        order_id=order_id, signal_id="sig-1", instrument=instrument, direction=direction,
        size_units=Decimal(units), entry_price=1.10, stop_loss=1.09,
        take_profit=1.12, reason="formula",
        factors_snapshot=MappingProxyType({}), sized_at=T0,
        param_set_id="ps-1", action=action)


def mk_orchestrator(tmp_path, faces=None, cfg=None, seed=7):
    log = CapturingLogger()
    store = FillReportStore(tmp_path / "fills.db")
    slept: list[float] = []

    async def sleep_fn(s: float) -> None:
        slept.append(s)

    orch = ExecutionOrchestrator(
        cfg or exec_cfg(),
        faces if faces is not None else {"mock": MockExecutionFace()},
        VenueQuality(), store, slippage_alert_bps=8.0, rng=Random(seed),
        logger=log, session_id="xtest", now_fn=lambda: T0, sleep_fn=sleep_fn)
    return orch, log, store, slept


# ---------------------------- fragmenter (C-EXE-1/2) ---------------------------- #

def test_fragments_sum_exactly_to_total_property() -> None:
    rng = Random(3)
    for seed in range(50):
        total = Decimal(rng.randrange(150_000, 2_000_000)) / Decimal("100")
        fp = plan("o", total, fast_decay=False, cfg=exec_cfg(),
                  venues=["mock"], now=T0, rng=Random(seed))
        assert sum(f.units for f in fp.fragments) == total   # no unit created/destroyed


def test_jitter_distributions_in_bounds_and_not_degenerate() -> None:
    ratios, gaps = [], []
    for seed in range(100):
        fp = plan("o", Decimal("400000"), fast_decay=False, cfg=exec_cfg(),
                  venues=["mock"], now=T0, rng=Random(seed))
        n = len(fp.fragments)
        assert n >= 2
        mean = Decimal("400000") / n
        ratios += [float(f.units / mean) for f in fp.fragments]
        times = [f.scheduled_at for f in fp.fragments]
        gaps += [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    # sizes: uniform(0.85,1.15) renormalised => envelope [0.85/1.15, 1.15/0.85]
    assert all(0.70 <= r <= 1.40 for r in ratios)
    assert max(ratios) - min(ratios) > 0.05          # not degenerate
    assert all(0.5 <= g <= 3.0 for g in gaps)        # exact spec bounds
    assert max(gaps) - min(gaps) > 0.1


def test_no_fragment_below_min_and_dust_is_merged() -> None:
    cfg = exec_cfg(fragment_threshold_lots=1.0, min_fragment_lots=0.9)
    for seed in range(30):
        fp = plan("o", Decimal("210000"), fast_decay=False, cfg=cfg,
                  venues=["mock"], now=T0, rng=Random(seed))
        assert all(f.units >= Decimal("90000") for f in fp.fragments)
        assert sum(f.units for f in fp.fragments) == Decimal("210000")


def test_path_classification() -> None:
    cfg = exec_cfg()
    small = plan("o", Decimal("50000"), fast_decay=False, cfg=cfg,
                 venues=["mock"], now=T0, rng=Random(1))
    assert small.path == "single" and len(small.fragments) == 1
    frag = plan("o", Decimal("300000"), fast_decay=False, cfg=cfg,
                venues=["mock"], now=T0, rng=Random(1))
    assert frag.path == "fragment" and len(frag.fragments) >= 2
    ioc = plan("o", Decimal("900000"), fast_decay=True, cfg=cfg,
               venues=["mock"], now=T0, rng=Random(1))
    assert ioc.path == "ioc" and len(ioc.fragments) == 1   # speed over stealth


def test_scheduled_path_spreads_across_window_time_weighted() -> None:
    fp = plan("o", Decimal("800000"), fast_decay=False, cfg=exec_cfg(),
              venues=["mock"], now=T0, rng=Random(5))
    assert fp.path == "scheduled"
    assert fp.weighting == "time"        # v2.11: never mislabelled as VWAP
    span = (max(f.scheduled_at for f in fp.fragments)
            - min(f.scheduled_at for f in fp.fragments)).total_seconds()
    assert span >= 200                   # genuinely spread across the 300s window
    assert sum(f.units for f in fp.fragments) == Decimal("800000")


def test_signature_randomisation_consecutive_plans_differ() -> None:
    rng = Random(11)
    a = plan("o1", Decimal("400000"), fast_decay=False, cfg=exec_cfg(),
             venues=["mock"], now=T0, rng=rng)
    b = plan("o2", Decimal("400000"), fast_decay=False, cfg=exec_cfg(),
             venues=["mock"], now=T0, rng=rng)
    assert [f.units for f in a.fragments] != [f.units for f in b.fragments]


def test_venue_rotation_uses_multiple_venues() -> None:
    fp = plan("o", Decimal("800000"), fast_decay=False, cfg=exec_cfg(),
              venues=["v1", "v2"], now=T0, rng=Random(2))
    assert {f.venue for f in fp.fragments} == {"v1", "v2"}


# ---------------------------- slippage ---------------------------- #

def test_slippage_sign_adverse_positive_both_sides() -> None:
    assert slippage_bps(1.10, 1.1001, 1) > 0     # paid more buying: adverse
    assert slippage_bps(1.10, 1.0999, 1) < 0     # favourable buy
    assert slippage_bps(1.10, 1.0999, -1) > 0    # received less selling: adverse
    assert slippage_bps(1.10, 1.1001, -1) < 0


# ---------------------------- orchestrator ---------------------------- #

async def test_zero_size_is_noop(tmp_path) -> None:
    orch, log, store, _ = mk_orchestrator(tmp_path)
    order = SizedOrder(
        order_id="z", signal_id="s", instrument="EUR_USD", direction=1,
        size_units=Decimal("0"), entry_price=1.10, stop_loss=1.09,
        take_profit=None, reason="veto", factors_snapshot=MappingProxyType({}),
        sized_at=T0, param_set_id="ps", action="open")
    assert await orch.submit(order, valid_for_seconds=300) == ()
    assert log.events("EXEC_NOOP") and store.row_count() == 0


async def test_full_fill_lifecycle_and_store(tmp_path) -> None:
    orch, log, store, slept = mk_orchestrator(tmp_path)
    reports = await orch.submit(mk_order("250000"), valid_for_seconds=300)
    assert all(r.status is FillStatus.FILLED for r in reports)
    total = sum((r.filled_units for r in reports), Decimal("0"))
    assert total == Decimal("250000")            # C-EXE-6: exactly as sized
    assert store.row_count() == len(reports)
    assert log.events("FRAGMENT_PLAN") and log.events("FILL")
    assert all(0.5 <= s <= 3.0 for s in slept[1:])   # inter-fragment jitter honoured


async def test_frozen_blocks_opens_allows_closes(tmp_path) -> None:
    # Reduce-only closes (builder F1) made this STRICTER: the freeze admits only them. A
    # "close" into a flat venue used to FILL (opening a position during a flatten);
    # it is now REJECTED, and only a close of a position the venue holds goes through.
    face = MockExecutionFace()
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    orch.set_freeze(True, "risk_flatten")
    assert await orch.submit(mk_order("100000"), valid_for_seconds=300) == ()
    assert log.events("EXEC_FROZEN_REJECT")
    flat = await orch.submit(mk_order("100000", action="close", order_id="c-flat"),
                             valid_for_seconds=300)
    assert [r.status for r in flat] == [FillStatus.REJECTED]        # nothing to close
    assert await face.open_positions() == () and log.events("EXEC_CLOSE_REFUSED")
    orch.set_freeze(False, "test")
    await orch.submit(mk_order("100000", order_id="o-long"), valid_for_seconds=300)
    orch.set_freeze(True, "risk_flatten")
    closes = await orch.submit(mk_order("100000", action="close", order_id="c-long"),
                               valid_for_seconds=300)
    assert [r.status for r in closes] == [FillStatus.FILLED]         # a flatten can close
    assert closes[0].direction == -1                                 # by trading the other side
    assert await face.open_positions() == ()                         # and the venue is FLAT


async def test_capability_reject_unknown_instrument(tmp_path) -> None:
    orch, log, store, _ = mk_orchestrator(tmp_path)
    reports = await orch.submit(mk_order(instrument="XAU_USD"),
                                valid_for_seconds=300)
    assert len(reports) == 1 and reports[0].status is FillStatus.REJECTED
    assert log.events("EXEC_CAPABILITY_REJECT")
    assert store.row_count() == 1                # loud AND reported, never silent


async def test_capability_reject_ioc_unsupported(tmp_path) -> None:
    face = MockExecutionFace()
    no_ioc = CapabilityDescriptor(
        venue="mock", order_types=frozenset({"market"}), supports_ioc=False,
        account_model="netting", partial_close=True, min_lot=0.01,
        lot_step=0.01, max_order_lots=100.0,
        symbol_map={"EUR_USD": "EUR_USD"}, quote_depth=False,
        asset_classes=frozenset({"fx"}), server_side_stops=True)
    face.descriptor = no_ioc
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=10)  # fast decay
    assert reports[0].status is FillStatus.REJECTED
    assert log.events("EXEC_CAPABILITY_REJECT")[0]["data"]["ioc"] is True


async def test_capability_reject_exceeds_max_order_lots(tmp_path) -> None:
    face = MockExecutionFace()
    small = CapabilityDescriptor(
        venue="mock", order_types=frozenset({"market"}), supports_ioc=True,
        account_model="netting", partial_close=True, min_lot=0.01,
        lot_step=0.01, max_order_lots=1.0,
        symbol_map={"EUR_USD": "EUR_USD"}, quote_depth=False,
        asset_classes=frozenset({"fx"}), server_side_stops=True)
    face.descriptor = small
    orch, _, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("900000"), valid_for_seconds=300)
    assert reports[0].status is FillStatus.REJECTED


async def test_partial_fill_remainder_completes_never_exceeds(tmp_path) -> None:
    face = MockExecutionFace(script=["partial:0.5", "fill"])
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.PARTIAL, FillStatus.FILLED]
    assert sum((r.filled_units for r in reports), Decimal("0")) == Decimal("100000")
    assert reports[1].fragment_id.endswith(":p1")


async def test_partial_retries_are_bounded(tmp_path) -> None:
    face = MockExecutionFace(script=["partial:0.5", "partial:0.5", "partial:0.5",
                                     "partial:0.5"])
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert len(reports) == 1 + orch_mod.MAX_REMAINDER_RETRIES
    filled = sum((r.filled_units for r in reports), Decimal("0"))
    assert filled < Decimal("100000")            # honest shortfall, no overshoot
    assert log.events("EXEC_PARTIAL_GIVEUP")


async def test_reject_reroutes_to_next_best_venue_bounded(tmp_path) -> None:
    bad = MockExecutionFace(script=["reject"])
    good = MockExecutionFace()
    good.name = "mock2"
    good.descriptor = CapabilityDescriptor(
        venue="mock2", order_types=frozenset({"market"}), supports_ioc=True,
        account_model="netting", partial_close=True, min_lot=0.01, lot_step=0.01,
        max_order_lots=100.0, symbol_map={"EUR_USD": "EUR_USD"},
        quote_depth=False, asset_classes=frozenset({"fx"}), server_side_stops=True)
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": bad, "mock2": good})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    statuses = [r.status for r in reports]
    assert FillStatus.REJECTED in statuses and FillStatus.FILLED in statuses
    assert log.events("EXEC_REROUTE")
    filled = sum((r.filled_units for r in reports), Decimal("0"))
    assert filled == Decimal("100000")


async def test_persistent_reject_gives_up_no_spin(tmp_path) -> None:
    face = MockExecutionFace(script=["reject", "reject", "reject"])
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert all(r.status is FillStatus.REJECTED for r in reports)
    assert log.events("EXEC_REJECT_GIVEUP")
    assert face.submissions <= 2                 # bounded, no spin


async def test_disconnect_reconciles_then_retries_no_duplicate_fill(tmp_path) -> None:
    face = MockExecutionFace(script=["disconnect", "fill"])
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.FILLED]
    assert face.submissions == 1                 # exactly one venue hit
    rec = log.events("EXEC_RECONCILE")
    assert rec and rec[0]["data"]["broker_positions"] == []  # broker consulted first


async def test_double_disconnect_gives_up_loudly(tmp_path) -> None:
    face = MockExecutionFace(script=["disconnect", "disconnect"])
    orch, log, store, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert len(reports) == 1 and reports[0].status is FillStatus.REJECTED
    assert len(log.events("EXEC_RECONCILE")) == 2
    assert store.row_count() == 1                # the giveup is still reported


async def test_budget_exceeded_is_observed_never_gates(tmp_path, monkeypatch) -> None:
    ticks = iter(range(0, 1000))

    def fake_perf() -> float:
        return next(ticks) * 0.5                 # +500ms per observation

    monkeypatch.setattr(orch_mod.time, "perf_counter", fake_perf)
    orch, log, _, _ = mk_orchestrator(tmp_path)
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert reports and reports[0].status is FillStatus.FILLED   # executed anyway
    assert orch.budget_exceeded_count == 1
    assert log.events("EXEC_BUDGET_EXCEEDED")


async def test_slippage_alert_emitted_above_guardrail_mirror(tmp_path) -> None:
    face = MockExecutionFace(fill_offset=0.002)  # ~18 bps adverse on 1.10
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit(mk_order("100000"), valid_for_seconds=300)
    assert reports[0].slippage_bps > 8.0
    assert log.events("SLIPPAGE_ALERT")
    # F10: alert only — the filled quantity is untouched (no autonomous resize)
    assert reports[0].filled_units == Decimal("100000")


def test_store_ingestion_is_idempotent(tmp_path) -> None:
    store = FillReportStore(tmp_path / "f.db")
    from core.execution.venue import FillReport
    r = FillReport(
        fill_id="f1", order_id="o", fragment_id="g", instrument="EUR_USD",
        direction=1, requested_price=1.10, fill_price=1.10,
        filled_units=Decimal("1"), slippage_bps=0.0, fill_time=T0,
        venue="mock", status=FillStatus.FILLED, remaining_units=Decimal("0"),
        session_id="s")
    store.write(r)
    store.write(r)
    assert store.row_count() == 1
    store.close()


def test_venue_quality_orders_by_fills_slippage_rejects(tmp_path) -> None:
    from core.execution.venue import FillReport
    q = VenueQuality()

    def rep(venue, status, slip=0.0):
        return FillReport(
            fill_id=f"{venue}-{status.value}-{slip}", order_id="o",
            fragment_id="g", instrument="EUR_USD", direction=1,
            requested_price=1.10,
            fill_price=0.0 if status is FillStatus.REJECTED else 1.10,
            filled_units=Decimal("0") if status is FillStatus.REJECTED else Decimal("1"),
            slippage_bps=slip, fill_time=T0, venue=venue, status=status,
            remaining_units=Decimal("1") if status is FillStatus.REJECTED else Decimal("0"),
            session_id="s")

    q.update(rep("clean", FillStatus.FILLED))
    q.update(rep("slippy", FillStatus.FILLED, slip=20.0))
    q.update(rep("rejecty", FillStatus.REJECTED))
    assert q.score("clean", "EUR_USD") > q.score("slippy", "EUR_USD")
    assert q.score("clean", "EUR_USD") > q.score("rejecty", "EUR_USD")


# ---------------------------- attach (GAP-0018) ---------------------------- #

async def test_attach_verifies_symbol_map_and_flat_account() -> None:
    face = MockExecutionFace()
    log = CapturingLogger()
    await verify_attach(face, {"EUR_USD", "USD_JPY"}, log)   # flat: passes
    assert log.events("ATTACH_VERIFIED")
    with pytest.raises(DataQualityError):
        await verify_attach(face, {"EUR_USD", "XAU_USD"}, log)  # unmapped symbol


async def test_attach_halts_on_open_positions_flat_or_decide() -> None:
    face = MockExecutionFace()
    await face.submit_order(fragment_id="pre", order_id="o", instrument="EUR_USD",
                            direction=1, units=Decimal("1000"),
                            requested_price=1.10, ioc=False, now=T0,
                            session_id="s")
    log = CapturingLogger()
    with pytest.raises(AttachHalt) as exc:
        await verify_attach(face, {"EUR_USD"}, log)
    assert len(exc.value.positions) == 1
    assert log.events("ATTACH_HALTED_OPEN_POSITIONS")


# ---------------------------- schema gates ---------------------------- #

def test_execution_config_gates() -> None:
    with pytest.raises(Exception):
        exec_cfg(fragment_size_jitter=(1.05, 1.15))        # must straddle 1.0
    with pytest.raises(Exception):
        exec_cfg(fragment_time_jitter_s=(3.0, 0.5))        # ascending required
    with pytest.raises(Exception):
        exec_cfg(min_fragment_lots=2.0)                    # min > threshold
    with pytest.raises(Exception):
        exec_cfg(vwap_threshold_lots=0.5)                  # scheduled is the LARGE path
