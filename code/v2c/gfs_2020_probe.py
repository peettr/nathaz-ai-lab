#!/usr/bin/env python3
"""Anonymous GDEX three-case field read. GRIB held only in memory, never saved.
T=AIWP 00/12 + 3h provisional OFCL public time; GFS previous 18/06 + f054.
No station observation is read.
"""
import csv,json,urllib.request,time,math
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
from eccodes import codes_new_from_message,codes_get,codes_get_array,codes_release
P=Path(__file__).resolve().parent
cases={r['event']:r for r in csv.DictReader((P.parent/'v2b/input_availability.csv').open())}
UA={'User-Agent':'PETW-B1-v2c-research/1.0'}
def read(case):
 a=cases[case];init=datetime.fromisoformat(a['init_utc']);gfs=init-timedelta(hours=6);d=gfs.strftime('%Y%m%d');h=gfs.strftime('%H');url=f'https://osdf-director.osg-htc.org/ncar/gdex/d084001/{gfs:%Y}/{d}/gfs.0p25.{d}{h}.f054.grib2'
 start=time.monotonic();req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=180) as r:
  raw=r.read();http=r.status
 fields={};metadata={};off=0;count=0
 while off+16<=len(raw):
  if raw[off:off+4]!=b'GRIB':raise ValueError(f'bad magic offset {off}')
  length=int.from_bytes(raw[off+8:off+16],'big');assert length>16 and off+length<=len(raw),(off,length,len(raw))
  msg=raw[off:off+length];g=codes_new_from_message(msg);count+=1
  try:
   name=codes_get(g,'shortName');lev=codes_get(g,'typeOfLevel');num=codes_get(g,'level')
   key=('p' if name=='prmsl' else ('u' if name=='u' else ('v' if name=='v' else '?')))
   if (name=='prmsl' and lev=='meanSea') or (name in ('u','v') and lev=='isobaricInhPa' and num==850):
    fields[key]=codes_get_array(g,'values');metadata[key]=dict(shortName=name,typeOfLevel=lev,level=num,offset=off,length=length,validityDate=codes_get(g,'validityDate'),validityTime=codes_get(g,'validityTime'))
    if key=='p': lats=codes_get_array(g,'latitudes');lons=codes_get_array(g,'longitudes')
  finally:codes_release(g)
  off+=length
  if len(fields)==3:break
 downloaded_bytes=len(raw)
 del raw
 # Use b-deck at forecast landfall valid instant only for retrospective spatial sampling?
 # Operational OFCL f048 coordinates at same valid time, from NHC a-deck; no BEST center.
 from sys import path
 path.insert(0,str(P.parent/'v2b'))
 from gfs_env_probe import center
 events=list(csv.DictReader((P.parent/'v2_new_events_probe.csv').open()))+list(csv.DictReader((P.parent/'events_verified.csv').open()))
 event=next(e for e in events if e.get('event',e.get('name'))==case)
 lat0,lon0,adeck=center(event,init)
 la=np.radians(lats);lo=np.radians(lons);la0=math.radians(lat0);lo0=math.radians(lon0);dl=(lo-lo0+np.pi)%(2*np.pi)-np.pi
 dist=12742*np.arcsin(np.minimum(1,np.sqrt(np.sin((la-la0)/2)**2+np.cos(la)*math.cos(la0)*np.sin(dl/2)**2)))
 dx=np.cos((la+la0)/2)*dl;dy=la-la0;norm=np.hypot(dx,dy);norm=np.where(norm==0,1,norm)
 tang=(-fields['u']*dy+fields['v']*dx)/norm
 return dict(event=case,ofcl_init=init.isoformat(),decision_T=(init+timedelta(hours=3)).isoformat(),gfs_init=gfs.isoformat(),gfs_lead_hours=54,url=url,adeck_url=adeck,ofcl_center=[lat0,lon0],http=http,downloaded_bytes=downloaded_bytes,read_bytes=sum(x['length'] for x in metadata.values()),grib_messages_scanned=count,field_metadata=metadata,V500_850hpa_kt=float(np.mean(tang[(dist>=400)&(dist<=600)])*1.943844),Penv_hpa=float(np.mean(fields['p'][(dist>=800)&(dist<=1000)])/100),n500=int(np.sum((dist>=400)&(dist<=600))),n900=int(np.sum((dist>=800)&(dist<=1000))),seconds=round(time.monotonic()-start,2))
if __name__=='__main__':
 import sys
 for c in sys.argv[1:]:
  try:r=read(c)
  except Exception as e:r={'event':c,'error':repr(e)}
  with (P/f'gfs_{c.lower()}_probe.json').open('x') as f:json.dump(r,f,indent=2)
  print(json.dumps(r))
