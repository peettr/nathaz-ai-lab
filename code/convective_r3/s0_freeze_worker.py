"""S0 only: verify station identity, freeze event candidates, search paired controls with checkpoints."""
import csv,datetime as dt,gzip,io,json,math,os,pathlib,random,re,tarfile,time
from collections import defaultdict,Counter
from urllib.parse import urlencode
import requests,numpy as np
from PIL import Image
R=pathlib.Path('/content'); OUT=R/'s0_stage';OUT.mkdir(exist_ok=True)
S=requests.Session();S.headers['User-Agent']='University academic StormCast validation'
def save(name,obj):
 p=OUT/name
 if p.exists():
  assert json.load(p.open())==json.loads(json.dumps(obj)),('immutable stage mismatch',name)
  print('MATCHED_EXISTING',name,len(obj),flush=True);return
 with p.open('x') as f:json.dump(obj,f)
 print('SAVED',name,len(obj),flush=True)
def get(url,attempts=4):
 for i in range(attempts):
  try:
   r=S.get(url,timeout=50);r.raise_for_status();return r
  except Exception as e:
   print('HTTP_RETRY',url[:90],i,repr(e),flush=True);time.sleep(2**i)
 raise RuntimeError(url)
def utc(s):return dt.datetime.fromisoformat(s.replace('Z','').replace(' ','T'))
def hav(a,b,c,d):
 a,b,c,d=map(math.radians,(a,b,c,d));h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
 return 12742*math.asin(min(1,math.sqrt(h)))
STATES={'ALABAMA':'AL','ALASKA':'AK','ARIZONA':'AZ','ARKANSAS':'AR','CALIFORNIA':'CA','COLORADO':'CO','CONNECTICUT':'CT','DELAWARE':'DE','FLORIDA':'FL','GEORGIA':'GA','HAWAII':'HI','IDAHO':'ID','ILLINOIS':'IL','INDIANA':'IN','IOWA':'IA','KANSAS':'KS','KENTUCKY':'KY','LOUISIANA':'LA','MAINE':'ME','MARYLAND':'MD','MASSACHUSETTS':'MA','MICHIGAN':'MI','MINNESOTA':'MN','MISSISSIPPI':'MS','MISSOURI':'MO','MONTANA':'MT','NEBRASKA':'NE','NEVADA':'NV','NEW HAMPSHIRE':'NH','NEW JERSEY':'NJ','NEW MEXICO':'NM','NEW YORK':'NY','NORTH CAROLINA':'NC','NORTH DAKOTA':'ND','OHIO':'OH','OKLAHOMA':'OK','OREGON':'OR','PENNSYLVANIA':'PA','RHODE ISLAND':'RI','SOUTH CAROLINA':'SC','SOUTH DAKOTA':'SD','TENNESSEE':'TN','TEXAS':'TX','UTAH':'UT','VERMONT':'VT','VIRGINIA':'VA','WASHINGTON':'WA','WEST VIRGINIA':'WV','WISCONSIN':'WI','WYOMING':'WY','DISTRICT OF COLUMBIA':'DC'}
# IEM ASOS network identity from authoritative network inventory, including archive periods.
rows=json.load(open(R/'s0_all_grid.json'))
states={STATES[r['state'].upper()] for r in rows};net={}
for state in sorted(states):
 url=f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson'
 for f in get(url).json()['features']:
  net[f['id']]=dict(state=state,lat=f['geometry']['coordinates'][1],lon=f['geometry']['coordinates'][0],start=f['properties'].get('archive_begin'),end=f['properties'].get('archive_end'),url=url)
print('STATIONS',len(net),flush=True)
with tarfile.open(R/'s0_prior_inputs.tar.gz') as t:
 seen=set()
 for name in ('events_verified.csv','r2/events_r2_verified.csv','r2/controls_r2_candidates.csv'):
  for x in csv.DictReader(io.TextIOWrapper(t.extractfile(name))):
   date=(x.get('peak_utc') or x.get('utc'))[:10]
   if date:seen.add((x['station'],date))
