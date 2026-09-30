"""Authorisation for the cTrader session (ACIS-13 §7.1 A2–A3, §6.7, §12): a mixin of `CTraderSession`.

Invariants:
  * A transient venue state (§12: rate limits, maintenance, an unreachable server, a connection
    limit) re-raises, for the reconnector's backoff; it never detaches.
  * A stale token (CH_ACCESS_TOKEN_INVALID, OA_AUTH_TOKEN_EXPIRED) re-raises for ONE refresh (A3,
    §6.7); a refresh the venue refuses for any other reason detaches (VENUE_TOKEN_DEAD).
  * ALREADY_LOGGED_IN on this connection is success (F-34). Any other refusal DETACHES: the
    application or the grant needs a human, and retrying it would only spend the budget
    (GAP-P12D-132 TAE-09, TAI-02).
  * The bound account is config, never discovered (C-VEN-5): it must be in the grant, with the
    trading scope, and its isLive must equal `environment == live` (A2).
  * A refreshed token pair is persisted BEFORE it is used (C-VEN-8).
"""

from __future__ import annotations

from core.data.ctrader import schema as s
from core.data.ctrader.link import AuthRefused, Grant, LinkState  # noqa: F401
from core.data.ctrader.tokens import TokenPair, pair_from_refresh
from core.data.ctrader.wire import Frame, VenueError

RETRYABLE = frozenset({"REQUEST_FREQUENCY_EXCEEDED", "BLOCKED_PAYLOAD_TYPE",   # §12: backoff,
                       "SERVER_IS_UNDER_MAINTENANCE", "CH_SERVER_NOT_REACHABLE",  # never a
                       "CANT_ROUTE_REQUEST", "CONNECTIONS_LIMIT_EXCEEDED"})        # detach
TOKEN_STALE = frozenset({"CH_ACCESS_TOKEN_INVALID", "OA_AUTH_TOKEN_EXPIRED"})   # A3: refresh once


class AuthMixin:
    """The session supplies `request`, `_tokens`, `_now`, `_mono`, `_log`, `_bound`, `_pair`,
    `environment`, `_detach` and `_set`."""

    async def _refresh(self, pair: TokenPair) -> TokenPair:
        try:
            res = await self.request(s.PT.REFRESH_TOKEN_REQ, {"refreshToken": pair.refresh_token},
                                     req_class="auth")
        except VenueError as err:
            if err.code in RETRYABLE:
                raise
            self._detach(f"refresh refused: {err.code}")
            raise AuthRefused("VENUE_TOKEN_DEAD", err.code) from err
        new = pair_from_refresh(dict(res.payload), self._now(), pair)
        self._tokens.write(new)                          # persisted BEFORE use (C-VEN-8)
        self._refreshed = self._mono()
        self._log.event("VENUE_TOKEN_REFRESHED", expires_at=new.expires_at.isoformat())
        return new

    async def _check_grant(self, pair: TokenPair) -> Grant:
        res = await self._auth(s.PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": pair.access_token})
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
        await self._auth(s.PT.ACCOUNT_AUTH_REQ, {"accessToken": self._pair.access_token})
        self._log.event("VENUE_ACCOUNT_AUTH")

    async def _auth(self, pt: int, payload: dict) -> Frame | None:
        """One authorisation request under A3 and §12 (see the invariants)."""
        try:
            return await self.request(pt, payload, req_class="auth")
        except VenueError as err:
            if err.code in RETRYABLE or err.code in TOKEN_STALE:
                raise
            if err.code == "ALREADY_LOGGED_IN":           # success on this connection (F-34)
                return None
            self._detach(f"authorisation refused: {err.code}")
            raise AuthRefused("VENUE_AUTH_REFUSED", err.code) from err
