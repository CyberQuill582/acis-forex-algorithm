"""GAP-0005 exact g() + estimator cold-start (ACIS-05 §6.1, C-GOV-1/2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.data.errors import DataQualityError
from core.governor.marginal_alpha import CAP, FLOOR, MarginalAlphaEstimator, g


def test_g_exact_vectors() -> None:
    assert g(-5.0) == FLOOR and g(0.0) == FLOOR          # anti-greed floor
    assert g(0.5) == pytest.approx(0.625)                 # 0.25 + 0.75*0.5
    assert g(1.0) == 1.0                                  # neutral, exactly
    assert g(1.5) == pytest.approx(1.25)                  # 1 + 0.5*0.5
    assert g(2.0) == CAP and g(50.0) == CAP               # capped, never more


def test_g_monotone_nondecreasing() -> None:
    xs = [-2.0, -0.5, 0.0, 0.1, 0.5, 0.9, 1.0, 1.3, 2.0, 3.0]
    ys = [g(x) for x in xs]
    assert all(a <= b for a, b in zip(ys, ys[1:]))
    assert all(FLOOR <= y <= CAP for y in ys)


def test_g_rejects_non_finite() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(DataQualityError):
            g(bad)


def _est(**kw) -> MarginalAlphaEstimator:
    base = dict(window=50, min_trades=20, min_bucket=5)
    base.update(kw)
    return MarginalAlphaEstimator(**base)


def test_cold_start_pins_to_neutral() -> None:
    est = _est()
    for i in range(10):
        est.record_trade(Decimal("100"), Decimal("1"))
    res = est.factor()
    assert res.factor == 1.0 and res.pinned


def test_degenerate_buckets_pin() -> None:
    est = _est()
    for _ in range(30):
        est.record_trade(Decimal("100"), Decimal("1"))   # all identical sizes
    res = est.factor()
    assert res.factor == 1.0 and res.pinned


def test_positive_marginal_scales_up_capped() -> None:
    est = _est()
    for _ in range(15):
        est.record_trade(Decimal("100"), Decimal("1"))    # 0.01/unit
    for _ in range(15):
        est.record_trade(Decimal("300"), Decimal("9"))    # bigger trades earn MORE/unit
    res = est.factor()
    assert not res.pinned
    assert 1.0 < res.factor <= CAP                        # m=(9-1)/200=0.04 > b=0.02


def test_negative_marginal_floors() -> None:
    est = _est()
    for _ in range(15):
        est.record_trade(Decimal("100"), Decimal("2"))
    for _ in range(15):
        est.record_trade(Decimal("300"), Decimal("1"))    # more capital, LESS pnl
    res = est.factor()
    assert not res.pinned and res.factor == FLOOR


def test_nonpositive_baseline_floors() -> None:
    est = _est()
    for _ in range(15):
        est.record_trade(Decimal("100"), Decimal("-2"))
    for _ in range(15):
        est.record_trade(Decimal("300"), Decimal("-1"))
    res = est.factor()
    assert res.factor == FLOOR and not res.pinned


def test_trade_records_require_decimal() -> None:
    est = _est()
    with pytest.raises(DataQualityError):
        est.record_trade(100.0, Decimal("1"))  # type: ignore[arg-type]
    with pytest.raises(DataQualityError):
        est.record_trade(Decimal("0"), Decimal("1"))
