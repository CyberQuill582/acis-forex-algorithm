"""R1-C stylized-facts probes on the lab prototype (gen_lab.py). Synthetic only.

Targets are QUOTED from Cont (2001), Quantitative Finance 1:223-236 (see R1C_SYNTH_LAB.md, Sources); the
numeric tolerances marked 'lab tolerance' are R1-C's (LLM-originated) operationalisation of a qualitative
fact, NOT values computed from any market data. Each check prints PASS/FAIL with its statistic.
Usage: OMP_NUM_THREADS=1 python probe_stylized.py [seeds] [variant]    variant: lab (default) | garch11
"""
import math
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from gen_lab import LabSpec, generate, intraday_panel, HOUR_VAR   # noqa: E402

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 4
VARIANT = sys.argv[2] if len(sys.argv) > 2 else "lab"


def acf(x, lags):
    x = x - x.mean()
    d = float(np.dot(x, x))
    return np.array([float(np.dot(x[:-k], x[k:])) / d for k in lags])


def hill(absx, frac=0.025):
    s = np.sort(absx)[::-1]
    k = max(10, int(frac * len(s)))
    return 1.0 / np.mean(np.log(s[:k] / s[k]))


def report(name, ok, stat, tol):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:38s} {stat:48s} tolerance: {tol}")
    return ok


