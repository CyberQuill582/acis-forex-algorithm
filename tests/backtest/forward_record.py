"""The tournament's forward record (TOURNAMENT, 2026-10-04): each registered strategy's forward daily net
returns in one append-only, hash-chained ledger, the evidence ACIS-09 C-BT-11 v2 stage D reads.

Mental model:
  * One line per file, <root>/<seq:06d>.json, chained like the look register (exclusive, fsynced, atomic
    writes; `prev_hash` = sha256 of the previous line's bytes). A deleted, edited or inserted line breaks
    the chain, and a broken record refuses every append (fail closed). Nothing is ever rewritten.
  * KINDS: `rule` (the pre-registered promotion rule; replaceable only before the first day), `entry`
    (a strategy's frozen declaration), `days` (rows of one strategy's settled days), `revision` (a
    recompute that differs from a recorded day: context only, the recorded value stands), `retire`.
  * An ENTRY is admitted only if its first exposure comes after the line is written, its forward start
    is on or after its certifying boundary (§5.6), the tournament's capacity has room and its alpha fits
    the unspent budget; alpha spent by a retired entry is never recycled.
  * DAYS are admitted only for a registered, unretired strategy, strictly after its last recorded day,
    on or after its forward start, and on or before the settled horizon, which must lie before the day
    the line is written: no history before a strategy's forward start can enter, and no day twice.
  * The chain head leaves the machine on its own branch (`forward-anchor`) through `look_anchor`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from tests.backtest.look_anchor import anchor as _anchor, anchored as _anchored
from tests.backtest.look_claims import HEX64, canonical_hash
from tests.backtest.look_register import GENESIS, Scan, _sha, _write_new

KINDS = ("rule", "entry", "days", "revision", "retire")
BRANCH, FILE = "forward-anchor", "FORWARD_ANCHOR.txt"
ENTRY_FIELDS = ("strategy", "family", "variant_hash", "clock", "instruments", "formula", "origin",
                "certifying_boundary", "forward_start", "first_exposure_utc", "sigma_daily", "sharpe_dev",
                "alpha", "spec_hash")


class RecordRefused(Exception):
    """A line the forward record cannot admit honestly."""


@dataclass
class State:
    rule: dict | None = None
    entries: dict[str, dict] = field(default_factory=dict)
    days: dict[str, list[tuple[date, float]]] = field(default_factory=dict)
    retired: dict[str, str] = field(default_factory=dict)
    last_written: datetime | None = None
    any_days: bool = False


def _utc(s: str) -> datetime:
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        raise ValueError(f"{s!r} carries no time zone")
    return t.astimezone(timezone.utc)


def fold(lines) -> State:
    """The record's meaning, from its parsed lines in order (a torn line contributes nothing)."""
    st = State()
    for x in lines:
        if x is None:
            continue
        st.last_written = _utc(x["written_utc"])
        kind = x["kind"]
        if kind == "rule":
            st.rule = x
        elif kind == "entry":
            st.entries[x["strategy"]], st.days[x["strategy"]] = x, []
        elif kind == "days":
            st.days[x["strategy"]] += [(date.fromisoformat(d), float(v)) for d, v in x["rows"]]
            st.any_days = True
        elif kind == "retire":
            st.retired[x["strategy"]] = x["reason"]
    return st


def _admit_entry(x: dict, st: State, now: datetime) -> None:
    if st.rule is None:
        raise RecordRefused("the promotion rule is registered before any entry")
    if missing := [k for k in ENTRY_FIELDS if k not in x]:
        raise RecordRefused(f"an entry declares {missing}")
    if x["strategy"] in st.entries:
        raise RecordRefused(f"{x['strategy']!r} is already registered: an entry is never re-declared")
    start, boundary = date.fromisoformat(x["forward_start"]), x["certifying_boundary"]
    if boundary is not None and start < date.fromisoformat(boundary):
        raise RecordRefused(f"forward start {start} precedes the certifying boundary {boundary} (§5.6)")
    if _utc(x["first_exposure_utc"]) <= now:
        raise RecordRefused(f"{x['strategy']}'s first exposure {x['first_exposure_utc']} is not after its "
                            "registration: a forward record never starts in the past")
    p = st.rule["params"]
    spent = sum(float(e["alpha"]) for e in st.entries.values())
    if len(st.entries) >= p["capacity"]:
        raise RecordRefused(f"the tournament's capacity of {p['capacity']} entries is used")
    if not (0 < float(x["alpha"]) and spent + float(x["alpha"]) <= p["alpha_total"] + 1e-12):
        raise RecordRefused(f"alpha {x['alpha']} does not fit the unspent {p['alpha_total'] - spent:.6g}")
    if not (math.isfinite(float(x["sigma_daily"])) and float(x["sigma_daily"]) > 0) or not HEX64.fullmatch(x["spec_hash"]):
        raise RecordRefused("an entry declares sigma_daily > 0 and a 64-hex spec hash")


