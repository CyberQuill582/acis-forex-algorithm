"""R1-A receipt: breadth, effective breadth and the pooled-rule certification frontier (synthetic only).

LLM-originated analysis (Opus 5.5, lane R1-A). Run: OMP_NUM_THREADS=1 python sim_breadth.py [R]
Part A  analytic: IDM(N,rho) = sqrt(N/(1+(N-1)rho)); years for 80% power, one-sided 5%, K looks.
Part B  sim check on an equicorrelated P&L panel: portfolio t-test power at the analytic length, and the
        FPR of the WRONG pooled-panel t-test that treats N*T rule-days as independent.
Part C  price->rule-P&L correlation map: EWMAC(16,64) continuous and sign forecasts on factor-correlated
        prices; measured rule-P&L correlation vs price correlation (theory: rho_p^2 for linear forecasts,
        rho_p*(2/pi)*asin(rho_p) for sign forecasts, on iid returns with no planted edge).
"""
import json
import math
import sys

import numpy as np
from scipy.signal import lfilter
from scipy.stats import norm

Z = norm.ppf(0.95) + norm.ppf(0.80)


def idm(n, rho):
    return math.sqrt(n / (1 + (n - 1) * rho))


def years_needed(sr, k=1, lo_factor=False):
    z = norm.ppf(1 - 0.05 / k) + norm.ppf(0.80)
    f = (1 + sr * sr / 2) if lo_factor else 1.0
    return z * z * f / (sr * sr)


def part_a():
    rows = []
    for rho in (0.05, 0.1, 0.2, 0.3, 0.5):
        for n in (1, 8, 20, 30, 40):
            m = idm(n, rho)
            row = {"rho": rho, "N": n, "IDM": round(m, 3), "shrink_factor_years": round(1 / m ** 2, 3),
                   "C1_frontier_9.3y_at_SR1_becomes": round(9.3 / m ** 2, 2),
                   "daily_frontier_6.2y_at_SR1_becomes": round(years_needed(1.0) / m ** 2, 2)}
            for s in (0.2, 0.3, 0.5):
                row[f"years_K1_s{s}"] = round(years_needed(s * m), 1)
                row[f"years_K20_s{s}"] = round(years_needed(s * m, 20), 1)
            rows.append(row)
    return rows


def part_b(R, rng):
    out = []
    for rho in (0.1, 0.3):
        for n in (8, 20, 40):
            s = 0.3
            sp = s * idm(n, rho)
            T = int(round(years_needed(sp) * 252))
            mu = s / math.sqrt(252)
            pw = fp_port = fp_naive = 0
            for _ in range(R):
                f = rng.standard_normal(T)
                e = rng.standard_normal((n, T))
                noise = math.sqrt(rho) * f[None, :] + math.sqrt(1 - rho) * e
                for planted in (True, False):
                    x = noise + (mu if planted else 0.0)
                    port = x.mean(0)
                    tp = port.mean() / (port.std(ddof=1) / math.sqrt(T))
                    if planted:
                        pw += tp > 1.645
                    else:
                        fp_port += tp > 1.645
                        flat = x.ravel()
                        tn = flat.mean() / (flat.std(ddof=1) / math.sqrt(flat.size))
                        fp_naive += tn > 1.645
            out.append({"rho": rho, "N": n, "per_inst_SR": s, "portfolio_SR": round(sp, 3),
                        "years_analytic": round(T / 252, 1), "power_sim": pw / R,
                        "FPR_portfolio_ttest": fp_port / R, "FPR_naive_pooled_panel_ttest": fp_naive / R})
    return out


def ewmac(r, fast):
    p = np.cumsum(r, axis=-1)
    a1, a2 = 2 / (fast + 1), 2 / (4 * fast + 1)
    e1 = lfilter([a1], [1, -(1 - a1)], p, axis=-1)
    e2 = lfilter([a2], [1, -(1 - a2)], p, axis=-1)
    return e1 - e2


def part_c(rng):
    out = []
    T = 252 * 200
    for rho_p in (0.2, 0.4, 0.6, 0.8):
        f = rng.standard_normal(T)
        r = math.sqrt(rho_p) * f[None, :] + math.sqrt(1 - rho_p) * rng.standard_normal((2, T))
        fc = ewmac(r, 16)
        pos_lin = fc / fc.std(axis=1, keepdims=True)
        pos_sgn = np.sign(fc)
        pnl_lin = pos_lin[:, :-1] * r[:, 1:]
        pnl_sgn = pos_sgn[:, :-1] * r[:, 1:]
        out.append({"price_corr": rho_p,
                    "pnl_corr_linear": round(float(np.corrcoef(pnl_lin)[0, 1]), 3),
                    "theory_linear_rho2": round(rho_p ** 2, 3),
                    "pnl_corr_sign": round(float(np.corrcoef(pnl_sgn)[0, 1]), 3),
                    "theory_sign": round(rho_p * 2 / math.pi * math.asin(rho_p), 3),
                    "position_corr_linear": round(float(np.corrcoef(pos_lin)[0, 1]), 3)})
    return out


if __name__ == "__main__":
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    rng = np.random.default_rng(20260925)
    res = {"A_analytic": part_a(), "B_sim": part_b(R, rng), "C_price_to_pnl_corr": part_c(rng),
           "note": "years_needed uses the daily-data SE (Lo factor ~1 at daily frequency); "
                   "C1's 9.3 y at SR 1 includes an annual-period (1+S^2/2) factor"}
    with open("sim_out_breadth.json", "w") as fh:
        json.dump(res, fh, indent=1)
    for k in ("B_sim", "C_price_to_pnl_corr"):
        for row in res[k]:
            print(k, row)
