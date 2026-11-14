#!/usr/bin/env python3
"""Secondary-only scoring, never modifies frozen P2. Run on Colab CPU.
Inputs: /content/pairs_p2.csv.gz; output: /content/score_p2_sec.
"""
import json, math, hashlib, gzip, time
from pathlib import Path
import numpy as np
import pandas as pd
OUT=Path('/content/score_p2_sec'); OUT.mkdir(exist_ok=True)
PAIRS=Path('/content/pairs_p2.csv.gz')
SOURCES=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS']
TERR=['ridge','pass','valley','plateau','plain']
EVENTS={'E99':('obs_gust_1s_ms',.99),'E95_3s':('obs_gust_3s_ms',.95),'bridge_20.1':('obs_gust_1s_ms',20.1),'bridge_26.8':('obs_gust_1s_ms',26.8),'bridge_31.3':('obs_gust_1s_ms',31.3),'MEWP_12.5':('obs_gust_1s_ms',12.5),'Beaufort_mean_11.1':('obs_mean_ms',11.1)}
METHODS=['G0','G1','G2','G0c']; GRID=np.arange(.05,.951,.05)
def scalar(v):return float(v) if np.isfinite(v) else None
def sector(u,v):return np.floor(((np.degrees(np.arctan2(-u,-v))+360+45)%360)/90).astype('Int64')
def design(d,method):
 if method=='G1':return np.column_stack([np.ones(len(d)),d.u.to_numpy(),d.gust.to_numpy()])
 if method=='G0c':return np.column_stack([np.ones(len(d)),d.gust.to_numpy()]) if d.attrs.get('target')!='obs_mean_ms' else np.column_stack([np.ones(len(d)),d.gfs_speed.to_numpy()])
 u=d.u.to_numpy();z=d.dz.to_numpy();return np.column_stack([np.ones(len(d)),u,d.v1.to_numpy(),z,u*z,d.gust.to_numpy(),*[(d.terrain==t).to_numpy(float) for t in TERR[:-1]]])
def fit(x,y):return np.linalg.lstsq(x,y,rcond=None)[0]
def probability(pred,res,thr):
 s=np.sort(res);return (len(s)-np.searchsorted(s,np.asarray(thr)-pred,side='left'))/len(s)
def confusion(y,alarm):
 y=np.asarray(y,bool);a=np.asarray(alarm,bool);ev=int(y.sum());ne=len(y)-ev;h=int((y&a).sum());fa=int((~y&a).sum());return {'n':len(y),'events':ev,'hits':h,'false_alarms':fa,'PSS':scalar(h/ev-fa/ne) if ev and ne else None,'POD':scalar(h/ev) if ev else None,'POFD':scalar(fa/ne) if ne else None,'FAR':scalar(fa/(h+fa)) if h+fa else None}
def score(d,top):
 y=d.event.to_numpy(bool);q={'n':len(d),'events':int(y.sum()),'methods':{}}
 c=np.mean((y-d.clim.to_numpy())**2) if len(d) else np.nan
 for m in METHODS:
  p=confusion(y,d[m+'_alarm']);p['brier']=scalar(np.mean((y-d[m+'_prob'].to_numpy())**2)) if m!='G0' and len(d) else None;p['BSS_vs_C']=scalar(1-p['brier']/c) if m!='G0' and c and np.isfinite(c) else None
  if top:
   order=d.sort_values([m+'_rank','station','init_utc','lead_h'],ascending=[False,True,True,True],kind='mergesort');p['topk']={}
   for label,k in [('5pct',math.ceil(.05*len(d))),('events',int(y.sum()))]:p['topk'][label]={'k':k,'capture':scalar(order.event.iloc[:k].sum()/y.sum()) if y.sum() else None}
  q['methods'][m]=p
 return q
def prepare(raw,source):
 g=raw[raw.source=='GFS'][['station','init_utc','lead_h','fc_u10_ms','fc_v10_ms','fc_gust_ms','m5_v1_ms','m5_delta_z_m']].copy()
 g['gfs_speed']=np.hypot(g.fc_u10_ms,g.fc_v10_ms);g['gfs_sector']=sector(g.fc_u10_ms,g.fc_v10_ms)
 g=g.rename(columns={'fc_gust_ms':'gust','m5_v1_ms':'v1','m5_delta_z_m':'dz'})[['station','init_utc','lead_h','gfs_speed','gfs_sector','gust','v1','dz']]
 d=raw[raw.source==source].merge(g,on=['station','init_utc','lead_h'],how='left',validate='one_to_one')
 d['u']=np.hypot(d.fc_u10_ms,d.fc_v10_ms);d['sector']=sector(d.fc_u10_ms,d.fc_v10_ms)
 d=d[(d.obs_6x10min_complete==1)&d[['u','gust','v1','dz','gfs_speed','obs_gust_1s_ms','obs_gust_3s_ms','obs_mean_ms']].notna().all(axis=1)].copy()
 assert not d.duplicated(['station','init_utc','lead_h']).any()
 return d

