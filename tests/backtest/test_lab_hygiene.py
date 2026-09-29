"""The lab-hygiene law (R1.1 C-10; ACIS-09 C-BT-12, R-1 item 5): the lab grades machinery, never
edge. It is never fitted to real data and holds no second cost model, and this test makes both
structural: no lab module imports a real-data source or names a data path, and none defines a
friction constant (C-7: costs come from a declared instrument's block)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

LAB = sorted((Path(__file__).resolve().parent).glob("lab_*.py"))
FORBIDDEN_MODULES = ("tests.backtest.sources", "tests.backtest.download", "scripts")
FORBIDDEN_TEXT = re.compile(r"(?<![\w/])data/|\.bi5|\.csv|dukascopy|histdata")   # the repo's data/, not core/data/
FRICTION = ("commission", "slippage", "per_side_cost")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_the_lab_modules_exist() -> None:
    assert {p.stem for p in LAB} >= {"lab_theory", "lab_market", "lab_intraday", "lab_source"}


def test_no_lab_module_imports_a_real_data_source() -> None:
    for path in LAB:
        for node in ast.walk(_tree(path)):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            bad = [n for n in names if n.startswith(FORBIDDEN_MODULES) or n.split(".")[0] == "data"]
            assert not bad, (path.name, bad)


def test_no_lab_module_names_a_data_file_or_a_vendor() -> None:
    for path in LAB:
        strings = [n.value.lower() for n in ast.walk(_tree(path))
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        bad = [s for s in strings if FORBIDDEN_TEXT.search(s)]
        assert not bad, (path.name, bad)


def test_no_lab_module_defines_a_friction_constant() -> None:
    for path in LAB:
        targets = [t.id.lower() for n in ast.walk(_tree(path)) if isinstance(n, (ast.Assign, ast.AnnAssign))
                   for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)]
        assert not [t for t in targets if any(f in t for f in FRICTION)], path.name