for x in json.load(open(R/'s0_fit_actual.json')):seen.add((x['station'],x['utc'][:10]))
counts=Counter();unique={}
for x in rows:
 if not x['grid_inside']:counts['grid_out']+=1;continue
 n=net.get(x['station']); day=x['hit']['utc'][:10]
 if not n or n['state']!=STATES[x['state'].upper()] or n['start'] and day<n['start'] or n['end'] and day>n['end']:
  counts['not_asos_network']+=1;continue
 if (x['station'],day) in seen or (x['station'],x['ncei_utc'][:10]) in seen:counts['seen']+=1;continue
 key=(x['station'],day)
 if key not in unique or (-float(x['hit']['kt']),x['hit']['utc'],x['id'])<(-float(unique[key]['hit']['kt']),unique[key]['hit']['utc'],unique[key]['id']):unique[key]=x
byday=defaultdict(list)
for x in unique.values():byday[(x['group'],x['hit']['utc'][:10])].append(x)
elig=[]
for key,group in sorted(byday.items()):
 group.sort(key=lambda x:(-float(x['hit']['kt']),x['hit']['utc'],x['id']))
 elig+=group[:3];counts['day_cap_excluded']+=max(0,len(group)-3)
counts.update({k:sum(x['group']==k for x in elig) for k in ('v1','conus')})
print('ELIGIBLE',dict(counts),flush=True)
save('eligible.json',elig)
# Deterministic within-year proportional stratified draw; all records selected if below caps.
rng=random.Random(20261016);selected=[]
for g,limit in [('v1',120),('conus',80)]:
 group=[x for x in elig if x['group']==g]; strata=defaultdict(list)
 for x in group:strata[x['hit']['utc'][:4]].append(x)
 if len(group)<=limit:selected+=group;continue
 alloc={y:int(limit*len(v)/len(group)) for y,v in strata.items()};rem=limit-sum(alloc.values())
 order=sorted(strata,key=lambda y:(-(limit*len(strata[y])/len(group)-alloc[y]),y))
 for y in order[:rem]:alloc[y]+=1
 for y in sorted(strata):selected+=rng.sample(sorted(strata[y],key=lambda x:x['id']),alloc[y])
save('selected.json',selected)
# NCEI thunderstorm reports full country: all years of selected events incl source versions.
reports=[]
for year in sorted({int(x['hit']['utc'][:4]) for x in selected}):
 src=next(x['ncei_url'] for x in selected if x['hit']['utc'].startswith(str(year)))
 records=csv.DictReader(io.StringIO(gzip.decompress(get(src).content).decode('utf-8-sig')))
 for x in records:
  if x['EVENT_TYPE']!='Thunderstorm Wind':continue
  try:
   raw=dt.datetime.strptime(x['BEGIN_DATE_TIME'],'%d-%b-%y %H:%M:%S');z=int(re.search(r'([+-]\d{1,2})$',x['CZ_TIMEZONE']).group(1));t=raw-dt.timedelta(hours=z)
   reports.append((t.isoformat(),float(x['BEGIN_LAT']),float(x['BEGIN_LON']),x['EVENT_ID'],src))
  except (ValueError,TypeError,AttributeError):continue
