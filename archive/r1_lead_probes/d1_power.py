"""Lead check on PLAN_R1 B2: the power of the flagship family D1 against the plan's own stage-A bar.
One-sided lower bound of an annual Sharpe estimated over Y years: SR_hat > z_(1-a) / sqrt(Y) (the plan's
own approximation, se = 1/sqrt(Y)). D1's expected net SR is the plan's own R1-B range (FTMO swaps -0.15..+0.32,
swap-free +0.32..+0.79). Holm's first step tests the best family at a/K; fixed-sequence tests the pre-registered
primary family at the full a."""
from statistics import NormalDist
N = NormalDist(); a = 0.05
def bar(k, y): return N.inv_cdf(1 - a / k) / y ** 0.5
def power(mu, b, y): return 1 - N.cdf((b - mu) * y ** 0.5)
cases = [("Holm K=10, Y=10 (plan B2)", 10, 10), ("Holm K=5,  Y=10", 5, 10), ("Holm K=3,  Y=10", 3, 10),
         ("fixed-sequence (primary), Y=10", 1, 10), ("fixed-sequence (primary), Y=11", 1, 11)]
mus = [("FTMO mid 0.08", .085), ("swap-free low 0.32", .32), ("swap-free mid 0.55", .555), ("swap-free high 0.79", .79)]
print(f"{'test':34s} {'bar':>5s} " + " ".join(f"{m:>20s}" for m, _ in mus))
for name, k, y in cases:
    b = bar(k, y)
    print(f"{name:34s} {b:5.2f} " + " ".join(f"{power(mu, b, y):20.0%}" for _, mu in mus))
