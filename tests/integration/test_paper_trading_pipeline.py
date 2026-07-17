"""Phase-7: full paper-trading integration (SPEC §15 phase 7, §13 integration).

The PRODUCTION layers 1–5 composed end-to-end on the mock feed via
tests/integration/paper_loop.py — every §2 conflict-table row proven THROUGH
the composed pipeline (not at a layer seam), per-gate skip attribution (§10
C15) observable live, and the GAP-0052 boot contract enforced.

Fixture series are empirically tuned against the real classifier + indicator
maths (phase-3/5 precedent): 280 flat-noise ticks at 60s cadence warm the
factory session medians (30) and the NVMA window (201), then classify
MEAN_REVERTING (tradeable once params are promoted); the TSMOM daily seed
(300 rising closes) makes the always-on module fire organically through the
whole stack.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from random import Random
from types import MappingProxyType

from core.data.feeds import MockPaperFeed
from core.data.normaliser import RawTick
from core.governor.portfolio_types import PortfolioState, Position
from core.regime.regime_types import RegimeType
from core.signals.signal_types import StrategyType
from tests.integration.paper_loop import PaperLoop, build_paper_loop
from tests.optimizer_fixtures import make_paramset

BOUNDARY = datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)   # Tuesday 00:00 (C1)
T0 = BOUNDARY + timedelta(minutes=10)                          # tokyo session
WARMUP = 280   # 201-tick NVMA window + 30 session-median samples, with margin


def flat_portfolio(**overrides) -> PortfolioState:
    base = dict(nav=Decimal("10000"), open_positions=(),
                per_currency_delta=MappingProxyType({}),
                per_cluster_exposure=MappingProxyType({}),
                daily_drawdown_pct=0.0, as_of=T0, stale=False)
    base.update(overrides)
    return PortfolioState(**base)


def mk_tick(i: int, mid: float, spread: float = 0.00012) -> RawTick:
    ts = T0 + timedelta(seconds=60 * i)
    bid = round(mid - spread / 2, 6)
    return RawTick(event_time=ts, recv_time=ts + timedelta(milliseconds=5),
                   instrument="EUR_USD", bid=bid, ask=round(bid + spread, 6),
                   volume=5.0, book=None, provider="mock", raw_payload={"i": i})


def flat_ticks(n: int = WARMUP) -> list[RawTick]:
    """Flat noise, spread jittered so the session-spread sigma is real (a
    constant spread makes sigma ~1e-16 and float dust trips ILLIQUID)."""
    rng = Random(11)
    return [mk_tick(i, 1.10 + (0.00005 if i % 2 else -0.00005)
                    + rng.uniform(-0.00002, 0.00002),
                    0.00012 + rng.uniform(-0.00002, 0.00002)) for i in range(n)]


def make_loop(tmp_path: Path, acis_config, factory, portfolio_fn,
              regimes=(RegimeType.MEAN_REVERTING, RegimeType.RANGING_TIGHT,
                       RegimeType.RANGING_WIDE)) -> PaperLoop:
    """Real layers from real config; ranging-family params promoted at a real
    session boundary with zero open positions; TSMOM daily history seeded."""
    loop = build_paper_loop(tmp_path, acis_config, factory, portfolio_fn)
    for regime in regimes:
        loop.params.stage(
            make_paramset(regime=regime, param_set_id=f"ps-{regime.value}",
                          mean_rev_zscore_entry=1.5),
            now=BOUNDARY - timedelta(hours=1))
    promoted = loop.params.promote(BOUNDARY)
    assert sorted(promoted) == sorted(r.value for r in regimes)
    for i in range(300):
        loop.agon.observe_daily_close("EUR_USD", 1.0 + 0.001 * i)
    return loop


def log_events(tmp_path: Path, event_type: str) -> list[dict]:
    lines = (tmp_path / "system_log.jsonl").read_text(encoding="utf-8")
    records = [json.loads(l) for l in lines.strip().splitlines()]
    return [r for r in records if r["event_type"] == event_type]


# --------------------------- end-to-end (the plumbing) --------------------------- #

async def test_e2e_mock_feed_to_sized_paper_orders(tmp_path, acis_config, factory) -> None:
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    pipeline = await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks()),
                              drain=True)

    assert pipeline.emitted == WARMUP and pipeline.rejected == 0
    assert loop.store.row_count() == WARMUP          # persisted through the writer
    # orders came out the bottom with the full audit chain intact
    assert len(loop.book.orders) >= 1
    first = loop.book.orders[0]
    assert first.size_units > 0 and first.reason == "formula"
    assert first.param_set_id == "ps-MEAN_REVERTING"  # signal -> params traceable
    assert first.direction == 1                       # TSMOM long from the daily seed
    assert first.take_profit is None                  # faithful TSMOM: no target
    assert first.stop_loss < first.entry_price        # far disaster stop only
    # §10 take-rate: considered >= emitted == placed (no governor zeros here)
    tr = loop.take_rate()
    assert tr["signals_considered"] >= tr["signals_emitted"] == tr["orders_placed"]
    assert tr["orders_placed"] == len(loop.book.orders)
    # GAP-0075 pinned VISIBLY: the harness opens one order per tradeable tick —
    # `orders_placed` counts SIZING DECISIONS, not positions. Position-aware
    # dedup/holding arrives with phase-9 accounting (PortfolioState from
    # FillReports); until then the spam is asserted, not masked.
    assert tr["orders_placed"] == 67
    # observable outcomes in the JSONL audit trail, not exit codes
    assert len(log_events(tmp_path, "SIZED")) == tr["orders_placed"]
    assert len(log_events(tmp_path, "SIGNAL_EMITTED")) == tr["signals_emitted"]


async def test_per_gate_skip_attribution_is_live(tmp_path, acis_config, factory) -> None:
    """§10 C15: every skip attributed to the specific gate that killed it —
    counters must match the logged events, per layer."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks()))

    skips = loop.skip_attribution()
    # NVMA: warm-up vetoes counted at the gate, matching VETO_APPLIED records
    assert skips["nvma"]["REGIME_WARMING"] == 200    # 201-tick window - 1
    vetoes = log_events(tmp_path, "VETO_APPLIED")
    per_reason: dict[str, int] = {}
    for v in vetoes:
        per_reason[v["data"]["reason"]] = per_reason.get(v["data"]["reason"], 0) + 1
    assert per_reason == skips["nvma"]
    # AGON: every untradeable tick attributed, matching the discard log
    assert skips["agon"]["vetoed_regime"] == len(
        log_events(tmp_path, "DISCARD_VETOED_REGIME"))
    # Governor: nothing zeroed on the clean run — the counter proves absence too
    assert skips["governor"] == {}


