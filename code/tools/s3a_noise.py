"""S3a 噪声项刻画（卡 §13）。用法: python3 -I s3a_noise.py <asos1min_dir> <out.json>"""
import sys,json,warnings,numpy as np
warnings.filterwarnings('ignore')
sys_argv=sys.argv[:];sys.argv=['x',sys_argv[1],'/dev/null']
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s3a_asos_analyze.py').read().split('out={}')[0],'defs','exec'),ns)
from scipy.stats import ks_2samp
rng=np.random.default_rng(1);out={}
def rho(W):
    per=[]
    for n,s,g in W:
        nb=len(s)//10;r=[]
        for i in range(nb):
            u=np.nanmean(s[i*10:(i+1)*10]);gg=g[i*10:(i+1)*10]
            if np.isfinite(u) and u>=10 and np.isfinite(gg).any():r.append(np.nanmax(gg)/u)
        if r:per.append(np.array(r))
    return per
P={k:rho(ns['windows'](k)[0]) for k in ('TS','SYN')}
for k,per in P.items():
    a=np.concatenate(per);out[k]=dict(windows=len(per),n=int(len(a)),q50=float(np.quantile(a,.5)),q90=float(np.quantile(a,.9)),q99=float(np.quantile(a,.99)),cv=float(a.std()/a.mean()))
a=np.concatenate(P['TS']);b=np.concatenate(P['SYN']);out['KS']=float(ks_2samp(a,b).statistic)
bs={'q50':[],'q99':[]}
for _ in range(1000):
    A=np.concatenate([P['TS'][i] for i in rng.integers(0,len(P['TS']),len(P['TS']))]);B=np.concatenate([P['SYN'][i] for i in rng.integers(0,len(P['SYN']),len(P['SYN']))])
    for q,k in ((.5,'q50'),(.99,'q99')):bs[k].append(np.quantile(A,q)-np.quantile(B,q))
for k in bs:out['d'+k]=dict(pt=out['TS'][k]-out['SYN'][k],ci=[float(np.percentile(bs[k],2.5)),float(np.percentile(bs[k],97.5))])
print(json.dumps(out,indent=1));json.dump(out,open(sys_argv[2],'w'),indent=1)
