"""Capital Governor guards, factors, hard limits, groups (ACIS-05 §14)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from config.schemas import (AccountRulebook, GovernorConfig, GuardrailLimits, NewsRules,
                            ZonedTime)
from core.data.errors import DataQualityError
from core.governor.capital_governor import CapitalGovernor, ResumeForbiddenError
from core.governor.factors import correlation_factor, liquidity_factor, vol_norm
from core.governor.portfolio_types import PortfolioState
from core.regime.regime_types import LiqState, RegimeType
from core.signals.signal_types import StrategyType
from tests.optimizer_fixtures import CapturingLogger
from tests.signals_fixtures import T0, mk_regime
from tests.unit.test_signal_types import mk_signal

FRIDAY_2100 = datetime(2026, 7, 10, 21, 0, tzinfo=timezone.utc)   # = the 17:00 EDT close
_NY_ROLL = ZonedTime(zone="America/New_York", at="17:00")


def mk_rulebook(**overrides) -> AccountRulebook:
    base = dict(platform="dev", news=NewsRules(restricted=False),
                min_hold_seconds=0, max_lots=None, weekend_holding_allowed=True,
                drawdown_rules=[])
    base.update(overrides)
    return AccountRulebook(**base)


def mk_portfolio(**overrides) -> PortfolioState:
    base = dict(nav=Decimal("10000"), open_positions=(),
                per_currency_delta=MappingProxyType({}),
                per_cluster_exposure=MappingProxyType({}),
                daily_drawdown_pct=0.0, as_of=T0, stale=False)
    base.update(overrides)
    return PortfolioState(**base)


def mk_governor(rulebook=None, blackout=None, base_unit: float = 1000.0, holidays=(),
                resume_gate=None, fixed_units=None,
                **cfg_overrides) -> tuple[CapitalGovernor, CapturingLogger]:
    log = CapturingLogger()
    cfg = dict(marginal_alpha_window=50, marginal_alpha_min_trades=20,
               marginal_alpha_min_bucket=5, weekend_entry_buffer_s=7200,
               scalp_min_hold_conflict=True)
    cfg.update(cfg_overrides)
    gov = CapitalGovernor(
        cfg=GovernorConfig(**cfg),
        guardrails=GuardrailLimits(
            daily_drawdown_pct=2.0, per_instrument_drawdown_pct=1.0,
            alpha_decay_sharpe_mult=0.5, var_cap_pct=3.0, cluster_cap_pct=20.0,
            single_currency_delta_cap_pct=30.0, slippage_alert_bps=8.0,
            equity_floor_usd=9000.0, taper_start_fraction=0.60,
            entry_halt_fraction=0.80),
        rulebook=rulebook or mk_rulebook(),
        base_unit_usd=base_unit,
        clusters={"usd_short": ["EUR_USD"], "yen_carry": ["USD_JPY"]},
        vol_targets={"EUR_USD": 0.0008, "USD_JPY": 0.0008},
        confidence_veto=0.55,
        session_boundaries=[_NY_ROLL, ZonedTime(zone="Asia/Tokyo", at="09:00"),
                            ZonedTime(zone="Europe/London", at="08:00"),
                            ZonedTime(zone="America/New_York", at="08:00")],
        week_close=_NY_ROLL,
        week_open=_NY_ROLL,
        holidays=holidays,
        scalp_horizon_s=900,
        atr_period=14,
        blackout=blackout or (lambda instrument, now: False),
        logger=log,
        resume_gate=resume_gate or (lambda token: None),   # no halt ledger in these tests
        fixed_units=fixed_units or (lambda instrument: None),
    )
    return gov, log


# baseline: 1000 × 0.6 conv × 1.0 liq × 1.0 corr × (0.9×0.9) regime × 1.0 ma
#           × 1.0 vol × 1.0 taper = 486 USD at entry 1.1
BASELINE_UNITS = (Decimal("486") / Decimal("1.1")).quantize(Decimal("0.01"))


def test_formula_happy_path_with_full_snapshot() -> None:
    gov, log = mk_governor()
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.reason == "formula"
    assert order.size_units == BASELINE_UNITS
    assert isinstance(order.size_units, Decimal)
    for key in ("conviction", "liquidity", "correlation", "regime", "marginal_alpha",
                "vol_norm", "taper", "base_unit_usd", "half_life_advisory"):
        assert key in order.factors_snapshot
    assert log.events("SIZED")[0]["data"]["reason"] == "formula"


# ---------------------------- §7.1 guards, each isolated ---------------------------- #

def test_expired_signal_sizes_zero() -> None:
    gov, _ = mk_governor()
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(),
                         T0 + timedelta(seconds=301))
    assert order.size_units == 0 and order.reason == "expired"


def test_vetoed_regime_sizes_zero() -> None:
    gov, _ = mk_governor()
    vetoed = mk_regime(RegimeType.MACRO_EVENT, tradeable=False)
    order = gov.allocate(mk_signal(), mk_portfolio(), vetoed, T0)
    assert order.size_units == 0 and order.reason == "veto"


def test_halt_zeroes_until_human_resume() -> None:
    gov, _ = mk_governor()
    gov.apply_halt("all", "test")
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "halt"
    with pytest.raises(ResumeForbiddenError):
        gov.resume("")
    with pytest.raises(ResumeForbiddenError):
        gov.resume("   ")
    gov.resume("OWNER-TOKEN-123")
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "formula"


def test_instrument_scoped_halt() -> None:
    gov, _ = mk_governor()
    gov.apply_halt("EUR_USD", "instrument stress")
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "halt"


def test_drawdown_halt_is_session_scoped_and_autoclears_at_boundary() -> None:
    gov, log = mk_governor()
    hot = mk_portfolio(daily_drawdown_pct=2.5)
    assert gov.allocate(mk_signal(), hot, mk_regime(), T0).reason == "drawdown_halt"
    # even with drawdown back under the limit, the session halt persists...
    calm = mk_portfolio(daily_drawdown_pct=0.0)
    at_11 = T0.replace(hour=11)
    assert gov.allocate(mk_signal(generated_at=at_11), calm, mk_regime(),
                        at_11).reason == "drawdown_halt"
    # ...until the next session boundary (12:00) passes — then it auto-clears
    past_boundary = T0.replace(hour=12, minute=1)
    fresh = mk_signal(generated_at=past_boundary)
    assert gov.allocate(fresh, calm, mk_regime(), past_boundary).reason == "formula"


def test_explicit_halt_survives_the_boundary() -> None:
    gov, _ = mk_governor()
    gov.apply_halt("all", "equity breaker")
    past_boundary = T0.replace(hour=12, minute=1)
    fresh = mk_signal(generated_at=past_boundary)
    assert gov.allocate(fresh, mk_portfolio(), mk_regime(),
                        past_boundary).reason == "halt"


def test_low_confidence_and_illiquid_zero() -> None:
    gov, _ = mk_governor()
    low = mk_regime()
    low = mk_regime(vol=low.volatility_class)
    import dataclasses
    lowc = dataclasses.replace(mk_regime(), confidence=0.5)
    assert gov.allocate(mk_signal(), mk_portfolio(), lowc, T0).reason == "low_confidence"
    ill = mk_regime(liq=LiqState.ILLIQUID)
    assert gov.allocate(mk_signal(), mk_portfolio(), ill, T0).reason == "illiquid"


def test_stale_portfolio_fails_safe() -> None:
    gov, log = mk_governor()
    order = gov.allocate(mk_signal(), mk_portfolio(stale=True), mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "portfolio_stale"
    assert len(log.events("PORTFOLIO_STALE")) == 1


def test_blackout_enforced_on_restricted_account_only() -> None:
    restricted = mk_rulebook(news=NewsRules(restricted=True, window_before_s=600,
                                            window_after_s=600))
    gov, log = mk_governor(rulebook=restricted, blackout=lambda i, n: True)
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "blackout"
    assert log.events("BLACKOUT_OVERRIDE_ENFORCED")[0]["data"]["instrument"] == "EUR_USD"
    # unrestricted account: same blackout callable, no override
    gov2, log2 = mk_governor(blackout=lambda i, n: True)
    assert gov2.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "formula"
    assert log2.events("BLACKOUT_OVERRIDE_ENFORCED") == []


def test_weekend_entry_buffer_blocks_no_weekend_accounts() -> None:
    no_weekend = mk_rulebook(weekend_holding_allowed=False)
    gov, _ = mk_governor(rulebook=no_weekend)
    sig = mk_signal(generated_at=FRIDAY_2100)
    order = gov.allocate(sig, mk_portfolio(), mk_regime(), FRIDAY_2100)
    assert order.size_units == 0 and order.reason == "weekend_ban"
    # GAP-P12D-58: a weekend-allowed account, same instant, is banned too (this line
    # asserted "formula" until the pre-close ban was decoupled from weekend holding)
    gov2, _ = mk_governor()
    assert gov2.allocate(sig, mk_portfolio(), mk_regime(), FRIDAY_2100).reason == "weekend_ban"
    # same account far from the close (Wednesday): sized
    wed = datetime(2026, 7, 8, 21, 0, tzinfo=timezone.utc)
    sig_wed = mk_signal(generated_at=wed)
    assert gov.allocate(sig_wed, mk_portfolio(), mk_regime(), wed).reason == "formula"


def test_scalp_min_hold_conflict() -> None:
    strict = mk_rulebook(min_hold_seconds=3600)
    gov, _ = mk_governor(rulebook=strict)
    scalp = mk_signal(strategy_type=StrategyType.MOMENTUM_SCALP)
    assert gov.allocate(scalp, mk_portfolio(), mk_regime(), T0).reason == "min_hold_conflict"
    # a swing signal on the same account is unaffected
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).reason == "formula"


# ---------------------------- hard limits ---------------------------- #

def test_cluster_cap_zeroes_never_splits() -> None:
    # base unit large enough that the formula's own correlation dampening
    # cannot keep the order under the hard cap — the cap must catch it
    gov, log = mk_governor(base_unit=5000.0)
    at_cap = mk_portfolio(per_cluster_exposure=MappingProxyType(
        {"usd_short": Decimal("500")}))
    order = gov.allocate(mk_signal(conviction=1.0), at_cap, mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "cluster_cap"
    assert len(log.events("CLUSTER_CAP_ZERO")) == 1


def test_currency_delta_cap_zeroes() -> None:
    gov, log = mk_governor()
    heavy_eur = mk_portfolio(per_currency_delta=MappingProxyType(
        {"EUR": Decimal("2900")}))
    order = gov.allocate(mk_signal(), heavy_eur, mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "currency_delta_cap"
    assert len(log.events("CURRENCY_DELTA_ZERO")) == 1


def test_lot_cap_zeroes_never_clamps() -> None:
    capped = mk_rulebook(max_lots=0.001)   # 100 units — far below the formula size
    gov, log = mk_governor(rulebook=capped)
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == 0 and order.reason == "lot_cap"
    assert len(log.events("LOT_CAP_ZERO")) == 1


def test_alpha_decay_throttles_quarter() -> None:
    gov, _ = mk_governor()
    gov.apply_risk_state(alpha_decay=True)
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == (Decimal("486") * Decimal("0.25")
                                / Decimal("1.1")).quantize(Decimal("0.01"))


# ------------------- v1.6 minimum size in paper and practice (master §5) ------------------- #

def test_paper_and_practice_trade_exactly_one_minimum_lot() -> None:
    gov, _ = mk_governor(fixed_units={"EUR_USD": Decimal("1000")}.get)
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.reason == "formula" and order.size_units == Decimal("1000")
    assert order.factors_snapshot["formula_units"] == str(BASELINE_UNITS)   # kept, not traded


def test_the_minimum_lot_never_raises_a_zero_and_meets_every_hard_limit() -> None:
    lot = {"EUR_USD": Decimal("1000")}.get
    gov, _ = mk_governor(fixed_units=lot)
    gov.apply_risk_state(taper_factor=0.0)                       # Risk's entry halt
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0).size_units == 0
    capped, _ = mk_governor(rulebook=mk_rulebook(max_lots=0.005), fixed_units=lot)
    order = capped.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)   # 441.82 fits 500
    assert order.size_units == 0 and order.reason == "lot_cap"   # the lot itself is judged


# ---------------------------- §6.3 taper (C-GOV-9) ---------------------------- #

def test_taper_halves_size_before_overrides() -> None:
    gov, _ = mk_governor()
    gov.apply_risk_state(taper_factor=0.5)
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == (Decimal("243") / Decimal("1.1")).quantize(Decimal("0.01"))
    assert order.factors_snapshot["taper"] == 0.5


def test_expansive_upward_edge_rejected() -> None:
    gov, log = mk_governor()
    with pytest.raises(DataQualityError):
        gov.apply_risk_state(taper_factor=1.2)
    assert len(log.events("RISK_STATE_REJECTED")) == 1
    # and the rejected value was NOT retained
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.factors_snapshot["taper"] == 1.0


# ---------------------------- factors ---------------------------- #

def test_vol_norm_exact_vectors() -> None:
    assert vol_norm(0.0008, 0.0008) == 1.0
    assert vol_norm(0.0004, 0.0008) == 1.0
    assert vol_norm(0.0016, 0.0008) == 0.5
    assert vol_norm(0.0032, 0.0008) == 0.25
    with pytest.raises(DataQualityError):
        vol_norm(-1.0, 0.0008)


def test_vol_norm_pinned_until_warm_then_dampens() -> None:
    from core.data.bars import Bar

    gov, log = mk_governor()
    base = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert base.factors_snapshot.get("vol_norm_pinned") is True
    assert len(log.events("VOL_NORM_PINNED")) >= 1
    # feed hot BARS (GAP-0059): true-range ATR/close far above the 0.0008 target
    mid = 1.1
    for i in range(40):
        nxt = mid * (1.004 if i % 2 else 0.996)
        lo, hi = min(mid, nxt), max(mid, nxt)
        gov.observe_bar("EUR_USD", Bar(
            ts_open=T0 + timedelta(minutes=i), open=mid, high=hi, low=lo,
            close=nxt, spread=0.0002, duration_s=60))
        mid = nxt
    hot = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert hot.factors_snapshot["vol_norm"] < 1.0
    assert hot.size_units < base.size_units


def test_liquidity_and_correlation_factors() -> None:
    assert liquidity_factor(LiqState.DEEP) == 1.0
    assert liquidity_factor(LiqState.THIN) == 0.4
    assert liquidity_factor(LiqState.ILLIQUID) == 0.0
    nav = Decimal("10000")
    assert correlation_factor(["c"], {"c": Decimal("0")}, nav, 20.0) == 1.0
    assert correlation_factor(["c"], {"c": Decimal("2000")}, nav, 20.0) == 0.0
    assert correlation_factor(["c"], {"c": Decimal("1000")}, nav, 20.0) == 0.5


def test_half_life_never_changes_size() -> None:
    import dataclasses
    gov, _ = mk_governor()
    short = dataclasses.replace(mk_regime(), estimated_half_life_seconds=10)
    long = dataclasses.replace(mk_regime(), estimated_half_life_seconds=86400)
    a = gov.allocate(mk_signal(), mk_portfolio(), short, T0)
    b = gov.allocate(mk_signal(), mk_portfolio(), long, T0)
    assert a.size_units == b.size_units     # C-GOV-6


# ---------------------------- pair groups (C-GOV-10) ---------------------------- #

def _pair_signals(**overrides):
    a = mk_signal(strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="g1",
                  direction=-1, stop_loss=1.105, take_profit=1.09, **overrides)
    b = mk_signal(signal_id="sig-2", instrument="USD_JPY",
                  strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="g1",
                  direction=-1, entry_price=155.0, stop_loss=155.8, take_profit=153.9)
    return a, b


def test_group_sizes_both_or_neither_balanced() -> None:
    gov, _ = mk_governor()
    a, b = _pair_signals()
    oa, ob = gov.allocate_group((a, b), mk_portfolio(), mk_regime(), T0)
    assert oa.size_units > 0                      # balanced in USD (GAP-P12D-26):
    assert abs(oa.size_units * Decimal("1.1") - ob.size_units) <= Decimal("0.02")   # EUR leg × 1.1 = USD leg
    assert gov.open_groups() == ("g1",)


def test_group_blocked_leg_kills_both() -> None:
    # blackout only USD_JPY on a restricted account: leg B zero => both zero
    restricted = mk_rulebook(news=NewsRules(restricted=True, window_before_s=600,
                                            window_after_s=600))
    gov, log = mk_governor(rulebook=restricted,
                           blackout=lambda inst, now: inst == "USD_JPY")
    a, b = _pair_signals()
    oa, ob = gov.allocate_group((a, b), mk_portfolio(), mk_regime(), T0)
    assert oa.size_units == 0 and ob.size_units == 0
    assert oa.reason == "group_blocked:blackout"
    assert gov.open_groups() == ()
    assert len(log.events("GROUP_BLOCKED")) == 1


def test_group_exit_closes_both_legs() -> None:
    gov, log = mk_governor()
    a, b = _pair_signals()
    gov.allocate_group((a, b), mk_portfolio(), mk_regime(), T0)
    closes = gov.check_group_exits({"g1": "coupling_break"}, T0 + timedelta(hours=1))
    assert len(closes) == 2
    assert all(o.action == "close" and o.reason == "coupling_break" for o in closes)
    assert {o.instrument for o in closes} == {"EUR_USD", "USD_JPY"}
    assert gov.open_groups() == ()
    assert len(log.events("GROUP_EXIT")) == 1
    # unknown group: no orders, logged, no crash
    assert gov.check_group_exits({"ghost": "reconvergence"}, T0) == ()
    assert len(log.events("GROUP_EXIT_UNKNOWN")) == 1


def test_mismatched_group_ids_raise() -> None:
    gov, _ = mk_governor()
    a, b = _pair_signals()
    import dataclasses
    b2 = mk_signal(signal_id="sig-3", instrument="USD_JPY",
                   strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="OTHER",
                   direction=-1, entry_price=155.0, stop_loss=155.8, take_profit=153.9)
    with pytest.raises(DataQualityError):
        gov.allocate_group((a, b2), mk_portfolio(), mk_regime(), T0)


def test_determinism_same_inputs_same_size() -> None:
    gov, _ = mk_governor()
    a = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    b = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert a.size_units == b.size_units and a.reason == b.reason


# ---------------- phase-6 audit triage regressions (GAP-0049..0053) ---------------- #

def _usd_quote_pair():
    """Two legs BOTH long with USD as quote: per-leg USD deltas look small, the
    NET is double — the auditor's exact GAP-0049 scenario."""
    a = mk_signal(strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="gq",
                  conviction=1.0)
    b = mk_signal(signal_id="sig-2", instrument="GBP_USD",
                  strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="gq",
                  conviction=1.0, entry_price=1.3, stop_loss=1.29, take_profit=1.32)
    return a, b


