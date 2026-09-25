import hashlib
SALT = "ACIS-R1-holdout-2026-09-25|"
for syms in (["XAG/USD","XCU/USD"],["XAG","XCU"],["XAGUSD","XCUUSD"],["XAG_USD","XCU_USD"]):
    o=sorted(syms,key=lambda s: hashlib.sha256((SALT+s).encode()).hexdigest())
    print(syms, "-> held out:", o[0])
for syms in (["USD/CAD"],):pass
# FX: margin of the FX draw under slash — print the full sorted order
fx = ["EUR/JPY","GBP/JPY","AUD/JPY","EUR/CHF","EUR/AUD","CHF/JPY","AUD/NZD","NZD/USD","CAD/JPY"]
for f in (lambda s:s, lambda s:s.replace("/","")):
    print([s for s in sorted(fx,key=lambda s: hashlib.sha256((SALT+f(s)).encode()).hexdigest())])
