"""The US Treasury's daily par yield curve, 2011-2025, from its issuer (REBAL's bond input, GAP-P12D-157).

    python scripts/download_treasury.py --out data/r1_real/treasury

Mental model:
  * One CSV a year from home.treasury.gov (the issuer; the repo takes rates from issuers, never mirrors).
    Each raw response is kept for provenance, and `ust_par.csv` holds `date,y7,y10` in percent.
  * Checks before anything is written: every year parses, has more than 240 bond-market days, every
    yield lies in [-1, 10]%, and the documented record-low 10-year close reproduces (0.54 on
    2020-03-09). `manifest.json` records URL, sha256 and rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
       "{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
YEARS = range(2011, 2026)
KNOWN_10Y = {date(2020, 3, 9): 0.54}


def parse(text: str) -> dict[date, tuple[float, float]]:
    rows = {}
    for r in csv.DictReader(io.StringIO(text)):
        d = datetime.strptime(r["Date"], "%m/%d/%Y").date()
        y7, y10 = float(r["7 Yr"]), float(r["10 Yr"])
        if not (-1.0 <= y7 <= 10.0 and -1.0 <= y10 <= 10.0):
            raise ValueError(f"{d}: implausible yields {y7}, {y10}")
        rows[d] = (y7, y10)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    raw, rows, manifest = {}, {}, {}
    for y in YEARS:
        url = URL.format(y=y)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "acis-research"}), timeout=60) as r:
            body = r.read()
        year = parse(body.decode("utf-8-sig"))
        if len(year) < 240:
            raise SystemExit(f"{y}: only {len(year)} days")
        raw[y], rows = body, {**rows, **year}
        manifest[str(y)] = {"url": url, "sha256": hashlib.sha256(body).hexdigest(), "rows": len(year)}
    for d, v in KNOWN_10Y.items():
        if abs(rows[d][1] - v) > 0.005:
            raise SystemExit(f"{d}: 10-year {rows[d][1]} is not the documented {v}")
    (a.out / "raw").mkdir(parents=True, exist_ok=True)
    for y, body in raw.items():
        (a.out / "raw" / f"{y}.csv").write_bytes(body)
    lines = ["date,y7,y10"] + [f"{d.isoformat()},{v[0]},{v[1]}" for d, v in sorted(rows.items())]
    out = "\n".join(lines) + "\n"
    (a.out / "ust_par.csv").write_bytes(out.encode("utf-8"))   # bytes: the manifest hashes what is on disk
    manifest["ust_par.csv"] = {"sha256": hashlib.sha256(out.encode()).hexdigest(), "rows": len(rows),
                               "span": [min(rows).isoformat(), max(rows).isoformat()]}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest["ust_par.csv"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
