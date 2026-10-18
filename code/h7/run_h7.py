#!/usr/bin/env python3
"""Bounded H7 Chicago low-beam trial; reads public DAT/IEM, streams radar volumes in memory."""
import csv,io,json,math,re,datetime,collections,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np,requests,pyart
from scipy.stats import median_abs_deviation
P=Path(__file__).resolve().parent;LAB=P.parents[1]
BASE='https://unidata-nexrad-level2.s3.amazonaws.com/'
RADAR=(41.60444,-88.08472) # overwritten by Level II metadata for heights and sampling
SITES=requests.get('https://mesonet.agron.iastate.edu/geojson/network/ASOS1MIN.geojson',timeout=60).json()['features']
DAT=json.loads((LAB/'loss_wind/dat_census_2019_2024_r2.json').read_text())['features']
CASES=[('2024-06-23','KLOT'),('2024-07-16','KLOT')]
def km(a,b,c,d):
 la,lb=map(math.radians,(a,c));dl=math.radians(d-b);da=lb-la
 return 12742*math.asin(min(1,math.sqrt(math.sin(da/2)**2+math.cos(la)*math.cos(lb)*math.sin(dl/2)**2)))
def date_of(p):return datetime.datetime.fromtimestamp(p['stormdate']/1000,datetime.timezone.utc)
def list_vol(day,radar):
 u=BASE+f'{day[:4]}/{day[5:7]}/{day[8:]}/{radar}/';r=requests.get(BASE,params={'list-type':'2','prefix':u[len(BASE):],'max-keys':1000},timeout=40);r.raise_for_status()
 root=ET.fromstring(r.content);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'};assert root.find('s:IsTruncated',ns).text=='false'
 out=[]
 for v in root.findall('s:Contents',ns):
  key=v.find('s:Key',ns).text;m=re.search(r'(\d{8}_\d{6})_V\d\d$',key)
  if m:out.append((datetime.datetime.strptime(m[1],'%Y%m%d_%H%M%S').replace(tzinfo=datetime.timezone.utc),key,int(v.find('s:Size',ns).text)))
 return out
def obs(day,station_names,start,end):
 p={'station':','.join(station_names),'tz':'UTC','vars':'sknt,gust_sknt','sample':'1min','what':'view','delim':'comma'}
 for ix,t in [(1,start),(2,end)]:
  for key,val in [('year',t.year),('month',t.month),('day',t.day),('hour',t.hour),('minute',t.minute)]:p[key+str(ix)]=val
 r=requests.get('https://mesonet.agron.iastate.edu/cgi-bin/request/asos1min.py',params=p,timeout=240);r.raise_for_status()
 with (P/f'iem_url_{day}.txt').open('w') as f:f.write(r.url+'\n')
 rows=list(csv.DictReader((line for line in io.StringIO(r.text) if not line.startswith('#')))); print('obs',day,len(rows),flush=True)
 ret=collections.defaultdict(list)
 for x in rows:
  try:
   t=datetime.datetime.fromisoformat(x['valid(UTC)'].replace(' ','T')).replace(tzinfo=datetime.timezone.utc)
   if not start<=t<=end:continue
   sk=float(x['sknt']) if x.get('sknt','') not in ('','M','None') else float('nan');g=float(x['gust_sknt']) if x.get('gust_sknt','') not in ('','M','None') else float('nan')
   if not 0<=sk<=120:sk=float('nan')
   if not 0<=g<=150 or g<sk:g=float('nan')
   ret[x['station']].append((t,sk*.514444,g*.514444))
  except (KeyError,ValueError):continue
 return ret
def sample(r,s,points):
 sl=r.get_slice(s);az=np.asarray(r.azimuth['data'][sl]);ranges=np.asarray(r.range['data'])/1000
 v=np.ma.filled(r.get_field(s,'velocity'),np.nan);sw=np.ma.filled(r.get_field(s,'spectrum_width'),np.inf)
 refl_s=min(range(r.nsweeps),key=lambda i:abs(float(r.fixed_angle['data'][i])-float(r.fixed_angle['data'][s])) if np.ma.count(r.get_field(i,'reflectivity')) else 999)
 z=np.ma.filled(r.get_field(refl_s,'reflectivity'),np.nan);zs=r.get_slice(refl_s);za=np.asarray(r.azimuth['data'][zs]);zr=np.asarray(r.range['data'])/1000
 la,lo,alt=float(r.latitude['data'][0]),float(r.longitude['data'][0]),float(r.altitude['data'][0]);ang=math.radians(float(r.fixed_angle['data'][s]));out={}
 for ident,p in points.items():
  lat,lon,elev=p['lat'],p['lon'],p.get('elev',0)
  x=(lon-lo)*111.195*math.cos(math.radians((lat+la)/2));y=(lat-la)*111.195;dist=math.hypot(x,y);bearing=(math.degrees(math.atan2(x,y))+360)%360
  height=alt+dist*1000*math.sin(ang)+(dist*1000)**2/(2*(4/3)*6371000)-elev
  if height>=300 or height<0:continue
  ai=int(np.argmin(abs((az-bearing+180)%360-180)));ri=int(np.argmin(abs(ranges-dist)))
  aa=[i for i in (ai-1,ai,ai+1) if 0<=i<len(az)];rr=[i for i in (ri-1,ri,ri+1) if 0<=i<len(ranges)]
  zz_ai=int(np.argmin(abs((za-bearing+180)%360-180)));zz_ri=int(np.argmin(abs(zr-dist)))
  zz=z[zs.start+zz_ai,zz_ri] if zz_ri<len(zr) else float('nan')
  block=v[np.ix_(aa,rr)];width=sw[np.ix_(aa,rr)]
  good=block[np.isfinite(block)&(width<=8)]
  if len(good)<4 or not np.isfinite(zz) or zz<10 or np.median(abs(good-np.median(good)))>5:continue
  out[ident]={'vr_ms':round(float(np.median(abs(good))),3),'beam_agl_m':round(height,1),'distance_km':round(dist,2),'reflectivity_dbz':round(float(zz),1)}
 return out
