"""Stage A as written: fixed-sequence at alpha=0.05 for the ordered families; 'families outside the order are
Holm-adjusted among themselves' (no alpha split stated); '<= 3 registered looks per family' (no look correction
stated for stage A, while stage B states Bonferroni over its <= 3 looks). Global null, SR_true = 0."""
import numpy as np
from statistics import NormalDist
class norm:
    ppf = staticmethod(NormalDist().inv_cdf)
    @staticmethod
    def sf(x):
        import numpy as _np
        from math import erfc, sqrt
        return _np.vectorize(lambda v: 0.5*erfc(v/sqrt(2)))(x)
rng = np.random.default_rng(3); z95 = norm.ppf(0.95); Y = 11; n = 40_000
bar = z95 / np.sqrt(Y)
print(f"bar SR > z0.95/sqrt(Y): Y=11 -> {z95/np.sqrt(11):.3f}, Y=10 -> {z95/np.sqrt(10):.3f}")
def sr_hat(k, rho=0.0):
    # k correlated SR estimates, each ~ N(0, 1/Y) under the null
    common = rng.standard_normal((n, 1)); idio = rng.standard_normal((n, k))
    return (np.sqrt(rho) * common + np.sqrt(1 - rho) * idio) / np.sqrt(Y)
# (1) ordered chain of 3 + Holm set of 3, each at alpha 0.05, families independent
seq = sr_hat(3); holm = sr_hat(3)
p_seq = norm.sf(seq * np.sqrt(Y)); p_h = np.sort(norm.sf(holm * np.sqrt(Y)), axis=1)
rej_seq = p_seq[:, 0] < 0.05                     # any false rejection in the chain starts with the first
holm_thr = 0.05 / np.array([3, 2, 1]); rej_h = p_h[:, 0] < holm_thr[0]
print(f"FWER chain alone={rej_seq.mean():.4f}  Holm set alone={rej_h.mean():.4f}  union={(rej_seq|rej_h).mean():.4f}")
# (2) one family, up to 3 registered looks, each graded at alpha 0.05, pass if any look passes
for rho in (0.0, 0.5, 0.8, 0.95):
    looks = sr_hat(3, rho)
    print(f"one family, 3 looks, look-corr {rho}: P(any look passes | null) = {(looks > bar).any(axis=1).mean():.4f}")