def test_gap0049_group_net_delta_breach_blocks_both() -> None:
    gov, log = mk_governor(base_unit=4000.0)   # each leg ~2600-3200 USD notional
    gov._clusters = {}                         # isolate the delta check from cluster caps
    heavy_usd = mk_portfolio(per_currency_delta=MappingProxyType(
        {"USD": Decimal("-1000")}))
    oa, ob = gov.allocate_group(_usd_quote_pair(), heavy_usd, mk_regime(), T0)
    # per-leg USD contribution ≈ -2900 each (< 3000 cap alone); net ≈ -5800+(-1000)
    assert oa.size_units == 0 and ob.size_units == 0
    assert oa.reason == "group_blocked:currency_delta_cap"
    assert gov.open_groups() == ()
    assert len(log.events("CURRENCY_DELTA_ZERO")) == 1


def test_gap0049_group_cluster_counted_once_and_capped() -> None:
    gov, log = mk_governor(base_unit=4000.0)
    # both legs' instruments in ONE cluster near its cap
    gov._clusters = {"usd_bloc": ["EUR_USD", "GBP_USD"]}
    near_cap = mk_portfolio(per_cluster_exposure=MappingProxyType(
        {"usd_bloc": Decimal("1500")}))
    oa, ob = gov.allocate_group(_usd_quote_pair(), near_cap, mk_regime(), T0)
    assert oa.size_units == 0 and ob.size_units == 0
    assert oa.reason == "group_blocked:cluster_cap"


