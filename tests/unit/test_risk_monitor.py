"""Risk Monitor: ingest/metrics/snapshot/reconcile (ACIS-07 §13/§14,
C-RSK-5/7/9/11)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from core.data.errors import DataQualityError
from core.execution.venue import BrokerPosition, FillStatus
from core.risk.sink import HaltSink
from core.risk.store import RiskStore
from tests.risk_fixtures import (RecordingSink, T0, acct, build_monitor, load_cfg,
                                 mk_fill, mk_trade)


# -- position/trade accounting from FillReports (F17 Decimal) ---------------- #

def test_open_then_close_books_a_trade_with_pnl() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1,
                       units=1000, price=1.10))
    assert len(mon.positions()) == 1
    # close at a higher price → positive realised PnL of (1.11-1.10)*1000 = 10
    mon.ingest(mk_fill(order_id="o2", instrument="EUR_USD", direction=-1,
                       units=1000, price=1.11, at=T0 + timedelta(minutes=10)))
    assert mon.positions() == ()
    snap = mon.evaluate(acct(10010.0), T0 + timedelta(minutes=11))
    assert snap.daily_pnl == Decimal("10.00")


def test_rejected_fill_is_not_a_position() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10, status=FillStatus.REJECTED))
    assert mon.positions() == ()          # a rejection is a report, never a fill


def test_partial_then_more_averages_entry() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1,
                       units=1000, price=1.10))
    mon.ingest(mk_fill(order_id="o1b", instrument="EUR_USD", direction=1,
                       units=1000, price=1.20))
    pos = mon.positions()[0]
    assert pos.size_units == Decimal("2000")
    assert abs(pos.avg_entry_price - 1.15) < 1e-9


# -- C-RSK-11: heartbeat open_positions is broker-reconciled truth ----------- #

def test_heartbeat_reflects_open_position_count(tmp_path) -> None:
    cfg, sink = load_cfg(), RecordingSink()
    risk_cfg = cfg.system.risk.model_copy(update={"heartbeat_path": str(tmp_path / "hb.json")})
    cfg2 = cfg.model_copy(update={"system": cfg.system.model_copy(update={"risk": risk_cfg})})
    mon, _, _, _ = build_monitor(cfg2, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10))
    mon.write_heartbeat(T0, "paper", 3)
    import json
    beat = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert beat["open_positions"] == 1 and beat["fast_loop_seq"] == 3


# -- alpha-decay drives the explicit upward-edge set/clear (GAP-0050/C-RSK-9) - #

def test_alpha_decay_sets_and_clears_explicitly() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, alpha, _ = build_monitor(cfg, sink)
    # arm: strong baseline (150) + weak recent (50) → flag → apply_risk_state(True)
    for i in range(150):
        mon._trades.append(mk_trade(12.0 if i % 2 else 8.0))
    for i in range(50):
        mon._trades.append(mk_trade(1.0 if i % 2 else -1.0))
    mon.evaluate(acct(10000.0), T0)
    assert (None, True) in sink.risk_states           # explicit set (not a taper)
    assert alpha.armed
    # a taper-only re-evaluate (still decayed) must NOT send alpha_decay=False
    sink.risk_states.clear()
    mon.evaluate(acct(10000.0), T0 + timedelta(minutes=1))
    assert all(alpha is not False for _, alpha in sink.risk_states)


def test_a_human_resume_clears_the_throttle_and_only_post_resume_decay_re_arms_it() -> None:
    """GAP-P12D-145 ("Human resume clears it", "Fresh evidence only"): the trades that armed the
    throttle cannot re-arm it after a resume; 30 decayed trades closed after it do."""
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, alpha, log = build_monitor(cfg, sink)
    for i in range(150):
        mon._trades.append(mk_trade(12.0 if i % 2 else 8.0))
    for i in range(50):
        mon._trades.append(mk_trade(1.0 if i % 2 else -1.0))
    mon.evaluate(acct(10000.0), T0)
    assert alpha.armed
    with pytest.raises(DataQualityError):
        mon.on_human_resume("  ", T0)                     # no token: nothing clears
    assert alpha.armed
    sink.risk_states.clear()
    mon.on_human_resume("human", T0)
    assert not alpha.armed and sink.risk_states == [(None, False)]
    assert any(e["event_type"] == "ALPHA_DECAY_CLEARED_BY_HUMAN" for e in log.events())
    snap = mon.evaluate(acct(10000.0), T0 + timedelta(minutes=1))  # same trades: no re-arm
    assert not alpha.armed and snap.alpha_decay_state == "inactive_warming"
    for i in range(29):
        mon._trades.append(mk_trade(1.0 if i % 2 else -1.0))
    mon.evaluate(acct(10000.0), T0 + timedelta(minutes=2))
    assert not alpha.armed                                # 29 fresh trades: still warming
    mon._trades.append(mk_trade(-1.0))
    mon.evaluate(acct(10000.0), T0 + timedelta(minutes=3))
    assert alpha.armed and sink.risk_states[-1] == (None, True)   # decay persists: re-armed


def test_a_human_resume_leaves_an_unarmed_throttle_alone() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, alpha, log = build_monitor(cfg, sink)
    mon.on_human_resume("human", T0)
    assert not alpha.armed and sink.risk_states == []
    assert not any(e["event_type"] == "ALPHA_DECAY_CLEARED_BY_HUMAN" for e in log.events())


def test_snapshot_alpha_state_is_first_class() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    snap = mon.evaluate(acct(10000.0), T0)            # no trades → warming
    assert snap.alpha_decay_state == "inactive_warming"
    assert snap.alpha_decay_flag is False


# -- C-RSK-5: restart reconciliation, broker authoritative ------------------- #

def test_restart_no_drift_does_not_halt() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10))
    broker = (BrokerPosition(instrument="EUR_USD", direction=1, size_units=Decimal("1000")),)
    assert mon.reconcile_on_restart(broker, T0) is False
    assert sink.halts == []


def test_restart_drift_starts_halted() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="o1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10))
    # broker shows a DIFFERENT position → drift → start halted, adopt broker truth
    broker = (BrokerPosition(instrument="USD_JPY", direction=-1, size_units=Decimal("500")),)
    assert mon.reconcile_on_restart(broker, T0) is True
    assert ("all", "restart_drift") in sink.halts
    assert {p.instrument for p in mon.positions()} == {"USD_JPY"}


def test_restart_restores_persisted_throttle_before_evaluate() -> None:
    # GAP-0050: a restart is never a relaxation — a persisted armed throttle is
    # restored, and warming afterward does not clear it. GAP-P9I-05: the restore
    # must RE-PUSH the throttle to the (fresh) Governor, not just set the flag.
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, alpha, _ = build_monitor(cfg, sink)
    mon.restore_restrictive_state(alpha_armed=True)
    assert alpha.armed
    assert (None, True) in sink.risk_states          # re-pushed over the edge
    mon.evaluate(acct(10000.0), T0)                   # no trades → warming
    # the throttle stays armed; no explicit clear was sent
    assert alpha.armed
    assert (None, False) not in sink.risk_states


def test_quote_ccy_pnl_converted_to_usd_for_enabled_universe() -> None:
    # GAP-P9E-04: USD_JPY books PnL in JPY; the per-instrument drawdown must be
    # in USD, not treat JPY as USD (which reported 5% on a ~$4.55 / 0.0455% loss).
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="j1", instrument="USD_JPY", direction=1, units=1000,
                       price=110.00))
    # mark down to 109.50: loss = 500 JPY ≈ $4.566 → 0.0455% of $10k NAV
    dd = mon._per_instrument_drawdown({"USD_JPY": 109.50}, Decimal("10000"))
    assert dd["USD_JPY"] == pytest.approx(0.04566, abs=1e-4)   # NOT 5.0


def test_usd_quoted_pnl_unchanged_by_conversion() -> None:
    # EUR_USD is USD-quoted → factor 1.0; the identity still holds exactly.
    cfg, sink = load_cfg(), RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink)
    mon.ingest(mk_fill(order_id="e1", instrument="EUR_USD", direction=1, units=1000,
                       price=1.10))
    dd = mon._per_instrument_drawdown({"EUR_USD": 1.095}, Decimal("10000"))
    assert dd["EUR_USD"] == pytest.approx(0.05, abs=1e-6)      # (1.10-1.095)*1000=$5


# -- C-RSK-7: the upward edge cannot resume or raise size -------------------- #

def test_halt_sink_has_no_resume_or_size_raising_surface() -> None:
    # A resume is a human action on the Governor/MCP layer, never reachable
    # from Risk. The sink's schema is risk-restrictive only.
    forbidden = {"resume", "set_size", "raise_limit", "increase", "unhalt"}
    assert forbidden.isdisjoint(dir(HaltSink))


# -- store round-trips the snapshot + restrictive state ---------------------- #

def test_store_persists_snapshot_and_restrictive_state(tmp_path) -> None:
    cfg, sink = load_cfg(), RecordingSink()
    store = RiskStore(tmp_path / "risk.db")
    mon, _, _, _ = build_monitor(cfg, sink, store=store, boot=T0)
    mon.evaluate(acct(10000.0), T0)
    assert store.snapshot_count() == 1
    store.save_restrictive_state(alpha_armed=True, taper_factor=0.5)
    assert store.load_restrictive_state() == {"alpha_armed": True, "taper_factor": 0.5}
    store.close()
