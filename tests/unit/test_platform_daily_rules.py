"""Daily-reset platform rules and a declared initial capital (GAP-P12D-54 / -59; §9.5).

FTMO's own rules (ftmo.com/en/trading-objectives/, dateModified 2026-09-24 when re-fetched by
the external audit on 2026-09-25; the 2-Step semantics are unchanged — audit X8):
  * Maximum Daily Loss — "recalculated daily at 00:00 CE(S)T as the difference between:
    the account balance recorded at 00:00 CE(S)T of the current day and the Maximum Daily
    Loss Amount, which is 5% of the Initial Simulated Capital", tested on "account equity
    (i.e., Balance + Open Positions P/L ± Swaps – Commissions)";
  * Maximum Loss — "a static limit ... below which your account equity ... cannot drop",
    at 10% of the initial capital.
The page's worked example on $100,000: the day-1 limit is $95,000; after a day that
closes at a $102,000 balance, the day-2 limit is $97,000.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.schemas import (AccountRulebook, DrawdownRule, NewsRules, PlatformRules,
                            ZonedTime)
from core.risk.guardrails import GuardrailContext
from core.risk.store import RiskStore, restore_on_boot
from tests.risk_fixtures import RecordingSink, acct, build_monitor, load_cfg

UTC = timezone.utc
PRAGUE_MIDNIGHT = ZonedTime(zone="Europe/Prague", at="00:00")
DAILY = "ftmo_2step:daily:intraday:equity"
MAX_LOSS = "ftmo_2step:static:intraday:equity"


def ftmo_rulebook(initial: float) -> AccountRulebook:
    return AccountRulebook(
        platform="ctrader", news=NewsRules(restricted=False), min_hold_seconds=0,
        weekend_holding_allowed=True, initial_capital=initial, drawdown_rules=[
            DrawdownRule(type="daily", anchor="intraday", basis="equity",
                         reset=PRAGUE_MIDNIGHT, reset_basis="balance",
                         limit_of="initial", limit_pct=5.0),
            DrawdownRule(type="static", anchor="intraday", basis="equity",
                         limit_of="initial", limit_pct=10.0)])


def _monitor(rulebook: AccountRulebook, sink, store=None, boot=None):
    cfg = load_cfg()
    accounts = {**cfg.platform_rules.accounts, "ftmo_2step": rulebook}
    cfg = cfg.model_copy(update={"platform_rules": PlatformRules(accounts=accounts)})
    return build_monitor(cfg, sink, account="ftmo_2step", store=store, boot=boot)


def _check(guards, *, equity, balance, at):
    out = guards.check(GuardrailContext(
        now=at, equity=_d(equity), balance=_d(balance), nav=_d(equity),
        per_instrument_drawdown_pct={}, var_pct=0.0, max_cluster_pct=0.0,
        slippage_slope_bps=0.0, tierg_flatten={}))
    return {s.rule_key: s for s in out.platform_drawdown}


def _d(x):
    from decimal import Decimal
    return Decimal(str(x))


# FTMO's day 1 is Tue 14 July 2026: 00:00 CEST = 13 July 22:00 UTC.
DAY1 = datetime(2026, 7, 14, 6, 0, tzinfo=UTC)
DAY2_RESET = datetime(2026, 7, 14, 22, 0, tzinfo=UTC)          # 00:00 CEST, 15 July


def test_ftmo_day1_floor_is_95000_on_equity() -> None:
    sink = RecordingSink()
    _, g, _, _ = _monitor(ftmo_rulebook(100_000.0), sink)
    s = _check(g, equity=95_000.01, balance=100_000.0, at=DAY1)
    assert s[DAILY].measured_pct == pytest.approx(4.99999, abs=1e-4)      # just inside
    assert not sink.halts
    s = _check(g, equity=94_999.0, balance=100_000.0, at=DAY1 + timedelta(hours=1))
    assert s[DAILY].distance_fraction >= 1.0                               # through $95,000
    assert ("all", f"platform_dd:{DAILY}") in sink.halts


def test_ftmo_day2_floor_is_97000_after_a_102000_close() -> None:
    sink = RecordingSink()
    _, g, _, _ = _monitor(ftmo_rulebook(100_000.0), sink)
    _check(g, equity=100_000.0, balance=100_000.0, at=DAY1)
    _check(g, equity=102_000.0, balance=102_000.0, at=DAY2_RESET - timedelta(minutes=5))
    s = _check(g, equity=97_000.01, balance=102_000.0, at=DAY2_RESET + timedelta(hours=8))
    assert s[DAILY].measured_pct == pytest.approx(4.99999, abs=1e-4)      # floor 102k − 5k
    assert s[MAX_LOSS].measured_pct == pytest.approx(2.99999, abs=1e-4)   # static: 100k − 10%
    assert not sink.halts
    _check(g, equity=96_999.0, balance=102_000.0, at=DAY2_RESET + timedelta(hours=9))
    assert ("all", f"platform_dd:{DAILY}") in sink.halts


def test_ftmo_max_loss_is_static_on_equity_at_initial_minus_10pct() -> None:
    sink = RecordingSink()
    _, g, _, _ = _monitor(ftmo_rulebook(100_000.0), sink)
    # an account attached while already in profit: the line is still initial − 10%
    s = _check(g, equity=110_000.0, balance=110_000.0, at=DAY1)
    assert s[MAX_LOSS].measured_pct == 0.0
    s = _check(g, equity=90_000.5, balance=110_000.0, at=DAY1 + timedelta(minutes=1))
    assert s[MAX_LOSS].measured_pct == pytest.approx(9.9995, abs=1e-4)    # floating, on equity
    assert s[MAX_LOSS].distance_fraction < 1.0


def test_floating_loss_at_the_engine_rollover_does_not_hide_ftmos_floor() -> None:
    # The lead's case: $6,000, balance 6,000 with −240 floating at the 17:00 New York
    # rollover (21:00 UTC in July). The engine's 2% daily anchors on equity 5,760 and
    # halts at 5,644.80; FTMO's floor is 6,000 − 300 = 5,700 from 00:00 CEST (22:00 UTC).
    # GAP-P12D-56: the absolute $9,000 equity floor also halts any $6k account at its
    # first check (owner-owned); every later halt coalesces under it, so the breach is
    # read from the rule's own measurement and its PLATFORM_DD_BREACH record.
    sink = RecordingSink()
    _, g, _, log = _monitor(ftmo_rulebook(6_000.0), sink)

    def breached() -> bool:
        return any(e["data"]["rule_key"] == DAILY for e in log.events("PLATFORM_DD_BREACH"))

    roll = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)
    _check(g, equity=6_000.0, balance=6_000.0, at=roll - timedelta(minutes=1))
    _check(g, equity=5_760.0, balance=6_000.0, at=roll)                      # engine day opens
    s = _check(g, equity=5_701.0, balance=6_000.0, at=roll + timedelta(hours=1, minutes=1))
    assert s[DAILY].distance_fraction < 1.0 and not breached()
    s = _check(g, equity=5_699.0, balance=6_000.0, at=roll + timedelta(hours=2))
    assert s[DAILY].distance_fraction >= 1.0 and breached()                  # FTMO's line holds
    assert s["engine:daily"].distance_fraction < 0.6     # the engine's own 2% is nowhere near
    assert ("all", "equity_floor") in sink.halts         # GAP-P12D-56, recorded as it is


def test_a_loss_booked_just_after_the_reset_still_counts_against_the_day() -> None:
    # FTMO reads the balance AT 00:00. A stop that closes at a loss two seconds later
    # must not lower the day's anchor: the engine keeps the larger bracketing sample.
    sink = RecordingSink()
    _, g, _, _ = _monitor(ftmo_rulebook(6_000.0), sink)
    _check(g, equity=6_000.0, balance=6_000.0, at=DAY2_RESET - timedelta(seconds=5))
    s = _check(g, equity=5_900.0, balance=5_900.0, at=DAY2_RESET + timedelta(seconds=5))
    assert s[DAILY].measured_pct == pytest.approx(100 / 6_000 * 100)       # not 0%


def test_max_reset_basis_takes_the_higher_of_balance_and_equity() -> None:
    rb = ftmo_rulebook(10_000.0).model_copy(update={"drawdown_rules": [DrawdownRule(
        type="daily", anchor="intraday", basis="equity", reset=PRAGUE_MIDNIGHT,
        reset_basis="max", limit_pct=5.0)]})
    sink = RecordingSink()
    _, g, _, _ = _monitor(rb, sink)
    s = _check(g, equity=10_400.0, balance=10_000.0, at=DAY1)   # floating profit at the reset
    s = _check(g, equity=10_000.0, balance=10_000.0, at=DAY1 + timedelta(hours=1))
    assert s[DAILY].measured_pct == pytest.approx(400 / 10_400 * 100)    # anchored on 10,400


def test_declared_initial_capital_anchors_a_static_rule_and_seeds_a_trailing_one() -> None:
    rb = ftmo_rulebook(10_000.0).model_copy(update={"drawdown_rules": [
        DrawdownRule(type="static", anchor="eod", basis="balance", limit_pct=10.0),
        DrawdownRule(type="trailing", anchor="intraday", basis="equity", limit_pct=5.0)]})
    sink = RecordingSink()
    _, g, _, _ = _monitor(rb, sink)
    s = _check(g, equity=9_800.0, balance=9_800.0, at=DAY1)     # attached 2% under water
    assert s["ftmo_2step:static:eod:balance"].measured_pct == pytest.approx(2.0)
    assert s["ftmo_2step:trailing:intraday:equity"].measured_pct == pytest.approx(2.0)


def test_restart_keeps_the_ftmo_day_anchor_and_never_restores_below_initial(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    sink = RecordingSink()
    mon, _, _, _ = _monitor(ftmo_rulebook(100_000.0), sink, store=store, boot=DAY1)
    mon.evaluate(acct(100_000.0), DAY1)
    mon.evaluate(acct(102_000.0), DAY2_RESET - timedelta(minutes=5))
    mon.evaluate(acct(98_000.0, balance=102_000.0), DAY2_RESET + timedelta(hours=1))
    # the static anchor on disk is tampered low: the restore still reads initial capital
    anchors = store.load_anchors()
    anchors[MAX_LOSS]["anchor"] = 50_000.0
    store.save_restrictive_state(alpha_armed=False, taper_factor=1.0, anchors=anchors)
    sink2 = RecordingSink()
    mon2, _, _, _ = _monitor(ftmo_rulebook(100_000.0), sink2, store=store)
    restore_on_boot(store, mon2, DAY2_RESET + timedelta(hours=2))
    snap = mon2.evaluate(acct(98_000.0, balance=102_000.0), DAY2_RESET + timedelta(hours=2))
    rules = {s.rule_key: s.measured_pct for s in snap.platform_drawdown}
    assert rules[DAILY] == pytest.approx(4.0)          # 102,000 day anchor, 5% of 100k
    assert rules[MAX_LOSS] == pytest.approx(2.0)       # initial 100,000, not the tampered 50,000
    store.close()


def test_daily_rule_schema_is_explicit() -> None:
    with pytest.raises(ValueError):
        DrawdownRule(type="daily", anchor="intraday", basis="equity", limit_pct=5.0)
    with pytest.raises(ValueError):
        DrawdownRule(type="static", anchor="eod", basis="balance", limit_pct=10.0,
                     reset=PRAGUE_MIDNIGHT, reset_basis="balance")
    with pytest.raises(ValueError):                    # % of initial, but none declared
        AccountRulebook(**{**ftmo_rulebook(10_000.0).model_dump(), "initial_capital": None})
    assert ftmo_rulebook(10_000.0).drawdown_rules[0].reset.zone == "Europe/Prague"


def test_the_shipped_rulebooks_keep_their_meaning() -> None:
    cfg = load_cfg()
    for key, rb in cfg.platform_rules.accounts.items():
        if key == "pepperstone_demo":                 # R6-5: the target path's capital_ref, sizing no rule
            assert (rb.initial_capital, rb.vol_target_annual, rb.drawdown_rules) == (10_000, 0.10, [])
        else:
            assert rb.initial_capital is None
        assert all(r.type != "daily" and r.limit_of == "anchor" for r in rb.drawdown_rules)
