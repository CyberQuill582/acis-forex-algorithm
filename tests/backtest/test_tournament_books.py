"""The tournament's books (TOURNAMENT): no look-ahead (a book run on data cut at any day reproduces every day
it settled on the longer data, exactly), flat and costless before the forward start, never past its settled
horizon, REBAL's calendar term causal in returns, and the registry reproducing the register's variants."""

from __future__ import annotations

import json
import lzma
from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pytest

from core.data.rates import RateTable
from core.signals import rules
from tests.backtest.bi5 import TICK
from tests.backtest.candle_store import Hourly
from tests.backtest.exchange_days import holidays as exchange_holidays
from tests.backtest.jp_days import CalendarRefused, is_bank_day
from tests.backtest.rebal import signals
from tests.backtest.look_claims import load_vector
from tests.backtest.tournament_books import (ROOT, BookSeries, close_book, d1_forecast, gotobi_tue_fri, kill_script,
                                             nyse_sessions_after, pool_book, rebal_position, rsim_book, window_book)
from tests.backtest.tournament_registry import BY_ID, FX13, POOL_SD, REGISTRY

DATA_FROM, DATA_TO = date(2020, 1, 1), date(2021, 12, 31)


def _hours(seed: int, base: float, vol: float = 0.0008, spread: float = 0.0001) -> Hourly:
    t0 = int(datetime.combine(DATA_FROM, time(0), timezone.utc).timestamp())
    n = ((DATA_TO - DATA_FROM).days + 1) * 24
    start = t0 + 3600 * np.arange(n, dtype=np.int64)
    weekday = np.array([datetime.fromtimestamp(int(s), timezone.utc).weekday() < 5 for s in start])
    steps = np.where(weekday, np.random.default_rng(seed).standard_normal(n) * vol, 0.0)
    trend = np.where(weekday, 0.00004 * np.sin(np.arange(n) / 2000.0), 0.0)
    mid = base * np.exp(np.cumsum(steps + trend))
    return Hourly("X", start, np.r_[mid[0], mid[:-1]], mid, np.full(n, spread * base), weekday)


class FakeStore:
    """Duck-typed InputStore over in-memory hours and series, cut at `data_end`."""

    def __init__(self, data_end: date, root=None) -> None:
        self.data_end, self.root = data_end, root
        self.h = {"EUR_USD": _hours(1, 1.1), "USD_JPY": _hours(2, 110.0), "US500": _hours(3, 3200.0, 0.002)}
        days = [d for d in (DATA_FROM + timedelta(k) for k in range((DATA_TO - DATA_FROM).days + 1))
                if d.weekday() < 5 and d not in exchange_holidays("XNYS", d.year)]          # the S&P's sessions
        rng = np.random.default_rng(4)
        self.spx = dict(zip(days, 3200.0 * np.exp(np.cumsum(rng.standard_normal(len(days)) * 0.01))))
        self.y7 = dict(zip(days, 1.5 + np.cumsum(rng.standard_normal(len(days)) * 0.03)))

    def minute_horizon(self, names, today):
        return min(today - timedelta(days=1), self.data_end)

    tick_horizon = minute_horizon

    def through(self, sid):
        return self.data_end - timedelta(days=1)

    def hourly(self, name, through):
        h, cut = self.h[name], int(datetime.combine(through + timedelta(days=1), time(0), timezone.utc).timestamp())
        k = h.start < cut
        return Hourly(name, h.start[k], h.mid_open[k], h.mid_close[k], h.spread_open[k], h.traded[k])

    def rates(self, through, a, b):
        pts = [(DATA_FROM + timedelta(days=k - 5), 1.0) for k in range((through - DATA_FROM).days + 6)]
        return RateTable({c: pts for c in ("USD", "EUR", "JPY")}, a, {})

    def closes(self, sid, through):
        return {d: v for d, v in (self.spx if sid == "spx_yahoo" else self.y7).items() if d <= through}

    def holidays_jp(self):
        return frozenset()


def _same_prefix(short, long) -> None:
    assert short.dates and short.horizon < long.horizon
    got = dict(zip(long.dates, long.net))
    assert all(d in got and got[d] == v for d, v in zip(short.dates, short.net))     # exact: no look-ahead
    assert all(d <= short.horizon for d in short.dates)


def test_the_rsim_book_is_causal_flat_before_its_start_and_settled_only_through_real_fills(shipped_config) -> None:
    book, start = rsim_book(d1_forecast(rules.d1), ("EUR_USD", "USD_JPY"), DATA_FROM, idm=1.5, buffer=0.1), date(2021, 3, 1)
    long = book(FakeStore(DATA_TO), shipped_config, start, DATA_TO + timedelta(days=1))
    for cut in (date(2021, 6, 15), date(2021, 9, 3), date(2021, 11, 26)):
        _same_prefix(book(FakeStore(cut), shipped_config, start, cut + timedelta(days=1)), long)
    assert long.dates[0] >= start and long.net[0] <= 0.0 and np.any(long.net != 0)  # day one pays its entry only
    short = book(FakeStore(date(2021, 9, 3)), shipped_config, start, date(2021, 9, 4))
    assert short.horizon == date(2021, 9, 2)                      # decided at the rates' horizon, filled on the cut day
    assert book(FakeStore(date(2021, 9, 4)), shipped_config, start, date(2021, 9, 5)).horizon == date(2021, 9, 2)


