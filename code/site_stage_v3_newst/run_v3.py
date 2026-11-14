"""L31.9c A371 v2 frozen implementation. Run on Colab CPU only.
Stages: map, admission, count, era, score. ERA/score require Lead's later authorization.
No new-site ERA wind is accessed by map/admission/count.
"""
import csv, json, os, sys, re, io, math, time, gzip, hashlib, datetime as dt, urllib.request, urllib.parse, traceback
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
ROOT=Path(os.environ.get('V3_ROOT','/content/v3')); ROOT.mkdir(exist_ok=True)
os.environ['SITE_STAGE_ROOT']=str(ROOT)
sys.path.insert(0,'/content/v3')
import run_colab as core
PL='KFOD KMCW KSPW KOTM KBRL KCID KOFK KHSI KEAR KMCK KOLU KGLD KHYS KSLN KEMP KCNU KMHK KGCK KHUT KSTJ KJLN KUIN KDEC KCMI KRFD KMSN KLSE KEAU KSTC KAXN KMHE KPIR KATY KRAP KJMS KGFK KDIK KSWO KGAG KIRK'.split()
OT='KLAF KFWA KSBN KEVV KBMG KHUF KDAY KTOL KMFD KCAK KYNG KLEX KBWG KTYS KCHA KTRI KHTS KBKW KCKB KROA KLYH KRIC KCHO KAVP KABE KIPT KBGM KELM KBTV KCON KORH KAVL KINT KCAE KAGS KMCN KCSG KMGM KHSV KMSL KTUP KGWO KMLU KTXK KTYR'.split()
ALL=PL+OT
assert len(ALL)==85 and len(set(ALL))==85
BASE=Path('/content/v3/build'); PA=BASE/'station_params.csv'; Q=BASE/'qc_station_seasons.jsonl'; E=BASE/'era_seasons.jsonl'
UTC=dt.timezone.utc; EST=dt.timezone(dt.timedelta(hours=-5))
def now():return dt.datetime.now(EST).isoformat(timespec='seconds')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def savej(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def savecsv(p,rows):
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def stage(s):
 with (ROOT/'stages.jsonl').open('a') as f:f.write(json.dumps({'stage':s,'at':now()})+'\n')
def fetch(url):
 for k in range(4):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PETW-A371-newstation/1.0'}),timeout=120) as r:return r.read()
  except Exception:
   if k==3:raise
   time.sleep(3*(k+1))
def fit(x,y):
 return [float(z) for z in np.linalg.lstsq(np.column_stack((np.ones(len(x)),x)),y,rcond=None)[0]]
def moments(a):
 a=np.asarray(a,dtype=float);return float(a.mean()),float(a.std(ddof=0))
def map_stage():
 assert not (ROOT/'map_frozen.json').exists()
 params={r['station']:r for r in csv.DictReader(PA.open())};q={(r['station'],int(r['season_year'])):r for r in lines(Q)}
 era={int(r['season_year']):r['stations'] for r in lines(E)}
 assert len(params)==29
 X=[];Y=[];station_rows=[]
 for st,r in sorted(params.items()):
  years=[int(z) for z in json.loads(r['seasons'])];obs=[];ev=[]
  for y in years:
   z=q[st,y];assert z['valid'] and z['qc_peak'] is not None,(st,y)
   obs.append(float(z['qc_peak']['kn']));ev.append(float(era[y][st]['ace1_max_mps']))
  m,s=moments(obs);em,es=moments(ev);beta=s*np.sqrt(6)/np.pi;ebeta=es*np.sqrt(6)/np.pi
  checks={k:float(actual)-float(r[k]) for k,actual in [('station_mu_kn',m),('station_beta_kn',beta),('era_mu_mps',em),('era_beta_mps',ebeta)]}
  if any(abs(v)>1e-6 for v in checks.values()):raise ValueError(('MAP_FIELD_MISMATCH',st,checks))
  station_rows.append({'station':st,'n':len(years),'years':years,'m':m,'s':s,'CV':s/m,'era_m':em,'era_s':es,'checks':checks})
 mco=fit(np.array([v['era_m'] for v in station_rows]),np.array([v['m'] for v in station_rows]))
 sco=fit(np.array([v['era_s'] for v in station_rows]),np.array([v['s'] for v in station_rows]))
 savej(ROOT/'map_frozen.json',{'generated_est':now(),'inputs_sha256':{p.name:digest(p) for p in (PA,Q,E)},'field_tolerance':1e-6,'max_abs_field_difference':max(abs(d) for v in station_rows for d in v['checks'].values()),'build_stations':station_rows,'a_m':mco[0],'c_m':mco[1],'a_s':sco[0],'c_s':sco[1],'m0':float(np.mean([v['m'] for v in station_rows])),'CV0':float(np.mean([v['CV'] for v in station_rows]))})
 stage('1 map_frozen');print('MAP_OK',len(station_rows),flush=True)
def homr(st):
 url=f'https://www.ncei.noaa.gov/access/homr/services/station/search?qid=ICAO%3A{st}&date=all&definitions=false'
 stations=json.loads(fetch(url))['stationCollection']['stations']
 # An ICAO station with no WIND records is a documented instrument failure,
 # not an ambiguous station lookup. Keep its location and fail gate (a).
 primary=[s for s in stations if any(i.get('idType')=='ICAO' and i.get('id')==st and i.get('date',{}).get('endDate')=='Present' for i in s.get('identifiers',[]))]
 if len(primary)>1:
  with_wind=[s for s in primary if any(e.get('element')=='WIND' for e in s.get('elements',[]))]
  if len(with_wind)==1:primary=with_wind
 if len(primary)!=1:raise ValueError(('ambiguous_homr',st,len(primary)))
 s=primary[0];loc=s.get('location',{});g=loc.get('geoInfo',{})
 def first(key,field):return loc[key][0][field]
 d={'station':st,'homr_url':url,'homr_id':s.get('ncdcStnId'),'lat':float(first('latitudes','latitude_dec')),'lon':float(first('longitudes','longitude_dec')),'elev_m':float(first('elevations','elevationMeters')),'county':g['counties'][0]['county'],'state':g['stateProvinces'][0]['stateProvince']}
 a=dt.date(2007,10,1);b=dt.date(2022,4,1)
 ints=[]
 for e in s.get('elements',[]):
  if e.get('element')!='WIND':continue
  date=e['date'];lo=dt.date.fromisoformat(date['beginDate'][:10]);en=date['endDate'];hi=dt.date(9999,12,31) if en=='Present' else dt.date.fromisoformat(en[:10]);ints.append((lo,hi,e['equipment']['equipment']))
 boundaries={a,b}
 for lo,hi,eq in ints:
  if a<lo<b:boundaries.add(lo)
  if a<hi<b:boundaries.add(hi)
 edges=sorted(boundaries);segments=[(str(x),sorted({eq for lo,hi,eq in ints if lo<=x and hi>=y})) for x,y in zip(edges,edges[1:])]
 d['instrument_ok']=all(eq==['ANEMSONIC'] for _,eq in segments)
 d['wind_segments']=segments;d['relocation_ok']=not any(a<=dt.date.fromisoformat(str(z['date'])[:10])<b for z in s.get('relocations',[]))
 d['elevation_ok']=d['elev_m']<=1000
 d['region']='plains' if 35<=d['lat']<=48 and -105<=d['lon']<=-88 else 'other'
 return d
def geography(meta):
 import geopandas as gpd
 from shapely.geometry import Point
 from shapely.ops import transform
 from pyproj import Transformer,CRS
 import zipfile
 def data(name):
  p=ROOT/(name+'.zip')
  if not p.exists():p.write_bytes(fetch(f'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_{name}.zip'))
  with zipfile.ZipFile(p) as f:f.extractall(ROOT/name)
  return gpd.read_file(ROOT/name/('ne_10m_'+name+'.shp'))
 coast=data('coastline');lakes=data('lakes');great=lakes[lakes['name'].astype(str).str.upper().str.contains('SUPERIOR|MICHIGAN|HURON|ERIE|ONTARIO|ST. CLAIR')]
 for r in meta:
  lat,lon=r['lat'],r['lon'];tr=Transformer.from_crs('EPSG:4326',CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs'),always_xy=True).transform
  w=coast.cx[lon-.6:lon+.6,lat-.6:lat+.6];w2=great.cx[lon-.3:lon+.3,lat-.3:lat+.3]
  r['coast_km']=min((transform(tr,g).distance(Point(0,0)) for g in w.geometry),default=1e8)/1000
  r['great_lake_km']=min((transform(tr,g.boundary).distance(Point(0,0)) for g in w2.geometry),default=1e8)/1000
  r['geog_ok']=r['coast_km']>=10 and r['great_lake_km']>=5
 return meta
def land(meta):
 import xarray as xr
 u='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
 s=xr.open_zarr(u,storage_options={'token':'anon'},consolidated=True);v=s['land_sea_mask']
 if 'time' in v.dims:v=v.isel(time=0)
 lat=np.asarray(s.latitude.values);lon=np.asarray(s.longitude.values)
 if lat[0]>lat[-1]:lat=lat[::-1];v=v.isel(latitude=slice(None,None,-1))
 mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])));mlon=np.arange(360)+.5
 def edge(x,clip=False):
  e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
  if clip:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
  return e
 sy=edge(lat,True);sx=edge(lon);ty=edge(mlat,True);tx=edge(mlon)
 for r in meta:
  iy=int(np.argmin(abs(mlat-r['lat'])));jx=int(np.argmin(abs(((mlon-r['lon'])+180)%360-180)))
  i0=max(0,np.searchsorted(sy,ty[iy])-1);i1=min(len(lat),np.searchsorted(sy,ty[iy+1])+1);j0=max(0,np.searchsorted(sx,tx[jx])-1);j1=min(len(lon),np.searchsorted(sx,tx[jx+1])+1)
  yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[iy+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[iy]))));xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[jx+1])-np.maximum(sx[j0:j1],tx[jx]))
  w=yy[:,None]*xx[None,:];block=v.isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).values
  r.update(ace_lat=float(mlat[iy]),ace_lon=float(mlon[jx]),ace_iy=iy,ace_ix=jx,land_fraction=float(np.sum(block*w)/w.sum()))
  r['land_ok']=r['land_fraction']>=.5
 return meta
