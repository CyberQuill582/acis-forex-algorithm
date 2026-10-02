"""The shipped R1.6 universe and its runtime (config/, core/runtime/target_wiring.py; ACIS-05 v1.7 §6.4,
R6-3/R6-4/R6-5): what the committed config declares, what A9 must budget for it, and a runtime built
from it — the target loop wired as a task, NVMA's no-parameters veto reading the family's registration,
and the legacy modules silent on the universe even with promoted parameters."""

from __future__ import annotations

from datetime import timedelta
from random import Random

from config.account_doctrine import guardrail_hash, rulebook_hash
from config.targets_schema import check_targets
from core.data.ctrader.meter import RequestMeter
from core.data.ctrader.session import Credentials, CTraderSession
from core.data.ctrader.tokens import TokenPair, TokenStore
from core.execution.ctrader_attach import HISTORY_PER_INSTRUMENT, attach, feasible
from core.execution.ctrader_face import CTraderExecutionFace
from core.execution.ctrader_store import VenueStore
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import FillReportStore
from core.execution.venue_quality import VenueQuality
from core.regime.regime_types import RegimeType
from core.runtime.target_decision import TO_USD
from core.runtime.target_loop import TargetLoop
from core.runtime.venue_link import VenueLink
from core.runtime.wiring import build
from tests.ctrader_fixtures import ACCOUNT, T0 as VENUE_T0, FakeVenue, capture_logger
from tests.integration.test_runtime import BOUNDARY, ClockedFeed, TickClock, flat_ticks
from tests.optimizer_fixtures import make_paramset


def _demo(cfg):
    return cfg.model_copy(update={"system": cfg.system.model_copy(update={"active_account": "pepperstone_demo"})})


def test_the_shipped_universe_is_the_enabled_fx_each_mapped_clustered_and_with_its_usd_leg(shipped_config) -> None:
    cfg = _demo(shipped_config)
    t, enabled = cfg.system.targets, set(cfg.instruments.enabled)
    check_targets(cfg)                                                       # universe = enabled, sizing declared
    assert len(t.universe) == 13 and set(t.universe) == enabled              # R6-4's explored FX first
    assert enabled <= set(cfg.system.venue.symbol_names)
    clustered = {s for members in cfg.instruments.clusters.values() for s in members}
    assert enabled <= clustered                                              # no instrument bounded by the delta cap alone
    for s in enabled:
        quote = cfg.instruments.instruments[s].quote_ccy
        assert quote == "USD" or TO_USD[quote][0] in enabled                 # its sizing rate is traded too
    book = cfg.platform_rules.accounts["pepperstone_demo"]
    assert (book.initial_capital, book.vol_target_annual) == (10_000, 0.20)   # R6-5, re-ruled 2026-10-02 (ACIS-05 v1.8)


def test_a9_budgets_two_history_requests_per_targeted_instrument(shipped_config) -> None:
    v = shipped_config.system.venue
    room = v.daily_request_budget - v.close_reserve
    loose = v.model_copy(update={"daily_request_budget": 1000, "close_reserve": 10})
    assert feasible(loose, room, targeted=13) is None
    base = 8 * (1 + v.backoff.max_consecutive) + 86400 / v.equity_poll_s * 2 + 86400 / v.reconcile_interval_s \
        + 4 * v.max_orders_per_day
    over = v.model_copy(update={"daily_request_budget": int(base) + v.close_reserve})   # room for all but history
    assert feasible(over, int(base), targeted=0) is None
    assert "projected" in feasible(over, int(base), targeted=1)              # one instrument's 2 requests tip it
    assert HISTORY_PER_INSTRUMENT == 2


