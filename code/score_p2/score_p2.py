#!/usr/bin/env python3
"""Frozen P2/P3 scorer. Inputs are read-only, outputs under /content/score_p2.
No test-season observation enters fits, thresholds, residual distributions or p*.
"""
import os, json, math, gzip, hashlib, time
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path('/content/score_p2'); ROOT.mkdir(exist_ok=True)
DATA=Path('/content/pairs_p2.csv.gz')
B=10000; SEED=20261111; LEADS=[24,30,36,42,48]; SOURCES=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS']; TERR=['ridge','pass','valley','plateau','plain']
DEVIATIONS=[
 'P1 的 obs_event_counts_lead.json 是不配预报的观测子集；本评分按完整共同样本重新计 E95 事件，不把 1062 硬塞入共同样本。',
 'G1/G2 训练残差采用训练内拟合残差的经验分布；训练季 p* 对应训练内概率，非交叉拟合。格点风向采用气象来向 atan2(-u,-v) 并以 ±45° 为 N/E/S/W 边界。',
 'G2 的阈值仍使用留出站训练季 P95，仅用于概率事件，属偏乐观参照；无本站实测的真正零样本站点不可知该阈值。',
 '工程阈值仅报发生率及共同样本分组的同一告警二值诊断；同一站 P95 概率告警并非工程阈值概率预报，不据此下工程技能结论。',
 'M5 原 fhr 分档为 6/12/24/48，与 P2 的 24/30/36/42/48 不一致；按本床五个 fhr 分档复用原 design/LOSO-本站 OLS 定义，仅 GFS，严格标为跨床复验非原 M5 逐值复现。',
 '预注册未给 Top-k 的相等分数、k 整数舍入、Brier 零基线及稀少事件无两类时的处理：以 station/init/lead 稳定字典序破同分，ceil(5%N)、事件数整数；Brier 气候分母为零、PSS 缺类返回 null；不单判检验事件 <10 的站×阈值。',
 '预注册仅明示 E95 的站 P95；3 s 阵风和 E99 分别由本站对应训练季 3 s P95/1 s P99 定义，并单列不判；绝对工程阈值仍依观测 1 s 阵风或 10 min 均风。'
]
def f(x):return float(x) if np.isfinite(x) else None
def quant(x):return [f(np.quantile(x,.05)),f(np.quantile(x,.95))]
def ci(x):
 a=np.sort(np.asarray(x,dtype=float));a=a[np.isfinite(a)];return [f(a[int(.025*len(a))]),f(a[int(.975*len(a))-1])] if len(a) else [None,None]
def ps(y,alarm):
 y=np.asarray(y,bool);a=np.asarray(alarm,bool);e=y.sum();ne=len(y)-e
 return {'n':len(y),'events':int(e),'hits':int((y&a).sum()),'false_alarms':int((~y&a).sum()),'POD':f((y&a).sum()/e) if e else None,'POFD':f((~y&a).sum()/ne) if ne else None,'FAR':f((~y&a).sum()/a.sum()) if a.sum() else None,'PSS':f((y&a).sum()/e-(~y&a).sum()/ne) if e and ne else None}
def fit(A,y):return np.linalg.lstsq(np.asarray(A,float),np.asarray(y,float),rcond=None)[0]
def matrix_g2(d):
 r=d['u'].to_numpy();v=d['v1'].to_numpy();z=d['dz'].to_numpy();g=d['gust'].to_numpy()
 return np.column_stack((np.ones(len(d)),r,v,z,r*z,g,*[(d.terrain==t).to_numpy(float) for t in TERR[:-1]]))
def matrix_g1(d):return np.column_stack((np.ones(len(d)),d.u.to_numpy(),d.gust.to_numpy()))
def prob(pred,res,threshold):
 s=np.sort(np.asarray(res,float));return (len(s)-np.searchsorted(s,threshold-np.asarray(pred,float),side='left'))/len(s)
