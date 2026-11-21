#!/usr/bin/env python3
"""Frozen candidate M7 Swiss LOSO scorer; only run after feature hash/card freeze.
M5 pair population and designs, FX added as one fixed column. Daily 1000 draws.
"""
import csv,io,json,math,tarfile
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import rankdata
R=Path('./23_AI_Weather/06_Logs/r23_2_m7');O=R/'score_v2';O.mkdir(exist_ok=True)
FHRS=(6,12,24,48);TERRAIN=('ridge','pass','valley','plateau')
METHODS=('R','T0','D2','FX0','FX-T0','FXD2','M+D1','M+D1+FX')
SEED=23050704

def design(d,m):
 raw=d.raw.to_numpy();v=d.v1.to_numpy();dz=d.dz.to_numpy();fx=d.fx.to_numpy()
 if m=='T0':return np.column_stack((np.ones(len(d)),raw))
 if m=='FX-T0':return np.column_stack((np.ones(len(d)),fx))
 if m=='M+D1':return np.column_stack((np.ones(len(d)),raw,v))
 if m=='M+D1+FX':return np.column_stack((np.ones(len(d)),raw,v,fx))
 if m in ('D2','FXD2'):
  a=np.column_stack((np.ones(len(d)),raw,v,dz,raw*dz,*[(d.terrain==t).to_numpy(dtype=float) for t in TERRAIN]))
  return np.column_stack((a,fx)) if m=='FXD2' else a
 raise ValueError(m)

def prepare():
 with tarfile.open(R/'score_stage_archive.tgz') as t:
  tr=pd.read_parquet(t.extractfile('train_pairs.parquet'))
  te=pd.read_parquet(t.extractfile('test_pairs.parquet'))
 fx=pd.read_json(R/'full_fx_rows_1107_161219.jsonl',lines=True)
 fx.init_utc=pd.to_datetime(fx.init_utc,utc=True)
 assert not fx.duplicated(['site','init_utc','fhr']).any()
 for name,d in [('train',tr),('test',te)]:
  # M5 stage archive contains neither issue nor cutoff. Reconstruct the
  # frozen four-hour availability assumption from the original init field;
  # this cannot certify an independently archived raw issuance timestamp.
  for col in ('init_utc','valid_end_utc'):d[col]=pd.to_datetime(d[col],utc=True)
  assert 'issue_utc' not in d and 'info_cutoff_utc' not in d
  d['issue_utc']=d.init_utc+pd.Timedelta(hours=4)
  d['info_cutoff_utc']=d.init_utc+pd.Timedelta(hours=4)
  assert not d.duplicated(['site','init_utc','fhr']).any(),name
  assert ((d.init_utc+pd.Timedelta(hours=4))<=d.issue_utc).all(),name+' issue'
  assert (d.info_cutoff_utc<=d.issue_utc).all(),name+' cutoff'
  assert (d.valid_end_utc==d.init_utc+pd.to_timedelta(d.fhr,unit='h')).all(),name+' valid'
  assert set(d.site)==set(json.loads((R/'stations.json').read_text())[i]['site'] for i in range(12))
  assert set(d.fhr)==set(FHRS)
 tr=tr[(tr.valid_end_utc<pd.Timestamp('2024-01-01',tz='UTC'))&(tr.issue_utc<pd.Timestamp('2023-12-31 18:00',tz='UTC'))].copy()
 te=te[te.issue_utc>=pd.Timestamp('2024-01-01',tz='UTC')].copy()
 assert len(tr)>10000 and len(te)>10000
 for d in (tr,te):
  old=len(d);d.reset_index(drop=True,inplace=True)
  merged=d.merge(fx[['site','init_utc','fhr','fx']],on=['site','init_utc','fhr'],how='left',validate='one_to_one')
  if len(merged)!=old or merged.fx.isna().any():raise ValueError('FX keys incomplete')
  d['fx']=merged.fx.to_numpy()
 return tr,te

