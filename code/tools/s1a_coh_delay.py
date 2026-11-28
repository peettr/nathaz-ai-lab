"""S1a 相干上界的时延修正（补充读数）：先按训练段互相关找输入整体最优时滞（0–6 s），把输入平移后再估多重相干；nperseg 512/1024 两档。
用法: python3 -I s1a_coh_delay.py <inputs.npz> <out.json>"""
import sys,json,numpy as np
from scipy.signal import csd
d=np.load(sys.argv[1]);t=d['t'];y=d['y'];X=d['x'];ST=list(d['stations']);FS=50
G={k:[f'{k}_z{z}' for z in (1,3,6)] for k in ['P_x-30.00','P_x-25.00','P_x-20.00','P_x-15.00','P_x-10.00','R_y0']}
tr=t<462;out={}
for g,st in G.items():
    x=X[:,[3*ST.index(s)+c for s in st for c in range(3)]]; x=x-x.mean(0)
    # 整体时滞：使 y 各测点与 x 各分量互相关平方和最大（训练段）
    best=(-1,0)
    for L in range(0,301,5):
        yy=y[L:][tr[L:]];xx=x[:len(x)-L][tr[L:]]
        c=np.corrcoef(np.c_[yy,xx].T)[:11,11:];s=(c**2).sum()
        if s>best[0]:best=(s,L)
    L=best[1];yy=y[L:];xx=x[:len(x)-L]
    res={}
    for nper in (512,1024):
        n=xx.shape[1];Sxx=np.empty((nper//2+1,n,n),complex)
        for i in range(n):
            for k in range(n): f,Sxx[:,i,k]=csd(xx[:,i],xx[:,k],fs=FS,nperseg=nper)
        nd=2*len(xx)//nper-1;vals=[]
        for j in range(11):
            yj=yy[:,j]-yy[:,j].mean();_,Syy=csd(yj,yj,fs=FS,nperseg=nper);Syy=Syy.real
            Syx=np.stack([csd(yj,xx[:,i],fs=FS,nperseg=nper)[1] for i in range(n)],axis=1)
            g2=np.clip(np.array([(Syx[m].conj()@np.linalg.solve(Sxx[m],Syx[m])).real/Syy[m] for m in range(len(f))]),0,1)
            gbc=np.clip((g2-n/nd)/(1-n/nd),0,1)
            vals.append((1-np.sum(Syy*(1-g2))/np.sum(Syy),1-np.sum(Syy*(1-gbc))/np.sum(Syy)))
        v=np.array(vals);res[nper]=dict(n_d=nd,R2_raw=float(v[:,0].mean()),R2_bc=float(v[:,1].mean()))
    out[g]=dict(lag_s=L/FS,**{f'nper{k}':v for k,v in res.items()})
    print(g,'lag_s',L/FS,{k:(round(v['R2_raw'],3),round(v['R2_bc'],3),v['n_d']) for k,v in res.items()},flush=True)
json.dump(out,open(sys.argv[2],'w'),indent=1)
