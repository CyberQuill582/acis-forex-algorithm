"""The daily-first synthetic lab (R1.1 C-3; ACIS-09 C-BT-12): N correlated instruments, one bar per
weekday, with effects of KNOWN Sharpe planted on demand. It grades MACHINERY, never edge: no real
data is read, fitted or resampled here (C-10, pinned by test_lab_hygiene). The design is R1-C's
(CLOUD_AUDIT/reports/r1/R1C_SYNTH_LAB.md §2.4, prototype evidence/R1C/gen_lab.py).

Mental model (every invariant the lab promises):
  * VOLATILITY UNITS. y = scale·(m + e + J + G): planted drift m, a conditionally Gaussian
    diffusive part e with one common factor, compound-Poisson jumps J, a Monday gap G. The day's
    SIMPLE excess return is r = sigma·y; a long financed on the harness's own rollover calendar
    (carry.swap_multiplier, /365) earns exactly r, so a financing-on null is null in the P&L the
    grader books (C-6), before the broker fee, which is friction.
  * NOTHING IS DEMEANED (except xsmom's per-day cross-section, which is the effect itself).
    The null (m = 0) has E[r_t | the past] = 0: sigma is known at the day's start and y is a
    zero-mean shock, so every non-anticipating rule earns nothing in expectation.
  * PRICES COMPOUND SIMPLE RETURNS: mid_t = mid_(t-1)·(1 + spot_t), spot = r - accrual. A
    long-biased rule earns nothing in PRICE units on the null (exp-built prices would pay it
    sigma²/2 a day). A simple return <= -1 is refused, never floored.
  * PLANTED DIFFERS FROM NULL IN DRIFT ONLY. The same seed gives the same noise (effects draw
    from a second generator), and `scale` makes planted's MODEL variance of y over the decision
    horizon (one weekday) equal the null's exactly: scale² · (Var m + other) = other.
  * PERMUTED shuffles whole days (every instrument together, so the cross-section is kept) and
    flips each day's sign: given the pool, r is a martingale difference in price units.
  * sigma = GARCH(1,1) feedback x an exogenous multi-scale log-volatility (AR(1) components with
    log-spaced half-lives; E[factor²] = 1 keeps the unconditional variance). GARCH(1,1) alone
    decays exponentially and fails Cont's power-law fact (R1-C §2.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from tests.backtest.carry import swap_multiplier
from tests.backtest.lab_theory import (YEAR, ar_phi, carry_kappa_for, drift_variance_for,
                                       season_size_for)


@dataclass(frozen=True)
class Effect:
    """What is planted, each as the annual Sharpe of its oracle per instrument (0 = absent)."""
    trend_sharpe: float = 0.0          # the oracle holding sign(m_t) over day t
    trend_halflife: float = 40.0       # weekdays: the latent drift's persistence (speed)
    trend_scope: str = "idio"          # "idio": one drift per instrument; "factor": one shared
    carry_sharpe: float = 0.0          # the rule sign(rate differential)
    xsmom_sharpe: float = 0.0          # the cross-sectional oracle
    xsmom_halflife: float = 60.0
    season_sharpe: float = 0.0         # the turn-of-month rule

    def __post_init__(self) -> None:
        if self.trend_scope not in ("idio", "factor"):
            raise ValueError("trend_scope must be 'idio' or 'factor'")
        if min(self.trend_sharpe, self.carry_sharpe, self.xsmom_sharpe, self.season_sharpe) < 0:
            raise ValueError("an effect's Sharpe is a strength: >= 0")


@dataclass(frozen=True)
class LabSpec:
    """Knob defaults are R1-C's lab tuning toward Cont (2001)'s qualitative facts, never a fit
    to data (R1-C §2.5 declares the ~6 sweeps). FX anchor: Baillie & Bollerslev (1989), daily FX
    as a t-GARCH."""
    n_inst: int = 20
    days: int = 3640                              # weekdays (~14.4 years)
    seed: int = 1
    start: str = "2012-01-02"                     # a Monday
    ann_vol: tuple[float, float] = (0.06, 0.14)   # per-instrument annual vol, spread evenly
    rho: float = 0.3                              # the one factor's |loading|² (corr b_i·b_j)
    nu: float = 8.0                               # Student-t by variance mixing, > 2
    garch: tuple[float, float] = (0.04, 0.90)     # (a, b) on the standardised squared return
    sv_sd: float = 0.5                            # multi-scale log-vol: total sd of log sigma
    sv_halflives: tuple[float, ...] = (3.0, 15.0, 75.0, 375.0, 1875.0)
    jumps_per_year: float = 2.0                   # compound Poisson
    jump_sd: float = 3.0                          # Laplace size sd, in daily-sigma units
    weekend_var: float = 0.25                     # Monday gap variance, share of a weekday's
    rate_sd: float = 0.02                         # cross-sectional sd of the annual rate differential
    rate_halflife: float = 500.0                  # weekdays
    financing: bool = True                        # False: rates are zero and carry is refused
    effect: Effect = field(default_factory=Effect)

    def __post_init__(self) -> None:
        a, b = self.garch
        if not (0.0 <= self.rho < 1.0 and self.nu > 2.0 and self.n_inst >= 1 and self.days > 300):
            raise ValueError("bad LabSpec: 0 <= rho < 1, nu > 2, n_inst >= 1, days > 300")
        if not (a >= 0 and b >= 0 and a + b < 1):
            raise ValueError("GARCH must be stationary: a, b >= 0 and a + b < 1")
        if self.jumps_per_year / YEAR * self.jump_sd ** 2 >= 0.5:
            raise ValueError("jumps would carry half the variance")
        if not self.financing and self.effect.carry_sharpe:
            raise ValueError("carry cannot be planted when the grader books no financing")
        if np.datetime64(self.start, "D").astype(object).weekday() != 0:
            raise ValueError("start must be a Monday")

    @property
    def other(self) -> float:
        """Var(e + J + G) of y per weekday, averaged over the week (Mondays carry the gap)."""
        return 1.0 + self.weekend_var / 5.0


@dataclass(frozen=True)
class LabPath:
    """One generated history. Every array is (T,) or (T, N) and read-only."""
    spec: LabSpec
    kind: str                # "null", "planted" or "permuted"
    dates: np.ndarray        # weekday dates, datetime64[D]
    sigma: np.ndarray        # conditional daily sd, known at the day's start
    y: np.ndarray            # the excess return in volatility units
    r: np.ndarray            # the simple excess return = sigma·y
    spot: np.ndarray         # the simple spot return = r - accrual
    accrual: np.ndarray      # a long's financing for the day's rollover: rate x its days / 365
    rate: np.ndarray         # the annual rate differential (base minus quote)
    m: np.ndarray            # the planted drift in vol units, before `scale` (the truth)
    scale: float             # the variance match (1.0 on the null)
    fac: np.ndarray          # the common factor's diffusive shock (T,)
    idio: np.ndarray         # the idiosyncratic diffusive shocks
    wf: np.ndarray           # Var(fac | mixing draw) (T,)
    we: np.ndarray           # Var(idio | mixing draw)
    loadings: np.ndarray     # b_i (N,)
    diff_scale: float        # diffusive = diff_scale·(b·fac + sqrt(1 - b²)·idio)
    jumps: np.ndarray
    gap: np.ndarray
    tom: np.ndarray          # turn-of-month flags (T,)
    season_dir: np.ndarray   # (N,)

    def mids(self, first: np.ndarray | float = 1.0) -> np.ndarray:
        """The mid at each day's close: first·prod(1 + spot) (T, N)."""
        return np.asarray(first, float) * np.cumprod(1.0 + self.spot, axis=0)