def kscore(d,method,kind):
 z=d.sort_values([method,'station','init_utc','lead_h'],ascending=[False,True,True,True],kind='mergesort');k=math.ceil(.05*len(z)) if kind=='5pct' else int(z.event.sum());return {'k':k,'capture':f(z.event.iloc[:k].sum()/z.event.sum()) if z.event.sum() else None,'random_row_expectation':f(k/len(z))}
def block_counts(d,labels,kind):
 # One draw for both methods. Confusion cells are additive over whole blocks.
 cells=np.column_stack([d.event.to_numpy(int),1-d.event.to_numpy(int), (d.event & d.G0_alarm).to_numpy(int), (~d.event & d.G0_alarm).to_numpy(int), (d.event & d.G1_alarm).to_numpy(int), (~d.event & d.G1_alarm).to_numpy(int)])
 ids,un=np.unique(labels,return_inverse=True);agg=np.zeros((len(ids),6),dtype=np.int64);np.add.at(agg,un,cells)
 rng=np.random.default_rng(SEED+(0 if kind=='day' else 1));draw=np.zeros(B)
 for st in range(0,B,250):
  inds=rng.integers(0,len(ids),size=(min(250,B-st),len(ids)));cnt=agg[inds].sum(axis=1);ok=(cnt[:,0]>0)&(cnt[:,1]>0)
  dd=np.full(len(cnt),np.nan);dd[ok]=(cnt[ok,4]-cnt[ok,2])/cnt[ok,0]-(cnt[ok,5]-cnt[ok,3])/cnt[ok,1];draw[st:st+len(cnt)]=dd
 return {'unit':kind,'blocks':len(ids),'valid':int(np.isfinite(draw).sum()),'CI95':ci(draw)}
def topk_day_ci(d,method,kind):
 # Resample verifying UTC days; keep all rows in each sampled block, including repeated days.
 a=d.sort_values([method,'station','init_utc','lead_h'],ascending=[False,True,True,True],kind='mergesort');ids,day=np.unique(a.day.to_numpy(),return_inverse=True);y=a.event.to_numpy(np.int16);N=len(a)
 rng=np.random.default_rng(SEED+100+(['G0','G1','G2'].index(method))*10+(kind=='events'))
 out=np.full(B,np.nan)
 for i in range(B):
  w=np.bincount(rng.integers(0,len(ids),len(ids)),minlength=len(ids))[day];total=int(w.sum());ev=int(w@y);k=math.ceil(.05*total) if kind=='5pct' else ev
  if ev and k:
   cw=np.cumsum(w);cut=np.searchsorted(cw,k,side='left');hits=int(w[:cut]@y[:cut]);hits+=int((k-(cw[cut-1] if cut else 0))*y[cut]);out[i]=hits/ev
 return {'CI95':ci(out),'valid':int(np.isfinite(out).sum())}
def reliability(d,m):
 bins=np.minimum(np.floor(d[m].to_numpy()*10).astype(int),9);return [{'bin':i,'n':int((bins==i).sum()),'forecast_mean':f(d.loc[bins==i,m].mean()) if (bins==i).any() else None,'observed_frequency':f(d.event.to_numpy()[bins==i].mean()) if (bins==i).any() else None} for i in range(10)]
def score_group(d,top=False):
 out={'n':len(d),'events':int(d.event.sum()),'methods':{m:ps(d.event,d[m+'_alarm']) for m in ['G0','G1','G2']}}
 c=((d.event-d.clim)**2).mean()
 for m in ['G1','G2']:
  b=((d.event-d[m])**2).mean();out['methods'][m].update({'brier':f(b),'BSS_vs_C':f(1-b/c) if c else None,'coverage90':f(((d.obs>=d[m+'_low'])&(d.obs<=d[m+'_high'])).mean())})
 if top:
  out['topk']={m:{kind:dict(kscore(d,m,kind),**topk_day_ci(d,m,kind)) for kind in ['5pct','events']} for m in ['G0','G1','G2']}
  out['reliability']={m:reliability(d,m) for m in ['G1','G2']}
 return out
