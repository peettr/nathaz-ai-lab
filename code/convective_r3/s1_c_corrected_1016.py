"""Corrected S1(c): two seen V1 members, anchored AGL; original terrain rule sensitivity."""
import csv, datetime as dt, json, math, pathlib
import numpy as np, torch, xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import HRRR, HRRR_FX, ARCO
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
R=pathlib.Path('/content')
events=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='v1'][:2]
levels=[*range(1,12),13,15,20]
variables=['u10m','v10m']+[f'{v}{k}hl' for v in ('u','v','t','q','Z','p') for k in levels]
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval()
hrrr=HRRR(verbose=False);fx=HRRR_FX(verbose=False)
la,lo=model.lat,model.lon%360;hla,hlo=HRRR.grid()
assert np.max(np.abs(la-hla[273:785,579:1219]))<.001
results=[]
for event_index,e in enumerate(events):
 peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2)
 a=np.sin((np.deg2rad(la)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lo)-math.radians(float(e['lon'])%360))/2)**2
 yy,xx=np.where(12742*np.arcsin(np.sqrt(np.minimum(a,1)))<=25);assert len(yy)>0
 gy,gx=yy+273,xx+579
 terrain=hrrr([init],['z']).sel(variable='z').values[0,gy,gx]/9.80665
 # Analysis/initial HRRR on identical cells; native hybrid Z is metres, no /g.
 hrrr_z1=fx([init],[dt.timedelta(hours=0)],['Z1hl']).values[0,0,0,gy,gx]
 h1=hrrr_z1-terrain
 assert np.all(np.isfinite(h1)) and np.nanmin(h1)>3 and np.nanmax(h1)<20,(np.nanmin(h1),np.nanmax(h1))
 root=R/f's1_c_corrected_{event_index}.zarr';assert not root.exists(),root
 torch.manual_seed(101);torch.cuda.manual_seed_all(101)
 deterministic([init],3,model,hrrr,ZarrBackend(str(root)),output_coords={'variable':np.array(variables)},verbose=False)
 data=xr.open_zarr(root)
 hrs=[h for h in (1,2,3) if abs((init+dt.timedelta(hours=h)-peak).total_seconds())<=3600]
 drift=[];pbl=[];pbl_old=[];nan=0;top=0;total=0;best=None;old_gust=[];new_gust=[]
 for h in hrs:
  fields={v:data[v].isel(time=0,lead_time=h).values[yy,xx] for v in variables}
  Z=np.stack([fields[f'Z{k}hl'] for k in levels]);raw=Z-terrain[None,:]
  z=Z-Z[0:1]+h1[None,:]
  theta=np.stack([fields[f't{k}hl']*(1000/(fields[f'p{k}hl']/100))**.286*(1+.61*fields[f'q{k}hl']) for k in levels])
  winds=np.stack([np.hypot(fields[f'u{k}hl'],fields[f'v{k}hl']) for k in levels]);wind10=np.hypot(fields['u10m'],fields['v10m'])
  valid=np.isfinite(theta)&np.isfinite(z)&np.isfinite(winds)&np.isfinite(wind10)[None,:]
  cross=(theta>=theta[0:1]+.5)&valid
  first=np.where(cross.any(axis=0),cross.argmax(axis=0),len(levels)-1)
  below=(np.arange(len(levels))[:,None]<=first[None,:])&valid
  def calc(zz):
   ex=np.where(below,np.clip(1-.5*zz/1000,.5,1)*(winds-wind10[None,:]),-np.inf)
   return wind10+np.maximum(0,np.max(ex,axis=0))
  gust=calc(z);legacy=calc(np.maximum(0,raw))
  drift.extend(raw[0].tolist());pbl.extend(z[first,np.arange(len(yy))].tolist());pbl_old.extend(np.maximum(0,raw[first,np.arange(len(yy))]).tolist())
  total+=len(yy);nan+=int((~valid.all(axis=0)|~np.isfinite(gust)).sum());top+=int(cross.any(axis=0).sum())
  old_gust.extend(legacy.tolist());new_gust.extend(gust.tolist())
  ix=int(np.nanargmax(gust));value=float(gust[ix])
  if best is None or value>best['gust_ms']:
   best=dict(gust_ms=value,lead_h=h,lat=float(la[yy[ix],xx[ix]]),lon=float(lo[yy[ix],xx[ix]]),h1_m=float(h1[ix]),terrain_m=float(terrain[ix]),pbl_top_m=float(z[first[ix],ix]),levels=[dict(level=k,z_agl_m=float(z[j,ix]),z_legacy_m=float(max(0,raw[j,ix])),theta_v_k=float(theta[j,ix]),p_pa=float(fields[f'p{k}hl'][ix]),u_ms=float(fields[f'u{k}hl'][ix]),v_ms=float(fields[f'v{k}hl'][ix])) for j,k in enumerate(levels)])
  print('HOUR',e['id'],h,'columns',len(yy),'top',int(cross.any(axis=0).sum()),'nan',nan,flush=True)
 result=dict(id=e['id'],station=e['station'],seed=101,init=init.isoformat(),hours=hrs,n_columns=total,h1_m=[float(np.min(h1)),float(np.median(h1)),float(np.max(h1))],ai_z1_minus_terrain_m=[float(np.min(drift)),float(np.median(drift)),float(np.max(drift))],anchored_nan_columns=nan,pbl_found_columns=top,pbl_found_fraction=top/total,pbl_top_anchored_m=[float(np.min(pbl)),float(np.median(pbl)),float(np.max(pbl))],pbl_top_legacy_m=[float(np.min(pbl_old)),float(np.median(pbl_old)),float(np.max(pbl_old))],gust_peak_anchored_ms=float(np.max(new_gust)),gust_peak_legacy_clipped_ms=float(np.max(old_gust)),gust_column_difference_median_ms=float(np.median(np.array(new_gust)-np.array(old_gust))),profile=best)
 result['c_pass']=nan==0 and top/total>=.95
 results.append(result)
 (R/'s1_c_corrected_metrics.json').write_text(json.dumps(results,indent=2));print('EVENT_DONE',e['id'],{k:v for k,v in result.items() if k!='profile'},flush=True)
print('DONE_CORRECTED_C',len(results),flush=True)
