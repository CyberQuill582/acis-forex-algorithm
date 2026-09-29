"""The falsification markets must carry exactly the answer they claim (GAP-P12D-28), under the
synthetic-lab law ACIS-09 C-BT-12 (GAP-P12D-90/91/117). Every statistical test here also runs the
DEFECT it guards against, so it is shown to have the power to catch it."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from tests.backtest.synthetic_market import (KINDS, MarketSpec, SyntheticMarket, episodes,
                                             horizon_mean_square, match_scale, planted_drift,
                                             synthetic_spx)

UTC = timezone.utc
START = datetime(2014, 1, 6, tzinfo=UTC)                     # a Monday
PRICES = (("EUR_USD", 1.10), ("USD_JPY", 110.0))


def _market(kind: str, days: int = 21, **kw) -> SyntheticMarket:
    return SyntheticMarket(MarketSpec(kind, START, days, PRICES, **kw))


def _t(values) -> float:
    return statistics.fmean(values) / (statistics.stdev(values) / math.sqrt(len(values)))


def _demeaned(rets):
    mean = math.fsum(rets) / len(rets)
    return [r - mean for r in rets]


def test_every_kind_is_deterministic_and_per_instrument() -> None:
    for kind in KINDS:
        a, b = _market(kind), _market(kind)
        assert a.returns("EUR_USD") == b.returns("EUR_USD")
        assert a.returns("EUR_USD") != a.returns("USD_JPY")


def test_nothing_is_demeaned_so_net_drift_is_zero_in_expectation_not_pinned_in_the_sample() -> None:
    """GAP-P12D-91: the old generator pinned every path's sum to exactly 0 (a bridge). Now each
    path keeps its sampled drift, and the drift is zero only on average over paths."""
    for kind in KINDS:
        sums = [math.fsum(SyntheticMarket(MarketSpec(kind, START, 70, PRICES, tick_seconds=3600, seed=s))
                          .returns("EUR_USD")) for s in range(200)]
        assert sum(abs(x) < 1e-12 for x in sums) == 0, kind           # no path is pinned
        assert abs(_t(sums)) < 3.0, (kind, _t(sums))


def _momentum_t(paths, lookback: int) -> float:
    """t of sign(sum of the past `lookback` returns) · next return, one mean per path."""
    per_path = []
    for r in paths:
        past = math.fsum(r[:lookback])
        acc = []
        for t in range(lookback, len(r)):
            acc.append((1.0 if past > 0 else -1.0) * r[t])
            past += r[t] - r[t - lookback]
        per_path.append(statistics.fmean(acc))
    return _t(per_path)


@pytest.mark.parametrize("kind", ["null", "permuted"])
def test_the_nulls_are_martingales_and_the_old_bridge_is_caught(kind) -> None:
    """R1-C C-1: on a daily-tick null, sign(past L)·next return averages 0 at L = 63/126/252.
    The same draws demeaned (the old generator) show the bridge's momentum loss, at t < -3."""
    paths = [list(SyntheticMarket(MarketSpec(kind, START, 490, PRICES, tick_seconds=86400, seed=s))
                  .returns("EUR_USD")) for s in range(200)]
    for lookback in (63, 126, 252):
        assert abs(_momentum_t(paths, lookback)) < 3.0, (kind, lookback)
    assert _momentum_t([_demeaned(p) for p in paths], 126) < -3.0      # the defect, reproduced


def test_planted_matches_the_null_variance_exactly_at_the_decision_horizon() -> None:
    """GAP-P12D-90, by construction (common random numbers and an exact rescale), never by a
    sampled tolerance: planted = scale · (null noise + scheduled drift), and scale makes the
    MODEL variance over the decision horizon equal the null's. The old planted market was
    3.3x the null's daily volatility."""
    for match in (86400, 3600):
        spec = MarketSpec("planted", START, 70, PRICES, match_seconds=match)
        null = SyntheticMarket(MarketSpec("null", START, 70, PRICES, match_seconds=match))
        planted, steps = SyntheticMarket(spec), match // spec.tick_seconds
        noise_var = steps * spec.daily_vol ** 2 / spec.ticks_per_day
        for k, (inst, _) in enumerate(PRICES):
            drift = planted_drift(spec, episodes(spec, k))
            scale = match_scale(spec, drift)
            assert scale ** 2 * (noise_var + horizon_mean_square(drift, steps)) == pytest.approx(noise_var, rel=1e-12)
            assert list(planted.returns(inst)) == [scale * (e + m) for e, m in zip(null.returns(inst), drift)]


