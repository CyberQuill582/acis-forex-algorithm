"""§7.5 adapter conformance suite (ACIS-06 v1.1 §7.5) — the RELEASE GATE every
execution face must pass before it may be selected in system_config.yaml.

Parametrized over adapter factories: v1 ships the mock face conformant here;
OANDA/MT5 faces (phase 12, ACIS-13) add themselves to ADAPTERS and must pass
this exact suite against their platform's demo environment, unchanged."""

from __future__ import annotations

import inspect
import re
from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.execution.venue import (
    BrokerAccount,
    CapabilityDescriptor,
    FillStatus,
    MockExecutionFace,
)

T0 = datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)

# adapter name -> factory (script hooks let the suite provoke partial/reject/
# disconnect on venues that support scripting; real platforms provoke them via
# their demo environments' test order types)
ADAPTERS = {
    "mock": lambda script=None: MockExecutionFace(script=script),
}


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request):
    return ADAPTERS[request.param]


async def _submit(face, fragment_id="c1", units="1000", instrument="EUR_USD",
                  direction=1, stop_loss=None):
    return await face.submit_order(
        fragment_id=fragment_id, order_id="ord-c", instrument=instrument,
        direction=direction, units=Decimal(units), requested_price=1.10, ioc=False,
        now=T0, session_id="conf", stop_loss=stop_loss)


async def test_round_trip_lifecycle(adapter) -> None:
    face = adapter()
    report = await _submit(face)
    assert report.status is FillStatus.FILLED
    assert report.filled_units == Decimal("1000")
    positions = await face.open_positions()
    assert len(positions) == 1
    assert positions[0].instrument == "EUR_USD"
    assert positions[0].size_units == Decimal("1000")


async def test_partial_fill_reports_remaining(adapter) -> None:
    face = adapter(script=["partial:0.25"])
    report = await _submit(face)
    assert report.status is FillStatus.PARTIAL
    assert report.filled_units == Decimal("250")
    assert report.remaining_units == Decimal("750")


async def test_rejection_is_a_report_not_a_silent_drop(adapter) -> None:
    face = adapter(script=["reject"])
    report = await _submit(face)
    assert report.status is FillStatus.REJECTED
    assert report.filled_units == 0
    assert report.remaining_units == Decimal("1000")


async def test_duplicate_submit_is_idempotent_one_venue_hit(adapter) -> None:
    face = adapter()
    a = await _submit(face, fragment_id="dup")
    b = await _submit(face, fragment_id="dup")
    assert a.fill_id == b.fill_id                     # the ORIGINAL report
    positions = await face.open_positions()
    assert positions[0].size_units == Decimal("1000")  # counted once


async def test_reconnect_mid_order_broker_is_authoritative(adapter) -> None:
    face = adapter(script=["disconnect", "fill"])
    with pytest.raises(ConnectionError):
        await _submit(face, fragment_id="rc")
    # the failed submission must NOT have reached the venue
    assert await face.open_positions() == ()
    report = await _submit(face, fragment_id="rc")    # reconciled retry
    assert report.status is FillStatus.FILLED
    positions = await face.open_positions()
    assert positions[0].size_units == Decimal("1000")  # exactly once


async def test_cancel_semantics(adapter) -> None:
    face = adapter()
    assert await face.cancel("never-submitted") is True   # guaranteed unfilled
    await _submit(face, fragment_id="done")
    assert await face.cancel("done") is False             # already executed


async def test_account_snapshot_is_decimal_grade(adapter) -> None:
    face = adapter()
    account = await face.account_snapshot()
    assert isinstance(account, BrokerAccount)
    for name in ("equity", "balance", "margin_used"):
        assert isinstance(getattr(account, name), Decimal)  # F17 boundary


def test_capability_descriptor_is_declared_data(adapter) -> None:
    face = adapter()
    d = face.descriptor
    assert isinstance(d, CapabilityDescriptor)
    assert {f.name for f in fields(d)} >= {
        "venue", "order_types", "supports_ioc", "account_model", "partial_close",
        "min_lot", "lot_step", "max_order_lots", "symbol_map", "quote_depth",
        "asset_classes", "server_side_stops"}
    assert "market" in d.order_types


# ── §279 server-side-stop placement (per-adapter release gate) ────────────────
# "every SizedOrder carries a stop-loss placed AT THE BROKER — position risk is
# bounded even if ACIS vanishes." A live-attachable adapter must (a) DECLARE the
# capability and (b) actually rest the stop at the venue, provably independent of
# engine memory. A demo/practice environment provokes the same via a real
# protective-stop order type; the mock proves the contract in v1.

def test_capability_declares_server_side_stops(adapter) -> None:
    d = adapter().descriptor
    assert isinstance(d.server_side_stops, bool)
    # v1 ships only live-attachable faces; a face that cannot hold stops is not
    # attachable for live and would be excluded here with its reason.
    assert d.server_side_stops is True


