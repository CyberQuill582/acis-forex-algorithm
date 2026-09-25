"""R1-A receipt: anytime-valid e-processes for the demo forward record (synthetic only).

LLM-originated design (Opus 5.5, lane R1-A). Not an implementation; a receipt.
Run:  OMP_NUM_THREADS=1 python sim_eprocess_demo.py [R]   -> sim_out_eprocess.json

Edge test, H0: E[r_t | past] <= 0 (daily net P&L as a fraction of equity).
  E_BET  : one-sided testing-by-betting, x_t = clip(r_t/(C*SIG), -1, 1), SIG = the DECLARED daily
           vol target (a pre-registered constant, not estimated), bet lambda_t predictable
           (aGRAPA-style plug-in mean/(var+mean^2), clipped to [0, 0.8]).  W_t = prod(1+lambda_t x_t).
  E_MIX  : average of constant-lambda betting wealths, lambda in {0.05,0.1,0.2,0.4,0.8}.
  E_NMIX : one-sided half-normal-mixture SPRT with KNOWN sigma = SIG (Robbins / mSPRT form).
  NAIVE  : one-sided t-test repeated every day (p < 0.05) -- the thing NOT to do.
Kill test, H0: E[r_t] >= mu_claim  (same betting e-process on x' = clip((mu_claim - r)/(C*SIG)))
Cost-gap test on paired fills d_i = realised - modelled cost (units: modelled cost per fill):
  breach  H0: E[d] <= +DELTA ;  certify-inside  = both H0: E[d] >= +DELTA and H0: E[d] <= -DELTA rejected.
"""
import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np
from scipy.stats import norm

SIG = 0.005          # declared daily vol target (0.5%/day ~ 7.9%/yr)
C = 6.0              # clip scale in declared sigmas
YEAR = 252
DAYS = 20 * YEAR     # 20-year horizon for hitting times
CHECK_Y = [0.25, 0.5, 1, 2, 3, 5, 10, 20]
LAM_GRID = np.array([0.05, 0.1, 0.2, 0.4, 0.8])
LAM_MAX = 0.8
RHO_NMIX = 0.06      # mixture scale in standardised units (tuned for SR~1 over 1-5 y)
BATCH = 250


def gen_returns(dist, sr, n, T, rng):
    mu = sr * SIG / math.sqrt(YEAR)
    if dist == "gauss":
        e = rng.standard_normal((n, T))
    elif dist == "t4":
        e = rng.standard_t(4, (n, T)) / math.sqrt(2.0)
    elif dist == "volmis":           # sizing error: true vol 1.5x the declared target
        e = 1.5 * rng.standard_normal((n, T))
    elif dist == "skewL":            # left-skewed: rare -6 sd-ish losses, mean 0, var 1
        p, J = 0.01, -6.0
        jump = (rng.random((n, T)) < p) * J
        base = rng.standard_normal((n, T))
        m = p * J
        v = p * (1 - p) * J * J
        e = (base * math.sqrt(max(1 - v, 1e-9)) + jump - m)
    elif dist == "garch":            # GARCH(1,1) a=.06 b=.92, t5 innovations, unit unconditional var
        a, b = 0.06, 0.92
        om = 1 - a - b
        z = rng.standard_t(5, (n, T)) / math.sqrt(5 / 3)
        e = np.empty((n, T))
        h = np.ones(n)
        for t in range(T):
            e[:, t] = np.sqrt(h) * z[:, t]
            h = om + a * e[:, t] ** 2 + b * h
    else:
        raise ValueError(dist)
    return mu + SIG * e


def bet_agrapa(x):
    """x: (n,T) in [-1,1]. Returns log-wealth path (n,T). Predictable plug-in bet."""
    n, T = x.shape
    logw = np.empty((n, T))
    s = np.zeros(n)
    s2 = np.zeros(n)
    lw = np.zeros(n)
    n0 = 20.0                       # pseudo-count prior: mean 0, var (1/C)^2
    v0 = (1.0 / C) ** 2
    for t in range(T):
        k = t + n0
        m = s / k
        v = (s2 + n0 * v0) / k - m * m
        lam = np.clip(m / (v + m * m), 0.0, LAM_MAX)
        lw = lw + np.log1p(lam * x[:, t])
        logw[:, t] = lw
        s += x[:, t]
        s2 += x[:, t] ** 2
    return logw


