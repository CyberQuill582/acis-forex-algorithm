"""The guard acts first; recording never gates it (audit F0 / X2; ACIS-07 §7).

Regression tests from the audits' repros (`r6_store_failure.py`, `r2_store_failure.py`):
the risk store raises `database is locked` at the moment equity falls under the $9,000
floor. Before the fix the halt-ledger write ran BEFORE the halt was forwarded and the
breaker's latch was set BEFORE the edge call, so one failed write dropped the equity-floor
flatten and HALT for the life of the process. Now the Governor and execution act first,
a failed write is retried and alarmed and kept pending, and every latch waits for the edge.
"""

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


class LockedStore(RiskStore):
    """A risk store whose chosen write raises `database is locked` while `locked`."""

    def __init__(self, path, fail: str) -> None:
        super().__init__(path)
        self.fail = fail
        self.locked = False

    def _gate(self, name: str) -> None:
        if self.locked and name == self.fail:
            raise sqlite3.OperationalError("database is locked")

    def record_halt(self, *a, **k):
        self._gate("record_halt")
        return super().record_halt(*a, **k)

    def open_halts(self):
        self._gate("open_halts")
        return super().open_halts()

    def write_snapshot(self, *a, **k):
        self._gate("write_snapshot")
        return super().write_snapshot(*a, **k)

    def save_restrictive_state(self, *a, **k):
        self._gate("save_restrictive_state")
        return super().save_restrictive_state(*a, **k)


def _process(tmp_path, store, inner_cls=GovernorHaltSink):
    gov, _ = mk_governor()
    orch = _mk_exec(tmp_path)
    log = CapturingLogger()
    sink = PersistentHaltSink(inner_cls(gov, orch, PaperBook()), store, lambda: T0, log)
    mon, _, _, _ = build_monitor(load_cfg(), sink, store=store, logger=log)
    return gov, orch, mon, log


def _entry(gov, at) -> str:
    return gov.allocate(mk_signal(generated_at=at), mk_portfolio(), mk_regime(), at).reason


@pytest.mark.parametrize("write_point", ["record_halt", "open_halts", "write_snapshot",
                                         "save_restrictive_state"])
def test_the_equity_breaker_holds_when_any_store_write_fails(tmp_path, write_point) -> None:
    store = LockedStore(tmp_path / "risk.db", write_point)
    gov, orch, mon, log = _process(tmp_path, store)
    mon.evaluate(acct(9_050.0), T0)
    store.locked = True
    mon.evaluate(acct(8_990.0), T0 + timedelta(seconds=1))   # under the floor; no raise
    assert _entry(gov, T0 + timedelta(seconds=1)) == "halt"  # the HALT is in force
    assert orch.frozen                                       # and the flatten froze opens
    alarms = [e["event_type"] for e in log.events()
              if e["event_type"] in ("HALT_LEDGER_WRITE_FAILED", "RISK_STORE_WRITE_FAILED")]
    assert alarms                                            # the failure is loud
    store.locked = False                                     # the store recovers ...
    mon.evaluate(acct(8_990.0), T0 + timedelta(seconds=2))   # ... and the next check flushes
    assert {(k, s, r) for k, s, r, _ in store.open_halts()} == {
        ("flatten", "all", "equity_floor"), ("halt", "all", "equity_floor")}
    gov2, orch2, mon2, _ = _process(tmp_path, store)         # so a restart still restores it
    restore_on_boot(store, mon2)
    assert _entry(gov2, T0 + timedelta(minutes=1)) == "halt" and orch2.frozen
    store.close()


class FlakyEdge(GovernorHaltSink):
    """The Governor-side adapter fails its first flatten (e.g. execution briefly down)."""
    failed = False

    def flatten(self, scope: str, reason: str) -> None:
        if not FlakyEdge.failed:
            FlakyEdge.failed = True
            raise ConnectionError("execution unreachable")
        super().flatten(scope, reason)


def test_an_edge_call_that_fails_is_reissued_not_latched(tmp_path) -> None:
    FlakyEdge.failed = False
    store = RiskStore(tmp_path / "risk.db")
    gov, orch, mon, _ = _process(tmp_path, store, FlakyEdge)
    with pytest.raises(ConnectionError):
        mon.evaluate(acct(8_990.0), T0)                      # the edge itself failed
    mon.evaluate(acct(8_990.0), T0 + timedelta(seconds=1))   # so the breaker fires again
    assert _entry(gov, T0 + timedelta(seconds=1)) == "halt" and orch.frozen
    store.close()
