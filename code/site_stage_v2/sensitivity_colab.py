"""Pre-registered sensitivity and process-time diagnostics; not used by main decision."""
import csv,json,math,datetime as dt
from pathlib import Path
import numpy as np
root=Path('/content/site_stage_v2');params=list(csv.DictReader((root/'station_params.csv').open()));main=list(csv.DictReader((root/'loso_results.csv').open()));adm={r['station']:r for r in csv.DictReader((root/'station_admission.csv').open())};meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())};o={(x['station'],x['season_year']):x for x in map(json.loads,(root/'station_only_seasons_corrected.jsonl').read_text().splitlines())};e={x['season_year']:x['stations'] for x in map(json.loads,(root/'era_seasons.jsonl').read_text().splitlines())}
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
def rv(mu,b,T):return mu+b*(-np.log(-np.log(1-1/T))-np.euler_gamma)
rows=[]
for h in params:
 st=h['station'];x={k:float(v) for k,v in h.items() if k.endswith(('_kn','_mps'))}
 for mode in ('ratio','regional_ols','no_buffer_ols'):
  train=[q for q in params if q['station']!=st and (mode!='regional_ols' or q['region']==h['region']) and (mode=='no_buffer_ols' or hav(meta[st],meta[q['station']])>200)]
  pred={}
  for T in (10,50):
   if mode=='ratio':
    c=np.median([float(q[f'station_x{T}_kn'])/float(q[f'era_x{T}_mps']) for q in train]);p=c*x[f'era_x{T}_mps']
   else:
    par={}
    for j in ('mu','beta'):
     xx=np.array([float(q[f'era_{j}_mps']) for q in train]);yy=np.array([float(q[f'station_{j}_kn']) for q in train]);coef=np.linalg.lstsq(np.column_stack([np.ones(len(xx)),xx]),yy,rcond=None)[0];par[j]=float(coef[0]+coef[1]*x[f'era_{j}_mps'])
    p=rv(par['mu'],par['beta'],T)
   pred[f'R{T}']=p/x[f'station_x{T}_kn']
  rows.append({'station':st,'region':h['region'],'mode':mode,'training_count':len(train),**pred})
with (root/'sensitivity_results.csv').open('x',newline='') as f:w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
d=[]
for h in params:
 st=h['station']
 for y in range(2007,2022):
  z=o[st,y]
  if not z['valid']:continue
  stationtime=dt.datetime.fromisoformat(z['peak']['event_utc'].replace('Z','+00:00'))
  eratime=dt.datetime.fromisoformat(e[y][st]['max_utc'].replace('Z','+00:00'))
  dh=abs((stationtime-eratime).total_seconds())/3600
  d.append({'station':st,'region':h['region'],'season_year':y,'station_peak_utc':stationtime.isoformat(),'era_peak_utc':eratime.isoformat(),'hours_apart':dh,'within_36h':str(dh<=36).lower(),'station_peak_kn':z['peak']['kn'],'era_season_max_mps':e[y][st]['ace1_max_mps'],'ratio_kn_per_mps':z['peak']['kn']/e[y][st]['ace1_max_mps']})
with (root/'event_diagnostic.csv').open('x',newline='') as f:w=csv.DictWriter(f,list(d[0]));w.writeheader();w.writerows(d)
print('SENS',[(mode,sum(abs(float(r['R10'])-1)<=.15 for r in rows if r['mode']==mode),len(params)) for mode in ('ratio','regional_ols','no_buffer_ols')]);print('EVENT_36H',sum(x['within_36h']=='true' for x in d),len(d),flush=True)
