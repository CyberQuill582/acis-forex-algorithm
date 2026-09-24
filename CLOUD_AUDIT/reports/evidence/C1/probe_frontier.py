"""C1 — analytic frontier: years of OOS record for 80% power at FWER 5%, and MinBTL, and the
closed-form hurdle the as-built DSR gate imposes. Pure arithmetic; no data."""
import math
from statistics import NormalDist
Z = NormalDist()
G = 0.5772156649015329

def emax(n):
    return 0.0 if n < 2 else (1 - G) * Z.inv_cdf(1 - 1 / n) + G * Z.inv_cdf(1 - 1 / (n * math.e))

print("Frontier: OOS years for 80% power, one-sided FWER 5% Bonferroni over K looks; S = realised OOS Sharpe")
print("S".ljust(6), " ".join(f"K={k}".ljust(8) for k in (1, 5, 20, 100)))
for S in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
    row = []
    for K in (1, 5, 20, 100):
        z = Z.inv_cdf(1 - 0.05 / K)
        row.append(f"{((z + 0.8416) / S) ** 2 * (1 + S * S / 2):.1f}".ljust(8))
    print(f"{S}".ljust(6), " ".join(row))
print()
print("MinBTL (years) = (E[max_N]/S)^2  (Bailey-Lopez de Prado 2014): IS length below which the best of N")
print("zero-edge configs is EXPECTED to show annual Sharpe S")
print("N".ljust(8), " ".join(f"S={s}".ljust(8) for s in (0.5, 1.0, 1.5)))
for N in (10, 60, 1000, 20000, 90000):
    print(f"{N}".ljust(8), " ".join(f"{(emax(N) / s) ** 2:.1f}".ljust(8) for s in (0.5, 1.0, 1.5)))
print()
print("As-built DSR hurdle (approx., trial Sharpes at null dispersion): annual OOS Sharpe needed")
print("  ~= E[max_Ntrials] / sqrt(holdout_years) + 1.645 / sqrt(OOS_years); holdout = 20% of 2y = 0.4y")
for nt in (10, 90, 720):
    for Y in (2, 10):
        print(f"  N_trials={nt:4d} OOS_years={Y:2d}: {emax(nt) / math.sqrt(0.4) + 1.645 / math.sqrt(Y):.2f}")
