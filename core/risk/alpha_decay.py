"""Alpha-decay detection (ACIS-07 §7, master §8, C5/F13).

Rolling Sharpe(recent) < threshold × Sharpe(baseline) ⇒ decay. The corrected
version makes "not enough data" a first-class state (`inactive_warming`) so a
short trade history never reads as "healthy" (C5), and the Sharpe is NaN-safe
(σ≈0 ⇒ a defined sentinel, never a divide-by-near-zero spurious flag, F13).

The GAP-0050 clear contract lives here as pure state: a fired throttle clears
ONLY after a confirmed recovery (`recovery_trades` closed trades whose rolling
Sharpe exceeds `recovery_mult` × baseline). The Risk Monitor turns a state
transition into the explicit `apply_risk_state(alpha_decay=…)` call — this
module never talks to the Governor.

GAP-P12D-145 ("fresh evidence only", owner ruling 2026-10-03): the one human resume disarms it
(`clear_by_human`), and trades closed before the resume never count again. Until the post-resume
trades form a full baseline of their own (recent_window + baseline_min_trades of them), their
recent window is judged against the FROZEN baseline that armed the throttle (PR16I-02); after
that the standard rule runs on post-resume trades only. Entries are zeroed while armed, so without
this the trades that armed it would re-arm it at once and lock the book out. The arming baseline
and an open window are persisted with `armed` (`baseline`), so a restart and its `--resume` keep
the rule though the trade history starts empty (PR16I-01).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, stdev

from core.risk.risk_types import Trade

# σ below this (in return-fraction terms) is treated as "no dispersion": the
# ratio is undefined, so we return a defined sentinel instead of dividing.
_SIGMA_FLOOR = 1e-12


def mean_sigma(trades: list[Trade]) -> float:
    """Mean/σ of per-trade returns — a SAMPLE-σ transform, NOT an annualised,
    risk-free-adjusted Sharpe ratio (GAP-P9E-05: it may not wear the canonical
    'Sharpe' name — the GAP-0091 naming law, §16). SAMPLE σ (`stdev`, not
    `pstdev`) so the ratio has no window-size bias when comparing the recent
    window to the differently-sized baseline (GAP-P9E-06). σ≈0 ⇒ 0.0 (no
    dispersion = no measurable edge), never a divide-by-near-zero blow-up
    (C-RSK-2/F13). Fewer than 2 trades or an empty window ⇒ 0.0.

    Used only as a RATIO (recent vs baseline) where the missing annualisation
    and risk-free rate cancel — the throttle logic is sound; the name is honest."""
    if len(trades) < 2:
        return 0.0
    rets = [_ret(t) for t in trades]
    mu = fmean(rets)
    sigma = stdev(rets)
    if sigma < _SIGMA_FLOOR or not math.isfinite(sigma):
        return 0.0
    s = mu / sigma
    return s if math.isfinite(s) else 0.0


def _ret(t: Trade) -> float:
    """Per-trade return as a fraction of notional at risk (entry_price × units).
    Sign follows realised PnL; the denominator is always positive."""
    notional = abs(float(t.units) * t.entry_price)
    if notional <= 0:
        return 0.0
    return float(t.pnl) / notional


@dataclass(frozen=True)
class AlphaDecayReading:
    state: str                 # inactive_warming | active | flagged
    flag: bool
    mean_sigma_recent: float   # per-trade mean/σ, NOT an annualised Sharpe (P9E-05)
    mean_sigma_baseline: float
    n_recent: int
    n_baseline: int


class AlphaDecayDetector:
    """Pure, stateful only in that it remembers whether a throttle is armed —
    which the GAP-0050 clear contract requires (a taper-only update must never
    clear it; a restart restores it). Feed it the full closed-trade history."""

    def __init__(self, *, recent_window: int, min_trades: int,
                 baseline_min_trades: int, sharpe_mult: float,
                 recovery_trades: int, recovery_mult: float) -> None:
        self._recent_window = recent_window
        self._min_trades = min_trades
        self._baseline_min = baseline_min_trades
        self._mult = sharpe_mult
        self._recovery_trades = recovery_trades
        self._recovery_mult = recovery_mult
        self._armed = False           # persisted restrictive state (GAP-0050)
        self._origin = 0              # trades before the last human clear never count again
        self._fresh = False           # a human clear's fresh-evidence window is open
        self._arming_baseline: float | None = None   # mean/sigma of the baseline that armed it

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def baseline(self) -> float | None:
        """What a restart keeps beside `armed`: the arming baseline while armed or while a fresh
        window is open, else None."""
        return self._arming_baseline if (self._armed or self._fresh) else None

    def restore_armed(self, armed: bool, baseline: float | None = None) -> None:
        """Restart reconciliation, BEFORE the first evaluate: a persisted throttle is restored (a
        restart is never a relaxation, GAP-0050); a persisted baseline while not armed reopens the
        fresh-evidence window on the new process's (empty) history."""
        self._armed = bool(armed)
        self._arming_baseline = baseline
        self._fresh = not self._armed and baseline is not None
        self._origin = 0

    def clear_by_human(self, n_trades: int) -> None:
        """Disarm; the first `n_trades` closed trades never count again, and the fresh window opens."""
        self._armed, self._fresh, self._origin = False, True, n_trades

    def evaluate(self, trades: list[Trade]) -> AlphaDecayReading:
        hist = trades[self._origin:]
        if self._fresh and len(hist) < self._recent_window + self._baseline_min:
            return self._fresh_window(hist)
        self._fresh = False
        recent = hist[-self._recent_window:]
        baseline = hist[-200:-self._recent_window]
        n_recent, n_baseline = len(recent), len(baseline)

        if n_recent < self._min_trades or n_baseline < self._baseline_min:
            # Insufficient data: never FLAG, but an armed throttle stays armed —
            # warming after a restart does not clear a real decay (GAP-0050).
            return AlphaDecayReading("inactive_warming", self._armed,
                                     mean_sigma(recent),
                                     mean_sigma(baseline), n_recent, n_baseline)

        s_recent = mean_sigma(recent)
        s_baseline = mean_sigma(baseline)

        if not self._armed:
            # GAP-P9I-01: `s_recent < mult·s_baseline` INVERTS when the baseline
            # is ≤ 0 (a strategy with no positive edge to decay from) — an
            # IMPROVING recent (−0.6 > −1.0) would wrongly flag. Decay is only
            # meaningful as erosion of a positive edge, so require s_baseline > 0.
            flag = s_baseline > 0.0 and s_recent < self._mult * s_baseline
            if flag:
                self._armed, self._arming_baseline = True, s_baseline
                return AlphaDecayReading("flagged", True, s_recent, s_baseline,
                                         n_recent, n_baseline)
            return AlphaDecayReading("active", False, s_recent, s_baseline,
                                     n_recent, n_baseline)

        # Armed: clear ONLY on confirmed recovery (GAP-0050) — the last
        # `recovery_trades` closed trades' mean/σ must exceed recovery_mult ×
        # baseline. Otherwise the throttle stays armed.
        recovery = hist[-self._recovery_trades:]
        recovered = (len(recovery) >= self._recovery_trades
                     and mean_sigma(recovery) > self._recovery_mult * s_baseline)
        if recovered:
            self._armed, self._arming_baseline = False, None
            return AlphaDecayReading("active", False, s_recent, s_baseline,
                                     n_recent, n_baseline)
        return AlphaDecayReading("flagged", True, s_recent, s_baseline,
                                 n_recent, n_baseline)

    def _fresh_window(self, hist: list[Trade]) -> AlphaDecayReading:
        """Post-resume trades against the frozen arming baseline (GAP-P12D-145, PR16I-02)."""
        recent, base = hist[-self._recent_window:], self._arming_baseline
        s_recent, n = mean_sigma(recent), len(recent)
        if self._armed:                           # re-armed inside the window: GAP-0050's recovery rule
            recovery = hist[-self._recovery_trades:]
            if len(recovery) >= self._recovery_trades and mean_sigma(recovery) > self._recovery_mult * base:
                self._armed = False
                return AlphaDecayReading("active", False, s_recent, base, n, 0)
            return AlphaDecayReading("flagged", True, s_recent, base, n, 0)
        if n < self._min_trades or base is None:  # no arming baseline known: never flag on a guess
            return AlphaDecayReading("inactive_warming", False, s_recent, base or 0.0, n, 0)
        if base > 0.0 and s_recent < self._mult * base:
            self._armed = True
            return AlphaDecayReading("flagged", True, s_recent, base, n, 0)
        return AlphaDecayReading("active", False, s_recent, base, n, 0)
