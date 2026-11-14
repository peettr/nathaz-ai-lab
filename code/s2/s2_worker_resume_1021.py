"""R23.4b S2 V1: frozen-cohort pilot and resumable group runner. Colab only."""
import csv, datetime as dt, hashlib, json, math, os, pathlib, sys, tempfile, time, traceback
import numpy as np
import torch
import xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import ARCO, HRRR, HRRR_FX
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic

R=pathlib.Path('/content/s2'); R.mkdir(exist_ok=True)
E=pathlib.Path('/content/events_r3.csv'); C=pathlib.Path('/content/controls_r3.csv')
assert hashlib.sha256(E.read_bytes()).hexdigest()=='c103e67f0cb0f6185c727539732bf0849f03c405fe7975b9332f88ccf617f892'
assert hashlib.sha256(C.read_bytes()).hexdigest()=='e0d01424a6492804850e761aa658630218bae9118b56e9444cc3a812dbedee97'
events=[r for r in csv.DictReader(E.open()) if r['group']=='v1']; controls=[r for r in csv.DictReader(C.open()) if r['group']=='v1']
assert len(events)==len(controls)==120 and [x['id'] for x in events]==[x['event_id'] for x in controls]
# Interleave pairs; first 20 groups are ten event/control pairs.
units=[(kind,row) for e,c in zip(events,controls) for kind,row in [('event',e),('control',c)]]
START=int(os.environ['S2_START']); END=int(os.environ['S2_END'])
assert (START,END) in ((20,130),(130,240))
OUT=R/f'incremental_{START}_{END}.jsonl'
DONE=R/f's2_{START}_{END}.done'
levels=[*range(1,12),13,15,20]; variables=['u10m','v10m']+[f'{v}{k}hl' for v in ('u','v','t','q','Z','p') for k in levels]
existing={}
if OUT.exists():
 for line in OUT.read_text().splitlines():
  if not line.strip(): continue
  row=json.loads(line);key=(row['unit_index'],row['kind'],row.get('seed'))
  if row['status']=='ok':
   assert key not in existing,key
   existing[key]=row

def persist(row):
 with OUT.open('a') as f: f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
 print('ROW',row['unit_index'],row['kind'],row.get('seed'),row['status'],row.get('elapsed_s'),flush=True)

def distance(lat,lon,slat,slon):
 a=np.sin((np.deg2rad(lat)-math.radians(slat))/2)**2+np.cos(np.deg2rad(lat))*math.cos(math.radians(slat))*np.sin((np.deg2rad(lon%360)-math.radians(slon%360))/2)**2
 return 12742*np.arcsin(np.sqrt(np.minimum(a,1)))

def peak(values, hours, locs, model_lat, model_lon, peak_time, init, narrow=False, profile=None):
 radius=10 if narrow else 25;tol=1800 if narrow else 3600; winner=None
 for h,arr in zip(hours,values):
  if abs((init+dt.timedelta(hours=h)-peak_time).total_seconds())>tol:continue
  good=locs<=radius
  if not np.any(good):continue
  ix=int(np.nanargmax(np.where(good,arr,np.nan)));val=float(arr[ix]);
  if winner is None or val>winner['ms']:
   winner={'ms':val,'lead_h':h,'distance_km':float(locs[ix]),'lat':float(model_lat[ix]),'lon':float(model_lon[ix]),'edge_km':float(radius-locs[ix])}
   if profile is not None:winner['profile']=profile(h,ix)
 return winner

def diagnostic(fields,h1):
 Z=np.stack([fields[f'Z{k}hl'] for k in levels]); z=Z-Z[:1]+h1[None,:]
 theta=np.stack([fields[f't{k}hl']*(1000/(fields[f'p{k}hl']/100))**.286*(1+.61*fields[f'q{k}hl']) for k in levels]);wind=np.stack([np.hypot(fields[f'u{k}hl'],fields[f'v{k}hl']) for k in levels]);base=np.hypot(fields['u10m'],fields['v10m'])
 valid=np.isfinite(theta)&np.isfinite(z)&np.isfinite(wind)&np.isfinite(base)[None,:]
 cross=(theta>=theta[:1]+.5)&valid; first=np.where(cross.any(axis=0),cross.argmax(axis=0),len(levels)-1)
 below=(np.arange(len(levels))[:,None]<=first[None,:])&valid
 excess=np.where(below,np.clip(1-.5*z/1000,.5,1)*(wind-base[None,:]),-np.inf)
 gust=base+np.maximum(0,np.max(excess,axis=0)); gust[~valid[0]]=np.nan
 anomaly=np.any((np.diff(z,axis=0)<0)&(z[:-1]<1000)&(z[1:]<1000),axis=0)
 return gust,base,z,theta,first,anomaly

