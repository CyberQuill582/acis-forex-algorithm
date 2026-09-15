"""Hand-worked values and boundaries for the §14 metrics (GAP-P12D-28 mutation-gate triage).

Each number is worked in the comment beside it, so a changed operator, divisor or
comparison changes a result."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.backtest.metrics import (ClosedTrade, _returns_from_equity, annual_sharpe,
                                    compute_metrics, max_drawdown_pct, positive_months_pct,
                                    profit_factor, rolling_var_breach_rate, spx_correlation,
                                    var_breach_frequency, win_rate)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _eq(vals):
    return [(T0 + timedelta(days=i), Decimal(str(v))) for i, v in enumerate(vals)]


def _trade(pnl: str, strategy: str = "TREND") -> ClosedTrade:
    return ClosedTrade(T0, T0 + timedelta(hours=1), Decimal(pnl), strategy)


def test_annual_sharpe_hand_worked() -> None:
    # [0.01, 0.03]: mean 0.02, SAMPLE variance 0.0002, sd 0.0141421 -> 1.41421 · sqrt(4) = 2.82843
    assert annual_sharpe([0.01, 0.03], 4) == pytest.approx(2 * math.sqrt(2))
    assert annual_sharpe([0.01, math.nan, 0.03], 4) == pytest.approx(2 * math.sqrt(2))


def test_returns_from_equity_use_the_absolute_prior_and_skip_a_zero_base() -> None:
    # -100 -> -50: (-50 + 100) / 100 = 0.5 ; -50 -> 0: 50 / 50 = 1.0 ; 0 -> 10: zero base -> 0.0
    assert _returns_from_equity(_eq([-100, -50, 0, 10])) == pytest.approx([0.5, 1.0, 0.0])


def test_compute_metrics_sharpe_comes_from_equity_returns() -> None:
    # 100 110 99 108.9 -> returns 0.1 -0.1 0.1: mean 1/30, sample var 0.013333, sd 0.11547
    # -> Sharpe (1/30) / 0.11547 = 0.288675 at one period a year
    m = compute_metrics(trades=[], equity_curve=_eq([100, 110, 99, 108.9]), rollover_marks=(),
                        spx_closes={}, periods_per_year=1)
    assert m.annual_sharpe == pytest.approx(0.288675, abs=1e-6)


def test_drawdown_ignores_non_positive_peaks() -> None:
    assert max_drawdown_pct(_eq([0, 10, 5])) == 50.0          # the zero start is no peak
    assert max_drawdown_pct(_eq([-10, -20])) == 0.0
    assert max_drawdown_pct(_eq([100, 100, 100])) == 0.0


def test_drawdown_override_wins_even_at_zero() -> None:
    kw = dict(trades=[], equity_curve=_eq([100, 120, 90]), rollover_marks=(), spx_closes={},
              periods_per_year=252)
    assert compute_metrics(**kw).max_drawdown_pct == 25.0
    assert compute_metrics(**kw, max_drawdown_pct_override=31.5).max_drawdown_pct == 31.5
    assert compute_metrics(**kw, max_drawdown_pct_override=0.0).max_drawdown_pct == 0.0


def test_flat_trades_are_neither_wins_nor_losses() -> None:
    trades = [_trade("100"), _trade("0"), _trade("-50")]
    assert win_rate(trades) == 1 / 3
    assert profit_factor(trades) == 2.0
    assert profit_factor([_trade("10"), _trade("0")]) == math.inf
    assert profit_factor([_trade("0")]) == 0.0


def test_positive_months_take_each_months_last_mark_and_need_a_strict_rise() -> None:
    eq = [(datetime(2026, 1, 1, tzinfo=timezone.utc), Decimal("100")),
          (datetime(2026, 1, 31, tzinfo=timezone.utc), Decimal("90")),   # January closes at 90
          (datetime(2026, 2, 27, tzinfo=timezone.utc), Decimal("95"))]   # 95 > 90: positive
    assert positive_months_pct(eq) == 100.0
    flat = [(datetime(2026, m, 5, tzinfo=timezone.utc), Decimal("100")) for m in (1, 2)]
    assert positive_months_pct(flat) == 0.0
    assert positive_months_pct(flat[:1]) == 0.0


def test_var_breach_frequency_counts_strict_exceedances_of_finite_days() -> None:
    assert var_breach_frequency([1.0, 1.5, math.nan], var_pct=1.0) == 0.5


DAYS = [date(2025, 1, d) for d in (6, 7, 8, 9, 10)]
SPX = dict(zip(DAYS, [100.0, 110.0, 99.0, 108.9, 98.01]))           # +10% -10% +10% -10%
EQUITY = [Decimal(v) for v in ("100", "90", "99", "89.1", "98.01")]   # -10% +10% -10% +10%


def test_spx_correlation_hand_worked_opposite_moves() -> None:
    assert spx_correlation(list(zip(DAYS, EQUITY)), SPX) == pytest.approx(-1.0)


def test_spx_correlation_skips_a_zero_equity_base_and_needs_three_samples() -> None:
    zero_first = [(DAYS[0], Decimal("0"))] + list(zip(DAYS[1:], EQUITY[1:]))
    assert spx_correlation(zero_first, SPX) == pytest.approx(-1.0)          # 0 -> 90 skipped, 3 left
    assert math.isnan(spx_correlation(zero_first[:4], {d: SPX[d] for d in DAYS[:4]}))   # 2 left
    assert spx_correlation([(d, Decimal("100")) for d in DAYS], SPX) == 0.0  # flat equity
    bad_close = {**SPX, DAYS[2]: 0.0}                                     # a non-positive close is no session
    # samples 6->7, 7->9, 9->10 in percent: equity -10 -1 +10, SPX +10 -1 -10; means -1/3
    # cov (-29/3)(31/3) + (-2/3)(-2/3) + (31/3)(-29/3) = -1794/9 ; each variance (841+4+961)/9 = 1806/9
    assert spx_correlation(list(zip(DAYS, EQUITY)), bad_close) == pytest.approx(-1794 / 1806)


def test_rolling_var_breach_rate_hand_worked() -> None:
    # day 2: history [0.01, -0.01], sd 0.0141421, VaR 2.326 · sd = 0.032896; loss 0.05 breaches
    # day 3: history [0.01, -0.01, -0.05], sd 0.030551, VaR 0.07106; a flat day does not
    returns = [0.01, -0.01, -0.05, 0.0]
    assert rolling_var_breach_rate(returns) == 0.5
    assert rolling_var_breach_rate(returns, z=10.0) == 0.0     # VaR 0.1414 at day 2: no breach
    assert rolling_var_breach_rate([0.01, -0.01, math.nan, -0.05]) == 1.0   # NaN dropped first
    # a 4% loss breaches the 2.326σ VaR (0.0329) but not a 3.326σ one (0.0470): the z is the 99% quantile
    assert rolling_var_breach_rate([0.01, -0.01, -0.04]) == 1.0


def test_drawdown_counts_a_peak_below_one_unit() -> None:
    assert max_drawdown_pct(_eq([1, 0.5])) == 50.0


def test_trades_under_one_unit_still_count() -> None:
    assert win_rate([_trade("0.5")]) == 1.0
    assert profit_factor([_trade("0.5"), _trade("-1")]) == 0.5
    assert profit_factor([_trade("2"), _trade("0.5"), _trade("-1")]) == 2.5   # a small win is no loss
    assert profit_factor([_trade("0.5")]) == math.inf


def test_spx_correlation_takes_closes_below_one_and_a_flat_index() -> None:
    small = {d: v / 200 for d, v in SPX.items()}                         # the same moves at 0.5-scale levels
    assert spx_correlation(list(zip(DAYS, EQUITY)), small) == pytest.approx(-1.0)
    assert spx_correlation(list(zip(DAYS, EQUITY)), {d: 5000.0 for d in DAYS}) == 0.0   # flat index


def test_duration_averages_hand_worked() -> None:
    trades = [ClosedTrade(T0, T0 + timedelta(hours=1), Decimal("1"), "TREND"),
              ClosedTrade(T0, T0 + timedelta(hours=3), Decimal("1"), "BREAKOUT")]
    m = compute_metrics(trades=trades, equity_curve=_eq([100, 101]), rollover_marks=(), spx_closes={},
                        periods_per_year=252)
    assert m.avg_trade_duration_s == 2 * 3600                          # (1 h + 3 h) / 2
    assert m.tsmom_avg_duration_s == 0.0 and m.scalp_avg_duration_s == 0.0   # none of either


def test_rolling_var_breach_rate_second_breach_and_divisors() -> None:
    # day 3 history [0.01, -0.01, -0.05]: mean -1/60, sample sd 0.030551, VaR 0.07106: an 8% loss breaches
    assert rolling_var_breach_rate([0.01, -0.01, -0.05, -0.08]) == 1.0       # two breaches in two days
    # day 2: sample sd 0.0141421 over [0.01, -0.01], VaR 0.032896: a 2.5% loss stays inside
    assert rolling_var_breach_rate([0.01, -0.01, -0.025]) == 0.0


def test_records_are_frozen_and_a_trade_has_no_notional_unless_given() -> None:
    t = _trade("1")
    assert t.notional_usd is None
    with pytest.raises(AttributeError):
        t.pnl = Decimal("2")
    m = compute_metrics(trades=[], equity_curve=_eq([100, 101]), rollover_marks=(), spx_closes={},
                        periods_per_year=252)
    with pytest.raises(AttributeError):
        m.n_trades = 5
