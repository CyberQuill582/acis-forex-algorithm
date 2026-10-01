"""The TREND family's estimators reproduce Carver's own code (GAP-P12D-122; master §5.6 v2.22).

`tests/reference/carver/reference.json` holds the outputs of pysystemtrade's functions, copied
verbatim at the pinned commit and run under pandas (`generate.py` beside it). The stdlib versions
in core/signals must match them value for value, NaN for NaN: an external referent, not a
self-consistency check.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from core.signals import ewm, rules

REF = json.loads((Path(__file__).resolve().parents[1] / "reference" / "carver" / "reference.json")
                 .read_text(encoding="utf-8"))
PRICE = REF["price"]
NAN = float("nan")


def same(ours: list[float], theirs: list) -> None:
    assert len(ours) == len(theirs)
    for t, (a, b) in enumerate(zip(ours, theirs)):
        if b is None:
            assert a != a, f"t={t}: Carver has no value, we have {a}"
        else:
            assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), f"t={t}: {a} != Carver {b}"


def test_the_reference_is_the_pinned_commit() -> None:
    assert REF["source"] == f"pysystemtrade@{ewm.CARVER_COMMIT}"


def test_ewm_mean_and_std_are_pandas_adjusted_ewma() -> None:
    same(ewm.ewm_mean(PRICE, 16, 1), REF["ewm_mean_span16"])
    same(ewm.ewm_std(ewm.diff(PRICE), 35, 10), REF["ewm_std_span35_min10"])


def test_a_gap_decays_the_weights_and_counts_toward_min_periods_only_when_observed() -> None:
    gappy = [NAN if i in (5, 6, 50, 51, 52, 300) else p for i, p in enumerate(PRICE)]
    same(ewm.ewm_mean(gappy, 8, 3), REF["ewm_mean_gappy_span8"])
    same(ewm.ewm_std(gappy, 8, 3), REF["ewm_std_gappy_span8"])


def test_the_normaliser_is_carvers_mixed_vol() -> None:
    same(ewm.mixed_vol(ewm.diff(PRICE)), REF["mixed_vol"])


@pytest.mark.parametrize("fast,slow", [(16, 64), (32, 128), (64, 256)])
def test_ewmac_is_carvers_scaled_and_capped(fast: int, slow: int) -> None:
    raw = REF["ewmac_raw"][f"{fast},{slow}"]
    scalar = rules.EWMAC_SCALARS[(fast, slow)]
    expected = [None if x is None else max(-20.0, min(20.0, x * scalar)) for x in raw]
    same(rules.ewmac(PRICE, fast, slow), expected)


@pytest.mark.parametrize("lookback", [40, 80, 160])
def test_breakout_is_carvers_scaled_and_capped(lookback: int) -> None:
    raw = REF["breakout_raw"][str(lookback)]
    scalar = rules.BREAKOUT_SCALARS[lookback]
    same(rules.breakout(PRICE, lookback),
         [None if x is None else max(-20.0, min(20.0, x * scalar)) for x in raw])


def test_d1_is_the_equal_weight_speeds_times_the_fdm_capped() -> None:
    speeds = [rules.ewmac(PRICE, f, s) for f, s in rules.EWMAC_SCALARS]
    for t in (200, 800, 1399):
        expected = max(-20.0, min(20.0, rules.D1_FDM * sum(x[t] for x in speeds) / 3))
        assert math.isclose(rules.d1(PRICE)[t], expected, rel_tol=1e-12)


def _weekdays(n: int, start: date = date(2012, 1, 2)) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_mop_signs_the_twelve_month_excess_return_at_each_month_end_and_holds_it() -> None:
    days = _weekdays(len(PRICE))
    f = rules.mop_12m(PRICE, days)
    ends = [i for i, d in enumerate(days) if rules.is_month_end(d)]
    first = next(i for i in ends if days[i].year == days[0].year + 1)       # a year after the first end
    assert all(x != x for x in f[:first])
    for k, i in enumerate(ends):
        if i < first:
            continue
        j = next(e for e in ends if (days[e].year, days[e].month) == (days[i].year - 1, days[i].month))
        sign = 10.0 if PRICE[i] > PRICE[j] else -10.0
        stop = ends[k + 1] if k + 1 < len(ends) else len(PRICE)
        assert set(f[i:stop]) == {sign}                    # decided at the end, held a month


def test_month_end_is_a_calendar_fact() -> None:
    assert rules.is_month_end(date(2026, 9, 30))           # a Wednesday, October next
    assert rules.is_month_end(date(2026, 7, 31))           # a Friday, August on Monday
    assert not rules.is_month_end(date(2026, 9, 29))
    assert rules.is_month_end(date(2026, 10, 30))          # Friday; the 31st is a Saturday


def test_a_forecast_never_reads_past_its_decision_day() -> None:
    days = _weekdays(len(PRICE))
    members = {"d1": rules.d1, "bo160": lambda p: rules.breakout(p, 160),
               "mop": lambda p: rules.mop_12m(p, days[:len(p)]), "mopvol": rules.mop_vol}
    for name, f in members.items():
        full = f(PRICE)
        for t in (30, 400, 911, 1399):
            head = f(PRICE[:t + 1])[-1]
            assert (head != head and full[t] != full[t]) or math.isclose(head, full[t], rel_tol=1e-12), name
