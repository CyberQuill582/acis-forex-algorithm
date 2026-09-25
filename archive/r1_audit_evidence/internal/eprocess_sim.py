"""Reproduce C-BT-11 v2 stage D as written:
E1: W = mean_{lam in L} prod(1 + lam*max(r/(6 s*), -1)); 'edge shown' W>=20.
E2: same bettor on (mu_claim - r); W>=5 freeze, W>=20 kill.
sigma* read two ways: daily vol target (favourable to power) and annual (literal 'vol target').
"""
import numpy as np
rng = np.random.default_rng(20260925)
L = np.array([0.05, 0.1, 0.2, 0.4, 0.8])
DAYS = 252

def run(r, s_star, mu_claim=None, clip=True):
    x = (r if mu_claim is None else (mu_claim - r)) / (6 * s_star)
    if clip:
        x = np.maximum(x, -1.0)
    # log wealth per lambda, per path, cumulative
    logf = np.log1p(L[None, None, :] * x[:, :, None])   # paths x days x lam
    cum = np.cumsum(logf, axis=1)
    W = np.exp(cum).mean(axis=2)                          # paths x days
    return W

def first_hit(W, thr):
    hit = W >= thr
    any_ = hit.any(axis=1)
    idx = np.where(any_, hit.argmax(axis=1), -1)
    return any_, idx

def returns(n, T, sr_ann, sig_d, df=None):
    mu = sr_ann * sig_d / np.sqrt(DAYS)
    if df is None:
        z = rng.standard_normal((n, T))
    else:
        z = rng.standard_t(df, (n, T)) / np.sqrt(df / (df - 2))
    return mu + sig_d * z

sig_ann = 0.10; sig_d = sig_ann / np.sqrt(DAYS)
N = 2000
print("== E1 validity under H0 (mean 0), 10y horizon, P(sup W >= 20); Ville bound 0.05")
for df in (None, 3, 2.2):
    r = returns(N, 10 * DAYS, 0.0, sig_d, df)
    for label, s in (("daily s*", sig_d), ("annual s*", sig_ann)):
        W = run(r, s)
        print(f"  tails={'normal' if df is None else 't'+str(df):7s} {label:9s} P={first_hit(W,20)[0].mean():.4f}  "
              f"days clipped/path={np.mean((r/(6*s))<-1)*10*DAYS:.3f}")
print("== E1 power: P(W>=20 within Y years), true SR, daily s* (the favourable reading)")
for sr in (0.3, 0.5, 0.8, 1.0, 1.5):
    r = returns(1000, 40 * DAYS, sr, sig_d)
    W = run(r, sig_d)
    any_, idx = first_hit(W, 20)
    for Y in (2, 5, 10, 20, 40):
        pass
    print(f"  SR {sr}: " + "  ".join(f"{Y}y={np.mean(any_ & (idx < Y*DAYS)):.2f}" for Y in (2, 5, 10, 20, 40)))
print("== E1 power with ANNUAL s* (literal 'vol target'), SR 1.0")
r = returns(500, 40 * DAYS, 1.0, sig_d); W = run(r, sig_ann); a, i = first_hit(W, 20)
print("  " + "  ".join(f"{Y}y={np.mean(a & (i < Y*DAYS)):.2f}" for Y in (5, 10, 20, 40)))
print("== E2 (kill) on a DEAD strategy (true SR 0), mu_claim = (SR_dev/2) as a daily mean return, daily s*")
for sr_dev in (0.5, 0.8, 1.2):
    mu_claim = (sr_dev / 2) * sig_d / np.sqrt(DAYS)
    r = returns(1000, 20 * DAYS, 0.0, sig_d)
    W = run(r, sig_d, mu_claim=mu_claim)
    a5, i5 = first_hit(W, 5); a20, i20 = first_hit(W, 20)
    print(f"  SR_dev {sr_dev}: freeze(W>=5) " + " ".join(f"{Y}y={np.mean(a5 & (i5 < Y*DAYS)):.2f}" for Y in (0.25, 1, 3, 10, 20))
          + " | kill(W>=20) " + " ".join(f"{Y}y={np.mean(a20 & (i20 < Y*DAYS)):.2f}" for Y in (1, 3, 10, 20)))
print("== E2 on a LOSING strategy (true SR -0.5), SR_dev 0.8")
mu_claim = 0.4 * sig_d / np.sqrt(DAYS); r = returns(1000, 20 * DAYS, -0.5, sig_d)
W = run(r, sig_d, mu_claim=mu_claim); a5, i5 = first_hit(W, 5); a20, i20 = first_hit(W, 20)
print("  freeze " + " ".join(f"{Y}y={np.mean(a5 & (i5 < Y*DAYS)):.2f}" for Y in (0.25, 1, 3, 10)) +
      " | kill " + " ".join(f"{Y}y={np.mean(a20 & (i20 < Y*DAYS)):.2f}" for Y in (1, 3, 10)))
print("== P(E2 silent for the first 3 months) on a dead strategy, SR_dev 0.8:", end=" ")
mu_claim = 0.4 * sig_d / np.sqrt(DAYS); r = returns(2000, 63, 0.0, sig_d)
W = run(r, sig_d, mu_claim=mu_claim); print(f"{1 - first_hit(W,5)[0].mean():.3f}")
print("== E2 LITERAL (mu_claim = SR_dev/2 = 0.4 as a raw fraction of equity): days to kill")
r = returns(200, 60, 0.0, sig_d)
for label, s in (("daily s*", sig_d), ("annual s*", sig_ann)):
    W = run(r, s, mu_claim=0.4); a, i = first_hit(W, 20)
    print(f"  {label}: killed={a.mean():.2f} median day={np.median(i[a]) if a.any() else None}")
