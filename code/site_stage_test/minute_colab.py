"""Frozen one-minute gust sensitivity, Colab CPU; stream raw rows, save only season summaries."""
import csv,io,json,time,datetime as dt,urllib.request
from pathlib import Path
from collections import defaultdict
from run_colab import ROOT,ALL,fetch,query,parse,num,load_obs,label,stamp
obs={}
for z in (ROOT/'station_seasons.jsonl').read_text().splitlines():
 r=json.loads(z);obs[(r['station'],r['season_year'])]=r
storm=json.loads((ROOT/'storms.json').read_text());track=json.loads((ROOT/'tracks.json').read_text())
SE=defaultdict(list);TR=defaultdict(list)
for e in storm:SE[e['station']].append(e)
for e in track:TR[int(e['time'][:4])].append(e)
out=ROOT/'minute_sensitivity.jsonl';done=set()
if out.exists():
 for z in out.read_text().splitlines():
  x=json.loads(z);done.add((x['station'],x['season_year']))
for y in range(2000,2022):
 for st in ALL:
  if (st,y) in done:continue
  a=dt.datetime(y,10,1);b=dt.datetime(y+1,4,1);url=query(st,a,b,fields='sknt,gust_sknt',kind='minute')
  for attempt in range(5):
   minute={};rowcount=0
   try:
    with fetch(url) as resp:
     reader=csv.DictReader(io.TextIOWrapper(resp,encoding='utf8',errors='replace'))
     for r in reader:
      t=parse(r.get('valid(UTC)') or r.get('valid') or '')
      if not t or not a<=t<b:continue
      k=int((t-a).total_seconds()//60);v=num(r.get('gust_sknt'))
      rowcount+=1
      if v is not None:minute[k]=v
    break
   except Exception as exc:  # includes http.client.IncompleteRead mid-stream
    print('MINUTE_RETRY',st,y,attempt,repr(exc),flush=True)
    if attempt==4:raise
    time.sleep(5*(attempt+1))
  obsfull=load_obs(st,y);metarmax=max((v['value'] for v in obsfull['candidates']),default=0)
  evs=SE[st];fixes=TR[y]+TR[y+1];counts=defaultdict(int);selected=None
  for k,v in sorted(minute.items(),key=lambda z:(-z[1],z[0])):
   neighbors=[minute[j] for j in range(max(0,k-5),k+6) if j!=k and j in minute]
   isolated=(v-metarmax>=20 and bool(neighbors) and v-max(neighbors)>=30)
   if isolated:counts['isolated_spike_removed']+=1;continue
   t=a+dt.timedelta(minutes=k);c={'time':t,'value':v}
   lab,ev=label(c,obsfull,evs,fixes);counts[lab]+=1
   if lab=='nonconvective':selected={'kn':v,'event_utc':stamp(t),'source_url':url,'evidence':ev};break
  row={'station':st,'season_year':y,'minute_peak':selected,'coverage':obsfull['coverage'],'metar_season_peak_kn':metarmax,'screen_count':dict(counts),'minute_source_url':url,'rows':rowcount}
  with out.open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
  print('MINUTE',st,y,selected and selected['kn'],counts['isolated_spike_removed'],flush=True)
  time.sleep(.3)
(ROOT/'minute.done').write_text(json.dumps({'rows':sum(1 for _ in out.open()),'expected':154}))
