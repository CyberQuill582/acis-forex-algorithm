"""The register-aware stage-A verdict (ACIS-09 C-BT-11 v2 steps 2-3; GAP-P12D-111, GAP-P12D-100):
serial gatekeeping over a registered cycle, each look at alpha/k, Holm outside the chain, fail closed."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from tests.backtest.look_claims import store_vector
from tests.backtest.look_declarations import Declaration
from tests.backtest.look_register import LookRefused
from tests.backtest.test_look_claims import _claim, _look, canonical  # noqa: F401 (fixture)
from tests.backtest.verdict import VerdictRefused, cycle_verdict

RNG = np.random.default_rng(7)
NOISE = RNG.normal(0.0, 0.01, 2500)
NULL = NOISE - NOISE.mean()                      # HAC t = 0: p = 0.5
EDGE = NULL + 0.002                              # HAC t ~ 10: p ~ 0
WHEN = datetime.now(timezone.utc) - timedelta(days=1)


def _variant(name: str, kind: str = "fixed", k: int = 1):
    boot = (20, 1) if kind == "explored" else (None, None)
    return _claim(variant=name, simulator="rsim", declaration=Declaration(kind, k, "PASSIVE_LONG", *boot))


def _graded(reg, cfg, claim, daily, *, benchmark=None, cost2x=None, kill=None):
    look = _look(reg, cfg, claim=claim, changed=f"grade variant {claim.variant}")
    reg.consume(look)
    dates = [date(2014, 1, 1) + timedelta(days=i) for i in range(len(daily))]
    vec = lambda v: store_vector(reg.root, dates, [float(x) for x in v])            # noqa: E731
    arms = {"benchmark": "PASSIVE_LONG",
            "benchmark_vector": vec(np.zeros(len(daily)) if benchmark is None else benchmark),
            "cost2x_vector": vec(daily if cost2x is None else cost2x),
            "kill_only_vectors": {n: vec(v) for n, v in (kill or {}).items()}}
    reg.record_outcome(look, {"stage_a": arms}, daily=(dates, [float(x) for x in daily]))
    return look


def _cycle(reg, chain, holm=()):
    reg.register_cycle(cycle_id="c1", order=[c.variant_hash for c in chain], holm=[c.variant_hash for c in holm],
                       now_fn=lambda: WHEN)


def test_the_chain_passes_in_order_and_stops_at_the_first_member_that_has_not_passed(canonical, acis_config) -> None:
    a, b, c = (_variant(n) for n in ("a", "b", "c"))
    _cycle(canonical, [a, b, c])
    _graded(canonical, acis_config, a, EDGE)
    _graded(canonical, acis_config, b, NULL)
    _graded(canonical, acis_config, c, EDGE)                    # an edge, but behind a failure
    v = cycle_verdict(canonical.root, "c1")
    assert v.alpha == 0.03 and [m.status for m in v.chain] == ["passed", "failed", "untested"]
    assert v.passed == (a.variant_hash,) and v.chain[1].p == 1.0      # a zero mean has no paired excess


def test_each_look_is_tested_at_alpha_over_k(canonical, acis_config) -> None:
    weak = NULL + 0.00045                                       # HAC p ~ 0.016
    a, b = _variant("a", k=1), _variant("b", k=3)
    _cycle(canonical, [a, b])
    _graded(canonical, acis_config, a, weak)
    _graded(canonical, acis_config, b, weak)
    v = cycle_verdict(canonical.root, "c1")
    assert 0.01 < v.chain[0].p < 0.03 and v.chain[0].status == "passed"
    assert v.chain[1].p == pytest.approx(3 * v.chain[0].p) and v.chain[1].status == "open"   # 3p > 0.03, 2 looks left


@pytest.mark.parametrize("bad", [{"benchmark": EDGE + 1e-4}, {"cost2x": EDGE - 0.003},
                                 {"kill": {"D1:ratiox1.1": NULL - 1e-6}}])
def test_a_kill_only_failure_refuses_an_edge(canonical, acis_config, bad) -> None:
    a = _variant("a")
    _cycle(canonical, [a])
    _graded(canonical, acis_config, a, EDGE, **bad)
    m = cycle_verdict(canonical.root, "c1").chain[0]
    assert m.status == "failed" and m.p == 1.0


def test_the_holm_set_is_tested_only_after_the_whole_chain_passed(canonical, acis_config) -> None:
    a, h1, h2, h3 = _variant("a", k=2), _variant("h1"), _variant("h2"), _variant("h3")
    _cycle(canonical, [a], holm=[h1, h2])
    _graded(canonical, acis_config, h1, NULL + 0.00043)        # HAC p ~ 0.021 and ~ 0.026: each < 0.03 alone,
    _graded(canonical, acis_config, h2, NULL + 0.00041)        # but the smaller is not < 0.03 / 2
    first = cycle_verdict(canonical.root, "c1")
    assert first.chain[0].status == "open" and [m.status for m in first.holm] == ["untested", "untested"]
    _graded(canonical, acis_config, a, EDGE)
    v = cycle_verdict(canonical.root, "c1")
    assert v.chain[0].status == "passed"
    ps = [m.p for m in v.holm]
    assert all(0.015 < x < 0.03 for x in ps), ps                # the precondition the Holm step needs
    assert [m.status for m in v.holm] == ["failed", "failed"]   # Holm stops at 0.015; each alone would pass


def test_holm_passes_the_strong_member_first_and_then_tests_the_next_at_the_full_alpha(canonical, acis_config) -> None:
    a, h1, h2 = _variant("a"), _variant("h1"), _variant("h2")
    _cycle(canonical, [a], holm=[h1, h2])
    _graded(canonical, acis_config, a, EDGE)
    _graded(canonical, acis_config, h1, EDGE)
    _graded(canonical, acis_config, h2, NULL + 0.00041)        # HAC p ~ 0.026 < 0.03 / 1
    v = cycle_verdict(canonical.root, "c1")
    assert [m.status for m in v.holm] == ["passed", "passed"] and len(v.passed) == 3


def test_an_explored_member_a_pending_look_and_a_broken_register_fail_closed(canonical, acis_config) -> None:
    e, p = _variant("e", kind="explored"), _variant("p")
    _cycle(canonical, [p, e])
    look = _look(canonical, acis_config, claim=p, changed="p")  # registered, never graded
    v = cycle_verdict(canonical.root, "c1")
    assert [m.status for m in v.chain] == ["pending", "untested"]
    with pytest.raises(VerdictRefused, match="no cycle"):
        cycle_verdict(canonical.root, "c2")
    (canonical.root / "000001.json").write_bytes(b"{}")         # an edited line breaks the chain
    with pytest.raises(VerdictRefused, match="broken or torn"):
        cycle_verdict(canonical.root, "c1")
    assert look.look_id


def test_a_stacked_instrument_day_panel_cannot_be_stored_as_the_graded_vector(canonical) -> None:
    """GAP-P12D-100: the graded unit is the portfolio daily series; a panel repeats dates."""
    days = [date(2014, 1, 1) + timedelta(days=i) for i in range(3)]
    with pytest.raises(ValueError, match="strictly increasing"):
        store_vector(canonical.root, days + days, [0.0] * 6)


def test_a_stage_a_look_names_its_cycle_and_counts_only_there(canonical, acis_config) -> None:
    """R12I-04 (GAP-P12D-127): a stage-A look outside any cycle is refused; its line names the latest
    cycle that lists its variant and its look index; a cycle's verdict reads only its own looks."""
    a, b, c = _variant("a"), _variant("b", k=2), _variant("c")
    with pytest.raises(LookRefused, match="belongs to a registered cycle"):
        _look(canonical, acis_config, claim=a, changed="no cycle yet")
    canonical.register_cycle(cycle_id="c1", order=[a.variant_hash, b.variant_hash, c.variant_hash],
                             now_fn=lambda: datetime.now(timezone.utc) - timedelta(days=100))   # an earlier quarter
    _graded(canonical, acis_config, a, NULL)                    # c1 stops at a: b and c untested
    canonical.register_cycle(cycle_id="c2", order=[b.variant_hash], now_fn=lambda: datetime.now(timezone.utc))
    look = _graded(canonical, acis_config, b, EDGE)
    assert look.cycle == {"cycle_id": "c2", "look_index": 1}
    assert _graded(canonical, acis_config, b, EDGE).cycle == {"cycle_id": "c2", "look_index": 2}
    c1, c2 = cycle_verdict(canonical.root, "c1"), cycle_verdict(canonical.root, "c2")
    assert [m.status for m in c1.chain] == ["failed", "untested", "untested"]
    assert c2.chain[0].status == "passed" and c2.alpha == 0.01 and len(c2.chain[0].looks) == 2


