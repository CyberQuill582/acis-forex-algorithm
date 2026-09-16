"""The constitution's checks, as one command (SPEC_CONSTITUTION A12/A14/A15/A16).

ACIS has no npm, so the family checks — which are language-agnostic and live once in
`../specs_constitution/checks/` rather than being copied per project (A14: forks drift) —
are composed here instead.

    python scripts/governance_gate.py            # the phase green gate: everything
    python scripts/governance_gate.py --session  # session start: the cheap subset only

Session start is deliberately cheap (drift + shape + the ledger digest, seconds). The
falsification harness runs at the phase gate and NEVER at session start: a slow harness
wired into every run gets disabled, which is worse than none (A16).

Exit 0 only when every step it ran exited 0; the first failure is reported and the rest
still run, so one red step never hides another.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECKS = REPO.parent / "specs_constitution" / "checks"

SHAPE_RULES = "HEADER,BLOCK,HISTORY,QUOTE"

# (label, argv, session-start?) — argv[0] "node" is resolved below.
STEPS = [
    ("constitution drift + read path (A14/A13)", ["node", str(CHECKS / "constitution-drift.mjs"), "."], True),
    # SIZE is tests/unit/test_module_budget.py's ratchet already; this carries the comment rules
    ("comment shape, ratcheted (A12)", ["node", str(CHECKS / "code-shape.mjs"), "--rule", SHAPE_RULES,
                                        "--baseline", "code-shape.baseline.json"], True),
    ("comment shape, files this phase touched (A12)", ["node", str(CHECKS / "code-shape.mjs"),
                                                       "--rule", SHAPE_RULES,
                                                       "--baseline", "code-shape.baseline.json",
                                                       "--since", "HEAD", "--quiet"], False),
    ("ledger closure (A15)", [sys.executable, str(REPO / "scripts" / "ledger_check.py")], True),
    ("falsification (A16)", ["node", str(CHECKS / "falsify.mjs"), "--root", "."], False),
]


def main(argv: list[str]) -> int:
    session_only = "--session" in argv
    if shutil.which("node") is None:
        print("governance_gate: node is not on PATH — the family checks cannot run.", file=sys.stderr)
        return 2
    if not CHECKS.is_dir():
        print(f"governance_gate: no checks directory at {CHECKS}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for label, argv_step, at_session in STEPS:
        if session_only and not at_session:
            continue
        print(f"\n=== {label} ===", flush=True)
        code = subprocess.run(argv_step, cwd=REPO).returncode
        if code != 0:
            failures.append(f"{label} (exit {code})")

    print()
    if failures:
        print("governance_gate: RED —", "; ".join(failures), file=sys.stderr)
        return 1
    print(f"governance_gate: green ({'session subset' if session_only else 'full phase gate'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