# --------------------------- the six §2 conflict-table rows --------------------------- #

async def test_row1_nvma_veto_kills_signal_zero_reach_governor(
        tmp_path, acis_config, factory) -> None:
    """Row 1: NVMA no-trade + AGON high-conviction signal => discard, no exception."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    # a spread 3x the session median (but under max-plausible) on the last tick,
    # exactly when TSMOM would otherwise fire
    ticks = flat_ticks() + [mk_tick(WARMUP, 1.10, spread=0.0004)]
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=ticks))

    ctx = loop.last_context
    assert ctx.tradeable is False
    assert "SPREAD_VETO" in ctx.inputs_snapshot["veto_reasons"]
    assert loop.nvma.veto_counters["SPREAD_VETO"] >= 1
    veto_ts = ticks[-1].event_time
    # zero signals reached the Governor on the veto tick: no SIZED record there
    assert all(o.sized_at != veto_ts for o in loop.book.orders)
    assert not any(r["data"].get("instrument") == "EUR_USD"
                   and r["data"].get("order_id")
                   for r in log_events(tmp_path, "SIZED")
                   if r["timestamp"].startswith(veto_ts.strftime("%Y-%m-%dT%H:%M")))


async def test_row2_new_params_stage_and_wait_for_flat_boundary(
        tmp_path, acis_config, factory) -> None:
    """Row 2: QIEA new params ready + open positions => stage; deploy at next
    session boundary only. The ParamLibrary's position gate IS the paper book."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks()))
    assert loop.book.open_position_count() >= 1      # paper positions are open

    challenger = make_paramset(regime=RegimeType.MEAN_REVERTING,
                               param_set_id="ps-challenger",
                               mean_rev_zscore_entry=1.5)
    loop.params.stage(challenger, now=T0 + timedelta(hours=5))
    # next boundary (07:00) arrives with positions still open: NO promotion
    assert loop.params.on_boundary(BOUNDARY + timedelta(hours=7)) == []
    active = loop.params.get_active(RegimeType.MEAN_REVERTING)
    assert active.params.param_set_id == "ps-MEAN_REVERTING"   # unchanged
    pending = loop.params.get_pending(RegimeType.MEAN_REVERTING)
    assert pending and pending[0].boundaries_skipped == 1
    # flat at the following boundary: the challenger deploys
    loop.book.flatten()
    promoted = loop.params.on_boundary(BOUNDARY + timedelta(hours=12))
    assert promoted == [RegimeType.MEAN_REVERTING.value]
    assert (loop.params.get_active(RegimeType.MEAN_REVERTING)
            .params.param_set_id == "ps-challenger")


