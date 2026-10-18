"""Prague PVK: Apr-May 2022 selection, Jun-Sep leave-one-month-out evaluation."""
import json, sys
from pathlib import Path
import numpy as np,pandas as pd
from scipy.special import expit
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/prague_forecasts');OUT=R/'final_v1';OUT.mkdir(exist_ok=True)
SOURCES=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'];LEADS=[24,48]
METHODS={'direct100':['FOUR_v200_GFS','GFS'],'log_z0_0p03':SOURCES,'power_alpha_0p2':SOURCES,'stat_ratio':SOURCES,
         'log_z0_0p3':SOURCES,'power_alpha_0p14':SOURCES,'power_alpha_0p3':SOURCES}
PRIMARY_METHODS={'direct100','log_z0_0p03','power_alpha_0p2','stat_ratio'}
def linear(x,y):
 m=np.isfinite(x)&np.isfinite(y);x=np.asarray(x)[m];y=np.asarray(y)[m]
 if len(x)<20 or np.std(x)<.01:return (float(np.mean(y)) if len(y) else np.nan,0.)
 b,a=np.polyfit(x,y,1);return float(a),float(b)
def logit(x,y):
 x=np.asarray(x);y=np.asarray(y,dtype=int)
 if len(np.unique(y))<2:return (0.,float(np.log((y.sum()+.5)/(len(y)-y.sum()+.5))))
 mu=x.mean();sd=max(x.std(),.1);z=(x-mu)/sd
 def fun(p):
  h=p[0]+p[1]*z;return np.logaddexp(0,h).sum()-(h*y).sum()+.01*p[1]**2
 fit=minimize(fun,[0.,0.],method='BFGS')
 return float(fit.x[1]/sd),float(fit.x[0]-fit.x[1]*mu/sd)
def raw(g,method,ratio):
 z=g.actual_agl.to_numpy();u10=np.hypot(g.fc_u,g.fc_v)
 if method=='direct100':return np.hypot(g.fc_u100,g.fc_v100)
 if method=='log_z0_0p03':return u10*np.log(z/.03)/np.log(10/.03)
 if method=='log_z0_0p3':return u10*np.log(z/.3)/np.log(10/.3)
 if method=='power_alpha_0p2':return u10*(z/10)**.2
 if method=='power_alpha_0p14':return u10*(z/10)**.14
 if method=='power_alpha_0p3':return u10*(z/10)**.3
 if method=='stat_ratio':return u10*ratio
 raise ValueError(method)
def score(g,source,method,lead,fold):
 return {'station':g.station.iloc[0],'target_agl':int(g.target_agl.iloc[0]),'source':source,'method':method,'lead_h':lead,'fold':fold,'n':len(g),'mae':float(np.mean(np.abs(g.pred-g.wind))),'raw_mae':float(np.mean(np.abs(g.raw_pred-g.wind))),'bias':float(np.mean(g.pred-g.wind))}
def fold_fit(train,test,method):
 # station/gate/source/lead group already isolated. Statistical ratio and MOS use strictly training observations.
 r=np.nanmedian((train.wind/np.hypot(train.fc_u,train.fc_v)).where(np.hypot(train.fc_u,train.fc_v)>=.5)) if method=='stat_ratio' else np.nan
 if not np.isfinite(r):r=1.
 x=raw(train,method,r);a,b=linear(x,train.wind.to_numpy());train=train.copy();test=test.copy()
 train['pred']=np.maximum(0,a+b*x);test['raw_pred']=raw(test,method,r);train['raw_pred']=x
 test['pred']=np.maximum(0,a+b*test.raw_pred)
 k,h=logit(train.pred.to_numpy(),(train.wind.to_numpy()>=8))
 test['prob8']=expit(h+k*test.pred.to_numpy());return test,{'a':a,'b':b,'ratio':float(r),'logit_slope':k,'logit_intercept':h}
def load():
 rows=[]
 for m in ('04','05','06','07','08','09'):
  data=json.loads(Path(f'/content/prague_qc/qc_2022{m}.json').read_text())
  rows.extend({'station':'PVK','target_agl':101,'actual_agl':101.4,'valid_utc':t,'wind':v,'n10':4} for t,v in data['hours'].items())
 obs=pd.DataFrame(rows);obs.valid_utc=pd.to_datetime(obs.valid_utc,utc=True)
 obs=obs.drop_duplicates(['station','target_agl','valid_utc'])
 station=pd.DataFrame([{'station':'PVK','lat':50.072588,'lon':14.428428}])
 rows=[]
 for source in SOURCES:
  files=sorted((R/'parts'/source).glob('*.csv'))
  if not files:raise ValueError('missing forecast '+source)
  rows.extend(pd.read_csv(f) for f in files)
 fc=pd.concat(rows,ignore_index=True);fc.init_utc=pd.to_datetime(fc.init_utc,utc=True);fc['valid_utc']=fc.init_utc+pd.to_timedelta(fc.lead_h,unit='h')
 # Only valid period and complete four-source forecast init/lead pairs, to compare methods on common times.
 fc=fc[fc.valid_utc.between(pd.Timestamp('2022-04-01',tz='UTC'),pd.Timestamp('2022-10-02',tz='UTC'))]
 return obs,fc,station