def bet_mix(x):
    lws = [np.cumsum(np.log1p(l * x), axis=1) for l in LAM_GRID]
    st = np.stack(lws, 0)
    mx = st.max(0)
    return mx + np.log(np.exp(st - mx).mean(0))


def nmix_known_sigma(r):
    S = np.cumsum(r / SIG, axis=1)
    t = np.arange(1, r.shape[1] + 1)[None, :]
    a = 1 + RHO_NMIX ** 2 * t
    z = RHO_NMIX * S / np.sqrt(a)
    return math.log(2) - 0.5 * np.log(a) + 0.5 * z * z + norm.logcdf(z)


def naive_first_reject(r):
    T = r.shape[1]
    cs = np.cumsum(r, axis=1)
    cs2 = np.cumsum(r * r, axis=1)
    t = np.arange(1, T + 1)[None, :]
    m = cs / t
    v = np.maximum(cs2 / t - m * m, 1e-18) * t / np.maximum(t - 1, 1)
    tstat = m / np.sqrt(v / t)
    tstat[:, :20] = -np.inf
    return tstat > 1.645


def first_hit(logw, thr):
    hit = logw >= thr
    anyh = hit.any(1)
    idx = np.where(anyh, hit.argmax(1), -1)
    return idx


def summarize_hits(idx_list, T):
    idx = np.concatenate(idx_list)
    n = len(idx)
    out = {}
    for y in CHECK_Y:
        d = int(y * YEAR)
        if d <= T:
            out[f"P_by_{y}y"] = float(((idx >= 0) & (idx < d)).mean())
    hit = np.where(idx >= 0, idx + 1, np.inf)
    med = np.median(hit)
    out["median_days"] = None if not np.isfinite(med) else float(med)
    out["median_years"] = None if not np.isfinite(med) else round(float(med) / YEAR, 2)
    out["mean_capped_years"] = float(np.minimum(hit, T).mean() / YEAR)
    out["n"] = n
    return out


def edge_cell(args):
    dist, sr, R, seed = args
    rng = np.random.default_rng(seed)
    res = {k: {20: [], 100: []} for k in ("E_BET", "E_MIX", "E_NMIX")}
    naive = []
    for b in range(0, R, BATCH):
        n = min(BATCH, R - b)
        r = gen_returns(dist, sr, n, DAYS, rng)
        x = np.clip(r / (C * SIG), -1, 1)
        paths = {"E_BET": bet_agrapa(x), "E_MIX": bet_mix(x), "E_NMIX": nmix_known_sigma(r)}
        for k, lw in paths.items():
            for thr in (20, 100):
                res[k][thr].append(first_hit(lw, math.log(thr)))
        nv = naive_first_reject(r[:, : 10 * YEAR])
        naive.append(np.where(nv.any(1), nv.argmax(1), -1))
    out = {"dist": dist, "sr": sr}
    for k in res:
        out[k] = {f"e>={thr}": summarize_hits(res[k][thr], DAYS) for thr in (20, 100)}
    out["NAIVE_daily_ttest"] = summarize_hits(naive, 10 * YEAR)
    return out


def kill_cell(args):
    dist, sr_true, sr_claim, R, seed = args
    rng = np.random.default_rng(seed)
    mu_c = sr_claim * SIG / math.sqrt(YEAR)
    hits = {5: [], 20: []}
    for b in range(0, R, BATCH):
        n = min(BATCH, R - b)
        r = gen_returns(dist, sr_true, n, 10 * YEAR, rng)
        x = np.clip((mu_c - r) / (C * SIG), -1, 1)
        lw = bet_agrapa(x)
        for thr in hits:
            hits[thr].append(first_hit(lw, math.log(thr)))
    return {"dist": dist, "sr_true": sr_true, "sr_claim": sr_claim,
            **{f"kill_e>={thr}": summarize_hits(hits[thr], 10 * YEAR) for thr in hits}}


def cost_noise(n, T, rng, sd):
    # right-skewed paired-difference noise: t3 core + 2% adverse spikes of +5 modelled costs, centred
    core = rng.standard_t(3, (n, T)) / math.sqrt(3.0)
    spike = (rng.random((n, T)) < 0.02) * 5.0
    e = core + spike - 0.02 * 5.0
    return sd * e / math.sqrt(1 + 0.02 * 0.98 * 25)


