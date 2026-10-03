"""The target path's slow loop (core/runtime/target_loop.py; ACIS-04 v1.6 §4b, ACIS-05 v1.7 §6.4,
ACIS-03 v2.2): it decides after 17:00 New York, executes ONCE at the symbol's slot, re-derives the same
target after a restart, never catches up a missed slot, never re-enters a stopped position the same day,
skips holidays, and promotes a new family-version only once the universe is flat."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import partial
from zoneinfo import ZoneInfo

import pytest

from core.data.bars import Bar
from core.data.fx_clock import rollover_utc
from core.data.rates import RateTable
from core.governor.target_gate import target_orders
from core.runtime.history_store import HistoryStore
from core.runtime.target_decision import BookSizing, Lots
from core.runtime.target_loop import EngineView, Member, TargetLoop
from core.signals.daily import SLOTS
from tests.optimizer_fixtures import CapturingLogger

from tests.unit.test_governor import mk_governor, mk_portfolio, mk_rulebook

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
LOT = Decimal("1000")
DAY = date(2026, 9, 30)                                   # a Wednesday
AFTER = rollover_utc(DAY) + timedelta(minutes=3)          # 17:03 New York
SLOT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)           # 08:00 New York (EDT)
DARK = {date(2025, 12, 25), date(2026, 1, 1)}


def _bars(drift: float, seed: int, until=AFTER) -> list[Bar]:
    rng, out, px = random.Random(seed), [], 1.10
    t = datetime(2024, 10, 1, tzinfo=UTC)
    while t < until:
        fx_day = (t.astimezone(NY) + timedelta(hours=7)).date()             # the trading day 17:00 -> 17:00 closes
        if fx_day.weekday() < 5 and fx_day not in DARK and t + timedelta(hours=1) <= until:
            px *= math.exp(drift + rng.gauss(0, 0.0008))
            out.append(Bar(ts_open=t, open=px, high=px * 1.0004, low=px * 0.9996, close=px, spread=0.0, duration_s=3600))
        t += timedelta(hours=1)
    return out


@dataclass
class Held:
    instrument: str
    direction: int
    size_units: Decimal
    stop_loss: float | None = 1.0
    param_set_id: str = "trend_d1_v1"
    group_id: str | None = None


class Rig:
    def __init__(self, tmp_path, *, drift=0.0002, fetch_error=None, registered=True, open_=True) -> None:
        self.log, self.now = CapturingLogger(), AFTER
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.store = HistoryStore(tmp_path / "history.db")
        self.data = {"EUR_USD": _bars(drift, 1)}
        self.fail: set[str] = set()                    # instruments whose fetch raises
        self.held: dict[str, Held] = {}
        self.busy: set[str] = set()
        self.sent, self.flattened, self.fetches = [], [], []
        self.fetch_error, self.registered, self.open_ = fetch_error, registered, open_
        self.clock_ok, self.cap = True, LOT
        self.closing = []                         # each slot's `closing` argument (PR16I-04)
        self.feed_refusal = None                  # the feed watch's verdict at every slot
        gov, _ = mk_governor()
        days = [date(2024, 9, 1) + timedelta(days=k) for k in range(800)]
        self.rates = RateTable({"USD": [(d, 4.0) for d in days], "EUR": [(d, 3.0) for d in days],
                                "GBP": [(d, 3.5) for d in days]})
        self.gate = partial(target_orders, gov, limits=gov.guards._limits, rules=mk_rulebook(),
                            clusters={"usd_short": ["EUR_USD"]}, stop_mult=10.0, logger=self.log)

    async def fetch(self, instrument, start, end):
        self.fetches.append((instrument, start, end))
        if self.fetch_error or instrument in self.fail:
            raise self.fetch_error or ConnectionError(f"{instrument}: venue down")
        return [b for b in self.data[instrument] if start <= b.ts_open and b.ts_open + timedelta(hours=1) <= end]

    def loop(self, family="trend_d1_v1") -> TargetLoop:
        view = EngineView(held_of=self.held.get, busy=lambda: frozenset(self.busy), marks=lambda: {"EUR_USD": 1.2},
                          portfolio=lambda closing=(): (self.closing.append(closing), mk_portfolio(nav=Decimal("100000")))[1],
                          feed_refusal=lambda i, now: self.feed_refusal, submit=self.sent.append,
                          flatten=lambda scope, why: self.flattened.append((scope, why)),
                          clock_ok=lambda i: self.clock_ok)
        return TargetLoop(
            members={i: Member(i, "fx", "USD", SLOTS["fx"], lambda now: self.open_) for i in self.data},
            store=self.store, fetch=self.fetch, rates=lambda: self.rates,
            sizing=BookSizing(10_000, 0.10, 1.0, 0.10, {i: 1.0 for i in self.data}), lots_of=lambda i: Lots(LOT, LOT, self.cap),
            gate=self.gate, engine=view, family=family, registered=lambda f: self.registered, history_days=730,
            settle_s=120, slot_grace_s=300, atr_period=14, now_fn=lambda: self.now, logger=self.log)

    def events(self, kind):
        return [e["data"] for e in self.log.events(kind)]


async def test_it_decides_after_the_close_and_executes_once_at_the_slot(tmp_path) -> None:
    rig = Rig(tmp_path)
    loop = rig.loop()
    await loop.tick(rollover_utc(DAY) + timedelta(seconds=60), boot=True)    # before settle: yesterday's decision
    assert loop.decided == DAY - timedelta(days=1)
    await loop.tick(AFTER)
    (decided,) = [e for e in rig.events("TARGET_DECIDED") if e["day"] == DAY.isoformat()]
    assert decided["reason"] == "target" and decided["target"] == "1000" and decided["slot"] == SLOT.isoformat()
    assert decided["shadow"] > 0 and decided["close"] > 0 and decided["q"] == 1.0          # the shadow book's mark
    await loop.tick(SLOT - timedelta(seconds=1))
    assert rig.sent == []                                                      # never before the slot
    await loop.tick(SLOT + timedelta(seconds=30))
    await loop.tick(SLOT + timedelta(seconds=90))                              # a reconnect, a second wake
    (item,) = rig.sent
    (order,) = item.orders
    assert (order.action, order.direction, order.size_units, order.take_profit) == ("open", 1, LOT, None)
    assert order.stop_loss == pytest.approx(1.2 - 10 * decided["atr"])
    assert order.factors_snapshot["inputs_hash"] == decided["inputs_hash"]


async def test_a_restart_re_derives_the_same_target_and_drops_a_slot_already_passed(tmp_path) -> None:
    rig = Rig(tmp_path)
    first = rig.loop()
    await first.tick(AFTER, boot=True)
    second = rig.loop()                                                        # a restart on the same cache
    await second.tick(AFTER + timedelta(minutes=30), boot=True)
    a, b = [e for e in rig.events("TARGET_DECIDED") if e["day"] == DAY.isoformat()]
    assert (a["target"], a["inputs_hash"]) == (b["target"], b["inputs_hash"])
    assert len(rig.fetches) == 1                                               # the restart reads the cache
    late = rig.loop()
    await late.tick(SLOT + timedelta(minutes=30), boot=True)                    # down across the slot
    assert late.pending == {} and rig.events("TARGET_SLOT_PASSED")
    assert rig.sent == []                                                      # never caught up


async def test_a_position_changed_since_the_decision_is_not_re_entered_the_same_day(tmp_path) -> None:
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v1")
    rig.held["EUR_USD"] = Held("EUR_USD", -1, LOT)                            # short into an up-trend: a flip
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert loop.pending["EUR_USD"].decision.target == LOT
    del rig.held["EUR_USD"]                                                    # its disaster stop fired
    await loop.tick(SLOT + timedelta(seconds=5))
    assert rig.sent == [] and rig.events("TARGET_SLOT_SKIPPED")[-1]["reason"] == "position_changed"


async def test_a_flip_judges_its_open_net_of_its_own_close(tmp_path) -> None:
    """PR16I-04: at the slot, a flip's own closing leg is read as filled when the entry is judged."""
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v1")
    rig.held["EUR_USD"] = Held("EUR_USD", -1, LOT)                            # short into an up-trend
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    await loop.tick(SLOT + timedelta(seconds=5))
    (closing,) = rig.closing[-1]
    assert (closing.action, closing.direction, closing.size_units, closing.reason) == ("close", -1, LOT, "target_flip")
    assert [o.action for o in rig.sent[-1].orders] == ["close", "open"]