def test_gap0049_healthy_group_still_sizes() -> None:
    gov, _ = mk_governor()
    a = mk_signal(strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="g1",
                  direction=-1, stop_loss=1.105, take_profit=1.09)
    b = mk_signal(signal_id="sig-2", instrument="USD_JPY",
                  strategy_type=StrategyType.PAIR_DIVERGENCE, group_id="g1",
                  direction=-1, entry_price=155.0, stop_loss=155.8, take_profit=153.9)
    oa, ob = gov.allocate_group((a, b), mk_portfolio(), mk_regime(), T0)
    assert oa.size_units > 0 and abs(oa.size_units * Decimal("1.1") - ob.size_units) <= Decimal("0.02")


def test_gap0050_taper_only_call_never_clears_alpha_decay() -> None:
    gov, log = mk_governor()
    gov.apply_risk_state(alpha_decay=True)
    throttled = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    gov.apply_risk_state(taper_factor=0.9)      # the auditor's exploit call
    after = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert after.size_units <= throttled.size_units          # never a raise
    assert log.events("ALPHA_DECAY_CLEARED") == []
    gov.apply_risk_state(alpha_decay=False)     # explicit relaxation: allowed + audited
    assert len(log.events("ALPHA_DECAY_CLEARED")) == 1


def test_gap0051_risk_reducing_order_passes_a_breached_delta() -> None:
    gov, _ = mk_governor()
    breached = mk_portfolio(per_currency_delta=MappingProxyType(
        {"EUR": Decimal("3600")}))              # already over the 3000 cap
    short = mk_signal(direction=-1, stop_loss=1.105, take_profit=1.09)
    order = gov.allocate(short, breached, mk_regime(), T0)
    assert order.size_units > 0                 # reducing |delta|: never blocked
    long = mk_signal()
    assert gov.allocate(long, breached, mk_regime(), T0).reason == "currency_delta_cap"


