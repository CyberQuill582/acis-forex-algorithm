"""A restart never relaxes a drawdown limit (GAP-P12D-55; GAP-0050; ACIS-07 §7).

The anchors of every drawdown rule — the static inception anchor, the trailing
high-water mark, the engine's daily day-open anchor with its day — and the last
delivered taper are persisted after every evaluate and restored before the first
evaluate of the next process. Before this fix a restarted engine re-based every
rule at the first equity it saw and read 0% (and a fresh 1.0 taper) on an account
already 6% down."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.data.errors import DataQualityError
from core.risk.guardrails import build_drawdown_series
from core.risk.store import RiskStore, restore_on_boot
from tests.risk_fixtures import RecordingSink, T0, acct, build_monitor, load_cfg

FTMO_TRAILING = "ftmo:trailing:intraday:equity"
FTMO_STATIC = "ftmo:static:eod:balance"


def _all_rules(snap) -> dict[str, float]:
    out = {s.rule_key: s.measured_pct for s in snap.platform_drawdown}
    out["engine:daily"] = snap.daily_drawdown_pct
    return out


def _run_down_to_9400(cfg, store):
    """The first process: a $10k ftmo account falls to 9,400 (−6%) on one day."""
    sink = RecordingSink()
    mon, _, _, _ = build_monitor(cfg, sink, account="ftmo", store=store, boot=T0)
    mon.evaluate(acct(10000.0), T0)
    snap = mon.evaluate(acct(9400.0), T0 + timedelta(minutes=30))
    return snap, sink


def _restart(cfg, store, now=T0 + timedelta(minutes=40)):
    """A fresh process on the same store: nothing in memory survives."""
    sink = RecordingSink()
    mon, _, _, log = build_monitor(cfg, sink, account="ftmo", store=store)
    restore_on_boot(store, mon, now)
    return mon, sink, log


def test_restart_at_a_drawdown_still_reads_it_on_every_rule(tmp_path) -> None:
    # The lead's reproduction: 10,000 → 9,400, then rebuild everything.
    cfg = load_cfg()
    store = RiskStore(tmp_path / "risk.db")
    before, _ = _run_down_to_9400(cfg, store)
    assert _all_rules(before) == pytest.approx(
        {"engine:daily": 6.0, FTMO_TRAILING: 6.0, FTMO_STATIC: 6.0})
    assert before.taper_factor == 0.0

    mon, sink, log = _restart(cfg, store)
    # the taper is back on the (fresh) Governor BEFORE the first evaluate
    assert sink.risk_states[0] == (0.0, None)
    assert log.events("TAPER_RESTORED")[0]["data"]["factor"] == 0.0
    after = mon.evaluate(acct(9400.0), T0 + timedelta(minutes=40))
    assert _all_rules(after) == pytest.approx(
        {"engine:daily": 6.0, FTMO_TRAILING: 6.0, FTMO_STATIC: 6.0})   # NOT 0.0
    assert after.taper_factor == 0.0                                    # NOT 1.0
    # and the restarted engine halts again instead of trading a fresh budget
    assert ("all", f"platform_dd:{FTMO_TRAILING}") in sink.halts
    assert sink.session_halts == ["daily_drawdown"]
    store.close()


def test_restart_across_a_trading_day_boundary_reanchors_the_daily_rule(tmp_path) -> None:
    # The first process dies on Wed 15 July; the engine restarts on Thu 16 July,
    # after the 21:00 UTC (17:00 EDT) rollover it never saw.
    cfg = load_cfg()
    store = RiskStore(tmp_path / "risk.db")
    _run_down_to_9400(cfg, store)
    next_day = T0 + timedelta(days=1)

    mon, _, _ = _restart(cfg, store)
    snap = mon.evaluate(acct(9400.0), next_day)
    rules = _all_rules(snap)
    assert rules["engine:daily"] == pytest.approx(0.0)       # a new day: yesterday is not today
    assert rules[FTMO_TRAILING] == pytest.approx(6.0)        # the account rules never reset
    assert rules[FTMO_STATIC] == pytest.approx(6.0)
    day = store.load_anchors()["engine:daily"]["day"]
    assert day == "2026-07-15"                                # the new trading day, persisted


def test_a_loss_taken_while_the_engine_was_down_is_not_forgotten(tmp_path) -> None:
    # Down over the rollover, the account slid 9,400 → 9,300. The engine never saw
    # the rollover, so the new day anchors on the larger of the two samples that
    # bracket it (the last persisted 9,400) — never on the lower boot value.
    cfg = load_cfg()
    store = RiskStore(tmp_path / "risk.db")
    _run_down_to_9400(cfg, store)
    mon, _, _ = _restart(cfg, store)
    snap = mon.evaluate(acct(9300.0), T0 + timedelta(days=1))
    assert snap.daily_drawdown_pct == pytest.approx((9400 - 9300) / 9400 * 100)
    # a second rollover watched in-process re-anchors on its first observation, as ratified
    snap = mon.evaluate(acct(9300.0), T0 + timedelta(days=2))
    assert snap.daily_drawdown_pct == pytest.approx(0.0)


def test_store_keeps_anchors_apart_from_the_legacy_restrictive_keys(tmp_path) -> None:
    store = RiskStore(tmp_path / "risk.db")
    store.save_restrictive_state(alpha_armed=False, taper_factor=0.5,
                                 anchors={"engine:daily": {"anchor": 10000.0,
                                                           "day": "2026-07-14", "last": 9900.0}})
    assert store.load_restrictive_state() == {"alpha_armed": False, "taper_factor": 0.5, "alpha_baseline": None}
    assert store.load_anchors() == {"engine:daily": {"anchor": 10000.0, "day": "2026-07-14",
                                                     "last": 9900.0}}
    store.close()


def test_restore_refuses_a_corrupt_anchor_and_skips_a_retired_rule() -> None:
    cfg = load_cfg()
    rb = cfg.platform_rules.accounts["ftmo"]
    series = build_drawdown_series(cfg.guardrails, rb.drawdown_rules, "ftmo",
                                   initial_capital=rb.initial_capital)
    with pytest.raises(DataQualityError):
        series.restore({FTMO_STATIC: {"anchor": float("nan"), "day": None, "last": None}})
    with pytest.raises(DataQualityError):
        series.restore({FTMO_STATIC: {"anchor": -5.0, "day": None, "last": None}})
    restored = series.restore({"ftmo:gone:eod:equity": {"anchor": 1.0, "day": None,
                                                         "last": None}})
    assert restored == ()                         # a rule the rulebook no longer has


def test_two_rules_may_not_share_one_anchor() -> None:
    from config.schemas import DrawdownRule
    cfg = load_cfg()
    twin = DrawdownRule(type="static", anchor="eod", basis="balance", limit_pct=10.0)
    with pytest.raises(DataQualityError):
        build_drawdown_series(cfg.guardrails, [twin, twin.model_copy()], "x",
                              initial_capital=None)
