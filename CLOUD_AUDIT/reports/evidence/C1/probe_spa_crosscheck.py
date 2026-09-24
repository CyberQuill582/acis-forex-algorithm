"""Cross-check this lane's vectorised SPA/RC p-values against the `arch` package (synthetic only)."""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim_protocols as sp
from arch.bootstrap import SPA

rng = np.random.default_rng(11)
T, P = 3024, 60
for trial, drift in enumerate([0.0, 0.0, 0.03, 0.06]):
    R = rng.standard_normal((T, P)) * 0.006
    R[:, 0] += drift * 0.006          # one config with a per-day Sharpe of `drift`
    W = sp.boot_weights(rng, T, B=999)
    bm = (W @ R.astype(np.float32)) / T
    p_spa, p_rc, _ = sp.spa_family(R.mean(0), bm, T)
    # arch: losses of the models vs a zero benchmark; SPA tests whether any model beats the benchmark
    spa = SPA(np.zeros(T), -R, block_size=10, reps=999, bootstrap="circular", studentize=True, seed=trial)
    spa.compute()
    pv = spa.pvalues
    print(f"drift/day={drift}: this-lane SPA_c={p_spa:.3f} RC={p_rc:.3f} | arch consistent={pv['consistent']:.3f} upper(RC)={pv['upper']:.3f}")
