"""The venue's quantity and request limits (GAP-P12D-57, core/execution/venue_limits.py)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random

import pytest

from core.data.errors import DataQualityError
from core.execution.fragmenter import plan
from core.execution.mock_face import MockExecutionFace
from core.execution.venue_limits import RequestBudget, venue_quantity
from tests.optimizer_fixtures import CapturingLogger
from tests.unit.test_execution import exec_cfg

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
MOCK = MockExecutionFace().descriptor                  # min 0.01 lot, step 0.01 lot = 1,000 units


@pytest.mark.parametrize("units, sendable, remainder", [
    ("332", "0", "332"),            # the SCOUT's typical Governor order: under the minimum
    ("999.99", "0", "999.99"),
    ("1000", "1000", "0"),          # exactly one minimum lot
    ("1926.40", "1000", "926.40"),  # rounded DOWN, never up to 2,000
    ("250000", "250000", "0"),
])
def test_quantity_rounds_down_to_whole_steps_and_refuses_below_the_minimum(
        units, sendable, remainder) -> None:
    assert venue_quantity(Decimal(units), MOCK) == (Decimal(sendable), Decimal(remainder))


def test_a_coarser_minimum_than_step_refuses_a_whole_step_below_it() -> None:
    d = replace(MOCK, min_lot=0.1, lot_step=0.01)     # min 10,000 units, step 1,000
    assert venue_quantity(Decimal("9000"), d) == (Decimal("0"), Decimal("9000"))
    assert venue_quantity(Decimal("10500"), d) == (Decimal("10000"), Decimal("500"))


def test_descriptor_refuses_a_lot_step_it_cannot_round_to() -> None:
    with pytest.raises(DataQualityError):
        replace(MOCK, lot_step=0.0)
    with pytest.raises(DataQualityError):
        replace(MOCK, lot_step=0.02, min_lot=0.01)    # a step coarser than the minimum


def test_request_budget_is_a_rolling_24_hours() -> None:
    log = CapturingLogger()
    budget = RequestBudget("v", 2, seed=[T0 - timedelta(hours=23)])
    assert budget.admit(T0, closing=False, order_id="a", log=log)
    assert not budget.admit(T0, closing=False, order_id="b", log=log)       # 2 in 24 h
    assert budget.used(T0 + timedelta(hours=1)) == 1                       # the seed aged out
    assert budget.admit(T0 + timedelta(hours=1), closing=False, order_id="c", log=log)
    assert [e["data"]["order_id"] for e in log.events("EXEC_REQUEST_BUDGET_REFUSED")] == ["b"]


def test_a_close_is_admitted_and_counted_past_the_budget() -> None:
    log = CapturingLogger()
    budget = RequestBudget("v", 1)
    assert budget.admit(T0, closing=False, order_id="open", log=log)
    assert budget.admit(T0, closing=True, order_id="close", log=log)
    assert budget.used(T0) == 2                    # counted: it still spends the venue's cap
    assert log.events("EXEC_REQUEST_BUDGET_DERISK")[0]["data"]["order_id"] == "close"


def test_fragments_are_whole_lot_steps_and_still_sum_exactly() -> None:
    step = Decimal("1000")
    for seed in range(50):
        fp = plan("o", Decimal("437000"), fast_decay=False, cfg=exec_cfg(),
                  venues=["mock"], now=T0, rng=Random(seed), quantum=step)
        assert sum(f.units for f in fp.fragments) == Decimal("437000")
        assert all(f.units % step == 0 and f.units >= step for f in fp.fragments)
