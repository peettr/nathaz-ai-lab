"""Fixed-seed StormCast V1 + HRRR gust baseline; append-only checkpoints."""
import csv,datetime as dt,json,math,time,traceback
from pathlib import Path
import numpy as np,torch,xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO,HRRR,HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
ROOT=Path('/content');out=ROOT/'r2_v1_main.jsonl'
events=list(csv.DictReader((ROOT/'events_r2_verified.csv').open()))
controls=list(csv.DictReader((ROOT/'controls_r2_candidates.csv').open()))
rows=[x for x in events if x['group']=='v1'][:20]+controls[:10]
seeds=list(range(101,111));leads=(1,2,3)
existing={(x['id'],x['lead_h'],x['source'],x.get('seed')) for line in out.read_text().splitlines() if (x:=json.loads(line)).get('status')=='ok'} if out.exists() else set()
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
hrrr=HRRR();fx=HRRR_FX()
lat,lon=model.lat,model.lon%360;hlat,hlon=HRRR.grid();hlon=hlon%360
print('START_ROWS',len(rows),'EXISTING',len(existing),'DEVICE',torch.cuda.get_device_name(),flush=True)
def write(r):
 with out.open('a') as f:f.write(json.dumps(r,default=str)+'\n')
 print('ROW',r['id'],r['lead_h'],r['source'],r.get('seed'),r['status'],r.get('runtime_sec'),flush=True)
def distances(la,lo,slat,slon):
 a=np.sin((np.deg2rad(la)-math.radians(slat))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(slat))*np.sin((np.deg2rad(lo%360)-math.radians(slon%360))/2)**2
 return 12742*np.arcsin(np.sqrt(np.minimum(a,1)))
def max_window(fields,d,init,peak,radius,tolerance):
 best=None
 for h,arr in fields.items():
  valid=init+dt.timedelta(hours=h)
  if abs((valid-peak).total_seconds())>3600*tolerance:continue
  sub=np.where(d<=radius,arr,np.nan)
  if np.isnan(sub).all():continue
  ij=np.unravel_index(np.nanargmax(sub),sub.shape);v=float(sub[ij])
  if best is None or v>best['ms']:
   best={'ms':v,'distance_km':float(d[ij]),'time_bias_min':(valid-peak).total_seconds()/60,'grid_lat':float((lat if arr.shape==lat.shape else hlat)[ij]),'valid':valid.isoformat()}
 return best
for event in rows:
 peak=dt.datetime.fromisoformat(event['utc']);slat=float(event['lat']);slon=float(event['lon']);d=distances(lat,lon,slat,slon);hd=distances(hlat,hlon,slat,slon)
 center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
 for lead in leads:
  init=center-dt.timedelta(hours=lead);ts=time.monotonic()
  def base(source,seed=None):return {'status':'ok','id':event['id'],'group':event['group'],'station':event['station'],'obs_kt':float(event['obs_kt']),'peak_utc':peak.isoformat(),'init':init.isoformat(),'lead_h':lead,'source':source,'seed':seed,'condition':'ARCO_ERA5','ncei_url':event['ncei_url'],'iem_url':event['iem_url']}
  if (event['id'],lead,'hrrr',None) not in existing:
   try:
    hrs=range(max(1,lead-1),lead+2);a=fx([init],[dt.timedelta(hours=h) for h in hrs],['u10m','v10m','fg10m'])
    u=a.sel(variable='u10m').values[0];v=a.sel(variable='v10m').values[0];g=a.sel(variable='fg10m').values[0]
    speed={h:np.hypot(u[i],v[i]) for i,h in enumerate(hrs)};gust={h:g[i] for i,h in enumerate(hrs)}
    row=base('hrrr')
    for name,r,tol in [('wide',25,1),('narrow',10,.5)]:
     row[name]={'gust':max_window(gust,hd,init,peak,r,tol),'speed10':max_window(speed,hd,init,peak,r,tol)}
    row['runtime_sec']=round(time.monotonic()-ts,2);write(row)
   except Exception as ex:write({**base('hrrr'),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1500:]})
  for seed in seeds:
   if (event['id'],lead,'v1',seed) in existing:continue
   ts=time.monotonic();root=ROOT/f"r2_{event['id']}_L{lead}_seed{seed}.zarr"
   try:
    if root.exists():raise FileExistsError(f'partial root {root}; do not overwrite')
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    deterministic([init],lead+1,model,hrrr,ZarrBackend(str(root)),output_coords={'variable':np.array(['u10m','v10m'])},verbose=False)
    z=xr.open_zarr(root); fields={}
    for h in range(max(1,lead-1),lead+2):
     fields[h]=np.hypot(z['u10m'].isel(time=0,lead_time=h).values,z['v10m'].isel(time=0,lead_time=h).values)
    row=base('v1',seed)
    for name,r,tol in [('wide',25,1),('narrow',10,.5)]:row[name]=max_window(fields,d,init,peak,r,tol)
    row['runtime_sec']=round(time.monotonic()-ts,2);row['gpu_peak_gb']=round(torch.cuda.max_memory_allocated()/1e9,3);write(row)
   except Exception as ex:write({**base('v1',seed),'status':'error','error':repr(ex),'trace':traceback.format_exc()[-1500:]})
print('DONE',len(rows),flush=True)
