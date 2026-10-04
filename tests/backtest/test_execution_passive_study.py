"""The passive-first study's runner (scripts/execution_passive_study.py): slot clocks, the minute stamp, the
demo's rollover window, and the sealed holdout."""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from scripts.execution_passive_study import (POLICIES, demo_quotes, demo_rows, demo_slot, main, minute_quotes,
                                             run_slots, tick)
from tests.backtest.candles_min import DAY
from tests.backtest.passive_fill import Quotes

NY = ZoneInfo("America/New_York")


def test_each_quoted_minute_is_stamped_at_its_end_and_an_unquoted_one_is_dropped():
    bid, ask = np.zeros(3, DAY), np.zeros(3, DAY)
    bid["ts"] = [0, 60, 120]
    for arr, px in ((bid, 100.0), (ask, 100.5)):
        arr["open"] = arr["close"] = px
        arr["low"], arr["high"] = px - 1, px + 1
    bid["volume"] = [1.0, 0.0, 2.0]
    q = minute_quotes(bid, ask)
    assert list(q.t) == [60_000, 180_000]                  # minute 60 had no volume and no move
    assert q.ask_low[0] == 99.5 and q.bid_high[0] == 101.0


def test_an_exit_rests_one_window_before_its_deadline_and_an_entry_rests_from_its_slot():
    day = date(2021, 6, 1)
    start = int(datetime(2021, 6, 1, 14, 0, tzinfo=NY).timestamp() * 1000)
    t = np.arange(start, start + 3 * 3_600_000, 10_000)
    q = Quotes.from_ticks(t, np.full(len(t), 4200.0), np.full(len(t), 4200.5))
    rows = run_slots(q, "US500", day, "", "test")
    assert len(rows) == 2 * len(POLICIES) * 2
    for _, inst, slot, pol, unit, o in rows:
        assert inst == "US500" and unit == "2021-06-01" and not o.filled
        assert o.saving_bp == pytest.approx(0.0)           # a still market: the fallback pays the same quote
        assert o.wait_s == int(pol.split("/")[1][:-1])     # both kinds wait out their whole window


def test_the_demo_rollover_window_is_2055_to_2130_utc_and_the_hours_around_it_are_dropped():
    at = lambda h, m: datetime(2026, 10, 1, h, m, tzinfo=timezone.utc)  # noqa: E731
    assert demo_slot(at(20, 55)) == demo_slot(at(21, 29)) == "demo_rollover"
    assert demo_slot(at(20, 54)) is None and demo_slot(at(22, 59)) is None
    assert demo_slot(at(19, 59)) == demo_slot(at(23, 0)) == "demo_day"


def test_the_venue_feed_runs_d1s_slot_on_every_demo_pair_and_the_minute_arrivals_around_it():
    start = int(datetime(2026, 10, 2, 7, 0, tzinfo=NY).timestamp() * 1000)
    t = np.arange(start, start + 3 * 3_600_000, 5_000)
    rows = demo_rows({"EUR_GBP": Quotes.from_ticks(t, np.full(len(t), 0.86000), np.full(len(t), 0.86001))})
    slots = {(src, slot) for src, _, slot, _, _, _ in rows}
    assert ("pepperstone_demo", "d1_0800ny") in slots and ("pepperstone_demo", "demo_day") in slots
    assert tick("USD_JPY") == pytest.approx(0.001) and tick("US500") == pytest.approx(0.1)


def test_the_runtimes_data_log_and_the_csv_extract_give_the_same_fresh_ticks(tmp_path):
    ticks = [("EUR_USD", "2026-10-02T12:00:00.100000+00:00", 1.1, 1.10001, False),
             ("EUR_USD", "2026-10-02T12:00:00.050000+00:00", 1.1, 1.1, False),
             ("EUR_USD", "2026-10-02T12:00:01+00:00", 1.2, 1.2, True)]
    log = tmp_path / "data_log.jsonl"
    log.write_text("\n".join([json.dumps({"event_type": "REGIME_SHIFT", "data": {}})] + [json.dumps(
        {"event_type": "MARKET_STATE", "data": {"instrument": i, "event_time": t, "bid": b, "ask": a, "is_stale": s}})
        for i, t, b, a, s in ticks]), encoding="utf-8")
    extract = tmp_path / "x.csv.gz"
    with gzip.open(extract, "wt", encoding="utf-8") as f:
        f.write("instrument,event_time,bid,ask,is_stale\n" + "".join(f"{i},{t},{b},{a},{int(s)}\n" for i, t, b, a, s in ticks))
    a, b = demo_quotes(log)["EUR_USD"], demo_quotes(extract)["EUR_USD"]
    assert list(a.ask) == list(b.ask) == [1.1, 1.10001]       # in time order, the stale tick dropped
    assert list(a.t) == list(b.t)


def test_the_study_refuses_to_read_the_sealed_holdout(tmp_path):
    with pytest.raises(SystemExit):
        main(["--end", "2024-01-02", "--out", str(tmp_path / "x.json")])
