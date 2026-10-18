"""Supplement Storm Events records with legacy CST/EST/MST fields and relabel v1.
Produces new versioned files; never rewrites prior outputs.
"""
import csv,gzip,io,json,re,urllib.request,datetime as dt,time
from pathlib import Path
P=Path('/content/site_stage_audit');META=json.load(open('/content/homr_station_counties.json'))
CO={x['station']:(x['counties'][0]['county'].upper(),x['states'][0]['stateProvince'].upper()) for x in META}
STATES={'MN':'MINNESOTA','IA':'IOWA','NE':'NEBRASKA','MI':'MICHIGAN','PA':'PENNSYLVANIA','NY':'NEW YORK','TX':'TEXAS','SD':'SOUTH DAKOTA','ND':'NORTH DAKOTA','KS':'KANSAS','MO':'MISSOURI','IN':'INDIANA','OH':'OHIO','CT':'CONNECTICUT'}
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/';html=urllib.request.urlopen(base,timeout=60).read().decode();names=set(re.findall(r'StormEvents_details-ftp_v1\.0_d\d{4}_c\d{8}\.csv\.gz',html));files={int(re.search(r'_d(\d{4})_',n).group(1)):base+n for n in names}
events=[];fail=[]
for y in range(2000,2008):
 try:
  with urllib.request.urlopen(files[y],timeout=100) as resp,gzip.GzipFile(fileobj=resp) as gz:
   for r in csv.DictReader(io.TextIOWrapper(gz,encoding='utf-8-sig',errors='replace')):
    county=(r.get('CZ_NAME') or '').strip().upper();state=(r.get('STATE') or '').strip().upper()
    ty=(r.get('EVENT_TYPE') or '').strip()
    if ty not in ('Thunderstorm Wind','Tornado','High Wind','Strong Wind','Blizzard','Hurricane (Typhoon)','Tropical Storm','Tropical Depression'):continue
    z=(r.get('CZ_TIMEZONE') or '').strip().upper()
    m=re.search(r'([+-]\d{1,2})',z);off=int(m.group(1)) if m else {'CST':-6,'EST':-5,'MST':-7,'PST':-8,'AST':-4}.get(z)
    if off is None:continue
    def parse(s):
     for f in ('%d-%b-%y %H:%M:%S','%d-%b-%y %H:%M','%m/%d/%Y %H:%M:%S'):
      try:return (dt.datetime.strptime(s.strip(),f)-dt.timedelta(hours=off)).isoformat()+'Z'
      except ValueError:pass
     return None
    b=parse(r.get('BEGIN_DATE_TIME',''));e=parse(r.get('END_DATE_TIME',''))
    if not b or not e:continue
    for st,(co,abbr) in CO.items():
     if county==co and state==STATES[abbr]:events.append({'station':st,'type':ty,'begin_utc':b,'end_utc':e,'event_id':r.get('EVENT_ID'),'cz_type':r.get('CZ_TYPE'),'cz_name':county,'tz_raw':z,'url':files[y]})
  print('SUPPLEMENT',y,len(events),flush=True)
 except Exception as exc:fail.append({'year':y,'error':repr(exc)});print('SUPPLEMENT_ERROR',y,repr(exc),flush=True)
(P/'storm_events_legacy_supplement.json').open('x').write(json.dumps({'events':events,'failures':fail}))
from collections import defaultdict
old=json.load(open(P/'storm_events_filtered.json'))['events'];dedup={(e['station'],e['event_id']):e for e in old+events}
E=defaultdict(list)
for e in dedup.values():E[e['station']].append(e)
def iso(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None)
labels=[json.loads(z) for z in (P/'peak_labels.jsonl').read_text().splitlines() if z]
out=P/'peak_labels_corrected.jsonl';counts={}
with out.open('x') as f:
 for r in labels:
  st=r['station'];t=iso(r['peak_utc']);ev=r['evidence'];hit=[]
  for x in E[st]:
   if iso(x['begin_utc'])-dt.timedelta(hours=1)<=t<=iso(x['end_utc'])+dt.timedelta(hours=1):hit.append(x)
  cv=bool(ev.get('metar_hits') or any(e['type'] in ('Thunderstorm Wind','Tornado') for e in hit));tc=bool(ev.get('nhc_500km_fixes') or any(e['type'] in ('Hurricane (Typhoon)','Tropical Storm','Tropical Depression') for e in hit))
  nc=any(e['type'] in ('High Wind','Strong Wind','Blizzard') for e in hit)
  new='unknown' if cv and tc else 'convection' if cv else 'tropical_cyclone' if tc else 'nonconvective' if nc or (ev.get('metar_hourly_complete') and not fail and not ev.get('storm_source_failures')) else 'unknown'
  if new!=ev.get('label'):counts[(ev.get('label'),new)]=counts.get((ev.get('label'),new),0)+1
  ev['label_original']=ev.get('label');ev['label']=new;ev['matched_events']=hit;ev['legacy_timezone_supplement']=True;r['evidence']=ev
  f.write(json.dumps(r,ensure_ascii=False)+'\n')
(P/'corrected.exit.json').open('x').write(json.dumps({'input_labels':len(labels),'output_labels':sum(1 for _ in out.open()),'legacy_events':len(events),'source_failures':fail,'label_changes':{str(k):v for k,v in counts.items()}}))
print('CORRECTED',len(labels),counts,flush=True)
