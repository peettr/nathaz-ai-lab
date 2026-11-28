#!/usr/bin/env python3
"""ASOS A1 verification: 8/4 split, common-case pair, daily bootstrap gates.
--obs 2023 hourly CSV --climate-obs 2022 hourly CSV --parts forecast_parts directory.
"""
import argparse,json,glob
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
LEADS=[6,12,24,36,48,72];SPEED=[6,8,10,12];GUST=[10,13,15]
def clean(v):return None if not np.isfinite(v) else float(v)
def fit(x,y):
    mask=np.isfinite(x)&np.isfinite(y)
    if mask.sum()<12 or np.std(x[mask])<1e-6:return (float(np.mean(y[mask])),0.) if mask.any() else (np.nan,np.nan)
    b,a=np.polyfit(x[mask],y[mask],1);return a,b
def skill(y,p,d=None,q=None):
    m=np.isfinite(y)&np.isfinite(p);diff=p[m]-y[m]
    dm=m&np.isfinite(d)&np.isfinite(q) if d is not None and q is not None else np.zeros(len(y),bool)
    return {'n':int(m.sum()),'mae':clean(np.mean(abs(diff)) if m.any() else np.nan),'bias':clean(np.mean(diff) if m.any() else np.nan),'direction_mae_deg':clean(np.mean(abs((q[dm]-d[dm]+180)%360-180)) if dm.any() else np.nan)}
def event(y,p,t):
    m=np.isfinite(y)&np.isfinite(p);o=y[m]>=t;f=p[m]>=t;h=int((o&f).sum());miss=int((o&~f).sum());fa=int((~o&f).sum())
    return {'n':int(m.sum()),'events':int(o.sum()),'hits':h,'misses':miss,'false_alarms':fa,'hit_rate':clean(h/(h+miss) if h+miss else np.nan),'false_alarm_ratio':clean(fa/(h+fa) if h+fa else np.nan),'csi':clean(h/(h+miss+fa) if h+miss+fa else np.nan),'brier_deterministic':clean(np.mean((f.astype(float)-o.astype(float))**2) if m.any() else np.nan)}
def record(g,source,lead,variant,scol,gcol,dcol):
    y=g.obs_speed.to_numpy();p=g[scol].to_numpy();d=g.obs_dir.to_numpy();q=g[dcol].to_numpy() if dcol else None
    r={'source':source,'lead_h':lead,'variant':variant,**skill(y,p,d,q)}
    for t in SPEED:r[f'wind_{t}']=event(y,p,t)
    for t in GUST:r[f'gust_{t}']=event(g.obs_gust.to_numpy(),g[gcol].to_numpy(),t) if gcol else None
    return r
def gate_metrics(df,source,lead,base):
    g=df[(df.lead_h==lead)&(df.source==source)]
    gg=df[(df.lead_h==lead)&(df.source==base)]
    keys=['station','init_utc','lead_h'];joined=g.merge(gg[keys+['corrected','pred_gust']],on=keys,suffixes=('','_base'),validate='one_to_one')
    return joined
def delta(g,base,metric):
    if metric=='mae':
        e=np.abs(g.corrected.to_numpy()-g.obs_speed.to_numpy());b=np.abs(g.corrected_base.to_numpy()-g.obs_speed.to_numpy())
        ok=np.isfinite(e)&np.isfinite(b)
        return float(np.mean(e[ok])/np.mean(b[ok])-1) if ok.sum() else np.nan
    t=8;y=g.obs_speed.to_numpy()
    aa=event(y,g.corrected.to_numpy(),t)['csi'];bb=event(y,g.corrected_base.to_numpy(),t)['csi']
    return aa-bb if aa is not None and bb is not None else np.nan
