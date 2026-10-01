"""Stage A's HAC detector is calibrated on the lab (GAP-P12D-121), and RSIM books the lab's
theory premise exactly: B0's machinery holds through the simulator that grades the families."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from core.optimizer.costs import CostModel
from tests.backtest.hac import hac_detector, hac_t, nw_lags
from tests.backtest.lab_calibration import B0_SEEDS, calibrate, ewmac_pool, one_sided_t
from tests.backtest.lab_market import Effect, LabSpec, generate
from tests.backtest.rsim import BookSpec, Lots, run
from tests.backtest.rsim_lab import lab_market
from tests.backtest.test_lab_calibration import SPEC, _planted


def test_newey_west_lag_rule_and_iid_agreement() -> None:
    assert nw_lags(100) == 4 and nw_lags(3000) == 8
    x = np.random.default_rng(1).normal(0.1, 1.0, 5000)
    plain = x.mean() / x.std(ddof=0) * np.sqrt(x.size)
    assert hac_t(x, lags=0) == pytest.approx(plain, rel=1e-12)
    assert hac_t(x) == pytest.approx(plain, rel=0.1)                     # iid: lags change little


def test_hac_keeps_its_size_on_an_autocorrelated_null() -> None:
    rng, n, sims, phi = np.random.default_rng(7), 1000, 3000, 0.10
    plain, hac = one_sided_t(0.05), hac_detector(0.05)
    hits_plain = hits_hac = 0
    for _ in range(sims):
        e = rng.normal(size=n)
        x = np.empty(n)
        x[0] = e[0]
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        hits_plain += plain(x)
        hits_hac += hac(x)
    se = np.sqrt(0.05 * 0.95 / sims)
    assert hits_plain / sims > 0.05 + 2 * se                             # Lo (2002): the iid test is loose
    assert abs(hits_hac / sims - 0.05) < 2.5 * se                        # HAC holds its size


def test_b0_holds_with_the_hac_detector() -> None:
    """GAP-P12D-121 / lab_calibration: stage A's detector is calibrated through B0 before it binds."""
    effect, theory = _planted()
    cal = calibrate(ewmac_pool(), SPEC, effect, theory, B0_SEEDS, detector=hac_detector(0.05))
    assert cal.holds, cal.failures()


def _pool_forecast(path, fast=16, slow=64) -> np.ndarray:
    """ewmac_pool's own sign decision as a forecast panel: the sign at t from y up to t."""
    a_f, a_s = 2 / (fast + 1), 2 / (slow + 1)
    cum = np.cumsum(path.y, axis=0)
    ef, es, out = np.zeros(path.y.shape[1]), np.zeros(path.y.shape[1]), np.empty(path.y.shape)
    for t in range(len(cum)):
        ef += a_f * (cum[t] - ef)
        es += a_s * (cum[t] - es)
        out[t] = 10.0 * np.sign(ef - es)
    return out


def test_rsim_books_the_labs_theory_premise_exactly() -> None:
    """Sized by the true sigma, with no cost, no buffer and fine lots, RSIM's daily return is the
    lab pool's P&L times vol_target/16, day for day: price, financing and timing all exact."""
    path = generate(LabSpec(n_inst=5, days=700, seed=3, effect=Effect(trend_sharpe=1.0)))
    m = lab_market(path)
    m = replace(m, spread=np.zeros_like(m.spread))
    sigma_next = np.vstack([path.sigma[1:], np.full((1, path.sigma.shape[1]), np.nan)])
    spec = BookSpec(costs={n: CostModel(0.0, 0.0) for n in m.names}, capital=1e6, vol_target=0.16,
                    buffer=0.0, lots={n: Lots(1e-6, 1e-6) for n in m.names})
    res = run(m, _pool_forecast(path), sigma_next, spec)
    pool = ewmac_pool()(path)
    assert res.daily[1:] == pytest.approx(0.01 * pool[1:], rel=1e-6, abs=1e-12)
