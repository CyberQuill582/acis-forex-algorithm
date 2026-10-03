"""FX value's inputs from their issuers: ECB reference rates and BIS consumer prices (FACTORY, GAP-P12D-158).

    python scripts/download_fx_value.py --out data/r1_real/fx_value

Mental model:
  * ECB: the daily euro reference rates (14:15 CET) of USD, JPY, GBP, AUD, CAD and CHF, 2005-2025, from
    the ECB's own data API; `ecb_daily.csv` holds `date,currency,eur_rate` (units of the currency per EUR).
  * BIS: the long consumer price series (WS_LONG_CPI, index 628) of US, XM (euro area), JP, GB, AU, CA and
    CH, monthly 2004-2025; `bis_cpi.csv` holds `month,area,cpi`. Australia's is quarterly, repeated in
    each of the quarter's months by the BIS. These are today's vintages, not real-time ones (declared).
  * P&L-blind: nothing here reads a strategy return. Checks before anything is written: every series
    is present and in range, and the ECB's documented EUR/USD high reproduces (1.5990 on 2008-07-15).
    Each raw response is kept; `manifest.json` records every URL, sha256 and row count.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path

CCYS = ("USD", "JPY", "GBP", "AUD", "CAD", "CHF")
AREAS = ("US", "XM", "JP", "GB", "AU", "CA", "CH")
ECB = ("https://data-api.ecb.europa.eu/service/data/EXR/D." + "+".join(CCYS)
       + ".EUR.SP00.A?startPeriod=2005-01-01&endPeriod=2025-12-31&format=csvdata")
BIS = ("https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LONG_CPI/1.0/M." + "+".join(AREAS)
       + ".628?startPeriod=2004-01&endPeriod=2025-12&format=csv")
KNOWN = {("2008-07-15", "USD"): 1.5990}
RANGE = {"USD": (0.9, 1.7), "JPY": (90.0, 200.0), "GBP": (0.6, 1.0), "AUD": (1.1, 2.2), "CAD": (1.2, 1.8),
         "CHF": (0.9, 1.7)}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "acis-research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def parse_ecb(body: bytes) -> list[tuple[str, str, float]]:
    rows = []
    for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
        if r["OBS_VALUE"]:
            ccy, v = r["CURRENCY"], float(r["OBS_VALUE"])
            lo, hi = RANGE[ccy]
            if not lo <= v <= hi:
                raise ValueError(f"{r['TIME_PERIOD']} {ccy}: {v} outside {lo}..{hi}")
            rows.append((r["TIME_PERIOD"], ccy, v))
    return sorted(rows)


def parse_bis(body: bytes) -> list[tuple[str, str, float]]:
    rows = []
    for r in csv.DictReader(io.StringIO(body.decode("utf-8-sig"))):
        if r["OBS_VALUE"] and r["OBS_VALUE"].lower() != "nan":     # the US skipped 2025-10 (shutdown)
            v = float(r["OBS_VALUE"])
            if not 50.0 <= v <= 200.0:
                raise ValueError(f"{r['TIME_PERIOD']} {r['REF_AREA']}: CPI {v} outside 50..200")
            rows.append((r["TIME_PERIOD"], r["REF_AREA"], v))
    return sorted(rows)


def check(ecb: list, bis: list) -> None:
    days = {}
    for d, c, _ in ecb:
        days.setdefault(c, set()).add(d)
    if set(days) != set(CCYS) or any(len(v) < 5000 for v in days.values()):
        raise SystemExit(f"ECB: a currency is missing or short: { {c: len(v) for c, v in days.items()} }")
    got = {(d, c): v for d, c, v in ecb}
    for k, v in KNOWN.items():
        if abs(got[k] - v) > 1e-9:
            raise SystemExit(f"ECB {k}: {got[k]} is not the documented {v}")
    months = {}
    for m, a, _ in bis:
        months.setdefault(a, set()).add(m)
    if set(months) != set(AREAS) or any(len(v) < 260 for v in months.values()):
        raise SystemExit(f"BIS: an area is missing or short: { {a: len(v) for a, v in months.items()} }")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    raw = {"ecb_daily.raw.csv": _get(ECB), "bis_cpi.raw.csv": _get(BIS)}
    ecb, bis = parse_ecb(raw["ecb_daily.raw.csv"]), parse_bis(raw["bis_cpi.raw.csv"])
    check(ecb, bis)
    files = {"ecb_daily.csv": "date,currency,eur_rate\n" + "".join(f"{d},{c},{v}\n" for d, c, v in ecb),
             "bis_cpi.csv": "month,area,cpi\n" + "".join(f"{m},{ar},{v}\n" for m, ar, v in bis)}
    (a.out / "raw").mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, body in raw.items():
        (a.out / "raw" / name).write_bytes(body)
        manifest[f"raw/{name}"] = {"url": ECB if name.startswith("ecb") else BIS,
                                   "sha256": hashlib.sha256(body).hexdigest()}
    for name, text in files.items():
        body = text.encode("utf-8")
        (a.out / name).write_bytes(body)             # bytes: the manifest hashes what is on disk
        manifest[name] = {"sha256": hashlib.sha256(body).hexdigest(), "rows": text.count("\n") - 1}
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
