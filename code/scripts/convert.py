#!/usr/bin/env python3
"""L26.15 路径 b：只读 R21 运行根，转成 5 Hz 小文件。不写原运行根。numpy only."""
import json,sys,time
from pathlib import Path
import numpy as np
R=Path('/groups/kareem/[用户]/DWT/silsoe_lbm/runs'); OUT=Path(sys.argv[1]); OUT.mkdir(exist_ok=True)
g=lambda p:str(next(R.glob(p)))
RUNS={ # name:(inflow group, role, [prefixes], keep_from_s)
 'v7':('seed1','train',[str(R/'silsoe600_v7/S600v7_seg1'),str(R/'silsoe600_v7/S600v7_seg2')],60.),
 'P101_drive':('seed1','train',[g('sync_r3/P101_drive*')+'/sync'],360.),
 'P202_drive':('seed1','train',[g('sync_r3/P202_drive*')+'/sync'],360.),
 'P303_drive':('seed1','train',[g('sync_r3/P303_drive*')+'/sync'],360.),
 'P101_pre':('seed101','train',[g('sync_r3/P101_pre*')+'/sync'],60.),
 'P202_pre':('seed202','train',[g('sync_r3/P202_pre*')+'/sync'],60.),
 'P303_pre':('seed303','val',[g('sync_r3/P303_pre*')+'/sync'],60.),
 'A1_101':('seed777','test',[g('sync_r4/A1_101*')+'/sync'],360.),
 'A1_202':('seed777','ceiling',[g('sync_r4/A1_202*')+'/sync'],360.),
 'A1_303':('seed777','ceiling',[g('sync_r4/A1_303*')+'/sync'],360.)}
CHECK_ONLY={'Bpre_101':g('sync_r4/Bpre_101*')+'/sync','Bpre_202':g('sync_r4/Bpre_202*')+'/sync','Bdrive_101':g('sync_r4/Bdrive_101*')+'/sync','Bdrive_202':g('sync_r4/Bdrive_202*')+'/sync','A2_101':g('sync_r4/A2_101*')+'/sync'}
FS=50.;DEC=10;CHK='R_y0_z6_uz'
PTS=[f'R_y{y}_z{z}' for z in (1,3,6,12) for y in (-12,-6,0,6,12)]+[f'P_x-30.00_z{z}' for z in (1,3,6,12)]+['REF']
def lowpass(x,fc,w,dt=1/FS):
    "零相位 FFT 低通：<=fc-w 增益 1，fc-w..fc+w 余弦过渡，>=fc+w 为 0。x (Nt,...)"
    n=x.shape[0]; f=np.fft.rfftfreq(n,dt); H=np.where(f<=fc-w,1.,np.where(f>=fc+w,0.,.5*(1+np.cos(np.pi*(f-fc+w)/(2*w)))))
    m=x.mean(0,keepdims=True); X=np.fft.rfft(x-m,axis=0); X*=H.reshape((-1,)+(1,)*(x.ndim-1))
    return np.fft.irfft(X,n=n,axis=0)+m
def lp_chunks(x,fc,w):
    y=np.empty(x.shape,'f4')
    for i in range(0,x.shape[1],400): y[:,i:i+400]=lowpass(x[:,i:i+400].astype('f8'),fc,w)
    return y
def read_csv(p,names):
    hdr=open(p).readline().strip().split(','); idx=[hdr.index(n) for n in names]
    return np.loadtxt(p,delimiter=',',skiprows=1,usecols=idx,dtype='f8',ndmin=2)
def probes(prefs):
    cols=['t_s','REF_rho']+[f'{p}_{c}' for p in PTS for c in ('ux','uy','uz')]
    return np.concatenate([read_csv(p+'_probes.csv',cols) for p in prefs])
