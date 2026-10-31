#!/usr/bin/env python3
"""事后 10-28；仅在冻结 main.csv 逐值复现后运行。按 UTC issue 日整块，种子 230604。"""
import json, math, hashlib
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import rankdata, hypergeom
from sklearn.metrics import roc_auc_score
ROOT=Path('/content/m6'); OUT=ROOT/'postreview'; OUT.mkdir(exist_ok=True)
CFG=json.loads((ROOT/'config.json').read_text()); DRAWS=CFG['bootstrap_days']; SEED=CFG['bootstrap_seed']; LEADS=CFG['leads_min']
METHODS=['P','R','F','F_D','B','B_D','T0','D2','B_R','B_T0','B_D2']
EDGES=[('R','F'),('F','F_D'),('F','B'),('F_D','B_D'),('B','B_D'),('R','T0'),('R','D2'),('T0','D2'),('B_R','B_D2'),('B_T0','B_D2')]
K=(.01,.05,.10)
def auc(y,p):
    pos=y.sum(); n=len(y)
    return (rankdata(p).dot(y)-pos*(pos+1)/2)/(pos*(n-pos)) if 0<pos<n else np.nan

def topk(yy, event, pred, daycopy, sites):
    n=len(yy); strong=np.flatnonzero(yy); pairs=np.stack([daycopy[strong],event[strong]],axis=1)
    _,eid=np.unique(pairs,axis=0,return_inverse=True)
    ans={}
    site_indices=[np.flatnonzero(sites==s) for s in np.unique(sites)]
    for m,score in pred.items():
        pooled=np.argsort(-score,kind='stable')
        site_orders=[ix[np.argsort(-score[ix],kind='stable')] for ix in site_indices]
        for k in K:
            for scope in ('pooled','within_site'):
                alarm=np.zeros(n,dtype=bool)
                if scope=='pooled':alarm[pooled[:max(1,math.ceil(n*k))]]=True
                else:
                    for ix,order in zip(site_indices,site_orders):alarm[order[:max(1,math.ceil(len(ix)*k))]]=True
                captured=np.zeros(int(eid.max())+1,dtype=bool);np.logical_or.at(captured,eid,alarm[strong])
                ans[m,k,scope]=(float(alarm[strong].mean()),float(captured.mean()),len(captured))
    return ans

def ci(v):return (float(np.nanquantile(v,.025)),float(np.nanquantile(v,.975)))
def load(d):return pd.read_parquet(ROOT/f'test_predictions_delay{d}.parquet')

def check_parity():
    frozen=pd.read_csv(ROOT/'frozen_main.csv').sort_values(['delay_h','lead_min','metric']).reset_index(drop=True)
    rebuilt=pd.read_csv(ROOT/'rebuild_core/rebuilt_main.csv').sort_values(['delay_h','lead_min','metric']).reset_index(drop=True)
    assert frozen.shape==rebuilt.shape and frozen[['delay_h','lead_min','metric','n','days']].equals(rebuilt[['delay_h','lead_min','metric','n','days']])
    cols=['point','lo','hi'];delta=(frozen[cols]-rebuilt[cols]).abs().to_numpy().max()
    assert np.isfinite(delta) and delta<=1e-12,('MAIN_MISMATCH',delta)
    (OUT/'parity.json').write_text(json.dumps({'rows':len(frozen),'max_abs_difference':float(delta),'tolerance':1e-12,'passed':True},indent=2))
    print('PARITY_OK',len(frozen),delta,flush=True)

