"""R1-A receipt: pooled vs per-instrument vs empirical-Bayes (James-Stein-type) parameter choice.

LLM-originated design (Opus 5.5, lane R1-A). Synthetic only.  Run: python sim_shrinkage.py [R]
N instruments x P speeds.  True annual SR s[i,p] = profile[p] + tau * z[i,p] (z corr 0.8 across speeds).
Estimates over Y dev years: s_hat = s + e, e ~ N(0, 1/Y), corr 0.85^|p-q| across speeds, rho across
instruments (the rule-P&L correlation).  Each method picks one speed per instrument; the score is the
TRUE SR of what it picked (averaged over instruments) = the realised out-of-sample edge per instrument.
"""
import json
import math
import sys

import numpy as np

PROFILE = np.array([0.15, 0.25, 0.30, 0.30, 0.25, 0.20])
P = len(PROFILE)


def corr_speeds(c):
    idx = np.arange(P)
    return c ** np.abs(idx[:, None] - idx[None, :])


def run(N, Y, tau, rho, R, rng):
    Lz = np.linalg.cholesky(0.8 * np.ones((P, P)) + 0.2 * np.eye(P))
    Le = np.linalg.cholesky(corr_speeds(0.85))
    se = 1 / math.sqrt(Y)
    res = {k: [] for k in ("oracle", "fixed_middle", "pooled_argmax", "per_inst_argmax", "eb_shrunk_argmax",
                           "equal_weight_all_speeds")}
    dev_flags = []
    for _ in range(R):
        s = PROFILE[None, :] + tau * (rng.standard_normal((N, P)) @ Lz.T)
        common = rng.standard_normal(P) @ Le.T
        idio = rng.standard_normal((N, P)) @ Le.T
        e = se * (math.sqrt(rho) * common[None, :] + math.sqrt(1 - rho) * idio)
        sh = s + e
        pooled = sh.mean(0)
        res["oracle"].append(s.max(1).mean())
        res["fixed_middle"].append(s[:, 2].mean())
        res["pooled_argmax"].append(s[:, np.argmax(pooled)].mean())
        res["per_inst_argmax"].append(s[np.arange(N), sh.argmax(1)].mean())
        res["equal_weight_all_speeds"].append(s.mean(1).mean())   # SR of the combination is higher; see note
        # EB: tau^2 by moments, correcting for cross-instrument error correlation
        disp = sh.var(0, ddof=1).mean()
        tau2 = max(0.0, disp - se * se * (1 - rho))
        Bw = se * se * (1 - rho) / (se * se * (1 - rho) + tau2) if tau2 > 0 else 1.0
        shr = pooled[None, :] + (1 - Bw) * (sh - pooled[None, :])
        res["eb_shrunk_argmax"].append(s[np.arange(N), shr.argmax(1)].mean())
        dev_flags.append(Bw < 0.5)
    out = {k: round(float(np.mean(v)), 4) for k, v in res.items()}
    out["P(EB allows deviation: shrink weight on own estimate > 0.5)"] = round(float(np.mean(dev_flags)), 3)
    # per-instrument claim power: one-sided 5% test that instrument i's best-speed SR > 0 (no multiplicity)
    out["power_single_instrument_SR0.30"] = round(float(
        1 - __import__("scipy.stats").stats.norm.cdf(1.645 - 0.30 / se)), 3)
    return out


if __name__ == "__main__":
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    rng = np.random.default_rng(42)
    rows = []
    for tau in (0.0, 0.1, 0.2, 0.3):
        for Y in (12,):
            row = {"N": 30, "Y": Y, "tau": tau, "rho": 0.1}
            row.update(run(30, Y, tau, 0.1, R, rng))
            rows.append(row)
            print(row)
    json.dump(rows, open("sim_out_shrinkage.json", "w"), indent=1)
