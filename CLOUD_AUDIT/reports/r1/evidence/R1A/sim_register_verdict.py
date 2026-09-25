"""R1-A receipt: register-level verdict rules under an ADAPTIVE researcher, and held-out instruments.

LLM-originated design (Opus 5.5, lane R1-A). Synthetic only. Run:
  OMP_NUM_THREADS=1 python sim_register_verdict.py <world> <R>     world in null | idio | idio_weak | factor | idio_strong  [mu]
World: 28 instruments (20 development + 8 held out), factor-correlated daily returns (price corr 0.3),
260-day burn-in, 12 development years, 2 forward years.  Planted: 'idio' = per-instrument persistent
Markov drift (mean spell 60 d); 'factor' = the same drift on the common factor (all instruments trend together).
Pool: 7 families x 11 params x 2 forms x 5 universes = 770 pooled configs (dev instruments only).
Researcher: 200 registered runs, adaptive: 30% explore (new family preferred), 70% hill-climb from the
best-so-far (one coordinate changed). Verdicts computed on the first K in {20,50,100,200} runs.
"""
import json
import math
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd
from scipy.signal import lfilter
from scipy.stats import norm

YEAR = 252
BURN, DEV, FWD = 260, 12 * YEAR, 2 * YEAR
T = BURN + DEV + FWD
NDEV, NHO = 20, 8
NI = NDEV + NHO
RHO = 0.3
PARAMS = [2, 3, 5, 8, 12, 16, 24, 32, 48, 64, 96]
FAMS = ["ewmac", "breakout", "tsmom", "reversal", "calendar", "xsmom", "volfilt"]
NF, NP, NFORM, NU = len(FAMS), len(PARAMS), 2, 5
KS = [20, 50, 100, 200]
B = 300
LAMS = np.array([0.05, 0.1, 0.2, 0.4, 0.8])


def gen(world, rng, mu):
    f = rng.standard_normal(T)
    e = rng.standard_normal((NI, T))
    r = math.sqrt(RHO) * f[None, :] + math.sqrt(1 - RHO) * e
    if world.startswith("idio"):
        s = np.empty((NI, T))
        st = rng.choice([-1.0, 1.0], NI)
        flips = rng.random((NI, T)) < 1 / 60
        for t in range(T):
            st = np.where(flips[:, t], -st, st)
            s[:, t] = st
        r = r + mu * s
    elif world == "factor":
        st = rng.choice([-1.0, 1.0])
        flips = rng.random(T) < 1 / 60
        s = np.empty(T)
        for t in range(T):
            if flips[t]:
                st = -st
            s[t] = st
        r = r + mu * s[None, :]
    return r


def ema(x, span):
    a = 2 / (span + 1)
    return lfilter([a], [1, -(1 - a)], x, axis=1)


def norm_pos(x, form):
    if form == 1:
        return np.sign(x)
    sd = x[:, BURN:].std(axis=1, keepdims=True) + 1e-12
    return np.clip(x / sd, -2, 2) / 2