def main():
    check_parity()
    aucrows=[]; top=[]; groups=[]; per_site=[]; rel=[]
    for d in (3,4,6):
        df=load(d)
        if d!=4:continue
        for L,g0 in df.groupby('lead_min'):
            g=g0.reset_index(drop=True);y=g.strong.to_numpy(bool);ev=g.event_id.to_numpy();sites=g.site.to_numpy();dates=g.issue_utc.dt.date.to_numpy();days=np.unique(dates)
            rng=np.random.default_rng(SEED+L+40000); blocks=[np.flatnonzero(dates==day) for day in days]
            predictions={m:g[m].to_numpy(float) for m in METHODS}
            point_auc={m:float(np.mean([auc(y[sites==s],predictions[m][sites==s]) for s in np.unique(sites)])) for m in METHODS}
            # Point events preserve the original event across adjacent calendar days.
            point_top=topk(y,ev,predictions,np.zeros(len(y),dtype=int),sites)
            event_sizes=g.loc[g.strong].groupby(['site','event_id']).size()
            random_exp={}
            for k in K:
                for scope in ('pooled','within_site'):
                    if scope=='pooled':
                        kk=max(1,math.ceil(len(g)*k));random_exp[k,scope]=(kk/len(g),float(np.mean(hypergeom.sf(0,len(g),event_sizes.to_numpy(),kk))))
                    else:
                        numer=0.;evprob=[]
                        for s in np.unique(sites):
                            ns=int((sites==s).sum());ks=max(1,math.ceil(ns*k));ssizes=event_sizes.loc[s].to_numpy()
                            numer+=int(y[sites==s].sum())*ks/ns
                            evprob.extend(hypergeom.sf(0,ns,ssizes,ks).tolist())
                        random_exp[k,scope]=(numer/y.sum(),float(np.mean(evprob)))
            site_draw={m:np.empty(DRAWS) for m in METHODS}; top_draw={(m,k,scope,t):np.empty(DRAWS) for m in METHODS for k in K for scope in ('pooled','within_site') for t in (0,1)}
            for b in range(DRAWS):
                pick=rng.integers(0,len(days),len(days));idx=np.concatenate([blocks[i] for i in pick]);copies=np.repeat(np.arange(len(pick)),[len(blocks[i]) for i in pick]); yy=y[idx]; ss=sites[idx];ee=ev[idx]
                pred={m:v[idx] for m,v in predictions.items()}
                for m in METHODS:
                    site_draw[m][b]=np.nanmean([auc(yy[ss==s],pred[m][ss==s]) for s in np.unique(sites)])
                t=topk(yy,ee,pred,copies,ss)
                for m in METHODS:
                    for k in K:
                        for scope in ('pooled','within_site'):top_draw[m,k,scope,0][b],top_draw[m,k,scope,1][b]=t[m,k,scope][:2]
                if (b+1)%200==0:print('BOOT',L,b+1,flush=True)
            for m in METHODS:
                lo,hi=ci(site_draw[m]);aucrows.append((L,m,'AUC_site_mean',point_auc[m],lo,hi,len(g),len(days)))
                for k in K:
                    for scope in ('pooled','within_site'):
                        r,e,n=point_top[m,k,scope];rlo,rhi=ci(top_draw[m,k,scope,0]);elo,ehi=ci(top_draw[m,k,scope,1]);top.append((L,m,k,scope,r,rlo,rhi,e,elo,ehi,n,len(g),*random_exp[k,scope]))
            for a,bm in EDGES:
                val=site_draw[bm]-site_draw[a];lo,hi=ci(val)
                aucrows.append((L,f'{a}_to_{bm}','delta_AUC_site_mean',point_auc[bm]-point_auc[a],lo,hi,len(g),len(days)))
                for k in K:
                    for scope in ('pooled','within_site'):
                        old=point_top[a,k,scope];new=point_top[bm,k,scope];rlo,rhi=ci(top_draw[bm,k,scope,0]-top_draw[a,k,scope,0]);elo,ehi=ci(top_draw[bm,k,scope,1]-top_draw[a,k,scope,1]);top.append((L,f'{a}_to_{bm}',k,scope,new[0]-old[0],rlo,rhi,new[1]-old[1],elo,ehi,new[2],len(g),np.nan,np.nan))
            for typ,col in [('dz_positive',g.dz>0),('terrain',g.terrain)]:
                for val in sorted(col.unique()):
                    h=g[col==val]; rec=dict(lead_min=L,group_type=typ,group=str(val),stations=h.site.nunique(),n=len(h))
                    for m in METHODS:rec['MAE_'+m]=float(np.abs(h[m]-h.obs).mean())
                    groups.append(rec)
            for s,h in g.groupby('site'):
                per_site.append(dict(lead_min=L,site=s,n=len(h),MAE_B=float(np.abs(h.B-h.obs).mean()),MAE_B_D=float(np.abs(h.B_D-h.obs).mean()),MAE_B_D2=float(np.abs(h.B_D2-h.obs).mean()),MAE_B_R=float(np.abs(h.B_R-h.obs).mean()),MAE_B_T0=float(np.abs(h.B_T0-h.obs).mean())))
            # B_D2 vs persistence; same UTC-day draws and paired rows, independent of frozen gate.
            err2=np.abs(g.B_D2-g.obs).to_numpy();errp=np.abs(g.P-g.obs).to_numpy();rr=np.empty(DRAWS)
            rng2=np.random.default_rng(SEED+L+40000)
            for b in range(DRAWS):
                pick=rng2.integers(0,len(days),len(days));ix=np.concatenate([blocks[i] for i in pick]);rr[b]=(err2[ix].mean()-errp[ix].mean())/errp[ix].mean()
            lo,hi=ci(rr);rel.append((L,(err2.mean()-errp.mean())/errp.mean(),lo,hi,len(g)))
            print('LEAD_DONE',L,flush=True)
    pd.DataFrame(aucrows,columns=['lead_min','method','metric','point','lo','hi','n','days']).to_csv(OUT/'auc_site_ci.csv',index=False)
    pd.DataFrame(top,columns=['lead_min','method','k','scope','rows','rows_lo','rows_hi','events','events_lo','events_hi','n_events','n','random_rows','random_events']).to_csv(OUT/'topk_corrected.csv',index=False)
    pd.DataFrame(groups).to_csv(OUT/'groups.csv',index=False)
    pd.DataFrame(per_site).to_csv(OUT/'site_mae.csv',index=False)
    pd.DataFrame(rel,columns=['lead_min','B_D2_vs_P','lo','hi','n']).to_csv(OUT/'B_D2_vs_P.csv',index=False)
    models=json.loads((ROOT/'models.json').read_text()); taus=[]
    for delay,model in models.items():
        for key,tau in model['tau'].items():
            site,method=key.split(':');taus.append((int(delay),site,method,int(tau),tau in (15,480)))
    pd.DataFrame(taus,columns=['delay_h','site','method','tau_min','endpoint']).to_csv(OUT/'tau.csv',index=False)
    # Preserve frozen station and pooled coverage; summary expands 9 leads x 3 methods x 2 nominal.
    c=pd.read_csv(ROOT/'frozen_coverage_delay4.csv');station=c[c.site!='all'];summary=station.groupby(['method','nominal']).agg(min_coverage=('coverage','min'),max_coverage=('coverage','max'),n_sites=('site','nunique')).reset_index();summary.to_csv(OUT/'coverage_summary.csv',index=False)
    print('POST_DONE',flush=True)
if __name__=='__main__':main()
