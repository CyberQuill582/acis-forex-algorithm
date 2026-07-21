"""Scenario-replay RELEASE GATE (ACIS-12 §3/§14, master §8.5).

Part of every full suite run (cheap, synthetic). A failed invariant FAILS THE
BUILD — a build whose replay violates any max-loss ceiling or breaches the
equity floor does not ship. Re-runs by construction whenever the book or the
guardrails change (it reads both live).
"""

from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path

import pytest

from config.schemas import ScenarioBook, load_config
from core.optimizer.param_types import GENE_SPECS
from core.risk.scenario_replay import ScenarioReplay
from tests.optimizer_fixtures import CapturingLogger

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_NAV = Decimal("10000")            # the dev-account base (equity_floor 9000 assumes 10k)
_SL_CAP = GENE_SPECS["atr_multiplier_sl"][1]   # 3.5


def _replay(book, guardrails, instruments, *, nav=_NAV, clusters=None):
    return ScenarioReplay(
        book, guardrails, instruments, CapturingLogger(),
        nav=nav, equity_floor_usd=guardrails.equity_floor_usd,
        atr_multiplier_sl_cap=_SL_CAP, clusters=clusters or {})


@pytest.fixture
def cfg():
    return load_config(CONFIG_DIR)


@pytest.fixture
def instruments(cfg):
    # ALL declared specs — gap/vacuum scenarios reference extension instruments
    # (USD_CHF, XAU_USD) that must be known; the outage's worst-across-enabled
    # vol computation filters to specs that carry a vol target itself.
    return dict(cfg.instruments.instruments)


def test_release_gate_every_scenario_passes(cfg, instruments) -> None:
    """THE GATE: every shipped scenario is within its ceiling AND survives the
    equity floor against the current guardrails."""
    verdicts = _replay(cfg.scenario_book, cfg.guardrails, instruments,
                       clusters=cfg.instruments.clusters).replay_all()
    assert len(verdicts) == len(cfg.scenario_book.scenarios)
    failing = [v for v in verdicts if not v.passed]
    assert not failing, "scenario-replay ceiling/floor breach:\n" + "\n".join(
        f"{v.scenario}: loss={v.loss_pct_nav:.3f}% ceiling={v.ceiling_pct_nav}% "
        f"floor_survives={v.floor_survives}" for v in failing)


def test_gate_can_fail_on_oversized_caps(cfg, instruments) -> None:
    """A test-local oversized cluster cap (NEVER the real config) makes
    chf_depeg breach — the gate provably can fail (ACIS-12 §14)."""
    # both caps oversized (model_copy bypasses the schema ceilings by design —
    # this is a TEST-LOCAL construction, never the real config): worst book
    # 60% NAV × 35% gap = 21% NAV, breaching both the 7.5% ceiling and the floor.
    limits = cfg.guardrails.model_copy(
        update={"cluster_cap_pct": 60.0, "single_currency_delta_cap_pct": 80.0})
    verdicts = _replay(cfg.scenario_book, limits, instruments,
                       clusters=cfg.instruments.clusters).replay_all()
    chf = next(v for v in verdicts if v.scenario == "chf_depeg_2015")
    assert not chf.passed
    assert chf.loss_pct_nav > chf.ceiling_pct_nav
    assert not chf.floor_survives


def test_gap_loss_uses_post_gap_price(cfg, instruments) -> None:
    """C-SWN-2: loss scales with the gap, not the (irrelevant-by-law) stop level.
    A stop 10 pips above the gap floor changes nothing — the loss is worst ×
    |gap|, exactly."""
    replay = _replay(cfg.scenario_book, cfg.guardrails, instruments,
                     clusters=cfg.instruments.clusters)
    chf = next(sc for sc in cfg.scenario_book.scenarios if sc.name == "chf_depeg_2015")
    v = replay.replay_one(chf)
    worst = float(v.worst_book_notional)
    expected_pct = worst * 0.35 / float(_NAV) * 100.0   # faithful -35% gap (GAP-0108)
    assert v.loss_pct_nav == pytest.approx(expected_pct)


