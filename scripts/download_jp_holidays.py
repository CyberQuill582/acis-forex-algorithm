"""Japan's national holidays, 1955 onward, from the Cabinet Office (GOTOBI's calendar, GAP-P12D-158).

    python scripts/download_jp_holidays.py --out data/r1_real/jp_holidays

Mental model:
  * One CSV from www8.cao.go.jp (the issuer; the repo takes calendars from issuers, never mirrors), in
    Shift-JIS, `YYYY/M/D,name`. It lists every 国民の祝日 and 休日: substitute holidays, citizens'
    holidays, the 2019 enthronement days and the Olympic moves of 2020-2021 included.
  * Checks before anything is written: every row parses, 2011-2025 each hold 15-22 days, and four
    documented one-off days are present (2019-05-01 enthronement, 2019-10-22 enthronement ceremony,
    2020-07-24 and 2021-07-23 the moved Sports Day). The raw bytes are kept; `holidays.csv` holds
    `date` in ISO form, and `manifest.json` records URL, sha256 and rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path

URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
YEARS = range(2011, 2026)
KNOWN = (date(2019, 5, 1), date(2019, 10, 22), date(2020, 7, 24), date(2021, 7, 23))


def parse(body: bytes) -> list[date]:
    lines = body.decode("cp932").splitlines()
    out = [datetime.strptime(line.split(",")[0], "%Y/%m/%d").date() for line in lines[1:] if line.strip()]
    if len(set(out)) != len(out):
        raise ValueError("a holiday is listed twice")
    return sorted(out)


def check(days: list[date]) -> None:
    per_year = Counter(d.year for d in days)
    for y in YEARS:
        if not 15 <= per_year[y] <= 22:
            raise ValueError(f"{y}: {per_year[y]} holidays")
    missing = [d for d in KNOWN if d not in set(days)]
    if missing:
        raise ValueError(f"documented holidays missing: {missing}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "acis-research"}), timeout=60) as r:
        body = r.read()
    days = parse(body)
    check(days)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "syukujitsu.csv").write_bytes(body)
    out = ("date\n" + "".join(f"{d.isoformat()}\n" for d in days)).encode("utf-8")
    (a.out / "holidays.csv").write_bytes(out)
    manifest = {"url": URL, "raw_sha256": hashlib.sha256(body).hexdigest(),
                "holidays.csv": {"sha256": hashlib.sha256(out).hexdigest(), "rows": len(days),
                                 "span": [days[0].isoformat(), days[-1].isoformat()]}}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest["holidays.csv"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
