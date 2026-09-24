"""Per-module net P&L across seeds, mean and a t-based 95% CI, grouped by (kind, arm)."""
import json, math, sys
from collections import defaultdict
from pathlib import Path
T = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57}
g = defaultdict(lambda: defaultdict(list))
for s in sorted(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/c3/runs").glob("*/summary.json")):
    d = json.loads(s.read_text()); a = d["args"]
    if a["folds"] != 5 or a.get("scramble_invisible") or a.get("evo_salt") or a["episode_hours"]:
        continue
    arm = ("off:" + "+".join(a["off"])) if a["off"] else ("noveto" if a["no_veto"] else "on")
    key = (a["kind"], arm)
    mods = set(d["per_strategy"]) | {"ALL"}
    for m in ["ALL", "TREND", "BREAKOUT", "MEAN_REVERSION", "TSMOM"]:
        v = d["net"] if m == "ALL" else d["per_strategy"].get(m, {}).get("net", 0.0)
        g[key][m].append((a["seed"], v))
for key, mods in sorted(g.items()):
    for m, vals in mods.items():
        xs = [v for _, v in vals]; n = len(xs); mu = sum(xs) / n
        if n > 1:
            sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1)); hw = T[n - 1] * sd / math.sqrt(n)
            ci = f"[{mu - hw:+.2f}, {mu + hw:+.2f}]"
        else:
            ci = "(1 seed)"
        print(f"{key[0]:8s} {key[1]:10s} {m:15s} seeds={[s for s, _ in vals]} per-seed={[round(x, 2) for x in xs]} mean={mu:+.2f} 95%CI {ci}")
