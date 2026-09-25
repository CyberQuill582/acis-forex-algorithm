"""Shared fixtures for the Risk Monitor tests (ACIS-07 §14)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config.schemas import GuardrailLimits, RiskConfig, load_config
from core.execution.venue import BrokerAccount, FillReport, FillStatus, slippage_bps
from core.risk.alpha_decay import AlphaDecayDetector
from core.risk.guardrails import Guardrails, build_drawdown_series
from core.risk.monitor import RiskMonitor
from core.risk.risk_types import Trade
from core.risk.sink import HaltSink
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
T0 = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)


class RecordingSink(HaltSink):
    def __init__(self) -> None:
        self.halts: list[tuple[str, str]] = []
        self.session_halts: list[str] = []
        self.risk_states: list[tuple[float | None, bool | None]] = []
        self.flattens: list[tuple[str, str]] = []

    def apply_halt(self, scope: str, reason: str) -> None:
        self.halts.append((scope, reason))

    def apply_session_halt(self, now, reason: str) -> None:
        self.session_halts.append(reason)

    def apply_risk_state(self, *, taper_factor=None, alpha_decay=None) -> None:
        self.risk_states.append((taper_factor, alpha_decay))

    def flatten(self, scope: str, reason: str) -> None:
        self.flattens.append((scope, reason))


def load_cfg():
    return load_config(CONFIG_DIR)


def mk_alpha(cfg: RiskConfig) -> AlphaDecayDetector:
    return AlphaDecayDetector(
        recent_window=cfg.alpha_decay_recent_window,
        min_trades=cfg.alpha_decay_min_trades,
        baseline_min_trades=cfg.alpha_decay_baseline_min_trades,
        sharpe_mult=0.5,
        recovery_trades=cfg.alpha_decay_recovery_trades,
        recovery_mult=cfg.alpha_decay_recovery_mult)


def mk_trade(pnl: float, *, units: float = 1000.0, entry: float = 1.0,
             at: datetime = T0) -> Trade:
    direction = 1
    exit_price = entry + pnl / units
    if exit_price <= 0:
        exit_price = 0.0001
    return Trade(
        instrument="EUR_USD", direction=direction, units=Decimal(str(units)),
        entry_price=entry, exit_price=exit_price, opened_at=at,
        closed_at=at + timedelta(minutes=5), pnl=Decimal(str(pnl)),
        param_set_id="ps-1")


def acct(equity: float, balance: float | None = None) -> BrokerAccount:
    return BrokerAccount(equity=Decimal(str(equity)),
                         balance=Decimal(str(balance if balance is not None else equity)),
                         margin_used=Decimal("0"))


def mk_fill(*, order_id: str, instrument: str, direction: int, units: float,
            price: float, requested: float | None = None,
            at: datetime = T0, status: FillStatus = FillStatus.FILLED,
            session_id: str = "s1") -> FillReport:
    requested = requested if requested is not None else price
    rejected = status in (FillStatus.REJECTED, FillStatus.CANCELLED)
    filled = Decimal("0") if rejected else Decimal(str(units))
    fill_price = 0.0 if rejected else price
    slip = 0.0 if rejected else slippage_bps(requested, price, direction)
    return FillReport(
        fill_id=f"{order_id}:{at.isoformat()}", order_id=order_id,
        fragment_id=f"{order_id}:frag", instrument=instrument, direction=direction,
        requested_price=requested, fill_price=fill_price, filled_units=filled,
        slippage_bps=slip, fill_time=at, venue="mock", status=status,
        remaining_units=Decimal(str(units)) - filled, session_id=session_id)


def build_monitor(cfg, sink, *, account: str = "dev_paper",
                  taper_start: float | None = None,
                  entry_halt: float | None = None, logger=None, store=None):
    from tests.optimizer_fixtures import CapturingLogger
    log = logger or CapturingLogger()
    rb = cfg.platform_rules.accounts[account]
    from config.account_doctrine import compose
    doctrine = compose(cfg.guardrails, rb)
    series = build_drawdown_series(cfg.guardrails, rb.drawdown_rules, account,
                                   initial_capital=rb.initial_capital)
    g = Guardrails(
        cfg.guardrails, cfg.system.risk, series, sink, log,
        taper_start=taper_start if taper_start is not None else doctrine.taper_start_fraction,
        entry_halt=entry_halt if entry_halt is not None else doctrine.entry_halt_fraction,
        session_boundaries=cfg.system.session_boundaries)
    alpha = mk_alpha(cfg.system.risk)
    mon = RiskMonitor(cfg.system.risk, cfg.guardrails, g, alpha, sink,
                      cfg.instruments.clusters, "s1", log, store=store)
    return mon, g, alpha, log
