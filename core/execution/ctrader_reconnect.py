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
    HALT (the resting stops and the watchdog protect the book). Attempts continue at the cap, and
    the persisted request budget still bounds them.
  * DETACHED is terminal: the task ends, which the runtime treats as a stalled loop, so the book
    is flattened where it can be and halted, and a human re-grants and re-attaches.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable

from core.data.ctrader.link import AuthRefused, LinkState
from core.data.ctrader.wire import VenueError

DOWN = (LinkState.DISCONNECTED, LinkState.DETACHED)


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
        attempt, until = 0, None
        while True:
            growth = self._b.factor ** min(attempt, 64)     # capped: a long outage never overflows
            delay = self._rng.uniform(0.0, min(self._b.cap_s, self._b.base_s * growth))
            if until is not None:
                delay += max(0.0, (until - self._now()).total_seconds())
                self._log.event("VENUE_MAINTENANCE", until=until.isoformat())
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
            except VenueError as err:
                if err.maintenance_end_ms:
                    until = datetime.fromtimestamp(err.maintenance_end_ms / 1000, tz=timezone.utc)
                self._log.event("VENUE_RECONNECT_FAILED", attempt=attempt, error=err.code)
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                self._log.event("VENUE_RECONNECT_FAILED", attempt=attempt, error=type(exc).__name__)
            if self._s.state is LinkState.DETACHED:
                return False
            attempt += 1
            if attempt == self._b.max_consecutive:
                self._log.event("VENUE_UNREACHABLE", attempts=attempt)
