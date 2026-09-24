"""Does whole-path demeaning (synthetic_market._returns) tilt a 63/126/252-day TSMOM vote negative?
Daily-resolution analogue: n weekdays of iid N(0, 0.005) returns, demeaned over the whole path
(as the generator does), then the ACIS vote (sign of sum of signs of 63/126/252-day returns),
held 2 days (the 48 h cap), non-overlapping, from day 260 on. Compares with the undemeaned path."""
import numpy as np, sys
rng = np.random.default_rng(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
R, n, sd = 4000, 704, 0.005          # 985 calendar days ~ 704 weekdays (the ladder's span)
res = {True: [], False: []}
for _ in range(R):
    r = rng.normal(0, sd, n)
    for demean in (True, False):
        x = r - r.mean() if demean else r
        lp = np.concatenate([[0.0], np.cumsum(x)])
        tot = []
        for t in range(260, n - 2, 2):
            v = sum(np.sign(lp[t] - lp[t - L]) for L in (63, 126, 252))
            if v == 0: continue
            tot.append(np.sign(v) * (lp[t + 2] - lp[t]))
        res[demean].append(np.sum(tot))
for k, v in res.items():
    v = np.array(v)
    print(f"demeaned={k}: mean path P&L (log units) {v.mean():+.5f}  se {v.std(ddof=1)/np.sqrt(len(v)):.5f}  "
          f"sd {v.std(ddof=1):.5f}  t={v.mean()/(v.std(ddof=1)/np.sqrt(len(v))):+.1f}  frac<0 {np.mean(v<0):.3f}")
