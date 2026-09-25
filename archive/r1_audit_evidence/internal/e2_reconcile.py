import numpy as np
rng=np.random.default_rng(7); L=np.array([0.05,0.1,0.2,0.4,0.8]); D=252; sd=0.10/np.sqrt(D)
def W(x):
    x=np.maximum(x,-1.0); return np.exp(np.cumsum(np.log1p(L[None,None,:]*x[:,:,None]),axis=1)).mean(axis=2)
for claim_sr in (1.0, 0.5, 0.4, 0.25):   # mu_claim expressed as an annual Sharpe
    mu=claim_sr*sd/np.sqrt(D); r=sd*rng.standard_normal((1500,10*D))
    w=W((mu-r)/(6*sd)); hit=w>=20; a=hit.any(1); i=np.where(a,hit.argmax(1),10**9)
    print(f"claim SR {claim_sr}: kill by 1y={np.mean(i<D):.2f} 3y={np.mean(i<3*D):.2f} median_years={np.median(i)/D if np.mean(a)>0.5 else '>10'}")
