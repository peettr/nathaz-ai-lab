"""Score frozen one-minute gust sensitivity after minute.done, Colab only."""
import csv,json,math
from pathlib import Path
import numpy as np
root=Path('/content/site_stage_v2');assert (root/'minute.done').exists();adm=[r for r in csv.DictReader((root/'station_admission.csv').open()) if r['admitted']=='true'];meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())};o={(x['station'],x['season_year']):x for x in map(json.loads,(root/'minute_sensitivity.jsonl').read_text().splitlines())};e={x['season_year']:x['stations'] for x in map(json.loads,(root/'era_seasons.jsonl').read_text().splitlines())};assert len(o)==len(adm)*15
G=np.euler_gamma
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
def moment(x):return float(np.mean(x)),float(np.std(x,ddof=0)*np.sqrt(6)/np.pi)
def xt(a,b,T):return float(a+b*(-np.log(-np.log(1-1/T))-G))
pa=[]
for r in adm:
 st=r['station'];ys=[y for y in range(2007,2022) if o[st,y]['minute_peak'] and o[st,y]['coverage']>=.9];v=np.array([o[st,y]['minute_peak']['kn'] for y in ys],float);u=np.array([e[y][st]['ace1_max_mps'] for y in ys],float)
 if len(ys)<12:pa.append({'station':st,'region':r['region'],'n':len(ys),'error':'under_12_minutes'});continue
 m,b=moment(v);em,eb=moment(u);pa.append({'station':st,'region':r['region'],'n':len(ys),'sm':m,'sb':b,'em':em,'eb':eb,'x10':xt(m,b,10),'x50':xt(m,b,50)})
rows=[]
for h in pa:
 if h.get('error'):rows.append(h);continue
 st=h['station'];train=[q for q in pa if q['station']!=st and not q.get('error') and hav(meta[st],meta[q['station']])>200];pred={}
 for a,b in [('sm','em'),('sb','eb')]:
  x=np.array([q[b] for q in train]);y=np.array([q[a] for q in train]);c=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)[0];pred[a]=float(c[0]+c[1]*h[b])
 rows.append({'station':st,'region':h['region'],'n':h['n'],'train_count':len(train),'R10':xt(pred['sm'],pred['sb'],10)/h['x10'],'R50':xt(pred['sm'],pred['sb'],50)/h['x50'],'obs_x10_kn':h['x10'],'obs_x50_kn':h['x50']})
fields=list(dict.fromkeys(k for x in rows for k in x))
with (root/'minute_sensitivity_results.csv').open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
z=[r for r in rows if r.get('R10')];print('MINUTE_SENS',len(z),'hit',sum(abs(r['R10']-1)<=.15 for r in z),'invalid',[r for r in rows if r.get('error')],flush=True)
