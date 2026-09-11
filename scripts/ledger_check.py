"""Ledger closure check (CLAUDE.md "Ledger closure law"; SPEC_CONSTITUTION A15).

L1 unique IDs · L2 every cited ID resolves · L3 status vocabulary · L4 proof pointers
(tests, files) exist; a closure cites real proof · L5 a closure declares its Residual
(`none — why` or an owning ID) · L6 open/raised items are on TODO.md · L7 nothing live
in the archive · L8 parked items are justified · L9 stale unchecked to-dos.
Historical test names are written "former `test_x`"; "GAP-P10I" names an audit family.

Usage:  python scripts/ledger_check.py            # exit 1 + report on any violation
        python scripts/ledger_check.py --summary  # session-start digest of live items
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = "KNOWN_GAPS.md"
ARCHIVE = "KNOWN_GAPS_CLOSED.md"
OPS = "OPERATIONS_LEDGER.md"
TODO = "TODO.md"

# GAP-0092 / GAP-0091b / GAP-P11E-04 / GAP-SP12I-DOC; a tail starts upper-case or digit ("-pattern" is prose)
ID_RE =re.compile(r"\b(?:GAP|OPS)-[A-Za-z]*\d+[A-Za-z]*(?:-[A-Z0-9][A-Za-z0-9]*)?\b")
FAMILY_RE = re.compile(r"^GAP-S?P\d+[IE]$")       # "GAP-P10I" = a whole audit family, not an ID
ALIAS_RE = re.compile(r"\((P\d+[IE]-\d+[a-z]?)\)")  # "## GAP-0104 (P9E-04): ..." heading alias
PLACEHOLDER_RE = re.compile(r"\b(?:GAP|OPS)-(?:[A-Z0-9]+-)?(?:N+|X+|nn)\b")
STATUS_RE = re.compile(r"Status\**\s*:\s*\**\s*([A-Za-z][A-Za-z-]*)")
TEST_NAME_RE = re.compile(r"\btest_[A-Za-z0-9_]+\b(?!\s*=)")   # not `test_start = ...` prose
FORMER_RE = re.compile(r"former `?test_[A-Za-z0-9_]+`?")
RESIDUAL_RE = re.compile(r"\b(residual|remain(?:s|ing|der)?|follow-?up|deferred|still owed|not yet)\b", re.I)
RESIDUAL_FIELD_RE = re.compile(r"^- \**Residual\**\s*:\s*(.+)$", re.M)
DOC_PROOF_RE = re.compile(r"(?:ACIS_SPEC\.md|ACIS-\d\d\b|CLAUDE\.md|master §)")
PATH_RE = re.compile(r"(?<![\w/.-])((?:\[DIR:)?[A-Za-z_][\w.-]*(?:/[\w.-]+)+|[A-Z][A-Z0-9_]+\.md)")

LIVE_STATUSES = {"open", "raised", "mitigated", "accepted-risk"}
DONE_STATUSES = {"fixed", "closed", "resolved", "superseded"}
INFO_STATUSES = {"informational"}
VOCAB = LIVE_STATUSES | DONE_STATUSES | INFO_STATUSES
SCAN_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".js", ".ps1", ".toml", ".json", ".txt"}
SKIP_DIRS = {".git", ".claude", "node_modules", "data", "archive", "scratchpad",
             "conversation-archive", "__pycache__", ".pytest_cache", ".venv"}
FILE_EXT = (".py", ".md", ".yaml", ".yml", ".json", ".toml", ".ps1", ".js", ".txt", ".csv")
SPEC_SHORT_RE = re.compile(r"^specs/(ACIS-\d\d)$")
REPO_DIRS = {"core", "tests", "specs", "config", "monitoring", "scripts", "deploy", "archive"}
_NAME_INDEX: dict[str, list[Path]] | None = None


@dataclass
class Entry:
    ids: list[str]
    title: str
    file: str
    line: int
    body: str
    status: str | None = None
    refs: set[str] = field(default_factory=set)


def parse_ledger(path: Path) -> list[Entry]:
    if not path.exists():
        return []
    entries: list[Entry] = []
    cur: Entry | None = None
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            head = line.split(":")[0]
            ids = ID_RE.findall(head) or ID_RE.findall(line)
            ids += [f"GAP-{a}" for a in ALIAS_RE.findall(head)]
            if ids:
                cur = Entry(ids=ids, title=line[3:].strip(), file=path.name, line=n, body="")
                entries.append(cur)
                continue
            cur = None                              # a non-entry section heading
        elif line.startswith("<!--"):
            cur = None                              # audit banners are not entry bodies
        elif cur is not None:
            cur.body += line + "\n"
    for e in entries:
        m = STATUS_RE.search(e.body)
        e.status = m.group(1).lower() if m else None
        e.refs = {r for r in ID_RE.findall(PLACEHOLDER_RE.sub("", e.body))
                  if not FAMILY_RE.match(r)} - set(e.ids)
    return entries


def repo_test_names() -> tuple[set[str], set[str]]:
    """(test function names, test module stems) under tests/."""
    files = list((ROOT / "tests").rglob("test_*.py"))
    funcs = {f for p in files for f in re.findall(r"^\s*(?:async\s+)?def (test_[A-Za-z0-9_]+)",
                                                  p.read_text(encoding="utf-8"), re.M)}
    return funcs, {p.stem for p in files}


def test_ref_resolves(name: str, funcs: set[str], modules: set[str]) -> bool:
    """A cited `test_x` names a test function or module, or prefixes one (`test_stop_*`)."""
    return any(x == name or x.startswith(name) for x in funcs | modules)


def _name_index() -> dict[str, list[Path]]:
    """basename -> paths, over the repo (archive included, junk dirs excluded)."""
    global _NAME_INDEX
    if _NAME_INDEX is None:
        _NAME_INDEX = {}
        skip = SKIP_DIRS - {"archive"}
        for p in ROOT.rglob("*"):
            if p.is_file() and not any(x in skip for x in p.relative_to(ROOT).parts):
                _NAME_INDEX.setdefault(p.name, []).append(p)
    return _NAME_INDEX


def cited_paths(text: str) -> tuple[set[str], set[str]]:
    """(pointers that resolve, pointers that don't): repo paths, `[DIR:x]` tags, `specs/ACIS-NN`,
    bare doc names. A pointer resolving ONLY inside archive/ is rot — the file moved."""
    ok, bad = set(), set()
    for raw in PATH_RE.findall(text):
        is_dir = raw.startswith("[DIR:")
        p = raw.removeprefix("[DIR:").rstrip("].,;:)`'\"")
        if p.startswith(("http", "www.", "data/", "~")) or "*" in p or "{" in p:
            continue
        short = SPEC_SHORT_RE.match(p)
        if short:
            (ok if list((ROOT / "specs").glob(f"{short.group(1)}-*.md")) else bad).add(p)
            continue
        if not (is_dir or p.endswith(FILE_EXT)):
            continue                                     # prose like "config/enum"
        if "/" in p:
            if p.split("/")[0] not in REPO_DIRS:
                continue
            if (ROOT / p).exists():
                ok.add(p)
            else:
                moved = (ROOT / "archive" / Path(p).name).exists()
                bad.add(p + (" (now in archive/ — update the pointer)" if moved else ""))
            continue
        hits = _name_index().get(p, [])
        live = [h for h in hits if "archive" not in h.relative_to(ROOT).parts]
        if live:
            ok.add(p)
        elif hits:
            bad.add(p + " (now in archive/ — update the pointer)")
        else:
            bad.add(p)
    return ok, bad


def repo_references() -> dict[str, list[str]]:
    """Every GAP-/OPS- ID cited in tracked text files outside the ledgers."""
    refs: dict[str, list[str]] = {}
    for p in ROOT.rglob("*"):
        if (not p.is_file() or p.suffix not in SCAN_SUFFIXES
                or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts)
                or p.name in (LIVE, ARCHIVE, OPS)):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        text = PLACEHOLDER_RE.sub("", text)
        for i in set(ID_RE.findall(text)):
            if FAMILY_RE.match(i):
                continue
            refs.setdefault(i, []).append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return refs


def check() -> tuple[list[str], list[Entry]]:
    live = parse_ledger(ROOT / LIVE)
    archive = parse_ledger(ROOT / ARCHIVE)
    ops = parse_ledger(ROOT / OPS)
    entries = live + archive + ops
    v: list[str] = []
    where = lambda e: f"{e.file}:{e.line} {'/'.join(e.ids)}"

    # L1 unique
    seen: dict[str, Entry] = {}
    for e in entries:
        for i in e.ids:
            if i in seen:
                v.append(f"L1 UNIQUE    {i} defined twice: {where(seen[i])} and {where(e)}")
            seen[i] = e
    by_id = seen

    # L2 every cited ID resolves (repo files + inside ledger bodies)
    for i, files in sorted(repo_references().items()):
        if i not in by_id:
            v.append(f"L2 RESOLVES  {i} cited in {', '.join(sorted(files)[:4])} but defined in no ledger")
    for e in entries:
        for r in sorted(e.refs - set(by_id)):
            v.append(f"L2 RESOLVES  {where(e)} cites {r}, which no ledger defines")

    funcs, modules = repo_test_names()
    todo_text = (ROOT / TODO).read_text(encoding="utf-8")
    todo_ids = set(ID_RE.findall(todo_text))
    for e in entries:
        s = e.status
        # L3 status vocabulary
        if s is None:
            v.append(f"L3 STATUS    {where(e)} has no Status")
            continue
        if s not in VOCAB:
            v.append(f"L3 STATUS    {where(e)} status {s!r} not in {sorted(VOCAB)}")
            continue
        text = FORMER_RE.sub("", e.body + e.title)
        cited_tests = set(TEST_NAME_RE.findall(text))
        good = {t for t in cited_tests if test_ref_resolves(t, funcs, modules)}
        paths_ok, paths_bad = cited_paths(e.body)
        # L4 proof exists, and no cited test or file pointer has rotted
        for t in sorted(cited_tests - good):
            v.append(f"L4 PROOF     {where(e)} cites {t}, which no test defines")
        for p in sorted(paths_bad):
            v.append(f"L4 PROOF     {where(e)} cites {p}, which does not exist")
        if (s in DONE_STATUSES and not good and not paths_ok
                and not DOC_PROOF_RE.search(e.body)):
            v.append(f"L4 PROOF     {where(e)} is {s} but cites no existing test, spec or path proof")
        # L5 no open wound behind a closed label
        if s in DONE_STATUSES:
            field_m = RESIDUAL_FIELD_RE.search(e.body)
            if field_m:
                val = field_m.group(1).strip()
                named = [i for i in ID_RE.findall(val) if not FAMILY_RE.match(i)]
                if not val.lower().startswith("none") and not any(i in by_id for i in named):
                    v.append(f"L5 NO-WOUND  {where(e)} Residual must be 'none — <why>' or "
                             f"name a ledger ID; got {val[:60]!r}")
                elif val.lower().startswith("none") and len(val) < 12:
                    v.append(f"L5 NO-WOUND  {where(e)} 'Residual: none' needs a reason")
            elif e.file == LIVE:
                v.append(f"L5 NO-WOUND  {where(e)} is {s} in the live ledger but declares no Residual")
            elif RESIDUAL_RE.search(e.body):
                live_links = [r for r in e.refs if r in by_id and by_id[r].status in LIVE_STATUSES]
                if not live_links:
                    m = RESIDUAL_RE.search(e.body)
                    v.append(f"L5 NO-WOUND  {where(e)} is {s} but mentions '{m.group(0)}' without "
                             f"a Residual field or a link to a live ledger ID that owns it")
        # L6 open/raised must be on the worklist
        if s in ("open", "raised") and not (set(e.ids) & todo_ids):
            v.append(f"L6 ANCHORED  {where(e)} is {s} but TODO.md never references it")
        # L7 nothing live buried in the archive
        if e.file == ARCHIVE and s in LIVE_STATUSES:
            v.append(f"L7 ARCHIVE   {where(e)} is {s} yet filed in the closed archive")
        # L8 parked items are justified
        if s in ("accepted-risk", "mitigated") and not re.search(r"Justification\**\s*:\s*\S", e.body):
            v.append(f"L8 PARKED    {where(e)} is {s} with no Justification")

    # L9 stale unchecked TODO items
    for n, line in enumerate(todo_text.splitlines(), 1):
        if re.match(r"\s*- \[ \]", line):
            ids = [i for i in ID_RE.findall(line) if i in by_id]
            if ids and all(by_id[i].status in DONE_STATUSES for i in ids):
                v.append(f"L9 STALE     TODO.md:{n} unchecked but all its IDs are closed: {', '.join(ids)}")
    return v, entries


def summary(entries: list[Entry]) -> str:
    groups = {"raised": "OWNER DECISIONS PENDING", "open": "OPEN WORK",
              "mitigated": "MITIGATED (residual tracked)", "accepted-risk": "ACCEPTED RISK"}
    out = ["ACIS ledger digest (scripts/ledger_check.py --summary)"]
    for s, label in groups.items():
        items = [e for e in entries if e.status == s]
        if not items:
            continue
        out.append(f"\n{label} ({len(items)}):")
        for e in items:
            out.append(f"  {'/'.join(e.ids):<28} {e.title.split(':', 1)[-1].strip()[:100]}")
    out.append("\nLEDGER CLOSURE LAW (CLAUDE.md): anything found, suggested or decided this session "
               "that is not finished must be written to KNOWN_GAPS.md (with an ID) or TODO.md "
               "BEFORE the session ends — chat is not a record. Closing an entry needs a "
               "`Residual:` line. `python scripts/ledger_check.py` must pass (it runs in CI).")
    return "\n".join(out)


def main() -> int:
    # a hook captures stdout through a pipe, where Windows Python defaults to cp1252 and
    # dies on the first "√" or "—" in a ledger title — the digest must never crash
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--summary", action="store_true", help="print the live-item digest")
    a = ap.parse_args()
    violations, entries = check()
    if a.summary:
        print(summary(entries))
        if violations:
            print(f"\n!! {len(violations)} ledger-closure violation(s) — run scripts/ledger_check.py")
        return 0
    for line in violations:
        print(line)
    print(f"{len(entries)} entries checked; {len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
