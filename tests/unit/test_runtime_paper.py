"""The paper venue: a stop fires on the mark, and equity is the paper ledger (core/runtime/paper.py)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.data.errors import DataQualityError
from core.execution.mock_face import MockExecutionFace
from core.optimizer.costs import CostModel
from core.runtime.paper import PaperVenue

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
COST = CostModel(commission_per_side=0.00001, slippage_per_side=0.00001)


def usd(amount: str):
    return pytest.approx(Decimal(amount), abs=Decimal("1e-9"))


def venue(**costs) -> PaperVenue:
    return PaperVenue(MockExecutionFace().descriptor, costs or {"EUR_USD": COST}, Decimal("10000"))


async def _open(v, instrument="EUR_USD", direction=1, price=1.10, stop=1.09, fid="f1"):
    return await v.submit_order(fragment_id=fid, order_id="o", instrument=instrument,
                                direction=direction, units=Decimal("1000"), requested_price=price,
                                ioc=True, now=T0, session_id="s", stop_loss=stop)


async def test_a_resting_stop_fires_on_the_mark_through_a_gap_and_arrives_unsolicited() -> None:
    v = venue()
    v.on_mark("EUR_USD", 1.0999, 1.1001, T0)
    await _open(v)
    assert v.on_mark("EUR_USD", 1.0905, 1.0915, T0) is None       # mid 1.091: above the stop
    fired = v.on_mark("EUR_USD", 1.0880, 1.0890, T0)               # mid 1.0885: gapped through
    assert (fired.fill_price, fired.requested_price, fired.direction) == (1.0885, 1.09, -1)
    assert fired.order_id.startswith("venue:")
    assert await asyncio.wait_for(anext(v.venue_fills()), 1) is fired
    assert await v.open_positions() == () and v.on_mark("EUR_USD", 1.0, 1.0002, T0) is None


async def test_paper_equity_is_nav_plus_realised_minus_friction_plus_open_pnl() -> None:
    v = venue()
    v.on_mark("EUR_USD", 1.0999, 1.1001, T0)                       # spread 0.0002
    await _open(v)                                                 # side cost 0.00012 × 1000
    assert (await v.account_snapshot()).equity == usd("9999.88")  # (the cost model is float)
    v.on_mark("EUR_USD", 1.1009, 1.1011, T0)                       # +0.0010 × 1000 open
    assert (await v.account_snapshot()).equity == usd("10000.88")
    await v.close_position(fragment_id="c1", order_id="o", instrument="EUR_USD", direction=1,
                           units=Decimal("1000"), requested_price=1.1010, now=T0, session_id="s")
    account = await v.account_snapshot()
    assert account.equity == account.balance == usd("10000.76")    # +1.00 − 2 × 0.12


async def test_yen_pnl_is_booked_in_usd_and_a_cross_is_refused() -> None:
    v = venue(USD_JPY=CostModel(commission_per_side=0.0, slippage_per_side=0.0))
    v.on_mark("USD_JPY", 150.0, 150.0, T0)
    await _open(v, "USD_JPY", price=150.0, stop=149.0)
    await v.close_position(fragment_id="c1", order_id="o", instrument="USD_JPY", direction=1,
                           units=Decimal("1000"), requested_price=151.0, now=T0, session_id="s")
    booked = (await v.account_snapshot()).balance - Decimal("10000")
    assert booked == usd(str(Decimal(1000) / Decimal(151)))
    cross = venue(EUR_GBP=COST)
    with pytest.raises(DataQualityError):
        await _open(cross, "EUR_GBP", price=0.86, stop=0.85)
