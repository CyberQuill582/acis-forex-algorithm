"""Master §5.6's cost filters on the REAL candles, per instrument and member (GAP-P12D-136, R1.3).

P&L-BLIND: it reads spreads at each symbol's execution slot and Carver's volatility, never a
return a rule earned, so it spends no real-data look. Development tier only (2012-2023).

  * Cost per trade, SR = the median over decision days of per-side cost / (daily price vol x 16),
    per-side cost = half the quoted spread at the fill + a DECLARED commission per side (two
    scenarios: none, and $3.5 per 100k notional on FX and metals, 0 on indices: Pepperstone
    Razor-like, until the swap-free venue is picked); daily price vol = Carver's normaliser x close.
  * Swap: the owner ruled the SWAP-FREE world (2026-10-02), where the swap filter is 0 and admits;
    FTMO's markup world is reported beside it for reference (annual vol = median normaliser x 16).

    python scripts/r1_admission.py --candles /opt/acis/data/dukascopy_candles --macro /opt/acis/data/macro \\
        --out data/validation/r1_admission
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.backtest.cost_filters import MEMBER_INPUTS, admit, filter_turnover  # noqa: E402
from tests.backtest.financing import load_rate_table  # noqa: E402
from tests.backtest.rsim_lab import carver_pct_vol  # noqa: E402
from tests.backtest.rsim_real import build  # noqa: E402
from tests.backtest.swaps import load_ftmo  # noqa: E402
from tests.backtest.universe import BY_NAME, EXPLORED  # noqa: E402

COMMISSION_BP = {"none": {"fx": 0.0, "metal": 0.0, "index": 0.0},
                 "razor_like": {"fx": 0.35, "metal": 0.35, "index": 0.0}}
WARMUP = 260


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candles", required=True)
    ap.add_argument("--macro", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    names = [n for n in EXPLORED if BY_NAME[n].asset_class != "energy"]
    real = build(Path(a.candles), names, load_rate_table(Path(a.macro)), date(2012, 1, 2), date(2023, 12, 29),
                 tier="development")
    m, pct = real.market, carver_pct_vol(real.market)
    ftmo, rows = load_ftmo(), []
    for i, n in enumerate(names):
        live = slice(real.first_valid[n] + WARMUP, None)
        close, spread, fill, vol = m.close[live, i], m.spread[live, i], m.fill[live, i], pct[live, i]
        ok = np.isfinite(vol) & (vol > 0)
        daily_vol_price = vol[ok] * close[ok]
        annual_vol_pct = float(np.median(vol[ok])) * 16.0 * 100.0
        markup = ftmo.entry(n).markup_pct(float(np.median(close[-260:]))) if n in ftmo.entries else float("nan")
        row = {"instrument": n, "class": BY_NAME[n].asset_class, "days": int(ok.sum()),
               "median_spread_bp": float(np.median(spread[ok] / fill[ok])) * 1e4,
               "annual_vol_pct": annual_vol_pct, "ftmo_markup_pct": markup, "scenarios": {}}
        for scen, bp in COMMISSION_BP.items():
            per_side = spread[ok] / 2.0 + bp[BY_NAME[n].asset_class] * 1e-4 * fill[ok]
            cost_sr = float(np.median(per_side / (daily_vol_price * 16.0)))
            members = {}
            for member in MEMBER_INPUTS:
                tim = MEMBER_INPUTS[member][2]
                free = admit(n, member, turnover=filter_turnover(member), cost_per_trade_sr=cost_sr,
                             annual_vol_pct=annual_vol_pct)
                at_ftmo = admit(n, member, turnover=filter_turnover(member), cost_per_trade_sr=cost_sr,
                                markup_pct=markup, member_time_in_market=tim, annual_vol_pct=annual_vol_pct)
                members[member] = {"trading_cost_sr": free.trading_cost_sr, "admitted_swap_free": free.admitted,
                                   "swap_cost_sr_ftmo": at_ftmo.swap_cost_sr, "admitted_ftmo": at_ftmo.admitted}
            row["scenarios"][scen] = {"cost_per_trade_sr": cost_sr, "members": members}
        rows.append(row)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "admission.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for scen in COMMISSION_BP:
        free = sum(r["scenarios"][scen]["members"]["D1"]["admitted_swap_free"] for r in rows)
        ftm = sum(r["scenarios"][scen]["members"]["D1"]["admitted_ftmo"] for r in rows)
        print(f"{scen}: D1 admitted on {free}/{len(rows)} swap-free, {ftm}/{len(rows)} at FTMO's swaps")
    for r in rows:
        s = r["scenarios"]["razor_like"]
        refused = [k for k, v in s["members"].items() if not v["admitted_swap_free"]]
        print(f"{r['instrument']:8s} spread {r['median_spread_bp']:6.2f}bp vol {r['annual_vol_pct']:5.1f}% "
              f"cost/trade {s['cost_per_trade_sr']:.4f}SR  swap-free refuses: {refused or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
