"""C8 v2.21: 'Positions round down to the venue's lot step exactly as execution does'.
ACIS-06 C-EXE-6: execution sends ORDER quantities in whole lot steps, rounded DOWN.
On a reduction the two rules differ, so the RSIM book and the executed book diverge."""
from decimal import Decimal as D, ROUND_DOWN
step = D("0.01")
def floor_pos(x): return (abs(x) / step).to_integral_value(ROUND_DOWN) * step * (1 if x >= 0 else -1)
for cur, tgt in ((D("0.10"), D("0.057")), (D("-0.10"), D("-0.057")), (D("0.00"), D("0.057"))):
    rsim = floor_pos(tgt)                                         # 'positions round down'
    order = (abs(tgt - cur) / step).to_integral_value(ROUND_DOWN) * step
    execd = cur + order * (1 if tgt > cur else -1)                # C-EXE-6: order rounded down
    print(f"current {cur:+} target {tgt:+}: RSIM position {rsim:+}  executed position {execd:+}  "
          f"{'SAME' if rsim == execd else 'DIFFERENT (executed holds more exposure)'}")
