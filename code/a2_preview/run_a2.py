#!/usr/bin/env python3
"""A2 bounded, causal probe→Cp preview and constrained linear AMD proxy. No source writes."""
import os, csv, json, time, argparse
from pathlib import Path
import numpy as np
import scipy.linalg as la
from scipy.signal import iirnotch, filtfilt, welch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
FS=50; TAPS=[f'V{i}' for i in range(2,7)]+[f'H{i}' for i in range(1,7)]
STATIONS={f'P_x{x}':[f'P_x{x}_z{z}' for z in (1,3,6)] for x in ('-30.00','-25.00','-20.00','-15.00','-10.00')}
STATIONS['R_y0']=[f'R_y0_z{z}' for z in (1,3,6)]
DIST={s:(-3-float(s[3:]) if s.startswith('P_x') else 24.1) for s in STATIONS}
HORIZONS=(0,.5,1,2,3,5,8); LAGS=np.arange(61)*5

def read(path,cols):
    with open(path) as f: hdr=next(csv.reader(f))
    if not set(cols).issubset(hdr):raise ValueError(f'missing CSV columns {path}')
    a=np.loadtxt(path,delimiter=',',skiprows=1,usecols=[hdr.index(c) for c in cols],ndmin=2)
    if not np.all(np.isfinite(a)):raise ValueError('nonfinite CSV')
    return a

def load(root):
    ps=sum(STATIONS.values(),[])
    pc=['step','t_s']+[f'{p}_{v}' for p in ps for v in ('ux','uy','uz')]+['REF_rho','REF_ux','REF_uy','REF_uz']
    tc=['step','t_s']+TAPS
    p=np.concatenate([read(root/f'S600v7_seg{s}_probes.csv',pc) for s in (1,2)])
    a=np.concatenate([read(root/f'S600v7_seg{s}_taps.csv',tc) for s in (1,2)])
    if len(a)!=32100 or not np.array_equal(a[:,0],p[:,0]) or not np.all(np.diff(a[:,0])==16):raise ValueError('seam')
    idx=np.arange(len(p)); rho=p[:,pc.index('REF_rho')];cs=np.r_[0.,np.cumsum(rho)]
    ref=(cs[idx+1]-cs[np.maximum(0,idx-99)])/(idx-np.maximum(0,idx-99)+1)
    keep=a[:,1]>=42; t=a[keep,1];a=a[keep];p=p[keep];ref=ref[keep]
    if len(t)!=30001 or np.max(np.abs(t-a[:,0]*.00125))>1e-4:raise ValueError('cadence')
    vel=p[:,[pc.index('REF_'+v) for v in ('ux','uy','uz')]]
    q=float(np.mean(.5*p[t<462,pc.index('REF_rho')]*np.sum(vel[t<462]**2,axis=1)))
    y=(a[:,2:]-ref[:,None])/(3*q)
    x={s:p[:,[pc.index(f'{v}_{c}') for v in group for c in ('ux','uy','uz')]] for s,group in STATIONS.items()}
    return t,x,y,q

def filtered(y):
    z=y.copy()
    # Offline acoustic-removal diagnostic, never controller's actual force signal.
    for freq in (.27,.52,.95):
        b,a=iirnotch(freq,20,FS);z=filtfilt(b,a,z,axis=0)
    return z

def model(x,y,t):
    # v4b PCA 9 instantaneous channels and causal 61 lags; validation-only ridge choice.
    n=len(t);ids=np.arange(300,n-400);tr=ids[(t[ids]<462)&(ids%5==0)]
    va=ids[(t[ids]>=462)&(t[ids]<522)&(ids%5==0)]
    te=ids[(t[ids]>=522)&(t[ids]<634)] # seam-free and every tau+history inside same segment
    xm=x[tr].mean(0);xs=np.maximum(x[tr].std(0),1e-8)
    standardized=((x-xm)/xs).astype('float32');_,_,vt=np.linalg.svd(standardized[tr],full_matrices=False)
    z=standardized@vt[:9].T
    def design(ix):return np.concatenate([z[ix-l] for l in LAGS],axis=1).astype('float64')
    A=design(tr);V=design(va);E=design(te);am=A.mean(0);ast=np.maximum(A.std(0),1e-8)
    A=(A-am)/ast;V=(V-am)/ast;E=(E-am)/ast
    g=A.T@A; eye=np.eye(g.shape[0]); yy=np.mean(y[tr],axis=0)
    out={}; setup={}; preds={}
    for h in HORIZONS:
        shift=round(FS*h);Y=y[tr+shift];Yv=y[va+shift];Ye=y[te+shift]
        ym=Y.mean(0);rhs=A.T@(Y-ym)
        options=[]
        for alpha in (100.,1000.,10000.):
            coef=la.solve(g+alpha*eye,rhs,assume_a='pos',check_finite=False)
            options.append((float(np.sqrt(np.mean((V@coef+ym-Yv)**2))),alpha,coef))
        loss,alpha,coef=min(options,key=lambda v:v[0]);pred=E@coef+ym
        rm=np.sqrt(np.mean((pred-Ye)**2,axis=0)); corr=[float(np.corrcoef(pred[:,j],Ye[:,j])[0,1]) if np.std(pred[:,j])>1e-10 else None for j in range(11)]
        mean_pred=np.tile(ym,(len(te),1)); persist=y[te]
        rmse=float(np.mean(rm)); meanrm=float(np.mean(np.sqrt(np.mean((mean_pred-Ye)**2,axis=0))))
        persrm=float(np.mean(np.sqrt(np.mean((persist-Ye)**2,axis=0)))) if h else None
        out[str(h)]={'corr':float(np.mean(corr)) if None not in corr else None,'rmse':rmse,'mean_baseline_rmse':meanrm,'persistence_rmse':persrm,'skill_mean':1-rmse/meanrm,'skill_persistence':1-rmse/persrm if h else None,'tap_corr':corr,'ridge_alpha':alpha,'validation_rmse':loss}
        preds[h]=pred
    return te,out,preds

