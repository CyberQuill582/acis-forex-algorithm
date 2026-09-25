"""Master v2.21 §5.5 as written: per instrument, forecasts combined with fixed weights (equal risk across families),
x FDM, capped at +-20, into one target position with a 10% no-trade buffer. Pair groups 'stay all-or-none'.
Units: forecast units; the buffer is taken as 10% of the forecast-10 position (Carver's convention) = 1.0 unit."""
FDM, CAP, BUF = 1.5, 20.0, 1.0
W = {"TREND": 1/3, "BREAKOUT": 1/3, "PAIR": 1/3}
def net(f): return max(-CAP, min(CAP, FDM * sum(W[k] * v for k, v in f.items())))
before = {"EURUSD": {"TREND": 20, "BREAKOUT": 20, "PAIR": 0}, "USDCHF": {"TREND": 0, "BREAKOUT": 0, "PAIR": 0}}
after  = {"EURUSD": {"TREND": 20, "BREAKOUT": 20, "PAIR": +5}, "USDCHF": {"TREND": 0, "BREAKOUT": 0, "PAIR": -5}}
for inst in before:
    b, a = net(before[inst]), net(after[inst])
    print(f"pair ENTRY  {inst}: target {b:6.2f} -> {a:6.2f}  change {a-b:+.2f}  order={'YES' if abs(a-b) > BUF else 'no'}")
for inst in before:   # the coupling break / exit: pair forecast back to 0
    b, a = net(after[inst]), net(before[inst])
    print(f"pair EXIT   {inst}: target {b:6.2f} -> {a:6.2f}  change {a-b:+.2f}  order={'YES' if abs(a-b) > BUF else 'no'}")
