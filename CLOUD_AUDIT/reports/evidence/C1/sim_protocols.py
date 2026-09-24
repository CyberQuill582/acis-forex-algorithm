"""C1 CALIBRATOR — independent protocol FPR/power simulator (synthetic data only).

Receipt, not an implementation. Imports the repo's gate READ-ONLY from /tmp/review-acis
(BASE 7695ed04): tests/backtest/deflated_sharpe.py, report.py constants, oos_plan.plan_folds.

World: 8 instruments, daily, 260-day burn-in + 12-year dev span (2012-2023, 12 x 252 d)
+ 2-year holdout (504 d). Nulls: iid Gaussian, GARCH(1,1)-t5, common factor rho=0.4.
Planted: GARCH-t base + a persistent Markov trend state per instrument (mean duration D
days), drift sized so the best config in the pool nets the target annual Sharpe.

Config pool (4,536): 21 base signals (TSMOM L in 12 lookbacks, 9 MA-crossover pairs)
x 3 entry bands x 4 rebalance periods x {trend, reversal} x 9 universes (8 single
instruments + equal-weight basket). Cost 1 bp of notional per unit position change.

Search: a pipeline revision = N configs drawn from the pool; K revisions re-scored on the
same history, keep the best. Protocols scored per replication for every (N, K).
"""
from __future__ import annotations

import itertools
import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/tmp/review-acis")
from tests.backtest import deflated_sharpe as ds          # noqa: E402  (read-only import)
from tests.backtest.report import DSR_MIN, SHARPE_MIN, _MIN_TRIALS  # noqa: E402
from tests.backtest.oos_plan import plan_folds, DATA_START  # noqa: E402
from statistics import NormalDist  # noqa: E402

Z = NormalDist()
SIG = 0.006                    # daily vol per instrument (~9.5% annual)
M = 8
BURN, YEAR = 260, 252
DEV_Y, HOLD_Y = 12, 2
T_DEV, T_H = DEV_Y * YEAR, HOLD_Y * YEAR
T = BURN + T_DEV + T_H
COST = 1e-4                    # per unit |dpos| (1 bp per side; ~2 bp round trip on majors)
TS_L = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
MAC = [(2, 8), (2, 20), (5, 20), (5, 50), (10, 40), (10, 100), (20, 80), (20, 200), (50, 200)]
BANDS = [0.0, 0.5, 1.0]
REBAL = [1, 3, 5, 10]
NS = [int(x) for x in os.environ.get("C1_NS", "1,60,1000").split(",")]
KS = [int(x) for x in os.environ.get("C1_KS", "1,20").split(",")]
B_BOOT, BLOCK = 299, 10
CPCV_S = 10
HOLDOUT_FRAC = 0.20            # config/system_config.yaml:75

# fold layout from the repo's own ratified plan: test years 2014-2023, 2-year train
FOLDS = plan_folds(2014, 2023)
FOLD_IDX = [((f.train_start.year - DATA_START.year) * YEAR + BURN,
             (f.train_end.year - DATA_START.year) * YEAR + BURN,
             (f.test_end.year - DATA_START.year) * YEAR + BURN) for f in FOLDS]
# (embargo of 7 days is irrelevant here: no config reads the future and holds are daily)


def _mac_scale():
    rng = np.random.default_rng(12345)
    p = np.cumsum(rng.standard_normal(200_000))
    out = []
    for f, s in MAC:
        d = _ma(p, f) - _ma(p, s)
        out.append(np.nanstd(d))
    return np.array(out)


