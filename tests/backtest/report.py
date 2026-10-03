"""§14 grader + `ValidationReport` (ACIS-09 §4/§7/§13, master §14).

The honesty guards live HERE, in code, not just in prose:
  · the grader is only ever CALLED on the out-of-sample block (C-BT-1) —
    `build_report` routes `out_of_sample` (never `in_sample`) into
    `grade_out_of_sample`, and `targets_met`/`passed` derive only from it;
    (GAP-P11I-06 honesty: this is a FLOW guarantee, not a type barrier — both
    blocks are `MetricBlock`, so the guard is "the grader is never handed the
    in-sample block", proven by test, not "the type makes it impossible");
  · `passed` is ACIS-09 C-BT-11 v2's (R1.4, GAP-P12D-104; master §14 v2.21/v2.22): the
    family-version's STAGE RECORD holds (B0, stages A and B passed, stage C did not kill;
    `verdict.py` decides stage A from the register), AND the two §14 gates (Max DD < 15%,
    SPX correlation < 0.25), AND C-BT-2 (≥2 years, >1 fold, ≥30 trades — GAP-P11I-07),
    C-BT-4 (the guardrail hash) and C-BT-7 (no §9.5 rule violation). A report without a
    stage record never passes, so a 30% drawdown or a tampered hash cannot reach the human
    token on a verdict alone (the GAP-P12D-104 defect);
  · reported with every grade, never gated (master §14, the §5.6 expectancy law): annual
    Sharpe, win rate, profit factor, positive months, average duration (`targets_met` keeps
    all seven rows), and the Deflated Sharpe and trial count (informational, GAP-P12D-16 superseded);
  · grading is per account (C-BT-7).
A single split, a too-thin sample, an in-sample grade, a rule-violating run, a
relaxed-limit run, or a family without its stage record CANNOT pass — provable by test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping, Sequence

from tests.backtest.metrics import MetricBlock, SliceStats

# master §14 minimums (out-of-sample). Values mirror ACIS_SPEC.md §14 exactly;
# tightening the grader is allowed, loosening is a master-spec change.
SHARPE_MIN = 1.5
MAX_DD_MAX_PCT = 15.0
WIN_RATE_MIN = 0.48
PROFIT_FACTOR_MIN = 1.4
POSITIVE_MONTHS_MIN_PCT = 70.0
SPX_CORR_MAX = 0.25
DURATION_MIN_S = 30 * 60            # 30 min
DURATION_MAX_S = 48 * 3600         # 48 h
GATES = ("max_drawdown", "spx_correlation")   # the only gated §14 rows since v2.21 (GAP-P12D-96)

_MIN_YEARS = 2.0
_MIN_FOLDS = 2                       # >1 fold — a single split cannot pass
DSR_MIN = 0.95                       # GAP-P12D-16's former gate: now an informational column
_MIN_TRADES = 30                     # GAP-P11I-07: a statistically meaningful sample
#                                      (mirrors master §8 alpha_decay_min_trades) —
#                                      one lucky PF=+inf trade cannot clear §14


class InSampleGradeError(Exception):
    """Raised if anything tries to grade an in-sample block (C-BT-1)."""


@dataclass(frozen=True)
class StageRecord:
    """C-BT-11 v2's verdict on the graded family-version, read from its records (R1.4)."""
    b0: bool                         # the machinery proven at the same recon_commit (step 0)
    stage_a: bool                    # in its cycle's `verdict.cycle_verdict(...).passed`
    stage_b: bool                    # the engine confirmation (step 4)
    stage_c_killed: bool             # the held-out instruments or the 2024-25 holdout killed it (step 6)

    @property
    def holds(self) -> bool:
        return self.b0 and self.stage_a and self.stage_b and not self.stage_c_killed


