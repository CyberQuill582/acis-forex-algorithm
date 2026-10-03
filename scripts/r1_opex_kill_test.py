"""OPEX's real-data looks: kill tests of US500 over the option-expiration week (GAP-P12D-158).

    python scripts/r1_opex_kill_test.py --dry-check        # P&L-blind
    python scripts/r1_opex_kill_test.py --line v1          # v1a and v1b, both registered before either grade

Mental model (register-first: every refusal happens before any compute):
  * The book (`opex.py` on `event_daily.simulate_daily`): US500 long from the last S&P cash close before the
    week of the month's third Friday to that week's last close (Stivers & Sun 2013's weekly returns, the
    S&P 500 index 1983-2008). v1a is flat otherwise; v1b, the CONTRAST, is short the other weeks at the
    calendar's ratio, so the equity premium nets out and only an OE-week excess can earn. Swap-free.
  * DECLARED departures: the US500 CFD at its anchored cash close for the S&P 500 index's close; C8 costs.
  * WINDOW ROLES, fixed before any look (owner, "fix that", GAP-P12D-158): the practitioner backtests that
    selected OPEX cover 2015-2024, so 2015-2023 was seen by the selection; 2012-2014 is the only clean
    history. The outcome reports both segments; a pass on seen years is non-evidence, and kills still kill.
  * The benchmark is the passive long on the same marks (context only). Its origin is the literature
    PROPOSED by this session's lead (claude-opus-5-5, web) on 2026-10-03: kill-only (HAC t < -0.5).
  * `--dry-check` reads no strategy return; every look's numbers go to data/validation/r1_kill_test/.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.event_daily import quoted, simulate_daily  # noqa: E402
from tests.backtest.event_sim import Leg  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.opex import oe_week, segments, target, third_friday  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2012, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
SEEN_FROM = date(2015, 1, 1)                      # the selecting practitioner backtests begin (window roles)
CORE = ("opex: us500 long from the last s&p cash close before the week of the month's third friday to that "
        "week's last close, anchored cash closes, c8 costs on each change of units, swap-free")


@dataclass(frozen=True)
class Version:
    formula: str
    contrast: bool


LINES = {"v1": {"opex_v1a_week": Version(f"{CORE}; flat in the other weeks", False),
                "opex_v1b_contrast": Version(f"{CORE}; short the other weeks at minus (oe holds / other holds) "
                                             "on the calendar, so a constant drift nets to zero", True)}}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-03",
                exposure="web", reference="Stivers & Sun, Returns and option activity over the option-expiration "
                "week for S&P 100 stocks, Journal of Banking & Finance 37(11) (2013) 4226-4240; proposed by the "
                "lead 2026-10-03 (GAP-P12D-158)", published="2013-11-01")


def _spx(path: Path) -> dict[date, float]:
    with path.open(encoding="utf-8") as f:
        return {date.fromisoformat(r["date"]): float(r["value"]) for r in csv.DictReader(f)}


def dry_check(days, us500) -> dict:
    graded = [d for d in days if GRADED_FROM <= d <= END]
    t = target(days)
    leg = Leg(quoted(us500), np.zeros(1, np.int64))
    held = [d for s, d in enumerate(days) if GRADED_FROM <= d <= END and t[s] == 1.0]
    anchors = [leg.anchor("XNYS", d) for d in graded]
    spreads = [leg.spreads[j] / leg.closes[j] * 1e4 for j in anchors if j is not None]
    months = sorted({(d.year, d.month) for d in graded})
    moved = [f"{y}-{m:02d}" for y, m in months if third_friday(y, m) not in set(days)]
    return {"sessions": len(graded), "oe_weeks": len({(d.year, d.month) for d in graded if oe_week(d)}),
            "sessions_held_v1a": len(held), "expiry_friday_closed": moved,
            "contrast_short_size": float(-target(days, contrast=True).min()),
            "sessions_without_anchor": sum(j is None for j in anchors),
            "anchor_spread_bp": {"median": float(np.median(spreads)), "p95": float(np.percentile(spreads, 95))}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: weeks, sessions, anchors, spreads, no look")
    ap.add_argument("--line", choices=sorted(LINES), help="the registered line to look at (required for a look)")
    a = ap.parse_args(argv)
    spx = _spx(a.macro / "spx_yahoo.csv")
    days = [d for d in sorted(spx) if START <= d <= END]
    us500 = load(a.candles, "US500", (END.year, END.month))
    if a.dry_check:
        print(json.dumps(dry_check(days, us500), indent=1))
        return 0
    if a.line is None:
        ap.error("a look needs --line")
    versions, cfg, reg = LINES[a.line], load_config(ROOT / "config"), LookRegister(CANONICAL)
    cost = cost_model(cfg, "US500")
    looks = {}
    for family, v in versions.items():                       # every line first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-OPEX-US500", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": v.formula, "instruments": ["US500"]},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=CandleSource(), claim=claim,
                                            account="research", instruments=("US500",), costs={"US500": cost},
                                            start=START, graded_from=GRADED_FROM, end=END)
    stressed = lambda s: cost.__class__(cost.commission_per_side, cost.slippage_per_side,  # noqa: E731
                                        stress=cost.stress * s, spread_floor=cost.spread_floor)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    out = {}
    for family, (look, fold) in looks.items():
        pos = target(days, versions[family].contrast)
        grade_event_look(look, fold, register=reg, cfg=cfg, source=CandleSource(), costs={"US500": cost},
                         graded_from=GRADED_FROM,
                         run=lambda s, pos=pos: simulate_daily(us500, days, pos, stressed(s), START, GRADED_FROM, END),
                         benchmark=lambda: simulate_daily(us500, days, np.ones(len(days)), None, START, GRADED_FROM,
                                                          END).daily,
                         summary=lambda r: {"sessions_skipped": len(r.skipped),
                                            "segments": segments(r, [SEEN_FROM], GRADED_FROM)})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])),
                       "hac_t": verdict.hac_t, "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "benchmark_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "sessions_skipped": outcome["sessions_skipped"], "segments": outcome["segments"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"opex_{a.line}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
