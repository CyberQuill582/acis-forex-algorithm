"""The look register (GAP-P12D-64), complete by construction: every repro of the dual audit
(GAP-P12D-83: INTERNAL HIGH-1 L1-L5 and the race, EXTERNAL X4 (a)-(f) and X9) is a regression here.
The register counts looks; it changes no threshold and no gate."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import tests.backtest.look_claims as lc
import tests.backtest.look_register as lr
from config.schemas import load_config
from tests.backtest.data_loader import BacktestDataLoader, TickSource
from tests.backtest.harness import NOT_REPLAYED
from tests.backtest.look_claims import Claim, Origin
from tests.backtest.look_declarations import Declaration
from tests.backtest.look_gate import begin_grade
from tests.backtest.look_register import LookRefused, LookRegister, config_hash, data_tier
from tests.backtest.oos_plan import plan_folds
from tests.backtest.report import build_report
from tests.backtest.sources import DukascopyTickSource
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket
from tests.backtest.walk_forward import Fold
from tests.optimizer_fixtures import CapturingLogger

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]
GIT = ("c0ffee", False)
REAL_FOLDS = plan_folds(2014, 2015)


class _StandInMirror(DukascopyTickSource):
    """A source object whose class declares real provenance and the name 'dukascopy'; no data is read."""

    def __init__(self) -> None:
        pass


class _Undeclared(TickSource):
    name = "dukascopy-mirror"

    def load(self, instrument, start, end):
        return iter(())


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    """The one real-data register, relocated for the test; git reports a clean tree at c0ffee."""
    root = tmp_path / "data" / "validation" / "looks"
    monkeypatch.setattr(lr, "CANONICAL", root)
    monkeypatch.setattr(lr, "git_state", lambda repo=None: GIT)
    monkeypatch.setattr(lc, "OPEN_ORIGINS", frozenset(lc.ORIGINS))       # the register's mechanics for every
    monkeypatch.setattr(lc, "OPEN_SIMULATORS", frozenset(lc.SIMULATORS))  # claim; the scope has its own test
    return LookRegister(root)


def _claim(family: str) -> Claim:
    """A real-data look carries its declared family-version (register v2, GAP-P12D-98)."""
    return Claim(family=family, variant="fixed", universe_id="test-universe", origin=Origin("human"),
                 declared_space={"grid": {}, "formula": "sign(ewmac 16/64)", "instruments": ["EUR_USD", "USD_JPY"]},
                 simulator="engine", recon_commit=GIT[0],
                 declaration=Declaration("fixed", 3, "PASSIVE_LONG"))


def _real(reg, cfg, family="trend-v1", **kw):
    kw.setdefault("git", GIT)
    if family.strip():                                      # a blank family is refused before any claim
        kw.setdefault("claim", _claim(family))
    return reg.register(cfg=cfg, source=_StandInMirror(), instruments=sorted(cfg.instruments.enabled),
                        folds=REAL_FOLDS, family=family, account="dev_paper", **kw)


def _grade_args(cfg, source_obj, key=None, **kw):
    args = dict(cfg=cfg, loader=BacktestDataLoader({key or source_obj.name: source_obj}, CapturingLogger()),
                source=key or source_obj.name, instruments=sorted(cfg.instruments.enabled), folds=REAL_FOLDS,
                account="dev_paper", cost_stress=1.0, spread_floor=0.0, simulator="engine")
    args.update(kw)
    return args


def _fold(test_start: datetime, test_end: datetime) -> Fold:
    return Fold(0, test_start - timedelta(days=730), test_start, test_start + timedelta(days=7), test_end)


# -- where a look may live, and what tier it is (L1, L2, X4 a/d, X9) ------------------------ #

def test_a_real_data_look_outside_the_canonical_register_is_refused(canonical, tmp_path, acis_config) -> None:
    with pytest.raises(LookRefused, match="must be registered in"):
        _real(LookRegister(tmp_path / "anywhere"), acis_config)                  # L1 / X4(a)
    look = _real(canonical, acis_config)
    moved = tmp_path / "anywhere2"
    moved.mkdir()
    (moved / "000001.json").write_bytes(Path(look.path).read_bytes())
    with pytest.raises(LookRefused, match="needs its look in"):
        begin_grade(replace(look, path=str(moved / "000001.json")), **_grade_args(acis_config, _StandInMirror()))


def test_the_tier_comes_from_the_source_object_never_a_caller_string(canonical, tmp_path, acis_config) -> None:
    assert data_tier(SyntheticMarket(MarketSpec("null", datetime(2014, 1, 6, tzinfo=UTC), 7, (("EUR_USD", 1.1),))),
                     REAL_FOLDS) == 0
    assert data_tier(_StandInMirror(), REAL_FOLDS) == 2
    with pytest.raises(LookRefused, match="declares no provenance"):            # X4(d): never tier 0
        data_tier(_Undeclared(), REAL_FOLDS)
    look = _real(canonical, acis_config)
    with pytest.raises(LookRefused, match="names a source whose own name"):     # L2: a real object keyed 'synthetic'
        begin_grade(look, **_grade_args(acis_config, _StandInMirror(), key="synthetic"))


def test_tiers_follow_the_test_windows_and_forward_starts_after_the_model_cutoff() -> None:
    src = _StandInMirror()
    assert data_tier(src, plan_folds(2014, 2023)) == 2 and data_tier(src, plan_folds(2024, 2025)) == 3
    assert data_tier(src, [_fold(datetime(2010, 1, 1, tzinfo=UTC), datetime(2011, 1, 1, tzinfo=UTC))]) == 1
    # X9: Jan-Jun 2026 is history the June-2026 models may have seen: exploration, not forward
    assert data_tier(src, [_fold(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 6, 1, tzinfo=UTC))]) == 1
    assert data_tier(src, [_fold(datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC))]) == 4
    with pytest.raises(LookRefused, match="straddles"):
        data_tier(src, [_fold(datetime(2023, 6, 1, tzinfo=UTC), datetime(2024, 6, 1, tzinfo=UTC))])
    with pytest.raises(LookRefused, match="one data tier"):
        data_tier(src, plan_folds(2023, 2023) + plan_folds(2024, 2024))


# -- one line is one grade, for exactly its run, on the code it names (L3, L4, X4 c) -------- #

def test_one_line_is_one_grade(canonical, acis_config) -> None:
    look = _real(canonical, acis_config)
    begin_grade(look, **_grade_args(acis_config, _StandInMirror()))
    with pytest.raises(LookRefused, match="already graded"):                   # L3
        begin_grade(look, **_grade_args(acis_config, _StandInMirror()))


def test_the_grade_refuses_before_any_compute_without_its_own_line(canonical, tmp_path, acis_config) -> None:
    from tests.backtest.oos_runner import RunInputs, run_walk_forward
    base = dict(cfg=acis_config, account="dev_paper", source="dukascopy",
                loader=BacktestDataLoader({"dukascopy": _StandInMirror()}, CapturingLogger()), cache=None,
                folds=REAL_FOLDS, spx_closes={}, financing=None, work_dir=tmp_path / "engine", logger=CapturingLogger())
    with pytest.raises(LookRefused, match="no registered look"):
        run_walk_forward(lr_inputs := RunInputs(**base, look=None))
    look = _real(canonical, acis_config)
    with pytest.raises(LookRefused, match="another run"):
        run_walk_forward(replace(lr_inputs, look=look, cost_stress=2.0))
    assert not (tmp_path / "engine").exists()                        # refused before the engine was built


def test_a_line_binds_its_run_properties(canonical, acis_config) -> None:
    look = _real(canonical, acis_config)
    for other in (dict(cost_stress=3.0), dict(account="other"), dict(folds=REAL_FOLDS[:1])):
        with pytest.raises(LookRefused, match="another run"):
            begin_grade(look, **_grade_args(acis_config, _StandInMirror(), **other))


def test_a_real_look_needs_a_clean_tree_and_the_grade_the_same_commit(canonical, monkeypatch, acis_config) -> None:
    for git in (("c0ffee", True), ("unknown", True)):                            # X4(c)
        with pytest.raises(LookRefused, match="clean tracked tree"):
            _real(canonical, acis_config, git=git)
    look = _real(canonical, acis_config)
    monkeypatch.setattr(lr, "git_state", lambda repo=None: ("beef00", False))
    with pytest.raises(LookRefused, match="would not pin the code"):
        begin_grade(look, **_grade_args(acis_config, _StandInMirror()))


def test_git_state_ignores_untracked_files(tmp_path) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for args in (["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "a"], check=True)
    (tmp_path / "untracked.md").write_text("an audit report", encoding="utf-8")
    assert lr.git_state(tmp_path)[1] is False
    (tmp_path / "a.txt").write_text("edited", encoding="utf-8")
    assert lr.git_state(tmp_path)[1] is True


# -- tamper evidence and torn lines (L4, L5, X4 b/f) ------------------------------------------ #

def test_forged_deleted_or_edited_lines_break_the_chain_and_the_register_fails_closed(canonical, acis_config) -> None:
    first = _real(canonical, acis_config)
    second = _real(canonical, acis_config, changed="tweak A")
    third = _real(canonical, acis_config, changed="tweak B")
    begin_grade(third, **_grade_args(acis_config, _StandInMirror()))
    Path(third.path).unlink()                                     # X4(b): bury the latest look
    assert any("has no look line" in b for b in canonical.scan().broken)
    with pytest.raises(LookRefused, match="register is broken"):
        _real(canonical, acis_config, changed="tweak C")
    Path(third.path).write_bytes(json.dumps(lr.asdict(third), sort_keys=True).encode())   # restore
    assert not canonical.scan().broken
    edited = json.loads(Path(second.path).read_text(encoding="utf-8"))
    edited["changed"] = "something milder"                        # rewrite history
    Path(second.path).write_text(json.dumps(edited, sort_keys=True), encoding="utf-8")
    assert any("does not chain" in b for b in canonical.scan().broken)
    with pytest.raises(LookRefused, match="register is broken"):
        begin_grade(first, **_grade_args(acis_config, _StandInMirror()))


def test_a_hand_forged_look_object_is_refused(canonical, acis_config) -> None:   # L4
    look = _real(canonical, acis_config)
    with pytest.raises(LookRefused, match="not on disk as registered"):
        begin_grade(replace(look, git_commit="deadbeef"), **_grade_args(acis_config, _StandInMirror()))
    with pytest.raises(LookRefused, match="no registered look"):
        begin_grade(None, **_grade_args(acis_config, _StandInMirror()))


def test_a_torn_line_is_reported_and_counted_and_never_bricks_the_register(canonical, acis_config) -> None:
    good = _real(canonical, acis_config)
    (canonical.root / "000002.json").write_bytes(b"")               # L5 / X4(f): a power cut mid-write
    later = _real(canonical, acis_config, changed="after the power cut")
    assert later.look_id == "000003" and later.prev_hash == lr._sha(b"")
    summary = canonical.summary()
    assert summary["torn_lines"] == ["000002.json"] and summary["family_looks"][lr.TORN] == {"unknown": 1}
    assert summary["tier_totals"] == {"unknown": 1, "validation": 2}
    begin_grade(good, **_grade_args(acis_config, _StandInMirror()))  # no JSONDecodeError anywhere


# -- counting (the race, X4 e) ---------------------------------------------------------------- #

def test_a_real_family_that_looked_before_must_say_what_changed(canonical, tmp_path, acis_config) -> None:
    first = _real(canonical, acis_config)
    assert first.tier_name == "validation" and first.changed == "first look" and first.previous is None
    assert first.prev_hash == lr.GENESIS
    with pytest.raises(LookRefused, match="say what changed"):
        _real(canonical, acis_config)
    second = _real(canonical, acis_config, changed="gene ranges narrowed")
    assert second.previous == ("000001", "c0ffee", config_hash(acis_config))
    market = SyntheticMarket(MarketSpec("null", datetime(2014, 1, 6, tzinfo=UTC), 7, (("EUR_USD", 1.1),)))
    synthetic = LookRegister(tmp_path / "synthetic-run")
    for _ in range(2):                                     # tier 0: unlimited, no account owed
        synthetic.register(cfg=acis_config, source=market, instruments=["EUR_USD"], folds=REAL_FOLDS,
                           family="trend-v1", account="dev_paper", git=GIT)
    with pytest.raises(LookRefused, match="name its hypothesis family"):
        _real(canonical, acis_config, family="  ")

def test_concurrent_first_looks_are_unambiguous(canonical, acis_config) -> None:
    barrier, results = threading.Barrier(2), []
    first_scan = threading.local()

    class _Slow(LookRegister):
        def scan(self):
            out = super().scan()
            if not getattr(first_scan, "done", False):                # both read, then both claim
                first_scan.done = True
                barrier.wait()
            return out

    def go():
        try:
            results.append(_real(_Slow(canonical.root), acis_config))
        except LookRefused as exc:
            results.append(exc)
    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    looks = [r for r in results if isinstance(r, lr.Look)]
    refused = [r for r in results if isinstance(r, LookRefused)]
    assert len(looks) == 1 and looks[0].changed == "first look" and len(refused) == 1
    assert "say what changed" in str(refused[0])


def test_a_renamed_family_still_adds_to_its_tier_total(canonical, acis_config) -> None:   # X4(e)
    _real(canonical, acis_config)
    _real(canonical, acis_config, family="trend-v1b")
    assert canonical.summary()["tier_totals"] == {"validation": 2}


# -- outcome, and the real-data entry point ----------------------------------------------------- #

def test_the_real_data_script_writes_its_line_before_it_grades(monkeypatch, tmp_path) -> None:
    spec = importlib.util.spec_from_file_location("run_oos_validation", ROOT / "scripts" / "run_oos_validation.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = load_config(ROOT / "config")
    monkeypatch.setattr(lr, "CANONICAL", tmp_path / "data" / "validation" / "looks")
    monkeypatch.setattr(lr, "git_state", lambda repo=None: GIT)
    monkeypatch.setattr(lc, "REAL_LOOKS_OPEN", True)
    monkeypatch.setattr(lc, "OPEN_SIMULATORS", frozenset(lc.SIMULATORS))   # engine looks: R12I-12's scope
    seen: list = []

    def grade(inp):
        line = json.loads(Path(inp.look.path).read_text(encoding="utf-8"))    # on disk BEFORE the grade
        seen.append(line)
        report = build_report(account=inp.account, period=(datetime(2014, 1, 8, tzinfo=UTC),) * 2, n_folds=2,
                              in_sample=NOT_REPLAYED, out_of_sample=NOT_REPLAYED, per_regime={},
                              guardrail_hash="h", expected_guardrail_hash="h", var_breach_frequency=math.nan,
                              rule_violations=(), fidelity_caveats=())
        return replace(report, look={"look_id": inp.look.look_id, "family_looks": {line["family"]: {"validation": 1}}})
    for name, fn in (("ROOT", tmp_path), ("load_config", lambda p: cfg), ("missing_labels", lambda *a: []),
                     ("load_spx_closes", lambda p: {}), ("load_rate_table", lambda p: None),
                     ("make_financing", lambda t: None), ("run_walk_forward", grade)):
        monkeypatch.setattr(mod, name, fn)
    monkeypatch.setattr(sys, "argv", ["run_oos_validation.py", "--first-test-year", "2014", "--last-test-year", "2015"])
    with pytest.raises(SystemExit):                          # no family, no look, no grade
        mod.main()
    assert seen == [] and not (tmp_path / "data" / "validation" / "looks").exists()
    monkeypatch.setattr(sys, "argv", sys.argv + ["--family", "trend-v1", "--operator", "owner",
                                               "--origin", "human", "--recon-commit", "c0ffee",
                                               "--kind", "fixed", "--look-budget", "2", "--benchmark", "PASSIVE_LONG"])
    assert mod.main() == 0
    assert seen[0]["family"] == "trend-v1" and seen[0]["tier_name"] == "validation" and seen[0]["operator"] == "owner"
    assert seen[0]["source_class"] == "DukascopyTickSource" and seen[0]["git_commit"] == "c0ffee"
    assert mod.main() == 2 and len(seen) == 1                # a second look must say what changed


def test_a_look_claiming_one_simulator_cannot_be_graded_by_the_other(canonical, acis_config) -> None:
    """R12I-03 (GAP-P12D-127): the claim's simulator must be the grader's; nothing is consumed on refusal."""
    look = _real(canonical, acis_config)
    with pytest.raises(LookRefused, match="this grader is 'rsim'"):
        begin_grade(look, **_grade_args(acis_config, _StandInMirror(), simulator="rsim"))
    assert not (canonical.root / f"{look.look_id}.graded.json").exists()
    begin_grade(look, **_grade_args(acis_config, _StandInMirror()))
