"""C1 — how long an OOS/demo record must be before CIs on P(pass), EV and P(breach) are useful.

Maps the sampling distribution of the record's net Sharpe (block bootstrap of a synthetic fat-
tailed daily P&L record, cross-checked against Lo 2002's iid SE) through the monotone EV(S),
P_pass(S) curves measured by sim_prop (sim_out_prop.json). Also: the zero-gross-edge EV at a
given turnover, and the break-even S_net / gross Sharpe per turnover. Writes sim_out_prop_ci.json.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "sim_out_prop.json")))


def curve(policy, swing, delta, hc, key):
    rows = sorted((c["S_net"], c[key]) for c in d["cells"] if c["policy"] == policy and c["swing"] == swing
                  and c["delta"] == delta and c["haircut"] == hc)
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def interp(x, xs, ys):
    return float(np.interp(x, xs, ys))


def breakeven(xs, ys):
    for i in range(len(xs) - 1):
        if ys[i] < 0 <= ys[i + 1]:
            return xs[i] + (0 - ys[i]) * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
    return float("nan")


def boot_sr(rng, S, months, B=2000, block=5):
    n = int(round(months * 21))
    z = rng.standard_t(4, n) / math.sqrt(2.0)
    x = S / math.sqrt(252) + z
    nb = int(math.ceil(n / block))
    starts = rng.integers(0, n, size=(B, nb))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(B, -1)[:, :n]
    xb = x[idx]
    srb = xb.mean(1) / xb.std(1) * math.sqrt(252)
    return float(x.mean() / x.std() * math.sqrt(252)), np.quantile(srb, [0.05, 0.95])


if __name__ == "__main__":
    out = {"breakeven": {}, "zero_gross": {}, "record": []}
    C_PER_RT = 1.5e-4 / (0.006 * math.sqrt(252))          # Sharpe drag per round trip / yr
    for pol, swing in (("survival_first", False), ("survival_first", True), ("bold", False), ("bold", True),
                       ("timid", False)):
        for dl, hc in ((0.25, 0.0), (0.5, 0.25)):
            xs, ys = curve(pol, swing, dl, hc, "EV")
            if len(xs) == 0:
                continue
            be = breakeven(xs, ys)
            key = f"{pol}|{'swing' if swing else 'intraday'}|delta{dl}|haircut{hc}"
            out["breakeven"][key] = {"S_net": be, "max_round_trips_per_yr_at_zero_gross": -be / C_PER_RT if be < 0 else 0.0}
            out["zero_gross"][key] = {str(n): {"S_net": -n * C_PER_RT, "EV": interp(-n * C_PER_RT, xs, ys)}
                                      for n in (12, 50, 100, 252, 520, 1260)}
    # record-length CIs (survival-first, intraday, optimistic and conservative economics)
    rng = np.random.default_rng(2026)
    xs, ev = curve("survival_first", False, 0.25, 0.0, "EV")
    _, evc = curve("survival_first", False, 0.5, 0.25, "EV")
    _, pp = curve("survival_first", False, 0.25, 0.0, "P_pass")
    for S in (0.0, 0.5, 1.0):
        for months in (0.5, 3, 6, 12, 24, 60):
            se = math.sqrt((1 + S * S / 2) / (months / 12))
            lo, hi = S - 1.645 * se, S + 1.645 * se
            shat, (blo, bhi) = boot_sr(rng, S, months)
            out["record"].append({
                "true_S": S, "months": months, "lo02_se": se, "S_90ci": [lo, hi],
                "boot_S_90ci_width": float(bhi - blo), "lo_width": 2 * 1.645 * se,
                "EV_90ci": [interp(lo, xs, ev), interp(hi, xs, ev)],
                "EV_cons_90ci": [interp(lo, xs, evc), interp(hi, xs, evc)],
                "P_pass_90ci": [interp(lo, xs, pp), interp(hi, xs, pp)],
                "P_G1_pass": 1 - 0.5 * (1 + math.erf((1.645 - S / se) / math.sqrt(2))),
            })
    json.dump(out, open(os.path.join(HERE, "sim_out_prop_ci.json"), "w"), indent=1)
    for k, v in out["breakeven"].items():
        print(k, "S_net*=%.2f" % v["S_net"], "max RT/yr at zero gross=%.0f" % v["max_round_trips_per_yr_at_zero_gross"],
              {n: round(z["EV"]) for n, z in out["zero_gross"][k].items()})
    for r in out["record"]:
        print(r["true_S"], r["months"], "S90 [%.2f,%.2f] bootW %.2f loW %.2f EV [%.0f,%.0f] EVc [%.0f,%.0f] Ppass [%.2f,%.2f] G1 %.3f" % (
            *r["S_90ci"], r["boot_S_90ci_width"], r["lo_width"], *r["EV_90ci"], *r["EV_cons_90ci"], *r["P_pass_90ci"], r["P_G1_pass"]))
