"""Station-only v2 admission, 2007/08–2021/22; no ERA5 pairing."""
import os,sys,csv,json,time,datetime as dt,traceback
from pathlib import Path
os.environ['SITE_STAGE_ROOT']='/content/site_stage_v2'
sys.path.insert(0,'/content')
import run_colab as core
root=Path('/content/site_stage_v2');meta=list(csv.DictReader((root/'static_gates.csv').open()))
core.ALL=[r['station'] for r in meta];core.CO={r['station']:(r['county'].upper(),{'MN':'MINNESOTA','ND':'NORTH DAKOTA','SD':'SOUTH DAKOTA','IA':'IOWA','NE':'NEBRASKA','KS':'KANSAS','MO':'MISSOURI','OK':'OKLAHOMA','IL':'ILLINOIS','NY':'NEW YORK','OH':'OHIO','MI':'MICHIGAN','PA':'PENNSYLVANIA','IN':'INDIANA','KY':'KENTUCKY','TN':'TENNESSEE','WV':'WEST VIRGINIA','VA':'VIRGINIA','NC':'NORTH CAROLINA','SC':'SOUTH CAROLINA','GA':'GEORGIA','AL':'ALABAMA','MS':'MISSISSIPPI','AR':'ARKANSAS','LA':'LOUISIANA','TX':'TEXAS','CT':'CONNECTICUT','WI':'WISCONSIN'}.get(r['state'],r['state'])) for r in meta}
core.COORD={r['station']:(float(r['lat']),float(r['lon'])) for r in meta}
print('county',core.CO,flush=True)
storm=core.storm_data();track=core.tracks()
from collections import defaultdict
SE=defaultdict(list);TR=defaultdict(list)
for x in storm:SE[x['station']].append(x)
for x in track:TR[int(x['time'][:4])].append(x)
p=root/'station_only_seasons.jsonl';done=set()
if p.exists():
 for line in p.read_text().splitlines():
  v=json.loads(line);done.add((v['station'],v['season_year']))
for st in core.ALL:
 for y in range(2007,2022):
  if (st,y) in done:continue
  try:
   o=core.load_obs(st,y);rank=sorted(o['candidates'],key=lambda z:(-z['value'],z['time']));selected=None;counts=defaultdict(int)
   for cand in rank:
    lab,ev=core.label(cand,o,SE[st],TR[y]+TR[y+1]);counts[lab]+=1
    if lab=='nonconvective':
     selected={'kn':cand['value'],'event_utc':core.stamp(cand['time']),'source':cand['source'],'evidence':ev};break
   v={'station':st,'season_year':y,'coverage':o['coverage'],'peak':selected,'valid':bool(o['coverage']>=.9 and selected is not None),'screen_count':dict(counts),'metar_url':o['url']}
  except Exception as ex:
   v={'station':st,'season_year':y,'valid':False,'error':repr(ex),'trace':traceback.format_exc()[-600:]}
  with p.open('a') as f:f.write(json.dumps(v)+'\n');f.flush();os.fsync(f.fileno())
  print('SEASON',st,y,v.get('coverage'),v.get('valid'),v.get('error',''),flush=True)
(root/'admission.done').write_text(str(len(core.ALL)*15))
print('FINISHED',len(core.ALL)*15,flush=True)
