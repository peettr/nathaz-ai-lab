#!/usr/bin/env python3
"""Run official L37 checkpoint on Colab, keeping only bounded diagnostics."""
import argparse,datetime as dt,hashlib,json,os,pathlib,subprocess,sys,threading,time
import numpy as np
import xarray as xr
import jax
sys.path.insert(0,'/content/r234c_graphcast_source/NCEP')
sys.path.insert(0,'/content/r234c_graphcast_source')
from run_graphcast import GraphCastModel
from graphcast import rollout
import dataclasses
from graphcast import data_utils
P=(850,700,500,250)
A_LAT,A_LON=40.17563,360-103.22203  # KAKO Akron, Colorado (not Akron, Ohio)

def monitor(stop,samples):
 while not stop.wait(1.0):
  p=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
  try:samples.append(int(p.stdout.splitlines()[0]))
  except Exception:pass

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cycle',default='2020060806');ap.add_argument('--case',default='zero');ap.add_argument('--run-tag',default='');ap.add_argument('--steps',type=int,default=4);ap.add_argument('--root',default='/content/r234c_gc37_78b7088f');a=ap.parse_args()
 root=pathlib.Path(a.root);src=root/f'input_{a.cycle}_{a.case}.nc';out=root/f'forecast_{a.cycle}_{a.run_tag or a.case}_{a.steps}step';out.mkdir(exist_ok=False)
 m=GraphCastModel(str(root/'weights'),str(src),str(out),37,a.steps)
 m.load_pretrained_model();print('checkpoint_loaded',m.task_config,m.model_config,flush=True)
 # NOAA helper's reindex starts at 0 and silently loses an input labeled -6h.
 # Retain the genuine (-6h, 0h) input while extending only future slots.
 ds=xr.load_dataset(src); old=ds.time.values.astype('timedelta64[ns]')
 assert old.size==2 and np.array_equal(old,np.array([-6,0])*np.timedelta64(1,'h')),(old,'expected t-6h and t0')
 start=ds.datetime.values[0,0]
 new_time=np.arange(-1,a.steps+1)*np.timedelta64(6,'h')
 ds=ds.reindex(time=new_time)
 ds['datetime']=(('batch','time'),np.asarray([start+(np.arange(a.steps+2)*np.timedelta64(6,'h'))]))
 m.current_batch=ds;print('input_loaded',m.current_batch.sizes,'input_times',old,'extended_times',new_time,flush=True)
 m.extract_inputs_targets_forcings();print('extracted',m.inputs.sizes,m.targets.sizes,m.forcings.sizes,flush=True)
 for typ,dset in [('inputs',m.inputs),('forcings',m.forcings)]:
  nonfinite={k:int(np.size(v.values)-np.count_nonzero(np.isfinite(v.values))) for k,v in dset.data_vars.items()}
  print(typ+'_nonfinite',nonfinite,flush=True)
  if any(nonfinite.values()):raise ValueError((typ,'nonfinite',nonfinite))
 m.load_normalization_stats();m.load_model()
 samples=[];stop=threading.Event();thread=threading.Thread(target=monitor,args=(stop,samples),daemon=True);thread.start()
 begin=time.monotonic();stats=[]
 try:
  gen=rollout.chunked_prediction_generator(m.model,rng=jax.random.PRNGKey(0),inputs=m.inputs,targets_template=m.targets*np.nan,forcings=m.forcings,num_steps_per_chunk=1)
  for i,pred in enumerate(gen,1):
   pred=jax.device_get(pred)
   record={'step':i,'forecast_h':i*6,'wall_since_start_seconds':round(time.monotonic()-begin,3),'peak_vram_mib':max(samples) if samples else None,'level_hpa':pred.level.values.tolist(),'nan':{k:int(np.count_nonzero(~np.isfinite(v.values))) for k,v in pred.data_vars.items()}}
   assert pred.level.size==37,record['level_hpa']
   if any(record['nan'].values()):raise ValueError(('nonfinite_forecast',record))
   arr={}
   for var in ('temperature','u_component_of_wind','v_component_of_wind'):
    for lev in P: arr[f'{var}_{lev}']=np.asarray(pred[var].sel(level=lev).values).squeeze().astype('float32')
   arr['mean_sea_level_pressure']=np.asarray(pred.mean_sea_level_pressure.values).squeeze().astype('float32')
   # bounded regional copy for WPS, latitude/longitude center + ~1000km margin
   reg=pred.sel(lat=slice(30,52),lon=slice(244,270))
   for var in ('geopotential','temperature','u_component_of_wind','v_component_of_wind','specific_humidity'):
    arr[f'reg_{var}']=np.asarray(reg[var].values).squeeze().astype('float32')
   arr['reg_lat']=reg.lat.values;arr['reg_lon']=reg.lon.values;arr['reg_level']=reg.level.values
   np.savez_compressed(out/f'step_{i:02d}.npz',**arr)
   (out/f'step_{i:02d}.json').write_text(json.dumps(record,indent=2))
   print('STEP_DONE',json.dumps(record),flush=True);stats.append(record)
 finally:
  stop.set();thread.join(5)
 summary={'cycle':a.cycle,'case':a.case,'steps':len(stats),'total_wall_seconds':round(time.monotonic()-begin,3),'peak_vram_mib':max(samples) if samples else None,'records':stats,'source_sha256':hashlib.file_digest(src.open('rb'),'sha256').hexdigest()}
 (out/'summary.json').write_text(json.dumps(summary,indent=2))
 print('INFERENCE_DONE',json.dumps({k:summary[k] for k in ('cycle','case','steps','total_wall_seconds','peak_vram_mib')}),flush=True)
if __name__=='__main__':main()