async def test_a_feed_refusal_at_the_slot_stops_the_open_and_still_sends_the_close(tmp_path) -> None:
    """PC-I-01: the loop passes the feed watch's verdict to the gate at every slot."""
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v1")
    rig.held["EUR_USD"] = Held("EUR_USD", -1, LOT)                            # short into an up-trend: a flip
    rig.feed_refusal = "stale_feed"
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    await loop.tick(SLOT + timedelta(seconds=5))
    assert [o.action for o in rig.sent[-1].orders] == ["close"]
    assert rig.events("TARGET_ENTRY_ZERO")[-1]["reason"] == "stale_feed"


async def test_a_family_frozen_after_the_decision_opens_nothing_at_the_slot(tmp_path) -> None:
    """PR16I-10: master §2 wants a registered AND validated rule set; the slot re-asks, so a family
    frozen or retired overnight sends its closes but no open."""
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v1")
    rig.held["EUR_USD"] = Held("EUR_USD", -1, LOT)                            # short into an up-trend: a flip
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    rig.registered = False                                                     # frozen before the slot
    await loop.tick(SLOT + timedelta(seconds=5))
    (executed,) = rig.events("TARGET_EXECUTED")
    assert executed["reason"] == "family_not_allowed" and [o.action for o in rig.sent[-1].orders] == ["close"]


