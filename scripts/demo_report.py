"""The demo's forward-record report, read from the engine's own logs (TODO item 3; master v2.33).

    python scripts/demo_report.py --logs /opt/acis/repo/logs [--since 2026-10-15] [--out report.json]

Mental model (P&L-blind about the venue: it reads only what the engine logged):
  * REFUSALS: every daily decision's outcome (`TARGET_DECIDED` reasons), every slot skip
    (`TARGET_SLOT_SKIPPED`), every refused entry (`TARGET_ENTRY_ZERO`, the feed watch's and the
    guards' reasons) and every executed slot, counted by reason: where the book is held back.
  * THE SHADOW BOOK: the uncapped continuous position each decision logged (`shadow`, Carver's
    forecast/10 x average position at the demo's capital_ref and vol target), marked from one decision's
    close to the next: daily USD P&L = shadow(t-1) x (close(t) - close(t-1)) x q(t), summed over the
    instruments; swap-free (no carry), cost-free (an upper bound). It is the forward twin of the book
    RSIM grades, free of the one-lot cap, so stage D's daily series exists from the first decision.
  * It reports the shadow book's annualised Sharpe and realised volatility against the declared vol
    target (the realised-daily-vol report), and the count of decision days. Never a pass or a verdict.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _events(path: Path, kinds: set[str], since: str | None):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not any(f'"{k}"' in line for k in kinds):
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event_type") in kinds and (since is None or e.get("timestamp", "") >= since):
                yield e


def refusals(logs: Path, since: str | None) -> dict:
    out = {"decided": Counter(), "slot_skipped": Counter(), "entry_zero": Counter(), "executed": Counter()}
    for e in _events(logs / "target_log.jsonl", {"TARGET_DECIDED", "TARGET_SLOT_SKIPPED", "TARGET_EXECUTED"}, since):
        d, kind = e["data"], e["event_type"]
        key = {"TARGET_DECIDED": "decided", "TARGET_SLOT_SKIPPED": "slot_skipped", "TARGET_EXECUTED": "executed"}[kind]
        out[key][d.get("reason")] += 1
    for e in _events(logs / "governor_log.jsonl", {"TARGET_ENTRY_ZERO"}, since):
        out["entry_zero"][e["data"].get("reason")] += 1
    return {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in out.items()}


def shadow_book(logs: Path, since: str | None) -> dict:
    marks: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)     # day, shadow, close, q
    for e in _events(logs / "target_log.jsonl", {"TARGET_DECIDED"}, since):
        d = e["data"]
        if d.get("boot") or d.get("shadow") is None or d.get("close") is None or d.get("q") is None:
            continue
        rows = marks[d["instrument"]]
        if rows and rows[-1][0] == d["day"]:
            continue                                     # one mark per instrument per decision day
        rows.append((d["day"], float(d["shadow"]), float(d["close"]), float(d["q"])))
    daily: dict[str, float] = defaultdict(float)
    for rows in marks.values():
        for (_, units, c0, _), (day, _, c1, q1) in zip(rows, rows[1:]):
            daily[day] += units * (c1 - c0) * q1
    pnl = [daily[d] for d in sorted(daily)]
    n = len(pnl)
    mean = sum(pnl) / n if n else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in pnl) / (n - 1)) if n > 1 else 0.0
    return {"days": n, "total_usd": sum(pnl), "daily_usd": dict(sorted(daily.items())),
            "annual_sharpe": mean / sd * math.sqrt(252) if sd > 0 else None,
            "annual_vol_usd": sd * math.sqrt(252) if n > 1 else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logs", type=Path, required=True)
    ap.add_argument("--since", help="ISO date: count only events at or after it")
    ap.add_argument("--capital-ref", type=float, default=10_000.0, help="the demo's sizing capital (ACIS-05 v1.8)")
    ap.add_argument("--vol-target", type=float, default=0.20)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    book = shadow_book(a.logs, a.since)
    vol = book["annual_vol_usd"]
    report = {"refusals": refusals(a.logs, a.since), "shadow_book": {k: v for k, v in book.items() if k != "daily_usd"},
              "realised_vol_vs_target": None if vol is None else vol / (a.capital_ref * a.vol_target)}
    text = json.dumps(report, indent=1)
    print(text)
    if a.out:
        a.out.write_text(json.dumps({**report, "shadow_daily_usd": book["daily_usd"]}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