def cost_cell(args):
    gap, sd, delta, R, seed = args[:5]
    CD = args[5] if len(args) > 5 else 5.0   # clip scale in modelled costs; must bound the ADVERSE tail
    rng = np.random.default_rng(seed)
    NF = 5000
    out = {"gap": gap, "sd": sd, "delta": delta, "CD": CD}
    clipped = 0
    br, lo, hi, both = [], [], [], []
    for b in range(0, R, BATCH):
        n = min(BATCH, R - b)
        d = gap + cost_noise(n, NF, rng, sd)
        clipped += int((np.abs(d) > CD - delta).sum())
        lw_breach = bet_agrapa(np.clip((d - delta) / CD, -1, 1))
        lw_up = bet_agrapa(np.clip((delta - d) / CD, -1, 1))     # rejects E[d] >= +delta
        lw_dn = bet_agrapa(np.clip((d + delta) / CD, -1, 1))     # rejects E[d] <= -delta
        thr = math.log(20)
        br.append(first_hit(lw_breach, thr))
        hu = first_hit(lw_up, thr)
        hd = first_hit(lw_dn, thr)
        both.append(np.where((hu >= 0) & (hd >= 0), np.maximum(hu, hd), -1))
    def summ(lst):
        idx = np.concatenate(lst)
        hit = np.where(idx >= 0, idx + 1, np.inf)
        med = np.median(hit)
        return {"P_by_100": float(((idx >= 0) & (idx < 100)).mean()),
                "P_by_250": float(((idx >= 0) & (idx < 250)).mean()),
                "P_by_500": float(((idx >= 0) & (idx < 500)).mean()),
                "P_by_1000": float(((idx >= 0) & (idx < 1000)).mean()),
                "P_by_5000": float((idx >= 0).mean()),
                "median_fills": None if not np.isfinite(med) else float(med)}
    out["frac_obs_beyond_clip"] = clipped / (R * NF)
    out["breach_e>=20"] = summ(br)
    out["certify_inside_e>=20"] = summ(both)
    return out


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "costonly":
    R = int(sys.argv[1])
    args = [(g, sd, 0.25, R, 9000 + i * 7 + j, CD) for i, CD in enumerate((5.0, 20.0))
            for j, (g, sd) in enumerate([(a, b) for a in (0.0, 0.25, 0.5, 1.0) for b in (0.5, 1.0, 2.0)])]
    with Pool(2) as p:
        cost = p.map(cost_cell, args)
    d = json.load(open("sim_out_eprocess.json"))
    d["cost"] = cost
    json.dump(d, open("sim_out_eprocess.json", "w"), indent=1)
    print("cost done")
elif __name__ == "__main__":
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    edge_args = []
    s = 1000
    for dist in ("gauss", "t4", "garch", "skewL", "volmis"):
        for sr in (0.0, 0.5, 1.0, 1.5, 2.0):
            if dist in ("skewL", "volmis") and sr not in (0.0, 1.0):
                continue
            edge_args.append((dist, sr, R, s)); s += 1
    kill_args = [("t4", st, sc, R, 5000 + i) for i, (st, sc) in enumerate(
        [(0.0, 0.5), (0.0, 1.0), (0.0, 1.5), (0.5, 1.0), (0.5, 0.5), (1.0, 1.0), (1.5, 1.5)])]
    cost_args = []
    for CD in (5.0, 20.0):
        for gap in (0.0, 0.25, 0.5, 1.0):
            for sd in (0.5, 1.0, 2.0):
                cost_args.append((gap, sd, 0.25, R, 9000 + len(cost_args), CD))
    with Pool(2) as p:
        edge = p.map(edge_cell, edge_args)
        kill = p.map(kill_cell, kill_args)
        cost = p.map(cost_cell, cost_args)
    meta = {"SIG": SIG, "C": C, "DAYS": DAYS, "R": R, "LAM_GRID": LAM_GRID.tolist(),
            "RHO_NMIX": RHO_NMIX, "LAM_MAX": LAM_MAX}
    with open("sim_out_eprocess.json", "w") as f:
        json.dump({"meta": meta, "edge": edge, "kill": kill, "cost": cost}, f, indent=1)
    print("done")
