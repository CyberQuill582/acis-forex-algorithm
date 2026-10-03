"""Dukascopy 1-minute BID + ASK candles for the six explored indices, 2012-2025 (GAP-P12D-158: IMOM;
GAP-P12D-157: REBAL-live's timing look). P&L-blind data sourcing.

The R1.5 mirror bucket (`download_dukascopy_s3.BUCKET`, Requester Pays: the owner's AWS account pays a
few cents for ~37,000 day files, ~400 MB). Each instrument-year is one `aws s3 sync` filtered to
`*/{BID,ASK}_candles_min_1.bi5`; every day is then decoded by tests/backtest/candles_min.py and recorded
in manifest.jsonl with both sides' sha256. A day that fails is deleted and named; reruns skip what is
recorded.

  python scripts/download_dukascopy_minutes.py --out data/r1_real/dukascopy_minutes            # sync + verify
  python scripts/download_dukascopy_minutes.py --out data/r1_real/dukascopy_minutes --no-sync  # verify only

From the laptop the sync is latency-bound (~1.3 s a file, ~20 h), so the 2026-10-03 pull ran the same
filtered sync on the AWS data server (the bucket's region), packed one archive through the transfer
bucket, and verified it here with --no-sync.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from download_dukascopy_s3 import AUTH_ERRORS, BUCKET, aws  # noqa: E402
from tests.backtest.candles import CandleError  # noqa: E402
from tests.backtest.candles_min import decode_day  # noqa: E402
from tests.backtest.universe import BY_NAME  # noqa: E402

NAMES = ("US500", "US30", "UK100", "EU50", "JP225", "AUS200")
YEARS = range(2012, 2026)
SIDES = ("BID", "ASK")


class _Done:
    returncode, stdout, stderr = 0, "", ""


def verify(out: Path, name: str, day_dir: Path) -> dict:
    y, m0, d = int(day_dir.parent.parent.name), int(day_dir.parent.name), int(day_dir.name)
    day = date(y, m0 + 1, d)
    rec = {"instrument": name, "day": day.isoformat()}
    for side in SIDES:
        raw = (day_dir / f"{side}_candles_min_1.bi5").read_bytes()
        rows = decode_day(raw, name, day)
        rec[side] = {"sha256": hashlib.sha256(raw).hexdigest(), "traded_minutes": int((rows["volume"] > 0).sum())}
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-sync", action="store_true", help="verify the files already in --out")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    manifest = a.out / "manifest.jsonl"
    done = {(r["instrument"], r["day"]) for r in map(json.loads, manifest.read_text(encoding="utf-8").splitlines())} \
        if manifest.exists() else set()
    bad = []
    with manifest.open("a", encoding="utf-8") as man:
        for name in NAMES:
            duka = BY_NAME[name].duka
            for y in YEARS:
                r = _Done() if a.no_sync else aws(
                    "s3", "sync", f"s3://{BUCKET}/{duka}/{y}/", str(a.out / duka / str(y)), "--exclude", "*",
                    "--include", "*/BID_candles_min_1.bi5", "--include", "*/ASK_candles_min_1.bi5", "--only-show-errors")
                if r.returncode:
                    err = (r.stderr or r.stdout).strip()
                    if any(x in err for x in AUTH_ERRORS):
                        raise SystemExit(f"AWS credentials problem, owner must fix: {err[:200]}")
                    bad.append(f"{name} {y}: sync failed: {err[:160]}")
                    continue
                for day_dir in sorted(p for p in (a.out / duka / str(y)).glob("*/*") if p.is_dir()):
                    key = (name, f"{y}-{int(day_dir.parent.name) + 1:02d}-{int(day_dir.name):02d}")
                    if key in done:
                        continue
                    try:
                        man.write(json.dumps(verify(a.out, name, day_dir)) + "\n")
                    except (CandleError, FileNotFoundError, ValueError) as e:
                        bad.append(f"{key}: {e}")
                        for side in SIDES:
                            (day_dir / f"{side}_candles_min_1.bi5").unlink(missing_ok=True)
                man.flush()
                print(f"{name} {y}: done", flush=True)
    print(f"{len(bad)} problem day(s)")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
