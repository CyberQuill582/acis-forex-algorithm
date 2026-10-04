"""The tournament's daily fetch: the newest public inputs into the frozen input store (TOURNAMENT, 2026-10-04).

    python scripts/forward_fetch.py --store data/forward/inputs              # what the daily job runs first
    python scripts/forward_fetch.py --store data/forward/inputs --audit      # re-sync every month since EPOCH

Mental model (P&L-blind: it reads no strategy return):
  * DUKASCOPY: the R1.5 archive bucket (Requester Pays; in eu-west-1 the transfer is free) publishes each
    UTC day's 1-minute and tick files at ~03:30 UTC the next day and a month's hourly file on the 2nd of
    the next. Each month in scope is one `aws s3 sync` into a staging copy, then every file is imported
    write-once (`InputStore.add_file`): a changed remote file becomes a revision line, never a new value.
  * A needed file still missing HOLE_AFTER_DAYS after its day is declared a hole (read as no data).
  * SERIES: Yahoo's S&P 500 closes, the Treasury's par curve, the ECB fixings and the CFTC gold report
    freeze through yesterday (at most their last print); the overnight rates through two days ago (a late
    print is ignored, the table forward-fills, as the live engine does); BIS CPI through month - 5.
  * Every action is a JSONL event (logs/tournament_log.jsonl); the summary is printed as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from core.data.rates import CCY_SERIES  # noqa: E402
from tests.backtest.forward_store import (ARCHIVE_END, COT, CPI, ECB, EPOCH, HOLE_AFTER_DAYS, RATE_SIDS, SIDES,  # noqa: E402
                                          SPX, Y7, InputStore, days_between, hour_rel, minute_rel, tick_rel)
from tests.backtest.tournament_registry import REGISTRY  # noqa: E402
from tests.backtest.universe import BY_NAME  # noqa: E402

LAGS = {SPX: 1, Y7: 1, **{s: 2 for s in RATE_SIDS}}           # days a print may take before its date freezes


def needs() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(instruments needing candles, instruments needing ticks) over the registry."""
    ticks = tuple(sorted({s.instruments[0] for s in REGISTRY if s.clock == "jst_window"}))
    return tuple(sorted({n for s in REGISTRY for n in s.instruments} | set(ticks))), ticks


def aws_sync(prefix: str, dest: Path, includes: tuple[str, ...]) -> str:
    """`aws s3 sync` of one archive prefix with include filters; returns '' or the error text."""
    from download_dukascopy_s3 import AUTH_ERRORS, BUCKET, aws
    args = ["s3", "sync", f"s3://{BUCKET}/{prefix}", str(dest), "--exclude", "*", "--only-show-errors"]
    for inc in includes:
        args += ["--include", inc]
    r = aws(*args)
    err = (r.stderr or r.stdout).strip() if r.returncode else ""
    if any(a in err for a in AUTH_ERRORS):
        raise SystemExit(f"AWS credentials problem, the owner must fix it: {err[:200]}")
    return err


