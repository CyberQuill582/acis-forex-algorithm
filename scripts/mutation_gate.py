"""Targeted mutation-testing quality gate (ACIS-09 §14, master §16 / v2.10 item d).

Mutation-tests the code whose silent lies are most expensive — the fitness
function, the C8 cost model, and the §14 backtest metrics — and treats a
SURVIVING mutant (a change the tests do not catch) as a finding to triage.

This is a PERIODIC gate (CI / manual), deliberately NOT part of the fast pytest
suite: a full mutation campaign is slow. `mutmut` is a declared dev/CI-tier
dependency per the §16 spec edit — it is NOT a core or fast-loop dependency, and
importing it is not required to run the engine. Run:

    python scripts/mutation_gate.py            # runs mutmut on the targets
    python scripts/mutation_gate.py --check    # verify config only (CI smoke)

A surviving mutant is NOT auto-fixed and NEVER weakens a guardrail — it is
surfaced for a human/author to add the missing test, exactly like an adversarial
audit finding.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The high-value targets (master §16 v2.10 item d): fitness, cost model, metrics.
TARGETS = (
    "core/optimizer/fitness.py",
    "core/optimizer/costs.py",
    "tests/backtest/metrics.py",
)
# tests that must pass for a mutant to be "killed" (the graded-metric + cost/
# fitness tests — the cost model is exercised through the fitness suite).
RUNNER = "python -m pytest tests/backtest/test_metrics_and_grader.py "\
    "tests/unit/test_fitness.py -q"


def _config_ok() -> bool:
    for t in TARGETS:
        if not (REPO / t).is_file():
            print(f"MISSING target: {t}", file=sys.stderr)
            return False
    return True


def main(argv: list[str]) -> int:
    if not _config_ok():
        return 2
    if "--check" in argv:
        print("mutation-gate config OK; targets:", ", ".join(TARGETS))
        return 0
    try:
        import mutmut  # noqa: F401  (dev/CI-tier dependency, §16)
    except ImportError:
        print("mutmut not installed — this is the declared dev/CI dependency "
              "(§16). Install it in the CI/quality-gate environment: "
              "`pip install mutmut`. It is intentionally NOT a runtime dependency.",
              file=sys.stderr)
        return 3
    paths = ",".join(str(REPO / t) for t in TARGETS)
    cmd = ["mutmut", "run", "--paths-to-mutate", paths, "--runner", RUNNER]
    print("running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=REPO)
    # mutmut returns non-zero when mutants survive; surface it as a gate failure.
    if proc.returncode != 0:
        print("\nSURVIVING MUTANT(S) — a finding to triage: add the missing test "
              "for the graded metric / cost model that the mutant slipped past. "
              "Do NOT weaken any guard to make a mutant die.", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