async def test_the_slot_reports_alpha_decay_on_the_capped_book_and_applies_it_live(tmp_path) -> None:
    """PR16E-01: the loop passes `alpha_throttles` from the mode's cap (one lot = paper/practice)."""
    for cap, sent in ((LOT, True), (None, False)):
        rig = Rig(tmp_path / str(cap))
        rig.cap = cap
        rig.gate.args[0].apply_risk_state(alpha_decay=True)                     # the Governor behind the gate
        loop = rig.loop()
        await loop.tick(AFTER, boot=True)
        await loop.tick(SLOT + timedelta(seconds=5))
        assert bool(rig.sent) is sent, (cap, rig.events("TARGET_EXECUTED"))


async def test_a_closed_market_or_a_busy_instrument_skips_the_slot(tmp_path) -> None:
    rig = Rig(tmp_path, open_=False)
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    await loop.tick(SLOT + timedelta(seconds=5))
    assert rig.sent == [] and rig.events("TARGET_SLOT_SKIPPED")[-1]["reason"] == "market_closed"
    rig2 = Rig(tmp_path / "b")
    loop2 = rig2.loop()
    await loop2.tick(AFTER, boot=True)
    rig2.busy.add("EUR_USD")
    await loop2.tick(SLOT + timedelta(seconds=5))
    assert rig2.sent == [] and rig2.events("TARGET_SLOT_SKIPPED")[-1]["reason"] == "busy"


async def test_a_holiday_is_not_a_decision_day_and_a_failed_fetch_gives_no_target(tmp_path) -> None:
    rig = Rig(tmp_path)
    rig.now = rollover_utc(date(2025, 12, 25)) + timedelta(minutes=5)
    rig.data["EUR_USD"] = _bars(0.0002, 1, until=rig.now)
    await rig.loop().tick(rig.now, boot=True)
    assert rig.events("TARGETS_NO_DECISION_DAY")[-1]["day"] == "2025-12-25"
    bad = Rig(tmp_path / "b", fetch_error=ConnectionError("venue down"))
    loop = bad.loop()
    await loop.tick(AFTER, boot=True)
    assert bad.events("TRENDBARS_FAILED") and loop.pending == {}


async def test_an_unregistered_family_makes_no_target(tmp_path) -> None:
    rig = Rig(tmp_path, registered=False)
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert loop.pending == {} and rig.events("TARGETS_FAMILY_UNREGISTERED")


async def test_a_first_activation_over_held_positions_flattens_them_first(tmp_path) -> None:
    rig = Rig(tmp_path)
    rig.held["EUR_USD"] = Held("EUR_USD", 1, LOT, param_set_id="qiea:champion")   # left by the legacy path
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert rig.flattened == [("EUR_USD", "family_promotion")] and rig.store.get("active_family") is None


async def test_a_new_family_version_flattens_first_and_promotes_only_when_flat(tmp_path) -> None:
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v0")
    rig.held["EUR_USD"] = Held("EUR_USD", 1, LOT, param_set_id="trend_d1_v0")
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert rig.flattened == [("EUR_USD", "family_promotion")] and loop.pending == {}
    assert rig.store.get("active_family") == "trend_d1_v0"                     # never promoted while held
    del rig.held["EUR_USD"]
    nxt = rollover_utc(DAY + timedelta(days=1)) + timedelta(minutes=3)
    rig.data["EUR_USD"] = _bars(0.0002, 1, until=nxt)
    rig.now = nxt
    await loop.tick(nxt)
    assert rig.store.get("active_family") == "trend_d1_v1" and rig.events("FAMILY_PROMOTED")
    assert "EUR_USD" in loop.pending


