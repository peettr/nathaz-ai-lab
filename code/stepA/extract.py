"""Extract one post-merge storm window per frozen cohort SID on Colab."""
import json,time,traceback
from pathlib import Path
import numpy as np,onnx,onnxruntime as ort,xarray as xr
from onnx import helper
R=Path('/content/l2612-stepA'); P=R/'extract_progress.jsonl';T=time.time()
def log(**v):
 v['elapsed_s']=round(time.time()-T,2);print(json.dumps(v),flush=True)
 with P.open('a') as f:f.write(json.dumps(v)+'\n')
try:
 gate=json.loads((R/'gate.json').read_text());assert gate['pass'];name=gate['cut'];shape=gate['shape'];records=json.loads((R/'cohort_2021.json').read_text());assert len(records)==321
 assert len(shape)==3 and shape[0]==1 and shape[1]%8==0,(name,shape)
 resolutions=[(91,180),(181,360),(361,720),(721,1440)]
 matches=[(y,x) for y,x in resolutions if shape[1]==8*y*x];assert len(matches)==1,(name,shape)
 ny,nx=matches[0];latstep=180/(ny-1);lonstep=360/nx
 def indices(r):
  ys=np.where(abs(90-latstep*np.arange(ny)-r['lat'])<=5)[0];xs=np.where(abs((lonstep*np.arange(nx)-r['lon']+180)%360-180)<=5)[0]
  return np.array([b*ny*nx+y*nx+x for b in range(8) for y in ys for x in xs],np.int32)
 ds=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
 levs=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
 def grab(r):
  s=ds.sel(time=np.datetime64(r['time']));up=np.stack([s[v].sel(level=levs).values for v in ['geopotential','specific_humidity','temperature','u_component_of_wind','v_component_of_wind']]).astype(np.float32)
  sf=np.stack([s[v].values for v in ['mean_sea_level_pressure','10m_u_component_of_wind','10m_v_component_of_wind','2m_temperature']]).astype(np.float32)
  if s['latitude'].values[0]<s['latitude'].values[-1]:up=up[...,::-1,:];sf=sf[...,::-1,:]
  return np.ascontiguousarray(up),np.ascontiguousarray(sf)
 m=onnx.load(str(R/'pangu_weather_24.onnx'));del m.graph.output[:];m.graph.output.extend([helper.make_tensor_value_info(name,onnx.TensorProto.FLOAT,None)])
 opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
 session=ort.InferenceSession(m.SerializeToString(),opts,providers=['CUDAExecutionProvider','CPUExecutionProvider']);feednames=[x.name for x in m.graph.input]
 # Validate spatial flattening on a localized MSL perturbation.
 up,sf=grab(records[0]);orig=session.run([name],dict(zip(feednames,[up,sf])))[0][0];sf2=sf.copy();iy=int(round((90-20)/.25));ix=int(round(130/.25));sf2[0,iy-2:iy+3,ix-2:ix+3]+=2000
 pert=session.run([name],dict(zip(feednames,[up,sf2])))[0][0];diff=np.linalg.norm(pert-orig,axis=1).reshape(8,ny,nx);peaks=[]
 for b in range(8):
  y,x=np.unravel_index(np.argmax(diff[b]),diff[b].shape);peaks.append({'block':b,'row':int(y),'col':int(x),'lat':90-y*latstep,'lon':x*lonstep,'peak':float(diff[b,y,x])})
 (R/'layout_probe.json').write_text(json.dumps({'ny':ny,'latstep':latstep,'lonstep':lonstep,'peaks':peaks,'source':'WeatherBench2 ERA5 MSL +2000 Pa at 20N,130E'},indent=2))
 log(stage='layout',peaks=peaks);assert any(abs(p['lat']-20)<=2*latstep and abs(p['lon']-130)<=4 for p in peaks),'layout disproved: STOP'
 del up,sf,sf2,orig,pert,diff
 out=R/'windows';out.mkdir(exist_ok=True)
 for i,r in enumerate(records):
  p=out/f'{i:04d}.npz'
  if p.exists():continue
  start=time.time();up,sf=grab(r);val=session.run([name],dict(zip(feednames,[up,sf])))[0][0];idx=indices(r)
  np.savez_compressed(p,window=val[idx].astype('float16'),indices=idx);log(stage='activation',n=i+1,sid=r['sid'],tokens=[已隐去],seconds=round(time.time()-start,2));del up,sf,val
  if i==49:(R/'first50.json').write_text(json.dumps({'seconds':time.time()-T,'records':50,'all':len(records)}))
 (R/'extract.done').write_text('ok');log(stage='done',count=len(records))
except BaseException as e:
 log(stage='error',error=repr(e),traceback=traceback.format_exc());(R/'extract.done').write_text('error');raise
