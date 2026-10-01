"""R1.5: Dukascopy hourly BID + ASK candles for the 30-instrument research universe, 2012-2025.

Bucket `cfg-public-proper-wallaby` (eu-west-1, Requester Pays: the owner's AWS account pays, about
10,000 files and ~65 MB in all, a few cents). Each instrument-year is one `aws s3 sync` filtered to
`*/{BID,ASK}_candles_hour_1.bi5`; every month is then decoded and checked by
tests/backtest/candles.py (whole hours, OHLC order, the plausible envelope, ask >= bid at the
close on most hours) into manifest.jsonl with its sha256. A month that fails is deleted and named.

  python scripts/download_dukascopy_candles.py check   # identity, symbols present, size and cost
  python scripts/download_dukascopy_candles.py run     # download + verify; reruns skip what is there
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from download_dukascopy_s3 import AUTH_ERRORS, BUCKET, aws  # noqa: E402
from tests.backtest.candles import CandleError, decode_month, glitches  # noqa: E402
from tests.backtest.universe import UNIVERSE  # noqa: E402

OUT = ROOT / "data" / "dukascopy_candles"
MANIFEST = OUT / "manifest.jsonl"
YEARS = range(2012, 2026)
SIDES = ("BID", "ASK")


def months(first: str):
    fy, fm = (int(x) for x in first.split("-"))
    for y in YEARS:
        for m in range(1, 13):
            if (y, m) >= (fy, fm):
                yield y, m


def path(inst, y: int, m: int, side: str) -> Path:
    return OUT / inst.duka / str(y) / f"{m - 1:02d}" / f"{side}_candles_hour_1.bi5"


def cmd_check() -> int:
    """Cheap: the identity, then each instrument's FIRST and LAST month present (two LISTs each; a
    recursive listing walks decades of tick files and takes hours). Size: ~6.5 KB a file."""
    who = aws("sts", "get-caller-identity", "--query", "Arn", "--output", "text", s3=False)
    print("identity:", who.stdout.strip() or f"FAILED: {who.stderr.strip()[:200]}")
    if who.returncode:
        return 2
    files = 0
    for inst in UNIVERSE:
        ms = list(months(inst.first))
        files += 2 * len(ms)
        ok = []
        for y, m in (ms[0], ms[-1]):
            ls = aws("s3", "ls", f"s3://{BUCKET}/{inst.duka}/{y}/{m - 1:02d}/")
            ok.append(sum(f"{s}_candles_hour_1.bi5" in ls.stdout for s in SIDES) == 2)
        print(f"  {inst.name:8} {inst.duka:14} {inst.first}..2025-12 {len(ms):3d} months: "
              f"{'ok' if all(ok) else 'MISSING first/last ' + str(ok)}", flush=True)
    print(f"TOTAL {files} files, ~{files * 6.5e-3:.0f} MB: ~${files * 6.5e-6 * 0.09:.3f} transfer + "
          f"~${files * 0.0004 / 1000:.3f} requests")
    return 0


def verify(inst, y: int, m: int) -> dict:
    sides = {}
    for s in SIDES:
        p = path(inst, y, m, s)
        raw = p.read_bytes()
        sides[s] = (decode_month(raw, inst.name, y, m), hashlib.sha256(raw).hexdigest(), p)
    bid, ask = sides["BID"][0], sides["ASK"][0]
    traded = [(b, a) for b, a in zip(bid, ask) if b.volume > 0 or a.volume > 0]
    crossed = sum(a.close < b.close for b, a in traded)
    if traded and crossed > max(3, 0.02 * len(traded)):
        raise CandleError(f"{inst.name} {y}-{m:02d}: ask < bid at the close on {crossed}/{len(traded)} traded hours")
    return {"instrument": inst.name, "month": f"{y}-{m:02d}", "traded_hours": len(traded), "crossed": crossed,
            "glitch_hours": glitches(bid, inst.name) + glitches(ask, inst.name),
            **{f"{s.lower()}_sha256": sides[s][1] for s in SIDES},
            **{f"{s.lower()}_path": sides[s][2].relative_to(ROOT).as_posix() for s in SIDES}}


def cmd_run() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    done = set()
    if MANIFEST.exists():
        done = {(r["instrument"], r["month"]) for r in map(json.loads, MANIFEST.read_text(encoding="utf-8").splitlines())}
    bad = []
    with MANIFEST.open("a", encoding="utf-8") as man:
        for inst in UNIVERSE:
            for y in YEARS:
                todo = [(yy, m) for yy, m in months(inst.first) if yy == y and (inst.name, f"{y}-{m:02d}") not in done]
                if not todo:
                    continue
                r = aws("s3", "sync", f"s3://{BUCKET}/{inst.duka}/{y}/", str(OUT / inst.duka / str(y)),
                        "--exclude", "*", "--include", "*/BID_candles_hour_1.bi5",
                        "--include", "*/ASK_candles_hour_1.bi5", "--only-show-errors")
                if r.returncode:
                    err = (r.stderr or r.stdout).strip()
                    if any(a in err for a in AUTH_ERRORS):
                        raise SystemExit(f"AWS credentials problem, owner must fix: {err[:200]}")
                    bad.append(f"{inst.name} {y}: sync failed: {err[:160]}")
                    continue
                for yy, m in todo:
                    try:
                        man.write(json.dumps(verify(inst, yy, m)) + "\n")
                    except (CandleError, FileNotFoundError) as e:
                        bad.append(str(e))
                        for s in SIDES:
                            path(inst, yy, m, s).unlink(missing_ok=True)
                man.flush()
            print(f"{inst.name}: done", flush=True)
    print(f"{len(bad)} problem month(s)")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("check", "run"))
    return {"check": cmd_check, "run": cmd_run}[ap.parse_args().cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
