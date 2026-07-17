"""The import-direction law (SPEC §2) as an executable contract.

Must exist before layer 2 is started and stay green forever. Each core layer
may import ONLY from itself and its declared upstream producer(s); everything
else core-to-core is a violation — including RELATIVE imports, which are
resolved against the file's package before matching (GAP-0026).

Ruling recorded for GAP-0021 (the ALLOWED map's interpretation of §2):
§2's "one layer at a time" governs the DATA FLOW (each layer consumes the
boundary object of the layer directly above). Type/producer IMPORTS follow the
spec's own explicit cross-references: §5.5 has the Arena read RegimeContext +
ActiveParamSet (signals→{optimizer, regime}); §6's sizing formula consumes
regime factors (governor→regime); §5 has QIEA read regime-labelled HISTORICAL
data only (optimizer→{regime, data}). Any import outside these named edges is
a violation; widening ALLOWED requires a spec citation added here. The single
upward Risk→Governor edge is a RUNTIME channel (risk-restrictive instructions
only) — never an import license.

Also asserts the §7.5 feed-face rule (C-DATA-6): no account/position surface.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORE = REPO_ROOT / "core"

ALLOWED: dict[str, set[str]] = {
    "data": set(),
    "regime": {"data"},
    "optimizer": {"regime", "data"},   # §5: fitness on regime-labelled history
    # §5.5 + ACIS-04 §2 (LOCKED): AGON consumes MarketState directly and shares the
    # data-layer error/logging vocabulary — hence "data" (widened at phase 5 with
    # this citation, per the GAP-0021 ruling recorded above).
    "signals": {"optimizer", "regime", "data"},
    # §6 + ACIS-05 §2/§5 (LOCKED): the Governor consumes Signal + RegimeContext,
    # shares the data-layer error vocabulary (PortfolioState raises
    # DataQualityError), and reuses the proven ATR for C16 vol-norm — hence
    # "data" (widened at phase 6 with this citation, GAP-0021 ruling pattern).
    "governor": {"signals", "regime", "data"},
    # §7 + ACIS-06 v1.1 (LOCKED): Execution consumes SizedOrder and shares the
    # data-layer error/logging vocabulary (FillReport validates on construction
    # raising DataQualityError, ACIS-00 §4 error base; JSONL envelope §11) —
    # hence "data" (widened at phase 8 with this citation, GAP-0021 ruling
    # pattern). NO market-state/feed import: quotes reach execution only as
    # prices on orders; the feed face stays ACIS-01's (GAP-0013).
    "execution": {"governor", "data"},
    "risk": {"execution"},
}


def _core_imports(path: Path, root: Path) -> set[str]:
    """Layers named by any import in `path`, with relative imports resolved
    against the file's package (GAP-0026: `from ..risk import x` == `core.risk`)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(root.parent).with_suffix("")
    pkg = list(rel.parts[:-1] if rel.parts[-1] != "__init__" else rel.parts[:-1])
    found: set[str] = set()

    def _note(parts: list[str]) -> None:
        if len(parts) >= 2 and parts[0] == "core":
            found.add(parts[1])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _note(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    _note(node.module.split("."))
            else:
                base = pkg[: len(pkg) - (node.level - 1)]
                suffix = node.module.split(".") if node.module else []
                _note(base + suffix)
    return found


def _scan(core_root: Path) -> list[str]:
    violations: list[str] = []
    for layer_dir in sorted(
        p for p in core_root.iterdir() if p.is_dir() and not p.name.startswith("_")
    ):
        layer = layer_dir.name
        assert layer in ALLOWED, f"unknown core layer directory: {layer}"
        for py in layer_dir.rglob("*.py"):
            for imported in _core_imports(py, core_root):
                if imported != layer and imported not in ALLOWED[layer]:
                    violations.append(f"{py} imports core.{imported}")
    return violations


def test_no_upward_or_skip_imports() -> None:
    violations = _scan(CORE)
    assert not violations, "layer-law violations:\n" + "\n".join(violations)


def test_relative_upward_import_is_caught(tmp_path: Path) -> None:
    """GAP-0026: the contract must see `from ..risk import x` inside core/data."""
    fake_core = tmp_path / "core"
    (fake_core / "data").mkdir(parents=True)
    (fake_core / "data" / "evil.py").write_text(
        "from ..risk import monitor\n", encoding="utf-8"
    )
    violations = _scan(fake_core)
    assert violations and "core.risk" in violations[0]


def test_feed_face_exposes_no_account_surface() -> None:
    """GAP-0013 / C-DATA-6: quotes only — no account, position, equity, margin."""
    from core.data import feeds

    forbidden = re.compile(r"account|position|equity|margin|balance|order", re.IGNORECASE)
    for _, cls in inspect.getmembers(feeds, inspect.isclass):
        if cls.__module__ != feeds.__name__:
            continue
        for member in dir(cls):
            if member.startswith("_"):
                continue
            assert not forbidden.search(member), (
                f"{cls.__name__}.{member}: feed face must expose no account surface"
            )
