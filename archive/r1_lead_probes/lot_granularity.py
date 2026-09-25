"""Lead check on PLAN_R1: can a ~$6k-$10k FTMO account hold the pooled trend book's positions?
Contract sizes are FTMO's own (wp-json/ftmo/symbols, fetched 2026-09-25). Prices and vols are
labelled ROUND ASSUMPTIONS (the same price levels R1-B assumed where it gave one). Minimum
volume 0.01 lot is an ASSUMPTION (the JSON has no min-volume field). Sizing is Carver's:
risk budget_i = capital * vol_target * weight_i * IDM; position at forecast f = budget/sigma * f/10.
Round-DOWN to whole lot steps, as ACIS does (GAP-P12D-57)."""
FX = [("EUR/USD",1.15,.07),("USD/JPY",1.0,.10),("GBP/USD",1.30,.08),("AUD/USD",.65,.10),("USD/CAD",1.0,.06),
      ("USD/CHF",1.0,.08),("EUR/GBP",1.15,.06),("EUR/JPY",1.15,.10),("GBP/JPY",1.30,.11),("AUD/JPY",.65,.12),
      ("EUR/CHF",1.15,.06),("EUR/AUD",1.15,.09),("CHF/JPY",1.25,.10)]      # (pair, base-ccy USD value, vol)
MIN_NOTIONAL = {p: 1000*b for p,b,_ in FX}                                   # 0.01 lot = 1,000 base units
VOL = {p: v for p,_,v in FX}
OTHER = {  # symbol: (contractSize, price in USD-equivalent, vol)   min notional = 0.01*cs*price
 "XAU/USD":(100,3500,.16),"XAG/USD":(5000,40,.28),
 "US500":(1,6500,.17),"US30":(1,45000,.16),"UK100":(1,9000*1.3,.14),"JP225":(10,38000/150,.20),
 "EU50":(1,5300*1.15,.18),"AUS200":(1,8500*.65,.14),"UKOIL":(100,70,.35),"NATGAS":(1000,3,.60)}
for s,(cs,px,v) in OTHER.items():
    MIN_NOTIONAL[s] = .01*cs*px; VOL[s] = v
CLASS = {**{p:"FX" for p,_,_ in FX}, "XAU/USD":"MET","XAG/USD":"MET", **{k:"IDX" for k in
         ("US500","US30","UK100","JP225","EU50","AUS200")}, "UKOIL":"NRG","NATGAS":"NRG"}
n_in = {c: sum(1 for k in CLASS if CLASS[k]==c) for c in set(CLASS.values())}
IDM = 2.45                                                                  # PLAN_R1: 2.4-2.5
for cap in (6000, 10000, 25000):
    for tgt in (.10, .20):
        dead, tally = [], {}
        for s,c in CLASS.items():
            w = .25 / n_in[c]
            avg_notional = cap*tgt*w*IDM / VOL[s]                            # at |forecast| = 10
            f_min = 10*MIN_NOTIONAL[s]/avg_notional                          # |f| needed for ONE min lot
            tally.setdefault(c, []).append(f_min)
            if f_min > 20: dead.append(s)
        summ = "  ".join(f"{c}: |f|>= {min(v):.0f}-{max(v):.0f}" for c,v in sorted(tally.items()))
        print(f"${cap:>6,} at {tgt:.0%} vol: never trades (needs |f|>20 cap): {len(dead):2d}/23 {dead}")
        print(f"          forecast needed for one min lot -> {summ}")
