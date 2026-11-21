"""S1a 第一个读数。用法: python3 -I s1a_bounds.py <inputs.npz> <metrics_v4b.json> <out_dir>"""
import sys,json,numpy as np,scipy.linalg as la
from scipy.signal import csd
from pathlib import Path
d=np.load(sys.argv[1]); v4=json.load(open(sys.argv[2])); out=Path(sys.argv[3]); out.mkdir(exist_ok=True)
if (out/'s1a_bounds.json').exists(): raise FileExistsError
t=d['t'];y=d['y'];X=d['x'];ST=list(d['stations'])
GROUPS={k:[f'{k}_z{z}' for z in (1,3,6)] for k in ['P_x-30.00','P_x-25.00','P_x-20.00','P_x-15.00','P_x-10.00','R_y0']}
FS=50; ids=np.arange(400,len(t)-400)
tr=ids[(t[ids]<462)&(ids%5==0)]; va=ids[(t[ids]>=462)&(t[ids]<522)&(ids%5==0)]; te=ids[t[ids]>=522]
te_v4=np.arange(300,len(t)); te_v4=te_v4[t[te_v4]>=522]
def r2(yt,yp):
    return 1-((yt-yp)**2).sum(0)/((yt-yt.mean(0))**2).sum(0)
def ridge(x,lags):
    xm=x[tr].mean(0);xs=np.maximum(x[tr].std(0),1e-12);Z=(x-xm)/xs
    F=lambda s:np.concatenate([Z[s-k] for k in lags],axis=1)
    Ftr,Fv,Fte=F(tr),F(va),F(te);fm=Ftr.mean(0);fs=np.maximum(Ftr.std(0),1e-12)
    D=(Ftr-fm)/fs;ym=y[tr].mean(0);G=D.T@D;R=D.T@(y[tr]-ym);best=None
    for a in (1e1,1e2,1e3,1e4):
        c=la.solve(G+a*np.eye(len(G)),R,assume_a='pos');e=np.mean((((Fv-fm)/fs)@c+ym-y[va])**2)
        if best is None or e<best[0]: best=(e,a,c)
    e,a,c=best;p=((Fte-fm)/fs)@c+ym
    return r2(y[te],p),np.sqrt(((p-y[te])**2).mean(0)),a
def coh(x):
    nper=512;n=x.shape[1];zs=lambda s:(s-s.mean())
    Sxx=np.empty((nper//2+1,n,n),complex)
    for i in range(n):
        for k in range(n): f,Sxx[:,i,k]=csd(zs(x[:,i]),zs(x[:,k]),fs=FS,nperseg=nper)
    nd=2*len(x)//nper-1;p=n;res=[]
    for j in range(y.shape[1]):
        f,Syy=csd(zs(y[:,j]),zs(y[:,j]),fs=FS,nperseg=nper);Syy=Syy.real
        Syx=np.stack([csd(zs(y[:,j]),zs(x[:,i]),fs=FS,nperseg=nper)[1] for i in range(n)],axis=1)
        g=np.array([ (Syx[m].conj()@np.linalg.solve(Sxx[m],Syx[m])).real/Syy[m] for m in range(len(f))])
        g=np.clip(g,0,1);gbc=np.clip((g-p/nd)/(1-p/nd),0,1)
        res.append((1-np.sum(Syy*(1-g))/np.sum(Syy),1-np.sum(Syy*(1-gbc))/np.sum(Syy)))
    return np.array(res),nd
LC=np.arange(61)*5; LNC=np.arange(-60,61)*5
vt=y[te_v4].var(0)
rows={}
for g,st in GROUPS.items():
    cols=[3*ST.index(s)+c for s in st for c in range(3)]; x=X[:,cols]
    r2c,rmc,ac=ridge(x,LC); r2n,rmn,an=ridge(x,LNC); ch,nd=coh(x)
    m=v4['families'][g]['metrics']
    fir=1-np.array(m['linear_FIR']['rmse'])**2/vt; cnn=1-np.array(m['CNN']['rmse'])**2/vt
    rows[g]=dict(distance_m=v4['families'][g]['distance_to_face_m'],
      R2_causal=float(r2c.mean()),R2_noncausal=float(r2n.mean()),R2_coh_raw=float(ch[:,0].mean()),R2_coh_bc=float(ch[:,1].mean()),n_d=nd,
      R2_v4b_FIR=float(fir.mean()),R2_v4b_CNN=float(cnn.mean()),RMSE_causal=float(rmc.mean()),RMSE_noncausal=float(rmn.mean()),
      RMSE_v4b_FIR=float(np.mean(m['linear_FIR']['rmse'])),RMSE_v4b_CNN=float(np.mean(m['CNN']['rmse'])),alpha_c=ac,alpha_nc=an,
      per_tap=dict(R2_causal=r2c.tolist(),R2_noncausal=r2n.tolist(),R2_coh_bc=ch[:,1].tolist(),R2_v4b_FIR=fir.tolist(),R2_v4b_CNN=cnn.tolist()))
    r=rows[g];print(f"{g:10s} d={r['distance_m']:5.2f} C={r['R2_causal']:.3f} NC={r['R2_noncausal']:.3f} COHraw={r['R2_coh_raw']:.3f} COHbc={r['R2_coh_bc']:.3f} FIRv4b={r['R2_v4b_FIR']:.3f} CNNv4b={r['R2_v4b_CNN']:.3f} | RMSE C={r['RMSE_causal']:.4f} NC={r['RMSE_noncausal']:.4f} FIR={r['RMSE_v4b_FIR']:.4f} CNN={r['RMSE_v4b_CNN']:.4f}",flush=True)
json.dump(dict(note='S1a first reading; see card S1a_命题卡_v0.md',test_samples=len(te),test_samples_v4b=len(te_v4),rows=rows),open(out/'s1a_bounds.json','w'),indent=1,ensure_ascii=False)
