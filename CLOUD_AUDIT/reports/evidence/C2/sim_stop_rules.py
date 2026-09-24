"""C2 sizing sim: how many pips per trade the graded book's stop rules are worth, on a
synthetic tape that has what the ACIS synthetic tape lacks: a daily rollover spread spike and
weekend gaps. Synthetic only; no ACIS code runs here. The rules are restated from
tests/backtest/book.py:112-126 and tests/backtest/data_loader.py:82-83.

    python sim_stop_rules.py          # ~20 s, one core

The tape: EUR_USD-like random walk, 20 s ticks, sigma 0.5%/day. The normal spread is 1.0 pip.
For 5 minutes after each 17:00 New York rollover the spread is uniform 3-15 pips (the mid
does not move). Weekend: Friday's close to Sunday's open is one Gaussian gap, sd 30 pips.
Trades: at random times, long or short at random, with a 10-pip stop, a 15-pip target and a
48 h max hold. The entry cost is the same under both rules, so only the exits differ.
  HARNESS rules: a tick with spread > 5 pips is DROPPED; the stop triggers on the MID; the
                 exit is booked AT the stop price; friction is half the tick's spread.
  BROKER rules:  a sell stop triggers on bid <= stop and fills at that bid (a buy stop on
                 ask); a gap fills at the first quote beyond the stop.
Both rules use the same random-entry trades, so the difference is the rules alone.
"""

import math
import random

PIP = 0.0001
TICK_S = 20
TPD = 86400 // TICK_S


def tape(days, rng, gap_pips=30.0, spike=True):
    """(mid, spread, dropped_by_loader); weekdays only; the rollover is at 22:00 UTC."""
    sig = 0.005 / math.sqrt(TPD)
    mid, out = 1.1, []
    for d in range(days):
        wd = d % 7
        if wd >= 5:
            continue
        if wd == 0 and d > 0:
            mid *= math.exp(rng.gauss(0, gap_pips * PIP / 1.1) if gap_pips else 0.0)     # the weekend gap
        for i in range(TPD):
            sec = i * TICK_S
            if wd == 4 and sec >= 22 * 3600:
                break                                        # Friday after the rollover: closed
            mid *= math.exp(rng.gauss(0, sig))
            in_spike = spike and 22 * 3600 <= sec < 22 * 3600 + 300
            s = rng.uniform(3, 15) * PIP if in_spike else 1.0 * PIP
            out.append((mid, s, s > 5 * PIP))
    return out


def exit_harness(tp, i, d, stop, tgt, max_ticks):
    for j in range(i + 1, min(len(tp), i + max_ticks)):
        mid, s, dropped = tp[j]
        if dropped:
            continue
        if (d == 1 and mid <= stop) or (d == -1 and mid >= stop):
            return d * (stop - tp[i][0]) - s / 2
        if (d == 1 and mid >= tgt) or (d == -1 and mid <= tgt):
            return d * (tgt - tp[i][0]) - s / 2
    mid, s, _ = tp[min(len(tp) - 1, i + max_ticks)]
    return d * (mid - tp[i][0]) - s / 2


def exit_broker(tp, i, d, stop, tgt, max_ticks):
    for j in range(i + 1, min(len(tp), i + max_ticks)):
        mid, s, _ = tp[j]
        bid, ask = mid - s / 2, mid + s / 2
        if d == 1 and bid <= stop:
            return bid - tp[i][0]
        if d == -1 and ask >= stop:
            return tp[i][0] - ask
        if d == 1 and bid >= tgt:
            return tgt - tp[i][0]
        if d == -1 and ask <= tgt:
            return tp[i][0] - tgt
    mid, s, _ = tp[min(len(tp) - 1, i + max_ticks)]
    return d * (mid - tp[i][0]) - s / 2


def main(days=364, n_trades=6000, seed=4, **tape_kw):
    rng = random.Random(seed)
    tp = tape(days, rng, **tape_kw)
    print('tape:', tape_kw or 'weekend gap sd 30 pips + rollover spike')
    max_ticks = 48 * 3600 // TICK_S
    diffs, h_all, b_all = [], [], []
    for _ in range(n_trades):
        i = rng.randrange(0, len(tp) - max_ticks - 1)
        if tp[i][2]:
            continue
        d = rng.choice((1, -1))
        stop, tgt = tp[i][0] - d * 10 * PIP, tp[i][0] + d * 15 * PIP
        h = exit_harness(tp, i, d, stop, tgt, max_ticks) / PIP
        b = exit_broker(tp, i, d, stop, tgt, max_ticks) / PIP
        h_all.append(h)
        b_all.append(b)
        diffs.append(h - b)
    n = len(diffs)
    m = sum(diffs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / (n - 1))
    print(f"{n} random-entry trades, 10-pip stop / 15-pip target / 48 h max hold, one synthetic year")
    print(f"  mean exit pips, harness rules = {sum(h_all) / n:+.3f}; broker rules = {sum(b_all) / n:+.3f}")
    print(f"  harness minus broker = {m:+.3f} pips/trade (95% CI +/- {1.96 * sd / math.sqrt(n):.3f}); "
          f"trades where the rules disagree: {sum(abs(x) > 1e-9 for x in diffs)}/{n}")
    worst = sorted(diffs)[-5:]
    print("  the five largest single-trade flatterings (pips):", [round(x, 1) for x in worst])


if __name__ == "__main__":
    main()
    main(gap_pips=0.0)
    main(spike=False)
    main(gap_pips=0.0, spike=False)
