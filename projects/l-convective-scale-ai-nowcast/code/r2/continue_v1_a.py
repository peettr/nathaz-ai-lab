"""Resume frozen V1 ERA5 matrix from immutable gate checkpoint; never replay successful keys."""
import csv, datetime as dt, json, math, os, time, traceback
from pathlib import Path
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO, HRRR, HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
R=Path('/content'); OUT=R/'r2_v1_main.jsonl'; LOG=R/'r2_segment_a_groups.jsonl'; DONE=R/'r2_segment_a.done'
assert not DONE.exists(), 'Existing done marker; no replay'
rows=list(csv.DictReader((R/'segment_a_manifest.csv').open()))
assert len(rows)==30 and sum(x['group']=='v1' for x in rows)==20 and sum(x['group']=='control' for x in rows)==10
checkpoint=[json.loads(s) for s in OUT.read_text().splitlines()]
seen={(x['id'],x['lead_h'],x['source'],x.get('seed')) for x in checkpoint if x['status']=='ok'}
assert len(seen)==sum(x['status']=='ok' for x in checkpoint),'Duplicate successful keys'
class Cached:
 def __init__(self,source):self.source=source;self.cache={}
 def __call__(self,time,variable):
  key=(tuple(str(t) for t in np.atleast_1d(time)),tuple(str(v) for v in np.atleast_1d(variable)))
  if key not in self.cache:
   self.cache[key]=self.source(time,variable).load()
   print('CACHE_MISS',type(self.source).__name__,key[0],key[1],flush=True)
  return self.cache[key]
 def clear(self):self.cache.clear()
 def __getattr__(self,name):return getattr(self.source,name)
cond=Cached(ARCO());initial=Cached(HRRR());fx=HRRR_FX()
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=cond).to('cuda').eval()
lat,lon=model.lat,model.lon%360;hlat,hlon=HRRR.grid();hlon=hlon%360
print('MODEL_READY',torch.cuda.get_device_name(),len(checkpoint),flush=True)
def append(path,row):
 with path.open('a') as f:f.write(json.dumps(row,default=str)+'\n');f.flush();os.fsync(f.fileno())
def distances(la,lo,slat,slon):
 a=np.sin((np.deg2rad(la)-math.radians(slat))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(slat))*np.sin((np.deg2rad(lo%360)-math.radians(slon%360))/2)**2
 return 12742*np.arcsin(np.sqrt(np.minimum(a,1)))
def maximum(fields,dist,la,lo,init,peak,radius,tolerance):
 best=None
 for hour,arr in fields.items():
  valid=init+dt.timedelta(hours=hour)
  if abs((valid-peak).total_seconds())>3600*tolerance:continue
  sub=np.where(dist<=radius,arr,np.nan)
  if np.isnan(sub).all():continue
  ij=np.unravel_index(np.nanargmax(sub),sub.shape);v=float(sub[ij])
  if best is None or v>best['ms']:
   best=dict(ms=v,distance_km=float(dist[ij]),time_bias_min=(valid-peak).total_seconds()/60,grid_lat=float(la[ij]),grid_lon=float(lo[ij]),valid=valid.isoformat())
 return best
for e in rows:
 eid=e['id'];peak=dt.datetime.fromisoformat(e['utc']);slat=float(e['lat']);slon=float(e['lon']);d=distances(lat,lon,slat,slon);hd=distances(hlat,hlon,slat,slon)
 center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
 for lead in (1,2,3):
  if all((eid,lead,'v1',s) in seen for s in range(101,111)) and (eid,lead,'hrrr',None) in seen:continue
  start=time.monotonic();init=center-dt.timedelta(hours=lead)
  def base(source,seed=None):return dict(status='ok',id=eid,group=e['group'],station=e['station'],obs_kt=float(e['obs_kt']),peak_utc=peak.isoformat(),init=init.isoformat(),lead_h=lead,source=source,seed=seed,condition='ARCO_ERA5',ncei_url=e['ncei_url'],iem_url=e['iem_url'],segment='A')
  if (eid,lead,'hrrr',None) not in seen:
   try:
    t=time.monotonic();hours=range(max(1,lead-1),lead+2);a=fx([init],[dt.timedelta(hours=h) for h in hours],['u10m','v10m','fg10m'])
    u=a.sel(variable='u10m').values[0];v=a.sel(variable='v10m').values[0];g=a.sel(variable='fg10m').values[0]
    speed={h:np.hypot(u[i],v[i]) for i,h in enumerate(hours)};gust={h:g[i] for i,h in enumerate(hours)}
    row=base('hrrr');row['wide']={'gust':maximum(gust,hd,hlat,hlon,init,peak,25,1),'speed10':maximum(speed,hd,hlat,hlon,init,peak,25,1)}
    row['narrow']={'gust':maximum(gust,hd,hlat,hlon,init,peak,10,.5),'speed10':maximum(speed,hd,hlat,hlon,init,peak,10,.5)}
    row['runtime_sec']=round(time.monotonic()-t,2);append(OUT,row);seen.add((eid,lead,'hrrr',None))
   except Exception as ex:append(OUT,{**base('hrrr'),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1800:]})
  for seed in range(101,111):
   if (eid,lead,'v1',seed) in seen:continue
   t=time.monotonic();root=R/f'r2a_{eid}_L{lead}_s{seed}.zarr'
   try:
    if root.exists():raise FileExistsError(f'Partial root {root}; never overwrite')
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    deterministic([init],lead+1,model,initial,ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
    z=xr.open_zarr(root);fields={h:np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values) for h in range(max(1,lead-1),lead+2)}
    row=base('v1',seed);row['wide']=maximum(fields,d,lat,lon,init,peak,25,1);row['narrow']=maximum(fields,d,lat,lon,init,peak,10,.5)
    row['runtime_sec']=round(time.monotonic()-t,2);row['gpu_peak_gb']=round(torch.cuda.max_memory_allocated()/1e9,3)
    append(OUT,row);seen.add((eid,lead,'v1',seed));print('MEMBER_DONE',eid,lead,seed,row['runtime_sec'],flush=True)
   except Exception as ex:
    append(OUT,{**base('v1',seed),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1800:]});print('MEMBER_ERROR',eid,lead,seed,repr(ex),flush=True)
  complete=all((eid,lead,'v1',s) in seen for s in range(101,111)) and (eid,lead,'hrrr',None) in seen
  rec=dict(id=eid,lead_h=lead,complete=complete,wall_sec=round(time.monotonic()-start,2),members_done=sum((eid,lead,'v1',s) in seen for s in range(101,111)),hrrr_done=(eid,lead,'hrrr',None) in seen)
  append(LOG,rec);print('GROUP_DONE',rec,flush=True);cond.clear();initial.clear()
DONE.write_text('complete' if all(all((e['id'],l,'v1',s) in seen for s in range(101,111)) and (e['id'],l,'hrrr',None) in seen for e in rows for l in (1,2,3)) else 'incomplete')
print('SEGMENT_A_DONE',DONE.read_text(),flush=True)
