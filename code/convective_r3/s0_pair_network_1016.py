"""S0 remote CPU worker: exact protocol pairing, state-network date caches, resumable."""
import csv,datetime as dt,io,json,math,os,pathlib,random,re,time,collections,concurrent.futures,bisect,threading
from urllib.parse import urlencode
import requests,numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from earth2studio.data import HRRR
R=pathlib.Path('/content'); O=R/'s0_pair_1016';O.mkdir(exist_ok=True)
selected=json.loads((R/'s0_selected_provisional_1016.json').read_text()); eligible=json.loads((R/'s0_eligible_1016.json').read_text()); reports=json.loads((R/'s0_ncei_reports_1016.json').read_text())
STATES={'ALABAMA':'AL','ALASKA':'AK','ARIZONA':'AZ','ARKANSAS':'AR','CALIFORNIA':'CA','COLORADO':'CO','CONNECTICUT':'CT','DELAWARE':'DE','FLORIDA':'FL','GEORGIA':'GA','HAWAII':'HI','IDAHO':'ID','ILLINOIS':'IL','INDIANA':'IN','IOWA':'IA','KANSAS':'KS','KENTUCKY':'KY','LOUISIANA':'LA','MAINE':'ME','MARYLAND':'MD','MASSACHUSETTS':'MA','MICHIGAN':'MI','MINNESOTA':'MN','MISSISSIPPI':'MS','MISSOURI':'MO','MONTANA':'MT','NEBRASKA':'NE','NEVADA':'NV','NEW HAMPSHIRE':'NH','NEW JERSEY':'NJ','NEW MEXICO':'NM','NEW YORK':'NY','NORTH CAROLINA':'NC','NORTH DAKOTA':'ND','OHIO':'OH','OKLAHOMA':'OK','OREGON':'OR','PENNSYLVANIA':'PA','RHODE ISLAND':'RI','SOUTH CAROLINA':'SC','SOUTH DAKOTA':'SD','TENNESSEE':'TN','TEXAS':'TX','UTAH':'UT','VERMONT':'VT','VIRGINIA':'VA','WASHINGTON':'WA','WEST VIRGINIA':'WV','WISCONSIN':'WI','WYOMING':'WY','DISTRICT OF COLUMBIA':'DC'}
ADJ={'AL':'FL GA MS TN','AK':'','AZ':'CA NV UT NM','AR':'MO TN MS LA TX OK','CA':'OR NV AZ','CO':'WY NE KS OK NM AZ UT','CT':'NY MA RI','DE':'MD PA NJ','FL':'GA AL','GA':'FL AL TN NC SC','HI':'','ID':'WA OR NV UT WY MT','IL':'WI IA MO KY IN','IN':'IL KY OH MI','IA':'MN SD NE MO IL WI','KS':'NE MO OK CO','KY':'IL IN OH WV VA TN MO','LA':'TX AR MS','ME':'NH','MD':'VA WV PA DE DC','MA':'RI CT NY VT NH','MI':'WI IN OH','MN':'ND SD IA WI','MS':'LA AR TN AL','MO':'IA IL KY TN AR OK KS NE','MT':'ID WY SD ND','NE':'SD IA MO KS CO WY','NV':'CA OR ID UT AZ','NH':'ME VT MA','NJ':'NY PA DE','NM':'AZ UT CO OK TX','NY':'PA NJ CT MA VT','NC':'VA TN GA SC','ND':'MT SD MN','OH':'MI IN KY WV PA','OK':'KS MO AR TX NM CO','OR':'WA ID NV CA','PA':'NY NJ DE MD WV OH','RI':'CT MA','SC':'NC GA','SD':'ND MN IA NE WY MT','TN':'KY VA NC GA AL MS AR MO','TX':'NM OK AR LA','UT':'ID WY CO AZ NV','VT':'NY MA NH','VA':'WV MD DC NC TN KY','WA':'OR ID','WV':'OH PA MD VA KY','WI':'MI MN IA IL','WY':'MT SD NE CO UT ID','DC':'MD VA'}
def utc(s):return dt.datetime.fromisoformat(s.replace('Z','').replace(' ','T'))
def hav(a,b,c,d):
 a,b,c,d=map(math.radians,(a,b,c,d));h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(h)))
