"""QIEA evolution gates + decode/repair + reproducibility (ACIS-03 Â§6/Â§14)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.data.errors import DataQualityError
from core.optimizer.param_types import GENE_SPECS, RegimeLabelledHistory
from core.optimizer.qiea import QIEA, decode_gene, fitness_window, repair_invariants
from core.regime.regime_types import RegimeType
from tests.optimizer_fixtures import (
    T0,
    TEST_COSTS,
    CapturingLogger,
    bars_from_closes,
    opt_cfg,
    zigzag_closes,
    zigzag_history,
)

REGIME = RegimeType.STRONG_TREND_UP


def make_qiea(cfg=None) -> tuple[QIEA, CapturingLogger]:
    log = CapturingLogger()
    return QIEA(cfg or opt_cfg(), TEST_COSTS, log,
                signal_bar_seconds=60, atr_period=14), log


# ---------------------------- decode / repair -------------------------------- #

def test_decode_clamps_out_of_range_raw() -> None:
    lo, hi, _ = GENE_SPECS["ema_fast"]
    assert decode_gene("ema_fast", -0.5) == lo
    assert decode_gene("ema_fast", 1.5) == hi
    assert decode_gene("ema_fast", 0.0) == lo
    assert decode_gene("ema_fast", 1.0) == hi


def test_decode_float_gene_in_range() -> None:
    v = decode_gene("atr_multiplier_sl", 0.5)
    assert 1.0 <= v <= 3.5 and isinstance(v, float)


def test_repair_ema_invariant() -> None:
    g = {"ema_fast": 50, "ema_slow": 30, "atr_multiplier_sl": 1.0, "atr_multiplier_tp": 2.0}
    assert repair_invariants(g)["ema_slow"] == 51


def test_repair_tp_sl_invariant() -> None:
    g = {"ema_fast": 5, "ema_slow": 20, "atr_multiplier_sl": 3.0, "atr_multiplier_tp": 2.0}
    r = repair_invariants(g)
    assert r["atr_multiplier_tp"] > r["atr_multiplier_sl"]
    assert r["atr_multiplier_tp"] <= GENE_SPECS["atr_multiplier_tp"][1]


# ---------------------------- evolution gates -------------------------------- #

def test_evolve_returns_valid_paramset_and_logs_run() -> None:
    qiea, log = make_qiea()
    ps = qiea.evolve(REGIME, zigzag_history(500), seed=42, now=T0)
    assert ps is not None
    assert ps.regime is REGIME  # ParamSet construction already proved ranges+invariants
    runs = log.events("EVOLUTION_RUN")
    assert len(runs) == 1
    assert runs[0]["data"]["seed"] == 42
    assert runs[0]["data"]["train_bars"] == 400 and runs[0]["data"]["holdout_bars"] == 100


def test_same_seed_same_history_identical_champion() -> None:
    """Â§3 determinism scope: reproducibility is the binding requirement. (Seed 9: seed 7's
    champion is a knife-edge the §5.6 plateau law now refuses — pinned in test_plateau_law.py.)"""
    a = make_qiea()[0].evolve(REGIME, zigzag_history(500), seed=9, now=T0)
    b = make_qiea()[0].evolve(REGIME, zigzag_history(500), seed=9, now=T0)
    assert a is not None and b is not None
    assert a.gene_values() == b.gene_values()
    assert a.param_set_id == b.param_set_id
    assert a.fitness_score == b.fitness_score


def test_insufficient_bars_no_evolution() -> None:
    qiea, log = make_qiea()
    assert qiea.evolve(REGIME, zigzag_history(80), seed=1, now=T0) is None
    assert len(log.events("EVOLUTION_INSUFFICIENT_DATA")) == 1
    assert log.events("EVOLUTION_RUN") == []


def test_champion_failing_holdout_gate_is_not_staged() -> None:
    """C-QIEA-8: trades in train, flat holdout tail => rejected out-of-sample."""
    closes = zigzag_closes(400) + [zigzag_closes(400)[-1]] * 100  # flat last 100
    history = RegimeLabelledHistory("EUR_USD", bars_from_closes(closes, REGIME), bar_seconds=60)
    qiea, log = make_qiea()
    assert qiea.evolve(REGIME, history, seed=42, now=T0) is None
    assert len(log.events("EVOLUTION_REJECTED_OOS")) == 1
    assert log.events("EVOLUTION_RUN") == []


def test_mislabelled_bar_raises() -> None:
    bars = bars_from_closes(zigzag_closes(500), RegimeType.RANGING_TIGHT)
    qiea, _ = make_qiea()
    with pytest.raises(DataQualityError):
        qiea.evolve(REGIME, RegimeLabelledHistory("EUR_USD", bars, bar_seconds=60), seed=1, now=T0)


def test_evolves_on_every_bar_inside_the_span_not_a_bar_count() -> None:
    """GAP-P12D-29 (master §5 v2.18): the window is a recency span in time. Of 2,000 one-minute
    bars, exactly the 1,440 that open within one day of `now` are used — the oldest bar on the
    span's edge included, nothing older, and no 500-bar cap."""
    cfg = opt_cfg(fitness_span_days=1)
    history = zigzag_history(2000)
    now = history.bars[-1].ts + timedelta(seconds=60)
    window = fitness_window(history, cfg, now)
    assert len(window) == 1440 and window[0].ts == now - timedelta(days=1)
    qiea, log = make_qiea(cfg)
    assert qiea.evolve(REGIME, history, seed=42, now=now) is not None
    run = log.events("EVOLUTION_RUN")[0]["data"]
    assert run["train_bars"] + run["holdout_bars"] == 1440