def setup_events(meta):
 core.ALL=[r['station'] for r in meta];core.CO={r['station']:(r['county'].upper(),{'MN':'MINNESOTA','ND':'NORTH DAKOTA','SD':'SOUTH DAKOTA','IA':'IOWA','NE':'NEBRASKA','KS':'KANSAS','MO':'MISSOURI','OK':'OKLAHOMA','IL':'ILLINOIS','NY':'NEW YORK','OH':'OHIO','MI':'MICHIGAN','PA':'PENNSYLVANIA','IN':'INDIANA','KY':'KENTUCKY','TN':'TENNESSEE','WV':'WEST VIRGINIA','VA':'VIRGINIA','NC':'NORTH CAROLINA','SC':'SOUTH CAROLINA','GA':'GEORGIA','AL':'ALABAMA','MS':'MISSISSIPPI','AR':'ARKANSAS','LA':'LOUISIANA','TX':'TEXAS','CT':'CONNECTICUT','WI':'WISCONSIN'}.get(r['state'],r['state'])) for r in meta};core.COORD={r['station']:(r['lat'],r['lon']) for r in meta}
 storm=core.storm_data();tracks=core.tracks();se=defaultdict(list);tr=defaultdict(list)
 for v in storm:se[v['station']].append(v)
 for v in tracks:tr[int(v['time'][:4])].append(v)
 return se,tr
