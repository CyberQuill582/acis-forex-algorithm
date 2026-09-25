# Lead P3: independent re-implementation of R1-A's P1 betting e-process from its PARTIAL's definition.
import numpy as np, sys
rng=np.random.default_rng(int(sys.argv[1]) if len(sys.argv)>1 else 7)
R=int(sys.argv[2]) if len(sys.argv)>2 else 1000
Y=10; T=252*Y; sig_ann=0.10; s=sig_ann/np.sqrt(252)
def draws(sr_ann, kind):
    mu=sr_ann*s/np.sqrt(252)*np.sqrt(252)/np.sqrt(252)  # daily mean = SR_ann*sigma_daily/sqrt(252)
    mu=sr_ann*s/np.sqrt(252)
    if kind=='gauss': z=rng.standard_normal((R,T))
    else: z=rng.standard_t(4,(R,T))/np.sqrt(2.0)   # unit-variance t4
    return mu+s*z
def eproc(r):
    x=np.maximum(r/(6*s),-1.0)
    n=np.arange(1,T+1)
    cs=np.cumsum(x,1); cs2=np.cumsum(x*x,1)
    m=np.zeros_like(x); v=np.zeros_like(x)
    m[:,1:]=cs[:,:-1]/n[:-1]; v[:,1:]=np.maximum(cs2[:,:-1]/n[:-1]-m[:,1:]**2,1e-12)
    lam=np.clip(m/(v+m*m),0,0.8); lam[:,:20]=0.0   # burn-in: no bet on the first 20 days
    logW=np.cumsum(np.log1p(lam*x),1)
    return logW
def tpeek(r):
    n=np.arange(1,T+1); cs=np.cumsum(r,1); cs2=np.cumsum(r*r,1)
    m=cs/n; sd=np.sqrt(np.maximum(cs2/n-m*m,1e-18)); t=m/(sd/np.sqrt(n))
    t[:,:20]=0
    return t
out={}
for kind in ('gauss','t4'):
    r=draws(0.0,kind); lw=eproc(r); tp=tpeek(r)
    out[f'null_{kind}_FPR_e20_10y']=float(np.mean(lw.max(1)>=np.log(20)))
    out[f'null_{kind}_tpeek_FPR_10y']=float(np.mean(tp.max(1)>=1.645))
for sr in (1.0,1.5,2.0):
    r=draws(sr,'t4'); lw=eproc(r); hit=lw>=np.log(20)
    first=np.where(hit.any(1),hit.argmax(1),10**9)
    out[f'SR{sr}_P(e20 by 3y)']=float(np.mean(first<756))
    out[f'SR{sr}_median_years_to_e20']=float(np.median(first)/252) if np.mean(first<10**9)>0.5 else '>10y'
for k,v in out.items(): print(k, v)
