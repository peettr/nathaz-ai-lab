"""Preregistered metrics; run on CPU Colab after complete observation and ERA extracts."""
from pathlib import Path
import json,csv,math
import numpy as np
from run_colab import ROOT,STATIONS,EXTRA,ALL
D=json.loads((ROOT/'obs.done').read_text());E=json.loads((ROOT/'era.done').read_text());assert D['rows']==154 and E['expected']==22
obs=[json.loads(z) for z in (ROOT/'station_seasons.jsonl').read_text().splitlines()];era={r['season_year']:r for r in (json.loads(z) for z in (ROOT/'era_seasons.jsonl').read_text().splitlines())}
assert len(obs)==154 and len({(x['station'],x['season_year']) for x in obs})==154 and len(era)==22
rows=[]
minute={}
if (ROOT/'minute.done').exists():
 assert json.loads((ROOT/'minute.done').read_text())['rows']==154
 minute={(r['station'],r['season_year']):r for r in (json.loads(z) for z in (ROOT/'minute_sensitivity.jsonl').read_text().splitlines())}
noconv={}
if (ROOT/'era_noconv.done').exists():
 assert json.loads((ROOT/'era_noconv.done').read_text())['seasons']==15
 noconv={r['season_year']:r for r in (json.loads(z) for z in (ROOT/'era_noconv.jsonl').read_text().splitlines())}
for o in obs:
 st=o['station'];y=o['season_year'];d=era[y]['stations'][st];p=o['peak']
 mp=(minute.get((st,y)) or {}).get('minute_peak')
 nc=noconv.get(y,{}).get('stations',{}).get(st,{})
 rows.append({'station':st,'season':o['season'],'season_year':y,'period':'main' if 2007<=y<=2021 else 'full_only','eligible':bool(o['coverage']>=.9 and p),'coverage':o['coverage'],'metar_covered_hours':o['hours_covered'],'metar_expected_hours':o['expected_hours'],'station_kn':p['kn'] if p else None,'minute_kn':mp['kn'] if mp else None,'minute_event_utc':mp['event_utc'] if mp else None,'event_utc':p['event_utc'] if p else None,'event_source':p['source'] if p else None,'event_raw':p['raw'] if p else None,'metar_url':o['metar_url'],'screen_count':o['screen_count'],'era_ace1_mps':d['ace1_max_mps'],'era_nearest025_mps':d['nearest025_max_mps'],'era_noconv_mps':nc.get('ace1_max_mps'),'era_max_utc':d['max_utc']})
with (ROOT/'season_pairs.csv').open('w',newline='') as f:
 fields=[k for k in rows[0] if k not in ('event_raw','screen_count')]+['screen_count_json','event_raw']
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for r in rows:w.writerow({k:(json.dumps(r['screen_count']) if k=='screen_count_json' else r.get(k)) for k in fields})

def score(v):
 # n x 2, ERA m/s to station knots is learned, no fixed gust factor.
 x=v[:,0];y=v[:,1];n=len(y)
 if n<3:return None
 pred=[];base=[]
 for k in range(n):
  keep=np.arange(n)!=k;xx=x[keep];yy=y[keep];den=np.sum((xx-xx.mean())**2)
  b=np.sum((xx-xx.mean())*(yy-yy.mean()))/den if den>1e-16 else 0.
  pred.append(yy.mean()+b*(x[k]-xx.mean()));base.append(yy.mean())
 pe=(y-np.array(pred))**2;be=(y-np.array(base))**2
 return {'S':float(1-pe.mean()/be.mean()) if be.mean()>0 else None,'pred':pred,'baseline':base,'pred_sq':pe,'baseline_sq':be}
def gumbel10(a):
 if len(a)<2:return None
 sd=np.std(a,ddof=0)
 return float(np.mean(a)+sd*math.sqrt(6)/math.pi*(-math.log(-math.log(.9))-0.5772156649015329))
def ratio(v,years):
 if len(v)<4:return None
 z=[]
 for parity in (0,1):
  tr=years%2==parity;te=~tr
  if tr.sum()<2 or te.sum()<2:return None
  a=v[tr];b=v[te];sx=np.std(a[:,0],ddof=0);sy=np.std(a[:,1],ddof=0)
  if sx<=1e-12:return None
  mapped=np.mean(a[:,1])+(b[:,0]-np.mean(a[:,0]))*sy/sx
  q=gumbel10(b[:,1]);pr=gumbel10(mapped)
  if q is None or q<=0 or pr<=0:return None
  z.append(pr/q)
 return math.sqrt(z[0]*z[1])
