"""R1-D receipt: timing and trade shape of a bar-level research simulator (synthetic only).

LLM-originated sketch, NOT an implementation. It answers two questions:
  1. Compute: how long does one pooled-rule run take on 30 instruments x 14 years of
     daily and of hourly bars, if every fill is priced by ACIS's own scalar
     `core.optimizer.costs.CostModel.per_side_cost` (object identity, no vectorised twin)?
  2. Shape: on a planted multi-day trend where the rule HAS an edge, what do the
     SPEC section-14 trade-shape rows (win rate > 48%, avg duration 30 min-48 h,
     positive months > 70%) read?
No real market data: every series is drawn from numpy's PCG64 generator.
Run: OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python sim_rsim_daily.py /tmp/review-acis
"""
import sys, time, json
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis")
from core.optimizer.costs import CostModel  # the ONE cost model, read-only import

N_INST, YEARS, DPY = 30, 14, 260


def market(n_bars, bars_per_day, planted, rng, rho=0.3, episode_days=40, snr=0.08):
    """Factor-correlated Gaussian returns (unit daily vol); planted = persistent-sign drift."""
    s = 1.0 / np.sqrt(bars_per_day)
    common = rng.standard_normal(n_bars)[:, None]
    eps = np.sqrt(rho) * common + np.sqrt(1 - rho) * rng.standard_normal((n_bars, N_INST))
    r = s * eps
    if planted:
        # sign flips with prob 1/episode_days per day -> mean episode ~ episode_days
        p = 1.0 / (episode_days * bars_per_day)
        flips = rng.random((n_bars, N_INST)) < p
        sign = np.where(np.cumsum(flips, axis=0) % 2 == 0, 1.0, -1.0) * rng.choice([-1, 1], N_INST)
        r = r + (snr / bars_per_day) * sign                  # daily drift = snr x daily vol (unit)
    # NO whole-path demeaning (the C3 defect): the null has zero EXPECTED drift only.
    return r


def ewma(x, span):
    a = 2.0 / (span + 1.0)
    out = np.empty_like(x); acc = x[0]
    for i in range(x.shape[0]):
        acc = a * x[i] + (1 - a) * acc; out[i] = acc
    return out


def run(r, bars_per_day, fast_d=16, slow_d=64, cap=20.0, buffer=0.1, cost_models=None, spread=0.02):
    price = np.cumsum(r, axis=0)
    f, s = fast_d * bars_per_day, slow_d * bars_per_day
    raw = ewma(price, f) - ewma(price, s)
    vol = np.sqrt(ewma(r * r, 25 * bars_per_day)) * np.sqrt(bars_per_day)   # daily vol, causal
    fc = raw / np.maximum(vol, 1e-9)
    fc = fc * (10.0 / max(np.mean(np.abs(fc[s:])), 1e-9))   # one pooled scalar (from the whole path: a
    fc = np.clip(fc, -cap, cap)                              # look, acceptable in a timing sketch only)
    target = fc / 10.0 / np.maximum(vol, 1e-9) * 0.01       # 1% daily risk per instrument at |fc|=10
    pos = np.zeros_like(target); held = np.zeros(N_INST)
    fills = 0; cost = np.zeros_like(target)
    for t in range(1, target.shape[0]):                     # decide on bar t-1 close, hold bar t
        tgt = target[t - 1]
        move = np.abs(tgt - held) > buffer * np.maximum(np.abs(tgt), 1e-3)
        for i in np.nonzero(move)[0]:
            c = cost_models[i].per_side_cost(spread)        # scalar call, shared object
            cost[t, i] = c * abs(tgt[i] - held[i])
            held[i] = tgt[i]; fills += 1
        pos[t] = held
    pnl = pos * r - cost
    return pnl, pos, fills


def shape(pnl, pos, bars_per_day):
    """Trade = a maximal run of same-sign position (a flip closes one and opens the next)."""
    wins = tot = 0; durs = []
    for i in range(pos.shape[1]):
        sg = np.sign(pos[:, i]); start = None
        for t in range(len(sg)):
            if start is None and sg[t] != 0:
                start = t
            elif start is not None and (sg[t] != sg[start]):
                tot += 1; wins += pnl[start:t, i].sum() > 0; durs.append((t - start) / bars_per_day)
                start = t if sg[t] != 0 else None
    daily = pnl.sum(axis=1).reshape(-1, bars_per_day).sum(axis=1)
    months = daily[: len(daily) // 21 * 21].reshape(-1, 21).sum(axis=1)
    ann_sr = daily.mean() / daily.std() * np.sqrt(DPY)
    return dict(trades=tot, win_rate=round(wins / max(tot, 1), 3),
                avg_duration_days=round(float(np.mean(durs)), 1),
                positive_months_pct=round(100 * float((months > 0).mean()), 1),
                portfolio_annual_sr=round(float(ann_sr), 2))


if __name__ == "__main__":
    out = {}
    models = [CostModel(commission_per_side=0.0, slippage_per_side=0.0) for _ in range(N_INST)]
    t0 = time.perf_counter(); n = 100_000
    for _ in range(n):
        models[0].per_side_cost(0.02)
    out["per_side_cost_us_per_call"] = round((time.perf_counter() - t0) / n * 1e6, 3)
    for label, bpd in (("daily", 1), ("hourly", 24)):
        for kind in ("null", "planted"):
            rng = np.random.default_rng(20260925 + bpd + (kind == "planted"))
            r = market(YEARS * DPY * bpd, bpd, kind == "planted", rng)
            t0 = time.perf_counter()
            pnl, pos, fills = run(r, bpd, cost_models=models)
            dt = time.perf_counter() - t0
            out[f"{label}_{kind}"] = dict(bars=r.shape[0], instruments=N_INST, fills=fills,
                                          seconds=round(dt, 2), **shape(pnl, pos, bpd))
    print(json.dumps(out, indent=1))
