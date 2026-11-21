"""Prague no-local-high-altitude S1: airport MOS + two-stage morphology.
Runs only after run_verify.py completes. Uses identical S0 forecast/observation pairs.
"""
import json,math,csv
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import roc_auc_score
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path('/content/prague_forecasts');O=R/'final_v1';O.mkdir(exist_ok=True)
sectors=pd.DataFrame(json.loads((R/'morph_sectors.json').read_text())['sectors'])
v=pd.read_csv(O/'paired_station.csv.gz',parse_dates=['init_utc','valid_utc'])
# One record per station/lead/source/lead time/method. S0 is local MOS from the same held-out fold.
v=v[((v.source=='GFS')&(v.method=='direct100'))|((v.source=='GRAP_v100_GFS')&(v.method=='log_z0_0p03'))].copy()
v['month']=v.valid_utc.dt.strftime('%Y-%m')
v['wind_from_deg']=(np.degrees(np.arctan2(-v.fc_u,-v.fc_v))+360)%360
v['sector_from_deg']=((v.wind_from_deg+15)//30*30).astype(int)%360
v=v.merge(sectors[['sector_from_deg','z0_m','d_m']],on='sector_from_deg',validate='many_to_one')
air=[]
with open('/content/lkpr.csv') as f:
 for row in csv.DictReader(f):
  try:air.append((pd.Timestamp(row['valid'],tz='UTC'),float(row['sknt'])*.514444))
  except (ValueError,KeyError):pass
# IEM routine METAR nominal :00/:30. UTC hour average of reports during same clock hour.
air=pd.DataFrame(air,columns=['hour','airport10']);air.hour=air.hour.dt.floor('h');air=air.groupby('hour',as_index=False).airport10.mean()
v=v.merge(air.rename(columns={'hour':'valid_utc'}),on='valid_utc',how='inner',validate='many_to_one')
v=v.dropna(subset=['airport10','pred','wind','fc_u','fc_v']).copy()
for zref in (.03,.01,.1):
 for zb in (60,100,200):
  if ((zb-v.d_m)<=2*v.z0_m).any():raise ValueError('blending height below canopy validity threshold')

def fit(x,y):
 b,a=np.polyfit(x,y,1);return a,b
parts=[]
for (source,lead),g in v.groupby(['source','lead_h']):
 for month in sorted(g.month.unique()):
  train=g[g.month!=month];test=g[g.month==month].copy()
  if len(train)<20 or len(test)<10:raise ValueError('fold insufficient')
  x=np.hypot(train.fc_u,train.fc_v);a,b=fit(x,train.airport10)
  ground=np.maximum(0,a+b*np.hypot(test.fc_u,test.fc_v))
  test['ground_mos']=ground
  for zref in (.03,.01,.1):
   for zb in (60,100,200):
    factor=(np.log(zb/zref)/np.log(10/zref))*(np.log((101.4-test.d_m)/test.z0_m)/np.log((zb-test.d_m)/test.z0_m))
    test[f'S1_zb{zb}_ref{zref}']=ground*factor
  test['S0']=test.pred
  test['S3']=test.raw_pred
  test['airport_mos_a']=a;test['airport_mos_b']=b
  parts.append(test)
out=pd.concat(parts,ignore_index=True)
cols=['S0','S3']+[f'S1_zb{zb}_ref{zref}' for zref in (.03,.01,.1) for zb in (60,100,200)]
records=[]
def metric(g,col):
 p=g[col].to_numpy();o=g.wind.to_numpy();ev=o>=8;pred=p>=8
 hits=int((ev&pred).sum());miss=int((ev&~pred).sum());fa=int((~ev&pred).sum())
 return {'n':len(g),'mae':float(np.abs(p-o).mean()),'bias':float((p-o).mean()),'auc8':float(roc_auc_score(ev,p)) if ev.any() and (~ev).any() else None,'csi8':hits/(hits+miss+fa) if hits+miss+fa else None}
def bootstrap(g,col,n=2000):
 day=g.valid_utc.dt.floor('D').to_numpy();unique,idx=np.unique(day,return_inverse=True);v=np.bincount(idx,weights=abs(g[col]-g.wind));b=np.bincount(idx,weights=abs(g.S0-g.wind));rng=np.random.default_rng(20261015);draw=rng.integers(0,len(unique),size=(n,len(unique)))
 return {'relative_pct':100*(v.sum()/b.sum()-1),'ci95_pct':list(100*np.quantile(v[draw].sum(axis=1)/b[draw].sum(axis=1)-1,[.025,.975])),'days':len(unique)}
for (source,lead),g in out.groupby(['source','lead_h']):
 for col in cols:
  r={'source':source,'lead_h':int(lead),'method':col,**metric(g,col)}
  if col!='S0':r['vs_S0']=bootstrap(g,col)
  records.append(r)
out.to_csv(O/'paired_transfer.csv.gz',index=False,compression='gzip')
(O/'transfer_metrics.json').write_text(json.dumps({'records':records,'sectors':sectors.to_dict('records'),'airport_mos_reference':'PVK grid 10m vs LKPR METAR 10m; cross-site, not collocated','floor_height_assumption':'OSM building:levels*3m, no-height median imputed'},indent=2))
fig,ax=plt.subplots(figsize=(8,4.7))
for src in ['GFS','GRAP_v100_GFS']:
 for lead in (24,48):
  q=[next(r['mae'] for r in records if r['source']==src and r['lead_h']==lead and r['method']==c) for c in ['S0','S3','S1_zb60_ref0.03','S1_zb100_ref0.03','S1_zb200_ref0.03']]
  ax.plot(['S0','S3','S1 60','S1 100','S1 200'],q,'o-',label=f'{src} {lead}h')
ax.set_ylabel('MAE (m/s)');ax.set_xlabel('Method / blending height (m)');ax.grid(alpha=.3);ax.legend(fontsize=8)
fig.text(.01,.01,'TURDATA Zenodo 10655033; NOAA AIWP / GFS; IEM LKPR; OSM Overpass (ODbL)',fontsize=7)
fig.tight_layout(rect=(0,.04,1,1));fig.savefig(O/'transfer_mae.png',dpi=150);plt.close(fig)
print('TRANSFER_DONE',len(out),json.dumps([r for r in records if r['source']=='GFS' and r['lead_h']==24 and r['method'] in ('S0','S3','S1_zb60_ref0.03','S1_zb100_ref0.03','S1_zb200_ref0.03')]),flush=True)
