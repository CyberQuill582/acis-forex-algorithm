"""§14 performance metrics (ACIS-09 §3/§4, master §14).

NaN-safe, Decimal PnL at the accounting boundary (F17/C-BT-6). The avg-duration
metric EXCLUDES TSMOM (GAP-0055) and MOMENTUM_SCALP (GAP-0009) — both multi-scale
by design — and reports them separately (C-BT-8); folding them into the 30min–48h
band would be dishonest. Metrics never reach the §14 grader except through a
`MetricBlock`; the grader consumes only the out-of-sample block (C-BT-1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence

# strategies excluded from the §14 avg-duration band (reported separately)
_DURATION_CARVE_OUT = frozenset({"TSMOM", "MOMENTUM_SCALP"})


@dataclass(frozen=True)
class ClosedTrade:
    entry_ts: datetime
    exit_ts: datetime
    pnl: Decimal                 # realised, account currency (Decimal, F17)
    strategy_type: str

    @property
    def duration_s(self) -> float:
        return (self.exit_ts - self.entry_ts).total_seconds()


@dataclass(frozen=True)
class MetricBlock:
    annual_sharpe: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    positive_months_pct: float
    spx_correlation: float
    avg_trade_duration_s: float          # excludes TSMOM + MOMENTUM_SCALP (§14)
    tsmom_avg_duration_s: float          # reported separately (GAP-0055)
    scalp_avg_duration_s: float          # reported separately (GAP-0009)
    n_trades: int

    def as_dict(self) -> dict:
        return {k: (v if math.isfinite(v) else None) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


def _returns_from_equity(equity: Sequence[tuple[datetime, Decimal]]) -> list[float]:
    out: list[float] = []
    for (_, e0), (_, e1) in zip(equity, equity[1:]):
        f0 = float(e0)
        if f0 == 0.0:
            out.append(0.0)
        else:
            out.append((float(e1) - f0) / abs(f0))
    return out


def annual_sharpe(returns: Sequence[float], periods_per_year: float) -> float:
    """Mean/std of period returns, annualised. Zero/degenerate variance → 0.0
    (never a spurious infinity that could flatter the grade).

    DECLARED DEVIATION (GAP-P11E-05, §5.6): this is the rf=0 form (mean raw
    return / std), not the textbook mean-EXCESS-return / std. It slightly
    over-states Sharpe vs a positive risk-free rate; declared here so the name
    does not imply an excess-return computation it does not do (§16 naming law).
    A non-zero rf is a per-day-rate input the phase-11 data-ops loader supplies
    when live; until then rf=0 is the stated assumption."""
    r = [x for x in returns if math.isfinite(x)]
    if len(r) < 2:
        return 0.0
    mean = sum(r) / len(r)
    var = sum((x - mean) ** 2 for x in r) / (len(r) - 1)
    sd = math.sqrt(var)
    if sd == 0.0:
        return 0.0
    return (mean / sd) * math.sqrt(periods_per_year)


def max_drawdown_pct(equity: Sequence[tuple[datetime, Decimal]]) -> float:
    """Worst peak-to-trough as a POSITIVE percent of the running peak."""
    peak = None
    worst = 0.0
    for _, e in equity:
        f = float(e)
        if peak is None or f > peak:
            peak = f
        if peak and peak > 0:
            dd = (peak - f) / peak * 100.0
            worst = max(worst, dd)
    return worst


def win_rate(trades: Sequence[ClosedTrade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades)


def profit_factor(trades: Sequence[ClosedTrade]) -> float:
    gross_win = sum((float(t.pnl) for t in trades if t.pnl > 0), 0.0)
    gross_loss = -sum((float(t.pnl) for t in trades if t.pnl < 0), 0.0)
    if gross_loss == 0.0:
        return float("inf") if gross_win > 0 else 0.0
    return gross_win / gross_loss


def positive_months_pct(equity: Sequence[tuple[datetime, Decimal]]) -> float:
    """Fraction of calendar months whose end-equity exceeds the prior month's."""
    by_month: dict[tuple[int, int], Decimal] = {}
    for ts, e in equity:
        by_month[(ts.year, ts.month)] = e            # last obs of the month wins
    months = [by_month[k] for k in sorted(by_month)]
    if len(months) < 2:
        return 0.0
    pos = sum(1 for a, b in zip(months, months[1:]) if b > a)
    return pos / (len(months) - 1) * 100.0


