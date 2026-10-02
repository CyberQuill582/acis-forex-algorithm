"""The target-position path's gate and decision (ACIS-05 v1.7 §6.4, ACIS-04 v1.6 §4b; R1.6): what a banded
target sends, what blocks an entry but never a reduction, when no target is made, and B0(d) parity —
the engine's decision sequence equals RSIM's practice book on a lab tape."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from core.data.bars import Bar
from core.data.fx_clock import rollover_utc
from core.data.rates import RateTable, swap_multiplier
from core.governor.target_gate import target_orders
from core.data.rates import CCY_SERIES, StaleRateError, load_rate_table
from core.governor.target import banded_target
from core.runtime.target_decision import BookSizing, Lots, class_equal_weights, decide, usd_per_quote
from core.signals.daily import DailySeries
from config.schemas import load_config
from core.signals import rules
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.rsim import BookSpec, Lots as RsimLots, panel, run
from tests.backtest.rsim_lab import carver_pct_vol, lab_costs, lab_market
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_governor import mk_governor, mk_portfolio, mk_rulebook

LOT = Decimal("1000")
ATR = 0.0070


@dataclass(frozen=True)
class Held:
    instrument: str
    direction: int
    size_units: Decimal
    stop_loss: float | None = 1.0
    param_set_id: str = "trend_d1_v1"
    group_id: str | None = None


def _gate(gov=None, rules_=None, **kw):
    gov = gov or mk_governor()[0]
    args = dict(limits=gov.guards._limits, rules=rules_ or mk_rulebook(), clusters={"usd_short": ["EUR_USD"]},
                instrument="EUR_USD", held=None, target=LOT, mark=1.10, atr=ATR, stop_mult=10.0, step=LOT,
                minimum=LOT, portfolio=mk_portfolio(), regime=mk_regime(), marks={"EUR_USD": 1.10}, now=T0,
                family="trend_d1_v1", snapshot={"forecast": 7.0}, logger=gov._log)
    args.update(kw)
    return target_orders(gov, **args)


# -- the gate --------------------------------------------------------------------------------- #

def test_an_open_from_flat_carries_the_disaster_stop_and_no_take_profit() -> None:
    r = _gate()
    (o,) = r.orders
    assert (r.reason, o.action, o.direction, o.size_units, o.take_profit) == ("open", "open", 1, LOT, None)
    assert o.stop_loss == pytest.approx(1.10 - 10 * ATR) and o.param_set_id == "trend_d1_v1"
    short = _gate(target=-LOT).orders[0]
    assert short.direction == -1 and short.stop_loss == pytest.approx(1.10 + 10 * ATR)


def test_a_flip_closes_the_whole_holding_then_opens_and_a_flat_target_only_closes() -> None:
    held = Held("EUR_USD", 1, LOT)
    r = _gate(held=held, target=-LOT)
    assert r.reason == "flip" and [(o.action, o.direction, o.size_units) for o in r.orders] == [
        ("close", 1, LOT), ("open", -1, LOT)]
    r = _gate(held=held, target=Decimal("0"))
    assert r.reason == "flat" and [(o.action, o.size_units) for o in r.orders] == [("close", LOT)]
    assert _gate(held=held, target=LOT).orders == () and _gate(held=held, target=LOT).reason == "hold"
    r = _gate(held=Held("EUR_USD", 1, 3 * LOT), target=LOT)
    assert r.reason == "reduce" and [(o.action, o.size_units) for o in r.orders] == [("close", 2 * LOT)]
    assert _gate(held=held, target=2 * LOT).reason == "add_unsupported"


def test_a_blocked_entry_places_nothing_while_its_reduction_still_executes() -> None:
    gov, _ = mk_governor()
    gov.apply_halt("all", "test")
    assert _gate(gov=gov).orders == () and _gate(gov=gov).reason == "halt"
    r = _gate(gov=gov, held=Held("EUR_USD", 1, LOT), target=-LOT)
    assert r.reason == "halt" and [o.action for o in r.orders] == ["close"]       # the reduction is never blocked
    assert _gate(regime=mk_regime(tradeable=False)).reason == "veto"
    assert _gate(regime=None).reason == "no_regime"
    assert _gate(atr=math.nan).reason == "stop_invalid"


def test_the_risk_edge_throttles_and_the_hard_caps_zero_a_one_lot_entry() -> None:
    gov, _ = mk_governor()
    gov.apply_risk_state(taper_factor=0.5)
    assert _gate(gov=gov).reason == "taper"                       # half a minimum lot rounds to zero
    gov.apply_risk_state(taper_factor=1.0, alpha_decay=True)
    assert _gate(gov=gov).reason == "alpha_decay"
    big = mk_portfolio(nav=Decimal("100000"))
    assert _gate(gov=mk_governor()[0], target=4 * LOT, portfolio=big).reason == "open"
    gov2, _ = mk_governor()
    gov2.apply_risk_state(alpha_decay=True)
    (o,) = _gate(gov=gov2, target=4 * LOT, portfolio=big).orders  # 4 lots × 0.25 = one lot
    assert o.size_units == LOT
    assert _gate(target=2 * LOT).reason == "cluster_cap"           # $2,200 > 90% of 20% of a $10k NAV
    assert _gate(rules_=mk_rulebook(max_lots=0.005)).reason == "lot_cap"
    full = mk_portfolio(per_cluster_exposure=MappingProxyType({"usd_short": Decimal("1790")}))
    assert _gate(portfolio=full).reason == "cluster_cap"           # 1,790 + 1,100 > 90% of 20% of 10,000


# -- the decision ------------------------------------------------------------------------------- #

def _flat_rates(days, eur=lambda d: 0.0) -> RateTable:
    return RateTable({"USD": [(d, 0.0) for d in days], "EUR": [(d, eur(d)) for d in days]})


def _series(closes, days) -> DailySeries:
    bars = tuple(Bar(ts_open=rollover_utc(d) - timedelta(days=1), open=c, high=c * 1.002, low=c * 0.998,
                     close=c, spread=0.0, duration_s=86400) for c, d in zip(closes, days))
    return DailySeries("EUR_USD", tuple(days), tuple(closes), (True,) * len(days), bars)


def _weekdays(n: int, end=date(2026, 9, 30)) -> list[date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


SIZING = BookSizing(capital_ref=10_000, vol_target=0.10, idm=1.0, buffer=0.10, weights={"EUR_USD": 1.0})
PRACTICE = Lots(LOT, LOT, LOT)


def test_no_target_on_stale_rates_a_stale_close_warm_up_or_no_usd_rate() -> None:
    days = _weekdays(400)
    closes = [1.10 * (1 + 0.0004 * k) for k in range(400)]
    kw = dict(series={}, sizing=SIZING, lots=PRACTICE, atr_period=14)
    ok = decide("EUR_USD", "fx", "USD", _series(closes, days), days[-1], Decimal(0), rates=_flat_rates(days), **kw)
    assert ok.reason == "target" and ok.target == LOT and ok.forecast.inputs_hash      # an up-trend: one lot long
    stale_rates = _flat_rates(days[:-15])
    assert decide("EUR_USD", "fx", "USD", _series(closes, days), days[-1], Decimal(0), rates=stale_rates,
                  **kw).reason == "no_target:stale_rates"
    s = _series(closes, days)
    stale = DailySeries(s.instrument, s.days, s.closes, s.fresh[:-1] + (False,), s.bars)
    assert decide("EUR_USD", "fx", "USD", stale, days[-1], Decimal(0), rates=_flat_rates(days), **kw).reason == \
        "no_target:stale_close"
    assert decide("EUR_USD", "fx", "USD", _series(closes[:200], days[:200]), days[199], Decimal(0),
                  rates=_flat_rates(days), **kw).reason == "no_target:warming_up"
    assert decide("EUR_USD", "fx", "JPY", _series(closes, days), days[-1], Decimal(0), rates=_flat_rates(days),
                  **kw).reason in ("no_target:stale_rates", "no_target:no_usd_rate")
    assert class_equal_weights({"A": "fx", "B": "fx", "C": "metal"}) == {"A": 0.25, "B": 0.25, "C": 0.5}


def test_b0d_the_engines_decisions_equal_rsims_practice_book_on_a_lab_tape() -> None:
    """B0(d): the same tape, the same family, the same sizing and the one-lot practice cap — the
    engine's target at every decision equals RSIM's position after that decision's fill."""
    path = generate(LabSpec(n_inst=1, days=620, seed=21, effect=Effect(trend_sharpe=1.0, trend_halflife=40.0)))
    m = lab_market(path)
    days = [d for d in m.days]
    mids, price = m.close[:, 0], m.price[:, 0]
    implied = [0.0] + [price[t] / price[t - 1] * mids[t - 1] / mids[t] - 1.0 for t in range(1, len(days))]
    rates = RateTable({"USD": [(d, 0.0) for d in days],
                       "EUR": [(d, a * 36500.0 / swap_multiplier(d, "tom_next")) for d, a in zip(days, implied)]})
    cfg = load_config(Path(__file__).resolve().parents[2] / "config")
    spec = BookSpec(costs=lab_costs(cfg, m.names), capital=10_000, vol_target=0.10, idm=1.0,
                    lots={m.names[0]: RsimLots(1000, 1000)}, lot_cap={m.names[0]: 1000.0})
    forecast = panel(m, rules.d1)
    forecast[:260] = np.nan                                                    # RSIM's warm-up (`masked`)
    book = run(m, forecast, carver_pct_vol(m), spec)
    held, compared = Decimal(0), 0
    sizing = BookSizing(capital_ref=10_000, vol_target=0.10, idm=1.0, buffer=0.10, weights={"EUR_USD": 1.0})
    for t in range(260, len(days)):
        d = decide("EUR_USD", "fx", "USD", _series(list(mids[: t + 1]), days[: t + 1]), days[t], held, rates=rates,
                   series={}, sizing=sizing, lots=PRACTICE, atr_period=14)
        assert d.reason == "target", (t, d.reason)
        assert float(d.target) == book.units[t, 0], t
        held, compared = d.target, compared + 1
    assert compared > 300 and len({float(u) for u in book.units[260:, 0]}) > 1       # it traded