def test_the_close_book_is_causal_and_reads_only_the_published_calendar_ahead(shipped_config) -> None:
    book, start = close_book("US500", rebal_position, DATA_FROM), date(2021, 2, 1)
    long = book(FakeStore(DATA_TO), shipped_config, start, DATA_TO + timedelta(days=1))
    for cut in (date(2021, 5, 25), date(2021, 11, 24), date(2021, 11, 29)):        # inside month-end weeks
        _same_prefix(book(FakeStore(cut), shipped_config, start, cut + timedelta(days=1)), long)
    assert long.dates[0] == start and long.net[0] <= 0.0


def test_rebal_position_on_any_day_equals_the_full_grids_when_the_sessions_were_as_published() -> None:
    s = FakeStore(DATA_TO)
    days = [d for d in sorted(s.spx) if d.year == 2021]
    full = signals(days, s.spx, s.y7)["position"]
    for k in range(5, len(days) - 45, 7):
        assert rebal_position(days[: k + 1], s.spx, s.y7)[k] == full[k]


def test_the_nyse_sessions_ahead_skip_its_month_end_holidays() -> None:
    nov = nyse_sessions_after(date(2026, 11, 20), months=1)
    assert date(2026, 11, 26) not in nov and date(2026, 11, 27) in nov and nov[-1] == date(2026, 11, 30)
    assert date(2026, 12, 25) not in nyse_sessions_after(date(2026, 12, 1), months=1)


def _ticks(root, d: date, sec_bid_ask) -> None:
    r = np.zeros(len(sec_bid_ask), TICK)
    r["ms"] = [s * 1000 for s, _, _ in sec_bid_ask]
    r["bid"], r["ask"] = [round(b * 1000) for _, b, _ in sec_bid_ask], [round(a * 1000) for _, _, a in sec_bid_ask]
    f = root / "ticks" / "USD_JPY" / str(d.year) / f"{d.month - 1:02d}" / f"{d.day:02d}_ticks.bi5"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(lzma.compress(r.tobytes(), format=lzma.FORMAT_ALONE))


def test_the_window_book_trades_only_tuesday_to_friday_gotobi_days_and_is_causal(tmp_path, shipped_config) -> None:
    g = kill_script("r1_gotobi_kill_test")
    for k in range(40):
        d = date(2021, 3, 1) + timedelta(days=k)
        _ticks(tmp_path, d, [(s, 110.0 + 0.01 * (d.day % 7) + s / 864000, 110.004 + 0.01 * (d.day % 7) + s / 864000)
                             for s in range(0, 86400, 60)])
    book = window_book("USD_JPY", (g.H1,), g.TIMES, g.ZONE, gotobi_tue_fri)
    start, end = date(2021, 3, 2), date(2021, 4, 8)
    long = book(FakeStore(end, tmp_path), shipped_config, start, end + timedelta(days=1))
    traded = {d for d, v in zip(long.dates, long.net) if v != 0}
    assert traded == {d for d in gotobi_tue_fri(start, end, frozenset())}
    assert all(d.weekday() in (1, 2, 3, 4) for d in traded)
    _same_prefix(book(FakeStore(date(2021, 3, 20), tmp_path), shipped_config, start, date(2021, 3, 21)), long)


def test_the_registry_reproduces_the_registers_variant_hashes_and_the_shipped_universe(shipped_config) -> None:
    registered = {                                                              # the look register's claims
        "D1-FX13": "bcd0a0d8951ae2095d56f944e38244aef46c202be2cd10bc5b6d290c6a3d8802",       # 000001, 000027
        "REBAL-v1a": "f2cbbb5c5d2cbf3e9ae959be6cb5ad33abb208fc57eaaabb48b4acce9671ba6d",     # 000007, 000025
        "GOTOBI-v1a": "bf98356cae9d1027b9f41fe0db1b00fc8b9cdae4c8eb02f1d67d525050e2c128",    # 000015, 000021
        "HALLOWEEN-v1": "696a559239a5cda59b3f6255468d9d4c357ae68bc717d1dd36ddd48e72375dd8",  # 000053
        "HEDGEP-gold": "7ef409005f492a17e82d30cb5a0f0156c7c01717dcaaab2586d7d0bd1f31be8e",   # 000045
        "FXVALUE-ppp": "b146068859006ccc87d8ba42eeb0f006e4fbd8c1384c95fb558089f8c92ae661"}   # 000049
    assert {"D1-FX13", "REBAL-v1a", "GOTOBI-v1a"} <= {s.sid for s in REGISTRY} <= set(registered)
    assert all(s.variant_hash == registered[s.sid] for s in REGISTRY)
    assert list(FX13) == sorted(shipped_config.system.targets.universe)
    for s in REGISTRY:
        e = s.entry()
        assert e["certifying_boundary"] <= e["forward_start"] and datetime.fromisoformat(e["first_exposure_utc"]).date() \
            >= date(2026, 10, 4)
    assert all(s.drift(shipped_config, s.entry()) is None for s in REGISTRY)     # the looks' C8 costs, unchanged


