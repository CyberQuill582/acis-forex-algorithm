"""The three-loop runtime (master §10): the fast loop, Risk's cadence, and the venue's work.

Invariants:
  * The fast loop (`on_state`, once per MarketState) is synchronous and only DECIDES: marks,
    the paper venue's stops, the exits owed, boundary promotions, then NVMA → params → AGON →
    Governor → the position policy. Venue work is queued to the executor, never awaited here.
  * Loop 2 classifies each instrument at most once per `regime.cycle_seconds` (C-REG-1); loop 1 is
    promotion only (C2: a crossed boundary, flat and idle; sets evolved offline, GAP-P12D-129).
  * Risk evaluates every `eval_cadence_s`, on every fill (GAP-0099) and venue fill, and writes the
    heartbeat; that timer also calls no tick for `fast_loop_stall_s` in an open market a stall (TAI-13).
  * At a restart a practice book is venue truth, the fills SYNCING recovered already in it (TAI-05);
    a paper book adopts nothing from the account and logs what it leaves on its venue stops.
  * A core task that ends or raises while the feed runs is a stalled loop (§10), and a deliberate
    stop (`request_stop`: SIGINT/SIGTERM, GAP-P12D-135) takes the same path: flatten everything, halt,
    drain the closes, end. A position still held after the drain is logged critical (the watchdog).
  * Reaching the venue's close reserve, in practice, flattens and halts everything once (ACIS-13
    v1.2 §6.5, owner ruling D2): the equity breaker would be blind there, so nothing stays open.
  * The fast loop's clock is the tick's own timestamp; everything else reads `now_fn`. The target
    universe (R6-3) gets no legacy signal or exit here: only target_loop.py trades it.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from core.data.normaliser import MarketState
from core.execution.venue import BrokerAccount
from core.risk.store import restore_on_boot
from core.runtime.feed_check import FeedWatch
from core.runtime.executor import WorkItem
from core.runtime.policy import exits_due, route, route_group
from core.runtime.portfolio import build_portfolio

DRAIN_TIMEOUT_S = 30.0          # how long a stopping runtime waits for its closes to leave


class Runtime:
    def __init__(self, parts) -> None:
        self.p = parts                           # core/runtime/wiring.py `Parts`
        self.marks: dict[str, float] = {}
        self.seq = 0
        self.snapshot = None
        self.account: BrokerAccount | None = None
        self.account_at: datetime | None = None
        self.booted = False
        self._classified_at: dict[str, datetime] = {}
        self._clock_verified: set[str] = set()
        self._clock_failed: set[str] = set()
        self._in_reserve = False
        self.feed = FeedWatch(max_age_s=2 * parts.regime_cycle_s,                 # the target path's data
                              spread_mult=parts.cfg.system.regime.spread_veto_mult,   # check (master v2.33,
                              tick_size={i: spec.tick_size                            # v2.35's floor)
                                         for i, spec in parts.cfg.instruments.instruments.items()})
        self._stop = asyncio.Event()
        self.stop_reason: str | None = None

    def request_stop(self, reason: str) -> None:
        """A deliberate stop: `run()` flattens, halts and returns "stopped" (GAP-P12D-135)."""
        if self.stop_reason is None:
            self.stop_reason = reason
            self.p.log.event("ENGINE_STOP_REQUESTED", reason=reason)
        self._stop.set()

    # -- Loop 3: the fast loop ---------------------------------------------------------- #

    def on_state(self, st: MarketState) -> None:
        t0 = time.perf_counter()
        p, now = self.p, st.timestamp
        self.seq += 1
        self.marks[st.instrument] = st.mid
        self.feed.observe(st)
        p.paper.on_mark(st.instrument, st.bid, st.ask, now)
        for boundary in p.boundaries.crossed(now):
            p.params.on_boundary(boundary)       # C2: promotes only while flat
        held = {pos.instrument: pos for pos in p.risk.positions()}
        busy = p.executor.busy
        legacy = {i: pos for i, pos in held.items() if i not in p.target_universe}    # R6-3
        for close in exits_due(legacy, self.marks, busy, now, p.max_hold_s):
            p.executor.submit(WorkItem((close,), valid_for_seconds=0))
        p.nvma.observe(st)
        ctx = self._regime(st)
        bar = p.agon.observe(st)
        if bar is not None:
            p.governor.observe_bar(st.instrument, bar)          # GAP-0059: one aggregator
        active = p.params.get_active(ctx.regime)
        clock_ok = self._clock_ok(st)            # A8 on every tick: the target path reads it too
        signals = () if st.instrument in p.target_universe else p.agon.generate(   # R6-3: one path
            st, ctx, active.params if active is not None else None, now)
        if signals and not clock_ok:
            signals = ()                         # ACIS-13 A8: no entry before the clock is proven
        if not signals and not held:
            return self._budget(t0, st)
        portfolio = self.portfolio()
        for close in p.governor.weekend_flatten(portfolio, now) if held else ():
            if work := route(close, held, busy, now):
                p.executor.submit(WorkItem(work, valid_for_seconds=0))
        groups: dict[str, list] = {}
        for s in signals:
            if s.group_id is not None:
                groups.setdefault(s.group_id, []).append(s)
            elif work := route(p.governor.allocate(s, portfolio, ctx, now), held, busy, now):
                p.executor.submit(WorkItem(work, s.valid_for_seconds, strategy=s.strategy_type))
        for legs in groups.values():
            sized = p.governor.allocate_group(tuple(legs), portfolio, ctx, now)
            if work := route_group(sized, held, busy):
                p.executor.submit(WorkItem(work, legs[0].valid_for_seconds, group=True,
                                           strategy=legs[0].strategy_type))
        self._budget(t0, st)

    def clock_verified(self, instrument: str) -> bool:
        return instrument in self._clock_verified

    def _clock_ok(self, st: MarketState) -> bool:
        """ACIS-13 A8, finished here: the first LIVE tick per instrument (market open, not a
        stale or closing print) must arrive within `clock_skew_tolerance_ms` of the host clock.
        Until one does, that instrument takes no entry; its exits are never blocked."""
        if st.instrument in self._clock_verified:
            return True
        if st.session == "closed" or st.is_stale:
            return False                          # no live tick yet: nothing to judge
        lag_ms = (st.ingest_ts - st.timestamp).total_seconds() * 1000.0
        if st.raw.get("_acis_meta", {}).get("clock_skew"):
            if st.instrument not in self._clock_failed:
                self._clock_failed.add(st.instrument)
                self.p.log.event("CLOCK_CHECK_FAILED", instrument=st.instrument, lag_ms=lag_ms)
            return False
        self._clock_verified.add(st.instrument)
        self.p.log.event("CLOCK_VERIFIED", instrument=st.instrument, lag_ms=lag_ms)
        return True

    def _regime(self, st: MarketState):
        last = self._classified_at.get(st.instrument)
        if last is None or (st.timestamp - last).total_seconds() >= self.p.regime_cycle_s:
            self._classified_at[st.instrument] = st.timestamp
            return self.p.nvma.classify(st)
        return self.p.nvma.regime_store[st.instrument]

    def _budget(self, t0: float, st: MarketState) -> None:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if elapsed_ms > self.p.decision_budget_ms:          # §10 decisiveness: measured
            self.p.log.event("FAST_LOOP_BUDGET_EXCEEDED", instrument=st.instrument,
                             elapsed_ms=round(elapsed_ms, 3), budget_ms=self.p.decision_budget_ms)

    def portfolio(self, closing=()):
        """The Governor's snapshot. Paper reads its always-current ledger; practice reads the
        budgeted poll, whose age can make the snapshot stale (then entries are zeroed). `closing`:
        closes about to be sent with the entry being judged (a flip's own leg), read as filled."""
        p = self.p
        if p.mode.mode == "practice" and p.venue is not None:
            account, at = p.venue.account, p.venue.account_at
            age = (p.now_fn() - at).total_seconds() if at is not None else float("inf")
            nav = account.equity if account is not None else p.paper_nav
        else:
            nav, age = p.paper.account().equity, 0.0
        return build_portfolio(
            positions=p.risk.positions(), strategy_of=p.executor.strategy_of, marks=self.marks,
            nav=nav, daily_drawdown_pct=self.snapshot.daily_drawdown_pct if self.snapshot else 0.0,
            clusters=p.clusters, as_of=p.now_fn(), account_age_s=age,
            max_age_s=p.account_max_age_s(), logger=p.log,
            inflight=(*p.executor.inflight.values(), *closing))

    # -- Risk: evaluate, heartbeat ------------------------------------------------------- #

    async def evaluate(self) -> None:
        p = self.p
        now = p.now_fn()
        self._reserve_edge()                     # first: inside the reserve the poll is refused
        if p.mode.mode == "practice" and p.venue is not None:
            account, at = p.venue.account, p.venue.account_at     # the budgeted poll
        else:
            account, at = await p.paper.account_snapshot(), now
        if account is None:
            p.log.event("RISK_NO_ACCOUNT_YET")
            return
        self.account, self.account_at = account, at
        self.snapshot = p.risk.evaluate(account, now, marks=dict(self.marks))
        p.edge.flush()                           # a halt the ledger could not write yet

    def _reserve_edge(self) -> None:
        """On the rising edge into the close reserve: flatten and halt, once (D2)."""
        p = self.p
        entered = p.mode.mode == "practice" and p.venue_is_book and p.venue.in_reserve()
        if entered and not self._in_reserve:
            p.log.event("VENUE_BUDGET_RESERVE_REACHED", severity="critical", budget=p.venue.session.budget())
            p.edge.flatten("all", "budget_reserve")
            p.edge.apply_halt("all", "budget_reserve")
        self._in_reserve = entered

    async def risk_loop(self) -> None:
        p = self.p
        seen, since = self.seq, p.now_fn()
        while True:
            await self.evaluate()
            now = p.now_fn()
            p.risk.write_heartbeat(now, p.mode.mode, self.seq)
            if self.seq != seen or not p.market_open(now):
                seen, since = self.seq, now
            elif (now - since).total_seconds() >= p.stall_s:
                p.log.event("FAST_LOOP_SILENT", seconds=(now - since).total_seconds(), seq=self.seq)
                raise RuntimeError("Loop 3 made no progress while a market was open")   # a stall
            await asyncio.sleep(p.eval_cadence_s)

    async def venue_fills(self, orchestrator, name: str, *, ingest: bool = True) -> None:
        async for fill in orchestrator.venue_fills(name):       # a stop firing, a stop-out
            if not ingest:                       # the account is not this process's book
                self.p.log.event("VENUE_FILL_OUTSIDE_THE_BOOK", fill_id=fill.fill_id,
                                 instrument=fill.instrument, severity="critical")
                continue
            self.p.risk.ingest(fill)
            await self.evaluate()

    # -- the process --------------------------------------------------------------------- #

    async def boot(self, venue_positions=()) -> None:
        """Before the first tick: every persisted halt and anchor back (ACIS-07 §7), venue truth
        adopted (a drift halts for a human, C-RSK-5), the account read, pair groups rebuilt."""
        p, now = self.p, self.p.now_fn()
        restore_on_boot(p.risk_store, p.risk, now)
        if p.venue is not None:
            if p.venue_is_book:
                p.risk.reconcile_on_restart(tuple(venue_positions), now)
            elif venue_positions:                      # an ended practice session's, on their stops
                p.log.event("VENUE_POSITIONS_OUTSIDE_THE_BOOK", severity="critical", book=p.book,
                            instruments=sorted(pos.instrument for pos in venue_positions))
            p.venue.discard_recovered()                # already in venue truth (TAI-05)
            await p.venue.poll_once()
        await self.evaluate()
        p.log.event("BOOT_GROUPS_REBUILT", rebuilt=p.governor.rebuild_groups(self.portfolio()))
        self.booted = True

    async def run(self) -> str:
        """Run until the feed ends (a test, a replay), a core task stalls, or a stop is requested;
        return why."""
        p = self.p
        if not self.booted:                       # a raise, alive under -O (GAP-0079)
            raise RuntimeError("boot() must run before the first tick")
        fast = asyncio.create_task(p.pipeline.run(), name="fast_loop")
        others = [asyncio.create_task(c, name=n) for n, c in p.tasks(self)]
        stop = asyncio.create_task(self._stop.wait(), name="stop")
        done, _ = await asyncio.wait([fast, *others, stop], return_when=asyncio.FIRST_COMPLETED)
        if stop in done:
            p.edge.flatten("all", "operator_stop")
            p.edge.apply_halt("all", "operator_stop")
            outcome = "stopped"
        elif fast in done and fast.exception() is None:
            outcome = "feed_ended"
        else:
            dead = next(t for t in done)
            error = dead.exception() if not dead.cancelled() else None
            p.log.event("LOOP_STALLED", task=dead.get_name(), error=repr(error))
            p.edge.flatten("all", "loop_stalled")
            p.edge.apply_halt("all", "loop_stalled")
            outcome = f"stalled:{dead.get_name()}"
        try:
            await asyncio.wait_for(p.executor.queue.join(), DRAIN_TIMEOUT_S)
        except asyncio.TimeoutError:
            p.log.event("DRAIN_TIMEOUT", pending=p.executor.queue.qsize())
        await self.evaluate()
        if outcome == "stopped" and (left := p.risk.positions()):
            p.log.event("STOP_LEFT_POSITIONS", severity="critical",
                        instruments=sorted(pos.instrument for pos in left))
        p.risk.write_heartbeat(p.now_fn(), p.mode.mode, self.seq)
        await p.writer.stop()                     # the market-state record drains, then ends
        for task in [fast, *others, stop]:
            if task.get_name() != "writer":
                task.cancel()
        await asyncio.gather(fast, *others, stop, return_exceptions=True)
        return outcome
