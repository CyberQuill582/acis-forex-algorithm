"""Build the runtime from config (master §10): every layer, once, in dependency order.

Invariants:
  * Every part is the production class, built from the validated config; nothing is mocked
    except the paper venue, which is the paper mode's venue by law (master §7.5).
  * One edge: Risk holds `PersistentHaltSink(RuntimeHaltSink)`, and the MCP control target
    routes through the same edge, so every halt is recorded and survives a restart.
  * Paper and practice trade one venue minimum lot (ACIS-05 v1.6, GAP-P12D-129): the Governor
    is handed the attached venue's minimum per instrument, or the paper descriptor's.
  * The ParamLibrary's flat gate counts Risk's positions AND the executor's in-flight work, so
    no promotion slips in between a submit and its fill (C2).
  * Stores live under `root/data/runtime`, logs under `root/logs`: one tree per deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from random import SystemRandom
from typing import Callable

from config.account_doctrine import compose, guardrail_hash, rulebook_hash
from config.schemas import AcisConfig
from core.data.asset_classes import build_calendars
from core.data.feeds import FeedConnector
from core.data.ingestion import IngestionPipeline
from core.data.jsonl_logging import JsonlEventLogger
from core.data.normaliser import FactoryConfig, MarketStateFactory
from core.data.store import AsyncBoundedWriter, MarketStateStore
from core.execution.mock_face import MockExecutionFace
from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import UNITS_PER_LOT, FillReportStore
from core.execution.venue_quality import VenueQuality
from core.governor.capital_governor import CapitalGovernor
from core.optimizer.costs import CostModel
from core.optimizer.param_library import ParamLibrary
from core.regime.nvma import NVMA, NVMAEngine
from core.risk.alpha_decay import AlphaDecayDetector
from core.risk.drawdown_series import build_drawdown_series
from core.risk.guardrails import Guardrails
from core.risk.halt_ledger import PersistentHaltSink
from core.risk.monitor import RiskMonitor
from core.risk.store import RiskStore
from core.runtime.boundaries import BoundaryClock
from core.runtime.engine import Runtime
from core.runtime.executor import Executor
from core.runtime.halt_edge import RuntimeControl, RuntimeHaltSink
from core.runtime.paper import PaperVenue
from core.runtime.venue_link import VenueLink
from core.signals.agon import AGON
from core.signals.canonical import register_canonical
from core.signals.provenance import ProvenanceStore
from monitoring.mode import ModeController


@dataclass
class Parts:
    """Everything the loops touch (engine.py reads these names)."""
    cfg: AcisConfig
    log: JsonlEventLogger
    now_fn: Callable[[], datetime]
    pipeline: IngestionPipeline
    writer: AsyncBoundedWriter
    nvma: NVMAEngine
    params: ParamLibrary
    agon: AGON
    governor: CapitalGovernor
    risk: RiskMonitor
    risk_store: RiskStore
    edge: PersistentHaltSink
    control: RuntimeControl
    mode: ModeController
    paper: PaperVenue
    paper_orch: ExecutionOrchestrator
    venue: VenueLink | None
    executor: Executor
    boundaries: BoundaryClock
    clusters: dict

    @property
    def max_hold_s(self) -> float: return self.cfg.system.runtime.max_hold_s
    @property
    def paper_nav(self) -> Decimal: return Decimal(str(self.cfg.system.runtime.paper_nav_usd))
    @property
    def regime_cycle_s(self) -> float: return self.cfg.system.regime.cycle_seconds
    @property
    def decision_budget_ms(self) -> float: return self.cfg.system.signals.fast_loop_decision_budget_ms
    @property
    def eval_cadence_s(self) -> float: return self.cfg.system.risk.eval_cadence_s

    def account_max_age_s(self) -> float:
        """Older than this, the portfolio is stale and the Governor zeroes entries."""
        if self.mode.mode == "practice" and self.venue is not None:
            return 2.0 * self.cfg.system.venue.equity_poll_s
        return 3.0 * self.eval_cadence_s

    def route_to(self) -> ExecutionOrchestrator | None:
        if self.mode.mode == "paper":
            return self.paper_orch
        if self.mode.mode == "practice" and self.venue is not None and self.venue.practice_eligible:
            return self.venue.orchestrator
        return None                              # backtest, live, or no eligible venue

    def tasks(self, rt: Runtime):
        yield "executor", self.executor.run()
        yield "writer", self.writer.run()
        yield "risk", rt.risk_loop()
        yield "paper_fills", rt.venue_fills(self.paper_orch, self.paper.name)
        if self.venue is not None:
            yield "venue_fills", rt.venue_fills(self.venue.orchestrator, self.venue.face.name)
            yield "account_poll", self.venue.poll()
            yield "reconcile", self.venue.reconcile(self.risk, self.executor)
            if self.venue.reconnector is not None:
                yield "reconnect", self.venue.reconnector.run()


def build(cfg: AcisConfig, *, root: Path, session_id: str, feed: FeedConnector,
          venue: VenueLink | None = None, now_fn=lambda: datetime.now(timezone.utc)) -> Runtime:
    sysc, rb_key = cfg.system, cfg.system.active_account
    rulebook = cfg.platform_rules.accounts[rb_key]
    data, logs = root / "data" / "runtime", root / "logs"
    data.mkdir(parents=True, exist_ok=True)

    def logger(stream: str, layer: str) -> JsonlEventLogger:
        return JsonlEventLogger(logs / f"{stream}.jsonl", layer=layer, session_id=session_id)

    log = logger("system_log", "runtime")
    enabled = {s: sp for s, sp in cfg.instruments.instruments.items() if sp.enabled}
    calendars = build_calendars(cfg.instruments.calendars)
    d = sysc.data
    factory = MarketStateFactory(
        cfg=FactoryConfig(stale_threshold_ms=d.stale_threshold_ms,
                          clock_skew_tolerance_ms=d.clock_skew_tolerance_ms,
                          reorder_tolerance_ms=d.reorder_tolerance_ms,
                          tick_velocity_window_s=d.tick_velocity_window_s,
                          session_median_window=d.session_median_window,
                          session_median_min_samples=d.session_median_min_samples),
        calendars_by_instrument={s: calendars[sp.calendar] for s, sp in enabled.items()},
        max_plausible_spread={s: sp.max_plausible_spread for s, sp in enabled.items()},
        macro_imminent=lambda instrument, ts: False)            # no live calendar yet (ledger)
    writer = AsyncBoundedWriter(MarketStateStore(data / "market_state.sqlite"),
                                queue_max=d.queue_max, session_id=session_id, logger=log)
    held: list = []                              # the gate reads Risk + the executor, built below

    class _FlatGate:
        def open_position_count(self) -> int:
            return len(held[0].positions()) + len(held[1].busy) if held else 1

    params = ParamLibrary(data / "params.db", sysc.session_boundaries,
                          sysc.param_stall_alert_boundaries, _FlatGate(), logger("param_log", "optimizer"))
    nvma = NVMAEngine(NVMA(cfg=sysc.regime, session_median=factory.session_median,
                           tierg_shock=lambda instrument, ts: False, has_params_for=params.has_active),
                      sysc.regime, logger("regime_log", "regime"))
    signal_log = logger("signal_log", "signals")
    prov = ProvenanceStore(data / "provenance.db", sysc.provenance.revalidation_cadence_days, signal_log)
    register_canonical(prov, datetime(2026, 7, 1, tzinfo=timezone.utc))
    agon = AGON(sysc.signals, cfg.instruments.pair_relationships, prov,
                lambda inst, sess, kind: factory.session_median(inst, sess, kind) or 0.0, signal_log)
    paper_descriptor = venue.attached.descriptor if venue is not None else MockExecutionFace().descriptor

    def min_lot(instrument: str) -> Decimal | None:           # ACIS-05 v1.6
        if venue is not None:
            return venue.min_units(instrument)
        return Decimal(str(paper_descriptor.min_lot)) * UNITS_PER_LOT

    fx = cfg.instruments.calendars["fx_default"]
    governor = CapitalGovernor(
        cfg=sysc.governor, guardrails=cfg.guardrails, rulebook=rulebook, base_unit_usd=sysc.base_unit_usd,
        clusters=cfg.instruments.clusters,
        vol_targets={s: sp.vol_target_atr_frac for s, sp in enabled.items()},
        confidence_veto=sysc.regime.confidence_veto, session_boundaries=sysc.session_boundaries,
        week_close=fx.week_close, week_open=fx.week_open, holidays=fx.holidays,
        scalp_horizon_s=sysc.signals.momentum_scalp_horizon_bars[1] * sysc.signals.momentum_scalp_bar_seconds,
        atr_period=sysc.signals.atr_period, blackout=lambda instrument, now: False,
        logger=logger("governor_log", "governor"),
        resume_gate=lambda token: held[0].on_human_resume(token, now_fn()), fixed_units=min_lot)
    costs = {s: CostModel(commission_per_side=sp.costs.commission_per_side,
                          slippage_per_side=sp.costs.slippage_per_side) for s, sp in enabled.items()}
    paper = PaperVenue(paper_descriptor, costs, Decimal(str(sysc.runtime.paper_nav_usd)))
    trade_log = logger("trade_log", "execution")
    paper_orch = ExecutionOrchestrator(
        sysc.execution, {paper.name: paper}, VenueQuality(), FillReportStore(data / "paper_fills.db"),
        slippage_alert_bps=cfg.guardrails.slippage_alert_bps, rng=SystemRandom(), logger=trade_log,
        session_id=session_id, now_fn=now_fn)
    orchestrators = [paper_orch] + ([venue.orchestrator] if venue is not None else [])
    risk_log = logger("risk_log", "risk")
    risk_store = RiskStore(data / "risk.db")
    edge = PersistentHaltSink(
        RuntimeHaltSink(governor, orchestrators, lambda scope, why: held[1].submit_flatten(scope, why)),
        risk_store, now_fn, risk_log)
    doctrine = compose(cfg.guardrails, rulebook)
    guards = Guardrails(cfg.guardrails, sysc.risk,
                        build_drawdown_series(cfg.guardrails, rulebook.drawdown_rules, rb_key,
                                              initial_capital=rulebook.initial_capital),
                        edge, risk_log, taper_start=doctrine.taper_start_fraction,
                        entry_halt=doctrine.entry_halt_fraction,
                        session_boundaries=sysc.session_boundaries)
    beat = Path(sysc.risk.heartbeat_path)          # the watchdog reads it under the same root
    r = sysc.risk.model_copy(update={"heartbeat_path": str(beat if beat.is_absolute() else root / beat)})
    alpha = AlphaDecayDetector(recent_window=r.alpha_decay_recent_window, min_trades=r.alpha_decay_min_trades,
                               baseline_min_trades=r.alpha_decay_baseline_min_trades,
                               sharpe_mult=cfg.guardrails.alpha_decay_sharpe_mult,
                               recovery_trades=r.alpha_decay_recovery_trades,
                               recovery_mult=r.alpha_decay_recovery_mult)
    risk = RiskMonitor(r, cfg.guardrails, guards, alpha, edge, cfg.instruments.clusters,
                       session_id, risk_log, store=risk_store)
    runtime_ref: list[Runtime] = []
    executor = Executor(route_to=lambda: parts.route_to(), risk=risk,
                        on_fill=lambda: runtime_ref[0].evaluate(), halt=edge.apply_halt,
                        mark_of=lambda i: runtime_ref[0].marks.get(i), now_fn=now_fn, logger=trade_log)
    held.extend([risk, executor])
    mode = ModeController(initial_mode="paper", guardrail_hash=guardrail_hash(cfg.guardrails),
                          rulebook_hash=rulebook_hash(rulebook), validation_record_ok=lambda: False,
                          logger=log, practice_eligible=lambda: venue is not None and venue.practice_eligible)
    parts = Parts(cfg=cfg, log=log, now_fn=now_fn, writer=writer, nvma=nvma, params=params, agon=agon,
                  governor=governor, risk=risk, risk_store=risk_store, edge=edge,
                  control=RuntimeControl(edge, governor, orchestrators), mode=mode, paper=paper,
                  paper_orch=paper_orch, venue=venue, executor=executor,
                  boundaries=BoundaryClock(sysc.session_boundaries), clusters=cfg.instruments.clusters,
                  pipeline=None)
    runtime = Runtime(parts)
    runtime_ref.append(runtime)
    parts.pipeline = IngestionPipeline(feed, factory, writer, log, subscribers=[runtime.on_state],
                                       data_logger=logger("data_log", "data"),
                                       log_sample_rate=d.log_sample_rate)
    return runtime