def bootstrap_ratio(g,base,seed=333,n=2000):
 # paired verifying UTC days; percent improvement 1-MAE(main)/MAE(base).
 day=g.valid_utc.dt.floor('d');_,inv=np.unique(day,return_inverse=True);N=inv.max()+1
 v=np.bincount(inv,weights=np.abs(g.pred-g.wind),minlength=N);b=np.bincount(inv,weights=np.abs(g[base]-g.wind),minlength=N)
 point=float(1-v.sum()/b.sum());rng=np.random.default_rng(seed);cnt=rng.multinomial(N,[1/N]*N,size=n)
 ci=np.quantile(1-(cnt@v)/(cnt@b),[.025,.975]);return {'improvement':point,'ci95':ci.tolist(),'n':len(g),'days':int(N),'status':'通过' if ci[0]>=.15 else '点估计通过、统计不确定' if point>=.15 else '未通过'}
def bootstrap_auc(g,n=2000):
 y=(g.wind.to_numpy()>=8).astype(int);p=g.prob8.to_numpy();point=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else np.nan
 days=g.valid_utc.dt.floor('d').to_numpy();uniq=np.unique(days);groups=[np.where(days==day)[0] for day in uniq];rng=np.random.default_rng(20261014);s=[]
 for i in range(n):
  ids=np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]);yy=y[ids]
  if len(np.unique(yy))==2:s.append(roc_auc_score(yy,p[ids]))
 ci=np.quantile(s,[.025,.975]).tolist() if s else [np.nan,np.nan]
 return {'auc':point,'ci95':ci,'n_events':int(y.sum()),'n':len(y),'days':len(uniq),'status':'通过' if ci[0]>=.85 else '点估计通过、统计不确定' if point>=.85 else '未通过'}