async def test_a_runtime_from_the_shipped_config_wires_the_target_loop_and_silences_legacy(
        tmp_path, shipped_config) -> None:
    sysc = shipped_config.system.model_copy(update={
        "active_account": "pepperstone_demo",
        "venue": shipped_config.system.venue.model_copy(update={"ctid_trader_account_id": ACCOUNT,
                                                                "equity_poll_s": 1e6})})
    cfg = shipped_config.model_copy(update={"system": sysc})
    fake, log = FakeVenue(), capture_logger()[0]
    tokens = TokenStore(tmp_path / "tokens.json")
    tokens.write(TokenPair("a", "r", VENUE_T0 + timedelta(days=20), VENUE_T0, "trading"))
    key = sysc.venue.account_key
    session = CTraderSession(environment="demo", binding=ACCOUNT, credentials=Credentials("c", "s"), tokens=tokens,
                             meter=RequestMeter(tmp_path / "v.db", key, budget=1000, reserve=100, now=VENUE_T0),
                             logger=log, connect=fake.connect, now_fn=lambda: fake.clock, rate_per_s=10_000,
                             history_per_s=10_000)
    attached = await attach(sysc.venue, rulebook_key="pepperstone_demo",
                            rulebook=cfg.platform_rules.accounts["pepperstone_demo"],
                            instruments=cfg.instruments.instruments, session=session,
                            store=VenueStore(tmp_path / "v.db", key), logger=log, now=VENUE_T0,
                            execution_cap=sysc.execution.max_venue_requests_per_day)   # A9 aside: targeted=0
    assert attached.report.verdict == "ATTACHED" and len(attached.specs) == 13
    face = CTraderExecutionFace(session, attached.specs, attached.descriptor, VenueStore(tmp_path / "v.db", key),
                                log, account_key=key, now_fn=lambda: fake.clock, order_ack_timeout_s=2.0,
                                stop_confirm_timeout_s=0.0)
    events = face.start()
    positions, _ = await face.synchronise()
    clock = TickClock()
    orch = ExecutionOrchestrator(sysc.execution, {face.name: face}, VenueQuality(), FillReportStore(tmp_path / "vf.db"),
                                 slippage_alert_bps=8.0, rng=Random(7), logger=log, session_id="rt", now_fn=clock)
    link = VenueLink(face=face, orchestrator=orch, attached=attached, poll_s=1e6, reconcile_s=1e6, now_fn=clock,
                     logger=log, session=session, events=events)
    rt = build(cfg, root=tmp_path, session_id="rt", feed=ClockedFeed(clock, flat_ticks()), venue=link,
               now_fn=clock, intended_mode="practice")
    assert isinstance(rt.p.targets, TargetLoop) and rt.p.target_universe == frozenset(sysc.targets.universe)
    assert rt.p.targets.sizing.weights["EUR_USD"] == 1 / 13 and rt.p.targets.sizing.cash_vol == 10_000 * 0.20 / 16
    for regime in (RegimeType.MEAN_REVERTING, RegimeType.RANGING_TIGHT, RegimeType.RANGING_WIDE):
        rt.p.params.stage(make_paramset(regime=regime, param_set_id=f"ps-{regime.value}",
                                        mean_rev_zscore_entry=1.5), now=BOUNDARY - timedelta(hours=1))
    rt.p.params.promote(BOUNDARY)                         # the legacy demo's trigger (tests/integration/test_runtime.py)
    for i in range(300):
        rt.p.agon.observe_daily_close("EUR_USD", 1.0 + 0.001 * i)
    await rt.boot(positions)
    rt.p.mode.set_mode("practice", guardrail_hash=guardrail_hash(cfg.guardrails),
                       rulebook_hash=rulebook_hash(cfg.platform_rules.accounts["pepperstone_demo"]))
    assert await rt.run() == "feed_ended"
    assert rt.p.agon.take_rate()["signals_emitted"] == 0                    # R6-3: one path per instrument
    assert [m for m in fake.transport.sent if m["payloadType"] == 2106] == []
    await session.stop()


