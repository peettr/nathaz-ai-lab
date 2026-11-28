"""S3a v2 分析（卡 §16）。用法: python3 -I s3a_v2_analyze.py <TS_dir> <SYN_dir> <out.json>"""
import sys,os,glob,csv,json,datetime as dt,numpy as np
TSD,SYD,OUT=sys.argv[1:4];L=3;rng=np.random.default_rng(0);NB=1000
def load(p):
    rows=list(csv.DictReader(open(p)))
    if not rows:return None
    t=[dt.datetime.strptime(r['valid(UTC)'],'%Y-%m-%d %H:%M') for r in rows];t0=min(t)
    s=np.full(361,np.nan);g=np.full(361,np.nan)
    for ti,r in zip(t,rows):
        i=int((ti-t0).total_seconds()//60)
        if 0<=i<361:
            try:s[i]=float(r['sknt'])
            except:pass
            try:g[i]=float(r['gust_sknt'])
            except:pass
    return s,g
def windows(d,pref):
    W=[];why={'empty':0,'lowvalid':0}
    for p in sorted(glob.glob(os.path.join(d,pref+'_*.csv'))):
        x=load(p)
        if x is None:why['empty']+=1;continue
        s,g=x;ok=np.isfinite(s)&np.isfinite(g)
        if ok.mean()<0.8:why['lowvalid']+=1;continue
        s=s.copy();g=g.copy();s[~ok]=np.nan;g[~ok]=np.nan;W.append((os.path.basename(p),s,g))
    return W,why
def blocks(s,g,T):
    nb=len(s)//T;U=np.full(nb,np.nan);G=np.full(nb,np.nan)
    for i in range(nb):
        ss=s[i*T:(i+1)*T];gg=g[i*T:(i+1)*T]
        if np.isfinite(ss).sum()>=0.8*T:U[i]=np.nanmean(ss);G[i]=np.nanmax(gg)
    return U,G
def rows(W,T):
    R=[]
    for wi,(n,s,g) in enumerate(W):
        U,G=blocks(s,g,T)
        for t in range(L,len(U)):
            v=[wi,G[t],U[t],U[t-1],U[t-2],U[t-3]]
            if np.all(np.isfinite(v)):R.append(v)
    return np.array(R)
def cv(R,nw,seed):
    r=np.random.default_rng(seed);fold=np.arange(nw)%5;r.shuffle(fold);f=fold[R[:,0].astype(int)];y=R[:,1];P={k:np.zeros(len(y)) for k in ('M','MZ','g')}
    for k in range(5):
        tr=f!=k;te=f==k
        for nm,c in (('M',[2]),('MZ',[2,3,4,5])):
            w=np.linalg.lstsq(np.c_[np.ones(tr.sum()),R[tr][:,c]],y[tr],rcond=None)[0];P[nm][te]=np.c_[np.ones(te.sum()),R[te][:,c]]@w
        P['g'][te]=R[te,2]*y[tr].sum()/R[tr,2].sum()
    return P
r2=lambda y,p:float(1-((y-p)**2).sum()/((y-y.mean())**2).sum())
def stats(R,nw,seed=0):
    P=cv(R,nw,seed);y=R[:,1];M,MZ,g=(r2(y,P[k]) for k in ('M','MZ','g'))
    return dict(M=M,MZ=MZ,g=g,d_mem=MZ-M,noise=1-MZ,g_loss=MZ-g,n=int(len(y)),ghat=float(y.sum()/R[:,2].sum())),y-P['MZ']
def resample(R,nw):
    idx=rng.integers(0,nw,nw);parts=[];
    for j,i in enumerate(idx):
        sub=R[R[:,0]==i].copy();sub[:,0]=j;parts.append(sub)
    return np.concatenate(parts)
def rho(W,lo=10,hi=np.inf):
    per=[]
    for n,s,g in W:
        U,G=blocks(s,g,10);m=np.isfinite(U)&np.isfinite(G)&(U>=lo)&(U<hi);per.append(G[m]/U[m])
    return per
def q(a,p):return float(np.quantile(a,p)) if len(a) else float('nan')
out={}
Wt,wt=windows(TSD,'TS');Ws,ws=windows(SYD,'SYN');out['windows']=dict(TS=len(Wt),TS_drop=wt,SYN=len(Ws),SYN_drop=ws);print(out['windows'],flush=True)
for T in (10,20,30):
    Rt=rows(Wt,T);Rs=rows(Ws,T);st,et=stats(Rt,len(Wt));ss,es=stats(Rs,len(Ws));o=dict(TS=st,SYN=ss,D=st['d_mem']-ss['d_mem'],N=st['noise']-ss['noise'])
    if T==10:
        bD=[];bN=[]
        for b in range(NB):
            a,_=stats(resample(Rt,len(Wt)),len(Wt),b+1);c,_=stats(resample(Rs,len(Ws)),len(Ws),b+1);bD.append(a['d_mem']-c['d_mem']);bN.append(a['noise']-c['noise'])
        o['D_ci']=[float(np.percentile(bD,2.5)),float(np.percentile(bD,97.5))];o['N_ci']=[float(np.percentile(bN,2.5)),float(np.percentile(bN,97.5))]
        # B' residual tail by window
        rt=[et[Rt[:,0]==i] for i in range(len(Wt))];rs=[es[Rs[:,0]==i] for i in range(len(Ws))]
        o['e_q99']=dict(TS=q(np.concatenate(rt),.99),SYN=q(np.concatenate(rs),.99),TS_q50=q(np.concatenate(rt),.5),SYN_q50=q(np.concatenate(rs),.5))
        be=[q(np.concatenate([rt[i] for i in rng.integers(0,len(rt),len(rt))]),.99)-q(np.concatenate([rs[i] for i in rng.integers(0,len(rs),len(rs))]),.99) for _ in range(NB)]
        o['e_dq99']=dict(pt=o['e_q99']['TS']-o['e_q99']['SYN'],ci=[float(np.percentile(be,2.5)),float(np.percentile(be,97.5))])
    out[T]=o;print(T,json.dumps({k:(v if not isinstance(v,dict) else {kk:round(vv,4) if isinstance(vv,float) else vv for kk,vv in v.items()}) for k,v in o.items()},default=str),flush=True)
def rho_cmp(lo,hi):
    pt,ps=rho(Wt,lo,hi),rho(Ws,lo,hi);a=np.concatenate(pt);b=np.concatenate(ps);o=dict(nTS=int(len(a)),nSYN=int(len(b)))
    if len(a)<200 or len(b)<200:o['note']='样本不足';return o
    o.update(TS_q50=q(a,.5),SYN_q50=q(b,.5),TS_q99=q(a,.99),SYN_q99=q(b,.99),TS_cv=float(a.std()/a.mean()),SYN_cv=float(b.std()/b.mean()))
    b99=[];b50=[]
    for _ in range(NB):
        A=np.concatenate([pt[i] for i in rng.integers(0,len(pt),len(pt))]);B=np.concatenate([ps[i] for i in rng.integers(0,len(ps),len(ps))])
        b99.append(q(A,.99)-q(B,.99));b50.append(q(A,.5)-q(B,.5))
    o['dq99']=dict(pt=o['TS_q99']-o['SYN_q99'],ci=[float(np.percentile(b99,2.5)),float(np.percentile(b99,97.5))]);o['dq50']=dict(pt=o['TS_q50']-o['SYN_q50'],ci=[float(np.percentile(b50,2.5)),float(np.percentile(b50,97.5))]);return o
out['rho_all']=rho_cmp(10,np.inf);out['rho_strata']={f'{lo}-{hi}':rho_cmp(lo,hi) for lo,hi in ((10,15),(15,20),(20,np.inf))}
print(json.dumps({k:out[k] for k in ('rho_all','rho_strata')},indent=1,default=str))
json.dump(out,open(OUT,'w'),indent=1,default=str)