def _ma(p, n):
    c = np.cumsum(np.insert(p, 0, 0.0))
    out = np.full(p.shape, np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


MAC_SD = _mac_scale()


# --------------------------------------------------------------------------- worlds
def garch_t(rng, n, m, alpha=0.06, beta=0.92, nu=5.0):
    omega = SIG ** 2 * (1 - alpha - beta)
    z = rng.standard_t(nu, size=(n, m)) / math.sqrt(nu / (nu - 2))
    h = np.full(m, SIG ** 2)
    e = np.empty((n, m))
    for t in range(n):
        e[t] = math.sqrt(1.0) * np.sqrt(h) * z[t]
        h = omega + alpha * e[t] ** 2 + beta * h
    return e


def markov_state(rng, n, m, dur):
    flips = rng.random((n, m)) < 1.0 / dur
    s = np.where(rng.random(m) < 0.5, -1.0, 1.0)
    out = np.empty((n, m))
    for t in range(n):
        s = np.where(flips[t], -s, s)
        out[t] = s
    return out


def gen_world(kind, rng, n=T, mu=0.0, dur=40.0):
    if kind == "iid":
        return rng.standard_normal((n, M)) * SIG
    if kind == "garch":
        return garch_t(rng, n, M)
    if kind == "factor":
        f = rng.standard_normal((n, 1))
        e = rng.standard_normal((n, M))
        return SIG * (math.sqrt(0.4) * f + math.sqrt(0.6) * e)
    if kind == "regime":   # global 2-state Markov volatility: low 0.7 sigma / high 1.6 sigma, spells 150 / 50 d
        st = np.empty(n)
        hi = False
        u = rng.random(n)
        for t in range(n):
            if (hi and u[t] < 1 / 50) or ((not hi) and u[t] < 1 / 150):
                hi = not hi
            st[t] = 1.6 if hi else 0.7
        return rng.standard_normal((n, M)) * SIG * st[:, None]
    if kind == "planted":
        return garch_t(rng, n, M) + mu * SIG * markov_state(rng, n, M, dur)
    raise ValueError(kind)


# --------------------------------------------------------------------------- pool
def build_pool(r):
    """r: (n, M) returns. Returns R (n, P) float32 config returns and meta universe (P,)."""
    n = r.shape[0]
    p = np.cumsum(r, axis=0) / SIG                       # vol-normalised log price
    zs = []
    for L in TS_L:
        z = np.full((n, M), np.nan)
        z[L:] = (p[L:] - p[:-L]) / math.sqrt(L)
        zs.append(z)
    for k, (f, s) in enumerate(MAC):
        z = np.stack([_ma(p[:, i], f) - _ma(p[:, i], s) for i in range(M)], axis=1) / MAC_SD[k]
        zs.append(z)
    zs = np.nan_to_num(np.stack(zs)).astype(np.float32)                     # (21, n, M), NaN -> 0 (flat)
    tidx = np.arange(n)
    r = r.astype(np.float32)
    gross, cost = [], []
    for b in BANDS:
        pos = (np.sign(zs) * (np.abs(zs) > b)).astype(np.float32)             # position decided at close t
        for h in REBAL:
            ph = pos[:, (tidx // h) * h, :]
            held = np.zeros_like(ph)
            held[:, 1:] = ph[:, :-1]                     # position held over day t
            g = held * r[None]                           # (21, n, M)
            dpos = np.abs(np.diff(held, axis=1, prepend=np.float32(0.0)))
            gross.append(g)
            cost.append(np.float32(COST) * dpos)
    gross = np.concatenate(gross)                        # (252, n, M)
    cost = np.concatenate(cost)
    single_g = gross.transpose(1, 0, 2).reshape(n, -1)   # (n, 252*M)
    single_c = cost.transpose(1, 0, 2).reshape(n, -1)
    bask_g = gross.mean(axis=2).T                        # (n, 252)
    bask_c = cost.mean(axis=2).T
    R = np.concatenate([single_g - single_c, -single_g - single_c,
                        bask_g - bask_c, -bask_g - bask_c], axis=1).astype(np.float32)
    nb = gross.shape[0]
    uni_single = np.tile(np.arange(M), nb)
    universe = np.concatenate([uni_single, uni_single, np.full(nb, M), np.full(nb, M)])
    return R, universe


def pool_size():
    return (len(TS_L) + len(MAC)) * len(BANDS) * len(REBAL) * (M + 1) * 2


# --------------------------------------------------------------------------- helpers
class _Rows:
    def __init__(self, c, row):
        self.c, self.row = c, row

    def __getitem__(self, key):
        if isinstance(key, tuple):
            return self.c[self.row[key[0]], key[1]]
        return self.c[self.row[key]]


class Prefix:
    """Window sums at a fixed set of breakpoints (fold edges, CPCV blocks, dev/holdout)."""

    def __init__(self, R):
        bps = {0, R.shape[0], BURN, BURN + T_DEV}
        for a, b, c in FOLD_IDX:
            cut = b - max(1, round((b - a) * HOLDOUT_FRAC))
            bps.update((a, cut, b, c))
        L = T_DEV // CPCV_S
        bps.update(BURN + i * L for i in range(CPCV_S + 1))
        bps = sorted(bps)
        self.row = {v: k for k, v in enumerate(bps)}
        R64 = R.astype(np.float64)
        seg1 = np.add.reduceat(R64, bps[:-1], axis=0)
        np.multiply(R64, R64, out=R64)
        seg2 = np.add.reduceat(R64, bps[:-1], axis=0)
        z = np.zeros((1, R.shape[1]))
        c1 = np.concatenate([z, np.cumsum(seg1, axis=0)])
        c2 = np.concatenate([z, np.cumsum(seg2, axis=0)])
        self.s1 = _Rows(c1, self.row)
        self.s2 = _Rows(c2, self.row)

    def sharpe(self, a, b, cols=None):
        s1 = self.s1[b] - self.s1[a]
        s2 = self.s2[b] - self.s2[a]
        if cols is not None:
            s1, s2 = s1[cols], s2[cols]
        n = b - a
        mean = s1 / n
        var = np.maximum(s2 / n - mean ** 2, 1e-30) * n / (n - 1)
        return mean / np.sqrt(var), mean


def psr_pass(x, sr0):
    m = ds.moments(x.tolist())
    if m is None:
        return False, float("nan")
    v = ds.probabilistic_sharpe(m, sr0)
    return (v >= DSR_MIN), v


def annual(sr_daily):
    return sr_daily * math.sqrt(YEAR)


# --------------------------------------------------------------------------- protocols
def walk_forward(R, pre, universe, cols):
    """One revision. Returns OOS returns, as-built trial list (per fold x universe champion
    holdout Sharpe), exactly mirroring evolve_step: champion per universe by fit window,
    staged = best holdout mean (E_R analogue), trial = its holdout per-period Sharpe."""
    oos, trials = [], []
    uni = universe[cols]
    for a, b, c in FOLD_IDX:
        n_tr = b - a
        cut = b - max(1, round(n_tr * HOLDOUT_FRAC))
        fit_sr, _ = pre.sharpe(a, cut, cols)
        ho_sr, ho_mean = pre.sharpe(cut, b, cols)
        best_c, best_m = None, -np.inf
        for g in np.unique(uni):
            idx = np.nonzero(uni == g)[0]
            j = idx[np.argmax(fit_sr[idx])]
            trials.append(float(ho_sr[j]))
            if ho_mean[j] > best_m:
                best_m, best_c = ho_mean[j], cols[j]
        oos.append(R[b:c, best_c])
    return np.concatenate(oos).astype(np.float64), trials


def cpcv(pre, cols, a0, S=CPCV_S):
    """CSCV/PBO over S equal blocks of the dev span. Returns (pbo, avg OOS Sharpe of selected)."""
    L = T_DEV // S
    edges = [a0 + i * L for i in range(S + 1)]
    s1 = np.stack([pre.s1[edges[i + 1], cols] - pre.s1[edges[i], cols] for i in range(S)])
    s2 = np.stack([pre.s2[edges[i + 1], cols] - pre.s2[edges[i], cols] for i in range(S)])
    combos = np.array(list(itertools.combinations(range(S), S // 2)))
    mask = np.zeros((len(combos), S))
    mask[np.arange(len(combos))[:, None], combos] = 1.0
    n_half = L * S // 2

    def sr(m):
        a1, a2 = m @ s1, m @ s2
        mean = a1 / n_half
        var = np.maximum(a2 / n_half - mean ** 2, 1e-30)
        return mean / np.sqrt(var)
    is_sr, oos_sr = sr(mask), sr(1.0 - mask)
    pick = np.argmax(is_sr, axis=1)
    chosen = oos_sr[np.arange(len(combos)), pick]
    rank = (oos_sr < chosen[:, None]).sum(axis=1) + 1
    w = rank / (len(cols) + 1)
    lam = np.log(w / (1 - w))
    return float((lam <= 0).mean()), float(chosen.mean()), n_half


def boot_weights(rng, n, B=B_BOOT, b=BLOCK):
    """Circular block bootstrap as a (B, n) count matrix."""
    nb = int(math.ceil(n / b))
    W = np.zeros((B, n), dtype=np.float32)
    starts = rng.integers(0, n, size=(B, nb))
    offs = (starts[:, :, None] + np.arange(b)[None, None, :]) % n
    offs = offs.reshape(B, -1)[:, :n]
    for i in range(B):
        np.add.at(W[i], offs[i], 1.0)
    return W


def spa_family(dbar, bmeans, n):
    """Hansen SPA_c p-value and studentised RC/StepM-step-1 p-value for columns given.
    dbar (P,), bmeans (B, P) bootstrap means."""
    omega = np.maximum(bmeans.std(axis=0) * math.sqrt(n), 1e-12)
    t = math.sqrt(n) * dbar / omega
    tobs = max(float(t.max()), 0.0)
    thr = -math.sqrt(2 * math.log(math.log(n)))
    mu_c = np.where(t <= thr, dbar, 0.0)
    centred = math.sqrt(n) * (bmeans - dbar[None]) / omega[None]
    spa_star = np.maximum((centred + math.sqrt(n) * mu_c[None] / omega[None]).max(axis=1), 0.0)
    rc_star = centred.max(axis=1)
    p_spa = float((spa_star >= tobs).mean())
    p_rc = float((rc_star >= float(t.max())).mean())
    return p_spa, p_rc, float(t.max())


def emax(n):
    if n < 2:
        return 0.0
    g = ds.EULER_GAMMA
    return (1 - g) * Z.inv_cdf(1 - 1 / n) + g * Z.inv_cdf(1 - 1 / (n * math.e))


def c_bhy(m):
    return float(np.sum(1.0 / np.arange(1, m + 1)))


# --------------------------------------------------------------------------- one replication
def replicate(kind, seed, mu=0.0, dur=40.0, best_cfg=None):
    rng = np.random.default_rng(seed)
    r = gen_world(kind, rng, mu=mu, dur=dur)
    R, universe = build_pool(r)
    P = R.shape[1]
    pre = Prefix(R)
    a0, a1 = BURN, BURN + T_DEV
    dev_sr, dev_mean = pre.sharpe(a0, a1)
    ho_R = R[a1:]
    W = boot_weights(rng, T_DEV)
    bmeans = (W @ R[a0:a1]) / T_DEV                     # (B, P)
    out = {}
    timing = {}
    for N in NS:
        revs = []
        for k in range(max(KS)):
            if N == 1:
                cols = np.array([best_cfg if (k == 0 and best_cfg is not None) else rng.integers(P)])
            else:
                cols = rng.choice(P, size=N, replace=False)
            revs.append(cols)
        for K in KS:
            rv = revs[:K]
            res = {}
            # ---- walk-forward: as built, naive keep-best, repaired (K-honest), N*K naive DSR
            t0 = time.perf_counter()
            wf = [walk_forward(R, pre, universe, c) for c in rv]
            asb, asb14, naive, dsr_nk = [], [], [], []
            oos_srs = []
            for (x, trials), cols in zip(wf, rv):
                m = ds.moments(x.tolist())
                sr_oos = m.sharpe if m is not None else float("nan")
                oos_srs.append(sr_oos)
                n_tr = len(trials)
                v = ds.deflated_sharpe(x.tolist(), trials, n_tr)
                ok = (n_tr >= _MIN_TRIALS) and (v >= DSR_MIN)
                asb.append(ok)
                asb14.append(ok and annual(sr_oos) > SHARPE_MIN)
                naive.append(psr_pass(x, 0.0)[0])
                # "honest N" naive: all configs ever evaluated, variance of their dev Sharpes
                allc = np.unique(np.concatenate(rv))
                var = max(float(np.var(dev_sr[allc], ddof=1)) if len(allc) > 1 else 0.0, 1.0 / len(x))
                sr0 = ds.expected_max_sharpe(var, len(allc)) if len(allc) > 1 else 0.0
                dsr_nk.append(psr_pass(x, sr0)[0])
            if K == 1:
                x0, tr0 = wf[0]
                st = out.setdefault("stats", {})
                st[f"N{N}_wf_oos_annual_sr"] = annual(oos_srs[0])
                st[f"N{N}_asbuilt_dsr"] = float(ds.deflated_sharpe(x0.tolist(), tr0, len(tr0)))
                st[f"N{N}_asbuilt_sr0_annual"] = annual(ds.sharpe_threshold(tr0, len(tr0)))
                st[f"N{N}_n_trials"] = len(tr0)
            kb = int(np.nanargmax(oos_srs))
            var_k = max(float(np.var(oos_srs, ddof=1)) if K > 1 else 0.0, 1.0 / len(wf[0][0]))
            sr0_k = ds.expected_max_sharpe(var_k, K) if K > 1 else 0.0
            rep_pass, _ = psr_pass(wf[kb][0], sr0_k)
            _, psr_kb = psr_pass(wf[kb][0], 0.0)
            res["WF_PSR_bonfK"] = bool((1.0 - psr_kb) * K < 0.05)
            res["WF_asbuilt_DSR"] = any(asb)
            res["WF_asbuilt_DSR+S14"] = any(asb14)
            res["WF_PSR0_keepbest"] = any(naive)
            res["WF_DSR_repairedK"] = bool(rep_pass)
            res["WF_DSR_NxK_dev"] = any(dsr_nk)
            timing["WF"] = time.perf_counter() - t0
            # ---- CPCV / PBO
            t0 = time.perf_counter()
            if N > 1:
                cp = [cpcv(pre, c, a0) for c in rv]
                res["CPCV_PBO<0.5&z"] = any((pb < 0.5) and (s * math.sqrt(nh) > 1.645) for pb, s, nh in cp)
                res["CPCV_PBO<0.2"] = any(pb < 0.2 for pb, _, _ in cp)
            timing["CPCV"] = time.perf_counter() - t0
            # ---- SPA / StepM (step 1 = studentised RC) / HLZ
            t0 = time.perf_counter()
            spa_any, rc_any, bonf_any, bhy_any = [], [], [], []
            for c in rv:
                p_spa, p_rc, tmax = spa_family(dev_mean[c], bmeans[:, c], T_DEV)
                spa_any.append(p_spa < 0.05)
                rc_any.append(p_rc < 0.05)
                p1 = 1 - Z.cdf(tmax)
                bonf_any.append(p1 * len(c) < 0.05)
                bhy_any.append(p1 * len(c) * c_bhy(len(c)) < 0.05)
            union = np.unique(np.concatenate(rv))
            p_spa_u, p_rc_u, tmax_u = spa_family(dev_mean[union], bmeans[:, union], T_DEV)
            p1u = 1 - Z.cdf(tmax_u)
            mk = N * K
            res["SPA_keepbest"] = any(spa_any)
            res["SPA_union"] = p_spa_u < 0.05
            res["StepM_keepbest"] = any(rc_any)
            res["StepM_union"] = p_rc_u < 0.05
            res["HLZ_bonf_keepbest"] = any(bonf_any)
            res["HLZ_bonf_NK"] = p1u * mk < 0.05
            res["HLZ_BHY_NK"] = p1u * mk * c_bhy(mk) < 0.05
            timing["SPA+StepM+HLZ"] = time.perf_counter() - t0
            # ---- MinBTL used as a gate: best IS annual Sharpe above E[max] of N*K nulls
            best_is = max(float(dev_sr[c].max()) for c in rv)
            res["MinBTL_gate_NK"] = annual(best_is) > emax(len(union)) / math.sqrt(DEV_Y)
            # ---- 2-year time holdout: select on dev, test on holdout
            champs = [c[np.argmax(dev_sr[c])] for c in rv]
            ho = [psr_pass(ho_R[:, j].astype(np.float64), 0.0)[0] for j in champs]
            best_rev = int(np.argmax([dev_sr[j] for j in champs]))
            res["Holdout_once"] = bool(ho[best_rev])
            if K == 1:
                out["stats"][f"N{N}_holdout_annual_sr"] = annual(float(np.mean(ho_R[:, champs[0]]) / np.std(ho_R[:, champs[0]])))
                out["stats"][f"N{N}_dev_best_is_annual_sr"] = annual(best_is)
            res["Holdout_keepbest"] = any(ho)
            # ---- stack: WF repaired-K AND holdout once
            res["STACK_WFrepK+Holdout"] = res["WF_DSR_repairedK"] and res["Holdout_once"]
            res["STACK_WFbonfK+Holdout"] = res["WF_PSR_bonfK"] and res["Holdout_once"]
            out[f"N{N}_K{K}"] = {k: bool(v) for k, v in res.items()}
    return out, timing


# --------------------------------------------------------------------------- calibration
def calibrate(target, dur, years=40, seed=7, hi=1.0):
    """Find mu so the best pool config nets `target` annual Sharpe. The best config is chosen
    on one long sample and its Sharpe measured on an independent one (no max-of-noise bias)."""
    rA, rB = np.random.default_rng(seed), np.random.default_rng(seed + 1)
    n = years * YEAR
    bA, sA = garch_t(rA, n, M), markov_state(rA, n, M, dur)
    bB, sB = garch_t(rB, n, M), markov_state(rB, n, M, dur)
    lo = 0.0
    best = None
    for _ in range(12):
        mu = 0.5 * (lo + hi)
        RA, _ = build_pool(bA + mu * SIG * sA)
        best = int(np.argmax(RA.mean(0) / RA.std(0)))
        del RA
        RB, _ = build_pool(bB + mu * SIG * sB)
        x = RB[:, best].astype(np.float64)
        del RB
        if x.mean() / x.std() * math.sqrt(YEAR) < target:
            lo = mu
        else:
            hi = mu
    return 0.5 * (lo + hi), best


if __name__ == "__main__":
    print(pool_size())
