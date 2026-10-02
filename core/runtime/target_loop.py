"""The target-position path's slow loop (ACIS-04 v1.6 §4b, ACIS-05 v1.7 §6.4, ACIS-03 v2.2; R1.6).

Mental model:
  * DECIDE once per New York weekday, `settle_s` after 17:00: append each instrument's new H1 bars
    from the venue (one metered query each; a failed fetch leaves that day without a close, so no
    target), skip a day nothing traded (a holiday), else decide every instrument
    (target_decision.py). A target that differs from the held position waits for its SLOT; a new
    decision supersedes an older one.
  * EXECUTE at the slot, at most `slot_grace_s` late, through the target gate. Nothing is sent (the
    reason is logged) on a missed slot or a closed market (never caught up), a busy instrument, no
    mark, or a position changed since the decision: a disaster stop or a flatten (R6-2, no same-day
    re-entry; the next decision acts).
  * BOOT re-derives the latest decision from the cache: deterministic, so a restart yields the same
    target; a slot already passed is dropped. Only this loop opens positions on the universe (R6-3).
  * FLATTEN-THEN-PROMOTE (ACIS-03 v2.2), checked at each decision (the 17:00 boundary): while the
    cached active family-version differs from the configured one, no target is made and the universe
    is flattened through the reduce-only close; the version is promoted only once all is flat and
    idle, else it waits for the next boundary. The family must be registered in provenance.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Mapping

from core.data.ctrader.meter import BudgetRefused
from core.data.ctrader.wire import VenueError
from core.data.errors import DataQualityError
from core.data.fx_clock import rollover_utc
from core.runtime.executor import WorkItem
from core.runtime.history_store import HistoryStore
from core.runtime.target_decision import BookSizing, Decision, Lots, decide
from core.signals.daily import decision_days, series, slot_after
from core.signals.signal_types import StrategyType

FETCH_ERRORS = (ConnectionError, OSError, asyncio.TimeoutError, VenueError, BudgetRefused, DataQualityError)
MAX_SLEEP_S = 300.0


@dataclass(frozen=True)
class Member:
    instrument: str
    asset_class: str
    quote: str
    slot: tuple[str, int]
    market_open: Callable[[datetime], bool]


@dataclass(frozen=True)
class Pending:
    decision: Decision
    slot: datetime


@dataclass(frozen=True)
class EngineView:
    """What the loop reads of the running engine, and its one way out (the executor)."""
    held_of: Callable[[str], object]
    busy: Callable[[], frozenset]
    marks: Callable[[], Mapping[str, float]]
    portfolio: Callable[[], object]
    regime_of: Callable[[str], object]
    submit: Callable[[WorkItem], None]
    flatten: Callable[[str, str], None]


class TargetLoop:
    def __init__(self, *, members: Mapping[str, Member], store: HistoryStore, fetch, rates, sizing: BookSizing,
                 lots_of: Callable[[str], Lots | None], gate, engine: EngineView, family: str,
                 registered: Callable[[str], bool], history_days: int, settle_s: float, slot_grace_s: float,
                 atr_period: int, now_fn: Callable[[], datetime], logger) -> None:
        self.members, self.store, self._fetch, self._rates = dict(members), store, fetch, rates
        self.sizing, self._lots_of, self._gate, self.engine = sizing, lots_of, gate, engine
        self.family, self._registered = family, registered
        self._history = timedelta(days=history_days)
        self._settle, self._grace = timedelta(seconds=settle_s), timedelta(seconds=slot_grace_s)
        self._atr_period, self._now, self._log = atr_period, now_fn, logger
        self.pending: dict[str, Pending] = {}
        self.decided: date | None = None

    # -- the loop ------------------------------------------------------------------------ #

    async def run(self) -> None:
        await self.tick(self._now(), boot=True)
        while True:
            now = self._now()
            await asyncio.sleep(max(0.0, min(MAX_SLEEP_S, (self._next_wake(now) - now).total_seconds())))
            await self.tick(self._now())

    async def tick(self, now: datetime, *, boot: bool = False) -> None:
        day = self._latest_day(now)
        if day is not None and day != self.decided:
            self.decided = day
            await self.decide(day, now, boot=boot)
        for instrument in sorted(i for i, p in self.pending.items() if p.slot <= now):
            self.execute(instrument, now)

    def _latest_day(self, now: datetime) -> date | None:
        d = (now - self._settle).date()
        for _ in range(7):
            if d.weekday() < 5 and rollover_utc(d) + self._settle <= now:
                return d
            d -= timedelta(days=1)
        return None

    def _next_wake(self, now: datetime) -> datetime:
        d = now.date()
        while d.weekday() >= 5 or rollover_utc(d) + self._settle <= now:
            d += timedelta(days=1)
        slots = [p.slot for p in self.pending.values()]
        return min([rollover_utc(d) + self._settle, *slots])

    # -- the decision -------------------------------------------------------------------- #

    async def decide(self, day: date, now: datetime, *, boot: bool = False) -> None:
        at = rollover_utc(day)
        for instrument in self.members:
            await self._refresh(instrument, at)
        if not self._promotion_settled(now):
            return
        if not self._registered(self.family):
            self._log.event("TARGETS_FAMILY_UNREGISTERED", family=self.family, severity="critical")
            return
        try:
            rates = self._rates()
        except (OSError, ValueError, KeyError) as exc:          # a missing or malformed rate file
            self._log.event("TARGETS_NO_RATES", error=repr(exc))
            return
        hours = {i: [b for b in self.store.bars(i) if b.ts_open < at] for i in self.members}
        firsts = [h[0].ts_open.date() for h in hours.values() if h]
        days = decision_days(hours, min(firsts), day) if firsts else []
        if day not in days:
            self._log.event("TARGETS_NO_DECISION_DAY", day=day.isoformat())
            return
        all_series = {i: series(i, h, days) for i, h in hours.items()}
        for instrument, m in self.members.items():
            self._decide_one(instrument, m, day, at, now, all_series, rates, boot)

    def _decide_one(self, instrument, m: Member, day, at, now, all_series, rates, boot) -> None:
        lots = self._lots_of(instrument)
        self.pending.pop(instrument, None)                 # a new decision supersedes the old
        if lots is None:
            self._log.event("TARGET_NO_LOTS", instrument=instrument)
            return
        d = decide(instrument, m.asset_class, m.quote, all_series[instrument], day, signed(self.engine.held_of(instrument)),
                   rates=rates, series=all_series, sizing=self.sizing, lots=lots, atr_period=self._atr_period)
        f = d.forecast
        slot = slot_after(at, m.slot)
        self._log.event("TARGET_DECIDED", instrument=instrument, day=day.isoformat(), reason=d.reason,
                        held=str(d.held), target=None if d.target is None else str(d.target),
                        forecast=None if f is None else round(f.value, 6),
                        pct_vol=None if f is None else f.pct_vol, inputs_hash=None if f is None else f.inputs_hash,
                        atr=d.atr, slot=slot.isoformat(), boot=boot)
        if d.target is not None and d.target != d.held:
            if boot and now > slot + self._grace:
                self._log.event("TARGET_SLOT_PASSED", instrument=instrument, slot=slot.isoformat())
                return
            self.pending[instrument] = Pending(d, slot)

    async def _refresh(self, instrument: str, at: datetime) -> None:
        start = self.store.last_end(instrument) or at - self._history
        if start >= at:
            return
        try:
            self.store.add(instrument, await self._fetch(instrument, start, at))
        except FETCH_ERRORS as exc:                          # that day gets no close: no target
            self._log.event("TRENDBARS_FAILED", instrument=instrument, error=repr(exc))

    # -- the slot ------------------------------------------------------------------------ #

    def execute(self, instrument: str, now: datetime) -> None:
        p = self.pending.pop(instrument)
        m, e, d = self.members[instrument], self.engine, p.decision
        held = e.held_of(instrument)
        why = ("slot_missed" if now > p.slot + self._grace else "market_closed" if not m.market_open(now)
               else "busy" if instrument in e.busy() else "position_changed" if signed(held) != d.held
               else "no_mark" if e.marks().get(instrument) is None else None)
        if why is not None:
            self._log.event("TARGET_SLOT_SKIPPED", instrument=instrument, reason=why, slot=p.slot.isoformat())
            return
        lots, f = self._lots_of(instrument), d.forecast
        result = self._gate(instrument=instrument, held=held, target=d.target, mark=e.marks()[instrument],
                            atr=d.atr, step=lots.step, minimum=lots.minimum, portfolio=e.portfolio(),
                            regime=e.regime_of(instrument), marks=e.marks(), now=now, family=self.family,
                            snapshot={"forecast": f.value, "pct_vol": f.pct_vol, "inputs_hash": f.inputs_hash,
                                      "decision_day": d.day.isoformat(), "target": str(d.target)})
        self._log.event("TARGET_EXECUTED", instrument=instrument, reason=result.reason,
                        orders=[(o.action, o.direction, str(o.size_units)) for o in result.orders])
        if result.orders:
            e.submit(WorkItem(result.orders, valid_for_seconds=0, strategy=StrategyType.TREND))

    # -- flatten-then-promote ------------------------------------------------------------ #

    def _promotion_settled(self, now: datetime) -> bool:
        active = self.store.get("active_family")
        held = [i for i in self.members if self.engine.held_of(i) is not None]
        if active == self.family:
            return True
        if active is None and not held:
            self.store.put("active_family", self.family)
            self._log.event("FAMILY_ACTIVATED", family=self.family)
            return True
        self.pending.clear()
        if held or self.engine.busy() & set(self.members):
            self._log.event("FAMILY_PROMOTION_FLATTENING", staged=self.family, active=active, held=held)
            for instrument in held:
                self.engine.flatten(instrument, "family_promotion")
            return False
        self.store.put("active_family", self.family)
        self._log.event("FAMILY_PROMOTED", family=self.family, previous=active)
        return True


def signed(held) -> Decimal:
    return Decimal(held.direction) * held.size_units if held is not None else Decimal("0")
