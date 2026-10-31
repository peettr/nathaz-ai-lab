"""Public-data event list -> HRRR init -> StormCast/ERA5 -> station neighborhood verification.
Run on Colab A100; checkpoint pinned in Earth2Studio 0.19.0.
Gust comparison caveat: StormCast predicts vector 10 m wind, NOT gust.
"""
import datetime as dt, json, math, os, time, traceback
from pathlib import Path
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO, HRRR, HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic

ROOT=Path('/content')
EVENTS=[json.loads(s) for s in (ROOT/'convective_observations.jsonl').read_text().splitlines() if s.startswith('{')]
if os.getenv('LIMIT_EVENTS'): EVENTS=EVENTS[:int(os.environ['LIMIT_EVENTS'])]
OUT=ROOT/'convective_metrics.jsonl'
existing={(r['id'],r['lead_h']) for s in OUT.read_text().splitlines() if (r:=json.loads(s)).get('status')=='ok'} if OUT.exists() else set()
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
hrrr=HRRR(); fx=HRRR_FX()
model_lat,model_lon=model.lat,model.lon%360
full_lat,full_lon=HRRR.grid();full_lon=full_lon%360
print('READY_EVENTS',len(EVENTS),'DEVICE',torch.cuda.get_device_name(),flush=True)

def metrics(data, latgrid, longrid, station_lat, station_lon, peak, init, field):
    """Return each field's space-time maximum with strict circular distance."""
    lat=np.deg2rad(latgrid); lon=np.deg2rad(longrid); slat=math.radians(station_lat); slon=math.radians(station_lon%360)
    a=np.sin((lat-slat)/2)**2 +np.cos(lat)*math.cos(slat)*np.sin((lon-slon)/2)**2
    distance=6371*2*np.arcsin(np.sqrt(np.minimum(a,1)))
    rv={}
    for radius,tolerance,label in ((25,1,'wide'),(10,0.5,'narrow')):
        mask=distance<=radius
        if not mask.any(): raise ValueError('station outside grid')
        best=None
        for k,arr in data.items():
            for hour,values in arr.items():
                valid=init+dt.timedelta(hours=int(hour))
                if abs((valid-peak).total_seconds())>tolerance*3600:continue
                subset=np.where(mask,values,np.nan)
                if np.all(np.isnan(subset)):continue
                ij=np.unravel_index(np.nanargmax(subset),subset.shape)
                v=float(subset[ij])
                if best is None or v>best['value_ms']:
                    best={'value_ms':v,'valid_utc':valid.isoformat(),'time_bias_min':round((valid-peak).total_seconds()/60,1),'distance_km':round(float(distance[ij]),2),'grid_lat':float(latgrid[ij]),'grid_lon':float(longrid[ij]%360-360),'field':k}
        rv[label]=best
    return rv

for event in EVENTS:
  peak=dt.datetime.fromisoformat(event['utc']); lat=float(event['lat']);lon=float(event['lon'])
  # Forecast center is the nearest UTC hour; validate in the frozen windows, not at arbitrary event time.
  center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
  for lead in (1,2,3,6):
    if (event['id'],lead) in existing:continue
    init=center-dt.timedelta(hours=lead)
    root=ROOT/f"convective_{event['id']}_L{lead}.zarr"
    t0=time.monotonic(); print('START',event['id'],lead,init.isoformat(),flush=True)
    try:
      if root.exists(): raise FileExistsError(f'partial output requires review: {root}')
      torch.cuda.reset_peak_memory_stats()
      output=ZarrBackend(str(root))
      deterministic([init.replace(tzinfo=None)],lead+1,model,hrrr,output,output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
      ds=xr.open_zarr(root)
      mo={}
      for h in range(1,lead+2):
        u=ds['u10m'].isel(time=0,lead_time=h).values;v=ds['v10m'].isel(time=0,lead_time=h).values
        mo[h]=np.hypot(u,v)
      ai=metrics({'speed10m':mo},model_lat,model_lon,lat,lon,peak,init,'speed10m')
      print('AI_DONE',event['id'],lead,'sec',round(time.monotonic()-t0,1),flush=True)
      fxdata=fx([init.replace(tzinfo=None)],[dt.timedelta(hours=h) for h in range(1,lead+2)],['u10m','v10m','fg10m'])
      hu=fxdata.sel(variable='u10m').values[0];hv=fxdata.sel(variable='v10m').values[0];hg=fxdata.sel(variable='fg10m').values[0]
      hr={h:np.hypot(hu[i],hv[i]) for i,h in enumerate(range(1,lead+2))}
      gust={h:hg[i] for i,h in enumerate(range(1,lead+2))}
      baseline=metrics({'speed10m':hr,'GUST':gust},full_lat,full_lon,lat,lon,peak,init,'mixed')
      # Report speed and gust independently, never pick whichever is larger.
      baseline_speed=metrics({'speed10m':hr},full_lat,full_lon,lat,lon,peak,init,'speed10m')
      baseline_gust=metrics({'GUST':gust},full_lat,full_lon,lat,lon,peak,init,'GUST')
      p=hrrr([init.replace(tzinfo=None)],['u10m','v10m'])
      pu=p.sel(variable='u10m').values[0];pv=p.sel(variable='v10m').values[0]
      persist=metrics({'speed10m':{0:np.hypot(pu,pv)}},full_lat,full_lon,lat,lon,init,init,'speed10m')['wide']
      row={'status':'ok','id':event['id'],'station':event['station'],'peak_utc':peak.isoformat(),'init_utc':init.isoformat(),'lead_h':lead,'obs_kt':float(event['ncei_kt']),'ai':ai,'hrrr_speed':baseline_speed,'hrrr_gust':baseline_gust,'persistence':persist,'runtime_sec':round(time.monotonic()-t0,1),'gpu_peak_gb':round(torch.cuda.max_memory_allocated()/1e9,3),'conditioning':'ERA5_ARCO','event_source':event['ncei_url'],'observation_source':event['iem_url']}
      with OUT.open('a') as f:f.write(json.dumps(row)+'\n')
      print('DONE',event['id'],lead,'sec',row['runtime_sec'],'gpu',row['gpu_peak_gb'],'ai',ai,flush=True)
    except Exception as ex:
      traceback.print_exc()
      row={'status':'error','id':event['id'],'lead_h':lead,'init_utc':init.isoformat(),'error':repr(ex),'runtime_sec':round(time.monotonic()-t0,1)}
      with OUT.open('a') as f:f.write(json.dumps(row)+'\n')
      print('ERROR',row,flush=True)
      if event is EVENTS[0]:raise
print('BATCH_COMPLETE',len(EVENTS),'rows',len(OUT.read_text().splitlines()),flush=True)
