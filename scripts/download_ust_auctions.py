"""Download the US Treasury's note auction calendar, 2011-2025 (AUCTION's kill test, GAP-P12D-158; P&L-blind).

    python scripts/download_ust_auctions.py      # writes data/r1_real/treasury/auctions.csv + its sha256

Source: the Treasury's own FiscalData API, "Treasury Securities Auctions Data" (auctions_query), every Note
auction (new issues and reopenings) with its date, term, reopening flag, offering amount, issue date, CUSIP
and its FRN and TIPS flags (the kill test keeps fixed-rate nominal notes only).
It reads no price and no yield.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "r1_real" / "treasury"
API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
FIELDS = ("auction_date", "security_term", "security_type", "reopening", "offering_amt", "issue_date", "cusip",
          "floating_rate", "inflation_index_security")


def fetch(page: int) -> dict:
    query = (f"?filter=security_type:eq:Note,auction_date:gte:2011-01-01,auction_date:lte:2025-12-31"
             f"&fields={','.join(FIELDS)}&sort=auction_date&page[size]=1000&page[number]={page}")
    with urllib.request.urlopen(API + query.replace("[", "%5B").replace("]", "%5D"), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    rows, page = [], 1
    while True:
        body = fetch(page)
        rows += body["data"]
        if page >= body["meta"]["total-pages"]:
            break
        page += 1
    if len(rows) != body["meta"]["total-count"]:
        raise SystemExit(f"fetched {len(rows)} rows, the API counts {body['meta']['total-count']}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "auctions.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "auctions.manifest.json").write_text(json.dumps({"url": API, "rows": len(rows), "sha256": sha}, indent=1),
                                                encoding="utf-8")
    print(json.dumps({"rows": len(rows), "sha256": sha}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
