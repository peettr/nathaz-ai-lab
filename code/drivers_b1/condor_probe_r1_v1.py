#!/usr/bin/env python3
"""R1 four-step GC37 Blackwell probe; never claims cropped reference is global."""
import hashlib, json, os, pathlib, subprocess, sys, threading, time
import numpy as np
import xarray as xr
import jax
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'graphcast_source'/'NCEP'))
sys.path.insert(0, str(ROOT/'graphcast_source'))
from run_graphcast import GraphCastModel
from graphcast import rollout

SRC = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/inputs_2024_R1R2_v1/input_2024073100_zero.nc')
REF = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/gc37_raw_R1_v1/2024073100')
PARAM = ROOT/'weights'/'params'/'GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz'
EXPECTED_SHA = '4e8cf600f3f402ebb430483e782b94648cef57bb757dec24dd7b11760d3fbacc'
FIELD = {'T':'temperature','U':'u_component_of_wind','V':'v_component_of_wind','Z':'geopotential'}
THRESH = {'T':0.1224, 'U':0.2702, 'V':0.26558, 'Z':None}

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def monitor(stop, samples):
    while not stop.wait(0.5):
        p = subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
        try: samples.append(int(p.stdout.splitlines()[0].strip()))
        except (ValueError, IndexError): pass

def main():
    assert sha(PARAM)==EXPECTED_SHA
    assert SRC.is_file() and REF.is_dir()
    env = {'python':sys.version, 'jax':jax.__version__, 'jaxlib':__import__('jaxlib').__version__, 'jax_devices':list(map(str,jax.devices())),
           'driver':subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],capture_output=True,text=True).stdout.strip(),
           'weight_sha256':EXPECTED_SHA,'source_sha256':sha(SRC),'source_commit':subprocess.check_output(['git','-C',str(ROOT/'graphcast_source'),'rev-parse','HEAD'],text=True).strip()}
    assert any(d.platform=='gpu' for d in jax.devices()), env
    (ROOT/'environment.json').write_text(json.dumps(env,indent=2))
    m=GraphCastModel(str(ROOT/'weights'),str(SRC),str(ROOT/'steps'),37,4)
    m.load_pretrained_model()
    ds=xr.load_dataset(SRC)
    old=ds.time.values.astype('timedelta64[ns]')
    assert np.array_equal(old,np.array([-6,0])*np.timedelta64(1,'h')),old
    start=ds.datetime.values[0,0]
    ds=ds.reindex(time=np.arange(-1,5)*np.timedelta64(6,'h'))
    ds['datetime']=(('batch','time'),np.asarray([start+np.arange(6)*np.timedelta64(6,'h')]))
    m.current_batch=ds;m.extract_inputs_targets_forcings()
    for kind,dataset in [('inputs',m.inputs),('forcings',m.forcings)]:
        assert all(np.isfinite(v.values).all() for v in dataset.data_vars.values()),kind
    m.load_normalization_stats();m.load_model()
    samples=[];stop=threading.Event();thread=threading.Thread(target=monitor,args=(stop,samples),daemon=True);thread.start()
    records=[]
    try:
        gen=rollout.chunked_prediction_generator(m.model,rng=jax.random.PRNGKey(0),inputs=m.inputs,targets_template=m.targets*np.nan,forcings=m.forcings,num_steps_per_chunk=1)
        for i in range(1,5):
            tick=time.monotonic();pred=jax.device_get(next(gen))
            model_step_seconds=time.monotonic()-tick
            record={'step':i,'nan':{},'comparison_scope':'R1 saved crop only; global reference absent','fields':{}}
            for label,key in FIELD.items():
                arr=np.asarray(pred[key].values)
                record['nan'][label]=int(np.count_nonzero(~np.isfinite(arr)))
                assert record['nan'][label]==0,(i,key)
            refpath=REF/f'step_{i:02d}.npz'
            with np.load(refpath) as saved:
                lat=saved['reg_lat'];lon=saved['reg_lon'];levels=saved['reg_level']
                region=pred.sel(lat=slice(float(lat[0]),float(lat[-1])),lon=slice(float(lon[0]),float(lon[-1])))
                assert np.array_equal(region.lat.values,lat) and np.array_equal(region.lon.values,lon) and np.array_equal(region.level.values,levels)
                for label,key in FIELD.items():
                    a=np.asarray(region[key].values).squeeze()
                    b=saved['reg_'+key]
                    assert a.shape==b.shape,(key,a.shape,b.shape)
                    delta=a.astype('float64')-b.astype('float64')
                    record['fields'][label]={'crop_rmse':float(np.sqrt(np.mean(delta**2))), 'crop_max_abs':float(np.max(np.abs(delta))), 'global_rmse':None,'global_max_abs':None,'threshold_global':THRESH[label]}
            record['wall_seconds']=model_step_seconds
            record['peak_vram_mib']=max(samples) if samples else None
            records.append(record)
            (ROOT/f'step_{i:02d}.json').write_text(json.dumps(record,indent=2))
            print('STEP_DONE',i,flush=True)
    finally:
        stop.set();thread.join(5)
    assert len(records)==4
    result={'environment':env,'steps':records,'global_verdict':'NOT_EVALUABLE: Colab archived only 30–53 N, 240–290 E cropped fields; no full-global baseline','crop_diagnostic_only':True}
    (ROOT/'report.json').write_text(json.dumps(result,indent=2))
    print('PROBE_DONE',flush=True)
if __name__=='__main__':main()
