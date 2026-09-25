"""EXTERNAL R1 audit probe: how often does the sign of the 12-month SPOT return (what ACIS's TSMOM signs,
canonical.py GAP-0073) differ from the sign of the 12-month EXCESS return (what MOP 2012 eq. 5 signs:
spot change + the interest differential of the forward)? Data: the repo's ECB reference rates and
overnight rates (read-only). Carry accrued ACT/365 on the overnight rates (policy rate for AUD)."""
import csv, math, bisect
from datetime import date, timedelta
M = r"C:/Users/USER/Documents/Private/ClaudeInsights/Knowledgevault/acis/data/macro/"
def load(fn, key=None):
    out = {}
    with open(M + fn, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if key and row[key[0]] != key[1]: continue
            out[date.fromisoformat(row["date"])] = float(row["value"] if "value" in row else row["eur_rate"])
    return out
fx = {c: {} for c in ("USD","JPY","GBP","AUD","CAD","CHF")}
with open(M + "ecb_exr.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        fx[row["currency"]][date.fromisoformat(row["date"])] = float(row["eur_rate"])
rates = {"USD": load("usd_effr.csv"), "JPY": load("jpy_tona.csv"), "GBP": load("gbp_sonia.csv"),
         "CHF": load("chf_saron.csv"), "CAD": load("cad_corra.csv"), "EUR": load("eur_dfr.csv"),
         "AUD": load("bis_policy.csv", ("area","AU"))}
def ffill(series):
    ks = sorted(series); return ks, [series[k] for k in ks]
RF = {c: ffill(s) for c, s in rates.items()}
def rate(c, d):
    ks, vs = RF[c]; i = bisect.bisect_right(ks, d) - 1
    return vs[i] if i >= 0 else vs[0]
def price(base, quote, d):  # units of quote per base, from EUR crosses
    b = 1.0 if base == "EUR" else fx[base].get(d); q = 1.0 if quote == "EUR" else fx[quote].get(d)
    if b is None or q is None: return None
    return q / b
days = sorted(fx["USD"])
pairs = [("EUR","USD"),("USD","JPY"),("GBP","USD"),("AUD","USD"),("USD","CAD"),("USD","CHF"),("EUR","GBP"),
         ("EUR","JPY"),("GBP","JPY"),("AUD","JPY"),("EUR","CHF"),("EUR","AUD"),("CHF","JPY"),("CAD","JPY")]
print("pair     obs  sign(spot12m)!=sign(excess12m)  median|carry12m|  median|spot12m|")
for base, quote in pairs:
    n = diff = 0; carries = []; spots = []
    for d in days:
        if d < date(2013,1,1): continue
        d0 = d - timedelta(days=365)
        j = bisect.bisect_left(days, d0)
        if j >= len(days): continue
        d0 = days[j]
        p1, p0 = price(base, quote, d), price(base, quote, d0)
        if not p1 or not p0: continue
        spot = math.log(p1 / p0)
        carry = 0.0; x = d0
        while x < d:
            carry += (rate(base, x) - rate(quote, x)) / 100.0 / 365.0; x += timedelta(days=1)
        n += 1; diff += (spot > 0) != (spot + carry > 0); carries.append(abs(carry)); spots.append(abs(spot))
    carries.sort(); spots.sort()
    print(f"{base}/{quote}  {n:5d}  {100*diff/n:6.1f}%                       {100*carries[n//2]:5.2f}%          {100*spots[n//2]:5.2f}%")