async def test_server_side_stop_rests_at_broker(adapter) -> None:
    face = adapter()
    await _submit(face, stop_loss=1.09)
    # the stop lives at the VENUE, keyed to the position — a fresh query (an
    # engine restart / a different client) still sees it: it is not in ACIS.
    stops = await face.resting_stops()
    assert stops.get("EUR_USD") == 1.09
    (pos,) = await face.open_positions()
    assert pos.stop_loss == 1.09           # the position is protected at the broker


async def test_server_side_stop_retires_when_flat(adapter) -> None:
    face = adapter()
    await _submit(face, stop_loss=1.09)
    await _submit(face, fragment_id="close", units="1000", direction=-1)
    assert await face.open_positions() == ()      # flat
    assert await face.resting_stops() == {}       # the resting stop is gone with it


async def test_stop_on_a_venue_that_cannot_hold_it_is_refused(adapter) -> None:
    """Capability honesty: a face declaring server_side_stops=False must REJECT
    an order carrying a stop — never accept it unprotected (silent emulation)."""
    from dataclasses import replace

    face = adapter()
    if face.descriptor.server_side_stops:
        face.descriptor = replace(face.descriptor, server_side_stops=False)
    with pytest.raises(Exception):
        await _submit(face, stop_loss=1.09)
    assert await face.open_positions() == ()      # nothing opened unprotected


def test_symbol_map_covers_enabled_universe(adapter, acis_config) -> None:
    face = adapter()
    enabled = {s for s, sp in acis_config.instruments.instruments.items()
               if sp.enabled}
    missing = enabled - set(face.descriptor.symbol_map)
    assert not missing, f"descriptor must map the enabled universe: {missing}"


def test_gap0013_feed_face_still_exposes_no_account_surface() -> None:
    """The §7.5 split, asserted from the conformance side too: the FEED faces
    carry no account/position/order surface — that lives only on the execution
    face, flowing downward to Risk."""
    from core.data import feeds

    forbidden = re.compile(r"account|position|equity|margin|balance|order",
                           re.IGNORECASE)
    for _, cls in inspect.getmembers(feeds, inspect.isclass):
        if cls.__module__ != feeds.__name__:
            continue
        for member in dir(cls):
            if not member.startswith("_"):
                assert not forbidden.search(member)


# ── GAP-P12D-57: the venue's quantity and request limits, held by the execution path ──
# Composed over each adapter through the REAL orchestrator: whatever a face declares
# as its minimum lot, lot step and request cap, the engine never sends a quantity the
# venue cannot take, never rounds one UP, never exceeds the budget on an open — and a
# close always goes through.

def _orchestrator(face, tmp_path, *, requests_per_day=1000, now=T0, store=None):
    from random import Random

    from config.schemas import ExecutionConfig
    from core.execution.orchestrator import ExecutionOrchestrator
    from core.execution.venue import FillReportStore, VenueQuality
    from tests.optimizer_fixtures import CapturingLogger

    async def instant(_s: float) -> None:
        return None

    log = CapturingLogger()
    cfg = ExecutionConfig(
        fragment_threshold_lots=1.0, fragment_size_jitter=(0.85, 1.15),
        fragment_time_jitter_s=(0.5, 3.0), min_fragment_lots=0.10, vwap_threshold_lots=5.0,
        vwap_window_s=300, fast_decay_seconds=30, signature_lot_variance=0.15,
        dispatch_budget_ms=100, max_venue_requests_per_day=requests_per_day)
    orch = ExecutionOrchestrator(
        cfg, {face.name: face}, VenueQuality(), store or FillReportStore(tmp_path / "f.db"),
        slippage_alert_bps=8.0, rng=Random(7), logger=log, session_id="conf",
        now_fn=lambda: now, sleep_fn=instant)
    return orch, log


def _order(units, action="open", direction=1, order_id="o-lim"):
    from types import MappingProxyType

    from core.governor.portfolio_types import SizedOrder
    return SizedOrder(
        order_id=order_id, signal_id="s", instrument="EUR_USD", direction=direction,
        size_units=Decimal(str(units)), entry_price=1.10, stop_loss=1.09, take_profit=None,
        reason="formula", factors_snapshot=MappingProxyType({}), sized_at=T0,
        param_set_id="ps", action=action)


def _lot_units(lots: float) -> Decimal:
    return Decimal(str(lots)) * Decimal("100000")


async def test_sub_minimum_order_is_refused_and_never_reaches_the_venue(adapter, tmp_path) -> None:
    face = adapter()
    below = _lot_units(face.descriptor.min_lot) - _lot_units(face.descriptor.lot_step) / 2
    orch, log = _orchestrator(face, tmp_path)
    reports = await orch.submit(_order(below), valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.REJECTED]   # a report, not a drop
    assert reports[0].remaining_units == below
    assert await face.open_positions() == ()                      # the venue never saw it
    assert log.events("EXEC_MIN_LOT_REFUSED")


