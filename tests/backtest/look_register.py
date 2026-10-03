"""The look register (GAP-P12D-64; archive/RESEARCH_VALIDATION_FIREWALL_2026-09-24.md §5.2-§5.5).

Every re-scoring of a changed pipeline against the same history is another trial, and the
uncounted ones are the false-positive channel: keeping the best of 5 uncounted revisions passes
pure noise 9-19% of the time, the best of 20 21-37% (§5.2). So every grade is a LOOK, and its
line is written BEFORE the grade runs. Complete by construction, not by caller diligence
(dual audit GAP-P12D-83, HIGH-1 / X4):

  * ONE register for real data. A look whose data tier is > 0 must live in `CANONICAL`;
    `look_gate.begin_grade` refuses any other location. Synthetic (tier 0) looks, unlimited by protocol,
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
  * One line is one grade: `look_gate.begin_grade` consumes the line (<N>.graded.json, exclusive), after
    re-checking the source, run properties, chain and — for real data — the git commit on a
    clean tracked tree. `record_outcome` writes the grade's Sharpe, trade count, pass fields and
    per-trade returns (<N>.outcome.json), so the DSR/PBO trial variance can be derived.
  * A real re-look by a family must say what changed; a concurrent registration that loses the
    number re-reads the register first, so "first look" is unambiguous. Counting only: nothing
    here reads a threshold or touches a gate.
  * v2 (R1.2, look_claims): a real-data look carries its CLAIM (declared-space hash, variant,
    origin + model cutoff, cost map, universe, simulator, recon_commit); a cycle's testing order is
    a `kind: cycle` line in the same chain; an outcome may store its daily return vector.
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
from typing import Callable, Sequence

from config.schemas import AcisConfig
import tests.backtest.look_claims as lc
import tests.backtest.look_anchor as look_anchor
import tests.backtest.look_outcomes as look_outcomes
from tests.backtest.look_claims import Claim, cost_map_hash, cycle_line
from tests.backtest.look_cycles import is_stage_a, stage_a_cycle
from tests.backtest.look_tiers import FORWARD_START, TIER_NAMES, TierRefused  # noqa: F401 (re-export)
from tests.backtest.look_tiers import data_tier as _data_tier
from tests.backtest.walk_forward import Fold

REPO = Path(__file__).resolve().parents[2]
CANONICAL = REPO / "data" / "validation" / "looks"
GENESIS = "0" * 64
TORN = "(torn line)"
KINDS = ("look", "cycle", "outcome")


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
    kind: str = "look"               # every line is a look or a cycle row (R1.2)
    claim: dict | None = None        # the registered family-version (look_claims.Claim.line)
    cycle: dict | None = None        # a stage-A look's {cycle_id, look_index} (look_cycles, R12I-04)


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
    try:
        return _data_tier(src, folds)
    except TierRefused as exc:
        raise LookRefused(str(exc)) from None


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
        lines, broken, torn, head, looked = [], [], [], GENESIS, set()
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
            if line is not None and line.get("kind", "look") not in KINDS:
                broken.append(f"{p.name} is a {line.get('kind')!r} line this register cannot read: fail closed")
            if line is not None and line.get("kind") == "outcome" and line.get("look_id") not in looked:
                broken.append(f"{p.name} is the outcome of {line.get('look_id')!r}, no earlier look line")
            looked |= {p.stem} if line is not None and line.get("kind", "look") == "look" else set()
            if line is not None and line["prev_hash"] != head:
                broken.append(f"{p.name} does not chain to the line before it: a line was deleted, edited or inserted")
            lines.append(line)
            head = _sha(data)
        for marker in self.root.glob("[0-9]" * 6 + ".*.json") if self.root.exists() else ():
            if int(marker.name[:6]) > len(files):
                broken.append(f"{marker.name} has no look line: its line was deleted")
        return Scan(tuple(lines), head, tuple(broken), tuple(torn))

    def looks(self) -> list[dict]:
        return [x for x in self.scan().lines if x is not None and x.get("kind", "look") == "look"]

    def family_counts(self) -> dict[str, dict[str, int]]:
        counts: dict[str, Counter] = {}
        for line in self.scan().lines:
            if line is not None and line.get("kind", "look") != "look":
                continue
            family, tier = (line["family"], line["tier_name"]) if line else (TORN, "unknown")
            counts.setdefault(family, Counter())[tier] += 1
        return {f: dict(sorted(c.items())) for f, c in sorted(counts.items())}

    def _append(self, build: Callable[[Scan, Path], "Look | dict"]) -> "Look | dict":
        """Write build(scan, path) as the next line: exclusive, re-deciding if another writer wins."""
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            scan = self.scan()
            if scan.broken:
                raise LookRefused("the look register is broken, refusing to add to it: " + "; ".join(scan.broken))
            path = self.root / f"{scan.next_seq:06d}.json"
            line = build(scan, path)
            try:
                _write_new(path, json.dumps(asdict(line) if isinstance(line, Look) else line,
                                            sort_keys=True).encode("utf-8"))
                if self.root.resolve() == CANONICAL.resolve():
                    look_anchor.anchor(self, REPO)      # GAP-P12D-86: every canonical line leaves the machine
                return line
            except FileExistsError:
                continue                                     # another registrant won: re-read, re-decide

    def register(self, *, cfg: AcisConfig, source: object, instruments: Sequence[str], folds: Sequence[Fold],
                 family: str, account: str, changed: str = "", operator: str | None = None,
                 cost_stress: float = 1.0, spread_floor: float = 0.0,
                 git: tuple[str, bool] | None = None, claim: Claim | None = None) -> Look:
        if not family.strip():
            raise LookRefused("a look must name its hypothesis family")
        tier = data_tier(source, folds)
        if tier > 0 and not lc.REAL_LOOKS_OPEN:
            raise LookRefused("real-data looks are closed until R1.4 lands with the register's recording "
                              "fixes (GAP-P12D-127; R-1: no real-data look before R1.1-R1.4 are green)")
        if tier > 0 and self.root.resolve() != CANONICAL.resolve():
            raise LookRefused(f"a {TIER_NAMES[tier]} look must be registered in {CANONICAL}, not {self.root}")
        if tier > 0 and claim is None:
            raise LookRefused("a real-data look carries its claim: declared space, origin, cost map, universe "
                              "(ACIS-09 C-BT-11 v2 step 1, GAP-P12D-98)")
        if claim is not None and claim.family != family:
            raise LookRefused(f"the claim is family {claim.family!r}'s, not {family!r}'s")
        commit, dirty = git if git is not None else git_state()
        if tier > 0 and (dirty or commit == "unknown"):
            raise LookRefused("a real-data look needs a clean tracked tree at a known commit: commit first")
        claimed = claim.line(cost_map_hash(cfg, instruments, cost_stress, spread_floor)) if claim else None

        def build(scan: Scan, path: Path) -> Look:
            looks = [x for x in scan.lines if x is not None and x.get("kind", "look") == "look"]
            now = datetime.now(timezone.utc)
            try:
                lc.refuse_backwards_clock(scan.lines, now)
                if claim is not None:
                    lc.admit_claim(claim, instruments, scan.lines, tier)
                cycle = stage_a_cycle(claim.variant_hash, scan.lines) if claim and is_stage_a(tier, claim.simulator) else None
            except ValueError as e:
                raise LookRefused(str(e)) from None
            prior = [x for x in looks if x["family"] == family]
            previous = (prior[-1]["look_id"], prior[-1]["git_commit"], prior[-1]["config_hash"]) if prior else None
            if tier > 0 and previous is not None and not changed.strip():
                raise LookRefused(f"family {family!r} last looked at {previous[0]}: say what changed since")
            span = (min(f.train_start for f in folds).isoformat(), max(f.test_end for f in folds).isoformat())
            return Look(look_id=path.stem, path=str(path), registered_utc=now.isoformat(timespec="seconds"),
                        git_commit=commit, git_dirty=dirty, config_hash=config_hash(cfg), family=family, tier=tier,
                        tier_name=TIER_NAMES[tier], source=source.name, source_class=type(source).__qualname__,
                        instruments=tuple(sorted(instruments)), start=span[0], end=span[1], account=account,
                        cost_stress=float(cost_stress), spread_floor=float(spread_floor),
                        changed=changed.strip() or ("first look" if previous is None else ""),
                        previous=previous, operator=operator or getpass.getuser(), prev_hash=scan.head, claim=claimed,
                        cycle=cycle)
        return self._append(build)

    def register_cycle(self, *, cycle_id: str, order: Sequence[str], alpha: float | None = None,
                       operator: str | None = None, now_fn=lambda: datetime.now(timezone.utc),
                       holm: Sequence[str] = ()) -> dict:
        """A cycle's testing order (variant hashes), before any real look of its members; its alpha
        is the spending schedule's (a given alpha must equal it)."""
        def build(scan: Scan, path: Path) -> dict:
            now = now_fn()
            try:
                line = cycle_line(cycle_id=cycle_id, order=order, alpha=alpha, lines=scan.lines, now=now,
                                  holm=holm)
            except ValueError as e:
                raise LookRefused(str(e)) from None
            return {**line, "look_id": path.stem, "registered_utc": now.isoformat(timespec="seconds"),
                    "operator": operator or getpass.getuser(), "prev_hash": scan.head}
        return self._append(build)

    def consume(self, look: Look) -> None:
        try:
            _write_new(self.root / f"{look.look_id}.graded.json",
                       json.dumps({"graded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}).encode())
        except FileExistsError:
            raise LookRefused(f"look {look.look_id} was already graded: one line is one grade") from None

    def record_outcome(self, look: Look, outcome: dict, daily: tuple[Sequence, Sequence[float]] | None = None) -> None:
        """The grade's outcome; `daily` = (dates, portfolio net returns), stored by its hash. Only for
        a look of THIS register whose line is on disk as written and that was graded (R12I-08)."""
        look_outcomes.record(self, look, outcome, daily)          # a chained line (look_outcomes.py)

    def outcome(self, look_id: str) -> dict | None:
        return look_outcomes.read(self.scan().lines, look_id)

    def summary(self) -> dict:
        """What a report carries: per-family and per-tier counts (a renamed family still adds to
        its tier's total), the chain head (an anchor outside the register), torn lines."""
        scan = self.scan()
        tiers = Counter(x["tier_name"] if x else "unknown" for x in scan.lines if not x or x.get("kind", "look") == "look")
        return {"family_looks": self.family_counts(), "tier_totals": dict(sorted(tiers.items())),
                "cycles": [x["cycle_id"] for x in scan.lines if x and x.get("kind") == "cycle"],
                "chain_head": scan.head, "torn_lines": list(scan.torn)}