def test_the_quote_rate_converts_each_quote_to_usd_through_its_usd_leg_and_sizes_with_it() -> None:
    """R16I-07: ten of the thirteen pairs size through this conversion; pin it by hand."""
    day = date(2026, 9, 30)
    one = lambda name, close: DailySeries(name, (day,), (close,), (True,), ())          # noqa: E731
    legs = {"USD_JPY": one("USD_JPY", 150.0), "GBP_USD": one("GBP_USD", 1.25), "USD_CHF": one("USD_CHF", 0.8)}
    assert usd_per_quote("JPY", day, legs) == pytest.approx(1 / 150.0)
    assert usd_per_quote("GBP", day, legs) == pytest.approx(1.25)
    assert usd_per_quote("CHF", day, legs) == pytest.approx(1 / 0.8)
    assert usd_per_quote("USD", day, {}) == 1.0 and usd_per_quote("CAD", day, legs) is None
    days = _weekdays(400)
    closes = [150.0 * (1 + 0.0004 * k) for k in range(400)]
    s = DailySeries("USD_JPY", tuple(days), tuple(closes), (True,) * 400, _series(closes, days).bars)
    rates = RateTable({"USD": [(d, 0.0) for d in days], "JPY": [(d, 0.0) for d in days]})
    uncapped = Lots(LOT, LOT, None)
    sizing = BookSizing(capital_ref=10_000, vol_target=0.10, idm=1.0, buffer=0.10, weights={"USD_JPY": 1.0})
    d = decide("USD_JPY", "fx", "JPY", s, days[-1], Decimal(0), rates=rates, series={"USD_JPY": s},
               sizing=sizing, lots=uncapped, atr_period=14)
    f = d.forecast
    want = banded_target(0.0, f.value, f.pct_vol, f.price_basis, 1 / closes[-1], cash_vol=sizing.cash_vol,
                         weight=1.0, idm=1.0, buffer=0.10, step=LOT, minimum=LOT)
    assert d.target == want and d.target >= 2 * LOT                          # q = 1/USDJPY: ~6,000 units, not ~0


