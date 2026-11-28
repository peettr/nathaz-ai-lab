"""GEV L-moment substitution sensitivity, no effect on frozen Gumbel decision."""
import csv,json,math
import numpy as np
from lmoments3 import distr
from pathlib import Path
root=Path('/content/site_stage_qc/final');adm=[r for r in csv.DictReader((root/'station_admission.csv').open()) if r['admitted']=='true'];eligible={r['station'] for r in adm if sum(1 for z in map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines()) if z['station']==r['station'] and z['valid'])>=12};adm=[r for r in adm if r['station'] in eligible];meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())};o={(x['station'],x['season_year']):x for x in map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines())};e={x['season_year']:x['stations'] for x in map(json.loads,(root/'era_seasons.jsonl').read_text().splitlines())}
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
fits={}
for r in adm:
 st=r['station'];ys=[y for y in range(2007,2022) if o[st,y]['valid']];station=np.array([o[st,y]['qc_peak']['kn'] for y in ys]);era=np.array([e[y][st]['ace1_max_mps'] for y in ys]);fits[st]={}
 for source,values in [('station',station),('era',era)]:
  try:
   p=distr.gev.lmom_fit(values);fits[st][source]={f'x{T}':float(distr.gev.ppf(1-1/T,**p)) for T in (10,50)};fits[st][source]['shape']=float(p['c'])
  except Exception as ex:fits[st][source]={'error':repr(ex)}
rows=[]
for r in adm:
 st=r['station'];train=[q['station'] for q in adm if q['station']!=st and hav(meta[st],meta[q['station']])>200]
 row={'station':st,'region':r['region'],'training_count':len(train)}
 for T in (10,50):
  try:
   x=np.array([fits[q]['era'][f'x{T}'] for q in train]);y=np.array([fits[q]['station'][f'x{T}'] for q in train]);coef=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)[0];pred=coef[0]+coef[1]*fits[st]['era'][f'x{T}'];actual=fits[st]['station'][f'x{T}'];row[f'R{T}']=pred/actual;row[f'pred_x{T}_kn']=pred;row[f'obs_x{T}_kn']=actual
  except Exception as ex:row[f'R{T}']='';row[f'error_{T}']=repr(ex)
 rows.append(row)
fields=list(dict.fromkeys(k for r in rows for k in r))
with (root/'gev_lmom_sensitivity.csv').open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
(root/'gev_fits.json').write_text(json.dumps(fits,indent=2));print('GEV',len(rows),'valid',sum(bool(r.get('R10')) for r in rows),'shape_range',min(v['station'].get('shape',100) for v in fits.values()),max(v['station'].get('shape',-100) for v in fits.values()),flush=True)
