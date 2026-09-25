"""A pair group is both legs or neither in execution too (ACIS-05 §5.5; audit F11).

Regression tests from the audit's repro (`r9_pair_leg_rounding.py`): on the shipped mock
venue (minimum lot 0.01 = 1,000 units, same step), legs of EUR_USD +1,500 and USD_JPY −900
used to leave the venue holding ONE directional leg (+1,000) because each leg was rounded
and checked on its own. Now every leg is checked first and one refusal refuses the group,
and an open pair leg sent alone is refused."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from core.execution.venue import FillStatus, MockExecutionFace
from tests.unit.test_execution import mk_order, mk_orchestrator


def _pair(units_a: str, units_b: str):
    a = replace(mk_order(units_a, instrument="EUR_USD", order_id="leg-a"), group_id="g1")
    b = replace(mk_order(units_b, instrument="USD_JPY", order_id="leg-b"), group_id="g1",
                direction=-1)
    return a, b


async def test_a_leg_below_the_minimum_refuses_the_whole_group(tmp_path) -> None:
    face = MockExecutionFace()
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    reports = await orch.submit_group(_pair("1500", "900"), valid_for_seconds=300)
    assert [r.status for r in reports] == [FillStatus.REJECTED, FillStatus.REJECTED]
    assert await face.open_positions() == ()                 # FLAT, not one naked leg
    assert face.submissions == 0                             # nothing reached the venue
    assert log.events("EXEC_GROUP_REFUSED")[0]["data"]["legs"] == ["leg-b"]


async def test_a_pair_leg_sent_alone_is_refused(tmp_path) -> None:
    face = MockExecutionFace()
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    for leg in _pair("1500", "900"):                          # the audit's exact path
        (report,) = await orch.submit(leg, valid_for_seconds=300)
        assert report.status is FillStatus.REJECTED
    assert await face.open_positions() == ()
    assert len(log.events("EXEC_GROUP_LEG_ALONE")) == 2


async def test_a_group_the_venue_can_take_opens_both_legs(tmp_path) -> None:
    face = MockExecutionFace()
    orch, _, _, _ = mk_orchestrator(tmp_path, faces={"mock": face})
    await orch.submit_group(_pair("2000", "3000"), valid_for_seconds=300)
    held = {p.instrument: (p.direction, p.size_units) for p in await face.open_positions()}
    assert held == {"EUR_USD": (1, Decimal("2000")), "USD_JPY": (-1, Decimal("3000"))}


async def test_a_group_is_refused_when_the_budget_cannot_send_both_legs(tmp_path) -> None:
    from tests.unit.test_execution import exec_cfg
    face = MockExecutionFace()
    orch, log, _, _ = mk_orchestrator(tmp_path, faces={"mock": face},
                                      cfg=exec_cfg(max_venue_requests_per_day=2))
    await orch.submit(mk_order("1000", order_id="solo"), valid_for_seconds=300)  # 1 of 2 used
    reports = await orch.submit_group(_pair("2000", "3000"), valid_for_seconds=300)
    assert all(r.status is FillStatus.REJECTED for r in reports)
    assert {p.instrument for p in await face.open_positions()} == {"EUR_USD"}   # only "solo"
    assert log.events("EXEC_GROUP_REFUSED")