async def test_opens_in_flight_count_in_every_exposure_so_one_slot_cannot_cross_a_cap() -> None:
    """R16I-05: a slot's later entries are judged against its earlier, unfilled ones."""
    import asyncio
    from decimal import Decimal
    from types import MappingProxyType
    from core.governor.portfolio_types import SizedOrder
    from core.governor.target_gate import target_orders
    from core.runtime.executor import Executor, WorkItem
    from core.runtime.portfolio import build_portfolio
    from tests.optimizer_fixtures import CapturingLogger
    from tests.signals_fixtures import T0, mk_regime
    from tests.unit.test_governor import mk_governor, mk_rulebook

    class _NoRisk:
        def positions(self):
            return ()

    async def _nothing():
        return None

    log = CapturingLogger()
    ex = Executor(route_to=lambda: None, risk=_NoRisk(), on_fill=_nothing, halt=lambda s, r: None,
                  mark_of=lambda i: None, now_fn=lambda: T0, logger=log)
    first = SizedOrder(order_id="o1", signal_id="s", instrument="EUR_USD", direction=1, size_units=Decimal("1000"),
                       entry_price=1.10, stop_loss=1.0, take_profit=None, reason="target_open",
                       factors_snapshot=MappingProxyType({}), sized_at=T0, param_set_id="trend_d1_v1")
    ex.submit(WorkItem((first,), valid_for_seconds=0))
    clusters = {"usd_short": ["EUR_USD", "GBP_USD"]}
    marks = {"EUR_USD": 1.10, "GBP_USD": 1.30}
    pf = build_portfolio(positions=(), strategy_of={}, marks=marks, nav=Decimal("10000"), daily_drawdown_pct=0.0,
                         clusters=clusters, as_of=T0, account_age_s=0.0, max_age_s=60.0, logger=log,
                         inflight=tuple(ex.inflight.values()))
    assert pf.per_cluster_exposure["usd_short"] == Decimal("1100.000") and pf.open_positions == ()
    gov, _ = mk_governor()
    second = target_orders(gov, limits=gov.guards._limits, rules=mk_rulebook(), clusters=clusters,
                           instrument="GBP_USD", held=None, target=Decimal("1000"), mark=1.30, atr=0.007,
                           stop_mult=10.0, step=Decimal("1000"), minimum=Decimal("1000"), portfolio=pf,
                           regime=mk_regime(instrument="GBP_USD"), marks=marks, now=T0, family="trend_d1_v1",
                           snapshot={}, logger=log)
    assert second.reason == "cluster_cap"                                    # 1,100 + 1,300 > 90% × 20% × 10k
    task = asyncio.create_task(ex.run())
    await ex.queue.join()
    task.cancel()
    assert ex.inflight == {}                                                 # gone once its item ends


async def test_the_legacy_max_hold_never_closes_a_target_universe_position(tmp_path, acis_config) -> None:
    """R6-3's exit half (R16I-09): a universe position held past max_hold_s gets no legacy close;
    the same position outside the universe does (the control proves the test can see it)."""
    from decimal import Decimal
    from core.risk.risk_types import RiskPosition
    from tests.integration.test_paper_trading_pipeline import T0 as TICK0
    from tests.integration.test_runtime import runtime

    closes = {}
    for universe in (frozenset({"EUR_USD"}), frozenset()):
        rt = runtime(tmp_path / ("in" if universe else "out"), acis_config)
        await rt.boot()
        old = RiskPosition("EUR_USD", 1, Decimal("1000"), 1.10, opened_at=TICK0 - timedelta(days=5),
                           param_set_id="trend_d1_v1", stop_loss=1.0)
        rt.p.risk.positions = lambda old=old: (old,)
        rt.p.target_universe = universe
        sent = []
        rt.p.executor.submit = sent.append
        await rt.run()
        closes[bool(universe)] = [o for item in sent for o in item.orders if o.reason == "max_hold"]
    assert closes[True] == [] and closes[False]
