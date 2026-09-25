"""R1-D receipt: online regret-bounded allocation (Hedge / exponential weights) vs fixed equal risk
among a few rule sleeves, on SYNTHETIC daily returns only. LLM-originated sketch.

Question: at ACIS scale (K = 4-6 sleeves, 14 years daily, sleeve Sharpes 0.2-0.8, pairwise
correlation ~0.2-0.3), does Hedge's regret guarantee turn into a net gain over 1/K?
Hedge weights: w_i,t ∝ exp(eta * sum_{s<t} r_i,s / sigma_i), eta = sqrt(8 ln K / T) (the textbook
horizon-tuned rate) and a 10x more aggressive eta. Cost: c per unit of weight turnover, in units of
daily sleeve vol (c = 0.02 is about 2% of one day's sleeve risk per full switch).
Run: OMP_NUM_THREADS=1 python sim_hedge_vs_equal.py
"""
import json
import numpy as np

T, DPY, R = 14 * 260, 260, 400


def sleeves(rng, srs, rho):
    k = len(srs)
    c = np.sqrt(rho) * rng.standard_normal((T, 1)) + np.sqrt(1 - rho) * rng.standard_normal((T, k))
    return c + np.asarray(srs) / np.sqrt(DPY)          # unit daily vol, drift = SR/sqrt(260)


def run(x, eta, cost):
    k = x.shape[1]
    cum = np.vstack([np.zeros(k), np.cumsum(x, axis=0)[:-1]])   # information up to t-1 only
    z = eta * cum
    w = np.exp(z - z.max(axis=1, keepdims=True)); w /= w.sum(axis=1, keepdims=True)
    turn = np.abs(np.diff(w, axis=0, prepend=w[:1])).sum(axis=1)
    return (w * x).sum(axis=1) - cost * turn


def sr(p):
    return p.mean() / p.std() * np.sqrt(DPY)


def scenario(srs, rho, cost, seed):
    rng = np.random.default_rng(seed); k = len(srs)
    eta0 = np.sqrt(8 * np.log(k) / T)
    d_hedge, d_fast, best_hind = [], [], []
    for _ in range(R):
        x = sleeves(rng, srs, rho)
        ew = sr(x.mean(axis=1))
        d_hedge.append(sr(run(x, eta0, cost)) - ew)
        d_fast.append(sr(run(x, 10 * eta0, cost)) - ew)
        best_hind.append(max(sr(x[:, i]) for i in range(k)) - ew)
    f = lambda a: dict(mean=round(float(np.mean(a)), 3), p_beats_equal=round(float(np.mean(np.array(a) > 0)), 3))
    return dict(srs=srs, rho=rho, cost=cost, hedge_minus_equal=f(d_hedge),
                hedge10x_minus_equal=f(d_fast), best_in_hindsight_minus_equal=f(best_hind))


if __name__ == "__main__":
    out = [scenario([0.5] * 5, 0.25, 0.0, 1), scenario([0.5] * 5, 0.25, 0.02, 2),
           scenario([0.3, 0.3, 0.3, 0.3, 0.8], 0.25, 0.0, 3), scenario([0.3, 0.3, 0.3, 0.3, 0.8], 0.25, 0.02, 4),
           scenario([0.0, 0.0, 0.0, 0.8], 0.2, 0.02, 5)]
    print(json.dumps(out, indent=1))
