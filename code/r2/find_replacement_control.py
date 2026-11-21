"""Find an independently corroborated replacement for unverified CNK control."""
import csv,datetime as dt,gzip,io,json,math,pathlib,requests,urllib.parse,urllib.request,re
R=pathlib.Path(__file__).parent; D=R/'segment_a_20261015'
used={x['utc'][:10] for x in csv.DictReader((R/'controls_r2_candidates.csv').open())}
events=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='v1']
url=events[0]['ncei_url'];r=requests.get(url,timeout=120);r.raise_for_status();src=list(csv.DictReader(io.StringIO(gzip.decompress(r.content).decode('utf-8-sig'))))
def dist(a,b,c,d):
 a,c=math.radians(a),math.radians(c);h=math.sin((a-c)/2)**2+math.cos(a)*math.cos(c)*math.sin(math.radians(b-d)/2)**2
 return 12742*math.asin(min(1,math.sqrt(h)))
reports=[]
for x in src:
 try:
  if x['EVENT_TYPE'] not in ('Thunderstorm Wind','High Wind','Strong Wind','Tornado','Hail'):continue
  tm=dt.datetime.strptime(x['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S');z=re.search(r'([+-]\d{1,2})$',x['CZ_TIMEZONE']);tm-=dt.timedelta(hours=int(z.group(1)))
  reports.append((tm,float(x['BEGIN_LAT']),float(x['BEGIN_LON'])))
 except (ValueError,TypeError,AttributeError):pass
def fetch(u):
 req=urllib.request.Request(u,headers={'User-Agent':'ResearchLab-ConvectiveValidation/1.0'})
 with urllib.request.urlopen(req,timeout=45) as f:return f.read().decode('utf-8-sig')
def wind(st,t):
 q={'station':st,'sts':(t-dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(t+dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust','format':'onlycomma','missing':'M','report_type':'3,4'}
 u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(q);rr=list(csv.DictReader(fetch(u).splitlines()));vals=[]
 for x in rr:
  for k in ('gust','peak_wind_gust'):
   try:vals.append(float(x[k]))
   except (ValueError,TypeError,KeyError):pass
 return max(vals) if vals else None,len(rr),u
states={'TEXAS':'TX','IOWA':'IA','NEBRASKA':'NE','KANSAS':'KS','OKLAHOMA':'OK','ARKANSAS':'AR'};networks={}
for days in (-7,-14,7,14):
 for e in events:
  t=dt.datetime.fromisoformat(e['utc'])+dt.timedelta(days=days)
  if t.strftime('%Y-%m-%d') in used:continue
  a,b=float(e['lat']),float(e['lon'])
  if any(abs((t-q[0]).total_seconds())<=10800 and dist(a,b,q[1],q[2])<=50 for q in reports):continue
  try:
   gust,n,u=wind(e['station'],t)
   if not (gust is not None and gust<40 and n>=5):continue
   key=states[e['state']]+'_ASOS'
   if key not in networks:networks[key]=json.loads(fetch('https://mesonet.agron.iastate.edu/geojson/network.py?'+urllib.parse.urlencode({'network':key})))['features']
   near=[]
   for f in networks[key]:
    lon,lat=f['geometry']['coordinates'][:2];km=dist(a,b,lat,lon)
    if 1<km<=50:near.append((km,f['properties'].get('sid') or f['properties'].get('id')))
   neighbors=[]
   for km,sid in near:
    if sid and sid!=e['station']:
     vg,m,link=wind(sid,t);neighbors.append(dict(station=sid,km=km,gust_kt=vg,reports=m,url=link))
   if not any(x['gust_kt'] is not None for x in neighbors) or any(x['gust_kt'] is not None and x['gust_kt']>=40 for x in neighbors):continue
   row={k:e[k] for k in ('station','lat','lon','ncei_url')};row.update(group='control',id='C'+e['id']+'_'+str(days),utc=t.isoformat(),obs_kt=gust,iem_url=u)
   (D/'replacement_control_v2.json').write_text(json.dumps(dict(row=row,neighbors=neighbors,source=url),indent=2))
   print('FOUND',row['id'],row['utc'],'own',gust,'neighbors',[(x['station'],x['gust_kt']) for x in neighbors]);raise SystemExit(0)
  except Exception as ex:print('SKIP',e['id'],repr(ex))
raise RuntimeError('No independent replacement found')