async def test_row3_cluster_cap_sizes_to_zero_never_splits(
        tmp_path, acis_config, factory) -> None:
    """Row 3: signal would breach the correlation-cluster cap => size zero, no
    split. At the cap the DESIGNED zero mechanism for a solo order is the
    linear correlation factor reaching exactly 0.0 (factors.py: "0.0 at the
    cap — the hard cap zeroes there anyway"); the hard cluster_cap guard is
    the aggregate backstop, proven at group level (GAP-0049 unit tests)."""
    loaded = flat_portfolio(per_cluster_exposure=MappingProxyType(
        {"usd_short": Decimal("2000")}))            # exactly at the 20% x 10k cap
    loop = make_loop(tmp_path, acis_config, factory, lambda: loaded)
    loop.boot(loaded)
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks()))

    tr = loop.take_rate()
    assert tr["signals_emitted"] >= 1                # AGON did offer signals
    assert tr["orders_placed"] == 0                  # none was placed
    assert loop.skip_attribution()["governor"] == {"formula_zero": tr["orders_zeroed"]}
    assert loop.book.orders == []
    for record in log_events(tmp_path, "SIZED"):     # zero, never a partial split
        assert record["data"]["size_units"] == "0"


async def test_row3b_currency_delta_hard_override_zeroes_through_pipeline(
        tmp_path, acis_config, factory) -> None:
    """Row 3's hard-override half through the composed loop: a §6 hard limit
    (single-currency delta cap) has NO softening factor in front of it, so it
    fires as a true hard zero — never a clamp, never a split."""
    loaded = flat_portfolio(per_currency_delta=MappingProxyType(
        {"USD": Decimal("-2900")}))                 # near the 30% x 10k delta cap
    loop = make_loop(tmp_path, acis_config, factory, lambda: loaded)
    loop.boot(loaded)
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks()))

    tr = loop.take_rate()
    assert tr["signals_emitted"] >= 1 and tr["orders_placed"] == 0
    gov = loop.skip_attribution()["governor"]
    assert gov["currency_delta_cap"] == tr["orders_zeroed"]   # the hard gate, attributed
    assert loop.book.orders == []
    for record in log_events(tmp_path, "SIZED"):
        assert record["data"]["size_units"] == "0"


async def test_row4_daily_drawdown_halts_new_positions_for_session(
        tmp_path, acis_config, factory) -> None:
    """Row 4: daily drawdown limit hit while sizing => halt new positions for
    the session — the halt outlives the drawdown reading itself."""
    holder = {"p": flat_portfolio(daily_drawdown_pct=2.1)}    # >= the 2.0 limit
    loop = make_loop(tmp_path, acis_config, factory, lambda: holder["p"])
    loop.boot(holder["p"])
    ticks = flat_ticks(WARMUP + 20)

    seen = {"n": 0}
    orig = loop.on_state

    def recovering(state):
        orig(state)
        if loop.last_context.tradeable and seen["n"] == 0:
            seen["n"] = 1
            holder["p"] = flat_portfolio(daily_drawdown_pct=0.0)   # "recovers"
    loop.on_state = recovering

    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=ticks))
    assert seen["n"] == 1                            # the breach tick happened
    assert loop.book.orders == []                    # zero new orders post-breach
    gov = loop.skip_attribution()["governor"]
    assert gov["drawdown_halt"] >= 2                 # breach tick AND after recovery
    halts = log_events(tmp_path, "HALT_APPLIED")
    assert any(h["data"]["reason"] == "daily_drawdown_limit" for h in halts)


