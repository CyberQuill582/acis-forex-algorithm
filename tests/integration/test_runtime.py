"""The three-loop runtime end to end (master §10, Track A step 4): the production layers, wired
by core/runtime/wiring.py, on the phase-7 market that made 67 identical orders (GAP-0075).

Every postcondition is observed in the runtime's own records: Risk's positions, the paper
venue's resting stops, the halt ledger, the JSONL streams and the heartbeat."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from decimal import Decimal

import pytest

from core.data.feeds import MockPaperFeed
from core.regime.regime_types import RegimeType
from core.runtime.wiring import build
from tests.integration.test_paper_trading_pipeline import BOUNDARY, T0, WARMUP, flat_ticks
from tests.optimizer_fixtures import make_paramset


class TickClock:
    """The runtime's `now_fn` follows the ticks, so fills, exits and Risk share one timeline."""

    def __init__(self) -> None:
        self.t = T0

    def __call__(self):
        return self.t


class ClockedFeed(MockPaperFeed):
    """The phase-7 ticks; `at_tick[i]` runs just before tick i is delivered (an MCP call, a crash)."""

    def __init__(self, clock: TickClock, ticks, at_tick=None) -> None:
        super().__init__({"EUR_USD": 1.10}, scripted=ticks)
        self._clock, self._at = clock, dict(at_tick or {})

    async def stream(self):
        i = 0
        async for tick in super().stream():
            if i in self._at:
                self._at[i]()
            self._clock.t = tick.event_time
            yield tick
            await asyncio.sleep(0)            # a real feed awaits I/O per tick: the executor runs
            i += 1


def runtime(tmp_path, cfg, at_tick=None, ticks=None):
    clock = TickClock()
    rt = build(cfg, root=tmp_path, session_id="rt",
               feed=ClockedFeed(clock, ticks or flat_ticks(), at_tick), now_fn=clock)
    for regime in (RegimeType.MEAN_REVERTING, RegimeType.RANGING_TIGHT, RegimeType.RANGING_WIDE):
        rt.p.params.stage(make_paramset(regime=regime, param_set_id=f"ps-{regime.value}",
                                        mean_rev_zscore_entry=1.5), now=BOUNDARY - timedelta(hours=1))
    assert len(rt.p.params.promote(BOUNDARY)) == 3              # flat: the gate lets them in
    for i in range(300):                                        # the TSMOM daily seed (phase 7)
        rt.p.agon.observe_daily_close("EUR_USD", 1.0 + 0.001 * i)
    return rt


