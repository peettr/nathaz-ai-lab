import json,os,time,csv
import numpy as np, torch
# L26.15 copy: remove Colab-only /content/out import side effect; worker sets D/OUT.
D='/content/data'; OUT='/content/out'
TRAIN=['v7','P101_drive','P202_drive','P303_drive','P101_pre','P202_pre']; VAL=['P303_pre']; TEST=['A1_101']; CEIL=['A1_202','A1_303']
LAGS=np.arange(0,101,2)   # 0..20 s，每 0.4 s（5 Hz 下 2 帧）
HIST=100
def load(n):
    z=np.load(f'{D}/{n}.npz'); t=z['t']; keep=float(z['keep'])
    return dict(t=t,keep=keep,cp=z['cp'].astype('f4'),u=z['u'],r=z['qs_ratio'],idx=np.flatnonzero((t>=keep)&(np.arange(len(t))>=HIST)),prime_full=z['prime_full'],prime_low=z['prime_low'],tap_cols=z['tap_cols'])
def points():
    r=list(csv.DictReader(open(f'{D}/sync_surface_index.csv'))); X=[];N=[]
    nm={'windward':(-1,0,0),'leeward':(1,0,0),'roof':(0,0,1),'side_negative':(0,-1,0),'side_positive':(0,1,0)}
    for a in r:
        X.append(((float(a['z'])-221)*.15,(float(a['x'])-221)*.15,float(a['y'])*.15)); N.append(nm[a['face']])
    tc=list(csv.DictReader(open(f'{D}/sync_taps_index.csv')))
    for a in tc:
        x,y,z=float(a['x_m']),float(a['y_m']),float(a['z_m']); X.append((x,y,z))
        f=a['face']; N.append((-1,0,0) if abs(x+3)<1e-3 and f=='windward' else (1,0,0) if f=='leeward' else (0,0,1) if f=='roof' else (0,-1,0) if y<0 else (0,1,0))
    assert len(X)==8040; return (np.array(X)/6.).astype('f4'),np.array(N,'f4'),[a['tap_id'] for a in tc]
class Norm: pass
def fit_norm(runs):
    n=Norm(); U=np.concatenate([runs[k]['u'][runs[k]['idx']] for k in TRAIN]); n.um=U.mean(0); n.us=U.std(0)
    Y=np.concatenate([runs[k]['cp'][runs[k]['idx']] for k in TRAIN]); n.ym=Y.mean(0); n.ys=Y.std(0); assert (n.ys>0).all(); return n
def hist_feat(run,n,idx):
    u=(run['u']-n.um)/n.us; return np.stack([u[idx-l] for l in LAGS],2).reshape(len(idx),-1)   # (N,75*51)
def seq(run,n,idx):
    u=(run['u']-n.um)/n.us; return np.stack([u[i-HIST:i+1].T for i in idx])   # (N,75,101)
def rmse_corr(p,y):
    e=np.sqrt(((p-y)**2).mean(0)); a=p-p.mean(0); b=y-y.mean(0); c=(a*b).sum(0)/np.sqrt((a*a).sum(0)*(b*b).sum(0)+1e-20); return e,c
