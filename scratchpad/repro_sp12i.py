"""Lens-1 internal-consistency reproduction script (GAP-SP12I-*).
Run from repo root:  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py
"""
import re, yaml, pathlib
root = pathlib.Path(".")
master = (root / "ACIS_SPEC.md").read_text(encoding="utf-8")
sysc = yaml.safe_load((root / "config/system_config.yaml").read_text())
tst = (root / "tests/unit/test_spec_constants.py").read_text(encoding="utf-8")
a02 = (root / "specs/ACIS-02-NVMA_REGIME.md").read_text(encoding="utf-8")
a06 = (root / "specs/ACIS-06-EXECUTION_ORCHESTRATOR.md").read_text(encoding="utf-8")
a07 = (root / "specs/ACIS-07-RISK_MONITOR.md").read_text(encoding="utf-8")
a09 = (root / "specs/ACIS-09-BACKTEST_VALIDATION.md").read_text(encoding="utf-8")
sb  = (root / "config/scenario_book.yaml").read_text(encoding="utf-8")

print("SP12I-01 Sharpe drift:")
print("  master fitness :", re.search(r"Fitness = Sharpe[^,]*", master).group(0))
print("  master §8 snap :", "rolling 50-trade Sharpe" in master)
print("  ACIS-07 field  :", "NOT an annualised Sharpe" in a07)
print("  GAP-0105 closed but master still says 'Sharpe' (no 'mean_sigma' in master):",
      "mean_sigma" not in master and "per-trade mean" not in master)

print("SP12I-02 marginal-alpha / throttle prose constants unpinned:")
print("  master floor/cap/throttle present:", bool(re.search(r"floors at 0.25", master)),
      bool(re.search(r"Cap 1.5", master)), bool(re.search(r"cut all allocations to 25%", master)))
print("  drift test references 0.25 / 1.5 / 25%:",
      "0.25" in tst, "1.5" in tst, "25%" in tst)

print("SP12I-03 MOMENTUM_SCALP fast-decay fencepost:")
vfs = sysc["signals"]["valid_for_seconds"]["MOMENTUM_SCALP"]
fds = sysc["execution"]["fast_decay_seconds"]
print(f"  scalp valid_for={vfs}  fast_decay_seconds={fds}  strict '<' rule -> qualifies={vfs < fds}")
print("  ACIS-06 rule:", re.search(r"valid_for_seconds < fast_decay_seconds[^\n]*", a06).group(0)[:70])

print("SP12I-04 adx config-key naming drift:")
print("  actual config regime keys:", [k for k in sysc["regime"] if "adx" in k])
print("  ACIS-02 §6 says 'adx_strong_threshold':", "adx_strong_threshold" in a02)

print("SP12I-05 scenario_book vs ACIS-09 staleness:")
print("  scenario_book 'deferred to phase 11':", "deferred to phase 11" in sb)
print("  ACIS-09 says refinement delivered:", "refined to source the worst gap" in a09)
