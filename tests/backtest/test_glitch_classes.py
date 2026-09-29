"""§13 futures/account glitch classes at the BACKTEST level (ACIS-09 C-BT-10).

The seven forex/account classes testable in phase-11 validation. Each gets an
explicit backtest-context test; where the guard lives at another layer, the test
exercises that guard through a backtest-relevant fixture (never a re-import stub).

The two FUTURES-LIFECYCLE classes — contract-roll gap and expiry-with-open-
position — require the futures roll-or-flatten policy, which lands with futures
enablement at phase 12 (their precondition: no enabled futures ⇒ inert in forex
validation). See GAP-0109 + ACIS-09 §13 C-BT-10.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from tests.backtest.carry import carry_charge, swap_multiplier


# -- 1. triple-swap Wednesday carry ------------------------------------------- #

def test_triple_swap_wednesday_carry() -> None:
    # Wed 2026-01-07 is weekday 2 → triple; Tue/Thu → single
    assert swap_multiplier(date(2026, 1, 7)) == 3
    assert swap_multiplier(date(2026, 1, 6)) == 1
    # held Tue-night + Wed-night: naive 2× swap, correct = 1 + 3 = 4×
    nights = [date(2026, 1, 6), date(2026, 1, 7)]
    charged = carry_charge(nights=nights, daily_swap=Decimal("-0.50"))
    assert charged == Decimal("-2.00")                 # 4 × -0.50, not 2 × -0.50


# -- 2. holiday half-day session end (not a feed outage) ---------------------- #

def test_holiday_half_day_is_session_end_not_outage() -> None:
    from core.data.asset_classes import build_calendars
    from config.schemas import load_config
    from pathlib import Path

    cfg = load_config(Path(__file__).resolve().parent.parent.parent / "config")
    cals = build_calendars(cfg.instruments.calendars)
    cme = cals["cme_metals"]                            # half_days: 2026-11-27 → 17:00
    # before the early close: open; after it: CLOSED (session END, the backtest
    # must treat the calendar-declared early close as the session end, not a gap)
    assert cme.session_at(datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc)) != "closed"
    assert cme.session_at(datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)) == "closed"


# -- 3. trailing-drawdown anchor (EOD approximation must fail) ----------------- #

def test_trailing_drawdown_anchor_uses_intraday_high_water() -> None:
    """§9.5: the platform-measured trailing DD anchors on the INTRADAY high-water
    equity; an end-of-day approximation understates the breach. A backtest that
    grades a prop account must measure it the platform's way."""
    from config.schemas import DrawdownRule
    from core.risk.guardrails import _RuleAnchor

    rule = DrawdownRule(type="trailing", anchor="intraday", basis="equity", limit_pct=5.0)
    tracker = _RuleAnchor()
    day = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)          # a Monday, mid-day
    kw = dict(resets_daily=False)
    tracker.update(rule, 10000.0, day.replace(hour=8), **kw)      # inception
    tracker.update(rule, 10500.0, day.replace(hour=10), **kw)     # intraday high-water 10500
    # drop to 10000: trailing DD = (10500-10000)/10500 = 4.76% off the high-water,
    # NOT 0% an EOD-vs-open (10000 vs 10000) approximation would show
    dd = tracker.update(rule, 10000.0, day.replace(hour=14), **kw)
    assert dd > 4.0                                    # measured off the intraday peak


# -- 4. symbol suffix mismatch never silently merged (§7.5) ------------------- #

def test_symbol_suffix_incomplete_map_rejected_at_attach() -> None:
    """GAP-P11I-09 (real guard, not a re-assertion): the §13 suffix problem dies
    ONCE at attach — `verify_attach` REJECTS a descriptor whose symbol map does
    not cover the enabled universe, so an unmapped `EURUSD`/`EURUSD.pro` can never
    be silently merged or fabricated in a backtest."""
    import asyncio

    from core.data.errors import DataQualityError
    from core.execution.attach import verify_attach
    from core.execution.mock_face import MockExecutionFace
    from tests.optimizer_fixtures import CapturingLogger

    face = MockExecutionFace()
    with pytest.raises(DataQualityError):               # a symbol not in the map → reject
        asyncio.run(verify_attach(face, {"EUR_USD", "GBP_USD_UNMAPPED"}, CapturingLogger()))


# -- 5. limit-lock / exchange halt ⇒ ILLIQUID, stops not assumed to fill ------- #

def test_limit_lock_illiquid_ties_to_gap_law() -> None:
    """A limit-lock/exchange halt makes the instrument ILLIQUID; stops cannot be
    assumed to fill at level — the §8.5 gap law prices the loss at the reopening
    gap, never the stop level (the scenario-replay gate proves it)."""
    from tests.backtest.test_scenario_replay import _NAV, _SL_CAP, _replay
    from config.schemas import load_config
    from pathlib import Path

    cfg = load_config(Path(__file__).resolve().parent.parent.parent / "config")
    replay = _replay(cfg.scenario_book, cfg.guardrails,
                     dict(cfg.instruments.instruments), clusters=cfg.instruments.clusters)
    # the gap-through-stop scenario prices loss at |gap|, not at the (irrelevant) stop
    chf = next(sc for sc in cfg.scenario_book.scenarios if sc.name == "chf_depeg_2015")
    v = replay.replay_one(chf)
    worst = float(v.worst_book_notional)
    assert v.loss_pct_nav == worst * 0.35 / float(_NAV) * 100.0   # gap-priced, not stop-priced


# -- 6. weekend-ban fencepost (flattened before the holding-ban window) -------- #

def test_weekend_ban_fencepost_inclusive() -> None:
    """A position must be flat before the platform's weekend holding-ban window;
    the boundary is provably inclusive (a backtest on a no-weekend-hold account
    must not carry a position into the banned window)."""
    from tests.backtest.data_loader import _is_weekend
    # Friday 22:00 UTC is the fencepost — inclusive: 21:59 tradeable, 22:00 banned
    assert not _is_weekend(datetime(2026, 1, 2, 21, 59, tzinfo=timezone.utc))
    assert _is_weekend(datetime(2026, 1, 2, 22, 0, tzinfo=timezone.utc))


# -- 7. Tier-G shock during blackout: deterministic classification ------------ #

def test_tierg_deterministic_keyword_match_in_backtest() -> None:
    """GAP-P11I-09 (real guard): a backtest replaying headlines classifies them by
    the REAL deterministic keyword taxonomy — a matching headline arms Tier-G on
    the affected instruments, gibberish changes nothing (untrusted-input law
    C-EVT-6). (The full stricter-of / two-layer enforcement during a blackout is
    proven at the events+governor layer, test_events.py; this pins the classifier
    the backtest actually drives.)"""
    from core.data.events import Headline, TierGClassifier
    from config.schemas import load_config
    from pathlib import Path
    from tests.optimizer_fixtures import CapturingLogger

    cfg = load_config(Path(__file__).resolve().parent.parent.parent / "config")
    ts = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)   # a Monday
    cls, entry = next(iter(cfg.event_sources.tierg_taxonomy.items()))
    keyword = entry.keywords[0]

    matched = TierGClassifier(cfg.event_sources, CapturingLogger())
    matched.observe(Headline(text=f"Breaking news: {keyword} reported today",
                             source="reuters", published_at=ts))
    assert any(k[0] == cls for k in matched._state)      # the real keyword armed Tier-G

    inert = TierGClassifier(cfg.event_sources, CapturingLogger())
    inert.observe(Headline(text="local sports team wins the cup",
                           source="reuters", published_at=ts))
    assert not inert._state                              # gibernish arms nothing (C-EVT-6)