def make_predictions(allrows,src,target):
 gfs=allrows[allrows.source=='GFS'][['station','init_utc','lead_h','fc_gust_ms','m5_v1_ms','m5_delta_z_m']].rename(columns={'fc_gust_ms':'gust','m5_v1_ms':'v1','m5_delta_z_m':'dz'})
 a=allrows[allrows.source==src].merge(gfs,on=['station','init_utc','lead_h'],how='left',validate='one_to_one')
 a['u']=np.hypot(a.fc_u10_ms,a.fc_v10_ms);a['direction']=(np.degrees(np.arctan2(-a.fc_u10_ms,-a.fc_v10_ms))+360)%360
 a['sector']=np.floor(((a.direction+45)%360)/90).astype('Int64')
 a['obs']=a[target];a=a[(a.obs_6x10min_complete==1)&a[['obs','u','gust','v1','dz']].notna().all(axis=1)].copy()
 a['day']=a.valid_end_utc.str[:10];a['event']=False
 assert a.duplicated(['station','init_utc','lead_h']).sum()==0
 train=a[a.season.isin([1,2])];test=a[a.season==3].copy()
 threshold=train.groupby('station').obs.quantile(.95);test['threshold']=test.station.map(threshold)
 test['event']=test.obs>=test.threshold
 test['G0']=test.gust;test['G0_alarm']=test.G0>=test.threshold
 test['clim']=test.station.map(train.assign(event=train.obs>=train.station.map(threshold)).groupby('station').event.mean())
 for m in ['G1','G2']:test[m]=np.nan;test[m+'_pred']=np.nan;test[m+'_low']=np.nan;test[m+'_high']=np.nan;test[m+'_alarm']=False
 fitlog=[]; fallback=[]
 for station in sorted(test.station.unique()):
  own=train[train.station==station];other=train[train.station!=station];ix=test.station==station;part=test.loc[ix]
  for method in ['G1','G2']:
   if method=='G1':
    training=own;sectors=sorted(part.sector.dropna().unique());train_sets={sector:own[own.sector==sector] if (own.sector==sector).sum()>=30 else own for sector in sectors};fallback.extend([{'source':src,'target':target,'station':station,'sector':int(s),'n':int((own.sector==s).sum())} for s in sectors if (own.sector==s).sum()<30]);builder=matrix_g1
   else: training=other;sectors=[-1];train_sets={-1:other};builder=matrix_g2
   # p* uses all training data at this station (G2 other stations' observations and their own P95 thresholds).
   trpred=[];trprob=[];tryy=[]
   for sector in sectors:
    t=train_sets[sector];sel=part.sector==sector if method=='G1' else np.ones(len(part),bool);sub=part.loc[sel]
    if not len(sub):continue
    c=fit(builder(t),t.obs);res=t.obs.to_numpy()-builder(t)@c;pred=builder(sub)@c;p=prob(pred,res,sub.threshold.to_numpy());q=np.quantile(res,[.05,.95]);test.loc[sub.index,method]=p;test.loc[sub.index,method+'_pred']=pred;test.loc[sub.index,method+'_low']=pred+q[0];test.loc[sub.index,method+'_high']=pred+q[1]
    fitlog.append({'source':src,'target':target,'station':station,'method':method,'sector':int(sector),'n':len(t),'coefficients':c.tolist()})
    tr=training[training.sector==sector] if method=='G1' else training
    trp=builder(tr)@c;trpred.append(trp);trprob.append(prob(trp,res,tr.station.map(threshold).to_numpy()));tryy.append((tr.obs>=tr.station.map(threshold)).to_numpy())
   pp=np.concatenate(trprob);yy=np.concatenate(tryy);grid=np.arange(.05,.951,.05);scores=[ps(yy,pp>=z)['PSS'] for z in grid];best=int(np.nanargmax(scores));pstar=float(grid[best]);test.loc[ix,method+'_alarm']=test.loc[ix,method]>=pstar
   fitlog.append({'source':src,'target':target,'station':station,'method':method,'pstar':pstar,'train_PSS':scores[best]})
 assert test[['G1','G2','G1_pred','G2_pred']].notna().all().all()
 return test,fitlog,fallback,{'train':len(train),'test':len(test),'events':int(test.event.sum()),'stations':int(test.station.nunique())}
