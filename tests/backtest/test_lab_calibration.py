"""B0, machinery proven first (R1.1; ACIS-09 C-BT-11 v2 step 0, GAP-P12D-105): a planted trend is
detected at its theory power and the null at alpha, and the check catches a broken lab and a
broken detector. R1-C §2.8's receipt: 400 paths of 2.8 graded years, null 4.3%, planted 40.3%
against a theory 39.8%."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from tests.backtest.lab_calibration import B0_SEEDS, Calibration, calibrate, ewmac_pool
from tests.backtest.lab_market import Effect, LabSpec
from tests.backtest.lab_theory import (ar_phi, drift_variance_for, ewmac_sharpe, oracle_sharpe,
                                       pooled_ewmac_sharpe, solve_increasing)

SPEC = LabSpec(days=300 + 706)                     # 2.8 graded years after a 300-day burn-in
HALFLIFE, TARGET = 60.0, 0.25                      # the rule's per-instrument theory Sharpe


def _planted() -> tuple[Effect, float]:
    """The trend whose EWMAC 16/64 Sharpe per instrument is TARGET, and the pool's theory Sharpe."""
    other, phi = SPEC.other, ar_phi(HALFLIFE)
    v_m = solve_increasing(lambda v: ewmac_sharpe(v, phi, other, 16, 64), TARGET, 1e-9, 5.0)
    effect = Effect(trend_sharpe=oracle_sharpe(v_m, other), trend_halflife=HALFLIFE)
    assert drift_variance_for(effect.trend_sharpe, other) == pytest.approx(v_m, rel=1e-9)
    return effect, pooled_ewmac_sharpe(v_m, phi, other, SPEC.common, SPEC.n_inst, 16, 64)


def _demeaned(path):
    """GAP-P12D-91's defect re-applied: every instrument's path pinned to a zero sum."""
    return replace(path, y=path.y - path.y.mean(axis=0))


def test_b0_holds_on_the_lab_detection_at_theory_power_and_the_null_at_alpha() -> None:
    effect, theory = _planted()
    assert theory == pytest.approx(0.8555, abs=0.002)                # audit R11I-04; Monte Carlo 0.8569 +- 0.0096
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, B0_SEEDS)
    assert cal.holds, cal.failures()
    assert cal.theory_power == pytest.approx(0.4155, abs=0.002) and cal.n == 2000
    assert abs(cal.implied_sharpe_gap) < 0.05, cal.implied_sharpe_gap      # reported: ~5% resolution at n = 2000


def test_b0_fails_on_a_bridged_lab_its_power_is_lost() -> None:
    """The same machinery on paths demeaned per instrument: R1-C measured the planted power fall
    from 40% to 19%, so the check must refuse."""
    effect, theory = _planted()
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, range(1, 401), distort=_demeaned)
    assert any("planted detection rate" in f for f in cal.failures()), cal


def test_b0_fails_a_detector_that_always_finds_an_edge() -> None:
    effect, theory = _planted()
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, range(1, 41), detector=lambda pnl: True)
    assert any("null false-detect" in f for f in cal.failures()), cal


def test_the_verdict_arithmetic_is_binomial() -> None:
    at_alpha = Calibration(theory_sharpe=0.0, years=2.8, alpha=0.05, n=400, null_hits=20, planted_hits=20)
    assert at_alpha.holds                                             # theory power at SR 0 is alpha
    too_many = Calibration(0.0, 2.8, 0.05, 400, null_hits=40, planted_hits=20)
    assert not too_many.holds and np.isclose(too_many.theory_power, 0.05)
