"""Seven frozen first-round events; idempotent append-only ten-member gate run."""
import csv, datetime as dt, json, math, os, time, traceback
from pathlib import Path
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO, HRRR, HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
R=Path('/content'); OUT=R/'r2_v1_main.jsonl'; LOG=R/'gate7_groups.jsonl'; DONE=R/'gate7.done'
assert not DONE.exists(), 'Already completed; do not replay'
E=list(csv.DictReader((R/'gate7_events.csv').open()))
assert len(E)==7 and len({x['event_id'] for x in E})==7
CK=[json.loads(x) for x in OUT.read_text().splitlines()] if OUT.exists() else []
assert len({(x['id'],x['lead_h'],x['source'],x.get('seed')) for x in CK if x.get('status')=='ok'})==sum(x.get('status')=='ok' for x in CK), 'duplicate successful checkpoint keys'
seen={(x['id'],x['lead_h'],x['source'],x.get('seed')) for x in CK if x.get('status')=='ok'}
class Cached:
    def __init__(self, source): self.source=source;self.cache={}
    def __call__(self, time, variable):
        key=(tuple(str(t) for t in np.atleast_1d(time)), tuple(str(v) for v in np.atleast_1d(variable)))
        if key not in self.cache:
            self.cache[key]=self.source(time,variable).load()
            print('FETCH_CACHE_MISS',type(self.source).__name__,key[0],key[1],flush=True)
        return self.cache[key]
    def clear(self): self.cache.clear()
    def __getattr__(self,name): return getattr(self.source,name)
cond=Cached(ARCO()); initdata=Cached(HRRR());fx=HRRR_FX()
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=cond).to('cuda').eval()
lat,lon=model.lat,model.lon%360;hlat,hlon=HRRR.grid();hlon=hlon%360
print('MODEL_READY',torch.cuda.get_device_name(),len(CK),flush=True)
def write(path,obj):
    with path.open('a') as f:f.write(json.dumps(obj,default=str)+'\n');f.flush();os.fsync(f.fileno())
def distances(la,lo,slat,slon):
    a=np.sin((np.deg2rad(la)-math.radians(slat))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(slat))*np.sin((np.deg2rad(lo%360)-math.radians(slon%360))/2)**2
    return 12742*np.arcsin(np.sqrt(np.minimum(a,1)))
def max_window(fields,d,la,lo,init,peak,radius,tol):
    best=None
    for h,arr in fields.items():
        valid=init+dt.timedelta(hours=h)
        if abs((valid-peak).total_seconds())>3600*tol:continue
        sub=np.where(d<=radius,arr,np.nan)
        if np.isnan(sub).all():continue
        ij=np.unravel_index(np.nanargmax(sub),sub.shape);v=float(sub[ij])
        if best is None or v>best['ms']:
            best=dict(ms=v,distance_km=float(d[ij]),time_bias_min=(valid-peak).total_seconds()/60,grid_lat=float(la[ij]),grid_lon=float(lo[ij]),valid=valid.isoformat())
    return best
for e in E:
    eid=e['event_id'];peak=dt.datetime.strptime(e['peak_utc'],'%Y-%m-%d %H:%MZ');slat=float(e['lat']);slon=float(e['lon']);d=distances(lat,lon,slat,slon);hd=distances(hlat,hlon,slat,slon)
    center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
    for lead in (1,2,3):
        start=time.monotonic();init=center-dt.timedelta(hours=lead)
        def base(source,seed=None):return dict(status='ok',id=eid,group='v1',station=e['station'],obs_kt=float(e['peak_gust_kt']),peak_utc=peak.isoformat(),init=init.isoformat(),lead_h=lead,source=source,seed=seed,condition='ARCO_ERA5',ncei_url=e['noaa_bulk_url'],iem_url=e['iem_url'],gate='gate_7events')
        if (eid,lead,'hrrr',None) not in seen:
            try:
                t=time.monotonic();hrs=range(max(1,lead-1),lead+2);a=fx([init],[dt.timedelta(hours=h) for h in hrs],['u10m','v10m','fg10m'])
                u=a.sel(variable='u10m').values[0];v=a.sel(variable='v10m').values[0];g=a.sel(variable='fg10m').values[0]
                speed={h:np.hypot(u[i],v[i]) for i,h in enumerate(hrs)};gust={h:g[i] for i,h in enumerate(hrs)}
                row=base('hrrr');row['wide']={'gust':max_window(gust,hd,hlat,hlon,init,peak,25,1),'speed10':max_window(speed,hd,hlat,hlon,init,peak,25,1)}
                row['narrow']={'gust':max_window(gust,hd,hlat,hlon,init,peak,10,.5),'speed10':max_window(speed,hd,hlat,hlon,init,peak,10,.5)}
                row['runtime_sec']=round(time.monotonic()-t,2);write(OUT,row);seen.add((eid,lead,'hrrr',None))
            except Exception as ex:write(OUT,{**base('hrrr'),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1800:]})
        for seed in range(101,111):
            if (eid,lead,'v1',seed) in seen:continue
            t=time.monotonic();root=R/f'gate7_{eid}_L{lead}_s{seed}.zarr'
            try:
                if root.exists():raise FileExistsError(f'partial root {root}; never overwrite')
                torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
                deterministic([init],lead+1,model,initdata,ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
                z=xr.open_zarr(root)
                fields={h:np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values) for h in range(max(1,lead-1),lead+2)}
                row=base('v1',seed)
                row['wide']=max_window(fields,d,lat,lon,init,peak,25,1)
                row['narrow']=max_window(fields,d,lat,lon,init,peak,10,.5)
                row['runtime_sec']=round(time.monotonic()-t,2);row['gpu_peak_gb']=round(torch.cuda.max_memory_allocated()/1e9,3)
                write(OUT,row);seen.add((eid,lead,'v1',seed))
                print('MEMBER_DONE',eid,lead,seed,row['runtime_sec'],flush=True)
            except Exception as ex:
                write(OUT,{**base('v1',seed),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1800:]})
                print('MEMBER_ERROR',eid,lead,seed,repr(ex),flush=True)
        complete=all((eid,lead,'v1',s) in seen for s in range(101,111)) and (eid,lead,'hrrr',None) in seen
        rec=dict(id=eid,lead_h=lead,complete=complete,wall_sec=round(time.monotonic()-start,2),members_done=sum((eid,lead,'v1',s) in seen for s in range(101,111)),hrrr_done=(eid,lead,'hrrr',None) in seen,init=init.isoformat())
        write(LOG,rec);print('GROUP_DONE',rec,flush=True)
        cond.clear();initdata.clear()
DONE.write_text('complete' if all((e['event_id'],l,'v1',s) in seen and (e['event_id'],l,'hrrr',None) in seen for e in E for l in (1,2,3) for s in range(101,111)) else 'incomplete')
print('GATE_DONE',DONE.read_text(),flush=True)
