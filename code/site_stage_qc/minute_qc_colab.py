"""Minute sensitivity: same Q1-Q4 candidate checks, not primary decision."""
import csv,io,json,os,sys,datetime as dt,time,math,re
from pathlib import Path
from collections import defaultdict,Counter
os.environ['SITE_STAGE_ROOT']='/content/site_stage_qc';sys.path.insert(0,'/content');import run_colab as core
root=Path('/content/site_stage_qc/corrected');adm=[r for r in csv.DictReader((root/'station_admission.csv').open()) if r['admitted']=='true'];meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())};core.ALL=[r['station'] for r in adm];core.COORD={st:(float(meta[st]['lat']),float(meta[st]['lon'])) for st in core.ALL}
storm=json.loads((root.parent/'storms.json').read_text());track=json.loads((root.parent/'tracks.json').read_text());SE=defaultdict(list);TR=defaultdict(list)
for e in storm:SE[e['station']].append(e)
for e in track:TR[int(e['time'][:4])].append(e)
ref={(x['station'],x['season_year']):x for x in map(json.loads,(root/'qc_station_seasons.jsonl').read_text().splitlines())}
out=root/'minute_qc_sensitivity.jsonl';assert not out.exists()
for st in core.ALL:
 for y in range(2007,2022):
  try:
   a=dt.datetime(y,10,1);b=dt.datetime(y+1,4,1);url=core.query(st,a,b,fields='sknt,gust_sknt',kind='minute')
   for attempt in range(5):
    minute={};count=0
    try:
     with core.fetch(url) as resp:
      rd=csv.DictReader(io.TextIOWrapper(resp,encoding='utf8',errors='replace'))
      for row in rd:
       t=core.parse(row.get('valid(UTC)') or row.get('valid') or '')
       if not t or not a<=t<b:continue
       k=int((t-a).total_seconds()//60);v=core.num(row.get('gust_sknt'));s=core.num(row.get('sknt'));count+=1
       if v is not None:minute[k]=(v,s)
     break
    except Exception as ex:
     print('RETRY',st,y,attempt,repr(ex),flush=True)
     if attempt==4:raise
     time.sleep(5*(attempt+1))
   obs=core.load_obs(st,y);metarmax=max((v['value'] for v in obs['candidates']),default=0);counts=Counter();selected=None
   # Maxima of minute gusts, excluding the current timestamp. Q4 considers ±3 hours of other reports' wind maxima.
   for k,(v,s) in sorted(minute.items(),key=lambda z:(-z[1][0],z[0])):
    rules=[]
    if v>100:rules.append('Q1')
    if v!=int(v):rules.append('Q2') # minute archive has no METAR text; cannot reparse
    if s is not None and v-s>40:rules.append('Q3')
    nearby=[max(z for z in (w,sp) if z is not None) for j,(w,sp) in minute.items() if j!=k and abs(j-k)<=180]
    if nearby and v-max(nearby)>30:rules.append('Q4')
    neighbors=[minute[j][0] for j in range(max(0,k-5),k+6) if j!=k and j in minute]
    if v-metarmax>=20 and neighbors and v-max(neighbors)>=30:rules.append('v2_isolated_spike')
    if rules:
     counts.update(rules);continue
    t=a+dt.timedelta(minutes=k);lab,ev=core.label({'time':t,'value':v},obs,SE[st],TR[y]+TR[y+1]);counts[lab]+=1
    if lab=='nonconvective':selected={'kn':v,'event_utc':core.stamp(t),'evidence':ev};break
   entry={'station':st,'season_year':y,'minute_peak':selected,'coverage':obs['coverage'],'q_counts':dict(counts),'minute_source_url':url,'rows':count,'valid':ref[st,y]['valid'] and selected is not None}
  except Exception as ex:entry={'station':st,'season_year':y,'error':repr(ex),'valid':False}
  with out.open('a') as f:f.write(json.dumps(entry)+'\n');f.flush();os.fsync(f.fileno())
  print('MIN',st,y,entry.get('minute_peak',{}),entry.get('error',''),flush=True)
(root/'minute.done').write_text(json.dumps({'rows':435,'errors':sum('error' in json.loads(z) for z in out.open())}));print('MINUTE_DONE',flush=True)
