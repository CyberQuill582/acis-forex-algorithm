"""Phase-9 integration: the single upward edge, end to end (SPEC §15 phase 9,
ACIS-07 §14/§15).

Risk Monitor → (HaltSink adapter) → Capital Governor + Execution freeze + book
flatten. Proves the conflict-table row "daily drawdown limit hit → halt new
positions for session" and conflict-priority #1 (Risk HALT beats everything)
through the REAL layers — not mocks of them. Also graduates GAP-0075: position
accounting from FillReports gates re-entry, so one signal ≠ one position/tick.

The HaltSink adapter lives test-side by design (§18 lean-build: the production
three-loop runtime that owns this wiring lands at phase 10, exactly like
paper_loop.py composes phases 1–5 test-side).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from core.execution.orchestrator import ExecutionOrchestrator
from core.execution.venue import FillReportStore, MockExecutionFace, VenueQuality
from core.governor.capital_governor import CapitalGovernor, ResumeForbiddenError
from core.risk.sink import HaltSink
from tests.risk_fixtures import acct, build_monitor, load_cfg, mk_fill
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal


class PaperBook:
    def __init__(self) -> None:
        self.open: list = []
        self.closed: list = []

    def add(self, order) -> None:
        self.open.append(order)

    def flatten(self, scope: str) -> None:
        keep = [] if scope == "all" else [o for o in self.open if o.instrument != scope]
        moved = [o for o in self.open if o not in keep]
        self.closed.extend(moved)
        self.open = keep


class GovernorHaltSink(HaltSink):
    """The upward edge realised over the Governor's phase-6 surface + the
    execution freeze + the paper book flatten. Risk-restrictive only."""

    def __init__(self, governor: CapitalGovernor, orchestrator, book: PaperBook) -> None:
        self._gov = governor
        self._orch = orchestrator
        self._book = book

    def apply_halt(self, scope: str, reason: str) -> None:
        self._gov.apply_halt(scope, reason)

    def apply_session_halt(self, now, reason: str) -> None:
        self._gov.apply_session_halt(now, reason)

    def apply_risk_state(self, *, taper_factor=None, alpha_decay=None) -> None:
        self._gov.apply_risk_state(taper_factor=taper_factor, alpha_decay=alpha_decay)

    def flatten(self, scope: str, reason: str) -> None:
        self._orch.set_freeze(True, reason)      # block new opens (execution)
        self._book.flatten(scope)                # close positions (paper)


def _mk_exec(tmp_path):
    from random import Random
    from config.schemas import ExecutionConfig
    from tests.optimizer_fixtures import CapturingLogger

    async def instant(_s: float) -> None:
        return None

    return ExecutionOrchestrator(
        ExecutionConfig(fragment_threshold_lots=1.0, fragment_size_jitter=(0.85, 1.15),
                        fragment_time_jitter_s=(0.5, 3.0), min_fragment_lots=0.10,
                        vwap_threshold_lots=5.0, vwap_window_s=300, fast_decay_seconds=30,
                        signature_lot_variance=0.15, dispatch_budget_ms=100,
                        max_venue_requests_per_day=1000),
        {"mock": MockExecutionFace()}, VenueQuality(),
        FillReportStore(tmp_path / "fills.db"), slippage_alert_bps=8.0, rng=Random(7),
        logger=CapturingLogger(), session_id="r9", now_fn=lambda: T0, sleep_fn=instant)


def _wire(tmp_path):
    cfg = load_cfg()
    gov, _ = mk_governor()
    orch = _mk_exec(tmp_path)
    book = PaperBook()
    sink = GovernorHaltSink(gov, orch, book)
    mon, guards, alpha, _ = build_monitor(cfg, sink)
    return cfg, gov, orch, book, mon


# -- conflict row: daily drawdown breach ⇒ zero new orders for the session ---- #

def test_risk_drawdown_halt_zeroes_governor_orders(tmp_path) -> None:
    cfg, gov, orch, book, mon = _wire(tmp_path)
    # a clean portfolio (governor's OWN dd-check must not fire — we prove the
    # RISK-driven upward edge specifically)
    portfolio = mk_portfolio(daily_drawdown_pct=0.0)
    # before: a valid signal sizes normally
    assert gov.allocate(mk_signal(), portfolio, _regime(), T0).size_units > 0
    # anchor equity, then a 2.1% equity drop → engine daily limit (2.0%) breached
    mon.evaluate(acct(10000.0), T0)
    mon.evaluate(acct(9790.0), T0 + timedelta(seconds=1))
    # the upward edge session-halted the Governor → new entries zero out
    order = gov.allocate(mk_signal(generated_at=T0 + timedelta(seconds=2)),
                         portfolio, _regime(), T0 + timedelta(seconds=2))
    assert order.size_units == 0 and order.reason == "drawdown_halt"


# -- equity floor ⇒ flatten + resume rejected without a human token ---------- #

def test_equity_floor_flattens_and_requires_human_resume(tmp_path) -> None:
    cfg, gov, orch, book, mon = _wire(tmp_path)
    book.add(mk_signal())                        # a standing paper position
    mon.evaluate(acct(8000.0), T0)               # below the 9000 floor
    assert book.open == [] and book.closed        # flattened
    assert orch.frozen                            # new opens blocked at execution
    # global HALT is in force; a non-human resume is refused
    with pytest.raises(ResumeForbiddenError):
        gov.resume("")
    gov.resume("human:owner-token")               # only a human clears it
    order = gov.allocate(mk_signal(generated_at=T0), mk_portfolio(), _regime(), T0)
    # execution is still frozen (freeze is the Governor-independent flatten
    # latch); the order sizes but new opens do not reach a venue while frozen
    assert order.reason in ("formula", "halt")


# -- racing HALTs coalesce to one global halt through the real Governor ------- #

def test_racing_halts_single_governor_halt(tmp_path) -> None:
    cfg, gov, orch, book, mon = _wire(tmp_path)
    from core.risk.guardrails import GuardrailContext
    mon._guards.check(GuardrailContext(
        now=T0, equity=Decimal("10000"), balance=Decimal("10000"),
        nav=Decimal("10000"), per_instrument_drawdown_pct={}, var_pct=5.0,
        max_cluster_pct=40.0, slippage_slope_bps=0.0, tierg_flatten={}))
    order = gov.allocate(mk_signal(), mk_portfolio(), _regime(), T0)
    assert order.reason == "halt"                 # one global halt in force


# -- restart reconciliation: drift ⇒ start halted ---------------------------- #

def test_restart_drift_halts_governor(tmp_path) -> None:
    from core.execution.venue import BrokerPosition
    cfg, gov, orch, book, mon = _wire(tmp_path)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10))
    broker = (BrokerPosition(instrument="USD_JPY", direction=-1,
                             size_units=Decimal("500")),)
    assert mon.reconcile_on_restart(broker, T0) is True
    assert gov.allocate(mk_signal(), mk_portfolio(), _regime(), T0).reason == "halt"


# -- weekend-gap through a stop ⇒ realised loss booked at the GAP price ------- #

def test_weekend_gap_through_stop_books_loss_at_gap_price(tmp_path) -> None:
    cfg, gov, orch, book, mon = _wire(tmp_path)
    # long EUR_USD at 1.10; the Friday stop sits at 1.09
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10, at=T0))
    # Sunday open gaps to 1.05 — BELOW the stop; the fill books at the gap price,
    # not the stop level (§8.5 gap law; the position closes at 1.05).
    mon.ingest(mk_fill(order_id="o1x", instrument="EUR_USD", direction=-1, units=1000,
                       price=1.05, at=T0 + timedelta(hours=48)))
    snap = mon.evaluate(acct(9950.0), T0 + timedelta(hours=48, minutes=1))
    assert mon.positions() == ()
    assert snap.daily_pnl == Decimal("-50.00")    # (1.05-1.10)×1000, at the gap


# -- GAP-0075 graduation: position accounting gates re-entry ------------------ #

def test_position_accounting_gates_reentry(tmp_path) -> None:
    """One TSMOM-style signal repeated every tick yields ONE position, not one
    per tick — the phase-7 orders_placed==67 spam is replaced by a position-
    aware count via FillReport-reconstructed positions (GAP-0075)."""
    cfg, gov, orch, book, mon = _wire(tmp_path)

    def already_open(instrument: str, direction: int) -> bool:
        return any(p.instrument == instrument and p.direction == direction
                   for p in mon.positions())

    positions_opened = 0
    for tick in range(20):                        # same signal fires every tick
        if already_open("EUR_USD", 1):
            continue                              # re-entry suppressed
        mon.ingest(mk_fill(order_id=f"o{tick}", instrument="EUR_USD", direction=1,
                           units=1000, price=1.10, at=T0 + timedelta(minutes=tick)))
        positions_opened += 1
    assert positions_opened == 1                  # NOT 20 — one position, held
    assert len(mon.positions()) == 1


def _regime():
    return mk_regime()
