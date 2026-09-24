"""C1 CALIBRATOR — first-passage Monte Carlo of an FTMO-2-Step-Swing-$10k-style rulebook.

Receipt, synthetic only. Units: fractions of the initial balance A = $10,000.
Rules (ftmo.com/en/trading-objectives, fetched 2026-09-24):
  * phase 1 target +10%, phase 2 target +5% (fresh A each phase; phase 2 free);
  * Maximum Daily Loss: EQUITY may not drop below (BALANCE at 00:00 CE(S)T) - 5% of A,
    checked on every intraday sub-step; open P&L carried over midnight is NOT in the reference;
  * Maximum Loss: static, equity >= 0.90 A;  >= 4 trading days per phase;
  * fee EUR 89 ~ $104, refunded with the first reward; split 80%; rewards every 10 trading
    days (14 calendar) from the funded start, profit above A withdrawn, balance reset to A.
Market: P&L = k * (drift + sub-step shocks). Shocks Student-t(4) with log-SV (rho .97, sd .10);
per-day 1% chance of a 4-sigma symmetric jump, 0.1% chance of an adverse 6-sigma gap;
positions held over a weekend take a Monday-open gap with 2x variance (swing only).
Net annual Sharpe S_net = S_gross - N_rt * c_rt / (sigma_inst * sqrt(252)) (cost folded into
drift; declared simplification). Horizons: challenge <= 504 trading days total, funded 756 d.
"""
from __future__ import annotations

import math
import sys

import numpy as np

SUB = 8
FEE = 104.0
A = 10_000.0
SPLIT = 0.80
T1, T2, DLL, MLL = 0.10, 0.05, 0.05, 0.10
MIN_DAYS = 4
CH_MAX, FUND_DAYS = 504, 756
PAY_EVERY = 10
SIG_INST = 0.006


def s_net(s_gross, n_rt, c_rt_bp=1.5):
    return s_gross - n_rt * c_rt_bp * 1e-4 / (SIG_INST * math.sqrt(252))


