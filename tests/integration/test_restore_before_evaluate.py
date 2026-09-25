"""Restoring before the first evaluate is enforced, not a convention (audit F7; ACIS-07 §7).

The audit's repro (`r7_restore_ordering_and_collision.py`, part a): an equity-floor
flatten and HALT are recorded, then a fresh process evaluates WITHOUT calling
`restore_on_boot` — both rows sit open on disk, yet the Governor sizes. A store-backed
monitor now refuses to evaluate until the restore has run."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.data.errors import DataQualityError
from core.risk.halt_ledger import PersistentHaltSink
from core.risk.store import RiskStore, restore_on_boot
from tests.integration.test_risk_pipeline import GovernorHaltSink, PaperBook, _mk_exec
from tests.optimizer_fixtures import CapturingLogger
from tests.risk_fixtures import RecordingSink, acct, build_monitor, load_cfg
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal


def _process(tmp_path, store):
    gov, _ = mk_governor()
    log = CapturingLogger()
    sink = PersistentHaltSink(GovernorHaltSink(gov, _mk_exec(tmp_path), PaperBook()), store,
                              lambda: T0, log)
    mon, _, _, _ = build_monitor(load_cfg(), sink, store=store, logger=log)
    return gov, mon


def test_a_store_backed_monitor_refuses_to_evaluate_before_its_restore(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, first = _process(tmp_path, store)
    with pytest.raises(DataQualityError):
        first.evaluate(acct(10_000.0), T0)                   # even on a fresh, empty store
    restore_on_boot(store, first, T0)
    first.evaluate(acct(8_900.0), T0)                        # floor breached, rows recorded

    gov2, second = _process(tmp_path, store)                 # the runtime forgets the call
    with pytest.raises(DataQualityError):
        second.evaluate(acct(9_500.0), T0 + timedelta(minutes=1))
    restore_on_boot(store, second, T0 + timedelta(minutes=1))
    at = T0 + timedelta(minutes=2)
    assert gov2.allocate(mk_signal(generated_at=at), mk_portfolio(), mk_regime(),
                         at).reason == "halt"                # was "formula"
    store.close()


def test_a_monitor_without_a_store_evaluates_at_once() -> None:
    mon, _, _, _ = build_monitor(load_cfg(), RecordingSink())
    assert mon.evaluate(acct(10_000.0), T0).equity == acct(10_000.0).equity
