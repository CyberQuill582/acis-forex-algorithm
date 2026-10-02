"""The `targets:` block of system_config.yaml: the target-position path (ACIS-04 v1.6 §4b, ACIS-05 v1.7
§6.4; R1.6). Absent = the path is off.

Declared, never defaulted (SPEC §9): each value changes what the engine trades.
  * `family` — the registered family-version the path trades (a provenance id, e.g. `trend_d1_v1`).
  * `universe` — the instruments it trades (R6-4). One path per instrument (R6-3): until a mixed book
    is built, the universe IS the enabled set, so no legacy module trades beside it.
  * `idm` — the instrument diversification multiplier, fixed at registration (≤ 2.5, master §5.5).
  * `buffer` — Carver's band, a fraction of the average position (master §5.5: 0.10).
  * `history_days` — the venue history seeded at first boot (ACIS-04: at least 3 years).
  * `settle_s`, `slot_grace_s` — the decision runs this long after 17:00 New York; a slot may run at
    most this late, never caught up.
  * `macro_dir`, `rate_max_stale_days` (+ `_weekly`) — the dated overnight rates the excess-return price reads
    (R6-1: a table staler than this gives no target).
The active account's rulebook must declare `initial_capital` and `vol_target_annual` (ACIS-05 §6.4).
"""

from __future__ import annotations

from pydantic import Field

from config.calendars import _Strict


class TargetsConfig(_Strict):
    family: str = Field(min_length=1)
    universe: list[str] = Field(min_length=1)
    idm: float = Field(gt=0, le=2.5)
    buffer: float = Field(ge=0)
    history_days: int = Field(ge=1095)
    settle_s: float = Field(ge=0, le=3600)
    slot_grace_s: float = Field(gt=0, le=3600)
    macro_dir: str = Field(min_length=1)
    rate_max_stale_days: int = Field(gt=0, le=10)
    rate_max_stale_days_weekly: int = Field(gt=0, le=21)   # GAP-P12D-146: BIS, SNB


def check_targets(cfg) -> None:
    """Cross-file rules for an `AcisConfig` with a `targets:` block."""
    t = cfg.system.targets
    if t is None:
        return
    enabled = {s for s, sp in cfg.instruments.instruments.items() if sp.enabled}
    if set(t.universe) != enabled or len(t.universe) != len(set(t.universe)):
        raise ValueError(f"targets.universe must be the enabled instruments, once each (R6-3): "
                         f"{sorted(set(t.universe) ^ enabled)}")
    book = cfg.platform_rules.accounts[cfg.system.active_account]
    if book.initial_capital is None or book.vol_target_annual is None:
        raise ValueError(f"{cfg.system.active_account}: the target path needs initial_capital and "
                         "vol_target_annual declared (ACIS-05 v1.7 §6.4)")
