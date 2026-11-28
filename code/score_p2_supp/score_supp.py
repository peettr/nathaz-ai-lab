#!/usr/bin/env python3
"""Post-hoc station calibration attribution; frozen P2 files read-only."""
import json, math, gzip, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('/content/score_p2_supp_corrected');OUT.mkdir(exist_ok=True)
BASE=Path('/content'); B=10000;SEED=20261111
SRC=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS']
METHODS=['G0','G0c','G1','G1a','G1g']
PAIRS=[('G1','G0c'),('G1a','G0c'),('G1a','G1g'),('G0c','G0')]
def val(x):return float(x) if np.isfinite(x) else None
def ci(a):
 a=np.sort(np.asarray(a));a=a[np.isfinite(a)]
 return [val(a[int(.025*len(a))]),val(a[int(.975*len(a))-1])] if len(a) else [None,None]
def ps(y,a):
 y=np.asarray(y,bool);a=np.asarray(a,bool);e=int(y.sum());n=len(y)-e;h=int((y&a).sum());f=int((~y&a).sum());return dict(n=len(y),events=e,hits=h,false_alarms=f,POD=val(h/e) if e else None,POFD=val(f/n) if n else None,FAR=val(f/(h+f)) if h+f else None,PSS=val(h/e-f/n) if e and n else None)
def prob(pred,res,thr):
 s=np.sort(np.asarray(res,float));return (len(s)-np.searchsorted(s,thr-np.asarray(pred,float),side='left'))/len(s)
def design(d,m):
 if m=='G0c':return np.column_stack([np.ones(len(d)),d.gust.to_numpy(float)])
 if m=='G1a':return np.column_stack([np.ones(len(d)),d.u.to_numpy(float)])
 return np.column_stack([np.ones(len(d)),d.gfs_u.to_numpy(float)])
def group(d,top=True):
 y=d.event.to_numpy(bool);clim=((d.event-d.clim)**2).mean();o={'n':len(d),'events':int(y.sum()),'methods':{}}
 for m in METHODS:
  z=ps(y,d[m+'_alarm'].to_numpy(bool));z['brier']=val(np.mean((y-d[m].to_numpy(float))**2)) if m!='G0' else None;z['BSS_vs_C']=val(1-z['brier']/clim) if m!='G0' and clim else None
  o['methods'][m]=z
 if top:
  o['topk']={}
  for m in METHODS+['G0_station_percentile']:
   a=d.sort_values([m,'station','init_utc','lead_h'],ascending=[False,True,True,True],kind='mergesort');o['topk'][m]={}
   for name,k in [('5pct',math.ceil(.05*len(a))),('events',int(y.sum()))]:
    o['topk'][m][name]={'k':k,'capture':val(a.event.iloc[:k].sum()/y.sum()) if y.sum() else None,'random_row_expectation':val(k/len(a))}
 return o
def intervals(d):
 # Identical resampled blocks for all methods and contrasts; inclusive UTC verifying days.
 y=d.event.to_numpy(bool);arr=np.column_stack([y,~y,*[(y&d[m+'_alarm'].to_numpy(bool)) for m in METHODS],*[(~y&d[m+'_alarm'].to_numpy(bool)) for m in METHODS]]).astype(np.int64)
 out={}
 for typ,lab,offset in [('day',d.day.to_numpy(),0),('station',d.station.to_numpy(),1)]:
  ids,inv=np.unique(lab,return_inverse=True);ag=np.zeros((len(ids),12),np.int64);np.add.at(ag,inv,arr)
  rng=np.random.default_rng(SEED+offset);draw={f'{a}-{b}':[] for a,b in PAIRS};idx={m:i for i,m in enumerate(METHODS)}
  for st in range(0,B,100):
   x=ag[rng.integers(len(ids),size=(min(100,B-st),len(ids)))].sum(axis=1);e=x[:,0];ne=x[:,1];ok=(e>0)&(ne>0)
   for a,b in PAIRS:
    ia=idx[a];ib=idx[b];v=np.full(len(x),np.nan);v[ok]=(x[ok,2+ia]-x[ok,2+ib])/e[ok]-(x[ok,7+ia]-x[ok,7+ib])/ne[ok];draw[f'{a}-{b}'].extend(v)
  out[typ]={'blocks':len(ids),'contrasts':{key:{'CI95':ci(v),'valid':int(np.isfinite(v).sum())} for key,v in draw.items()}}
 return out
