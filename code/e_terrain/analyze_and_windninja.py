#!/usr/bin/env python3
"""Swiss cold-season paired verification; runs WindNinja only on preregistered strong-wind instances.
Source: MeteoSwiss; NOAA AIWP; NOAA GFS; NASA/USGS SRTM; USFS WindNinja.
All 10-minute observations end at timestamp; forecast valid UTC = initialization + lead.
"""
import csv,math,os,json,glob,time,subprocess
from pathlib import Path
from datetime import datetime,timezone
import numpy as np,pandas as pd,rasterio,pyproj
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/e_terrain');OUT=R/'analysis_v1';OUT.mkdir(exist_ok=False)
SRC=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'];LEADS=[24,48]
sites=pd.read_csv(R/'stations_frozen.csv').set_index('station');assert len(sites)==12
frozen=sites['frozen_at_us_eastern'].unique();assert len(frozen)==1
obs=[];limits={};gust={}
for sid in sites.index:
 o=pd.read_csv(R/f'obs_{sid}.csv',parse_dates=['time_utc']);o['station']=sid
 assert o['time_utc'].dt.tz is not None
 limits[sid]={'p95':float(o.speed_ms.quantile(.95)),'p99':float(o.speed_ms.quantile(.99))}
 gust[sid]=float((o.gust_1s_ms/o.speed_ms).where(o.speed_ms>=1).median())
 obs.append(o[['station','time_utc','speed_ms','gust_1s_ms']])
obs=pd.concat(obs,ignore_index=True);obs.rename(columns={'time_utc':'valid_utc','speed_ms':'obs_ms'},inplace=True)
parts=sorted((R/'full/forecast_parts').glob('*.csv'))
errors=sorted((R/'full/forecast_parts').glob('ERROR_*.txt'))
expected=len(pd.date_range('2023-10-01','2024-04-01',freq='12h',inclusive='left',tz='UTC'))*len(SRC)
print('FORECAST_MANIFEST',len(parts),expected,'errors',len(errors),flush=True)
assert len(parts)+len(errors)==expected,(len(parts),len(errors),expected)
print('ABSENT_OBJECTS', [p.name for p in errors],flush=True)
f=pd.concat((pd.read_csv(p) for p in parts),ignore_index=True)
f['init_utc']=pd.to_datetime(f.init_utc,utc=True);f['valid_utc']=f.init_utc+pd.to_timedelta(f.lead_h,unit='h')
f['interp_ms']=np.hypot(f.fc_u,f.fc_v)
f=f.merge(obs,on=['station','valid_utc'],how='left',validate='many_to_one')
f['terrain']=f.station.map(sites.terrain);f['p95']=f.station.map({s:v['p95'] for s,v in limits.items()});f['p99']=f.station.map({s:v['p99'] for s,v in limits.items()})
f['period']=np.where(f.valid_utc.dt.strftime('%Y-%m')<'2024-01','train',np.where(f.valid_utc.dt.strftime('%Y-%m')<='2024-03','test','other'))
f=f[f.period!='other'].copy()
# MOS trained separately for each station, source, lead using only Oct-Dec 2023.
models={}
for (sid,src,lead),g in f[f.period=='train'].groupby(['station','source','lead_h']):
 x=g[['interp_ms','obs_ms']].dropna();assert len(x)>50,(sid,src,lead,len(x))
 X=np.column_stack([x.interp_ms.to_numpy(),np.ones(len(x))]);coef=np.linalg.lstsq(X,x.obs_ms.to_numpy(),rcond=None)[0]
 models[(sid,src,int(lead))]=[float(coef[0]),float(coef[1]),len(x)]
with (OUT/'mos_coefficients.csv').open('x',newline='') as h:
 w=csv.writer(h);w.writerow(['station','source','lead_h','slope','intercept','training_n'])
 for (sid,src,lead),(a,b,n) in sorted(models.items()):w.writerow([sid,src,lead,a,b,n])
