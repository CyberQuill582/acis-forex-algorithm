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


async def _submit(face, fragment_id="c1", units="1000", instrument="EUR_USD"):
    return await face.submit_order(
        fragment_id=fragment_id, order_id="ord-c", instrument=instrument,
        direction=1, units=Decimal(units), requested_price=1.10, ioc=False,
        now=T0, session_id="conf")


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
        "asset_classes"}
    assert "market" in d.order_types


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
