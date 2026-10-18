"""Retry only four IEM transport errors, preserving original audit file."""
import csv,json,os,sys,time,datetime as dt
from pathlib import Path
os.environ['SITE_STAGE_ROOT']='/content/site_stage_v2';sys.path.insert(0,'/content');import run_colab as core
root=Path('/content/site_stage_v2');meta=list(csv.DictReader((root/'static_gates.csv').open()));core.ALL=[r['station'] for r in meta]
old=[json.loads(x) for x in (root/'station_only_seasons.jsonl').read_text().splitlines()];errors=[x for x in old if x.get('error')];assert len(errors)==4,(len(errors),errors)
# Restore coordinates/counties to match original stage exactly.
core.COORD={r['station']:(float(r['lat']),float(r['lon'])) for r in meta}
states={'MN':'MINNESOTA','ND':'NORTH DAKOTA','SD':'SOUTH DAKOTA','IA':'IOWA','NE':'NEBRASKA','KS':'KANSAS','MO':'MISSOURI','OK':'OKLAHOMA','IL':'ILLINOIS','NY':'NEW YORK','OH':'OHIO','MI':'MICHIGAN','PA':'PENNSYLVANIA','IN':'INDIANA','KY':'KENTUCKY','TN':'TENNESSEE','WV':'WEST VIRGINIA','VA':'VIRGINIA','NC':'NORTH CAROLINA','SC':'SOUTH CAROLINA','GA':'GEORGIA','AL':'ALABAMA','MS':'MISSISSIPPI','AR':'ARKANSAS','LA':'LOUISIANA','TX':'TEXAS','CT':'CONNECTICUT','WI':'WISCONSIN'}
core.CO={r['station']:(r['county'].upper(),states.get(r['state'],r['state'])) for r in meta}
storm=core.storm_data();tracks=core.tracks();resolved={}
for x in errors:
 st=x['station'];y=x['season_year'];o=core.load_obs(st,y);rank=sorted(o['candidates'],key=lambda z:(-z['value'],z['time']));evs=[e for e in storm if e['station']==st];fixes=[f for f in tracks if int(f['time'][:4]) in (y,y+1)];selected=None
 for c in rank:
  label,evidence=core.label(c,o,evs,fixes)
  if label=='nonconvective':selected={'kn':c['value'],'event_utc':core.stamp(c['time']),'source':c['source'],'evidence':evidence};break
 v={'station':st,'season_year':y,'coverage':o['coverage'],'peak':selected,'valid':bool(o['coverage']>=.9 and selected),'metar_url':o['url'],'retried_transport_error':x['error']};resolved[(st,y)]=v;print('RETRY_OK',st,y,v['coverage'],v['peak'],flush=True)
assert len(resolved)==4
out=root/'station_only_seasons_corrected.jsonl';assert not out.exists()
with out.open('x') as f:
 for v in old:f.write(json.dumps(resolved.get((v['station'],v['season_year']),v))+'\n')
print('CORRECTED',len(old),flush=True)