def test_the_bank_calendar_reaches_the_forward_years_and_its_2026_q4_gotobi_days_are_besshos() -> None:
    hol = frozenset({date(2026, 10, 12), date(2026, 11, 3), date(2026, 11, 23)})     # the Cabinet Office's 2026 Q4
    assert gotobi_tue_fri(date(2026, 10, 1), date(2026, 12, 31), hol) == [
        date(2026, 10, 9), date(2026, 10, 15), date(2026, 10, 20), date(2026, 10, 23), date(2026, 10, 30),
        date(2026, 11, 5), date(2026, 11, 10), date(2026, 11, 13), date(2026, 11, 20), date(2026, 11, 25),
        date(2026, 12, 4), date(2026, 12, 10), date(2026, 12, 15), date(2026, 12, 18), date(2026, 12, 25),
        date(2026, 12, 30)]                         # 10-05 and 11-30 are Mondays; 12-31 is the banks' closure
    assert not is_bank_day(date(2027, 1, 2), frozenset())
    with pytest.raises(CalendarRefused):
        is_bank_day(date(2028, 1, 5), frozenset())


def test_the_pool_averages_its_scaled_components_flat_where_one_has_no_row_and_settles_through_the_earliest() -> None:
    d = [date(2026, 10, 7) + timedelta(days=k) for k in range(3)]
    a = lambda store, cfg, fs, today: BookSeries(tuple(d), np.array([0.01, 0.02, 0.03]), d[2])   # noqa: E731
    b = lambda store, cfg, fs, today: BookSeries((d[1],), np.array([-0.04]), d[1])               # noqa: E731
    s = pool_book(((a, 2.0), (b, 0.5)))(None, None, d[0], d[2])
    assert s.dates == (d[0], d[1]) and s.horizon == d[1]               # b has settled only through d[1]
    assert np.allclose(s.net, [2.0 * 0.01 / 2, (2.0 * 0.02 + 0.5 * -0.04) / 2])


def test_the_pool_declares_its_components_development_numbers_before_its_first_exposure(shipped_config) -> None:
    pool = BY_ID["POOL-5"]
    e = pool.entry()
    assert set(e["params"]["components"]) == set(POOL_SD) and "FXVALUE-ppp" not in POOL_SD
    assert all(e["params"]["components"][k] == BY_ID[k].entry()["spec_hash"] for k in POOL_SD)
    assert e["first_exposure_utc"] == "2026-10-06T18:00:00+00:00" and e["certifying_boundary"] == "2026-10-04"
    assert pool.drift(shipped_config, e) is None
    looks = ROOT / "data" / "validation" / "looks"
    outcomes = {"D1-FX13": "000002", "REBAL-v1a": "000009", "GOTOBI-v1a": "000017", "HALLOWEEN-v1": "000054",
                "HEDGEP-gold": "000046"}
    if not (looks / "vectors").exists():
        pytest.skip("the look register's vectors are git-ignored data")
    vec = {}
    for sid, lid in outcomes.items():
        o = json.loads((looks / f"{lid}.json").read_text(encoding="utf-8"))
        ds, rs = load_vector(looks, o["outcome"]["daily_vector"] if "outcome" in o else o["daily_vector"])
        vec[sid] = dict(zip(ds, rs))
    lo, hi = max(min(v) for v in vec.values()), min(max(v) for v in vec.values())
    days = sorted({x for v in vec.values() for x in v if lo <= x <= hi})
    sd = {s: float(np.std([v.get(x, 0.0) for x in days])) for s, v in vec.items()}
    assert all(abs(sd[s] - POOL_SD[s]) < 5e-8 for s in POOL_SD)
    unit = 0.20 / np.sqrt(252)
    pool_r = np.mean([[vec[s].get(x, 0.0) * unit / POOL_SD[s] for x in days] for s in POOL_SD], axis=0)
    assert abs(pool_r.std() - pool.sigma_daily) < 5e-7
    assert abs(pool_r.mean() / pool_r.std() * np.sqrt(252) - pool.sharpe_dev) < 5e-4
    assert abs(-pool_r.min() / pool_r.std() - pool.history_worst_sigmas) < 5e-3