def m5(data):
 a=data[data.source=='GFS'].copy();a['raw']=np.hypot(a.fc_u10_ms,a.fc_v10_ms);a['v1']=a.m5_v1_ms;a['dz']=a.m5_delta_z_m;a['obs']=a.obs_mean_ms;a=a[(a.obs_6x10min_complete==1)&a[['raw','v1','dz','obs']].notna().all(axis=1)].copy();a['day']=a.valid_end_utc.str[:10]
 train=a[a.season.isin([1,2])];test=a[a.season==3].copy();methods=['R','T0','D2','M','M+D1'];test['R']=test.raw
 def design(d,m):
  if m in ['T0','M']:return np.column_stack([np.ones(len(d)),d.raw])
  if m=='M+D1':return np.column_stack([np.ones(len(d)),d.raw,d.v1])
  return np.column_stack([np.ones(len(d)),d.raw,d.v1,d.dz,d.raw*d.dz,*[(d.terrain==t).to_numpy(float) for t in TERR[:-1]]])
 for (st,lead),p in test.groupby(['station','lead_h']):
  own=train[(train.station==st)&(train.lead_h==lead)];pool=train[(train.station!=st)&(train.lead_h==lead)]
  for m in methods[1:]:
   tr=own if m.startswith('M') else pool;c=fit(design(tr,m),tr.obs);test.loc[p.index,m]=design(p,m)@c
 out={}
 for lead,p in [('pooled',test)]+[(str(x),test[test.lead_h==x]) for x in LEADS]:
  maes={m:f(np.mean(np.abs(p[m]-p.obs))) for m in methods};n=len(p);days,ix=np.unique(p.day,return_inverse=True);arr=np.column_stack([np.abs(p[m]-p.obs).to_numpy() for m in methods]);agg=np.zeros((len(days),len(methods)+1));np.add.at(agg,ix,np.column_stack([arr,np.ones(n)]));rng=np.random.default_rng(SEED+int(lead) if lead!='pooled' else SEED+500);di=[];mi=[]
  for j in range(0,B,250):
   ss=agg[rng.integers(len(days),size=(min(250,B-j),len(days)))].sum(axis=1);means=ss[:,:-1]/ss[:,-1,None];di.extend((means[:,2]-means[:,1])/means[:,1]);mi.extend((means[:,4]-means[:,3])/means[:,3])
  out[lead]={'n':n,'days':len(days),'MAE':maes,'D2_vs_T0_relative':f((maes['D2']-maes['T0'])/maes['T0']),'D2_vs_T0_CI95':ci(di),'M+D1_vs_M_relative':f((maes['M+D1']-maes['M'])/maes['M']),'M+D1_vs_M_CI95':ci(mi)}
 return out,test

