# Lead P3 of R1-B finding 1. Input: https://ftmo.com/wp-json/ftmo/symbols fetched 2026-09-25 to a scratch file
# (a firm's symbol specification, not price data; not committed). Usage: python3 repro_lead_ftmo_swaps.py <json>
import json, statistics, sys
def walk(x):
    if isinstance(x, dict):
        if 'swapLong' in x: yield x
        else:
            for v in x.values(): yield from walk(v)
    elif isinstance(x, list):
        for v in x: yield from walk(v)
act = [r for r in walk(json.load(open(sys.argv[1]))['data']) if r.get('active')]
by = {r['code']: r for r in act}
for c in ('EUR/USD', 'USD/JPY', 'XAU/USD', 'US500.cash', 'GER40.cash'):
    r = by[c]; print(c, {k: r.get(k) for k in ('swapLong', 'swapShort', 'swapType', 'commission', 'commissionType', 'leverageSwing')})
g10 = set('USD EUR JPY GBP AUD NZD CAD CHF NOK SEK'.split())
fx = [r for r in act if r.get('assetClass') == 'Forex' and set(r['code'].split('/')) <= g10]
keep, none = [], []
for r in fx:   # R1-B's symmetric-markup model: L = d - m, S = -d - m
    L, S = r['swapLong'], r['swapShort']; d = (L - S) / 2; m = -(L + S) / 2
    if max(L, S) <= 0: none.append(r['code'])
    keep.append(max(0.0, (abs(d) - m) / abs(d)) if d else 0.0)
print('active', len(act), 'G10 FX', len(fx), 'median keep', round(statistics.median(keep), 3), 'no positive side', len(none), none)
