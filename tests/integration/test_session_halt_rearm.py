"""The daily-drawdown session halt fires every day, not once per process (audits F2, F1,
X1; master §8: "halt all new positions for session").

Regression tests from the audits' repros (`r2b_inprocess_latch.py`, `r2_stale_session_latch.py`,
`r1_stale_session_latch.py`, `r1b_inprocess.py`). The Risk latch that stops a session halt
being re-issued within its session used to live for the whole process (F2, pre-existing),
and after a restart a stale session row re-set it until a human resume (F1/X1). Now the
latch lapses at the session boundary, exactly when the Governor's session halt does, and
a session row whose boundary passed while the engine was down is closed as expired.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from core.risk.halt_ledger import PersistentHaltSink
from core.risk.store import RiskStore, restore_on_boot
from tests.integration.test_risk_pipeline import GovernorHaltSink, PaperBook, _mk_exec
from tests.optimizer_fixtures import CapturingLogger
from tests.risk_fixtures import acct, build_monitor, load_cfg
from tests.signals_fixtures import mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio
from tests.unit.test_signal_types import mk_signal

D1 = datetime(2026, 7, 14, 14, 0, tzinfo=timezone.utc)   # Tue; the session ends 21:00 UTC
MIN = timedelta(minutes=1)


def _process(tmp_path, store=None, clock=D1):
    gov, _ = mk_governor()
    inner = GovernorHaltSink(gov, _mk_exec(tmp_path), PaperBook())
    log = CapturingLogger()
    sink = inner if store is None else PersistentHaltSink(inner, store, lambda: clock, log)
    mon, _, _, _ = build_monitor(load_cfg(), sink, store=store, logger=log)
    return gov, mon, log


def _entry(gov, at) -> str:
    return gov.allocate(mk_signal(generated_at=at), mk_portfolio(daily_drawdown_pct=0.0),
                        mk_regime(), at).reason


def _breach_and_recover(mon, day) -> None:
    mon.evaluate(acct(10_000.0), day)
    mon.evaluate(acct(9_790.0), day + MIN)                   # −2.1%: over the 2% daily limit
    mon.evaluate(acct(9_990.0), day + 2 * MIN)               # recovers inside the session


def test_a_breach_on_a_later_day_halts_again_in_one_process(tmp_path) -> None:
    gov, mon, _ = _process(tmp_path)
    _breach_and_recover(mon, D1)
    assert _entry(gov, D1 + 3 * MIN) == "drawdown_halt"
    day3 = D1 + timedelta(days=2)
    _breach_and_recover(mon, day3)
    assert _entry(gov, day3 + 3 * MIN) == "drawdown_halt"    # was "formula": halted once ever


def test_after_a_restart_the_next_day_a_fresh_breach_halts(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, mon, _ = _process(tmp_path, store)
    _breach_and_recover(mon, D1)                             # day 1: a session row is written
    day2 = D1 + timedelta(days=1)
    gov2, mon2, log2 = _process(tmp_path, store, day2)       # restart on day 2
    restore_on_boot(store, mon2, day2)
    assert _entry(gov2, day2) == "formula"                   # the lapsed halt is not restored
    assert log2.events("SESSION_HALTS_EXPIRED")
    _breach_and_recover(mon2, day2)
    assert _entry(gov2, day2 + 3 * MIN) == "drawdown_halt"   # the day-2 breach halts
    store.close()
    rows = sqlite3.connect(tmp_path / "risk.db").execute(
        "SELECT cleared_by FROM halt_event ORDER BY ts").fetchall()
    assert rows[0] == ("auto:session_boundary",)             # closed, never re-latched


def test_a_restart_inside_the_session_keeps_the_halt_until_its_boundary(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    _, mon, _ = _process(tmp_path, store)
    _breach_and_recover(mon, D1)
    gov2, mon2, _ = _process(tmp_path, store, D1 + timedelta(minutes=30))
    restore_on_boot(store, mon2, D1 + timedelta(minutes=30))
    assert _entry(gov2, D1 + timedelta(minutes=31)) == "drawdown_halt"
    close = D1.replace(hour=21)                              # 17:00 New York
    assert _entry(gov2, close + MIN) == "formula"            # it lifts at its boundary
    _breach_and_recover(mon2, close + 10 * MIN)              # and the next session re-arms
    assert _entry(gov2, close + 13 * MIN) == "drawdown_halt"
    store.close()
