"""The look register (GAP-P12D-64; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md §5.2-§5.5).

Every re-scoring of a changed pipeline against the same history is another trial, and the
uncounted ones are the false-positive channel: keeping the best of 5 uncounted revisions passes
pure noise 9-19% of the time, the best of 20 21-37% (§5.2). So every grade is a LOOK, and its
line is written BEFORE the grade runs. Complete by construction, not by caller diligence
(dual audit GAP-P12D-83, HIGH-1 / X4):

  * ONE register for real data. A look whose data tier is > 0 must live in `CANONICAL`;
    `begin_grade` refuses any other location. Synthetic (tier 0) looks, unlimited by protocol,
    may live in a run's own directory.
  * The tier is derived from the source OBJECT the grade reads: its class declares
    `provenance` ("real" / "synthetic"), its key must equal its `name`, and a source that
    declares neither is REFUSED, never tier 0. Real data is tiered by its test windows:
    1 exploration (before 2012), 2 validation (2012-2023), 3 holdout (2024-25),
    4 forward (from `FORWARD_START`, the generating model's knowledge cutoff; GAP-P12D-66).
  * Append-only hash chain: line N is <register>/<N:06d>.json and carries `prev_hash`, the
    sha256 of line N-1's bytes. Lines are written to a temp file, fsynced, then hard-linked
    into place (exclusive and atomic): a claimed number is never half-written or overwritten.
    A missing number, an edited or inserted line, or a grade marker whose line is gone breaks
    the chain, and a broken register refuses every registration and grade (fail closed).
    A torn line (unparseable bytes) is REPORTED and counted, never fatal, never JSONDecodeError.
  * One line is one grade: `begin_grade` consumes the line (<N>.graded.json, exclusive), after
    re-checking the source, run properties, chain and — for real data — the git commit on a
    clean tracked tree. `record_outcome` writes the grade's Sharpe, trade count, pass fields and
    per-trade returns (<N>.outcome.json), so the DSR/PBO trial variance can be derived.
  * A real re-look by a family must say what changed; a concurrent registration that loses the
    number re-reads the register first, so "first look" is unambiguous.
  * Counting only. Nothing here reads a threshold or touches a gate.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import subprocess
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from config.schemas import AcisConfig
from tests.backtest.oos_plan import DATA_START, HOLDOUT_END, HOLDOUT_START
from tests.backtest.walk_forward import Fold

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "data" / "validation" / "looks"
FORWARD_START = datetime(2026, 7, 1, tzinfo=timezone.utc)   # after the June-2026 model cutoff (X9)
TIER_NAMES = ("synthetic", "exploration", "validation", "holdout", "forward")
GENESIS = "0" * 64
TORN = "(torn line)"
# (from, to, tier): real test windows. 2026-01..06 is pre-cutoff history the models may have
# seen, so it is exploration, never "forward" (X9, GAP-P12D-66).
_WINDOWS = ((None, DATA_START, 1), (DATA_START, HOLDOUT_START, 2), (HOLDOUT_START, HOLDOUT_END, 3),
            (HOLDOUT_END, FORWARD_START, 1), (FORWARD_START, None, 4))


class LookRefused(Exception):
    """A grade without its registered look, or a look that cannot be registered honestly."""


@dataclass(frozen=True)
class Look:
    look_id: str
    path: str
    registered_utc: str
    git_commit: str
    git_dirty: bool
    config_hash: str
    family: str
    tier: int
    tier_name: str
    source: str
    source_class: str
    instruments: tuple[str, ...]
    start: str                       # the first fold's train start
    end: str                         # the last fold's test end
    account: str
    cost_stress: float
    spread_floor: float
    changed: str
    previous: tuple[str, str, str] | None     # the family's previous look: (id, commit, config hash)
    operator: str
    prev_hash: str                   # sha256 of the previous line's bytes (GENESIS for the first)


def config_hash(cfg: AcisConfig) -> str:
    return hashlib.sha256(json.dumps(cfg.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def git_state(repo: Path = REPO) -> tuple[str, bool]:
    """(HEAD, tracked files changed?) — untracked files do not count; ("unknown", True) on failure."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo,
                               capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True
    return head.stdout.strip(), bool(dirty.stdout.strip())