def test_gap0052_registry_rebuilds_from_portfolio_positions() -> None:
    from core.governor.portfolio_types import Position
    gov, log = mk_governor()                    # fresh instance = post-restart
    legs = (
        Position(instrument="EUR_USD", direction=-1, size_units=Decimal("400"),
                 entry_price=1.1, stop_loss=1.105, take_profit=1.09, opened_at=T0,
                 strategy_type=StrategyType.PAIR_DIVERGENCE, param_set_id="ps-1",
                 group_id="g-old"),
        Position(instrument="USD_JPY", direction=-1, size_units=Decimal("400"),
                 entry_price=155.0, stop_loss=155.8, take_profit=153.9, opened_at=T0,
                 strategy_type=StrategyType.PAIR_DIVERGENCE, param_set_id="ps-1",
                 group_id="g-old"),
    )
    portfolio = mk_portfolio(open_positions=legs)
    assert gov.rebuild_groups(portfolio) == 1
    assert gov.open_groups() == ("g-old",)
    closes = gov.check_group_exits({"g-old": "coupling_break"}, T0)
    assert len(closes) == 2 and all(o.action == "close" for o in closes)
    # an orphan (single leg) is surfaced, never silently adopted
    orphan = mk_portfolio(open_positions=(legs[0],))
    gov2, log2 = mk_governor()
    assert gov2.rebuild_groups(orphan) == 0
    assert len(log2.events("GROUP_REBUILD_ORPHAN")) == 1