def test_outage_bound_exceeds_plain_stop_distance(cfg, instruments) -> None:
    """C-SWN-4: the outage bound = stop geometry + gap allowance, strictly
    greater than a plain stop-distance loss (the gap allowance is real, never
    'fills at level')."""
    replay = _replay(cfg.scenario_book, cfg.guardrails, instruments,
                     clusters=cfg.instruments.clusters)
    outage = next(sc for sc in cfg.scenario_book.scenarios
                  if sc.kind == "broker_outage")
    v = replay.replay_one(outage)
    worst = float(v.worst_book_notional)
    vol_frac = max(sp.vol_target_atr_frac for sp in instruments.values()
                   if sp.vol_target_atr_frac is not None)
    plain_stop_pct = worst * (_SL_CAP * vol_frac) / float(_NAV) * 100.0
    assert v.loss_pct_nav > plain_stop_pct     # the gap allowance is on top


def test_vacuum_cost_scales_with_spread_mult(cfg, instruments) -> None:
    """C-SWN-5: forced-exit cost scales linearly with spread_mult."""
    base = next(sc for sc in cfg.scenario_book.scenarios
                if sc.kind == "liquidity_vacuum")
    doubled = base.model_copy(update={
        "params": {**base.params, "spread_mult": float(base.params["spread_mult"]) * 2}})
    book2 = ScenarioBook(scenarios=[base, doubled])
    replay = _replay(book2, cfg.guardrails, instruments, clusters=cfg.instruments.clusters)
    v_base = replay.replay_one(base)
    v_double = replay.replay_one(doubled)
    assert v_double.loss_pct_nav == pytest.approx(2 * v_base.loss_pct_nav)


def test_cluster_less_instrument_uses_delta_cap_not_cluster_cap(cfg, instruments) -> None:
    """GAP-P9I-02: a cluster-less instrument's worst legal book is bounded ONLY
    by the 30% delta cap (the 20% cluster cap does not apply). The gate must not
    flatter sizing by assuming a cluster cap that isn't there."""
    replay = _replay(cfg.scenario_book, cfg.guardrails, instruments, clusters={})  # none clustered
    chf = next(sc for sc in cfg.scenario_book.scenarios if sc.name == "chf_depeg_2015")
    v = replay.replay_one(chf)
    # cluster-less → 30% × NAV worst book (not 20%): 30% × 35% gap = 10.5% NAV
    assert float(v.worst_book_notional) == pytest.approx(0.30 * float(_NAV))
    assert v.loss_pct_nav == pytest.approx(10.5)
    assert not v.passed                       # exceeds the 7.5% ceiling when unclustered


def test_outage_gap_allowance_prefers_enabled_instrument(cfg, instruments) -> None:
    """GAP-0108 refinement: the broker-outage gap allowance sources from the worst
    ENABLED-instrument gap, not a disabled extension. A test-local book where
    EUR_USD (enabled) gaps 5% and USD_CHF (disabled) gaps 35% ⇒ the allowance is
    5%, not the 35% CHF."""
    book = ScenarioBook(scenarios=[
        {"name": "eur_gap", "kind": "gap_through_stop", "description": "d",
         "params": {"instrument": "EUR_USD", "gap_pct": -5.0}, "max_loss_pct_nav": 5.0},
        {"name": "chf_gap", "kind": "gap_through_stop", "description": "d",
         "params": {"instrument": "USD_CHF", "gap_pct": -35.0}, "max_loss_pct_nav": 7.5},
    ])
    r = _replay(book, cfg.guardrails, instruments, clusters=cfg.instruments.clusters)
    assert r._worst_book_gap_pct() == 5.0            # enabled EUR_USD, not disabled CHF


def test_outage_gap_allowance_falls_back_to_worst_when_none_enabled(cfg, instruments) -> None:
    """Conservative fallback: with NO enabled gap scenario (the shipped config —
    CHF + XAU both disabled), the outage retains the overall worst gap so it never
    under-provisions. The shipped gate is unchanged by the refinement."""
    r = _replay(cfg.scenario_book, cfg.guardrails, instruments,
                clusters=cfg.instruments.clusters)
    # shipped book: chf −35 (disabled), weekend_war +5 (disabled) ⇒ fallback 35
    assert r._worst_book_gap_pct() == 35.0


def test_missing_ceiling_is_config_fatal() -> None:
    """ACIS-12 §14: a scenario without max_loss_pct_nav cannot even be loaded."""
    with pytest.raises(Exception):
        ScenarioBook(scenarios=[{
            "name": "x", "kind": "flash_crash", "description": "d",
            "params": {"instrument": "EUR_USD", "drop_pct": -5.0}}])
