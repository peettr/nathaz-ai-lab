#!/usr/bin/env python3
"""A1 preregistered 2022-train/2023-test verification, no test-year model selection.
Inputs: station table, date years, forecast source list, immutable forecast parts,
METAR month CSV, 1-minute mixed observation station series and preliminary 2023 rows.
"""
import argparse,json,glob,collections
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit
from scipy.optimize import minimize
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
LEADS=[6,12,24,36,48,72];WIND=[6,8,10,12];GUST=[10,13,15]
KEY=['station','init_utc','lead_h']
def fl(v):return None if not np.isfinite(v) else float(v)
def lin(x,y):
 m=np.isfinite(x)&np.isfinite(y)
 if m.sum()<12:return [float(np.nanmean(y[m])),0.] if m.any() else [np.nan,np.nan]
 if np.std(x[m])<1e-8:return [float(np.mean(y[m])),0.]
 b,a=np.polyfit(x[m],y[m],1);return [float(a),float(b)]
def logistic(x,y):
 m=np.isfinite(x)&np.isfinite(y);x=x[m];y=y[m]
 if len(x)<30:return [0.,float(np.log((y.sum()+.5)/(len(y)-y.sum()+.5)))],len(x)
 mu=x.mean();sigma=max(x.std(),.1);xx=(x-mu)/sigma
 if y.sum()==0 or y.sum()==len(y):return [0.,float(np.log((y.sum()+.5)/(len(y)-y.sum()+.5)))],len(x)
 def loss(c):
  z=c[0]+c[1]*xx
  return np.logaddexp(0,z).sum()-(y*z).sum()+.01*c[1]**2
 res=minimize(loss,[float(np.log((y.mean()+.001)/(1-y.mean()+.001))),0.],method='BFGS')
 return [float(res.x[1]/sigma),float(res.x[0]-res.x[1]*mu/sigma)],len(x)
def evt(y,x,threshold,p=None):
 m=np.isfinite(y)&np.isfinite(x);o=y[m]>=threshold;f=x[m]>=threshold;h=int((o&f).sum());miss=int((o&~f).sum());fa=int((~o&f).sum())
 brier=None
 if p is not None:
  mp=np.isfinite(y)&np.isfinite(p)
  if mp.any():brier=fl(np.mean((p[mp]-(y[mp]>=threshold))**2))
 return {'n':int(m.sum()),'events':int(o.sum()),'hits':h,'misses':miss,'false_alarms':fa,'hit_rate':fl(h/(h+miss) if h+miss else np.nan),'false_alarm_ratio':fl(fa/(h+fa) if h+fa else np.nan),'csi':fl(h/(h+miss+fa) if h+miss+fa else np.nan),'misclassification_rate':fl((miss+fa)/len(o) if len(o) else np.nan),'brier_probability':brier}
def score(g,src,lead,variant,ycol,xcol,dircol=None,gustcol=None):
 y=g[ycol].to_numpy();x=g[xcol].to_numpy();m=np.isfinite(y)&np.isfinite(x);d=g['minute_dir' if ycol=='minute_speed' else 'obs_dir'].to_numpy();dd=g[dircol].to_numpy() if dircol else None
 md=m&np.isfinite(d)&np.isfinite(dd) if dd is not None else np.zeros(len(g),bool)
 r={'source':src,'lead_h':int(lead),'variant':variant,'observation':'METAR_2min' if ycol=='metar_speed' else 'minute_1h','n':int(m.sum()),'mae':fl(np.mean(abs(x[m]-y[m])) if m.any() else np.nan),'bias':fl(np.mean(x[m]-y[m]) if m.any() else np.nan),'direction_mae_deg':fl(np.mean(abs((dd[md]-d[md]+180)%360-180)) if md.any() else np.nan)}
 for t in WIND:r[f'wind_{t}']=evt(y,x,t,g[f'prob_wind_{t}'].to_numpy() if variant!='raw' and f'prob_wind_{t}' in g else None)
 for t in GUST:r[f'gust_{t}']=evt(g.minute_gust.to_numpy(),g[gustcol].to_numpy(),t,g[f'prob_gust_{t}'].to_numpy() if f'prob_gust_{t}' in g else None) if gustcol else None
 return r