def main():
 print('START',time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),flush=True)
 a=pd.read_csv(DATA,low_memory=False);assert len(a)==803344;assert a.source.nunique()==4;assert a.station.nunique()==37
 allmetrics={'prereg_sha256':'7597e110ad95e600ef9b104d31bafccaa97a01cd8b7a5badd0d6b3c99fee3229','deviations':DEVIATIONS,'sources':{},'M5':None}
 predictions=[];fitlogs=[];fallback=[]
 for src in SOURCES:
  d,logs,fb,counts=make_predictions(a,src,'obs_gust_1s_ms');predictions.append(d);fitlogs.extend(logs);fallback.extend(fb)
  o={'sample':counts,'pooled':score_group(d,top=True),'by_lead':{},'by_terrain':{},'stations':{},'secondary':{}}
  for lead,p in d.groupby('lead_h'):o['by_lead'][str(lead)]=score_group(p)
  for t,p in d.groupby('terrain'):o['by_terrain'][t]=score_group(p)
  for st,p in d.groupby('station'):o['stations'][st]={'terrain':p.terrain.iloc[0],'E95':score_group(p),'eligible_station_verdict':int(p.event.sum())>=10}
  if src==SOURCES[0]:
   o['primary']={'D':f(o['pooled']['methods']['G1']['PSS']-o['pooled']['methods']['G0']['PSS'])};o['primary']['day']=block_counts(d,d.day,'day');o['primary']['station']=block_counts(d,d.station,'station');D=o['primary']['D'];lo=[o['primary'][z]['CI95'][0] for z in ['day','station']];hi=[o['primary'][z]['CI95'][1] for z in ['day','station']];o['primary'].update({'pass':bool(D>0 and all(x>0 for x in lo)),'resolves_negative':bool(all(x is not None and x<.05 for x in hi)),'clearly_worse':bool(all(x is not None and x<0 for x in hi))})
   # Secondary event definitions use separate training-only quantiles and same fitted G1/G2 predictor/residual distributions.
   for name,target,q in [('E99','obs_gust_1s_ms',.99),('E95_3s','obs_gust_3s_ms',.95)]:
    tr=a[(a.source==src)&a.season.isin([1,2])&(a.obs_6x10min_complete==1)];threshold=tr.groupby('station')[target].quantile(q);e=d.copy();e['event']=e[target]>=e.station.map(threshold);o['secondary'][name]={'events':int(e.event.sum()),'G0':ps(e.event,e.G0>=e.station.map(threshold)),'G1_rank':kscore(e,'G1','5pct'),'G2_rank':kscore(e,'G2','5pct'),'note':'仅用 E95 训练模型的概率/排名作跨阈诊断，非此事件阈值的重新校准概率'}
   for name,field,threshold in [('bridge_20.1','obs_gust_1s_ms',20.1),('bridge_26.8','obs_gust_1s_ms',26.8),('bridge_31.3','obs_gust_1s_ms',31.3),('MEWP_12.5','obs_gust_1s_ms',12.5),('Beaufort_mean_11.1','obs_mean_ms',11.1)]:
    e=d.copy();e['event']=e[field]>=threshold;o['secondary'][name]={'events':int(e.event.sum()),'pooled':{m:ps(e.event,e[m+'_alarm']) for m in ['G0','G1','G2']},'by_terrain':{t:{'n':len(p),'events':int(p.event.sum()),'G0':ps(p.event,p.G0_alarm),'G1':ps(p.event,p.G1_alarm),'G2':ps(p.event,p.G2_alarm)} for t,p in e.groupby('terrain')},'station_lt10':[st for st,p in e.groupby('station') if p.event.sum()<10]}
  allmetrics['sources'][src]=o;print('SOURCE_DONE',src,counts,flush=True)
 pd.concat(predictions).drop(columns=['forecast_object_url']).to_csv(ROOT/'predictions_p2.csv.gz',index=False,compression={'method':'gzip','compresslevel':6,'mtime':0});(ROOT/'fits_p2.json').write_text(json.dumps({'fits':fitlogs,'fallback':fallback},allow_nan=False))
 allmetrics['M5'],mp=m5(a);mp[['station','terrain','season','init_utc','lead_h','valid_end_utc','obs','R','T0','D2','M','M+D1']].to_csv(ROOT/'m5_predictions.csv.gz',index=False,compression={'method':'gzip','compresslevel':6,'mtime':0});print('M5_DONE',flush=True)
 (ROOT/'metrics_p2.json').write_text(json.dumps(allmetrics,indent=2,allow_nan=False,ensure_ascii=False));print('SCORE_DONE',flush=True)
if __name__=='__main__':main()