@dataclass(frozen=True)
class ValidationReport:
    account: str
    period: tuple[datetime, datetime]
    split: str
    n_folds: int
    in_sample: MetricBlock            # transparency only — NEVER graded
    out_of_sample: MetricBlock        # the ONLY graded block
    # v1.6 (GAP-P12D-31): trade-level attribution, NOT MetricBlocks — a subset of trades has
    # no continuous equity curve, so Sharpe/drawdown/positive-months are undefined on it
    per_regime: Mapping[str, SliceStats]
    per_strategy: Mapping[str, SliceStats]
    equity_curve_ref: str
    drawdown_curve_ref: str
    targets_met: Mapping[str, bool]
    passed: bool
    var_breach_frequency: float
    rule_violations: tuple[str, ...]
    fidelity_caveats: tuple[str, ...]
    guardrail_hash: str
    # GAP-SP12E-03 / GAP-P12D-16: informational since R1.4 (C-BT-11 v2: "the Deflated Sharpe
    # stays as an informational column"); no clause of `passed` reads them.
    trial_count: int
    deflated_sharpe: float
    # GAP-P12D-18: the in-sample transparency record — one evolution summary per fold
    # (training windows are not replayed through the engine; `in_sample` is not graded)
    in_sample_evolution: tuple[Mapping, ...]
    # GAP-P12D-64: the look-register line this grade wrote first, and the register's
    # per-family look counts. Informational: no clause of `passed` reads it.
    look: Mapping = field(default_factory=dict)
    stages: StageRecord | None = None       # C-BT-11 v2's stage record; None = not graded by it


def grade_out_of_sample(block: MetricBlock) -> dict[str, bool]:
    """Per-§14-metric pass/fail on an OUT-OF-SAMPLE block only. Duration uses the
    carve-out-excluded `avg_trade_duration_s` (C-BT-8)."""
    return {
        "annual_sharpe": block.annual_sharpe > SHARPE_MIN,
        "max_drawdown": block.max_drawdown_pct < MAX_DD_MAX_PCT,
        "win_rate": block.win_rate > WIN_RATE_MIN,
        "profit_factor": block.profit_factor > PROFIT_FACTOR_MIN,
        "positive_months": block.positive_months_pct > POSITIVE_MONTHS_MIN_PCT,
        "spx_correlation": block.spx_correlation < SPX_CORR_MAX,
        "avg_duration": DURATION_MIN_S <= block.avg_trade_duration_s <= DURATION_MAX_S,
    }


def build_report(*, account: str, period: tuple[datetime, datetime], n_folds: int,
                 in_sample: MetricBlock, out_of_sample: MetricBlock,
                 per_regime: Mapping[str, SliceStats], guardrail_hash: str,
                 expected_guardrail_hash: str, var_breach_frequency: float,
                 rule_violations: Sequence[str], fidelity_caveats: Sequence[str],
                 equity_curve_ref: str = "", drawdown_curve_ref: str = "",
                 per_strategy: Mapping[str, SliceStats] = {},
                 split: str = "walk_forward", trial_count: int = 0,
                 deflated_sharpe: float = math.nan,
                 in_sample_evolution: Sequence[Mapping] = (),
                 stages: StageRecord | None = None) -> ValidationReport:
    targets_met = grade_out_of_sample(out_of_sample)          # C-BT-1: OOS only

    years = (period[1] - period[0]) / timedelta(days=365.25)
    guardrails_ok = guardrail_hash == expected_guardrail_hash  # C-BT-4
    passed = (
        stages is not None and stages.holds    # C-BT-11 v2: B0, A, B passed, C did not kill
        and all(targets_met[g] for g in GATES)  # §14: Max DD, SPX correlation
        and years >= _MIN_YEARS                # ≥2 years
        and n_folds >= _MIN_FOLDS              # >1 fold (C-BT-2)
        and out_of_sample.n_trades >= _MIN_TRADES  # thin-sample floor (P11I-07)
        and not rule_violations                # §9.5 (C-BT-7)
        and guardrails_ok                      # production limits (C-BT-4)
    )
    return ValidationReport(
        account=account, period=period, split=split, n_folds=n_folds,
        in_sample=in_sample, out_of_sample=out_of_sample, per_regime=dict(per_regime),
        per_strategy=dict(per_strategy),
        equity_curve_ref=equity_curve_ref, drawdown_curve_ref=drawdown_curve_ref,
        targets_met=targets_met, passed=passed,
        var_breach_frequency=var_breach_frequency,
        rule_violations=tuple(rule_violations), fidelity_caveats=tuple(fidelity_caveats),
        guardrail_hash=guardrail_hash, trial_count=trial_count,
        deflated_sharpe=deflated_sharpe, in_sample_evolution=tuple(in_sample_evolution), stages=stages)
