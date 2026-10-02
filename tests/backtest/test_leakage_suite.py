"""scripts/leakage_suite.py, wired like the other slow gates (A16): its stage 1 runs for real here
(seconds); its engine stage is stubbed, because one real variant costs minutes. What is pinned:
the guard's own control gates the run, every decision day is swept by both tests, a leak exits
1, a reference that decided nothing exits 5, and nothing is written outside the run directory."""

from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from config.schemas import load_config
from tests.legacy_universe import legacy_view
from tests.backtest.leakage import Decision
from tests.backtest.leakage_markets import decision_cuts

ROOT = Path(__file__).resolve().parents[2]
US = timedelta(microseconds=1)
ARGS = ["leakage_suite.py", "--train-days", "3", "--test-days", "2", "--folds", "2"]


def _script(monkeypatch, tmp_path, *, controls=None, variant=None, argv=ARGS):
    spec = importlib.util.spec_from_file_location("leakage_suite", ROOT / "scripts" / "leakage_suite.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)                        # never write under data/
    monkeypatch.setattr(mod, "leak_config", lambda root, small_optimizer: legacy_view(load_config(ROOT / "config")))
    monkeypatch.setattr(mod, "fresh_process_pool", lambda workers: ThreadPoolExecutor(max_workers=workers))
    if controls is not None:
        monkeypatch.setattr(mod, "controls", controls)
    if variant is not None:
        monkeypatch.setattr(mod, "variant_decisions", variant)
    monkeypatch.setattr(sys, "argv", argv)
    return mod


def _report(tmp_path) -> dict:
    run, = (tmp_path / "data" / "validation" / "leakage").iterdir()
    return json.loads((run / "report.json").read_text(encoding="utf-8"))


def _fake_engine(calls: list, *, leak: bool = False, orders: bool = True):
    """One order at every weekday noon; a leaky engine lets the order before each cut see
    whether the cut's future was perturbed."""
    def variant(spec, account, folds, work, root, small, cut, mode):
        calls.append((mode, cut))
        out = [Decision(folds[0].train_end - US, folds[0].train_end, "evolution", (json.dumps({"champions": 1}),))]
        noon = spec.start + timedelta(hours=12)
        while noon < spec.end and orders:
            future = cut is not None and noon >= cut
            if not (future and mode == "truncate"):
                peeked = leak and cut is not None and mode == "perturb" and noon == cut - timedelta(hours=12)
                out.append(Decision(noon, noon, "order", ("future" if future or peeked else "past", noon)))
            noon += timedelta(days=1)
        return cut, mode, out
    return variant


def _quiet_controls(cfg, account):
    return {"void": [], "sweeps": {}}


def test_controls_only_runs_the_real_positive_control_and_stops(monkeypatch, tmp_path) -> None:
    calls: list = []
    mod = _script(monkeypatch, tmp_path, variant=_fake_engine(calls), argv=["leakage_suite.py", "--controls-only"])
    assert mod.main() == 0 and calls == []
    sweeps = _report(tmp_path)["stage1"]["sweeps"]
    assert "no violation" in sweeps["honest_t2"] and "no violation" in sweeps["honest_t1"]
    assert "violating cut" in sweeps["peek_t2"] and "violating cut" in sweeps["peek_t1"]


def test_a_guard_that_does_not_bite_voids_the_run_before_any_engine_compute(monkeypatch, tmp_path, capsys) -> None:
    calls: list = []
    mod = _script(monkeypatch, tmp_path, variant=_fake_engine(calls))
    real = mod.oracle_decisions
    monkeypatch.setattr(mod, "oracle_decisions", lambda *a, leak_every=0, **kw: real(*a, leak_every=0, **kw))
    assert mod.main() == 4 and calls == []
    assert "VERDICT VOID" in capsys.readouterr().out
    assert any("peek passed" in v for v in _report(tmp_path)["stage1"]["void"])


def test_every_decision_day_is_swept_by_both_tests_and_a_silent_engine_exits_0(monkeypatch, tmp_path) -> None:
    calls: list = []
    mod = _script(monkeypatch, tmp_path, controls=_quiet_controls, variant=_fake_engine(calls))
    assert mod.main() == 0
    report = _report(tmp_path)
    cuts = [c.isoformat() for c in sorted({c for _, c in calls if c is not None})]
    assert report["stage2"]["cuts"] == cuts and len(cuts) >= 5
    assert sorted((m, c.isoformat()) for m, c in calls if c is not None) == sorted(
        (m, c) for m in ("perturb", "truncate") for c in cuts)
    assert calls[0] == ("perturb", None)                                  # the reference ran first
    assert all("no violation detected" in s for s in report["stage2"]["sweeps"])
    assert report["verdict"].startswith("no violation detected at") and "clean" not in report["verdict"].lower()


def test_a_leaking_engine_exits_1_and_names_the_decisions(monkeypatch, tmp_path) -> None:
    mod = _script(monkeypatch, tmp_path, controls=_quiet_controls, variant=_fake_engine([], leak=True))
    assert mod.main() == 1
    report = _report(tmp_path)
    assert report["verdict"].startswith("LEAK") and report["stage2"]["violations"]
    assert "T2 future-perturbation" in report["stage2"]["violations"][0]


def test_a_reference_that_decided_nothing_is_vacuous_never_a_pass(monkeypatch, tmp_path) -> None:
    calls: list = []
    mod = _script(monkeypatch, tmp_path, controls=_quiet_controls, variant=_fake_engine(calls, orders=False))
    assert mod.main() == 5 and calls == [("perturb", None)]               # no variant was run
    assert "placed no order" in _report(tmp_path)["verdict"]


def test_out_moves_the_run_directory_and_nothing_is_written_under_data(monkeypatch, tmp_path) -> None:
    """Windows MAX_PATH: a variant's label path is ~110 characters below the run directory."""
    mod = _script(monkeypatch, tmp_path, controls=_quiet_controls, variant=_fake_engine([]),
                  argv=ARGS + ["--out", str(tmp_path / "o")])
    assert mod.main() == 0
    run, = (tmp_path / "o").iterdir()
    assert (run / "report.json").exists() and not (tmp_path / "data").exists()


def test_every_engine_variant_runs_in_a_fresh_spawned_process(monkeypatch, tmp_path) -> None:
    """MEDIUM-1: a memo the reference run filled must not survive into a variant: spawn (never
    fork), and one task per worker process."""
    spec = importlib.util.spec_from_file_location("leakage_suite", ROOT / "scripts" / "leakage_suite.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pool = mod.fresh_process_pool(2)
    try:
        assert pool._mp_context.get_start_method() == "spawn" and pool._max_tasks_per_child == 1
    finally:
        pool.shutdown()


def test_the_grid_is_the_17h_new_york_decision_epochs_plus_the_fold_boundaries() -> None:
    """X8: the engine decides daily at the 17:00 New York rollover, so the grid cuts one tick
    after each rollover that opens a trading day; the fold boundaries are cuts too."""
    from zoneinfo import ZoneInfo
    from tests.backtest.synthetic_grade import START, plan
    from tests.backtest.synthetic_market import MarketSpec
    spec = MarketSpec("null", START, 14, (("EUR_USD", 1.1),))
    folds = plan(3, 2, 2, embargo=timedelta(days=2))
    cuts = decision_cuts(spec, folds)
    tick = timedelta(seconds=spec.tick_seconds)
    epochs = [(c - tick).astimezone(ZoneInfo("America/New_York")) for c in cuts
              if (c - tick).astimezone(ZoneInfo("America/New_York")).hour == 17]
    assert len(epochs) == 9 and all(e.minute == 0 and e.weekday() not in (4, 5) for e in epochs)
    assert {f.train_end for f in folds} | {f.test_start for f in folds} <= set(cuts)
    assert all(spec.start < c < spec.end for c in cuts) and cuts == sorted(cuts)
