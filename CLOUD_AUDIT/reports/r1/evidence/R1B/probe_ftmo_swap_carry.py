"""R1-B receipt: how much FX carry survives FTMO's published swap table.

Input: FTMO's own symbol specification JSON (https://ftmo.com/wp-json/ftmo/symbols, the data source
of https://ftmo.com/en/symbols/, page modified 2026-09-02), fetched 2026-09-25. This is broker
documentation (swap points, commission, contract size), NOT price data. No price series is read.

Model (standard broker swap construction): swap_long = d - m, swap_short = -d - m, in swap points
per lot per night, where d is the fair carry (rate differential) and m >= 0 the markup per side.
Hence d = (L - S)/2 and m = -(L + S)/2. Both are in the same unit, so the fraction of fair carry
the positive-carry side keeps, (|d| - m)/|d|, is price-independent: no price level is needed.

Usage: python probe_ftmo_swap_carry.py ftmo_symbols.json
"""
import json
import sys

rows = json.load(open(sys.argv[1]))["data"]["symbols"]
out = []
for x in rows:
    if not x["active"] or x["assetClass"] not in ("Forex", "Exotics", "Metals CFD", "Cash CFD"):
        continue
    L, S = float(x["swapLong"]), float(x["swapShort"])
    d, m = (L - S) / 2.0, -(L + S) / 2.0
    kept = (abs(d) - m) / abs(d) if abs(d) > 1e-9 else float("nan")
    side = "long" if d > 0 else "short"
    out.append((x["assetClass"], x["code"], L, S, d, m, side, kept))
print(f"{'class':<11}{'symbol':<13}{'swapL':>9}{'swapS':>9}{'fair d':>9}{'markup m':>9}  carry side  kept")
for c, code, L, S, d, m, side, kept in out:
    print(f"{c:<11}{code:<13}{L:>9.2f}{S:>9.2f}{d:>9.2f}{m:>9.2f}  {side:<10}{kept:>6.0%}")
fx = [k for c, *_, k in out if c == "Forex"]
fx_sorted = sorted(fx)
print(f"\nG10 Forex (n={len(fx)}): median share of fair carry kept by the positive-carry side = "
      f"{fx_sorted[len(fx)//2]:.0%}; share with no positive carry left at all (kept <= 0) = "
      f"{sum(k <= 0 for k in fx)/len(fx):.0%}")
