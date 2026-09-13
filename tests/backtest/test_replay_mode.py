"""Replay mode for the composed loop (GAP-P12D-12): NVMA at the §10 Loop-2 cadence, and a
log that counts everything exactly while writing only a sample of per-tick chatter."""

from __future__ import annotations

import json
from dataclasses import replace

from core.data.jsonl_logging import JsonlEventLogger
from tests.backtest.replay_logging import ReplayEventLogger
from tests.integration.paper_loop import build_paper_loop
from tests.integration.test_paper_trading_pipeline import flat_portfolio, flat_ticks


def _states(factory, n=280):
    return [s for s in (factory.build(r).state for r in flat_ticks(n)) if s is not None]


def _count_classify(loop) -> list:
    calls = []
    real = loop.nvma.classify

    def counting(state):
        calls.append(state.instrument)
        return real(state)

    loop.nvma.classify = counting
    return calls


def test_regime_is_classified_once_per_cycle_and_reused_between(tmp_path, acis_config, factory) -> None:
    loop = build_paper_loop(tmp_path, acis_config, factory, flat_portfolio, regime_cycle_s=120)
    loop.boot(flat_portfolio())
    calls = _count_classify(loop)
    states = _states(factory)                                    # EUR_USD, one tick every 60 s
    for st in states[:3]:
        loop.on_state(st)
    assert len(calls) == 2                                       # t=0 s and t=120 s, not t=60 s
    first = loop.last_context
    loop.on_state(states[3])                                     # t=180 s: reuses the t=120 s context
    assert loop.last_context is first and len(calls) == 2
    other = replace(states[4], instrument="USD_JPY")             # a new instrument classifies at once
    loop.on_state(other)
    assert calls[-1] == "USD_JPY"
    for st in states[5:]:
        loop.on_state(st)
    assert calls.count("EUR_USD") == (len(states) + 1) // 2 - 0  # every other 60-s tick


def test_default_still_classifies_every_tick(tmp_path, acis_config, factory) -> None:
    loop = build_paper_loop(tmp_path, acis_config, factory, flat_portfolio)
    loop.boot(flat_portfolio())
    calls = _count_classify(loop)
    states = _states(factory, 40)
    for st in states:
        loop.on_state(st)
    assert len(calls) == len(states)


class _Inner:
    def __init__(self) -> None:
        self.events, self.closed = [], False

    def event(self, event_type, **data):
        self.events.append((event_type, data))

    def close(self):
        self.closed = True


def test_replay_logger_counts_everything_and_samples_only_chatter() -> None:
    inner = _Inner()
    log = ReplayEventLogger(inner, keep_per_type=100)
    for _ in range(500):
        log.event("VETO_APPLIED", reason="DEAD_MARKET")
    for _ in range(300):
        log.event("DISCARD_VETOED_REGIME", instrument="EUR_USD")
    for _ in range(3):
        log.event("HALT_APPLIED", scope="all")                     # rare: always written in full
    written = [e for e, _ in inner.events]
    assert written.count("VETO_APPLIED") == 100 and written.count("DISCARD_VETOED_REGIME") == 100
    assert written.count("HALT_APPLIED") == 3
    assert log.counts == {"VETO_APPLIED": 500, "DISCARD_VETOED_REGIME": 300, "HALT_APPLIED": 3}
    log.close()
    summary = inner.events[-1]
    assert summary[0] == "REPLAY_LOG_SUMMARY" and summary[1]["counts"]["VETO_APPLIED"] == 500
    assert inner.closed


def test_replay_logger_plugs_into_the_real_loop(tmp_path, acis_config, factory) -> None:
    log_path = tmp_path / "system_log.jsonl"
    replay_log = ReplayEventLogger(JsonlEventLogger(log_path, layer="replay", session_id="t"), keep_per_type=5)
    loop = build_paper_loop(tmp_path, acis_config, factory, flat_portfolio, logger=replay_log, regime_cycle_s=120)
    loop.boot(flat_portfolio())
    for st in _states(factory):
        loop.on_state(st)
    replay_log.close()
    assert replay_log.counts["VETO_APPLIED"] > 5                  # counted beyond the sample
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert sum(r["event_type"] == "VETO_APPLIED" for r in records) == 5
    assert records[-1]["event_type"] == "REPLAY_LOG_SUMMARY"
    assert records[-1]["data"]["counts"]["VETO_APPLIED"] == replay_log.counts["VETO_APPLIED"]
