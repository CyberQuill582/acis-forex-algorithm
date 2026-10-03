"""IMOM's real-data looks: the 2012-2023 kill tests of intraday momentum into the US500 close (GAP-P12D-158).

    python scripts/r1_imom_kill_test.py --minutes data/r1_real/dukascopy_minutes --dry-check   # P&L-blind
    python scripts/r1_imom_kill_test.py --minutes data/r1_real/dukascopy_minutes               # the two looks

Mental model (register-first: every refusal happens before any compute):
  * The book (`event_intraday.py`): on each NYSE session, hold sign(predictor) on US500 from 15:30 to
    16:00 New York, prices from the 1-minute BID/ASK candles, each side paying THE C8 model at its
    minute's spread; flat overnight. ROD = previous close -> 15:30 (Baltussen et al. 2021, eq. 2);
    ONFH = previous close -> 10:00 (Gao et al. 2018, eq. 1). Owner rulings 2026-10-03: ROD; v1a trades
    every session, v1b only top-third |ROD| days (trailing 250 sessions); both looks' lines precede both
    grades, and the forward rule is GAP-P12D-158's.
  * Its origin is the literature SELECTED by the 2026-10-01 research agent (claude-opus-5-5, web), so
    master §5.6 certifies a pass only after that date: this look can only KILL (HAC t < -0.5).
  * `--dry-check` reads no strategy return: sessions priced, skip reasons, the spreads at 15:30 and
    16:00 in basis points (the cost a trade pays), and the share of up predictors.
  * Every number goes to data/validation/r1_kill_test/imom.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest.evaluate_events import grade_event_look, register_event_look  # noqa: E402
from tests.backtest.event_intraday import session_prices, simulate_imom  # noqa: E402
from tests.backtest.look_claims import Claim, Origin, load_vector  # noqa: E402
from tests.backtest.look_declarations import Declaration  # noqa: E402
from tests.backtest.look_register import CANONICAL, LookRegister, git_state  # noqa: E402
from tests.backtest.rsim import annual_sharpe  # noqa: E402
from tests.backtest.rsim_real import CandleSource  # noqa: E402
from tests.backtest.verdict import KILL_T, kill_verdict  # noqa: E402

START, GRADED_FROM, END = date(2012, 1, 3), date(2012, 2, 1), date(2023, 12, 29)
TIMES = {"onfh": time(10, 0), "c30": time(15, 30), "close": time(16, 0)}
CORE = ("imom rod: hold sign(us500 previous close -> 15:30 new york) from 15:30 to the 16:00 close, flat "
        "overnight, 1-minute bid/ask prices, c8 costs at each side's spread")
VERSIONS = {"imom_v1a_rod_us500": (f"{CORE}; every nyse session", None),
            "imom_v1b_rod_us500_top": (f"{CORE}; only when |rod| reaches the top third of the trailing 250 sessions",
                                       2 / 3)}
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-01",
                exposure="web", reference="Baltussen, Da, Lammers & Martens, Hedging Demand and Market Intraday "
                "Momentum, JFE 142 (2021); Gao, Han, Li & Zhou, Market Intraday Momentum, JFE 129 (2018); selected "
                "by the 2026-10-01 research agent EDGE (S3)", published="2021-10-01")


class MinuteSource(CandleSource):
    name = "dukascopy-candles-minute"


def dry_check(sessions, predictor_key: str) -> dict:
    graded = [s for s in sessions if GRADED_FROM <= s.day <= END]
    reasons = Counter(next((k for k in ("c30", "close") if s.prices[k] is None), "priced") for s in graded)
    bp = lambda k: np.array([s.prices[k][1] / s.prices[k][0] * 1e4 for s in graded if s.prices[k]])  # noqa: E731
    ups = [s.prices[predictor_key][0] > p.prices["close"][0] for p, s in zip(graded, graded[1:])
           if p.prices["close"] and s.prices[predictor_key]]
    return {"sessions": len(graded), "priced": dict(reasons),
            "spread_bp_15_30": {"median": float(np.median(bp("c30"))), "p95": float(np.percentile(bp("c30"), 95))},
            "spread_bp_16_00": {"median": float(np.median(bp("close"))), "p95": float(np.percentile(bp("close"), 95))},
            "share_up_predictor": float(np.mean(ups))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--minutes", type=Path, required=True)
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    ap.add_argument("--dry-check", action="store_true", help="P&L-blind: prices, spreads and skips, no look")
    a = ap.parse_args(argv)
    with (a.macro / "spx_yahoo.csv").open(encoding="utf-8") as f:
        days = [d for d in (date.fromisoformat(r["date"]) for r in csv.DictReader(f)) if START <= d <= END]
    sessions = session_prices(a.minutes, "US500", days, "America/New_York", TIMES)
    if a.dry_check:
        print(json.dumps(dry_check(sessions, "c30"), indent=1))
        return 0
    cfg, reg = load_config(ROOT / "config"), LookRegister(CANONICAL)
    cost = cost_model(cfg, "US500")
    looks = {}
    for family, (formula, _) in VERSIONS.items():            # both lines first: no grade between them
        claim = Claim(family=family, variant="fixed", universe_id="R1-IMOM-US500", origin=ORIGIN, simulator="event",
                      declared_space={"grid": {}, "formula": formula, "instruments": ["US500"]},
                      recon_commit=git_state()[0], declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
        looks[family] = register_event_look(register=reg, cfg=cfg, source=MinuteSource(), claim=claim,
                                            account="research", instruments=("US500",), costs={"US500": cost},
                                            start=START, graded_from=GRADED_FROM, end=END)
    stressed = lambda s: cost.__class__(cost.commission_per_side, cost.slippage_per_side,   # noqa: E731
                                        stress=cost.stress * s, spread_floor=cost.spread_floor)
    vec = lambda h: np.asarray(load_vector(CANONICAL, h)[1])                       # noqa: E731
    out = {}
    for family, (look, fold) in looks.items():
        top = VERSIONS[family][1]
        grade_event_look(look, fold, register=reg, cfg=cfg, source=MinuteSource(), costs={"US500": cost},
                         graded_from=GRADED_FROM,
                         run=lambda s, top=top: simulate_imom(sessions, stressed(s), START, GRADED_FROM, END, "rod",
                                                              top=top),
                         benchmark=lambda: simulate_imom(sessions, None, START, GRADED_FROM, END, "rod",
                                                         side=lambda r: 1.0).daily,
                         summary=lambda r: {"sessions_skipped": len(r.skipped),
                                            "sessions_traded": int(np.count_nonzero(r.daily))})
        outcome, verdict = reg.outcome(look.look_id), kill_verdict(CANONICAL, look.look_id)
        out[family] = {"look_id": look.look_id, "certifying_boundary": look.claim["certifying_boundary"],
                       "graded_days": outcome["graded_days"], "sessions_traded": outcome["sessions_traded"],
                       "annual_sharpe": annual_sharpe(vec(outcome["daily_vector"])), "hac_t": verdict.hac_t,
                       "kill_rule": f"HAC t < {KILL_T}", "killed": verdict.killed,
                       "benchmark_annual_sharpe": annual_sharpe(vec(outcome["context"]["benchmark_vector"])),
                       "cost2x_annual_sharpe": annual_sharpe(vec(outcome["context"]["cost2x_vector"])),
                       "sessions_skipped": outcome["sessions_skipped"]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "imom.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
