"""L26.12-03 post-skip merge topology and one-boundary parity gate. Colab only."""
import copy, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path
R=Path('/content/l2612-stepA'); R.mkdir(exist_ok=True)
def log(**kw):
 kw['time']=time.time(); print(json.dumps(kw),flush=True)
 with (R/'gate_progress.jsonl').open('a') as f:f.write(json.dumps(kw)+'\n')
try:
 import numpy as np, onnx, onnxruntime as ort, xarray as xr
 from onnx import helper
 W=R/'pangu_weather_24.onnx'; url='https://sites.ecmwf.int/repository/ai-models/test-data/pangu-weather/pangu_weather_24.onnx'
 if not W.exists():subprocess.run(['wget','-q','--show-progress','-O',str(W),url],check=True)
 digest=hashlib.file_digest(W.open('rb'),'sha256').hexdigest();log(stage='weights',bytes=W.stat().st_size,sha256=digest)
 m=onnx.load(str(W));nodes=list(m.graph.node);n=len(nodes);producer={o:i for i,node in enumerate(nodes) for o in node.output}; init={v.name for v in m.graph.initializer}; inputs={v.name for v in m.graph.input}; outs=[v.name for v in m.graph.output]
 main='/b1/Add_26_output_0';skip='/b1/Add_6_output_0';assert main in producer and skip in producer
 def boundary(k):
  return sorted({x for node in nodes[k:] for x in node.input if x and x not in init and producer.get(x,-1)<k}|{x for x in outs if producer.get(x,-1)<k})
 # Propagate both dependencies through topologically ordered graph.
 deps={main:1,skip:2}; merge=[]
 for i,node in enumerate(nodes):
  flag=0
  for x in node.input:flag|=deps.get(x,0)
  if flag==3 and not merge:merge.append((i,node.op_type,list(node.input),list(node.output)))
  for x in node.output:deps[x]=flag | (1 if x==main else 0) | (2 if x==skip else 0)
 assert merge,'no join of skip and trunk'
 merge_i,merge_op,merge_in,merge_out=merge[0];log(stage='first_merge',index=merge_i,op=merge_op,inputs=merge_in,outputs=merge_out)
 candidates=[]
 for k in range(merge_i+1,n):
  b=boundary(k); used=[x for x in b if x not in inputs and (x not in producer or nodes[producer[x]].op_type!='Constant')]
  if len(used)==1 and deps.get(used[0])==3 and not (set(b)&inputs):candidates.append((k,used[0],b))
  if candidates and k>merge_i+250:break
 assert candidates,'No one-input boundary after merge; STOP without SAE'
 k,cut,bound=candidates[0]; const=[x for x in bound if x in producer and nodes[producer[x]].op_type=='Constant']; used=[x for x in bound if x not in const]
 log(stage='cut',index=k,cut=cut,boundary=bound,constants=const,nonconstant=used,after=nodes[k].op_type)
 assert used==[cut] and cut not in inputs
 ds=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
 s=ds.sel(time=np.datetime64('2019-09-01T12:00'));levs=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
 up=np.stack([s[v].sel(level=levs).values for v in ['geopotential','specific_humidity','temperature','u_component_of_wind','v_component_of_wind']]).astype('float32');sf=np.stack([s[v].values for v in ['mean_sea_level_pressure','10m_u_component_of_wind','10m_v_component_of_wind','2m_temperature']]).astype('float32')
 if s['latitude'].values[0]<s['latitude'].values[-1]:up=up[...,::-1,:];sf=sf[...,::-1,:]
 feeds={list(inputs)[0]:up,list(inputs)[1]:sf}
 # Do not trust unordered set for input binding.
 feeds={m.graph.input[0].name:np.ascontiguousarray(up),m.graph.input[1].name:np.ascontiguousarray(sf)}
 opt=ort.SessionOptions();opt.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
 prov=['CUDAExecutionProvider','CPUExecutionProvider'];full_s=ort.InferenceSession(str(W),opt,providers=prov); full=full_s.run(None,feeds);del full_s
 A=copy.deepcopy(m);del A.graph.output[:];A.graph.output.extend([helper.make_tensor_value_info(cut,onnx.TensorProto.FLOAT,None)])
 sa=ort.InferenceSession(A.SerializeToString(),opt,providers=prov);mid=sa.run([cut],feeds)[0];del sa,A
 Bnodes=[nodes[producer[x]] for x in const]+nodes[k:]
 graph=helper.make_graph(Bnodes,'pangu_merge_B',[helper.make_tensor_value_info(cut,helper.np_dtype_to_tensor_dtype(mid.dtype),list(mid.shape))],list(m.graph.output),[v for v in m.graph.initializer if any(v.name in node.input for node in Bnodes)])
 B=helper.make_model(graph,opset_imports=m.opset_import);B.ir_version=m.ir_version
 sb=ort.InferenceSession(B.SerializeToString(),opt,providers=prov);pred=sb.run(None,{cut:mid});rel={name:float(np.max(np.abs(a-b))/max(np.max(np.abs(b)),1e-30)) for name,a,b in zip(outs,pred,full)}
 out={'weight_sha256':digest,'first_merge':{'index':merge_i,'op':merge_op,'inputs':merge_in,'outputs':merge_out},'cut_index':k,'cut':cut,'boundary':bound,'constants':const,'nonconstant':used,'shape':list(mid.shape),'rel_maxdiff':rel,'pass':all(v<1e-4 for v in rel.values()),'nodes':n,'source':'ECMWF Pangu Weather 24h ONNX; WeatherBench2 ERA5 derived zarr'}
 (R/'gate.json').write_text(json.dumps(out,indent=2));log(stage='parity',result=out)
 (R/'gate.done').write_text('ok' if out['pass'] else 'fail')
except BaseException as exc:
 log(stage='error',error=repr(exc),traceback=traceback.format_exc());(R/'gate.done').write_text('error');raise