def _admit_days(x: dict, st: State, now: datetime) -> None:
    sid = x.get("strategy")
    if sid not in st.entries or sid in st.retired:
        raise RecordRefused(f"{sid!r} is not a registered, active strategy")
    horizon = date.fromisoformat(x["horizon"])
    if horizon >= now.date():
        raise RecordRefused(f"the horizon {horizon} is not before the day the line is written")
    rows = x["rows"]
    if not rows:
        raise RecordRefused("a days line carries at least one row")
    last = st.days[sid][-1][0] if st.days[sid] else None
    first = date.fromisoformat(st.entries[sid]["forward_start"])
    for d, v in rows:
        d = date.fromisoformat(d)
        if d < first:
            raise RecordRefused(f"{sid} {d} precedes its forward start {first}: no backfill")
        if last is not None and d <= last:
            raise RecordRefused(f"{sid} {d} is not after its last recorded day {last}: no day twice")
        if d > horizon:
            raise RecordRefused(f"{sid} {d} lies beyond the settled horizon {horizon}")
        if not (isinstance(v, (int, float)) and math.isfinite(v)):
            raise RecordRefused(f"{sid} {d}: a net return is a finite number")
        last = d
    if not HEX64.fullmatch(x.get("inputs", "")):
        raise RecordRefused("a days line names the input store's 64-hex state")


def admit(x: dict, st: State, now: datetime) -> None:
    if x.get("kind") not in KINDS:
        raise RecordRefused(f"kind must be one of {KINDS}")
    if st.last_written is not None and now < st.last_written:
        raise RecordRefused(f"the clock reads {now.isoformat()}, before the last line's: fix the clock")
    kind = x["kind"]
    if kind == "rule":
        if st.any_days:
            raise RecordRefused("the promotion rule is frozen once the first day is recorded")
        if x.get("rule_hash") != canonical_hash(x.get("params")):
            raise RecordRefused("the rule's hash is not the hash of its parameters")
    elif kind == "entry":
        _admit_entry(x, st, now)
    elif kind == "days":
        _admit_days(x, st, now)
    elif kind == "revision":
        rows = st.days.get(x.get("strategy"), [])
        d = date.fromisoformat(x["date"])
        recorded = dict(rows).get(d)
        omitted = recorded is None and x.get("recorded") is None and rows and rows[0][0] < d < rows[-1][0]
        if not omitted and (recorded is None or recorded != x.get("recorded")):
            raise RecordRefused("a revision names a recorded day and its recorded value, or a day the record skipped")
    elif x.get("strategy") not in st.entries or x["strategy"] in st.retired or not x.get("reason", "").strip():
        raise RecordRefused("a retirement names an active strategy and its reason")


class ForwardRecord:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def scan(self) -> Scan:
        files = sorted(self.root.glob("[0-9]" * 6 + ".json")) if self.root.exists() else []
        lines, broken, torn, head, heads = [], [], [], GENESIS, []
        for k, p in enumerate(files, start=1):
            data = p.read_bytes()
            if p.stem != f"{k:06d}":
                broken.append(f"line {k:06d} is missing (found {p.name}): a line was deleted")
            try:
                line = json.loads(data)
                if not isinstance(line, dict) or "prev_hash" not in line or line.get("kind") not in KINDS:
                    raise ValueError("not a record line")
            except ValueError:
                line = None
                torn.append(p.name)
            if line is not None and line["prev_hash"] != head:
                broken.append(f"{p.name} does not chain to the line before it: deleted, edited or inserted")
            lines.append(line)
            head = _sha(data)
            heads.append(head)
        return Scan(tuple(lines), head, tuple(broken), tuple(torn), tuple(heads))

    def state(self) -> State:
        return fold(self.scan().lines)

    def append(self, line: dict, now: datetime | None = None) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            scan = self.scan()
            if scan.broken or scan.torn:
                raise RecordRefused("the forward record is broken, refusing to add to it: "
                                    + "; ".join(scan.broken + scan.torn))
            t = now or datetime.now(timezone.utc)
            admit(line, fold(scan.lines), t)
            out = {**line, "written_utc": t.isoformat(timespec="seconds"), "prev_hash": scan.head}
            try:
                _write_new(self.root / f"{scan.next_seq:06d}.json",
                           json.dumps(out, sort_keys=True, allow_nan=False).encode("utf-8"))
                return out
            except FileExistsError:
                continue                                  # another writer won: re-read, re-decide

    def anchor(self, repo: Path, remote: str = "origin") -> str:
        return _anchor(self, repo, remote, branch=BRANCH, file=FILE)

    def anchored(self, repo: Path, remote: str = "origin") -> bool:
        return _anchored(self, repo, remote, branch=BRANCH, file=FILE)
