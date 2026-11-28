"""S1a 第二步。用法: python3 -I s1a_step2.py <inputs.npz> <out.json>"""
import sys,json,numpy as np,scipy.linalg as la
d=np.load(sys.argv[1]);t=d['t'];Y=d['y'];X=d['x'];ST=list(d['stations'])
idx=np.arange(0,len(t),5);t=t[idx];Y=Y[idx];X=X[idx];FS=10
UP=['P_x-30.00','P_x-25.00','P_x-20.00','P_x-15.00','P_x-10.00'];RACK=['R_y0']
def cols(gs):return [3*ST.index(f'{g}_z{z}')+c for g in gs for z in (1,3,6) for c in range(3)]
nb=5;blk=np.array_split(np.arange(len(t)),nb);gap=12*FS
def cv(x,lags):
    lags=np.array(lags);lo=max(0,lags.max());hi=max(0,-lags.min())
    xm=x.mean(0);xs=np.maximum(x.std(0),1e-12);Z=(x-xm)/xs
    yt_all=[];yp_all=[]
    for b in blk:
        te=b[(b>=lo+gap)&(b<len(t)-hi-gap)]if False else b[(b>=lo)&(b<len(t)-hi)]
        te=te[gap:-gap] if len(te)>2*gap else te
        trm=np.ones(len(t),bool);trm[b[0]-gap if b[0]>=gap else 0:min(len(t),b[-1]+gap+1)]=False
        tr=np.where(trm)[0];tr=tr[(tr>=lo)&(tr<len(t)-hi)]
        nv=int(.15*len(tr));va=tr[-nv:];tr2=tr[:-nv]
        F=lambda s:np.concatenate([Z[s-k] for k in lags],axis=1)
        Ftr=F(tr2);fm=Ftr.mean(0);fs=np.maximum(Ftr.std(0),1e-12);D=(Ftr-fm)/fs;ym=Y[tr2].mean(0)
        G=D.T@D;R=D.T@(Y[tr2]-ym);Fv=(F(va)-fm)/fs;best=None
        for a in (1e1,1e2,1e3,1e4):
            c=la.solve(G+a*np.eye(len(G)),R,assume_a='pos');e=np.mean((Fv@c+ym-Y[va])**2)
            if best is None or e<best[0]:best=(e,a)
        a=best[1];Ftr=F(tr);fm=Ftr.mean(0);fs=np.maximum(Ftr.std(0),1e-12);D=(Ftr-fm)/fs;ym=Y[tr].mean(0)
        c=la.solve(D.T@D+a*np.eye(D.shape[1]),D.T@(Y[tr]-ym),assume_a='pos')
        yp_all.append(((F(te)-fm)/fs)@c+ym);yt_all.append(Y[te])
    yt=np.concatenate(yt_all);yp=np.concatenate(yp_all)
    r2=1-((yt-yp)**2).sum(0)/((yt-yt.mean(0))**2).sum(0);return float(r2.mean())
step=2 # 0.2 s
C06=np.arange(0,61,step);C012=np.arange(0,121,step);N6=np.arange(-60,61,step);N12=np.arange(-120,121,step)
out={'single':{},'multi':{},'delta':{}}
for g in UP+RACK:
    x=X[:,cols([g])];r={k:cv(x,l) for k,l in [('C_0_6',C06),('C_0_12',C012),('NC_6',N6),('NC_12',N12)]}
    r['LIN_star']=max(r['C_0_12'],r['NC_6'],r['NC_12']);out['single'][g]=r;print(g,{k:round(v,3) for k,v in r.items()},flush=True)
xm=X[:,cols(UP+RACK)];out['multi']['C_0_6']=cv(xm,np.arange(0,61,5));print('multi54 C_0_6 (0.5s step)',round(out['multi']['C_0_6'],3),flush=True)
xu=X[:,cols(UP)];out['multi']['up5_C_0_6']=cv(xu,np.arange(0,61,5));print('up5 C_0_6',round(out['multi']['up5_C_0_6'],3),flush=True)
for g,x in [('P_x-10.00',X[:,cols(['P_x-10.00'])]),('P_x-30.00',X[:,cols(['P_x-30.00'])]),('multi54',xm)]:
    st=step if g!='multi54' else 5
    res={D:cv(x,np.arange(D*FS,D*FS+61,st)) for D in (0,1,2,3,4,6,8,10)};out['delta'][g]=res
    print(g,'R2(Δ)',{k:round(v,3) for k,v in res.items()},flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1)