meta={}; chk={}
surf_idx=None
for name,(grp,role,prefs,keep) in RUNS.items():
    t0=time.time(); P=probes(prefs); t=P[:,0]; assert np.allclose(np.diff(t),.02,atol=1e-3),(name,np.diff(t).max())
    rho_list=[]; 
    for p in prefs:
        a=np.fromfile(p+'_surface_rho.bin',dtype='f4'); assert a.size%8000==0; rho_list.append(a.reshape(-1,8000))
    tap_cols=None
    taps=[]
    for p in prefs:
        h=open(p+'_taps.csv').readline().strip().split(','); tap_cols=h[2:]; taps.append(read_csv(p+'_taps.csv',tap_cols).astype('f4'))
    rho=np.concatenate(rho_list); taps=np.concatenate(taps); assert len(rho)==len(t)==len(taps),(name,len(rho),len(t),len(taps)); assert taps.shape[1]==40
    rr=P[:,1]; c=np.r_[0.,np.cumsum(rr)]; i=np.arange(len(rr)); lo=np.maximum(0,i-99); ref=(c[i+1]-c[lo])/(i-lo+1)  # 同 R21 smooth（2 s 尾随）
    U=P[:,2:].reshape(len(t),len(PTS),3); UR=U[:,-1]; U2=(UR**2).sum(1)
    k=t>=keep; q=float(np.mean(.5*rr[k]*U2[k])); assert q>0
    all_rho=np.concatenate([rho,taps],axis=1); del rho,taps
    cp=(all_rho-ref[:,None].astype('f4'))/3./q; del all_rho
    full=lp_chunks(cp,4.165,.2); prime_full=full[k].std(0); del full
    low=lp_chunks(cp,1.,.1); del cp
    prime_low=low[k].std(0); mean_cp=low[k].mean(0)
    u_in=lowpass(U.reshape(len(t),-1),2.,.2)*120.  # m/s（u_lat 0.05 <-> 6 m/s）
    ratio=lowpass(U2,1.,.1)/U2[k].mean()
    np.savez_compressed(OUT/f'{name}.npz',t=t[::DEC].astype('f8'),keep=keep,cp=low[::DEC].astype('f2'),u=u_in[::DEC].astype('f4'),qs_ratio=ratio[::DEC].astype('f4'),
        prime_full=prime_full,prime_low=prime_low,mean_cp=mean_cp,q=q,U_ref_mean=float(120*np.sqrt(U2[k].mean())),tap_cols=np.array(tap_cols))
    meta[name]=dict(group=grp,role=role,keep_from_s=keep,t0=float(t[0]),t1=float(t[-1]),n=len(t),q=q,U_ref_rms_ms=float(120*np.sqrt(U2[k].mean())),meanCp_win=float(mean_cp[1600:3200].mean()),nan=int(np.isnan(low).sum()),sec=round(time.time()-t0,1))
    idx=PTS.index('R_y0_z6'); chk[name]=(t,U[:,idx,2]*120.)  # 流向 = uz
    print(name,meta[name],flush=True); del low
for n,p in CHECK_ONLY.items():
    A=read_csv(p+'_probes.csv',['t_s',CHK]); chk[n]=(A[:,0],A[:,1]*(120. if n[0]!='B' else 60.))
def xc(a,b):
    a=lowpass(a,1.,.1)[::10];b=lowpass(b,1.,.1)[::10];a=(a-a.mean())/a.std();b=(b-b.mean())/b.std();n=len(a)+len(b)-1;F=np.fft.rfft
    c=np.fft.irfft(F(a,n)*np.conj(F(b,n)),n); lag=np.r_[0:len(a),-len(b)+1:0]
    ov=np.minimum(len(a),len(a)-lag)-np.maximum(0,-lag)
    ov=np.where(lag>=0,np.minimum(len(a)-lag,len(b)),np.minimum(len(b)+lag,len(a)))
    m=ov>=300; r=c[m]/ov[m]; j=np.argmax(abs(r)); return float(r[j]),float(lag[m][j]/5),int(ov[m][j])
pairs=[];names=list(chk)
for i,x in enumerate(names):
    for y in names[i+1:]:
        r,l,o=xc(chk[x][1],chk[y][1]); pairs.append(dict(a=x,b=y,max_r=round(r,3),lag_s=l,overlap_frames=o))
json.dump(dict(meta=meta,pairs=pairs,pts=PTS),open(OUT/'meta.json','w'),ensure_ascii=False,indent=1)
print('DONE',flush=True)
