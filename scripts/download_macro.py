"""ACIS OOS macro data — SPX + overnight financing rates (§14 guard-2; GAP-P12D-03).

Small daily series (tens of KB each) for 2011-01-01..2025-12-31 (2011 = warm-up):

  spx_yahoo   S&P 500 closes          Yahoo chart API ^GSPC   (§14 SPX-corr gate; checked
                                                               against known published closes)
  usd_effr    effective fed funds     New York Fed rates API  (USD overnight)
  eur_dfr     ECB deposit facility    ECB data API FM/DFR     (EUR overnight proxy — declared)
  gbp_sonia   SONIA                   Bank of England IADB
  jpy_tona    uncollateralised call   BoJ API FM01/STRDCLUCON
  chf_saron   SARON                   SNB data portal
  cad_corra   CORRA                   Bank of Canada Valet AVG.INTWO
  bis_policy  policy rates, 7 areas   BIS WS_CBPOL            (AUD source + cross-check;
                                                               JP hole 2013-04..2016-09)

Overnight rates, not policy rates, are the financing proxy: OANDA prices rollover off
liquidity providers' tom-next rates, which track overnight money-market rates. Every
rate comes from its ISSUING central bank (FRED mirrors were dropped 2026-09-11: FRED
accepts the connection from the owner's network, then never sends a byte).

Each series keeps the RAW response (provenance) + a normalised `date,value` CSV, and
every file is recorded in manifest.json with URL, sha256, row count and span. A series
that fails its plausibility checks (range, ordering, coverage) is rejected, not saved.

Usage:  python scripts/download_macro.py            # all series (skips ones already valid)
        python scripts/download_macro.py --force    # re-fetch everything
        python scripts/download_macro.py --live data/macro_live   # the runtime's rates (R1.6): the last
            1,200 days through today, no SPX, each series fresh within 10 days (R6-1); run daily
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "macro"
RAW = OUT / "raw"
MANIFEST = OUT / "manifest.json"
START, END = date(2011, 1, 1), date(2025, 12, 31)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CURL = r"C:\Windows\System32\curl.exe" if os.name == "nt" else "curl"   # Linux: the system curl
BIS_AREAS = ("US", "XM", "JP", "GB", "AU", "CH", "CA")


# ------------------------------------------------------------------- fetching
def fetch(url: str, *, via_os_tls: bool = False, attempts: int = 6) -> bytes:
    """GET with patient retry. `via_os_tls` uses Windows' curl (SChannel), which
    completes a server's missing intermediate certificate from the OS store —
    verification stays ON; it is never disabled."""
    delay = 10
    for n in range(1, attempts + 1):
        try:
            if via_os_tls:
                r = subprocess.run([CURL, "-sS", "--fail", "--max-time", "180", "-A", UA, url],
                                   capture_output=True, timeout=240)
                if r.returncode != 0:
                    raise OSError(f"curl exit {r.returncode}: {r.stderr.decode(errors='replace')[:200]}")
                return r.stdout
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except (OSError, subprocess.TimeoutExpired) as e:
            if n == attempts:
                raise
            print(f"    retry {n}/{attempts - 1} in {delay}s: {e!r}"[:160], flush=True)
            time.sleep(delay)
            delay = min(300, delay * 2)
    raise AssertionError("unreachable")


def _num(s: str) -> float | None:
    s = s.strip().strip('"')
    if s in ("", ".", "null", "NaN", "NA", "#N/A"):
        return None
    return float(s)


# --------------------------------------------------------------------- parsers
def parse_nyfed(raw: bytes) -> list[tuple[date, float]]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    out = [(datetime.strptime(r["Effective Date"], "%m/%d/%Y").date(), v) for r in rows
           if (v := _num(r["Rate (%)"])) is not None]
    return sorted(out)                                      # the API returns newest first


def parse_ecb(raw: bytes) -> list[tuple[date, float]]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    return [(date.fromisoformat(r["TIME_PERIOD"]), v) for r in rows
            if (v := _num(r["OBS_VALUE"])) is not None]


def parse_boe(raw: bytes) -> list[tuple[date, float]]:
    rows = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    next(rows)                                              # DATE,IUDSOIA
    return [(datetime.strptime(d, "%d %b %Y").date(), v) for d, x in rows
            if (v := _num(x)) is not None]


def parse_yahoo(raw: bytes) -> list[tuple[date, float]]:
    res = json.loads(raw)["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for ts, c in zip(res["timestamp"], closes):             # 13:30/14:30 UTC = NY same day
        if c is not None:
            out.append((datetime.fromtimestamp(ts, tz=timezone.utc).date(), float(c)))
    return out


def parse_boj(raw: bytes) -> list[tuple[date, float]]:
    text = raw.decode("utf-8", "replace")
    lines = text.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("SERIES_CODE,"))
    rows = csv.DictReader(io.StringIO("\n".join(lines[head:])))
    out = []
    for r in rows:
        v = _num(r["VALUES"])
        if v is not None:
            out.append((datetime.strptime(r["SURVEY_DATES"], "%Y%m%d").date(), v))
    return out


def parse_snb(raw: bytes, key: str = "SARON") -> list[tuple[date, float]]:
    text = raw.decode("utf-8-sig", "replace")
    lines = [l for l in text.splitlines() if l.strip()]
    head = next(i for i, l in enumerate(lines) if l.lower().startswith('"date"') or l.lower().startswith("date"))
    rows = csv.reader(io.StringIO("\n".join(lines[head:])), delimiter=";")
    header = [h.strip('"') for h in next(rows)]
    di, ki, vi = header.index("Date"), header.index("D0"), header.index("Value")
    return [(date.fromisoformat(r[di].strip('"')), v) for r in rows
            if r[ki].strip('"') == key and (v := _num(r[vi])) is not None]


def parse_boc(raw: bytes, code: str = "AVG.INTWO") -> list[tuple[date, float]]:
    obs = json.loads(raw)["observations"]
    return [(date.fromisoformat(o["d"]), float(o[code]["v"])) for o in obs
            if code in o and _num(o[code]["v"]) is not None]


def parse_bis(raw: bytes) -> list[tuple[date, str, float]]:
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    return [(date.fromisoformat(r["TIME_PERIOD"]), r["REF_AREA"], v) for r in rows
            if (v := _num(r["OBS_VALUE"])) is not None]


# ------------------------------------------------------------------ the series
def _unix(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def series(START: date, END: date) -> dict:
  return {
    #  id:         (url, parser, via_os_tls, (lo, hi) plausible range, expected first-date by)
    "spx_yahoo":  (f"https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1={_unix(START)}"
                   f"&period2={_unix(END) + 86400}&interval=1d", parse_yahoo, False, (800, 9000), date(2011, 1, 10)),
    "usd_effr":   ("https://markets.newyorkfed.org/api/rates/unsecured/effr/search.csv"
                   f"?startDate={START.isoformat()}&endDate={END.isoformat()}", parse_nyfed, False,
                   (-1, 10), date(2011, 1, 10)),
    "eur_dfr":    ("https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV"
                   f"?startPeriod={START.isoformat()}&endPeriod={END.isoformat()}&format=csvdata",
                   parse_ecb, False, (-1.5, 6), date(2011, 1, 10)),
    "gbp_sonia":  ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
                   f"&Datefrom={START:%d/%b/%Y}&Dateto={END:%d/%b/%Y}&SeriesCodes=IUDSOIA"
                   "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N", parse_boe, False, (-1, 8), date(2011, 1, 10)),
    "jpy_tona":   ("https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=csv&lang=en&db=FM01"
                   f"&code=STRDCLUCON&startDate={START:%Y%m}&endDate={END:%Y%m}", parse_boj, False,
                   (-1, 3), date(2011, 1, 10)),
    "chf_saron":  ("https://data.snb.ch/api/cube/snbgwdzid/data/csv/en"
                   f"?fromDate={START.isoformat()}&toDate={END.isoformat()}", parse_snb, True,
                   # floor −3: SARON printed −1.55/−1.69 on 2015-01-22/23, the week after
                   # the SNB dropped the EUR/CHF floor — real history, not bad data
                   (-3, 4), date(2011, 1, 10)),
    "cad_corra":  ("https://www.bankofcanada.ca/valet/observations/AVG.INTWO/json"
                   f"?start_date={START.isoformat()}&end_date={END.isoformat()}", parse_boc, False,
                   (-0.5, 7), date(2011, 1, 10)),
    "bis_policy": ("https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D."
                   + "+".join(BIS_AREAS) + f"?startPeriod={START.isoformat()}&endPeriod={END.isoformat()}"
                   "&format=csv", parse_bis, False, (-1.5, 10), date(2011, 1, 10)),
  }


SERIES = series(START, END)


# Well-documented S&P 500 closes the downloaded series must reproduce (±0.02).
SPX_KNOWN_CLOSES = {
    date(2012, 1, 3): 1277.06,
    date(2019, 12, 31): 3230.78,
    date(2020, 3, 23): 2237.40,      # COVID low
    date(2021, 12, 31): 4766.18,
    date(2022, 12, 30): 3839.50,
}


def validate(sid: str, rows, lo: float, hi: float, first_by: date | None,
             ends_by: date = date(2025, 12, 1)) -> str | None:
    """Return a rejection reason, or None if the series is usable."""
    if not rows:
        return "no rows"
    if sid == "spx_yahoo":
        got = dict(rows)
        for d, want in SPX_KNOWN_CLOSES.items():
            if d not in got or abs(got[d] - want) > 0.02:
                return f"known close {d} = {want}, series has {got.get(d)}"
    keyed = [(r[0], r[1]) for r in rows] if sid == "bis_policy" else [(r[0], "") for r in rows]
    per_key: dict[str, list] = {}
    for (d, k), r in zip(keyed, rows):
        per_key.setdefault(k, []).append((d, r[-1]))
    for k, pts in per_key.items():
        ds = [d for d, _ in pts]
        if any(b <= a for a, b in zip(ds, ds[1:])):
            return f"{k or sid}: dates not strictly increasing"
        bad = [v for _, v in pts if not (math.isfinite(v) and lo <= v <= hi)]
        if bad:
            return f"{k or sid}: {len(bad)} values outside [{lo}, {hi}] e.g. {bad[:3]}"
        if first_by and ds[0] > first_by:
            return f"{k or sid}: starts {ds[0]}, expected by {first_by}"
        if ds[-1] < ends_by:
            return f"{k or sid}: ends {ds[-1]}, expected by {ends_by}"
    if sid == "bis_policy" and sorted(per_key) != sorted(BIS_AREAS):
        return f"areas {sorted(per_key)} != {sorted(BIS_AREAS)}"
    return None


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--live", type=Path, help="the runtime's rate directory (R1.6): always re-fetched")
    a = ap.parse_args()
    out, today, todo, ends_by = OUT, datetime.now(timezone.utc).date(), SERIES, date(2025, 12, 1)
    if a.live:
        out, ends_by = a.live, today - timedelta(days=10)
        todo = {k: v[:4] + (None,) for k, v in series(today - timedelta(days=1200), today).items() if k != "spx_yahoo"}
    raw_dir, manifest_path = out / "raw", out / "manifest.json"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    failed = []
    for sid, (url, parser, os_tls, (lo, hi), first_by) in todo.items():
        norm = out / f"{sid}.csv"
        if not (a.force or a.live) and sid in manifest and norm.exists():
            print(f"skip  {sid} (already valid: {manifest[sid]['rows']} rows)")
            continue
        print(f"fetch {sid} ...", flush=True)
        try:
            raw = fetch(url, via_os_tls=os_tls)
            rows = parser(raw)
        except Exception as e:                              # report, keep going
            failed.append(sid)
            print(f"FAIL  {sid}: {e!r}"[:300])
            continue
        why = validate(sid, rows, lo, hi, first_by, ends_by)
        if why:
            failed.append(sid)
            print(f"REJECT {sid}: {why}")
            continue
        ext = "json" if raw[:1] in (b"{", b"[") else "csv"
        write_atomic(raw_dir / f"{sid}.{ext}", raw)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        if sid == "bis_policy":
            w.writerow(["date", "area", "value"])
            w.writerows((d.isoformat(), k, v) for d, k, v in rows)
        else:
            w.writerow(["date", "value"])
            w.writerows((d.isoformat(), v) for d, v in rows)
        write_atomic(norm, buf.getvalue().encode())
        manifest[sid] = {
            "url": url, "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "raw_file": f"raw/{sid}.{ext}", "sha256_raw": hashlib.sha256(raw).hexdigest(),
            "rows": len(rows), "first": rows[0][0].isoformat(), "last": rows[-1][0].isoformat(),
        }
        write_atomic(manifest_path, json.dumps(manifest, indent=1).encode())
        print(f"OK    {sid}: {len(rows)} rows {rows[0][0]} .. {rows[-1][0]}")
    print(f"done: {len(todo) - len(failed)}/{len(todo)} valid" + (f"; FAILED {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
