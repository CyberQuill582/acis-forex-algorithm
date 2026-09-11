"""Schema-validated configuration loading (SPEC §9, ACIS-01 §2).

All six YAML files are validated here via pydantic. A bad or incomplete config
is fatal at load time (`ConfigError`) — there are NO defaults for anything that
affects correctness or risk (SPEC §9: "missing limit = fatal").

Guardrail values (`guardrail_limits.yaml`) change only by human commit
(guard-integrity law, SPEC §9). Nothing in this module writes config.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from config.calendars import (ExchangeCalendar, FxCalendar, Session, ZonedTime,  # noqa: F401
                              _Strict, check_boundaries)


class ConfigError(Exception):
    """Fatal configuration error — the system refuses to start (SPEC §9)."""


# --------------------------------------------------------------------------- #
# system_config.yaml
# --------------------------------------------------------------------------- #

class DataConfig(_Strict):
    stale_threshold_ms: int = Field(gt=0)
    clock_skew_tolerance_ms: int = Field(gt=0)
    reorder_tolerance_ms: int = Field(ge=0)
    tick_velocity_window_s: float = Field(gt=0)
    queue_max: int = Field(gt=0)
    queue_overflow_policy: Literal["drop_oldest"]
    macro_lookahead_min: int = Field(gt=0)
    calendar_stale_threshold_s: int = Field(gt=0)
    log_sample_rate: int = Field(ge=1)
    session_median_window: int = Field(gt=1)
    session_median_min_samples: int = Field(gt=1)


class RegimeConfig(_Strict):
    """NVMA thresholds (ACIS-02 §5–6). All required — no correctness defaults."""

    cycle_seconds: int = Field(ge=60, le=300)  # C-REG-1 (F1): cadence lock at boot
    atr_periods: tuple[int, int, int]
    adx_period: int = Field(gt=1)
    adx_strong: float = Field(gt=0)
    adx_weak: float = Field(gt=0)
    bb_window: int = Field(gt=10)
    bb_squeeze_pct: float = Field(gt=0, lt=1)
    bb_release_pct: float = Field(gt=0, lt=1)
    hurst_window: int = Field(ge=100)
    # GAP-0070 (owner-ratified 2026-07-17): hurst_trend is GONE — R/S Hurst is
    # drift-invariant and can never gate a trend; its only role is the
    # anti-persistence (mean-reversion) gate below. Value re-derived against
    # the repaired Anis–Lloyd multi-window estimator (RW FP 7.5%, OU k>=0.2
    # detection 95-100% at window 201).
    hurst_meanrev: float = Field(gt=0, lt=0.5)
    confidence_veto: float = Field(gt=0, lt=1)
    spread_veto_mult: float = Field(gt=1)
    velocity_veto_mult: float = Field(gt=0, lt=1)
    vol_medium_ratio: float = Field(gt=0)
    vol_high_ratio: float = Field(gt=0)
    vol_extreme_ratio: float = Field(gt=0)
    spread_illiquid_sigma: float = Field(gt=0)
    stability_window: int = Field(gt=1)

    @model_validator(mode="after")
    def _ordered(self) -> "RegimeConfig":
        if not (self.adx_weak < self.adx_strong):
            raise ValueError("adx_weak must be < adx_strong")
        if not (self.vol_medium_ratio < self.vol_high_ratio < self.vol_extreme_ratio):
            raise ValueError("vol ratios must be strictly increasing")
        if not (self.bb_squeeze_pct < self.bb_release_pct):
            raise ValueError("bb_squeeze_pct must be < bb_release_pct")
        if sorted(self.atr_periods) != list(self.atr_periods):
            raise ValueError("atr_periods must be ascending")
        return self

    @property
    def max_lookback(self) -> int:
        return max(self.atr_periods[-1], self.hurst_window, self.bb_window) + 1


class OptimizerConfig(_Strict):
    """QIEA config (ACIS-03 §5). All required; expectancy_min_r is the C9 floor —
    schema-enforced >= 0, so the gate may be tightened but never loosened below
    'E <= 0 cannot win' (master §5 C9)."""

    population_size: int = Field(gt=1)
    generations: int = Field(gt=0)
    qbit_resolution: int = Field(ge=4, le=16)
    rotation_angle_rad: float = Field(gt=0, le=0.5)
    qiea_cycle_seconds: int = Field(ge=14_400, le=86_400)  # 4h..24h (master §5)
    fitness_bars: int = Field(gt=10)
    fitness_min_bars: int = Field(gt=10)     # GAP-0008 window minimum
    fitness_min_trades: int = Field(gt=0)
    holdout_fraction: float = Field(gt=0, lt=0.5)  # GAP-0008 chronological tail
    holdout_min_trades: int = Field(gt=0)
    expectancy_min_r: float = Field(ge=0)    # C9: may only ever be raised

    @model_validator(mode="after")
    def _window_order(self) -> "OptimizerConfig":
        if self.fitness_min_bars > self.fitness_bars:
            raise ValueError("fitness_min_bars must be <= fitness_bars")
        return self


_STRATEGY_TYPES = frozenset({
    "TREND", "BREAKOUT", "MEAN_REVERSION", "MOMENTUM_SCALP", "PAIR_DIVERGENCE", "TSMOM",
})


class SignalsConfig(_Strict):
    """AGON config (ACIS-04 §5). All required — no correctness defaults."""

    signal_bar_seconds: int = Field(gt=0)     # v2.11: THE declared time base
    atr_period: int = Field(gt=1)             # ext-review C1: no hardcoded 14
    tsmom_disaster_stop_atr: float = Field(ge=5.0)  # far beyond the evolved SL cap 3.5
    # C4: 0.45. Floor ge=0.45 (GAP-0043): the Signal contract's emitted floor is
    # 0.45 — a discard threshold below it would be a silent no-op knob whose
    # drops surface mislabelled as construction errors. Tighter allowed.
    conviction_discard: float = Field(ge=0.45, lt=1)
    medium_vol_discount: float = Field(gt=0, le=1.0)  # dampen-only by schema
    valid_for_seconds: dict[str, int]
    momentum_scalp_horizon_bars: tuple[int, int]
    momentum_scalp_bar_seconds: int = Field(gt=0)     # GAP-0009: 60 = the 1-minute bar
    momentum_scalp_surge_ratio: float = Field(gt=1)
    fast_loop_decision_budget_ms: int = Field(gt=0)   # GAP-0007: 250
    tsmom_lookback_days: tuple[int, int, int]
    tsmom_min_history_days: int = Field(gt=0)
    modules_enabled: dict[str, bool]

    @model_validator(mode="after")
    def _complete(self) -> "SignalsConfig":
        if set(self.modules_enabled) != _STRATEGY_TYPES:
            raise ValueError(f"modules_enabled must declare exactly {sorted(_STRATEGY_TYPES)}")
        missing = _STRATEGY_TYPES - set(self.valid_for_seconds)
        if missing:
            raise ValueError(f"valid_for_seconds missing modules: {sorted(missing)}")
        if any(v <= 0 for v in self.valid_for_seconds.values()):
            raise ValueError("valid_for_seconds values must be > 0")
        lo, hi = self.momentum_scalp_horizon_bars
        if not (0 < lo < hi):
            raise ValueError("momentum_scalp_horizon_bars must be ascending positive")
        if sorted(self.tsmom_lookback_days) != list(self.tsmom_lookback_days):
            raise ValueError("tsmom_lookback_days must be ascending")
        if self.tsmom_min_history_days <= self.tsmom_lookback_days[-1]:
            raise ValueError("tsmom_min_history_days must exceed the longest lookback")
        if self.momentum_scalp_bar_seconds != self.signal_bar_seconds:
            raise ValueError(
                "one time base (v2.11): momentum_scalp_bar_seconds must equal "
                "signal_bar_seconds — the GAP-0009 scalp bar IS the signal bar"
            )
        return self


class ProvenanceConfig(_Strict):
    """ACIS-11 §5 — lifecycle cadences."""

    revalidation_cadence_days: int = Field(gt=0)
    challenger_comparison_window_days: int = Field(gt=0)


class GovernorConfig(_Strict):
    """Capital Governor config (ACIS-05 §5). All required."""

    marginal_alpha_window: int = Field(gt=1)
    marginal_alpha_min_trades: int = Field(gt=0)
    marginal_alpha_min_bucket: int = Field(gt=0)
    weekend_entry_buffer_s: int = Field(ge=0)
    scalp_min_hold_conflict: bool

    @model_validator(mode="after")
    def _window_order(self) -> "GovernorConfig":
        if self.marginal_alpha_min_trades > self.marginal_alpha_window:
            raise ValueError("marginal_alpha_min_trades must be <= marginal_alpha_window")
        return self


class ExecutionConfig(_Strict):
    """Execution Orchestrator config (ACIS-06 v1.1 §5). All required — the
    block is schema-fatal if missing. `dispatch_budget_ms` is the v2.10(c)
    observability value (GAP-0007 pattern): measured + logged, never a
    guardrail. Slippage alert level is NOT duplicated here — the orchestrator
    consumes `guardrails.slippage_alert_bps` (single source). The F10
    auto-throttle knob is deliberately absent: raised, never applied."""

    fragment_threshold_lots: float = Field(gt=0)
    fragment_size_jitter: tuple[float, float]
    fragment_time_jitter_s: tuple[float, float]
    min_fragment_lots: float = Field(gt=0)
    vwap_threshold_lots: float = Field(gt=0)
    vwap_window_s: int = Field(gt=0)
    fast_decay_seconds: int = Field(gt=0)
    signature_lot_variance: float = Field(gt=0, lt=1)
    dispatch_budget_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def _bounds(self) -> "ExecutionConfig":
        lo, hi = self.fragment_size_jitter
        if not (0 < lo < 1 < hi):
            raise ValueError("fragment_size_jitter must straddle 1.0 with lo > 0")
        tlo, thi = self.fragment_time_jitter_s
        if not (0 < tlo < thi):
            raise ValueError("fragment_time_jitter_s must be ascending and > 0")
        if self.min_fragment_lots > self.fragment_threshold_lots:
            raise ValueError("min_fragment_lots must be <= fragment_threshold_lots "
                             "(a fragmentable order must allow >= 1 fragment)")
        if self.vwap_threshold_lots < self.fragment_threshold_lots:
            raise ValueError("vwap_threshold_lots must be >= fragment_threshold_lots "
                             "(scheduling is the LARGE-order path, ACIS-06 §6)")
        return self


class RiskConfig(_Strict):
    """Risk Monitor operational config (ACIS-07 §5). All required — the block
    is schema-fatal if missing. Guardrail LIMITS are not here: they live in
    guardrail_limits.yaml under the guard-integrity law. `heartbeat_interval_s`
    is capped at 10 by the §12/§8.6 heartbeat contract (ACIS-12 §4)."""

    alpha_decay_recent_window: int = Field(gt=1)
    alpha_decay_min_trades: int = Field(gt=0)
    alpha_decay_baseline_min_trades: int = Field(gt=0)   # C5
    alpha_decay_recovery_trades: int = Field(gt=0)       # GAP-0050 recovery gate
    alpha_decay_recovery_mult: float = Field(gt=0, lt=1)
    var_method: Literal["delta_normal_undiversified"]    # declared method (§18: no
    # diversification credit — conservative sum of per-position VaR)
    var_window: int = Field(gt=2)                        # marks per instrument for σ
    var_horizon_seconds: int = Field(gt=0)               # GAP-P9E-03: the DECLARED
    # VaR holding-period horizon; per-mark σ is scaled √(horizon/eval_cadence) to it
    slippage_window: int = Field(gt=0)                   # fills in the rolling mean
    eval_cadence_s: float = Field(gt=0)
    heartbeat_path: str
    heartbeat_interval_s: float = Field(gt=0, le=10.0)   # §12: never slower than 10s

    @model_validator(mode="after")
    def _windows(self) -> "RiskConfig":
        if self.alpha_decay_min_trades > self.alpha_decay_recent_window:
            raise ValueError(
                "alpha_decay_min_trades must be <= alpha_decay_recent_window")
        return self


class TunableParam(_Strict):
    """One human-committed tunable `acis_stage_config` may stage, WITH its
    declared numeric bounds (ACIS-08 §5, GAP-P10I-01/GAP-P10E-04). Staging is
    safe BY CONSTRUCTION: a staged value must fall inside [min, max] — there is
    no substring heuristic to evade and no way to stage a risk-raising value on
    an allowlisted path. Guardrail/equity paths are structurally forbidden."""

    path: str
    min: float
    max: float

    @model_validator(mode="after")
    def _bounds_and_not_guardrail(self) -> "TunableParam":
        low = self.path.strip().lower()
        if low.startswith("guardrail_limits") or "equity_floor" in low:
            raise ValueError(
                f"tunable path {self.path!r} is a guardrail/equity path — "
                "structurally forbidden (guard-integrity law, ACIS-08 §5)")
        if self.min > self.max:
            raise ValueError(f"tunable {self.path!r}: min must be <= max")
        return self


class MonitoringConfig(_Strict):
    """MCP monitoring/control plane operational config (ACIS-08 §6). Required —
    the block is schema-fatal if missing. Guardrail LIMITS are NOT here (they
    live in guardrail_limits.yaml, read-only to this layer). `tunable_paths` is
    the human-committed BOUNDED allowlist `acis_stage_config` may touch;
    guardrail/equity paths are structurally excluded (ACIS-08 §5, C-MCP-2)."""

    transport: Literal["stdio", "sse"]
    heartbeat_fast_s: float = Field(gt=0, le=10.0)     # §12 fast-loop SLA ceiling
    heartbeat_other_s: float = Field(gt=0)
    missed_beats_flatten: int = Field(gt=0)            # §12: 3 missed beats → flatten rec
    log_tail_max: int = Field(gt=0)
    tunable_paths: list[TunableParam] = Field(min_length=1)  # bounded allowlist

    @model_validator(mode="after")
    def _unique_paths(self) -> "MonitoringConfig":
        seen = [t.path.strip() for t in self.tunable_paths]
        if len(set(seen)) != len(seen):
            raise ValueError("tunable_paths: duplicate path")
        return self

    def tunable_bounds(self) -> dict[str, tuple[float, float]]:
        """path -> (min, max) for the tool-layer validator."""
        return {t.path.strip(): (t.min, t.max) for t in self.tunable_paths}


class SystemConfig(_Strict):
    mode: Literal["backtest", "paper", "live"]
    base_unit_usd: float = Field(gt=0)
    active_account: str
    session_boundaries: list[ZonedTime] = Field(min_length=1)  # C1: empty list is fatal
    param_stall_alert_boundaries: int = Field(gt=0)
    data: DataConfig
    regime: RegimeConfig
    optimizer: OptimizerConfig
    signals: SignalsConfig
    provenance: ProvenanceConfig
    governor: GovernorConfig
    execution: ExecutionConfig
    risk: RiskConfig
    monitoring: MonitoringConfig


# --------------------------------------------------------------------------- #
# instruments.yaml — asset-class law (SPEC §3.7): contract metadata is declared
# data; an enabled instrument with incomplete metadata is fatal.
# --------------------------------------------------------------------------- #

# FxCalendar / ExchangeCalendar live in config/calendars.py (local time, GAP-P12D-10).


class InstrumentCosts(_Strict):
    """C8 cost-model friction in price units (ACIS-03 §5). Required for every
    enabled instrument — no silent zero-cost optimisation. Phase 11 calibrates
    these against OANDA practice-feed spreads (master §13, v2.9)."""

    commission_per_side: float = Field(ge=0)
    slippage_per_side: float = Field(ge=0)


class InstrumentSpec(_Strict):
    enabled: bool
    asset_class: Literal["fx", "metal", "index_cfd", "energy", "future"]
    base_ccy: str | None = None
    quote_ccy: str
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    lot_step: float = Field(gt=0)
    min_lot: float = Field(gt=0)
    margin_model: str
    swap_convention: str
    max_plausible_spread: float = Field(gt=0)
    calendar: str
    roll_window_days: int | None = Field(default=None, gt=0)
    costs: InstrumentCosts | None = None
    vol_target_atr_frac: float | None = Field(default=None, gt=0)  # C16 declared target

    @model_validator(mode="after")
    def _futures_need_roll(self) -> "InstrumentSpec":
        if self.asset_class == "future" and self.roll_window_days is None:
            raise ValueError("future instrument requires roll_window_days (SPEC §3.7)")
        if self.enabled and self.costs is None:
            raise ValueError(
                "enabled instrument requires a costs block (C8 — no silent "
                "zero-cost optimisation, ACIS-03 §5)"
            )
        if self.enabled and self.vol_target_atr_frac is None:
            raise ValueError(
                "enabled instrument requires vol_target_atr_frac (C16 declared "
                "vol target, ACIS-05 §6.2)"
            )
        return self


class PairRelationship(_Strict):
    """§5.5 coupled-pair declaration. A correlation without its declared
    window AND method is a config error — schema-enforced."""

    legs: tuple[str, str]
    expected_sign: Literal[-1, 1]
    correlation_window: int = Field(gt=1)
    method: Literal["pearson_log_returns"]
    stability_floor: float = Field(gt=0, lt=1)
    zscore_window: int = Field(gt=1)

    @model_validator(mode="after")
    def _distinct_legs(self) -> "PairRelationship":
        if self.legs[0] == self.legs[1]:
            raise ValueError("pair legs must be distinct instruments")
        return self


class InstrumentsConfig(_Strict):
    calendars: dict[str, FxCalendar | ExchangeCalendar] = Field(min_length=1)
    instruments: dict[str, InstrumentSpec] = Field(min_length=1)
    clusters: dict[str, list[str]] = Field(default_factory=dict)
    pair_relationships: dict[str, PairRelationship] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cross_refs(self) -> "InstrumentsConfig":
        for sym, spec in self.instruments.items():
            if spec.calendar not in self.calendars:
                raise ValueError(f"{sym}: unknown calendar {spec.calendar!r}")
        # C7: clusters may reference disabled (extension) instruments — inert —
        # but an unknown symbol is a config error, never a silent drop.
        for cluster, members in self.clusters.items():
            for sym in members:
                if sym not in self.instruments:
                    raise ValueError(f"cluster {cluster!r}: unknown symbol {sym!r}")
        for name, rel in self.pair_relationships.items():
            for leg in rel.legs:
                if leg not in self.instruments:
                    raise ValueError(f"pair {name!r}: unknown leg {leg!r}")
        return self

    @property
    def enabled(self) -> dict[str, InstrumentSpec]:
        return {s: sp for s, sp in self.instruments.items() if sp.enabled}


# --------------------------------------------------------------------------- #
# guardrail_limits.yaml — human-commit only (guard-integrity law, SPEC §9).
# Every field required; the taper defaults 0.60/0.80 are the RATIFIED FLOOR
# (SPEC §9.5): stricter (smaller) is allowed, looser is schema-rejected.
# --------------------------------------------------------------------------- #

class GuardrailLimits(_Strict):
    daily_drawdown_pct: float = Field(gt=0)
    per_instrument_drawdown_pct: float = Field(gt=0)
    alpha_decay_sharpe_mult: float = Field(gt=0)
    var_cap_pct: float = Field(gt=0)
    cluster_cap_pct: float = Field(gt=0)
    # master §6 exact value 30; ceiling schema-enforced — stricter allowed, looser rejected
    single_currency_delta_cap_pct: float = Field(gt=0, le=30.0)
    slippage_alert_bps: float = Field(gt=0)
    equity_floor_usd: float = Field(gt=0)
    taper_start_fraction: float = Field(gt=0, le=0.60)
    entry_halt_fraction: float = Field(gt=0, le=0.80)

    @model_validator(mode="after")
    def _taper_order(self) -> "GuardrailLimits":
        if self.taper_start_fraction >= self.entry_halt_fraction:
            raise ValueError("taper_start_fraction must be < entry_halt_fraction")
        return self


# --------------------------------------------------------------------------- #
# platform_rules.yaml — account doctrine (SPEC §9.5): one rulebook per account,
# drawdown limits with their EXACT measurement semantics.
# --------------------------------------------------------------------------- #

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
    type: Literal["static", "trailing"]
    anchor: Literal["eod", "intraday"]
    basis: Literal["balance", "equity"]
    limit_pct: float = Field(gt=0)


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


class PlatformRules(_Strict):
    accounts: dict[str, AccountRulebook] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# event_sources.yaml — trusted channels + Tier-1/Tier-G taxonomy (SPEC §3.5–3.6)
# --------------------------------------------------------------------------- #

class EventSource(_Strict):
    name: str
    kind: Literal["calendar", "headline"]
    trust_tier: int = Field(ge=1, le=2)


class TierGClass(_Strict):
    keywords: list[str] = Field(min_length=1)
    affected: list[str] = Field(min_length=1)
    ttl_seconds: int = Field(gt=0)  # GAP-0015: bounded duration by construction
    flatten_eligible: bool
    confirmation_window_seconds: int = Field(gt=0)
    min_confirmations_for_flatten: int = Field(ge=2)  # GAP-0011: never a single source


class EventSourcesConfig(_Strict):
    sources: list[EventSource] = Field(min_length=1)
    tier1_events: list[str] = Field(min_length=1)
    tierg_taxonomy: dict[str, TierGClass] = Field(default_factory=dict)


class CautionMultiplier(_Strict):
    """§3.6 slow-lane staged value — dampen-only, clamped at the schema (GAP-0016)."""

    instrument: str
    value: float = Field(gt=0, le=1.0)


# --------------------------------------------------------------------------- #
# scenario_book.yaml (SPEC §8.5)
# --------------------------------------------------------------------------- #

class Scenario(_Strict):
    name: str
    kind: Literal["gap_through_stop", "flash_crash", "broker_outage", "liquidity_vacuum"]
    description: str
    params: dict[str, float | str] = Field(default_factory=dict)
    # ACIS-12 §2: the human-committed ceiling this scenario may ever cost.
    # Missing = config-fatal; the replay gate asserts loss <= ceiling AND
    # equity-floor survival for every scenario.
    max_loss_pct_nav: float = Field(gt=0)

    @model_validator(mode="after")
    def _kind_params(self) -> "Scenario":
        """ACIS-12 §12: a missing/invalid scenario field is fatal at load."""
        def need(key: str, numeric: bool = True) -> None:
            v = self.params.get(key)
            if v is None:
                raise ValueError(f"scenario {self.name!r} ({self.kind}) requires params.{key}")
            if numeric and not isinstance(v, (int, float)):
                raise ValueError(f"scenario {self.name!r}: params.{key} must be numeric")

        if self.kind == "gap_through_stop":
            need("instrument", numeric=False)
            need("gap_pct")
        elif self.kind == "flash_crash":
            need("instrument", numeric=False)
            need("drop_pct")
        elif self.kind == "broker_outage":
            need("duration_s")   # instrument optional: None = worst across enabled (C-SWN-4)
        elif self.kind == "liquidity_vacuum":
            need("instrument", numeric=False)
            need("spread_mult")
            need("ref_price")    # units = worst_notional / ref_price (C-SWN-5)
            if float(self.params["spread_mult"]) <= 1:
                raise ValueError(f"scenario {self.name!r}: spread_mult must exceed 1")
        return self


class ScenarioBook(_Strict):
    scenarios: list[Scenario] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #

class AcisConfig(_Strict):
    system: SystemConfig
    instruments: InstrumentsConfig
    guardrails: GuardrailLimits
    platform_rules: PlatformRules
    event_sources: EventSourcesConfig
    scenario_book: ScenarioBook

    @model_validator(mode="after")
    def _active_account_has_rulebook(self) -> "AcisConfig":
        # SPEC §9/§9.5: attach-time fatal if the active account has no rulebook.
        if self.system.active_account not in self.platform_rules.accounts:
            raise ValueError(
                f"active account {self.system.active_account!r} has no rulebook "
                "in platform_rules.yaml (SPEC §9.5 — fatal)"
            )
        # ACIS-10 §2: a Tier-G taxonomy entry naming an undeclared instrument is fatal
        # (C7 pattern: disabled/extension instruments are fine — inert; unknown is a bug).
        for cls, entry in self.event_sources.tierg_taxonomy.items():
            for sym in entry.affected:
                if sym not in self.instruments.instruments:
                    raise ValueError(f"tierg_taxonomy[{cls}]: unknown instrument {sym!r}")
        # ACIS-12 §12: a scenario naming an undeclared instrument is fatal
        # (mirrors the Tier-G taxonomy rule above; disabled/extension = inert-ok).
        for sc in self.scenario_book.scenarios:
            sym = sc.params.get("instrument")
            if sym is not None and sym not in self.instruments.instruments:
                raise ValueError(f"scenario {sc.name!r}: unknown instrument {sym!r}")
        # GAP-0025/0033: the C1 staging boundaries and the session windows may not
        # silently diverge (bidirectional, on local (zone, time) pairs).
        check_boundaries(self.system.session_boundaries, self.instruments.calendars)
        return self


_FILES = {
    "system": "system_config.yaml",
    "instruments": "instruments.yaml",
    "guardrails": "guardrail_limits.yaml",
    "platform_rules": "platform_rules.yaml",
    "event_sources": "event_sources.yaml",
    "scenario_book": "scenario_book.yaml",
}


def load_config(config_dir: str | Path) -> AcisConfig:
    """Load and validate all six config files. Any problem is fatal (SPEC §9)."""
    config_dir = Path(config_dir)
    raw: dict[str, object] = {}
    for key, filename in _FILES.items():
        path = config_dir / filename
        if not path.is_file():
            raise ConfigError(f"missing required config file: {path}")
        try:
            with open(path, encoding="utf-8") as fh:
                raw[key] = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{filename}: invalid YAML: {exc}") from exc
    try:
        return AcisConfig(**raw)  # type: ignore[arg-type]
    except Exception as exc:
        raise ConfigError(f"configuration invalid: {exc}") from exc
