"""scripts/ctrader_setup.py, the first-demo setup helpers (ACIS-13 §5.5, C-VEN-8): `tokens` refuses a
paste carrying a label and stores only clean values; `accounts` lists the grant's accounts and
prints no secret."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.data.ctrader.tokens import TokenPair, TokenStore
from scripts import ctrader_setup
from tests.ctrader_fixtures import ACCOUNT, FakeVenue


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    monkeypatch.setenv("ACIS_CTRADER_TOKEN_STORE", str(path))
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_ID", "1234_clientidvalue")
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_SECRET", "secret-never-printed")
    return path


def test_tokens_refuses_a_labelled_paste_and_stores_the_clean_pair(store, monkeypatch, capsys) -> None:
    answers = iter(["Access token abc", "a" * 43, "r" * 43])
    monkeypatch.setattr(ctrader_setup.getpass, "getpass", lambda prompt="": next(answers))
    ctrader_setup.store_tokens()
    pair = TokenStore(store).read()
    assert (pair.access_token, pair.refresh_token, pair.scope) == ("a" * 43, "r" * 43, "trading")
    assert pair.expires_at - pair.obtained_at == timedelta(days=28)
    out = capsys.readouterr().out
    assert "NOT accepted" in out and "a" * 43 not in out


def test_accounts_lists_the_grant_and_prints_no_secret(store, capsys) -> None:
    now = datetime.now(timezone.utc)
    TokenStore(store).write(TokenPair("access-1", "refresh-1", now + timedelta(days=28), now, "trading"))
    asyncio.run(ctrader_setup.list_accounts("demo", connect=FakeVenue().connect))
    out = capsys.readouterr().out
    assert "scope: 1" in out
    assert f"ctidTraderAccountId={ACCOUNT} traderLogin=77 isLive=False broker=Pepperstone" in out
    assert "secret-never-printed" not in out and "access-1" not in out
