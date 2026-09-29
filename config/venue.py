"""The `venue:` block of system_config.yaml (ACIS-13 §6.1): which real venue, which account, and the
adapter's budgets and timers. Human-committed; schema-fatal when invalid.

Invariants:
  * The account id is config, never discovered (C-VEN-5); 0 means "not yet committed" and the
    attach refuses it.
  * The request budget can never exceed 1,000 (half the FTMO / E8 cap, GAP-P12D-57, C-VEN-4), the
    close reserve sits inside it, and the order allowance fits in what the reserve leaves.
  * The heartbeat is at most 10 s (the documented cadence, C-VEN-10), and liveness outlasts it.
  * Local rate limits are at most half the documented per-connection limits (F-05).
  * Only the JSON-over-WebSocket transport exists; Protobuf needs a §16 edit first (OQ-02).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from config.calendars import _Strict


class BackoffConfig(_Strict):
    base_s: float = Field(gt=0)
    factor: float = Field(ge=1)
    cap_s: float = Field(gt=0)
    max_consecutive: int = Field(gt=0)


class RateLimits(_Strict):
    general: float = Field(gt=0, le=25)            # half of 50/s
    historical: float = Field(gt=0, le=2.5)        # half of 5/s


class VenueConfig(_Strict):
    adapter: Literal["mock", "ctrader"]
    environment: Literal["demo", "live"]
    ctid_trader_account_id: int = Field(ge=0)
    symbol_names: dict[str, str] = Field(min_length=1)
    transport: Literal["json_ws"]
    daily_request_budget: int = Field(gt=0, le=1000)
    close_reserve: int = Field(gt=0)
    max_orders_per_day: int = Field(gt=0)
    heartbeat_s: float = Field(gt=0, le=10)
    liveness_timeout_s: float = Field(gt=0)
    order_ack_timeout_s: float = Field(gt=0)
    stop_confirm_timeout_s: float = Field(gt=0)
    equity_poll_s: float = Field(gt=0)
    reconcile_interval_s: float = Field(gt=0)
    backoff: BackoffConfig
    rate_limit_per_s: RateLimits

    @model_validator(mode="after")
    def _consistent(self) -> "VenueConfig":
        if self.close_reserve >= self.daily_request_budget:
            raise ValueError("close_reserve must sit inside daily_request_budget")
        if 2 * self.max_orders_per_day > self.daily_request_budget - self.close_reserve:
            raise ValueError("the order allowance (2 per order) exceeds budget − reserve")
        if self.liveness_timeout_s <= self.heartbeat_s:
            raise ValueError("liveness_timeout_s must exceed heartbeat_s")
        return self

    @property
    def account_key(self) -> str:
        return f"{self.adapter}:{self.environment}:{self.ctid_trader_account_id}"