def native_events(test):
 # Threshold from native 10-min TRAIN, event groups from full 10-min series (gap >40 min starts new event).
 th={};events=[]
 with tarfile.open(R/'train_complete_20261027.tgz') as t:
  for site in sorted(test.site.unique()):
   with t.extractfile(f'obs/obs_{site}.csv') as f:x=pd.read_csv(f,usecols=['time_utc','speed_ms'])
   x.time_utc=pd.to_datetime(x.time_utc,utc=True)
   train=x[(x.time_utc>=pd.Timestamp('2023-10-01',tz='UTC'))&(x.time_utc<pd.Timestamp('2024-01-01',tz='UTC'))]
   th[site]=float(np.quantile(train.speed_ms.dropna(),.95))
   y=x[(x.time_utc>=pd.Timestamp('2024-01-01',tz='UTC'))&(x.time_utc<pd.Timestamp('2024-04-01',tz='UTC'))&(x.speed_ms>=th[site])].copy()
   starts=y.time_utc.diff().gt(pd.Timedelta(minutes=40)).fillna(True)
   if len(starts):starts.iloc[0]=True
   y['event_id']=[f'{site}:{int(i)}' for i in starts.cumsum()];y['site']=site
   events.append(y[['site','time_utc','event_id']])
 lookup=pd.concat(events,ignore_index=True)
 out=test.merge(lookup,left_on=['site','valid_end_utc'],right_on=['site','time_utc'],how='left',validate='many_to_one').drop(columns='time_utc')
 out['threshold_p95']=out.site.map(th);out['event']=(out.obs>=out.threshold_p95)
 if out.loc[out.event,'event_id'].isna().any():raise ValueError('event lookup missing')
 return out,th

def predict(tr,te):
 pred=[];coeff=[];conditions=[]
 for fhr in FHRS:
  for site in sorted(te.site.unique()):
   own=tr[(tr.site==site)&(tr.fhr==fhr)]
   pool=tr[(tr.site!=site)&(tr.fhr==fhr)]
   part=te[(te.site==site)&(te.fhr==fhr)].copy()
   if len(own)<50 or len(pool)<500 or not len(part):raise ValueError('empty fold')
   part['R']=part.raw;part['FX0']=part.fx
   for m in METHODS:
    if m in ('R','FX0'):continue
    fit=own if m.startswith('M+') else pool
    a=design(fit,m);b=design(part,m);c=np.linalg.lstsq(a,fit.obs.to_numpy(),rcond=None)[0]
    part[m]=b@c
    resid=fit.obs.to_numpy()-a@c
    if m in ('D2','FXD2'):
     for q in (.05,.10,.90,.95):part[f'{m}_q{round(q*100):02d}']=part[m]+np.quantile(resid,q)
    if m=='FXD2':conditions.append({'fhr':fhr,'site':site,'condition':float(np.linalg.cond(a))})
    coeff.append({'fhr':fhr,'site':site,'method':m,'n':len(fit),'coefficients':json.dumps(c.tolist())})
   pred.append(part)
 pd.DataFrame(coeff).to_csv(O/'coefficients.csv',index=False)
 pd.DataFrame(conditions).to_csv(O/'condition_numbers.csv',index=False)
 return pd.concat(pred,ignore_index=True)

def auc(e,s):
 e=np.asarray(e,dtype=bool);s=np.asarray(s);n=e.sum();neg=len(e)-n
 return float((rankdata(s,method='average')[e].sum()-n*(n+1)/2)/(n*neg)) if n and neg else np.nan

def topk(d,m,k,eventwise=False):
 n=max(1,math.ceil(len(d)*k/100))
 idx=d.sort_values([m,'site','init_utc'],ascending=[False,True,True],kind='mergesort').index[:n]
 if eventwise:
  ids=d.event_id.fillna('').to_numpy();present=set(ids[d.event.to_numpy()]);caught=set(ids[d.index.get_indexer(idx)])&present
  return len(caught)/len(present) if present else np.nan
 return float(d.loc[idx,'event'].sum()/d.event.sum()) if d.event.sum() else np.nan

