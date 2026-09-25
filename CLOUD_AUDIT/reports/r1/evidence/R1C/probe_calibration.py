"""R1-C task 6: is the lab USEFUL? A slow pooled rule (EWMA crossover 16/64 on daily bars, sign position,
vol-targeted by an EWMA vol estimate, equal risk per instrument, no fitted parameter) pooled on 20 lab
instruments, graded on the NULL and on a planted TREND of known theoretical Sharpe.
Checks: (a) the null's pooled Sharpe distribution is centred on zero (no bridge tilt); (b) the planted
trend is detected at the rate its theoretical Sharpe predicts; (c) the same with the BASE whole-path
demeaning re-applied, to show the tilt and the lost power. Synthetic only.
Usage: OMP_NUM_THREADS=1 python probe_calibration.py [paths] [target_rule_sr_per_inst] [halflife]
"""
import math
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from gen_lab import (Effect, LabSpec, _phi, generate, other_var, theory_ewmac,   # noqa: E402
                     theory_oracle_trend, _ewmac_weights, SQ2PI, YEAR)
from scipy.optimize import brentq  # noqa: E402

PATHS = int(sys.argv[1]) if len(sys.argv) > 1 else 100
TARGET = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
HL = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
FAST, SLOW, VOLSPAN = 16, 64, 36
DAYS, N, BURN = 3640, 20, 300


def rule_pnl(x, demean=False):
    """x: (T, N) excess log returns. Returns (T-BURN,) pooled daily P&L in risk units."""
    if demean:
        x = x - x.mean(axis=0, keepdims=True)                 # the BASE bug, re-applied per instrument
    T = x.shape[0]
    lp = np.cumsum(x, axis=0)
    af, asl, av = 2 / (FAST + 1), 2 / (SLOW + 1), 2 / (VOLSPAN + 1)
    ef = np.zeros(N); es = np.zeros(N); v = np.full(N, np.mean(x[:60] ** 2, axis=0))
    out = np.zeros(T)
    prev = np.zeros(N)
    for t in range(T):
        pos = np.sign(ef - es) / np.sqrt(v)                   # decided on data up to t-1
        out[t] = np.mean(pos * x[t])                          # equal risk, pooled
        ef += af * (lp[t] - ef); es += asl * (lp[t] - es)
        v += av * (x[t] ** 2 - v)
    return out[BURN:]


def ann_sr(p):
    return p.mean() / p.std(ddof=1) * math.sqrt(YEAR)


def theory_pooled(v_m, phi, ov, rho):
    """Pooled SR of N instruments with independent planted trends and common-factor noise: per-instrument
    SR times sqrt(N / (1 + (N-1) rho_pnl)), rho_pnl = (2/pi) arcsin(rho_X) * rho / (v_m + ov)."""
    s1 = theory_ewmac(v_m, phi, ov, FAST, SLOW)
    w = _ewmac_weights(FAST, SLOW, 12 * SLOW + 50)
    kk = np.arange(len(w)); s = 0.0; acc = 0.0
    for j in range(len(w)):
        acc = phi * (acc + (w[j - 1] if j else 0.0)); s += w[j] * (w[j] + 2 * acc)
    var_x = ov * float(np.sum(w * w)) + v_m * s
    rho_x = rho * float(np.sum(w * w)) / var_x
    rho_pnl = (2 / math.pi) * math.asin(rho_x) * rho / (v_m + ov)
    return s1, s1 * math.sqrt(N / (1 + (N - 1) * rho_pnl)), rho_pnl


def main():
    base = LabSpec(n_inst=N, days=DAYS)
    ov = other_var(base)
    phi = _phi(HL)
    # choose the oracle strength so that the RULE's theoretical per-instrument SR equals TARGET
    vm = brentq(lambda v: theory_ewmac(v, phi, ov, FAST, SLOW) - TARGET, 1e-9, 5.0)
    oracle = theory_oracle_trend(vm, phi, ov)
    rho_eps = base.rho
    s1, sN, rpnl = theory_pooled(vm, phi, ov, rho_eps)
    yrs = (DAYS - BURN) / YEAR
    crit = stats.norm.ppf(0.95)
    power_th = 1 - stats.norm.cdf(crit - sN * math.sqrt(yrs))
    print(f"rule EWMAC {FAST}/{SLOW} sign, vol-targeted; N={N}; {yrs:.1f} graded years; halflife {HL:.0f} d")
    print(f"planted trend: oracle SR/inst {oracle:.3f}; rule theory SR/inst {s1:.3f}; pooled theory SR {sN:.3f} "
          f"(rho_pnl {rpnl:.4f}); theory one-sided 5% power {power_th:.3f}")
    rows = {k: [] for k in ("null", "planted", "null_demeaned", "planted_demeaned")}
    for seed in range(1, PATHS + 1):
        pn = generate(LabSpec(n_inst=N, days=DAYS, seed=seed))
        pp = generate(LabSpec(n_inst=N, days=DAYS, seed=seed,
                              effect=Effect(trend_sr=oracle, trend_halflife=HL)))
        rows["null"].append(ann_sr(rule_pnl(pn.x)))
        rows["planted"].append(ann_sr(rule_pnl(pp.x)))
        rows["null_demeaned"].append(ann_sr(rule_pnl(pn.x, demean=True)))
        rows["planted_demeaned"].append(ann_sr(rule_pnl(pp.x, demean=True)))
    for k, v in rows.items():
        v = np.array(v)
        tstat = v * math.sqrt(yrs)
        print(f"  {k:17s} mean SR {v.mean():+.3f} (se {v.std(ddof=1) / math.sqrt(len(v)):.3f}; sd {v.std(ddof=1):.3f})"
              f"  detect rate (t>{crit:.3f}) {np.mean(tstat > crit):.3f}")
    print(f"  expected: null mean 0, null sd ~ 1/sqrt(years) = {1 / math.sqrt(yrs):.3f}, null detect ~0.05; "
          f"planted mean {sN:.3f}, detect {power_th:.3f}")


if __name__ == "__main__":
    main()
