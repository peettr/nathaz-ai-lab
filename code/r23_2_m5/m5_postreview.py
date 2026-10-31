#!/usr/bin/env python3
"""M5 post-review diagnostics, 10-27. Original scorer/config untouched. Run on Colab CPU."""
import io, json, tarfile, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
R=Path('/content/m5'); O=R/'supplement2'; O.mkdir(exist_ok=True)
METHODS=('R','T0','D1','D2','M','M+D1'); FHRS=(6,12,24,48)
PRED=R/'swiss_predictions_delay4.parquet'; TRAIN=R/'train_pairs.parquet'; TEST=R/'test_pairs.parquet'
FROZEN=R/'swiss_scores_delay4.csv'; OBS=R/'native_obs.tgz'
def auc(y,s):
    y=np.asarray(y,dtype=bool); s=np.asarray(s); n=y.sum(); neg=len(y)-n
    return float((rankdata(s,method='average')[y].sum()-n*(n+1)/2)/(n*neg)) if n and neg else np.nan
def stat(d,threshold='threshold_p95'):
    o=d.obs.to_numpy(); e=o>=d[threshold].to_numpy(); out={}
    for m in METHODS:
        p=d[m].to_numpy(); out['MAE_'+m]=np.abs(p-o).mean();out['AUC_'+m]=auc(e,p)
        for k in (1,5,10):
            order=d.sort_values([m,'site','init_utc'],ascending=[False,True,True],kind='mergesort').index[:max(1,math.ceil(len(d)*k/100))]
            out[f'Top{k}_'+m]=e[d.index.get_indexer(order)].sum()/e.sum() if e.sum() else np.nan
    out['D']=(out['MAE_D2']-out['MAE_T0'])/out['MAE_T0']
    return out
def ci(values):
    a=np.asarray(values,dtype=float);a=a[np.isfinite(a)]
    return [float(np.quantile(a,.025)),float(np.quantile(a,.975))] if len(a) else [None,None]
def daydraws(frame,seed=23050304):
    days=pd.to_datetime(frame.valid_end_utc,utc=True).dt.floor('D').to_numpy(); uniq=pd.unique(days)
    groups=[np.flatnonzero(days==x) for x in uniq]; rng=np.random.default_rng(seed)
    for _ in range(1000):yield np.concatenate([groups[x] for x in rng.integers(len(groups),size=len(groups))])
def gate(frame,tag):
    rows=[]
    for h in FHRS:
        f=frame[frame.fhr==h].reset_index(drop=True); o=f.obs.to_numpy();a=np.abs(f.D2.to_numpy()-o);b=np.abs(f.T0.to_numpy()-o)
        point=(a.mean()-b.mean())/b.mean(); days=pd.to_datetime(f.valid_end_utc,utc=True).dt.floor('D').to_numpy();u=pd.unique(days)
        groups=[np.flatnonzero(days==x) for x in u];g=np.array([[a[z].sum(),b[z].sum(),len(z)] for z in groups]);rng=np.random.default_rng(230503+h+400)
        choice=rng.integers(len(g),size=(1000,len(g)));tot=g[choice].sum(axis=1); vals=(tot[:,0]-tot[:,1])/tot[:,1]
        lo,hi=ci(vals); rows.append(dict(tag=tag,fhr=h,n=len(f),days=len(g),D=float(point),lo=lo,hi=hi,earliest_issue=str(pd.to_datetime(f.issue_utc,utc=True).min())))
    return rows
def station_auc(f):
    output=[]
    for site,part in f.groupby('site'):
        e=part.obs.to_numpy()>=part.threshold_p95.to_numpy();output.append({'site':site,**{m:auc(e,part[m].to_numpy()) for m in METHODS},'n':len(part),'events':int(e.sum())})
    return output