def _frozen(**arrays: np.ndarray) -> dict:
    for a in arrays.values():
        if isinstance(a, np.ndarray):
            a.setflags(write=False)
    return arrays


def calendar(spec: LabSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Weekday dates, the turn-of-month flags (the month's last day and first three) and Mondays."""
    dates = np.busday_offset(np.datetime64(spec.start), np.arange(spec.days), roll="forward")
    months = dates.astype("datetime64[M]")
    change = months[1:] != months[:-1]
    tom = np.r_[change, False]
    for s in np.flatnonzero(np.r_[True, change]):
        tom[s:s + 3] = True
    monday = (dates.view("int64") - 4) % 7 == 0               # 1970-01-01 was a Thursday
    return dates, tom, monday


def _ar1(eta: np.ndarray, phi: float, var: float) -> np.ndarray:
    """A stationary AR(1) with variance `var`, driven by unit shocks `eta` along axis 0."""
    out = np.empty_like(eta)
    out[0] = eta[0] * math.sqrt(var)
    kick = math.sqrt(var * (1.0 - phi * phi))
    for t in range(1, len(eta)):
        out[t] = phi * out[t - 1] + kick * eta[t]
    return out


def generate(spec: LabSpec) -> LabPath:
    rng = np.random.default_rng(spec.seed)
    T, N, E, other = spec.days, spec.n_inst, spec.effect, spec.other
    dates, tom, monday = calendar(spec)
    vol_d = np.linspace(*spec.ann_vol, N) / math.sqrt(YEAR)
    b = math.sqrt(spec.rho) * rng.choice((-1.0, 1.0), size=N)
    lam, nu = spec.jumps_per_year / YEAR, spec.nu
    diff_scale = math.sqrt(1.0 - lam * spec.jump_sd ** 2)   # jumps keep the total variance
    # the noise, all drawn first in a FIXED order: null and planted of one seed share it
    zf, ze = rng.standard_normal(T), rng.standard_normal((T, N))
    wf, we = (nu - 2.0) / rng.chisquare(nu, T), (nu - 2.0) / rng.chisquare(nu, (T, N))
    jumps = rng.laplace(0.0, spec.jump_sd / math.sqrt(2.0), (T, N)) * np.sqrt(rng.poisson(lam, (T, N)))
    gap_z = rng.standard_normal((T, N)) * np.sqrt((nu - 2.0) / rng.chisquare(nu, (T, N)))
    rate_eta, sv_eta = rng.standard_normal((T, N)), rng.standard_normal((len(spec.sv_halflives), T, N))
    # the effects, from their own generator
    eff = np.random.default_rng([spec.seed, 7919])
    tr_eta, trf_eta, xs_eta = eff.standard_normal((T, N)), eff.standard_normal(T), eff.standard_normal((T, N))
    season_dir = eff.choice((-1.0, 1.0), size=N)

    fac, idio = zf * np.sqrt(wf), ze * np.sqrt(we)
    diffusive = diff_scale * (b * fac[:, None] + np.sqrt(1.0 - b * b) * idio)
    gap = np.where(monday[:, None], math.sqrt(spec.weekend_var) * gap_z, 0.0)
    z = _ar1(rate_eta, ar_phi(spec.rate_halflife), 1.0)       # the standardised rate differential
    rate = spec.rate_sd * z if spec.financing else np.zeros((T, N))

    m, v_m = np.zeros((T, N)), 0.0
    if E.trend_sharpe:
        v = drift_variance_for(E.trend_sharpe, other)
        ph = ar_phi(E.trend_halflife)
        m += (np.sign(b) * _ar1(trf_eta, ph, v)[:, None] if E.trend_scope == "factor"
              else _ar1(tr_eta, ph, v))
        v_m += v
    if E.carry_sharpe:
        kappa = carry_kappa_for(E.carry_sharpe, other)
        m += kappa * z
        v_m += kappa * kappa
    if E.xsmom_sharpe:
        v = drift_variance_for(E.xsmom_sharpe, other)
        u = _ar1(xs_eta, ar_phi(E.xsmom_halflife), v / (1.0 - 1.0 / N))
        m += u - u.mean(axis=1, keepdims=True)                 # per day: the effect, not a bridge
        v_m += v
    if E.season_sharpe:
        s = season_size_for(E.season_sharpe, float(tom.mean()), other)
        m += s * tom[:, None] * season_dir
        v_m += s * s * float(tom.mean())
    scale = math.sqrt(other / (other + v_m))
    y = scale * (m + diffusive + jumps + gap)

    svf = np.ones((T, N))
    if spec.sv_sd > 0:
        k = len(spec.sv_halflives)
        lv = sum(_ar1(sv_eta[j], ar_phi(h), spec.sv_sd ** 2 / k) for j, h in enumerate(spec.sv_halflives))
        svf = np.exp(lv - spec.sv_sd ** 2)                     # E[svf²] = 1
    a, bb = spec.garch
    h, sigma = np.ones(N), np.empty((T, N))
    for t in range(T):                                         # sigma_t is known at the day's start
        sigma[t] = vol_d * np.sqrt(h) * svf[t]
        h = (1.0 - a - bb) + a * h * y[t] ** 2 + bb * h
    r = sigma * y
    if (r <= -1.0).any():
        raise ValueError("a simple return <= -1 was drawn: lower ann_vol or jump_sd")
    # ONE financing calendar (C-6): the day ends at its 17:00-New-York rollover, which the harness
    # bills rate x swap_multiplier / 365 (tom_next: Wednesday x3), so a financed long earns r
    nights = np.array([swap_multiplier(d.astype(object)) for d in dates], float)
    accrual = rate * nights[:, None] / 365.0
    kind = "planted" if v_m else "null"
    return LabPath(spec, kind, **_frozen(
        dates=dates, sigma=sigma, y=y, r=r, spot=r - accrual, accrual=accrual, rate=rate, m=m,
        fac=fac, idio=idio, wf=wf, we=we, loadings=b, jumps=jumps, gap=gap, tom=tom,
        season_dir=season_dir), scale=scale, diff_scale=diff_scale)


def permuted(path: LabPath, seed: int = 0) -> LabPath:
    """Whole days shuffled, every instrument together, then one random sign per day. Rates,
    dates and the calendar keep their order; the grader charges financing on its own path."""
    rng = np.random.default_rng([path.spec.seed, 31337, seed])
    order, flip = rng.permutation(len(path.dates)), rng.choice((-1.0, 1.0), size=len(path.dates))

    def signed(a: np.ndarray) -> np.ndarray:
        return a[order] * (flip if a.ndim == 1 else flip[:, None])

    r = signed(path.r)
    return replace(path, kind="permuted", **_frozen(
        sigma=path.sigma[order], y=signed(path.y), r=r, spot=r - path.accrual, m=signed(path.m),
        fac=signed(path.fac), idio=signed(path.idio), wf=path.wf[order], we=path.we[order],
        jumps=signed(path.jumps), gap=signed(path.gap)))
