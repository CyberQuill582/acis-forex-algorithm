"""The `runtime:` block of system_config.yaml (master §10 `[DIR:core/runtime]`, v2.25).

Declared, never defaulted (SPEC §9): each value changes what the engine does with a position.
  * `max_hold_s` — the position policy's max hold (GAP-0075). It is the backtest book's own
    max hold, so the engine the demo runs exits as the engine the harness graded; a test pins
    the two equal (`test_the_runtime_max_hold_is_the_harness_one`).
  * `paper_nav_usd` — the paper venue's starting equity. Paper mode never reaches a real venue,
    so its equity is the paper venue's own ledger, starting here.
  * `fast_loop_stall_s` — no fast-loop progress for this long while an enabled instrument's market
    is open is a stalled Loop 3 (master §10: flatten-and-halt). A heartbeat on Risk's timer alone
    cannot see it (GAP-P12D-132 TAI-13, TAE-04).
"""

from __future__ import annotations

from pydantic import Field

from config.calendars import _Strict


class RuntimeConfig(_Strict):
    max_hold_s: int = Field(gt=0)
    paper_nav_usd: float = Field(gt=0)
    fast_loop_stall_s: float = Field(gt=0)