def bootstrap(g,metric,n,seed):
    dates=g.valid_utc.dt.floor('D');unique=dates.drop_duplicates().to_numpy();rng=np.random.default_rng(seed)
    byday={x:np.flatnonzero(dates.to_numpy()==x) for x in unique};vals=[]
    for _ in range(n):
        choose=rng.choice(unique,size=len(unique),replace=True);inds=np.concatenate([byday[x] for x in choose]);vals.append(delta(g.iloc[inds],None,metric))
    arr=np.asarray(vals);arr=arr[np.isfinite(arr)]
    return [float(x) for x in np.quantile(arr,[.025,.975])] if len(arr)>=n*.9 else None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stations',required=True);ap.add_argument('--year',type=int,required=True);ap.add_argument('--sources',nargs='+',required=True);ap.add_argument('--obs',required=True);ap.add_argument('--climate-obs',required=True);ap.add_argument('--parts',required=True);ap.add_argument('--out',required=True);ap.add_argument('--bootstrap',type=int,default=1000);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);station=pd.read_csv(a.stations)
    files=[Path(a.parts)/f'{s}_{t:%Y%m%d%H}.csv' for t in pd.date_range(f'{a.year}-01-01',f'{a.year+1}-01-01',freq='12h',inclusive='left',tz='UTC') for s in a.sources]
    present=[p for p in files if p.exists()];missing=[p.name for p in files if not p.exists()]
    print('parts',len(present),'expected',len(files),'missing',missing[:30],flush=True)
    if len(present)<len(files)*.95:raise ValueError('archive coverage <95%; refuse verdict')
    counts=pd.Series([p.stem.rsplit('_',1)[-1][:6] for p in present]).value_counts()
    expected_per_month=pd.Series([p.stem.rsplit('_',1)[-1][:6] for p in files]).value_counts()
    if any(counts.get(m,0)<.95*n for m,n in expected_per_month.items()):raise ValueError('a monthly archive window <95%')
    fc=pd.concat((pd.read_csv(p) for p in present),ignore_index=True);fc['init_utc']=pd.to_datetime(fc.init_utc,utc=True)
    fc['valid_utc']=fc.init_utc+pd.to_timedelta(fc.lead_h,unit='h')
    obs=pd.read_csv(a.obs);obs['valid_utc']=pd.to_datetime(obs.valid_utc,utc=True)
    climate=pd.read_csv(a.climate_obs);climate['valid_utc']=pd.to_datetime(climate.valid_utc,utc=True)
    obs=obs.drop_duplicates(['station','valid_utc']);climate=climate.drop_duplicates(['station','valid_utc'])
    climate['month']=climate.valid_utc.dt.month;climate['hour']=climate.valid_utc.dt.hour
    clim=climate.groupby(['station','month','hour'])[['obs_speed','obs_gust']].mean().rename(columns={'obs_speed':'climatology','obs_gust':'climatology_gust'}).reset_index()
    obs0=obs.rename(columns={'valid_utc':'init_utc','obs_speed':'persistence','obs_gust':'persistence_gust','obs_dir':'persistence_dir'})[['station','init_utc','persistence','persistence_gust','persistence_dir']]
    df=fc.merge(obs,on=['station','valid_utc'],how='left',validate='many_to_one').merge(obs0,on=['station','init_utc'],how='left',validate='many_to_one')
    df['month']=df.valid_utc.dt.month;df['hour']=df.valid_utc.dt.hour
    df=df.merge(clim,on=['station','month','hour'],how='left',validate='many_to_one')
    # Restrict to exactly shared sources/station/init/lead and valid observed speed; retain missing gust flags.
    keys=['station','init_utc','lead_h'];ok=df.groupby(keys).agg(n=('source','nunique'),obs=('obs_speed','first'),persist=('persistence','first'),clim=('climatology','first')).reset_index()
    ok=ok[(ok.n==len(a.sources))&ok[['obs','persist','clim']].notna().all(axis=1)][keys]
    df=df.merge(ok,on=keys,how='inner',validate='many_to_one')
    if df.station.nunique()<6:raise ValueError('fewer than six valid stations')
    df['raw_speed']=np.hypot(df.fc_u,df.fc_v);df['raw_direction']=(270-np.degrees(np.arctan2(df.fc_v,df.fc_u)))%360
    df['corrected']=np.nan;df['pred_gust']=np.nan
    split=pd.Timestamp(f'{a.year}-09-01',tz='UTC');end=pd.Timestamp(f'{a.year+1}-01-01',tz='UTC')
    for (s,lead,src),grp in df.groupby(['station','lead_h','source']):
        tr=grp[grp.init_utc<split];a0,b0=fit(tr.raw_speed.to_numpy(),tr.obs_speed.to_numpy());z=np.maximum(0,a0+b0*grp.raw_speed.to_numpy())
        df.loc[grp.index,'corrected']=z
        ag,bg=fit(z[(grp.init_utc<split).to_numpy()],grp.loc[grp.init_utc<split,'obs_gust'].to_numpy())
        df.loc[grp.index,'pred_gust']=np.maximum(0,ag+bg*z)
    test=df[(df.init_utc>=split)&(df.init_utc<end)].copy()
    if test.empty:raise ValueError('No test data')
    ref=test[test.source==a.sources[0]];records=[]
    for (src,lead),g in test.groupby(['source','lead_h']):
        records.extend([record(g,src,int(lead),'raw','raw_speed',None,'raw_direction'),record(g,src,int(lead),'corrected','corrected','pred_gust','raw_direction')])
    for lead,g in ref.groupby('lead_h'):
        records.extend([record(g,'persistence',int(lead),'baseline','persistence','persistence_gust','persistence_dir'),record(g,'climatology',int(lead),'baseline','climatology','climatology_gust',None)])
    score={s:sum(next(r['mae'] for r in records if r['source']==s and r['lead_h']==l and r['variant']=='corrected') for l in (24,48)) for s in a.sources if s!='GFS'}
    best=min(score,key=score.get);gates=[]
    for lead in (24,48):
        for base in ['GFS','persistence','climatology']:
            if base in ('persistence','climatology'):
                g=test[(test.source==best)&(test.lead_h==lead)].copy();g['corrected_base']=g[base]
            else:g=gate_metrics(test,best,lead,base)
            value=delta(g,base,'mae');ci=bootstrap(g,'mae',a.bootstrap,20261014+lead+len(base))
            gates.append({'lead_h':lead,'comparison':f'{best} / {base} - 1','delta':clean(value),'ci95':ci,'pass':bool(value<= (.05 if base=='GFS' else -.15))})
    g=gate_metrics(test,best,24,'GFS');v=delta(g,'GFS','csi');ci=bootstrap(g,'csi',a.bootstrap,20261114)
    gates.append({'lead_h':24,'comparison':f'CSI8 {best} - GFS','delta':clean(v),'ci95':ci,'pass':bool(v>=0)})
    ratio=test[test.source=='FOUR_v200_GFS'].copy();ratio['fc100_speed']=np.hypot(ratio.fc_u100,ratio.fc_v100);ratio=ratio[ratio.obs_speed>=.5]
    ratio['ratio']=ratio.fc100_speed/ratio.obs_speed
    dist={'n':int(ratio.ratio.notna().sum()),'excluded_obs_below_0.5_mps':int(len(test[test.source=='FOUR_v200_GFS'])-len(ratio)),'quantiles':{str(q):clean(ratio.ratio.quantile(q)) for q in [.05,.25,.5,.75,.95]}}
    payload={'year':a.year,'stations':station.astype(object).where(pd.notna(station),None).to_dict('records'),'sources':a.sources,'missing_archive_files':missing,'archive_file_count':len(present),'archive_files_expected':len(files),'best_ai_by_24_48_mae':best,'common_cases':len(ok),'test_cases_per_source':len(ref),'period':{'train':'2023-01 through 2023-08','test':'2023-09 through 2023-12','climatology':'2022 monthly/hourly station observations'},'gates':gates,'verdict':bool(all(x['pass'] for x in gates)),'records':records,'ratio_100m_to_10m':dist,'brier_note':'Deterministic threshold indicators; not calibrated event probabilities.'}
    (out/'metrics.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False))
    test.to_csv(out/'paired_station_test.csv',index=False)
    df.to_csv(out/'paired_station_all.csv',index=False)
    for metric,filename,ylabel in [('mae','mae_vs_lead.png','MAE (m/s)'),('csi','csi8_vs_lead.png','CSI @ 8 m/s')]:
        fig,ax=plt.subplots(figsize=(7,4))
        for source in a.sources+['persistence','climatology']:
            rr=[next((r for r in records if r['source']==source and r['lead_h']==l and r['variant']==('corrected' if source in a.sources else 'baseline')),None) for l in LEADS]
            vals=[r['mae'] if metric=='mae' else r['wind_8']['csi'] for r in rr]
            ax.plot(LEADS,vals,marker='o',label=source)
        ax.set(xlabel='Lead (h)',ylabel=ylabel);ax.legend(fontsize=7);ax.grid(alpha=.3)
        fig.text(.01,.01,'Source: NOAA/CIRA AIWP, NOAA GFS AWS, NCEI ASOS via IEM (2023)',fontsize=7)
        fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/filename,dpi=150);plt.close(fig)
    lines=['# A1 2023 OKC ASOS forecast validation','',f'Conclusion: {"AI meets all pre-registered gates by point estimates, but uncertainty does not establish non-inferiority" if payload["verdict"] else "AI fails at least one pre-registered point-estimate gate"}; best AI={best}.','', 'ASOS one-minute 1h centered mean when available, METAR nearest 2-min report otherwise. Station/anemometer heights and mixed representativeness limit urban inference.','',f'Common paired cases (station × init × lead): {len(ok)}; test cases per source {len(ref)}; source files {len(present)}/{len(files)}. Missing archive: {missing}.','','## Gates (daily bootstrap 95% CI; delta AI/base - 1, CSI difference AI - GFS)','']
    for x in gates:lines.append(f"- {x['lead_h']}h {x['comparison']}: {x['delta']:.4f}, 95% CI {x['ci95']}, {'PASS' if x['pass'] else 'FAIL'}")
    lines.extend(['','## Main table','','|Source|Lead h|Variant|N|MAE|Bias|Direction MAE|Wind 6/8/10/12: hit / false alarm / CSI / deterministic Brier|Gust 10/13/15: same|','|---|---:|---|---:|---:|---:|---:|---|---|'])
    def txt(v):return 'NA' if v is None else f'{v:.3f}'
    def events(r,prefix,thresholds):return '; '.join(f'{t}: '+('/'.join(txt(r[f'{prefix}_{t}'][k]) for k in ['hit_rate','false_alarm_ratio','csi','brier_deterministic']) if r[f'{prefix}_{t}'] else 'NA') for t in thresholds)
    for r in records:lines.append(f"|{r['source']}|{r['lead_h']}|{r['variant']}|{r['n']}|{txt(r['mae'])}|{txt(r['bias'])}|{txt(r['direction_mae_deg'])}|{events(r,'wind',SPEED)}|{events(r,'gust',GUST)}|")
    lines+=['','## 100 m forecast / 10 m observed speed (FCNv2; descriptive only)',f"N={dist['n']}; median={dist['quantiles']['0.5']}; 5/25/75/95%={dist['quantiles']['0.05']}, {dist['quantiles']['0.25']}, {dist['quantiles']['0.75']}, {dist['quantiles']['0.95']}; excluded below 0.5 m/s={dist['excluded_obs_below_0.5_mps']}. Not a vertical-profile conversion coefficient.",'','Limitations: month/hour climatology trained on preceding 2022 observations (because Sep-Dec absent from Jan-Aug 2023 training); mixed 1-minute/METAR sampling; missing METAR gust is not zero. Direction not calibrated. Deterministic Brier is not probability calibration. Airport exposures not urban canyon. Bremnes et al. (2024), NPG 31:247-257, DOI 10.5194/npg-31-247-2024 provides external design comparison, not an OKC skill estimate.']
    (out/'results.md').write_text('\n'.join(lines)+'\n')
    print('METRICS_DONE',best,payload['verdict'],len(records),len(test),flush=True)
if __name__=='__main__':main()
