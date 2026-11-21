"""S3a-T 留出检验（卡 §20）。用法: python3 -I s3a_tail_holdout.py <r4_dir> <r3_TS_dir> <out.json>"""
import sys,json,warnings,numpy as np
from scipy.stats import genpareto
warnings.filterwarnings('ignore')
ns={};exec(compile(open(__file__.rsplit('/',1)[0]+'/s3a_v2_analyze.py').read().split('out={}')[0].replace('TSD,SYD,OUT=sys.argv[1:4]','TSD,SYD,OUT=None,None,None'),'defs','exec'),ns)
rng=np.random.default_rng(0)
def xi(a,q):
    u=np.quantile(a,q);y=a[a>u]-u;return float(genpareto.fit(y,floc=0)[0]),int(len(y))
out={}
for name,d in (('r4_holdout',sys.argv[1]),('r3_ref',sys.argv[2])):
    W,why=ns['windows'](d,'TS');o={'windows':len(W),'drop':why}
    for lo,hi,lab in ((10,15,'10-15'),(15,20,'15-20'),(20,np.inf,'20+')):
        p=[x for x in ns['rho'](W,lo,hi)];a=np.concatenate(p);oo={'n_blocks':int(len(a))}
        for q in (.9,.95):
            x,ne=xi(a,q)
            if ne<30:oo[str(q)]=dict(n_exc=ne,note='样本不足');continue
            b=[xi(np.concatenate([p[i] for i in rng.integers(0,len(p),len(p))]),q)[0] for _ in range(500)]
            oo[str(q)]=dict(n_exc=ne,xi=x,ci=[float(np.percentile(b,2.5)),float(np.percentile(b,97.5))])
        o[lab]=oo
    out[name]=o;print(name,json.dumps(o,default=str),flush=True)
h=out['r4_holdout'];a=h['10-15'].get('0.9',{});b=h['20+'].get('0.9',{})
ja=None if 'ci' not in a else a['ci'][0]>0;jb=None if 'ci' not in b else b['ci'][1]<=0.05
out['judge']=dict(a=ja,b=jb);print('judge',out['judge'])
json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