f=f[f.period=='test'].copy()
f['mos_ms']=[max(0,models[(x.station,x.source,int(x.lead_h))][0]*x.interp_ms+models[(x.station,x.source,int(x.lead_h))][1]) for x in f.itertuples()]
f['strong']=f.obs_ms>=f.p95
# Dates/source coverage on common valid observed cases; no aggregation of divergent missing cases.
common=f.groupby(['station','init_utc','lead_h']).filter(lambda g:len(g)==4 and g.obs_ms.notna().all())
assert common.groupby(['station','init_utc','lead_h']).size().eq(4).all()
f=common.copy();f['windninja_ms']=np.nan
strong=f[f.strong].copy();print('STRONG_CASES',len(strong),'ALL_TEST_CASES',len(f),flush=True)
wnroot=OUT/'windninja';wnroot.mkdir()
executable='/content/e_terrain/wn_env/bin/WindNinja_cli'
env={**os.environ,'WINDNINJA_DATA':'/content/e_terrain/wn_env/share/windninja','PROJ_DATA':'/content/e_terrain/wn_env/share/proj','PROJ_LIB':'/content/e_terrain/wn_env/share/proj'}
transform=pyproj.Transformer.from_crs('EPSG:4326','EPSG:32632',always_xy=True)
wnerrors=[];t0=time.monotonic()
for n,(idx,row) in enumerate(strong.iterrows(),1):
 sid=row.station;d=wnroot/f'{sid}_{row.source}_{row.init_utc.strftime("%Y%m%d%H")}_f{int(row.lead_h)}';d.mkdir(exist_ok=False)
 speed=float(row.interp_ms)
 if not np.isfinite(speed) or speed<=0:
  wnerrors.append((str(idx),'nonpositive inlet'));continue
 direction=(270-math.degrees(math.atan2(float(row.fc_v),float(row.fc_u))))%360
 cfg=d/'windninja.cfg'
 cfg.write_text(f'num_threads = 1\nelevation_file = {R/"dem"/(sid+".tif")}\nvegetation = grass\nmesh_resolution = 90\nunits_mesh_resolution = m\ninitialization_method = domainAverageInitialization\ninput_speed = {speed:.8f}\ninput_speed_units = mps\ninput_direction = {direction:.8f}\ninput_wind_height = 10\nunits_input_wind_height = m\noutput_wind_height = 10\nunits_output_wind_height = m\noutput_speed_units = mps\nwrite_ascii_output = true\noutput_path = {d}\n')
 try:
  z=subprocess.run([executable,str(cfg)],capture_output=True,text=True,timeout=100,env=env)
  if z.returncode:raise RuntimeError(f'exit={z.returncode}: {(z.stdout+z.stderr)[-500:]}')
  asc=list(d.glob('*_vel.asc'))
  if len(asc)!=1:raise RuntimeError(f'velocity files={len(asc)}')
  x,y=transform.transform(float(sites.loc[sid,'lon']),float(sites.loc[sid,'lat']))
  with rasterio.open(asc[0]) as raster:
   val=float(next(raster.sample([(x,y)]))[0]);assert np.isfinite(val) and val>=0 and val!=raster.nodata
  f.at[idx,'windninja_ms']=val
 except Exception as e:
  wnerrors.append((f'{sid}/{row.source}/{row.init_utc}/f{row.lead_h}',str(e)))
 if n%100==0:print('WN_PROGRESS',n,len(strong),'errors',len(wnerrors),'sec',int(time.monotonic()-t0),flush=True)
print('WN_DONE',len(strong)-len(wnerrors),len(wnerrors),'elapsed',time.monotonic()-t0,flush=True)
(OUT/'wn_errors.json').write_text(json.dumps(wnerrors,indent=2,default=str))
# Strong-wind comparison uses the exact same cases where WN and all sources succeed.
strong=f[f.strong].copy();paired=strong[strong.windninja_ms.notna()].copy()
paired[['station','terrain','source','init_utc','valid_utc','lead_h','obs_ms','p95','p99','interp_ms','mos_ms','windninja_ms']].to_csv(OUT/'paired_strong_cases.csv',index=False)
methods={'bilinear':'interp_ms','mos':'mos_ms','windninja':'windninja_ms'}
records=[]
for (sid,terrain,src,lead),g in paired.groupby(['station','terrain','source','lead_h']):
 for method,col in methods.items():
  err=g[col]-g.obs_ms
  records.append({'station':sid,'terrain':terrain,'source':src,'lead_h':int(lead),'method':method,'n':len(g),'strong_mae_ms':float(err.abs().mean()),'strong_bias_ms':float(err.mean())})
