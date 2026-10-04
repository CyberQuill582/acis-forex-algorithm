"""The tournament's daily job and weekly report (TOURNAMENT), end to end on stub books: registration once and
never in the past, only newly settled days appended, every recorded day re-checked (a changed recompute or a
skipped day is one revision line and blocks eligibility), a rule drift or an unsettled input stops a strategy."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from tests.backtest.forward_record import ForwardRecord
from tests.backtest.forward_store import StoreGap
from tests.backtest.look_claims import canonical_hash
from tests.backtest.tournament_books import BookSeries

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


daily, report = _script("tournament_daily"), _script("tournament_report")
T0 = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
START = date(2026, 10, 5)


class Stub:
    def __init__(self, sid: str, values: dict[date, float], tag: str = "v1", start: date = START) -> None:
        self.sid, self.values, self.tag, self.forward_start, self.fail = sid, values, tag, start, None

    def entry(self, alpha: float = 0.0025) -> dict:
        return {"kind": "entry", "strategy": self.sid, "family": "f", "variant_hash": "ab" * 32, "clock": "rsim_17ny",
                "instruments": ["EUR_USD"], "formula": "f", "origin": {}, "certifying_boundary": "2026-10-01",
                "forward_start": self.forward_start.isoformat(),
                "first_exposure_utc": f"{self.forward_start.isoformat()}T21:00:00+00:00", "sigma_daily": 0.01,
                "sharpe_dev": 0.5, "alpha": alpha, "spec_hash": canonical_hash({"sid": self.sid, "tag": self.tag})}

    def drift(self, cfg, entry: dict) -> str | None:
        return None if self.entry()["spec_hash"] == entry["spec_hash"] else "RULE DRIFT: the stub changed"

    def book(self, store, cfg, forward_start, today):
        if self.fail:
            raise self.fail
        days = sorted(d for d in self.values if forward_start <= d < today - timedelta(days=1))
        return BookSeries(tuple(days), np.array([self.values[d] for d in days]), today - timedelta(days=2), {})


class Store:
    def state_hash(self) -> str:
        return "cd" * 32


@pytest.fixture
def stubs(monkeypatch):
    vals = {START + timedelta(days=k): 0.001 * ((k % 3) - 1) for k in range(30) if (START + timedelta(days=k)).weekday() < 5}
    s = {"A": Stub("A", dict(vals)), "B": Stub("B", dict(vals))}
    monkeypatch.setattr(daily, "REGISTRY", tuple(s.values()))
    monkeypatch.setattr(daily, "BY_ID", s)
    return s


def test_registration_writes_the_rule_and_each_entry_once_and_never_in_the_past(tmp_path, stubs) -> None:
    rec = ForwardRecord(tmp_path / "rec")
    assert daily.register(rec, T0) == ["rule", "A", "B"]
    assert daily.register(rec, T0) == []
    late = Stub("C", {}, start=date(2026, 10, 3))
    daily.REGISTRY = (*daily.REGISTRY, late)
    assert daily.register(rec, T0)[0].startswith("C: REFUSED")
    assert set(rec.state().entries) == {"A", "B"}


def test_each_run_appends_only_newly_settled_days_and_rechecks_the_recorded_ones(tmp_path, stubs) -> None:
    rec = ForwardRecord(tmp_path / "rec")
    daily.register(rec, T0)
    out1 = daily.record(rec, Store(), None, date(2026, 10, 10), T0 + timedelta(days=6))
    assert out1["A"] == {"new_days": 4, "horizon": "2026-10-08", "revisions": 0, "recorded": 4}   # 10-05 .. 10-08
    out2 = daily.record(rec, Store(), None, date(2026, 10, 14), T0 + timedelta(days=10))
    assert out2["A"]["new_days"] == 2 and out2["A"]["recorded"] == 6                              # 10-09, 10-12
    stubs["A"].values[date(2026, 10, 6)] += 0.0005                         # an input revision changes a recompute
    out3 = daily.record(rec, Store(), None, date(2026, 10, 14), T0 + timedelta(days=10))
    assert out3["A"] == {"new_days": 0, "horizon": "2026-10-12", "revisions": 1, "recorded": 6}
    assert daily.record(rec, Store(), None, date(2026, 10, 14), T0 + timedelta(days=10))["A"]["revisions"] == 0
    assert dict(rec.state().days["A"])[date(2026, 10, 6)] == 0.0           # the recorded value stands
    rep = report.build(rec)
    assert rep["integrity"]["revisions"] == {"A": 1} and not rep["strategies"]["A"]["eligible_for_owner_review"]
    assert "the record failed its integrity or recompute check" in rep["strategies"]["A"]["why_not"]
    assert "the record failed its integrity or recompute check" not in rep["strategies"]["B"]["why_not"]


def test_a_rule_drift_or_an_unsettled_input_stops_a_strategy_and_appends_nothing(tmp_path, stubs, monkeypatch) -> None:
    rec = ForwardRecord(tmp_path / "rec")
    daily.register(rec, T0)
    stubs["A"].tag = "v2"
    stubs["B"].fail = StoreGap("EUR_USD 2026-10-07: neither stored nor a hole")
    out = daily.record(rec, Store(), None, date(2026, 10, 10), T0 + timedelta(days=6))
    assert out["A"].startswith("RULE DRIFT") and out["B"].startswith("NOT SETTLED")
    assert rec.state().days == {"A": [], "B": []}


def test_the_markdown_report_states_what_eligible_means(tmp_path, stubs) -> None:
    rec = ForwardRecord(tmp_path / "rec")
    daily.register(rec, T0)
    daily.record(rec, Store(), None, date(2026, 10, 14), T0 + timedelta(days=10))
    md = report.markdown(report.build(rec))
    assert "| A | 6 |" in md and "NOT evidence" in md and "Never a promotion" in md