async def test_row5_regime_shift_without_params_is_untradeable_and_never_swaps(
        tmp_path, acis_config, factory) -> None:
    """Row 5: regime shift + no evolved params for the new regime =>
    tradeable=False until QIEA completes evolution; §13: a shift mid-session
    with open positions must NOT swap params."""
    # only MEAN_REVERTING has ACTIVE params: every other regime the shift
    # passes through (RANGING flicker, POST_BREAKOUT, STRONG_TREND_UP) is
    # provably untradeable for lack of evolved params
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio,
                     regimes=(RegimeType.MEAN_REVERTING,))
    # trend params exist but are only STAGED - staging is not evolution-complete
    loop.params.stage(make_paramset(regime=RegimeType.STRONG_TREND_UP,
                                    param_set_id="ps-trend"),
                      now=T0 + timedelta(minutes=5))
    loop.boot(flat_portfolio())
    ticks = flat_ticks()
    m = 1.10
    for j in range(40):                              # the shift: a strong trend
        m += 0.0004
        ticks.append(mk_tick(WARMUP + j, m))
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=ticks))

    assert len(loop.book.orders) >= 1                # traded while mean-reverting
    shift_ts = ticks[WARMUP].event_time
    assert all(o.sized_at < shift_ts for o in loop.book.orders)  # none in the trend
    assert loop.last_context.regime is RegimeType.STRONG_TREND_UP
    assert loop.last_context.tradeable is False
    assert loop.nvma.veto_counters["NO_PARAMS_FOR_REGIME"] >= 1
    assert log_events(tmp_path, "REGIME_SHIFT")      # the shift is auditable
    # params never swapped mid-session: trend set still pending, not active
    assert loop.params.get_active(RegimeType.STRONG_TREND_UP) is None
    assert loop.params.get_pending(RegimeType.STRONG_TREND_UP)
    # and with positions open, the next boundary still refuses to promote
    assert loop.params.on_boundary(BOUNDARY + timedelta(hours=7)) == []


async def test_row6_opposite_directions_discard_both_through_the_pipeline(
        tmp_path, acis_config, factory) -> None:
    """Row 6: two strategies, opposite directions, same instrument => discard
    both. Organic: TSMOM votes LONG from the daily seed while a tuned 2-bar
    rise + stalling high fires the mean-reversion module SHORT."""
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    ticks = flat_ticks()
    rng = Random(23)
    extra = [1.10 + 0.0002, 1.10 + 0.0004]
    extra += [extra[-1] - 0.00003 * (i + 1) for i in range(4)]
    for j, em in enumerate(extra):
        ticks.append(mk_tick(WARMUP + j, em, 0.00012 + rng.uniform(-2e-05, 2e-05)))
    await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=ticks))

    assert loop.agon.skips.get("opposite", 0) >= 2   # both sides died, counted
    discards = log_events(tmp_path, "DISCARD_OPPOSITE")
    assert discards and all(d["data"]["instrument"] == "EUR_USD" for d in discards)
    # ambiguity = no trade: nothing was emitted (hence sized) on conflict ticks
    assert len(loop.book.orders) == len(log_events(tmp_path, "SIGNAL_EMITTED"))
    assert loop.take_rate()["signals_considered"] > loop.take_rate()["signals_emitted"]


# --------------------------- restart boot (GAP-0052) --------------------------- #

def _position(instrument: str, direction: int, group_id: str | None) -> Position:
    return Position(instrument=instrument, direction=direction,
                    size_units=Decimal("100"), entry_price=1.10, stop_loss=1.05,
                    take_profit=None, opened_at=T0,
                    strategy_type=StrategyType.PAIR_DIVERGENCE,
                    param_set_id="ps-restart", group_id=group_id)


async def test_gap0052_boot_rebuilds_groups_so_pair_legs_survive_restart(
        tmp_path, acis_config, factory) -> None:
    restart = flat_portfolio(open_positions=(
        _position("EUR_USD", 1, "g-restart"),
        _position("USD_JPY", -1, "g-restart"),
        _position("EUR_USD", 1, "g-orphan"),         # one leg only: never rebuilt
    ))
    loop = make_loop(tmp_path, acis_config, factory, lambda: restart)
    assert loop.boot(restart) == 1
    assert loop.governor.open_groups() == ("g-restart",)
    orphans = log_events(tmp_path, "GROUP_REBUILD_ORPHAN")
    assert len(orphans) == 1 and orphans[0]["data"]["group_id"] == "g-orphan"
    # the pre-restart group is closeable: a coupling break closes BOTH legs
    closes = loop.governor.check_group_exits({"g-restart": "coupling_break"},
                                             T0 + timedelta(hours=1))
    assert len(closes) == 2 and all(o.action == "close" for o in closes)
    assert loop.governor.open_groups() == ()


async def test_boot_is_mandatory_before_the_first_tick(
        tmp_path, acis_config, factory) -> None:
    loop = make_loop(tmp_path, acis_config, factory, flat_portfolio)
    try:
        await loop.run(MockPaperFeed({"EUR_USD": 1.10}, scripted=flat_ticks(5)))
    except RuntimeError as exc:              # GAP-0079: a real raise, -O-proof
        assert "GAP-0052" in str(exc)
    else:
        raise AssertionError("run() must refuse to start unbooted (GAP-0052)")
