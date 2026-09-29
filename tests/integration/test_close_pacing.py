"""Closes the venue keeps refusing are paced, never blocked (audits X6 / F5).

The audit's repro (`r4_budget.py` (b)): a request budget of 5 a day, a long held, and a
venue that rejects every close, re-emitted 20 times (the weekend flatten's every-tick
contract) — 21 venue submits against a budget of 5, because a close is never refused
by the budget. Now a failing close backs off exponentially per (venue, instrument), a
daily ceiling pins it to the slowest pace, and the attempts survive a restart."""

from __future__ import annotations

from datetime import timedelta
from random import Random

from core.execution.close_pacing import BASE_S, CEILING, MAX_S
from core.execution.fill_store import FillReportStore
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import FillStatus
from core.execution.mock_face import MockExecutionFace
from core.execution.venue_quality import VenueQuality
from tests.optimizer_fixtures import CapturingLogger
from tests.unit.test_execution import T0, exec_cfg, mk_order


class CountingFace(MockExecutionFace):
    def __init__(self) -> None:
        super().__init__()
        self.closes = 0

    async def close_position(self, **kw):
        self.closes += 1
        return await super().close_position(**kw)


def _orch(tmp_path, face, clock, limit=5):
    async def nosleep(_s: float) -> None:
        return None
    log = CapturingLogger()
    orch = ExecutionOrchestrator(
        exec_cfg(max_venue_requests_per_day=limit), {"mock": face}, VenueQuality(),
        FillReportStore(tmp_path / "fills.db"), 8.0, Random(7), log, "s",
        now_fn=lambda: clock[0], sleep_fn=nosleep)
    return orch, log


async def _close(orch, i):
    return await orch.submit(mk_order("100000", action="close", order_id=f"c{i}"),
                             valid_for_seconds=300)


async def test_a_refused_close_is_paced_not_resent_every_tick(tmp_path) -> None:
    face, clock = CountingFace(), [T0]
    orch, log = _orch(tmp_path, face, clock)
    await orch.submit(mk_order("100000", order_id="open"), valid_for_seconds=300)
    face._script = ["reject"] * 100                          # the venue refuses every close
    for i in range(20):                                      # 20 re-emissions, same tick
        await _close(orch, i)
    assert face.closes == 1                                  # was 20: one per re-emission
    assert len(log.events("EXEC_CLOSE_PACED")) == 19         # every paced attempt logged
    clock[0] = T0 + timedelta(seconds=BASE_S)                # the first backoff has passed
    reports = await _close(orch, 20)
    assert face.closes == 2 and reports[0].status is FillStatus.REJECTED
    clock[0] += timedelta(seconds=BASE_S)                    # 2 s, but the next wait is 4 s
    await _close(orch, 21)
    assert face.closes == 2


async def test_a_close_is_never_blocked_outright(tmp_path) -> None:
    face, clock = CountingFace(), [T0]
    orch, _ = _orch(tmp_path, face, clock)
    await orch.submit(mk_order("100000", order_id="open"), valid_for_seconds=300)
    face._script = ["reject"] * 12
    for i in range(12):                                      # keeps failing ...
        await _close(orch, i)
        clock[0] += timedelta(seconds=MAX_S)
    face._script = []                                        # ... until the venue takes it
    reports = await _close(orch, 99)
    assert [r.status for r in reports] == [FillStatus.FILLED]
    assert await face.open_positions() == ()


async def test_the_pace_survives_a_restart(tmp_path) -> None:
    face, clock = CountingFace(), [T0]
    orch, _ = _orch(tmp_path, face, clock)
    await orch.submit(mk_order("100000", order_id="open"), valid_for_seconds=300)
    face._script = ["reject"] * 10
    await _close(orch, 0)                                    # one failure, recorded
    orch2, log2 = _orch(tmp_path, face, clock)               # a fresh process, same fill log
    await _close(orch2, 1)
    assert face.closes == 1 and log2.events("EXEC_CLOSE_PACED")


async def test_past_the_daily_ceiling_closes_go_at_the_slowest_pace(tmp_path) -> None:
    from core.execution.close_pacing import ClosePacer
    store = FillReportStore(tmp_path / "fills.db")
    pacer = ClosePacer(store, T0)
    at = T0
    for _ in range(CEILING):                                 # CEILING closes that all FILLED
        pacer.record("mock", "EUR_USD", at, True)
        at += timedelta(seconds=1)
    assert pacer.wait_s("mock", "EUR_USD", at) == MAX_S - 1  # pinned to the slowest pace
    assert pacer.wait_s("mock", "EUR_USD", at + timedelta(seconds=MAX_S)) == 0.0
