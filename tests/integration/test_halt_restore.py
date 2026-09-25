"""Explicit HALTs survive a restart (ACIS-07 §7 "active halts"; GAP-0050).

Every halt, session halt and flatten crossing the upward edge is persisted before it
is forwarded, re-applied at boot through the same edge (same scope, same reason)
before the first evaluate, and cleared only by a human resume. Each "process" below
is a fresh Governor, orchestrator and Risk Monitor on the SAME risk store."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from core.data.errors import DataQualityError
from core.risk.halt_ledger import PersistentHaltSink
from core.risk.store import RiskStore, restore_on_boot
from tests.integration.test_risk_pipeline import GovernorHaltSink, PaperBook, _mk_exec
from tests.risk_fixtures import acct, build_monitor, load_cfg
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal

HUMAN = "owner-human-token"
NOON = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)   # = 08:00 EDT, the next boundary


def _process(tmp_path, store, clock=T0):
    from tests.optimizer_fixtures import CapturingLogger
    gov, glog = mk_governor()
    orch = _mk_exec(tmp_path)
    rlog = CapturingLogger()
    sink = PersistentHaltSink(GovernorHaltSink(gov, orch, PaperBook()), store, lambda: clock,
                              rlog)
    mon, _, _, _ = build_monitor(load_cfg(), sink, store=store, logger=rlog)
    return gov, glog, orch, mon, rlog, sink


def _entry(gov, at=T0, instrument="EUR_USD") -> str:
    sig = mk_signal(generated_at=at, instrument=instrument)
    return gov.allocate(sig, mk_portfolio(), mk_regime(), at).reason


def test_equity_floor_halt_survives_a_restart_until_a_human_resumes(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    gov, _, _, mon, _, _ = _process(tmp_path, store)
    mon.evaluate(acct(8_900.0), T0)                       # under the $9,000 floor
    assert _entry(gov) == "halt"

    gov2, _, orch2, mon2, rlog2, _ = _process(tmp_path, store)      # the restart
    assert _entry(gov2) == "formula"                      # a fresh Governor knows nothing...
    restore_on_boot(store, mon2, T0)                        # ...until boot, BEFORE any evaluate
    assert _entry(gov2) == "halt"
    assert orch2.frozen                                   # the flatten is re-applied too
    assert [h[:3] for h in rlog2.events("HALTS_RESTORED")[0]["data"]["halts"]] == [
        ["flatten", "all", "equity_floor"], ["halt", "all", "equity_floor"]]
    mon2.evaluate(acct(9_500.0), T0 + timedelta(minutes=1))   # recovered: still halted
    assert _entry(gov2) == "halt"

    with pytest.raises(DataQualityError):                 # no machine path unhalts
        mon2.on_human_resume("  ", T0)
    assert len(store.open_halts()) == 2
    gov2.resume(HUMAN)                                    # the human resume, as today
    mon2.on_human_resume(HUMAN, T0 + timedelta(minutes=2))
    assert _entry(gov2) == "formula"
    assert store.open_halts() == []

    gov3, _, _, mon3, _, _ = _process(tmp_path, store)    # a restart after the resume
    restore_on_boot(store, mon3, T0 + timedelta(minutes=3))
    assert _entry(gov3) == "formula"                      # nothing left to re-apply
    store.close()


def test_an_agent_halt_is_reapplied_with_its_own_scope_and_reason(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, _, _, _, _, sink = _process(tmp_path, store)
    sink.apply_halt("EUR_USD", "mcp_halt")                # the MCP control target's route
    gov2, glog2, _, mon2, _, _ = _process(tmp_path, store)
    restore_on_boot(store, mon2, T0)
    applied = glog2.events("HALT_APPLIED")
    assert [(e["data"]["scope"], e["data"]["reason"]) for e in applied] == [
        ("EUR_USD", "mcp_halt")]
    assert _entry(gov2) == "halt"
    store.close()


def test_a_session_halt_lifts_at_its_own_boundary_after_a_restart(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, _, _, _, _, sink = _process(tmp_path, store)
    sink.apply_session_halt(T0, "daily_drawdown")        # 10:00 UTC: halted until 12:00
    gov2, _, _, mon2, _, _ = _process(tmp_path, store)
    restore_on_boot(store, mon2, T0 + timedelta(minutes=4))
    assert _entry(gov2, T0 + timedelta(minutes=5)) == "drawdown_halt"
    assert _entry(gov2, NOON + timedelta(minutes=1)) == "formula"   # not a day-long halt
    store.close()


def test_restoring_writes_nothing_twice_and_keeps_distinct_reasons(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, _, _, _, _, sink = _process(tmp_path, store)
    sink.apply_halt("all", "var_cap")                     # two halts, one scope, one instant
    sink.apply_halt("all", "cluster_cap")
    assert len(store.open_halts()) == 2
    for hours in (1, 2):                                  # two restarts, each at a later clock
        _, _, _, mon, _, _ = _process(tmp_path, store, T0 + timedelta(hours=hours))
        restore_on_boot(store, mon, T0 + timedelta(hours=hours))
    assert sorted(r for _, _, r, _, _ in store.open_halts()) == ["cluster_cap", "var_cap"]
    store.close()


def test_the_ledger_is_signed_by_a_token_fingerprint_never_the_token(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, _, _, mon, _, sink = _process(tmp_path, store)
    sink.apply_halt("all", "mcp_halt")
    mon.on_human_resume(HUMAN, T0)
    store.close()
    (by,) = sqlite3.connect(tmp_path / "risk.db").execute(
        "SELECT cleared_by FROM halt_event").fetchone()
    assert by.startswith("human:") and HUMAN not in by