stat=pd.DataFrame(records);stat.to_csv(OUT/'strong_metrics.csv',index=False)
# Site-wise paired pooling over all 4 sources and both leads, same events for all three methods.
site=stat.groupby(['station','method']).apply(lambda g:np.average(g.strong_mae_ms,weights=g.n),include_groups=False).unstack()
assert len(site)==len(sites),(len(site),len(sites))
site['reduction_pct']=100*(1-site.windninja/site.bilinear)
win=int((site.windninja<site.bilinear).sum());moswin=int((site.windninja<=site.mos).sum())
red=float(site.reduction_pct.median());mos_median_win=bool(site.windninja.median()<=site.mos.median())
pass_gate=(red>=15 and win>=8 and mos_median_win)
# Full-time scores only where predicted method was actually run; WN absent outside strong subset.
full=[]
for (sid,terrain,src,lead),g in f.groupby(['station','terrain','source','lead_h']):
 for method,col in [('bilinear','interp_ms'),('mos','mos_ms')]:
  e=g[col]-g.obs_ms;event=g.obs_ms>=g.p99;alarm=g[col]>=g.p99
  full.append({'station':sid,'terrain':terrain,'source':src,'lead_h':int(lead),'method':method,'n':len(g),'full_mae_ms':float(e.abs().mean()),'full_bias_ms':float(e.mean()),'hit_rate_99':float((event&alarm).sum()/event.sum()) if event.sum() else None,'false_alarm_rate_99':float((~event&alarm).sum()/(~event).sum()) if (~event).sum() else None,'n_event_99':int(event.sum())})
fullstat=pd.DataFrame(full);fullstat.to_csv(OUT/'full_metrics_baselines.csv',index=False)
# WN 99th hit among observed events can be reported; false alarm cannot without all non-event instances.
wn_event=paired[paired.obs_ms>=paired.p99];wn_hit=float((wn_event.windninja_ms>=wn_event.p99).mean()) if len(wn_event) else None
terrain=stat.groupby(['terrain','method']).apply(lambda g:np.average(g.strong_mae_ms,weights=g.n),include_groups=False).unstack();terrain=terrain.reindex(['ridge','pass','valley','plateau'])
fig,ax=plt.subplots(figsize=(9,5));terrain.plot.bar(ax=ax,width=.75);ax.set_ylabel('MAE at strong observed 10-min winds (m/s)');ax.set_xlabel('MeteoSwiss exposure-derived terrain class');ax.set_title('Swiss cold season 2024 Jan–Mar; four sources, 24/48h, paired cases');ax.legend(title='Method');fig.text(.5,.01,'Source: MeteoSwiss; NOAA AIWP; NOAA GFS',ha='center',fontsize=9);fig.tight_layout(rect=(0,.04,1,1));fig.savefig(OUT/'strong_mae_by_terrain.png',dpi=170);plt.close(fig)
metrics={'status':'complete_common_cases' if not wnerrors else 'partial_windninja','frozen_at_us_eastern':frozen[0],'forecast_objects':len(parts),'forecast_expected':expected,'missing_objects':[p.name for p in errors],'strong_cases':len(strong),'wn_success_cases':len(paired),'wn_errors':len(wnerrors),'station_reduction_pct':site.reduction_pct.to_dict(),'median_station_reduction_pct':red,'stations_wn_better_bilinear':win,'stations_wn_not_worse_mos':moswin,'median_station_wn_mae_ms':float(site.windninja.median()),'median_station_mos_mae_ms':float(site.mos.median()),'median_station_wn_not_worse_mos':mos_median_win,'pass_gate':bool(pass_gate) if not wnerrors else None,'wn_event99_hit_rate_conditional':wn_hit,'wn_event99_n':len(wn_event),'windninja_false_alarm_rate_99':None,'terrain_strong_mae_ms':terrain.to_dict(),'observation_thresholds_ms':limits,'observed_gust_factor_median':gust,'full_time_windninja_mae':None,'strong_run_seconds':time.monotonic()-t0}
(OUT/'metrics.json').write_text(json.dumps(metrics,indent=2,default=str))
print('RESULT',json.dumps({k:metrics[k] for k in ['status','strong_cases','median_station_reduction_pct','stations_wn_better_bilinear','stations_wn_not_worse_mos','pass_gate']},default=str),flush=True)
