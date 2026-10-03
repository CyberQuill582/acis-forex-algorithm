"""AUCTION's books (GAP-P12D-158; Lou, Yan & Zhang 2013): the par curve's parsing, the auction calendar's
filters, the PRE/POST windows, a duration-neutral butterfly, and a planted auction cycle earning net where a
flat curve only pays its costs."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from tests.backtest.ust_auction import auctions, book, butterfly, load_curve, windows

HEAD = 'Date,"1 Mo","3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'


def _days(n: int, first: date = date(2019, 3, 1)) -> list[date]:
    out, d = [], first
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_the_curve_reads_the_tenors_it_needs_and_skips_a_row_missing_one(tmp_path) -> None:
    (tmp_path / "2019.csv").write_text(HEAD + "03/04/2019,2.4,2.4,2.5,2.5,2.6,2.6,2.6,2.7,2.8,2.9,3.0\n"
                                       "03/01/2019,2.4,2.4,,2.5,2.6,2.6,2.6,2.7,2.8,2.9,3.0\n", encoding="utf-8")
    days, curve = load_curve(tmp_path)
    assert days == [date(2019, 3, 4)] and curve["10y"][0] == 2.8 and curve["6m"][0] == 2.5


def test_the_calendar_keeps_fixed_nominal_notes_and_counts_ten_year_reopenings(tmp_path) -> None:
    rows = [("2019-03-26", "2-Year", "No", "No"), ("2019-03-26", "2-Year", "Yes", "No"),   # an FRN
            ("2019-04-18", "5-Year", "No", "Yes"),                                         # a TIPS
            ("2019-03-12", "9-Year 10-Month", "No", "No"), ("2019-02-13", "10-Year", "No", "No")]
    f = tmp_path / "a.csv"
    f.write_text("auction_date,security_term,floating_rate,inflation_index_security\n"
                 + "".join(",".join(r) + "\n" for r in rows), encoding="utf-8")
    assert auctions(f, ("2y", "5y", "10y")) == {"2y": [date(2019, 3, 26)], "5y": [],
                                                "10y": [date(2019, 2, 13), date(2019, 3, 12)]}


def test_pre_holds_into_the_auction_close_post_holds_from_it_and_edges_are_skipped() -> None:
    days = _days(12)
    pos, skipped = windows(days, [days[5], days[1], date(2019, 3, 2)], 2)
    assert pos.tolist() == [0, 0, 0, 1, 1, -1, -1, 0, 0, 0, 0, 0]
    assert [s["reason"] for s in skipped] == ["edge", "no curve row"]


def test_the_butterfly_is_duration_neutral_and_earns_when_the_two_year_alone_cheapens() -> None:
    days = _days(3)
    flat = {"6m": np.full(3, 2.0), "2y": np.full(3, 2.0), "5y": np.full(3, 2.0), "10y": np.full(3, 2.0)}
    shift = {k: v + np.array([0.0, 0.0, 0.10]) for k, v in flat.items()}
    carry = butterfly(days, flat)[2]
    assert butterfly(days, shift)[2] - carry == pytest.approx(0.0, abs=2e-5)    # a parallel 10 bp move nets out
    cheap = dict(flat, **{"2y": flat["2y"] + np.array([0.0, 0.0, 0.05])})
    assert butterfly(days, cheap)[2] > carry + 5e-4                               # the 2-year alone: ~9 bp


def test_a_planted_auction_cycle_earns_net_and_a_flat_curve_only_pays_its_costs() -> None:
    days = _days(40, date(2019, 3, 1))
    a, t, per_side = 20, 5, 1e-5
    y = np.zeros(40)
    y[a - t + 1:a + 1] = np.arange(1, t + 1) * 0.01             # +1 bp a day into the auction
    y[a + 1:a + t + 1] = (t - np.arange(1, t + 1)) * 0.01        # back down after it
    pos, _ = windows(days, [days[a]], t)
    r = book(days, pos, np.r_[0.0, np.diff(2.0 + y)] / 100, per_side, days[0], days[1], days[-1])
    assert r.daily.sum() == pytest.approx(2 * t * 1e-4 - 4 * per_side)          # 10 bp of yield, two round trips
    flat = book(days, pos, np.zeros(40), per_side, days[0], days[1], days[-1])
    assert flat.daily.sum() == pytest.approx(-4 * per_side)
    assert np.count_nonzero(flat.daily) == 3                                      # in, flip, out