def common(df,sources,obscol):
 keys=KEY;counts=df.groupby(keys).source.nunique();ok=counts[counts==len(sources)].index
 df=df.set_index(keys).loc[ok].reset_index()
 # Pair to finite observed wind and initialization observation; climatology is long-term history.
 df=df[np.isfinite(df[obscol])&np.isfinite(df['persistence'])&np.isfinite(df['climatology'])].copy()
 return df
def paired(test,primary,base,lead):
 a=test[(test.source==primary)&(test.lead_h==lead)].copy()
 if base in ('persistence','climatology'):a['baseline_value']=a[base]
 else:
  b=test[(test.source==base)&(test.lead_h==lead)][KEY+['corrected']].rename(columns={'corrected':'baseline_value'})
  a=a.merge(b,on=KEY,validate='one_to_one')
 return a[np.isfinite(a.corrected)&np.isfinite(a.baseline_value)&np.isfinite(a.metar_speed)]
def gate(g,metric,threshold,seed,reps):
 # Resample verifying UTC days, keeping all paired stations/initializations together.
 day=g.valid_utc.dt.floor('D');unique,inv=np.unique(day.to_numpy(),return_inverse=True);rng=np.random.default_rng(seed);N=len(unique)
 obs=g.metar_speed.to_numpy();aa=g.corrected.to_numpy();bb=g.baseline_value.to_numpy()
 if metric=='mae':
  suma=np.bincount(inv,weights=np.abs(aa-obs),minlength=N);sumb=np.bincount(inv,weights=np.abs(bb-obs),minlength=N)
  point=suma.sum()/sumb.sum()-1
  counts=rng.multinomial(N,np.full(N,1/N),size=reps)
  samples=(counts@suma)/(counts@sumb)-1
 else:
  ev=obs>=8
  def make(x):
   pred=x>=8;return [np.bincount(inv,weights=(ev&pred),minlength=N),np.bincount(inv,weights=(ev&~pred),minlength=N),np.bincount(inv,weights=(~ev&pred),minlength=N)]
  u=make(aa);v=make(bb)
  csi=lambda t:t[0]/(t[0]+t[1]+t[2]) if (t[0]+t[1]+t[2]) else np.nan
  point=csi([x.sum() for x in u])-csi([x.sum() for x in v])
  counts=rng.multinomial(N,np.full(N,1/N),size=reps)
  a=[邮箱](u).T;b=[邮箱](v).T
  samples=a[:,0]/np.maximum(a.sum(axis=1),1)-b[:,0]/np.maximum(b.sum(axis=1),1)
 ci=np.quantile(samples,[.025,.975]).tolist()
 point_pass=bool(point<=threshold) if metric=='mae' else bool(point>=threshold)
 definite=bool(ci[1]<=threshold) if metric=='mae' else bool(ci[0]>=threshold)
 return {'delta':fl(point),'ci95':ci,'threshold':threshold,'point_pass':point_pass,'statistically_supported':definite,'status':('通过' if definite else '点估计通过、统计不确定' if point_pass else '未通过'), 'paired_cases':len(g),'verifying_days':N}
