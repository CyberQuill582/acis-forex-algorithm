"""C1 prop-EV grid (single process). Writes sim_out_prop.json next to this file."""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_prop as sp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
S_GRID = [-1.5, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0]
POLICIES = {
    # name: (k_challenge, k_funded, cushion coefficient or None)
    "survival_first": (0.010, 0.010, 0.10),
    "bold": (0.015, 0.015, None),
    "timid": (0.005, 0.005, None),
    "acis_realised": (0.0004, 0.0004, None),
}
PATHS = int(sys.argv[1]) if len(sys.argv) > 1 else 4000

if __name__ == "__main__":
    t0 = time.time()
    out = {"paths": PATHS, "fee": sp.FEE, "split": sp.SPLIT, "cells": []}
    for swing in (True, False):
        for pol, (kc, kf, cush) in POLICIES.items():
            if pol == "acis_realised" and not swing:
                continue
            for S in S_GRID:
                for delta, hc in ((0.25, 0.0), (0.50, 0.25)):
                    if pol != "survival_first" and (delta, hc) != (0.25, 0.0):
                        continue
                    r = sp.simulate(S, k_ch=kc, k_f=kf, prop_cushion=cush, swing=swing,
                                    paths=PATHS, seed=1000 + int(S * 100), delta=delta, haircut=hc)
                    r.update(policy=pol, swing=swing, S_net=S, delta=delta, haircut=hc)
                    out["cells"].append(r)
                    print(json.dumps(r), flush=True)
    out["wall_s"] = time.time() - t0
    with open(os.path.join(HERE, "sim_out_prop.json"), "w") as f:
        json.dump(out, f, indent=1)