@pytest.mark.parametrize("month, close_utc", [(7, 21), (1, 22)])   # 17:00 New York, EDT / EST
def test_swing_account_refuses_an_entry_an_hour_before_the_friday_close(month, close_utc) -> None:
    """GAP-P12D-58: FTMO forbids opening a trade "two hours or less before a relevant
    financial market is closed for at least two hours" on EVERY account type, so the
    pre-close ban binds an account that may hold over the weekend (FTMO Swing) too."""
    friday = datetime(2026, 7, 10) if month == 7 else datetime(2026, 1, 9)
    close = friday.replace(hour=close_utc, tzinfo=timezone.utc)
    swing = mk_rulebook(weekend_holding_allowed=True)
    gov, _ = mk_governor(rulebook=swing)
    for at, reason in ((close - timedelta(hours=1), "weekend_ban"),
                       (close - timedelta(hours=2), "weekend_ban"),        # the fence post
                       (close - timedelta(hours=2, minutes=1), "formula")):
        sig = mk_signal(generated_at=at)
        assert gov.allocate(sig, mk_portfolio(), mk_regime(), at).reason == reason, at


def test_gap0053_weekend_ban_covers_the_whole_closed_window() -> None:
    no_weekend = mk_rulebook(weekend_holding_allowed=False)
    gov, _ = mk_governor(rulebook=no_weekend)
    for instant in (
        datetime(2026, 7, 10, 23, 30, tzinfo=timezone.utc),   # Friday post-close
        datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),    # Saturday
        datetime(2026, 7, 12, 20, 30, tzinfo=timezone.utc),   # Sunday pre-open (21:00 EDT)
        datetime(2026, 1, 11, 21, 30, tzinfo=timezone.utc),   # Sunday pre-open (22:00 EST)
    ):
        sig = mk_signal(generated_at=instant)
        assert gov.allocate(sig, mk_portfolio(), mk_regime(), instant).reason == "weekend_ban"
    # GAP-P12D-10: the summer market reopens at 21:00 UTC, not 22:00
    for after_open in (datetime(2026, 7, 12, 21, 30, tzinfo=timezone.utc),
                       datetime(2026, 1, 11, 22, 30, tzinfo=timezone.utc)):
        sig = mk_signal(generated_at=after_open)
        assert gov.allocate(sig, mk_portfolio(), mk_regime(), after_open).reason == "formula"


