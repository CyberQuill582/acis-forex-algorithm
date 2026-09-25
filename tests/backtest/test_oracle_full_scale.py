"""The oracle positive control at FULL fold scale on a coarse tape (audits F1, F2, E1).

The falsification plan's fold count (25 folds, > 2 graded years) on a 300 s tape grades in seconds,
so the suite can pin what stage 1 of `scripts/falsify_engine.py` would decide, instead of learning
it after ~20 minutes of compute and a VOID. One instrument (EUR_USD); the account varies per test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config.account_doctrine import guardrail_hash
from config.schemas import load_config
from tests.backtest.oracle import grade_oracle, non_dsr_failures, void_reasons
from tests.backtest.report import PROFIT_FACTOR_MIN
from tests.backtest.synthetic_grade import START, plan
from tests.backtest.synthetic_market import MarketSpec
from tests.optimizer_fixtures import CapturingLogger

ROOT = Path(__file__).resolve().parents[2]
FOLDS = plan(1, 30, 25)                                   # the falsification fold count, short trains
DAYS = (FOLDS[-1].test_end - START).days


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT / "config")


def _grade(cfg, kind: str, account: str, sign_error: float = 0.0):
    spec = MarketSpec(kind, START, DAYS, (("EUR_USD", 1.10),), tick_seconds=300)
    return grade_oracle(spec, cfg, account, FOLDS, CapturingLogger(), instruments=["EUR_USD"],
                        sign_error=sign_error)


def test_the_planted_oracle_clears_every_non_dsr_clause_at_full_fold_scale(cfg) -> None:
    """Audit F1: the 2-fold positive control asserted net > 0 and a Sharpe, so a §14 change only
    the full-scale oracle cannot meet (e.g. DURATION_MAX_S = 4 h against its ~7 h holds) left the
    whole suite green and would VOID every real stage-1 run. Here the full fold count grades."""
    hash_ = guardrail_hash(cfg.guardrails)
    fails = {k: non_dsr_failures(_grade(cfg, k, "dev_paper").report, hash_) for k in ("planted", "null")}
    assert fails["planted"] == (), fails["planted"]
    assert void_reasons(fails) == []


# the rungs for THIS tape (coarse, one instrument); the falsification tape has its own (oracle.RUNGS)
COARSE_RUNGS = {"planted-near-pass": 0.42, "planted-near-fail": 0.45}


def test_the_harness_passes_a_rung_just_above_the_cut_offs_and_refuses_one_just_below(cfg) -> None:
    """Audit E1: the perfect oracle clears §14 by a mile (PF ~13 here), so it says nothing about
    the harness's power near the decision level. Two weaker rungs of the SAME oracle — wrong on
    42% / 45% of whole episodes — bracket the binding cut-off (profit factor 1.4 for this trade
    structure; the Sharpe cut is never binding first): the harness must pass the one above and
    refuse the one below, by that §14 row, not by a rule or a floor."""
    hash_ = guardrail_hash(cfg.guardrails)
    grades = {k: _grade(cfg, "planted", "dev_paper", p) for k, p in COARSE_RUNGS.items()}
    fails = {k: non_dsr_failures(g.report, hash_) for k, g in grades.items()}
    assert fails["planted-near-pass"] == ()
    assert fails["planted-near-fail"] == ("section-14 profit_factor",)
    pf = {k: g.report.out_of_sample.profit_factor for k, g in grades.items()}
    cut = PROFIT_FACTOR_MIN                                               # the ratified §14 value, one source
    assert cut < pf["planted-near-pass"] < cut + 0.2 and cut - 0.2 < pf["planted-near-fail"] < cut, pf
    assert void_reasons(fails) == []


def test_on_a_weekend_flat_min_hold_account_the_oracle_keeps_the_rules_and_the_grade_decides(cfg) -> None:
    """Audit F2: on prop_demo (weekend holding forbidden, 60 s minimum hold) every stage-1 run used
    to VOID on `weekend_holding`, and null was "refused" by that rule whatever its metrics. Now no
    oracle breaks a rule, planted clears every non-DSR clause, and null is refused by §14 rows."""
    rulebook = cfg.platform_rules.accounts["prop_demo"]
    assert not rulebook.weekend_holding_allowed and rulebook.min_hold_seconds > 0   # fixture precondition
    hash_ = guardrail_hash(cfg.guardrails)
    planted, null = _grade(cfg, "planted", "prop_demo"), _grade(cfg, "null", "prop_demo")
    assert planted.report.rule_violations == () and null.report.rule_violations == ()
    fails = {"planted": non_dsr_failures(planted.report, hash_), "null": non_dsr_failures(null.report, hash_)}
    assert fails["planted"] == ()
    assert fails["null"] and all(f.startswith("section-14") for f in fails["null"])
    assert void_reasons(fails) == []