model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval(); analysis=HRRR(verbose=False); fx=HRRR_FX(verbose=False)
lat,lon=model.lat,model.lon%360; hl,ho=HRRR.grid();ho=ho%360
assert np.max(np.abs(lat-hl[273:785,579:1219]))<.001
print('MODEL_READY',torch.cuda.get_device_name(),len(units),'range',START,END,flush=True)
for idx in range(START,END):
 kind,row=units[idx]
 start=time.monotonic();key=row['id'] if kind=='event' else row['event_id'];t=dt.datetime.fromisoformat(row['utc']);center=(t+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2);hours=[1,2,3]
 d=distance(lat,lon,float(row['lat']),float(row['lon']));y,x=np.where(d<=25);assert len(y)>0
 gy,gx=y+273,x+579;locs=d[y,x];hloc=distance(hl,ho,float(row['lat']),float(row['lon']));hy,hx=np.where(hloc<=25)
 terrain=analysis([init],['z']).sel(variable='z').values[0,gy,gx]/9.80665
 h1=fx([init],[dt.timedelta(hours=0)],['Z1hl']).values[0,0,0,gy,gx]-terrain
 assert np.isfinite(h1).all() and 3<min(h1) and max(h1)<20,(key,min(h1),max(h1))
 if (idx,'baseline',None) not in existing:
  try:
   bh=[];bd=[]
   for h in hours:
    vs=['fg10m','u10m','v10m']+[f'{v}{k}hl' for v in ('u','v','t','q','Z','p') for k in levels]
    a=fx([init],[dt.timedelta(hours=h)],vs).values[0,0,:,gy,gx];assert a.shape==(len(y),len(vs)),a.shape;bf={v:a[:,j] for j,v in enumerate(vs)}
    g,base,z,th,first,an=diagnostic(bf,h1);bh.append({'h':h,'fg':fx([init],[dt.timedelta(hours=h)],['fg10m']).values[0,0,0,hy,hx].tolist()});bd.append(g)
   fg=peak([np.array(v['fg']) for v in bh],hours,hloc[hy,hx],hl[hy,hx],ho[hy,hx],t,init)
   fg_n=peak([np.array(v['fg']) for v in bh],hours,hloc[hy,hx],hl[hy,hx],ho[hy,hx],t,init,True)
   formula=peak(bd,hours,locs,lat[y,x],lon[y,x],t,init)
   persist(dict(status='ok',unit_index=idx,kind='baseline',seed=None,event_id=key,fg_wide=fg,fg_narrow=fg_n,hrrr_formula_wide=formula,init=init.isoformat(),elapsed_s=time.monotonic()-start))
  except Exception as ex:
   persist(dict(status='error',unit_index=idx,kind='baseline',seed=None,error=repr(ex),trace=traceback.format_exc()[-1200:]));continue
 for seed in range(101,111):
  if (idx,'member',seed) in existing:continue
  t0=time.monotonic()
  try:
   torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
   # Disposable per-member scratch: removed by TemporaryDirectory after extraction.
   with tempfile.TemporaryDirectory(prefix='s2_scratch_',dir='/content') as tmp:
    # Earth2Studio 0.19 does not accept lat/lon as output dimensions.
    # Save full-grid temporary Zarr (as verified in S1), then extract points and delete.
    coords={'variable':np.array(variables)}
    deterministic([init],3,model,analysis,ZarrBackend(tmp+'/fields.zarr'),output_coords=coords,verbose=False)
    ds=xr.open_zarr(tmp+'/fields.zarr'); ix_y=y;ix_x=x
    gusts=[];ratios=[];heur=[];nonmono=0;colcount=0;profiles={}
    for h in hours:
     fields={v:ds[v].isel(time=0,lead_time=h).values[ix_y,ix_x] for v in variables}
     gust,base,z,theta,first,an=diagnostic(fields,h1)
     assert np.isfinite(gust).all(),(idx,seed,h,'nonfinite')
     gusts.append(gust);ratios.append(base*1.6677)
     # HRRRCast compute_wind_gust optional-VVEL branch: max(1.4*U10, max column wind at p >=700 hPa).
     pp=np.stack([fields[f'p{k}hl'] for k in levels]); winds=np.stack([np.hypot(fields[f'u{k}hl'],fields[f'v{k}hl']) for k in levels]);heur.append(np.maximum(1.4*base,np.max(np.where(pp>=70000,winds,-np.inf),axis=0)))
     colcount+=len(y);nonmono+=int(an.sum())
     def profile(j,z=z.copy(),theta=theta.copy(),winds=winds.copy(),first=first.copy(),Z1=fields['Z1hl'].copy()):
      return dict(z_agl_m=z[:,j].tolist(),theta_v_k=theta[:,j].tolist(),wind_ms=winds[:,j].tolist(),pbl_top_m=float(max(0,z[first[j],j])),pbl_layer=int(levels[first[j]]),h1_m=float(h1[j]),ai_z1_minus_terrain_m=float(Z1[j]-terrain[j]))
     profiles[h]=profile
    def cb(h,j):return profiles[h](j)
    res={nm:dict(wide=peak(arr,hours,locs,lat[y,x],lon[y,x],t,init,profile=cb if nm=='diagnostic' else None),narrow=peak(arr,hours,locs,lat[y,x],lon[y,x],t,init,True)) for nm,arr in [('diagnostic',gusts),('factor16777',ratios),('hrrrcast_without_vvel',heur)]}
    persist(dict(status='ok',unit_index=idx,kind='member',seed=seed,event_id=key,init=init.isoformat(),methods=res,nonmonotonic_columns=nonmono,columns=colcount,elapsed_s=time.monotonic()-t0))
  except Exception as ex:persist(dict(status='error',unit_index=idx,kind='member',seed=seed,event_id=key,error=repr(ex),trace=traceback.format_exc()[-1600:],elapsed_s=time.monotonic()-t0))
 print('GROUP_END',idx,key,round(time.monotonic()-start,1),flush=True)
final={}
for line in OUT.read_text().splitlines():
 if line.strip():
  r=json.loads(line)
  if r['status']=='ok':final[(r['unit_index'],r['kind'],r.get('seed'))]=r
counts=[sum((i,'member',s) in final for s in range(101,111)) for i in range(START,END)]
assert all((i,'baseline',None) in final for i in range(START,END)),('missing baseline',counts)
assert all(c>=8 for c in counts),('less than 8 valid members; retry once before scoring',counts)
DONE.write_text(json.dumps({'start':START,'end':END,'groups':len(counts),'member_counts':counts,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat()}));print('DONE',START,END,flush=True)
