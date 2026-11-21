"""Freeze six 2026 CONUS station/time controls with event and neighbor checks."""
import csv,datetime as dt,gzip,io,math,pathlib,requests,urllib.parse,urllib.request,re,json,time
R=pathlib.Path(__file__).parent;outdir=R/'segment_b_20261015';outdir.mkdir(exist_ok=True)
positives=[r for r in csv.DictReader((R/'events_r2_verified.csv').open()) if r['group']=='conus']
assert len(positives)>=10
url=positives[0]['ncei_url'];reply=requests.get(url,timeout=120);reply.raise_for_status();entries=list(csv.DictReader(io.StringIO(gzip.decompress(reply.content).decode('utf-8-sig'))))
reports=[]
for e in entries:
 try:
  if e['EVENT_TYPE'] not in ('Thunderstorm Wind','High Wind','Strong Wind','Tornado','Hail'):continue
  t=dt.datetime.strptime(e['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S');z=re.search(r'([+-]\d{1,2})$',e['CZ_TIMEZONE']);t-=dt.timedelta(hours=int(z.group(1)))
  reports.append((t,float(e['BEGIN_LAT']),float(e['BEGIN_LON']),e['EVENT_TYPE']))
 except (ValueError,TypeError,AttributeError):pass
print('ARCHIVE',url,len(reports),flush=True)
def km(a,b,c,d):
 a,c=math.radians(a),math.radians(c);v=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin(math.radians(d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(v)))
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ResearchLab-ConvectiveValidation/1.0'})
 with urllib.request.urlopen(req,timeout=60) as f:return f.read().decode('utf-8-sig')
def station(station,t):
 params={'station':station,'sts':(t-dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(t+dt.timedelta(hours=3)).strftime('%Y-%m-%dT%H:%MZ'),'tz':'UTC','data':'gust,peak_wind_gust,metar','format':'onlycomma','missing':'M','report_type':'3,4'}
 u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urllib.parse.urlencode(params)
 records=list(csv.DictReader(fetch(u).splitlines()));values=[]
 for rec in records:
  for k in ('gust','peak_wind_gust'):
   try:values.append(float(rec[k]))
   except (ValueError,TypeError,KeyError):pass
 return max(values) if values else None,len(records),u
states={'NEBRASKA':'NE','KANSAS':'KS','ARKANSAS':'AR','OKLAHOMA':'OK','ILLINOIS':'IL'};networks={};controls=[];audit=[];used=set()
for offset_days in (-7,-14,7,14):
 for e in positives:
  if len(controls)>=6:break
  t=dt.datetime.fromisoformat(e['utc'])+dt.timedelta(days=offset_days);a,b=float(e['lat']),float(e['lon'])
  if t.date() in used or any(abs((q[0]-t).total_seconds())<=3*3600 and km(a,b,q[1],q[2])<=50 for q in reports):continue
  try:
   gust,n,u=station(e['station'],t)
   if n<5 or gust is None or gust>=40:continue
   state=e['state'];key=states[state]+'_ASOS'
   if key not in networks:networks[key]=json.loads(fetch('https://mesonet.agron.iastate.edu/geojson/network.py?'+urllib.parse.urlencode({'network':key})))['features']
   near=[]
   for f in networks[key]:
    x,y=f['geometry']['coordinates'][:2];dist=km(a,b,y,x)
    if 1<dist<=50:near.append((dist,f['properties'].get('sid') or f['properties'].get('id')))
   neighbors=[]
   for dist,sid in sorted(near):
    if not sid:continue
    g,num,link=station(sid,t);neighbors.append(dict(station=sid,km=round(dist,1),peak_kt=g,reports=num,url=link));time.sleep(.1)
   status='nearby_metar_lt40' if any(z['peak_kt'] is not None for z in neighbors) and all(z['peak_kt'] is None or z['peak_kt']<40 for z in neighbors) else 'uncertain'
   item=dict(group='control',id='C'+e['id']+'_'+str(offset_days),station=e['station'],utc=t.isoformat(),obs_kt=gust,lat=e['lat'],lon=e['lon'],ncei_url=url,iem_url=u)
   if status=='nearby_metar_lt40':controls.append(item);used.add(t.date())
   audit.append(dict(id=item['id'],status=status,neighbors=neighbors,own_gust_kt=gust,storm_reports_50km_3h=0))
   print(item['id'],status,len(neighbors),flush=True)
  except Exception as ex:print('FAILED',e['id'],repr(ex),flush=True);audit.append(dict(id='C'+e['id'],status='error',error=repr(ex)))
assert len(controls)>=6,f'Only {len(controls)} independent controls; cannot score negative cohort'
manifest=outdir/'controls_conus_verified.csv';assert not manifest.exists()
with manifest.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(controls[0]));w.writeheader();w.writerows(controls)
with (outdir/'controls_audit.jsonl').open('x') as f:
 for x in audit:f.write(json.dumps(x)+'\n')
print('COMPLETE',len(controls),flush=True)
