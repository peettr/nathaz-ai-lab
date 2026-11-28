"""S3a-next 尾部（卡 §18）。用法: python3 -I s3a_tail.py <TS_dir> <SYN_dir> <out.json>"""
import sys,json,warnings,numpy as np
from scipy.stats import genpareto,kstest
warnings.filterwarnings('ignore')
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s3a_v2_analyze.py').read().split('out={}')[0].replace('TSD,SYD,OUT=sys.argv[1:4]','TSD,SYD,OUT=None,None,None'),'defs','exec'),ns)
rng=np.random.default_rng(0)
def fit(a,q):
    u=np.quantile(a,q);y=a[a>u]-u;c,_,s=genpareto.fit(y,floc=0);return float(c),float(s),float(u),y
def grp(W,lo=10,hi=np.inf):return [x for x in ns['rho'](W,lo,hi)]
out={};Wt,_=ns['windows'](sys.argv[1],'TS');Ws,_=ns['windows'](sys.argv[2],'SYN');per={'TS':grp(Wt),'SYN':grp(Ws)}
bs={}
for k,p in per.items():
    a=np.concatenate(p);c,s,u,y=fit(a,.9);ks=kstest(y,'genpareto',args=(c,0,s))
    qs=np.linspace(.05,.95,19);emp=np.quantile(y,qs);th=genpareto.ppf(qs,c,0,s)
    stab={str(q):fit(a,q)[0] for q in (.85,.9,.95)}
    b=[]
    for _ in range(500):
        A=np.concatenate([p[i] for i in rng.integers(0,len(p),len(p))]);b.append(fit(A,.9)[0])
    bs[k]=np.array(b)
    out[k]=dict(n=int(len(a)),u90=u,n_exc=int(len(y)),xi=c,sigma=s,xi_ci=[float(np.percentile(b,2.5)),float(np.percentile(b,97.5))],ks_p=float(ks.pvalue),qq_max_relerr=float(np.max(np.abs(emp-th)/np.maximum(th,1e-9))),xi_by_threshold=stab,thr_stable=abs(stab['0.85']-stab['0.95'])<=.15)
    print(k,out[k],flush=True)
d=bs['TS']-bs['SYN'];out['dxi']=dict(pt=out['TS']['xi']-out['SYN']['xi'],ci=[float(np.percentile(d,2.5)),float(np.percentile(d,97.5))]);print('dxi',out['dxi'])
out['strata']={}
for lo,hi in ((10,15),(15,20),(20,np.inf)):
    o={}
    for k,W in (('TS',Wt),('SYN',Ws)):
        p=grp(W,lo,hi);a=np.concatenate(p);c,s,u,y=fit(a,.9)
        if len(y)<50:o[k]=dict(n_exc=int(len(y)),note='超量不足 50');continue
        b=[fit(np.concatenate([p[i] for i in rng.integers(0,len(p),len(p))]),.9)[0] for _ in range(500)]
        o[k]=dict(n_exc=int(len(y)),xi=c,xi_ci=[float(np.percentile(b,2.5)),float(np.percentile(b,97.5))])
    out['strata'][f'{lo}-{hi}']=o;print(lo,hi,o,flush=True)
json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
