"""Phase-11 unit tests: §14 metrics + the grader honesty guards (ACIS-09 §13/§14).

Postcondition-style. Covers C-BT-1 (OOS-only grade), C-BT-2 (walk-forward
required), C-BT-4 (guardrail hash), C-BT-7 (rules-active), C-BT-8 (duration
carve-outs), plus NaN-safety.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.backtest.metrics import (ClosedTrade, MetricBlock, annual_sharpe,
                                    compute_metrics, max_drawdown_pct,
                                    positive_months_pct, profit_factor,
                                    rolling_var_breach_rate,
                                    var_breach_frequency, win_rate)
from tests.backtest.report import build_report, grade_out_of_sample
from tests.backtest.walk_forward import generate_folds

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
GH = "GUARDRAIL_HASH_64"


def _eq(vals):
    return [(T0 + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(vals)]


# -- metrics ------------------------------------------------------------------ #

def test_sharpe_zero_variance_is_zero_not_inf() -> None:
    assert annual_sharpe([0.01, 0.01, 0.01], 252) == 0.0     # flat → no spurious inf
    assert annual_sharpe([], 252) == 0.0
    assert annual_sharpe([0.01], 252) == 0.0                  # <2 samples


def test_constant_nonzero_returns_have_no_sharpe() -> None:
    """GAP-P12D-17: a plain `sum` left float dust on a long constant series — an annual
    Sharpe of 4.5e16 from 50 × 0.01 — which would clear the §14 Sharpe > 1.5 gate."""
    for value, n in ((0.01, 50), (0.001, 252), (-0.0007, 500)):
        assert annual_sharpe([value] * n, 252) == 0.0


def test_max_drawdown_peak_to_trough() -> None:
    # 100 → 120 → 90 → 130: worst DD is (120-90)/120 = 25%
    assert max_drawdown_pct(_eq([100, 120, 90, 130])) == 25.0


def test_win_rate_and_profit_factor() -> None:
    trades = [
        ClosedTrade(T0, T0 + timedelta(hours=1), Decimal("100"), "TREND"),
        ClosedTrade(T0, T0 + timedelta(hours=1), Decimal("-50"), "TREND"),
        ClosedTrade(T0, T0 + timedelta(hours=1), Decimal("50"), "TREND"),
    ]
    assert win_rate(trades) == 2 / 3
    assert profit_factor(trades) == 150.0 / 50.0
    assert win_rate([]) == 0.0                                # NaN-safe
    assert profit_factor([]) == 0.0


def test_positive_months() -> None:
    eq = [(datetime(2026, m, 28, tzinfo=timezone.utc), Decimal(str(v)))
          for m, v in [(1, 100), (2, 110), (3, 105), (4, 120)]]
    # Feb>Jan (+), Mar<Feb (-), Apr>Mar (+) → 2/3 months positive
    assert positive_months_pct(eq) == 2 / 3 * 100.0


def test_avg_duration_carve_out_excludes_tsmom_and_scalp() -> None:
    trades = [
        ClosedTrade(T0, T0 + timedelta(hours=2), Decimal("1"), "TREND"),       # 2h — in band
        ClosedTrade(T0, T0 + timedelta(days=90), Decimal("1"), "TSMOM"),       # excluded
        ClosedTrade(T0, T0 + timedelta(minutes=10), Decimal("1"), "MOMENTUM_SCALP"),  # excluded
    ]
    m = compute_metrics(trades=trades, equity_curve=_eq([100, 101, 102]),
                        rollover_marks=(), spx_closes={}, periods_per_year=252)
    # the §14 band metric sees ONLY the 2h TREND trade
    assert m.avg_trade_duration_s == 2 * 3600
    # TSMOM + scalp are surfaced separately, never folded in
    assert m.tsmom_avg_duration_s == 90 * 86400
    assert m.scalp_avg_duration_s == 10 * 60


def test_var_breach_frequency() -> None:
    """GAP-0103: the observed 1-day VaR breach rate. 3 of 100 days exceed a 1%
    VaR ⇒ 0.03 (a well-calibrated 1% VaR would sit near 0.01)."""
    losses = [0.2] * 97 + [1.5, 2.0, 1.1]          # 3 days breach the 1% VaR
    assert var_breach_frequency(losses, var_pct=1.0) == pytest.approx(0.03)
    assert var_breach_frequency([], var_pct=1.0) == 0.0            # NaN-safe


def test_rolling_var_breach_rate_is_kupiec_backtest() -> None:
    """GAP-P11E-01/P11I-08: the expanding-window delta-normal VaR backtest — a real
    rate, never a 0.0 stub. A calm history followed by a one-off crash day breaches
    (the crash loss exceeds the z·σ VaR forecast built from the calm prior days);
    a perfectly flat record has zero variance ⇒ no VaR ⇒ vacuously no breach."""
    # 40 small alternating returns (non-zero σ) then one −10% crash day
    calm = [0.001 * (1 if i % 2 else -1) for i in range(40)]
    rate = rolling_var_breach_rate(calm + [-0.10])
    assert rate > 0.0                                   # the crash day breached
    assert rate < 0.10                                  # but only one of ~39 days
    assert rolling_var_breach_rate([0.0] * 40) == 0.0   # zero-variance ⇒ no breach
    assert rolling_var_breach_rate([0.01]) == 0.0       # <3 returns ⇒ 0.0 (NaN-safe)


# -- walk-forward folds ------------------------------------------------------- #

def test_generate_folds_rolling() -> None:
    folds = generate_folds(
        period_start=T0, period_end=T0 + timedelta(days=365),
        train_window=timedelta(days=180), test_window=timedelta(days=30),
        step=timedelta(days=30), embargo=timedelta(days=7))
    assert len(folds) >= 2
    assert folds[0].train_start == T0
    assert folds[0].test_start == folds[0].train_end + timedelta(days=7)   # embargo gap
    assert all(f.test_end <= T0 + timedelta(days=365) for f in folds)


def test_generate_folds_rejects_overlapping_oos() -> None:
    """GAP-P11E-06: a step smaller than the test window would replay overlapping
    out-of-sample periods and double-count them in the concatenated record —
    refused at construction, not silently double-counted."""
    with pytest.raises(ValueError, match="non-overlapping"):
        generate_folds(
            period_start=T0, period_end=T0 + timedelta(days=365),
            train_window=timedelta(days=180), test_window=timedelta(days=30),
            step=timedelta(days=15), embargo=timedelta(days=7))   # step < test_window


# -- grader honesty guards ---------------------------------------------------- #

def _block(**over) -> MetricBlock:
    base = dict(annual_sharpe=2.0, max_drawdown_pct=8.0, win_rate=0.55,
                profit_factor=1.8, positive_months_pct=80.0, spx_correlation=0.10,
                avg_trade_duration_s=3600.0, tsmom_avg_duration_s=0.0,
                scalp_avg_duration_s=0.0, n_trades=200)
    base.update(over)
    return MetricBlock(**base)


def _report(**over):
    two_years = (T0, T0 + timedelta(days=int(365.25 * 2) + 1))
    base = dict(account="dev_paper", period=two_years, n_folds=3,
                in_sample=_block(), out_of_sample=_block(), per_regime={},
                guardrail_hash=GH, expected_guardrail_hash=GH,
                var_breach_frequency=0.0, rule_violations=[], fidelity_caveats=["tick"],
                trial_count=12, deflated_sharpe=0.97)
    base.update(over)
    return build_report(**base)


def test_passing_report_passes() -> None:
    assert _report().passed is True


def test_deflated_sharpe_below_095_cannot_pass() -> None:
    """GAP-P12D-16 (owner-ratified): every §14 metric passes, but the Sharpe does not
    survive the correction for the trials behind it."""
    r = _report(deflated_sharpe=0.94)
    assert all(r.targets_met.values()) and r.passed is False
    assert _report(deflated_sharpe=0.95).passed is True
    assert _report(deflated_sharpe=float("nan")).passed is False       # no Sharpe at all


def test_unrecorded_trials_cannot_pass() -> None:
    """Fewer than 2 trials means the selection went unrecorded, so the DSR corrects nothing."""
    assert _report(trial_count=1).passed is False
    r = _report()
    kwargs = dict(account=r.account, period=r.period, n_folds=3, in_sample=r.in_sample,
                  out_of_sample=r.out_of_sample, per_regime={}, guardrail_hash=GH,
                  expected_guardrail_hash=GH, var_breach_frequency=0.0, rule_violations=[],
                  fidelity_caveats=["tick"])
    assert build_report(**kwargs).passed is False                       # the defaults cannot pass


def test_single_fold_cannot_pass() -> None:
    assert _report(n_folds=1).passed is False                 # C-BT-2


def test_under_two_years_cannot_pass() -> None:
    short = (T0, T0 + timedelta(days=365))
    assert _report(period=short).passed is False


def test_thin_sample_cannot_pass() -> None:
    """GAP-P11I-07: a stellar block with too few trades (one lucky PF=+inf trade)
    cannot clear §14 — the ≥30-trade floor makes the sample statistically real."""
    r = _report(out_of_sample=_block(n_trades=5))
    assert all(r.targets_met.values())                        # every metric "passes"
    assert r.passed is False                                  # …but the sample is thin


def test_rule_violation_forces_fail() -> None:
    assert _report(rule_violations=["news_trade_in_blackout"]).passed is False  # C-BT-7


def test_guardrail_hash_mismatch_invalidates() -> None:
    assert _report(guardrail_hash="TAMPERED", expected_guardrail_hash=GH).passed is False  # C-BT-4


def test_grader_uses_out_of_sample_only() -> None:
    """C-BT-1: a stellar in-sample block cannot rescue a failing out-of-sample."""
    r = _report(in_sample=_block(annual_sharpe=9.0),
                out_of_sample=_block(annual_sharpe=0.5))     # OOS fails Sharpe
    assert r.targets_met["annual_sharpe"] is False
    assert r.passed is False


def test_duration_carve_out_does_not_sink_the_grade() -> None:
    """C-BT-8: a TSMOM-heavy run (huge tsmom_avg_duration) still passes avg-duration
    because the §14 band metric excludes it."""
    r = _report(out_of_sample=_block(avg_trade_duration_s=3600.0,
                                     tsmom_avg_duration_s=200 * 86400))
    assert r.targets_met["avg_duration"] is True
    assert r.passed is True


def test_grade_maps_every_metric() -> None:
    tm = grade_out_of_sample(_block())
    assert set(tm) == {"annual_sharpe", "max_drawdown", "win_rate", "profit_factor",
                       "positive_months", "spx_correlation", "avg_duration"}
