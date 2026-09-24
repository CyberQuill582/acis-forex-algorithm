"""Calibrate planted drift mu (in daily-sigma units) per target net Sharpe. Writes sim_out_calibration.json."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_protocols as sp

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {k: v for k, v in {"planted_md05": (0.5, 40.0), "planted_md10": (1.0, 40.0), "planted_id05": (0.5, 5.0)}.items() if k in (sys.argv[1:] or [k])}
if __name__ == "__main__":
    out = {}
    for name, (s, dur) in TARGETS.items():
        t0 = time.time()
        mu, best = sp.calibrate(s, dur, hi=3.0 if dur < 10 else 1.0)
        out[name] = {"target_sr": s, "dur": dur, "mu": mu, "best_cfg": best, "wall_s": time.time() - t0}
        print(name, out[name], flush=True)
    json.dump(out, open(os.path.join(HERE, "sim_out_calibration%s.json" % ("_" + "_".join(sys.argv[1:]) if sys.argv[1:] else "")), "w"), indent=1)
