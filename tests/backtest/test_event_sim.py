"""D3's event simulator on synthetic hourly candles (GAP-P12D-154; owner ruling "Papers' window"): the
windows come from the exchange's calendar, the anchors are the home cash closes of T-2 and T+3, the
legs' weights read no future, costs book on their days, and a planted turn-of-month effect earns
where a null does not."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.candle_store import Hourly
from tests.backtest.event_sim import NY, passive_long, per_index, simulate
from tests.backtest.exchange_days import month_turn
from tests.backtest.hac import hac_t

FREE = {"US500": CostModel(0.0, 0.0)}


def _epoch(d: date, t: time, zone=NY) -> int:
    return int(datetime.combine(d, t, tzinfo=zone).timestamp())


def _hourly(first: date, last: date, closes, spread: float = 0.0, untraded=(), name: str = "US500") -> Hourly:
    """Every New York weekday hour traded (the CFD trades through holidays), except the `untraded` dates."""
    start = np.arange(_epoch(first, time(), timezone.utc), _epoch(last, time(), timezone.utc), 3600, dtype=np.int64)
    local = [datetime.fromtimestamp(int(s), NY) for s in start]
    traded = np.array([t.weekday() < 5 and t.date() not in untraded for t in local])
    c = np.asarray(closes(start), float)
    return Hourly(name, start, np.r_[c[0], c[:-1]], c, np.full(len(start), spread), traded)


def _linear(start: np.ndarray) -> np.ndarray:
    return 1000.0 + 0.01 * ((start - start[0]) // 3600 + 1)


def _close_at(h: Hourly, d: date) -> float:
    """The close of the hour ending at 16:00 New York on d."""
    return float(h.mid_close[int(np.searchsorted(h.start, _epoch(d, time(16)) - 3600))])


def test_each_event_runs_from_the_cash_close_of_t_minus_2_to_that_of_t_plus_3() -> None:
    h = _hourly(date(2021, 1, 1), date(2021, 9, 1), _linear)
    r = simulate({"US500": h}, FREE, date(2021, 1, 4), date(2021, 4, 1), date(2021, 8, 31))
    turns = [month_turn("XNYS", 2021, m) for m in range(4, 8)]
    assert [(e["t_minus_2"], e["t_plus_3"]) for e in r.events] == [(t[0].isoformat(), t[4].isoformat()) for t in turns]
    may = r.events[1]
    assert may["t_minus_2"] == "2021-05-27"           # the CFD traded on Memorial Day; the exchange did not
    assert may["gross"] == pytest.approx(_close_at(h, date(2021, 6, 3)) / _close_at(h, date(2021, 5, 27)) - 1)


def test_a_legs_daily_pieces_sum_to_its_weight_times_its_net_and_costs_book_per_side() -> None:
    h = _hourly(date(2020, 1, 1), date(2021, 1, 1), _linear, spread=1.0)
    cost = {"US500": CostModel(0.0, 0.25)}                                  # per side: 1.0/2 + 0.25
    r = simulate({"US500": h}, cost, date(2020, 1, 2), date(2020, 4, 1), date(2020, 12, 31))
    assert len(r.events) == 8 and not r.skipped
    assert r.daily.sum() == pytest.approx(sum(e["weight"] * e["net"] for e in r.events), rel=1e-12)
    for e in r.events:
        p_in = _close_at(h, date.fromisoformat(e["t_minus_2"]))
        assert e["gross"] - e["net"] == pytest.approx(2 * 0.75 / p_in)
    doubled = simulate({"US500": h}, {"US500": CostModel(0.0, 0.25, stress=2.0)}, date(2020, 1, 2),
                       date(2020, 4, 1), date(2020, 12, 31))
    assert doubled.events[0]["gross"] - doubled.events[0]["net"] == pytest.approx(2 * (r.events[0]["gross"] - r.events[0]["net"]))


def test_a_legs_weight_reads_no_price_after_its_entry() -> None:
    rng = np.random.default_rng(7)
    steps = rng.normal(0.0, 0.002, 9000)
    walk = lambda start: 1000.0 * np.exp(np.cumsum(steps[:len(start)]))      # noqa: E731
    t2 = month_turn("XNYS", 2020, 6)[0]
    cut = _epoch(t2, time(16))                                               # every hour after June's entry
    later = lambda start: walk(start) * np.where(start >= cut, 1.0 + rng.uniform(0, 0.2, len(start)), 1.0)  # noqa: E731
    a, b = (simulate({"US500": _hourly(date(2020, 1, 1), date(2020, 12, 31), f)}, FREE, date(2020, 1, 2),
                     date(2020, 4, 1), date(2020, 12, 30)) for f in (walk, later))
    june = [i for i, e in enumerate(a.events) if e["t_minus_2"] == t2.isoformat()][0]
    assert a.events[june]["weight"] == b.events[june]["weight"]
    assert a.events[june + 1]["weight"] != b.events[june + 1]["weight"]   # the next leg does see it


def test_a_turn_without_data_vol_or_an_anchor_is_skipped_with_its_reason() -> None:
    july = month_turn("XNYS", 2018, 7)
    h = _hourly(date(2018, 7, 1), date(2018, 12, 31), _linear, untraded={july[4]})
    r = simulate({"US500": h}, FREE, date(2018, 1, 2), date(2018, 4, 2), date(2018, 12, 31))
    reasons = {s["t_minus_2"][:7]: s["reason"] for s in r.skipped}
    assert reasons["2018-04"] == reasons["2018-05"] == reasons["2018-06"] == "before_data"
    assert reasons["2018-07"] == "no_exit_anchor" and len(r.events) == 4      # August.. November turns
    assert per_index(r.events, r.skipped)["US500"]["skipped"] == {"before_data": 3, "no_exit_anchor": 1}


def _planted(mu: float, seed: int):
    rng = np.random.default_rng(seed)
    windows = []
    for y in range(2014, 2020):
        for m in range(1, 13):
            t = month_turn("XNYS", y, m)
            windows.append((_epoch(t[0], time(16)), _epoch(t[4], time(16))))
    lo, hi = np.array(windows).T

    def closes(start):
        inside = (np.searchsorted(lo, start, side="right") - 1)
        drift = np.where((inside >= 0) & (start < hi[np.maximum(inside, 0)]), mu, 0.0)
        return 1000.0 * np.exp(np.cumsum(rng.normal(0.0, 0.002, len(start)) + drift))
    return _hourly(date(2014, 1, 1), date(2020, 1, 1), closes, spread=0.2)


def test_a_planted_turn_of_month_effect_earns_net_of_cost_and_a_null_does_not() -> None:
    graded = (date(2014, 1, 2), date(2014, 4, 1), date(2019, 12, 31))
    cost = {"US500": CostModel(0.0, 0.05)}
    t = {}
    for label, mu in (("planted", 0.0001), ("null", 0.0)):
        r = simulate({"US500": _planted(mu, seed=11)}, cost, *graded)
        keep = np.array([d >= graded[1] for d in r.days])
        t[label] = hac_t(r.daily[keep])
    assert t["planted"] > 3.0 and t["null"] < 2.0, t


def test_the_passive_long_holds_every_mark_from_its_vol_warmup() -> None:
    h = _hourly(date(2020, 1, 1), date(2020, 12, 31), _linear)
    daily = passive_long({"US500": h}, date(2020, 1, 2), date(2020, 12, 30))
    assert np.isfinite(daily).all() and (daily[:31] == 0).all() and (daily[40:] > 0).sum() > 150
