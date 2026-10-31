"""ACE2 frozen monthly-IC rollout; outputs regional six-hourly fields and points."""
import sys,time,json,subprocess,yaml
from pathlib import Path
import xarray as xr,numpy as np
base=Path('/content/ace_formal'); month=int(sys.argv[1]); assert 1<=month<=10
label=f'm{month:02d}';out=base/'members'/label
out.mkdir(parents=True,exist_ok=False)
(out/'start.lock').open('x').write(f'1979-{month:02d}-01T00:00:00\n')
start=np.datetime64(f'1979-{month:02d}-01T00:00:00');last=np.datetime64('2010-04-01T00:00:00')
steps=int((last-start)/np.timedelta64(6,'h'))
cfg=yaml.safe_load((base/'inference_config.yaml').read_text())
cfg['checkpoint_path']=str(base/'ace2_era5_ckpt.tar');cfg['experiment_dir']=str(out/'output')
cfg['initial_condition']['path']=str(base/'initial_conditions/ic_1979.nc')
cfg['initial_condition']['start_indices']['times']=[str(start)]
cfg['forcing_loader']['dataset']['data_path']=str(base/'forcing_data')
cfg['forcing_loader']['num_data_workers']=0;cfg['n_forward_steps']=steps
cfg['forward_steps_in_memory']=50;cfg['data_writer']['names']=['UGRD10m','VGRD10m','PRESsfc']
cfg['logging']['log_to_wandb']=False
(out/'config.yaml').open('x').write(yaml.safe_dump(cfg))
print('BEGIN',label,steps,str(start),str(last),flush=True)
t=time.monotonic()
with (out/'model.log').open('x') as f:
 p=subprocess.run([sys.executable,'-m','fme.ace.inference',str(out/'config.yaml')],stdout=f,stderr=subprocess.STDOUT)