async def test_no_bar_after_the_decision_moves_its_target_or_inputs_hash(tmp_path) -> None:
    """The structural future-scramble for the target path (GAP-P12D-65's law): bars after 17:00 New
    York, which the cache holds after a later boot, change neither the target nor its inputs hash."""
    rig = Rig(tmp_path)
    await rig.loop().tick(AFTER, boot=True)
    rng, at = random.Random(5), rollover_utc(DAY)
    future = [Bar(ts_open=b.ts_open, open=b.open * f, high=b.high * f * 1.01, low=b.low * f * 0.99, close=b.close * f,
                  spread=0.0, duration_s=3600)
              for b in _bars(0.0002, 1, until=AFTER + timedelta(days=3)) if b.ts_open >= at
              for f in (1 + rng.uniform(-0.05, 0.05),)]
    assert len(future) > 40
    rig.store.add("EUR_USD", future)
    await rig.loop().decide(DAY, AFTER + timedelta(days=3))
    a, b = [e for e in rig.events("TARGET_DECIDED") if e["day"] == DAY.isoformat()]
    assert (a["target"], a["inputs_hash"], a["forecast"]) == (b["target"], b["inputs_hash"], b["forecast"])


async def test_a_restart_after_a_stop_out_does_not_re_enter_before_the_next_decision(tmp_path) -> None:
    """R16I-03: the day's held position is persisted, so a restart re-derives nothing for a book a
    disaster stop changed."""
    rig = Rig(tmp_path)
    rig.store.put("active_family", "trend_d1_v1")
    rig.held["EUR_USD"] = Held("EUR_USD", 1, LOT)                             # target == held: nothing pending
    await rig.loop().tick(AFTER, boot=True)
    assert [e["target"] for e in rig.events("TARGET_DECIDED")][-1] == "1000"
    del rig.held["EUR_USD"]                                                   # its stop fired overnight
    restarted = rig.loop()
    await restarted.tick(SLOT - timedelta(hours=4), boot=True)                 # 04:00 New York
    await restarted.tick(SLOT + timedelta(seconds=5))
    assert restarted.pending == {} and rig.sent == []
    assert rig.events("TARGET_DECIDED")[-1]["reason"] == "no_target:position_changed_since_decision"


async def test_a_failed_fetch_gives_no_target_even_with_a_populated_cache(tmp_path) -> None:
    """R16I-04: the instrument whose fetch failed does not decide on yesterday's close."""
    rig = Rig(tmp_path)
    rig.data["GBP_USD"] = _bars(0.0002, 2)                                    # a second pair that fetches fine
    await rig.loop().tick(AFTER - timedelta(days=1), boot=True)               # day D-1 cached for both
    rig.fail = {"EUR_USD"}
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    today = {e["instrument"]: e["reason"] for e in rig.events("TARGET_DECIDED") if e["day"] == DAY.isoformat()}
    assert today["EUR_USD"] == "no_target:fetch_failed" and "EUR_USD" not in loop.pending
    assert today["GBP_USD"] == "target"                                       # the day itself was decided


async def test_the_decision_waits_for_a_proven_clock_and_an_entry_needs_its_own(tmp_path) -> None:
    """R16I-02 (ACIS-13 A8): no decision before any instrument's clock is proven (it retries), and no
    entry for an instrument whose clock is unproven at its slot."""
    rig = Rig(tmp_path)
    rig.clock_ok = False
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert loop.decided is None and rig.events("TARGETS_CLOCK_UNVERIFIED") and rig.fetches == []
    rig.clock_ok = True
    await loop.tick(AFTER + timedelta(minutes=5))
    assert loop.decided == DAY and "EUR_USD" in loop.pending
    rig.clock_ok = False
    await loop.tick(SLOT + timedelta(seconds=5))
    assert rig.sent == [] and rig.events("TARGET_EXECUTED")[-1]["reason"] == "clock_unverified"


async def test_a_history_with_a_hole_gives_no_target(tmp_path) -> None:
    rig = Rig(tmp_path)
    hole = (datetime(2026, 3, 2, tzinfo=UTC), datetime(2026, 3, 14, tzinfo=UTC))
    rig.data["EUR_USD"] = [b for b in rig.data["EUR_USD"] if not hole[0] <= b.ts_open < hole[1]]
    await rig.loop().tick(AFTER, boot=True)
    assert rig.events("HISTORY_HOLE")[-1]["instruments"] == ["EUR_USD"]
    assert rig.events("TARGET_DECIDED")[-1]["reason"] == "no_target:history_hole"


async def test_the_mode_cap_is_reapplied_at_the_slot(tmp_path) -> None:
    """R16I-10: a decision taken uncapped never sends more than the cap in force at its slot."""
    rig = Rig(tmp_path)
    rig.cap = None
    loop = rig.loop()
    await loop.tick(AFTER, boot=True)
    assert loop.pending["EUR_USD"].decision.target > LOT                      # uncapped at the decision
    rig.cap = LOT                                                             # practice by the slot
    await loop.tick(SLOT + timedelta(seconds=5))
    (item,) = rig.sent
    assert [o.size_units for o in item.orders] == [LOT]
