"""Falsification of the grading pipeline with scripted strategies (GAP-P12D-28, owner items 1–2).

The real harness, book, metrics, SPX join, Deflated Sharpe and §14 gates run unchanged; only
the engine is replaced by a scripted loop, so the verdict is known in advance:
  * a planted, consistent edge over two years MUST pass every gate — the pipeline can pass;
  * a coin-flip strategy on the same calendar MUST fail, with the Deflated Sharpe below 0.95.
(Whether the REAL engine finds a planted edge is the engine-level half of GAP-P12D-28.)
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from tests.backtest.harness import Backtest, FoldData
from tests.backtest.test_harness_regressions import _FakeLoop, _fold, _ms, _order
from tests.backtest.test_harness_runtime import NY_ROLL, _ParamsStub
from tests.optimizer_fixtures import TEST_COSTS

UTC = timezone.utc
START = datetime(2016, 1, 4, tzinfo=UTC)                      # a Monday
DAYS = 2 * 365 + 30
TRIALS = {"champions": 2, "trial_sharpes": [0.02, 0.05, -0.01, 0.03]}


def _business_days():
    d = START
    while d < START + timedelta(days=DAYS):
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _scripted(outcome) -> tuple[list, dict, dict]:
    """One long a day, opened at 10:00 UTC at 1.10 and closed one hour later at `outcome(i)`."""
    states, script = [], {}
    for i, day in enumerate(_business_days()):
        opened = day.replace(hour=10)
        exit_px = outcome(i)
        states += [_ms(opened, 1.10), _ms(opened + timedelta(hours=1), exit_px)]
        # a winner's target IS its exit tick and a loser's stop IS its exit tick (the same float:
        # 1.10 - 0.005 is 1.0950000000000002, which a literal 1.095 stop would never touch)
        win = exit_px > 1.10
        script[opened] = [_order(opened, 1, 1.10, 1.09 if win else exit_px, exit_px if win else 1.12)]
    rng = random.Random(99)
    spx, level = {}, 2000.0
    for day in _business_days():
        level *= 1 + rng.gauss(0, 0.01)
        spx[day.date()] = level
    return states, script, spx


def _grade(outcome):
    states, script, spx = _scripted(outcome)
    half = len(states) // 2
    half -= half % 2                                           # keep each trade's two ticks together
    folds = [FoldData(_fold(0, states[0].timestamp), states[:half]),
             FoldData(_fold(1, states[half].timestamp), states[half:])]
    bt = Backtest(account="a", cost_models=defaultdict(lambda: TEST_COSTS), session_boundaries=[NY_ROLL])
    loop = _FakeLoop(script)
    loop.params = _ParamsStub(bt)
    return bt.run(loop=loop, folds=folds, evolve_fn=lambda lp, fd: dict(TRIALS, fold=fd.fold.index),
                  spx_closes=spx, guardrail_hash="GH", expected_guardrail_hash="GH")


def test_a_planted_edge_passes_every_gate() -> None:
    rng = random.Random(1)
    report = _grade(lambda i: 1.10 + rng.uniform(0.003, 0.008))   # every trade wins 30–80 pips
    failed = [k for k, ok in report.targets_met.items() if not ok]
    assert failed == [], failed
    assert report.deflated_sharpe >= 0.95 and report.trial_count == 8
    assert report.passed is True                               # the pipeline CAN pass


def test_a_coin_flip_strategy_fails() -> None:
    rng = random.Random(2)
    report = _grade(lambda i: 1.10 + (0.005 if rng.random() < 0.5 else -0.005))
    assert report.out_of_sample.n_trades > 400, report.out_of_sample   # every trade closed the same hour
    assert report.passed is False, (report.out_of_sample, report.deflated_sharpe)
    assert not (report.deflated_sharpe >= 0.95)                # NaN or below the gate
    assert not report.targets_met["profit_factor"] or not report.targets_met["annual_sharpe"]
