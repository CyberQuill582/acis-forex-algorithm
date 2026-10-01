"""First-demo setup helpers (ACIS-13 §5.5, §6.7, C-VEN-8). Human-run, on the engine host.

    python scripts/ctrader_setup.py tokens     # type the Playground pair at hidden prompts
    python scripts/ctrader_setup.py accounts   # list the accounts the grant covers

`tokens` writes the store named by ACIS_CTRADER_TOKEN_STORE through `TokenStore.write` (0600,
atomic). The expiry is set to 28 days, inside cTrader's ~30-day access-token life, so the session
refreshes early rather than late. `accounts` is read-only: application auth, then the grant's
account list, printing ids, logins, isLive and the scope, never a secret. A human reads the
`ctidTraderAccountId` of the demo's login and commits it as `venue.ctid_trader_account_id`.
"""

from __future__ import annotations

import asyncio
import getpass
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data.ctrader import schema as s  # noqa: E402
from core.data.ctrader.link import Credentials  # noqa: E402
from core.data.ctrader.tokens import TokenPair, TokenStore  # noqa: E402
from core.data.ctrader.transport import open_websocket  # noqa: E402
from core.data.ctrader.wire import decode, encode, error_of  # noqa: E402

ASSUMED_LIFE = timedelta(days=28)


def _ask(label: str) -> str:
    """One clean value: a paste that carries a label or a second line is refused and asked again."""
    while True:
        value = getpass.getpass(f"{label} (paste ONLY the value, then Enter): ").strip()
        if len(value) >= 16 and not any(c.isspace() for c in value):
            print(f"  ok: {label} accepted ({len(value)} characters)")
            return value
        print(f"  NOT accepted: {len(value)} characters or it contains a space. Copy just the value.")


def store_tokens() -> None:
    store = TokenStore.from_env()
    access, refresh = _ask("Access token"), _ask("Refresh token")
    now = datetime.now(timezone.utc)
    store.write(TokenPair(access, refresh, now + ASSUMED_LIFE, now, "trading"))
    print(f"token store written: {store.path}")


async def _reply(ws, want: int):
    while True:
        raw = await ws.receive()
        if raw is None:
            raise SystemExit("the venue closed the connection")
        frame = decode(raw)
        if (err := error_of(frame)) is not None:
            raise SystemExit(f"venue refused: {err.code} {err.description}")
        if frame.payload_type == want:
            return frame.payload


async def list_accounts(environment: str) -> None:
    creds, pair = Credentials.from_env(), TokenStore.from_env().read()
    ws = await open_websocket(environment)
    try:
        await ws.send_str(encode(s.PT.APPLICATION_AUTH_REQ,
                                 {"clientId": creds.client_id, "clientSecret": creds.client_secret}, "a1"))
        await _reply(ws, s.PT.APPLICATION_AUTH_RES)
        await ws.send_str(encode(s.PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": pair.access_token}, "a2"))
        res = await _reply(ws, s.PT.GET_ACCOUNTS_BY_ACCESS_TOKEN_RES)
    finally:
        await ws.close()
    print(f"scope: {res.get('permissionScope')}")
    for a in res.get("ctidTraderAccount", []):
        print(f"ctidTraderAccountId={a.get('ctidTraderAccountId')} traderLogin={a.get('traderLogin')} "
              f"isLive={a.get('isLive', False)} broker={a.get('brokerTitleShort')}")


if __name__ == "__main__":
    if sys.argv[1:] == ["tokens"]:
        store_tokens()
    elif sys.argv[1:] == ["accounts"]:
        asyncio.run(list_accounts("demo"))
    else:
        raise SystemExit(__doc__)
