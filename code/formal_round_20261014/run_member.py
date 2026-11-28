import sys,time,json,subprocess,yaml
from pathlib import Path
from datetime import datetime
import xarray as xr,numpy as np
base=Path('/content/ace_formal'); month=int(sys.argv[1]) if len(sys.argv)>1 else 1
smoke=(len(sys.argv)>2 and sys.argv[2]=='smoke')
assert 1<=month<=10
label=f'm{month:02d}'+('_smoke' if smoke else '')
out=base/'members'/label
out.mkdir(parents=True,exist_ok=False)
(out/'start.lock').open('x').write(f'1979-{month:02d}-01T00:00:00\n')
start=np.datetime64(f'1979-{month:02d}-01T00:00:00');last=np.datetime64('2022-12-31T18:00:00')
steps=40 if smoke else int((last-start)/np.timedelta64(6,'h'))
cfg=yaml.safe_load((base/'inference_config.yaml').read_text())
cfg['checkpoint_path']=str(base/'ace2_era5_ckpt.tar')
cfg['experiment_dir']=str(out/'output')
cfg['initial_condition']['path']=str(base/'initial_conditions/ic_1979.nc')
cfg['initial_condition']['start_indices']['times']=[str(start)]
cfg['forcing_loader']['dataset']['data_path']=str(base/'forcing_data')
cfg['forcing_loader']['num_data_workers']=0
cfg['n_forward_steps']=steps
cfg['forward_steps_in_memory']=50
cfg['data_writer']['names']=['UGRD10m','VGRD10m']
cfg['logging']['log_to_wandb']=False
(out/'config.yaml').open('x').write(yaml.safe_dump(cfg))
print('BEGIN',label,steps,str(start),str(last),flush=True)
t=time.monotonic()
with (out/'model.log').open('x') as f:
 p=subprocess.run([sys.executable,'-m','fme.ace.inference',str(out/'config.yaml')],stdout=f,stderr=subprocess.STDOUT)
result={'month':month,'steps':steps,'returncode':p.returncode,'wall_s':time.monotonic()-t,'initial_time':str(start),'final_prediction_time':str(last),'smoke':smoke}
(out/'exit.json').open('x').write(json.dumps(result,indent=2))
print('MODEL_EXIT',result,flush=True)
if p.returncode:print((out/'model.log').read_text()[-5000:]);sys.exit(p.returncode)
d=xr.open_dataset(out/'output'/'autoregressive_predictions.nc')
print('PREDICTIONS',dict(d.sizes),[(k,list(d[k].dims)) for k in ['UGRD10m','VGRD10m']],flush=True)
assert d.valid_time.values[0,0]==start+np.timedelta64(6,'h')
assert d.valid_time.values[0,-1]==(start+np.timedelta64(6*steps,'h'))
assert d.sizes['time']==steps
if not smoke:
 coord=json.loads((base/'reference/grid_and_weights.json').read_text())
 inds=coord['stations'];order=coord['order'];lat=xr.DataArray([inds[k]['i'] for k in order],dims='station');lon=xr.DataArray([inds[k]['j'] for k in order],dims='station')
 times=d.valid_time.values[0];cold=((times.astype('datetime64[M]').astype(int)%12)+1)
 years=times.astype('datetime64[Y]').astype(int)+1970
 keep=((cold>=10)|(cold<=3)) & (years>=1980) & (years<=2022)
 # keep only complete seasons from 1980/81 through 2021/22
 keep &= ~((years==1980)&(cold<=3)) & ~((years==2022)&(cold>=10))
 u=d.UGRD10m.isel(sample=0,lat=lat,lon=lon).values[keep];v=d.VGRD10m.isel(sample=0,lat=lat,lon=lon).values[keep];ts=times[keep]
 assert u.shape[1]==8 and np.isfinite(u).all() and np.isfinite(v).all()
 expected=np.concatenate([np.arange(np.datetime64(f'{y}-10-01T00'),np.datetime64(f'{y+1}-04-01T00'),np.timedelta64(6,'h')) for y in range(1980,2022)]).astype('datetime64[ns]')
 assert np.array_equal(ts,expected),(len(ts),len(expected),ts[0],ts[-1])
 np.savez_compressed(out/'cold_points.npz',time=ts,u=u.astype('f4'),v=v.astype('f4'),order=order)
 print('POINTS_DONE',label,len(ts),list(order),(out/'cold_points.npz').stat().st_size,flush=True)
print('MEMBER_DONE',label,flush=True)