def events(tmp_path, stream: str, event_type: str) -> list[dict]:
    lines = (tmp_path / "logs" / f"{stream}.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if r["event_type"] == event_type]


async def test_the_phase7_market_makes_one_position_with_its_stop_not_a_firehose(
        tmp_path, acis_config) -> None:
    rt = runtime(tmp_path, acis_config)
    await rt.boot()
    assert await rt.run() == "feed_ended"
    assert rt.p.agon.take_rate()["signals_emitted"] > 1          # TSMOM re-fired tick after tick...
    opens = [e for e in events(tmp_path, "trade_log", "SUBMIT") if e["data"]["action"] == "open"]
    assert len(opens) == 1                                       # ...but ONE order left (GAP-0075)
    (pos,) = rt.p.risk.positions()
    assert (pos.instrument, pos.direction, pos.size_units) == ("EUR_USD", 1, Decimal("1000"))
    assert (await rt.p.paper.resting_stops())["EUR_USD"] == pos.stop_loss < pos.avg_entry_price
    beat = json.loads((tmp_path / "logs" / "heartbeat.json").read_text(encoding="utf-8"))
    assert (beat["mode"], beat["open_positions"], beat["fast_loop_seq"]) == ("paper", 1, WARMUP)
    account = rt.p.paper.account()               # GAP-0091b: Risk marks at the runtime's marks
    assert rt.snapshot.daily_pnl == pytest.approx(account.equity - account.balance)
    assert rt.snapshot.daily_pnl != 0


async def test_staged_params_promote_at_a_crossed_session_boundary_while_flat(
        tmp_path, acis_config) -> None:
    # GAP-P12D-129: the demo's sets are staged offline; the runtime's own sweep promotes them
    from datetime import datetime, timezone
    start = datetime(2026, 7, 14, 6, 55, tzinfo=timezone.utc)      # 07:00 UTC = London 08:00 BST
    ticks = [t async for t in MockPaperFeed({"EUR_USD": 1.1}, start=start, n_ticks=10,
                                            tick_interval_s=60).stream()]
    clock = TickClock()
    rt = build(acis_config, root=tmp_path, session_id="rt", now_fn=clock,
               feed=ClockedFeed(clock, ticks))
    rt.p.params.stage(make_paramset(regime=RegimeType.MEAN_REVERTING, param_set_id="demo-mr"),
                      now=start - timedelta(days=1))
    await rt.boot()
    assert rt.p.params.get_active(RegimeType.MEAN_REVERTING) is None
    await rt.run()
    assert rt.p.params.get_active(RegimeType.MEAN_REVERTING).params.param_set_id == "demo-mr"


async def test_an_mcp_flatten_closes_the_holding_freezes_opens_and_is_recorded(
        tmp_path, acis_config) -> None:
    holder = []
    rt = runtime(tmp_path, acis_config, at_tick={260: lambda: holder[0].p.control.flatten("all", "mcp")})
    holder.append(rt)
    await rt.boot()
    await rt.run()
    submits = events(tmp_path, "trade_log", "SUBMIT")
    assert [e["data"]["action"] for e in submits] == ["open", "close"]   # nothing reopened
    assert rt.p.risk.positions() == () and await rt.p.paper.resting_stops() == {}
    assert rt.p.paper_orch.frozen                                # opens refused until a human
    assert [(h.kind, h.scope, h.reason) for h in rt.p.risk_store.open_halts()] == [
        ("flatten", "all", "mcp")]


async def test_practice_sends_the_one_open_to_the_attached_demo_with_its_stop(
        tmp_path, acis_config) -> None:
    from random import Random

    from config.account_doctrine import guardrail_hash, rulebook_hash
    from core.data.ctrader.meter import RequestMeter
    from core.data.ctrader.session import Credentials, CTraderSession
    from core.data.ctrader.tokens import TokenPair, TokenStore
    from core.execution.ctrader_attach import attach
    from core.execution.ctrader_face import CTraderExecutionFace
    from core.execution.ctrader_store import VenueStore
    from core.execution.orchestrator import ExecutionOrchestrator
    from core.execution.venue import FillReportStore
    from core.execution.venue_quality import VenueQuality
    from core.runtime.venue_link import VenueLink
    from tests.ctrader_fixtures import ACCOUNT, T0 as VENUE_T0, FakeVenue, capture_logger

    # one boot poll stays fresh across the replay's tick-hours: this test is about routing
    sysc = acis_config.system.model_copy(update={
        "active_account": "pepperstone_demo",
        "venue": acis_config.system.venue.model_copy(update={"ctid_trader_account_id": ACCOUNT,
                                                             "equity_poll_s": 1e6})})
    cfg = acis_config.model_copy(update={"system": sysc})
    fake, log = FakeVenue(), capture_logger()[0]
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("a", "r", VENUE_T0 + timedelta(days=20), VENUE_T0, "trading"))
    key = sysc.venue.account_key
    session = CTraderSession(environment="demo", binding=ACCOUNT, credentials=Credentials("c", "s"),
                             tokens=tokens, meter=RequestMeter(tmp_path / "v.db", key, budget=1000,
                                                               reserve=100, now=VENUE_T0),
                             logger=log, connect=fake.connect, now_fn=lambda: fake.clock,
                             rate_per_s=10_000)
    attached = await attach(sysc.venue, rulebook_key="pepperstone_demo",
                            rulebook=cfg.platform_rules.accounts["pepperstone_demo"],
                            instruments=cfg.instruments.instruments, session=session,
                            store=VenueStore(tmp_path / "v.db", key), logger=log, now=VENUE_T0,
                            execution_cap=sysc.execution.max_venue_requests_per_day)
    assert attached.report.practice_eligible
    face = CTraderExecutionFace(session, attached.specs, attached.descriptor,
                                VenueStore(tmp_path / "v.db", key), log, account_key=key,
                                now_fn=lambda: fake.clock, order_ack_timeout_s=2.0,
                                stop_confirm_timeout_s=0.0)
    face.start()
    positions, _ = await face.synchronise()
    clock = TickClock()
    orch = ExecutionOrchestrator(sysc.execution, {face.name: face}, VenueQuality(),
                                 FillReportStore(tmp_path / "vf.db"), slippage_alert_bps=8.0,
                                 rng=Random(7), logger=log, session_id="rt", now_fn=clock)
    link = VenueLink(face=face, orchestrator=orch, attached=attached, poll_s=1e6, reconcile_s=1e6,
                     now_fn=clock, logger=log)
    rt = build(cfg, root=tmp_path, session_id="rt", feed=ClockedFeed(clock, flat_ticks()),
               venue=link, now_fn=clock)
    for regime in (RegimeType.MEAN_REVERTING, RegimeType.RANGING_TIGHT, RegimeType.RANGING_WIDE):
        rt.p.params.stage(make_paramset(regime=regime, param_set_id=f"ps-{regime.value}",
                                        mean_rev_zscore_entry=1.5), now=BOUNDARY - timedelta(hours=1))
    rt.p.params.promote(BOUNDARY)
    for i in range(300):
        rt.p.agon.observe_daily_close("EUR_USD", 1.0 + 0.001 * i)
    await rt.boot(positions)
    rt.p.mode.set_mode("practice", guardrail_hash=guardrail_hash(cfg.guardrails),
                       rulebook_hash=rulebook_hash(cfg.platform_rules.accounts["pepperstone_demo"]))
    assert await rt.run() == "feed_ended"
    orders = [m["payload"] for m in fake.transport.sent if m["payloadType"] == 2106]
    assert len(orders) == 1 and orders[0]["relativeStopLoss"] > 0    # one open, protected
    assert rt.p.paper.submissions == 0                                # nothing went to paper
    (pos,) = rt.p.risk.positions()
    assert pos.size_units == attached.specs["EUR_USD"].min_units      # one venue minimum lot
    await session.stop()


