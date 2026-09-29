"""The first-demo-session probe (scripts/ctrader_probe.py) end to end against the fake venue: it
attaches read-only, records frames with every secret redacted, and its one round trip is allowed
only on a practice-eligible account."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from config.rulebook import AccountRulebook
from core.data.ctrader.tokens import TokenPair, TokenStore
from scripts import ctrader_probe
from tests.ctrader_fixtures import ACCOUNT, T0, FakeVenue

RULES = {"platform": "ctrader", "news": {"restricted": False}, "min_hold_seconds": 0,
         "weekend_holding_allowed": True, "drawdown_rules": [], "account_class": "practice"}


@pytest.fixture
def probe_env(tmp_path, monkeypatch, acis_config):
    venue = FakeVenue()
    venue_cfg = acis_config.system.venue.model_copy(update={"ctid_trader_account_id": ACCOUNT})
    accounts = {**acis_config.platform_rules.accounts, "demo": AccountRulebook.model_validate(RULES),
                "not_practice": AccountRulebook.model_validate(
                    {k: v for k, v in RULES.items() if k != "account_class"})}
    cfg = acis_config.model_copy(update={
        "system": acis_config.system.model_copy(update={"venue": venue_cfg}),
        "platform_rules": acis_config.platform_rules.model_copy(update={"accounts": accounts})})
    monkeypatch.setattr(ctrader_probe, "load_config", lambda _: cfg)
    monkeypatch.setattr(ctrader_probe, "open_websocket", venue.connect)
    store = tmp_path / "tokens.json"
    TokenStore(store).write(TokenPair("access-SECRET", "refresh-SECRET", T0 + timedelta(days=20), T0, "trading"))
    monkeypatch.setenv("ACIS_CTRADER_TOKEN_STORE", str(store))
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_SECRET", "client-SECRET")
    return venue, tmp_path


def _args(tmp_path, rulebook, trade):
    return SimpleNamespace(config="config", rulebook=rulebook, spots_s=0.3, trade=trade,
                           db=str(tmp_path / "v.db"), log=str(tmp_path / "p.jsonl"))


async def test_the_probe_attaches_records_redacted_frames_and_round_trips(probe_env) -> None:
    venue, tmp = probe_env
    report = await ctrader_probe.probe(_args(tmp, "demo", trade=True))
    assert report["attach"]["verdict"] == "ATTACHED" and report["attach"]["account_class"] == "practice"
    assert report["spots"] and report["spots"][0]["snapshot"] is True
    assert report["trade"]["open"] == "FILLED" and report["trade"]["close"] == "FILLED"
    assert report["trade"]["stop_at_venue"] is not None
    assert "SECRET" not in json.dumps(report)                   # tokens and the client secret redacted
    assert venue.positions == {}                                # the round trip left it flat


async def test_the_probe_never_trades_an_account_that_is_not_practice(probe_env) -> None:
    venue, tmp = probe_env
    report = await ctrader_probe.probe(_args(tmp, "not_practice", trade=True))
    assert "refused" in report["trade"] and 2106 not in venue.requests
