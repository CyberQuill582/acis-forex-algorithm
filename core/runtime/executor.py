"""The runtime's executor: venue work, one item at a time, through the mode's orchestrator.

Invariants:
  * An item's instruments are BUSY from `submit` until its last report is ingested, so the
    position policy routes nothing new to them meanwhile (GAP-0075: no firehose). Its opens and
    closes are IN FLIGHT over the same span, and the Governor's portfolio counts them (R16I-05, PR16I-04).
  * Items run serially, in the order the fast loop decided them.
  * Orders go only to the current mode's orchestrator (`route_to`): paper → the paper venue,
    practice → the attached venue. Any other answer sends nothing; this module opens no gate.
  * A reversal opens only once its close has left the instrument flat: never through flat.
  * Risk hears every order before it is sent (`note_order`) and every report after, and is
    evaluated on each fill (GAP-0099), so the equity breaker does not wait for its cadence.
  * A flatten closes what is held WHEN IT RUNS, not when it was queued: an open still in flight
    ahead of it may fill, and a close sized at queue time would leave that remainder open.
  * An item that raises is logged and halts entries through the edge; the executor keeps
    running, because a later close (a flatten) must still reach the venue.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import FillReport
from core.governor.portfolio_types import SizedOrder
from core.runtime.policy import close_of
from core.signals.signal_types import StrategyType


@dataclass(frozen=True)
class WorkItem:
    orders: tuple[SizedOrder, ...]
    valid_for_seconds: int                 # the signal's validity (ACIS-06: IOC below fast decay)
    group: bool = False                    # both legs or neither (ACIS-06 submit_group)
    strategy: StrategyType | None = None   # recorded for the Governor's portfolio
    flatten: tuple[str, str] | None = None     # (scope, reason): closes built when it runs
    holds: frozenset[str] = frozenset()        # instruments a flatten keeps busy meanwhile

    @property
    def instruments(self) -> frozenset[str]:
        return frozenset(o.instrument for o in self.orders) | self.holds


class Executor:
    def __init__(self, *, route_to: Callable[[], ExecutionOrchestrator | None], risk,
                 on_fill: Callable[[], Awaitable[None]], halt: Callable[[str, str], None],
                 mark_of: Callable[[str], float | None], now_fn: Callable[[], datetime],
                 logger) -> None:
        self._route_to, self._risk, self._on_fill, self._halt = route_to, risk, on_fill, halt
        self._mark_of, self._now, self._log = mark_of, now_fn, logger
        self.queue: asyncio.Queue[WorkItem] = asyncio.Queue()
        self.busy: set[str] = set()
        self.inflight: dict[str, SizedOrder] = {}      # orders submitted, not yet reported (PR16I-04)
        self.strategy_of: dict[str, StrategyType] = {}

    def submit(self, item: WorkItem) -> None:
        self.busy |= item.instruments
        self.inflight.update((o.order_id, o) for o in item.orders if o.action in ("open", "close"))
        self.queue.put_nowait(item)

    def submit_flatten(self, scope: str, reason: str) -> None:
        held = frozenset(p.instrument for p in self._risk.positions()
                         if scope in ("all", p.instrument))
        self.submit(WorkItem((), valid_for_seconds=0, flatten=(scope, reason), holds=held))

    async def run(self) -> None:
        while True:
            item = await self.queue.get()
            try:
                await self._run(item)
            except Exception as exc:              # logged, entries halted, the loop lives on
                self._log.event("EXECUTOR_ITEM_FAILED", error=repr(exc),
                                orders=[o.order_id for o in item.orders])
                self._halt("all", "executor_error")
            finally:
                self.busy -= item.instruments
                for o in item.orders:
                    self.inflight.pop(o.order_id, None)
                self.queue.task_done()

    async def _run(self, item: WorkItem) -> None:
        orch = self._route_to()
        if orch is None:
            self._log.event("ORDER_NOT_SENT", reason="mode_sends_no_orders",
                            orders=[o.order_id for o in item.orders])
            return
        if item.flatten is not None:
            item = self._closes_now(item)
        if item.group:
            for leg in item.orders:
                self._risk.note_order(leg)
            await self._ingest(await orch.submit_group(item.orders,
                                                       valid_for_seconds=item.valid_for_seconds),
                               item.strategy)
            return
        for i, order in enumerate(item.orders):
            if i and order.action == "open" and not self._flat(item.orders[i - 1].instrument):
                self._log.event("REVERSAL_HELD", order_id=order.order_id,
                                instrument=order.instrument, reason="the close left a holding")
                return
            self._risk.note_order(order)
            await self._ingest(await orch.submit(order, valid_for_seconds=item.valid_for_seconds),
                               item.strategy)

    def _closes_now(self, item: WorkItem) -> WorkItem:
        scope, reason = item.flatten
        now = self._now()
        closes = tuple(close_of(p, reason=f"flatten:{reason}", now=now,
                                price=self._mark_of(p.instrument) or p.avg_entry_price)
                       for p in self._risk.positions() if scope in ("all", p.instrument))
        self._log.event("FLATTEN_CLOSES", scope=scope, reason=reason,
                        instruments=[c.instrument for c in closes])
        return WorkItem(closes, valid_for_seconds=0, holds=item.holds)

    def _flat(self, instrument: str) -> bool:
        return all(p.instrument != instrument for p in self._risk.positions())

    async def _ingest(self, reports: tuple[FillReport, ...], strategy: StrategyType | None) -> None:
        filled = False
        for report in reports:
            self._risk.ingest(report)
            if report.filled_units > 0:
                filled = True
                self._risk.observe_slippage(report.slippage_bps)
        held = {p.instrument for p in self._risk.positions()}
        for report in reports:                     # the strategy follows the holding it opened
            if report.instrument not in held:
                self.strategy_of.pop(report.instrument, None)
            elif strategy is not None and report.filled_units > 0:
                self.strategy_of.setdefault(report.instrument, strategy)
        if filled:
            await self._on_fill()
