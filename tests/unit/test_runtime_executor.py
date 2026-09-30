"""The runtime's executor (core/runtime/executor.py): busy until reported, evaluate on fills only,
never through flat, a failing item halts without killing the loop, a flatten sized when it runs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from core.execution.venue import FillReport, FillStatus
from core.risk.risk_types import RiskPosition
from core.runtime.executor import Executor, WorkItem
from tests.optimizer_fixtures import CapturingLogger
from tests.unit.test_runtime_policy import order

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def report(o, filled: str) -> FillReport:
    side = -o.direction if o.action == "close" else o.direction      # the side traded
    units = Decimal(filled)
    return FillReport(fill_id=f"{o.order_id}:f", order_id=o.order_id, fragment_id=o.order_id,
                      instrument=o.instrument, direction=side, requested_price=o.entry_price,
                      fill_price=o.entry_price if units else 0.0, filled_units=units, slippage_bps=0.0,
                      fill_time=T0, venue="fake",
                      status=FillStatus.FILLED if units == o.size_units else
                      (FillStatus.PARTIAL if units else FillStatus.REJECTED),
                      remaining_units=o.size_units - units, session_id="t")


class FakeRisk:
    def __init__(self) -> None:
        self.held: dict[str, Decimal] = {}          # instrument -> signed units
        self.noted: list[str] = []

    def positions(self):
        return tuple(RiskPosition(instrument=i, direction=1 if u > 0 else -1, size_units=abs(u),
                                  avg_entry_price=1.1, opened_at=T0, param_set_id="ps")
                     for i, u in self.held.items() if u)

    def note_order(self, o) -> None:
        self.noted.append(o.order_id)

    def ingest(self, r: FillReport) -> None:
        net = self.held.get(r.instrument, Decimal("0")) + r.direction * r.filled_units
        self.held[r.instrument] = net
        if not net:
            del self.held[r.instrument]

    def observe_slippage(self, bps: float) -> None:
        pass


class FakeOrch:
    def __init__(self, fills: dict[str, str] | None = None, boom: str | None = None) -> None:
        self.fills, self.boom, self.sent = fills or {}, boom, []

    async def submit(self, o, *, valid_for_seconds: int):
        if o.order_id == self.boom:
            raise RuntimeError("venue exploded")
        self.sent.append((o.action, o.instrument, o.size_units))
        return (report(o, self.fills.get(o.order_id, str(o.size_units))),)


def executor(risk, orch, *, route=True):
    fills, halts = [], []

    async def on_fill() -> None:
        fills.append(1)

    ex = Executor(route_to=lambda: orch if route else None, risk=risk, on_fill=on_fill,
                  halt=lambda scope, why: halts.append((scope, why)), mark_of=lambda i: 1.1,
                  now_fn=lambda: T0, logger=CapturingLogger())
    return ex, fills, halts


async def drain(ex: Executor) -> None:
    task = asyncio.create_task(ex.run())
    await ex.queue.join()
    task.cancel()


async def test_busy_until_reported_and_risk_is_evaluated_only_on_a_fill() -> None:
    risk, orch = FakeRisk(), FakeOrch(fills={"o-USD_JPY-1": "0"})
    ex, fills, _ = executor(risk, orch)
    ex.submit(WorkItem((order(),), 300))
    ex.submit(WorkItem((order("USD_JPY"),), 300))              # rejected at the venue
    assert ex.busy == {"EUR_USD", "USD_JPY"}
    await drain(ex)
    assert ex.busy == set() and fills == [1]                     # one fill, one evaluate
    assert risk.noted == ["o-EUR_USD-1", "o-USD_JPY-1"]          # Risk heard both before the send


async def test_a_reversal_never_opens_through_a_holding_its_close_left() -> None:
    risk = FakeRisk()
    risk.held["EUR_USD"] = Decimal("1000")
    close = order(action="close")
    orch = FakeOrch(fills={close.order_id: "400"})               # the close fills only in part
    ex, _, _ = executor(risk, orch)
    ex.submit(WorkItem((close, order(direction=-1)), 300))
    await drain(ex)
    assert orch.sent == [("close", "EUR_USD", Decimal("1000"))]  # the short was never sent
    assert risk.held == {"EUR_USD": Decimal("600")}


async def test_a_failing_item_halts_entries_and_the_next_item_still_runs() -> None:
    risk, orch = FakeRisk(), FakeOrch(boom="o-EUR_USD-1")
    ex, _, halts = executor(risk, orch)
    ex.submit(WorkItem((order(),), 300))
    ex.submit(WorkItem((order("USD_JPY"),), 300))
    await drain(ex)
    assert halts == [("all", "executor_error")]
    assert orch.sent == [("open", "USD_JPY", Decimal("1000"))] and ex.busy == set()


async def test_a_flatten_closes_what_is_held_when_it_runs_not_when_queued() -> None:
    risk, orch = FakeRisk(), FakeOrch()
    ex, _, _ = executor(risk, orch)
    ex.submit(WorkItem((order(),), 300))                         # in flight ahead of the flatten
    ex.submit_flatten("all", "mcp")                              # queued while nothing is held
    await drain(ex)
    assert orch.sent == [("open", "EUR_USD", Decimal("1000")), ("close", "EUR_USD", Decimal("1000"))]
    assert risk.held == {}


async def test_a_mode_that_sends_nothing_sends_nothing() -> None:
    risk, orch = FakeRisk(), FakeOrch()
    ex, fills, _ = executor(risk, orch, route=False)
    ex.submit(WorkItem((order(),), 300))
    await drain(ex)
    assert orch.sent == [] and fills == [] and ex.busy == set()
