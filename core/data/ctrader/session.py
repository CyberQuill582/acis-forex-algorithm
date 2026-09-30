"""CTraderSession (ACIS-13 §3.2, §6.2, §6.6, §6.7, §7.1 A2–A3, §8.1): one connection to the venue —
transport, authentication and request metering ONLY (GAP-0013, C-VEN-6).

Invariants:
  * No market, account or position state lives here, and no public member names any (the §14.1
    attribute scan). Inbound frames are routed by payload type without being interpreted:
    spots to `spots`, execution and trader events to `events`, the three auth events to `events`
    AND to this session's own state machine.
  * Every request is admitted by the persisted budget BEFORE it is sent (C-VEN-4) and paced to the
    local rate limit (half the documented 50/s, F-05). Heartbeats are neither.
  * A request never waits past its timeout, and a dead link fails every waiter at once, so no caller
    blind-resends: what reached the venue is found by search, never assumed (C-VEN-1).
  * The bound account is config, never discovered (C-VEN-5): it must appear in the grant, with the
    `trading` scope, and its `isLive` must equal `environment == live` (A2), else attach is refused.
  * A refreshed token pair is persisted BEFORE it is used (C-VEN-8); a dead refresh token detaches.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from core.data.ctrader import schema as s
from core.data.ctrader.link import AuthRefused, Credentials, Grant, LinkState
from core.data.ctrader.meter import RequestMeter
from core.data.ctrader.tokens import TokenPair, TokenStore, pair_from_refresh
from core.data.ctrader.transport import Transport, open_websocket
from core.data.ctrader.wire import HEARTBEAT, Correlator, Frame, LinkClock, VenueError, decode, encode
from core.data.errors import DataQualityError

UNSCOPED = frozenset({s.PT.APPLICATION_AUTH_REQ, s.PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                      s.PT.REFRESH_TOKEN_REQ})
RATE_LIMITED = frozenset({"REQUEST_FREQUENCY_EXCEEDED", "BLOCKED_PAYLOAD_TYPE"})


class CTraderSession:
    def __init__(self, *, environment: str, binding: int, credentials: Credentials,
                 tokens: TokenStore, meter: RequestMeter, logger,
                 connect: Callable[[str], Awaitable[Transport]] = open_websocket,
                 now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 mono_fn: Callable[[], float] = time.monotonic,
                 heartbeat_s: float = 10.0, liveness_timeout_s: float = 30.0,
                 request_timeout_s: float = 10.0, rate_per_s: float = 25.0) -> None:
        if environment not in s.HOSTS:
            raise DataQualityError("environment", environment, f"one of {sorted(s.HOSTS)}")
        self.environment = environment
        self._bound = int(binding)
        self._creds = credentials
        self._tokens = tokens
        self._meter = meter
        self._log = logger
        self._connect = connect
        self._now = now_fn
        self._mono = mono_fn
        self._hb, self._live_s = heartbeat_s, liveness_timeout_s
        self._timeout = request_timeout_s
        self._gap = 1.0 / rate_per_s
        self._last_send = float("-inf")
        self._send_lock = asyncio.Lock()
        self._corr = Correlator("acis")
        self._link: LinkClock | None = None
        self._t: Transport | None = None
        self._tasks: list[asyncio.Task] = []
        self._pair: TokenPair | None = None
        self._refreshed = float("-inf")
        self.state = LinkState.DISCONNECTED
        self.spots: asyncio.Queue[Frame] = asyncio.Queue()
        self.events: asyncio.Queue[Frame] = asyncio.Queue()

    # -- lifecycle ------------------------------------------------------------------------- #

    async def start(self) -> Grant:
        """Connect and authorise (A3); leaves the session SYNCING for the face to finish."""
        self._set(LinkState.CONNECTING)
        self._t = await self._connect(self.environment)
        self._link = LinkClock(self._mono(), heartbeat_s=self._hb, liveness_timeout_s=self._live_s)
        self._tasks = [asyncio.create_task(self._read()), asyncio.create_task(self._beat())]
        self._log.event("VENUE_CONNECT", environment=self.environment)
        self._set(LinkState.APP_AUTH)
        await self.request(s.PT.APPLICATION_AUTH_REQ, {"clientId": self._creds.client_id,
                                                       "clientSecret": self._creds.client_secret},
                           req_class="auth")
        self._log.event("VENUE_APP_AUTH")
        self._pair = self._tokens.read()
        if self._pair.needs_refresh(self._now()):
            self._pair = await self._refresh(self._pair)
        grant = await self._check_grant(self._pair)
        await self._authorise_binding()
        self._set(LinkState.SYNCING)
        return grant

    def mark_ready(self) -> None:
        """The face finished SYNCING (deals ingested, reconciled, re-subscribed): dispatch may resume."""
        if self.state is LinkState.SYNCING:
            self._set(LinkState.READY)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        # wait for them: a cancelled reader's `finally` must never mark a LATER link lost (GAP-0020)
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._t is not None:
            await self._t.close()
        self._lost("stopped")

    # -- requests -------------------------------------------------------------------------- #

    async def request(self, pt: int, payload: dict, *, req_class: str,
                      timeout_s: float | None = None) -> Frame:
        if self.state in (LinkState.DISCONNECTED, LinkState.DETACHED) or self._t is None:
            raise ConnectionError(f"venue link is {self.state.value}")
        now = self._now()
        self._meter.admit(req_class, now)               # BudgetRefused: nothing is sent
        body = dict(payload)
        if pt not in UNSCOPED:
            body["ctidTraderAccountId"] = self._bound
        msg_id, future = self._corr.open()
        self._meter.record(int(pt), req_class, msg_id, now)
        await self._send(encode(pt, body, msg_id))
        try:
            return await asyncio.wait_for(future, timeout_s or self._timeout)
        except asyncio.TimeoutError:
            self._corr.forget(msg_id)
            raise
        except VenueError as err:
            if err.code in RATE_LIMITED:
                self._log.event("VENUE_RATE_LIMITED", payload_type=int(pt),
                                retry_after_s=err.retry_after_s)
            raise

    def budget(self) -> dict:
        return self._meter.state(self._now())

    async def refresh_if_due(self) -> bool:
        """Refresh proactively inside the last week, at a quiet moment the caller chose (§6.7)."""
        if self._pair is None or not self._pair.needs_refresh(self._now()):
            return False
        await self._recover(refresh=True)
        return self.state is not LinkState.DETACHED

    # -- internals ------------------------------------------------------------------------- #

    async def _refresh(self, pair: TokenPair) -> TokenPair:
        try:
            res = await self.request(s.PT.REFRESH_TOKEN_REQ, {"refreshToken": pair.refresh_token},
                                     req_class="auth")
        except VenueError as err:
            self._detach(f"refresh refused: {err.code}")
            raise AuthRefused("VENUE_TOKEN_DEAD", err.code) from err
        new = pair_from_refresh(dict(res.payload), self._now(), pair)
        self._tokens.write(new)                          # persisted BEFORE use (C-VEN-8)
        self._refreshed = self._mono()
        self._log.event("VENUE_TOKEN_REFRESHED", expires_at=new.expires_at.isoformat())
        return new

    async def _check_grant(self, pair: TokenPair) -> Grant:
        res = await self.request(s.PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ,
                                 {"accessToken": pair.access_token}, req_class="auth")
        scope = s.enum_value(s.PermissionScope, s.field(res.payload, "permissionScope"))
        if scope is not s.PermissionScope.SCOPE_TRADE:
            self._detach("the grant is view-only")
            raise AuthRefused("ATTACH_SCOPE", "the grant lacks the trading scope")
        bound = [a for a in res.payload.get("ctidTraderAccount", [])
                 if int(a["ctidTraderAccountId"]) == self._bound]
        if not bound:
            self._detach("the bound id is not in the grant")
            raise AuthRefused("ATTACH_NOT_GRANTED", "a human must re-grant this binding")
        grant = Grant(bool(s.field(bound[0], "isLive")), bound[0].get("traderLogin"),
                      bound[0].get("brokerTitleShort"))
        if grant.is_live != (self.environment == "live"):
            self._detach("environment mismatch")
            raise AuthRefused("ATTACH_ENV_MISMATCH",
                              f"environment {self.environment}, venue isLive={grant.is_live}")
        return grant

    async def _authorise_binding(self) -> None:
        self._set(LinkState.ACCOUNT_AUTH)
        try:
            await self.request(s.PT.ACCOUNT_AUTH_REQ, {"accessToken": self._pair.access_token},
                               req_class="auth")
        except VenueError as err:
            if err.code != "ALREADY_LOGGED_IN":          # success on this connection (F-34)
                raise
        self._log.event("VENUE_ACCOUNT_AUTH")

    async def _send(self, data: str) -> None:
        async with self._send_lock:                      # paced: never above the local rate
            wait = self._last_send + self._gap - self._mono()
            if wait > 0:
                await asyncio.sleep(wait)
            await self._t.send_str(data)
            self._last_send = self._mono()
            self._link.sent(self._last_send)

    async def _read(self) -> None:
        try:
            while (raw := await self._t.receive()) is not None:
                self._link.received(self._mono())
                try:
                    frame = decode(raw)
                except DataQualityError as exc:
                    self._log.event("VENUE_BAD_FRAME", reason=str(exc))
                    continue
                if self._corr.resolve(frame) or frame.payload_type == s.PT.HEARTBEAT_EVENT:
                    continue
                self._route(frame)
        finally:
            self._lost("link closed")

    def _route(self, frame: Frame) -> None:
        pt = frame.payload_type
        if pt in s.FEED_EVENTS:
            self.spots.put_nowait(frame)
        elif pt in s.EXECUTION_EVENTS or pt in s.AUTH_EVENTS:
            self.events.put_nowait(frame)
            if pt in s.AUTH_EVENTS:
                self._on_auth_event(frame)
        else:
            self._log.event("VENUE_UNROUTED", payload_type=pt)

    def _on_auth_event(self, frame: Frame) -> None:
        """Keyed on the payload type only; the venue's `reason` is logged as data (C-VEN-15)."""
        pt = frame.payload_type
        self._log.event("VENUE_AUTH_EVENT", payload_type=pt,
                        reason_code=str(frame.payload.get("reason", ""))[:64])
        if pt == s.PT.CLIENT_DISCONNECT_EVENT or self.state not in (LinkState.READY,
                                                                    LinkState.SYNCING):
            return                                   # the link closes; reconnect re-authorises
        if pt == s.PT.ACCOUNTS_TOKEN_INVALIDATED_EVENT and self._mono() - self._refreshed < 60:
            return                                   # our own refresh invalidated the old pair
        self._tasks.append(asyncio.create_task(self._recover(refresh=pt != s.PT.ACCOUNT_DISCONNECT_EVENT)))

    async def _recover(self, *, refresh: bool) -> None:
        prior = self.state
        self._set(LinkState.REAUTH)
        try:
            if refresh:
                self._pair = await self._refresh(self._pair)
            await self._authorise_binding()
        except (VenueError, AuthRefused) as err:
            self._detach(f"re-authorisation failed: {getattr(err, 'code', getattr(err, 'verdict', ''))}")
            return
        self._set(prior)

    async def _beat(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            now = self._mono()
            if self._link.dead(now):
                self._log.event("VENUE_DISCONNECT", reason_code="liveness timeout")
                await self._t.close()
                return
            if self._link.heartbeat_due(now):
                await self._send(HEARTBEAT)

    def _lost(self, why: str) -> None:
        self._corr.fail_all(ConnectionError(f"venue link lost: {why}"))
        if self.state is not LinkState.DETACHED:
            self._set(LinkState.DISCONNECTED)

    def _detach(self, why: str) -> None:
        self._log.event("VENUE_ACCOUNT_DETACHED", reason_code=why)
        self._set(LinkState.DETACHED)

    def _set(self, state: LinkState) -> None:
        if state is not self.state:
            self._log.event("VENUE_STATE", **{"from": self.state.value, "to": state.value})
            self.state = state
