"""ECB euro foreign-exchange reference rates — the independent price check for Dukascopy
(GAP-P12D-14 check 1, owner-approved 2026-09-13).

The ECB publishes one reference rate per currency per TARGET business day, set by a
daily concertation at 14:15 Frankfurt time (quoted as units of currency per 1 EUR).
Free, official, and fully independent of Dukascopy — so it can catch a wrong price
level, a shifted day or a wrong point scale in the tick data, which HistData (whose FX
ticks are Dukascopy's own, GAP-P12D-13) cannot.

    data/macro/ecb_exr.csv    date,currency,eur_rate   (USD, GBP, JPY, CHF, CAD, AUD)

Reuses scripts/download_macro.py's patient fetch + ECB CSV parser + atomic writes.
    python scripts/download_ecb_rates.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from download_macro import OUT, RAW, fetch, parse_ecb, write_atomic  # noqa: E402

CURRENCIES = ("USD", "GBP", "JPY", "CHF", "CAD", "AUD")
START, END = date(2012, 1, 1), date(2025, 12, 31)
URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A"
       "?startPeriod={start}&endPeriod={end}&format=csvdata")
# Wide 2012–2025 envelopes per 1 EUR: a wrong series or scale is far outside them.
# (EUR/CHF really printed 1.2599 on 2013-05-22, above the SNB's 1.20 floor.)
PLAUSIBLE = {"USD": (0.95, 1.65), "GBP": (0.69, 0.97), "JPY": (93.0, 190.0),
             "CHF": (0.90, 1.30), "CAD": (1.20, 1.70), "AUD": (1.15, 2.00)}
NORM = OUT / "ecb_exr.csv"
MANIFEST = OUT / "ecb_manifest.json"


def validate(ccy: str, rows: list[tuple[date, float]]) -> str | None:
    """Return a rejection reason, or None if the series is usable."""
    if len(rows) < 3400:                                  # ~255 TARGET days × 14 years
        return f"only {len(rows)} rows"
    ds = [d for d, _ in rows]
    if any(b <= a for a, b in zip(ds, ds[1:])):
        return "dates not strictly increasing"
    lo, hi = PLAUSIBLE[ccy]
    bad = [(d, v) for d, v in rows if not lo <= v <= hi]
    if bad:
        return f"{len(bad)} values outside [{lo}, {hi}], e.g. {bad[:2]}"
    if ds[0] > date(2012, 1, 5) or ds[-1] < date(2025, 12, 1):
        return f"covers {ds[0]} .. {ds[-1]}, expected 2012-01 .. 2025-12"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if NORM.exists() and MANIFEST.exists() and not a.force:
        print(f"skip  {NORM.name} (already valid; --force to refetch)")
        return 0
    RAW.mkdir(parents=True, exist_ok=True)
    out, manifest = ["date,currency,eur_rate"], {}
    for ccy in CURRENCIES:
        url = URL.format(ccy=ccy, start=START.isoformat(), end=END.isoformat())
        print(f"fetch ECB EUR/{ccy} ...", flush=True)
        raw = fetch(url)
        rows = parse_ecb(raw)
        why = validate(ccy, rows)
        if why:
            print(f"REJECT EUR/{ccy}: {why}")
            return 1
        write_atomic(RAW / f"ecb_exr_{ccy.lower()}.csv", raw)
        out += [f"{d.isoformat()},{ccy},{v}" for d, v in rows]
        manifest[ccy] = {"url": url, "rows": len(rows), "first": rows[0][0].isoformat(),
                         "last": rows[-1][0].isoformat(), "sha256_raw": hashlib.sha256(raw).hexdigest()}
        print(f"OK    EUR/{ccy}: {len(rows)} rows {rows[0][0]} .. {rows[-1][0]}")
    write_atomic(NORM, ("\n".join(out) + "\n").encode())
    manifest["fetched_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_atomic(MANIFEST, json.dumps(manifest, indent=1).encode())
    print(f"wrote {NORM} ({len(out) - 1} rows)")
    return 0


def load(path=NORM) -> dict[tuple[date, str], float]:
    """{(date, currency): units per EUR} from the normalised CSV."""
    rates = {}
    for line in io.StringIO(path.read_text(encoding="utf-8")).read().splitlines()[1:]:
        d, ccy, v = line.split(",")
        rates[(date.fromisoformat(d), ccy)] = float(v)
    return rates


if __name__ == "__main__":
    sys.exit(main())
