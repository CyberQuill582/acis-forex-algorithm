"""HALLOWEEN's one real-data look: the "Sell in May" contrast on one index per country (FACTORY, GAP-P12D-158).

    python scripts/r1_halloween_kill_test.py --dry-check    # P&L-blind: sessions, switches, spreads, ex-ante cost
    python scripts/r1_halloween_kill_test.py --look         # the ONE look, kill-only (HAC t < -0.5)

Mental model (register-first; owner pre-authorisation 2026-10-03: one pre-declared version, one look):
  * Position `halloween.py`: long November-April, short May-October, sized at each switch to LEG_RISK over
    the trailing vol, each index traded at its own cash close (`event_multi.book`), C8 costs, swap-free.
    The paper holds bills in summer; the contrast shorts instead, so the equity premium nets out (OPEX's
    lesson: a long-only calendar book is mostly beta).
  * DECLARED departures: the CFD's anchored mid for each country's index; US500, UK100, EU50, JP225 and
    AUS200 for the paper's 37 market indexes (the Dow is left out as the S&P 500's subset).
  * WINDOW ROLES: Bouman & Jacobsen's sample ends 1998 and Andrade et al.'s out-of-sample test 2012, so
    2012 was seen and 2013-2023 is after both; the outcome reports 2012 and 2013-2023 as segments.
  * EXPECTED CORRELATION, before the look: about 0 with D1-FX13, REBAL v1a and GOTOBI v1a (a half-year
    calendar position against daily, contrarian and intraday ones).
  * The origin is the literature SELECTED by FACTORY (claude-opus-5-5, web) on 2026-10-04: kill-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest import halloween  # noqa: E402
from tests.backtest.candle_store import load  # noqa: E402
from tests.backtest.event_multi import book, passive_targets, sessions  # noqa: E402
from tests.backtest.factory_looks import END, GRADED_FROM, claim, context, event_look  # noqa: E402
from tests.backtest.look_claims import Origin  # noqa: E402

FAMILY, UNIVERSE = "halloween_v1_contrast", "R1-HALLOWEEN-5IDX"
NAMES = ("US500", "UK100", "EU50", "JP225", "AUS200")
START, SEEN_UNTIL = date(2012, 1, 2), date(2013, 1, 1)
FORMULA = ("halloween: each index at its own cash-close anchor holds +0.01/sigma when the session held into is in "
           "november-april and -0.01/sigma in may-october, sigma the sd of the last 60 session returns read at the "
           "season's first position and held to the next switch; c8 costs, swap-free, flat before 2012-02-01")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                exposure="web", reference="Bouman & Jacobsen, The Halloween indicator, American Economic Review 92(5) "
                "(2002) 1618-1635; out of sample Andrade, Chhaochharia & Fuerst, Financial Analysts Journal 69(4) "
                "(2013); selected by FACTORY 2026-10-04 (GAP-P12D-158)", published="2002-12-01")
EX_ANTE = {"andrade_2013_oos_1998_2012": "November-April beat May-October in all 37 markets, by about 10 "
           "percentage points a half-year", "contrast_gross_per_year_at_unit_notional": 0.10}


def dry_check(legs, cfg) -> dict:
    out = {}
    for n, s in legs.items():
        graded = np.array([GRADED_FROM <= d <= END for d in s.days])
        t = np.nan_to_num(halloween.target(s))[graded]
        side = np.array([cost_model(cfg, n).per_side_cost(sp) / p for sp, p in zip(s.spreads[graded], s.closes[graded])])
        years = graded.sum() / 252.0
        changes = np.abs(np.diff(np.r_[0.0, t]))
        out[n] = {"sessions": int(graded.sum()), "trades": int((changes > 0).sum()),
                  "median_anchor_spread_bp": float(np.median(s.spreads[graded] / s.closes[graded]) * 1e4),
                  "mean_abs_position": float(np.mean(np.abs(t))), "annual_cost": float(np.sum(changes * side) / years),
                  "ex_ante_annual_gross": float(EX_ANTE["contrast_gross_per_year_at_unit_notional"] * np.mean(np.abs(t)))}
    return out | {"ex_ante": EX_ANTE}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-check", action="store_true")
    g.add_argument("--look", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(ROOT / "config")
    legs = {n: sessions(load(a.candles, n, (END.year, END.month)), n, START, END) for n in NAMES}
    if a.dry_check:
        print(json.dumps(dry_check(legs, cfg), indent=1))
        return 0
    costs, targets = {n: cost_model(cfg, n) for n in NAMES}, {n: halloween.target(s) for n, s in legs.items()}
    look_id = event_look(cfg=cfg, cl=claim(FAMILY, FORMULA, NAMES, UNIVERSE, ORIGIN, "event"), costs=costs, start=START,
                         run=lambda c: book(legs, targets, c, START, GRADED_FROM, END),
                         benchmark=lambda: book(legs, passive_targets(legs), None, START, GRADED_FROM, END),
                         summary={"sessions": {n: len(s.days) for n, s in legs.items()}})
    out = context(look_id, [SEEN_UNTIL]) | {"family": FAMILY, "instruments": list(NAMES)}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "halloween.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
