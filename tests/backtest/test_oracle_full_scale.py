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
from tests.backtest.synthetic_grade import START, plan
from tests.backtest.synthetic_market import MarketSpec
from tests.optimizer_fixtures import CapturingLogger

ROOT = Path(__file__).resolve().parents[2]
FOLDS = plan(1, 30, 25)                                   # the falsification fold count, short trains
DAYS = (FOLDS[-1].test_end - START).days


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT / "config")


def _grade(cfg, kind: str, account: str):
    spec = MarketSpec(kind, START, DAYS, (("EUR_USD", 1.10),), tick_seconds=300)
    return grade_oracle(spec, cfg, account, FOLDS, CapturingLogger(), instruments=["EUR_USD"])


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