print('REPORTS',len(reports),flush=True);save('reports.json',reports)
# Adjacent-state geographic proxy is NOT adequate. Define official Census adjacency table explicitly.
ADJ={'AL':'FL GA MS TN','AK':'','AZ':'CA NV UT NM','AR':'MO TN MS LA TX OK','CA':'OR NV AZ','CO':'WY NE KS OK NM AZ UT','CT':'NY MA RI','DE':'MD PA NJ','FL':'GA AL','GA':'FL AL TN NC SC','HI':'','ID':'WA OR NV UT WY MT','IL':'WI IA MO KY IN','IN':'IL KY OH MI','IA':'MN SD NE MO IL WI','KS':'NE MO OK CO','KY':'IL IN OH WV VA TN MO','LA':'TX AR MS','ME':'NH','MD':'VA WV PA DE DC','MA':'RI CT NY VT NH','MI':'WI IN OH','MN':'ND SD IA WI','MS':'LA AR TN AL','MO':'IA IL KY TN AR OK KS NE','MT':'ID WY SD ND','NE':'SD IA MO KS CO WY','NV':'CA OR ID UT AZ','NH':'ME VT MA','NJ':'NY PA DE','NM':'AZ UT CO OK TX','NY':'PA NJ CT MA VT','NC':'VA TN GA SC','ND':'MT SD MN','OH':'MI IN KY WV PA','OK':'KS MO AR TX NM CO','OR':'WA ID NV CA','PA':'NY NJ DE MD WV OH','RI':'CT MA','SC':'NC GA','SD':'ND MN IA NE WY MT','TN':'KY VA NC GA AL MS AR MO','TX':'NM OK AR LA','UT':'ID WY CO AZ NV','VT':'NY MA NH','VA':'WV MD DC NC TN KY','WA':'OR ID','WV':'OH PA MD VA KY','WI':'MI MN IA IL','WY':'MT SD NE CO UT ID','DC':'MD VA'}
# Network only includes states of eligible events. Add adjacent ASOS stations for pairing.
need=set(STATES[x['state'].upper()] for x in selected)
for st in list(need):need.update(ADJ.get(st,'').split())
for state in sorted(need-set(states)):
 for f in get(f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson').json()['features']:
  net[f['id']]=dict(state=state,lat=f['geometry']['coordinates'][1],lon=f['geometry']['coordinates'][0],start=f['properties'].get('archive_begin'),end=f['properties'].get('archive_end'),url=f'https://mesonet.agron.iastate.edu/geojson/network/{state}_ASOS.geojson')
# Only potential controls with IEM archive valid and within model subgrid. Exact grid edge checked by a grid mask; station must be inside selected cohort footprint.
from earth2studio.data import HRRR
from scipy.spatial import cKDTree
la0,lo0=HRRR.grid();trees={};edge={}
for g,sl in [('v1',(slice(273,785),slice(579,1219))),('conus',(slice(17,1041),slice(3,1795)))]:
 la=la0[sl];lo=lo0[sl];rad=np.deg2rad(np.stack([la.ravel(),lo.ravel()],axis=-1));xyz=np.stack([np.cos(rad[:,0])*np.cos(rad[:,1]),np.cos(rad[:,0])*np.sin(rad[:,1]),np.sin(rad[:,0])],axis=-1)
 trees[g]=(cKDTree(xyz),la.shape);edge[g]=(np.concatenate((la[0,:],la[-1,:],la[1:-1,0],la[1:-1,-1])),np.concatenate((lo[0,:],lo[-1,:],lo[1:-1,0],lo[1:-1,-1])))
def gridok(n,g):
 a,b=map(math.radians,(n['lat'],n['lon']));t,shape=trees[g];d,ix=t.query([math.cos(a)*math.cos(b),math.cos(a)*math.sin(b),math.sin(a)]);j,i=np.unravel_index(ix,shape)
 if j in (0,shape[0]-1) or i in (0,shape[1]-1) or 12742*math.asin(min(1,d/2))>=3:return False
 ela,elo=edge[g]; aa=np.radians(ela);bb=np.radians(elo);h=np.sin((aa-a)/2)**2+np.cos(aa)*math.cos(a)*np.sin((bb-b)/2)**2
 return float((12742*np.arcsin(np.sqrt(np.clip(h,0,1)))).min())>=25
# Avoid repeated grid work; cache station/group eligibility.
gridcache={};used=set();eventdays={x['hit']['utc'][:10] for x in elig};paired=[];unpaired=[];querycache={}
pattern=re.compile(r'\b(?:\+|-)?TS[A-Z]*\b|\bVCTS\b')
def metar(st,day):
 key=(st,day)
 if key in querycache:return querycache[key]
 start=dt.datetime.fromisoformat(day)
 u='https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?'+urlencode(dict(station=st,sts=(start-dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%MZ'),ets=(start+dt.timedelta(days=1,hours=1)).strftime('%Y-%m-%dT%H:%MZ'),tz='UTC',data='gust,peak_wind_gust,peak_wind_time,metar',format='onlycomma',missing='M',report_type='3,4'))
 try:rec=list(csv.DictReader(io.StringIO(get(u).text)))
 except Exception as e:print('METAR_ERR',st,day,repr(e),flush=True);return []
 ans=[]
 for v in rec:
  if not pattern.search(v.get('metar','')):continue
  t=utc(v['valid']);
  if t.date().isoformat()!=day:continue
  window=[r for r in rec if r.get('valid') and abs((utc(r['valid'])-t).total_seconds())<=3600]
  speeds=[]
  for r in window:
   for f,tf in [('gust','valid'),('peak_wind_gust','peak_wind_time')]:
    try:
     speed=float(r[f]);w=utc(r[tf]);
     if abs((w-t).total_seconds())<=3600:speeds.append(speed)
    except (ValueError,TypeError,KeyError):pass
  if speeds and max(speeds)<20/0.514444:
   ans.append(dict(station=st,utc=t.isoformat(),max_kt=max(speeds),metar=v['metar'],iem_url=u))
 querycache[key]=ans;return ans
def radar(n,t):
 lat,lon=n['lat'],n['lon'];pixelx=round((lon+126)/.005);pixely=round((50-lat)/.005)
 base=t.replace(second=0,microsecond=0,minute=t.minute//5*5)
 for off in sorted(range(-30,36,5),key=abs):
  when=base+dt.timedelta(minutes=off)
  if abs((when-t).total_seconds())>1800:continue
  u='https://mesonet.agron.iastate.edu/archive/data/'+when.strftime('%Y/%m/%d')+'/GIS/uscomp/n0q_'+when.strftime('%Y%m%d%H%M')+'.png'
  try:im=Image.open(io.BytesIO(get(u).content))
  except Exception as e:print('RADAR_ERR',repr(e),flush=True);continue
  dy=round(25/111/.005)+2;dx=round(25/(111*math.cos(math.radians(lat)))/.005)+2
  box=(max(0,pixelx-dx),max(0,pixely-dy),min(im.width,pixelx+dx+1),min(im.height,pixely+dy+1));v=np.asarray(im.crop(box));ys,xs=np.where(v>=145)
  for yy,xx in zip(ys,xs):
   if hav(lat,lon,50-(box[1]+int(yy))*.005,-126+(box[0]+int(xx))*.005)<=25:return u
 return None
def no_report(n,t):
 for stamp,lat,lon,eid,src in reports:
  if abs((utc(stamp)-t).total_seconds())<=7200 and hav(n['lat'],n['lon'],lat,lon)<=50:return False
 return True
# Closest calendar dates first; phase 15 then 30, same/adjacent states. Climatic-region fallback is not silently approximated.
for index,x in enumerate(selected,1):
 st=STATES[x['state'].upper()];t=utc(x['hit']['utc']);g=x['group'];options=[]
 for station,n in net.items():
  if n['state'] not in ({st}|set(ADJ.get(st,'').split())):continue
  key=(station,g)
  if key not in gridcache:gridcache[key]=gridok(n,g)
  if gridcache[key]:options.append((station,n))
 found=None
 for bound in (15,30):
  for distance in range(1,bound+1):
   if bound==30 and distance<=15:continue
   choices=[]
   for delta in (-distance,distance):
    day=(t.date()+dt.timedelta(days=delta)).isoformat()
    if day in eventdays:continue
    for station,n in options:
     if n['start'] and day<n['start'] or n['end'] and day>n['end'] or (station,day) in seen or (station,day) in used:continue
     for candidate in metar(station,day):
      if not no_report(n,utc(candidate['utc'])):continue
      url=radar(n,utc(candidate['utc']))
      if url:choices.append(dict(**candidate,lat=n['lat'],lon=n['lon'],state=n['state'],radar_url=url,network_url=n['url'],ncei_url=x['ncei_url'],event_id=x['id'],day_gap=distance,phase=bound))
   if choices:
    found=random.Random(20261016+index).choice(sorted(choices,key=lambda v:(v['station'],v['utc'])));break
  if found:break
 if found:paired.append(found);used.add((found['station'],found['utc'][:10]))
 else:unpaired.append(x['id'])
 if index%5==0:
  print('MATCH',index,len(selected),'paired',len(paired),'unpaired',len(unpaired),'cache',len(querycache),flush=True)
  (OUT/'match_progress.json').write_text(json.dumps(dict(index=index,paired=paired,unpaired=unpaired)))
save('paired.json',paired);save('unpaired.json',unpaired)
(OUT/'S0_DONE').write_text(str(len(selected)))
print('S0_DONE',len(selected),len(paired),len(unpaired),flush=True)