def simulate(S, k_ch=0.01, k_f=0.01, prop_cushion=None, swing=True, paths=4000, seed=0,
             delta=0.25, haircut=0.0, fat=True):
    """Returns dict of EV ($ per attempt), P(pass), mean days to pass, P(any payout),
    P(funded breach within 126 d), payouts, and the pass-day array."""
    rng = np.random.default_rng(seed)
    mu_d = S / math.sqrt(252)                    # per-day drift in units of daily sd
    # state
    phase = np.ones(paths, dtype=np.int8)        # 1,2 challenge; 3 funded; 0 dead; 4 funded done
    bal = np.ones(paths)                         # balance (realised)
    opn = np.zeros(paths)                        # open P&L
    day_in_phase = np.zeros(paths, dtype=np.int32)
    ch_days = np.zeros(paths, dtype=np.int32)
    fund_day = np.zeros(paths, dtype=np.int32)
    pass_day = np.full(paths, -1)
    breach_day = np.full(paths, -1)
    pv = np.zeros(paths)                         # discounted $ to the trader
    first_paid = np.zeros(paths, dtype=bool)
    lvol = np.zeros(paths)
    t = 0
    while True:
        active = (phase == 1) | (phase == 2) | (phase == 3)
        if not active.any() or t > CH_MAX + FUND_DAYS + 10:
            break
        dow = t % 5
        ref = bal.copy()                         # 00:00 balance reference (open P&L excluded)
        floor_d = ref - DLL
        lvol = 0.97 * lvol + 0.10 * rng.standard_normal(paths) if fat else lvol
        vol = np.exp(lvol - 0.10 ** 2 / (1 - 0.97 ** 2)) if fat else np.ones(paths)   # E[vol^2]=1
        k = np.where(phase == 3, k_f, k_ch)
        if prop_cushion is not None:
            k = np.where(phase == 3, np.minimum(k_f, prop_cushion * np.maximum(bal + opn - (1 - MLL), 0)), k)
        jump = (rng.random(paths) < 0.01) * rng.choice([-4.0, 4.0], paths) if fat else 0.0
        crash = ((rng.random(paths) < 0.001) * -6.0 + 0.006) if fat else 0.0   # mean-compensated
        norm = 1 / math.sqrt(1 + 0.16 + 0.036) if fat else 1.0                  # daily sd = 1
        dead_today = np.zeros(paths, dtype=bool)
        hit_today = np.zeros(paths, dtype=bool)
        tgt = np.where(phase == 1, 1 + T1, np.where(phase == 2, 1 + T2, np.inf))
        can_hit = (day_in_phase + 1) >= MIN_DAYS
        for s in range(SUB):
            if fat:
                z = rng.standard_t(4, paths) / math.sqrt(2.0)
            else:
                z = rng.standard_normal(paths)
            if s == 0 and dow == 0 and swing:
                z = z * math.sqrt(2.0)           # weekend gap on held positions
            shock = z * vol / math.sqrt(SUB)
            if s == SUB // 2 and fat:
                shock = shock + jump + crash
            dx = k * (mu_d / SUB + norm * shock)
            live = active & ~dead_today & ~hit_today
            opn = np.where(live, opn + dx, opn)
            eq = bal + opn
            breach = live & ((eq < floor_d) | (eq < 1 - MLL))
            dead_today |= breach
            hit_today |= live & ~breach & can_hit & (eq >= tgt)
        # end of day: breach handling
        bd = active & dead_today
        breach_day = np.where(bd & (phase == 3) & (breach_day < 0), fund_day, breach_day)
        phase = np.where(bd, 0, phase)
        active = active & ~bd
        # realise: intraday closes everything; swing realises on Fridays (weekly holds)
        if not swing or dow == 4:
            bal = np.where(active, bal + opn, bal)
            opn = np.where(active, 0.0, opn)
        day_in_phase += active
        eq = bal + opn
        # targets (checked on equity, flatten on hit)
        ph_start = phase.copy()
        for ph in (1, 2):
            hit = active & (ph_start == ph) & hit_today
            nxt = 2 if ph == 1 else 3
            if ph == 2:
                pass_day = np.where(hit, t + 1, pass_day)
            phase = np.where(hit, nxt, phase)
            bal = np.where(hit, 1.0, bal)
            opn = np.where(hit, 0.0, opn)
            day_in_phase = np.where(hit, 0, day_in_phase)
        chal = (phase == 1) | (phase == 2)
        ch_days += chal
        phase = np.where(chal & (ch_days >= CH_MAX), 0, phase)   # give up
        # funded payouts
        f = active & (phase == 3) & (day_in_phase > 0)
        fund_day = np.where(f, fund_day + 1, fund_day)
        pay_now = f & (fund_day % PAY_EVERY == 0)
        if pay_now.any():
            prof = np.maximum(bal + opn - 1.0, 0.0)
            pay = pay_now & (prof > 0)
            disc = math.exp(-delta * (t + 1) / 252)
            cash = SPLIT * prof * A * (1 - haircut)
            refund = pay & ~first_paid
            pv = np.where(pay, pv + disc * cash + np.where(refund, disc * FEE * (1 - haircut), 0.0), pv)
            first_paid |= pay
            bal = np.where(pay, 1.0, bal)
            opn = np.where(pay, 0.0, opn)
        phase = np.where(f & (fund_day >= FUND_DAYS), 4, phase)
        t += 1
    passed = pass_day >= 0
    return {
        "EV": float(pv.mean() - FEE),
        "EV_se": float(pv.std() / math.sqrt(paths)),
        "P_pass": float(passed.mean()),
        "days_to_pass": float(pass_day[passed].mean()) if passed.any() else float("nan"),
        "P_any_payout": float(first_paid[passed].mean()) if passed.any() else float("nan"),
        "P_breach_126d_funded": float(((breach_day >= 0) & (breach_day <= 126))[passed].mean()) if passed.any() else float("nan"),
    }


if __name__ == "__main__":
    print(simulate(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0, paths=2000))