def data_tier(src: object, folds: Sequence[Fold]) -> int:
    provenance = getattr(src, "provenance", None)
    if provenance == "synthetic":
        return 0
    if provenance != "real":
        raise LookRefused(f"source {getattr(src, 'name', src)!r} ({type(src).__qualname__}) declares no "
                          "provenance: it cannot be graded, and it is never tier 0")
    tiers = set()
    for f in folds:
        tier = next((t for lo, hi, t in _WINDOWS if (lo is None or lo <= f.test_start)
                     and (hi is None or f.test_end <= hi)), None)
        if tier is None:
            raise LookRefused(f"the test window {f.test_start.date()} -> {f.test_end.date()} straddles two data tiers")
        tiers.add(tier)
    if len(tiers) != 1:
        raise LookRefused(f"one look grades one data tier; these folds span {sorted(TIER_NAMES[t] for t in tiers)}")
    return tiers.pop()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    """Exclusive and atomic: the bytes are complete and fsynced before the name exists."""
    tmp = path.parent / f".tmp-{uuid.uuid4().hex}"
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(tmp, path)                       # FileExistsError if the name is taken
    finally:
        tmp.unlink()


@dataclass(frozen=True)
class Scan:
    lines: tuple[dict | None, ...]   # parsed lines in order; None = torn
    head: str                        # the chain head: sha256 of the last line's bytes
    broken: tuple[str, ...]          # tamper evidence: fail closed
    torn: tuple[str, ...]            # unparseable lines: reported and counted

    @property
    def next_seq(self) -> int:
        return len(self.lines) + 1