async def test_no_entry_until_a_live_tick_proves_the_host_clock(tmp_path, acis_config) -> None:
    # ACIS-13 A8: every tick arrives 2 s after its venue stamp (tolerance 1.5 s, stale 2.5 s)
    from dataclasses import replace
    late = [replace(t, recv_time=t.event_time + timedelta(seconds=2)) for t in flat_ticks()]
    rt = runtime(tmp_path, acis_config, ticks=late)
    await rt.boot()
    await rt.run()
    assert rt.p.agon.take_rate()["signals_emitted"] > 0             # the engine wanted to trade
    assert events(tmp_path, "system_log", "CLOCK_CHECK_FAILED")[0]["data"]["lag_ms"] == 2000.0
    assert rt.p.risk.positions() == () and rt.p.paper.submissions == 0


async def test_a_dying_fast_loop_is_a_stall_flattened_and_halted(tmp_path, acis_config) -> None:
    def crash() -> None:
        raise ConnectionResetError("feed died")

    rt = runtime(tmp_path, acis_config, at_tick={270: crash})
    await rt.boot()
    assert await rt.run() == "stalled:fast_loop"
    assert rt.p.risk.positions() == ()                           # the closes drained first
    assert {(h.kind, h.reason) for h in rt.p.risk_store.open_halts()} == {
        ("flatten", "loop_stalled"), ("halt", "loop_stalled")}
    assert events(tmp_path, "system_log", "LOOP_STALLED")[0]["data"]["task"] == "fast_loop"
