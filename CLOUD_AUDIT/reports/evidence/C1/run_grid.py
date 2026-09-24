"""Run the C1 protocol grid for one world with <= 2 worker processes.

usage: OMP_NUM_THREADS=1 python run_grid.py <world> <R> [mu dur best_cfg]
world in {iid, garch, factor, planted_*}. Writes sim_out_<world>.json next to this file.
"""
import json
import math
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_protocols as sp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _one(args):
    kind, seed, mu, dur, best = args
    out, _ = sp.replicate(kind, seed, mu=mu, dur=dur, best_cfg=best)
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


if __name__ == "__main__":
    world, R = sys.argv[1], int(sys.argv[2])
    mu = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    dur = float(sys.argv[4]) if len(sys.argv) > 4 else 40.0
    best = int(sys.argv[5]) if len(sys.argv) > 5 else None
    kind = "planted" if world.startswith("planted") else world
    base = int.from_bytes(world.encode()[:6].ljust(6, b"_"), "big") % 9973 * 100_000
    t0 = time.time()
    with Pool(2) as pool:
        rows = pool.map(_one, [(kind, base + i, mu, dur, best) for i in range(R)], chunksize=4)
    agg = {}
    with open(os.path.join(HERE, f"sim_rows_{world}.json"), "w") as f:
        json.dump(rows, f, separators=(",", ":"))
    if "stats" in rows[0]:
        import numpy as _np
        agg["stats"] = {k: {"mean": float(_np.nanmean([r["stats"][k] for r in rows])),
                            "sd": float(_np.nanstd([r["stats"][k] for r in rows])),
                            "n_nan": int(sum(1 for r in rows if r["stats"][k] != r["stats"][k]))}
                        for k in rows[0]["stats"]}
    for cell in rows[0]:
        if cell == "stats":
            continue
        agg[cell] = {}
        for proto in rows[0][cell]:
            k = sum(r[cell][proto] for r in rows)
            agg[cell][proto] = {"rate": k / R, "k": k, "ci95": wilson(k, R)}
    res = {"world": world, "R": R, "mu": mu, "dur": dur, "best_cfg": best,
           "wall_s": time.time() - t0, "agg": agg}
    with open(os.path.join(HERE, f"sim_out_{world}.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(world, "done", res["wall_s"])
