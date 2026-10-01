"""RSIM's real-data source (GAP-P12D-136 item 1): the decision at 17:00 New York, the fill at the
symbol's slot after it, carry by the swap calendar, q, the excess price, and the tier guards.
Synthetic candle files in the archive's own layout; the real-data check builds markets only and
never computes a P&L (a P&L on real data is a look, evaluate()'s alone)."""

from __future__ import annotations

import calendar
import lzma
import struct
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from tests.backtest.financing import RateTable
from tests.backtest.rsim_real import NY, SourceRefused, build, masked
from tests.backtest.universe import BY_NAME

REAL = Path("/opt/acis/data/dukascopy_candles")


def _write(root: Path, name: str, months, price_of) -> None:
    inst = BY_NAME[name]
    for y, m in months:
        hours = calendar.monthrange(y, m)[1] * 24
        t0 = int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp())
        for side, off in (("BID", -0.5), ("ASK", 0.5)):
            rows = []
            for k in range(hours):
                at = t0 + 3600 * k
                weekend = datetime.fromtimestamp(at, NY).weekday() >= 5
                p = price_of(at)
                o, c = round((p + off * 1e-4) * inst.scale), round((p + 1e-5 + off * 1e-4) * inst.scale)
                rows.append(struct.pack(">IIIIIf", 3600 * k, o, c, min(o, c), max(o, c), 0.0 if weekend else 1.0))
            d = root / inst.duka / str(y) / f"{m - 1:02d}"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{side}_candles_hour_1.bi5").write_bytes(lzma.compress(b"".join(rows), format=lzma.FORMAT_ALONE))


def _rates(eur=2.0, usd=1.0, jpy=0.0) -> RateTable:
    days = [date(2011, 12, 1) + timedelta(days=k) for k in range(130)]
    return RateTable({"EUR": [(d, eur) for d in days], "USD": [(d, usd) for d in days], "JPY": [(d, jpy) for d in days]})


@pytest.fixture
def root(tmp_path):
    months = [(2012, 1), (2012, 2)]
    _write(tmp_path, "EUR_USD", months, lambda at: 1.3 + (at % 86400) / 86400 * 0.01)
    _write(tmp_path, "USD_JPY", months, lambda at: 77.0)
    return tmp_path


def test_the_decision_reads_the_last_close_and_fills_at_the_slot_after_it(root) -> None:
    rm = build(root, ["EUR_USD"], _rates(), date(2012, 1, 2), date(2012, 2, 29), tier="development")
    m = rm.market
    t = m.days.index(date(2012, 1, 4))                                  # a Wednesday
    decision = datetime(2012, 1, 4, 17, tzinfo=NY)
    last_hour_end = decision.astimezone(timezone.utc)                    # 22:00 UTC: the 16:00 NY hour's close
    expect_close = 1.3 + ((last_hour_end.timestamp() - 3600) % 86400) / 86400 * 0.01 + 1e-5
    assert m.close[t, 0] == pytest.approx(expect_close, abs=2e-5)
    fill = datetime(2012, 1, 5, 8, tzinfo=NY)                            # next morning, 08:00 New York
    assert m.fill[t, 0] == pytest.approx(1.3 + (fill.timestamp() % 86400) / 86400 * 0.01, abs=2e-5)
    assert m.spread[t, 0] == pytest.approx(1e-4, abs=2e-6)


def test_friday_fills_monday_and_carry_counts_the_swap_calendar(root) -> None:
    m = build(root, ["EUR_USD"], _rates(eur=2.0, usd=1.0), date(2012, 1, 2), date(2012, 2, 29), tier="development").market
    fri, tue = m.days.index(date(2012, 1, 6)), m.days.index(date(2012, 1, 10))
    # Friday's fill is Monday 08:00; the window to Tuesday's fill holds Monday's rollover (x1)
    assert m.nights[fri, 0] == 1.0 and m.carry[fri, 0] == pytest.approx(0.01 / 365)
    # Tuesday's fill (Wednesday 08:00) to Wednesday's (Thursday 08:00): Wednesday's rollover, x3
    assert m.nights[tue, 0] == 3.0 and m.carry[tue, 0] == pytest.approx(3 * 0.01 / 365)


def test_q_converts_the_quote_currency_at_the_fill(root) -> None:
    m = build(root, ["USD_JPY"], _rates(), date(2012, 1, 2), date(2012, 2, 29), tier="development").market
    assert m.q[10, 0] == pytest.approx(1 / 77.0, rel=1e-5)


def test_the_tiers_and_energy_are_refused(root) -> None:
    with pytest.raises(SourceRefused, match="may not read"):
        build(root, ["NZD_USD"], _rates(), date(2012, 1, 2), date(2012, 2, 29), tier="development")
    with pytest.raises(SourceRefused, match="ends 2023-12-31"):
        build(root, ["EUR_USD"], _rates(), date(2023, 1, 2), date(2024, 2, 29), tier="development")
    with pytest.raises(SourceRefused, match="rolls"):
        build(root, ["UKOIL"], _rates(), date(2012, 1, 2), date(2012, 2, 29), tier="development")


def test_masking_keeps_an_instrument_flat_before_its_data_and_warm_up(root) -> None:
    rm = build(root, ["EUR_USD"], _rates(), date(2012, 1, 2), date(2012, 2, 29), tier="development")
    f = masked(np.ones((len(rm.market.days), 1)), rm, warmup=5)
    assert np.isnan(f[: rm.first_valid["EUR_USD"] + 5]).all() and not np.isnan(f[-1]).any()


@pytest.mark.skipif(not REAL.exists(), reason="the verified candles live on the compute server")
def test_the_real_candles_build_a_market_whose_fills_follow_their_decisions() -> None:
    from tests.backtest.financing import load_rate_table
    rates = load_rate_table(Path("/opt/acis/data/macro"))
    rm = build(REAL, ["EUR_USD", "USD_JPY", "US500", "US30", "XAU_USD"], rates, date(2012, 1, 2),
               date(2023, 12, 29), tier="development")
    m = rm.market
    assert len(m.days) > 3000 and rm.first_valid["US30"] > rm.first_valid["EUR_USD"]     # US30 from 2013-09
    assert 0.9 < m.close[:, 0].min() < 1.0 < m.close[:, 0].max() < 1.7                    # EUR/USD: parity 2022
    assert 1000 < m.close[:, 2].min() and m.close[:, 2].max() < 5000                       # US500, 2012-2023
    assert (m.nights[:, 0] >= 0).all() and m.nights[:, 0].sum() == pytest.approx(365 * 12, rel=0.02)
