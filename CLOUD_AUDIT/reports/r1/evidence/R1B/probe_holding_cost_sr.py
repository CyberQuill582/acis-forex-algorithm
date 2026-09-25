"""R1-B receipt: FTMO swap markup as an annual holding cost, and in Sharpe units per year held.

UNIT CONVERSION ONLY. Price levels and annual volatilities below are ROUND ASSUMPTIONS typed by the
author (order-of-magnitude, labelled), NOT data read from any price series. Results scale linearly:
halve the assumed price and the %-cost doubles. Swap points come from FTMO's own symbol JSON
(https://ftmo.com/wp-json/ftmo/symbols, fetched 2026-09-25). Point = 10**-digits.
Markup per side m = -(swapLong + swapShort)/2 (see probe_ftmo_swap_carry.py). Charged ~365 nights/yr
(weekend charged as a triple night), which is the standard CFD convention (assumption).
Cost in SR units per year held at full size = m% / vol%.
Usage: python probe_holding_cost_sr.py ftmo_symbols.json
"""
import json
import sys

# symbol: (assumed price, assumed annual vol %)  -- ROUND ASSUMPTIONS, not data
ASSUMED = {
    "EUR/USD": (1.15, 7), "USD/JPY": (150, 10), "GBP/USD": (1.33, 8), "AUD/USD": (0.65, 10),
    "USD/CAD": (1.38, 6), "USD/CHF": (0.80, 8), "NZD/USD": (0.59, 10), "EUR/GBP": (0.86, 6),
    "EUR/JPY": (172, 10), "GBP/JPY": (200, 11), "AUD/JPY": (98, 13), "EUR/CHF": (0.93, 6),
    "EUR/AUD": (1.77, 9), "AUD/NZD": (1.10, 6), "CAD/JPY": (109, 11), "CHF/JPY": (188, 10),
    "XAU/USD": (3500, 16), "XAG/USD": (40, 28), "XPT/USD": (1300, 25),
    "US500.cash": (6500, 17), "US100.cash": (24000, 22), "US30.cash": (46000, 16),
    "GER40.cash": (23500, 19), "UK100.cash": (9200, 14), "JP225.cash": (45000, 22),
    "EU50.cash": (5400, 19), "US2000.cash": (2400, 23),
}
rows = {x["code"]: x for x in json.load(open(sys.argv[1]))["data"]["symbols"] if x["active"]}
print(f"{'symbol':<12}{'m %/yr':>8}{'long %/yr':>10}{'short %/yr':>11}{'vol %':>7}{'m/vol SR':>9}")
for code, (price, vol) in ASSUMED.items():
    x = rows[code]
    pt = 10 ** -x["digits"]
    L = x["swapLong"] * pt / price * 365 * 100
    S = x["swapShort"] * pt / price * 365 * 100
    m = -(L + S) / 2
    print(f"{code:<12}{m:>8.2f}{L:>10.2f}{S:>11.2f}{vol:>7}{m / vol:>9.2f}")
