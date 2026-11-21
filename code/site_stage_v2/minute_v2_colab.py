"""Frozen 1-min gust sensitivity on newly admitted v2 sites, Colab CPU only."""
import csv,io,json,time,os,sys,datetime as dt
from pathlib import Path
from collections import defaultdict
os.environ['SITE_STAGE_ROOT']='/content/site_stage_v2';sys.path.insert(0,'/content');import run_colab as core
root=Path('/content/site_stage_v2');adm=[r for r in csv.DictReader((root/'station_admission.csv').open()) if r['admitted']=='true'];meta={r['station']:r for r in csv.DictReader((root/'static_gates.csv').open())};core.ALL=[r['station'] for r in adm];core.COORD={st:(float(meta[st]['lat']),float(meta[st]['lon'])) for st in core.ALL};storm=json.loads((root/'storms.json').read_text());track=json.loads((root/'tracks.json').read_text());SE=defaultdict(list);TR=defaultdict(list)
for e in storm:SE[e['station']].append(e)
for e in track:TR[int(e['time'][:4])].append(e)
out=root/'minute_sensitivity.jsonl';done=set()
if out.exists():
 for line in out.read_text().splitlines():
  r=json.loads(line);done.add((r['station'],r['season_year']))
for st in core.ALL:
 for y in range(2007,2022):
  if (st,y) in done:continue
  a=dt.datetime(y,10,1);b=dt.datetime(y+1,4,1);url=core.query(st,a,b,fields='sknt,gust_sknt',kind='minute')
  for attempt in range(5):
   minute={};count=0
   try:
    with core.fetch(url) as resp:
     rd=csv.DictReader(io.TextIOWrapper(resp,encoding='utf8',errors='replace'))
     for r in rd:
      t=core.parse(r.get('valid(UTC)') or r.get('valid') or '')
      if not t or not a<=t<b:continue
      k=int((t-a).total_seconds()//60);v=core.num(r.get('gust_sknt'));count+=1
      if v is not None:minute[k]=v
    break
   except Exception as ex:
    print('RETRY',st,y,attempt,repr(ex),flush=True)
    if attempt==4:raise
    time.sleep(5*(attempt+1))
  obs=core.load_obs(st,y);metarmax=max((v['value'] for v in obs['candidates']),default=0);counts=defaultdict(int);selected=None
  for k,v in sorted(minute.items(),key=lambda z:(-z[1],z[0])):
   neighbors=[minute[j] for j in range(max(0,k-5),k+6) if j!=k and j in minute]
   if v-metarmax>=20 and neighbors and v-max(neighbors)>=30:counts['isolated_spike_removed']+=1;continue
   t=a+dt.timedelta(minutes=k);lab,ev=core.label({'time':t,'value':v},obs,SE[st],TR[y]+TR[y+1]);counts[lab]+=1
   if lab=='nonconvective':selected={'kn':v,'event_utc':core.stamp(t),'evidence':ev};break
  row={'station':st,'season_year':y,'minute_peak':selected,'coverage':obs['coverage'],'metar_season_peak_kn':metarmax,'screen_count':dict(counts),'minute_source_url':url,'rows':count}
  with out.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
  print('MINUTE',st,y,selected and selected['kn'],counts['isolated_spike_removed'],flush=True)
(root/'minute.done').write_text(str(len(core.ALL)*15));print('DONE',len(core.ALL)*15,flush=True)
