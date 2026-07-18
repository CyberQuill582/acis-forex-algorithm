"""Guardrail checks + stop authority (ACIS-07 §13/§14, C-RSK-3/4/6/8/9/10)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.risk.guardrails import GuardrailContext, taper_factor
from tests.risk_fixtures import RecordingSink, acct, build_monitor, load_cfg
from tests.risk_fixtures import T0


def _ctx(*, equity=10000.0, balance=None, nav=10000.0, per_inst=None, var=0.0,
         cluster=0.0, slip=0.0, tierg=None, now=T0):
    return GuardrailContext(
        now=now, equity=Decimal(str(equity)),
        balance=Decimal(str(balance if balance is not None else equity)),
        nav=Decimal(str(nav)), per_instrument_drawdown_pct=per_inst or {},
        var_pct=var, max_cluster_pct=cluster, slippage_slope_bps=slip,
        tierg_flatten=tierg or {})


# -- C-RSK-6: taper hand-vectors + min-across-limits ------------------------- #

def test_taper_hand_vectors() -> None:
    assert taper_factor(0.60, 0.60, 0.80) == 1.0
    assert taper_factor(0.70, 0.60, 0.80) == pytest.approx(0.5)
    assert taper_factor(0.80, 0.60, 0.80) == 0.0
    assert taper_factor(0.50, 0.60, 0.80) == 1.0
    assert taper_factor(0.95, 0.60, 0.80) == 0.0


def test_min_across_limits_binds_to_nearest_wall() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)                # 0.60/0.80 fractions
    # EUR_USD at 70% of its 1.0% limit → taper 0.5; USD_JPY at 80% → 0.0.
    out = g.check(_ctx(per_inst={"EUR_USD": 0.70, "USD_JPY": 0.80}))
    assert out.taper_factor == 0.0                       # the nearest wall binds
    # the delivered taper is the min, sent over the edge with alpha_decay None
    assert sink.risk_states[-1] == (0.0, None)


def test_taper_only_update_never_clears_alpha_decay() -> None:
    # C-RSK-9: every taper the guardrails deliver carries alpha_decay=None —
    # a taper update can never silently relax an armed throttle.
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    g.check(_ctx(per_inst={"EUR_USD": 0.70}))
    assert all(alpha is None for _, alpha in sink.risk_states)


def test_prop_stricter_fractions_bite_earlier() -> None:
    # prop_demo overrides taper_start=0.50/entry_halt=0.70 (stricter, ratified).
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink, account="prop_demo")
    out = g.check(_ctx(per_inst={"EUR_USD": 0.60}))      # 60% of the 1.0% limit
    # under 0.50/0.70: (0.70-0.60)/(0.70-0.50)=0.5; under the default it'd be 1.0
    assert out.taper_factor == pytest.approx(0.5)


# -- C-RSK-3: equity breaker (unthrottleable, flatten + halt) ---------------- #

def test_equity_breaker_flattens_and_halts() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    out = g.check(_ctx(equity=8000.0))                   # below floor 9000
    assert out.equity_floor_breached
    assert ("all", "equity_floor") in sink.flattens
    assert ("all", "equity_floor") in sink.halts


def test_equity_breaker_fires_even_with_taper_pressure() -> None:
    # unthrottleable: the breaker is checked first and cannot be masked.
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    out = g.check(_ctx(equity=8500.0, per_inst={"EUR_USD": 0.75}))
    assert out.equity_floor_breached
    assert ("all", "equity_floor") in sink.flattens


# -- C-RSK-4: racing HALTs coalesce to one, most-severe scope wins ----------- #

def test_racing_halts_coalesce_to_single_global() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    # VaR breach AND cluster breach in the same evaluate → one global halt.
    g.check(_ctx(var=5.0, cluster=40.0))
    assert sink.halts.count(("all", "var_cap")) == 1
    assert not any(scope == "all" and reason == "cluster_cap"
                   for scope, reason in sink.halts)      # subsumed


def test_instrument_halt_subsumed_by_global() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    g.check(_ctx(var=5.0))                               # global halt first
    g.check(_ctx(var=5.0, per_inst={"EUR_USD": 2.0}))    # inst breach, but covered
    assert not any(scope == "EUR_USD" for scope, _ in sink.halts)


# -- C-RSK-10: Tier-G flatten both branches ---------------------------------- #

def test_tierg_flatten_fires_on_confirmed_condition() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    g.check(_ctx(tierg={"EUR_USD": ("geopolitical", ("reuters", "bloomberg"))}))
    assert ("EUR_USD", "tierg_flatten") in sink.flattens


def test_no_tierg_no_flatten() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    g.check(_ctx())
    assert sink.flattens == []


# -- per-instrument + VaR + cluster HALTs at their exact limits -------------- #

def test_per_instrument_drawdown_halts_that_instrument() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    g.check(_ctx(per_inst={"EUR_USD": 1.0}))             # exactly the 1.0% limit
    assert ("EUR_USD", "per_instrument_drawdown") in sink.halts


def test_var_and_cluster_caps_halt() -> None:
    cfg = load_cfg()
    s1 = RecordingSink()
    _, g1, _, _ = build_monitor(cfg, s1)
    g1.check(_ctx(var=3.01))
    assert ("all", "var_cap") in s1.halts
    s2 = RecordingSink()
    _, g2, _, _ = build_monitor(cfg, s2)
    g2.check(_ctx(cluster=20.01))
    assert ("all", "cluster_cap") in s2.halts


# -- slippage alert is alert-only (no throttle knob exists, GAP-0004) -------- #

def test_slippage_alert_sets_flag_only() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink)
    out = g.check(_ctx(slip=9.0))                        # > 8.0 bps
    assert out.slippage_slope_alert
    assert sink.halts == [] and sink.flattens == []


# -- C-RSK-8: platform trailing-intraday-equity uses the high-water anchor ---- #

def test_trailing_intraday_equity_uses_high_water_not_eod() -> None:
    cfg, sink = load_cfg(), RecordingSink()
    _, g, _, _ = build_monitor(cfg, sink, account="prop_demo")
    for eq in (10000.0, 10500.0, 10200.0):
        out = g.check(_ctx(equity=eq, nav=eq))
    trailing = [s for s in out.platform_drawdown if "trailing:intraday:equity" in s.rule_key][0]
    # high-water 10500 → (10500-10200)/10500 = 2.857%; an EOD/open anchor (10000)
    # would report 0% — the fixture proves the high-water anchor.
    assert abs(trailing.measured_pct - 2.857142857) < 1e-3
