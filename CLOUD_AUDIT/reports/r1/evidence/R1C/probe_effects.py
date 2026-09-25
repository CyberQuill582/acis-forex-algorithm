"""R1-C: does each planted effect deliver its DECLARED theoretical Sharpe, and does the null give zero?
Per effect, the rule that the effect's theory is written for, graded in vol units (P&L = position * y, the
excess return over the lab's true sigma) and also with an estimated vol (EWMA, 36-day span) on excess
returns x, as a real rule would. Per-instrument annual Sharpe, averaged over instruments and seeds.
Synthetic only. Usage: OMP_NUM_THREADS=1 python probe_effects.py [seeds]
"""
import math
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from gen_lab import (Effect, LabSpec, _phi, generate, other_var, theory_ewmac, v_m_for,  # noqa: E402
                     YEAR)

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
BURN = 300


def sr(p):
    p = p[BURN:]
    return p.mean(axis=0) / p.std(axis=0, ddof=1) * math.sqrt(YEAR)


def lagged(a):
    out = np.zeros_like(a); out[1:] = a[:-1]; return out


def ewmac_sign(y, f, s):
    lp = np.cumsum(y, axis=0); af, a_s = 2 / (f + 1), 2 / (s + 1)
    ef = np.zeros(y.shape[1]); es = np.zeros(y.shape[1]); pos = np.zeros_like(y)
    for t in range(y.shape[0]):
        pos[t] = np.sign(ef - es)
        ef += af * (lp[t] - ef); es += a_s * (lp[t] - es)
    return pos


def est_vol(x, span=36):
    a = 2 / (span + 1); v = np.full(x.shape[1], np.mean(x[:60] ** 2, axis=0)); out = np.zeros_like(x)
    for t in range(x.shape[0]):
        out[t] = np.sqrt(v); v += a * (x[t] ** 2 - v)
    return out


def rules(p):
    """name -> (T, N) positions decided with information up to t-1."""
    y = p.y
    r = {}
    r["trend EWMAC16/64"] = ewmac_sign(y, 16, 64)
    r["trend oracle sign(m[t-1])"] = lagged(np.sign(p.m))
    r["carry sign(rate[t-1])"] = lagged(np.sign(p.rate))
    mom = np.zeros_like(y); acc = np.zeros(y.shape[1]); a = 2 / 61
    for t in range(y.shape[0]):
        mom[t] = acc; acc = acc + a * (y[t] - acc)
    r["xsmom rank EWMA60"] = np.sign(mom - mom.mean(axis=1, keepdims=True))
    r["season oracle tom*dir"] = p.tom[:, None] * p.season_dir[None, :] * np.ones_like(y)
    return r


def main():
    ov = other_var(LabSpec())
    target = 0.5
    cases = {
        "null": Effect(),
        "trend": Effect(trend_sr=target, trend_halflife=60),
        "carry": Effect(carry_sr=target),
        "xsmom": Effect(xsmom_sr=target, xsmom_halflife=60),
        "season": Effect(season_sr=target),
    }
    vm = v_m_for(target, _phi(60), ov)
    print(f"target per-instrument SR {target}: trend oracle {target} -> EWMAC16/64 theory "
          f"{theory_ewmac(vm, _phi(60), ov, 16, 64):.3f}; carry rule {target}; xsmom oracle {target}; "
          f"season oracle {target}")
    acc = {}
    for name, eff in cases.items():
        for seed in range(1, SEEDS + 1):
            p = generate(LabSpec(seed=seed, effect=eff))
            ev = est_vol(p.x)
            for rn, pos in rules(p).items():
                acc.setdefault((name, rn, "vol-units"), []).append(sr(pos * p.y).mean())
                acc.setdefault((name, rn, "est-vol x"), []).append(sr(pos * p.x / ev).mean())
    print(f"{'market':7s} {'rule':28s} {'grading':10s} {'mean SR/inst':>12s} {'se':>7s}")
    for (m, rn, g), v in acc.items():
        v = np.array(v)
        print(f"{m:7s} {rn:28s} {g:10s} {v.mean():+12.3f} {v.std(ddof=1) / math.sqrt(len(v)):7.3f}")


if __name__ == "__main__":
    main()