result={'month':month,'steps':steps,'returncode':p.returncode,'wall_s':time.monotonic()-t,'initial_time':str(start),'final_prediction_time':str(last)}
(out/'exit.json').open('x').write(json.dumps(result,indent=2))
print('MODEL_EXIT',result,flush=True)
if p.returncode:print((out/'model.log').read_text()[-5000:],flush=True);sys.exit(p.returncode)
d=xr.open_dataset(out/'output'/'autoregressive_predictions.nc')
assert all(v in d for v in ['UGRD10m','VGRD10m','PRESsfc']),list(d.data_vars)
times=d.valid_time.values[0]
assert times[0]==start+np.timedelta64(6,'h') and times[-1]==last and d.sizes['time']==steps
sites=json.loads((base/'sites_frozen.json').read_text());order=sites['order']
inds=sites['stations'];ilat=xr.DataArray([inds[k]['i'] for k in order],dims='station');ilon=xr.DataArray([inds[k]['j'] for k in order],dims='station')
mo=times.astype('datetime64[M]').astype(int)%12+1;yr=times.astype('datetime64[Y]').astype(int)+1970
keep=((mo>=10)|(mo<=3)) & (yr>=1980) & (yr<=2010)
keep &= ~((yr==1980)&(mo<=3))
u=d.UGRD10m.isel(sample=0,lat=ilat,lon=ilon).values[keep]
v=d.VGRD10m.isel(sample=0,lat=ilat,lon=ilon).values[keep];ts=times[keep]
expected=np.concatenate([np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')) for y in range(1980,2010)]).astype('datetime64[ns]')
assert np.array_equal(ts,expected) and u.shape[1]==8 and np.isfinite(u).all() and np.isfinite(v).all()
np.savez_compressed(out/'cold_points.npz',time=ts,u=u.astype('f4'),v=v.astype('f4'),order=order)
print('POINTS_DONE',label,len(ts),flush=True)
subprocess.run([sys.executable,str(base/'reduce_points.py'),str(month),str(out/'cold_points.npz'),str(out/'summary.json')],check=True)
# Regional archive: closed, immutable calendar-year chunks, every predicted 6-h instant.
# Model latitude ascending; longitude 0..360. Preserve exact grid coordinates in each chunk.
lat=d.lat.values;lon=d.lon.values
ri=np.flatnonzero((lat>=25)&(lat<=50));rj=np.flatnonzero((lon>=235)&(lon<=295))
assert len(ri)>20 and len(rj)>50 and np.array_equal(ri,np.arange(ri[0],ri[-1]+1))
assert np.array_equal(rj,np.arange(rj[0],rj[-1]+1))
regional=out/'region';regional.mkdir(exist_ok=False)
manifest=[]
for year in range(1979,2011):
 ix=np.flatnonzero(yr==year)
 if len(ix)==0:continue
 sl=d.isel(sample=0,time=slice(ix[0],ix[-1]+1),lat=slice(ri[0],ri[-1]+1),lon=slice(rj[0],rj[-1]+1))
 arrays={name:sl[name].values.astype('f4') for name in ('UGRD10m','VGRD10m','PRESsfc')}
 assert all(np.isfinite(a).all() and a.shape==(len(ix),len(ri),len(rj)) for a in arrays.values())
 path=regional/f'{year}.npz'
 np.savez_compressed(path,time=times[ix],lat=lat[ri],lon=lon[rj],**arrays)
 manifest.append({'year':year,'file':path.name,'bytes':path.stat().st_size,'steps':len(ix)})
 print('REGION_YEAR_DONE',label,year,len(ix),path.stat().st_size,flush=True)
(out/'region_manifest.json').open('x').write(json.dumps({'member':month,'start':str(start),'last':str(last),'files':manifest},indent=2))
assert sum(x['steps'] for x in manifest)==steps
# Frozen auxiliary: grid-cell cold-season PRESsfc anomaly, not sea-level pressure.
pi=np.flatnonzero((lat[ri]>=35)&(lat[ri]<=48));pj=np.flatnonzero((lon[rj]>=255)&(lon[rj]<=272))
assert len(pi)>10 and len(pj)>10
psum=np.zeros((len(pi),len(pj)),dtype='f8');npress=0
for entry in manifest:
 with np.load(regional/entry['file']) as z:
  tt=z['time'];mm=tt.astype('datetime64[M]').astype(int)%12+1
  cold=((mm>=10)|(mm<=3))&(tt>=np.datetime64('1980-10-01'))&(tt<np.datetime64('2010-04-01'))
  arr=z['PRESsfc'][cold][:,pi][:,:,pj]
  psum+=arr.sum(axis=0,dtype='f8');npress+=len(arr)
clim=psum/npress;mins={y:float('inf') for y in range(1980,2010)}
for entry in manifest:
 with np.load(regional/entry['file']) as z:
  tt=z['time'];mm=tt.astype('datetime64[M]').astype(int)%12+1;yy=tt.astype('datetime64[Y]').astype(int)+1970
  cold=((mm>=10)|(mm<=3))&(tt>=np.datetime64('1980-10-01'))&(tt<np.datetime64('2010-04-01'))
  sy=np.where(mm>=10,yy,yy-1);arr=z['PRESsfc'][cold][:,pi][:,:,pj];sseason=sy[cold]
  for y in np.unique(sseason):mins[int(y)]=min(mins[int(y)],float(np.min(arr[sseason==y]-clim)))
assert len(mins)==30 and all(np.isfinite(v) for v in mins.values())
(out/'pressure_minima.json').open('x').write(json.dumps({'member':month,'units':'Pa','climatology_period':'1980/81–2009/10 cold seasons','rows':[{'season':y,'minimum_anomaly_pa':mins[y]} for y in sorted(mins)],'lat':lat[ri][pi].tolist(),'lon':lon[rj][pj].tolist()}))
print('PRESSURE_MINIMA_DONE',label,npress,flush=True)
print('MEMBER_DONE',label,len(manifest),flush=True)
(out/'complete.done').open('x').write(json.dumps({'member':month,'years':len(manifest),'steps':steps}))
