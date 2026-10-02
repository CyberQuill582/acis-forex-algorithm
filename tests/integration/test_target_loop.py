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
from tests.signals_fixtures import mk_regime
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
        self.held: dict[str, Held] = {}
        self.busy: set[str] = set()
        self.sent, self.flattened, self.fetches = [], [], []
        self.fetch_error, self.registered, self.open_ = fetch_error, registered, open_
        gov, _ = mk_governor()
        days = [date(2024, 9, 1) + timedelta(days=k) for k in range(800)]
        self.rates = RateTable({"USD": [(d, 4.0) for d in days], "EUR": [(d, 3.0) for d in days]})
        self.gate = partial(target_orders, gov, limits=gov.guards._limits, rules=mk_rulebook(),
                            clusters={"usd_short": ["EUR_USD"]}, stop_mult=10.0, logger=self.log)

    async def fetch(self, instrument, start, end):
        self.fetches.append((instrument, start, end))
        if self.fetch_error:
            raise self.fetch_error
        return [b for b in self.data[instrument] if start <= b.ts_open and b.ts_open + timedelta(hours=1) <= end]

    def loop(self, family="trend_d1_v1") -> TargetLoop:
        view = EngineView(held_of=self.held.get, busy=lambda: frozenset(self.busy), marks=lambda: {"EUR_USD": 1.2},
                          portfolio=lambda: mk_portfolio(nav=Decimal("100000")),
                          regime_of=lambda i: mk_regime(instrument=i), submit=self.sent.append,
                          flatten=lambda scope, why: self.flattened.append((scope, why)))
        return TargetLoop(
            members={"EUR_USD": Member("EUR_USD", "fx", "USD", SLOTS["fx"], lambda now: self.open_)},
            store=self.store, fetch=self.fetch, rates=lambda: self.rates,
            sizing=BookSizing(10_000, 0.10, 1.0, 0.10, {"EUR_USD": 1.0}), lots_of=lambda i: Lots(LOT, LOT, LOT),
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
