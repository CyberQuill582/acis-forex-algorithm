"""The cTrader token store (ACIS-13 §5.5, §6.7, C-VEN-8): the OAuth pair in ONE JSON file named by
an environment variable, never YAML, never the repo, never a log line.

Invariants:
  * Single writer: the engine's session. The watchdog plugin only reads (§7.9).
  * A write goes to a temporary file, is fsynced, then atomically renamed over the store, so a
    crash leaves either the old pair or the new one, never half of each.
  * A refresh returns a NEW pair and the old one dies at once (F-08), so the new pair is
    persisted BEFORE it is used; a crash in between loses nothing.
  * `repr` never shows a token.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.data.errors import DataQualityError

REFRESH_BEFORE = timedelta(days=7)       # refresh proactively inside the last week (§6.7)
ENV_VAR = "ACIS_CTRADER_TOKEN_STORE"


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime
    obtained_at: datetime
    scope: str

    def __post_init__(self) -> None:
        if not self.access_token or not self.refresh_token:
            raise DataQualityError("token", "<redacted>", "both tokens are required")
        if self.expires_at.tzinfo is None or self.obtained_at.tzinfo is None:
            raise DataQualityError("expires_at", self.expires_at, "must be tz-aware")

    def needs_refresh(self, now: datetime) -> bool:
        return self.expires_at - now <= REFRESH_BEFORE


class TokenStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @classmethod
    def from_env(cls) -> "TokenStore":
        path = os.environ.get(ENV_VAR)
        if not path:
            raise DataQualityError(ENV_VAR, None, "the token store path is not set")
        return cls(path)

    def read(self) -> TokenPair:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return TokenPair(raw["access_token"], raw["refresh_token"],
                             datetime.fromisoformat(raw["expires_at_utc"]),
                             datetime.fromisoformat(raw["obtained_at_utc"]), str(raw["scope"]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DataQualityError("token_store", str(self.path), "unreadable or malformed") from exc

    def write(self, pair: TokenPair) -> None:
        body = json.dumps({"access_token": pair.access_token, "refresh_token": pair.refresh_token,
                           "expires_at_utc": pair.expires_at.isoformat(),
                           "obtained_at_utc": pair.obtained_at.isoformat(), "scope": pair.scope})
        tmp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, body.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self.path)


def pair_from_refresh(payload: dict, now: datetime, previous: TokenPair) -> TokenPair:
    """The pair a `ProtoOARefreshTokenRes` carries (`expiresIn` in seconds); a refresh keeps the
    grant's scope, which the response does not repeat."""
    return TokenPair(payload["accessToken"], payload["refreshToken"],
                     now + timedelta(seconds=int(payload["expiresIn"])),
                     now.astimezone(timezone.utc), previous.scope)
