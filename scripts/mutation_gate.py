"""Targeted mutation-testing quality gate (ACIS-09 §14, master §16 / v2.10 item d).

Mutation-tests the code whose silent lies are most expensive — the fitness
function, the C8 cost model, the §14 backtest metrics and the Deflated Sharpe —
and treats a SURVIVING mutant (a change the tests do not catch) as a finding to
triage.

This is a PERIODIC gate (CI / manual), deliberately NOT part of the fast pytest
suite: a full mutation campaign is slow. `mutmut` (2.x; mutmut 3 does not run on
Windows) is a declared dev/CI-tier dependency per the §16 spec edit — it is NOT a
core or fast-loop dependency, and importing it is not required to run the engine.
Run:

    python scripts/mutation_gate.py            # runs mutmut on the targets
    python scripts/mutation_gate.py --check    # verify config only (CI smoke)

mutmut calls `--run-tests` once per mutant (see `run_tests`). A surviving mutant is
NOT auto-fixed and NEVER weakens a guardrail — it is surfaced for a human/author to
add the missing test, exactly like an adversarial audit finding.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The high-value targets (master §16 v2.10 item d): fitness, cost model, metrics — plus the
# Deflated Sharpe, a graded metric since the report's pass verdict gates on it (GAP-P12D-28).
TARGETS = (
    "core/optimizer/fitness.py",
    "core/optimizer/costs.py",
    "tests/backtest/metrics.py",
    "tests/backtest/deflated_sharpe.py",
)
# the tests a mutant must fail to be killed (the cost model is exercised through the fitness suite)
TESTS = (
    "tests/unit/test_fitness.py",
    "tests/unit/test_fitness_indicators.py",
    "tests/unit/test_fitness_exits.py",
    "tests/unit/test_fitness_components.py",
    "tests/unit/test_fitness_entries.py",
    "tests/backtest/test_metrics_and_grader.py",
    "tests/backtest/test_metrics_exact.py",
    "tests/backtest/test_oos_honesty.py",
    "tests/backtest/test_deflated_sharpe.py",
    "tests/backtest/test_deflated_sharpe_exact.py",
)
RUNNER = "python scripts/mutation_gate.py --run-tests"


def _config_ok() -> bool:
    for t in TARGETS + TESTS:
        if not (REPO / t).is_file():
            print(f"MISSING file: {t}", file=sys.stderr)
            return False
    return True


def run_tests(run=subprocess.run) -> int:
    """The per-mutant test run. mutmut 2 records a mutant as killed ONLY when its runner exits
    with 1, so pytest's exit 2 — a collection error, which is what a mutant that breaks an
    import produces — was recorded as a SURVIVOR (GAP-P12D-28: CostModel's `v = None` mutant
    was killed by hand but "survived" the gate). Every failing exit is reported as 1.
    No bytecode is written: mutmut swaps same-size lines back and forth within a second, and a
    cached .pyc matching a file's size and mtime second ran the WRONG version (metrics `return
    0.0` -> `return 1.0` "survived" the gate but was killed by hand)."""
    code = run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
               cwd=REPO, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).returncode
    return 0 if code == 0 else 1


def main(argv: list[str]) -> int:
    if "--run-tests" in argv:
        return run_tests()
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
              "`pip install mutmut==2.5.1`. It is intentionally NOT a runtime dependency.",
              file=sys.stderr)
        return 3
    paths = ",".join(str(REPO / t) for t in TARGETS)
    cmd = ["mutmut", "run", "--paths-to-mutate", paths, "--runner", RUNNER]
    print("running:", " ".join(cmd))
    # the sources are UTF-8; mutmut 2 opens them with the platform default (cp1252 on Windows)
    proc = subprocess.run(cmd, cwd=REPO, env={**os.environ, "PYTHONUTF8": "1"})
    return _verdict(proc.returncode)


def _verdict(code: int) -> int:
    """mutmut 2's exit code is a bit field: 1 fatal error, 2 survived, 4 timeout, 8 suspicious."""
    if code & 1:
        print("\nMUTMUT FAILED TO RUN — no verdict; this is not a pass.", file=sys.stderr)
    elif code & 2:
        print("\nSURVIVING MUTANT(S) — a finding to triage: add the missing test "
              "for the graded metric / cost model that the mutant slipped past. "
              "Do NOT weaken any guard to make a mutant die. `mutmut results` lists them.",
              file=sys.stderr)
    elif code:
        print("\nno survivors, but timeouts/suspicious mutants — inspect `mutmut results`.",
              file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