def isd_ids():
 rows=list(csv.DictReader(io.StringIO(fetch('https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv').decode('utf-8-sig'))));out=defaultdict(list)
 for r in rows:
  st=r.get('ICAO','').strip()
  if st in ALL and r.get('USAF')!='999999' and r.get('WBAN')!='99999':out[st].append((r['USAF']+r['WBAN'],r.get('END','')))
 return out
WIND_RE=re.compile(r'\b(?:\d{3}|VRB)(\d{2,3})G(\d{2,3})KT\b');SUST_RE=re.compile(r'\b(?:\d{3}|VRB)(\d{2,3})(?:G\d{2,3})?KT\b');PK_RE=re.compile(r'\bPK\s+WND\s+\d{3}(\d{2,3})/(\d{4})\b')
def raw_wind(raw,src):
 m=(PK_RE if src=='pk' else WIND_RE).search((raw or '').upper());return int(m.group(1 if src=='pk' else 2)) if m else None
def sust(raw):
 m=SUST_RE.search((raw or '').upper());return int(m.group(1)) if m else None
def isd(st,c,ids,cache):
 day=c['time'].strftime('%Y-%m-%d');key=(st,day)
 if key not in cache:
  ident=sorted(ids[st],key=lambda a:a[1],reverse=True)[0][0]
  url='https://www.ncei.noaa.gov/access/services/data/v1?'+urllib.parse.urlencode({'dataset':'global-hourly','stations':ident,'startDate':day,'endDate':day,'format':'json','includeAttributes':'true'})
  raw=fetch(url);cache[key]=(json.loads(raw),url,raw)
 rows,url,raw=cache[key];matched=[]
 if c['source']=='pk':
  for r in rows:
   rt=core.parse(r.get('DATE',''))
   if not rt or not 0<=(rt-c['time']).total_seconds()<=5400:continue
   for m in PK_RE.finditer(r.get('REM','')):
    hh,mm=int(m.group(2)[:2]),int(m.group(2)[2:]);et=rt.replace(hour=hh,minute=mm)
    if (et-rt).total_seconds()>0:et-=dt.timedelta(days=1)
    if abs((et-c['time']).total_seconds())<=600:matched.append((abs((et-c['time']).total_seconds()),r,float(m.group(1))))
  if not matched:return 'ISD 未核',c['value'],None,url
  _,r,v=min(matched,key=lambda z:z[0]);info={'isd_time':r['DATE'],'REM_PK_WND':v}
 else:
  for r in rows:
   rt=core.parse(r.get('DATE',''))
   if not rt or abs((rt-c['time']).total_seconds())>600:continue
   parts=str(r.get('OC1') or '').split(',')
   if parts[0].isdigit() and parts[0]!='9999':matched.append((abs((rt-c['time']).total_seconds()),r,parts))
  if not matched:return 'ISD 未核',c['value'],None,url
  _,r,parts=min(matched,key=lambda z:z[0]);v=float(parts[0])/10/.514444;info={'isd_time':r['DATE'],'OC1':r['OC1']}
  if len(parts)>1 and parts[1] in ('2','3','6','7'):return 'ISD 可疑/错误',None,info,url
 return ('ISD 更正' if abs(v-c['value'])>2 else 'ISD 一致'),(v if abs(v-c['value'])>2 else c['value']),info,url
