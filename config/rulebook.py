"""platform_rules.yaml — the account doctrine (SPEC §9.5): one rulebook per account, every
drawdown limit with its EXACT measurement semantics. Human-committed; nothing here writes
config. Split out of config/schemas.py (GAP-P12M-01), which re-exports these names.

Invariants:
  * A `daily` rule (GAP-P12D-54) declares its local reset instant (`reset`, a {zone, at}
    like every market time) and what is captured there (`reset_basis`: balance, equity or
    the higher of the two). A static or trailing rule declares neither.
  * `limit_of: initial` sizes a limit as a % of the rulebook's declared `initial_capital`
    (FTMO: "5% of the Initial Simulated Capital"), so it is a schema error without one.
    The default `anchor` keeps every existing rule's meaning: a % of its own anchor.
  * A declared `initial_capital` anchors static rules and seeds trailing high-water marks;
    it can only make a rule stricter than the first observed basis would.
  * Per-account taper fractions may only be STRICTER than the ratified 0.60/0.80 floor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from config.calendars import ZonedTime, _Strict


class NewsRules(_Strict):
    restricted: bool
    window_before_s: int | None = Field(default=None, ge=0)
    window_after_s: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _windows_if_restricted(self) -> "NewsRules":
        if self.restricted and (self.window_before_s is None or self.window_after_s is None):
            raise ValueError("restricted account requires explicit blackout windows (SPEC §3.5)")
        return self


class DrawdownRule(_Strict):
    type: Literal["static", "trailing", "daily"]
    anchor: Literal["eod", "intraday"]
    basis: Literal["balance", "equity"]            # what is measured against the anchor
    limit_pct: float = Field(gt=0)
    reset: ZonedTime | None = None                 # daily only: when the day rolls, local
    reset_basis: Literal["balance", "equity", "max"] | None = None   # daily only: captured then
    limit_of: Literal["anchor", "initial"] = "anchor"

    @model_validator(mode="after")
    def _daily_fields(self) -> "DrawdownRule":
        daily = self.type == "daily"
        if daily != (self.reset is not None) or daily != (self.reset_basis is not None):
            raise ValueError("a daily rule declares `reset` and `reset_basis`; "
                             "a static or trailing rule declares neither")
        return self


class AccountRulebook(_Strict):
    platform: str
    news: NewsRules
    min_hold_seconds: int = Field(ge=0)
    max_lots: float | None = Field(default=None, gt=0)
    weekend_holding_allowed: bool
    drawdown_rules: list[DrawdownRule]  # may be empty (personal account), but must be declared
    consistency_max_day_profit_pct: float | None = Field(default=None, gt=0)
    min_trading_days: int | None = Field(default=None, gt=0)
    # Per-account override of the §9.5 taper — stricter-only (ratified floor).
    taper_start_fraction: float | None = Field(default=None, gt=0, le=0.60)
    entry_halt_fraction: float | None = Field(default=None, gt=0, le=0.80)
    initial_capital: float | None = Field(default=None, gt=0)   # the account's starting capital

    @model_validator(mode="after")
    def _initial_declared(self) -> "AccountRulebook":
        if self.initial_capital is None and any(r.limit_of == "initial"
                                                for r in self.drawdown_rules):
            raise ValueError("a rule sized on initial capital needs `initial_capital` declared")
        return self


class PlatformRules(_Strict):
    accounts: dict[str, AccountRulebook] = Field(min_length=1)