def native_threshold(pred):
    out={}; audit=[]
    with tarfile.open(OBS,'r:gz') as tf:
        for site in sorted(pred.site.unique()):
            x=pd.read_csv(io.BytesIO(tf.extractfile(f'obs/obs_{site}.csv').read()))
            t=pd.to_datetime(x.time_utc,utc=True);mask=(t>=pd.Timestamp('2023-10-01',tz='UTC'))&(t<pd.Timestamp('2024-01-01',tz='UTC'))
            values=pd.to_numeric(x.loc[mask,'speed_ms'],errors='coerce').dropna();out[site]=float(np.quantile(values,.95));audit.append(dict(site=site,n=int(len(values)),p95=out[site],time_min=str(t[mask].min()),time_max=str(t[mask].max())))
    pd.DataFrame(audit).to_csv(O/'native_thresholds.csv',index=False)
    return out
def event_lookup(pred,th):
    frames=[]
    with tarfile.open(OBS,'r:gz') as tf:
        for site in sorted(pred.site.unique()):
            x=pd.read_csv(io.BytesIO(tf.extractfile(f'obs/obs_{site}.csv').read()))
            x.time_utc=pd.to_datetime(x.time_utc,utc=True); x=x[x.speed_ms>=th[site]][['time_utc']].sort_values('time_utc')
            starts=x.time_utc.diff().gt(pd.Timedelta(minutes=40)).fillna(True)
            if len(starts):starts.iloc[0]=True
            x['event_id']=[f'{site}:{j}' for j in starts.cumsum().to_numpy()];x['site']=site;frames.append(x)
    return pd.concat(frames,ignore_index=True)
def event_top(d,m,k):
    e=d.obs.to_numpy()>=d.native_p95.to_numpy(); ids=d.event_id.fillna('').to_numpy(dtype=str)
    if np.any(e & (ids=='')):raise ValueError('missing native event mapping')
    n=max(1,math.ceil(len(d)*k/100)); chosen=d.sort_values([m,'site','init_utc'],ascending=[False,True,True],kind='mergesort').index[:n]
    loc=d.index.get_indexer(chosen);den=len(np.unique(ids[e]));return float(len(np.unique(ids[loc][e[loc]]))/den) if den else np.nan
