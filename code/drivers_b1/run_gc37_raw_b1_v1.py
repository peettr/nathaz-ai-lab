#!/usr/bin/env python3
"""Frozen TFIX 37-level forecast; event-specific crop; no WRF integration."""
import argparse,datetime as dt,hashlib,json,pathlib,subprocess,sys,threading,time
import numpy as np
import xarray as xr
import jax
sys.path.insert(0,'/content/r234c_graphcast_source/NCEP')
sys.path.insert(0,'/content/r234c_graphcast_source')
from run_graphcast import GraphCastModel
from graphcast import rollout

HERE=pathlib.Path(__file__).resolve().parent

def monitor(stop,samples):
    while not stop.wait(1):
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
        try:samples.append(int(p.stdout.splitlines()[0]))
        except (ValueError,IndexError):pass

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cycle',required=True);ap.add_argument('--event',choices=('N1','N3','N4'),required=True);ap.add_argument('--steps',type=int,required=True);ap.add_argument('--root',required=True);ap.add_argument('--bbox',required=True);a=ap.parse_args()
    bbox=json.loads(pathlib.Path(a.bbox).read_text())['events'][a.event]['domain']
    lat0,lat1=bbox['crop_lat'];lon0,lon1=[360+x for x in bbox['crop_lon_west_neg']]
    root=pathlib.Path(a.root);src=root/f'input_{a.cycle}_zero.nc';out=root/f'forecast_{a.cycle}_{a.steps}step';out.mkdir(exist_ok=False)
    m=GraphCastModel(str(root/'weights'),str(src),str(out),37,a.steps)
    m.load_pretrained_model()
    # TFIX: retain true -6h and 0h rather than NOAA helper's reindex from 0h.
    ds=xr.load_dataset(src);old=ds.time.values.astype('timedelta64[ns]')
    assert old.size==2 and np.array_equal(old,np.array([-6,0])*np.timedelta64(1,'h')),old
    start=ds.datetime.values[0,0];new_time=np.arange(-1,a.steps+1)*np.timedelta64(6,'h')
    ds=ds.reindex(time=new_time)
    ds['datetime']=(('batch','time'),np.asarray([start+np.arange(a.steps+2)*np.timedelta64(6,'h')]))
    m.current_batch=ds;m.extract_inputs_targets_forcings()
    for kind,dataset in [('inputs',m.inputs),('forcings',m.forcings)]:
        counts={k:int(np.size(v.values)-np.count_nonzero(np.isfinite(v.values))) for k,v in dataset.data_vars.items()}
        if any(counts.values()):raise ValueError((kind,'nonfinite',counts))
    m.load_normalization_stats();m.load_model()
    samples=[];stop=threading.Event();worker=threading.Thread(target=monitor,args=(stop,samples),daemon=True);worker.start()
    begin=time.monotonic();stats=[]
    try:
        gen=rollout.chunked_prediction_generator(m.model,rng=jax.random.PRNGKey(0),inputs=m.inputs,targets_template=m.targets*np.nan,forcings=m.forcings,num_steps_per_chunk=1)
        for i,pred in enumerate(gen,1):
            pred=jax.device_get(pred)
            record={'step':i,'forecast_h':6*i,'wall_since_start_seconds':round(time.monotonic()-begin,3),'peak_vram_mib':max(samples) if samples else None,'level_hpa':pred.level.values.tolist(),'nan':{k:int(np.count_nonzero(~np.isfinite(v.values))) for k,v in pred.data_vars.items()}}
            assert pred.level.size==37,record['level_hpa']
            if any(record['nan'].values()):raise ValueError(('nonfinite_forecast',record))
            reg=pred.sel(lat=slice(lat0,lat1),lon=slice(lon0,lon1))
            assert reg.sizes['lat']==int(round((lat1-lat0)*4))+1 and reg.sizes['lon']==int(round((lon1-lon0)*4))+1,reg.sizes
            arr={f'reg_{name}':np.asarray(reg[name].values).squeeze().astype('float32') for name in ('2m_temperature','10m_u_component_of_wind','10m_v_component_of_wind','mean_sea_level_pressure','geopotential','temperature','u_component_of_wind','v_component_of_wind','specific_humidity')}
            arr.update(reg_lat=reg.lat.values,reg_lon=reg.lon.values,reg_level=reg.level.values)
            np.savez_compressed(out/f'step_{i:02d}.npz',**arr)
            (out/f'step_{i:02d}.json').write_text(json.dumps(record,indent=2))
            print('STEP_DONE',json.dumps(record),flush=True);stats.append(record)
    finally:
        stop.set();worker.join(5)
    with src.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    summary={'event':a.event,'cycle':a.cycle,'steps':len(stats),'total_wall_seconds':round(time.monotonic()-begin,3),'peak_vram_mib':max(samples) if samples else None,'records':stats,'source_sha256':sha,'bbox':bbox}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print('INFERENCE_DONE',json.dumps({k:summary[k] for k in ('event','cycle','steps','total_wall_seconds','peak_vram_mib')}),flush=True)
if __name__=='__main__':main()
