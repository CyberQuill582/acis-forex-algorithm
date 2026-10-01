"""Stage A for a fixed family (ACIS-09 C-BT-11 v2 step 3): one alpha-spending bound, three
kill-only refusals, and D1's plateau neighbours as master §5 defines them."""

from __future__ import annotations

import numpy as np

from core.signals import rules
from tests.backtest.stage_a import D1_BASE, d1_neighbours, stage_a

RNG = np.random.default_rng(5)
EDGE = RNG.normal(0.001, 0.005, 3000)           # a clear edge: HAC t ~ 9


def test_d1s_neighbours_are_its_three_parameters_at_plus_and_minus_ten_percent() -> None:
    n = d1_neighbours()
    assert len(n) == 6 and all(len(p) == 3 for p in n.values())
    assert n["speed_scalex0.9"] == {**D1_BASE, "speed_scale": 0.9}
    assert n["ratiox1.1"]["ratio"] == 4.4 and n["vol_daysx0.9"]["vol_days"] == 31.5
    price = list(np.cumprod(1 + RNG.normal(0, 0.006, 900)))
    assert rules.d1(price, **D1_BASE)[-1] == rules.d1(price)[-1]          # the base IS the family


def test_a_clear_edge_passes_and_each_kill_only_condition_refuses_alone() -> None:
    zero = np.zeros_like(EDGE)
    ok = stage_a(EDGE, zero, EDGE, {"m": 1.0}, 0.03)
    assert ok.passed
    assert not stage_a(EDGE, EDGE + 1e-4, EDGE, {"m": 1.0}, 0.03).passed          # loses to its benchmark
    assert not stage_a(EDGE, zero, EDGE - 0.002, {"m": 1.0}, 0.03).passed         # dies at 2x cost
    refused = stage_a(EDGE, zero, EDGE, {"m": 1.0, "D1:ratiox1.1": -1e-6, "MOP12": 0.0}, 0.03)
    assert not refused.passed and refused.refusing == ("D1:ratiox1.1", "MOP12")    # E <= 0 refuses


def test_noise_does_not_clear_the_bound() -> None:
    noise = RNG.normal(0.0, 0.005, 3000)
    a = stage_a(noise - noise.mean(), np.zeros(3000), noise, {}, 0.03)
    assert not a.bound_above_zero and not a.passed