def read_forecasts(parts,year,sources,old=None):
 arrays=[]
 for s in sources:
  files=sorted((Path(parts)/str(year)/s).glob('*.csv'))
  if files:
   print('READ',year,s,len(files),flush=True)
   arrays.append(pd.concat((pd.read_csv(f) for f in files),ignore_index=True))
  elif old and year==2023:
   sub=pd.read_csv(old,usecols=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
   sub=sub[sub.source==s];print('REUSE',year,s,len(sub),flush=True)
   arrays.append(sub)
  else:raise ValueError(f'No forecast files {year} {s}')
 return pd.concat(arrays,ignore_index=True)
def load_obs(args):
 met=[];ledger=[]
 for y in range(args.train_year-9,args.test_year+1):
  files=sorted(Path(args.metar).glob(f'metar_{y}_*.csv'))
  if len(files)!=12:raise ValueError(f'METAR {y} incomplete {len(files)}/12')
  met.extend(pd.read_csv(f) for f in files)
  ledger.extend(json.loads(f.read_text()) for f in sorted(Path(args.metar).glob(f'metar_{y}_*.json')))
 m=pd.concat(met,ignore_index=True);m['valid_utc']=pd.to_datetime(m.valid_utc,utc=True)
 m=m.drop_duplicates(['station','valid_utc']);print('METAR_ROWS',len(m),flush=True)
 c=m[m.valid_utc.dt.year<=args.train_year].copy();c['month']=c.valid_utc.dt.month;c['hour']=c.valid_utc.dt.hour
 climat=c.groupby(['station','month','hour']).obs_speed.agg(['mean','count']).reset_index().rename(columns={'mean':'climatology','count':'climatology_n'})
 one=[]
 for y in (args.train_year,args.test_year):
  o=pd.read_csv(args.minute_mix_template.format(year=y));o=o[o.obs_method=='NCEI_1min_IEM'][['station','valid_utc','obs_speed','obs_gust','obs_dir','obs_count']]
  o=o[pd.to_datetime(o.valid_utc,utc=True).dt.year==y].drop_duplicates(['station','valid_utc'])
  one.append(o)
 one=pd.concat(one,ignore_index=True);one['valid_utc']=pd.to_datetime(one.valid_utc,utc=True)
 one=one.rename(columns={'obs_speed':'minute_speed','obs_gust':'minute_gust','obs_dir':'minute_dir','obs_count':'minute_count'})
 current=m[m.valid_utc.dt.year.isin([args.train_year,args.test_year])][['station','valid_utc','obs_speed','obs_dir']].rename(columns={'obs_speed':'metar_speed'})
 current=current.merge(one,on=['station','valid_utc'],how='left',validate='one_to_one')
 current['month']=current.valid_utc.dt.month;current['hour']=current.valid_utc.dt.hour
 current=current.merge(climat,on=['station','month','hour'],how='left',validate='many_to_one')
 init=current[['station','valid_utc','metar_speed']].rename(columns={'valid_utc':'init_utc','metar_speed':'persistence'})
 return current,init,climat,ledger,m

def main():
 p=argparse.ArgumentParser();p.add_argument('--stations',required=True);p.add_argument('--train-year',type=int,default=2022);p.add_argument('--test-year',type=int,default=2023);p.add_argument('--sources',nargs='+',required=True);p.add_argument('--parts',required=True);p.add_argument('--metar',required=True);p.add_argument('--minute-mix-template',required=True);p.add_argument('--old-2023',required=True);p.add_argument('--out',required=True);p.add_argument('--bootstrap',type=int,default=1000)
 a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 if (out/'metrics.json').exists():raise FileExistsError('Never overwrite existing metrics')
 stations=pd.read_csv(a.stations);sources=a.sources;assert 'GFS' in sources
 current,init,climat,ledger,allmet=load_obs(a)
 forecast=pd.concat([read_forecasts(a.parts,a.train_year,sources),read_forecasts(a.parts,a.test_year,sources,a.old_2023)],ignore_index=True)
 forecast['init_utc']=pd.to_datetime(forecast.init_utc,utc=True,format='mixed');forecast['valid_utc']=forecast.init_utc+pd.to_timedelta(forecast.lead_h,unit='h')
 # Refuse a yearly verdict if any source/month archive coverage is below 95%.
 for yr in (a.train_year,a.test_year):
  for mo in range(1,13):
   needed=2*pd.Period(f'{yr}-{mo:02}',freq='M').days_in_month
   for source in sources:
    n=forecast.loc[(forecast.init_utc.dt.year==yr)&(forecast.init_utc.dt.month==mo)&(forecast.source==source)&(forecast.lead_h==24),'init_utc'].nunique()
    target=30 if yr==a.train_year else needed
    if n<.95*target:raise ValueError(f'ARCHIVE_INCOMPLETE {yr}-{mo:02} {source}: {n}/{target}; no yearly verdict')
    if yr==a.train_year and n<needed:print('TRAIN_SAMPLED',mo,source,n,needed,flush=True)
 # Do not allow held-out observations or out-of-calendar verification into training.
 forecast=forecast[forecast.valid_utc.dt.year.isin([a.train_year,a.test_year])].copy()
 print('FORECAST_ROWS',len(forecast),'SOURCES',forecast.groupby([forecast.init_utc.dt.year,'source']).init_utc.nunique().to_dict(),flush=True)
 df=forecast.merge(current.drop(columns=['month','hour']),on=['station','valid_utc'],how='left',validate='many_to_one')
 df=df.merge(init,on=['station','init_utc'],how='left',validate='many_to_one')
 df['month']=df.valid_utc.dt.month;df['hour']=df.valid_utc.dt.hour
 tr=common(df[(df.valid_utc.dt.year==a.train_year)&(df.lead_h.isin([24,48]))],sources,'metar_speed')
 te=common(df[df.valid_utc.dt.year==a.test_year],sources,'metar_speed')
 if tr.station.nunique()<6 or te.station.nunique()<6:raise ValueError('fewer than six common stations')
 for frame in (tr,te):
  frame['raw_speed']=np.hypot(frame.fc_u,frame.fc_v)
  frame['raw_direction']=(270-np.degrees(np.arctan2(frame.fc_v,frame.fc_u)))%360
  frame['corrected']=np.nan;frame['pred_gust']=np.nan
  for t in WIND:frame[f'prob_wind_{t}']=np.nan
  for t in GUST:frame[f'prob_gust_{t}']=np.nan
 params={};prob_params={};training_mae={}
 for (station,lead,source),g in tr.groupby(['station','lead_h','source']):
  key=(station,int(lead),source);a0,b0=lin(g.raw_speed.to_numpy(),g.metar_speed.to_numpy());params[key]=[a0,b0]
  gm=g[g.minute_gust.notna()&g.minute_speed.notna()]
  if len(gm)>=12:
   zg=np.maximum(0,a0+b0*gm.raw_speed.to_numpy());gust_params=lin(zg,gm.minute_gust.to_numpy())
  else:gust_params=[np.nan,np.nan]
  params[key].extend(gust_params)
  for t in WIND:
   z=np.maximum(0,a0+b0*g.raw_speed.to_numpy());prob_params[(key,'wind',t)]=logistic(z,(g.metar_speed.to_numpy()>=t).astype(float))
  for t in GUST:
   z=np.maximum(0,a0+b0*gm.raw_speed.to_numpy())
   prob_params[(key,'gust',t)]=logistic(z,(gm.minute_gust.to_numpy()>=t).astype(float))
 for frame in (tr,te):
  for key,g in frame.groupby(['station','lead_h','source']):
   key=(key[0],int(key[1]),key[2]);coeff=params.get(key)
   if coeff is None:
    if frame is tr or int(key[1]) in (24,48):raise ValueError(f'no training coefficient {key}')
    continue # 2023-only leads are raw-only, never fit on the held-out year.
   z=np.maximum(0,coeff[0]+coeff[1]*g.raw_speed.to_numpy());frame.loc[g.index,'corrected']=z
   if np.isfinite(coeff[2]):frame.loc[g.index,'pred_gust']=np.maximum(0,coeff[2]+coeff[3]*z)
   for typ,thresholds in [('wind',WIND),('gust',GUST)]:
    for t in thresholds:
     (slope,intercept),n=prob_params[(key,typ,t)]
     if n>=1:frame.loc[g.index,f'prob_{typ}_{t}']=expit(intercept+slope*z)
 for s in sources:
  g=tr[(tr.source==s)&(tr.lead_h==24)];training_mae[s]=float(abs(g.corrected-g.metar_speed).mean())
 ai=[s for s in sources if s!='GFS'];primary=min(ai,key=lambda s:(training_mae[s],s))
 print('TRAIN_SELECTION',primary,training_mae,'TRAIN_CASES',len(tr)//len(sources),'TEST_CASES',len(te)//len(sources),flush=True)
 # Baseline calibration is fit only on training year for true Brier.
 for base in ['persistence','climatology']:
  for t in WIND:
   pp=tr[tr.source==sources[0]];coef,n=logistic(pp[base].to_numpy(),(pp.metar_speed.to_numpy()>=t).astype(float))
   for frame in (tr,te):frame[f'{base}_prob_{t}']=expit(coef[1]+coef[0]*frame[base].to_numpy())
 records=[]
 for obscol in ['metar_speed','minute_speed']:
  for (source,lead),g in te.groupby(['source','lead_h']):
   if obscol=='minute_speed':g=g[g.minute_speed.notna()]
   for variant,xcol in ([('raw','raw_speed'),('corrected','corrected')] if lead in (24,48) else [('raw','raw_speed')]):
    records.append(score(g,source,lead,variant,obscol,xcol,'raw_direction', 'pred_gust' if variant=='corrected' and obscol=='minute_speed' else None))
  ref=te[te.source==sources[0]]
  for lead,g in ref.groupby('lead_h'):
   if obscol=='minute_speed':g=g[g.minute_speed.notna()]
   for base in ['persistence','climatology']:
    b=g.copy()
    for t in WIND:b[f'prob_wind_{t}']=b[f'{base}_prob_{t}']
    records.append(score(b,base,lead,'baseline',obscol,base,None,None))
 gates=[]
 for lead in [24,48]:
  for base in ['GFS','persistence','climatology']:
   g=paired(te,primary,base,lead)
   gates.append({'lead_h':lead,'comparison':f'{primary}/{base}-1','metric':'MAE_relative',**gate(g,'mae',.05 if base=='GFS' else -.15,20261014+lead+len(base),a.bootstrap)})
 g=paired(te,primary,'GFS',24)
 gates.append({'lead_h':24,'comparison':f'{primary}-GFS','metric':'CSI8_difference',**gate(g,'csi',0,20261114,a.bootstrap)})
 ratios=te[(te.source=='FOUR_v200_GFS')&np.isfinite(te.fc_u100)&np.isfinite(te.minute_speed)&(te.minute_speed>=.5)].copy()
 ratio=np.hypot(ratios.fc_u100,ratios.fc_v100)/ratios.minute_speed
 dist={'n':len(ratio),'observation':'one-minute centered hourly scalar speed, >=0.5 m/s','quantiles':{str(q):fl(ratio.quantile(q)) for q in [.05,.25,.5,.75,.95]}}
 # Two event thresholds: train-year probability models only; ROC via rank U statistic.
 from scipy.stats import rankdata
 reliability={};roc_auc={};fig,axes=plt.subplots(1,2,figsize=(12,5))
 for t,ax in zip([8,10],axes):
  reliability[str(t)]={};roc_auc[str(t)]={}
  for s in sources:
   g=te[(te.source==s)&(te.lead_h==24)];p=g[f'prob_wind_{t}'].to_numpy();o=(g.metar_speed.to_numpy()>=t).astype(int)
   mask=np.isfinite(p);p=p[mask];o=o[mask];bins=np.minimum((p*10).astype(int),9)
   bucket=[{'bin':i,'n':int((bins==i).sum()),'mean_probability':fl(p[bins==i].mean() if (bins==i).any() else np.nan),'event_frequency':fl(o[bins==i].mean() if (bins==i).any() else np.nan)} for i in range(10)]
   reliability[str(t)][s]=bucket
   npos=o.sum();nneg=len(o)-npos
   roc_auc[str(t)][s]=fl((rankdata(p)[o==1].sum()-npos*(npos+1)/2)/(npos*nneg)) if npos and nneg else None
   pts=[v for v in bucket if v['n']>=10];ax.plot([v['mean_probability'] for v in pts],[v['event_frequency'] for v in pts],marker='o',label=s,linewidth=1)
  ax.plot([0,1],[0,1],':',color='black');ax.set(xlabel=f'P(wind >= {t} m/s)',ylabel='Observed event frequency',xlim=(0,1),ylim=(0,1));ax.legend(fontsize=6)
 fig.text(.01,.01,'NOAA/CIRA AIWP; NOAA GFS AWS; IEM ASOS METAR 2023',fontsize=7);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/'reliability8_10.png',dpi=160);plt.close(fig)
 for metric,name in [('mae','mae_vs_lead.png'),('csi','csi8_vs_lead.png')]:
  fig,ax=plt.subplots(figsize=(8,5))
  for s in sources+['persistence','climatology']:
   variant='corrected' if s in sources else 'baseline'
   ll=[24,48] if s in sources else LEADS
   rr=[next(r for r in records if r['source']==s and r['lead_h']==lead and r['variant']==variant and r['observation']=='METAR_2min') for lead in ll]
   ax.plot(ll,[r['mae'] if metric=='mae' else r['wind_8']['csi'] for r in rr],marker='o',label=s)
  ax.set(xlabel='Lead (h)',ylabel='MAE (m/s)' if metric=='mae' else 'CSI @ 8 m/s');ax.legend(fontsize=6,ncol=2);ax.grid(alpha=.25)
  fig.text(.01,.01,'NOAA/CIRA AIWP; NOAA GFS AWS; IEM ASOS METAR 2023',fontsize=7);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/name,dpi=160);plt.close(fig)
 station_counts=allmet.groupby(['station',allmet.valid_utc.dt.year]).size()
 years={str(s):{str(y):int(station_counts.get((s,y),0)) for y in range(a.train_year-9,a.test_year+1)} for s in stations.station}
 ledger_summary={'source_months':len(ledger),'response_bytes_total':sum(x['response_bytes'] for x in ledger),'download_seconds_total':sum(x['seconds'] for x in ledger),'station_year_observation_counts':years,'forecast_object_count':{str(y):{s:len(list((Path(a.parts)/str(y)/s).glob('*.csv'))) for s in sources} for y in (a.train_year,a.test_year)},'cu':'account shared; cannot attribute per station-year; see run audit'}
 (out/'retrieval_ledger.json').write_text(json.dumps(ledger_summary,indent=2))
 # Only station-level samples cross from Colab to 工作站; enough to reproduce scores and selections.
 keep=KEY+['source','valid_utc','fc_u','fc_v','fc_u100','fc_v100','raw_speed','raw_direction','corrected','pred_gust','metar_speed','obs_dir','minute_speed','minute_gust','minute_dir','minute_count','persistence','climatology','climatology_n']+[f'prob_wind_{t}' for t in WIND]+[f'prob_gust_{t}' for t in GUST]
 te[keep].to_csv(out/'paired_station_test.csv.gz',index=False,compression='gzip')
 tr[keep].to_csv(out/'paired_station_train.csv.gz',index=False,compression='gzip')
 payload={'train_year':a.train_year,'test_year':a.test_year,'sources':sources,'excluded_sources':'IFS-initialized AIWP not included in this narrowed run','primary_selected_on_2022_24h_mae':primary,'training_24h_mae':training_mae,'train_cases_per_source':len(tr)//len(sources),'test_cases_per_source':len(te)//len(sources),'gates':gates,'all_statistically_supported':bool(all(x['statistically_supported'] for x in gates)),'all_point_pass':bool(all(x['point_pass'] for x in gates)),'records':records,'reliability':reliability,'roc_auc':roc_auc,'ratio_100m_to_observed_10m':dist,'climatology_station_year_counts':years,'gust_stations_train':sorted(tr.loc[tr.minute_gust.notna(),'station'].unique().tolist()),'gust_stations_test':sorted(te.loc[te.minute_gust.notna(),'station'].unique().tolist())}
 (out/'metrics.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
 def fmt(v):return 'NA' if v is None else f'{v:.3f}'
 def events(r,typ,ths):
  return '; '.join(f"{t}: "+('/'.join(fmt(r[f'{typ}_{t}'][k]) for k in ('hit_rate','false_alarm_ratio','csi','misclassification_rate','brier_probability')) if r[f'{typ}_{t}'] else 'NA') for t in ths)
 lines=['# A1 审查修订：2022 训练／2023 全年 ASOS 检验','',f"一句结论：2022 按 24 h 订正后 MAE 预选 {primary}；2023 原定判据按区间 {'全部通过' if payload['all_statistically_supported'] else '未全部通过'}（点估计 {'全过' if payload['all_point_pass'] else '未全过'}）。",'',f"共同有效配对：训练 {payload['train_cases_per_source']}／源，检验 {payload['test_cases_per_source']}／源；2023 检验没有参与任何拟合、气候值或源选择。训练年按每月前 15 天、00/12 UTC 抽样，24/48 h 订正；其余时效只有原始预测。IFS 初值三源未纳入，主源只在 GFS 初值三源中按训练 MAE 预选。",'', '## 判据（按验证日整组自助重抽样，95% 区间）','']
 for g in gates:lines.append(f"- {g['lead_h']} h {g['comparison']} {g['metric']}: {fmt(g['delta'])}, 95% CI [{fmt(g['ci95'][0])}, {fmt(g['ci95'][1])}], 界限 {g['threshold']:.2f}：{g['status']}（共同配对 {g['paired_cases']}）。")
 lines+=['','## 主表：METAR 2 分钟持续风（全部站；列内阈值 6/8/10/12 m/s 顺序，命中率/空报率/CSI/误分类率/真实概率 Brier）','', '|源|h|版本|n|MAE|偏差|风向 MAE|持续风阈值 6/8/10/12|','|---|---:|---|---:|---:|---:|---:|---|']
 for r in records:
  if r['observation']=='METAR_2min':lines.append(f"|{r['source']}|{r['lead_h']}|{r['variant']}|{r['n']}|{fmt(r['mae'])}|{fmt(r['bias'])}|{fmt(r['direction_mae_deg'])}|{events(r,'wind',WIND)}|")
 lines+=['','## 1 分钟站：以有效时刻为中心 1 h 风速／窗内最大阵风（仅 1 分钟站）','',f"训练年可用阵风站：{payload['gust_stations_train']}；检验年：{payload['gust_stations_test']}。无 1 分钟资料时不做阵风验证；METAR 报阵风并非无事件也有记录。",'', '|源|h|版本|n|持续风 MAE|持续风 6/8/10/12（同上）|阵风 10/13/15（同上）|','|---|---:|---|---:|---:|---|---|']
 for r in records:
  if r['observation']=='minute_1h':lines.append(f"|{r['source']}|{r['lead_h']}|{r['variant']}|{r['n']}|{fmt(r['mae'])}|{events(r,'wind',WIND)}|{events(r,'gust',GUST)}|")
 lines+=['','## ≥8 与 ≥10 m/s 概率诊断（24 h；2022 拟合，2023 独立检验）',f"ROC AUC：{roc_auc}。可靠性图 reliability8_10.png；概率形式是否找回大风时段需同时看少见事件数量、AUC 与高概率箱实际频率。",'', '## 100 m FCNv2 与 1 h 10 m 观测风速之比（描述，不参与判据）',f"有效 N={dist['n']}；分位数 5/25/50/75/95% = {dist['quantiles']}；分母过滤 <0.5 m/s（假设，避免近零爆炸）。不是城市廓线换算系数。",'', '## 口径及局限', '全部站独立 METAR 2 min 同质口径用于判据；1 分钟站另外检验 1 h 风速和窗内最大阵风。METAR 不用阵风评分。分站／提前量线性订正与超越事件逻辑回归仅 2022 拟合；气候值是 2013–2022 年分站×月×UTC 小时的历史 METAR 2 min 平均。测高、风速计类型未逐站得到同期证据时不假定精确 10 m；低空城市外推无直接验证。','', '图：mae_vs_lead.png、csi8_vs_lead.png、reliability8_10.png。误分类率与概率 Brier 分列，不将确定性 0/1 评分冒充概率技巧。','', 'Bremnes 等（2024）NPG 31:247–257 DOI 10.5194/npg-31-247-2024 是挪威站点后处理设计参照，采用分位数神经网络而非本实验线性 MOS；不可用于外推 OKC 数值。']
 (out/'results.md').write_text('\n'.join(lines)+'\n')
 print('VERIFICATION_DONE',primary,payload['all_point_pass'],payload['all_statistically_supported'],len(te),flush=True)
if __name__=='__main__':main()