def main():
    kw = {}
    if VARIANT == "garch11":
        kw.update(garch=((1.0, 0.05, 0.94),), sv_sd=0.0)   # a single GARCH(1,1): the known slow-decay failure
    import json, os
    kw.update({k: (tuple(map(tuple, v)) if k == "garch" else v)
               for k, v in json.loads(os.environ.get("LAB_KW", "{}")).items()})   # knob sweeps
    res = {k: [] for k in ("acf_frac", "hill", "kurt1", "kurt5", "kurt20", "skew", "absacf1_5",
                           "beta", "r2_pow", "r2_exp", "ckurt", "ukurt", "corr", "monday")}
    lags = np.arange(1, 21)
    alags = np.arange(1, 101)
    for seed in range(1, SEEDS + 1):
        p = generate(LabSpec(seed=seed, **kw))
        x = p.x
        T, N = x.shape
        band = 1.96 / math.sqrt(T)
        absacf = np.zeros(len(alags))
        for i in range(N):
            xi = x[:, i]
            a = acf(xi, lags)
            # heteroskedasticity-robust band: under volatility clustering the iid band 1.96/sqrt(T) is
            # too narrow (Cont 2001 on sample ACFs of heavy-tailed dependent series); se_k from x_t^2 x_{t-k}^2
            xc = xi - xi.mean(); d = float(np.dot(xc, xc))
            se = np.array([math.sqrt(float(np.dot(xc[:-k] ** 2, xc[k:] ** 2))) / d for k in lags])
            res["acf_frac"].append(np.mean(np.abs(a) > 1.96 * se))
            z = xi / xi.std()
            res["hill"].append(hill(np.abs(z)))
            res["kurt1"].append(stats.kurtosis(xi))
            res["kurt5"].append(stats.kurtosis(xi[: T // 5 * 5].reshape(-1, 5).sum(1)))
            res["kurt20"].append(stats.kurtosis(xi[: T // 20 * 20].reshape(-1, 20).sum(1)))
            res["skew"].append(stats.skew(xi))
            ab = acf(np.abs(xi), alags)
            absacf += ab / N
            res["absacf1_5"].append(ab[:5].mean())
            res["ckurt"].append(stats.kurtosis(xi / p.sigma[:, i]) + 3)
            res["ukurt"].append(stats.kurtosis(xi) + 3)
        # slow decay: power-law vs exponential fit of the (instrument-averaged) |r| ACF, lags 1..100
        ok = absacf > 0
        lx, ly = np.log(alags[ok]), np.log(absacf[ok])
        sl, ic, r, *_ = stats.linregress(lx, ly)
        _, _, re_, *_ = stats.linregress(alags[ok], ly)
        res["beta"].append(-sl); res["r2_pow"].append(r * r); res["r2_exp"].append(re_ * re_)
        c = np.corrcoef(x.T)
        res["corr"].append(np.abs(c[np.triu_indices(N, 1)]).mean())
        mon = np.isin(np.arange(T), np.flatnonzero(p.gap[:, 0] != 0))
        res["monday"].append(np.mean([(x[mon, i] / p.sigma[mon, i]).var() / (x[~mon, i] / p.sigma[~mon, i]).var()
                                      for i in range(N)]))
    R = {k: float(np.mean(v)) for k, v in res.items()}
    print(f"variant={VARIANT}  seeds={SEEDS}  instruments=20  weekdays=3640 per seed  (null lab, no planted effect)")
    out = []
    out.append(report("1 absence of linear autocorrelation", R["acf_frac"] <= 0.10,
                      f"share of |acf(1..20)| > 1.96 robust se: {R['acf_frac']:.3f}", "<= 0.10 (lab tolerance; 0.05 nominal)"))
    out.append(report("2 heavy tails (tail index 2 < a < 5)", 2.0 < R["hill"] < 5.0,
                      f"Hill alpha (top 2.5%) {R['hill']:.2f}; excess kurt {R['kurt1']:.2f}", "Cont: 'higher than two and less than five'"))
    out.append(report("3 gain/loss asymmetry ABSENT for FX", abs(R["skew"]) < 0.2,
                      f"mean skew {R['skew']:+.3f}", "|skew| < 0.2 (lab tol.; Cont fn 2)"))
    out.append(report("4 aggregational Gaussianity", R["kurt1"] > R["kurt5"] > R["kurt20"] and R["kurt20"] < 0.5 * R["kurt1"],
                      f"excess kurt 1d {R['kurt1']:.2f} > 5d {R['kurt5']:.2f} > 20d {R['kurt20']:.2f}", "monotone, 20d < half of 1d (lab tol.)"))
    out.append(report("6 volatility clustering", R["absacf1_5"] > 0.05,
                      f"mean acf(|r|) lags 1-5 {R['absacf1_5']:.3f}", "> 0.05 (lab tolerance)"))
    out.append(report("7 conditional heavy tails", 3.0 < R["ckurt"] < R["ukurt"],
                      f"kurt(r/sigma) {R['ckurt']:.2f} < kurt(r) {R['ukurt']:.2f}", "3 < conditional < unconditional"))
    out.append(report("8 slow decay of |r| acf (power law)", 0.2 <= R["beta"] <= 0.4 and R["r2_pow"] > R["r2_exp"],
                      f"beta {R['beta']:.3f}; R2 power {R['r2_pow']:.3f} vs exp {R['r2_exp']:.3f}", "Cont: beta in [0.2, 0.4]; power fits better"))
    print(f"  [info] mean |pairwise corr| {R['corr']:.3f} (spec rho 0.30);  Monday/weekday var ratio {R['monday']:.3f} (spec 1.25)")
    print("  [n/a ] 5 intermittency, 9 leverage (equity), 10 volume, 11 time-scale asymmetry: not modelled / not asserted")
    # intraday seasonality: self-consistency with the lab's declared session shape (NOT a literature calibration)
    p = generate(LabSpec(seed=1, **kw))
    byhour = np.zeros(24); roll = []; hour_off = []
    for t in range(0, 400):
        d = intraday_panel(p, t, tick_seconds=60)
        h = d["hours"]
        byhour += np.bincount(h, weights=(np.abs(d["logret"]) / p.sigma[t][:, None]).mean(axis=0), minlength=24)
        sp = d["spread_frac"].mean(axis=0)
        roll.append(sp[:5].mean()); hour_off.append(0.5 * (sp[60:65].mean() + sp[-60:-55].mean()))
    cr = np.corrcoef(byhour, np.sqrt(HOUR_VAR))[0, 1]
    ratio = float(np.mean(roll) / np.mean(hour_off))
    out.append(report("S intraday vol seasonality (self-cons.)", cr > 0.9,
                      f"corr(mean|r| by UTC hour, sqrt(profile)) {cr:.3f}", "> 0.9; shape is a lab knob"))
    out.append(report("S rollover spread spike at 17:00 New York", ratio > 3.0,
                      f"spread first 5 min / one hour off {ratio:.1f}x", "> 3x (knob 8x; ACIS_SPEC.md:407 records 6-13x)"))
    print(f"SUMMARY variant={VARIANT}: {sum(out)}/{len(out)} PASS")


if __name__ == "__main__":
    main()
