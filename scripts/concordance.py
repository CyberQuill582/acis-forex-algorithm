"""Concordance generator (owner-ratified 2026-07-17, surface-area reduction).

Scans every doc and source file for rule/finding IDs (GAP-NNNN, F-series,
C-series corrections, C-XXX-N deep-spec contracts) and regenerates
CONCORDANCE.md: each ID -> every file:line where it appears. The output is
GENERATED, never hand-edited — the same ID cited in two places with different
meanings becomes something you can SEE instead of a contradiction hiding
across ~400KB of prose. Deterministic output; stdlib only; run on demand:

    python scripts/concordance.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "CONCORDANCE.md"

# ID grammar, most-specific first so C-RSK-6 is never eaten as bare "C6".
ID_RE = re.compile(
    r"\b(GAP-\d{4}|C-[A-Z]{2,5}-\d{1,2}|[CF]\d{1,2})\b"
)
# Bare C/F hits only count as IDs in prose contexts; these are known non-IDs.
NOISE = {"F1"}  # extend if a false positive ever appears

SCAN_GLOBS = ["*.md", "specs/*.md", "config/*.py", "config/*.yaml",
              "core/**/*.py", "monitoring/**/*.py", "tests/**/*.py"]
SKIP_NAMES = {OUT.name}


def _sort_key(ident: str) -> tuple:
    if ident.startswith("GAP-"):
        return (0, int(ident[4:]))
    if re.fullmatch(r"C\d+", ident):
        return (1, int(ident[1:]))
    if re.fullmatch(r"F\d+", ident):
        return (2, int(ident[1:]))
    return (3, ident)


def build() -> str:
    hits: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    files = sorted({p for g in SCAN_GLOBS for p in ROOT.glob(g)
                    if p.is_file() and p.name not in SKIP_NAMES})
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in ID_RE.finditer(line):
                ident = m.group(1)
                if ident not in NOISE:
                    hits[ident][rel].append(lineno)

    lines = [
        "# CONCORDANCE.md — GENERATED, DO NOT EDIT",
        "",
        "Regenerate with `python scripts/concordance.py`. Maps every rule/finding ID",
        "to each file:line citing it, so cross-document contradictions are visible as",
        "diffs instead of hiding in prose. Not normative — the specs and ledgers are.",
        "",
    ]
    for ident in sorted(hits, key=_sort_key):
        locs = hits[ident]
        total = sum(len(v) for v in locs.values())
        parts = [f"{f}:{','.join(map(str, ns))}" for f, ns in sorted(locs.items())]
        lines.append(f"- **{ident}** ({total}) — " + " · ".join(parts))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8", newline="\n")
    n_ids = sum(1 for ln in build().splitlines() if ln.startswith("- **"))
    print(f"wrote {OUT.name}: {n_ids} distinct IDs")