def test_only_days_after_the_certifying_boundary_count_toward_a_pass(canonical, acis_config) -> None:
    """Master §5.6: a literature rule published inside the window passes only on its later days. An edge
    planted before publication and none after earns nothing; the same edge after publication passes."""
    from tests.backtest.look_claims import Origin
    paper = Origin("literature", reference="a 2014 paper", published="2014-07-01")
    days = (date(2015, 7, 1) - date(2014, 1, 1)).days + 1                    # through mid-2015
    cut = (date(2014, 7, 1) - date(2014, 1, 1)).days
    before = np.concatenate([EDGE[:cut], NULL[:days - cut] + 0.00003])      # paired excess and 2x still > 0
    after = np.concatenate([NULL[:cut] + 0.00003, EDGE[:days - cut]])
    a = _claim(variant="early", simulator="rsim", origin=paper, declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
    b = _claim(variant="late", simulator="rsim", origin=paper, declaration=Declaration("fixed", 1, "PASSIVE_LONG"))
    _cycle(canonical, [b], holm=[a])
    _graded(canonical, acis_config, b, after)
    _graded(canonical, acis_config, a, before)
    v = cycle_verdict(canonical.root, "c1")
    assert v.chain[0].status == "passed" and v.holm[0].status == "failed" and v.holm[0].p > 0.4


def test_a_kill_only_look_names_no_cycle_and_is_killed_only_below_minus_half(canonical, acis_config) -> None:
    """Owner rulings 2026-10-03: an LLM-selected rule's history look can only falsify; it spends no alpha
    (no cycle) and is killed at HAC t < -0.5 (stage C's rule), never passed."""
    from tests.backtest.look_claims import Origin
    from tests.backtest.verdict import KILL_T, kill_verdict
    picked = Origin("literature", model_id="claude-opus-5", model_cutoff="2026-01-01", proposed="2026-09-24",
                    exposure="web", reference="Carver 2015", published="2015-10-01")
    looks = {}
    for name, series in (("noisy", NULL - 0.00005), ("bad", NULL - 0.0004), ("good", EDGE)):
        claim = _claim(variant=name, simulator="rsim", origin=picked)
        looks[name] = _graded(canonical, acis_config, claim, series)
        assert looks[name].cycle is None
    verdicts = {n: kill_verdict(canonical.root, look.look_id) for n, look in looks.items()}
    assert KILL_T == -0.5 and verdicts["noisy"].hac_t < 0 and not verdicts["noisy"].killed
    assert verdicts["bad"].killed and not verdicts["good"].killed
