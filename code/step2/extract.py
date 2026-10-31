"""One intensity-prioritized initial time per storm; kept entirely on Colab."""
import json,os,sys,time,traceback
from pathlib import Path
T=time.time(); R=Path('/content/l2612'); prog=R/'extract_progress.jsonl'
def log(**v):
 v['wall_s']=round(time.time()-T,2);line=json.dumps(v,default=str);print(line,flush=True)
 with prog.open('a') as f:f.write(line+'\n')
try:
 import numpy as np,onnx,onnxruntime as ort,xarray as xr
 from onnx import helper
 m=json.loads((R/'manifest.json').read_text());by_sid={}
 for r in m['records']:
  if r['sid'] not in by_sid or (r['wind_kt'],r['time'])>(by_sid[r['sid']]['wind_kt'],by_sid[r['sid']]['time']):by_sid[r['sid']]=r
 records=sorted(by_sid.values(),key=lambda r:(r['year']>=2021,r['sid']))
 assert len({r['sid'] for r in records})==len(records)
 log(stage='start',n=len(records),train=sum(r['year']<=2020 for r in records),test=sum(r['year']>=2021 for r in records))
 prior={}
 for i,r in enumerate(m['records'][:50]):prior[(r['sid'],r['time'])]=R/f'activation_{i:04d}.npz'
 ds=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
 levs=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
 def grab(r):
  s=ds.sel(time=np.datetime64(r['time']))
  up=np.stack([s[v].sel(level=levs).values for v in ['geopotential','specific_humidity','temperature','u_component_of_wind','v_component_of_wind']]).astype(np.float32)
  sf=np.stack([s[v].values for v in ['mean_sea_level_pressure','10m_u_component_of_wind','10m_v_component_of_wind','2m_temperature']]).astype(np.float32)
  if s['latitude'].values[0]<s['latitude'].values[-1]:up=up[...,::-1,:];sf=sf[...,::-1,:]
  return np.ascontiguousarray(up),np.ascontiguousarray(sf)
 def indices(r):
  y=np.where(abs(90-2*np.arange(91)-r['lat'])<=5)[0]
  x=np.where(abs((2*np.arange(180)-r['lon']+180)%360-180)<=5)[0]
  return np.array([b*91*180+yy*180+xx for b in range(8) for yy in y for xx in x],dtype=np.int32)
 model=onnx.load(str(R/'pangu_weather_24.onnx'));nodes=list(model.graph.node);k=3856
 producer={o:i for i,n in enumerate(nodes) for o in n.output};ini={i.name for i in model.graph.initializer}
 bound=sorted({x for n in nodes[k:] for x in n.input if x and x not in ini and producer.get(x,-1)<k})
 a=onnx.load(str(R/'pangu_weather_24.onnx'));del a.graph.output[:]
 a.graph.output.extend([helper.make_tensor_value_info(x,onnx.TensorProto.FLOAT,None) for x in bound])
 opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
 sess=ort.InferenceSession(a.SerializeToString(),opts,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
 # Validate flattening layout empirically using a localized input perturbation, before extracting windows.
 up,sf=grab(records[0]);main='/b1/Add_26_output_0';original=sess.run([main],{'input':up,'input_surface':sf})[0][0]
 probe_lat,probe_lon=20.,130.; iy=int(round((90-probe_lat)/.25));ix=int(round(probe_lon/.25));sf2=sf.copy();sf2[0,iy-2:iy+3,ix-2:ix+3]+=2000.
 pert=sess.run([main],{'input':up,'input_surface':sf2})[0][0]
 diff=np.linalg.norm(pert-original,axis=1).reshape(8,91,180)
 peaks=[]
 for b in range(8):
  y,x=np.unravel_index(np.argmax(diff[b]),diff[b].shape)
  peaks.append({'block':b,'row':int(y),'col':int(x),'lat_guess':90-2*int(y),'lon_guess':2*int(x),'peak':float(diff[b,y,x])})
 probe={'input':{'lat':probe_lat,'lon':probe_lon,'field':'surface MSL','perturbation_Pa':2000,'size_grid':5},'peaks':peaks,'hypothesis':'flatten b*91*180+row*180+col; guessed 2 degree token spacing'}
 (R/'layout_probe.json').write_text(json.dumps(probe,indent=2));log(stage='layout',peaks=peaks)
 del up,sf,sf2,original,pert,diff
 # Stop rather than silently extract the wrong geographic window.
 assert any(abs(p['lat_guess']-probe_lat)<=4 and abs((p['lon_guess']-probe_lon+180)%360-180)<=4 for p in peaks), 'layout hypothesis disproved'
 out=R/'windows';out.mkdir(exist_ok=True)
 for i,r in enumerate(records):
  path=out/f'{i:04d}.npz'
  if path.exists():continue
  old=prior.get((r['sid'],r['time']))
  if old and old.exists():
   import shutil;shutil.copyfile(old,path);log(stage='reuse',n=i+1,sid=r['sid'])
  else:
   t=time.time();up,sf=grab(r)
   vals=sess.run([main],{'input':up,'input_surface':sf})[0][0];idx=indices(r)
   np.savez_compressed(path,window=vals[idx].astype(np.float16),indices=idx)
   del up,sf,vals;log(stage='activation',n=i+1,sid=r['sid'],time=r['time'],tokens=[已隐去],seconds=round(time.time()-t,2),bytes=path.stat().st_size)
  if i%10==0:(R/'extract_count.json').write_text(json.dumps({'completed':i+1,'total':len(records)}))
 (R/'cohort.json').write_text(json.dumps(records,indent=1));(R/'extract.done').write_text('ok\n');log(stage='done',n=len(records))
except BaseException as e:
 log(stage='error',error=repr(e),traceback=traceback.format_exc());(R/'extract.done').write_text('error\n');raise
