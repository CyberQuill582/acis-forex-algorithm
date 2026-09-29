"""The lab-hygiene law (R1.1 C-10; ACIS-09 C-BT-12, R-1 item 5): the lab grades machinery, never
edge. It is never fitted to real data and holds no second cost model, and this test makes both
structural with an ALLOWLIST (audit R11I-12: a denylist was bypassed four ways):
  * a lab module may import only the stdlib and numpy modules named below, and from the repo only
    the NAMED objects below (so `financing.load_rate_table`, which reads real data, is out);
  * no dynamic import, exec, eval or file access;
  * no friction constant under any name: a number bound to a commission, slippage, markup or fee
    name, as an assignment, a default or a keyword, is refused (C-7: costs come from a declared
    instrument's block).
The checker is proven against the four bypasses the audit built."""

from __future__ import annotations

import ast
import re
from pathlib import Path

LAB = sorted((Path(__file__).resolve().parent).glob("lab_*.py"))
PLAIN = {"__future__", "math", "bisect", "dataclasses", "datetime", "statistics", "typing", "numpy"}
NAMED = {"tests.backtest.carry": {"swap_multiplier"}, "tests.backtest.financing": {"RateTable"},
         "tests.backtest.data_loader": {"TickSource"}, "core.data.fx_clock": {"rollover_utc"},
         "core.data.normaliser": {"RawTick"}, "config.schemas": {"AcisConfig"}}
LAB_MODULES = {f"tests.backtest.{p.stem}" for p in LAB}
DYNAMIC = {"importlib", "__import__", "exec", "eval", "compile", "open"}
FRICTION = re.compile(r"commission|slippage|markup|fee|per_side|spread_cost", re.I)


def violations(source: str) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out += [f"import {a.name}" for a in node.names if a.name.split(".")[0] not in PLAIN]
        elif isinstance(node, ast.ImportFrom):
            mod, names = node.module or "", {a.name for a in node.names}
            ok = (mod.split(".")[0] in PLAIN or mod in LAB_MODULES
                  or (mod in NAMED and names <= NAMED[mod]))
            if not ok:
                out.append(f"from {mod} import {sorted(names)}")
        elif isinstance(node, ast.Name) and node.id in DYNAMIC and isinstance(node.ctx, ast.Load):
            out.append(f"dynamic {node.id}")          # a field DECLARED as `open` is not a read of open()
        elif isinstance(node, ast.Attribute) and node.attr in ("import_module", "__import__"):
            out.append(f"dynamic .{node.attr}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id if isinstance(t, ast.Name) else getattr(t, "attr", "") for t in targets]
            if any(FRICTION.search(n) for n in names) and _has_number(node.value):
                out.append(f"friction constant {names}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args.args[len(node.args.args) - len(node.args.defaults):] + node.args.kwonlyargs
            defaults = node.args.defaults + [d for d in node.args.kw_defaults]
            out += [f"friction default {a.arg}" for a, d in zip(args, defaults)
                    if d is not None and FRICTION.search(a.arg) and _has_number(d)]
        elif isinstance(node, ast.keyword) and node.arg and FRICTION.search(node.arg) and _has_number(node.value):
            out.append(f"friction keyword {node.arg}")
    return out


def _has_number(node: ast.AST | None) -> bool:
    return node is not None and any(isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                                    and not isinstance(n.value, bool) for n in ast.walk(node))


def test_the_lab_modules_exist() -> None:
    assert {p.stem for p in LAB} >= {"lab_theory", "lab_market", "lab_intraday", "lab_source", "lab_calibration"}


def test_every_lab_module_obeys_the_allowlist() -> None:
    for path in LAB:
        assert violations(path.read_text(encoding="utf-8")) == [], path.name


def test_the_checker_catches_the_four_bypasses_the_audit_built() -> None:
    """R11I-12 (d): an allowed module's real-data loader, a dynamic import, a friction constant as
    a default, and one under another name. Plus the plain cases the old lint caught."""
    for bypass in ("from tests.backtest.financing import load_rate_table",
                   "import importlib\nm = importlib.import_module('tests.backtest.' + 'sources')",
                   "def spread(x, commission_per_side=0.5):\n    return x",
                   "MARKUP = 0.0002",
                   "from tests.backtest.sources import DukascopyTickSource",
                   "import scripts.download_dukascopy_s3",
                   "rows = open('data/dukascopy/x.bi5').read()",
                   "CostModel(slippage_per_side=0.00002)"):
        assert violations(bypass), bypass
    assert violations("import math\nfrom tests.backtest.financing import RateTable\nbase_spread = 1e-4") == []
