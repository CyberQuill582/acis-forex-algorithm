"""Independent validation checks of the Dukascopy tick archive (GAP-P12D-14, owner-approved
2026-09-13). HistData's FX ticks are Dukascopy's own (GAP-P12D-13), so these checks use
sources and structure that Dukascopy does not control:

  1. ECB   — Dukascopy mid at the ECB's 14:15-Frankfurt concertation vs the published euro
             reference rate (USD pairs via the ECB's own crosses), every TARGET business day.
  2. TRIANGLE — EUR/GBP must equal EUR/USD ÷ GBP/USD at the same instant (hourly samples).
  3. STRUCTURE — the market's own clock marks: no ticks inside the FX weekend; the spread
             spike at the REAL 17:00-New-York rollover (vs one hour early/late); gold's
             daily 17:00–18:00 New-York break; the tick burst at the REAL 08:30-New-York
             US jobs report. A timestamp shifted by an hour fails the early/late comparison.

Everything here FLAGS for investigation and never averages or edits the data (C-BT-9).
`day_metrics` runs per instrument-day (worker processes); `summarise_*` aggregate.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

from core.data.fx_clock import local_to_utc, rollover_utc
from tests.backtest.validation_ticks import DayTicks

FX = ("EUR_USD", "GBP_USD", "AUD_USD", "USD_CHF", "USD_CAD", "EUR_GBP", "USD_JPY")
TRIANGLE = ("EUR_USD", "GBP_USD", "EUR_GBP")
ECB_FLAG_BPS = 25.0            # |Dukascopy − ECB| worth a human look
TRIANGLE_SLACK_BPS = 2.0       # beyond the three quotes' combined half-spreads
_H = timedelta(hours=1)
_M = timedelta(minutes=1)

# ACIS instrument -> its price from the ECB's per-EUR rates (currency -> units per 1 EUR)
ECB_PRICE = {
    "EUR_USD": lambda r: r["USD"],
    "EUR_GBP": lambda r: r["GBP"],
    "GBP_USD": lambda r: r["USD"] / r["GBP"],
    "AUD_USD": lambda r: r["USD"] / r["AUD"],
    "USD_JPY": lambda r: r["JPY"] / r["USD"],
    "USD_CHF": lambda r: r["CHF"] / r["USD"],
    "USD_CAD": lambda r: r["CAD"] / r["USD"],
}
ECB_NEEDS = {"EUR_USD": ("USD",), "EUR_GBP": ("GBP",), "GBP_USD": ("USD", "GBP"),
             "AUD_USD": ("USD", "AUD"), "USD_JPY": ("USD", "JPY"),
             "USD_CHF": ("USD", "CHF"), "USD_CAD": ("USD", "CAD")}


def ecb_fixing_utc(d: date) -> datetime:
    """14:15 Frankfurt; Frankfurt is always London + 1 h (same EU summer-time dates)."""
    return local_to_utc(d, "14:15", "Europe/London") - _H


def _mid(q: tuple[float, float]) -> float:
    return (q[0] + q[1]) / 2.0


def _median_ratio(num: list[float], den: list[float]) -> float | None:
    if not num or not den:
        return None
    base = statistics.median(den)
    return statistics.median(num) / base if base > 0 else None


def day_metrics(root: Path, instrument: str, d: date, rates: dict[str, float] | None) -> dict:
    """All per-day facts the checks need, from ONE decompression of the day file.
    `rates` is the ECB's {currency: units per EUR} for `d`, or None if not a fixing day."""
    t = DayTicks(root, instrument, d)
    out: dict = {"instrument": instrument, "day": d.isoformat(), "ticks": len(t)}
    if not len(t):
        return out
    wd = d.weekday()                                          # Mon=0 … Sun=6
    start, end = t.start, t.start + 24 * _H
    roll = rollover_utc(d)
    out["weekend_ticks"] = (len(t) if wd == 5 else t.count(roll, end) if wd == 4
                            else t.count(start, roll) if wd == 6 else 0)

    if rates is not None and instrument in ECB_PRICE and all(c in rates for c in ECB_NEEDS[instrument]):
        q = t.last_at_or_before(ecb_fixing_utc(d), max_age_s=120)
        if q is not None:
            ref = ECB_PRICE[instrument](rates)
            out["ecb_bps"] = (_mid(q) - ref) / ref * 1e4

    if instrument in TRIANGLE and wd < 5:
        out["hourly"] = {h: t.last_at_or_before(start + h * _H, max_age_s=5) for h in range(1, 21)}

    if wd in (0, 1, 2, 3):                                    # a trading day follows each roll
        marks = {"true": roll, "early": roll - _H, "late": roll + _H}
        if instrument == "XAU_USD":                           # the daily break starts at the roll
            out["gold_break"] = {k: t.count(m, m + _H) for k, m in marks.items()}
        else:
            out["roll_spread"] = {k: _median_ratio(t.spreads(m, m + 5 * _M), t.spreads(m - 65 * _M, m - 5 * _M))
                                  for k, m in marks.items()}

    if wd == 4 and d.day <= 7 and ("USD" in instrument or instrument == "XAU_USD"):
        nfp = local_to_utc(d, "08:30", "America/New_York")
        out["nfp_burst"] = {k: t.count(m, m + 5 * _M) / max(1, t.count(m - 10 * _M, m - 5 * _M))
                            for k, m in {"true": nfp, "early": nfp - _H, "late": nfp + _H}.items()}
    return out


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def _medians(days: list[dict], key: str) -> dict[str, float] | None:
    rows = [r[key] for r in days if key in r]
    if not rows:
        return None
    out = {}
    for label in ("true", "early", "late"):
        vals = [row[label] for row in rows if row.get(label) is not None]
        if vals:
            out[label] = round(statistics.median(vals), 3)
    return out | {"days": len(rows)}