def qc_one(st,y,se,tr,ids,cache,log):
 o=core.load_obs(st,y);cs=sorted(o['candidates'],key=lambda c:(-c['value'],c['time']));n=Counter();best=None;selected=None;loop=0
 for c in cs:
  if best is not None and c['value']<=best['kn']:selected=best;break
  rules=[];v=c['value'];parsed=raw_wind(c['raw'],c['source']);sp=sust(c['raw'])
  if v>100:rules.append('Q1')
  if v!=int(v):
   if parsed is None:rules.append('Q2')
   else:v=float(parsed);n['Q2_reparsed']+=1
  if c['source']=='gust' and sp is not None and v-sp>40:rules.append('Q3')
  others=[z['value'] for z in cs if z is not c and z['report_time']!=c['report_time'] and abs((z['time']-c['time']).total_seconds())<=10800]
  others += [w for z in o['reports'] if abs((z['time']-c['time']).total_seconds())<=10800 and z['time']!=c['report_time'] if (w:=sust(z['raw'])) is not None]
  if others and v-max(others)>30:rules.append('Q4')
  if rules:
   n.update(rules);log.append({'station':st,'season_year':y,'event_utc':core.stamp(c['time']),'report_utc':core.stamp(c['report_time']),'source':c['source'],'original_kn':c['value'],'rules':';'.join(rules),'raw':c['raw'],'generated_est':now()});continue
  c2=dict(c,value=v);lab,evidence=core.label(c2,o,se[st],tr[y]+tr[y+1]);n['mechanism_'+lab]+=1
  if lab!='nonconvective':continue
  if loop>=5:n['Q5_unresolved']+=1;break
  loop+=1;status,new,info,url=isd(st,c2,ids,cache);n[status]+=1
  if status=='ISD 可疑/错误':
   log.append({'station':st,'season_year':y,'event_utc':core.stamp(c['time']),'report_utc':core.stamp(c['report_time']),'source':c['source'],'original_kn':c['value'],'rules':'Q5','raw':c['raw'],'generated_est':now()});continue
  if status=='ISD 更正':n['Q5_corrected_candidate']+=1
  candidate={'kn':new,'event_utc':core.stamp(c['time']),'report_utc':core.stamp(c['report_time']),'source':c['source'],'original_kn':c['value'],'isd_status':status,'isd_info':info,'isd_url':url,'evidence':evidence}
  if best is None or candidate['kn']>best['kn']:best=candidate
  if status!='ISD 更正':selected=best;break
 if selected is None and not n['Q5_unresolved']:selected=best
 return {'station':st,'season_year':y,'coverage':o['coverage'],'qc_peak':selected,'valid':bool(o['coverage']>=.9 and selected is not None and not n['Q5_unresolved']),'rule_counts':dict(n),'q5_loops':loop,'metar_url':o['url'],'generated_est':now()}