def spx_correlation(returns: Sequence[float], spx_returns: Sequence[float]) -> float:
    """Pearson correlation of aligned period returns. Degenerate variance → 0.0
    (no spurious correlation from a flat series)."""
    n = min(len(returns), len(spx_returns))
    a = [returns[i] for i in range(n) if math.isfinite(returns[i]) and math.isfinite(spx_returns[i])]
    b = [spx_returns[i] for i in range(n) if math.isfinite(returns[i]) and math.isfinite(spx_returns[i])]
    if len(a) < 2:
        return 0.0
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0.0 or vb == 0.0:
        return 0.0
    return cov / math.sqrt(va * vb)


def _avg_duration(trades: Sequence[ClosedTrade], *, include: bool,
                  only: str | None = None) -> float:
    if only is not None:
        sel = [t for t in trades if t.strategy_type == only]
    elif include:
        sel = [t for t in trades if t.strategy_type not in _DURATION_CARVE_OUT]
    else:
        sel = list(trades)
    if not sel:
        return 0.0
    return sum(t.duration_s for t in sel) / len(sel)


def var_breach_frequency(daily_losses_pct: Sequence[float], var_pct: float) -> float:
    """Fixed-threshold exceedance rate: the fraction of days whose realised loss
    (POSITIVE % of NAV) exceeded a single VaR estimate `var_pct`. NaN-safe."""
    days = [x for x in daily_losses_pct if math.isfinite(x)]
    if not days:
        return 0.0
    return sum(1 for x in days if x > var_pct) / len(days)


# z(0.99) — the one-tailed 99% normal quantile (matches the Risk Monitor's VaR)
_Z_99 = 2.326


def rolling_var_breach_rate(returns: Sequence[float], *, z: float = _Z_99) -> float:
    """GAP-0103 / GAP-P11E-01 (Kupiec POF backtest): the observed 1-day 1% VaR
    EXCEEDANCE RATE over the out-of-sample record. For each day t, the delta-normal
    1% VaR is forecast from the EXPANDING history of prior returns
    (VaR_t = z·σ_{<t}); a breach is a realised loss exceeding VaR_t. Returns the
    breach fraction — a well-calibrated 1% VaR breaches on ~1% of days (the
    "binding frequency" the owner deferred to phase 11 to report).

    This is a RATE (referent: the 1% confidence LEVEL), a distinct quantity from
    the 3%-of-NAV `var_cap_pct` MAGNITUDE ceiling the Risk Monitor enforces live
    — the two are never conflated. NaN-safe; <3 returns ⇒ 0.0."""
    r = [x for x in returns if math.isfinite(x)]
    if len(r) < 3:
        return 0.0
    breaches = days = 0
    for t in range(2, len(r)):
        hist = r[:t]
        mean = sum(hist) / len(hist)
        var_h = sum((x - mean) ** 2 for x in hist) / (len(hist) - 1)
        sd = math.sqrt(var_h)
        var_forecast = z * sd                         # 1% VaR magnitude (loss side)
        if -r[t] > var_forecast:                      # realised loss exceeded VaR
            breaches += 1
        days += 1
    return breaches / days if days else 0.0


def compute_metrics(*, trades: Sequence[ClosedTrade],
                    equity_curve: Sequence[tuple[datetime, Decimal]],
                    spx_returns: Sequence[float],
                    periods_per_year: float,
                    max_drawdown_pct_override: float | None = None) -> MetricBlock:
    """`max_drawdown_pct_override` (GAP-P11I-04): when the caller has measured the
    drawdown off a finer INTRADAY high-water than the daily `equity_curve`, it
    passes that (more conservative, never-understated) figure here; the daily
    curve still drives the return-based metrics. Absent an override the drawdown
    falls back to the daily curve (single-observation callers, tests)."""
    returns = _returns_from_equity(equity_curve)
    dd = (max_drawdown_pct_override if max_drawdown_pct_override is not None
          else max_drawdown_pct(equity_curve))
    return MetricBlock(
        annual_sharpe=annual_sharpe(returns, periods_per_year),
        max_drawdown_pct=dd,
        win_rate=win_rate(trades),
        profit_factor=profit_factor(trades),
        positive_months_pct=positive_months_pct(equity_curve),
        spx_correlation=spx_correlation(returns, spx_returns),
        avg_trade_duration_s=_avg_duration(trades, include=True),        # §14 band
        tsmom_avg_duration_s=_avg_duration(trades, include=False, only="TSMOM"),
        scalp_avg_duration_s=_avg_duration(trades, include=False, only="MOMENTUM_SCALP"),
        n_trades=len(trades))
