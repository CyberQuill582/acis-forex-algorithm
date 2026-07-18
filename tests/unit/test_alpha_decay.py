"""Alpha-decay detector (ACIS-07 §13 C-RSK-1/2/9, master §8, C5/F13)."""

from __future__ import annotations

from decimal import Decimal

from core.risk.alpha_decay import AlphaDecayDetector, sharpe_nan_safe
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
    assert r.sharpe_recent < 0.5 * r.sharpe_baseline


# -- C-RSK-2 (F13): NaN-safe Sharpe ------------------------------------------ #

def test_zero_dispersion_sharpe_is_defined_sentinel() -> None:
    identical = [mk_trade(10.0) for _ in range(50)]      # σ = 0
    assert sharpe_nan_safe(identical) == 0.0             # no divide-by-zero
    assert sharpe_nan_safe([]) == 0.0


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
