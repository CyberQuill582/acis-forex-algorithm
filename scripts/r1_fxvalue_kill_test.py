"""FXVALUE's one real-data look: currency value against PPP on the six dollar pairs (FACTORY, GAP-P12D-158).

    python scripts/r1_fxvalue_kill_test.py --dry-check      # P&L-blind: ranks, turnover, spreads, ex-ante cost
    python scripts/r1_fxvalue_kill_test.py --look           # the ONE look, kill-only (HAC t < -0.5)

Mental model (register-first; owner pre-authorisation 2026-10-03: one pre-declared version, one look):
  * Signal `fx_value.py` (AMP 2013, ranked over USD and six currencies, monthly), graded by RSIM on the
    six dollar pairs: 17:00 New York decisions, 08:00 fills, $1M, 20% vol target, IDM 1, equal weights,
    the house 10% buffer, swap-free, C8 costs plus each fill's quoted spread.
  * DECLARED departures: 7 currencies, not 10 (NZD is held out, NOK and SEK not in the universe); spot
    only, no interest leg (swap-free); ECB fixings and current-vintage CPI read 4 months late; RSIM's
    risk-weighted pairs for the paper's notional ranks, so the dollar leg is only roughly neutral.
  * WINDOW ROLES: AMP's sample ends 2011-07; the century study the slate cites (Ilmanen et al. 2021)
    covers to 2020, so 2012-2020 was seen and 2021-2023 is reported as its own segment.
  * EXPECTED CORRELATION, before the look: D1-FX13 about -0.2 (AMP's currency value-momentum -0.42);
    REBAL v1a and GOTOBI v1a about 0. Measured afterwards from the stored vectors, as context.
  * The origin is the literature SELECTED by FACTORY (claude-opus-5-5, web) on 2026-10-04: kill-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.schemas import load_config  # noqa: E402
from core.optimizer.costs import cost_model  # noqa: E402
from tests.backtest import fx_value  # noqa: E402
from tests.backtest.factory_looks import END, claim, context, rsim_look  # noqa: E402
from tests.backtest.financing import load_rate_table  # noqa: E402
from tests.backtest.look_claims import Origin  # noqa: E402
from tests.backtest.rsim import BookSpec  # noqa: E402
from tests.backtest.rsim_lab import carver_pct_vol  # noqa: E402
from tests.backtest.rsim_real import build  # noqa: E402

FAMILY, UNIVERSE = "fxvalue_v1_ppp", "R1-FXVALUE-6USD"
NAMES = ("AUD_USD", "EUR_USD", "GBP_USD", "USD_CAD", "USD_CHF", "USD_JPY")
START, FIRST, SEEN_UNTIL = date(2012, 1, 2), (2012, 1), date(2021, 1, 1)
FORMULA = ("fxvalue: monthly, rank usd eur jpy gbp aud cad chf by log(mean daily ecb usd-per-unit spot over months "
           "m-65..m-54 / last fixing of m) - (5-year log cpi change of the currency - of the us, cpi read at m-4 "
           "and m-64); forecast on each dollar pair 5 x (rank - 4), negated for usd_xxx, held through month m+1; "
           "rsim 17:00 new york decisions, swap-free")
ORIGIN = Origin("literature", model_id="claude-opus-5-5", model_cutoff="2026-06-30", proposed="2026-10-04",
                exposure="web", reference="Asness, Moskowitz & Pedersen, Value and momentum everywhere, Journal of "
                "Finance 68(3) (2013) 929-985; selected by FACTORY 2026-10-04 (GAP-P12D-158)", published="2013-06-01")
EX_ANTE = {"source_currency_value_factor": {"sharpe": 0.44, "mean": 0.039, "sd": 0.090, "sample": "1979-01..2011-07",
                                            "returns": "forward (spot plus the interest differential)"}}


def _inputs(root: Path) -> dict:
    return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in ("ecb_daily.csv", "bis_cpi.csv")}


def dry_check(m, f, cfg) -> dict:
    graded = np.array([d >= date(2012, 2, 1) for d in m.days])
    fg = f[graded]
    month_rows = [k for k in range(1, len(fg)) if not np.array_equal(fg[k], fg[k - 1])]
    years = (m.days[-1] - date(2012, 2, 1)).days / 365.25
    turnover = float(np.abs(np.diff(fg, axis=0)).sum(axis=0).mean() / 10.0 / years)   # units of A per year
    out = {"decision_days": int(graded.sum()), "signal_changes": len(month_rows),
           "mean_abs_forecast": float(np.nanmean(np.abs(fg))), "forecast_turnover_A_per_year": turnover}
    spreads, cost_sr = {}, {}
    for i, n in enumerate(m.names):
        bp = m.spread[graded, i] / m.fill[graded, i] * 1e4
        cm = cost_model(cfg, n)
        side_bp = float(np.median([cm.per_side_cost(s) / p * 1e4 for s, p in zip(m.spread[graded, i], m.fill[graded, i])]))
        vol = float(np.std(np.diff(np.log(m.close[graded, i])), ddof=1) * np.sqrt(252))
        spreads[n] = {"median_spread_bp": float(np.median(bp)), "median_c8_side_bp": side_bp, "annual_vol": vol}
        cost_sr[n] = turnover * side_bp * 1e-4 / vol                  # forecast trades only; the buffer's vol trades add a little
    out.update(spreads=spreads, ex_ante_cost_sharpe=cost_sr, ex_ante=EX_ANTE)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candles", type=Path, default=ROOT / "data" / "r1_real" / "dukascopy_candles")
    ap.add_argument("--macro", type=Path, default=ROOT / "data" / "r1_real" / "macro")
    ap.add_argument("--inputs", type=Path, default=ROOT / "data" / "r1_real" / "fx_value")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "validation" / "r1_kill_test")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-check", action="store_true")
    g.add_argument("--look", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(ROOT / "config")
    spot, cpi = fx_value.load_spot(a.inputs / "ecb_daily.csv"), fx_value.load_cpi(a.inputs / "bis_cpi.csv")
    m = build(a.candles, NAMES, load_rate_table(a.macro), START, END, tier="development").market
    f = fx_value.panel(m.days, m.names, spot, cpi, FIRST)
    if a.dry_check:
        print(json.dumps(dry_check(m, f, cfg) | {"inputs": _inputs(a.inputs)}, indent=1))
        return 0
    spec = BookSpec(costs={n: cost_model(cfg, n) for n in m.names}, capital=1_000_000.0, vol_target=0.20, idm=1.0,
                    buffer=cfg.system.targets.buffer, world="swap_free")
    look_id = rsim_look(cfg=cfg, cl=claim(FAMILY, FORMULA, m.names, UNIVERSE, ORIGIN, "rsim"), market=m,
                        forecast=f, pct_vol=carver_pct_vol(m), spec=spec)
    out = context(look_id, [SEEN_UNTIL]) | {"family": FAMILY, "inputs": _inputs(a.inputs)}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "fxvalue.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
