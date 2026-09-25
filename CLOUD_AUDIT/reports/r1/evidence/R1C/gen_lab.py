"""R1-C synthetic market lab: a PROTOTYPE generator for testing ACIS's machinery (grader, register,
sequential test, rule capture) with known, plantable ground truth. Synthetic only: no real data is read,
fitted, bootstrapped or resampled. Numpy only. LLM-originated design (R1-C), a receipt, not an
implementation.

Mental model (every invariant the lab promises):
  * DAILY FIRST. One weekday = one bar. Everything is generated in VOLATILITY UNITS:
        y[i,t] = m[i,t] + eps[i,t] + J[i,t] + G[i,t]        (excess return / sigma[i,t])
        excess return x[i,t] = sigma[i,t] * y[i,t]
        spot log return  s[i,t] = x[i,t] - c[i,t]            (c = financing accrual of a LONG, rate diff / 252)
    so a long position that is charged/paid financing earns exactly x. The NULL is m == 0: the excess
    return is a martingale difference with zero EXPECTED drift. Nothing is ever demeaned (the BASE bug,
    tests/backtest/synthetic_market.py:113-114), so there is no Brownian-bridge tilt.
  * eps: unit-variance, conditionally Gaussian given per-day variance-mixing draws (Student-t by scale
    mixture), with ONE common factor: eps_i = b_i f + sqrt(1-b_i^2) e_i, corr(i,j) = b_i b_j. Because
    eps is Gaussian GIVEN (sigma, mixing draws), an intraday path is an exact Brownian bridge refinement
    of the day (see `intraday`), unlike the whole-path demeaning which conditions on the FUTURE.
  * sigma = GARCH(1,1) feedback (short-term clustering, reacts to returns) x an exogenous multi-scale
    log-volatility (a sum of AR(1) components with log-spaced half-lives 3..1875 days, a superposition
    that approximates the slow, power-law-like decay of |r| autocorrelation that a single GARCH(1,1)
    cannot give: its decay is exponential). Unconditional variance is preserved (E[svf^2] = 1).
  * J: rare Laplace jumps (compound Poisson), G: a Monday-only weekend gap term. Both zero-mean.
  * Planted effects (all zero = null), each in vol units so its Sharpe is independent of GARCH:
      trend  : m = AR(1) latent drift per instrument (or one common drift, scope "factor"),
               strength = the ORACLE's annual Sharpe (position sign(m_t) on day t+1); any EWMA-crossover
               rule's Sharpe follows in closed form (`theory_ewmac`).
      carry  : m = kappa * zrate[i,t], zrate the standardised rate differential; the rule sign(rate
               diff) earns kappa*sqrt(2/pi) per day.
      xsmom  : m = u_i - mean_j u_j, u AR(1); strength = the XS oracle's annual Sharpe.
      season : m = s * dir_i on the last trading day and first 3 trading days of each month.
  * Every draw comes from ONE numpy Generator seeded by (seed); the null and every planted variant with
    the same seed share the noise, so a planted-vs-null difference is the effect alone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
from scipy.optimize import brentq

YEAR = 252
NY = ZoneInfo("America/New_York")
SQ2PI = math.sqrt(2.0 / math.pi)


@dataclass(frozen=True)
class Effect:
    trend_sr: float = 0.0          # ORACLE annual Sharpe per instrument (0 = none)
    trend_halflife: float = 40.0   # latent drift half-life, trading days (speed)
    trend_scope: str = "idio"      # "idio": independent per instrument; "factor": one common drift
    carry_sr: float = 0.0          # annual Sharpe per instrument of sign(rate differential)
    xsmom_sr: float = 0.0          # XS oracle annual Sharpe per instrument
    xsmom_halflife: float = 60.0
    season_sr: float = 0.0         # annual Sharpe per instrument of the turn-of-month rule


@dataclass(frozen=True)
class LabSpec:
    n_inst: int = 20
    days: int = 3640                      # weekdays (~14.4 years)
    seed: int = 1
    ann_vol: tuple[float, float] = (0.06, 0.14)   # per-instrument annual vol, spread evenly
    rho: float = 0.3                      # |pairwise correlation| from the one factor (b = sqrt(rho))
    nu: float = 8.0                       # Student-t degrees of freedom (scale mixture), > 2
    garch: tuple[tuple[float, float, float], ...] = ((1.0, 0.04, 0.90),)   # (weight, a, b) components
    sv_sd: float = 0.5                    # multi-scale log-vol: total sd of log sigma (0 = GARCH only)
    sv_halflives: tuple[float, ...] = (3.0, 15.0, 75.0, 375.0, 1875.0)   # log-spaced => ~power-law |r| acf
    jump_per_year: float = 2.0            # compound Poisson intensity
    jump_sd: float = 3.0                  # jump sd in daily-sigma units (Laplace)
    weekend_var: float = 0.25             # Monday gap variance as a share of one weekday's
    rate_sd: float = 0.02                 # cross-sectional sd of the annual rate differential
    rate_halflife: float = 500.0          # trading days; rate differentials move slowly
    financing_in_grader: bool = True      # False => rate differentials are zero (a spot-only grader
                                          # would otherwise see UIP drift -c as a spurious 'edge')
    effect: Effect = field(default_factory=Effect)
    start: str = "2012-01-02"             # a Monday

    def __post_init__(self):
        if not (0.0 <= self.rho < 1.0 and self.nu > 2.0 and self.n_inst >= 1 and self.days > 300):
            raise ValueError("bad LabSpec")
        if not self.financing_in_grader and self.effect.carry_sr:
            raise ValueError("carry cannot be planted when the grader books no financing")
        s = sum(w * a / (1 - b) for w, a, b in self.garch)
        if abs(sum(w for w, _, _ in self.garch) - 1) > 1e-9 or s >= 1:
            raise ValueError("GARCH components must have weights summing to 1 and be stationary")


def _phi(halflife: float) -> float:
    return 0.5 ** (1.0 / halflife)


def other_var(spec: LabSpec) -> float:
    """Variance of y excluding planted drift, averaged over weekdays (Mondays carry the gap)."""
    return 1.0 + spec.weekend_var / 5.0


# ---------------------------------------------------------------- closed-form theory (vol units)
def theory_oracle_trend(v_m: float, phi: float, ov: float) -> float:
    """Annual Sharpe of position sign(m_t) held over day t+1, m AR(1) with stationary var v_m."""
    mean = phi * SQ2PI * math.sqrt(v_m)
    return mean / math.sqrt(v_m + ov - mean ** 2) * math.sqrt(YEAR)


def _ewmac_weights(fast: int, slow: int, kmax: int) -> np.ndarray:
    af, asl = 2.0 / (fast + 1), 2.0 / (slow + 1)
    k = np.arange(kmax)
    return (1 - asl) ** (k + 1) - (1 - af) ** (k + 1)       # EWMA_f(p) - EWMA_s(p) = sum w_k y_{t-k}


def theory_ewmac(v_m: float, phi: float, ov: float, fast: int, slow: int) -> float:
    """Annual Sharpe of sign(EWMA_fast - EWMA_slow of the vol-normalised cumulative return) on day t+1,
    under joint Gaussianity: E[sign(X) y'] = sqrt(2/pi) Cov(X, y') / sd(X)."""
    kmax = int(12 * slow) + 50
    w = _ewmac_weights(fast, slow, kmax)
    k = np.arange(kmax)
    cov_xy = v_m * float(np.sum(w * phi ** (k + 1)))
    # Var(X) = sum_j sum_k w_j w_k gamma(|j-k|), gamma(0) = v_m + ov, gamma(d) = v_m phi^d
    # = ov * sum w^2 + v_m * sum_j sum_k w_j w_k phi^|j-k|  (computed by a recursion, O(kmax))
    s = 0.0
    acc = 0.0
    for j in range(kmax):                     # acc_j = sum_{k<j} w_k phi^(j-k)
        acc = phi * (acc + (w[j - 1] if j else 0.0))
        s += w[j] * (w[j] + 2.0 * acc)
    var_x = ov * float(np.sum(w * w)) + v_m * s
    mean = SQ2PI * cov_xy / math.sqrt(var_x)
    return mean / math.sqrt(v_m + ov - mean ** 2) * math.sqrt(YEAR)


def v_m_for(sr: float, phi: float, ov: float) -> float:
    return 0.0 if sr == 0 else brentq(lambda v: theory_oracle_trend(v, phi, ov) - sr, 1e-12, 50.0)


def kappa_for_carry(sr: float, ov: float) -> float:
    if sr == 0:
        return 0.0
    f = lambda k: k * SQ2PI / math.sqrt(ov + k * k - (k * SQ2PI) ** 2) * math.sqrt(YEAR) - sr
    return brentq(f, 1e-9, 5.0)


def season_s_for(sr: float, frac: float, ov: float) -> float:
    """Rule holds dir_i only on flagged days (fraction frac): annual SR = s f sqrt(252) / sqrt(f (ov + s^2) - (s f)^2)."""
    if sr == 0:
        return 0.0
    f = lambda s: s * frac * math.sqrt(YEAR) / math.sqrt(frac * (ov + s * s) - (s * frac) ** 2) - sr
    return brentq(f, 1e-9, 5.0)


# ---------------------------------------------------------------- calendar
def calendar(spec: LabSpec):
    days = np.busday_offset(np.datetime64(spec.start), np.arange(spec.days), roll="forward")
    months = days.astype("datetime64[M]")
    first = np.r_[True, months[1:] != months[:-1]]
    last = np.r_[months[1:] != months[:-1], False]
    idx = np.arange(spec.days)
    tom = np.zeros(spec.days, bool)
    for s in np.flatnonzero(first):
        tom[s:s + 3] = True
    tom |= last
    monday = (days.astype("datetime64[D]").view("int64") - 4) % 7 == 0   # 1970-01-01 was a Thursday
    return days, tom, monday, idx


# ---------------------------------------------------------------- generation
@dataclass
class LabPath:
    spec: LabSpec
    dates: np.ndarray        # (T,) datetime64[D]
    sigma: np.ndarray        # (T, N) conditional daily sd of the excess return
    y: np.ndarray            # (T, N) excess return in vol units
    x: np.ndarray            # (T, N) excess log return  (= sigma * y)
    spot: np.ndarray         # (T, N) spot log return    (= x - carry accrual)
    accrual: np.ndarray      # (T, N) financing accrual of a long, per weekday (rate diff / 252)
    rate: np.ndarray         # (T, N) annual rate differential (base minus quote)
    m: np.ndarray            # (T, N) planted drift in vol units (ground truth; zero on the null)
    diffusive: np.ndarray    # (T, N) the conditionally-Gaussian part of y (bridge endpoint for intraday)
    jumps: np.ndarray        # (T, N)
    gap: np.ndarray          # (T, N) weekend gap part (Mondays only)
    mixvar: np.ndarray       # (T, N) conditional variance of `diffusive` given the mixing draws
    tom: np.ndarray          # (T,) turn-of-month flag
    season_dir: np.ndarray   # (N,)
    loadings: np.ndarray     # (N,)
    fac: np.ndarray          # (T,)   common-factor diffusive shock z_f sqrt(w_f)   (intraday: ONE shared bridge)
    idio: np.ndarray         # (T, N) idiosyncratic diffusive shock z_e sqrt(w_e)
    wf: np.ndarray           # (T,)   conditional variance of fac
    we: np.ndarray           # (T, N) conditional variance of idio
    diff_scale: float        # diffusive = diff_scale * (b fac + sqrt(1-b^2) idio)


def generate(spec: LabSpec) -> LabPath:
    rng = np.random.default_rng(spec.seed)
    T, N, E = spec.days, spec.n_inst, spec.effect
    dates, tom, monday, _ = calendar(spec)
    ov = other_var(spec)
    vol_d = np.linspace(*spec.ann_vol, N) / math.sqrt(YEAR)
    signs = rng.choice((-1.0, 1.0), size=N)
    b = math.sqrt(spec.rho) * signs
    lam = spec.jump_per_year / YEAR
    jshare = lam * spec.jump_sd ** 2
    if jshare >= 0.5:
        raise ValueError("jumps would carry half the variance")
    diff_scale = math.sqrt(1.0 - jshare)
    nu = spec.nu
    # --- noise draws, all at once, in a FIXED order (effects are drawn after, so null and planted share noise)
    zf = rng.standard_normal(T)
    ze = rng.standard_normal((T, N))
    wf = (nu - 2.0) / rng.chisquare(nu, T)
    we = (nu - 2.0) / rng.chisquare(nu, (T, N))
    jcount = rng.poisson(lam, (T, N))
    jsize = rng.laplace(0.0, spec.jump_sd / math.sqrt(2.0), (T, N)) * np.sqrt(jcount)
    gz = rng.standard_normal((T, N)) * np.sqrt((nu - 2.0) / rng.chisquare(nu, (T, N)))
    rate_eta = rng.standard_normal((T, N))
    sv_eta = rng.standard_normal((len(spec.sv_halflives), T, N))
    rate0 = rng.standard_normal(N)
    # --- effect draws
    eff_rng = np.random.default_rng([spec.seed, 7919])
    tr_eta = eff_rng.standard_normal((T, N))
    trf_eta = eff_rng.standard_normal(T)
    xs_eta = eff_rng.standard_normal((T, N))
    season_dir = eff_rng.choice((-1.0, 1.0), size=N)

    mixvar = diff_scale ** 2 * (b[None, :] ** 2 * wf[:, None] + (1 - b[None, :] ** 2) * we)
    diffusive = diff_scale * (b[None, :] * zf[:, None] * np.sqrt(wf)[:, None]
                              + np.sqrt(1 - b[None, :] ** 2) * ze * np.sqrt(we))
    gap = np.where(monday[:, None], math.sqrt(spec.weekend_var) * gz, 0.0)

    # rate differentials: AR(1) around a per-instrument level, cross-sectional sd rate_sd
    phr = _phi(spec.rate_halflife)
    z = np.empty((T, N)); z[0] = rate0
    for t in range(1, T):
        z[t] = phr * z[t - 1] + math.sqrt(1 - phr * phr) * rate_eta[t]
    rate = spec.rate_sd * z if spec.financing_in_grader else np.zeros((T, N))
    accrual = rate / YEAR

    # planted drift m (vol units)
    m = np.zeros((T, N))
    if E.trend_sr:
        ph = _phi(E.trend_halflife)
        vm = v_m_for(E.trend_sr, ph, ov)
        if E.trend_scope == "factor":
            f = np.empty(T); f[0] = trf_eta[0] * math.sqrt(vm)
            for t in range(1, T):
                f[t] = ph * f[t - 1] + math.sqrt(vm * (1 - ph * ph)) * trf_eta[t]
            m += np.sign(b)[None, :] * f[:, None]
        else:
            u = np.empty((T, N)); u[0] = tr_eta[0] * math.sqrt(vm)
            for t in range(1, T):
                u[t] = ph * u[t - 1] + math.sqrt(vm * (1 - ph * ph)) * tr_eta[t]
            m += u
    if E.carry_sr:
        m += kappa_for_carry(E.carry_sr, ov) * z
    if E.xsmom_sr:
        ph = _phi(E.xsmom_halflife)
        # oracle sign(mx_t) on t+1: phi sqrt(2/pi) sd(mx); sd(mx) = sqrt(vu (1 - 1/N))
        vx = v_m_for(E.xsmom_sr, ph, ov)
        vu = vx / (1 - 1 / N)
        u = np.empty((T, N)); u[0] = xs_eta[0] * math.sqrt(vu)
        for t in range(1, T):
            u[t] = ph * u[t - 1] + math.sqrt(vu * (1 - ph * ph)) * xs_eta[t]
        m += u - u.mean(axis=1, keepdims=True)      # CROSS-SECTIONAL demeaning (per day): intended
    if E.season_sr:
        s = season_s_for(E.season_sr, float(tom.mean()), ov)
        m += s * tom[:, None] * season_dir[None, :]

    y = m + diffusive + jsize + gap

    # GARCH components on the normalised squared excess return; sigma[t] is known at the start of day t
    comps = np.array(spec.garch)
    w, a, bb = comps[:, 0], comps[:, 1], comps[:, 2]
    h = np.ones((len(w), N))
    sigma = np.empty((T, N))
    # exogenous multi-scale log-vol (conditionally Gaussian days are preserved: it only scales sigma)
    svf = np.ones((T, N))
    if spec.sv_sd > 0:
        K = len(spec.sv_halflives)
        lv = np.zeros((T, N))
        for k, hl in enumerate(spec.sv_halflives):
            ph = _phi(hl); sdk = spec.sv_sd / math.sqrt(K)
            c = np.empty((T, N)); c[0] = sdk * sv_eta[k, 0]
            for t in range(1, T):
                c[t] = ph * c[t - 1] + sdk * math.sqrt(1 - ph * ph) * sv_eta[k, t]
            lv += c
        svf = np.exp(lv - spec.sv_sd ** 2)                    # E[svf^2] = 1: unconditional variance kept
    for t in range(T):
        tot = (w[:, None] * h).sum(axis=0)
        sigma[t] = vol_d * np.sqrt(tot) * svf[t]
        q = (sigma[t] * y[t] / (vol_d * svf[t])) ** 2         # GARCH reacts to the SV-standardised return
        h = (1 - a - bb)[:, None] + a[:, None] * q[None, :] + bb[:, None] * h
    x = sigma * y
    spot = x - accrual
    return LabPath(spec, dates, sigma, y, x, spot, accrual, rate, m, diffusive, jsize, gap, mixvar,
                   tom, season_dir, b, zf * np.sqrt(wf), ze * np.sqrt(we), wf, we, diff_scale)


def permuted(path: LabPath, seed: int = 0) -> LabPath:
    """The permuted control (FIX-C at day scale): days shuffled (all instruments together, so the
    cross-section is kept), then ONE random sign per day. Given the pool of days, the excess return is a
    martingale-difference sequence: every non-anticipating rule has exactly zero expected gross P&L.
    Rates/financing keep their own path (the grader charges them); dates and the calendar stay in order.
    Never demeaned: shuffle-then-demean is a bridge (fixed sum), which is the BASE defect."""
    rng = np.random.default_rng([path.spec.seed, 31337, seed])
    T = path.x.shape[0]
    k = rng.permutation(T)
    e = rng.choice((-1.0, 1.0), size=T)
    sg = lambda a: a[k] * (e if a.ndim == 1 else e[:, None])       # re-index and flip a signed array
    x = sg(path.x)
    return LabPath(path.spec, path.dates, path.sigma[k], sg(path.y), x, x - path.accrual, path.accrual,
                   path.rate, sg(path.m), sg(path.diffusive), sg(path.jumps), sg(path.gap), path.mixvar[k],
                   path.tom, path.season_dir, path.loadings, sg(path.fac), sg(path.idio), path.wf[k],
                   path.we[k], path.diff_scale)


# ---------------------------------------------------------------- intraday on demand
# Relative variance share per UTC hour (LLM-chosen shape: Asia low, London open up, London/NY overlap
# highest, late NY low, rollover hour lowest). A lab knob, NOT a calibration to any real series.
HOUR_VAR = np.array([0.6, 0.6, 0.7, 0.7, 0.6, 0.6, 0.8, 1.4, 1.8, 1.6, 1.4, 1.3,
                     1.6, 2.0, 2.2, 1.9, 1.5, 1.1, 0.8, 0.6, 0.5, 0.35, 0.4, 0.5])
HOUR_SPREAD = np.array([1.8, 1.8, 1.6, 1.5, 1.5, 1.4, 1.2, 1.0, 0.9, 0.9, 0.9, 0.9,
                        0.9, 0.85, 0.85, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 1.9, 1.8])


def _bridge(rng, wv, var, endpoint, shape):
    """Brownian bridge increments on a time-changed clock (weights wv, sum 1), total variance `var`,
    pinned to `endpoint`. Exact: a Gaussian walk conditioned on its sum."""
    inc = rng.standard_normal(shape) * np.sqrt(wv * var)
    return inc - wv * (inc.sum(axis=-1, keepdims=True) - endpoint)


def session_start_utc(day: np.datetime64) -> datetime:
    """The lab's trading day for weekday `day` runs [17:00 New York of the previous calendar day,
    17:00 New York of `day`): the FX convention (Monday's day opens Sunday 17:00 NY). DST-correct."""
    d = day.astype("datetime64[D]").astype(object) - timedelta(days=1)
    return datetime(d.year, d.month, d.day, 17, tzinfo=NY).astimezone(timezone.utc)


def intraday_panel(path: LabPath, t: int, tick_seconds: int = 60, joint: bool = True,
                   base_spread: np.ndarray | float = 1e-4, roll_minutes: int = 10, roll_mult: float = 8.0,
                   spike_prob: float = 0.002, spike_mult: float = 8.0, tick_rate: float = 0.5,
                   rng: np.random.Generator | None = None) -> dict:
    """All N instruments' ticks for weekday t, whose per-instrument sums are EXACTLY x[t, :].
    joint=True (the design): ONE bridge for the common factor, one per idiosyncratic shock, each pinned
    to its own daily endpoint, so intraday co-movement is a correlated Brownian motion and no instrument's
    past predicts another's rest-of-day. joint=False (kept only for the probe) bridges each instrument's
    combined shock independently, which PLANTS a spurious lead-lag/pairs edge. Planted drift is spread
    in proportion to session variance; a jump lands on one random tick; Monday's gap on the first tick.
    Spread: base x session profile x (roll_mult for `roll_minutes` after the 17:00 New York open of the
    day) x random spikes. `emit` thins quotes with a session-shaped Poisson-like intensity (the price
    path is unchanged; an adapter yields a RawTick only where emit is True)."""
    p = path
    N = p.x.shape[1]
    rng = rng or np.random.default_rng([p.spec.seed, 104729, t])
    n = 86400 // tick_seconds
    t0 = session_start_utc(p.dates[t])
    secs = np.arange(n) * tick_seconds
    hours = ((t0.hour * 3600 + t0.minute * 60 + secs) // 3600) % 24
    wv = HOUR_VAR[hours]; wv = wv / wv.sum()
    if joint:
        f = _bridge(rng, wv, p.wf[t], p.fac[t], (n,))
        e = _bridge(rng, wv[None, :], p.we[t][:, None], p.idio[t][:, None], (N, n))
        b = p.loadings[:, None]
        inc = p.diff_scale * (b * f[None, :] + np.sqrt(1 - b * b) * e)
    else:
        inc = _bridge(rng, wv[None, :], p.mixvar[t][:, None], p.diffusive[t][:, None], (N, n))
    inc = inc + wv[None, :] * p.m[t][:, None]
    for i in np.flatnonzero(p.jumps[t]):
        inc[i, rng.integers(n)] += p.jumps[t, i]
    inc[:, 0] += p.gap[t]
    logret = p.sigma[t][:, None] * inc                                   # (N, n): sums to x[t]
    spread = np.broadcast_to(np.asarray(base_spread, float).reshape(-1, 1), (N, 1)) * HOUR_SPREAD[hours][None, :]
    spread = np.where(secs[None, :] < roll_minutes * 60, spread * roll_mult, spread)
    spread = np.where(rng.random((N, n)) < spike_prob, spread * spike_mult, spread)
    intensity = np.clip(tick_rate * HOUR_VAR[hours] / HOUR_VAR.mean(), 0.0, 1.0)
    emit = rng.random((N, n)) < intensity[None, :]
    emit[:, 0] = True
    times = np.datetime64(t0.replace(tzinfo=None), "s") + secs.astype("timedelta64[s]")
    return {"times_utc": times, "logret": logret, "spread_frac": spread, "emit": emit, "hours": hours}


if __name__ == "__main__":
    import time
    t0 = time.perf_counter()
    p = generate(LabSpec())
    t1 = time.perf_counter()
    print(f"20 instruments x {p.spec.days} weekdays generated in {1000 * (t1 - t0):.0f} ms")
    ov = other_var(p.spec)
    for hl in (20, 40, 80):
        ph = _phi(hl); vm = v_m_for(0.6, ph, ov)
        print(f"trend oracle SR 0.60 hl {hl}d: v_m {vm:.5f}; EWMAC SR "
              + " ".join(f"{f}/{4 * f}:{theory_ewmac(vm, ph, ov, f, 4 * f):.3f}" for f in (4, 8, 16, 32, 64)))
    d = intraday_panel(p, 10)
    print(f"intraday day 10: {d['logret'].shape} grid, starts {d['times_utc'][0]} UTC; max |sum - x| "
          f"{np.abs(d['logret'].sum(axis=1) - p.x[10]).max():.2e}; emitted {d['emit'].mean():.2f} of grid")
