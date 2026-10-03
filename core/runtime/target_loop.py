"""The target-position path's slow loop (ACIS-04 v1.6 §4b, ACIS-05 v1.7 §6.4, ACIS-03 v2.2; R1.6).

Mental model:
  * DECIDE once per New York weekday, `settle_s` after 17:00, once some instrument's clock is
    proven (ACIS-13 A8; until then it retries): append each instrument's new H1 bars (one metered
    query each), skip a day nothing traded (a holiday), else decide every instrument
    (target_decision.py), yielding to the event loop between them. A failed fetch or a history
    with a hole gives that instrument no target. A target that differs from the held position waits
    for its SLOT; a new decision supersedes an older one.
  * EXECUTE at the slot, at most `slot_grace_s` late, through the target gate. Nothing is sent (the
    reason is logged) on a missed slot or a closed market (never caught up), a busy instrument, no
    mark, or a position changed since the decision: a disaster stop or a flatten (R6-2, no same-day
    re-entry; the next decision acts). An entry whose instrument's clock is unproven is dropped.
  * BOOT re-derives the latest decision from the cache: deterministic, so a restart yields the same
    target; a slot already passed is dropped, and the day's held position is persisted, so a restart
    after a stop-out does not re-enter (R16I-03). Only this loop opens positions on the universe.
  * FLATTEN-THEN-PROMOTE (ACIS-03 v2.2) is checked at each decision (target_promotion.py). The
    family must be registered in provenance AND allowed to enter (master §2's registered, validated
    rule set), asked at the decision and again at the slot, where only its opens are dropped (PR16I-10).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Mapping

from core.data.ctrader.meter import BudgetRefused
from core.data.ctrader.wire import VenueError
from core.data.errors import DataQualityError
from core.data.fx_clock import rollover_utc
from core.governor.target_gate import close_leg
from core.runtime.executor import WorkItem
from core.runtime.history_store import HistoryStore
from core.runtime.target_promotion import promotion_settled
from core.runtime.target_decision import BookSizing, Decision, Lots, decide
from core.signals.daily import decision_days, series, slot_after
from core.signals.signal_types import StrategyType

FETCH_ERRORS = (ConnectionError, OSError, asyncio.TimeoutError, VenueError, BudgetRefused, DataQualityError)
MAX_SLEEP_S = 300.0
HOLE = timedelta(days=5)          # a gap no FX weekend or holiday explains: a hole in the history


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
    portfolio: Callable[..., object]          # portfolio(closing=()): a flip's own close read as filled
    feed_refusal: Callable[[str, datetime], str | None]   # the entry data check (feed_check.py)
    submit: Callable[[WorkItem], None]
    flatten: Callable[[str, str], None]
    clock_ok: Callable[[str], bool]          # ACIS-13 A8: a live tick proved the host clock


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
            if not await self.decide(day, now, boot=boot):
                self.decided = None                       # retried at the next wake
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

    async def decide(self, day: date, now: datetime, *, boot: bool = False) -> bool:
        """Decide `day`; False when it must wait for a proven clock (ACIS-13 A8, R16I-02)."""
        if not any(self.engine.clock_ok(i) for i in self.members):
            self._log.event("TARGETS_CLOCK_UNVERIFIED", day=day.isoformat())
            return False
        at = rollover_utc(day)
        failed = {i for i in self.members if not await self._refresh(i, at)}
        if not promotion_settled(self.store, self.family, self.members, self.engine, self.pending, self._log):
            return True
        if not self._registered(self.family):
            self._log.event("TARGETS_FAMILY_UNREGISTERED", family=self.family, severity="critical")   # or not allowed
            return True
        try:
            rates = self._rates()
        except (OSError, ValueError, KeyError) as exc:          # a malformed rate file
            self._log.event("TARGETS_NO_RATES", error=repr(exc))
            return True
        hours = {}
        for i in self.members:                             # R16I-06: never starve the event loop
            hours[i] = [b for b in self.store.bars(i) if b.ts_open < at]
            await asyncio.sleep(0)
        holes = {i for i, h in hours.items() if any(b.ts_open - a.ts_open > HOLE for a, b in zip(h, h[1:]))}
        if holes:
            self._log.event("HISTORY_HOLE", instruments=sorted(holes), severity="critical")
        firsts = [h[0].ts_open.date() for h in hours.values() if h]
        days = decision_days(hours, min(firsts), day) if firsts else []
        if day not in days:
            self._log.event("TARGETS_NO_DECISION_DAY", day=day.isoformat())
            return True
        all_series = {i: series(i, h, days) for i, h in hours.items()}
        for instrument, m in self.members.items():
            why = "fetch_failed" if instrument in failed else "history_hole" if instrument in holes else None
            self._decide_one(instrument, m, day, at, now, all_series, rates, boot, why)
            await asyncio.sleep(0)
        return True

    def _decide_one(self, instrument, m: Member, day, at, now, all_series, rates, boot, why) -> None:
        lots = self._lots_of(instrument)
        self.pending.pop(instrument, None)                 # a new decision supersedes the old
        held, key = signed(self.engine.held_of(instrument)), f"decision:{instrument}"
        prior = json.loads(self.store.get(key) or "{}")
        if prior.get("day") == day.isoformat() and Decimal(prior["held"]) != held:
            why = why or "position_changed_since_decision"     # a restart after a stop-out (R16I-03)
        if lots is None or why is not None:
            self._log.event("TARGET_DECIDED", instrument=instrument, day=day.isoformat(), boot=boot,
                            reason=f"no_target:{why or 'no_lots'}", held=str(held), target=None)
            return
        d = decide(instrument, m.asset_class, m.quote, all_series[instrument], day, held,
                   rates=rates, series=all_series, sizing=self.sizing, lots=lots, atr_period=self._atr_period)
        if prior.get("day") != day.isoformat():
            self.store.put(key, json.dumps({"day": day.isoformat(), "held": str(held)}))
        f = d.forecast
        slot = slot_after(at, m.slot)
        self._log.event("TARGET_DECIDED", instrument=instrument, day=day.isoformat(), reason=d.reason,
                        held=str(d.held), target=None if d.target is None else str(d.target),
                        forecast=None if f is None else round(f.value, 6),
                        pct_vol=None if f is None else f.pct_vol, inputs_hash=None if f is None else f.inputs_hash,
                        atr=d.atr, slot=slot.isoformat(), boot=boot,
                        shadow=d.shadow, q=d.q, close=None if f is None else f.price_basis)   # the shadow book
        if d.target is not None and d.target != d.held:
            if boot and now > slot + self._grace:
                self._log.event("TARGET_SLOT_PASSED", instrument=instrument, slot=slot.isoformat())
                return
            self.pending[instrument] = Pending(d, slot)

    async def _refresh(self, instrument: str, at: datetime) -> bool:
        """Append the new bars; False on a failed fetch (that instrument gets no target, R16I-04)."""
        start = self.store.last_end(instrument) or at - self._history
        if start >= at:
            return True
        try:
            self.store.add(instrument, await self._fetch(instrument, start, at))
            return True
        except FETCH_ERRORS as exc:
            self._log.event("TRENDBARS_FAILED", instrument=instrument, error=repr(exc))
            return False

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
        target = d.target if lots.cap is None or abs(d.target) <= lots.cap else lots.cap.copy_sign(d.target)
        flip = held is not None and target and (target > 0) != (held.direction > 0)
        closing = (close_leg(held, held.size_units, e.marks()[instrument], now, "target_flip"),) if flip else ()
        result = self._gate(instrument=instrument, held=held, target=target, mark=e.marks()[instrument],
                            atr=d.atr, step=lots.step, minimum=lots.minimum, portfolio=e.portfolio(closing),
                            entry_refusal=e.feed_refusal(instrument, now), marks=e.marks(), now=now, family=self.family,
                            alpha_throttles=lots.cap is None,     # the one-lot cap = paper/practice: report only
                            snapshot={"forecast": f.value, "pct_vol": f.pct_vol, "inputs_hash": f.inputs_hash,
                                      "decision_day": d.day.isoformat(), "target": str(target)})
        orders, reason = result.orders, result.reason
        if any(o.action == "open" for o in orders) and not e.clock_ok(instrument):
            orders, reason = tuple(o for o in orders if o.action == "close"), "clock_unverified"   # A8
        if any(o.action == "open" for o in orders) and not self._registered(self.family):        # PR16I-10
            orders, reason = tuple(o for o in orders if o.action == "close"), "family_not_allowed"
        self._log.event("TARGET_EXECUTED", instrument=instrument, reason=reason,
                        orders=[(o.action, o.direction, str(o.size_units)) for o in orders])
        if orders:
            e.submit(WorkItem(orders, valid_for_seconds=0, strategy=StrategyType.TREND))


def signed(held) -> Decimal:
    return Decimal(held.direction) * held.size_units if held is not None else Decimal("0")
