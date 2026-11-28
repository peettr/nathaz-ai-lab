#!/usr/bin/env python3
"""Prepare bounded P24 GraphCast L37 GFS input (only on Colab VM).

Uses NCAR d084001 pgrb2 + d084003 pgrb2b, native q, and the
Lead-authorized upper-w assumption. Never substitutes ERA5 initial states.
"""
import argparse, datetime as dt, hashlib, json, pathlib, time, urllib.request
import numpy as np
import xarray as xr
import pygrib
LEVELS=np.array([1,2,3,5,7,10,20,30,50,70,100,125,150,175,200,225,250,300,350,400,450,500,550,600,650,700,750,775,800,825,850,875,900,925,950,975,1000],dtype=np.int32)
BASE='https://osdf-director.osg-htc.org/ncar/gdex/'
def url(dataset,t,forecast=0):
 s=t.strftime('%Y%m%d%H'); stem='gfs.0p25b' if dataset=='d084003' else 'gfs.0p25'
 return f'{BASE}{dataset}/2020/{t:%Y%m%d}/{stem}.{s}.f{forecast:03d}.grib2'
def download(u,dest):
 if not dest.exists():
  t=time.monotonic(); tmp=dest.with_suffix('.partial'); req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=200) as response,tmp.open('xb') as out:
   while chunk:=response.read(4*1024*1024): out.write(chunk)
  tmp.rename(dest)
  print('download',u,dest.stat().st_size,'sec',round(time.monotonic()-t,2),flush=True)
 return {'url':u,'bytes':dest.stat().st_size,'sha256':hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()}
def rec(grb,short,level=None,typ=None):
 query={'shortName':short}
 if level is not None: query.update(level=int(level),typeOfLevel=typ or 'isobaricInhPa')
 arr=grb.select(**query)
 if len(arr)!=1: raise ValueError((short,level,typ,len(arr)))
 return arr[0]
def val(msg):
 a=msg.values
 if np.ma.isMaskedArray(a): a=a.filled(np.nan)
 a=np.asarray(a,dtype='float32')
 if a.shape!=(721,1440): raise ValueError(('bad_shape',msg.shortName,a.shape))
 return a[::-1,:].copy()
def state(t,raw,case):
 gm=pygrib.open(str(raw[f'main_{t:%Y%m%d%H}'])); ga=pygrib.open(str(raw[f'aux_{t:%Y%m%d%H}']))
 fields={}
 fieldmap={'geopotential':'gh','temperature':'t','u_component_of_wind':'u','v_component_of_wind':'v','specific_humidity':'q','vertical_velocity':'w'}
 origin={}
 for name,short in fieldmap.items():
  arr=np.empty((len(LEVELS),721,1440),dtype=np.float32); origin[name]={}
  for ix,p in enumerate(LEVELS):
   if short=='w' and p<100:
    origin[name][str(p)]='lead_approved_upper_w_'+case
    continue
   source=ga if (p in (125,175,225,775,825,875) or short=='q') else gm
   msg=rec(source,short,p); arr[ix]=val(msg)
   origin[name][str(p)]='d084003' if source is ga else 'd084001'
   if short=='w' and str(msg.units).lower() not in ('pa s**-1','pa s-1','pa/s','pa s^-1'):
    print('w_units',msg.units,flush=True)
  if short=='w':
   hundred=arr[list(LEVELS).index(100)]
   for ix,p in enumerate(LEVELS):
    if p>=100: continue
    arr[ix]=0 if case=='zero' else hundred*(p/100)
  if name=='geopotential': arr*=np.float32(9.80665)
  if not np.isfinite(arr).all(): raise ValueError((t,name,'nonfinite',np.count_nonzero(~np.isfinite(arr))))
  fields[name]=arr
 surface={'2m_temperature':val(rec(gm,'2t')),'10m_u_component_of_wind':val(rec(gm,'10u')),'10m_v_component_of_wind':val(rec(gm,'10v')),'mean_sea_level_pressure':val(rec(gm,'prmsl'))}
 static={'geopotential_at_surface':val(rec(gm,'orog'))*np.float32(9.80665),'land_sea_mask':val(rec(gm,'lsm'))}
 gm.close();ga.close()
 return fields,surface,static,origin
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--cycle',default='2020060806');ap.add_argument('--case',choices=['zero','scaled'],required=True);ap.add_argument('--root',default='/content/r234c_gc37_428d60ab');a=ap.parse_args()
 root=pathlib.Path(a.root);root.mkdir(parents=True,exist_ok=True)
 t0=dt.datetime.strptime(a.cycle,'%Y%m%d%H'); times=[t0-dt.timedelta(hours=6),t0]; want={}
 for t in times:
  for ds,key in [('d084001','main'),('d084003','aux')]: want[f'{key}_{t:%Y%m%d%H}']=url(ds,t)
  want[f'precip_{t:%Y%m%d%H}']=url('d084001',t-dt.timedelta(hours=6),6)
 raw={}; provenance={}
 for k,u in want.items():
  p=root/'raw'/u.rsplit('/',1)[-1];p.parent.mkdir(exist_ok=True)
  provenance[k]=download(u,p);raw[k]=p
 times_data=[];surf_data=[];static=None;origins={}
 for t in times:
  fields,surf,static,origin=state(t,raw,a.case)
  # APCP f006 is the 6 h accumulation ending at this analysis time.
  g=pygrib.open(str(raw[f'precip_{t:%Y%m%d%H}']));matches=g.select(shortName='tp',typeOfLevel='surface')
  print('precip_candidates',t,[(m.stepRange,m.units) for m in matches],flush=True)
  matches=[m for m in matches if str(m.stepRange) in ('0-6','6')]
  if not matches: raise ValueError(('precip_step_missing',t))
  first=val(matches[0])
  if any(not np.array_equal(first,val(x),equal_nan=True) for x in matches[1:]):
   raise ValueError(('precip_step_conflicting_duplicates',t,len(matches)))
  surf['total_precipitation_6hr']=first/np.float32(1000)
  g.close(); times_data.append(fields);surf_data.append(surf);origins[str(t)]=origin
 lat=np.arange(-90,90.0001,0.25,dtype=np.float32);lon=np.arange(0,360,0.25,dtype=np.float32)
 coords={'batch':np.array([0]),'time':np.array([np.timedelta64(-6,'h'),np.timedelta64(0,'h')]),'level':LEVELS,'lat':lat,'lon':lon}
 d={name:(('batch','time','level','lat','lon'),np.stack([s[name] for s in times_data])[None,...]) for name in times_data[0]}
 d.update({name:(('batch','time','lat','lon'),np.stack([s[name] for s in surf_data])[None,...]) for name in surf_data[0]})
 d.update({name:(('lat','lon'),value) for name,value in static.items()})
 ds=xr.Dataset(d,coords=coords);ds=ds.assign_coords(datetime=(('batch','time'),np.array([[np.datetime64(t,'ns') for t in times]])))
 dest=root/f'input_{a.cycle}_{a.case}.nc';ds.to_netcdf(dest,engine='netcdf4',encoding={v:{'zlib':True,'complevel':1} for v in d}); ds.close()
 report={'case':a.case,'cycle':a.cycle,'input_sha256':hashlib.file_digest(dest.open('rb'),'sha256').hexdigest(),'sources':provenance,'origins':origins,'model_levels_hpa':LEVELS.tolist()}
 (root/f'input_{a.cycle}_{a.case}.json').write_text(json.dumps(report,indent=2))
 print('INPUT_READY',dest,report['input_sha256'],flush=True)
if __name__=='__main__':main()
