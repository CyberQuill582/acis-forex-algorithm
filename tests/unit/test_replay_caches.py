"""GAP-P12D-15 replay speed: ATR memo, WAL-mode stores, and the parsed-params memo.

Each change must be invisible in behaviour — same values, and promotions and freezes made
through ANY connection visible on the very next call — and only skip repeated work. The
loop-level test runs the real composed loop twice over the same ticks, once with the
memos defeated, freezes a strategy through a second connection mid-run, and requires
identical orders and counters.
"""

from __future__ import annotations

import dataclasses
import math
import random
from collections import deque
from datetime import datetime, timedelta, timezone

import pytest

import core.signals.indicators as indicators
from core.data.bars import Bar
from core.regime.regime_types import RegimeType
from core.signals.canonical import STRATEGY_IDS
from core.signals.indicators import AtrMemo, wilder_atr
from core.signals.provenance import ProvenanceStore
from core.signals.signal_types import StrategyType
from tests.integration.test_paper_trading_pipeline import flat_portfolio, flat_ticks, make_loop
from tests.optimizer_fixtures import CapturingLogger, make_paramset
from tests.signals_fixtures import T0
from tests.unit.test_param_library import AT_BOUNDARY, FakeGate, make_lib
from tests.unit.test_provenance import mk_record, mk_store

START = datetime(2025, 1, 7, tzinfo=timezone.utc)


def _walk(n: int, seed: int = 3) -> list[Bar]:
    rng, close, out = random.Random(seed), 1.10, []
    for i in range(n):
        new = close * (1 + rng.gauss(0, 0.0004))
        hi, lo = max(close, new) * (1 + abs(rng.gauss(0, 0.0002))), min(close, new) * (1 - abs(rng.gauss(0, 0.0002)))
        out.append(Bar(ts_open=START + timedelta(minutes=i), open=close, high=hi, low=lo,
                       close=new, spread=0.0001, duration_s=60))
        close = new
    return out