def main():
 obs,fc,station=load();sources=set(fc.source.unique());assert set(SOURCES)==sources
 expected=pd.date_range('2022-04-01','2022-10-01',freq='12h',tz='UTC',inclusive='left')
 coverage={s:{str(p):int(fc[(fc.source==s)&(fc.init_utc.dt.strftime('%Y-%m')==str(p))&(fc.lead_h==24)].init_utc.nunique()) for p in pd.period_range('2022-04','2022-09',freq='M')} for s in SOURCES}
 print('COVERAGE',coverage,flush=True)
 # Forecasts as station-time, observation as station-time-gate.
 merged=fc.merge(obs[['station','target_agl','actual_agl','valid_utc','wind','n10']],on=['station','valid_utc'],how='inner')
 merged['month']=merged.valid_utc.dt.strftime('%Y-%m');merged=merged[merged.n10>=4]
 merged=merged[merged.station.eq('PVK')]
 complete=merged.groupby(['station','target_agl','init_utc','lead_h']).source.nunique()
 common=complete[complete==len(SOURCES)].index
 merged=merged.set_index(['station','target_agl','init_utc','lead_h']).loc[common].reset_index()
 if merged.empty:raise ValueError('No PVK target')
 # Persistence observation at init for exactly same gate; no look-ahead.
 initobs=obs[['station','target_agl','valid_utc','wind']].rename(columns={'valid_utc':'init_utc','wind':'persistence'})
 merged=merged.merge(initobs,on=['station','target_agl','init_utc'],how='left',validate='many_to_one')
 choice=[];predictions=[];parameters=[]
 for (station,gate,source,lead),g in merged.groupby(['station','target_agl','source','lead_h']):
  for method,allowed in METHODS.items():
   if source not in allowed:continue
   # April-May selection only; calibration for held-out months uses other evaluation months.
   selection=g[g.month.isin(['2022-04','2022-05'])]
   if len(selection)>=40:
    selected,p=fold_fit(selection,selection,method)
    choice.append(score(selected,source,method,lead,'selection_in_sample'))
   ev=g[g.month.between('2022-06','2022-09')]
   for month in sorted(ev.month.unique()):
    tr=ev[ev.month!=month];te=ev[ev.month==month]
    if len(tr)<40 or len(te)<10:continue
    te,p=fold_fit(tr,te,method)
    # monthly folds use training month UTC cycle only, non-seasonal hourly climatology.
    clim=tr.groupby(tr.valid_utc.dt.hour).wind.mean();te['climatology']=te.valid_utc.dt.hour.map(clim)
    te['method']=method;predictions.append(te)
    parameters.append({'station':station,'gate':int(gate),'source':source,'lead':int(lead),'month':month,**p,'train_n':len(tr)})
 if not choice:raise ValueError('no selection records')
 sel=pd.DataFrame(choice);s=sel[(sel.station=='PVK')&(sel.target_agl==101)&(sel.lead_h==24)]
 primary=s[s.method.isin(PRIMARY_METHODS)].sort_values(['mae','source','method']).iloc[0][['source','method']].to_dict()
 print('PRIMARY',primary,'selection_n',len(s),flush=True)
 paired=pd.concat(predictions,ignore_index=True)
 paired.to_csv(OUT/'paired_station.csv.gz',index=False,compression='gzip')
 results=[]
 for (station,gate,source,method,lead),g in paired.groupby(['station','target_agl','source','method','lead_h']):
  v=score(g,source,method,lead,'LOMO');v['events8']=int((g.wind>=8).sum());v['auc8']=float(roc_auc_score(g.wind>=8,g.prob8)) if (g.wind>=8).nunique()==2 else None
  results.append(v)
 rec=pd.DataFrame(results);main=paired[(paired.station=='PVK')&(paired.target_agl==101)&(paired.source==primary['source'])&(paired.method==primary['method'])]
 gates={}
 for lead in LEADS:
  g=main[main.lead_h==lead].dropna(subset=['persistence','climatology']);gates[str(lead)]={base:bootstrap_ratio(g,base,seed=lead+len(base)) for base in ('persistence','climatology')}
 g=main[(main.lead_h==24)&main.persistence.notna()&main.climatology.notna()];gates['auc8_24h']=bootstrap_auc(g)
 count=obs.groupby(['station','target_agl',obs.valid_utc.dt.strftime('%Y-%m')]).size().reset_index(name='hours');count.columns=['station','target_agl','month','hours']
 payload={'primary':primary,'selection':sel.to_dict('records'),'records':results,'gates':gates,'observation_hours_by_month':count.to_dict('records'),'forecast_initializations_by_month':coverage,'parameters':parameters,'selection_used_for_fit':True,'evaluation_lomo_months':'2022-06:2022-09'}
 (OUT/'metrics.json').write_text(json.dumps(payload,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
 fig,ax=plt.subplots(figsize=(9,5))
 subset=rec[(rec.station=='PVK')&(rec.target_agl==101)&(rec.lead_h==24)]
 for src in SOURCES:
  q=subset[subset.source==src];ax.plot(q.method,q.mae,'o-',label=src)
 ax.set(ylabel='24 h MAE (m/s)',xlabel='Height conversion + station MOS');ax.tick_params(axis='x',rotation=20);ax.legend(fontsize=7);ax.grid(alpha=.3)
 fig.text(.01,.01,'Bauerova et al. TURDATA Zenodo 10655033; NOAA/CIRA AIWP; NOAA/NCEP GFS AWS',fontsize=7);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(OUT/'methods_mae.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(9,5))
 for lead in LEADS:
  gg=main[main.lead_h==lead];grp=gg.groupby('month').apply(lambda x:pd.Series({'mae':np.mean(abs(x.pred-x.wind)),'persist':np.mean(abs(x.persistence-x.wind)),'climate':np.mean(abs(x.climatology-x.wind))}),include_groups=False)
  ax.plot(grp.index,grp.mae,'o-',label=f'primary {lead}h')
  if lead==24:ax.plot(grp.index,grp.persist,'--',label='persistence 24h');ax.plot(grp.index,grp.climate,':',label='climatology 24h')
 ax.set(xlabel='Held-out month',ylabel='MAE (m/s)');ax.tick_params(axis='x',rotation=30);ax.legend(fontsize=8);ax.grid(alpha=.3)
 fig.text(.01,.01,'Bauerova et al. TURDATA Zenodo 10655033; NOAA/CIRA AIWP; NOAA/NCEP GFS AWS',fontsize=7);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(OUT/'monthly_mae.png',dpi=150);plt.close(fig)
 print('VERIFY_DONE',json.dumps({'primary':primary,'gates':gates}),flush=True)
if __name__=='__main__':main()
