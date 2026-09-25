"""Fitness function + C9 expectancy gate (ACIS-03 §6.1–§6.3, master §5 C8/C9).

Deterministic mini-backtest of a decoded ParamSet over regime-labelled bars —
v1 evaluation harness: the canonical dual-EMA core (EMA cross + RSI filter +
ATR SL/TP + max-holding exit). Every fill pays the C8 CostModel. A gated-out
individual scores WORST_FITNESS = -1.0, strictly below the formula floor
(-0.2), so C9's "cannot win evolution" is arithmetic, not procedural.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from config.schemas import OptimizerConfig
from core.optimizer.costs import CostModel
from core.optimizer.param_types import LabelledBar, ParamSet

WORST_FITNESS = -1.0
E_R_REPORT_CAP = 10.0  # log-reporting cap when no losing trades exist
# GAP-0071: there is deliberately NO module ATR-period constant — the period
# is threaded from the ONE declared config value (signals.atr_period) by the
# caller, so fitness calibrates the SL/TP genes on the same ATR AGON spends
# them with. A divergence is unrepresentable, not a coincidence of literals.


# --------------------------------------------------------------------------- #
# indicators (stdlib, deterministic — phases 1–3 precedent)
# --------------------------------------------------------------------------- #

def ema_series(closes: Sequence[float], period: int) -> list[float]:
    k = 2.0 / (period + 1.0)
    out = [closes[0]]
    for c in closes[1:]:
        out.append(c * k + out[-1] * (1.0 - k))
    return out


def rsi_series(closes: Sequence[float], period: int) -> list[float]:
    """Wilder RSI; index i is the RSI at bar i (neutral 50 during warm-up)."""
    out = [50.0] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period, len(closes)):
        if i > period:
            d = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0.0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def atr_series(bars: Sequence[LabelledBar], period: int) -> list[float]:
    """Wilder ATR; index i is the ATR at bar i (0.0 during warm-up)."""
    out = [0.0] * len(bars)
    if len(bars) <= period:
        return out
    trs = []
    for i in range(1, len(bars)):
        b, prev_close = bars[i], bars[i - 1].close
        trs.append(max(b.high - b.low, abs(b.high - prev_close), abs(b.low - prev_close)))
    atr = sum(trs[:period]) / period
    out[period] = atr
    for i in range(period + 1, len(bars)):
        atr = (atr * (period - 1) + trs[i - 1]) / period
        out[i] = atr
    return out


# --------------------------------------------------------------------------- #
# mini-backtest (§6.1) — closed-trade net PnLs in price units (float scores;
# F17 Decimal applies to live accounting, not statistical ranking — §3 note)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Trade:
    """One mini-backtest trade in bar indices: WHEN each decision was taken, which a PnL list
    cannot show (the GAP-P12D-65 leakage suite compares decisions, not PnLs)."""
    signal_bar: int        # the bar whose close decided the entry
    direction: int         # +1 long, -1 short
    entry_price: float     # the fill: bars[signal_bar + 1].open
    exit_bar: int          # the bar the exit was decided on (the last bar when `marked`)
    exit_price: float
    pnl: float             # net of both sides' C8 cost
    # how it closed: "gap" (at the open, through the stop), "stop" / "target" (intrabar),
    # "hold" (max hold, at the close), "mark" (the window-end mark, GAP-0039: not a decision)
    exit_kind: str

    @property
    def marked(self) -> bool:
        return self.exit_kind == "mark"


def simulate_trades(
    params: ParamSet,
    bars: Sequence[LabelledBar],
    costs: CostModel,
    entry_start: int = 0,
    *,
    atr_period: int,
) -> list[float]:
    """Closed-trade net PnLs: the PnLs of `trade_path`, in exit order."""
    return [t.pnl for t in trade_path(params, bars, costs, entry_start, atr_period=atr_period)]


def trade_path(
    params: ParamSet,
    bars: Sequence[LabelledBar],
    costs: CostModel,
    entry_start: int = 0,
    *,
    atr_period: int,
) -> list[Trade]:
    """Every trade, in exit order. `entry_start` supports the §6.3 holdout: indicators
    warm up on the full window, but new entries are only permitted from that
    index on — no lookahead, and no artificial indicator starvation in the tail.
    `atr_period` is the declared signals.atr_period (GAP-0071)."""
    n = len(bars)
    warmup = max(params.ema_slow, params.rsi_period + 1, atr_period + 1, entry_start)
    if n <= warmup + 1:
        return []
    closes = [b.close for b in bars]
    ema_f = ema_series(closes, params.ema_fast)
    ema_s = ema_series(closes, params.ema_slow)
    rsi = rsi_series(closes, params.rsi_period)
    atr = atr_series(bars, atr_period)

    trades: list[Trade] = []
    direction = 0          # 0 flat, +1 long, -1 short
    entry_mid = sl = tp = 0.0
    entry_cost = 0.0
    signal_bar = bars_held = 0

    for i in range(warmup, n):
        bar = bars[i]
        if direction != 0:
            bars_held += 1
            exit_mid: float | None = None
            kind = ""
            # SL checked before TP on the same bar — conservative (§6.1). A bar that OPENS
            # through the stop fills at that open, the first price after the gap (T6,
            # GAP-P12D-65); a gap through the target still fills at the target, never better.
            if direction > 0:
                if bar.low <= sl:
                    exit_mid, kind = (bar.open, "gap") if bar.open < sl else (sl, "stop")
                elif bar.high >= tp:
                    exit_mid, kind = tp, "target"
            else:
                if bar.high >= sl:
                    exit_mid, kind = (bar.open, "gap") if bar.open > sl else (sl, "stop")
                elif bar.low <= tp:
                    exit_mid, kind = tp, "target"
            if exit_mid is None and bars_held >= params.max_holding_periods:
                exit_mid, kind = bar.close, "hold"
            if exit_mid is not None:
                # a fill at the open pays the latest spread known then, the prior bar's close
                # (X2, GAP-P12D-83): the gap bar's own closing spread is its future
                exit_spread = bars[i - 1].spread if kind == "gap" else bar.spread
                pnl = direction * (exit_mid - entry_mid) - entry_cost - costs.per_side_cost(exit_spread)
                trades.append(Trade(signal_bar, direction, entry_mid, i, exit_mid, pnl, kind))
                direction = 0
            continue
        if i + 1 >= n:
            break
        crossed_up = ema_f[i - 1] <= ema_s[i - 1] and ema_f[i] > ema_s[i]
        crossed_down = ema_f[i - 1] >= ema_s[i - 1] and ema_f[i] < ema_s[i]
        a = atr[i]
        if a <= 0.0:
            continue
        if crossed_up and rsi[i] < params.rsi_overbought:
            direction = 1
        elif crossed_down and rsi[i] > params.rsi_oversold:
            direction = -1
        else:
            continue
        entry_bar = bars[i + 1]
        entry_mid = entry_bar.open
        entry_cost = costs.per_side_cost(entry_bar.spread)
        sl = entry_mid - direction * params.atr_multiplier_sl * a
        tp = entry_mid + direction * params.atr_multiplier_tp * a
        signal_bar, bars_held = i, 0
    if direction != 0:
        # GAP-0039: mark-to-close — a position still open at the window end is
        # closed at the final bar's close, net of costs; every entered trade is
        # accounted, so end-of-window losers cannot silently vanish from E_R.
        last = bars[-1]
        pnl = direction * (last.close - entry_mid) - entry_cost - costs.per_side_cost(last.spread)
        trades.append(Trade(signal_bar, direction, entry_mid, n - 1, last.close, pnl, "mark"))
    return trades


# --------------------------------------------------------------------------- #
# C9 expectancy (§6.2 — the exact GAP-0006 contract)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ExpectancyResult:
    n_trades: int
    expectancy: float   # E = mean net PnL per closed trade
    e_r: float          # E / avgLoss (R-multiples); capped for reporting


def expectancy_r(pnls: Sequence[float]) -> ExpectancyResult:
    n = len(pnls)
    if n == 0 or any(not math.isfinite(p) for p in pnls):
        return ExpectancyResult(n, float("nan"), float("nan"))
    e = sum(pnls) / n
    losses = [-p for p in pnls if p < 0]
    if not losses:
        return ExpectancyResult(n, e, E_R_REPORT_CAP if e > 0 else float("nan"))
    avg_loss = sum(losses) / len(losses)
    return ExpectancyResult(n, e, e / avg_loss)


def passes_expectancy_gate(res: ExpectancyResult, min_trades: int, min_e_r: float) -> bool:
    if res.n_trades < min_trades:
        return False
    # NaN e_r (zero trades, NaN pnl, or no-loss-with-E<=0) fails: nan > x is False.
    return math.isfinite(res.e_r) and res.e_r > min_e_r


# --------------------------------------------------------------------------- #
# fitness components (§6.1 — each in [0,1], unit-tested)
# --------------------------------------------------------------------------- #

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def mean_sigma_component(pnls: Sequence[float]) -> float:
    """Per-trade mean/σ transform clamped to [0,1] — NOT an annualised Sharpe
    ratio (no time base, no risk-free rate). Renamed from `sharpe_component`
    under the §16 naming law (external-referent verification, GAP-0091)."""
    n = len(pnls)
    mean = sum(pnls) / n
    var = sum((p - mean) ** 2 for p in pnls) / n
    if var == 0.0:
        s = 3.0 if mean > 0 else -3.0 if mean < 0 else 0.0
    else:
        s = mean / math.sqrt(var)
    return _clamp01((s + 3.0) / 6.0)


def profit_factor_component(pnls: Sequence[float]) -> float:
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = sum(-p for p in pnls if p < 0)
    if gross_loss == 0.0:
        return 1.0 if gross_win > 0 else 0.0
    return _clamp01((gross_win / gross_loss) / 3.0)


def max_drawdown_penalty(pnls: Sequence[float]) -> float:
    gross_win = sum(p for p in pnls if p > 0)
    if gross_win == 0.0:
        return 1.0
    equity = peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return _clamp01(max_dd / gross_win)


def evaluate_fitness(pnls: Sequence[float], cfg: OptimizerConfig) -> float:
    """The §6.1 formula, guarded by the §6.2 gate. Range [-0.2, 0.8] or WORST."""
    res = expectancy_r(pnls)
    if not passes_expectancy_gate(res, cfg.fitness_min_trades, cfg.expectancy_min_r):
        return WORST_FITNESS
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls)
    return (
        0.40 * mean_sigma_component(pnls)
        + 0.20 * win_rate
        + 0.20 * profit_factor_component(pnls)
        - 0.20 * max_drawdown_penalty(pnls)
    )


def fitness_of(
    params: ParamSet, bars: Sequence[LabelledBar], costs: CostModel,
    cfg: OptimizerConfig, *, atr_period: int
) -> float:
    return evaluate_fitness(simulate_trades(params, bars, costs,
                                            atr_period=atr_period), cfg)
