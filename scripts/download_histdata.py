"""ACIS OOS data acquisition — HistData.com ASCII TICK download (§14 guard-2, master §13).

Primary bulk tick source for the ratified 8-instrument universe, 2012-01 .. 2025-12
(owner-ratified 2026-09-11 after Dukascopy proved unable to sustain the volume from the
owner's connection). HistData publishes one zip per pair per month:

    DAT_ASCII_<PAIR>_T_<YYYYMM>.csv   "YYYYMMDD HHMMSSNNN,bid,ask,volume"
    timestamps in EST *without* daylight saving, i.e. a fixed UTC-5 offset

Unattended and self-resuming, like scripts/download_dukascopy.js:

  ORDER    newest month first, all 8 instruments per month — the on-disk data is always
           one contiguous recent window covering the whole universe.
  NETWORK  a network error never counts as a failure; waits for TCP reachability, backs
           off, retries indefinitely.
  RATE     polite fixed pacing between files; 429/503 trigger an escalating cooldown.
  ATOMIC   streamed to <file>.part, VERIFIED, then renamed — a crash can never leave a
           truncated zip that resume would treat as done.
  VERIFY   every zip must pass zipfile.testzip(), contain the expected CSV, parse fully,
           and stay inside its month. Row count, first/last UTC tick, crossed/non-positive
           quotes, out-of-order/duplicate timestamps and HistData's own gap report are
           recorded per file in manifest.jsonl — the provenance record for the §14 run.
  RESUME   an existing verified zip is skipped. The zip is kept exactly as published
           (original provenance); the backtest reader parses it directly.

Usage (always via the absolute interpreter path on this machine — PATH is broken):
    python scripts/download_histdata.py test --pair eurgbp --month 2012-01
    python scripts/download_histdata.py run          # normally launched by the supervisor

Output:  data/histdata/<INSTRUMENT>/<YYYY>/HISTDATA_COM_ASCII_<PAIR>_T<YYYYMM>.zip
Status:  data/histdata/status.json    Log: data/histdata/download.log
Exit:    0 complete (writes COMPLETE)  1 pass incomplete  2 fatal  3 locked
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import msvcrt
import os
import re
import shutil
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

INSTRUMENTS = {
    "eurusd": "EUR_USD",
    "usdjpy": "USD_JPY",
    "gbpusd": "GBP_USD",
    "audusd": "AUD_USD",
    "usdchf": "USD_CHF",
    "usdcad": "USD_CAD",
    "eurgbp": "EUR_GBP",
    "xauusd": "XAU_USD",
}
FIRST_MONTH = (2012, 1)
LAST_MONTH = (2025, 12)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "histdata"
LOG = OUT / "download.log"
STATUS = OUT / "status.json"
STATE = OUT / "state.json"
MANIFEST = OUT / "manifest.jsonl"
LOCK = OUT / "download.lock"
COMPLETE = OUT / "COMPLETE"

SITE = "https://www.histdata.com"
PAGE = SITE + "/download-free-forex-historical-data/?/ascii/tick-data-quotes/{pair}/{year}/{month}"
GET = SITE + "/get.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
EST_FIXED = timezone(timedelta(hours=-5))      # HistData: EST, NO daylight saving

PAUSE_S = 8                   # between files (HistData asks for gentle use)
COOLDOWN_BASE_S = 5 * 60
COOLDOWN_MAX_S = 60 * 60
HARD_ATTEMPTS = 5             # non-network failures per file per run
PERM_FAIL_RUNS = 3            # runs a file may hard-fail before it is skipped
DISK_MIN_GB = 3.0
TIMEOUT_S = 120


# ----------------------------------------------------------------- infrastructure
def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def acquire_lock():
    """OS file lock: released automatically if the process dies, so never stale."""
    fh = open(LOCK, "a+")
    fh.seek(0)
    try:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        fh.close()
        return None
    return fh


def online() -> bool:
    try:
        socket.create_connection(("www.histdata.com", 443), timeout=10).close()
        return True
    except OSError:
        return False


def wait_for_network() -> None:
    if online():
        return
    log("NETWORK DOWN - waiting for connectivity (checking every 30 s)...")
    t0 = time.time()
    while not online():
        time.sleep(30)
    log(f"NETWORK BACK after {round((time.time() - t0) / 60)} min - resuming")


def free_gb() -> float:
    return shutil.disk_usage(OUT).free / 1e9


def wait_for_disk() -> None:
    if free_gb() >= DISK_MIN_GB:
        return
    log(f"DISK LOW ({free_gb():.1f} GB free < {DISK_MIN_GB}) - paused; free space to continue")
    while free_gb() < DISK_MIN_GB:
        time.sleep(600)
    log("DISK OK - resuming")


class RateLimited(Exception):
    pass


class Unavailable(Exception):
    """HistData does not offer this pair-month (no download form on the page)."""


# --------------------------------------------------------------------------- plan
def months():
    y, m = LAST_MONTH
    while (y, m) >= FIRST_MONTH:
        yield y, m
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)


def zip_path(pair: str, y: int, m: int) -> Path:
    return OUT / INSTRUMENTS[pair] / str(y) / f"HISTDATA_COM_ASCII_{pair.upper()}_T{y}{m:02d}.zip"


def build_plan():
    return [(pair, y, m) for (y, m) in months() for pair in INSTRUMENTS]


# ------------------------------------------------------------------------ fetching
def http(url: str, data: bytes | None = None, referer: str | None = None):
    headers = {"User-Agent": UA}
    if referer:
        headers.update({"Referer": referer, "Origin": SITE,
                        "Content-Type": "application/x-www-form-urlencoded"})
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            raise RateLimited(f"HTTP {e.code}") from e
        raise


def form_fields(pair: str, y: int, m: int) -> tuple[str, dict]:
    page = PAGE.format(pair=pair, year=y, month=m)
    html = http(page).read().decode("utf-8", "replace")
    form = re.search(r'<form[^>]*id="file_down".*?</form>', html, re.S)
    if not form:
        raise Unavailable(f"no download form on {page}")
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form.group(0)))
    want = {"date": str(y), "datemonth": f"{y}{m:02d}", "platform": "ASCII",
            "timeframe": "T", "fxpair": pair.upper()}
    for k, v in want.items():                  # never download the wrong file
        if fields.get(k) != v:
            raise ValueError(f"form field {k}={fields.get(k)!r}, expected {v!r}")
    if not fields.get("tk"):
        raise ValueError("form has no tk token")
    return page, fields


def download(pair: str, y: int, m: int, dest: Path) -> int:
    page, fields = form_fields(pair, y, m)
    time.sleep(1.5)
    resp = http(GET, urllib.parse.urlencode(fields).encode(), referer=page)
    part = dest.with_suffix(".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with part.open("wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
    with part.open("rb") as f:
        head = f.read(4)
    if head != b"PK\x03\x04":
        snippet = part.read_bytes()[:200].decode("utf-8", "replace").replace("\n", " ")
        part.unlink(missing_ok=True)
        if re.search(r"limit|too many|slow down", snippet, re.I):
            raise RateLimited(f"non-zip throttle page: {snippet[:80]}")
        raise ValueError(f"response is not a zip ({n} bytes): {snippet[:120]!r}")
    return n


# ---------------------------------------------------------------------- verifying
TS_RE = re.compile(r"^\d{8} \d{9}$")


def est_to_utc(ts: str) -> datetime:
    return (datetime.strptime(ts[:15], "%Y%m%d %H%M%S")
            .replace(microsecond=int(ts[15:18]) * 1000, tzinfo=EST_FIXED)
            .astimezone(timezone.utc))


def verify(pair: str, y: int, m: int, path: Path) -> dict:
    """Fully parse the zip. Raises ValueError on anything that makes it unusable."""
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            raise ValueError(f"corrupt member {bad}")
        csv_name = f"DAT_ASCII_{pair.upper()}_T_{y}{m:02d}.csv"
        names = zf.namelist()
        if csv_name not in names:
            raise ValueError(f"{csv_name} missing; zip has {names}")
        rows = crossed = nonpos = out_of_order = dup = 0
        first = last = prev = None
        with zf.open(csv_name) as raw:
            for line in io.TextIOWrapper(raw, encoding="ascii", errors="strict"):
                line = line.strip()
                if not line:
                    continue
                ts, bid, ask, *_ = line.split(",")
                if not TS_RE.match(ts):
                    raise ValueError(f"bad timestamp {ts!r} at row {rows + 1}")
                b, a = float(bid), float(ask)
                rows += 1
                if b <= 0 or a <= 0:
                    nonpos += 1
                elif a < b:
                    crossed += 1
                if prev is not None:
                    if ts < prev:
                        out_of_order += 1
                    elif ts == prev:
                        dup += 1
                if first is None:
                    first = ts
                last = prev = ts
        if rows == 0:
            raise ValueError("CSV has no rows")
        if first[:6] != f"{y}{m:02d}" or last[:6] != f"{y}{m:02d}":
            raise ValueError(f"ticks outside {y}-{m:02d}: {first} .. {last}")
        gaps, max_gap = 0, 0
        report = [n for n in names if n.endswith(".txt")]
        if report:
            txt = zf.read(report[0]).decode("utf-8", "replace")
            secs = [int(s) for s in re.findall(r"Gap of (\d+)s", txt)]
            gaps, max_gap = len(secs), max(secs, default=0)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "instrument": INSTRUMENTS[pair], "pair": pair.upper(), "month": f"{y}-{m:02d}",
        "bytes": path.stat().st_size, "sha256": digest, "rows": rows,
        "first_utc": est_to_utc(first).isoformat(), "last_utc": est_to_utc(last).isoformat(),
        "crossed": crossed, "nonpositive": nonpos, "out_of_order": out_of_order,
        "duplicate_ts": dup, "gap_reports": gaps, "max_gap_s": max_gap,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ------------------------------------------------------------------------- fetch one
def fetch_one(pair: str, y: int, m: int, state: dict) -> str:
    """Download + verify one pair-month. Returns 'ok' | 'unavailable' | 'failed'."""
    dest = zip_path(pair, y, m)
    key = dest.name
    hard, cool = 0, COOLDOWN_BASE_S
    net_wait = 5
    while True:
        wait_for_disk()
        try:
            n = download(pair, y, m, dest)
            rec = verify(pair, y, m, dest.with_suffix(".part"))
            os.replace(dest.with_suffix(".part"), dest)
            rec["file"] = str(dest.relative_to(ROOT)).replace("\\", "/")
            with MANIFEST.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            state["hard_fails"].pop(key, None)
            write_json_atomic(STATE, state)
            flags = [f"{k}={rec[k]}" for k in ("crossed", "nonpositive", "out_of_order", "duplicate_ts")
                     if rec[k]]
            log(f"OK    {INSTRUMENTS[pair]} {y}-{m:02d}  {n / 1e6:.1f}MB  rows={rec['rows']:,}  "
                f"gaps={rec['gap_reports']}(max {rec['max_gap_s']}s)  {' '.join(flags)}")
            return "ok"
        except Unavailable as e:
            state["unavailable"][key] = str(e)
            write_json_atomic(STATE, state)
            log(f"N/A   {INSTRUMENTS[pair]} {y}-{m:02d}  {e}")
            return "unavailable"
        except RateLimited as e:
            log(f"429   {INSTRUMENTS[pair]} {y}-{m:02d}  {e} - cooldown {cool // 60} min")
            time.sleep(cool)
            cool = min(COOLDOWN_MAX_S, cool * 2)
        except OSError as e:                   # urllib/socket/timeout errors all derive from it
            if isinstance(e, urllib.error.HTTPError):
                hard += 1
                log(f"ERR   {INSTRUMENTS[pair]} {y}-{m:02d}  {hard}/{HARD_ATTEMPTS}  HTTP {e.code}")
            else:
                log(f"NET   {INSTRUMENTS[pair]} {y}-{m:02d}  {e!r} - retry in {net_wait}s")
                time.sleep(net_wait)
                net_wait = min(600, net_wait * 2)
                wait_for_network()
                continue
        except (ValueError, zipfile.BadZipFile, UnicodeDecodeError) as e:
            hard += 1
            log(f"ERR   {INSTRUMENTS[pair]} {y}-{m:02d}  {hard}/{HARD_ATTEMPTS}  {e}")
        dest.with_suffix(".part").unlink(missing_ok=True)
        if hard >= HARD_ATTEMPTS:
            state["hard_fails"][key] = state["hard_fails"].get(key, 0) + 1
            write_json_atomic(STATE, state)
            log(f"FAIL  {INSTRUMENTS[pair]} {y}-{m:02d}  (run {state['hard_fails'][key]}/{PERM_FAIL_RUNS})")
            return "failed"
        if hard:
            time.sleep(30)


# ------------------------------------------------------------------------ commands
def load_state() -> dict:
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    s.setdefault("hard_fails", {})
    s.setdefault("unavailable", {})
    return s


def cmd_run() -> int:
    if COMPLETE.exists():
        log("COMPLETE marker present - nothing to do")
        return 0
    lock = acquire_lock()
    if lock is None:
        print("another downloader holds the lock")
        return 3
    state = load_state()
    plan = build_plan()
    todo, done = [], 0
    for p, y, m in plan:
        z = zip_path(p, y, m)
        if z.exists():
            done += 1
        elif z.name in state["unavailable"] or state["hard_fails"].get(z.name, 0) >= PERM_FAIL_RUNS:
            continue
        else:
            todo.append((p, y, m))
    skipped = len(plan) - done - len(todo)
    log(f"START pid={os.getpid()} files={len(plan)} done={done} skipped={skipped} "
        f"remaining={len(todo)} free={free_gb():.1f}GB")
    wait_for_network()
    stamps, gb = [], 0.0
    for p, y, m in todo:
        result = fetch_one(p, y, m, state)
        if result == "ok":
            done += 1
            gb += zip_path(p, y, m).stat().st_size / 1e9
            stamps = (stamps + [time.time()])[-60:]
        span_h = (stamps[-1] - stamps[0]) / 3600 if len(stamps) > 1 else 0
        per_h = (len(stamps) - 1) / span_h if span_h else 0
        left = len(plan) - done - len(state["unavailable"])
        write_json_atomic(STATUS, {
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "done": done, "total": len(plan), "percent": round(100 * done / len(plan), 2),
            "unavailable": len(state["unavailable"]),
            "permanent_failures": sum(1 for v in state["hard_fails"].values() if v >= PERM_FAIL_RUNS),
            "downloaded_this_run_gb": round(gb, 3), "files_per_hour": round(per_h, 1),
            "eta_hours": round(left / per_h, 1) if per_h else None,
            "reached_back_to": f"{y}-{m:02d}", "free_disk_gb": round(free_gb(), 1),
            "pid": os.getpid(),
        })
        time.sleep(PAUSE_S)
    missing = [z for z in (zip_path(p, y, m) for p, y, m in plan)
               if not z.exists() and z.name not in state["unavailable"]
               and state["hard_fails"].get(z.name, 0) < PERM_FAIL_RUNS]
    if not missing:
        perm = [k for k, v in state["hard_fails"].items() if v >= PERM_FAIL_RUNS]
        COMPLETE.write_text(
            f"{datetime.now(timezone.utc).isoformat()} done={done} "
            f"unavailable={len(state['unavailable'])} permanent_failures={len(perm)}\n"
            + "".join(f"UNAVAILABLE {k}\n" for k in state["unavailable"])
            + "".join(f"FAILED {k}\n" for k in perm), encoding="utf-8")
        log(f"FINISHED - {done} files; unavailable={len(state['unavailable'])} failed={len(perm)}")
        return 0
    log(f"PASS ENDED with {len(missing)} files still missing - supervisor will rerun")
    return 1


def cmd_test(pair: str, month: str) -> int:
    y, m = (int(x) for x in month.split("-"))
    if pair not in INSTRUMENTS:
        print(f"unknown pair {pair}; choose from {list(INSTRUMENTS)}")
        return 2
    t0 = time.time()
    state = load_state()
    result = fetch_one(pair, y, m, state)
    if result != "ok":
        print(f"TEST {result.upper()}")
        return 1
    rec = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines()][-1]
    print("TEST OK in", round(time.time() - t0, 1), "s")
    print(json.dumps(rec, indent=1))
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    t = sub.add_parser("test")
    t.add_argument("--pair", required=True)
    t.add_argument("--month", required=True, help="YYYY-MM")
    a = ap.parse_args()
    try:
        return cmd_run() if a.cmd == "run" else cmd_test(a.pair.lower(), a.month)
    except Exception as e:                      # supervisor restarts on exit 2
        log(f"FATAL {e!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
