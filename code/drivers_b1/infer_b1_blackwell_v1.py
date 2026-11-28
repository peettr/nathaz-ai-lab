#!/usr/bin/env python3
"""D-X2 production: nine GC37 cycles on qualified Blackwell, one cycle at a time."""
import hashlib, json, os, pathlib, subprocess, sys, threading, time
import numpy as np
import xarray as xr
import jax
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'graphcast_source'/'NCEP'))
sys.path.insert(0, str(ROOT/'graphcast_source'))
sys.path.insert(0, str(ROOT))
from run_graphcast import GraphCastModel
from graphcast import rollout
from check_gc37x_inputs_v2 import check
INPUT = pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/inputs_N1N3N4_v1')
PARAM = ROOT/'weights'/'params'/'GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz'
EXPECTED = '4e8cf600f3f402ebb430483e782b94648cef57bb757dec24dd7b11760d3fbacc'
FIELDS = ('2m_temperature','10m_u_component_of_wind','10m_v_component_of_wind','mean_sea_level_pressure','geopotential','temperature','u_component_of_wind','v_component_of_wind','specific_humidity')

def sha(path):
    with open(path,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def gpu_monitor(stop,samples):
    while not stop.wait(.5):
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True)
        try: samples.append(int(p.stdout.splitlines()[0]))
        except (ValueError,IndexError): pass

def run_one(event,lead,cycle,nsteps,bbox):
    src=INPUT/f'input_{cycle}_zero.nc'
    assert src.is_file(),src
    out=ROOT/'raw'/event/cycle
    assert not out.exists(),('existing cycle: never overwrite/recompute',out)
    gate=check(src,'graphcast')
    gate['source_sha256']=sha(src)
    gatepath=ROOT/'gates'/f'{event}_{lead}_{cycle}.json'
    assert not gatepath.exists(),gatepath
    gatepath.write_text(json.dumps(gate,indent=2)+'\n')
    assert gate['passed'],gate['errors']
    out.mkdir(parents=True)
    model=GraphCastModel(str(ROOT/'weights'),str(src),str(out),37,nsteps)
    model.load_pretrained_model()
    ds=xr.load_dataset(src)
    old=ds.time.values.astype('timedelta64[ns]')
    assert np.array_equal(old,np.array([-6,0])*np.timedelta64(1,'h'))
    start=ds.datetime.values[0,0]
    ds=ds.reindex(time=np.arange(-1,nsteps+1)*np.timedelta64(6,'h'))
    ds['datetime']=(('batch','time'),np.asarray([start+np.arange(nsteps+2)*np.timedelta64(6,'h')]))
    model.current_batch=ds;model.extract_inputs_targets_forcings()
    for kind,dataset in [('inputs',model.inputs),('forcings',model.forcings)]:
        assert all(np.isfinite(v.values).all() for v in dataset.data_vars.values()),kind
    model.load_normalization_stats();model.load_model()
    la0,la1=bbox['crop_lat'];lo0,lo1=[360+x for x in bbox['crop_lon_west_neg']]
    samples=[];stop=threading.Event();t=threading.Thread(target=gpu_monitor,args=(stop,samples),daemon=True);t.start()
    records=[];begin=time.monotonic()
    try:
        gen=rollout.chunked_prediction_generator(model.model,rng=jax.random.PRNGKey(0),inputs=model.inputs,targets_template=model.targets*np.nan,forcings=model.forcings,num_steps_per_chunk=1)
        for i in range(1,nsteps+1):
            tick=time.monotonic();pred=jax.device_get(next(gen));wall=time.monotonic()-tick
            nan={k:int(np.count_nonzero(~np.isfinite(v.values))) for k,v in pred.data_vars.items()}
            assert pred.level.size==37 and not any(nan.values()),(event,cycle,i,nan)
            reg=pred.sel(lat=slice(la0,la1),lon=slice(lo0,lo1))
            assert reg.sizes['lat']==int(round((la1-la0)*4))+1 and reg.sizes['lon']==int(round((lo1-lo0)*4))+1
            arr={f'reg_{name}':np.asarray(reg[name].values).squeeze().astype('float32') for name in FIELDS}
            arr.update(reg_lat=reg.lat.values,reg_lon=reg.lon.values,reg_level=reg.level.values)
            np.savez_compressed(out/f'step_{i:02d}.npz',**arr)
            record={'step':i,'forecast_h':6*i,'wall_seconds':wall,'nan':nan,'level_hpa':pred.level.values.tolist(),'peak_vram_mib':max(samples) if samples else None}
            (out/f'step_{i:02d}.json').write_text(json.dumps(record,indent=2)+'\n')
            records.append(record)
            print('STEP_DONE',event,cycle,i,flush=True)
    finally:
        stop.set();t.join(5)
    summary={'event':event,'lead':lead,'cycle':cycle,'steps':nsteps,'records':records,'total_wall_seconds':time.monotonic()-begin,'peak_vram_mib':max(samples) if samples else None,'source_sha256':gate['source_sha256'],'bbox':bbox}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    manifest=[]
    for p in sorted(out.glob('step_*.npz')): manifest.append(f'{sha(p)}  {p.name}')
    assert len(manifest)==nsteps
    (out/'SHA256SUMS').write_text('\n'.join(manifest)+'\n')
    (out/'RAW_READY').write_text(f'{event} {cycle} {nsteps}\n')
    print('RAW_READY',event,cycle,nsteps,flush=True)

def main():
    assert sha(PARAM)==EXPECTED
    assert any(d.platform=='gpu' for d in jax.devices())
    config=json.loads((ROOT/'event_times_bbox_gc37x.json').read_text())['events']
    planned=[]
    for event in ('N1','N3','N4'):
        for lead in ('24h','48h','72h'):
            spec=config[event]['leads'][lead];cycle=spec['t0'].replace('-','').replace(':','').replace('T','')[:10]
            planned.append((event,lead,cycle,int(spec['length_h']//6),config[event]['domain']))
    assert len(planned)==9
    (ROOT/'gates').mkdir(exist_ok=True)
    for args in planned:
        run_one(*args)
    print('SUCCESS_ALL',flush=True)
if __name__=='__main__':main()
