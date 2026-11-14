#!/usr/bin/env python3
"""Delayed-cycle retrained LOSO D2/FXD2 and paired verifying-day bootstrap."""
import io,json,tarfile
from pathlib import Path
import numpy as np,pandas as pd
R=Path('/content/delay6');O=R/'score';O.mkdir(parents=True,exist_ok=True)
FHRS=(6,12,24,48);TERRAIN=('ridge','pass','valley','plateau');SEED=23050704

def design(d,fx):
 raw=d.raw.to_numpy();v=d.v1.to_numpy();dz=d.dz.to_numpy()
 a=np.column_stack((np.ones(len(d)),raw,v,dz,raw*dz,*[(d.terrain==t).to_numpy(dtype=float) for t in TERRAIN]))
 return np.column_stack((a,d.fx.to_numpy())) if fx else a

def read():
 with tarfile.open(R/'score_stage_archive.tgz') as t:
  train=pd.read_parquet(t.extractfile('train_pairs.parquet'));test=pd.read_parquet(t.extractfile('test_pairs.parquet'))
 rows=[]
 for p in sorted((R/'infer').glob('*.jsonl')):
  with p.open() as f:rows.extend(json.loads(line) for line in f)
 feat=pd.DataFrame(rows);feat.init_new=pd.to_datetime(feat.init_new,utc=True)
 assert not feat.duplicated(['site','init_new','fhr']).any()
 for name,d in (('train',train),('test',test)):
  for c in ('init_utc','valid_end_utc'):d[c]=pd.to_datetime(d[c],utc=True)
  assert 'issue_utc' not in d and 'info_cutoff_utc' not in d
  assert not d.duplicated(['site','init_utc','fhr']).any()
  d['issue_utc']=d.init_utc+pd.Timedelta(hours=4);d['init_new']=d.init_utc-pd.Timedelta(hours=6)
  assert (d.init_new+pd.Timedelta(hours=6)<=d.issue_utc).all(),name+' availability'
  assert (d.valid_end_utc==d.init_new+pd.to_timedelta(d.fhr+6,unit='h')).all(),name+' valid'
  assert ((d.valid_end_utc-d.issue_utc)==pd.to_timedelta(d.fhr-4,unit='h')).all(),name+' L'
 train=train[(train.valid_end_utc<pd.Timestamp('2024-01-01',tz='UTC'))&(train.issue_utc<pd.Timestamp('2023-12-31 18:00',tz='UTC'))].copy()
 test=test[test.issue_utc>=pd.Timestamp('2024-01-01',tz='UTC')].copy()
 assert (len(train),len(test))==(17604,17252)
 def join(d):
  original=d[['site','init_utc','valid_end_utc','fhr','issue_utc','obs','terrain']].reset_index(drop=True)
  new=d.drop(columns=['raw','v1','dz','z_model_sfc'],errors='ignore').merge(feat,on=['site','init_new','fhr'],how='left',validate='one_to_one')
  assert len(new)==len(d) and new[['raw','v1','dz','fx']].notna().all().all()
  assert (new.source_fhr==new.fhr+6).all()
  assert (new.valid_end_utc==new.init_new+pd.to_timedelta(new.source_fhr,unit='h')).all()
  assert (new.init_new+pd.Timedelta(hours=6)<=new.issue_utc).all()
  assert new[['site','init_utc','valid_end_utc','fhr','issue_utc','obs','terrain']].equals(original), 'population changed'
  return new
 return join(train),join(test)

def score():
 tr,te=read();parts=[];coeff=[]
 for fhr in FHRS:
  for site in sorted(te.site.unique()):
   fit=tr[(tr.site!=site)&(tr.fhr==fhr)];part=te[(te.site==site)&(te.fhr==fhr)].copy()
   assert len(fit)>=500 and len(part)>0
   for fx,name in ((False,'D2'),(True,'FXD2')):
    a=design(fit,fx);c=np.linalg.lstsq(a,fit.obs.to_numpy(),rcond=None)[0]
    part[name]=design(part,fx)@c
    coeff.append({'fhr':fhr,'site':site,'method':name,'n_train':len(fit),'coefficients':json.dumps(c.tolist()),'condition':float(np.linalg.cond(a))})
   parts.append(part)
 pred=pd.concat(parts,ignore_index=True)
 pred.to_parquet(O/'paired_predictions.parquet',index=False)
 pd.DataFrame(coeff).to_csv(O/'coefficients.csv',index=False)
 out=[]
 for fhr,d in pred.groupby('fhr'):
  d=d.copy();d['day']=d.valid_end_utc.dt.floor('D');groups=[np.flatnonzero(d.day.to_numpy()==x) for x in d.day.unique()]
  assert len(groups)>=30
  obs=d.obs.to_numpy();err0=abs(d.D2.to_numpy()-obs);err1=abs(d.FXD2.to_numpy()-obs)
  rng=np.random.default_rng(SEED+fhr);draw=[]
  for _ in range(1000):
   ix=np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]);draw.append((err1[ix].mean()-err0[ix].mean())/err0[ix].mean())
  out.append({'fhr':int(fhr),'L':int(fhr-4),'n':len(d),'days':len(groups),'mae_d2':float(err0.mean()),'mae_fxd2':float(err1.mean()),'D':float((err1.mean()-err0.mean())/err0.mean()),'lo':float(np.quantile(draw,.025)),'hi':float(np.quantile(draw,.975))})
  print('SCORE',out[-1],flush=True)
 pd.DataFrame(out).to_csv(O/'scores.csv',index=False)
 (O/'score.done').write_text(json.dumps({'train_rows':len(tr),'test_rows':len(te),'fhrs':list(FHRS),'draws':1000,'note':'secondary only; no decision'})+'\n')
if __name__=='__main__':score()
