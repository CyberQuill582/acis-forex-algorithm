"""(1) How often does the author's fitness-sweep tape exercise the T6 gap branch?  (2) On a gappy tape,
does the author's exhaustive sweep catch a gap exit that reads its own bar's close?"""
import sys, inspect, textwrap, math, random
from pathlib import Path
TREE = Path(sys.argv[1]); sys.path.insert(0, str(TREE))
import core.optimizer.fitness as fitness
from tests.backtest.leakage import future_perturbation, truncation
from tests.backtest.leakage_tapes import bar_cuts, bar_tape, bar_tape_variant, bars_from_path, trade_path_decisions
from tests.optimizer_fixtures import TEST_COSTS, make_paramset

params = make_paramset(max_holding_periods=12)

def gap_exits(bars, tp=fitness.trade_path):
    n = 0
    for t in tp(params, bars, TEST_COSTS, atr_period=14):
        b = bars[t.exit_bar]
        if not t.marked and t.exit_price == b.open and t.exit_price != t.entry_price:
            n += 1
    return n

author = bar_tape(240, seed=21)
print("author tape: exits", sum(not t.marked for t in fitness.trade_path(params, author, TEST_COSTS, atr_period=14)),
      "| gap-through exits", gap_exits(author))

def gappy(n, seed, body=6e-4, gap=3e-3):
    rng = random.Random(seed); path = [1.1]
    for i in range(1, 2 * n):
        s = body if i % 2 else gap                       # odd step: open->close; even step: close->next open
        drift = 3e-4 * (1 if (i // 30) % 2 else -1)
        path.append(path[-1] * math.exp(rng.gauss(drift, s)))
    return bars_from_path(path, [1e-4 * (1 + rng.random()) for _ in range(n)])

src = textwrap.dedent(inspect.getsource(fitness.trade_path))
# LEAD v2 (fixed tree): the SAME planted leak -- a gap exit that reads its own bar's CLOSE and fills
# at the stop when the close recovers -- re-planted against the fixed code's gap branch
A = 'exit_mid, kind = (bar.open, "gap") if bar.open < sl else (sl, "stop")'
B = 'exit_mid, kind = (bar.open, "gap") if bar.open > sl else (sl, "stop")'
assert src.count(A) == 1 and src.count(B) == 1, 'gap branch text moved'
leaky_src = src.replace(A, 'exit_mid, kind = ((sl, "gap") if bar.close > sl else (bar.open, "gap")) if bar.open < sl else (sl, "stop")').replace(B, 'exit_mid, kind = ((sl, "gap") if bar.close < sl else (bar.open, "gap")) if bar.open > sl else (sl, "stop")')
assert leaky_src != src
ns = dict(vars(fitness)); exec(leaky_src, ns); leaky = ns["trade_path"]
for seed in (22, 31, 32, 33):
    bars = gappy(240, seed)
    ref_h = trade_path_decisions(fitness.trade_path(params, bars, TEST_COSTS, atr_period=14))
    ref_l = trade_path_decisions(leaky(params, bars, TEST_COSTS, atr_period=14))
    diff = sum(a.key() != b.key() for a, b in zip(ref_h, ref_l))
    pnl_h = sum(t.pnl for t in fitness.trade_path(params, bars, TEST_COSTS, atr_period=14))
    pnl_l = sum(t.pnl for t in leaky(params, bars, TEST_COSTS, atr_period=14))
    cuts = bar_cuts(len(bars))
    out = []
    for name, tp in (("honest", fitness.trade_path), ("leaky", leaky)):
        run = lambda k, mode, tp=tp: trade_path_decisions(tp(params, bar_tape_variant(bars, k, mode), TEST_COSTS, atr_period=14))
        ref = run(len(bars), "truncate")
        t2 = future_perturbation(ref, lambda t: run(t, "perturb"), cuts)
        t1 = truncation(ref, lambda t: run(t, "truncate"), cuts)
        out.append(f"{name}: T2 {len(t2.violations)} viol/{t2.compared} cmp, T1 {len(t1.violations)} viol/{t1.compared} cmp")
    print(f"gappy seed {seed}: gap exits {gap_exits(bars)}, leaky decisions differing {diff}, "
          f"pnl honest {pnl_h:.5f} leaky {pnl_l:.5f} | " + " | ".join(out))