def admission():
 assert (ROOT/'map_frozen.json').exists() and not (ROOT/'station_admission.csv').exists()
 meta=[]
 for st in ALL:
  try:meta.append(homr(st))
  except Exception as e:meta.append({'station':st,'homr_error':repr(e),'region':'unknown'} )
  print('HOMR',st,meta[-1].get('homr_error','ok'),flush=True)
 savej(ROOT/'homr.json',meta)
 # Fail closed when HOMR fails. Do not infer station location from preliminary roster.
 if any('homr_error' in r for r in meta):raise RuntimeError('HOMR incomplete; no admission until resolved')
 geography(meta);land(meta);savej(ROOT/'static_gates.json',meta)
 se,tr=setup_events(meta);ids=isd_ids();assert all(ids[st] for st in ALL)
 q=ROOT/'qc_station_seasons.jsonl';lg=ROOT/'qc_log.csv';cache={};log=[];done=set()
 if q.exists():done={(r['station'],r['season_year']) for r in lines(q)}
 for r in meta:
  st=r['station']
  for y in range(2007,2022):
   if (st,y) in done:continue
   try:row=qc_one(st,y,se,tr,ids,cache,log)
   except Exception as e:row={'station':st,'season_year':y,'valid':False,'error':repr(e),'trace':traceback.format_exc()[-900:],'generated_est':now()}
   with q.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
   print('QC',st,y,row.get('valid'),row.get('error',''),flush=True)
   if log:
    with lg.open('a',newline='') as f:
     w=csv.DictWriter(f,list(log[0]));
     if f.tell()==0:w.writeheader()
     w.writerows(log)
    log.clear()
 obs={(r['station'],r['season_year']):r for r in lines(q)};assert len(obs)==len(ALL)*15
 frozen=[]
 for r in meta:
  st=r['station'];n=sum(bool(obs[st,y].get('valid')) for y in range(2007,2022));errors=[y for y in range(2007,2022) if 'error' in obs[st,y]]
  reasons=[k for k in ('instrument_ok','relocation_ok','elevation_ok','geog_ok','land_ok') if not r[k]]
  if n<12:reasons.append('valid_seasons_lt12')
  # A failed season is missing, not an exclusion of the entire station.
  frozen.append({'station':st,'region':r['region'],'lat':r['lat'],'lon':r['lon'],'generated_est':now(),'admitted':not reasons,'reasons':';'.join(reasons),'valid_seasons':n,'error_seasons':json.dumps(errors),'instrument_ok':r['instrument_ok'],'relocation_ok':r['relocation_ok'],'elevation_m':r['elev_m'],'coast_km':r['coast_km'],'great_lake_km':r['great_lake_km'],'geog_ok':r['geog_ok'],'ace_lat':r['ace_lat'],'ace_lon':r['ace_lon'],'ace_iy':r['ace_iy'],'ace_ix':r['ace_ix'],'land_fraction':r['land_fraction'],'land_ok':r['land_ok'],'homr_url':r['homr_url']})
 # Same-grid tie: valid-season count descending; ICAO ascending.
 groups=defaultdict(list)
 for r in frozen:
  if r['admitted']:groups[(r['ace_iy'],r['ace_ix'])].append(r)
 for group in groups.values():
  group.sort(key=lambda r:(-r['valid_seasons'],r['station']))
  for loser in group[1:]:loser['admitted']=False;loser['reasons']='same_grid:'+group[0]['station']
 savecsv(ROOT/'station_admission.csv',frozen);stage('2 admission');count()
def count():
 rows=list(csv.DictReader((ROOT/'station_admission.csv').open()));c=Counter(r['region'] for r in rows if r['admitted']=='True');result={'at':now(),'counts':dict(c),'same_grid_rejects':[(r['station'],r['reasons']) for r in rows if r['reasons'].startswith('same_grid:')],'status':'站数不足' if c['plains']<10 or c['other']<10 else '准入满足；等待 Lead 核对脚本，不进行 ERA5 配对'}
 savej(ROOT/'station_count.json',result);stage('3 count');print('COUNT',result,flush=True)
def recount():
 """Reapply frozen gates to existing admission rows; never fetch observations."""
 old=list(csv.DictReader((ROOT/'station_admission.csv').open()));groups=defaultdict(list)
 for r in old:
  r['reasons']=';'.join(x for x in r['reasons'].split(';') if x!='unresolved_download_errors' and not x.startswith('same_grid:'))
  r['admitted']=str(not bool(r['reasons']))
  r['generated_est']=now()
  if r['admitted']=='True':groups[(r['ace_iy'],r['ace_ix'])].append(r)
 for group in groups.values():
  group.sort(key=lambda r:(-int(r['valid_seasons']),r['station']))
  for loser in group[1:]:loser.update(admitted='False',reasons='same_grid:'+group[0]['station'])
 savecsv(ROOT/'station_admission_v2.csv',old)
 c=Counter(r['region'] for r in old if r['admitted']=='True')
 result={'at':now(),'counts':dict(c),'same_grid_rejects':[(r['station'],r['reasons']) for r in old if r['reasons'].startswith('same_grid:')],
         'status':'站数不足' if c['plains']<10 or c['other']<10 else '准入满足'}
 savej(ROOT/'station_count_v2.json',result);stage('3 recount');print('RECOUNT',result,flush=True)
