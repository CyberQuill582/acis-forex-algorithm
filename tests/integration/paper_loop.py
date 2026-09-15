"""Phase-7 paper-trading loop harness (SPEC §15 phase 7, §13 integration).

Composes the PRODUCTION layers 1–5 exactly along §10's medium+fast loops —
mock feed → MarketStateFactory → NVMA → ParamLibrary → AGON → Governor — with
a paper book standing in for the phase-8 Execution Orchestrator. The
composition lives test-side by design (§18 lean-build: the production
three-loop runtime lands with the phases that need it, 8–10); every part
composed here IS the production code, wired through its real interfaces:

- NVMA session medians come from the real MarketStateFactory (C-DATA-4);
- NVMA's `has_params_for` is `ParamLibrary.has_active` (ACIS-03 §7.5);
- the ParamLibrary's PositionGate is the paper book (C2: open positions
  block promotion through the same wiring the live engine will use);
- the Governor is fed the SAME completed signal bars AGON aggregates
  (GAP-0059: one declared aggregation, never two);
- boot MUST call `governor.rebuild_groups(portfolio)` before the first tick
  (GAP-0052) — `run()` refuses to start unbooted.

§10 C15: `take_rate()` + `skip_attribution()` merge the per-gate counters the
three deciding layers keep, so every skip is attributable to the gate that
killed it — the same surfaces `acis://status` exposes at phase 10.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from config.schemas import AcisConfig
from core.data.feeds import FeedConnector
from core.data.ingestion import IngestionPipeline
from core.data.jsonl_logging import JsonlEventLogger
from core.data.normaliser import MarketState, MarketStateFactory
from core.data.store import AsyncBoundedWriter, MarketStateStore
from core.governor.capital_governor import CapitalGovernor
from core.governor.portfolio_types import PortfolioState, SizedOrder
from core.optimizer.param_library import ParamLibrary
from core.regime.nvma import NVMA, NVMAEngine
from core.signals.agon import AGON
from core.signals.canonical import register_canonical
from core.signals.provenance import ProvenanceStore


class PaperBook:
    """Paper positions (phase-8 stand-in) + the ParamLibrary PositionGate."""

    def __init__(self) -> None:
        self.orders: list[SizedOrder] = []
        self.closed: list[SizedOrder] = []

    def open_position_count(self) -> int:
        return len(self.orders)

    def open(self, order: SizedOrder) -> None:
        self.orders.append(order)

    def flatten(self) -> None:
        self.closed.extend(self.orders)
        self.orders.clear()


class PaperLoop:
    def __init__(
        self,
        factory: MarketStateFactory,
        nvma_engine: NVMAEngine,
        param_library: ParamLibrary,
        agon: AGON,
        governor: CapitalGovernor,
        writer: AsyncBoundedWriter,
        store: MarketStateStore,
        logger: JsonlEventLogger,
        portfolio_fn,
        regime_cycle_s: float | None = None,
    ) -> None:
        self._factory = factory
        # None: classify every tick (the compressed test cadence). A number: §10 Loop 2 —
        # classify each instrument at most once per `regime_cycle_s`, reusing the stored
        # context in between (historical replays, GAP-P12D-12).
        self._cycle_s = regime_cycle_s
        self._classified_at: dict[str, datetime] = {}
        self.nvma = nvma_engine
        self.params = param_library
        self.agon = agon
        self.governor = governor
        self._writer = writer
        self.store = store
        self._log = logger
        self._portfolio_fn = portfolio_fn
        self.book = PaperBook()
        self._booted = False
        self.last_context = None

    # -- boot (GAP-0052) ---------------------------------------------------- #

    def boot(self, portfolio: PortfolioState) -> int:
        rebuilt = self.governor.rebuild_groups(portfolio)
        self._log.event("BOOT_GROUPS_REBUILT", rebuilt=rebuilt)
        self._booted = True
        return rebuilt

    # -- the composed medium+fast loop -------------------------------------- #

    def on_state(self, state: MarketState) -> None:
        # medium loop (§10 Loop 2): per tick by default, or at `regime_cycle_s`
        self.nvma.observe(state)
        ctx = self._regime(state)
        self.last_context = ctx
        # fast loop (§10 Loop 3)
        bar = self.agon.observe(state)
        if bar is not None:
            self.governor.observe_bar(state.instrument, bar)   # GAP-0059
        active = self.params.get_active(ctx.regime)
        signals = self.agon.generate(
            state, ctx, active.params if active is not None else None,
            state.timestamp)
        if not signals:
            return
        portfolio = self._portfolio_fn()
        by_group: dict[str, list] = {}
        for s in signals:
            if s.group_id is not None:
                by_group.setdefault(s.group_id, []).append(s)
                continue
            order = self.governor.allocate(s, portfolio, ctx, state.timestamp)
            if order.size_units > 0:
                self.book.open(order)
        for legs in by_group.values():
            oa, ob = self.governor.allocate_group(
                tuple(legs), portfolio, ctx, state.timestamp)
            if oa.size_units > 0 and ob.size_units > 0:
                self.book.open(oa)
                self.book.open(ob)

    def _regime(self, state: MarketState):
        if self._cycle_s is None:
            return self.nvma.classify(state)
        last = self._classified_at.get(state.instrument)
        if last is None or (state.timestamp - last).total_seconds() >= self._cycle_s:
            self._classified_at[state.instrument] = state.timestamp
            return self.nvma.classify(state)
        return self.nvma.regime_store[state.instrument]

    async def run(self, feed: FeedConnector, *, drain: bool = False) -> IngestionPipeline:
        """drain=True runs the async writer to completion (the e2e persistence
        test); default enqueue-only — the bounded queue holds a test feed and
        the writer's own behaviour is phase-1-tested."""
        if not self._booted:   # GAP-0079: a real raise — assert dies under -O
            raise RuntimeError("boot() must run before the first tick (GAP-0052)")
        pipeline = IngestionPipeline(
            feed, self._factory, self._writer, self._log,
            subscribers=[self.on_state])
        if not drain:
            await pipeline.run()
            return pipeline
        task = asyncio.create_task(self._writer.run())
        await pipeline.run()
        await self._writer.stop()
        await task
        return pipeline

    # -- §10 C15 observability ------------------------------------------------ #

    def take_rate(self) -> dict:
        agon = self.agon.take_rate()
        gov = self.governor.take_rate()
        return {"signals_considered": agon["signals_considered"],
                "signals_emitted": agon["signals_emitted"],
                "orders_placed": gov["orders_placed"],
                "orders_zeroed": gov["orders_zeroed"]}

    def skip_attribution(self) -> dict:
        """§10 C15 per-gate counters as three PER-LAYER VIEWS of the loop —
        deliberately NOT a partition (GAP-0078): one vetoed tick appears both
        as its NVMA reason and as AGON's `vetoed_regime` (the reason explains
        the discard). Never sum across layers; read each layer's dict alone."""
        return {"nvma": dict(self.nvma.veto_counters),
                "agon": dict(self.agon.skips),
                "governor": dict(self.governor.skips)}


