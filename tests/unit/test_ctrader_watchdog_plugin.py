"""The watchdog's cTrader flatten plugin (master §8.6 layer 2, ACIS-13 §7.9, §14.2 case 8): it imports
nothing from core/, closes every position and cancels every pending order on the bound account, and
reports `ok` only when a second reconcile finds the account flat."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest

from scripts.acis_watchdog import FlattenResult, _PLUGINS
from tests.ctrader_fixtures import ACCOUNT, FakeVenue

PLUGIN_PY = Path(__file__).resolve().parents[2] / "scripts" / "watchdog_plugins" / "ctrader_flatten.py"


def test_the_plugin_imports_nothing_from_core() -> None:
    tree = ast.parse(PLUGIN_PY.read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    assert not [m for m in names if m.split(".")[0] in ("core", "config", "monitoring")], names


def _plugin(venue: FakeVenue):
    plugin = _PLUGINS["ctrader"]({"environment": "demo", "ctid_trader_account_id": ACCOUNT})
    plugin._connect = venue.connect
    plugin._settle = 1.0                                      # keep the refusal test short
    return plugin


@pytest.fixture
def env(tmp_path, monkeypatch):
    store = tmp_path / "tokens.json"
    store.write_text(json.dumps({"access_token": "access-1"}), encoding="utf-8")
    monkeypatch.setenv("ACIS_CTRADER_TOKEN_STORE", str(store))
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_SECRET", "sec")


def test_the_plugin_flattens_every_position_and_proves_it_flat(env) -> None:
    venue = FakeVenue()

    async def seed():                                         # two positions the engine left open
        await venue.connect("demo")
        for pid, sid in ((1, 1), (2, 2)):
            venue.positions[pid] = {"positionId": pid, "positionStatus": 1, "swap": 0,
                                    "tradeData": {"symbolId": sid, "volume": 100_000, "tradeSide": 1}}
    asyncio.run(seed())
    result = _plugin(venue).flatten_all("unused")
    assert result == FlattenResult(ok=True, positions_closed=2)
    assert venue.positions == {}
    assert venue.requests.count(2111) == 2 and venue.requests.count(2124) == 2   # closes + two reconciles


def test_a_flatten_that_leaves_a_position_open_is_never_reported_ok(env) -> None:
    venue = FakeVenue()

    async def refuse_closes(p, mid, t):                       # the venue ignores every close
        t.push(2126, {"executionType": 2}, mid)
    venue._on_close_position_req = refuse_closes
    venue.positions[1] = {"positionId": 1, "positionStatus": 1, "swap": 0,
                          "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1}}
    result = _plugin(venue).flatten_all("unused")
    assert result.ok is False and "still open" in result.error



def test_a_close_that_fills_after_its_acknowledgement_is_waited_for(env) -> None:
    """GAP-P12D-133 (case 8 on the demo): cTrader acknowledges a close before it fills, so the first
    reconcile can still show the position; the plugin polls for flat instead of reporting failure."""
    venue = FakeVenue()

    async def ack_then_fill(p, mid, t):
        t.push(2126, {"executionType": 2}, mid)
        asyncio.get_running_loop().call_later(0.3, venue.positions.pop, p["positionId"], None)
    venue._on_close_position_req = ack_then_fill
    venue.positions[1] = {"positionId": 1, "positionStatus": 1, "swap": 0,
                          "tradeData": {"symbolId": 1, "volume": 100_000, "tradeSide": 1}}
    result = _plugin(venue).flatten_all("unused")
    assert result == FlattenResult(ok=True, positions_closed=1)
    assert venue.positions == {} and venue.requests.count(2124) >= 3   # the book, then polls until flat

def test_the_watchdog_binding_matches_the_engine_binding() -> None:
    """OQ-06: the account binding lives in two human-committed files and the engine may not read
    `watchdog.yaml`, so CI checks they agree; a mismatch would flatten the wrong account, or none."""
    import yaml

    from config.schemas import load_config

    root = Path(__file__).resolve().parents[2]
    wd = yaml.safe_load((root / "config" / "watchdog.yaml").read_text(encoding="utf-8"))
    venue = load_config(str(root / "config")).system.venue
    if wd["flatten_plugin"] == "ctrader":
        assert wd["environment"] == venue.environment
        assert int(wd["ctid_trader_account_id"]) == venue.ctid_trader_account_id != 0
