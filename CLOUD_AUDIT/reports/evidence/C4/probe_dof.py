"""C4 receipt: degrees-of-freedom of ACIS's parameter search vs what the data can support.

Pure arithmetic, stdlib only, no market data. Inputs are read from /tmp/review-acis (BASE) config
where possible; everything else is stated. Bailey & Lopez de Prado (2014) expected-max-Sharpe
under the null of N independent zero-skill trials, and MinBTL = (E[max z] / SR_target)^2 years.
"""
import math, sys
from statistics import NormalDist
import yaml

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis"
Z = NormalDist()
G = 0.5772156649015329

def emax_z(n):  # expected max of n iid N(0,1), BLdP approximation
    if n < 2:
        return 0.0
    return (1 - G) * Z.inv_cdf(1 - 1 / n) + G * Z.inv_cdf(1 - 1 / (n * math.e))

cfg = yaml.safe_load(open(f"{ROOT}/config/system_config.yaml"))
opt = cfg["optimizer"]
pop, gens, res = opt["population_size"], opt["generations"], opt["qbit_resolution"]
n_genes, tradeable_regimes, instruments, modules = 11, 9, 8, 6
evals_per_evolve = pop * gens
per_fold = evals_per_evolve * tradeable_regimes * instruments
print(f"QIEA: pop {pop} x gens {gens} = {evals_per_evolve} fitness evaluations per (regime, instrument)")
print(f"genome: {n_genes} genes x {res} bits = {n_genes*res} bits (2^{n_genes*res} points)")
print(f"per fold: {evals_per_evolve} x {tradeable_regimes} regimes x {instruments} instruments = {per_fold} evaluations")
print(f"staged per fold: {tradeable_regimes} ParamSets (1 per regime, best holdout E[R] across {instruments} instruments)")
print(f"module on/off combinations: 2^{modules} = {2**modules}; numeric knobs in system_config.yaml: 100 (+55 instruments.yaml)")
print()
span_y = opt["fitness_span_days"] / 365.25
print(f"fitness window per fold: {span_y:.2f} years of calendar; a regime sees only its own bars")
print("| N (effective independent trials) | E[max z] | noise-max annual SR on 2y full | on 2y x 20% regime share | MinBTL yrs @SR0.5 | MinBTL yrs @SR1.0 |")
print("|---|---|---|---|---|---|")
for n in (1, 10, 100, 1000, 10_000, per_fold):
    e = emax_z(n)
    full = e / math.sqrt(span_y)
    reg = e / math.sqrt(span_y * 0.2)
    print(f"| {n} | {e:.2f} | {full:.2f} | {reg:.2f} | {(e/0.5)**2:.1f} | {(e/1.0)**2:.1f} |")
print()
print("Data available: 12 dev years x 8 instruments. At rho~0.4 common factor the 8 series are worth ~",
      f"{8/(1+7*0.4):.1f} independent series (n/(1+(n-1)rho)), i.e. ~{12*8/(1+7*0.4):.0f} instrument-years")
print("Graded DSR (tests/backtest/harness.py:217-218) counts n_trials = #surviving champions (+min),",
      f"at most {tradeable_regimes*instruments} per fold, vs {per_fold} evaluations actually searched per fold",
      f"(ratio {per_fold/(tradeable_regimes*instruments):.0f}x).")
