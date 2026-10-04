"""The tournament's pre-registered promotion rule (TOURNAMENT): milestone D's screen is never evidence alone,
significance is corrected for the tournament's capacity at fixed looks only, stage D's E1 tripwire and E2
kill bind, and on a null tournament the rule's family-wise false-eligibility rate stays under its alpha."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from tests.backtest.forward_record import State
from tests.backtest.tournament_rule import PARAMS, RuleMismatch, evaluate, holm, rule_line, stage_d

SIGMA = 0.01
ALPHA = PARAMS["alpha_total"] / PARAMS["capacity"]


def _exact(n: int, sharpe: float, seed: int, sigma: float = SIGMA) -> np.ndarray:
    """A series whose realised annual Sharpe is exactly `sharpe` and daily sd exactly `sigma`."""
    z = np.random.default_rng(seed).standard_normal(n)
    z = (z - z.mean()) / z.std(ddof=1)
    return sigma * (z + sharpe / math.sqrt(252))


def _state(series: dict[str, np.ndarray], sharpe_dev: float = 0.5) -> State:
    st = State(rule=rule_line())
    for sid, r in series.items():
        st.entries[sid] = {"strategy": sid, "alpha": ALPHA, "sigma_daily": SIGMA, "sharpe_dev": sharpe_dev}
        st.days[sid] = [(date(2026, 10, 5) + timedelta(days=k), float(v)) for k, v in enumerate(r)]
    return st


def _one(series: dict[str, np.ndarray], sid: str, **kw):
    return next(v for v in evaluate(_state(series, **kw), True) if v.strategy == sid)


def test_holm_over_the_capacity_is_bonferroni_at_its_first_step_and_then_steps_down() -> None:
    a = {"a": ALPHA, "b": ALPHA, "c": ALPHA}
    empty = PARAMS["alpha_total"] - 3 * ALPHA
    assert holm({"a": ALPHA * 0.99, "b": 0.02, "c": 0.5}, a, PARAMS["alpha_total"], empty) == {"a"}
    assert holm({"a": ALPHA * 1.01, "b": 0.02, "c": 0.5}, a, PARAMS["alpha_total"], empty) == set()
    full = {k: 0.05 / 3 for k in "abc"}                                     # a full family of three: plain Holm
    assert holm({"a": 0.016, "b": 0.024, "c": 0.049}, full, 0.05, 0.0) == {"a", "b", "c"}
    assert holm({"a": 0.017, "b": 0.001, "c": 0.049}, full, 0.05, 0.0) == {"a", "b", "c"}  # 0.017 <= 0.05/2
    assert holm({"a": 0.024, "b": 0.06, "c": 0.001}, full, 0.05, 0.0) == {"a", "c"}     # c, then a at 0.05/2


def test_milestone_d_alone_is_a_screen_never_eligibility_and_its_luck_is_reported() -> None:
    v = _one({"w": _exact(130, 0.8, 1)}, "w")
    assert v.screen_d and not v.eligible and not v.holm_rejected
    assert v.luck_one == pytest.approx(1 - 0.5 * (1 + math.erf(0.8 * math.sqrt(130 / 252) / math.sqrt(2))))
    assert "not significant after the correction for the capacity" in v.reasons
    short = _one({"s": _exact(100, 3.0, 2)}, "s")
    assert not short.screen_d and not short.eligible and short.p_looks == ()


def test_a_strong_forward_edge_is_eligible_only_at_a_look_and_with_an_intact_record() -> None:
    v = _one({"s": _exact(260, 4.0, 3)}, "s")
    assert [n for n, _ in v.p_looks] == [126, 252]                          # 260 days: the 504 look is not done
    assert v.holm_rejected and v.screen_d and v.eligible
    bad = next(x for x in evaluate(_state({"s": _exact(260, 4.0, 3)}), {"s": False}))
    assert not bad.eligible and "the record failed its integrity or recompute check" in bad.reasons


def test_peeking_between_looks_earns_nothing() -> None:
    r = _exact(251, 4.0, 4)
    assert [n for n, _ in _one({"s": r}, "s").p_looks] == [126]
    assert _one({"s": r}, "s").p_star == _one({"s": r[:126]}, "s").p_star


def test_the_correction_counts_the_capacity_not_the_entries_registered() -> None:
    r = _exact(252, 2.9, 5)
    alone = _one({"s": r}, "s")
    crowd = _one({"s": r, **{f"n{k}": _exact(252, 0.0, 10 + k) for k in range(6)}}, "s")
    assert alone.p_star == crowd.p_star and alone.holm_rejected == crowd.holm_rejected
    assert crowd.luck_any > alone.luck_any                                  # the luck of the best of N does grow


def test_a_tripwire_day_voids_e1_and_a_record_far_below_its_claim_is_killed_by_e2() -> None:
    r = _exact(300, 4.0, 6)
    r[150] = -6.5 * SIGMA
    v = _one({"s": r}, "s")
    assert v.e1_voided and v.e1 == 0.0 and not v.eligible and not v.screen_d
    e1, voided, e2, e2max = stage_d(_exact(400, -2.0, 7), SIGMA, 2.0, PARAMS)
    assert not voided and e2max >= PARAMS["e_kill"] and e1 < 1.0
    k = _one({"k": _exact(400, -2.0, 7)}, "k", sharpe_dev=2.0)
    assert k.killed and not k.screen_d


def test_a_record_registered_under_another_rule_is_refused() -> None:
    st = _state({"s": _exact(10, 0.0, 8)})
    st.rule = {**st.rule, "params": {**PARAMS, "min_sharpe": 0.2}}
    with pytest.raises(RuleMismatch):
        evaluate(st, True)


def test_on_null_tournaments_the_family_wise_false_eligibility_stays_under_alpha() -> None:
    rng, trials, hits, screens, singles = np.random.default_rng(2026), 200, 0, 0, 0
    for _ in range(trials):
        series = {f"s{k}": SIGMA * rng.standard_normal(504) for k in range(PARAMS["capacity"])}
        verdicts = evaluate(_state(series), True)
        hits += any(v.eligible for v in verdicts)
        screens += any(v.screen_d for v in verdicts)
        singles += sum(v.screen_d for v in evaluate(_state({k: s[:126] for k, s in series.items()}), True))
    assert hits / trials <= PARAMS["alpha_total"] + 3 * math.sqrt(0.05 * 0.95 / trials)
    assert screens / trials > 0.9                                           # the screen alone fires on noise
    assert 0.30 < singles / (trials * PARAMS["capacity"]) < 0.42            # about a third at 126 days
