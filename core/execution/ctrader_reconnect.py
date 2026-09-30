"""Reconnect with backoff (ACIS-13 §6.6, §8.1; GAP-0020): a lost link comes back through SYNCING.

Invariants:
  * The delay is full-jitter exponential, `uniform(0, min(cap_s, base_s × factor**attempt))`, with
    the RNG injected (SystemRandom in production, seeded in tests). A venue maintenance window is
    slept through to its stated end, plus the jitter: never polled.
  * Every successful reconnect passes SYNCING before any dispatch: the session re-authorises, the
    face resolves its in-flight orders and ingests the deals missed while down (they reach Risk as
    venue fills), reconciles, and marks READY; only then is the feed re-subscribed with a logged
    FEED_RECONNECT. The gap is logged, never interpolated.
  * `max_consecutive` failures in one outage raise VENUE_UNREACHABLE once: a health event, not a
    HALT (the resting stops and the watchdog protect the book). Attempts continue at the cap. The
    persisted budget is hard for authorisation too, so a spent budget refuses the attempt locally,
    and the reconnector then waits `BUDGET_WAIT_S` for the rolling window instead of ending
    (GAP-P12D-132 TAI-02); an application or grant the venue refuses detaches (TAE-09).
  * DETACHED is terminal: the task ends, which the runtime treats as a stalled loop, so the book
    is flattened where it can be and halted, and a human re-grants and re-attaches.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable

from core.data.ctrader.link import AuthRefused, LinkState
from core.data.ctrader.meter import BudgetRefused
from core.data.ctrader.wire import VenueError

DOWN = (LinkState.DISCONNECTED, LinkState.DETACHED)
BUDGET_WAIT_S = 900.0          # a spent budget frees as the rolling 24 h window moves


def backoff_delay(backoff, attempt: int, rng) -> float:
    """Full jitter (Brooker 2015): uniform(0, min(cap, base × factor**attempt)), exponent capped."""
    return rng.uniform(0.0, min(backoff.cap_s, backoff.base_s * backoff.factor ** min(attempt, 64)))


def hold_until(exc: BaseException, now: datetime) -> tuple[datetime | None, str | None]:
    """A failure that names its own end: a maintenance window, or a spent budget's window."""
    if isinstance(exc, BudgetRefused):
        return now + timedelta(seconds=BUDGET_WAIT_S), "VENUE_BUDGET_WAIT"
    if isinstance(exc, VenueError) and exc.maintenance_end_ms:
        return datetime.fromtimestamp(exc.maintenance_end_ms / 1000, tz=timezone.utc), "VENUE_MAINTENANCE"
    return None, None


class Reconnector:
    def __init__(self, *, session, face, feed, backoff, rng, logger,
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 sleep=asyncio.sleep, poll_s: float = 1.0) -> None:
        self._s, self._face, self._feed, self._b = session, face, feed, backoff
        self._rng, self._log, self._now, self._sleep, self._poll = rng, logger, now_fn, sleep, poll_s

    async def run(self) -> None:
        while True:
            while self._s.state not in DOWN:
                await asyncio.sleep(self._poll)          # watching, not backing off
            lost_at = self._now()
            if self._s.state is LinkState.DETACHED or not await self._reconnect():
                self._log.event("VENUE_RECONNECT_ABANDONED", state=self._s.state.value)
                return
            self._log.event("VENUE_RECONNECTED", gap_s=(self._now() - lost_at).total_seconds())

    async def _reconnect(self) -> bool:
        attempt, until, why = 0, None, None
        while True:
            delay = backoff_delay(self._b, attempt, self._rng)
            if until is not None:
                delay += max(0.0, (until - self._now()).total_seconds())
                self._log.event(why, until=until.isoformat())    # VENUE_MAINTENANCE or _BUDGET_WAIT
            self._log.event("VENUE_BACKOFF", attempt=attempt, delay_s=round(delay, 3))
            await self._sleep(delay)
            until = None
            await self._s.stop()                        # the dead link's tasks end before a new one
            try:
                await self._s.start()
                await self._face.synchronise()
                await self._feed.subscribe(reconnect=True)
                return True
            except AuthRefused as refused:              # the session has detached itself
                self._log.event("VENUE_RECONNECT_REFUSED", verdict=refused.verdict)
                return False
            except (BudgetRefused, VenueError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
                until, why = hold_until(exc, self._now())
                self._log.event("VENUE_RECONNECT_FAILED", attempt=attempt,
                                error=getattr(exc, "code", None) or type(exc).__name__)
            if self._s.state is LinkState.DETACHED:
                return False
            attempt += 1
            if attempt == self._b.max_consecutive:
                self._log.event("VENUE_UNREACHABLE", attempts=attempt)
