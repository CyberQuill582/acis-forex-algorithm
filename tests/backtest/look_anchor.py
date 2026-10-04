"""The look register's outside anchor (GAP-P12D-86; ACIS-09 C-BT-11 v2 step 1 v1.10, owner ruling
2026-09-29 "Push the chain head to GitHub (Recommended)").

    anchor(register)            # after every line appended to the canonical register
    anchored(register)          # what a real-data grade checks first

Mental model:
  * The register is a local hash chain, so deleting or editing its LAST line leaves no trace inside it.
    The cure is a commitment that leaves the machine: every appended line's chain head is appended to
    `LOOK_ANCHOR.txt` on the branch `look-anchor` and pushed to the project's GitHub remote, whose
    server-side push record is the external timestamp (Crosby & Wallach 2009).
  * The anchor commit is written with git PLUMBING (hash-object, mktree, commit-tree, update-ref with
    the old value as a compare-and-swap): HEAD, the index and the working tree never move, so a look
    registered at a commit is still graded at that commit (`look_gate.begin_grade`'s clean-tree rule).
  * `anchored` FETCHES the remote's branch first (a forced refspec, so a local ref cannot stand in for
    the remote), then requires every anchored line, in strictly rising order, to name the register's
    chain head after that line, and the last to be the current head: a head committed locally but never
    pushed, or a tail rolled back and rewritten, is not anchored and the grade is refused (GAP-P12D-159,
    PC-I-06 and PCE-01). A fetch that fails refuses too. The branch is not server-protected (GAP-P12D-86).
  * Nothing here reads a threshold or touches a gate's value; it only refuses a real-data grade whose
    register head the outside world has not seen.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

BRANCH = "look-anchor"
FILE = "LOOK_ANCHOR.txt"


class AnchorError(Exception):
    """The anchor could not be written or pushed; the register's head stays unanchored."""


def _git(repo: Path, *args: str, stdin: str | None = None, check: bool = True) -> str:
    # bytes, never text mode: Windows text mode would end stdin's lines with CR LF and corrupt the
    # tree entry's file name
    r = subprocess.run(["git", *args], cwd=repo, input=stdin.encode("utf-8") if stdin is not None else None,
                       capture_output=True)
    if check and r.returncode != 0:
        raise AnchorError(f"git {' '.join(args)} failed: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout.decode("utf-8") if r.returncode == 0 else ""


def _content(repo: Path, ref: str, file: str = FILE) -> str:
    return _git(repo, "show", f"{ref}:{file}", check=False)


def anchor(register, repo: Path, remote: str = "origin", *, branch: str = BRANCH, file: str = FILE) -> str:
    """Append the register's current head to the anchor branch and push it; return the anchor commit.
    `branch`/`file` let another chained ledger (the forward record) keep its own anchor."""
    scan = register.scan()
    if scan.broken:
        raise AnchorError("a broken register is never anchored: " + "; ".join(scan.broken))
    prev = _git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}", check=False).strip()
    old = _content(repo, f"refs/heads/{branch}", file) if prev else ""
    if old.splitlines() and old.splitlines()[-1].split()[1] == scan.head:
        commit = prev                                         # already anchored locally: push again
    else:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        blob = _git(repo, "hash-object", "-w", "--stdin", stdin=f"{old}{len(scan.lines):06d} {scan.head} {stamp}\n").strip()
        tree = _git(repo, "mktree", stdin=f"100644 blob {blob}\t{file}\n").strip()
        parent = ("-p", prev) if prev else ()
        what = "look register" if branch == BRANCH else branch
        commit = _git(repo, "commit-tree", tree, *parent, "-m", f"{what} anchor {len(scan.lines):06d}").strip()
        _git(repo, "update-ref", f"refs/heads/{branch}", commit, prev or "0" * 40)   # compare-and-swap
    _git(repo, "push", remote, f"refs/heads/{branch}:refs/heads/{branch}")
    return commit


def anchored(register, repo: Path, remote: str = "origin", *, branch: str = BRANCH, file: str = FILE) -> bool:
    """True when the remote's anchor names every anchored head in order, ending at the current head."""
    try:
        _git(repo, "fetch", "-q", remote, f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}")
    except AnchorError:
        return False
    scan = register.scan()
    rows = [line.split() for line in _content(repo, f"refs/remotes/{remote}/{branch}", file).splitlines()]
    if not rows or scan.broken:
        return False
    seqs = [int(r[0]) for r in rows]
    if any(b <= a for a, b in zip(seqs, seqs[1:])) or seqs[-1] != len(scan.heads):
        return False
    return all(scan.heads[s - 1] == r[1] for s, r in zip(seqs, rows))