async def test_quantity_is_rounded_down_to_the_lot_step_never_up(adapter, tmp_path) -> None:
    face = adapter()
    step, minimum = _lot_units(face.descriptor.lot_step), _lot_units(face.descriptor.min_lot)
    sized = minimum * 2 + step * Decimal("0.345")                 # not a whole number of steps
    orch, log = _orchestrator(face, tmp_path)
    reports = await orch.submit(_order(sized), valid_for_seconds=300)
    filled = sum((r.filled_units for r in reports), Decimal("0"))
    unsent = sum((r.remaining_units for r in reports if r.status is FillStatus.REJECTED),
                 Decimal("0"))
    assert filled == minimum * 2                                  # DOWN to the step
    assert filled % step == 0 and filled <= sized                 # never a part-step, never up
    assert filled + unsent == sized                               # the remainder is reported
    (pos,) = await face.open_positions()
    assert pos.size_units == filled
    assert log.events("EXEC_LOT_STEP_ROUNDED")


async def test_spent_request_budget_refuses_opens_but_never_a_close(adapter, tmp_path) -> None:
    face = adapter()
    lot = _lot_units(face.descriptor.min_lot)
    orch, log = _orchestrator(face, tmp_path, requests_per_day=2)
    for i in range(2):
        (r,) = await orch.submit(_order(lot, order_id=f"o{i}"), valid_for_seconds=300)
        assert r.status is FillStatus.FILLED
    refused = await orch.submit(_order(lot, order_id="o-over"), valid_for_seconds=300)
    assert [r.status for r in refused] == [FillStatus.REJECTED]
    (pos,) = await face.open_positions()
    assert pos.size_units == lot * 2                              # the refused open never got there
    assert log.events("EXEC_REQUEST_BUDGET_REFUSED")
    # de-risking is never throttled: the close goes through, and the exception is logged
    closed = await orch.submit(_order(lot * 2, action="close", direction=-1,
                                      order_id="o-close"), valid_for_seconds=300)
    assert [r.status for r in closed] == [FillStatus.FILLED]
    assert await face.open_positions() == ()
    assert log.events("EXEC_REQUEST_BUDGET_DERISK")


async def test_spent_budget_refuses_a_close_that_would_add_to_the_position(adapter,
                                                                         tmp_path) -> None:
    # Only a close that truly shrinks the venue position is exempt. A `close` carrying
    # the position's OWN direction (as the Governor's group exits do today) would add
    # to it, so it is an open in all but name and is refused once the budget is spent.
    face = adapter()
    lot = _lot_units(face.descriptor.min_lot)
    orch, log = _orchestrator(face, tmp_path, requests_per_day=1)
    await orch.submit(_order(lot, order_id="o-long"), valid_for_seconds=300)
    adds = await orch.submit(_order(lot, action="close", direction=1, order_id="o-mislabel"),
                             valid_for_seconds=300)
    assert [r.status for r in adds] == [FillStatus.REJECTED]
    (pos,) = await face.open_positions()
    assert pos.size_units == lot                                  # not doubled
    too_big = await orch.submit(_order(lot * 2, action="close", direction=-1,
                                       order_id="o-flip"), valid_for_seconds=300)
    assert [r.status for r in too_big] == [FillStatus.REJECTED]   # would flip, not close
    assert log.events("EXEC_REQUEST_BUDGET_REFUSED")


async def test_request_budget_survives_a_restart(adapter, tmp_path) -> None:
    from datetime import timedelta

    from core.execution.venue import FillReportStore
    face = adapter()
    lot = _lot_units(face.descriptor.min_lot)
    store = FillReportStore(tmp_path / "fills.db")
    orch, _ = _orchestrator(face, tmp_path, requests_per_day=2, store=store)
    for i in range(2):
        await orch.submit(_order(lot, order_id=f"o{i}"), valid_for_seconds=300)
    # a fresh process on the same fill log, an hour later: the budget is still spent
    orch2, log2 = _orchestrator(face, tmp_path, requests_per_day=2, store=store,
                                now=T0 + timedelta(hours=1))
    refused = await orch2.submit(_order(lot, order_id="o-after"), valid_for_seconds=300)
    assert [r.status for r in refused] == [FillStatus.REJECTED]
    assert log2.events("EXEC_REQUEST_BUDGET_REFUSED")
    # 25 hours on, the rolling 24-hour window has passed: opens flow again
    orch3, _ = _orchestrator(face, tmp_path, requests_per_day=2, store=store,
                             now=T0 + timedelta(hours=25))
    (r,) = await orch3.submit(_order(lot, order_id="o-next-day"), valid_for_seconds=300)
    assert r.status is FillStatus.FILLED