def months(first: date, last: date):
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch_dukascopy(store: InputStore, staging: Path, today: date, now: datetime, sync=aws_sync,
                    audit: bool = False) -> dict:
    candles, ticks = needs()
    out = {"synced": 0, "errors": [], "imported": {}}
    def take(rel: str, src: Path) -> None:
        if src.exists():
            r = store.add_file(rel, src.read_bytes(), now)
            out["imported"][r] = out["imported"].get(r, 0) + 1
    pre = [(y, m) for y, m in months(ARCHIVE_END + timedelta(days=1), EPOCH - timedelta(days=1))]
    for n in candles:
        duka = BY_NAME[n].duka
        if any(not (store.root / hour_rel(n, y, m, s)).exists() for y, m in pre for s in SIDES):
            for y in sorted({y for y, _ in pre}):
                err = sync(f"{duka}/{y}/", staging / duka / str(y), ("*/BID_candles_hour_1.bi5", "*/ASK_candles_hour_1.bi5"))
                out["errors"] += [f"{n} {y} hourly: {err[:160]}"] if err else []
            for y, m in pre:
                for s in SIDES:
                    take(hour_rel(n, y, m, s), staging / duka / str(y) / f"{m - 1:02d}" / f"{s}_candles_hour_1.bi5")
        h = store.minute_horizon((n,), today)
        h = min(h, store.tick_horizon(n, today)) if n in ticks else h
        first = EPOCH if audit else max(EPOCH, h + timedelta(days=1))
        for y, m in months(first, today):
            inc = ("*/BID_candles_min_1.bi5", "*/ASK_candles_min_1.bi5") + (("*_ticks.bi5",) if n in ticks else ())
            dest = staging / duka / str(y) / f"{m - 1:02d}"
            err = sync(f"{duka}/{y}/{m - 1:02d}/", dest, inc)
            out["synced"] += 1
            out["errors"] += [f"{n} {y}-{m:02d}: {err[:160]}"] if err else []
            for d in (x for x in days_between(date(y, m, 1), today - timedelta(days=1)) if x.month == m and x >= EPOCH):
                for s in SIDES:
                    take(minute_rel(n, d, s), dest / f"{d.day:02d}" / f"{s}_candles_min_1.bi5")
                if n in ticks:
                    take(tick_rel(n, d), dest / f"{d.day:02d}_ticks.bi5")
    out["holes"] = declare_holes(store, candles, ticks, today, now)
    return out


def declare_holes(store: InputStore, candles, ticks, today: date, now: datetime) -> int:
    """A needed file still missing HOLE_AFTER_DAYS after its UTC day is a hole from now on."""
    n_before, holes = len(store.holes()), store.holes()
    last = today - timedelta(days=1 + HOLE_AFTER_DAYS)
    for d in days_between(EPOCH, last):
        for n in candles:
            for s in SIDES:
                if not (store.root / minute_rel(n, d, s)).exists():
                    store.declare_hole(minute_rel(n, d, s), now, f"missing {HOLE_AFTER_DAYS} days after its day")
        for n in ticks:
            if not (store.root / tick_rel(n, d)).exists() and not store._no_ticks(n, d, holes):
                store.declare_hole(tick_rel(n, d), now, f"missing {HOLE_AFTER_DAYS} days after its day")
    return len(store.holes()) - n_before


def fetch_series(store: InputStore, today: date, now: datetime) -> dict:
    import download_macro as dm
    import download_treasury as dt
    out = {}
    start = ARCHIVE_END + timedelta(days=1)
    specs = {sid: v for sid, v in dm.series(start, today).items() if sid in (SPX, *RATE_SIDS)}
    areas = {a for sid, a in CCY_SERIES.values() if a}
    for sid, (url, parser, os_tls, (lo, hi), _) in specs.items():
        try:
            raw = parser(dm.fetch(url, via_os_tls=os_tls))
            rows = [(r[0], r[1], r[2]) if len(r) == 3 else (r[0], None, r[1]) for r in raw]
            rows = [r for r in rows if (r[1] is None or r[1] in areas) and lo <= r[2] <= hi]
            out[sid] = _freeze(store, sid, rows, today, now)
        except Exception as e:                       # a failed source does not advance; the others do
            out[sid] = f"FAILED: {e!r}"[:200]
    try:
        rows = []
        for y in range(start.year, today.year + 1):
            body = dm.fetch(dt.URL.format(y=y))
            rows += [(d, None, v[0]) for d, v in dt.parse(body.decode("utf-8-sig")).items()]
        out[Y7] = _freeze(store, Y7, rows, today, now)
    except Exception as e:
        out[Y7] = f"FAILED: {e!r}"[:200]
    return out | fetch_factory_series(store, today, now)