def test_a_missing_rate_file_stales_only_its_currency(tmp_path) -> None:
    """R16I-08: R6-1 is per instrument; one missing series never blocks the others."""
    for ccy, (sid, area) in CCY_SERIES.items():
        if ccy != "CHF":
            body = "date,area,value\n2026-09-30,AU,3.6\n" if area else "date,value\n2026-09-30,1.5\n"
            (tmp_path / f"{sid}.csv").write_text(body, encoding="utf-8")
    table = load_rate_table(tmp_path)
    assert table.rate("USD", date(2026, 10, 1)) == Decimal("1.5")
    with pytest.raises(StaleRateError):
        table.rate("CHF", date(2026, 10, 1))


def test_a_weekly_source_stays_fresh_for_21_days_and_a_daily_one_for_10(tmp_path) -> None:
    """GAP-P12D-146 (R6-1 amended): the limit follows the source's cadence. AUD (BIS, weekly)
    18 days old is fresh; USD (EFFR, daily) 11 days old is stale; past 21 days AUD is stale too."""
    for ccy, (sid, area) in CCY_SERIES.items():
        body = "date,area,value\n2026-09-13,AU,3.6\n" if area else "date,value\n2026-09-20,1.5\n"
        (tmp_path / f"{sid}.csv").write_text(body, encoding="utf-8")
    table = load_rate_table(tmp_path, 10, 21)
    assert table.rate("AUD", date(2026, 10, 1)) == Decimal("3.6")            # 18 days, weekly: fresh
    assert table.rate("CHF", date(2026, 10, 1)) == Decimal("1.5")            # 11 days, weekly: fresh
    with pytest.raises(StaleRateError):
        table.rate("USD", date(2026, 10, 1))                                # 11 days, daily: stale
    with pytest.raises(StaleRateError):
        table.rate("AUD", date(2026, 10, 5))                                # 22 days: stale
    with pytest.raises(StaleRateError):
        load_rate_table(tmp_path).rate("AUD", date(2026, 10, 1))           # no weekly limit: 10 days