def build_paper_loop(
    tmp_path: Path,
    cfg: AcisConfig,
    factory: MarketStateFactory,
    portfolio_fn,
    *,
    account: str = "dev_paper",
    registered_at: datetime | None = None,
    tierg_shock=None,
    blackout=None,
    session_id: str = "itest7",
    logger=None,
    regime_cycle_s: float | None = None,
    position_gate=None,
) -> PaperLoop:
    """Wire the real layers from the real config (the phase-12 attach shape). A replay
    passes `regime_cycle_s` (cfg.system.regime.cycle_seconds), a ReplayEventLogger, and the
    `Backtest` as `position_gate`, so params promote only when the backtest's book is flat."""
    log = logger if logger is not None else JsonlEventLogger(
        tmp_path / "system_log.jsonl", layer="integration", session_id=session_id)
    store = MarketStateStore(tmp_path / "acis.sqlite")
    writer = AsyncBoundedWriter(store, queue_max=cfg.system.data.queue_max,
                                session_id=session_id, logger=log)
    book_holder: list[PaperBook] = []

    class _Gate:
        def open_position_count(self) -> int:
            return book_holder[0].open_position_count() if book_holder else 0

    lib = ParamLibrary(tmp_path / "params.db", cfg.system.session_boundaries,
                       cfg.system.param_stall_alert_boundaries, position_gate or _Gate(), log)
    nvma = NVMA(
        cfg=cfg.system.regime,
        session_median=factory.session_median,
        tierg_shock=tierg_shock or (lambda instrument, ts: False),
        has_params_for=lib.has_active,
    )
    engine = NVMAEngine(nvma, cfg.system.regime, log)
    prov = ProvenanceStore(tmp_path / "provenance.db",
                           cfg.system.provenance.revalidation_cadence_days, log)
    register_canonical(prov, registered_at or datetime(2026, 7, 1, tzinfo=timezone.utc))
    agon = AGON(
        cfg.system.signals,
        cfg.instruments.pair_relationships,
        prov,
        # C-DATA-4 hand-off: a warming median (None) must stay conservative —
        # 0.0 makes the scalp surge test unsatisfiable, never a fabricated rate.
        lambda inst, sess, kind: factory.session_median(inst, sess, kind) or 0.0,
        log,
    )
    signals_cfg = cfg.system.signals
    fx = cfg.instruments.calendars["fx_default"]
    enabled = {s: sp for s, sp in cfg.instruments.instruments.items() if sp.enabled}
    governor = CapitalGovernor(
        cfg=cfg.system.governor,
        guardrails=cfg.guardrails,
        rulebook=cfg.platform_rules.accounts[account],
        base_unit_usd=cfg.system.base_unit_usd,
        clusters=cfg.instruments.clusters,
        vol_targets={s: sp.vol_target_atr_frac for s, sp in enabled.items()},
        confidence_veto=cfg.system.regime.confidence_veto,
        session_boundaries=cfg.system.session_boundaries,
        week_close=fx.week_close,
        week_open=fx.week_open,
        scalp_horizon_s=(signals_cfg.momentum_scalp_horizon_bars[1]
                         * signals_cfg.momentum_scalp_bar_seconds),
        atr_period=signals_cfg.atr_period,
        blackout=blackout or (lambda instrument, now: False),
        logger=log,
    )
    loop = PaperLoop(factory, engine, lib, agon, governor, writer, store, log,
                     portfolio_fn, regime_cycle_s=regime_cycle_s)
    book_holder.append(loop.book)
    loop.provenance = prov          # the attempt registry the OOS runner counts (GAP-P12D-18)
    return loop