def test_at_the_default_strength_no_horizon_tells_planted_from_null_by_volatility() -> None:
    """Measured on half a year: the one-tick, five-minute and hourly horizons sit a few percent
    below the null (the drift's share is taken out of the noise), and the daily horizon carries
    only its sampling noise. The old planted market was 12.3x the null's daily variance."""
    null, planted = _market("null", days=182), _market("planted", days=182)
    for inst, _ in PRICES:
        for steps in (1, 15, 180, 4320):                              # 20 s, 5 min, 1 h, 1 day
            ratio = horizon_mean_square(planted.returns(inst), steps) / horizon_mean_square(null.returns(inst), steps)
            assert 0.9 < ratio < 1.1, (inst, steps, ratio)


def test_the_oracle_sharpe_sets_the_drift_at_any_tick_size() -> None:
    for tick in (20, 300, 3600):
        spec = MarketSpec("planted", START, 7, PRICES, tick_seconds=tick, oracle_sharpe=10.0)
        assert spec.drift_sigma * math.sqrt(252 * spec.ticks_per_day) == pytest.approx(10.0)


def test_only_the_planted_market_carries_the_scheduled_drift() -> None:
    """The oracle's projection sign(episode)·return: significant on planted, absent on the two
    nulls, which carry the same schedule unapplied."""
    t = {}
    for kind in KINDS:
        m = _market(kind, days=70)
        sched, rets = episodes(m.spec, 0), m.returns("EUR_USD")
        t[kind] = _t([ep.sign * r for ep in sched for r in rets[ep.start:ep.end]])
    assert t["planted"] > 3.0 and abs(t["null"]) < 3.0 and abs(t["permuted"]) < 3.0, t


def test_permuting_keeps_every_move_and_changes_order_and_sign() -> None:
    planted, permuted = _market("planted").returns("EUR_USD"), _market("permuted").returns("EUR_USD")
    assert sorted(map(abs, planted)) == sorted(map(abs, permuted))
    assert math.fsum(r * r for r in planted) == pytest.approx(math.fsum(r * r for r in permuted), rel=1e-12)
    flipped = sum(1 for r in permuted if r < 0) / len(permuted)
    assert 0.49 < flipped < 0.51 and list(planted) != list(permuted)


def test_prices_compound_simple_returns_so_a_long_bias_earns_nothing_in_price_units() -> None:
    """GAP-P12D-117: exp-built prices pay an always-long rule σ²/2 a day in price units. Each mid
    is the last times (1 + its zero-mean simple return), so over 2,000 paths at 2% daily vol a
    buy-and-hold's price P&L centres on 0. The SAME draws built as exp(running sum), the old
    construction, earn the convexity on top: σ²T/2 on average, which is what is removed."""
    m = _market("null")
    prev, rets, mids = 1.10, m.returns("EUR_USD"), m.mids("EUR_USD")
    for k, r in enumerate(rets):
        assert mids[k] == prev * (1.0 + r)
        prev = mids[k]
    held, convexity = [], []
    for s in range(2000):
        spec = MarketSpec("permuted" if s % 2 else "null", START, 84, PRICES, tick_seconds=86400,
                          daily_vol=0.02, seed=s)
        market = SyntheticMarket(spec)
        pnl = market.mids("EUR_USD")[-1] / 1.10 - 1.0
        held.append(pnl)
        convexity.append(math.expm1(math.fsum(market.returns("EUR_USD"))) - pnl)
    assert abs(_t(held)) < 3.0, _t(held)
    theory = 0.02 ** 2 * 60 / 2                                       # σ²T/2 over 60 weekdays
    assert statistics.fmean(convexity) == pytest.approx(theory, rel=0.15) and _t(convexity) > 10


def test_a_simple_return_at_or_below_minus_one_is_refused() -> None:
    m = SyntheticMarket(MarketSpec("null", START, 700, PRICES, tick_seconds=86400, daily_vol=0.6))
    with pytest.raises(ValueError, match="<= -1"):
        m.mids("EUR_USD")


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


def test_a_bad_spec_is_refused() -> None:
    with pytest.raises(ValueError, match="Monday"):
        MarketSpec("null", START + timedelta(hours=1), 5, PRICES)
    with pytest.raises(ValueError, match="kind"):
        MarketSpec("drifting", START, 5, PRICES)
    with pytest.raises(ValueError, match="match_seconds"):
        MarketSpec("planted", START, 5, PRICES, match_seconds=30)
    with pytest.raises(ValueError, match="oracle_sharpe"):
        MarketSpec("planted", START, 5, PRICES, oracle_sharpe=-1.0)
