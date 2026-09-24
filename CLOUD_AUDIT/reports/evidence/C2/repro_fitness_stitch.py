"""C2 reproduction: QIEA's fitness sim scores a STITCHED series, and caps every gap at the stop.

    cd /tmp/review-acis && python <this file>          # ~1-2 min, one core, synthetic only

Mechanism (code at BASE 7695ed04):
  * LabelledBarCache.history (tests/backtest/regime_labels.py:165-181) and
    qiea.fitness_window (core/optimizer/qiea.py:69-76) return ONLY the bars of one regime,
    concatenated. Episodes of that regime are hours or days apart in real time.
  * simulate_trades (core/optimizer/fitness.py:82-160) treats the result as contiguous. A
    position open at the end of one episode is carried across the jump into the next one,
    and when the jump's bar opens beyond the stop, the fill is AT the stop (fitness.py:117-125).
    EMA/RSI/ATR also run across the jump.

Part 1: one hand-built case. Part 2: a null random walk (no edge at all), labelled with
random regime blocks. Every ParamSet is scored two ways: (a) stitched, as QIEA does, and
(b) episode by episode, with each episode simulated on its own (no cross-jump carry). On a
market with NO edge, (a) minus (b) is the bias the stitch alone adds to the numbers QIEA
selects on.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from core.optimizer.costs import CostModel                     # noqa: E402
from core.optimizer.fitness import expectancy_r, simulate_trades  # noqa: E402
from core.optimizer.param_types import LabelledBar            # noqa: E402
from core.regime.regime_types import RegimeType               # noqa: E402
from tests.optimizer_fixtures import make_paramset            # noqa: E402

UTC = timezone.utc
R = RegimeType.STRONG_TREND_UP
OTHER = RegimeType.RANGING_WIDE
COST = CostModel(commission_per_side=0.0, slippage_per_side=0.00002)
ATR_P = 14


def bar(ts, o, h, l, c, regime=R, spread=0.00008):
    return LabelledBar(ts=ts, open=o, high=max(h, o, c), low=min(l, o, c), close=c,
                       spread=spread, regime=regime)


def part1():
    """A random-walk episode of the target regime that ENDS with a position open, then, 2 days
    later in real time, the next episode of the same regime opening 150 pips lower. Episode 1
    on its own marks the position to its last close; the stitched series carries it across
    the jump and books the stop price, although the first bar after the jump opens far
    beyond it."""
    rng = random.Random(0)
    p = make_paramset(ema_fast=5, ema_slow=20, rsi_period=7, rsi_overbought=80.0,
                      atr_multiplier_sl=1.0, atr_multiplier_tp=5.0, max_holding_periods=48)
    t = datetime(2026, 1, 5, 8, tzinfo=UTC)
    for attempt in range(10_000):
        raw = null_bars(120, 0.00025, rng)
        ep1 = [bar(t + timedelta(minutes=i), o, h, l, c) for i, (_, o, h, l, c) in enumerate(raw)]
        last = ep1[-1].close
        t2 = t + timedelta(days=2)
        ep2 = [bar(t2 + timedelta(minutes=i), last - 0.0150, last - 0.0149, last - 0.0152,
                   last - 0.0151) for i in range(5)]
        alone = simulate_trades(p, ep1, COST, atr_period=ATR_P)
        both = simulate_trades(p, ep1 + ep2, COST, atr_period=ATR_P)
        if alone and both and len(both) == len(alone) and both[-1] != alone[-1] and both[-1] < 0:
            break
    print("Part 1 (hand case, attempt", attempt, "):")
    print("   episode 1 alone, last trade marked to its own close:", round(alone[-1] * 1e4, 2), "pips")
    print("   stitched, the same trade carried across a -150 pip jump:", round(both[-1] * 1e4, 2),
          "pips  <- booked AT THE STOP; a fill at the first bar's open would be about",
          round((ep2[0].open - last) * 1e4 + alone[-1] * 1e4, 1), "pips")


def null_bars(n, sigma, rng):
    t = datetime(2020, 1, 6, tzinfo=UTC)
    px, out = 1.1, []
    for i in range(n):
        o = px
        path = [o]
        for _ in range(4):
            path.append(path[-1] * math.exp(rng.gauss(0.0, sigma / 2)))
        px = path[-1]
        out.append((t + timedelta(minutes=i), o, max(path), min(path), px))
    return out


def label_blocks(n, rng, frac=0.25, lo=30, hi=400):
    labels, i = [], 0
    while i < n:
        L = rng.randint(lo, hi)
        labels.extend([R if rng.random() < frac else OTHER] * L)
        i += L
    return labels[:n]


def gap_aware(params, bars, costs, *, atr_period):
    """simulate_trades at BASE with ONE change, for measurement only: a stop (or target) that
    the bar OPENS beyond fills at that open, as a resting stop order would. Everything else
    (signals, warm-up, costs, max hold, mark-to-close) is line-for-line the BASE logic."""
    import core.optimizer.fitness as F
    n = len(bars)
    warmup = max(params.ema_slow, params.rsi_period + 1, atr_period + 1)
    if n <= warmup + 1:
        return []
    closes = [b.close for b in bars]
    ema_f, ema_s = F.ema_series(closes, params.ema_fast), F.ema_series(closes, params.ema_slow)
    rsi, atr = F.rsi_series(closes, params.rsi_period), F.atr_series(bars, atr_period)
    pnls, d, entry, sl, tp, cost_in, held = [], 0, 0.0, 0.0, 0.0, 0.0, 0
    for i in range(warmup, n):
        b = bars[i]
        if d != 0:
            held += 1
            x = None
            if d > 0:
                if b.low <= sl:
                    x = min(sl, b.open)
                elif b.high >= tp:
                    x = max(tp, b.open)
            else:
                if b.high >= sl:
                    x = max(sl, b.open)
                elif b.low <= tp:
                    x = min(tp, b.open)
            if x is None and held >= params.max_holding_periods:
                x = b.close
            if x is not None:
                pnls.append(d * (x - entry) - cost_in - costs.per_side_cost(b.spread))
                d = 0
            continue
        if i + 1 >= n:
            break
        up = ema_f[i - 1] <= ema_s[i - 1] and ema_f[i] > ema_s[i]
        dn = ema_f[i - 1] >= ema_s[i - 1] and ema_f[i] < ema_s[i]
        a = atr[i]
        if a <= 0.0:
            continue
        if up and rsi[i] < params.rsi_overbought:
            d = 1
        elif dn and rsi[i] > params.rsi_oversold:
            d = -1
        else:
            continue
        eb = bars[i + 1]
        entry, cost_in = eb.open, costs.per_side_cost(eb.spread)
        sl, tp, held = entry - d * params.atr_multiplier_sl * a, entry + d * params.atr_multiplier_tp * a, 0
    if d != 0:
        pnls.append(d * (bars[-1].close - entry) - cost_in - costs.per_side_cost(bars[-1].spread))
    return pnls


def part2(n_bars=60_000, n_params=100, seed=3, lo=30, hi=400):
    rng = random.Random(seed)
    raw = null_bars(n_bars, 0.00025, rng)          # ~2.5 pip sd per minute: a plausible 1-min tape
    labels = label_blocks(n_bars, rng, lo=lo, hi=hi)
    bars = [bar(ts, o, h, l, c, regime=lab) for (ts, o, h, l, c), lab in zip(raw, labels)]
    target = [b for b in bars if b.regime is R]
    episodes, cur = [], []
    for b, lab in zip(bars, labels):
        if lab is R:
            cur.append(b)
        elif cur:
            episodes.append(cur)
            cur = []
    if cur:
        episodes.append(cur)
    diffs, st_means, ep_means, gaps = [], [], [], []
    prng = random.Random(seed + 1)
    for _ in range(n_params):
        fast = prng.randint(5, 30)
        p = make_paramset(ema_fast=fast, ema_slow=max(20, fast + prng.randint(5, 60)),
                          rsi_period=prng.randint(7, 21), rsi_overbought=prng.uniform(65, 80),
                          rsi_oversold=prng.uniform(20, 35),
                          atr_multiplier_sl=(sl := prng.uniform(1.0, 3.0)),
                          atr_multiplier_tp=min(5.0, max(1.5, sl + prng.uniform(0.2, 3.0))),
                          max_holding_periods=prng.randint(1, 48))
        s = simulate_trades(p, target, COST, atr_period=ATR_P)
        e = [x for ep in episodes for x in simulate_trades(p, ep, COST, atr_period=ATR_P)]
        g = gap_aware(p, target, COST, atr_period=ATR_P)
        assert len(g) == len(s), "gap-aware fill must keep the trade set"
        gaps.append((statistics.fmean(s) - statistics.fmean(g)) * 1e4)
        if len(s) < 20 or len(e) < 20:
            continue
        ms, me = statistics.fmean(s) * 1e4, statistics.fmean(e) * 1e4    # pips per trade
        st_means.append(ms)
        ep_means.append(me)
        diffs.append(ms - me)
    k = len(diffs)
    sd = statistics.stdev(diffs)
    print(f"\nPart 2 (regime blocks {lo}-{hi} bars; null random walk, {n_bars} one-minute bars, {len(episodes)} target-regime "
          f"episodes, {len(target)} target bars, {k} ParamSets with >=20 trades each way):")
    print(f"   mean net pips/trade  stitched (as QIEA scores) = {statistics.fmean(st_means):+.3f}")
    print(f"   mean net pips/trade  episode-by-episode        = {statistics.fmean(ep_means):+.3f}")
    print(f"   stitch bias = {statistics.fmean(diffs):+.3f} pips/trade "
          f"(95% CI +/- {1.96 * sd / math.sqrt(k):.3f}); "
          f"ParamSets where stitched > episodic: {sum(d > 0 for d in diffs)}/{k}")
    print(f"   PURE gap-cap bias (same stitched bars, same trades, stop filled at the gapped open "
          f"instead): {statistics.fmean(gaps):+.3f} pips/trade (max {max(gaps):+.3f})")
    print(f"   share of ParamSets with positive stitched E: {sum(m > 0 for m in st_means)}/{k}; "
          f"episodic: {sum(m > 0 for m in ep_means)}/{k}")


if __name__ == "__main__":
    part1()
    part2()
    part2(lo=10, hi=120)