# Steps 4–5 implemented here, but NOT launched in the current delegation.
def era():
 import calendar, xarray as xr
 assert (ROOT/'station_count_v2.json').exists() and json.loads((ROOT/'station_count_v2.json').read_text())['status']=='准入满足'
 rows=[r for r in csv.DictReader((ROOT/'station_admission_v2.csv').open()) if r['admitted']=='True'];assert rows
 obs={(r['station'],int(r['season_year'])):r for r in lines(ROOT/'qc_station_seasons.jsonl')}
 url='gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'
 s=xr.open_zarr(url,storage_options={'token':'anon'},consolidated=True)
 s=s.isel(latitude=slice(None,None,-1));slat=s.latitude.values;slon=s.longitude.values
 mlat=np.sort(np.rad2deg(np.arcsin(np.polynomial.legendre.leggauss(180)[0])));mlon=np.arange(360)+.5
 def edges(x,periodic=False):
  e=np.empty(len(x)+1);e[1:-1]=(x[1:]+x[:-1])/2;e[0]=x[0]-(x[1]-x[0])/2;e[-1]=x[-1]+(x[-1]-x[-2])/2
  if not periodic:e[0]=max(-90,e[0]);e[-1]=min(90,e[-1])
  return e
 sy=edges(slat);sx=edges(slon,True);ty=edges(mlat);tx=edges(mlon,True)
 indices=[(int(r['ace_iy']),int(r['ace_ix'])) for r in rows]
 i0=int(np.searchsorted(sy,min(ty[i] for i,j in indices),side='right')-1);i1=int(np.searchsorted(sy,max(ty[i+1] for i,j in indices),side='left')+1)
 j0=int(np.searchsorted(sx,min(tx[j] for i,j in indices),side='right')-1);j1=int(np.searchsorted(sx,max(tx[j+1] for i,j in indices),side='left')+1)
 W=[]
 for i,j in indices:
  yy=np.maximum(0,np.sin(np.deg2rad(np.minimum(sy[i0+1:i1+1],ty[i+1])))-np.sin(np.deg2rad(np.maximum(sy[i0:i1],ty[i]))))
  xx=np.maximum(0,np.minimum(sx[j0+1:j1+1],tx[j+1])-np.maximum(sx[j0:j1],tx[j]))
  w=yy[:,None]*xx[None,:];w/=w.sum();W.append(w.ravel())
 W=np.stack(W,axis=1);assert np.allclose(W.sum(axis=0),1)
 dest=ROOT/'era_seasons.jsonl';done={r['season_year'] for r in lines(dest)} if dest.exists() else set()
 for y in range(2007,2022):
  if y in done:continue
  months=[]
  for m in (10,11,12,1,2,3):
   yr=y if m>=10 else y+1
   a=f'{yr}-{m:02d}-01T00:00:00';b=f'{yr}-{m:02d}-{calendar.monthrange(yr,m)[1]:02d}T23:59:59'
   block=s[['10m_u_component_of_wind','10m_v_component_of_wind']].sel(time=slice(a,b)).isel(latitude=slice(i0,i1),longitude=slice(j0,j1)).load();n=len(block.time)
   assert n in (112,116,120,124),(yr,m,n)
   vel=np.hypot(block['10m_u_component_of_wind'].values.reshape(n,-1)@W,block['10m_v_component_of_wind'].values.reshape(n,-1)@W)
   months.append((block.time.values,vel));print('ERA_MONTH',yr,m,n,flush=True)
  ts=np.concatenate([z[0] for z in months]);vel=np.concatenate([z[1] for z in months]);expected=np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')).astype('datetime64[ns]')
  assert np.array_equal(ts,expected) and np.isfinite(vel).all()
  row={'season_year':y,'stations':{r['station']:{'ace1_max_mps':float(vel[:,k].max()),'max_utc':str(ts[vel[:,k].argmax()])} if obs[r['station'],y].get('valid',False) else None for k,r in enumerate(rows)},'n_6h':len(ts),'generated_est':now()}
  with dest.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
  print('ERA_DONE',y,len(ts),flush=True)
 stage('4 era')
def twoway(D):
 # Drop all-empty seasons before degrees-of-freedom accounting.
 D=D[:,np.any(np.isfinite(D),axis=0)];K,N=D.shape
 di=np.nanmean(D,axis=1);dj=np.nanmean(D,axis=0);grand=np.nanmean(D)
 R=D-di[:,None]-dj[None,:]+grand;df=np.isfinite(D).sum()-K-N+1
 if df<=0:raise ValueError('non-positive two-way degrees of freedom')
 return D,R,df
def interval_b(D,b):
 D,R,df=twoway(D);K,N=D.shape;di=np.nanmean(D,1);dj=np.nanmean(D,0)
 term=np.var(di,ddof=1)/K+np.var(dj,ddof=1)/N-np.nansum(R**2)/df/(K*N)
 if not np.isfinite(term):return [None,None]
 se=np.sqrt(max(0,term));return [float(b-1.645*se),float(b+1.645*se)]
def compare_status(ci,t):
 if None in ci:return '检不出（区间不可算）'
 lo,hi=ci
 return '过' if lo>=-t and hi<=t else '不过' if lo>t or hi<-t else '检不出'
