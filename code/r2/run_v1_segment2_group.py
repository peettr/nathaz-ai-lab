"""One idempotent event×lead group, with fixed 10-member seeds; host downloads after each group."""
import csv, datetime as dt, json, math, os, time, traceback
from pathlib import Path
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO, HRRR, HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
R=Path('/content'); output=R/'r2_v1_main.jsonl'
events=list(csv.DictReader((R/'events_r2_verified.csv').open()))
controls=list(csv.DictReader((R/'controls_r2_candidates.csv').open()))
# Already completed event groups remain in the original checkpoint; interleave remaining events/controls.
rows=[]
for i in range(10):
    rows.extend([events[i*2],controls[i],events[i*2+1]])
existing={(r['id'],r['lead_h'],r['source'],r.get('seed')) for line in output.read_text().splitlines() if (r:=json.loads(line)).get('status')=='ok'} if output.exists() else set()
remaining=[(e,l) for e in rows for l in (1,2,3) if any((e['id'],l,'v1',s) not in existing for s in range(101,111)) or (e['id'],l,'hrrr',None) not in existing]
if not remaining:
    print('SEGMENT_ALL_DONE',flush=True)
else:
    e,lead=remaining[0]; peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0); init=center-dt.timedelta(hours=lead)
    if 'r2_model' not in globals():
        r2_model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
        r2_hrrr=HRRR();r2_fx=HRRR_FX();r2_lat,r2_lon=r2_model.lat,r2_model.lon%360;r2_hlat,r2_hlon=HRRR.grid();r2_hlon=r2_hlon%360
    def distance(lat,lon):
        a=np.sin((np.deg2rad(lat)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lon%360)-math.radians(float(e['lon'])%360))/2)**2
        return 12742*np.arcsin(np.sqrt(np.minimum(a,1)))
    d=distance(r2_lat,r2_lon);hd=distance(r2_hlat,r2_hlon)
    def max_window(fields,dist,lat,lon,radius,tolerance):
        best=None
        for h,arr in fields.items():
            valid=init+dt.timedelta(hours=h)
            if abs((valid-peak).total_seconds())>3600*tolerance:continue
            sub=np.where(dist<=radius,arr,np.nan)
            if np.isnan(sub).all():continue
            ij=np.unravel_index(np.nanargmax(sub),sub.shape);v=float(sub[ij])
            if best is None or v>best['ms']:
                best={'ms':v,'distance_km':float(dist[ij]),'time_bias_min':(valid-peak).total_seconds()/60,'grid_lat':float(lat[ij]),'grid_lon':float(lon[ij]),'valid':valid.isoformat()}
        return best
    def base(source,seed=None):return dict(status='ok',id=e['id'],group=e['group'],station=e['station'],obs_kt=float(e['obs_kt']),peak_utc=peak.isoformat(),init=init.isoformat(),lead_h=lead,source=source,seed=seed,condition='ARCO_ERA5',ncei_url=e['ncei_url'],iem_url=e['iem_url'])
    def write(x):
        with output.open('a') as f:f.write(json.dumps(x,default=str)+'\n');f.flush();os.fsync(f.fileno())
        print('ROW',x['id'],x['lead_h'],x['source'],x.get('seed'),x['status'],flush=True)
    if (e['id'],lead,'hrrr',None) not in existing:
        t=time.monotonic()
        try:
            hrs=range(max(1,lead-1),lead+2);a=r2_fx([init],[dt.timedelta(hours=h) for h in hrs],['u10m','v10m','fg10m'])
            u=a.sel(variable='u10m').values[0];v=a.sel(variable='v10m').values[0];g=a.sel(variable='fg10m').values[0]
            speed={h:np.hypot(u[i],v[i]) for i,h in enumerate(hrs)};gust={h:g[i] for i,h in enumerate(hrs)}
            row=base('hrrr')
            for name,r,tol in [('wide',25,1),('narrow',10,.5)]:row[name]={'gust':max_window(gust,hd,r2_hlat,r2_hlon,r,tol),'speed10':max_window(speed,hd,r2_hlat,r2_hlon,r,tol)}
            row['runtime_sec']=round(time.monotonic()-t,2);write(row)
        except Exception as ex:write({**base('hrrr'),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1500:]})
    for seed in range(101,111):
        if (e['id'],lead,'v1',seed) in existing:continue
        t=time.monotonic();root=R/f"r2s2_{e['id']}_L{lead}_seed{seed}.zarr"
        try:
            if root.exists():raise FileExistsError(f'partial root {root}')
            torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            deterministic([init],lead+1,r2_model,r2_hrrr,ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
            z=xr.open_zarr(root);fields={h:np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values) for h in range(max(1,lead-1),lead+2)}
            row=base('v1',seed)
            for name,r,tol in [('wide',25,1),('narrow',10,.5)]:row[name]=max_window(fields,d,r2_lat,r2_lon,r,tol)
            row['runtime_sec']=round(time.monotonic()-t,2);row['gpu_peak_gb']=round(torch.cuda.max_memory_allocated()/1e9,3);write(row)
        except Exception as ex:write({**base('v1',seed),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1500:]})
    print('GROUP_DONE',e['id'],lead,flush=True)
