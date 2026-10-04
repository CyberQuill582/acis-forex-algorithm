"""The tournament's input store (TOURNAMENT, 2026-10-04): every forward input fetched once and frozen, so
a strategy's forward days are a pure function of what is on disk.

Mental model:
  * FILES are write-once. A re-fetch whose bytes differ is a `revision` line in manifest.jsonl (context,
    the stored file stands). A needed file still missing HOLE_AFTER_DAYS after its UTC day ended is
    declared a `hole` and read as no data from then on, even if it appears later.
  * SOURCES by period, never mixed inside one: through 2025 the archive's hourly candles (the history
    looks' own files); 2026 months before EPOCH the archive bucket's monthly hourly files; from EPOCH each
    UTC day's 1-minute BID/ASK files aggregated to hours (open of the first minute, close of the last,
    traded if any volume). On 2026-09 this matched the hourly file on ~95% of traded hours' closes, the
    rest within ~1.5 pips: a declared source departure. GOTOBI's ticks are the UTC day files from EPOCH.
  * SERIES (the S&P close, the Treasury 7-year par yield, the overnight rates) freeze per date: a run
    appends only dates after the series' frozen-through day, up to the day the caller settles; a later
    print of a frozen date is a revision line, never a change. Through 2025 the archive's files stand.
  * HORIZONS: a source is settled through its last UTC day with every needed file present, a declared
    hole, or (ticks) a minute record with no volume all day. No strategy reads past its horizon.
  * `state_hash` (manifest + series) is what a forward days line records as its inputs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from core.data.rates import CCY_SERIES, WEEKLY_SOURCES, RateTable
from tests.backtest.candle_store import Hourly, load
from tests.backtest.candles_min import decode_day
from tests.backtest.jp_days import load_holidays
from tests.backtest.look_register import _write_new
from tests.backtest.universe import BY_NAME

EPOCH = date(2026, 10, 1)
ARCHIVE_END = date(2025, 12, 31)
HOLE_AFTER_DAYS = 4
SIDES = ("BID", "ASK")
SPX, Y7 = "spx_yahoo", "ust_y7"
ECB, CPI, COT = "ecb_exr", "bis_cpi", "cot_gold"          # FACTORY's inputs: area = currency, CPI area, COT field
COT_FIELDS = ("open_interest", "commercial_long", "commercial_short")
RATE_SIDS = tuple(sorted({sid for sid, _ in CCY_SERIES.values()}))


class StoreGap(Exception):
    """A needed input is neither on disk nor a declared hole."""


def minute_rel(name: str, d: date, side: str) -> str:
    return f"minutes/{BY_NAME[name].duka}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"


def hour_rel(name: str, y: int, m: int, side: str) -> str:
    return f"hourly/{BY_NAME[name].duka}/{y}/{m - 1:02d}/{side}_candles_hour_1.bi5"


def tick_rel(name: str, d: date) -> str:
    return f"ticks/{name}/{d.year}/{d.month - 1:02d}/{d.day:02d}_ticks.bi5"


def days_between(first: date, last: date):
    d = first
    while d <= last:
        yield d
        d += timedelta(days=1)


def _aggregate(bid: np.ndarray, ask: np.ndarray) -> tuple[np.ndarray, ...]:
    """A UTC day's 1,440 minutes as 24 hours: (start, mid open, mid close, spread at the open, traded)."""
    b, a = bid.reshape(24, 60), ask.reshape(24, 60)
    return (b["ts"][:, 0].astype(np.int64), (b["open"][:, 0] + a["open"][:, 0]) / 2,
            (b["close"][:, -1] + a["close"][:, -1]) / 2, np.maximum(a["open"][:, 0] - b["open"][:, 0], 0.0),
            (b["volume"].sum(axis=1) > 0) | (a["volume"].sum(axis=1) > 0))


