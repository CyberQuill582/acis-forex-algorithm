"""The cTrader attach (ACIS-13 §7.1 A1–A6, A11; master v2.23 practice eligibility) against the fake
venue: a verified attach, and each named refusal with nothing traded."""

from __future__ import annotations

import pytest

from config.rulebook import AccountRulebook
from core.data.ctrader.meter import RequestMeter
from core.data.ctrader.session import Credentials, CTraderSession
from core.data.ctrader.tokens import TokenPair, TokenStore
from core.execution.ctrader_attach import attach
from core.execution.ctrader_store import VenueStore
from tests.ctrader_fixtures import ACCOUNT, T0, FakeVenue, capture_logger, events
from datetime import timedelta

DEMO_RULES = {"platform": "ctrader", "news": {"restricted": False}, "min_hold_seconds": 0,
              "weekend_holding_allowed": True, "drawdown_rules": [], "account_class": "practice"}


async def _attach(tmp_path, acis_config, venue=None, *, account=ACCOUNT, rules=None):
    venue = venue or FakeVenue()
    cfg = acis_config.system.venue.model_copy(update={"ctid_trader_account_id": account})
    log, buf = capture_logger()
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("access-1", "refresh-1", T0 + timedelta(days=20), T0, "trading"))
    session = CTraderSession(environment=cfg.environment, binding=account,
                             credentials=Credentials("cid", "sec"), tokens=tokens,
                             meter=RequestMeter(tmp_path / "v.db", cfg.account_key, budget=1000,
                                                reserve=100, now=T0),
                             logger=log, connect=venue.connect, now_fn=lambda: venue.clock,
                             rate_per_s=10_000)
    result = await attach(cfg, rulebook_key="pepperstone_demo",
                          rulebook=AccountRulebook.model_validate(rules or DEMO_RULES),
                          instruments=acis_config.instruments.instruments, session=session,
                          store=VenueStore(tmp_path / "v.db", cfg.account_key), logger=log, now=T0,
                          execution_cap=acis_config.system.execution.max_venue_requests_per_day)
    return venue, result, buf


async def test_a_practice_demo_attaches_verified_and_eligible_for_practice(tmp_path, acis_config) -> None:
    venue, result, buf = await _attach(tmp_path, acis_config)
    report = result.report
    assert report.verdict == "ATTACHED" and report.practice_eligible
    assert report.deposit_asset == "USD" and report.symbols == ("EUR_USD", "USD_JPY")
    assert result.descriptor.symbol_map == {"EUR_USD": "EURUSD", "USD_JPY": "USDJPY"}
    assert result.feed_symbols == {1: ("EUR_USD", 5), 2: ("USD_JPY", 3)}
    assert [e["n"] for e in events(buf, "ATTACH_STEP")] == [1, 3, 4, 5, 6]
    assert 2106 not in venue.requests                          # an attach never trades


async def test_an_uncommitted_binding_is_refused_before_the_venue_is_contacted(tmp_path, acis_config) -> None:
    venue, result, _ = await _attach(tmp_path, acis_config, account=0)
    assert result.report.verdict == "FATAL" and "ATTACH_UNBOUND" in result.report.reason
    assert venue.requests == []


async def test_a_rulebook_without_the_practice_class_attaches_but_is_not_practice(tmp_path, acis_config) -> None:
    rules = {k: v for k, v in DEMO_RULES.items() if k != "account_class"}
    _, result, _ = await _attach(tmp_path, acis_config, rules=rules)
    assert result.report.verdict == "ATTACHED" and not result.report.practice_eligible


async def test_a_first_attach_onto_an_occupied_account_halts_for_a_human(tmp_path, acis_config) -> None:
    venue = FakeVenue()
    venue.positions[1] = {"positionId": 1, "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1}}
    _, result, _ = await _attach(tmp_path, acis_config, venue)
    assert result.report.verdict == "HALTED_OPEN_POSITIONS" and result.report.open_positions == 1
    assert not result.report.practice_eligible and 2106 not in venue.requests


@pytest.mark.parametrize("breakage, verdict", [
    ("suffix", "ATTACH_SYMBOL"),              # the venue names EURUSD.pro: never fuzzy-merged
    ("tick", "ATTACH_CONTRACT"),              # a 4-digit EURUSD disagrees with instruments.yaml
    ("platform", "ATTACH_PLATFORM_MISMATCH"),
])
async def test_each_contract_disagreement_is_a_named_refusal(tmp_path, acis_config, breakage, verdict) -> None:
    venue, rules = FakeVenue(), dict(DEMO_RULES)
    if breakage == "suffix":
        venue.light = [{**venue.light[0], "symbolName": "EURUSD.pro"}, venue.light[1]]
    elif breakage == "tick":
        venue.symbols[1]["digits"] = 4
    else:
        rules["platform"] = "mt5"
    _, result, _ = await _attach(tmp_path, acis_config, venue, rules=rules)
    assert result.report.verdict == "FATAL" and verdict in result.report.reason


def test_a_budget_that_cannot_carry_the_day_is_refused_before_the_venue(acis_config) -> None:
    from core.execution.ctrader_attach import feasible
    cfg = acis_config.system.venue
    assert feasible(cfg, 900) is None                                    # the committed defaults fit
    assert "max_venue_requests_per_day" in feasible(cfg, 1000)           # the orchestrator must refuse first
    tight = cfg.model_copy(update={"equity_poll_s": 60.0})               # 2,880 polls a day
    assert "projected" in feasible(tight, 900)
