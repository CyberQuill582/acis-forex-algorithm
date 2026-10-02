"""The oracle positive control (GAP-P12D-37): the harness must RECOGNISE a strategy known to be
good, and must REFUSE the same logic where its knowledge is worthless.

Before this file nothing in the suite asserted that the grader can tell a good strategy from a
bad one on the synthetic markets the engine is falsified on; an unsatisfiable gate and a 30-
minute duration floor went unnoticed for a 6-hour run. The oracle knows the planted episode
state perfectly and nothing else (oracle.py); it is graded by the real harness, book, C8 cost
map, metrics and report.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from config.account_doctrine import guardrail_hash
from config.schemas import load_config
from tests.backtest.data_loader import BacktestDataLoader
from tests.legacy_universe import legacy_view
from tests.backtest.money import quote_to_account
from tests.backtest.oracle import grade_oracle, non_dsr_failures, oracle_ticks, void_reasons
from tests.backtest.oracle_loop import NOTIONAL_FRACTION, STRATEGY, OracleLoop, OracleTick
from tests.backtest.synthetic_grade import FIRST_MID, START, plan
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, episodes
from tests.backtest.report import SHARPE_MIN
from tests.backtest.test_metrics_and_grader import GH, _block, _report
from tests.backtest.tick_stream import build_factory, market_states
from tests.optimizer_fixtures import CapturingLogger

ROOT = Path(__file__).resolve().parents[2]
PAIR = (("EUR_USD", 1.10), ("USD_JPY", 110.0))


@pytest.fixture(scope="module")
def cfg():
    return legacy_view(load_config(ROOT / "config"))     # the legacy engine's synthetic pairs


def test_the_episode_schedule_is_exactly_the_planted_drift() -> None:
    """The oracle's knowledge is the ONE schedule `_returns` applies: planted is the null's noise
    plus that schedule's drift, times ONE variance-matching scale (C-BT-12), so planted/scale minus
    null is exactly the drift."""
    spec = MarketSpec("planted", START, 14, PAIR)
    planted, null = SyntheticMarket(spec), SyntheticMarket(MarketSpec("null", START, 14, PAIR))
    sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
    for k, (inst, _) in enumerate(PAIR):
        schedule = episodes(spec, k)
        assert schedule == episodes(MarketSpec("null", START, 14, PAIR), k)   # every kind has it
        assert schedule[0].start == 0 and all(a.end == b.start for a, b in zip(schedule, schedule[1:]))
        assert {ep.sign for ep in schedule} == {-1.0, 1.0}
        p, q = planted.returns(inst), null.returns(inst)
        scale = p[0] / (q[0] + schedule[0].sign * spec.drift_sigma * sigma)
        assert 0.9 < scale < 1.0                                  # the drift adds variance; the match removes it
        for ep in schedule:
            for j in (ep.start, ep.end - 1):
                assert p[j] / scale - q[j] == pytest.approx(ep.sign * spec.drift_sigma * sigma, abs=1e-15)


def test_episode_sign_is_the_state_in_force_never_the_next_one() -> None:
    """At the last tick of an episode the oracle still sees that episode; the new sign shows
    only on the tick whose return the new episode produced (no foresight of a change)."""
    m = SyntheticMarket(MarketSpec("planted", START, 7, PAIR))
    ticks = list(m.load("EUR_USD", START, START + timedelta(days=2)))     # > 7 episodes of <= 4 h
    assert [m.index_of(t.event_time) for t in ticks] == list(range(len(ticks)))
    for a, b in zip(episodes(m.spec, 0)[:6], episodes(m.spec, 0)[1:7]):
        assert m.episode_sign("EUR_USD", ticks[b.start - 1].event_time) == a.sign
        assert m.episode_sign("EUR_USD", ticks[b.start].event_time) == b.sign
    with pytest.raises(ValueError, match="weekday tick"):
        m.index_of(START + timedelta(days=5, hours=1))                   # a Saturday


def test_oracle_ticks_equal_the_factory_path(cfg) -> None:
    """The oracle skips the MarketStateFactory; every field the harness and book read must be
    exactly what the factory would have produced, in the same merged order."""
    m = SyntheticMarket(MarketSpec("planted", START, 7, PAIR))
    insts = [i for i, _ in PAIR]
    start, end = START + timedelta(days=4, hours=19), START + timedelta(days=4, hours=23)  # Fri: the weekend cut
    loader = BacktestDataLoader({m.name: m}, CapturingLogger())
    fields = ("timestamp", "instrument", "bid", "ask", "spread", "mid")
    ours = [tuple(getattr(t, f) for f in fields) for t in oracle_ticks(cfg, loader, m.name, insts, start, end)]
    theirs = [tuple(getattr(s, f) for f in fields) for s in market_states(
        cfg=cfg, loader=loader, factory=build_factory(cfg, insts), source=m.name,
        instruments=insts, start=start, end=end)]
    assert ours == theirs and len(ours) > 500                            # and the weekend cut applied
    assert max(t[0] for t in ours) < START + timedelta(days=4, hours=22)


def test_the_oracle_sizes_one_nav_of_notional_on_every_instrument() -> None:
    """Audit E9: a fixed 10,000 units was $11k of EUR/USD but $18M of gold on a $10k account.
    Each order's USD notional is NAV x NOTIONAL_FRACTION, to within one unit's value."""
    prices = (("EUR_USD", 1.10), ("USD_JPY", 110.0), ("XAU_USD", 1800.0))
    loop = OracleLoop(SyntheticMarket(MarketSpec("planted", START, 7, prices)), nav=Decimal("10000"))
    for inst, px in prices:
        loop.on_state(OracleTick(START, inst, px - 1e-4, px + 1e-4, 2e-4, px))
    target = Decimal("10000") * NOTIONAL_FRACTION
    for order, (inst, px) in zip(loop.book.orders, prices):
        usd_per_unit = Decimal(str(px)) * quote_to_account(inst, px, {})
        assert target - usd_per_unit < order.size_units * usd_per_unit <= target, (inst, order.size_units)
    assert [o.size_units for o in loop.book.orders] == [Decimal(9090), Decimal(10000), Decimal(5)]


def test_non_dsr_failures_is_every_clause_of_passed_but_the_trials() -> None:
    """The positive control's criterion must not drift from the ratified gate: with the trial
    clauses satisfied, `passed` holds exactly when there is no non-DSR failure."""
    short = (START, START + timedelta(days=365))
    cases = [_report(), _report(out_of_sample=_block(annual_sharpe=0.5)), _report(n_folds=1),
             _report(period=short), _report(out_of_sample=_block(n_trades=5)),
             _report(rule_violations=["min_hold"]), _report(guardrail_hash="TAMPERED")]
    for r in cases:
        assert r.passed is (not non_dsr_failures(r, GH)), (r.passed, non_dsr_failures(r, GH))
    assert non_dsr_failures(_report(trial_count=0, deflated_sharpe=float("nan")), GH) == ()


def test_void_reasons_need_planted_recognised_and_every_control_refused_by_a_section_14_row() -> None:
    assert void_reasons({"planted": (), "null": ("section-14 win_rate",),
                         "permuted": ("section-14 annual_sharpe",)}) == []
    assert "planted oracle failed" in void_reasons({"planted": ("section-14 avg_duration",)})[0]
    assert "not refused by any section-14 row" in void_reasons({"planted": (), "null": ()})[0]
    # audit F2: a control refused only by a sample floor or a rule is not refused by the grade,
    # and an oracle that breaks a rule it is built to keep voids the run by itself
    floor_only = void_reasons({"planted": (), "null": ("12 trades < 30",)})
    assert len(floor_only) == 1 and "not refused by any section-14 row" in floor_only[0]
    ruled = void_reasons({"planted": (), "null": ("section-14 win_rate", "rule violation weekend_holding")})
    assert len(ruled) == 1 and "null oracle broke the account's rules" in ruled[0]


def _falsify_script(monkeypatch, tmp_path, cfg, oracle_failures: dict, calls: list, engine: dict | None = None):
    """scripts/falsify_engine.py with the heavy stages stubbed: threads, not processes, and its
    ROOT moved to `tmp_path` so no run directory is written under any data/."""
    spec = importlib.util.spec_from_file_location("falsify_engine", ROOT / "scripts" / "falsify_engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rung_defaults = {"planted-near-pass": [], "planted-near-fail": ["section-14 profit_factor"]}

    def oracle_row(s, out, account, folds, root, *, sign_error=0.0, tag=None):
        kind = tag or s.kind
        calls.append(("oracle", kind))
        fails = oracle_failures[kind] if kind in oracle_failures else rung_defaults[kind]
        return {"kind": kind, "trades": 40, "net_pnl": "1", "sharpe": 9.0, "psr": 1.0,
                "non_dsr_failures": fails, "seconds": 0}

    def label_year(s, instrument, year, out, root):
        calls.append(("label", s.kind))
        return s.kind, instrument, year, 1, 0.0

    def grade(s, out, account, folds, root):
        calls.append(("grade", s.kind))
        passed, non_dsr = (engine or {}).get(s.kind, (s.kind == "planted", [] if s.kind == "planted"
                                                                             else ["section-14 win_rate"]))
        return {"kind": s.kind, "passed": passed, "trades": 40, "sharpe": 0.0, "dsr": 0.0,
                "trials": 4, "sr0_hurdle": 0.345, "champions": [], "failed": [],
                "non_dsr_failed": non_dsr, "seconds": 0}

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "load_config", lambda path: cfg)
    for name, fn in (("oracle_row", oracle_row), ("label_year", label_year), ("grade", grade),
                     ("ProcessPoolExecutor", ThreadPoolExecutor)):
        monkeypatch.setattr(mod, name, fn)
    kinds = [k for k in oracle_failures if k in ("planted", "null", "permuted")]
    monkeypatch.setattr(sys, "argv", ["falsify_engine.py", "--kinds", *kinds])
    return mod


def _engine_calls(calls: list) -> list:
    return [c for c in calls if c[0] != "oracle"]


def test_a_failed_oracle_voids_the_verdict_before_any_engine_compute(monkeypatch, tmp_path, cfg, capsys) -> None:
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg,
                          {"planted": ["section-14 avg_duration"], "null": ["section-14 win_rate"]}, calls)
    assert mod.main() == 4
    assert _engine_calls(calls) == []                                      # the engine never ran
    assert "VERDICT VOID" in capsys.readouterr().out


def test_a_near_fail_rung_the_harness_passes_voids_the_verdict(monkeypatch, tmp_path, cfg, capsys) -> None:
    """Audit E1: stage 1 grades both rungs whenever planted runs, and a grader that passes the rung
    just below the cut-offs has no power there, so no engine verdict is given."""
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg, {"planted": [], "null": ["section-14 win_rate"],
                                                       "planted-near-fail": []}, calls)
    assert mod.main() == 4
    assert {c[1] for c in calls if c[0] == "oracle"} == {"planted", "null", "planted-near-pass",
                                                         "planted-near-fail"}
    assert _engine_calls(calls) == [] and "planted-near-fail oracle was not refused" in capsys.readouterr().out


@pytest.mark.parametrize("kinds", [("null", "permuted"), ("planted",)])
def test_no_verdict_without_the_positive_control_and_a_control(monkeypatch, tmp_path, cfg, capsys, kinds) -> None:
    """Audits E3/F4: `--kinds null permuted` used to exit 0 and print "planted passes" for a market
    that never ran — a dead grader "held". Without planted, or without any control, nothing runs."""
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg, {k: ["section-14 win_rate"] for k in kinds}, calls)
    assert mod.main() == 5
    assert calls == [] and "NO VERDICT" in capsys.readouterr().out


def test_the_held_message_names_only_the_markets_graded(monkeypatch, tmp_path, cfg, capsys) -> None:
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg, {"planted": [], "null": ["section-14 win_rate"]}, calls)
    assert mod.main() == 0
    held = [line for line in capsys.readouterr().out.splitlines() if "falsification held" in line]
    assert held == ["falsification held on the markets graded in this run: planted passed; null did not"]


def test_a_planted_refusal_only_by_the_dsr_gate_is_gate_limited_not_an_engine_failure(
        monkeypatch, tmp_path, cfg, capsys) -> None:
    """Audit E2: stage 1 excludes the DSR clauses, so a planted run that met every other clause of
    `passed` and failed only the (open, GAP-P12D-33/37) DSR gate was reported as the engine's
    failure. It is GATE-LIMITED: its own exit code and message."""
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg, {"planted": [], "null": ["section-14 win_rate"]}, calls,
                          engine={"planted": (False, [])})
    assert mod.main() == 6
    out = capsys.readouterr().out
    assert "GATE-LIMITED" in out and "NOT an engine verdict" in out and "FALSIFICATION FAILED" not in out
    # a planted run that ALSO failed a non-DSR clause is the engine's failure, and so is a passing control
    for engine in ({"planted": (False, ["section-14 profit_factor"])}, {"null": (True, [])}):
        mod = _falsify_script(monkeypatch, tmp_path, cfg, {"planted": [], "null": ["section-14 win_rate"]},
                              calls, engine=engine)
        assert mod.main() == 1 and "FALSIFICATION FAILED" in capsys.readouterr().out


def test_a_recognised_oracle_hands_over_to_the_unchanged_engine_stage(monkeypatch, tmp_path, cfg, capsys) -> None:
    """Audit E4: the run reports each engine run's per-trade SR0 HURDLE, labelled as one; it no
    longer writes `oracle_deflation.json`, which was not a faithful Deflated Sharpe (the oracle is
    not in the trial set, and ~5-trade holdout Sharpes are not commensurate with its record)."""
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg,
                          {"planted": [], "null": ["section-14 win_rate"]}, calls)
    assert mod.main() == 0                                                 # planted passed, null did not
    assert {c for c in calls if c[0] == "grade"} == {("grade", "planted"), ("grade", "null")}
    run = next((tmp_path / "data" / "validation" / "falsification").iterdir())
    assert not (run / "oracle_deflation.json").exists()
    out = capsys.readouterr().out
    assert "oracle deflated" not in out and "DSR=" not in out
    hurdles = [line for line in out.splitlines() if "SR0 hurdle" in line]
    assert len(hurdles) == 2 and all("= 0.345 (a hurdle" in line for line in hurdles)


def test_the_harness_recognises_the_oracle_on_planted_and_refuses_it_on_null(cfg) -> None:
    """The positive control itself: twelve folds of the falsification plan's shape on the pair,
    every declared C8 cost charged. On planted the oracle must make money after costs with a
    strongly positive Sharpe, significant by the harness's own PSR; on null the SAME trades (same
    schedule, same timing) must show no edge. The variance-matched market (C-BT-12) plants an
    oracle Sharpe of 10, not ~157, so the sample must be large enough to be significant on ANY
    seed, not only the committed one (audit R11I-10). Seeds 7-11, measured 2026-09-29 on this
    design: planted Sharpe 5.7-8.3 with PSR 1.000; null PSR at most 0.84. The Sharpe bar of 4.0
    sits ~2 se under that range; a halved oracle (~3.5) mostly fails it. The null's net is at
    most half the planted's: on the oracle-157 market the ratio was 1/10, but at this strength
    the null's sampling noise alone reaches ~16% (seed 10)."""
    folds = plan(1, 7, 12)
    days = (folds[-1].test_end - START).days
    graded = {}
    for kind in ("planted", "null"):
        spec = MarketSpec(kind, START, days, tuple((i, FIRST_MID[i]) for i, _ in PAIR))
        graded[kind] = grade_oracle(spec, cfg, cfg.system.active_account, folds, CapturingLogger(),
                                    instruments=[i for i, _ in PAIR])
    planted, null = graded["planted"], graded["null"]
    p, n = planted.report.out_of_sample, null.report.out_of_sample
    assert p.n_trades == n.n_trades >= 30                                  # identical oracle logic
    assert set(planted.report.per_strategy) == {STRATEGY}
    assert planted.net_pnl > 0 and p.annual_sharpe > 4.0 > SHARPE_MIN, (planted.net_pnl, p)
    assert planted.report.deflated_sharpe >= 0.95                         # PSR vs 0: no trials
    assert planted.report.trial_count == 0 and planted.report.passed is False   # the gate's own refusal
    assert null.report.deflated_sharpe < 0.95, null.report.deflated_sharpe   # no significant edge
    assert null.net_pnl < planted.net_pnl / 2
    assert any(f.startswith("section-14") for f in non_dsr_failures(null.report, guardrail_hash(cfg.guardrails)))