def main():
    pred=pd.read_parquet(PRED);train=pd.read_parquet(TRAIN);test=pd.read_parquet(TEST);frozen=pd.read_csv(FROZEN)
    pred['issue_utc']=pd.to_datetime(pred.issue_utc,utc=True);pred['valid_end_utc']=pd.to_datetime(pred.valid_end_utc,utc=True)
    for h in FHRS:
        f=pred[pred.fhr==h].reset_index(drop=True);s=stat(f)
        for m in METHODS:
            target=frozen[(frozen.fhr==h)&(frozen.metric=='MAE_'+m)].point.iloc[0]
            if abs(s['MAE_'+m]-target)>1e-10:raise ValueError('frozen reproduction '+str((h,m,s['MAE_'+m],target)))
    boundary=pred[pred.issue_utc>=pd.Timestamp('2024-01-01',tz='UTC')].copy()
    gate_rows=gate(boundary,'issue_ge_Jan1')
    # Refit every LOSO fold using only rows with verifying time earlier than its first test issue.
    # Preserve all frozen test rows and method design; own-station M fitted under same cutoff.
    from m5_score import design, METHODS as originals
    assert tuple(originals)==METHODS
    refit=pred.copy(); cutrows=[]
    tr_valid=pd.to_datetime(train.valid_end_utc,utc=True)
    for h in FHRS:
        earliest=pd.to_datetime(pred.loc[pred.fhr==h,'issue_utc'],utc=True).min()
        cutrows.append({'fhr':h,'earliest_issue':str(earliest),'excluded_train_rows':int(((train.fhr==h)&(tr_valid>=earliest)).sum())})
        for site in sorted(pred.site.unique()):
            sel=(refit.fhr==h)&(refit.site==site);pool=train[(train.fhr==h)&(train.site!=site)&(tr_valid<earliest)]
            own=train[(train.fhr==h)&(train.site==site)&(tr_valid<earliest)]
            part=refit.loc[sel].copy()
            for m in METHODS[1:]:
                fit=own if m.startswith('M') else pool
                coef=np.linalg.lstsq(design(fit,m),fit.obs.to_numpy(),rcond=None)[0]
                refit.loc[sel,m]=design(part,m)@coef
    pd.DataFrame(cutrows).to_csv(O/'refit_cutoffs.csv',index=False)
    gate_rows.extend(gate(refit,'refit_train_before_first_issue'))
    pd.DataFrame(gate_rows).to_csv(O/'boundary_gates.csv',index=False)
    th=native_threshold(pred);pred['native_p95']=pred.site.map(th)
    lookup=event_lookup(pred,th)
    pred=pred.merge(lookup,left_on=['site','valid_end_utc'],right_on=['site','time_utc'],how='left',validate='many_to_one').drop(columns='time_utc')
    result=[];station=[]; coverage=[];inc=[]
    for h in FHRS:
        f=pred[pred.fhr==h].reset_index(drop=True)
        point_station=station_auc(f); station.extend([dict(fhr=h,**r) for r in point_station]);sites=sorted(f.site.unique())
        for site,ss in f.groupby('site'):
            cov={'fhr':h,'site':site,'n':len(ss)}
            for m in ('T0','D2','M'):
                for q,l,u in ((90,5,95),(80,10,90)):
                    cov[f'cover{q}_'+m]=float(((ss.obs>=ss[f'{m}_q{l:02d}'])&(ss.obs<=ss[f'{m}_q{u:02d}'])).mean())
            coverage.append(cov)
            a=np.abs(ss['M+D1']-ss.obs).mean()-np.abs(ss.M-ss.obs).mean()
            inc.append(dict(fhr=h,site=site,dz=float(ss.dz.iloc[0]),delta=float(a),n=len(ss)))
        native_point=stat(f,'native_p95');orig_point=stat(f)
        native_event={(m,k):event_top(f,m,k) for m in METHODS for k in (1,5,10)}
        draws={k:[] for k in native_point}; event_draws={(m,k):[] for m in METHODS for k in (1,5,10)}
        mean_draws={m:[] for m in METHODS}
        for ix in daydraws(f,23050304+h):
            b=f.iloc[ix].reset_index(drop=True); v=stat(b,'native_p95')
            for k in draws:draws[k].append(v[k])
            for site,ss in b.groupby('site'):
                pass
            for m,k in event_draws:event_draws[(m,k)].append(event_top(b,m,k))
            sa=station_auc(b)
            for m in METHODS:mean_draws[m].append(float(np.nanmean([x[m] for x in sa])))
        for k,v in native_point.items():
            lo,hi=ci(draws[k]);result.append(dict(fhr=h,metric=k,point=float(v),lo=lo,hi=hi,original_point=float(orig_point[k]),n=len(f),type='native_threshold'))
        for (m,k),v in native_event.items():
            lo,hi=ci(event_draws[(m,k)]);result.append(dict(fhr=h,metric=f'eventTop{k}_{m}',point=v,lo=lo,hi=hi,original_point=None,n=len(f),type='native_threshold'))
        for m in METHODS:
            avg=float(np.nanmean([x[m] for x in point_station]));lo,hi=ci(mean_draws[m]);result.append(dict(fhr=h,metric='station_mean_AUC_'+m,point=avg,lo=lo,hi=hi,original_point=orig_point['AUC_'+m],n=len(f),type='station_auc'))
        print('POST_FHR_DONE',h,flush=True)
    pd.DataFrame(result).to_csv(O/'secondary_ci.csv',index=False);pd.DataFrame(station).to_csv(O/'station_auc.csv',index=False);pd.DataFrame(coverage).to_csv(O/'station_coverage.csv',index=False);pd.DataFrame(inc).to_csv(O/'station_increment.csv',index=False)
    (O/'audit.json').write_text(json.dumps({'rows':len(pred),'train_rows':len(train),'test_rows':len(test),'gate':gate_rows,'methods':METHODS,'native_threshold':'site October-December complete 10-minute speed_ms P95','post_hoc':'2026-10-27'},indent=2,ensure_ascii=False))
    print('POST_DONE',flush=True)
if __name__=='__main__':main()
