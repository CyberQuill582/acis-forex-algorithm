"""FXVALUE's signal: currency value, the 5-year change in purchasing power parity (FACTORY, GAP-P12D-158;
Asness, Moskowitz & Pedersen, "Value and momentum everywhere", JF 68(3) (2013) 929-985, sec. I.B and eq. 1).

Mental model:
  * SPOT S_c: USD per unit of currency c from the ECB's daily reference rates (USD/EUR over c/EUR). For
    month m the OLD level is the mean of the daily S_c over months m-65..m-54 (the paper's "average spot
    exchange rate from 4.5 to 5.5 years ago"), the NOW level month m's last fixing.
  * VALUE(c, m) = log(old / now) - [log cpi_c(m-4)/cpi_c(m-64) - log cpi_US(m-4)/cpi_US(m-64)]: a currency
    that fell by more than its relative inflation explains is cheap. CPI is read 4 months late, so every
    figure (Australia's quarterly one too) was published before it is read. USD's value is 0.
  * RANK (eq. 1): the seven currencies' weights are rank - mean rank, the cheapest ranked 7. On c's dollar
    pair the forecast is 5 x (rank - 4), in [-15, 15], negated for a USD_c pair.
  * TIMING: month m's ranks hold from the first decision day of month m+1; `panel` maps them onto RSIM's
    days (NaN before the first signal). Every input of month m is dated m or earlier.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

CCYS = ("EUR", "JPY", "GBP", "AUD", "CAD", "CHF")
AREA = {"USD": "US", "EUR": "XM", "JPY": "JP", "GBP": "GB", "AUD": "AU", "CAD": "CA", "CHF": "CH"}
OLD, CPI_LAG, SPAN = (54, 65), 4, 60


def _shift(m: tuple[int, int], k: int) -> tuple[int, int]:
    n = m[0] * 12 + m[1] - 1 - k
    return n // 12, n % 12 + 1


def load_spot(path: Path) -> dict[str, dict[date, float]]:
    """USD per unit of each currency (EUR included) on every ECB fixing day."""
    per_eur: dict[str, dict[date, float]] = defaultdict(dict)
    with Path(path).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per_eur[r["currency"]][date.fromisoformat(r["date"])] = float(r["eur_rate"])
    usd = per_eur["USD"]
    out = {"EUR": dict(usd)}
    for c in CCYS[1:]:
        out[c] = {d: usd[d] / v for d, v in per_eur[c].items() if d in usd}
    return out


def load_cpi(path: Path) -> dict[str, dict[tuple[int, int], float]]:
    out: dict[str, dict[tuple[int, int], float]] = defaultdict(dict)
    with Path(path).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            y, mo = (int(x) for x in r["month"].split("-"))
            out[r["area"]][(y, mo)] = float(r["cpi"])
    return out


def value(c: str, m: tuple[int, int], spot: Mapping[str, Mapping[date, float]], cpi: Mapping) -> float:
    s = spot[c]
    lo, hi = _shift(m, OLD[1]), _shift(m, OLD[0])
    old = [v for d, v in s.items() if lo <= (d.year, d.month) <= hi]
    now = [v for d, v in sorted(s.items()) if (d.year, d.month) == m]
    if len(old) < 200 or not now:
        raise ValueError(f"{c} {m}: {len(old)} old fixings, {len(now)} in the month")
    t1, t0 = _shift(m, CPI_LAG), _shift(m, CPI_LAG + SPAN)
    infl = lambda a: math.log(cpi[a][t1] / cpi[a][t0])               # noqa: E731
    return math.log(float(np.mean(old)) / now[-1]) - (infl(AREA[c]) - infl("US"))


def ranks(m: tuple[int, int], spot: Mapping, cpi: Mapping) -> dict[str, int]:
    """1..7 over USD and CCYS, the highest value (cheapest) ranked 7."""
    v = {"USD": 0.0, **{c: value(c, m, spot, cpi) for c in CCYS}}
    order = sorted(v, key=lambda c: (v[c], c))
    return {c: k + 1 for k, c in enumerate(order)}


def pair_forecast(name: str, rank: Mapping[str, int]) -> float:
    base, quote = name.split("_")
    if quote == "USD":
        return 5.0 * (rank[base] - 4)
    if base == "USD":
        return -5.0 * (rank[quote] - 4)
    raise ValueError(f"{name} is not a dollar pair")


def panel(days: Sequence[date], names: Sequence[str], spot: Mapping, cpi: Mapping, first: tuple[int, int]) -> np.ndarray:
    """forecast[t, i]: month m's ranks on every decision day of month m+1, NaN before `first`'s month."""
    out, cache = np.full((len(days), len(names)), np.nan), {}
    for t, d in enumerate(days):
        m = _shift((d.year, d.month), 1)
        if m < first:
            continue
        if m not in cache:
            cache[m] = ranks(m, spot, cpi)
        out[t] = [pair_forecast(n, cache[m]) for n in names]
    return out
