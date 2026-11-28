"""S1a 第三步。用法: python3 -I s1a_step3.py <v7.npz> <v8.npz> <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
FS=10;UP=['P_x-30.00','P_x-25.00','P_x-20.00','P_x-15.00','P_x-10.00'];DIST={'P_x-30.00':27,'P_x-25.00':22,'P_x-20.00':17,'P_x-15.00':12,'P_x-10.00':7}
def load(p):
    d=np.load(p);idx=np.arange(0,len(d['t']),5);return d['y'][idx],d['x'][idx],list(d['stations'])
def cols(ST,gs):return [3*ST.index(f'{g}_z{z}')+c for g in gs for z in (1,3,6) for c in range(3)]
def cv(Y,x,lags,alphas=(1e1,1e2,1e3,1e4),pca=None):
    n=len(Y);blk=np.array_split(np.arange(n),5);gap=12*FS;lags=np.array(lags);lo=lags.max()
    yt_all=[];yp_all=[]
    for b in blk:
        te=b[b>=lo];te=te[gap:-gap]
        trm=np.ones(n,bool);trm[max(0,b[0]-gap):min(n,b[-1]+gap+1)]=False;tr=np.where(trm)[0];tr=tr[tr>=lo]
        xm=x[tr].mean(0);xs=np.maximum(x[tr].std(0),1e-12);Z=(x-xm)/xs
        if pca:
            _,_,Vt=np.linalg.svd(Z[tr],full_matrices=False);Z=Z@Vt[:pca].T
        F=lambda s:np.concatenate([Z[s-k] for k in lags],axis=1)
        nv=int(.15*len(tr));va=tr[-nv:];tr2=tr[:-nv]
        def fit(rows,a):
            Ft=F(rows);fm=Ft.mean(0);fs=np.maximum(Ft.std(0),1e-12);D=(Ft-fm)/fs;ym=Y[rows].mean(0)
            c=la.solve(D.T@D+a*np.eye(D.shape[1]),D.T@(Y[rows]-ym),assume_a='pos');return lambda s:((F(s)-fm)/fs)@c+ym
        best=min(alphas,key=lambda a:np.mean((fit(tr2,a)(va)-Y[va])**2))
        yp_all.append(fit(tr,best)(te));yt_all.append(Y[te])
    yt=np.concatenate(yt_all);yp=np.concatenate(yp_all)
    return float((1-((yt-yp)**2).sum(0)/((yt-yt.mean(0))**2).sum(0)).mean())
def thalf(r):
    ks=sorted(r);h=r[ks[0]]/2
    for a,b in zip(ks,ks[1:]):
        if r[b]<=h<r[a]:return a+(b-a)*(r[a]-h)/(r[a]-r[b])
    return None
out={}
DEL=[i/2 for i in range(21)]
for name,p in (('v7',sys.argv[1]),('v8diag',sys.argv[2])):
    Y,X,ST=load(p);res={}
    for g in UP:
        Uc=float(X[:,3*ST.index(f'{g}_z6')+2].mean()*120);tau=DIST[g]/Uc
        r={D:cv(Y,X[:,cols(ST,[g])],np.arange(int(round(D*FS)),int(round(D*FS))+61,2)) for D in DEL}
        th=thalf(r);Dc=min(DEL,key=lambda D:abs(D-(tau+2)))
        res[g]={'U_c':Uc,'tau_adv':tau,'R2':r,'T_half':th,'R2_at_tau+2':r[Dc],'Delta_used_for_tau+2':Dc,
                'a_ok':th is not None and abs(th-tau)<=1.0,'b_ok':r[Dc]<=0.05}
        print(name,g,'U=%.3f tau=%.2f Th=%s R2(0)=%.3f R2(%.1f)=%.3f'%(Uc,tau,None if th is None else round(th,2),r[0],Dc,r[Dc]),flush=True)
    r0=[res[g]['R2'][0] for g in UP];res['c_ok']=all(a<b for a,b in zip(r0,r0[1:]))
    out[name]=res
    json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
Y,X,ST=load(sys.argv[1])
xm=X[:,cols(ST,UP+['R_y0'])];L=np.arange(0,61,2);m={}
for k in (3,6,9,18):
    m[f'pca{k}']=cv(Y,xm,L,alphas=tuple(10.**k for k in range(1,8)),pca=k);print('pca',k,round(m[f'pca{k}'],3),flush=True)
    out['multi_v7']=m;json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
m['ridge_1e1_1e7']=cv(Y,xm,L,alphas=tuple(10.**k for k in range(1,8)));print('multi54 ridge to 1e7',round(m['ridge_1e1_1e7'],3),flush=True)
out['multi_v7']=m
json.dump(out,open(sys.argv[3],'w'),indent=1,default=str)