def weights():
    # Separable additive interpolation C(y,z)=V(z)+H(y)-C_center; projection only, no 2D pressure field.
    source=Path('./21_Digital_Wind_Tunnel/desktop_repo/fluidx3d/inflow/taps.csv')
    with open(source) as f: rows={r['tap_id']:r for r in csv.DictReader(f)}
    ys=np.array([float(rows[s]['y_m']) for s in TAPS[5:]]);zs=np.array([float(rows[s]['z_m']) for s in TAPS[:5]])
    def integral_weights(coords):
        bound=np.r_[0,(coords[1:]+coords[:-1])/2,6] if coords.min()>=0 else np.r_[-3,(coords[1:]+coords[:-1])/2,3]
        # Piecewise constant Voronoi area: every tap represents its clipped cell.
        return np.diff(bound)
    wy=integral_weights(ys)/6;wz=integral_weights(zs)/6
    w=np.r_[wz,wy]
    # Exact interpolation of vertical profile at z=3.01, estimated from V3 and V4.
    j=np.searchsorted(zs,3.01)-1
    w[j]-=(zs[j+1]-3.01)/(zs[j+1]-zs[j]);w[j+1]-=(3.01-zs[j])/(zs[j+1]-zs[j])
    return w,ys,zs,source

def controller(force,preview,dt,freq,limit,amplitude=1.0):
    # Units: one physical simulation second, nondimensional displacement, M=1; exact ZOH of linear plant.
    m=.05; damping=.02; wr=2*np.pi*freq; k=wr**2;c=2*damping*wr
    A=np.array([[0,1,0,0],[-k,-c,0,0],[0,0,0,1],[k,c,0,0]])
    B=np.array([[0],[-1],[0],[1+1/m]]); E=np.array([[0],[1],[0],[-1]])
    augment=np.zeros((6,6));augment[:4,:4]=A;augment[:4,4:5]=B;augment[:4,5:6]=E
    transition=la.expm(augment*dt); Ad=transition[:4,:4];Bd=transition[:4,4:5];Ed=transition[:4,5:6]
    Q=np.diag([wr**2,1,wr**2*20,.2]); R=np.array([[.08]])
    P=la.solve_discrete_are(Ad,Bd,Q*dt,R*dt); H=R*dt+Bd.T@P@Bd
    K=la.solve(H,Bd.T@P@Ad);Acl=Ad-Bd@K
    kernel=[]; vec=P@Ed
    for j in range(int(8/dt)+1):
        kernel.append(float(la.solve(H,Bd.T@vec)[0,0]));vec=Acl.T@vec
    n=len(force);state=np.zeros(4); hist=np.empty((n,4));us=np.empty(n);impacts=np.zeros(n);hit=0;umax=2*np.std(force)*amplitude
    for i in range(n):
        # preview[i,j] is the prediction issued at time i for F(i+j), no future observations.
        u=float(-K@state)-float(np.dot(kernel[:preview.shape[1]],preview[i]))
        u=float(np.clip(u,-umax,umax)); state=Ad@state+Bd[:,0]*u+Ed[:,0]*force[i]
        if abs(state[2])>limit:
            hit+=1;state[2]=np.sign(state[2])*limit
            if state[2]*state[3]>0:
                # Inelastic hard stop: internal impact transfers relative momentum to the structure.
                impacts[i]=m/(1+m)*state[3]/dt;state[1]+=impacts[i]*dt;state[3]=0
        hist[i]=state;us[i]=u
    acc=force-c*hist[:,1]-k*hist[:,0]-us+impacts
    def rms(v):return float(np.sqrt(np.mean(v*v)))
    return {'x_rms':rms(hist[:,0]),'x_peak':float(np.max(np.abs(hist[:,0]))),'acc_rms':rms(acc),'acc_peak':float(np.max(np.abs(acc))),'stroke_peak':float(np.max(np.abs(hist[:,2]))),'control_rms':rms(us),'hit_fraction':hit/n,'u_clip':umax},kernel

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    for item in ('results.md','metrics.json','preview.png','control.png'):
        if (a.out/item).exists():raise FileExistsError(item)
    tic=time.monotonic();t,x,y,q=load(a.input);w,ys,zs,source=weights()
    print('loaded',len(t),'q',q,'weight',w,'sum',w.sum(),flush=True)
    allres={}; pred={}
    for label,yy in [('raw',y),('acoustic_notch',filtered(y))]:
        allres[label]={};pred[label]={}
        for station in STATIONS:
            ids,score,p=model(x[station],yy,t)
            allres[label][station]=score;pred[label][station]=p
            print(label,station,'corr0',score['0']['corr'],'corr2',score['2']['corr'],flush=True)
    # Exclusive test window: 522..634 s, +8 s horizon reaches 642 s; no training/validation target in test.
    te=np.arange(300,len(t)-400);te=te[(t[te]>=522)&(t[te]<634)]
    F=y@w; F=F-np.mean(F[t<462]); force=F[te];dt=.1;ctrl_idx=np.arange(0,len(te),5)
    truth=force[ctrl_idx]; valid=ctrl_idx[ctrl_idx+400<len(force)]
    valid=valid[:]; truth=force[valid]; controllers={}
    f,wfreq=welch(F[t<462]-np.mean(F[t<462]),FS,nperseg=4096)
    peak=float(f[(f>.08)&(f<1.2)][np.argmax(wfreq[(f>.08)&(f<1.2)])]);freqs={'near_spectral_peak':peak,'off_resonance':max(1.4,2*peak)}
    for case,freq in freqs.items():
        for lname,limit in [('loose',.12),('tight',.025)]:
            key=f'{case}/{lname}';controllers[key]={}
            for station in STATIONS:
                controllers[key][station]={}
                signals={h:pred['raw'][station][h]@w-np.mean(F[t<462]) for h in HORIZONS}
                # Single issue-time vector 0...h forecasts interpolated only across independently fitted causal horizons.
                for horizon in HORIZONS:
                    steps=int(horizon/dt)+1
                    preview=np.stack([np.interp(np.arange(steps)*dt,HORIZONS,[signals[h][i] for h in HORIZONS]) for i in valid],axis=0)
                    feed,_=controller(truth,preview,dt,freq,limit)
                    controllers[key][station][str(horizon)]=feed
            zeros=np.zeros((len(truth),1));feedback,_=controller(truth,zeros,dt,freq,limit)
            perfect=np.stack([force[np.minimum(valid+j*5,len(force)-1)] for j in range(81)],axis=1)
            oracle,_=controller(truth,perfect,dt,freq,limit)
            controllers[key]['feedback']=feedback;controllers[key]['perfect_8s']=oracle
            print('control',key,'fb_acc',feedback['acc_rms'],'oracle_acc',oracle['acc_rms'],flush=True)
    payload={'provenance':'single-realization Silsoe v7 LBM; source hashes in ../lbm_transfer/provenance.json','q_train_lattice':q,'window_s':[42,642],'split_s':{'train':[48,462],'validation':[462,522],'test_issue':[522,634],'test_target_max':642},'time_step_s':.02,'cp':'(rho_tap - causal REF density 100 samples)/(3 * mean training 0.5*rho_REF*|u_REF|²)','filter':'raw and offline zero-phase sequential iirnotch Q=20 at 0.27/0.52/0.95 Hz on Cp only','weights':dict(zip(TAPS,map(float,w))),'distances_m':DIST,'spectral_peak_Hz':peak,'frequencies_Hz':freqs,'preview':allres,'control':controllers,'runtime_s':time.monotonic()-tic}
    (a.out/'metrics.json').write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for station in STATIONS:
        for j,label in enumerate(('raw','acoustic_notch')):
            axes[j].plot(HORIZONS,[allres[label][station][str(h)]['corr'] for h in HORIZONS],marker='o',label=f'{station} ({DIST[station]:g} m)')
    for ax,label in zip(axes,('raw Cp','offline acoustic-notch Cp')):
        ax.set(title=label,xlabel='Preview lead τ (s)',ylabel='Mean tap correlation',ylim=(0,1));ax.grid(alpha=.3);ax.legend(fontsize=8)
    fig.savefig(a.out/'preview.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained');base=controllers['near_spectral_peak/tight']['feedback']
    for station in STATIONS:
        vals=[controllers['near_spectral_peak/tight'][station][str(h)] for h in HORIZONS]
        axes[0].plot(HORIZONS,[1-v['acc_rms']/base['acc_rms'] for v in vals],marker='o',label=station)
        axes[1].plot(HORIZONS,[v['stroke_peak']/base['stroke_peak'] for v in vals],marker='o',label=station)
    axes[0].axhline(.1,color='k',ls='--');axes[0].set(ylabel='Acceleration RMS reduction vs feedback',xlabel='Preview lead τ (s)')
    axes[1].axhline(1,color='k',ls='--');axes[1].set(ylabel='Peak stroke / feedback',xlabel='Preview lead τ (s)')
    for ax in axes:ax.grid(alpha=.3);ax.legend(fontsize=7)
    fig.savefig(a.out/'control.png',dpi=150);plt.close(fig)
    print('DONE runtime_s',payload['runtime_s'],flush=True)
if __name__=='__main__':main()
