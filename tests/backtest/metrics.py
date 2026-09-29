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
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping, Sequence

# strategies excluded from the §14 avg-duration band (reported separately)
_DURATION_CARVE_OUT = frozenset({"TSMOM", "MOMENTUM_SCALP"})


@dataclass(frozen=True)
class ClosedTrade:
    entry_ts: datetime
    exit_ts: datetime
    pnl: Decimal                 # realised, account currency (Decimal, F17)
    strategy_type: str
    notional_usd: Decimal | None = None   # entry value in USD: pnl / notional is the trade's return
    regime: str | None = None             # the regime ACTIVE at entry (GAP-P12D-31 attribution)
    friction: Decimal = Decimal("0")      # C8 cost charged, account currency (pnl = gross - friction + carry)
    carry: Decimal = Decimal("0")         # financing booked, account currency (R11I-01)

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

    DECLARED DEVIATIONS (§5.6, §16 naming law):
    (1) GAP-P11E-05 — the rf=0 form (mean raw return / std), not textbook
        mean-EXCESS-return / std; slightly over-states Sharpe vs a positive rf. A
        non-zero rf is a per-day-rate the data-ops loader supplies when live.
    (2) GAP-SP12E-02 — this is the naïve iid √periods_per_year annualisation. Per
        Lo (2002, *The Statistics of Sharpe Ratios*) serial correlation can
        overstate an annualised Sharpe "by as much as 65 percent"; ACIS's flagship
        trend/momentum returns are positively autocorrelated at the daily scale
        within trends — exactly the sign that makes √252 OVERSTATE. This bias lands
        on the §14 Sharpe>1.5 live-gate, so a pass must be read with that in mind.
        Whether to apply the Lo autocorrelation correction (vs report raw + this
        caveat) is an owner decision raised at the spec audit; until ratified, the
        raw √t figure carries this declared caveat, never presented as unbiased."""
    r = [x for x in returns if math.isfinite(x)]
    if len(r) < 2:
        return 0.0
    # GAP-P12D-17: fsum keeps a constant series exactly constant — a plain sum of 50 × 0.01
    # left float dust, sd ≈ 1e-18 and an annual Sharpe of 4.5e16 that cleared §14's > 1.5
    mean = math.fsum(r) / len(r)
    var = math.fsum((x - mean) ** 2 for x in r) / (len(r) - 1)
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


def spx_correlation(marks: Sequence[tuple[date, Decimal]],
                    spx_closes: Mapping[date, float]) -> float:
    """Pearson correlation of strategy and S&P 500 returns over the SAME date intervals
    (GAP-SP12E-06: the old positional zip, which silently paired mismatched days, is gone).

    `marks` is equity marked at each 17:00-New-York rollover, labelled by its New York date
    (`rollover_marks.py`); `spx_closes` maps a date to the index close. Each pair of
    consecutive SPX session dates (p, d) with an equity mark on both gives one sample,
    (equity[d]/equity[p] - 1, close[d]/close[p] - 1). A US holiday or an FX-only day
    therefore never pairs different days; the FX return simply spans the same p → d.
    DECLARED DEVIATION: the FX mark is taken at 17:00 New York, one hour after the 16:00
    SPX close. Fewer than 3 joined samples ⇒ NaN, which FAILS the §14 gate (NaN < 0.25 is
    False), so missing data can never clear it. Zero variance ⇒ 0.0 (a flat series has no
    correlation)."""
    eq = {d: float(v) for d, v in marks}
    days = sorted(d for d, c in spx_closes.items() if math.isfinite(c) and c > 0)
    a: list[float] = []
    b: list[float] = []
    for p, d in zip(days, days[1:]):
        if p in eq and d in eq and eq[p] != 0.0:
            a.append(eq[d] / eq[p] - 1.0)
            b.append(spx_closes[d] / spx_closes[p] - 1.0)
    if len(a) < 3:
        return math.nan
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0.0 or vb == 0.0:
        return 0.0
    return cov / math.sqrt(va * vb)


def _avg_duration(trades: Sequence[ClosedTrade], *, only: str | None = None) -> float:
    """Mean duration of `only`'s trades or, with no `only`, of the §14 band (all but the TSMOM and
    MOMENTUM_SCALP carve-outs). An EMPTY population has no mean: NaN, never the 0.0 a zero-duration
    population gives; reading an empty carve-out's 0.0 as zero-duration trades was GAP-P12D-38.
    (An empty band fails §14 either way; an unreachable branch went in GAP-P12D-28.)"""
    if only is not None:
        sel = [t for t in trades if t.strategy_type == only]
    else:
        sel = [t for t in trades if t.strategy_type not in _DURATION_CARVE_OUT]
    if not sel:
        return math.nan
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
    """GAP-0103 / GAP-P11E-01: the observed 1-day 1% VaR EXCEEDANCE RATE over the
    out-of-sample record. For each day t, the delta-normal 1% VaR is forecast from
    the EXPANDING history of prior returns (VaR_t = z·σ_{<t}); a breach is a
    realised loss exceeding VaR_t. Returns the breach fraction — a well-calibrated
    1% VaR breaches on ~1% of days (the "binding frequency" the owner deferred to
    phase 11 to report).

    NOTE (GAP-SP12E-04, §16 naming law): this is the exceedance RATE — the INPUT to
    a Kupiec POF test, NOT the test itself. It computes no likelihood-ratio
    statistic and makes no χ²₁ accept/reject decision, so it must never be called a
    "Kupiec backtest": with a short record even a badly-miscalibrated VaR can show a
    rate near 1% by luck. The real Kupiec LR_POF significance test is a go-live add
    for the operational-referent VaR check (GAP-SP12E-05). This RATE (referent: the
    1% confidence LEVEL) is a distinct quantity from the 3%-of-NAV `var_cap_pct`
    MAGNITUDE ceiling the Risk Monitor enforces live — the two are never conflated.
    NaN-safe; <3 returns ⇒ 0.0."""
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
                    rollover_marks: Sequence[tuple[date, Decimal]],
                    spx_closes: Mapping[date, float],
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
        spx_correlation=spx_correlation(rollover_marks, spx_closes),
        avg_trade_duration_s=_avg_duration(trades),                      # §14 band
        tsmom_avg_duration_s=_avg_duration(trades, only="TSMOM"),
        scalp_avg_duration_s=_avg_duration(trades, only="MOMENTUM_SCALP"),
        n_trades=len(trades))


# --------------------------------------------------------------------------- #
# attribution slices (GAP-P12D-31) — which regime / strategy made or lost the money
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SliceStats:
    """Trade-level attribution for ONE regime or strategy. NOT a `MetricBlock`: a subset of
    trades has no continuous equity curve, so no Sharpe, drawdown or positive months (the
    fabrication GAP-P11E-02 forbids). `avg_duration_s` covers every trade (no §14 carve-out).
    net = direction - friction + carry, each summed exactly (R11I-01)."""
    n_trades: int
    net_pnl: Decimal
    win_rate: float
    profit_factor: float
    avg_duration_s: float
    gross_win: Decimal
    gross_loss: Decimal
    friction: Decimal = Decimal("0")     # the C8 cost charged, account currency
    carry: Decimal = Decimal("0")        # financing booked, account currency


def slice_stats(trades: Sequence[ClosedTrade]) -> SliceStats:
    wins, losses = [t.pnl for t in trades if t.pnl > 0], [-t.pnl for t in trades if t.pnl < 0]
    durations = [t.duration_s for t in trades]
    return SliceStats(
        n_trades=len(trades), net_pnl=sum((t.pnl for t in trades), Decimal("0")),
        win_rate=win_rate(trades), profit_factor=profit_factor(trades),
        avg_duration_s=sum(durations) / len(durations) if durations else 0.0,
        gross_win=sum(wins, Decimal("0")), gross_loss=sum(losses, Decimal("0")),
        friction=sum((t.friction for t in trades), Decimal("0")),
        carry=sum((t.carry for t in trades), Decimal("0")))


def slice_by(trades: Sequence[ClosedTrade], key: str) -> dict[str, SliceStats]:
    """Group closed trades by `key` ("regime" or "strategy_type"). A trade whose key is
    missing groups under UNATTRIBUTED, so a hole in attribution is VISIBLE in the report
    instead of silently dropping trades out of the breakdown."""
    buckets: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        buckets.setdefault(getattr(t, key) or "UNATTRIBUTED", []).append(t)
    return {k: slice_stats(v) for k, v in sorted(buckets.items())}