def aggregate(d):
 out={}
 for m in METHODS:
  out['MAE_'+m]=float(np.abs(d[m]-d.obs).mean())
  out['AUC_'+m]=auc(d.event,d[m]);out['station_mean_AUC_'+m]=float(np.nanmean([auc(s.event,s[m]) for _,s in d.groupby('site')]))
  for k in (1,5,10):
   out[f'Top{k}_'+m]=topk(d,m,k)
   out[f'eventTop{k}_'+m]=topk(d,m,k,True)
  if m in ('D2','FXD2'):
   for target,lo,hi in ((80,10,90),(90,5,95)):
    out[f'cover{target}_'+m]=float(((d.obs>=d[f'{m}_q{lo:02d}'])&(d.obs<=d[f'{m}_q{hi:02d}'])).mean())
 for a,b in (('FX0','R'),('FX-T0','T0'),('FX-T0','D2'),('M+D1+FX','M+D1')):
  out[f'delta_{a}_minus_{b}']=out['MAE_'+a]-out['MAE_'+b]
 out['D']=(out['MAE_FXD2']-out['MAE_D2'])/out['MAE_D2']
 return out

def daily_bootstrap(d,fhr):
 d=d.reset_index(drop=True).copy();d['day']=d.valid_end_utc.dt.floor('D');days=d.day.unique()
 if len(days)<30:raise ValueError('too few days')
 groups=[np.flatnonzero(d.day.to_numpy()==day) for day in days]
 point=aggregate(d);rng=np.random.default_rng(SEED+fhr)
 draws={m:[] for m in point}
 for i in range(1000):
  ix=np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]);b=d.iloc[ix].reset_index(drop=True)
  v=aggregate(b)
  for m in draws:draws[m].append(v[m])
  if (i+1)%200==0:print('BOOT_PROGRESS',fhr,i+1,flush=True)
 return [{'fhr':fhr,'metric':m,'point':val,'lo':float(np.nanquantile(draws[m],.025)),'hi':float(np.nanquantile(draws[m],.975)),'n':len(d),'days':len(days)} for m,val in point.items()]

def main():
 tr,te=prepare();pred=predict(tr,te);pred,th=native_events(pred)
 pred.to_parquet(O/'paired_predictions.parquet',index=False)
 with (O/'native_thresholds.json').open('x') as w:json.dump(th,w,indent=2)
 rows=[]
 for fhr in FHRS:
  d=pred[pred.fhr==fhr].copy();rows.extend(daily_bootstrap(d,fhr))
 pd.DataFrame(rows).to_csv(O/'scores.csv',index=False)
 site=[];terrain=[];dz=[];cover=[]
 for (fhr,s),d in pred.groupby(['fhr','site']):
  site.append({'fhr':fhr,'site':s,'terrain':d.terrain.iloc[0],'dz':d.dz.iloc[0],'n':len(d),**{f'MAE_{m}':float(np.abs(d[m]-d.obs).mean()) for m in ('D2','FXD2','FX0')}})
  for m in ('D2','FXD2'):
   for q,lo,hi in ((80,10,90),(90,5,95)):
    cover.append({'fhr':fhr,'site':s,'method':m,'nominal':q,'n':len(d),'observed':float(((d.obs>=d[f'{m}_q{lo:02d}'])&(d.obs<=d[f'{m}_q{hi:02d}'])).mean())})
 for group,field in [('terrain','terrain'),('dz','dz_sign')]:
  if group=='dz':pred['dz_sign']=np.where(pred.dz>0,'positive','negative')
  for (fhr,v),d in pred.groupby(['fhr',field]):
   terrain.append({'group':group,'fhr':fhr,'class':v,'stations':d.site.nunique(),'n':len(d),**{f'MAE_{m}':float(np.abs(d[m]-d.obs).mean()) for m in ('D2','FXD2','FX0')}})
 pd.DataFrame(site).to_csv(O/'station_mae.csv',index=False)
 pd.DataFrame(terrain).to_csv(O/'terrain_mae.csv',index=False)
 pd.DataFrame(cover).to_csv(O/'coverage.csv',index=False)
 gate=[x for x in rows if x['metric']=='D'];decision={'pass':any(x['hi']<0 for x in gate),'stop':all(x['hi']>=0 for x in gate),'D':gate,'train_rows':len(tr),'test_rows':len(te),'delayed6':'not yet evaluated; reselect GFS run is required'}
 (O/'gate.json').write_text(json.dumps(decision,indent=2));(O/'score.done').write_text('success\n')
 print('SCORE_DONE',json.dumps(decision),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  (O/'score.failed').write_text(__import__('traceback').format_exc());raise
