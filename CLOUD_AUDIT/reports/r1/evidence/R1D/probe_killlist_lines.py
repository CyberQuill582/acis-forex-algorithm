"""R1-D receipt: measured line counts for the R-1 kill list at BASE (read-only; stdlib only).
Run: python probe_killlist_lines.py /tmp/review-acis
Whole files are counted as `wc -l` does; partial retirements count the named line ranges."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis")
WHOLE_PROD = ["core/optimizer/qiea.py", "core/optimizer/fitness.py", "core/regime/stability.py",
              "core/governor/marginal_alpha.py", "core/execution/fragmenter.py"]
WHOLE_HARNESS = ["tests/backtest/evolve_step.py", "tests/backtest/regime_labels.py"]
RANGES = {  # (file, first, last, what)
    "param_library staging/promotion": ("core/optimizer/param_library.py", 112, 203),
    "VenueQuality": ("core/execution/venue.py", 315, 342),
    "AGON pair sampling": ("core/signals/agon.py", 140, 169),
    "AGON MR/SCALP/PAIR modules": ("core/signals/agon.py", 407, 481),
    "AGON conviction/discard pipeline": ("core/signals/agon.py", 267, 358),
}
REHOME = ["core/optimizer/plateau.py", "core/optimizer/param_types.py", "core/regime/nvma.py",
          "core/signals/provenance.py", "tests/backtest/deflated_sharpe.py", "tests/backtest/report.py",
          "tests/backtest/oos_plan.py", "core/optimizer/costs.py"]
TESTS = ["tests/unit/test_qiea.py", "tests/backtest/test_evolve_step.py",
         "tests/integration/test_qiea_promotion_cycle.py", "tests/unit/test_evaluation_registry.py",
         "tests/unit/test_fitness.py", "tests/unit/test_fitness_components.py", "tests/unit/test_fitness_entries.py",
         "tests/unit/test_fitness_exits.py", "tests/unit/test_fitness_indicators.py", "tests/unit/test_plateau_law.py",
         "tests/backtest/test_regime_labels.py", "tests/unit/test_marginal_alpha.py"]
PARTIAL_TESTS = ["tests/unit/test_param_library.py", "tests/unit/test_nvma.py"]


def n(p):
    return sum(1 for _ in open(ROOT / p, encoding="utf-8"))


def prod_total():
    return sum(n(p.relative_to(ROOT)) for d in ("core", "monitoring") for p in (ROOT / d).rglob("*.py"))


if __name__ == "__main__":
    print(f"production core/+monitoring/ .py lines: {prod_total()}")
    tot = 0
    for p in WHOLE_PROD + WHOLE_HARNESS:
        tot += n(p); print(f"KILL whole  {n(p):5d}  {p}")
    for what, (p, a, b) in RANGES.items():
        tot += b - a + 1; print(f"KILL range  {b - a + 1:5d}  {p}:{a}-{b}  ({what})")
    print(f"KILL subtotal (measured): {tot}")
    for p in REHOME:
        print(f"REHOME/KEEP {n(p):5d}  {p}")
    t = sum(n(p) for p in TESTS)
    for p in TESTS:
        print(f"TEST whole  {n(p):5d}  {p}")
    for p in PARTIAL_TESTS:
        print(f"TEST part   {n(p):5d}  {p}")
    print(f"TEST whole subtotal: {t}; partial files: {sum(n(p) for p in PARTIAL_TESTS)}")
