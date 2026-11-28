#!/usr/bin/env python3
"""Read operational GFS 48-h forecast MSLP and 10-m winds by HTTP byte range."""
import csv,gzip,io,math,urllib.request,json
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
from eccodes import codes_new_from_message,codes_get_array,codes_get,codes_release
P=Path(__file__).resolve().parent;B=P.parent
UA={'User-Agent':'PETW research GFS field range probe/1.0'}
def fetch(u,range_=None):
 h=dict(UA)
 if range_:h['Range']=f'bytes={range_[0]}-{range_[1]}'
 with urllib.request.urlopen(urllib.request.Request(u,headers=h),timeout=90) as r:
  b=r.read();assert not range_ or (r.status==206 and len(b)==range_[1]-range_[0]+1),(r.status,len(b),range_)
  return b
def center(e,init):
 year=e.get('year') or e['atcf_id'][-4:];sid=e['atcf_id'].lower()
 u=f'https://ftp.nhc.noaa.gov/atcf/archive/{year}/a{sid}.dat.gz'
 if year==2026:u=f'https://ftp.nhc.noaa.gov/atcf/aid_public/a{sid}.dat.gz'
 a=gzip.decompress(fetch(u)).decode()
 for line in a.splitlines():
  q=[x.strip() for x in line.split(',')]
  if len(q)>8 and q[2]==init.strftime('%Y%m%d%H') and q[4]=='OFCL' and q[5]=='48':
   return float(q[6][:-1])/10*(1 if q[6][-1]=='N' else -1),float(q[7][:-1])/10*(1 if q[7][-1]=='E' else -1),u
 raise ValueError(f'no OFCL 48 point {sid} {init}')
def read_case(e):
 t=datetime.fromisoformat(e['landfall_utc']);init=(t-timedelta(hours=48)).replace(hour=12 if (t-timedelta(hours=48)).hour>=12 else 0,minute=0,second=0,microsecond=0)
 d=init.strftime('%Y%m%d');h=init.strftime('%H');base=f'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{d}/{h}/atmos/gfs.t{h}z.pgrb2.0p50.f048'
 idx=fetch(base+'.idx').decode().splitlines();matches={}
 for i,line in enumerate(idx):
  for key,part in [('prmsl',':PRMSL:mean sea level:'),('u10',':UGRD:10 m above ground:'),('v10',':VGRD:10 m above ground:')]:
   if part in line:
    lo=int(line.split(':')[1]);hi=int(idx[i+1].split(':')[1])-1;matches[key]=(lo,hi)
 assert len(matches)==3,matches
 arrays={};sizes={};source={}
 for key,ran in matches.items():
  data=fetch(base,ran);g=codes_new_from_message(data)
  try:
   arrays[key]=codes_get_array(g,'values');sizes[key]=len(data)
   if key=='prmsl':lats=codes_get_array(g,'latitudes');lons=codes_get_array(g,'longitudes');source={'Ni':codes_get(g,'Ni'),'Nj':codes_get(g,'Nj'),'validityDate':codes_get(g,'validityDate'),'validityTime':codes_get(g,'validityTime')}
  finally:codes_release(g)
 lat0,lon0,adeck=center(e,init)
 # Approximate spherical great circle distance and local tangent azimuth, clockwise east/north components.
 la=np.radians(lats);lo=np.radians(lons);la0=math.radians(lat0);lo0=math.radians(lon0)
 dl=(lo-lo0+np.pi)%(2*np.pi)-np.pi
 a=np.sin((la-la0)/2)**2+np.cos(la)*math.cos(la0)*np.sin(dl/2)**2
 distance=12742*np.arcsin(np.minimum(1,np.sqrt(a)))
 dx=np.cos((la+la0)/2)*dl;dy=la-la0;norm=np.hypot(dx,dy);norm=np.where(norm==0,1,norm)
 tang=(-arrays['u10']*dy+arrays['v10']*dx)/norm
 m500=(distance>=400)&(distance<=600);m900=(distance>=800)&(distance<=1000)
 return dict(event=e.get('event',e.get('name')),init_utc=init.isoformat(),valid_utc=(init+timedelta(hours=48)).isoformat(),ofcl_center_lat=lat0,ofcl_center_lon=lon0,v500_tangential_kt=float(np.mean(tang[m500])*1.943844),penv_hpa=float(np.mean(arrays['prmsl'][m900])/100),ring500_cells=int(np.sum(m500)),ring900_cells=int(np.sum(m900)),bytes_read=sum(sizes.values())+len('\n'.join(idx)),field_bytes=sizes,idx_url=base+'.idx',grib_url=base,adeck_url=adeck,grid=source,definition='V500: 10m tangential wind in 400-600km ring, kt; Penv: MSLP 800-1000km ring, hPa. GFS f048 operational forecast, not 500-hPa wind.')
if __name__=='__main__':
 ev=list(csv.DictReader((B/'v2_new_events_probe.csv').open()))+list(csv.DictReader((B/'events_verified.csv').open()))
 lookup={r.get('event',r.get('name')):r for r in ev}
 results=[read_case(lookup[n]) for n in ('FRED','MILTON')]
 with (P/'gfs_env_probe.json').open('x') as f:json.dump(results,f,indent=2)
 print(json.dumps(results,indent=2))
