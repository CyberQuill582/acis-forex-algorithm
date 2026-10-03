"""D3's real-data look: the 2012-2023 kill test of the turn-of-month index long (GAP-P12D-154).

    python scripts/r1_d3_kill_test.py --candles data/r1_real/dukascopy_candles --dry-check   # P&L-blind
    python scripts/r1_d3_kill_test.py --candles data/r1_real/dukascopy_candles               # the one look

Mental model (register-first: every refusal happens before any compute):
  * D3 v1 (owner ruling 2026-10-03, "Papers' window"): each of the six explored indices is held long in
    its own market from the cash close of T-2 to that of T+3 (McConnell & Xu's [-1, +3]), equal risk,
    swap-free, the declared C8 costs plus each anchor hour's quoted spread (`event_sim`).
  * Its origin is the literature SELECTED by the cloud lead's R1 plan (claude-opus-5-5, web, 2026-09-25),
    so master §5.6 certifies a pass only after that date: this look can only KILL. It names no cycle,
    spends no alpha, and `verdict.kill_verdict` kills at a HAC t below -0.5 on the net daily series.
  * `--dry-check` reads no return: per index, the graded turns, their anchors' local hours and the
    turns without an anchor, so the timing is checked on the real candles before the look.
  * The look writes its line (pushed to the GitHub anchor), consumes it, grades, chains the outcome and
    writes every number and event to data/validation/r1_kill_test/d3.json. A kill drops D3; a survival
    credits nothing and returns the shelved index onboarding (GAP-P12D-27) to the queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.evaluate_events import evaluate_events  # noqa: E402
from tests.backtest.event_sim import HOME, Leg, marks, turns  # noqa: E402
from tests.backtest.exchange_days import SESSION  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.universe import EXPLORED  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

FAMILY = "tom_d3_v1"
FORMULA = ("d3: long each index in its own market from the cash close of t-2 to the cash close of t+3 "
           "(exchange calendars), equal risk 1% over 60-mark vol, swap-free")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-09-25",
                exposure="web", reference="McConnell & Xu, Equity Returns at the Turn of the Month, FAJ 64(2) "
                "2008; Etula, Rinne, Suominen & Vaittinen, Dash for Cash, RFS 33(1) 2020; selected by the "
                "cloud lead's PLAN_R1 (D3)", published="2008-03-01")
START, GRADED_FROM, END = date(2012, 1, 2), date(2012, 4, 2), date(2023, 12, 29)
NAMES = tuple(sorted(HOME))


def dry_check(hourly) -> dict:
    """Per index: graded turns, anchors found, and the local hour each anchor hour starts (no returns)."""
    stamps = np.array([t for _, t in marks(START, END)], np.int64)
    out = {}
    for name, h in hourly.items():
        leg, exchange = Leg(h, stamps), HOME[name]
        tz = ZoneInfo(SESSION[exchange][0])
        hours, missing, graded = Counter(), [], turns(exchange, GRADED_FROM, END)
        for t2, t3 in graded:
            for side, d in (("entry", t2), ("exit", t3)):
                j = leg.anchor(exchange, d)
                if j is None:
                    missing.append(f"{side} {d}")
                else:
                    hours[datetime.fromtimestamp(int(leg.starts[j]), tz).strftime("%H:%M")] += 1
        out[name] = {"exchange": exchange, "graded_turns": len(graded), "first_data": datetime.fromtimestamp(
            int(leg.starts[0]), tz).date().isoformat(), "anchor_hour_starts": dict(hours), "no_anchor": missing}
    return out


def report(look, verdict, result) -> dict:
    outcome = LookRegister(CANONICAL).outcome(look.look_id)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                 # noqa: E731
    daily, ctx = vec(outcome["daily_vector"]), outcome["context"]
    return {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"], "cycle": look.cycle,
            "graded": [look.start, look.end], "graded_days": outcome["graded_days"], "events": outcome["events"],
            "skipped": outcome["skipped"], "annual_sharpe": annual_sharpe(daily), "hac_t": verdict.hac_t,
            "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
            "benchmark_annual_sharpe": annual_sharpe(vec(ctx["benchmark_vector"])),
            "cost2x_annual_sharpe": annual_sharpe(vec(ctx["cost2x_vector"])),
            "per_index": outcome["per_index"], "event_list": list(result.events), "skipped_list": list(result.skipped)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: anchors and counts only, no look")
    ap.add_argument("--changed", default="", help="what changed since the family's last look (the register asks)")
    a = ap.parse_args(argv)
    if not set(NAMES) <= set(EXPLORED):
        raise SystemExit("D3 grades explored indices only (GER40 and US100 are held out)")
    hourly = {n: load(a.candles, n, (END.year, END.month)) for n in NAMES}
    if a.dry_check:
        print(json.dumps(dry_check(hourly), indent=1))
        return 0
    cfg = load_config(ROOT / "config")
    claim = Claim(family=FAMILY, variant="fixed", universe_id="R1-D3-6", origin=ORIGIN, simulator="event",
                  declared_space={"grid": {}, "formula": FORMULA, "instruments": list(NAMES)},
                  recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
    look, result = evaluate_events(register=LookRegister(CANONICAL), cfg=cfg, source=CandleSource(), family=FAMILY,
                                   claim=claim, account="research", hourly=hourly,
                                   costs={n: cost_model(cfg, n) for n in NAMES}, start=START,
                                   graded_from=GRADED_FROM, end=END, changed=a.changed)
    out = report(look, kill_verdict(CANONICAL, look.look_id), result)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "d3.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if not k.endswith("_list")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
