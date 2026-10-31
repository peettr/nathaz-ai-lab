#!/usr/bin/env python3
"""Metadata/observation-availability probe only; never forecasts station winds."""
import csv, io, json, math, gzip, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
P=Path(__file__).resolve().parent
H='https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt'
G='https://mesonet.agron.iastate.edu/geojson/network/{}_ASOS.geojson'
I='https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py'
A='https://ftp.nhc.noaa.gov/atcf/archive/{}/a{}.dat.gz'
S='https://noaa-oar-mlwp-data.s3.amazonaws.com/'
NEW={'ETA':'202011090400','ELSA':'202107071430','FRED':'202108161900','HENRI':'202108221520','MINDY':'202109090115','HAROLD':'202308221500','OPHELIA':'202309231015'}
STATES={'ETA':'FL','ELSA':'FL','FRED':'FL','HENRI':'RI,CT,MA','MINDY':'FL','HAROLD':'TX','OPHELIA':'NC,SC,VA'}
def fetch(u,timeout=45):return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'ResearchLab/1.0 metadata feasibility'}),timeout=timeout).read()
def distance(a,b,c,d):
 x=math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(x)))
def coverage(st,t):
 q={'station':st['station'],'vars':'sknt,gust_sknt','sts':(t-timedelta(hours=6)).strftime('%Y-%m-%dT%H:%MZ'),'ets':(t+timedelta(hours=6)).strftime('%Y-%m-%dT%H:%MZ'),'what':'download','tz':'UTC'}
 u=I+'?'+urllib.parse.urlencode(q)
 try:
  rows=list(csv.DictReader(io.StringIO(fetch(u,timeout=85).decode())))
  valid=set()
  for r in rows:
   try:
    if float(r['sknt'])>=0:valid.add(r['valid(UTC)'])
   except (KeyError,ValueError,TypeError):pass
  n=len(valid)
  return {**st,'valid_minutes_landfall_pm6':n,'proxy_90pct':n>=648,'fetch_error':'','source_url':u}
 except Exception as e:return {**st,'valid_minutes_landfall_pm6':'','proxy_90pct':False,'fetch_error':str(e),'source_url':u}
lines=fetch(H).decode().splitlines(); candidates=[]; name=''; sid=''
for line in lines:
 p=[x.strip() for x in line.split(',')]
 if p[0].startswith('AL') and len(p[0])==8:sid,name=p[:2]
 elif name in NEW and len(p)>7 and p[0]+p[1]==NEW[name] and p[2]=='L':
  candidates.append(dict(name=name,sid=sid,t=datetime.strptime(NEW[name],'%Y%m%d%H%M').replace(tzinfo=timezone.utc),lat=float(p[4][:-1]),lon=-float(p[5][:-1]),wind_kt=int(p[6]),status=p[3]))
net={k:json.loads(fetch(G.format(k)))['features'] for k in ('FL','RI','CT','MA','TX','NC','SC','VA')}
result=[]; stations=[]
for e in candidates:
 t=e['t']; init=(t-timedelta(hours=48)).replace(hour=12 if (t-timedelta(hours=48)).hour>=12 else 0,minute=0,second=0,microsecond=0)
 key=f'PANG_v100_GFS/{init.year}/{init:%m%d}/PANG_v100_GFS_{init:%Y%m%d%H}_f000_f240_06.nc'
 u=S+'?'+urllib.parse.urlencode({'list-type':'2','prefix':key,'max-keys':'1'})
 try: obj=int(ET.fromstring(fetch(u)).findtext('{*}KeyCount','0'))>0
 except Exception as ex: obj='ERROR '+str(ex)
 au=A.format(t.year,e['sid'].lower())
 try:
  raw=gzip.decompress(fetch(au)).decode(); arows=[q.split(',') for q in raw.splitlines()]; ofcl=sum(q[4].strip()=='OFCL' and q[2].strip()==init.strftime('%Y%m%d%H') for q in arows if len(q)>5)
 except Exception as ex:ofcl='ERROR '+str(ex)
 pool={}
 for state in STATES[e['name']].split(','):
  for f in net[state]:
   p=f['properties'];lat,lon=f['geometry']['coordinates'][1],f['geometry']['coordinates'][0]
   if distance(lat,lon,e['lat'],e['lon'])>150:continue
   if p.get('attributes',{}).get('HAS1MIN')!='1':continue
   if not (p.get('archive_begin') or '1900')[:10]<=t.date().isoformat()<=(p.get('archive_end') or '2100')[:10]:continue
   pool[p['sid']]={'event':e['name'],'station':p['sid'],'state':state,'distance_km':round(distance(lat,lon,e['lat'],e['lon']),1)}
 result.append({'event':e['name'],'atcf_id':e['sid'],'landfall_utc':t.isoformat(),'lat':e['lat'],'lon':e['lon'],'wind_kt':e['wind_kt'],'init_utc':init.isoformat(),'pangu_object':obj,'pangu_key':key,'ofcl_rows_same_cycle':ofcl,'candidate_has1min_150km':len(pool),'pangu_list_url':u,'adeck_url':au})
 with ThreadPoolExecutor(max_workers=5) as ex:
  fs=[ex.submit(coverage,s,t) for s in pool.values()]
  stations.extend(f.result() for f in as_completed(fs))
for r in result:
 ss=[s for s in stations if s['event']==r['event']]; r['obs_proxy_90pct_pm6']=sum(s['proxy_90pct'] for s in ss);r['obs_fetch_errors']=sum(bool(s['fetch_error']) for s in ss)
for filename,rows in [('v2_new_events_probe.csv',result),('v2_new_station_availability.csv',stations)]:
 with (P/filename).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print(*result,sep='\n')
print('station_rows',len(stations),'fetch_errors',sum(bool(s['fetch_error']) for s in stations))
