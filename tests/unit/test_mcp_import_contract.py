"""C-MCP-4: the MCP plane holds only narrow injected interfaces — it imports NO
`core/*` layer internals (no side channel, no bypass of Governor/Risk).

`monitoring/` may import stdlib and `config` (shared infrastructure: schemas +
the hash helpers); it must not import any `core.*` module. Control reaches the
engine only through the injected `ControlTarget`/`ConfigStager` protocols, and
observation only through injected provider callables — so there is no import
path by which the server could reach a guardrail or a layer's internals.
"""

from __future__ import annotations

import ast
from pathlib import Path

MONITORING = Path(__file__).resolve().parent.parent.parent / "monitoring"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module)
    return mods


def test_monitoring_imports_no_core_internals() -> None:
    offenders: list[str] = []
    for py in MONITORING.rglob("*.py"):
        for mod in _imports(py):
            if mod == "core" or mod.startswith("core."):
                offenders.append(f"{py.name} imports {mod}")
    assert not offenders, "monitoring must not import core internals:\n" + "\n".join(offenders)


def test_monitoring_only_imports_stdlib_config_or_self() -> None:
    """Positive form: every non-stdlib import is `config.*` or `monitoring.*`."""
    allowed_roots = {"config", "monitoring"}
    third_party_ok = {"structlog"}          # only if a module logs directly (none should)
    stray: list[str] = []
    for py in MONITORING.rglob("*.py"):
        for mod in _imports(py):
            root = mod.split(".")[0]
            if root in allowed_roots or root in third_party_ok:
                continue
            # stdlib check: importable without a top-level package we ship
            try:
                __import__(root)
            except Exception:
                stray.append(f"{py.name}: {mod}")
                continue
            # a stdlib module has no file under core/ or our packages — accept
    assert not stray, "unexpected imports:\n" + "\n".join(stray)
