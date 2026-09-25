"""The look register (GAP-P12D-64; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md §5.2-§5.5).

Every re-scoring of a changed pipeline against the same history is another trial, and the
uncounted ones are the false-positive channel: keeping the best of 5 uncounted revisions passes
pure noise 9-19% of the time, the best of 20 21-37% (§5.2). So every grade is a LOOK, and its
line is written BEFORE the grade runs.

Invariants:
  * Append-only, one file per look: <register>/<seq:06d>.json, created exclusively (open "x"),
    the `oos_plan.HoldoutGuard.begin_final` pattern. Creating the file claims the number, so
    two runs cannot share one and no look is overwritten. No code path deletes a look.
  * `oos_runner.run_walk_forward` refuses to grade without a `Look` that is on disk,
    byte-for-byte as registered, for THIS run: the same source, instruments, fold span and
    config hash. A hand-built Look, or one registered for another run, is refused.
  * The data tier is DERIVED, never claimed. A source that is not a declared real source
    (sources.py) is tier 0, synthetic. Real data is tiered by its graded test windows:
    1 exploration (before 2012), 2 validation (2012-2023), 3 holdout (2024-2025),
    4 forward (2026 on). Test windows that straddle two tiers are refused.
  * A real-data look by a family that has looked before must say what changed since; its line
    names the previous look (id, commit, config hash) so the change can be checked.
  * Counting only. Nothing here reads a threshold or touches a gate: the owner-ratified
    Deflated Sharpe / `passed` gate is unchanged (raising it per look is option C, GAP-P12D-33).
"""

from __future__ import annotations

import getpass
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from config.schemas import AcisConfig
from tests.backtest.oos_plan import DATA_START, HOLDOUT_END, HOLDOUT_START
from tests.backtest.sources import DukascopyTickSource, HistDataTickSource
from tests.backtest.walk_forward import Fold

REPO = Path(__file__).resolve().parents[2]
REAL_SOURCES = frozenset({DukascopyTickSource.name, HistDataTickSource.name})
TIER_NAMES = ("synthetic", "exploration", "validation", "holdout", "forward")


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
    instruments: tuple[str, ...]
    start: str                       # the first fold's train start
    end: str                         # the last fold's test end
    changed: str
    previous: tuple[str, str, str] | None     # the family's previous look: (id, commit, config hash)
    operator: str


def config_hash(cfg: AcisConfig) -> str:
    return hashlib.sha256(json.dumps(cfg.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def git_state(repo: Path = REPO) -> tuple[str, bool]:
    """(HEAD commit, working tree dirty?) — ("unknown", True) when git cannot say."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True
    return head.stdout.strip(), bool(dirty.stdout.strip())


def _window_tier(start: datetime, end: datetime) -> int:
    bounds = ((1, datetime.min.replace(tzinfo=timezone.utc), DATA_START), (2, DATA_START, HOLDOUT_START),
              (3, HOLDOUT_START, HOLDOUT_END), (4, HOLDOUT_END, datetime.max.replace(tzinfo=timezone.utc)))
    for tier, lo, hi in bounds:
        if lo <= start and end <= hi:
            return tier
    raise LookRefused(f"the test window {start.date()} -> {end.date()} straddles two data tiers")


def data_tier(source: str, folds: Sequence[Fold]) -> int:
    if source not in REAL_SOURCES:
        return 0
    tiers = {_window_tier(f.test_start, f.test_end) for f in folds}
    if len(tiers) != 1:
        raise LookRefused(f"one look grades one data tier; these folds span {sorted(TIER_NAMES[t] for t in tiers)}")
    return tiers.pop()


def _span(folds: Sequence[Fold]) -> tuple[str, str]:
    return min(f.train_start for f in folds).isoformat(), max(f.test_end for f in folds).isoformat()


class LookRegister:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def looks(self) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("[0-9]*.json"))]

    def family_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, Counter] = {}
        for line in self.looks():
            counts.setdefault(line["family"], Counter())[line["tier_name"]] += 1
        return {f: dict(sorted(c.items())) for f, c in sorted(counts.items())}

    def register(self, *, cfg: AcisConfig, source: str, instruments: Sequence[str], folds: Sequence[Fold],
                 family: str, changed: str = "", operator: str | None = None,
                 git: tuple[str, bool] | None = None) -> Look:
        if not family.strip():
            raise LookRefused("a look must name its hypothesis family")
        tier = data_tier(source, folds)
        prior = [x for x in self.looks() if x["family"] == family]
        previous = (prior[-1]["look_id"], prior[-1]["git_commit"], prior[-1]["config_hash"]) if prior else None
        if tier > 0 and previous is not None and not changed.strip():
            raise LookRefused(f"family {family!r} last looked at {previous[0]}: say what changed since")
        commit, dirty = git if git is not None else git_state()
        start, end = _span(folds)
        self.root.mkdir(parents=True, exist_ok=True)
        seq = len(list(self.root.glob("[0-9]*.json"))) + 1
        while True:
            path = self.root / f"{seq:06d}.json"
            look = Look(look_id=f"{seq:06d}", path=str(path),
                        registered_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        git_commit=commit, git_dirty=dirty, config_hash=config_hash(cfg), family=family,
                        tier=tier, tier_name=TIER_NAMES[tier], source=source, instruments=tuple(sorted(instruments)),
                        start=start, end=end, changed=changed.strip() or ("first look" if previous is None else ""),
                        previous=previous, operator=operator or getpass.getuser())
            try:
                with path.open("x", encoding="utf-8") as f:           # the line is the claim
                    json.dump(asdict(look), f, sort_keys=True)
                return look
            except FileExistsError:
                seq += 1


def verify_look(look: object, *, cfg: AcisConfig, source: str, instruments: Sequence[str],
                folds: Sequence[Fold]) -> dict[str, dict[str, int]]:
    """Refuse a grade unless `look` is registered on disk for exactly this run. Returns the
    register's per-family look counts, for the report."""
    if not isinstance(look, Look):
        raise LookRefused("no registered look: a grade must write its look-register line first (GAP-P12D-64)")
    path = Path(look.path)
    if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != json.loads(json.dumps(asdict(look))):
        raise LookRefused(f"look {look.look_id} is not on disk as registered ({path})")
    start, end = _span(folds)
    expected = (source, tuple(sorted(instruments)), start, end, config_hash(cfg), data_tier(source, folds))
    actual = (look.source, look.instruments, look.start, look.end, look.config_hash, look.tier)
    if actual != expected:
        raise LookRefused(f"look {look.look_id} was registered for another run: {actual} != {expected}")
    return LookRegister(path.parent).family_counts()
