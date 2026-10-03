"""The target path's own data check (core/runtime/feed_check.py; master v2.33, owner ruling
"Replace before the cutover"; v2.35's floor and ceiling, GAP-P12D-159): it reads only the tick feed."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from core.data.normaliser import deep_freeze
from core.runtime.feed_check import FeedWatch
from tests.signals_fixtures import T0, mk_state

TICK = 0.00001                                                   # EUR_USD's price increment


def _watch(**kw) -> FeedWatch:
    return FeedWatch(max_age_s=240.0, spread_mult=3.0, tick_size={"EUR_USD": TICK}, window=100, min_ticks=10, **kw)


def _feed(w: FeedWatch, n: int, spread: float = 0.0001) -> None:
    for k in range(n):
        w.observe(mk_state(spread=spread, ts=T0 + timedelta(seconds=k)))


def test_each_refusal_reads_only_the_tick_feed() -> None:
    w = _watch()
    assert w.refusal("EUR_USD", T0) == "no_feed"
    _feed(w, 9)
    assert w.refusal("EUR_USD", T0 + timedelta(seconds=10)) == "feed_warming"
    _feed(w, 1)
    at = T0 + timedelta(seconds=10)
    assert w.refusal("EUR_USD", at) is None
    assert w.refusal("EUR_USD", at + timedelta(seconds=250)) == "stale_feed"   # a silent feed
    w.observe(mk_state(spread=0.0004, ts=at))                                   # 4x the recent median
    assert w.refusal("EUR_USD", at) == "wide_spread"
    w.observe(replace(mk_state(spread=0.0001, ts=at), macro_events_imminent=True))
    assert w.refusal("EUR_USD", at) == "macro_event"
    w.observe(replace(mk_state(spread=0.0001, ts=at), is_stale=True))
    assert w.refusal("EUR_USD", at) == "stale_feed"                              # a late tick


def test_a_raw_spread_feed_whose_median_is_zero_is_judged_against_one_price_tick() -> None:
    w = _watch()
    _feed(w, 60, spread=0.0)                                     # a raw-spread venue: mostly 0.0 (PC-I-02 b)
    _feed(w, 10, spread=TICK)
    at = T0 + timedelta(seconds=70)
    w.observe(mk_state(spread=TICK, ts=at))
    assert w.refusal("EUR_USD", at) is None                      # one tick is not "wide" (v2.33 refused it)
    w.observe(mk_state(spread=2 * TICK, ts=at))
    assert w.refusal("EUR_USD", at) is None                      # under 3 ticks: not wide
    w.observe(mk_state(spread=4 * TICK, ts=at))
    assert w.refusal("EUR_USD", at) == "wide_spread"


def test_a_spread_the_normaliser_flags_implausible_is_refused_however_slowly_it_widened() -> None:
    w = _watch()
    for k in range(100):                                         # 1 pip widening to 10 pips (PC-I-02 a)
        w.observe(mk_state(spread=0.0001 + 0.0009 * k / 99, ts=T0 + timedelta(seconds=k)))
    at = T0 + timedelta(seconds=100)
    w.observe(mk_state(spread=0.001, ts=at))
    assert w.refusal("EUR_USD", at) is None                      # the median tracked the widening
    flagged = replace(mk_state(spread=0.001, ts=at), raw=deep_freeze({"_acis_meta": {"implausible_spread": True}}))
    w.observe(flagged)
    assert w.refusal("EUR_USD", at) == "wide_spread"             # the absolute ceiling still binds
