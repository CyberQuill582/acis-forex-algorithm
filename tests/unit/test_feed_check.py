"""The target path's own data check (core/runtime/feed_check.py; master v2.33, owner ruling
"Replace before the cutover"): it reads only the tick feed."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from core.runtime.feed_check import FeedWatch
from tests.signals_fixtures import T0, mk_state


def _watch(**kw) -> FeedWatch:
    return FeedWatch(max_age_s=240.0, spread_mult=3.0, window=100, min_ticks=10, **kw)


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
