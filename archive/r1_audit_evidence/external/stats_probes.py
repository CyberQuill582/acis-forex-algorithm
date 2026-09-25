"""EXTERNAL R1 audit probes (numpy, seeded). Each block reproduces one claimed finding."""
import numpy as np, math
rng = np.random.default_rng(20260925)
LAM = np.array([0.05, 0.1, 0.2, 0.4, 0.8])

def W(x):                      # mean over lambda of prod(1 + lam * max(x, -1)), x already scaled
    x = np.maximum(x, -1.0)
    return np.exp(np.cumsum(np.log1p(np.outer(x, LAM)), axis=0)).mean(axis=1)

print("== P1: E2 as literally written, mu_claim = SR_dev/2 (a Sharpe number) minus a daily return")
sr_dev, sig_a = 0.6, 0.20
sig_d = sig_a / math.sqrt(256)
for label, sstar in (("sigma* = annual target 0.20", sig_a), ("sigma* = daily 0.20/16", sig_d)):
    kills = []
    for rep in range(200):
        r = rng.normal(0.6 * sig_d / 16, sig_d, 2000)        # a REAL edge at SR 0.6
        w = W((sr_dev / 2 - r) / (6 * sstar))
        hit = np.argmax(w >= 20) if (w >= 20).any() else None
        kills.append(hit)
    ok = [k for k in kills if k is not None]
    print(f"  {label}: E2 >= 20 (KILL) in {len(ok)}/200 runs of a true SR-0.6 family; median day {np.median(ok) if ok else None}")
mu_claim_daily = (sr_dev / 2) * sig_d / 16
print(f"  dimensionally consistent mu_claim = (SR_dev/2)*sigma_d/sqrt(256) = {mu_claim_daily:.6f}/day (vs {sr_dev/2} as written)")

print("== P2: days for E1 to reach 20 (edge shown) at a true annual SR, both readings of sigma*")
for sr in (0.3, 0.5, 0.8, 1.0):
    for label, sstar in (("annual", sig_a), ("daily", sig_d)):
        T = 256 * 60; reps = 200; hits = []
        for rep in range(reps):
            r = rng.normal(sr * sig_d / 16, sig_d, T)
            w = W(r / (6 * sstar))
            hits.append(np.argmax(w >= 20) / 256 if (w >= 20).any() else np.inf)
        hits = np.array(hits)
        print(f"  SR {sr:.1f}, sigma* {label:6}: P(E1>=20 within 3y) {np.mean(hits<=3):.2f}, within 10y {np.mean(hits<=10):.2f}, median years {np.median(hits):.1f}")

print("== P3: stage C, residualised held-out portfolio, kill at t < -0.5")
# the family's edge is a COMMON factor: held-out strategy returns = beta * explored factor + idio; alpha = 0
Y, d = 12, 256
for share in (1.0, 0.7, 0.4):          # share of the edge carried by the common factor
    kills = 0; reps = 2000
    for rep in range(reps):
        f = rng.normal(0.5 * sig_d / 16, sig_d, Y * d)                     # explored factor, true SR 0.5
        idio = rng.normal((1 - share) * 0.5 * sig_d / 16, sig_d * 0.8, Y * d)
        h = 0.8 * f * share / max(share, 1e-9) * share + idio if share > 0 else idio
        X = np.column_stack([np.ones_like(f), f]); b, *_ = np.linalg.lstsq(X, h, rcond=None)
        res = h - X @ b; s2 = res @ res / (len(h) - 2)
        t_alpha = b[0] / math.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
        kills += t_alpha < -0.5
    print(f"  common-factor share of the edge {share:.1f}: residual-alpha kill rate {kills/reps:.3f}")
for sr in (0.0, 0.3, 0.5, 0.8):
    t = sr * math.sqrt(2)
    p = 0.5 * math.erfc((t + 0.5) / math.sqrt(2))
    print(f"  2024-25 holdout alone, true SR {sr}: P(t < -0.5) = {p:.3f}")

print("== P4: +/-1 sign-flipped LOG returns, price-unit P&L of an always-long unit position")
for name, vol_d in (("EURUSD-like 0.5%/day", 0.005), ("XAU-like 1%/day", 0.01), ("NATGAS-like 3.5%/day", 0.035)):
    base = rng.standard_t(4, 256 * 12) * vol_d / math.sqrt(2)            # fat-tailed 'real' returns
    pnl = []
    for rep in range(2000):
        e = rng.permutation(base) * rng.choice([-1.0, 1.0], base.size)
        pnl.append(np.expm1(e).mean())                                       # notional-sized long, per day
    pnl = np.array(pnl); ann = pnl.mean() * 256; vol = vol_d * 16
    print(f"  {name}: mean daily price-P&L per unit notional {pnl.mean():+.2e} (theory sigma^2/2 = {vol_d**2/2:.2e}); annual {ann:+.3%} on {vol:.0%} vol -> SR {ann/vol:+.3f}")

print("== P5: a demeaned random walk is a bridge: sign(12m lookback) trend rule, gross P&L t-stat")
for n in (256 * 3, 256 * 12):
    ts = []
    for rep in range(400):
        e = rng.normal(0, 1, n); e -= e.mean()
        c = np.concatenate([[0], np.cumsum(e)]); L = 252
        pos = np.sign(c[L:-1] - c[:-L - 1]); pnl = pos * e[L:]
        ts.append(pnl.mean() / (pnl.std() / math.sqrt(pnl.size)))
    print(f"  path {n} days: mean t of the trend rule {np.mean(ts):+.3f} (theory -sqrt(2L/(pi n)) ~ {-math.sqrt(2*252/(math.pi*n)):+.3f}); undemeaned = 0")

print("== P6: fixed-sequence chain at alpha plus a separate Holm set at alpha, all nulls true")
reps = 200000; a = 0.05
for k_chain, k_holm, rho in ((2, 3, 0.0), (2, 3, 0.5), (1, 4, 0.0)):
    z0 = rng.normal(size=(reps, 1)); z = math.sqrt(rho) * z0 + math.sqrt(1 - rho) * rng.normal(size=(reps, k_chain + k_holm))
    p = 0.5 * np.vectorize(math.erfc)(z / math.sqrt(2))                      # one-sided
    chain = p[:, 0] < a                                                       # first in order; later need it
    ps = np.sort(p[:, k_chain:], axis=1); m = k_holm
    holm = ps[:, 0] < a / m                                                   # Holm's first step decides any rejection
    print(f"  chain {k_chain}, Holm set {k_holm}, rho {rho}: FWER {np.mean(chain | holm):.4f} (claimed 0.05)")