def summarise_instrument_year(days: list[dict]) -> dict:
    """One instrument-year: ECB agreement, weekend leakage, and the clock-mark comparisons.
    `flags` lists what needs a human look; an empty list means every check passed."""
    inst, year = days[0]["instrument"], days[0]["day"][:4]
    s: dict = {"instrument": inst, "year": int(year), "day_files_with_ticks": sum(1 for r in days if r["ticks"]),
               "ticks": sum(r["ticks"] for r in days), "flags": []}
    ecb = [(r["day"], r["ecb_bps"]) for r in days if "ecb_bps" in r]
    if ecb:
        absb = [abs(b) for _, b in ecb]
        s["ecb"] = {"days": len(ecb), "median_bps": round(statistics.median(absb), 2),
                    "p95_bps": round(_pct(absb, 0.95), 2), "max_bps": round(max(absb), 2),
                    "over_flag": [(d, round(b, 1)) for d, b in ecb if abs(b) > ECB_FLAG_BPS]}
        if s["ecb"]["over_flag"]:
            s["flags"].append(f"ECB: {len(s['ecb']['over_flag'])} day(s) > {ECB_FLAG_BPS} bps")
    elif inst in ECB_PRICE:
        s["flags"].append("ECB: no comparable fixing days")

    weekend = sum(r.get("weekend_ticks", 0) for r in days)
    s["weekend_ticks"] = weekend
    if weekend:
        s["flags"].append(f"WEEKEND: {weekend} tick(s) inside the FX weekend window")

    roll = _medians(days, "roll_spread")
    if roll:
        s["roll_spread"] = roll
        true, other = roll.get("true", 0), max(roll.get("early", 0), roll.get("late", 0))
        if not (true >= 1.5 and true >= 1.5 * other):
            s["flags"].append(f"CLOCK: rollover spread spike not at 17:00 New York ({roll})")
    gold = _medians(days, "gold_break")
    if gold:
        s["gold_break"] = gold
        if not gold.get("true", 0) <= 0.2 * max(1.0, gold.get("early", 0)):
            s["flags"].append(f"CLOCK: gold daily break not at 17:00–18:00 New York ({gold})")
    nfp = _medians(days, "nfp_burst")
    if nfp:
        s["nfp_burst"] = nfp
        if not nfp.get("true", 0) > max(nfp.get("early", 0), nfp.get("late", 0)):
            s["flags"].append(f"CLOCK: jobs-report burst not at 08:30 New York ({nfp})")
    return s


def triangle_samples(eurusd: dict, gbpusd: dict, eurgbp: dict, day: str) -> list[dict]:
    """Per-hour EUR/GBP consistency for one day's `hourly` quotes of the three pairs."""
    out = []
    for h, qx in eurgbp.items():
        qa, qb = eurusd.get(h), gbpusd.get(h)
        if not (qa and qb and qx):
            continue
        implied = _mid(qa) / _mid(qb)
        dev = (_mid(qx) - implied) / implied * 1e4
        tol = sum((q[1] - q[0]) / _mid(q) * 1e4 / 2 for q in (qa, qb, qx)) + TRIANGLE_SLACK_BPS
        out.append({"day": day, "hour": h, "dev_bps": dev, "tol_bps": tol, "flagged": abs(dev) > tol})
    return out


def summarise_triangle(samples: list[dict], year: int) -> dict:
    devs = [abs(x["dev_bps"]) for x in samples]
    bad = [x for x in samples if x["flagged"]]
    s = {"year": year, "samples": len(samples), "flags": []}
    if devs:
        s |= {"median_bps": round(statistics.median(devs), 2), "p99_bps": round(_pct(devs, 0.99), 2),
              "flagged": len(bad),
              "examples": [(x["day"], x["hour"], round(x["dev_bps"], 1)) for x in bad[:5]]}
        if len(bad) > 0.01 * len(samples):
            s["flags"].append(f"TRIANGLE: {len(bad)}/{len(samples)} hourly samples outside spread tolerance")
    else:
        s["flags"].append("TRIANGLE: no aligned samples")
    return s
