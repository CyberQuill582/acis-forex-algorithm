"""Alpha-decay detector (ACIS-07 §13 C-RSK-1/2/9, master §8, C5/F13)."""

from __future__ import annotations

from decimal import Decimal

from core.risk.alpha_decay import AlphaDecayDetector, mean_sigma
from tests.risk_fixtures import load_cfg, mk_alpha, mk_trade


def _detector():
    return mk_alpha(load_cfg().system.risk)


# baseline strong (mean 10, σ 2 → Sharpe ~5), recent weak (mean 0, σ 1 → ~0)
def _strong_baseline(n: int):
    return [mk_trade(12.0 if i % 2 else 8.0) for i in range(n)]


def _weak_recent(n: int):
    return [mk_trade(1.0 if i % 2 else -1.0) for i in range(n)]


# -- C-RSK-1 (C5): baseline validity ----------------------------------------- #

def test_forty_baseline_trades_never_flags() -> None:
    # 90 trades ⇒ baseline window holds only 40 < 50 ⇒ inactive_warming.
    trades = _strong_baseline(40) + _weak_recent(50)
    r = _detector().evaluate(trades)
    assert r.state == "inactive_warming" and r.flag is False
    assert r.n_baseline == 40


def test_sixty_baseline_trades_can_flag() -> None:
    # 110 trades ⇒ baseline holds 60 ⇒ the comparison is live and flags.
    trades = _strong_baseline(60) + _weak_recent(50)
    r = _detector().evaluate(trades)
    assert r.state == "flagged" and r.flag is True
    assert r.mean_sigma_recent < 0.5 * r.mean_sigma_baseline


# -- C-RSK-2 (F13): NaN-safe mean/σ ------------------------------------------ #

def test_zero_dispersion_mean_sigma_is_defined_sentinel() -> None:
    identical = [mk_trade(10.0) for _ in range(50)]      # σ = 0
    assert mean_sigma(identical) == 0.0                  # no divide-by-zero
    assert mean_sigma([]) == 0.0


# -- GAP-P9I-01: a negative baseline must not flag a RECOVERING strategy ------ #

def test_negative_baseline_does_not_flag_improving_recent() -> None:
    # baseline mean/σ < 0 (no positive edge to decay from); recent IMPROVED but
    # still negative. `s_recent < 0.5·s_baseline` would invert and wrongly flag;
    # the fix requires s_baseline > 0, so a strategy with no edge never "decays".
    baseline = [mk_trade(-12.0 if i % 2 else -8.0) for i in range(60)]   # ≈ -1.0
    recent = [mk_trade(-7.0 if i % 2 else -5.0) for i in range(50)]      # ≈ -0.6, better
    r = _detector().evaluate(baseline + recent)
    assert r.mean_sigma_baseline < 0
    assert r.flag is False and r.state == "active"


def test_flat_baseline_never_spuriously_flags() -> None:
    # σ≈0 baseline (sentinel 0.0) ⇒ threshold 0.5×0 = 0; a losing recent still
    # only flags if s_recent < 0, never a divide-by-near-zero blow-up.
    trades = [mk_trade(10.0) for _ in range(150)] + [mk_trade(5.0) for _ in range(50)]
    r = _detector().evaluate(trades)
    assert r.state in ("active", "flagged")              # defined, no exception


# -- C-RSK-9 / GAP-0050: armed state semantics ------------------------------- #

def test_armed_throttle_survives_warming_restart() -> None:
    det = _detector()
    det.restore_armed(True)                              # persisted throttle restored
    # warming history (too few trades) must NOT clear a restored throttle
    r = det.evaluate(_weak_recent(10))
    assert r.state == "inactive_warming" and r.flag is True   # still armed


def test_armed_clears_only_on_confirmed_recovery() -> None:
    det = _detector()
    # arm it
    armed = _strong_baseline(60) + _weak_recent(50)
    assert det.evaluate(armed).flag is True
    # a still-weak recent does NOT clear
    assert det.evaluate(armed).flag is True
    # a confirmed recovery: last 20 trades strongly positive (high Sharpe) on
    # a moderate baseline ⇒ clears.
    recovered = _strong_baseline(100) + [mk_trade(20.0 if i % 2 else 18.0)
                                         for i in range(50)]
    r = det.evaluate(recovered)
    assert r.flag is False and r.state == "active"


# -- GAP-P12D-145: the human clear and the fresh-evidence window (PR16I-01/02, PR16I-08) ------- #

def _armed_detector():
    det = _detector()
    trades = _strong_baseline(150) + _weak_recent(50)
    r = det.evaluate(trades)
    assert r.flag and det.baseline == r.mean_sigma_baseline
    return det, trades, r.mean_sigma_baseline


def test_the_fresh_window_judges_against_the_baseline_that_armed_it() -> None:
    """PR16I-02: trades that close while armed (positions winding down) do not move the yardstick."""
    det, trades, arming = _armed_detector()
    trades += _weak_recent(60)                                # closes while armed: the window would shift
    det.evaluate(trades)
    det.clear_by_human(len(trades))
    trades += _weak_recent(29)
    assert not det.evaluate(trades).flag                      # 29 fresh trades: still too few
    trades += _weak_recent(1)
    r = det.evaluate(trades)
    assert r.flag and r.mean_sigma_baseline == arming and r.n_recent == 30


def test_after_the_window_only_post_resume_trades_count() -> None:
    """PR16I-02's second case: once the post-resume trades form their own baseline the standard rule
    runs on them alone, so the decayed trades before the resume never become the baseline."""
    det = _detector()
    trades = _strong_baseline(150) + [mk_trade(-30.0 if i % 2 else -28.0) for i in range(50)]
    assert det.evaluate(trades).flag
    det.clear_by_human(len(trades))
    trades += _strong_baseline(100)                           # healthy: no re-arm inside the window
    assert not det.evaluate(trades).flag and det.baseline is None    # the window has closed
    trades += _weak_recent(50)
    r = det.evaluate(trades)
    assert r.flag and r.n_baseline == 100 and r.mean_sigma_baseline > 0    # the 100 post-resume trades only
    # with the pre-resume losses in its baseline (mean below zero) the rule could never have fired


def test_a_restart_and_its_resume_keep_the_fresh_window() -> None:
    """PR16I-01: the arming baseline is persisted with `armed`, so a restarted process (empty trade
    history) still re-arms on 30 decayed post-resume trades; an open window survives a restart too."""
    _, _, arming = _armed_detector()
    det = _detector()
    det.restore_armed(True, arming)
    assert det.armed and det.baseline == arming
    det.clear_by_human(0)
    assert det.baseline == arming                             # the window is open: still persisted
    assert det.evaluate(_weak_recent(30)).flag
    reopened = _detector()
    reopened.restore_armed(False, arming)                     # a restart inside an open window
    assert not reopened.armed and reopened.evaluate(_weak_recent(30)).flag
    unknown = _detector()
    unknown.restore_armed(True, None)                         # a store from before the baseline was kept
    unknown.clear_by_human(0)
    assert not unknown.evaluate(_weak_recent(99)).flag        # never flags on a guessed baseline