def fetch_factory_series(store: InputStore, today: date, now: datetime) -> dict:
    """FACTORY's inputs from their issuers with FACTORY's own parsers: ECB fixings (through their last
    print), BIS CPI (through month - 5, the latest month its m - 4 read needs), CFTC gold (last report)."""
    import importlib
    import tests.backtest.tournament_factory as tf
    out, start = {}, ARCHIVE_END + timedelta(days=1)
    try:
        dfv, dc = importlib.import_module("download_fx_value"), importlib.import_module("download_cot")
    except ModuleNotFoundError as e:
        return {"skipped": f"FACTORY's downloaders are not on this branch: {e}"}
    old_ecb, old_bis = "startPeriod=2005-01-01&endPeriod=2025-12-31", "startPeriod=2004-01&endPeriod=2025-12"
    assert old_ecb in dfv.ECB and old_bis in dfv.BIS, "download_fx_value's URLs changed: re-check the forward fetch"
    jobs = {ECB: lambda: tf.read_rows(raw_ecb=dfv.parse_ecb(dfv._get(dfv.ECB.replace(
                old_ecb, f"startPeriod={start}&endPeriod={today}"))))[ECB],
            CPI: lambda: tf.read_rows(raw_cpi=dfv.parse_bis(dfv._get(dfv.BIS.replace(
                old_bis, f"startPeriod={start:%Y-%m}&endPeriod={today:%Y-%m}"))))[CPI],
            COT: lambda: tf.read_rows(raw_cot=[r for y in range(start.year, today.year + 1)
                                               for r in dc.rows(dfv._get(dc.URL.format(y=y)))])[COT]}
    m5 = today.year * 12 + today.month - 1 - 5
    for sid, job in jobs.items():
        try:
            rows = job()
            through = date(m5 // 12, m5 % 12 + 1, 1) if sid == CPI else min(today - timedelta(days=1),
                                                                             max(r[0] for r in rows))
            out[sid] = {"rows": store.freeze_series(sid, rows, through, now), "through": store.through(sid).isoformat()}
        except Exception as e:                       # a failed source does not advance; the others do
            out[sid] = f"FAILED: {e!r}"[:200]
    return out


def _freeze(store: InputStore, sid: str, rows, today: date, now: datetime) -> dict:
    through = today - timedelta(days=LAGS[sid])
    if sid in (SPX, Y7) and rows:
        through = min(through, max(r[0] for r in rows))      # never freeze past the last print
    return {"rows": store.freeze_series(sid, rows, through, now), "through": store.through(sid).isoformat()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", type=Path, default=ROOT / "data" / "forward" / "inputs")
    ap.add_argument("--staging", type=Path, default=ROOT / "data" / "forward" / "staging")
    ap.add_argument("--archive", type=Path, default=ROOT / "data" / "r1_real", help="dukascopy_candles, macro, treasury, jp_holidays")
    ap.add_argument("--audit", action="store_true", help="re-sync every month since EPOCH (revision check)")
    ap.add_argument("--skip-dukascopy", action="store_true")
    ap.add_argument("--skip-series", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    store = open_store(a.store, a.archive)
    log = JsonlEventLogger(ROOT / "logs" / "tournament_log.jsonl", "research", f"tournament-fetch-{now:%Y%m%dT%H%M%SZ}")
    summary = {"dukascopy": None if a.skip_dukascopy else fetch_dukascopy(store, a.staging, now.date(), now, audit=a.audit),
               "series": None if a.skip_series else fetch_series(store, now.date(), now), "state": store.state_hash()}
    log.event("FORWARD_FETCH", **summary)
    log.close()
    print(json.dumps(summary, indent=1, default=str))
    return 0


def open_store(store: Path, archive: Path) -> InputStore:
    return InputStore(store, archive_candles=archive / "dukascopy_candles", archive_macro=archive / "macro",
                      archive_treasury=archive / "treasury", holidays_csv=archive / "jp_holidays" / "holidays.csv")


if __name__ == "__main__":
    sys.exit(main())
