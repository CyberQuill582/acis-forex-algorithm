"""Walk-forward honesty additions: the embargo (GAP-SP12E-03) and the date-joined SPX
correlation with its rollover marks (GAP-SP12E-06)."""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.backtest.harness import Backtest, FoldData
from tests.backtest.metrics import MetricBlock, spx_correlation
from tests.backtest.report import grade_out_of_sample
from tests.backtest.rollover_marks import RolloverMarker
from tests.backtest.test_harness_regressions import _FakeLoop, _ms, _noop
from tests.backtest.walk_forward import Fold, generate_folds
from tests.optimizer_fixtures import TEST_COSTS

UTC = timezone.utc
T0 = datetime(2025, 1, 6, tzinfo=UTC)


# ------------------------------- embargo ------------------------------- #

def test_generate_folds_leaves_the_embargo_gap() -> None:
    folds = generate_folds(period_start=T0, period_end=T0 + timedelta(days=400),
                           train_window=timedelta(days=120), test_window=timedelta(days=60),
                           step=timedelta(days=60), embargo=timedelta(days=7))
    assert folds and all(f.test_start - f.train_end == timedelta(days=7) for f in folds)
    with pytest.raises(ValueError, match="embargo"):
        generate_folds(period_start=T0, period_end=T0 + timedelta(days=400),
                       train_window=timedelta(days=120), test_window=timedelta(days=60),
                       step=timedelta(days=60), embargo=timedelta(days=-1))


def test_harness_refuses_a_fold_shorter_than_the_max_hold() -> None:
    train_end = datetime(2025, 1, 7, 10, tzinfo=UTC)

    def fold(first_test: datetime) -> list[FoldData]:
        return [FoldData(Fold(0, train_end - timedelta(days=730), train_end, first_test,
                              first_test + timedelta(days=1)), [_ms(first_test, 1.10)])]

    bt = Backtest(account="acc", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=3600)
    with pytest.raises(ValueError, match="embargo"):           # 30 min < the 1 h max hold
        bt.run(loop=_FakeLoop({}), folds=fold(train_end + timedelta(minutes=30)), evolve_fn=_noop,
               spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")
    Backtest(account="acc", cost_models={"EUR_USD": TEST_COSTS}, max_hold_s=3600).run(
        loop=_FakeLoop({}), folds=fold(train_end + timedelta(hours=2)), evolve_fn=_noop,
        spx_closes={}, guardrail_hash="GH", expected_guardrail_hash="GH")


# --------------------------- date-joined SPX --------------------------- #

def _weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_spx_correlation_joins_by_date_across_a_us_holiday() -> None:
    """FX marks every weekday, including 4 July 2025 when the index is closed. The FX
    equity moves exactly with the index on index days and jumps on the holiday; the date
    join spans 3 → 7 July for both series, so the correlation is exactly 1. A positional
    zip would pair the holiday with the wrong day from there on."""
    rng = random.Random(4)
    fx_days = _weekdays(date(2025, 6, 2), 60)
    spx_days = [d for d in fx_days if d != date(2025, 7, 4)]
    closes, level = {}, 5000.0
    for d in spx_days:
        level *= 1 + rng.gauss(0, 0.01)
        closes[d] = level
    marks = [(d, Decimal(str(closes[d] * 2)) if d in closes else Decimal("123.0")) for d in fx_days]
    assert spx_correlation(marks, closes) == pytest.approx(1.0)


def test_too_little_overlap_is_nan_and_fails_the_gate() -> None:
    marks = [(date(2025, 1, d), Decimal("100")) for d in (6, 7, 8)]
    closes = {date(2025, 2, d): 5000.0 + d for d in (3, 4, 5, 6)}
    corr = spx_correlation(marks, closes)
    assert math.isnan(corr)
    block = MetricBlock(annual_sharpe=2.0, max_drawdown_pct=5.0, win_rate=0.6, profit_factor=2.0,
                        positive_months_pct=80.0, spx_correlation=corr,
                        avg_trade_duration_s=3600.0, tsmom_avg_duration_s=0.0,
                        scalp_avg_duration_s=0.0, n_trades=50)
    assert grade_out_of_sample(block)["spx_correlation"] is False


def test_rollover_marks_follow_new_york_time_across_dst_and_weekends() -> None:
    summer = RolloverMarker()
    for ts, eq in [(datetime(2025, 7, 8, 20, 59, tzinfo=UTC), "100"),    # 16:59 EDT
                   (datetime(2025, 7, 8, 21, 1, tzinfo=UTC), "105")]:    # 17:01 EDT
        summer.observe(ts, Decimal(eq))
    assert summer.marks == [(date(2025, 7, 8), Decimal("100"))]          # 21:00 UTC in summer

    winter = RolloverMarker()
    for ts, eq in [
        (datetime(2025, 1, 7, 21, 30, tzinfo=UTC), "200"),    # 16:30 EST
        (datetime(2025, 1, 7, 21, 59, tzinfo=UTC), "201"),    # 16:59 EST — 21:00 UTC is not the boundary in winter
        (datetime(2025, 1, 7, 22, 0, 1, tzinfo=UTC), "210"),  # 17:00:01 EST -> mark 7 Jan = 201
        (datetime(2025, 1, 10, 21, 59, tzinfo=UTC), "300"),   # Friday 16:59 EST; crosses 8 Jan first -> mark 8 Jan = 210
        (datetime(2025, 1, 12, 22, 5, tzinfo=UTC), "310"),    # Sunday re-open -> mark 10 Jan = 300 (no Sunday mark)
        (datetime(2025, 1, 13, 22, 1, tzinfo=UTC), "320"),    # Monday 17:01 EST -> mark 13 Jan = 310
    ]:
        winter.observe(ts, Decimal(eq))
    assert winter.marks == [(date(2025, 1, 7), Decimal("201")), (date(2025, 1, 8), Decimal("210")),
                            (date(2025, 1, 10), Decimal("300")), (date(2025, 1, 13), Decimal("310"))]