def run():
 print('SEC_START',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),flush=True)
 raw=pd.read_csv(PAIRS,low_memory=False);assert len(raw)==803344 and raw.station.nunique()==37
 # Station observation thresholds are independent of source and lead multiplicity.
 o=raw[(raw.season.isin([1,2]))&(raw.obs_6x10min_complete==1)][['station','valid_end_utc','obs_gust_1s_ms','obs_gust_3s_ms']].drop_duplicates(['station','valid_end_utc'])
 assert not o.duplicated(['station','valid_end_utc']).any();thresholds={}
 for key,(field,value) in EVENTS.items():
  thresholds[key]=o.groupby('station')[field].quantile(value).to_dict() if key in ('E99','E95_3s') else {st:value for st in o.station.unique()}
 result={'label':'只报不判；预注册副事件按各自阈值重算','input_sha256':hashlib.sha256(PAIRS.read_bytes()).hexdigest(),'training_unique_observation_count':len(o),'thresholds':thresholds,'sources':{},'rules':['训练季观测在(station,valid_end_utc)去重后求站阈值；G0c GFS风向扇区；G1取该源风向扇区。','G0c定义采用事后对照：站×GFS风向扇区 OLS；均风情境的G0c是GFS 10m风速的相同站点校准，属保守补定。','G1/G2/G0c各自针对事件阈值重算训练残差超阈概率和训练季PSS最大化p*；同一目标观测的OLS系数不因二值阈值改变；均风目标另行拟合。','G2在留出本站的其余站训练残差和事件上选p*，留出本站的站阈值只用于概率（乐观参考）。','G0不具有概率，Brier/BSS为null；G1/G2/G0c气候参考为训练季本站事件频率。','Top-k按station/init_utc/lead_h稳定破同分，k=ceil(5%N)或检验事件配对行数。','站×阈值检验事件<10只计入合并，不单独下结论。']}
 records=[]
 for src in SOURCES:
  d=prepare(raw,src);train=d[d.season.isin([1,2])].copy();test=d[d.season==3].copy()
  assert train.station.nunique()==test.station.nunique()==37
  source_out={}
  for event,(field,_) in EVENTS.items():
   target='obs_mean_ms' if field=='obs_mean_ms' else ('obs_gust_3s_ms' if field=='obs_gust_3s_ms' else 'obs_gust_1s_ms')
   t=train.copy();h=test.copy();t.attrs['target']=target;h.attrs['target']=target
   thr=thresholds[event];t['threshold']=t.station.map(thr);h['threshold']=h.station.map(thr)
   t['event']=t[field]>=t.threshold;h['event']=h[field]>=h.threshold
   h['clim']=h.station.map(t.groupby('station').event.mean());h['G0_rank']=h.gfs_speed if target=='obs_mean_ms' else h.gust
   h['G0_alarm']=h.G0_rank>=h.threshold
   for m in METHODS[1:]:h[m+'_prob']=np.nan;h[m+'_alarm']=False;h[m+'_rank']=np.nan
   pstar={};fallback=[]
   for st in sorted(h.station.unique()):
    own=t[t.station==st];other=t[t.station!=st];ix=h.station==st;part=h.loc[ix]
    for m in METHODS[1:]:
     col='gfs_sector' if m=='G0c' else 'sector'
     parts=[-1] if m=='G2' else sorted(part[col].unique())
     probs=[];labels=[]
     for sec in parts:
      tr=other if m=='G2' else own[own[col]==sec]
      if m!='G2' and len(tr)<30:tr=own;fallback.append([st,m,int(sec)])
      tr.attrs['target']=target
      coefficient=fit(design(tr,m),tr[target].to_numpy());res=tr[target].to_numpy()-design(tr,m)@coefficient
      sub=part if m=='G2' else part[part[col]==sec];sub.attrs['target']=target
      if len(sub):
       pr=probability(design(sub,m)@coefficient,res,sub.threshold.to_numpy());h.loc[sub.index,m+'_prob']=pr;h.loc[sub.index,m+'_rank']=pr
      trscore=other if m=='G2' else own[own[col]==sec];trscore.attrs['target']=target
      if len(trscore):
       probs.append(probability(design(trscore,m)@coefficient,res,trscore.threshold.to_numpy()))
       labels.append(trscore.event.to_numpy(bool))
     pp=np.concatenate(probs);yy=np.concatenate(labels)
     scores=np.array([confusion(yy,pp>=p)['PSS'] for p in GRID]);best=int(np.nanargmax(scores));star=float(GRID[best]);pstar.setdefault(st,{})[m]=star;h.loc[ix,m+'_alarm']=h.loc[ix,m+'_prob']>=star
   assert h[[m+'_prob' for m in METHODS[1:]]].notna().all().all()
   pooled=score(h,True);by_terrain={str(k):score(v,True) for k,v in h.groupby('terrain')};counts=h.groupby('station').event.sum();excluded=[str(k) for k,v in counts.items() if v<10]
   source_out[event]={'target':field,'n_train':len(t),'n_test':len(h),'unique_test_events':int(h.loc[h.event,['station','valid_end_utc']].drop_duplicates().shape[0]),'pooled':pooled,'by_terrain':by_terrain,'station_lt10':excluded,'pstar':pstar,'fallback':fallback}
   cols=['station','terrain','source','init_utc','lead_h','valid_end_utc','event','threshold','G0_rank','G0_alarm','clim']
   records.append(h.assign(event_name=event)[cols+['event_name']+[m+'_'+suffix for m in METHODS[1:] for suffix in ('prob','alarm')]])
   print('EVENT_DONE',src,event,len(h),int(h.event.sum()),flush=True)
  result['sources'][src]=source_out
 # Original table 6 audit: 2608 vs 2603 is a different threshold and denominator, not a computationally reconciled count.
 original_2608=2608; original_2603=2603
 result['three_second_audit']={'original_first_table_events':original_2608,'original_cross_source_table_events':original_2603,'note':'首表站阈值在按提前量重复的FOUR训练行上取；后表按旧主判E95的站P95告警换3s标签，报告者另用另一训练观测集阈值；下方独立核算旧口径的标签数并指出差异。'}
 (OUT/'metrics_sec.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
 pd.concat(records,ignore_index=True).to_csv(OUT/'predictions_sec.csv.gz',index=False,compression={'method':'gzip','compresslevel':6,'mtime':0})
 print('SEC_DONE',flush=True)
if __name__=='__main__':run()
