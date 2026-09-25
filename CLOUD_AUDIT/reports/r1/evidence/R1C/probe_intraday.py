"""R1-C: the intraday refinement must not re-introduce a bridge edge. Synthetic only.
(1) exactness: each instrument's ticks sum to its daily excess return;
(2) no within-day tilt: 'at the 12th hour, go with the day-so-far, hold to the close' has zero mean on the
    null, versus the same rule on a day pinned to ZERO (the BASE whole-path demeaning, at day scale);
(3) no spurious lead-lag/pairs edge: with JOINT bridges (one factor bridge + idiosyncratic bridges) the
    rest-of-day return of i is unpredictable from j's day-so-far; with INDEPENDENT per-instrument bridges
    pinned at correlated endpoints it is predictable (a planted pairs edge nobody asked for).
Usage: OMP_NUM_THREADS=1 python probe_intraday.py [days] [seed]
"""
import math
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from gen_lab import LabSpec, generate, intraday_panel, _bridge   # noqa: E402

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
MID = 12 * 60                              # grid index of the 12th hour (1-min grid)


def tstat(v):
    v = np.asarray(v); return v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))


def main():
    p = generate(LabSpec(seed=int(sys.argv[2]) if len(sys.argv) > 2 else 3, rho=0.5))
    err, mom_ok, mom_zero, ll_joint, ll_ind = 0.0, [], [], [], []
    b = p.loadings
    same = np.flatnonzero(np.sign(b) == np.sign(b[0]))
    i, j = same[0], same[1]                 # a positively correlated pair
    rng0 = np.random.default_rng(99)
    for t in range(DAYS):
        for joint, bucket in ((True, ll_joint), (False, ll_ind)):
            d = intraday_panel(p, t, joint=joint)
            lr = d["logret"] / p.sigma[t][:, None]                 # vol units
            if joint:
                err = max(err, float(np.abs(d["logret"].sum(axis=1) - p.x[t]).max()))
                past, rest = lr[:, :MID].sum(axis=1), lr[:, MID:].sum(axis=1)
                mom_ok.extend(np.sign(past) * rest)
                # the BASE bug at day scale: the same noise pinned to a ZERO day (bridge from 0 to 0)
                wv = np.full(lr.shape[1], 1.0 / lr.shape[1])
                z = _bridge(rng0, wv[None, :], np.ones((lr.shape[0], 1)), np.zeros((lr.shape[0], 1)), lr.shape)
                mom_zero.extend(np.sign(z[:, :MID].sum(axis=1)) * z[:, MID:].sum(axis=1))
            # lead-lag: j's day-so-far predicts i's rest-of-day?
            past_j = lr[j, :MID].sum() - lr[i, :MID].sum()          # j ahead of i so far
            rest_i = lr[i, MID:].sum()
            bucket.append(np.sign(past_j) * rest_i)
    print(f"days {DAYS}, 20 instruments, rho 0.5; pair ({i},{j}) corr sign +")
    print(f"(1) exactness: max |sum(ticks) - x| = {err:.2e}")
    print(f"(2) day-so-far momentum to close, lab null: mean {np.mean(mom_ok):+.4f} (t {tstat(mom_ok):+.1f}); "
          f"zero-pinned day (BASE-style): mean {np.mean(mom_zero):+.4f} (t {tstat(mom_zero):+.1f})")
    print(f"(3) pairs catch-up 'long i when j led': JOINT bridges mean {np.mean(ll_joint):+.4f} (t {tstat(ll_joint):+.1f}); "
          f"INDEPENDENT bridges mean {np.mean(ll_ind):+.4f} (t {tstat(ll_ind):+.1f})")


if __name__ == "__main__":
    main()
