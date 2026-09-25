import numpy as np
rng=np.random.default_rng(11); L=np.array([0.05,0.1,0.2,0.4,0.8]); D=252; sd=0.10/np.sqrt(D)
def W(x,lams=L):
    x=np.maximum(x,-1.0); return np.exp(np.cumsum(np.log1p(lams[None,None,:]*x[:,:,None]),axis=1)).mean(axis=2)
mu=1.0*sd/np.sqrt(D); r=sd*rng.standard_normal((1500,10*D))
for thr in (5,20):
    w=W((mu-r)/(6*sd)); hit=w>=thr; a=hit.any(1); i=np.where(a,hit.argmax(1),10**9)
    print(f"6sigma scale, thr {thr}: 1y={np.mean(i<D):.2f} median={np.median(i)/D:.1f}y")
# alternative: scale by 1 sigma instead of 6 (not what the text says)
for thr in (20,):
    w=W((mu-r)/(1*sd)); hit=w>=thr; a=hit.any(1); i=np.where(a,hit.argmax(1),10**9)
    print(f"1sigma scale, thr {thr}: 1y={np.mean(i<D):.2f} median={np.median(i)/D:.1f}y")
