"""The float pstdev that replaced exact-rational statistics.pstdev in NVMA (GAP-P12D-12):
same answers to 1e-12, exact zero on constants, order-independent, and the regime
indicators built on it are unchanged."""

from __future__ import annotations

import math
import random
import statistics

import pytest

from core.regime import nvma
from core.regime.fast_stats import pstdev


@pytest.mark.parametrize("seed", range(20))
def test_matches_statistics_pstdev_on_price_like_data(seed) -> None:
    rng = random.Random(seed)
    for n in (2, 8, 20, 100, 201):
        mids = [1.1 + rng.gauss(0, 0.0002) for _ in range(n)]
        assert pstdev(mids) == pytest.approx(statistics.pstdev(mids), rel=1e-12)
        yen = [150.0 + rng.gauss(0, 0.02) for _ in range(n)]
        assert pstdev(yen) == pytest.approx(statistics.pstdev(yen), rel=1e-12)
        spreads = [round(0.00012 + rng.uniform(-0.00002, 0.00002), 6) for _ in range(n)]
        assert pstdev(spreads) == pytest.approx(statistics.pstdev(spreads), rel=1e-12)


def test_constant_series_is_exactly_zero_like_the_exact_version() -> None:
    # GAP-0076: a sigma of 1e-17 instead of 0 would flip NVMA's ILLIQUID comparison
    for v in (1.1, 0.1, 110.25, 0.00012, 1943.845):
        assert pstdev([v] * 50) == 0.0 == statistics.pstdev([v] * 50)
    assert pstdev([0.1]) == 0.0


def test_result_does_not_depend_on_order() -> None:
    rng = random.Random(3)
    xs = [1.1 + rng.gauss(0, 0.0003) for _ in range(100)]
    assert pstdev(xs) == pstdev(sorted(xs)) == pstdev(list(reversed(xs)))


def test_empty_input_raises_like_statistics() -> None:
    with pytest.raises(statistics.StatisticsError):
        pstdev([])


def _walks() -> list[list[float]]:
    rng = random.Random(11)
    out = []
    for drift in (-2e-5, 0.0, 1e-5, 3e-5):                  # trending and noisy walks
        x, s = 1.1, []
        for _ in range(300):
            x += rng.gauss(drift, 1e-4)
            s.append(x)
        out.append(s)
    out.append([1.1 + (2e-4 if i % 2 else -2e-4) for i in range(300)])   # zigzag
    out.append([1.1] * 300)                                               # flat
    return out


def test_regime_indicators_give_the_same_answers_as_the_exact_original(monkeypatch) -> None:
    walks = _walks()
    fast = [(nvma.bollinger_width_percentile(w, 100), nvma.hurst_exponent(w, 200)) for w in walks]
    monkeypatch.setattr(nvma, "pstdev", statistics.pstdev)               # the exact original
    exact = [(nvma.bollinger_width_percentile(w, 100), nvma.hurst_exponent(w, 200)) for w in walks]
    for (fb, fh), (eb, eh) in zip(fast, exact):
        assert fb == eb or (math.isnan(fb) and math.isnan(eb))           # identical percentile rank
        assert (math.isnan(fh) and math.isnan(eh)) or fh == pytest.approx(eh, abs=1e-9)
