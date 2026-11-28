"""S3a-2 分析（卡 §11）。用法: python3 -I s3a_asos_analyze.py <asos1min_dir> <out.json>"""
import sys,os,glob,json,csv,numpy as np
D=sys.argv[1];rng=np.random.default_rng(0);L=3
def load(p):
    s=[];g=[]
    for r in csv.DictReader(open(p)):
        try:s.append(float(r['sknt']));g.append(float(r['gust_sknt']))
        except:s.append(np.nan);g.append(np.nan)
    return np.array(s),np.array(g)
def windows(pref):
    W=[];drop=0
    for p in sorted(glob.glob(os.path.join(D,pref+'_*.csv'))):
        s,g=load(p)
        if len(s)<300 or np.mean(np.isfinite(s)&np.isfinite(g))<0.8:drop+=1;continue
        W.append((os.path.basename(p),s,g))
    return W,drop
def rows(W,T):
    R=[]
    for wi,(n,s,g) in enumerate(W):
        nb=len(s)//T;U=np.array([np.nanmean(s[i*T:(i+1)*T]) for i in range(nb)]);G=np.array([np.nanmax(g[i*T:(i+1)*T]) if np.isfinite(g[i*T:(i+1)*T]).any() else np.nan for i in range(nb)])
        for t in range(L,nb):
            v=[wi,G[t],U[t],U[t-1],U[t-2],U[t-3]]
            if np.all(np.isfinite(v)):R.append(v)
    return np.array(R)
def cvpred(R,nw):
    fold=np.arange(nw)%5;rng.shuffle(fold);f=fold[R[:,0].astype(int)];y=R[:,1];P={k:np.zeros(len(y)) for k in ('M','MZ','g')}
    for k in range(5):
        tr=f!=k;te=f==k
        for nm,c in (('M',[2]),('MZ',[2,3,4,5])):
            w=np.linalg.lstsq(np.c_[np.ones(tr.sum()),R[tr][:,c]],y[tr],rcond=None)[0];P[nm][te]=np.c_[np.ones(te.sum()),R[te][:,c]]@w
        P['g'][te]=R[te,2]*y[tr].sum()/R[tr,2].sum()
    return P
def r2(y,p):return 1-((y-p)**2).sum()/((y-y.mean())**2).sum()
def stats(R,P,idx=None):
    m=np.ones(len(R),bool) if idx is None else np.concatenate([np.where(R[:,0]==i)[0] for i in idx])
    y=R[m,1] if idx is None else R[m,1];M,MZ,g=(r2(y,P[k][m]) for k in ('M','MZ','g'))
    return dict(M=M,MZ=MZ,g=g,d_mem=MZ-M,noise=1-MZ,g_loss=MZ-g,n=int(len(y)))
out={}
Wts,dts=windows('TS');Wsy,dsy=windows('SYN');out['windows']=dict(TS=len(Wts),TS_drop=dts,SYN=len(Wsy),SYN_drop=dsy)
print(out['windows'],flush=True)
for T in (10,20,30):
    o={}
    Rt=rows(Wts,T);Rs=rows(Wsy,T);Pt=cvpred(Rt,len(Wts));Ps=cvpred(Rs,len(Wsy))
    o['TS']=stats(Rt,Pt);o['SYN']=stats(Rs,Ps);o['D']=o['TS']['d_mem']-o['SYN']['d_mem']
    bs=[]
    for b in range(1000):
        it=rng.integers(0,len(Wts),len(Wts));is_=rng.integers(0,len(Wsy),len(Wsy))
        bs.append(stats(Rt,Pt,it)['d_mem']-stats(Rs,Ps,is_)['d_mem'])
    o['D_ci']=[float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))];out[T]=o
    print(T,'TS',{k:round(v,4) for k,v in o['TS'].items()},'\n   SYN',{k:round(v,4) for k,v in o['SYN'].items()},'\n   D=%.4f CI=[%.4f,%.4f]'%(o['D'],*o['D_ci']),flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1)