def main():
 print('SUPP_START',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),flush=True)
 raw=pd.read_csv(BASE/'pairs_p2.csv.gz',low_memory=False);frozen=pd.read_csv(BASE/'predictions_p2.csv.gz',low_memory=False)
 assert len(raw)==803344
 gfs=raw[raw.source=='GFS'][['station','init_utc','lead_h','fc_u10_ms','fc_v10_ms','fc_gust_ms','m5_v1_ms','m5_delta_z_m']].copy();gfs['gfs_u']=np.hypot(gfs.fc_u10_ms,gfs.fc_v10_ms);gfs['gfs_sector']=np.floor(((np.degrees(np.arctan2(-gfs.fc_u10_ms,-gfs.fc_v10_ms))+360)%360+45)%360/90).astype('Int64');gfs=gfs.rename(columns={'fc_gust_ms':'gust','m5_v1_ms':'v1','m5_delta_z_m':'dz'})[['station','init_utc','lead_h','gfs_u','gfs_sector','gust','v1','dz']]
 out={'label':'事后补充，不参加主判','B':B,'seed':SEED,'sources':{},'supplementary_rules':['G0 原阵风速度没有概率，Brier/BSS 不适用；G0c/G1a/G1g 使用训练内残差概率与训练内 PSS 最大化 p*。','站内标准化 G0 以训练季本站 GFS GUST 经验分布的右连续百分位定义；同分再按站名/起报/提前量排序。','站×扇区样本少于 30 回退至本站全部训练季，与冻结 G1 一致。','区间为相同重抽样本上的 PSS 配对差，不改冻结主判。']}
 predictions=[]
 for src in SRC:
  r=raw[raw.source==src].merge(gfs,on=['station','init_utc','lead_h'],how='left',validate='one_to_one');r['u']=np.hypot(r.fc_u10_ms,r.fc_v10_ms);r['direction']=(np.degrees(np.arctan2(-r.fc_u10_ms,-r.fc_v10_ms))+360)%360;r['sector']=np.floor(((r.direction+45)%360)/90).astype('Int64');r['obs']=r.obs_gust_1s_ms
  r=r[(r.obs_6x10min_complete==1)&r[['obs','u','gust','v1','dz','gfs_u']].notna().all(axis=1)].copy()
  train=r[r.season.isin([1,2])];t=r[r.season==3].copy();ref=frozen[frozen.source==src].copy();keys=['station','init_utc','lead_h'];assert len(ref)==len(t)
  t=t.merge(ref[keys+['event','threshold','clim','G0','G0_alarm','G1','G1_alarm','day']],on=keys,validate='one_to_one',suffixes=('','_frozen'))
  assert len(t)==len(ref) and t.event.sum()==ref.event.sum() and np.allclose(t.gust,t.G0) and (t.obs>=t.threshold).eq(t.event).all()
  t['G0_station_percentile']=np.nan
  for m in ['G0c','G1a','G1g']:t[m]=np.nan;t[m+'_alarm']=False
  fallback=[];fitlog=[]
  for station in sorted(t.station.unique()):
   own=train[train.station==station];part=t[t.station==station]
   sorted_g=np.sort(own.gust.to_numpy(float));t.loc[part.index,'G0_station_percentile']=np.searchsorted(sorted_g,part.gust.to_numpy(float),side='right')/len(sorted_g)
   for m in ['G0c','G1a','G1g']:
    pp=[];yy=[]
    sector_col='gfs_sector' if m=='G0c' else 'sector'
    for sec in sorted(part[sector_col].dropna().unique()):
     n=int((own[sector_col]==sec).sum());tr=own[own[sector_col]==sec] if n>=30 else own
     if n<30:fallback.append(dict(station=station,method=m,sector=int(sec),n=n))
     sub=part[part[sector_col]==sec];x=design(tr,m);c=np.linalg.lstsq(x,tr.obs.to_numpy(),rcond=None)[0];res=tr.obs.to_numpy()-x@c;p=prob(design(sub,m)@c,res,sub.threshold.to_numpy());t.loc[sub.index,m]=p
     # Frozen G1 p* uses all own training rows in that sector, even when fit fallback is full-station.
     trp=own[own[sector_col]==sec];pp.append(prob(design(trp,m)@c,res,trp.station.map(train.groupby('station').obs.quantile(.95)).to_numpy()));yy.append((trp.obs>=trp.station.map(train.groupby('station').obs.quantile(.95))).to_numpy())
     fitlog.append(dict(station=station,method=m,sector=int(sec),n=len(tr),coefficients=c.tolist()))
    p=np.concatenate(pp);y=np.concatenate(yy);grid=np.arange(.05,.951,.05);score=[ps(y,p>=v)['PSS'] for v in grid];best=int(np.nanargmax(score));threshold=float(grid[best]);t.loc[part.index,m+'_alarm']=t.loc[part.index,m]>=threshold;fitlog.append(dict(station=station,method=m,pstar=threshold,train_PSS=score[best]))
  assert t[['G0c','G1a','G1g','G0_station_percentile']].notna().all().all()
  pooled=group(t);d={'sample':{'train':len(train),'test':len(t),'events':int(t.event.sum()),'stations':t.station.nunique()},'pooled':pooled,'by_lead':{str(k):group(v) for k,v in t.groupby('lead_h')},'by_terrain':{str(k):group(v) for k,v in t.groupby('terrain')},'contrasts':{f'{a}-{b}':val(pooled['methods'][a]['PSS']-pooled['methods'][b]['PSS']) for a,b in PAIRS},'CI95':intervals(t),'fallback':fallback,'fitlog':fitlog}
  out['sources'][src]=d
  predictions.append(t[['source','station','terrain','init_utc','lead_h','valid_end_utc','event','threshold','G0','G0_alarm','G0c','G0c_alarm','G1','G1_alarm','G1a','G1a_alarm','G1g','G1g_alarm','G0_station_percentile']])
  print('SOURCE_DONE',src,len(t),flush=True)
 pd.concat(predictions).to_csv(OUT/'predictions_supp.csv.gz',index=False,compression={'method':'gzip','compresslevel':6,'mtime':0})
 (OUT/'metrics_supp.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
 with gzip.open(OUT/'predictions_supp.csv.gz','rb') as f: pass
 (OUT/'manifest_supp.json').write_text(json.dumps({p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in [OUT/'metrics_supp.json',OUT/'predictions_supp.csv.gz']},indent=2))
 print('SUPP_DONE',flush=True)
if __name__=='__main__':main()