def quantile_ratio(v,years):
 if len(v)<4:return None
 z=[]
 for parity in (0,1):
  train=years%2==parity;test=~train
  if train.sum()<2 or test.sum()<2:return None
  a=v[train];b=v[test];order=np.argsort(a[:,0]);xx=a[order,0];yy=np.sort(a[:,1]);
  if np.ptp(xx)<=1e-12:return None
  mapped=np.interp(b[:,0],xx,yy,left=yy[0],right=yy[-1])
  q=gumbel10(b[:,1]);pred=gumbel10(mapped)
  if q is None or q<=0 or pred is None or pred<=0:return None
  z.append(pred/q)
 return math.sqrt(z[0]*z[1])

def metric(st,which='main',xfield='era_ace1_mps',yfield='station_kn'):
 eligible=[r for r in rows if r['station']==st and r['eligible'] and (which=='full' or r['period']=='main') and r[yfield] is not None]
 eligible.sort(key=lambda r:r['season_year'])
 v=np.array([[r[xfield],r[yfield]] for r in eligible]);years=np.array([r['season_year'] for r in eligible]);z=score(v)
 if z is None:return {'station':st,'period':which,'n':len(eligible),'S':None,'R':None,'valid':False}
 return {'station':st,'period':which,'n':len(eligible),'S':z['S'],'R':ratio(v,years),'quantile_R':quantile_ratio(v,years),'valid':len(eligible)>=12 if which=='main' else True,'years':years,'values':v,'errors':z}
main={st:metric(st) for st in STATIONS};full={st:metric(st,'full') for st in ALL};nearest={st:metric(st,xfield='era_nearest025_mps') for st in ALL};minutes={st:metric(st,yfield='minute_kn') for st in ALL} if minute else {};masked={st:metric(st,xfield='era_noconv_mps') for st in STATIONS} if noconv else {}
rng=np.random.default_rng(20261016);B=2000;bootS=[];bootR={st:[] for st in STATIONS}
for it in range(B):
 sampled=rng.integers(2007,2022,15)
 skills=[]
 for st in STATIONS:
  d=main[st];yy=d.get('years')
  if yy is None or len(yy)<12:skills.append(None);bootR[st].append(None);continue
  ids=np.array([int(np.where(yy==y)[0][0]) for y in sampled if y in yy]);e=d['errors'];pe=e['pred_sq'][ids];be=e['baseline_sq'][ids]
  skills.append(float(1-pe.mean()/be.mean()) if len(ids)>=3 and be.mean()>0 else None)
  bootR[st].append(ratio(d['values'][ids],yy[ids]))
 bootS.append(float(np.mean(skills)) if all(x is not None for x in skills) else None)
def interval(x):
 clean=[a for a in x if a is not None and np.isfinite(a)]
 return [float(v) for v in np.quantile(clean,[.05,.95])] if len(clean)>100 else None
mean_s=float(np.mean([main[st]['S'] for st in STATIONS])) if all(main[st]['S'] is not None for st in STATIONS) else None
metrics=[]
for st in ALL:
 for name,group in [('main',main),('full',full),('nearest025',nearest),('minute',minutes),('era_noconv',masked)]:
  d=group.get(st)
  if not d:continue
  metrics.append({'station':st,'analysis':name,'n':d['n'],'S':d['S'],'R':d['R'],'quantile_R_sensitivity':d.get('quantile_R'),'R_90lo':interval(bootR[st])[0] if name=='main' and st in bootR and interval(bootR[st]) else None,'R_90hi':interval(bootR[st])[1] if name=='main' and st in bootR and interval(bootR[st]) else None,'valid':d['valid']})
with (ROOT/'metrics.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
num_s=sum(main[st]['S'] is not None and main[st]['valid'] and main[st]['S']>.10 for st in STATIONS)
num_r=sum(main[st]['R'] is not None and main[st]['valid'] and abs(main[st]['R']-1)<=.15 for st in STATIONS)
ci=interval(bootS);low,high=(ci or [None,None])
if num_s>=4 and low is not None and low>0 and num_r>=3:verdict='通过'
elif num_s<=2 or (high is not None and high<=0) or num_r<=1:verdict='不通过'
else:verdict='说不清'
res={'verdict':verdict,'S_above_0_10':num_s,'R_within_0_15':num_r,'main_stations':STATIONS,'station_count':5,'mean_S':mean_s,'mean_S_90_interval':ci,'unavailable_stations':[s for s in STATIONS if not main[s]['valid']],'bootstrap_B':B,'bootstrap_seed':20261016,'prairie_not_established':verdict=='通过' and all(main[s]['S']<=.10 for s in STATIONS[:3])}
(ROOT/'decision.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print('DECISION',json.dumps(res,ensure_ascii=False),flush=True)
