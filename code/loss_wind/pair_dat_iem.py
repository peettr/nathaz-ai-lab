#!/usr/bin/env python3
"""Read-only public DAT point / IEM METAR gust feasibility audit. UTC exact-point windows."""
import csv,io,json,math,pathlib,urllib.parse,urllib.request,datetime,collections,time
P=pathlib.Path(__file__).parent
DAT='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/0/query'
IEM='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py'
CASES=[('Ian_2022','hurricane',(-83,25,-79,31),'2022-09-27','2022-10-02','Tropical'),('Ida_2021','hurricane',(-92,28,-88,33),'2021-08-28','2021-08-31','Tropical'),('Dallas_20250304','thunderstorm',(-97.7,32.3,-96.2,33.5),'2025-03-04','2025-03-05','TSTM/Wind'),('Dallas_20190616','thunderstorm',(-97.7,32.3,-96.2,33.5),'2019-06-16','2019-06-17','TSTM/Wind'),('Houston_20240516','thunderstorm',(-96,29,-94.7,30.5),'2024-05-16','2024-05-17','TSTM/Wind')]
def fetch(url,params):
 req=urllib.request.Request(url+'?'+urllib.parse.urlencode(params,doseq=True),headers={'User-Agent':'research-feasibility/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:return r.read()
def km(a,b,c,d):
 p1,p2=math.radians(a),math.radians(c);dp=p2-p1;dl=math.radians(d-b)
 return 12742*math.asin(min(1,math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)))
def dt(s):return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
def network(states):
 out=[]
 for st in states:
  d=json.loads(fetch(f'https://mesonet.agron.iastate.edu/geojson/network/{st}_ASOS.geojson',{}))
  for f in d['features']:
   p=f['properties']; lon,lat=f['geometry']['coordinates'][:2]
   out.append({'id':f['id'],'lat':lat,'lon':lon,'begin':p.get('archive_begin'),'end':p.get('archive_end'),'network':st+'_ASOS'})
 return out
stations=network(['FL','LA','MS','AL','TX'])
(P/'iem_station_metadata_r2.json').write_text(json.dumps(stations,indent=2)+'\n')
allstats=[];pairs=[];record=[]
for name,kind,box,start,end,ef in CASES:
 where=f"stormdate >= TIMESTAMP '{start} 00:00:00' AND stormdate < TIMESTAMP '{end} 00:00:00' AND efscale = '{ef}'"
 base={'f':'json','geometry':','.join(map(str,box)),'geometryType':'esriGeometryEnvelope','spatialRel':'esriSpatialRelIntersects','inSR':4326,'where':where}
 count=json.loads(fetch(DAT,{**base,'returnCountOnly':'true'}))['count'];points=[]
 for offset in range(0,count,1000):
  data=json.loads(fetch(DAT,{**base,'outFields':'objectid,stormdate,windspeed,damage_txt,efscale,event_id,lat,lon,comments','returnGeometry':'false','orderByFields':'objectid','resultOffset':offset,'resultRecordCount':1000}))
  if 'error' in data:raise RuntimeError(data['error'])
  points.extend(x['attributes'] for x in data['features'])
 assert len(points)==count and len({p['objectid'] for p in points})==count,(name,count,len(points))
 (P/f'dat_{name}.json').write_text(json.dumps({'request':base,'count':count,'features':points},ensure_ascii=False)+'\n')
 eligible=[s for s in stations if any(km(p['lat'],p['lon'],s['lat'],s['lon'])<=25 for p in points if p['lat'] is not None and p['lon'] is not None) and (not s['begin'] or s['begin']<=end) and (not s['end'] or s['end']>=start)]
 # Pick spatially eligible sites only, not arbitrary distant stations; 2-day UTC padding.
 d0=datetime.date.fromisoformat(start)-datetime.timedelta(days=1);d1=datetime.date.fromisoformat(end)+datetime.timedelta(days=1)
 obs=[]
 for j in range(0,len(eligible),15):
  chunk=eligible[j:j+15]
  q={'station':[s['id'] for s in chunk],'data':'gust','year1':d0.year,'month1':d0.month,'day1':d0.day,'year2':d1.year,'month2':d1.month,'day2':d1.day,'tz':'Etc/UTC','format':'onlycomma','latlon':'yes','missing':'M','report_type':[3,4]}
  raw=fetch(IEM,q).decode('utf-8-sig',errors='replace');record.append({'case':name,'url':IEM+'?'+urllib.parse.urlencode(q,doseq=True),'rows':len(raw.splitlines())-1})
  obs.extend(dict(x) for x in csv.DictReader(io.StringIO(raw)) if x.get('gust') not in ('M','','None',None))
 (P/f'iem_gust_{name}.csv').write_text('station,valid,lon,lat,gust\n'+''.join(','.join(x.get(k,'') for k in ('station','valid','lon','lat','gust'))+'\n' for x in obs))
 bystation=collections.defaultdict(list)
 for x in obs:
  try:bystation[x['station']].append((dt(x['valid']),float(x['gust'])))
  except (ValueError,TypeError):continue
 stat={'case':name,'kind':kind,'dat_points':count,'dat_windspeed_nonempty':sum(str(x.get('windspeed') or '').strip().lower() not in ('','n/a','na','unknown') for x in points),'candidate_stations_25km':len(eligible),'stations_with_any_gust':len(bystation),'valid_gust_rows':sum(map(len,bystation.values())),'paired_5':0,'paired_10':0,'paired_25':0,'dat_time_midnight':0}
 for p in points:
  lat,lon=p.get('lat'),p.get('lon');t=p.get('stormdate');best=None
  if lat is None or lon is None or t is None:continue
  t=datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc)
  stat['dat_time_midnight']+=t.hour==0 and t.minute==0
  window=datetime.timedelta(hours=12 if kind=='hurricane' else 3)
  for s in eligible:
   dis=km(lat,lon,s['lat'],s['lon'])
   if dis>25:continue
   valid=[(ot,g) for ot,g in bystation[s['id']] if abs(ot-t)<=window]
   if not valid:continue
   obs_time,gust=min(valid,key=lambda v:abs(v[0]-t))
   if best is None or dis<best['distance_km']:best={'distance_km':dis,'station':s['id'],'gust_kt':gust,'observation_utc':obs_time.isoformat()}
  if best:
   for threshold in (5,10,25):stat[f'paired_{threshold}']+=best['distance_km']<=threshold
   pairs.append({'case':name,'objectid':p['objectid'],'dat_utc':t.isoformat(),'efscale':ef,'damage_txt':p.get('damage_txt'),'dat_windspeed_damage_inferred':p.get('windspeed'),'lat':lat,'lon':lon,**best})
 allstats.append(stat);print(stat,flush=True)
(P/'pair_stats_r2.json').write_text(json.dumps({'stats':allstats,'requests':record,'method':'DAT stormdate UTC +/- 3h thunder / +/- 12h hurricane; nearest ASOS/AWOS with nonmissing reported METAR gust within 25 km; classified efscale exactly TSTM/Wind/Tropical'},indent=2)+'\n')
with (P/'dat_iem_pairs_r2.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['case','objectid','dat_utc','efscale','damage_txt','dat_windspeed_damage_inferred','lat','lon','distance_km','station','gust_kt','observation_utc']);w.writeheader();w.writerows(pairs)
