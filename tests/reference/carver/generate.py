"""Regenerate `reference.json`: Carver's OWN code, run under pandas, on a fixed input series.

NOT run by pytest and NOT a project dependency: run it once in a scratch venv with pandas
(`pip install pandas numpy`), then commit the JSON. The functions below are copied verbatim from
pysystemtrade at master a62269d27707806ba61f516791b71a9cd14cf268 (2026-09-29):
  systems/provided/rules/ewmac.py      `ewmac`
  systems/provided/rules/breakout.py   `breakout`
  sysquant/estimators/vol.py           `mixed_vol_calc`, `simple_ewvol_calc`, `apply_min_vol`
with `BUSINESS_DAYS_IN_YEAR = 256.0` from syscore/dateutils.py, and the arguments of
sysdata/config/defaults.yaml `volatility_calculation` (days 35, min_periods 10, slow_vol_years 10,
proportion_of_slow_vol 0.3, vol_abs_min 1e-10). tests/unit/test_carver_reference.py checks
core/signals/ewm.py and core/signals/rules.py against the stored outputs.
"""

import json
import random
import sys

import numpy as np
import pandas as pd

BUSINESS_DAYS_IN_YEAR = 256.0


def ewmac(price, vol, Lfast, Lslow):
    fast_ewma = price.ewm(span=Lfast, min_periods=1).mean()
    slow_ewma = price.ewm(span=Lslow, min_periods=1).mean()
    raw_ewmac = fast_ewma - slow_ewma

    return raw_ewmac / vol.ffill()


def breakout(price, lookback=10, smooth=None):
    if smooth is None:
        smooth = max(int(lookback / 4.0), 1)

    assert smooth < lookback

    roll_max = price.rolling(
        lookback, min_periods=int(min(len(price), np.ceil(lookback / 2.0)))
    ).max()
    roll_min = price.rolling(
        lookback, min_periods=int(min(len(price), np.ceil(lookback / 2.0)))
    ).min()

    roll_mean = (roll_max + roll_min) / 2.0

    # gives a nice natural scaling
    output = 40.0 * ((price - roll_mean) / (roll_max - roll_min))
    smoothed_output = output.ewm(span=smooth, min_periods=np.ceil(smooth / 2.0)).mean()

    return smoothed_output


def apply_min_vol(vol, vol_abs_min=0.0000000001):
    vol[vol < vol_abs_min] = vol_abs_min

    return vol


def simple_ewvol_calc(daily_returns, days=35, min_periods=10, **ignored_kwargs):
    vol = daily_returns.ewm(adjust=True, span=days, min_periods=min_periods).std()

    return vol


def mixed_vol_calc(daily_returns, days=35, min_periods=10, slow_vol_years=20,
                   proportion_of_slow_vol=0.3, vol_abs_min=0.0000000001, backfill=False,
                   **ignored_kwargs):
    vol = simple_ewvol_calc(daily_returns, days=days, min_periods=min_periods)

    slow_vol_days = slow_vol_years * BUSINESS_DAYS_IN_YEAR
    long_vol = vol.ewm(span=slow_vol_days).mean()

    vol = long_vol * proportion_of_slow_vol + vol * (1 - proportion_of_slow_vol)

    vol = apply_min_vol(vol, vol_abs_min=vol_abs_min)

    return vol


def series():
    rng = random.Random(20261001)
    p = [1.1000]
    for t in range(1, 1400):
        if 400 <= t < 412:
            p.append(p[-1])                           # a flat stretch: the constant-series path
        else:
            p.append(p[-1] * (1.0 + rng.gauss(0.0001, 0.0060)))
    return p


def clean(s):
    return [None if (x != x) else float(x) for x in s]


def main():
    price = pd.Series(series())
    vol = mixed_vol_calc(price.diff(), days=35, min_periods=10, slow_vol_years=10,
                         proportion_of_slow_vol=0.3, vol_abs_min=0.0000000001)
    gappy = price.copy()
    gappy.iloc[[5, 6, 50, 51, 52, 300]] = np.nan
    out = {
        "source": "pysystemtrade@a62269d27707806ba61f516791b71a9cd14cf268",
        "pandas": pd.__version__,
        "price": clean(price),
        "ewm_mean_span16": clean(price.ewm(span=16, min_periods=1).mean()),
        "ewm_std_span35_min10": clean(simple_ewvol_calc(price.diff())),
        "ewm_mean_gappy_span8": clean(gappy.ewm(span=8, min_periods=3).mean()),
        "ewm_std_gappy_span8": clean(gappy.ewm(span=8, min_periods=3).std()),
        "mixed_vol": clean(vol),
        "ewmac_raw": {f"{f},{s}": clean(ewmac(price, vol, f, s)) for f, s in ((16, 64), (32, 128), (64, 256))},
        "breakout_raw": {str(n): clean(breakout(price, n)) for n in (40, 80, 160)},
    }
    json.dump(out, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
