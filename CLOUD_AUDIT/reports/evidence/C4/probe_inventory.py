"""C4 receipt: size inventory of ACIS components at BASE (read-only; run with cwd=/tmp/review-acis).

For each component: production files, physical lines, non-blank/non-comment/non-docstring-ish
lines (rough), number of test functions in test files that import the component's package,
and how many OPEN/MITIGATED ledger entries mention a component path. Prints a markdown table.
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
COMP = {
    "NVMA regime gate": (["core/regime"], ["core.regime"]),
    "QIEA + param library + fitness + costs": (["core/optimizer"], ["core.optimizer"]),
    "AGON arena + modules + provenance": (["core/signals"], ["core.signals"]),
    "Capital Governor": (["core/governor"], ["core.governor"]),
    "Risk Monitor + guardrails + scenario book": (["core/risk"], ["core.risk"]),
    "Execution Orchestrator + adapter contract": (["core/execution"], ["core.execution"]),
    "MCP plane": (["monitoring"], ["monitoring", "mcp"]),
    "Event/news intake (core/data/events.py)": (["core/data/events.py"], ["core.data.events"]),
    "Data layer (rest of core/data)": (["core/data"], ["core.data"]),
    "Backtest harness (tests/backtest non-test)": (["tests/backtest"], ["tests.backtest"]),
    "Governance tooling (ledger/gate/concordance/mutation)": (
        ["scripts/ledger_check.py", "scripts/governance_gate.py", "scripts/concordance.py", "scripts/mutation_gate.py"],
        ["scripts.ledger_check", "scripts.governance_gate", "scripts.concordance", "scripts.mutation_gate", "module_budget", "ledger_integrity", "mutation_gate"]),
    "Falsification/ladder/OOS runners": (
        ["scripts/falsify_engine.py", "scripts/cost_stress_ladder.py", "scripts/run_oos_validation.py"],
        ["scripts.falsify_engine", "scripts.cost_stress_ladder", "scripts.run_oos_validation", "falsification", "cost_stress"]),
    "Watchdog": (["scripts/acis_watchdog.py"], ["scripts.acis_watchdog", "watchdog"]),
}

def prod_files(paths):
    out = []
    for p in paths:
        q = ROOT / p
        if q.is_file():
            out.append(q)
        else:
            out += [f for f in q.rglob("*.py") if not f.name.startswith("test_") and "__pycache__" not in f.parts]
    return out

tests = [f for f in (ROOT / "tests").rglob("test_*.py")]
tsrc = {f: f.read_text(encoding="utf-8") for f in tests}
ledger = (ROOT / "KNOWN_GAPS.md").read_text(encoding="utf-8")
entries = re.split(r"\n(?=## GAP-)", ledger)
open_entries = [e for e in entries if e.startswith("## GAP-") and re.search(r"Status:\*?\*?\s*(open|OPEN|mitigated|MITIGATED|Open|Mitigated)", e)]

print("| Component | files | lines | test fns (files importing it) | open/mitigated gaps citing its path |")
print("|---|---|---|---|---|")
tot = 0
for name, (paths, mods) in COMP.items():
    fs = prod_files(paths)
    if name.startswith("Data layer"):
        fs = [f for f in fs if f.name != "events.py"]
    lines = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in fs)
    tot += lines
    tfs = [f for f, s in tsrc.items() if any(re.search(r"(from|import)\s+" + re.escape(m) + r"\b", s) or m in f.name for m in mods)]
    nfn = sum(len(re.findall(r"^\s*(async\s+)?def test_", tsrc[f], re.M)) for f in tfs)
    keys = [str(Path(p)) for p in paths]
    ng = sum(1 for e in open_entries if any(k in e for k in keys))
    print(f"| {name} | {len(fs)} | {lines} | {nfn} ({len(tfs)}) | {ng} |")
print(f"\nTotal lines counted: {tot}")
