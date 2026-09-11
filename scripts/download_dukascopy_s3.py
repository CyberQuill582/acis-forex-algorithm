"""ACIS OOS PRIMARY tick data — Dukascopy's official S3 archive (master §13 v2.13).

Bucket `cfg-public-proper-wallaby` (eu-west-1, Requester Pays), one file per UTC day:
`SYMBOL/YYYY/MM/DD_ticks.bi5` with MM ZERO-based. The AWS CLI does the transfer
(`aws s3 sync`: credentials, retries, concurrency and resume — present files are
skipped). This script orchestrates (newest year first, all 8 instruments) and VERIFIES
every new file with tests/backtest/bi5.py (LZMA, whole records, ticks inside their day,
plausible prices) into manifest.jsonl; a file that fails is deleted so the next sync
refetches it. A cleanly synced + verified instrument-year gets a `SYNCED` marker — the
reader treats a missing day inside a SYNCED year as "no ticks" (holiday), and a year
with no marker as not downloaded.

Credentials: the OWNER runs `aws configure`; this script never reads or prints keys.
Cost goes to the owner's AWS account (requester pays) — `check` prints the size first.

  python scripts/download_dukascopy_s3.py check     # CLI, identity, symbols, sizes, XAU scale
  python scripts/download_dukascopy_s3.py test --instrument EUR_USD --month 2012-01
  python scripts/download_dukascopy_s3.py run       # 2012–2025; launched by dl_supervisor.ps1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dl_common import Ops  # noqa: E402
from tests.backtest.bi5 import SYMBOLS, Bi5Error, decode  # noqa: E402

BUCKET, REGION = "cfg-public-proper-wallaby", "eu-west-1"
OUT = ROOT / "data" / "dukascopy"
MANIFEST, STATUS, COMPLETE = OUT / "manifest.jsonl", OUT / "status.json", OUT / "COMPLETE"
YEARS = list(range(2025, 2011, -1))                 # newest first
UTC = timezone.utc
OPS = Ops(OUT, "s3.eu-west-1.amazonaws.com")
log = OPS.log
AUTH_ERRORS = ("InvalidAccessKeyId", "SignatureDoesNotMatch", "AccessDenied",
               "Unable to locate credentials", "ExpiredToken")


def aws_exe() -> str:
    for c in (shutil.which("aws"), r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"):
        if c and Path(c).exists():
            return c
    raise SystemExit("AWS CLI v2 not found — install it, then run `aws configure` (owner).")


def aws(*args: str, s3: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
    extra = ["--region", REGION] + (["--request-payer", "requester"] if s3 else [])
    env = dict(os.environ, AWS_RETRY_MODE="adaptive", AWS_MAX_ATTEMPTS="10")
    return subprocess.run([aws_exe(), *args, *extra], capture_output=True, text=True,
                          env=env, timeout=timeout)


def prefix(inst: str, year: int, month: int | None = None) -> str:
    p = f"s3://{BUCKET}/{SYMBOLS[inst][0]}/{year}/"
    return p + (f"{month - 1:02d}/" if month else "")


def sync(src: str, dest: Path) -> None:
    """`aws s3 sync` with retry-until-done; network drops wait, bad credentials abort."""
    for attempt in range(1, 7):
        OPS.wait_for_disk()
        r = aws("s3", "sync", src, str(dest), "--exclude", "*", "--include", "*_ticks.bi5",
                "--only-show-errors")
        if r.returncode == 0:
            return
        err = (r.stderr or r.stdout).strip()
        if any(a in err for a in AUTH_ERRORS):
            raise SystemExit(f"AWS credentials/permission problem — owner must fix: {err[:200]}")
        log(f"SYNC  {src} attempt {attempt}/6 failed: {err[:160]}")
        OPS.wait_for_network()
        time.sleep(min(600, 30 * 2 ** attempt))
    raise RuntimeError(f"sync kept failing: {src}")


def verify_dir(inst: str, year: int, dest: Path, known: set[str]) -> tuple[int, int]:
    """Decode every unverified day file under `dest`; return (verified, rejected)."""
    ok = bad = 0
    for f in sorted(dest.rglob("*_ticks.bi5")):
        rel = f.relative_to(ROOT).as_posix()
        if rel in known:
            continue
        month0, day = int(f.parent.name), int(f.name.split("_")[0])
        start = datetime(year, month0 + 1, day, tzinfo=UTC)
        raw = f.read_bytes()
        try:
            ticks = list(decode(raw, inst, start))
            if ticks and not (start <= ticks[0].ts and ticks[-1].ts < start + timedelta(days=1)):
                raise Bi5Error(f"ticks outside {start:%Y-%m-%d}")
        except Bi5Error as e:
            f.unlink()                                   # the next sync refetches it
            bad += 1
            log(f"BAD   {rel}: {e}")
            continue
        rec = {"instrument": inst, "file": rel, "day": start.date().isoformat(),
               "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "ticks": len(ticks),
               "first_utc": ticks[0].ts.isoformat() if ticks else None,
               "last_utc": ticks[-1].ts.isoformat() if ticks else None}
        with MANIFEST.open("a", encoding="utf-8") as m:
            m.write(json.dumps(rec) + "\n")
        known.add(rel)
        ok += 1
    return ok, bad


def load_known() -> set[str]:
    if not MANIFEST.exists():
        return set()
    return {json.loads(l)["file"] for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l}


def missing_weekdays(inst: str, year: int) -> list[str]:
    """Weekdays with no file in a SYNCED year (holidays expected; the rest need review)."""
    d, out = date(year, 1, 1), []
    while d.year == year:
        p = OUT / inst / str(year) / f"{d.month - 1:02d}" / f"{d.day:02d}_ticks.bi5"
        if d.weekday() < 5 and d.strftime("%m-%d") not in ("12-25", "01-01") and not p.exists():
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cmd_run() -> int:
    if COMPLETE.exists():
        log("COMPLETE marker present - nothing to do")
        return 0
    if not OPS.acquire_lock():
        print("another downloader holds the lock")
        return 3
    known, coverage = load_known(), {}
    todo = [(y, i) for y in YEARS for i in SYMBOLS if not (OUT / i / str(y) / "SYNCED").exists()]
    log(f"START pid={os.getpid()} instrument-years remaining={len(todo)}/{len(YEARS) * len(SYMBOLS)} "
        f"free={OPS.free_gb():.1f}GB")
    OPS.wait_for_network()
    for n, (year, inst) in enumerate(todo, 1):
        dest = OUT / inst / str(year)
        sync(prefix(inst, year), dest)
        ok, bad = verify_dir(inst, year, dest, known)
        if bad:
            log(f"RETRY {inst} {year}: {bad} file(s) failed verification - refetching next pass")
            continue                                     # no SYNCED marker: next pass resyncs
        (dest / "SYNCED").write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
        coverage[f"{inst} {year}"] = missing_weekdays(inst, year)
        log(f"OK    {inst} {year}: +{ok} files  [{n}/{len(todo)}]  free={OPS.free_gb():.1f}GB")
        OPS.write_json(STATUS, {"updated": datetime.now(UTC).isoformat(timespec="seconds"),
                                "done_this_run": n, "remaining": len(todo) - n,
                                "reached": f"{inst} {year}", "verified_files": len(known),
                                "free_disk_gb": round(OPS.free_gb(), 1)})
    OPS.write_json(OUT / "coverage.json", coverage)
    left = [(y, i) for y in YEARS for i in SYMBOLS if not (OUT / i / str(y) / "SYNCED").exists()]
    if left:
        log(f"PASS ENDED with {len(left)} instrument-years unsynced - supervisor reruns")
        return 1
    COMPLETE.write_text(f"{datetime.now(UTC).isoformat()} files={len(known)}\n", encoding="utf-8")
    log(f"FINISHED - {len(known)} verified day files; review coverage.json for missing weekdays")
    return 0


def cmd_check() -> int:
    print(aws("--version", s3=False).stdout.strip() or aws("--version", s3=False).stderr.strip())
    who = aws("sts", "get-caller-identity", "--query", "Arn", "--output", "text", s3=False)
    print("identity:", who.stdout.strip() or f"FAILED — run `aws configure` first: {who.stderr.strip()[:200]}")
    if who.returncode:
        return 2
    top = aws("s3", "ls", f"s3://{BUCKET}/")
    have = {l.split()[-1].rstrip("/") for l in top.stdout.splitlines() if l.strip().endswith("/")}
    for inst, (sym, _) in SYMBOLS.items():
        print(f"  {inst:8} {sym:7} {'present' if sym in have else 'MISSING from bucket'}")
    total = 0
    for inst in SYMBOLS:
        ls = aws("s3", "ls", f"s3://{BUCKET}/{SYMBOLS[inst][0]}/", "--recursive")
        size = sum(int(p[2]) for l in ls.stdout.splitlines() if (p := l.split()) and len(p) == 4
                   and p[3].endswith("_ticks.bi5") and 2012 <= int(p[3].split("/")[1]) <= 2025)
        total += size
        print(f"  {inst:8} 2012-2025 ticks: {size / 1e9:.2f} GB")
    print(f"TOTAL {total / 1e9:.2f} GB  (requester pays: ~${total / 1e9 * 0.02:.2f} transfer + requests)")
    with tempfile.TemporaryDirectory() as tmp:          # XAU point-scale probe (bi5 PLAUSIBLE)
        aws("s3", "cp", f"s3://{BUCKET}/XAUUSD/2012/00/03_ticks.bi5", tmp)
        f = Path(tmp) / "03_ticks.bi5"
        t = next(decode(f.read_bytes(), "XAU_USD", datetime(2012, 1, 3, tzinfo=UTC)), None)
        print("XAU scale check:", f"first tick bid {t.bid} (2012-01-03 ~1600 expected)" if t else "no data")
    return 0


def cmd_test(inst: str, month: str) -> int:
    y, m = (int(x) for x in month.split("-"))
    dest = OUT / inst / str(y) / f"{m - 1:02d}"
    sync(prefix(inst, y, m), dest)
    ok, bad = verify_dir(inst, y, OUT / inst / str(y), load_known())
    print(f"TEST {inst} {month}: {ok} day files verified, {bad} rejected")
    return 0 if ok and not bad else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("run")
    t = sub.add_parser("test")
    t.add_argument("--instrument", required=True, choices=sorted(SYMBOLS))
    t.add_argument("--month", required=True, help="YYYY-MM")
    a = ap.parse_args()
    try:
        return {"check": cmd_check, "run": cmd_run}.get(a.cmd, lambda: cmd_test(a.instrument, a.month))()
    except SystemExit:
        raise
    except Exception as e:                               # supervisor restarts on exit 2
        log(f"FATAL {e!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
