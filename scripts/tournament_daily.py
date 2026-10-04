"""The tournament's daily job (TOURNAMENT, 2026-10-04): fetch, record each registered strategy's newly settled
forward days, re-check every recorded day, anchor.

    python scripts/tournament_daily.py --register --no-fetch       # once: the rule, then each new registry entry
    python scripts/tournament_daily.py                              # daily (deploy/forward/): fetch, then record
    python scripts/tournament_daily.py --anchor-repo /opt/acis/anchor --remote origin

Mental model:
  * REGISTER appends the promotion rule (tournament_rule.PARAMS) and every registry entry the record lacks.
    The record refuses an entry whose first exposure has passed: a late registration needs a later start.
  * RECORD, per active entry: its registry spec and the config's C8 costs must still be the registered
    ones (else RULE or COST DRIFT, and that strategy stops); its book runs on the frozen store; the days
    after its last recorded one, through its settled horizon, go into one `days` line with the store hash.
  * RECHECK: every recorded day is compared with that same recompute (to 1e-12). A difference or a skipped
    day becomes one `revision` line per value; the recorded value stands and the report flags it.
  * A book whose inputs are not settled yet (a gap, a stale rate, an unvetted calendar year) is skipped and
    logged; nothing is estimated. It never trades and never touches the engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from config.schemas import load_config  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from core.data.rates import StaleRateError  # noqa: E402
from forward_fetch import fetch_dukascopy, fetch_series, open_store  # noqa: E402
from tests.backtest.exchange_days import CalendarRefused as ExchangeRefused  # noqa: E402
from tests.backtest.forward_record import ForwardRecord, RecordRefused  # noqa: E402
from tests.backtest.forward_store import StoreGap  # noqa: E402
from tests.backtest.jp_days import CalendarRefused  # noqa: E402
from tests.backtest.look_claims import canonical_hash  # noqa: E402
from tests.backtest.rsim_real import SourceRefused  # noqa: E402
from tests.backtest.tournament_registry import BY_ID, REGISTRY  # noqa: E402
from tests.backtest.tournament_rule import PARAMS, rule_line  # noqa: E402

TOL = 1e-12
UNSETTLED = (StoreGap, StaleRateError, SourceRefused, CalendarRefused, ExchangeRefused)


def register(rec: ForwardRecord, now: datetime) -> list[str]:
    out, st = [], rec.state()
    if st.rule is None or (st.rule["rule_hash"] != canonical_hash(PARAMS) and not st.any_days):
        rec.append(rule_line(), now)
        out.append("rule")
    for s in REGISTRY:
        if s.sid not in rec.state().entries:
            try:
                rec.append(s.entry(), now)
                out.append(s.sid)
            except RecordRefused as e:
                out.append(f"{s.sid}: REFUSED: {e}")
    return out


def recheck(rec: ForwardRecord, sid: str, recorded: list[tuple[date, float]], series, now: datetime) -> int:
    """One revision line per recorded day whose recompute differs, or per day the record skipped."""
    fresh = dict(zip(series.dates, (float(v) for v in series.net)))
    seen = {(x["date"], x.get("recomputed")) for x in rec.scan().lines
            if x and x["kind"] == "revision" and x["strategy"] == sid}
    n, have = 0, dict(recorded)
    last = recorded[-1][0] if recorded else None
    todo = [(d, v, fresh.get(d)) for d, v in recorded if d <= series.horizon]
    todo += [(d, None, x) for d, x in fresh.items() if last and recorded[0][0] < d < last and d not in have]
    for d, v, x in todo:
        if (x is None or v is None or abs(x - v) > TOL) and (d.isoformat(), x) not in seen:
            reason = "skipped by the record" if v is None else "missing from the recompute" if x is None else "differs"
            rec.append({"kind": "revision", "strategy": sid, "date": d.isoformat(), "recorded": v, "recomputed": x,
                        "reason": reason}, now)
            n += 1
    return n


def record(rec: ForwardRecord, store, cfg, today: date, now: datetime) -> dict:
    st, summary = rec.state(), {}
    for sid, e in st.entries.items():
        if sid in st.retired:
            continue
        s = BY_ID.get(sid)
        why = "NOT ON THIS BRANCH: its book is not in the registry here" if s is None else s.drift(cfg, e)
        if why:
            summary[sid] = why
            continue
        try:
            series = s.book(store, cfg, s.forward_start, today)
        except UNSETTLED as err:
            summary[sid] = f"NOT SETTLED: {err}"[:240]
            continue
        recorded = st.days[sid]
        revisions = recheck(rec, sid, recorded, series, now)
        last = recorded[-1][0] if recorded else None
        new = [[d.isoformat(), float(v)] for d, v in zip(series.dates, series.net) if last is None or d > last]
        if new:
            rec.append({"kind": "days", "strategy": sid, "rows": new, "horizon": series.horizon.isoformat(),
                        "inputs": store.state_hash(), "meta": series.meta}, now)
        summary[sid] = {"new_days": len(new), "horizon": series.horizon.isoformat(), "revisions": revisions,
                        "recorded": len(recorded) + len(new)}
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", type=Path, default=ROOT / "data" / "forward" / "inputs")
    ap.add_argument("--staging", type=Path, default=ROOT / "data" / "forward" / "staging")
    ap.add_argument("--record", type=Path, default=ROOT / "data" / "forward" / "record")
    ap.add_argument("--archive", type=Path, default=ROOT / "data" / "r1_real")
    ap.add_argument("--register", action="store_true", help="append the rule and any new registry entry first")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--anchor-repo", type=Path, help="a git checkout whose remote takes the forward-anchor branch")
    ap.add_argument("--remote", default="origin")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    store, rec, cfg = open_store(a.store, a.archive), ForwardRecord(a.record), load_config(ROOT / "config")
    out = {"registered": register(rec, now) if a.register else []}
    if not a.no_fetch:
        out["fetch"] = {"dukascopy": fetch_dukascopy(store, a.staging, now.date(), now),
                        "series": fetch_series(store, now.date(), now)}
    out["record"] = record(rec, store, cfg, now.date(), datetime.now(timezone.utc))
    out["head"] = rec.scan().head
    if a.anchor_repo:
        out["anchor"] = rec.anchor(a.anchor_repo, a.remote)
    log = JsonlEventLogger(ROOT / "logs" / "tournament_log.jsonl", "research", f"tournament-{now:%Y%m%dT%H%M%SZ}")
    log.event("TOURNAMENT_DAILY", **out)
    log.close()
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
