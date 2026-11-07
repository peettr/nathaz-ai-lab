"""S1(c) single historical V1 member profile/height sanity only, NO score."""
import csv,datetime as dt,json,math,pathlib,traceback
import numpy as np,torch,xarray as xr
from earth2studio.models.px import StormCast
from earth2studio.data import HRRR,ARCO
from earth2studio.io import ZarrBackend
from earth2studio.run import deterministic
R=pathlib.Path('/content');e=[x for x in csv.DictReader((R/'events_r2_verified.csv').open()) if x['group']=='v1'][0]
peak=dt.datetime.fromisoformat(e['utc']);center=(peak+dt.timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0);init=center-dt.timedelta(hours=2)
levels=[*range(1,12),13,15,20];variables=['u10m','v10m']+[f'{name}{k}hl' for name in ('u','v','t','q','Z','p') for k in levels]
root=R/'s1_c_member101.zarr';assert not root.exists(),'no overwrite of model output'
model=StormCast.load_model(StormCast.load_default_package(),conditioning_data_source=ARCO()).to('cuda').eval();hrrr=HRRR(verbose=False)
print('LOADED',len(variables),torch.cuda.get_device_name(),flush=True)
torch.manual_seed(101);torch.cuda.manual_seed_all(101)
deterministic([init],3,model,hrrr,ZarrBackend(str(root)),output_coords={'variable':np.array(variables)},verbose=False)
zarr=xr.open_zarr(root);la,lo=model.lat,model.lon%360
a=np.sin((np.deg2rad(la)-math.radians(float(e['lat'])))/2)**2+np.cos(np.deg2rad(la))*math.cos(math.radians(float(e['lat'])))*np.sin((np.deg2rad(lo)-math.radians(float(e['lon'])%360))/2)**2
yy,xx=np.where(12742*np.arcsin(np.sqrt(np.minimum(a,1)))<=25);assert len(yy)>0
# Static HRRR HGT on matching model grid, verify coordinates before use.
hla,hlo=HRRR.grid();assert la.shape==(512,640) and np.max(np.abs(la-hla[273:785,579:1219]))<.001
terrain=hrrr([init],['z']).sel(variable='z').values[0,273:785,579:1219][yy,xx]/9.80665 # Earth2Studio z geopotential; native HGT m
hrs=[h for h in (1,2,3) if abs((init+dt.timedelta(hours=h)-peak).total_seconds())<=3600]
allz=[];finite=0;total=0;tops=0;capped=0;best=None
for h in hrs:
 fields={name:zarr[name].isel(time=0,lead_time=h).values[yy,xx] for name in variables}
 z=np.stack([fields[f'Z{k}hl'] for k in levels])-terrain[None,:]
 theta=np.stack([fields[f't{k}hl']*(1000/fields[f'p{k}hl'])**.286*(1+.61*fields[f'q{k}hl']) for k in levels]);winds=np.stack([np.hypot(fields[f'u{k}hl'],fields[f'v{k}hl']) for k in levels]);wind10=np.hypot(fields['u10m'],fields['v10m'])
 valid=np.isfinite(theta)&np.isfinite(z)&np.isfinite(winds)&np.isfinite(wind10)[None,:];cross=(theta>=theta[0:1]+.5)&valid
 first=np.where(cross.any(axis=0),cross.argmax(axis=0),len(levels)-1);below=(np.arange(len(levels))[:,None]<=first[None,:])&valid
 gust=wind10+np.maximum(0,np.where(below,np.clip(1-.5*z/1000,.5,1)*(winds-wind10[None,:]),-np.inf)).max(axis=0)
 allz.extend(z[0].tolist());total+=len(yy);finite+=int(valid.all(axis=0).sum());tops+=int(cross.any(axis=0).sum());capped+=int((~cross.any(axis=0)).sum())
 ix=int(np.nanargmax(gust));val=float(gust[ix])
 if best is None or val>best['gust_ms']:
  best=dict(gust_ms=val,lead_h=h,lat=float(la[yy[ix],xx[ix]]),lon=float(lo[yy[ix],xx[ix]]),terrain_m=float(terrain[ix]),pbl_top_m=float(z[first[ix],ix]),pbl_found=bool(cross[:,ix].any()),levels=[dict(level=k,z_agl_m=float(z[j,ix]),u_ms=float(fields[f'u{k}hl'][ix]),v_ms=float(fields[f'v{k}hl'][ix]),t_k=float(fields[f't{k}hl'][ix]),q=float(fields[f'q{k}hl'][ix]),p_pa=float(fields[f'p{k}hl'][ix]),theta_v_k=float(theta[j,ix])) for j,k in enumerate(levels)])
 print('HOUR',h,'columns',len(yy),'valid',int(valid.all(axis=0).sum()),'pbl_found',int(cross.any(axis=0).sum()),'z1',float(np.nanmin(z[0])),float(np.nanmax(z[0])),flush=True)
result=dict(id=e['id'],seed=101,init=init.isoformat(),hours=hrs,n_columns=total,z1_m_min=float(np.nanmin(allz)),z1_m_median=float(np.nanmedian(allz)),z1_m_max=float(np.nanmax(allz)),nan_columns=total-finite,pbl_found_fraction=tops/total,pbl_capped_columns=capped,grid_max_lat_diff=float(np.max(np.abs(la-hla[273:785,579:1219]))),profile=best)
result['c_pass']=3<=result['z1_m_min'] and result['z1_m_max']<=20 and result['nan_columns']==0 and result['pbl_found_fraction']>=.95
(R/'s1_c_metrics.json').write_text(json.dumps(result,indent=2));print('DONE',json.dumps({k:v for k,v in result.items() if k!='profile'}),flush=True)
