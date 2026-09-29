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
from tests.backtest.lab_theory import (ar_phi, detection_power, drift_variance_for, ewmac_sharpe,
                                       oracle_sharpe, pooled_ewmac_sharpe, solve_increasing)

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
    from 40% to 19%, so the implied Sharpe reads far outside the ±10% band and B0 refuses."""
    effect, theory = _planted()
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, range(1, 401), distort=_demeaned)
    assert cal.implied_sharpe_gap < -0.3 and any("implied Sharpe" in f for f in cal.failures()), cal


def test_b0_fails_a_detector_that_always_finds_an_edge() -> None:
    effect, theory = _planted()
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, range(1, 41), detector=lambda pnl: True)
    assert any("null false-detect" in f for f in cal.failures()), cal


def test_the_verdict_is_an_equivalence_band_at_the_declared_n() -> None:
    """ACIS-09 v1.9 (D-R11-1): (a) is |implied Sharpe / theory - 1| <= 10% at n >= 2,000; (b) is
    the null's rate within alpha + 2 binomial se."""
    theory, years = 0.8555, 2.8
    at = lambda power: round(detection_power(theory * power, years) * 2000)    # hits at a given Sharpe
    ok = Calibration(theory, years, 0.05, 2000, null_hits=100, planted_hits=at(1.0))
    assert ok.holds and abs(ok.implied_sharpe_gap) < 0.01
    assert Calibration(theory, years, 0.05, 2000, 100, at(1.08)).holds          # inside the band
    assert any("implied Sharpe" in f for f in Calibration(theory, years, 0.05, 2000, 100, at(1.15)).failures())
    assert any("implied Sharpe" in f for f in Calibration(theory, years, 0.05, 2000, 100, at(0.85)).failures())
    assert any("declared B0_N" in f for f in Calibration(theory, years, 0.05, 400, 20, round(0.4155 * 400)).failures())
    assert any("null false-detect" in f for f in Calibration(theory, years, 0.05, 2000, 140, at(1.0)).failures())
    assert not Calibration(0.0, years, 0.05, 2000, 100, 100).holds              # no theory Sharpe: no B0