class LookRegister:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def scan(self) -> Scan:
        files = sorted(self.root.glob("[0-9]" * 6 + ".json")) if self.root.exists() else []
        lines, broken, torn, head = [], [], [], GENESIS
        for k, p in enumerate(files, start=1):
            data = p.read_bytes()
            if p.stem != f"{k:06d}":
                broken.append(f"line {k:06d} is missing (found {p.name}): a line was deleted")
            try:
                line = json.loads(data)
                if not isinstance(line, dict) or "prev_hash" not in line:
                    raise ValueError("not a look line")
            except ValueError:
                line = None
                torn.append(p.name)
            if line is not None and line["prev_hash"] != head:
                broken.append(f"{p.name} does not chain to the line before it: a line was deleted, edited or inserted")
            lines.append(line)
            head = _sha(data)
        for marker in self.root.glob("[0-9]" * 6 + ".*.json") if self.root.exists() else ():
            if int(marker.name[:6]) > len(files):
                broken.append(f"{marker.name} has no look line: its line was deleted")
        return Scan(tuple(lines), head, tuple(broken), tuple(torn))

    def looks(self) -> list[dict]:
        return [x for x in self.scan().lines if x is not None]

    def family_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, Counter] = {}
        for line in self.scan().lines:
            family, tier = (line["family"], line["tier_name"]) if line else (TORN, "unknown")
            counts.setdefault(family, Counter())[tier] += 1
        return {f: dict(sorted(c.items())) for f, c in sorted(counts.items())}

    def register(self, *, cfg: AcisConfig, source: object, instruments: Sequence[str], folds: Sequence[Fold],
                 family: str, account: str, changed: str = "", operator: str | None = None,
                 cost_stress: float = 1.0, spread_floor: float = 0.0,
                 git: tuple[str, bool] | None = None) -> Look:
        if not family.strip():
            raise LookRefused("a look must name its hypothesis family")
        tier = data_tier(source, folds)
        if tier > 0 and self.root.resolve() != CANONICAL.resolve():
            raise LookRefused(f"a {TIER_NAMES[tier]} look must be registered in {CANONICAL}, not {self.root}")
        commit, dirty = git if git is not None else git_state()
        if tier > 0 and (dirty or commit == "unknown"):
            raise LookRefused("a real-data look needs a clean tracked tree at a known commit: commit first")
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            scan = self.scan()
            if scan.broken:
                raise LookRefused("the look register is broken, refusing to add to it: " + "; ".join(scan.broken))
            prior = [x for x in scan.lines if x is not None and x["family"] == family]
            previous = (prior[-1]["look_id"], prior[-1]["git_commit"], prior[-1]["config_hash"]) if prior else None
            if tier > 0 and previous is not None and not changed.strip():
                raise LookRefused(f"family {family!r} last looked at {previous[0]}: say what changed since")
            fold_span = (min(f.train_start for f in folds).isoformat(), max(f.test_end for f in folds).isoformat())
            path = self.root / f"{scan.next_seq:06d}.json"
            look = Look(look_id=path.stem, path=str(path), registered_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        git_commit=commit, git_dirty=dirty, config_hash=config_hash(cfg), family=family, tier=tier,
                        tier_name=TIER_NAMES[tier], source=source.name, source_class=type(source).__qualname__,
                        instruments=tuple(sorted(instruments)), start=fold_span[0], end=fold_span[1], account=account,
                        cost_stress=float(cost_stress), spread_floor=float(spread_floor),
                        changed=changed.strip() or ("first look" if previous is None else ""),
                        previous=previous, operator=operator or getpass.getuser(), prev_hash=scan.head)
            try:
                _write_new(path, json.dumps(asdict(look), sort_keys=True).encode("utf-8"))
                return look
            except FileExistsError:
                continue                                     # another registrant won: re-read, re-decide

    def consume(self, look: Look) -> None:
        try:
            _write_new(self.root / f"{look.look_id}.graded.json",
                       json.dumps({"graded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}).encode())
        except FileExistsError:
            raise LookRefused(f"look {look.look_id} was already graded: one line is one grade") from None

    def record_outcome(self, look: Look, outcome: dict) -> None:
        _write_new(self.root / f"{look.look_id}.outcome.json",
                   json.dumps(outcome, sort_keys=True, allow_nan=False).encode("utf-8"))

    def summary(self) -> dict:
        """What a report carries: per-family and per-tier counts (a renamed family still adds to
        its tier's total), the chain head (an anchor outside the register), torn lines."""
        scan = self.scan()
        tiers = Counter(x["tier_name"] if x else "unknown" for x in scan.lines)
        return {"family_looks": self.family_counts(), "tier_totals": dict(sorted(tiers.items())),
                "chain_head": scan.head, "torn_lines": list(scan.torn)}


def begin_grade(look: object, *, cfg: AcisConfig, loader, source: str, instruments: Sequence[str],
                folds: Sequence[Fold], account: str, cost_stress: float, spread_floor: float) -> dict:
    """Everything a grade must prove BEFORE any compute; then it consumes the line."""
    if not isinstance(look, Look):
        raise LookRefused("no registered look: a grade must write its look-register line first (GAP-P12D-64)")
    src = loader.source_object(source)
    if getattr(src, "name", None) != source:
        raise LookRefused(f"the loader key {source!r} names a source whose own name is {getattr(src, 'name', None)!r}")
    tier = data_tier(src, folds)
    register = LookRegister(Path(look.path).parent)
    if tier > 0 and register.root.resolve() != CANONICAL.resolve():
        raise LookRefused(f"a {TIER_NAMES[tier]} grade needs its look in {CANONICAL}, not {register.root}")
    scan = register.scan()
    if scan.broken:
        raise LookRefused("the look register is broken: " + "; ".join(scan.broken))
    on_disk = scan.lines[int(look.look_id) - 1] if 0 < int(look.look_id) <= len(scan.lines) else None
    if on_disk != json.loads(json.dumps(asdict(look))):
        raise LookRefused(f"look {look.look_id} is not on disk as registered ({look.path})")
    run = (source, type(src).__qualname__, tuple(sorted(instruments)), min(f.train_start for f in folds).isoformat(),
           max(f.test_end for f in folds).isoformat(), config_hash(cfg), tier, account, float(cost_stress),
           float(spread_floor))
    registered = (look.source, look.source_class, look.instruments, look.start, look.end, look.config_hash,
                  look.tier, look.account, look.cost_stress, look.spread_floor)
    if registered != run:
        raise LookRefused(f"look {look.look_id} was registered for another run: {registered} != {run}")
    if tier > 0:
        commit, dirty = git_state()
        if dirty or commit != look.git_commit:
            raise LookRefused(f"look {look.look_id} was registered at {look.git_commit}; the tree is now "
                              f"{commit}{' (dirty)' if dirty else ''}: the line would not pin the code that grades")
    register.consume(look)
    return register.summary()
