#!/usr/bin/env python3
"""H2 station audit; never change the event source grids."""
import csv,math,json,io,collections,concurrent.futures,time,urllib.request,urllib.parse
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parent
out=R/'station_clean_h2d.csv'
assert not out.exists(), 'do not overwrite site audit'
rows={}
for p in sorted(R.glob('grid_*_expanded.csv.gz'))+sorted(R.glob('grid_*_h2.csv.gz')):
 import gzip
 with gzip.open(p,'rt') as f:
  for r in csv.DictReader(f):
   key=r['station'] if ':' in r['station'] else 'TX:'+r['station']; lat=float(r['lat']);lon=float(r['lon'])
   if key in rows and (lat,lon)!=(rows[key]['lat'],rows[key]['lon']):raise ValueError((key,p))
   rows[key]={'station':key,'lat':lat,'lon':lon}
print('unique stations',len(rows),flush=True)
with (R/'station_clean_h2c.csv').open() as f:
 previous={r['station']:r for r in csv.DictReader(f)}
# IEM network metadata supplies station name and elevation; no observations redownloaded.
meta={}
for state in sorted({s.split(':')[0] for s in rows}):
 url=f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'
 with urllib.request.urlopen(url,timeout=60) as f: data=json.load(f)
 for item in data['features']:
  meta[f"{state}:{item['id']}"]=item['properties']
 print('metadata',state,len(data['features']),flush=True)
for k,v in rows.items():
 props=meta.get(k,{})
 v['name']=props.get('sname','') or ''
 v['elevation_m']=props.get('elevation','') or ''
# Exact ESA 2021 WorldCover 1km modal class, shared method with r1 addendum.
URL='https://planetarycomputer.microsoft.com/api/data/v1/item/crop.tif'
VALID={10,20,30,40,50,60,70,80,90,95,100}
def cover(v):
 import requests
 lat=v['lat'];lon=v['lon'];dlat=1/111.195;dlon=dlat/math.cos(math.radians(lat));xmin,xmax=lon-dlon,lon+dlon;ymin,ymax=lat-dlat,lat+dlat
 south=math.floor(lat/3)*3;west=math.floor(lon/3)*3
 item=f'ESA_WorldCover_10m_2021_v200_N{south:02d}W{-west:03d}'
 geom={'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[xmin,ymin],[xmax,ymin],[xmax,ymax],[xmin,ymax],[xmin,ymin]]]},'properties':{}}
 for retry in range(3):
  try:
   response=requests.post(URL,params={'collection':'esa-worldcover','item':item,'assets':'map','max_size':256,'dst_crs':'EPSG:4326'},json=geom,timeout=90);response.raise_for_status()
   im=Image.open(io.BytesIO(response.content));im.load();break
  except Exception:
   if retry==2:return ('',0,item,'request_failure')
   time.sleep(2*(retry+1))
 counts=collections.Counter();w,h=im.size;pix=im.load()
 for j in range(h):
  plat=ymax-(j+.5)*(ymax-ymin)/h
  for i in range(w):
   plon=xmin+(i+.5)*(xmax-xmin)/w
   if ((plat-lat)/dlat)**2+((plon-lon)/dlon)**2>1:continue
   x=pix[i,j];x=x[0] if isinstance(x,tuple) else x
   if x in VALID:counts[x]+=1
 n=sum(counts.values());return ((counts.most_common(1)[0][0] if n>=100 else ''),n,item,'')
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
 for i,(key,result) in enumerate(zip(rows,ex.map(lambda v: tuple(previous[v['station']][k] for k in ('worldcover_class','valid_pixels','worldcover_item','cover_error')) if v['station'] in previous else cover(v),rows.values()))):
  rows[key].update(zip(('worldcover_class','valid_pixels','worldcover_item','cover_error'),result))
  if i%100==0:print('WorldCover',i+1,'/',len(rows),flush=True)
def km(a,b):
 p1,p2=map(math.radians,(a['lat'],b['lat']));dl=math.radians(a['lon']-b['lon']);h=math.sin((p1-p2)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
 return 12742*math.asin(min(1,math.sqrt(h)))
# Global pair checks across all events, not just stations with valid METAR.
keys=sorted(rows);parents={k:k for k in keys};pairs=[]
def root(k):
 while parents[k]!=k:k=parents[k]
 return k
for i,a in enumerate(keys):
 for b in keys[i+1:]:
  if abs(rows[a]['lat']-rows[b]['lat'])>.019 or abs(rows[a]['lon']-rows[b]['lon'])>.023:continue
  d=km(rows[a],rows[b]);
  if d<2:
   pairs.append((a,b,d));parents[root(b)]=root(a)
# First separate land and platform; water/explicit offshore markers never enter land pool.
platform_terms=('platform','oil rig','offshore','lightship','light station','brazos 451','west cameron','east cameron','south marsh island','ship shoal','grand isle block','galveston 424')
for k,v in rows.items():
 name=v['name'].lower();e=v['elevation_m']
 v['platform_reason']='WorldCover 1km water' if str(v['worldcover_class'])=='80' else ('name indicates offshore platform' if any(t in name for t in platform_terms) else '')
 v['status']='platform' if v['platform_reason'] else ('unknown_cover' if v['worldcover_class']=='' else 'land')
 v['reason']=v['platform_reason']
 if k=='TX:T89':
  v['status']='excluded_suspicious';v['reason']='same coordinates as TX:CVB; suspect T89 geocode (review 2598bcfe)'
# Duplicate component: retain station with most finite observed wind hours, tie lexically.
counts=collections.Counter()
for p in sorted(R.glob('grid_*_expanded.csv.gz'))+sorted(R.glob('grid_*_h2.csv.gz')):
 import gzip
 with gzip.open(p,'rt') as f:
  for r in csv.DictReader(f):
   try:
    key=r['station'] if ':' in r['station'] else 'TX:'+r['station']
    if math.isfinite(float(r['obs'])):counts[key]+=1
   except (ValueError,TypeError):pass
components=collections.defaultdict(list)
for k in keys:components[root(k)].append(k)
for component in components.values():
 if len(component)<2:continue
 # Separate platform and land so offshore is never artificially merged with land.
 for group in ('land','platform','unknown_cover'):
  members=[k for k in component if rows[k]['status']==group]
  if len(members)<2:continue
  kept=sorted(members,key=lambda k:(-counts[k],k))[0]
  for k in members:
   if k!=kept:
    rows[k]['status']='excluded_duplicate';rows[k]['reason']='within 2 km, retain '+kept+' (more observed hours; tie lexical)'
for k,v in rows.items():v['valid_hours_all_events']=counts[k]
with out.open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(next(iter(rows.values())).keys()));w.writeheader();w.writerows(rows.values())
with (R/'near_pairs_h2d.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(('a','b','distance_km'));w.writerows(pairs)
print('status',dict(collections.Counter(v['status'] for v in rows.values())),'pairs',len(pairs),'output',out,flush=True)
print('platform',[(k,v['name']) for k,v in rows.items() if v['status']=='platform'],flush=True)
print('excluded',[(k,v['reason']) for k,v in rows.items() if v['status']=='excluded_duplicate'],flush=True)
