"""COMEX gold's weekly Commitments of Traders, 2011-2025, from the CFTC (HEDGEP's input, FACTORY, GAP-P12D-158).

    python scripts/download_cot.py --out data/r1_real/cot

Mental model:
  * The CFTC's legacy futures-only annual files (`deacot<year>.zip`, its historical compressed reports)
    hold one row per market per report; `cot_gold.csv` keeps COMEX gold (contract code 088691):
    `as_of,open_interest,commercial_long,commercial_short`. The as-of date is the Tuesday the positions
    were measured; the CFTC releases the report after 15:30 Eastern on the Friday (`hedgep.release`).
  * P&L-blind: positions only, no price. Checks before anything is written: every year has at least
    50 reports, dates rise strictly, and every count is non-negative and below the open interest.
    Each zip is kept; `manifest.json` records every URL, sha256 and row count.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://www.cftc.gov/files/dea/history/deacot{y}.zip"
YEARS, GOLD = range(2011, 2026), "088691"


def rows(body: bytes) -> list[tuple[str, int, int, int]]:
    z = zipfile.ZipFile(io.BytesIO(body))
    out = []
    for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode("latin-1"))):
        if r["CFTC Contract Market Code"].strip() == GOLD:
            oi, cl, cs = (int(r[k].strip()) for k in ("Open Interest (All)", "Commercial Positions-Long (All)",
                                                      "Commercial Positions-Short (All)"))
            if not (0 <= cl <= oi and 0 <= cs <= oi):
                raise ValueError(f"{r['As of Date in Form YYYY-MM-DD']}: implausible counts {oi}, {cl}, {cs}")
            out.append((r["As of Date in Form YYYY-MM-DD"].strip(), oi, cl, cs))
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    raw, data, manifest = {}, [], {}
    for y in YEARS:
        url = URL.format(y=y)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "acis-research"}), timeout=120) as r:
            body = r.read()
        year = rows(body)
        if len(year) < 50:
            raise SystemExit(f"{y}: only {len(year)} gold reports")
        raw[y], data = body, data + year
        manifest[f"raw/deacot{y}.zip"] = {"url": url, "sha256": hashlib.sha256(body).hexdigest(), "rows": len(year)}
    dates = [d for d, *_ in data]
    if any(b <= x for x, b in zip(dates, dates[1:])):
        raise SystemExit("the report dates do not rise strictly")
    (a.out / "raw").mkdir(parents=True, exist_ok=True)
    for y, body in raw.items():
        (a.out / "raw" / f"deacot{y}.zip").write_bytes(body)
    text = "as_of,open_interest,commercial_long,commercial_short\n" + "".join(f"{d},{o},{l},{s}\n" for d, o, l, s in data)
    (a.out / "cot_gold.csv").write_bytes(text.encode("utf-8"))      # bytes: the manifest hashes what is on disk
    manifest["cot_gold.csv"] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "rows": len(data),
                                "span": [dates[0], dates[-1]]}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest["cot_gold.csv"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