lock=threading.Lock(); sess=requests.Session();sess.headers.update({'User-Agent':'academic StormCast validation (contact via IEM)', 'Accept-Encoding':'gzip, deflate'})
def get(u):
 for i in range(5):
  try:
   r=sess.get(u,timeout=65);r.raise_for_status();return r
  except Exception as e:
   print('RETRY',i,repr(e),u[:100],flush=True);time.sleep(min(40,2**i))
 raise RuntimeError('HTTP_FAIL '+u)
# Network station inventory, exact HRRR grid slice and 25 km edge test.
need={STATES[x['state'].upper()] for x in selected}; need|={v for st in list(need) for v in ADJ[st].split()}
net={};stnets={}
for st in sorted(need):
 url=f'https://mesonet.agron.iastate.edu/geojson/network/{st}_ASOS.geojson';features=get(url).json()['features'];stnets[st]=[]
 for f in features:
  n=dict(station=f['id'],state=st,lat=f['geometry']['coordinates'][1],lon=f['geometry']['coordinates'][0],start=f['properties'].get('archive_begin'),end=f['properties'].get('archive_end'),network_url=url)
  net[(st,n['station'])]=n;stnets[st].append(n)
la0,lo0=HRRR.grid();trees={};edges={}
for g,sl in [('v1',(slice(273,785),slice(579,1219))),('conus',(slice(17,1041),slice(3,1795)))]:
 la=la0[sl];lo=lo0[sl];rad=np.deg2rad(np.stack([la.ravel(),lo.ravel()],axis=-1));xyz=np.stack([np.cos(rad[:,0])*np.cos(rad[:,1]),np.cos(rad[:,0])*np.sin(rad[:,1]),np.sin(rad[:,0])],axis=-1)
 trees[g]=(cKDTree(xyz),la.shape);edges[g]=(np.concatenate((la[0,:],la[-1,:],la[1:-1,0],la[1:-1,-1])),np.concatenate((lo[0,:],lo[-1,:],lo[1:-1,0],lo[1:-1,-1])))
del la0,lo0,la,lo,rad,xyz
def gridok(n,g):
 a,b=map(math.radians,(n['lat'],n['lon']));d,ix=trees[g][0].query([math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)]);shape=trees[g][1];j,i=np.unravel_index(ix,shape)
 if j in (0,shape[0]-1) or i in (0,shape[1]-1) or 12742*math.asin(min(1,d/2))>=3:return False
 ela,elo=edges[g];aa=np.radians(ela);bb=np.radians(elo);h=np.sin((aa-a)/2)**2+np.cos(aa)*math.cos(a)*np.sin((bb-b)/2)**2
 return float((12742*np.arcsin(np.sqrt(np.clip(h,0,1)))).min())>=25
valid={(st,g):{n['station'] for n in stnets[st] if gridok(n,g)} for st in sorted(need) for g in ('v1','conus')}
palette=np.asarray(Image.open(io.BytesIO(get('https://mesonet.agron.iastate.edu/archive/data/2022/05/11/GIS/uscomp/n0q_202205110535.png').content)).getpalette()).reshape(256,3)
radar_high={tuple(c) for c in palette[145:]};radar_low={tuple(c) for c in palette[:145]};assert not (radar_high & radar_low)
print('GRID STATIONS',sum(map(len,valid.values())),flush=True)
# Index reports by UTC date for finite 2h window, all types Thunderstorm Wind.
reportday=collections.defaultdict(list)
for stamp,lat,lon,eid,src in reports:reportday[stamp[:10]].append((utc(stamp),lat,lon,eid,src))
def nearreport(n,t):
 for day in (t.date()-dt.timedelta(days=1),t.date(),t.date()+dt.timedelta(days=1)):
  for z,lat,lon,eid,src in reportday[day.isoformat()]:
   if abs((z-t).total_seconds())<=7200 and hav(n['lat'],n['lon'],lat,lon)<=50:return eid
 return None