def scoring(rows,obs,era,mp,base=False,seed=20261106,fixed=False):
 K=len(rows);yrs=range(2007,2022);X=np.array([[obs.get((r['station'],y),np.nan) for y in yrs] for r in rows]);E=np.array([[era.get((r['station'],y),np.nan) for y in yrs] for r in rows]);assert np.array_equal(np.isfinite(X),np.isfinite(E))
 mi=np.nanmean(X,1);si=np.nanstd(X,1,ddof=0);mei=np.nanmean(E,1);sei=np.nanstd(E,1,ddof=0);cvi=si/mi
 cm=0 if base else mp['c_m'];cs=0 if base else mp['c_s']
 pm=np.full(K,mp['m0']) if base else mp['a_m']+cm*mei
 ps=np.array([mp['CV0']*v for v in pm]) if base else mp['a_s']+cs*sei
 pc=np.full(K,mp['CV0']) if base else ps/pm
 if np.any(~np.isfinite([*mi,*si,*mei,*sei,*pm,*ps,*pc])) or np.any(np.array([*mi,*si,*pm,*ps])<=0):
  return {'status':'检不出（区间不可算）','reason':'nonfinite_or_nonpositive'}
 bm=float(pm.sum()/mi.sum()-1);bc=float(pc.sum()/cvi.sum()-1);mbar=float(mi.mean());cvbar=float(cvi.mean())
 dm=(pm[:,None]+(0 if fixed else cm*(E-mei[:,None]))-(1+bm)*X)/mbar
 psi=cvi[:,None]*(((X-mi[:,None])**2-si[:,None]**2)/(2*si[:,None]**2)-(X-mi[:,None])/mi[:,None])
 phi=0 if fixed else (cs*((E-mei[:,None])**2-sei[:,None]**2)/(2*sei[:,None])-pc[:,None]*cm*(E-mei[:,None]))/pm[:,None]
 dc=(pc[:,None]+phi-(1+bc)*(cvi[:,None]+psi))/cvbar
 im=interval_b(dm,bm);ic=interval_b(dc,bc)
 d=pm/mi-1;dit=(pm[:,None]+(0 if fixed else cm*(E-mei[:,None]))-X)/mi[:,None]
 def sigma(d0,d1):
  _,res,df=twoway(d1);v=np.nansum(res**2)/df*np.mean(1/np.isfinite(d1).sum(1));return float(np.sqrt(max(0,np.var(d0,ddof=1)-v)))
 sig=sigma(d,dit);rng=np.random.default_rng(seed);boots=[]
 for _ in range(2000):
  ii=rng.integers(0,K,K);boots.append(sigma(d[ii],dit[ii]))
 sl,sh=np.quantile(boots,[.05,.95]);emin=0 if im[0] is None or im[0]<=0<=im[1] else min(abs(z) for z in im) if im[0] is not None else None
 emci=[float(np.hypot(emin,sl)),float(np.hypot(max(abs(z) for z in im),sh))] if emin is not None else [None,None]
 st=[compare_status(im,.05),compare_status(emci,.05) if emci[0] is not None else '检不出（区间不可算）',compare_status(ic,.12)]
 status='通过' if all(z=='过' for z in st) else '不通过' if any(z=='不过' for z in st) else '检不出'
 return {'status':status,'items':st,'K':K,'N':int(np.any(np.isfinite(X),axis=0).sum()),'b_m':bm,'b_m_ci90':im,'sigma_m':sig,'sigma_ci90':[float(sl),float(sh)],'e_m':float(np.hypot(bm,sig)),'e_m_ci90':emci,'b_CV':bc,'b_CV_ci90':ic,'station_m':mi.tolist(),'station_CV':cvi.tolist(),'pred_m':pm.tolist(),'pred_CV':pc.tolist(),'era_m':mei.tolist(),'era_s':sei.tolist()}
