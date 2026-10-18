"""Postprocess station-season audit on Colab CPU with NOAA Storm Events/HURDAT2.
No raw observations archived; retain per-peak METAR evidence, official event ids, source URLs.
"""
import csv,gzip,io,json,math,re,urllib.request,urllib.parse,datetime as dt,time,os
from pathlib import Path
P=Path('/content/site_stage_audit');META=json.load(open('/content/homr_station_counties.json'))
BY={x['station']:x for x in META}
CO={x['station']:(x['counties'][0]['county'].upper(),x['states'][0]['stateProvince'].upper()) for x in META}
# coordinates from current IEM network metadata; metadata API gives independent station identity
with open('/content/station_mapping.csv') as mf:
 ST={r['asos_icao']:(float(r['station_lat']),float(r['station_lon'])) for r in csv.DictReader(mf)}
assert set(ST)==set(BY)
# Replace provisional coordinate literals with verified HOMR ASOS site survey coordinates.
hist=json.load(open('/content/homr_history.json'))
for rec in hist['rows']:
 if rec['ncdc_id'] != BY.get(rec['station'],{}).get('ncdc_id'):continue
 pairs=json.loads(rec['locations_2000_plus'])
 if pairs:
  p=max(pairs,key=lambda x:x['date']['beginDate'])
  ST[rec['station']]=(float(p['latitude_dec']),float(p['longitude_dec']))
HEAD={'User-Agent':'PETW-AIWeather-site-audit/1.0'}
def fetch(url):
 for i in range(4):
  try:return urllib.request.urlopen(urllib.request.Request(url,headers=HEAD),timeout=150)
  except Exception:
   if i==3:raise
   time.sleep((i+1)*4)
def iso(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None)
def hav(a,b,c,d):
 a,b,c,d=map(math.radians,(a,b,c,d));q=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(q)))
# NOAA event filename directory listing; two identical hrefs per year
base='https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'
html=fetch(base).read().decode('utf-8');names=set(re.findall(r'StormEvents_details-ftp_v1\.0_d\d{4}_c\d{8}\.csv\.gz',html))
files={int(re.search(r'_d(\d{4})_',n).group(1)):base+n for n in names}
assert all(y in files for y in range(2000,2025))
# select only 15 counties; zone events kept only if cz_name equals county name (under-inclusive)
events=[]; failures=[]
for y in range(2000,2025):
 url=files[y]
 try:
  with fetch(url) as resp, gzip.GzipFile(fileobj=resp) as gz:
   rd=csv.DictReader(io.TextIOWrapper(gz,encoding='utf-8-sig',errors='replace'))
   for r in rd:
    county=(r.get('CZ_NAME') or r.get('cz_name') or '').upper().strip()
    state=(r.get('STATE') or r.get('state') or '').upper().strip()
    ty=(r.get('EVENT_TYPE') or r.get('event_type') or '').strip()
    if ty not in ('Thunderstorm Wind','Tornado','High Wind','Strong Wind','Blizzard','Hurricane (Typhoon)','Tropical Storm','Tropical Depression'):continue
    for station,(co,st) in CO.items():
     if county!=co or state!=({'MN':'MINNESOTA','IA':'IOWA','NE':'NEBRASKA','MI':'MICHIGAN','PA':'PENNSYLVANIA','NY':'NEW YORK','TX':'TEXAS','SD':'SOUTH DAKOTA','ND':'NORTH DAKOTA','KS':'KANSAS','MO':'MISSOURI','IN':'INDIANA','OH':'OHIO','CT':'CONNECTICUT'}[st]):continue
     z=(r.get('CZ_TIMEZONE') or r.get('cz_timezone') or '').upper()
     m=re.search(r'([+-]\d{1,2})',z)
     if not m:continue
     off=int(m.group(1))
     def parse_date(s):
      for f in ('%d-%b-%y %H:%M:%S','%d-%b-%y %H:%M','%m/%d/%Y %H:%M:%S','%m/%d/%Y %H:%M'):
       try:return dt.datetime.strptime(s.strip(),f)-dt.timedelta(hours=off)
       except ValueError:pass
      return None
     beg=parse_date(r.get('BEGIN_DATE_TIME',''));end=parse_date(r.get('END_DATE_TIME',''))
     if beg is None or end is None:continue
     events.append({'station':station,'type':ty,'begin_utc':beg.isoformat()+'Z','end_utc':end.isoformat()+'Z','event_id':r.get('EVENT_ID'),'cz_type':r.get('CZ_TYPE'),'cz_name':county,'tz_raw':z,'url':url})
  print('STORM',y,len(events),flush=True)
 except Exception as e:failures.append({'year':y,'error':repr(e),'url':url});print('STORM_ERROR',y,repr(e),flush=True)
 (P/'storm_events_filtered.json').write_text(json.dumps({'events':events,'failures':failures},ensure_ascii=False))
# HURDAT2 tracks: nearest fix ±3h, includes subtropical/post-tropical states in conservative distance screen
nhc='https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt';tracks=[];name=''
try:
 lines=fetch(nhc).read().decode('ascii',errors='replace').splitlines()
 for line in lines:
  x=[s.strip() for s in line.split(',')]
  if re.match(r'AL\d\d\d\d\d\d',x[0]):name=x[1];continue
  if len(x)<8:continue
  try:
   t=dt.datetime.strptime(x[0]+x[1],'%Y%m%d%H%M')
   lat=float(x[4][:-1])*(-1 if x[4][-1]=='S' else 1);lon=float(x[5][:-1])*(-1 if x[5][-1]=='W' else 1)
   tracks.append({'time_utc':t.isoformat()+'Z','lat':lat,'lon':lon,'name':name,'status':x[3]})
  except (ValueError,IndexError):pass
