"""C2 reproduction: a look-ahead that `refuse_lookahead` (tests/backtest/harness.py:77-88)
and tests/backtest/test_lookahead_canary.py cannot see — future information carried in the
regime LABELS, not in the bar timestamps.

    cd /tmp/review-acis && python <this file>        # ~10 s, synthetic only

The canary proves only that no evolved-on bar OPENS at or after train_end. Evolution reads
the bars of one regime; which bars those are is the label. If the label for bar i uses
prices after bar i (a centred indicator, a smoothed or relabelled regime series, a
"stability" pass that looks forward, or a labeller rebuilt on a whole year and then cut), every
timestamp is still honest and the canary is green, while fitness is scored on a subset of bars
chosen by where price went next. On a driftless random walk, that alone manufactures an
"edge" for a trend-follower.
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
from tests.backtest.harness import refuse_lookahead           # noqa: E402
from tests.backtest.walk_forward import Fold                  # noqa: E402
from tests.optimizer_fixtures import make_paramset            # noqa: E402

UTC = timezone.utc
UP, OTHER = RegimeType.STRONG_TREND_UP, RegimeType.RANGING_WIDE
COST = CostModel(commission_per_side=0.0, slippage_per_side=0.00002)


def walk(n, sigma, rng, t0):
    px, out = 1.1, []
    for i in range(n):
        o = px
        path = [o] + [0.0] * 4
        for k in range(1, 5):
            path[k] = path[k - 1] * math.exp(rng.gauss(0.0, sigma / 2))
        px = path[-1]
        out.append((t0 + timedelta(minutes=i), o, max(path), min(path), px))
    return out


def main(n=40_000, horizon=60, n_params=60):
    rng = random.Random(5)
    t0 = datetime(2020, 1, 6, tzinfo=UTC)
    raw = walk(n, 0.00025, rng, t0)
    closes = [c for *_, c in raw]
    train_end = raw[-1][0] - timedelta(minutes=horizon)            # the last labelled bar ends before it

    def label_future(i):   # LEAKY: "up-trend" iff price is higher `horizon` bars later
        return UP if i + horizon < n and closes[i + horizon] > closes[i] + 0.0010 else OTHER

    blocks, i = [], 0      # HONEST comparator: random regime blocks of similar coverage
    while i < n:
        L = rng.randint(30, 300)
        blocks += [UP if rng.random() < 0.3 else OTHER] * L
        i += L

    def bars(labeller):
        return [LabelledBar(ts=ts, open=o, high=h, low=l, close=c, spread=0.00008, regime=labeller(j))
                for j, (ts, o, h, l, c) in enumerate(raw) if ts + timedelta(minutes=1) <= train_end]

    leaky = [b for b in bars(label_future) if b.regime is UP]
    honest = [b for b in bars(lambda j: blocks[j]) if b.regime is UP]

    fold = Fold(0, t0, train_end, train_end + timedelta(days=3), train_end + timedelta(days=10))
    record = {"regimes": {UP.value: {"candidates": [{
        "instrument": "EUR_USD", "first_bar": leaky[0].ts.isoformat(),
        "last_bar": leaky[-1].ts.isoformat()}]}}}
    refuse_lookahead(record, fold)
    print(f"refuse_lookahead on the leaky record: NO RAISE (last bar {leaky[-1].ts.isoformat()} "
          f"< train end {train_end.isoformat()})")

    prng = random.Random(9)
    res = {"leaky": [], "honest": []}
    for _ in range(n_params):
        fast = prng.randint(5, 30)
        sl = prng.uniform(1.0, 3.0)
        p = make_paramset(ema_fast=fast, ema_slow=max(20, fast + prng.randint(5, 60)),
                          rsi_period=prng.randint(7, 21), rsi_overbought=prng.uniform(65, 80),
                          rsi_oversold=prng.uniform(20, 35), atr_multiplier_sl=sl,
                          atr_multiplier_tp=min(5.0, max(1.5, sl + prng.uniform(0.2, 3.0))),
                          max_holding_periods=prng.randint(10, 48))
        for name, series in (("leaky", leaky), ("honest", honest)):
            pn = simulate_trades(p, series, COST, atr_period=14)
            if len(pn) >= 10:
                res[name].append(expectancy_r(pn).e_r)
    for name, ers in res.items():
        print(f"{name:6s} labels: {len(ers)} ParamSets with >=10 trades; median E_R "
              f"{statistics.median(ers):+.3f}; share with E_R > 0: {sum(e > 0 for e in ers)}/{len(ers)}")
    print("Same driftless prices, same timestamps, same fitness code: only the labels differ.")


if __name__ == "__main__":
    main()
