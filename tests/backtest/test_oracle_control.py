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
import json
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
from tests.backtest.money import quote_to_account
from tests.backtest.oracle import grade_oracle, non_dsr_failures, oracle_ticks, void_reasons
from tests.backtest.oracle_loop import NOTIONAL_FRACTION, STRATEGY, OracleLoop, OracleTick
from tests.backtest.synthetic_grade import FIRST_MID, START, plan
from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, episodes
from tests.backtest.test_metrics_and_grader import GH, _block, _report
from tests.backtest.tick_stream import build_factory, market_states
from tests.optimizer_fixtures import CapturingLogger

ROOT = Path(__file__).resolve().parents[2]
PAIR = (("EUR_USD", 1.10), ("USD_JPY", 110.0))


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT / "config")


def test_the_episode_schedule_is_exactly_the_planted_drift() -> None:
    """The oracle's knowledge is the ONE schedule `_returns` applies: planted minus null (same
    noise) is that schedule's drift, up to the two markets' different demeaning constants."""
    spec = MarketSpec("planted", START, 14, PAIR)
    planted, null = SyntheticMarket(spec), SyntheticMarket(MarketSpec("null", START, 14, PAIR))
    sigma = spec.daily_vol / math.sqrt(spec.ticks_per_day)
    for k, (inst, _) in enumerate(PAIR):
        schedule = episodes(spec, k)
        assert schedule == episodes(MarketSpec("null", START, 14, PAIR), k)   # every kind has it
        assert schedule[0].start == 0 and all(a.end == b.start for a, b in zip(schedule, schedule[1:]))
        assert {ep.sign for ep in schedule} == {-1.0, 1.0}
        diff = [p - q for p, q in zip(planted.returns(inst), null.returns(inst))]
        offset = diff[0] - schedule[0].sign * spec.drift_sigma * sigma
        for ep in schedule:
            for j in (ep.start, ep.end - 1):
                assert diff[j] - offset == pytest.approx(ep.sign * spec.drift_sigma * sigma, abs=1e-15)


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


def _falsify_script(monkeypatch, tmp_path, cfg, oracle_failures: dict, calls: list):
    """scripts/falsify_engine.py with the heavy stages stubbed: threads, not processes, and its
    ROOT moved to `tmp_path` so no run directory is written under any data/."""
    spec = importlib.util.spec_from_file_location("falsify_engine", ROOT / "scripts" / "falsify_engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def oracle_row(s, out, account, folds, root):
        return {"kind": s.kind, "trades": 40, "net_pnl": "1", "sharpe": 9.0, "psr": 1.0,
                "non_dsr_failures": oracle_failures[s.kind], "trade_returns": [0.01, 0.02, 0.015], "seconds": 0}

    def label_year(s, instrument, year, out, root):
        calls.append(("label", s.kind))
        return s.kind, instrument, year, 1, 0.0

    def grade(s, out, account, folds, root):
        calls.append(("grade", s.kind))
        return {"kind": s.kind, "passed": s.kind == "planted", "trades": 40, "sharpe": 0.0, "dsr": 0.0,
                "trials": 4, "trial_sharpes": [0.1, 0.2, 0.3, 0.4], "champions": [], "failed": [], "seconds": 0}

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "load_config", lambda path: cfg)
    for name, fn in (("oracle_row", oracle_row), ("label_year", label_year), ("grade", grade),
                     ("ProcessPoolExecutor", ThreadPoolExecutor)):
        monkeypatch.setattr(mod, name, fn)
    monkeypatch.setattr(sys, "argv", ["falsify_engine.py", "--kinds", *oracle_failures])
    return mod


def test_a_failed_oracle_voids_the_verdict_before_any_engine_compute(monkeypatch, tmp_path, cfg, capsys) -> None:
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg,
                          {"planted": ["section-14 avg_duration"], "null": ["section-14 win_rate"]}, calls)
    assert mod.main() == 4
    assert calls == []                                                     # the engine never ran
    assert "VERDICT VOID" in capsys.readouterr().out


def test_a_recognised_oracle_hands_over_to_the_unchanged_engine_stage(monkeypatch, tmp_path, cfg) -> None:
    calls: list = []
    mod = _falsify_script(monkeypatch, tmp_path, cfg,
                          {"planted": [], "null": ["section-14 win_rate"]}, calls)
    assert mod.main() == 0                                                 # planted passed, null did not
    assert {c for c in calls if c[0] == "grade"} == {("grade", "planted"), ("grade", "null")}
    run = next((tmp_path / "data" / "validation" / "falsification").iterdir())
    deflation = json.loads((run / "oracle_deflation.json").read_text(encoding="utf-8"))
    assert set(deflation) == {"planted", "null"} and all(0.0 <= v <= 1.0 for v in deflation.values())


def test_the_harness_recognises_the_oracle_on_planted_and_refuses_it_on_null(cfg) -> None:
    """The positive control itself: two folds of the falsification plan's shape on one
    instrument, every declared C8 cost charged. On planted the oracle must make money after
    costs with a strongly positive Sharpe, significant by the harness's own PSR; on null the
    SAME trades (same schedule, same timing) must show no edge."""
    folds = plan(1, 7, 2)
    days = (folds[-1].test_end - START).days
    graded = {}
    for kind in ("planted", "null"):
        spec = MarketSpec(kind, START, days, (("EUR_USD", FIRST_MID["EUR_USD"]),))
        graded[kind] = grade_oracle(spec, cfg, cfg.system.active_account, folds, CapturingLogger(),
                                    instruments=["EUR_USD"])
    planted, null = graded["planted"], graded["null"]
    p, n = planted.report.out_of_sample, null.report.out_of_sample
    assert p.n_trades == n.n_trades >= 30                                  # identical oracle logic
    assert set(planted.report.per_strategy) == {STRATEGY}
    assert planted.net_pnl > 0 and p.annual_sharpe > 5.0, (planted.net_pnl, p)
    assert planted.report.deflated_sharpe >= 0.95                         # PSR vs 0: no trials
    assert planted.report.trial_count == 0 and planted.report.passed is False   # the gate's own refusal
    assert null.report.deflated_sharpe < 0.95, null.report.deflated_sharpe   # no significant edge
    assert null.net_pnl < planted.net_pnl / 10
    assert any(f.startswith("section-14") for f in non_dsr_failures(null.report, guardrail_hash(cfg.guardrails)))