except Exception as e:failures.append({'nhc':nhc,'error':repr(e)})
(P/'nhc_tracks_status.json').write_text(json.dumps({'points':len(tracks),'url':nhc,'failures':failures}))
# apply peak rules with fresh short IEM METAR window, peak timing for PK WND supplied by IEM
seasons=[json.loads(s) for s in (P/'season_audit.jsonl').read_text().splitlines() if s.strip()]
assert len({(x['station'],x['season']) for x in seasons})==len(seasons)
from collections import defaultdict
E=defaultdict(list)
for e in events:E[e['station']].append(e)
T=defaultdict(list)
for tr in tracks:T[tr['time_utc'][:4]].append(tr)
def metars(station,peak):
 a=peak-dt.timedelta(hours=2);b=peak+dt.timedelta(hours=2)
 params={'station':station[1:],'data':'gust,peak_wind_gust,peak_wind_time,wxcodes,metar','sts':a.strftime('%Y-%m-%dT%H:%MZ'),'ets':b.strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','report_type':'1,3,4','format':'onlycomma','missing':'M'}
 url='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
 time.sleep(1.05)
 with fetch(url) as resp:rows=list(csv.DictReader(io.TextIOWrapper(resp,encoding='utf-8',errors='replace')))
 return rows,url
RE=re.compile(r'(?<![A-Z])(?:VCTS|SQ|CB)(?![A-Z])|(?<![A-Z])TS(?=$|[^A-Z]|RA|SN|GR|GS)(?!NO)')
METAR_CACHE={}
def classify(st,peak):
 cache_key=(st,peak.replace(minute=0,second=0))
 try:
  if cache_key not in METAR_CACHE:METAR_CACHE[cache_key]=metars(st,peak)
  reports,url=METAR_CACHE[cache_key]
 except Exception as e:return {'label':'unknown','error':repr(e),'metar_available':False}
 close=[];hours=set();hits=[]
 for r in reports:
  try:t=iso(r['valid'].replace(' ','T')+'Z')
  except ValueError:continue
  if abs((t-peak).total_seconds())<=3600:
   close.append({'utc':t.isoformat()+'Z','wxcodes':r.get('wxcodes'),'metar':(r.get('metar') or '')[:700]})
   hours.add(t.replace(minute=0,second=0))
   if RE.search(' '+(r.get('wxcodes') or '')+' '+(r.get('metar') or '')+' '):hits.append(t.isoformat()+'Z')
 # ±1h complete hourly coverage: three bins containing peak-1h,peak,peak+1h
 bins={ (peak+dt.timedelta(hours=h)).replace(minute=0,second=0) for h in (-1,0,1)}
 complete=bins.issubset(hours)
 matched=[]
 for e in E[st]:
  b=iso(e['begin_utc']);end=iso(e['end_utc']);
  if b-dt.timedelta(hours=1)<=peak<=end+dt.timedelta(hours=1):matched.append(e)
 tr_hits=[]
 for tr in T[str(peak.year)]:
  if abs((iso(tr['time_utc'])-peak).total_seconds())<=10800:
   d=hav(*ST[st],tr['lat'],tr['lon'])
   if d<=500:tr_hits.append({'name':tr['name'],'time_utc':tr['time_utc'],'distance_km':round(d,1),'status':tr['status']})
 conv=bool(hits or any(e['type'] in ('Thunderstorm Wind','Tornado') for e in matched))
 tropical=bool(tr_hits or any(e['type'] in ('Hurricane (Typhoon)','Tropical Storm','Tropical Depression') for e in matched))
 nonconv=any(e['type'] in ('High Wind','Strong Wind','Blizzard') for e in matched)
 label='unknown' if conv and tropical else 'convection' if conv else 'tropical_cyclone' if tropical else 'nonconvective' if nonconv or (complete and not failures) else 'unknown'
 # if storm dataset incomplete, cannot infer negative from missing event
 return {'label':label,'metar_available':bool(close),'metar_hourly_complete':complete,'metar_hits':hits,'metars_near_peak':close,'matched_events':matched,'nhc_500km_fixes':tr_hits,'metar_url':url,'evidence_level':'county/track proxy' if (matched or tr_hits) else 'station METAR proxy','storm_source_failures':failures}
out=P/'peak_labels.jsonl'
with out.open('x') as f:
 for i,s in enumerate(seasons):
  peaks=[('minute',s['minute_peak_utc'],s['minute_peak_knots'])]
  for typ,key in (('metar_gust','metar_max_gust'),('metar_pk','metar_max_pk')):
   z=s.get(key)
   if z:peaks.append((typ,z.get('peak_wind_time_raw') if typ=='metar_pk' else z['report_utc'],z['knots']))
  for typ,t,v in peaks:
   if not t:continue
   try:peak=iso(t.replace(' ','T')+'Z' if not t.endswith('Z') else t)
   except ValueError:continue
   r={'station':s['station'],'season':s['season'],'peak_type':typ,'peak_utc':peak.isoformat()+'Z','knots':v,'evidence':classify(s['station'],peak)}
   f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
  if i%15==0:print('CLASSIFY',i,len(seasons),flush=True)
(P/'labels.exit.json').write_text(json.dumps({'seasons':len(seasons),'labels':sum(1 for _ in out.open()),'storm_failures':failures,'nhc_points':len(tracks)}))