class InputStore:
    def __init__(self, root: Path, *, archive_candles: Path, archive_macro: Path, archive_treasury: Path,
                 holidays_csv: Path) -> None:
        self.root, self.archive_candles = Path(root), Path(archive_candles)
        self.archive_macro, self.archive_treasury, self.holidays_csv = (Path(archive_macro), Path(archive_treasury),
                                                                        Path(holidays_csv))

    # ---------------------------------------------------------------- the manifest
    def manifest(self) -> list[dict]:
        p = self.root / "manifest.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    def _log(self, rec: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "manifest.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def holes(self) -> set[str]:
        return {r["hole"] for r in self.manifest() if "hole" in r}

    def add_file(self, rel: str, data: bytes, now: datetime) -> str:
        """Store `data` at `rel` once: 'added', 'same', 'revision' (bytes differ; kept) or 'hole'."""
        path, digest = self.root / rel, hashlib.sha256(data).hexdigest()
        stamp = now.isoformat(timespec="seconds")
        if rel in self.holes():
            self._log({"late": rel, "sha256": digest, "seen_utc": stamp})
            return "hole"
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                return "same"
            if not any(r.get("revision") == rel and r.get("sha256_new") == digest for r in self.manifest()):
                self._log({"revision": rel, "sha256_new": digest, "seen_utc": stamp})
            return "revision"
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_new(path, data)
        self._log({"path": rel, "sha256": digest, "bytes": len(data), "fetched_utc": stamp})
        return "added"

    def declare_hole(self, rel: str, now: datetime, reason: str) -> None:
        if not (self.root / rel).exists() and rel not in self.holes():
            self._log({"hole": rel, "reason": reason, "declared_utc": now.isoformat(timespec="seconds")})

    def _have(self, rel: str, holes: set[str]) -> bool:
        return rel in holes or (self.root / rel).exists()

    # ---------------------------------------------------------------- horizons
    def minute_horizon(self, names, today: date) -> date:
        """The last UTC day (before `today`) through which every name's minute files are settled."""
        holes, d = self.holes(), EPOCH
        while d < today and all(self._have(minute_rel(n, d, s), holes) for n in names for s in SIDES):
            d += timedelta(days=1)
        return d - timedelta(days=1)

    def tick_horizon(self, name: str, today: date) -> date:
        holes, d = self.holes(), EPOCH
        while d < today and (self._have(tick_rel(name, d), holes) or self._no_ticks(name, d, holes)):
            d += timedelta(days=1)
        return d - timedelta(days=1)

    def _no_ticks(self, name: str, d: date, holes: set[str]) -> bool:
        rels = [minute_rel(name, d, s) for s in SIDES]
        if any(r in holes or not (self.root / r).exists() for r in rels):
            return False
        return all(decode_day((self.root / r).read_bytes(), name, d)["volume"].sum() == 0 for r in rels)

    # ---------------------------------------------------------------- prices
    def hourly(self, name: str, through: date) -> Hourly:
        """The instrument's hours from its first month to the end of UTC day `through`, contiguous."""
        parts = [load(self.archive_candles, name, (ARCHIVE_END.year, ARCHIVE_END.month))]
        last_month = (EPOCH - timedelta(days=1)).year, (EPOCH - timedelta(days=1)).month
        try:
            parts.append(load(self.root / "hourly", name, last_month, since=(ARCHIVE_END.year + 1, 1)))
        except FileNotFoundError as e:
            raise StoreGap(f"{name}: a 2026 monthly hourly file is missing: {e}") from None
        holes, close = self.holes(), float(parts[-1].mid_close[-1])
        for d in days_between(EPOCH, through):
            rels = [minute_rel(name, d, s) for s in SIDES]
            if any(r in holes for r in rels):
                t0 = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
                hrs = (np.arange(24, dtype=np.int64) * 3600 + t0, np.full(24, close), np.full(24, close),
                       np.zeros(24), np.zeros(24, bool))
            elif all((self.root / r).exists() for r in rels):
                hrs = _aggregate(*(decode_day((self.root / r).read_bytes(), name, d) for r in rels))
            else:
                raise StoreGap(f"{name} {d}: its minute files are neither stored nor a declared hole")
            parts.append(Hourly(name, *hrs))
            close = float(hrs[2][-1])
        cols = [np.concatenate([getattr(p, f) for p in parts])
                for f in ("start", "mid_open", "mid_close", "spread_open", "traded")]
        keep = cols[0] < int(datetime.combine(through + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp())
        h = Hourly(name, *(c[keep] for c in cols))
        if np.any(np.diff(h.start) != 3600):
            raise StoreGap(f"{name}: the hours are not contiguous across the store's periods")
        return h

    # ---------------------------------------------------------------- frozen series
    def frozen(self) -> dict[str, str]:
        p = self.root / "series" / "frozen.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def _rows(self, path: Path) -> list[tuple[date, str | None, float]]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return [(date.fromisoformat(r["date"]), r.get("area") or None, float(r["value"])) for r in csv.DictReader(f)]

    def _archive(self, sid: str) -> list[tuple[date, str | None, float]]:
        root = self.archive_macro.parent
        if sid == Y7:
            with (self.archive_treasury / "ust_par.csv").open(newline="", encoding="utf-8") as f:
                rows = [(date.fromisoformat(r["date"]), None, float(r["y7"])) for r in csv.DictReader(f)]
        elif sid in (ECB, CPI, COT):
            path = root / ("cot/cot_gold.csv" if sid == COT else f"fx_value/{'ecb_daily' if sid == ECB else 'bis_cpi'}.csv")
            if not path.exists():
                return []
            with path.open(newline="", encoding="utf-8") as f:
                raw = list(csv.DictReader(f))
            rows = ([(date.fromisoformat(r["date"]), r["currency"], float(r["eur_rate"])) for r in raw] if sid == ECB
                    else [(date.fromisoformat(r["month"] + "-01"), r["area"], float(r["cpi"])) for r in raw] if sid == CPI
                    else [(date.fromisoformat(r["as_of"]), k, float(r[k])) for r in raw for k in COT_FIELDS])
        else:
            rows = self._rows(self.archive_macro / f"{sid}.csv")
        return [r for r in rows if r[0] <= ARCHIVE_END]

    def series(self, sid: str, through: date) -> list[tuple[date, str | None, float]]:
        rows = self._archive(sid) + self._rows(self.root / "series" / f"{sid}.csv")
        return [r for r in rows if r[0] <= through]

    def freeze_series(self, sid: str, rows, through: date, now: datetime) -> int:
        """Append the fetched rows dated after the series' frozen day, up to `through`; log revisions."""
        frozen = self.frozen()
        cur = date.fromisoformat(frozen.get(sid, ARCHIVE_END.isoformat()))
        path = self.root / "series" / f"{sid}.csv"
        have = {(d, a): v for d, a, v in self._rows(path)}
        seen = {(r.get("key"), r.get("seen")) for r in self.manifest() if r.get("revision") == f"series/{sid}"}
        for d, a, v in rows:
            key = f"{d.isoformat()}|{a or ''}"
            if ARCHIVE_END < d <= cur and have.get((d, a)) != v and (key, v) not in seen:
                self._log({"revision": f"series/{sid}", "key": key, "frozen": have.get((d, a)), "seen": v,
                           "seen_utc": now.isoformat(timespec="seconds")})
        new = sorted((r for r in rows if cur < r[0] <= through), key=lambda r: (r[0], r[1] or ""))
        if through > cur:
            path.parent.mkdir(parents=True, exist_ok=True)
            fresh = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f, lineterminator="\n")
                if fresh:
                    w.writerow(["date", "area", "value"])
                w.writerows((d.isoformat(), a or "", v) for d, a, v in new)
            tmp = path.parent / "frozen.json.tmp"
            tmp.write_text(json.dumps({**frozen, sid: through.isoformat()}, sort_keys=True), encoding="utf-8")
            os.replace(tmp, path.parent / "frozen.json")
        return len(new)

    def through(self, sid: str) -> date:
        return date.fromisoformat(self.frozen().get(sid, ARCHIVE_END.isoformat()))

    def closes(self, sid: str, through: date) -> dict[date, float]:
        return {d: v for d, _, v in self.series(sid, through)}

    def rates(self, through: date, max_stale_days: int, weekly_stale_days: int) -> RateTable:
        out = {}
        for ccy, (sid, area) in CCY_SERIES.items():
            rows = [(d, v) for d, a, v in self.series(sid, through) if area is None or a == area]
            if rows:
                out[ccy] = rows
        weekly = {c: weekly_stale_days for c, (sid, _) in CCY_SERIES.items() if sid in WEEKLY_SOURCES}
        return RateTable(out, max_stale_days, weekly)

    def holidays_jp(self) -> frozenset[date]:
        return load_holidays(self.holidays_csv)

    def state_hash(self) -> str:
        h = hashlib.sha256()
        for p in [self.root / "manifest.jsonl", *sorted((self.root / "series").glob("*"))]:
            if p.is_file():
                h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
        return h.hexdigest()
