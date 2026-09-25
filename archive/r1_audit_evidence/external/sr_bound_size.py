"""EXTERNAL R1 audit probe: size of the stage-A bar SR_hat_annual > z_0.95/sqrt(Y) under a TRUE zero mean,
Y = 11 years of daily OOS returns, for iid normal, iid t(3), GARCH(1,1)-t, and AR(1) with small rho."""
import numpy as np, math
rng = np.random.default_rng(11)
Y, d = 11, 256; n = Y * d; reps = 20000; bar = 1.6449 / math.sqrt(Y)
def size(gen):
    hits = 0
    for _ in range(reps):
        r = gen()
        sr = r.mean() / r.std(ddof=1) * math.sqrt(d)
        hits += sr > bar
    return hits / reps
def garch():
    w, a, b = 0.02, 0.08, 0.90; h = w / (1 - a - b); out = np.empty(n); z = rng.standard_t(5, n) / math.sqrt(5 / 3)
    for t in range(n):
        out[t] = math.sqrt(h) * z[t]; h = w + a * out[t] ** 2 + b * h
    return out
def ar(rho):
    e = rng.normal(size=n); x = np.empty(n); x[0] = e[0]
    for t in range(1, n): x[t] = rho * x[t - 1] + e[t]
    return x
print(f"bar = {bar:.3f} annual SR (Y = {Y}); nominal size 0.05; {reps} reps each")
print("iid normal   ", size(lambda: rng.normal(size=n)))
print("iid t(3)     ", size(lambda: rng.standard_t(3, n)))
reps = 4000
print("GARCH-t(5)   ", size(garch))
for rho in (0.05, 0.10):
    print(f"AR(1) rho {rho}", size(lambda: ar(rho)), f"(Lo 2002 variance factor ~ (1+rho)/(1-rho) = {(1+rho)/(1-rho):.2f})")
