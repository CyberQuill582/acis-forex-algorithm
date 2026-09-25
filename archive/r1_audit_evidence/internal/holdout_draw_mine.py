import hashlib
SALT = "ACIS-R1-holdout-2026-09-25|"
fx = ["EUR/USD","USD/JPY","GBP/USD","AUD/USD","USD/CAD","USD/CHF","EUR/GBP","EUR/JPY","GBP/JPY","AUD/JPY","EUR/CHF","EUR/AUD","CHF/JPY","AUD/NZD","NZD/USD","CAD/JPY"]
metals = ["XAU/USD","XAG/USD","XCU/USD"]
idx = ["US500","US30","UK100","JP225","EU50","AUS200","GER40","US100"]
energy = ["UKOIL","NATGAS","USOIL"]
ondisk = {"EUR/USD","USD/JPY","GBP/USD","AUD/USD","USD/CHF","USD/CAD","EUR/GBP","XAU/USD"}
k = {"fx":3,"metal":1,"index":2,"energy":1}
stated = {"AUD/NZD","NZD/USD","CAD/JPY","XCU/USD","GER40","US100","USOIL"}
fmts = {
 "slash": lambda s: s,
 "noslash": lambda s: s.replace("/",""),
 "underscore": lambda s: s.replace("/","_"),
 "lower_noslash": lambda s: s.replace("/","").lower(),
}
def draw(fmt, forced_first=True):
    out=set()
    for cls,syms in (("fx",fx),("metal",metals),("index",idx),("energy",energy)):
        cand=[s for s in syms if s not in ondisk] if forced_first else syms
        order=sorted(cand,key=lambda s: hashlib.sha256((SALT+fmt(s)).encode()).hexdigest())
        out |= set(order[:k[cls]])
    return out
for name,f in fmts.items():
    for forced in (True,False):
        d=draw(f,forced)
        print(f"{name:14s} forced_excluded={forced!s:5s} match={d==stated} draw={sorted(d)}")
# Also metals with XAU only? XAU forced; metals candidates XAG,XCU
