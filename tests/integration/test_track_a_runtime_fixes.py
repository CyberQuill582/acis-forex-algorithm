"""Regression tests for the Track A dual audit's runtime findings (GAP-P12D-132). Each names the
finding it pins; each reproduces a probe that failed on the code the audit read (`86ea8d3`)."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from random import Random
from types import SimpleNamespace

from core.data.feeds import MockPaperFeed
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import FillReportStore
from core.execution.venue_quality import VenueQuality
from core.risk.store import RiskStore
from core.runtime.__main__ import cli, exclusive_lock
from core.runtime.venue_link import VenueLink
from core.runtime.wiring import build
from tests.ctrader_fixtures import ACCOUNT, FakeVenue, capture_logger
from tests.integration.test_ctrader_adapter import _bind, _face, _open
from tests.integration.test_runtime import ClockedFeed, TickClock, events
from tests.integration.test_paper_trading_pipeline import flat_ticks

CONFIG = Path(__file__).resolve().parents[2] / "config"
WEDNESDAY = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)      # FX open


def deployment(tmp_path: Path) -> Path:
    shutil.copytree(CONFIG, tmp_path / "config")
    (tmp_path / "data" / "runtime").mkdir(parents=True)
    return tmp_path


def link_over(cfg, face, session, tmp_path, now_fn, log) -> VenueLink:
    orch = ExecutionOrchestrator(
        cfg.system.execution, {face.name: face}, VenueQuality(), FillReportStore(tmp_path / "vf.db"),
        slippage_alert_bps=8.0, rng=Random(7), logger=log, session_id="rt", now_fn=now_fn)
    attached = SimpleNamespace(report=SimpleNamespace(practice_eligible=True), specs=face._specs,
                               descriptor=face.descriptor)
    return VenueLink(face=face, orchestrator=orch, attached=attached, poll_s=1e6, reconcile_s=1e6,
                     now_fn=now_fn, logger=log, session=session)


# -- TAI-05: a restart is venue truth; a recovered fill is never replayed on top ------------ #

async def test_a_stop_that_fired_while_down_leaves_no_phantom_after_a_restart(tmp_path, acis_config) -> None:
    _bind(tmp_path)
    venue, session, face, _ = await _face(tmp_path)
    await _open(face)
    (pid,) = venue.positions
    await session.stop()                                               # the engine dies
    venue.fire_stop(pid, 1.0850)                                       # ...and the stop fires
    venue, session, face, _ = await _face(tmp_path, venue)             # the restart
    positions, _ = await face.synchronise()
    assert positions == () and face.router.unsolicited.qsize() == 1    # SYNCING recovered it
    clock, (log, buf) = TickClock(), capture_logger()
    rt = build(acis_config, root=tmp_path, session_id="rt", now_fn=clock,
               feed=ClockedFeed(clock, flat_ticks()[:5]), intended_mode="practice",
               venue=link_over(acis_config, face, session, tmp_path, clock, log))
    await rt.boot(positions)
    assert await rt.run() == "feed_ended"
    assert rt.p.risk.positions() == ()                                 # was a phantom short
    assert "BOOT_FILL_IN_VENUE_TRUTH" in buf.getvalue()
    await session.stop()


async def test_a_paper_process_leaves_the_accounts_positions_and_fills_out_of_its_book(
        tmp_path, acis_config) -> None:
    # an ended practice session left a protected demo position; the unit restarts in paper
    _bind(tmp_path)
    venue, session, face, _ = await _face(tmp_path)
    await _open(face)
    (pid,) = venue.positions
    await session.stop()
    venue, session, face, _ = await _face(tmp_path, venue)
    positions, _ = await face.synchronise()
    assert len(positions) == 1
    clock, (log, _buf) = TickClock(), capture_logger()
    feed = ClockedFeed(clock, flat_ticks()[:200], at_tick={0: lambda: venue.fire_stop(pid, 1.0850)})
    rt = build(acis_config, root=tmp_path, session_id="rt", now_fn=clock, feed=feed,
               venue=link_over(acis_config, face, session, tmp_path, clock, log))
    await rt.boot(positions)
    assert rt.p.risk.positions() == ()                                 # not adopted into paper
    assert events(tmp_path, "system_log", "VENUE_POSITIONS_OUTSIDE_THE_BOOK")[0]["data"]["instruments"] == [
        "EUR_USD"]
    assert await rt.run() == "feed_ended"
    assert rt.p.risk.positions() == () and rt.p.risk_store.open_halts() == []
    assert events(tmp_path, "system_log", "VENUE_FILL_OUTSIDE_THE_BOOK")        # its stop, logged only
    await session.stop()


# -- TAI-06 / TAI-17: paper never reconciles against the venue; practice refreshes its token there -- #

async def test_the_periodic_reconcile_and_token_refresh_run_in_practice_only() -> None:
    calls, refreshed = [], []

    class Face:
        async def open_positions(self):
            calls.append(1)
            return ()

    class Session:
        def budget(self):
            return {"used_24h": 10, "cap": 1000, "close_reserve": 100}

        async def refresh_if_due(self):
            refreshed.append(1)

    link = VenueLink(face=Face(), orchestrator=None, attached=None, poll_s=1e6, reconcile_s=0.01,
                     now_fn=lambda: WEDNESDAY, logger=capture_logger()[0], session=Session())
    executor = SimpleNamespace(busy=set(), queue=asyncio.Queue())
    risk = SimpleNamespace(reconcile_on_restart=lambda broker, now: None)
    mode = ["paper"]
    task = asyncio.create_task(link.reconcile(risk, executor, active=lambda: mode[0] == "practice",
                                              flatten=lambda s, r: None))
    await asyncio.sleep(0.1)
    assert calls == [] and refreshed == []                             # paper: the venue is not its book
    mode[0] = "practice"
    await asyncio.sleep(0.1)
    assert calls and refreshed                                         # practice: reconciled, refreshed
    task.cancel()


# -- TAI-07: a human resumes at the terminal --------------------------------------------------- #

def test_a_human_resume_at_the_terminal_lifts_the_persisted_halts(tmp_path, monkeypatch) -> None:
    root = deployment(tmp_path)
    store = RiskStore(root / "data" / "runtime" / "risk.db")
    store.record_halt("halt|x|all|restart_drift|1", WEDNESDAY.isoformat(), "all", "restart_drift")
    store.close()
    monkeypatch.setenv("ACIS_HUMAN_TOKEN_SHA256", hashlib.sha256(b"owner-secret").hexdigest())
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "owner-secret")
    assert cli(["--root", str(root), "--mock-ticks", "3", "--resume"]) == 0
    assert RiskStore(root / "data" / "runtime" / "risk.db").open_halts() == []


def test_a_wrong_token_resumes_nothing(tmp_path, monkeypatch) -> None:
    root = deployment(tmp_path)
    store = RiskStore(root / "data" / "runtime" / "risk.db")
    store.record_halt("halt|x|all|restart_drift|1", WEDNESDAY.isoformat(), "all", "restart_drift")
    store.close()
    monkeypatch.setenv("ACIS_HUMAN_TOKEN_SHA256", hashlib.sha256(b"owner-secret").hexdigest())
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "a-guess")
    assert cli(["--root", str(root), "--mock-ticks", "3", "--resume"]) == 3
    assert len(RiskStore(root / "data" / "runtime" / "risk.db").open_halts()) == 1


# -- TAI-11: one engine per deployment root -------------------------------------------------- #

def test_a_second_engine_on_one_root_is_refused(tmp_path) -> None:
    root = deployment(tmp_path)
    held = exclusive_lock(root / "data" / "runtime" / "engine.lock")
    try:
        assert cli(["--root", str(root), "--mock-ticks", "3"]) == 2
    finally:
        held.close()
    assert cli(["--root", str(root), "--mock-ticks", "3"]) == 0        # free once the first is gone


# -- TAI-10: a foreign position at a later start refuses it ----------------------------------- #

async def test_a_foreign_position_at_a_later_start_refuses_it(tmp_path, acis_config, monkeypatch) -> None:
    from core.data.ctrader.tokens import TokenPair, TokenStore
    from core.runtime.attach_venue import attach_venue
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("a", "r", datetime.now(timezone.utc) + timedelta(days=20),
                           datetime.now(timezone.utc), "trading"))
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_ID", "cid")
    monkeypatch.setenv("ACIS_CTRADER_CLIENT_SECRET", "sec")
    monkeypatch.setenv("ACIS_CTRADER_TOKEN_STORE", str(tmp_path / "tokens.json"))
    sysc = acis_config.system.model_copy(update={
        "active_account": "pepperstone_demo",
        "venue": acis_config.system.venue.model_copy(update={"ctid_trader_account_id": ACCOUNT})})
    cfg = acis_config.model_copy(update={"system": sysc})
    venue = FakeVenue()
    venue.clock = datetime.now(timezone.utc)                           # attach reads the host clock
    log = capture_logger()[0]
    first = await attach_venue(cfg, "pepperstone_demo", tmp_path, log, "s1", connect=venue.connect)
    assert first.exit_code is None
    assert first.link.face._spread_of == first.feed.spread             # D3: the stop widens by the live spread
    first.link.events.cancel()
    await first.session.stop()
    venue.positions[555] = {"positionId": 555, "positionStatus": 1, "swap": 0, "price": 150.0,
                            "commission": -300, "moneyDigits": 2, "usedMargin": 3_300, "stopLoss": 151.0,
                            "tradeData": {"symbolId": 2, "volume": 500_000, "tradeSide": 2,
                                          "label": "a human", "openTimestamp": venue.ms()}}
    second = await attach_venue(cfg, "pepperstone_demo", tmp_path, log, "s2", connect=venue.connect)
    assert second.exit_code == 2                                       # never trades beside it


# -- TAI-13 / TAE-04: a silent fast loop while a market is open is a stall -------------------- #

class HangingFeed(MockPaperFeed):
    async def stream(self):
        async for tick in super().stream():
            yield tick
        await asyncio.Event().wait()                                    # the feed goes silent, alive


async def test_a_fast_loop_silent_while_a_market_is_open_is_flattened_and_halted(tmp_path, acis_config) -> None:
    sysc = acis_config.system
    sysc = sysc.model_copy(update={"risk": sysc.risk.model_copy(update={"eval_cadence_s": 0.05}),
                                   "runtime": sysc.runtime.model_copy(update={"fast_loop_stall_s": 0.3})})
    cfg = acis_config.model_copy(update={"system": sysc})
    t0 = time.monotonic()
    rt = build(cfg, root=tmp_path, session_id="rt", feed=HangingFeed({"EUR_USD": 1.1}, n_ticks=3),
               now_fn=lambda: WEDNESDAY + timedelta(seconds=time.monotonic() - t0))
    await rt.boot()
    assert await asyncio.wait_for(rt.run(), 30) == "stalled:risk"
    assert events(tmp_path, "system_log", "FAST_LOOP_SILENT")
    assert {(h.kind, h.reason) for h in rt.p.risk_store.open_halts()} == {
        ("flatten", "loop_stalled"), ("halt", "loop_stalled")}


# -- TAI-14 / TAI-18: practice's own Risk store; the minimum lot only in paper and practice ---- #

def test_practice_keeps_its_own_risk_store(tmp_path, acis_config) -> None:
    build(acis_config, root=tmp_path, session_id="rt", feed=MockPaperFeed({"EUR_USD": 1.1}, n_ticks=1),
          intended_mode="practice")
    assert (tmp_path / "data" / "runtime" / "risk_practice.db").exists()
    assert not (tmp_path / "data" / "runtime" / "risk.db").exists()   # paper's anchors stay apart


def test_the_minimum_lot_is_injected_in_paper_and_practice_only(tmp_path, acis_config) -> None:
    rt = build(acis_config, root=tmp_path, session_id="rt", feed=MockPaperFeed({"EUR_USD": 1.1}, n_ticks=1))
    assert rt.p.governor._fixed_units("EUR_USD") == Decimal("1000")
    rt.p.mode.set_mode("backtest")
    assert rt.p.governor._fixed_units("EUR_USD") is None               # ACIS-05 v1.6 step 3b


# -- GAP-P12D-132 D2 (owner ruling): the close reserve flattens and halts, once ------------------ #

async def test_reaching_the_close_reserve_in_practice_flattens_and_halts_once(tmp_path, acis_config) -> None:
    from config.account_doctrine import guardrail_hash, rulebook_hash
    from tests.integration.test_track_a_adapter_fixes import pad
    venue, session, face, _ = await _face(tmp_path, budget=60, reserve=20)
    clock, (log, _buf) = TickClock(), capture_logger()
    rt = build(acis_config, root=tmp_path, session_id="rt", now_fn=clock, intended_mode="practice",
               feed=ClockedFeed(clock, flat_ticks()[:5]),
               venue=link_over(acis_config, face, session, tmp_path, clock, log))
    rulebook = acis_config.platform_rules.accounts[acis_config.system.active_account]
    rt.p.mode.set_mode("practice", guardrail_hash=guardrail_hash(acis_config.guardrails),
                       rulebook_hash=rulebook_hash(rulebook))
    await rt.boot()
    assert rt.p.risk_store.open_halts() == []                          # outside the reserve
    pad(session, venue, 40)                                            # 40 >= 60 - 20
    await rt.evaluate()
    await rt.evaluate()
    assert sorted((h.kind, h.reason) for h in rt.p.risk_store.open_halts()) == [
        ("flatten", "budget_reserve"), ("halt", "budget_reserve")]
    assert len(events(tmp_path, "system_log", "VENUE_BUDGET_RESERVE_REACHED")) == 1
    await session.stop()