# ---------------- v2.11 internal-audit triage regressions (GAP-0058) ---------------- #

def test_gap0058_tsmom_position_with_no_target_is_representable() -> None:
    from core.governor.portfolio_types import Position
    pos = Position(instrument="EUR_USD", direction=1, size_units=Decimal("100"),
                   entry_price=1.1, stop_loss=1.05, take_profit=None, opened_at=T0,
                   strategy_type=StrategyType.TSMOM, param_set_id="ps-1")
    assert pos.take_profit is None
    with pytest.raises(DataQualityError):            # stop stays mandatory (§8.6)
        Position(instrument="EUR_USD", direction=1, size_units=Decimal("100"),
                 entry_price=1.1, stop_loss=float("nan"), take_profit=None,
                 opened_at=T0, strategy_type=StrategyType.TSMOM, param_set_id="ps-1")


# ---------------- phase-7 audit triage regression (GAP-0074) ---------------- #

def test_gap0074_solo_hard_cluster_cap_fires_when_base_unit_exceeds_cap() -> None:
    """The hard SOLO cluster_cap guard is the backstop for configs where
    base_unit_usd exceeds the cluster cap (schema allows it): the soft
    correlation factor is 1.0 on an empty book, yet the order's own notional
    breaches the cap -> hard zero, never a clamp, attributed to the gate."""
    gov, log = mk_governor(base_unit=5000.0)  # raw ~2430 USD > 20% x 10k cap
    order = gov.allocate(mk_signal(), mk_portfolio(), mk_regime(), T0)
    assert order.size_units == 0
    assert order.reason == "cluster_cap"
    assert gov.skips["cluster_cap"] == 1      # SPEC 10 C15 attribution
    assert any(e["event_type"] == "CLUSTER_CAP_ZERO" for e in log.events())


def test_apply_session_halt_upward_edge_autoclears_and_never_shortens() -> None:
    # ACIS-07 §7 (phase 9): Risk's daily-drawdown halt lands session-scoped —
    # blocks new entries, auto-clears at the next boundary (master §8), and a
    # second call can only ever extend, never shorten, the halt in force.
    gov, log = mk_governor()
    gov.apply_session_halt(T0, "daily_drawdown")          # T0 10:00 -> until 12:00
    assert gov.allocate(mk_signal(), mk_portfolio(), mk_regime(),
                        T0).reason == "drawdown_halt"
    assert any(e["data"]["scope"] == "session"
               for e in log.events("HALT_APPLIED"))
    at_11 = T0.replace(hour=11)
    gov.apply_session_halt(at_11, "daily_drawdown")       # same boundary — no shorten
    past_boundary = T0.replace(hour=12, minute=1)
    fresh = mk_signal(generated_at=past_boundary)
    assert gov.allocate(fresh, mk_portfolio(), mk_regime(),
                        past_boundary).reason == "formula"