def score():
 assert (ROOT/'era_seasons.jsonl').exists() and (ROOT/'station_count_v2.json').exists() and json.loads((ROOT/'station_count_v2.json').read_text())['status']=='准入满足'
 rows=[r for r in csv.DictReader((ROOT/'station_admission_v2.csv').open()) if r['admitted']=='True'];q={(r['station'],int(r['season_year'])):r for r in lines(ROOT/'qc_station_seasons.jsonl')};er=lines(ROOT/'era_seasons.jsonl');assert len(er)==15 and len({e['season_year'] for e in er})==15
 obs={(r['station'],y):float(q[r['station'],y]['qc_peak']['kn']) for r in rows for y in range(2007,2022) if q[r['station'],y].get('valid',False)};era={(st,y):float(v['ace1_max_mps']) for e in er for st,v in e['stations'].items() if v is not None for y in [e['season_year']]}
 mp=json.loads((ROOT/'map_frozen.json').read_text());main=scoring(rows,obs,era,mp);baseline=scoring(rows,obs,era,mp,base=True)
 if 'station_m' not in main:
  savej(ROOT/'decision.json',{'generated_est':now(),'main':main,'baseline':baseline,'reason':'nonfinite_or_nonpositive; frozen rule: 检不出'});stage('5 score');return
 rng=np.random.default_rng(20261107);comparisons={}
 for kind,key,pred,basev,g in [('m','station_m','pred_m',mp['m0'],.000625),('CV','station_CV','pred_CV',mp['CV0'],.0036)]:
  a=np.array(main[key]);p=np.array(main[pred]);d=p/a-1;d0=basev/a-1;sample=d0*d0-d*d
  boots=[float(sample[rng.integers(0,len(a),len(a))].mean()) for _ in range(2000)];L,U=np.quantile(boots,[.05,.95]);word='明显有增量' if L>g else '无实用增量' if -g<=L and U<=g else '有增量' if L>0 else '增量未定'
  comparisons[kind]={'delta':float(sample.mean()),'ci90':[float(L),float(U)],'g':g,'word':word,'statistically_positive_within_equivalence':bool(word=='无实用增量' and L>0)}
 table=[];build={v['station'] for v in mp['build_stations']}
 # Build-grid identities are read from the v2 admission metadata, not the
 # station_params table (which does not carry grid indices).
 pr=list(csv.DictReader((BASE/'build_admission.csv').open()))
 buildgrid={(v['ace_iy'],v['ace_ix']) for v in pr if v['station'] in build}
 assert len({v['station'] for v in pr if v['station'] in build})==len(build)
 for i,r in enumerate(rows):
  mi=main['station_m'][i];cv=main['station_CV'][i];pm=main['pred_m'][i];pc=main['pred_CV'][i]
  table.append({'station':r['station'],'region':r['region'],'n_i':sum((r['station'],y) in obs for y in range(2007,2022)),
   'same_build_grid':str((r['ace_iy'],r['ace_ix']) in buildgrid),'m_kn':mi,'CV':cv,'pred_m_kn':pm,'pred_CV':pc,
   'd_m':pm/mi-1,'d_m_sign':'+' if pm>mi else '-' if pm<mi else '0','d_CV':pc/cv-1,'d_CV_sign':'+' if pc>cv else '-' if pc<cv else '0',
   'abs_d_m':abs(pm/mi-1),'abs_d_CV':abs(pc/cv-1),'CV_absolute_error':pc-cv,'era_m_mps':main['era_m'][i],'era_s_mps':main['era_s'][i]})
 savecsv(ROOT/'station_table.csv',table)
 K10=-math.log(-math.log(.9))-float(np.euler_gamma);v10=[]
 for i,r in enumerate(rows):
  ob=main['station_m'][i]+main['station_CV'][i]*main['station_m'][i]*np.sqrt(6)/np.pi*K10
  pred=main['pred_m'][i]+main['pred_CV'][i]*main['pred_m'][i]*np.sqrt(6)/np.pi*K10
  v10.append({'station':r['station'],'pred_over_obs':float(pred/ob)})
 same=[r for r,t in zip(rows,table) if t['same_build_grid']=='True'];different=[r for r,t in zip(rows,table) if t['same_build_grid']=='False']
 fixed=scoring(rows,obs,era,mp,fixed=True);no_same=scoring(different,obs,era,mp) if different else {'status':'检不出','reason':'no stations'}
 regional={g:scoring([r for r in rows if r['region']==g],obs,era,mp) for g in ('plains','other')}
 def regional_delta(group,key,pred,constant):
  ix=[i for i,r in enumerate(rows) if r['region']==group];a=np.array(main[key])[ix];p=np.array(main[pred])[ix]
  return float(np.mean((constant/a-1)**2-(p/a-1)**2))
 for g in regional:
  regional[g]['delta_m']=regional_delta(g,'station_m','pred_m',mp['m0']);regional[g]['delta_CV']=regional_delta(g,'station_CV','pred_CV',mp['CV0'])
 # The ISD unmatched count is descriptive and is not a QC rule or scoring gate.
 nonverified=[(st,y) for (st,y),z in q.items() if st in {r['station'] for r in rows} and z.get('valid') and (z.get('qc_peak') or {}).get('isd_status')=='ISD 未核']
 output={'generated_est':now(),'main':{k:v for k,v in main.items() if not isinstance(v,list) or k.endswith('ci90') or k=='items'},'regional':regional,
  'baseline':baseline,'comparison':comparisons,'fixed_prediction_sensitivity':fixed,'exclude_same_build_grid_sensitivity':no_same,
  'same_build_grid_count':len(same),'same_build_grid_stations':[r['station'] for r in same],
  'ISD_unverified_seasons':len(nonverified),'ISD_unverified_fraction':len(nonverified)/len(obs),
  'station_outside_m_5pct':sum(t['abs_d_m']>.05 for t in table),'station_outside_CV_12pct':sum(t['abs_d_CV']>.12 for t in table),
  'station_CV_d_below_minus12pct':sum(t['d_CV']<-.12 for t in table),'e_CV_descriptive':float(np.sqrt(np.mean(np.square([t['d_CV'] for t in table])))),
  'V10_pred_observed':v10,'V10_ratio_mean':float(np.mean([z['pred_over_obs'] for z in v10]))}
 savej(ROOT/'baseline_compare.json',{'generated_est':now(),'comparison':comparisons,'baseline':baseline,'regional':regional})
 savej(ROOT/'decision.json',output);stage('5 score')
if __name__=='__main__':
 cmd=sys.argv[1]
 if cmd=='map':map_stage()
 elif cmd=='admission':admission()
 elif cmd=='count':count()
 elif cmd=='recount':recount()
 elif cmd=='era':era()
 elif cmd=='score':score()
 else:raise SystemExit('stage must be map/admission/count/recount/era/score')
