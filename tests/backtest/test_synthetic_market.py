"""The falsification markets must carry exactly the answer they claim (GAP-P12D-28)."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from tests.backtest.synthetic_market import KINDS, MarketSpec, SyntheticMarket, synthetic_spx

UTC = timezone.utc
START = datetime(2014, 1, 6, tzinfo=UTC)                     # a Monday
PRICES = (("EUR_USD", 1.10), ("USD_JPY", 110.0))


def _market(kind: str, days: int = 21) -> SyntheticMarket:
    return SyntheticMarket(MarketSpec(kind, START, days, PRICES))


def _variance_ratio(rets, block: int) -> float:
    sums = [math.fsum(rets[i * block:(i + 1) * block]) for i in range(len(rets) // block)]
    return statistics.pvariance(sums) / (block * statistics.pvariance(rets))


def test_every_kind_is_deterministic_and_carries_no_net_drift() -> None:
    for kind in KINDS:
        a, b = _market(kind), _market(kind)
        assert a.returns("EUR_USD") == b.returns("EUR_USD")
        assert abs(math.fsum(a.returns("EUR_USD"))) < 1e-9
        assert a.returns("EUR_USD") != a.returns("USD_JPY")


def test_only_the_planted_market_trends() -> None:
    block = 180                                               # one hour: the shortest episode
    ratio = {k: _variance_ratio(_market(k).returns("EUR_USD"), block) for k in KINDS}
    assert ratio["planted"] > 2.5, ratio
    assert ratio["null"] < 1.3 and ratio["permuted"] < 1.3, ratio


def test_permuting_keeps_every_move_and_only_changes_their_order() -> None:
    planted, permuted = _market("planted").returns("EUR_USD"), _market("permuted").returns("EUR_USD")
    assert sorted(planted) == sorted(permuted)
    assert planted != permuted


def test_ticks_are_weekday_only_windowed_and_split_invariant() -> None:
    m, end = _market("planted", days=10), START + timedelta(days=10)
    whole = list(m.load("EUR_USD", START, end))
    assert len(whole) == 8 * 4320                             # Mon–Fri, then Mon–Wed, 20 s ticks
    assert whole[0].event_time == START and all(t.event_time.weekday() < 5 for t in whole)
    assert all(t.bid < t.ask for t in whole)
    cut = START + timedelta(days=2, hours=5, seconds=7)
    split = list(m.load("EUR_USD", START, cut)) + list(m.load("EUR_USD", cut, end))
    assert [(t.event_time, t.bid) for t in split] == [(t.event_time, t.bid) for t in whole]
    assert list(m.load("EUR_USD", START - timedelta(days=3), START)) == []
    assert list(m.load("EUR_USD", end, end + timedelta(days=5))) == []


def test_spx_is_business_days_only() -> None:
    spx = synthetic_spx(START, 14)
    assert len(spx) == 10 and all(d.weekday() < 5 for d in spx)


def test_a_start_that_is_not_monday_midnight_is_refused() -> None:
    with pytest.raises(ValueError, match="Monday"):
        MarketSpec("null", START + timedelta(hours=1), 5, PRICES)
    with pytest.raises(ValueError, match="kind"):
        MarketSpec("drifting", START, 5, PRICES)