pattern=re.compile(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b')
eventdays={x['hit']['utc'][:10] for x in eligible};used=set();paired=[];unpaired=[];queries=collections.Counter();radarcache={}
checkpoint=O/'progress.json';
if checkpoint.exists():
 p=json.loads(checkpoint.read_text());paired=p['paired'];unpaired=p['unpaired'];used={(x['station'],x['utc'][:10]) for x in paired};start=p['index'];print('RESUME',start,len(paired),flush=True)
else:start=0
# State network fetch for UTC day plus 1h each side, complete time windows; on disk small TS-window subset only.
def metarday(st,day):
 path=O/f'metar_{st}_{day}.json'
 if path.exists():return json.loads(path.read_text())
 t=dt.datetime.fromisoformat(day);u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urlencode(dict(network=f'{st}_ASOS',sts=(t-dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(t+dt.timedelta(days=1,hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',data='gust,peak_wind_gust,peak_wind_time,metar',format='onlycomma',missing='M',report_type='3,4'))
 rows=list(csv.DictReader(io.StringIO(get(u).text)));by=collections.defaultdict(list)
 for r in rows:
  if r.get('valid') and r['station'] in valid[(st,'v1')]|valid[(st,'conus')]:by[r['station']].append(r)
 out=[]
 for station,rr in by.items():
  for r in rr:
   if not pattern.search(r.get('metar') or ''):continue
   t0=utc(r['valid']);
   if t0.date().isoformat()!=day:continue
   window=[v for v in rr if abs((utc(v['valid'])-t0).total_seconds())<=3600]
   speeds=[]
   for v in window:
    for key,tk in [('gust','valid'),('peak_wind_gust','peak_wind_time')]:
     try:
      w=utc(v[tk]);speed=float(v[key]);
      if abs((w-t0).total_seconds())<=3600:speeds.append(speed)
     except (ValueError,TypeError,KeyError):pass
   if speeds and max(speeds)<20/.514444:
    out.append(dict(station=station,utc=t0.isoformat(),max_kt=max(speeds),metar=r['metar'],iem_url=u))
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(out));tmp.replace(path);queries['download']+=1
 return out
# IEM WMS-T crops the SAME n0q raster/palette; validated on 2022-05-11 05:35
# against archived source PNG at native 0.005 degree resolution: all 12800 RGB
# pixels exact, 40 dBZ classification agreement 1.0. Return original raster URL.
def radar(n,t):
 lat,lon=n['lat'],n['lon'];base=t.replace(second=0,microsecond=0,minute=t.minute//5*5)
 for off in sorted(range(-30,36,5),key=abs):
  when=base+dt.timedelta(minutes=off)
  if abs((when-t).total_seconds())>1800:continue
  u='https://mesonet.agron.iastate.edu/archive/data/'+when.strftime('%Y/%m/%d')+'/GIS/uscomp/n0q_'+when.strftime('%Y%m%d%H%M')+'.png'
  dy=25/111+.012;dx=25/(111*math.cos(math.radians(lat)))+.012;box=(lon-dx,lat-dy,lon+dx,lat+dy);width=round(2*dx/.005);height=round(2*dy/.005)
  params=dict(service='WMS',version='1.1.1',request='GetMap',layers='nexrad-n0q-wmst',styles='',srs='EPSG:4326',bbox=','.join(map(str,box)),width=width,height=height,format='image/png',transparent='true',time=when.strftime('%Y-%m-%dT%H:%M:00Z'))
  wms='https://mesonet.agron.iastate.edu/cgi-bin/wms/nexrad/n0q-t.cgi?'+urlencode(params)
  response=get(wms);assert response.headers.get('Content-Type','').startswith('image/png'),(wms,response.text[:200])
  image=np.asarray(Image.open(io.BytesIO(response.content)).convert('RGB'));colors=np.unique(image.reshape(-1,3),axis=0)
  assert all(tuple(c) in radar_high or tuple(c) in radar_low for c in colors),('unknown WMS color',wms)
  mask=np.zeros(image.shape[:2],bool)
  for c in colors:
   if tuple(c) in radar_high:mask|=np.all(image==c,axis=2)
  ys,xs=np.where(mask);queries['radar']+=1
  if len(xs):
   yy=np.radians(box[3]-(ys+.5)*(box[3]-box[1])/height);xx=np.radians(box[0]+(xs+.5)*(box[2]-box[0])/width)
   a,b=map(math.radians,(lat,lon));h=np.sin((yy-a)/2)**2+math.cos(a)*np.cos(yy)*np.sin((xx-b)/2)**2
   if np.any(12742*np.arcsin(np.sqrt(np.clip(h,0,1)))<=25):return u
 return None
# For each gap, query entire state network for both dates; all equal-distance valid pairs enumerated before seeded tie-break.
for index in range(start,len(selected)):
 x=selected[index];g=x['group'];st=STATES[x['state'].upper()];t=utc(x['hit']['utc']); states=sorted({st}|set(ADJ[st].split()));found=None;phase=0
 for bound in (15,30):
  for distance in range(1 if bound==15 else 16,bound+1):
   days=[(t.date()+dt.timedelta(days=d)).isoformat() for d in (-distance,distance)];jobs=[(s,day) for day in days if day not in eventdays for s in states if valid[(s,g)]]
   if not jobs:continue
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda pair:(pair,metarday(*pair)),jobs))
   precandidates={}
   for (s,day),cand in results:
    for c in cand:
     if c['station'] not in valid[(s,g)] or (c['station'],day) in used:continue
     n=net[(s,c['station'])]
     if n['start'] and day<n['start'] or n['end'] and day>n['end']:continue
     z=utc(c['utc']);
     if nearreport(n,z):continue
     key=(s,c['station'],day)
     precandidates.setdefault(key,[]).append((n,c))
   def radar_choice(group):
    for n,c in sorted(group,key=lambda v:(-v[1]['max_kt'],v[1]['utc'])):
     u=radar(n,utc(c['utc']))
     if u:return dict(**c,lat=n['lat'],lon=n['lon'],state=n['state'],radar_url=u,network_url=n['network_url'],ncei_url=x['ncei_url'],ncei_exclusion='all Thunderstorm Wind 50 km +/-2 h',event_id=x['id'],day_gap=distance,phase=bound)
   with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:choices=[v for v in pool.map(radar_choice,precandidates.values()) if v]
   if choices:
    found=random.Random(20261016+index+1).choice(sorted(choices,key=lambda v:(v['station'],v['utc'],v['state'])));phase=bound;break
  if found:break
 if found:paired.append(found);used.add((found['station'],found['utc'][:10]))
 else:unpaired.append(x['id']);print('UNPAIRED_NEEDS_CLIMATE_FALLBACK',index+1,x['id'],flush=True)
 print('EVENT_DONE',index+1,'paired',bool(found),'gap',found['day_gap'] if found else None,flush=True)
 if (index+1)%1==0 or index+1==len(selected):
  tmp=checkpoint.with_suffix('.tmp');tmp.write_text(json.dumps(dict(index=index+1,paired=paired,unpaired=unpaired,queries=dict(queries),utc=dt.datetime.utcnow().isoformat())));tmp.replace(checkpoint)
  print('CHECKPOINT',index+1,'paired',len(paired),'unpaired',len(unpaired),'requests',dict(queries),flush=True)
(O/'DONE').write_text(json.dumps({'index':len(selected),'paired':len(paired),'unpaired':len(unpaired),'queries':dict(queries)}))
print('DONE',len(paired),len(unpaired),flush=True)
