# 事后诊断（Liang Hu 11-01 问“是不是数据太少”，看过留出之后写，不改判定）：只用岭回归，按入流数和探针数看趋势
import sys,json; sys.path.insert(0,'/content/code')
import numpy as np,torch
from common import *
dev='cuda'; R={k:load(k) for k in TRAIN+VAL+TEST}
GR={'seed1':['v7','P101_drive','P202_drive','P303_drive'],'seed101':['P101_pre'],'seed202':['P202_pre']}
pts=[f'R_y{y}_z{z}' for z in (1,3,6,12) for y in (-12,-6,0,6,12)]+[f'P_x-30.00_z{z}' for z in (1,3,6,12)]+['REF']
PS={'全部25点':list(range(25)),'排架20点':list(range(20)),'y=0排架4点':[pts.index(f'R_y0_z{z}') for z in (1,3,6,12)]}
SETS={'只v7(1入流,582 s)':['#v7'],'seed1含drive(1入流)':['seed1'],'seed101+202(2入流,180 s)':['seed101','seed202'],'seed1+101(2入流)':['seed1','seed101'],'seed1+202(2入流)':['seed1','seed202'],'全部(3入流)':['seed1','seed101','seed202']}
n0=fit_norm(R)
def F(run,idx,cols):
    u=(run['u']-n0.um)/n0.us; c=[p*3+j for p in cols for j in range(3)]; return np.stack([u[idx-l][:,c] for l in LAGS],2).reshape(len(idx),-1).astype('f8')
out=[]
v=R['P303_pre']; t=R['A1_101']; yv=v['cp'][v['idx']]; yt=t['cp'][t['idx']]; S=np.arange(8000,8040)
for pn,cols in PS.items():
    Xv=torch.tensor(F(v,v['idx'],cols),device=dev); Xt=torch.tensor(F(t,t['idx'],cols),device=dev)
    for sn,g in SETS.items():
        if pn!='全部25点' and sn not in('全部(3入流)','seed1含drive(1入流)'): continue
        ks=['v7'] if g==['#v7'] else sum((GR[x] for x in g),[])
        X=torch.tensor(np.concatenate([F(R[k],R[k]['idx'],cols) for k in ks]),device=dev); Yc=np.concatenate([R[k]['cp'][R[k]['idx']] for k in ks]); m=Yc.mean(0); Y=torch.tensor((Yc-m)/n0.ys,device=dev,dtype=torch.float64)
        w,V=torch.linalg.eigh(X.T@X); P=V.T@(X.T@Y); best=None
        for a in (1e2,1e3,1e4,1e5,1e6,1e7):
            B=V@(P/(w+a)[:,None]); e,c=rmse_corr((Xv@B).cpu().numpy().astype('f4')*n0.ys+m,yv)
            if best is None or e.mean()<best[0]: best=(float(e.mean()),float(c.mean()),a,B)
        e,c=rmse_corr((Xt@best[3]).cpu().numpy().astype('f4')*n0.ys+m,yt); em=np.sqrt(((m-yt)**2).mean(0))
        out.append(dict(probes=pn,train=sn,frames=len(Yc),alpha=best[2],val_rmse=round(best[0],4),val_corr=round(best[1],3),test_taps_rmse=round(float(e[S].mean()),4),test_taps_corr=round(float(c[S].mean()),3),test_surf_rmse=round(float(e[:8000].mean()),4),test_surf_corr=round(float(c[:8000].mean()),3),test_timemean_surf_rmse=round(float(em[:8000].mean()),4))); print(out[-1],flush=True); del X,Y,P,V
        torch.cuda.empty_cache()
        json.dump(out,open('/content/out/lc.json','w'),ensure_ascii=False,indent=1)
print('DONE',flush=True); open('/content/run.done','w').write('1')