def _same(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b


# ------------------------------- ATR memo ------------------------------- #

def test_atr_memo_equals_wilder_atr_through_warmup_growth_and_eviction(monkeypatch) -> None:
    calls = []
    real = indicators.atr_series
    monkeypatch.setattr(indicators, "atr_series", lambda bars, p: calls.append(1) or real(bars, p))
    memo, window = AtrMemo(14), deque(maxlen=40)
    for bar in _walk(120):
        window.append(bar)
        expected = real(list(window), 14)[-1] if len(window) > 14 else float("nan")
        expected = expected if expected > 0 else float("nan")
        before = len(calls)
        assert _same(memo("EUR_USD", list(window)), expected)
        assert _same(memo("EUR_USD", list(window)), expected)      # between bars: a hit
        assert len(calls) - before <= 1                             # computed at most once per bar


def test_atr_memo_recomputes_when_any_bar_differs_even_with_same_ends() -> None:
    bars = _walk(30)
    memo = AtrMemo(14)
    first = memo("k", bars)
    swapped = bars[:10] + [_walk(30, seed=9)[10]] + bars[11:]      # same first, last and length
    assert _same(memo("k", swapped), wilder_atr(swapped, 14))
    assert not _same(wilder_atr(swapped, 14), first)
    other = _walk(30, seed=5)                                       # a different window, same key
    assert _same(memo("k", other), wilder_atr(other, 14))
    assert math.isnan(memo("k", []))


# ------------------------------ WAL-mode stores ------------------------------ #

def test_both_stores_open_in_wal_mode(tmp_path) -> None:
    lib, _ = make_lib(tmp_path, FakeGate(0))
    store, _ = mk_store(tmp_path)
    for db in (lib._db, store._db):
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_get_active_reuses_the_parse_only_while_the_row_is_unchanged(tmp_path) -> None:
    lib, _ = make_lib(tmp_path, FakeGate(0))
    regime = RegimeType.STRONG_TREND_UP
    assert lib.get_active(regime) is None
    lib.stage(make_paramset(regime=regime, param_set_id="ps-1"), now=AT_BOUNDARY - timedelta(hours=1))
    assert lib.get_active(regime) is None                           # staging never activates
    lib.promote(AT_BOUNDARY)
    first = lib.get_active(regime)
    assert first is not None and first.params.param_set_id == "ps-1"
    statements = []
    lib._db.set_trace_callback(statements.append)
    assert lib.get_active(regime) is first                          # same row: parse reused
    assert len(statements) == 1 and statements[0].startswith("SELECT")   # but the row is re-read
    lib._db.set_trace_callback(None)
    lib.stage(make_paramset(regime=regime, param_set_id="ps-2"), now=AT_BOUNDARY)
    lib.promote(AT_BOUNDARY + timedelta(days=1))
    assert lib.get_active(regime).params.param_set_id == "ps-2"      # visible on the very next call


def test_a_promotion_through_another_connection_is_seen_on_the_next_call(tmp_path) -> None:
    lib, _ = make_lib(tmp_path, FakeGate(0))
    other, _ = make_lib(tmp_path, FakeGate(0))                       # same file, both open
    regime = RegimeType.RANGING_WIDE
    other.stage(make_paramset(regime=regime, param_set_id="ps-a"), now=AT_BOUNDARY)
    other.promote(AT_BOUNDARY)
    assert lib.get_active(regime).params.param_set_id == "ps-a"
    other.stage(make_paramset(regime=regime, param_set_id="ps-b"), now=AT_BOUNDARY)
    other.promote(AT_BOUNDARY + timedelta(days=1))
    assert lib.get_active(regime).params.param_set_id == "ps-b"      # memo keyed on the row


def test_a_freeze_through_another_connection_is_seen_on_the_next_call(tmp_path) -> None:
    store, log = mk_store(tmp_path)
    store.register(mk_record())
    store.promote_one_rung("strat_v1", "evidence", T0)
    assert store.entry_allowed("strat_v1", T0) is True
    ProvenanceStore(tmp_path / "prov.db", 90, log).demote("strat_v1", "failed re-validation", T0)
    assert store.entry_allowed("strat_v1", T0) is False               # ACIS-11 §7: instantly


def test_a_rolled_back_write_is_not_remembered(tmp_path) -> None:
    lib, _ = make_lib(tmp_path, FakeGate(0))
    regime = RegimeType.RANGING_TIGHT
    lib.stage(make_paramset(regime=regime, param_set_id="ps-kept"), now=AT_BOUNDARY)
    lib.promote(AT_BOUNDARY)
    assert lib.get_active(regime).params.param_set_id == "ps-kept"
    lib._db.execute("UPDATE param_active SET source_pending_id = 'uncommitted' WHERE regime = ?",
                    (regime.value,))
    assert lib.get_active(regime).source_pending_id == "uncommitted"  # the transaction's view
    lib._db.rollback()
    assert lib.get_active(regime).source_pending_id != "uncommitted"


# ---------------------- loop-level equivalence (defeated memos) ---------------------- #

class _NoMemo:
    def __init__(self, period: int) -> None:
        self.period = period

    def __call__(self, key, bars):
        return wilder_atr(bars, self.period)


class _Forget(dict):
    def __setitem__(self, key, value) -> None:
        pass


def _without_ids(orders) -> list[dict]:
    """order_id / signal_id are fresh uuid4s per run; every other field must match."""
    return [{f.name: getattr(o, f.name) for f in dataclasses.fields(o)
             if f.name not in ("order_id", "signal_id")} for o in orders]


def test_composed_loop_is_identical_with_and_without_the_memos(tmp_path, acis_config, factory) -> None:
    (tmp_path / "memo").mkdir()
    (tmp_path / "plain").mkdir()
    memo = make_loop(tmp_path / "memo", acis_config, factory, flat_portfolio)
    plain = make_loop(tmp_path / "plain", acis_config, factory, flat_portfolio)
    plain.agon._atr = _NoMemo(plain.agon._atr.period)
    plain.governor._atr = _NoMemo(plain.governor._atr.period)
    plain.params._parsed = _Forget()
    for loop in (memo, plain):
        loop.boot(flat_portfolio())
    ticks = flat_ticks()
    freeze_at = len(ticks) * 3 // 4
    for i, raw in enumerate(ticks):
        if i == freeze_at:          # TSMOM fails re-validation, written through a SECOND connection
            for sub in ("memo", "plain"):
                ProvenanceStore(tmp_path / sub / "provenance.db", 90, CapturingLogger()).apply_revalidation(
                    STRATEGY_IDS[StrategyType.TSMOM], "FAIL", T0)
        state = factory.build(raw).state
        if state is not None:
            memo.on_state(state)
            plain.on_state(state)
    assert len(memo.book.orders) > 0
    assert memo.agon.skips.get("entry_frozen", 0) > 0                # the freeze reached the loop
    assert _without_ids(memo.book.orders) == _without_ids(plain.book.orders)
    assert memo.take_rate() == plain.take_rate()
    assert memo.skip_attribution() == plain.skip_attribution()