allcase=[]; allsamples=[]; allobservations=[]
for day,radar in CASES:
 la,lo=41.60444,-88.08472 # KLOT approximate; exact radar origin read from file
 pts=[p for p in DAT if p['efscale']=='TSTM/Wind' and date_of(p).date().isoformat()==day and km(p['lat'],p['lon'],la,lo)<=25 and p['windspeed'] not in ('','-99','N/A')]
 # fixed window: most frequent hourly DAT timestamp ±45 minutes; score-blind.
 hours=collections.Counter(date_of(p).replace(minute=0,second=0,microsecond=0) for p in pts);center=hours.most_common(1)[0][0]+datetime.timedelta(minutes=30)
 start=center-datetime.timedelta(minutes=45);end=center+datetime.timedelta(minutes=45)
 pts=[p for p in pts if start<=date_of(p)<=end];print(day,'DAT',len(pts),'window',start,end,flush=True)
 station={}
 for f in SITES:
  lon,lat=f['geometry']['coordinates'][:2];pr=f['properties'];begin=pr.get('archive_begin') or '1900';finish=pr.get('archive_end') or '2100'
  if km(lat,lon,la,lo)<60 and begin<=day<=finish:
   station[f['id']]={'lat':lat,'lon':lon,'elev':float(pr.get('elevation') or 0),'name':pr.get('sname','')}
 observations=obs(day,station,start-datetime.timedelta(hours=3),end+datetime.timedelta(hours=3))
 for k,records in observations.items():
  if records:
   mx=max((v[2] for v in records if math.isfinite(v[2])),default=float('nan'));mean=max((v[1] for v in records if math.isfinite(v[1])),default=float('nan'))
   allobservations.append({'day':day,'station':k,'gust_ms':mx if math.isfinite(mx) else None,'sustained_ms':mean if math.isfinite(mean) else None,'n_minutes':len(records),'lat':station[k]['lat'],'lon':station[k]['lon']})
 # Nearest ASOS elevation is only a terrain proxy; mark ±terrain uncertainty in report.
 pointmap={}
 for p in pts:
  near=min(station.values(),key=lambda st:km(p['lat'],p['lon'],st['lat'],st['lon']))
  pointmap['D'+str(p['objectid'])]={'lat':p['lat'],'lon':p['lon'],'elev':near['elev']}
 pointmap.update({'S'+k:v for k,v in station.items()})
 volumes=[v for v in list_vol(day,radar) if start-datetime.timedelta(minutes=3)<=v[0]<=end+datetime.timedelta(minutes=3)]
 print(day,'volumes',len(volumes),'compressed_MB',round(sum(v[2] for v in volumes)/1e6,1),'stations',len(station),flush=True)
 meta={'day':day,'radar':radar,'window_start_utc':start.isoformat(),'window_end_utc':end.isoformat(),'dat_points_window':len(pts),'station_metadata':len(station),'volumes':len(volumes),'compressed_bytes':sum(v[2] for v in volumes),'failed':[]}
 for i,(t,key,size) in enumerate(volumes):
  try:
   response=requests.get(BASE+key,timeout=120);response.raise_for_status();assert len(response.content)==size
   r=pyart.io.read_nexrad_archive(io.BytesIO(response.content));del response
   sweeps=[s for s in range(r.nsweeps) if np.ma.count(r.get_field(s,'velocity'))>1000]
   s=min(sweeps,key=lambda j:float(r.fixed_angle['data'][j]));ny=float(r.get_nyquist_vel(s,check_uniform=False))
   if not 0<ny<100:raise ValueError('invalid Nyquist '+str(ny))
   gf=pyart.filters.GateFilter(r);gf.exclude_masked('velocity');corrected=pyart.correct.dealias_region_based(r,gatefilter=gf,vel_field='velocity',check_nyquist_uniform=False)
   # replace velocity field in-memory, no archive modified
   r.add_field('velocity_h7',corrected,replace_existing=True)
   original=r.fields['velocity'];r.fields['velocity']=r.fields['velocity_h7']
   for ident,one in sample(r,s,pointmap).items():allsamples.append({'day':day,'id':ident,'scan_utc':t.isoformat(),'nyquist_ms':ny,**one})
   r.fields['velocity']=original;del r,corrected
  except Exception as ex:meta['failed'].append({'key':key,'error':str(ex)[:140]})
  if (i+1)%10==0:print(day,i+1,len(volumes),'samples',len(allsamples),flush=True)
 allcase.append(meta)
 # persist each event independently for partial progress
 (P/'raw_progress_h7.json').write_text(json.dumps({'cases':allcase,'samples':allsamples,'observations':allobservations},allow_nan=False,indent=2))
print('FINISHED',len(allsamples))