# ---------------- phase-4 audit triage regressions (GAP-0036/0037/0038) ---------------- #

def test_gap0036_same_seed_different_params_get_different_ids() -> None:
    """The audit-link id is content-derived: same seed, different history/regime
    => different champion params => different param_set_id (Â§4 traceability). (Seed 5 stages
    on both histories; seed 42's RANGING_TIGHT champion fails the §5.6 plateau law.)"""
    a = make_qiea()[0].evolve(REGIME, zigzag_history(500), seed=5, now=T0)
    b = make_qiea()[0].evolve(
        RegimeType.RANGING_TIGHT, zigzag_history(500, regime=RegimeType.RANGING_TIGHT, leg=25),
        seed=5, now=T0,
    )
    assert a is not None and b is not None
    assert a.param_set_id != b.param_set_id


def test_gap0037_rotation_gate_turns_thetas_toward_best_and_clamps() -> None:
    import math
    from core.optimizer.qiea import _THETA_MAX, _THETA_MIN

    thetas = [math.pi / 4, math.pi / 4, _THETA_MAX, _THETA_MIN]
    out = QIEA.rotate_toward(thetas, [1, 0, 1, 0], step=0.05)
    assert out[0] == pytest.approx(math.pi / 4 + 0.05)   # toward P(1)=1
    assert out[1] == pytest.approx(math.pi / 4 - 0.05)   # toward P(1)=0
    assert out[2] == _THETA_MAX and out[3] == _THETA_MIN  # never saturates past clamp


def test_gap0038_all_train_gated_champion_is_never_staged() -> None:
    """Flat train (zero trades => every individual WORST) + tradeable holdout tail:
    the arbitrary first collapse must NOT sneak out via a lucky small holdout."""
    closes = [1.1] * 400 + zigzag_closes(100, base=1.1)
    history = RegimeLabelledHistory("EUR_USD", bars_from_closes(closes, REGIME), bar_seconds=60)
    qiea, log = make_qiea()
    assert qiea.evolve(REGIME, history, seed=42, now=T0) is None
    assert len(log.events("EVOLUTION_REJECTED_TRAIN")) == 1
    assert log.events("EVOLUTION_RUN") == []
