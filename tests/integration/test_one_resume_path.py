"""Exactly one human-resume path, and it clears the halt ledger (audit F8).

The audit's repro (`r8_resume_split.py`): the equity floor halts; the human resumes
through `CapitalGovernor.resume` (the verb MCP drives); nothing cleared the ledger, so
the next restart re-applied the HALT, froze execution and flattened every position
opened since the legitimate resume. The Governor's resume now runs its injected
`resume_gate` — the risk ledger's clear — first, and lifts nothing if that fails."""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from core.risk.halt_ledger import PersistentHaltSink
from core.risk.store import RiskStore, restore_on_boot
from tests.integration.test_risk_pipeline import GovernorHaltSink, PaperBook, _mk_exec
from tests.optimizer_fixtures import CapturingLogger
from tests.risk_fixtures import acct, build_monitor, load_cfg
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal

HUMAN = "owner-human-token"


def _process(tmp_path, store, boot):
    monitor = []
    gov, _ = mk_governor(resume_gate=lambda token: monitor[0].on_human_resume(token, boot))
    orch, book = _mk_exec(tmp_path), PaperBook()
    log = CapturingLogger()
    sink = PersistentHaltSink(GovernorHaltSink(gov, orch, book), store, lambda: boot, log)
    mon, _, _, _ = build_monitor(load_cfg(), sink, store=store, logger=log, boot=boot)
    monitor.append(mon)
    return gov, orch, book, mon


def _entry(gov, at) -> str:
    return gov.allocate(mk_signal(generated_at=at), mk_portfolio(), mk_regime(), at).reason


def test_a_governor_resume_clears_the_ledger_so_a_restart_restores_nothing(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    gov, _, _, mon = _process(tmp_path, store, T0)
    mon.evaluate(acct(8_900.0), T0)                          # the equity floor halts
    gov.resume(HUMAN)                                        # the verb MCP drives
    assert _entry(gov, T0 + timedelta(minutes=1)) == "formula"
    assert store.open_halts() == []                          # was: 2 rows left open
    later = T0 + timedelta(hours=1)
    gov2, orch2, book2, _ = _process(tmp_path, store, later) # a restart after the resume
    book2.add(mk_signal())                                   # a position opened since
    assert _entry(gov2, later) == "formula"                  # not re-halted
    assert not orch2.frozen and book2.open                   # not frozen, not flattened
    store.close()


class LockedStore(RiskStore):
    locked = False

    def clear_halts(self, *a, **k):
        if self.locked:
            raise sqlite3.OperationalError("database is locked")
        return super().clear_halts(*a, **k)


def test_a_resume_whose_ledger_clear_fails_lifts_nothing(tmp_path) -> None:
    store = LockedStore(tmp_path / "risk.db")
    gov, _, _, mon = _process(tmp_path, store, T0)
    mon.evaluate(acct(8_900.0), T0)
    store.locked = True
    with pytest.raises(sqlite3.OperationalError):
        gov.resume(HUMAN)
    assert _entry(gov, T0 + timedelta(minutes=1)) == "halt"  # memory and disk still agree
    assert len(store.open_halts()) == 2
    store.close()