def positions(fam, p, form, r):
    price = np.cumsum(r, axis=1)
    if fam == "ewmac":
        return norm_pos(ema(price, p) - ema(price, 4 * p), form)
    if fam == "reversal":
        return -norm_pos(pd.DataFrame(r.T).rolling(max(1, p // 2)).sum().fillna(0).values.T, form)
    if fam == "tsmom":
        L = 3 * p
        return norm_pos(pd.DataFrame(price.T).diff(L).fillna(0).values.T, form)
    if fam == "breakout":
        L = 2 * p + 2
        df = pd.DataFrame(price.T)
        hi = df.rolling(L).max().values.T
        lo = df.rolling(L).min().values.T
        mid = (hi + lo) / 2
        rng_ = np.maximum(hi - lo, 1e-9)
        x = np.nan_to_num((price - mid) / rng_ * 2)
        return np.sign(x) if form == 1 else np.clip(x, -1, 1)
    if fam == "calendar":
        t = np.arange(T)
        conds = [t % 5 == 0, t % 5 == 1, t % 5 == 2, t % 5 == 3, t % 5 == 4,
                 t % 21 == 0, t % 21 <= 1, (t % 21 >= 20) | (t % 21 == 0),
                 t % 21 == 10, (t % 21 >= 9) & (t % 21 <= 11), t % 63 <= 2]
        sgn = 1.0 if form == 0 else -1.0
        return np.tile(np.where(conds[PARAMS.index(p)], sgn, 0.0), (r.shape[0], 1))
    if fam == "xsmom":
        L = 3 * p
        mom = pd.DataFrame(price.T).diff(L).fillna(0).values.T
        rk = mom.argsort(0).argsort(0) / (r.shape[0] - 1) - 0.5
        return (rk * 2) if form == 0 else np.sign(rk)
    if fam == "volfilt":
        base = norm_pos(ema(price, p) - ema(price, 4 * p), 0)
        vol = pd.DataFrame(r.T).rolling(60).std().values.T
        med = pd.DataFrame(vol.T).expanding(250).median().values.T
        keep = (vol < med) if form == 0 else (vol >= med)
        return np.where(np.nan_to_num(keep.astype(float)) > 0, base, 0.0)
    raise ValueError(fam)


GROUPS = [np.arange(NDEV)] + [np.arange(g * 5, g * 5 + 5) for g in range(4)]


def cid(fi, pi, fo, u):
    return ((fi * NP + pi) * NFORM + fo) * NU + u


def build(r):
    """Returns dev P&L matrix (770, DEV), fwd matrix (770, FWD), heldout base P&L dicts."""
    M = NF * NP * NFORM * NU
    dev = np.empty((M, DEV))
    fwd = np.empty((M, FWD))
    ho = {}
    for fi, fam in enumerate(FAMS):
        for pi, p in enumerate(PARAMS):
            for fo in range(NFORM):
                pos = positions(fam, p, fo, r) if fam != "xsmom" else None
                if fam == "xsmom":
                    pos_dev = positions(fam, p, fo, r[:NDEV])
                    pos_ho = positions(fam, p, fo, r[NDEV:])
                    pnl_dev_inst = pos_dev[:, :-1] * r[:NDEV, 1:]
                    pnl_ho_inst = pos_ho[:, :-1] * r[NDEV:, 1:]
                else:
                    pnl = pos[:, :-1] * r[:, 1:]
                    pnl_dev_inst, pnl_ho_inst = pnl[:NDEV], pnl[NDEV:]
                for u, g in enumerate(GROUPS):
                    if fam == "xsmom" and u > 0:
                        pg = positions(fam, p, fo, r[g])
                        s = (pg[:, :-1] * r[g, 1:]).mean(0)
                    else:
                        s = pnl_dev_inst[g].mean(0)
                    c = cid(fi, pi, fo, u)
                    dev[c] = s[BURN - 1: BURN - 1 + DEV]
                    fwd[c] = s[BURN - 1 + DEV:]
                h = pnl_ho_inst.mean(0)
                ho[(fi, pi, fo)] = (h[BURN - 1: BURN - 1 + DEV], h[BURN - 1 + DEV:])
    return dev, fwd, ho


def tstat(x):
    return x.mean(-1) / (x.std(-1, ddof=1) / math.sqrt(x.shape[-1]) + 1e-18)


def researcher(sr, rng, K):
    tried, seen_f = [], set()
    best = None
    untried = set(range(len(sr)))
    for k in range(K):
        cand = None
        if best is not None and k >= 3 and rng.random() < 0.7:
            fi, rem = divmod(best, NP * NFORM * NU)
            pi, rem = divmod(rem, NFORM * NU)
            fo, u = divmod(rem, NU)
            neigh = []
            for dp in (-2, -1, 1, 2):
                if 0 <= pi + dp < NP:
                    neigh.append(cid(fi, pi + dp, fo, u))
            neigh.append(cid(fi, pi, 1 - fo, u))
            for uu in range(NU):
                if uu != u:
                    neigh.append(cid(fi, pi, fo, uu))
            neigh = [c for c in neigh if c in untried]
            if neigh:
                cand = neigh[rng.integers(len(neigh))]
        if cand is None:
            fams = [f for f in range(NF) if f not in seen_f]
            fi = fams[rng.integers(len(fams))] if (fams and rng.random() < 0.5) else rng.integers(NF)
            pool = [c for c in range(fi * NP * NFORM * NU, (fi + 1) * NP * NFORM * NU) if c in untried]
            if not pool:
                pool = list(untried)
            cand = pool[rng.integers(len(pool))]
        tried.append(cand)
        untried.discard(cand)
        seen_f.add(cand // (NP * NFORM * NU))
        if best is None or sr[cand] > sr[best]:
            best = cand
    return tried


def maxt_crit(X, rng, W):
    """95% critical value of max studentised mean under H0 by multiplier bootstrap (block 10)."""
    Xc = X - X.mean(1, keepdims=True)
    sd = X.std(1, ddof=1, keepdims=True) + 1e-18
    Z = (Xc / sd) @ W / math.sqrt(X.shape[1])
    return np.quantile(Z.max(0), 0.95)


def e_mix(X):
    x = np.maximum(X / 6.0, -1)          # unit-variance P&L: clip at -6 sd (tripwire; never binds here)
    lw = np.stack([np.log1p(l * x).sum(1) for l in LAMS], 0)
    m = lw.max(0)
    return np.exp(m + np.log(np.exp(lw - m).mean(0)))


def one_rep(args):
    world, mu, seed = args
    rng = np.random.default_rng(seed)
    r = gen(world, rng, mu)
    dev, fwd, ho = build(r)
    sr = tstat(dev)
    tried_all = researcher(sr, rng, max(KS))
    nb = DEV // 10 + 1
    W = np.repeat(rng.standard_normal((nb, B)), 10, axis=0)[:DEV]
    out = {}
    per_fam = NP * NFORM * NU
    # family combination streams: equal weight over params x forms, universe = all dev instruments
    combo = np.stack([dev[[cid(fi, pi, fo, 0) for pi in range(NP) for fo in range(NFORM)]].mean(0)
                      for fi in range(NF)])
    combo_fwd = np.stack([fwd[[cid(fi, pi, fo, 0) for pi in range(NP) for fo in range(NFORM)]].mean(0)
                          for fi in range(NF)])
    t_combo = tstat(combo)
    t_combo_fwd = tstat(combo_fwd)
    for K in KS:
        tr = np.array(tried_all[:K])
        best = tr[np.argmax(sr[tr])]
        tb = sr[best]
        fams = sorted(set(int(c) // per_fam for c in tr))
        grid = np.concatenate([np.arange(f * per_fam, (f + 1) * per_fam) for f in fams])
        o = {}
        o["naive_best"] = bool(tb > 1.645)
        o["bonf_K"] = bool(tb > norm.ppf(1 - 0.05 / K))
        o["maxt_tried"] = bool(tb > maxt_crit(dev[tr], rng, W))
        o["maxt_declared_grid"] = bool(sr[grid].max() > maxt_crit(dev[grid], rng, W))
        o["famcombo_holm"] = bool(t_combo[fams].max() > norm.ppf(1 - 0.05 / len(fams)))
        ev = e_mix(dev[tr])
        o["e_bonf_K"] = bool(ev.max() >= K / 0.05)
        o["fwd_once_best"] = bool(tstat(fwd[best]) > 1.645)
        fbest = fams[int(np.argmax(t_combo[fams]))]
        o["fwd_once_famcombo"] = bool(t_combo_fwd[fbest] > 1.645)
        fi, rem = divmod(int(best), per_fam)
        pi, rem = divmod(rem, NFORM * NU)
        fo, u = divmod(rem, NU)
        h_dev, h_fwd = ho[(fi, pi, fo)]
        d = dev[best]
        beta = np.cov(h_dev, d)[0, 1] / (d.var(ddof=1) + 1e-18)
        o["heldout_raw_samewindow"] = bool(tstat(h_dev) > 1.645)
        o["heldout_resid_samewindow"] = bool(tstat(h_dev - beta * d) > 1.645)
        o["heldout_forward"] = bool(tstat(h_fwd) > 1.645)
        o["KILL_heldout_resid_lt0"] = bool(tstat(h_dev - beta * d) < 0)
        o["KILL_heldout_raw_lt0"] = bool(tstat(h_dev) < 0)
        o["KILL_fwd2y_best_lt0"] = bool(tstat(fwd[best]) < 0)
        o["n_fams"] = len(fams)
        o["best_dev_annSR"] = float(tb / math.sqrt(DEV) * math.sqrt(YEAR))
        o["best_fwd_annSR"] = float(fwd[best].mean() / fwd[best].std() * math.sqrt(YEAR))
        out[K] = o
    # fixed pre-registered reference: ewmac speed 16 linear, all dev instruments
    ref = cid(0, PARAMS.index(16), 0, 0)
    out["ref_fwd_annSR"] = float(fwd[ref].mean() / fwd[ref].std() * math.sqrt(YEAR))
    out["ref_dev_annSR"] = float(dev[ref].mean() / dev[ref].std() * math.sqrt(YEAR))
    out["ewmac_combo_dev_annSR"] = float(combo[0].mean() / combo[0].std() * math.sqrt(YEAR))
    out["oracle_best_dev_annSR"] = float(sr.max() / math.sqrt(DEV) * math.sqrt(YEAR))
    return out


def wilson(k, n):
    if n == 0:
        return (0, 0)
    p = k / n
    z = 1.96
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


if __name__ == "__main__":
    world = sys.argv[1]
    R = int(sys.argv[2])
    mu = {"null": 0.0, "idio": 0.08, "idio_weak": 0.05, "idio_strong": 0.10, "factor": 0.08}[world]
    if len(sys.argv) > 3:
        mu = float(sys.argv[3])
    with Pool(2) as p:
        reps = p.map(one_rep, [(world, mu, 777000 + i) for i in range(R)], chunksize=4)
    keys = [k for k in reps[0][KS[0]] if isinstance(reps[0][KS[0]][k], bool)]
    summ = {"world": world, "mu": mu, "R": R}
    for K in KS:
        row = {}
        for k in keys:
            n = sum(rp[K][k] for rp in reps)
            row[k] = {"pct": round(100 * n / R, 1), "wilson95": wilson(n, R)}
        row["mean_n_fams"] = float(np.mean([rp[K]["n_fams"] for rp in reps]))
        row["mean_best_dev_annSR"] = float(np.mean([rp[K]["best_dev_annSR"] for rp in reps]))
        row["mean_best_fwd_annSR"] = float(np.mean([rp[K]["best_fwd_annSR"] for rp in reps]))
        summ[f"K{K}"] = row
    for k in ("ref_fwd_annSR", "ref_dev_annSR", "ewmac_combo_dev_annSR", "oracle_best_dev_annSR"):
        summ[k] = float(np.mean([rp[k] for rp in reps]))
    tag = world if len(sys.argv) <= 3 else f"{world}_mu{sys.argv[3].replace('.', '')}"
    with open(f"sim_out_register_{tag}.json", "w") as fh:
        json.dump(summ, fh, indent=1)
    print(json.dumps(summ, indent=1))
