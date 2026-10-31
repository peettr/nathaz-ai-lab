"""Residual-preserving single-feature interventions, bounded by task CU cutoff."""
import csv,json,os,sys,time,traceback
from pathlib import Path
T=time.time();R=Path('/content/l2612');PROG=R/'intervene_progress.jsonl';DATA=R/'interventions.jsonl'
# 16:57 EDT allocation; at 5.3 CU/h the 18.5-CU stop is ~20:26 EDT. Stop early with margin.
from datetime import datetime
from zoneinfo import ZoneInfo
DEADLINE=datetime(2026,10,26,20,15,tzinfo=ZoneInfo('America/New_York')).timestamp()
def log(**v):
 v['wall_s']=round(time.time()-T,2);s=json.dumps(v,default=str);print(s,flush=True)
 with PROG.open('a') as f:f.write(s+'\n')
def emit(v):
 with DATA.open('a') as f:f.write(json.dumps(v,default=str)+'\n');f.flush()
def timegate():
 if time.time()>DEADLINE:raise TimeoutError('owned GPU CU cutoff reached; incremental results retained')
try:
 import numpy as np,onnx,onnxruntime as ort,torch,xarray as xr
 from onnx import helper
 torch.set_num_threads(4)
 cohort=json.loads((R/'cohort_2021.json').read_text());corr=json.loads((R/'correlations.json').read_text());features=np.load(R/'features.npy')
 cands={}
 for p,rows in corr['candidates'].items():
  for r in rows:
   j=r['feature'];sc=abs(r['train_rho'] or 0)
   if j not in cands or sc>cands[j][0]:cands[j]=(sc,p)
 targets=sorted(cands,key=lambda j:(-cands[j][0],j))[:5]
 ck=torch.load(R/'sae.pt',map_location='cpu',weights_only=False)
 W=ck['state']['enc.weight'].numpy();bias=ck['state']['enc.bias'].numpy();D=ck['state']['dec.weight'].numpy().T
 mu=ck['mean'];std=ck['std'];K=ck['k']
 # On each storm compute only its local TopK activations, then apply decoder vector in raw hidden units.
 ds=xr.open_zarr('gs://weatherbench2/datasets/era5/1959-2022-full_37-6h-0p25deg_derived.zarr',storage_options={'token':'anon'},chunks=None)
 levs=[1000,925,850,700,600,500,400,300,250,200,150,100,50]
 def grab(r):
  s=ds.sel(time=np.datetime64(r['time']))
  up=np.stack([s[v].sel(level=levs).values for v in ['geopotential','specific_humidity','temperature','u_component_of_wind','v_component_of_wind']]).astype(np.float32)
  sf=np.stack([s[v].values for v in ['mean_sea_level_pressure','10m_u_component_of_wind','10m_v_component_of_wind','2m_temperature']]).astype(np.float32)
  if s['latitude'].values[0]<s['latitude'].values[-1]:up=up[...,::-1,:];sf=sf[...,::-1,:]
  return np.ascontiguousarray(up),np.ascontiguousarray(sf)
 track={};eligible_sids={r['sid'] for r in cohort}
 for basin in ('NA','WP'):
  with (R/f'ibtracs.{basin}.list.v04r01.csv').open(newline='') as f:
   for row in csv.DictReader(f):
    sid=row['SID'].strip();t=row['ISO_TIME'].strip()
    if sid in eligible_sids:
     try:track[(sid,t)]=(float(row['LAT']),float(row['LON']))
     except (ValueError,KeyError):pass
 from datetime import datetime,timedelta
 tests=[r for r in cohort if r['year']>=2021]
 selected=[]
 for r in tests:
  t=(datetime.fromisoformat(r['time'])+timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
  if (r['sid'],t) in track:selected.append((r,track[(r['sid'],t)]))
  if len(selected)>=30:break
 assert len(selected)==30,('insufficient+24 positions',len(selected))
 testidx={r['sid']:i for i,r in enumerate(cohort)}
 magnitude=np.mean(features[[testidx[r['sid']] for r,_ in selected]],axis=0)
 random=np.random.default_rng(2612);controls={}
 for j in targets:
  cand=[c for c in range(1536) if c!=j and .5*magnitude[j]<=magnitude[c]<=1.5*magnitude[j]]
  controls[j]=random.choice(cand,size=min(10,len(cand)),replace=False).tolist()
 log(stage='design',targets=targets,controls=controls,storms=[r['sid'] for r,_ in selected],cutoff=DEADLINE)
 model=onnx.load(str(R/'pangu_weather_24.onnx'));nodes=list(model.graph.node);k=3856
 producer={o:i for i,n in enumerate(nodes) for o in n.output};ini={i.name for i in model.graph.initializer}
 bound=sorted({x for n in nodes[k:] for x in n.input if x and x not in ini and producer.get(x,-1)<k})
 a=onnx.load(str(R/'pangu_weather_24.onnx'));del a.graph.output[:]
 a.graph.output.extend([helper.make_tensor_value_info(x,onnx.TensorProto.FLOAT,None) for x in bound])
 const=[x for x in bound if nodes[producer[x]].op_type=='Constant'];used=[x for x in bound if x not in const]
 assert used==['/b1/Add_26_output_0','/b1/Add_6_output_0']
 nodesb=[nodes[producer[x]] for x in const]+nodes[k:]
 graph=helper.make_graph(nodesb,'pangu_B',[helper.make_tensor_value_info(x,onnx.TensorProto.FLOAT,[1,131040,384] if i==0 else [1,521280,192]) for i,x in enumerate(used)],list(model.graph.output),[v for v in model.graph.initializer if any(v.name in node.input for node in nodesb)])
 b=helper.make_model(graph,opset_imports=model.opset_import);b.ir_version=model.ir_version
 opts=ort.SessionOptions();opts.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
 sA=ort.InferenceSession(a.SerializeToString(),opts,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
 # Segment A and segment B cannot coexist on this A100: precompute only 30
 # temporary boundary pairs on VM disk, release A, then initialize B.
 boundary_dir=R/'intervention_boundaries';boundary_dir.mkdir(exist_ok=True)
 for ni,(r,pos) in enumerate(selected):
  timegate();p0=boundary_dir/f'{ni:02d}_main.npy';p1=boundary_dir/f'{ni:02d}_skip.npy'
  if p0.exists() and p1.exists():continue
  up,sf=grab(r);mid_a=sA.run(used,{'input':up,'input_surface':sf})
  np.save(p0,mid_a[0]);np.save(p1,mid_a[1]);del up,sf,mid_a
  log(stage='boundary_saved',n=ni+1,sid=r['sid'])
 import gc
 del sA,a;gc.collect()
 sB=ort.InferenceSession(b.SerializeToString(),opts,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
 def indices(r):
  yy=np.where(abs(90-2*np.arange(91)-r['lat'])<=5)[0];xx=np.where(abs((2*np.arange(180)-r['lon']+180)%360-180)<=5)[0]
  return np.array([bb*91*180+y*180+x for bb in range(8) for y in yy for x in xx],dtype=np.int32)
 def score(outputs,pos):
  lat,lon=pos;y=np.arange(721);x=np.arange(1440)
  iy=y[abs(90-y*.25-lat)<=5];ix=x[abs((x*.25-lon+180)%360-180)<=5]
  msl=outputs[1][0,iy[:,None],ix[None,:]]
  u=outputs[1][1,iy[:,None],ix[None,:]];v=outputs[1][2,iy[:,None],ix[None,:]]
  return (float(np.min(msl)/100),float(np.max(np.hypot(u,v))))
 completed=set()
 if DATA.exists():
  for line in DATA.read_text().splitlines():
   v=json.loads(line);completed.add((v['sid'],v['feature'],v['alpha'],v['control']))
 for ni,(r,pos) in enumerate(selected):
  timegate();mid=[np.load(boundary_dir/f'{ni:02d}_main.npy'),np.load(boundary_dir/f'{ni:02d}_skip.npy')]
  assert all(np.isfinite(x).all() for x in mid)
  base=score(sB.run(None,dict(zip(used,mid))),pos)
  idx=indices(r);hidden=mid[0][0,idx].copy()
  raw=np.maximum(((hidden-mu)/std)@W.T+bias,0)
  pick=np.argpartition(raw,-K,axis=1)[:,-K:];z=np.zeros_like(raw);rr=np.arange(len(idx))[:,None];z[rr,pick]=raw[rr,pick]
  # alpha=1 pure decoder replacement (residual removed), separately scored.
  replaced=mid[0].copy();replaced[0,idx]=(z@D)*std+mu
  repl_score=score(sB.run(None,{used[0]:replaced,used[1]:mid[1]}),pos)
  emit({'sid':r['sid'],'feature':-1,'alpha':1.,'control':'pure_decoder','dmsl_hpa':repl_score[0]-base[0],'dwind_ms':repl_score[1]-base[1],'baseline_msl_hpa':base[0]})
  for j in targets:
   for control,feats in [('target',[j]),('matched',controls[j])]:
    for c in feats:
     for alpha in (0.,.5,1.5,2.) if control=='target' else (0.,2.):
      if (r['sid'],c,alpha,control) in completed:continue
      timegate();changed=mid[0].copy();changed[0,idx]+=((alpha-1.)*z[:,c,None]*(D[c]*std)[None,:]).astype(np.float32)
      pred=sB.run(None,{used[0]:changed,used[1]:mid[1]});out=score(pred,pos)
      emit({'sid':r['sid'],'feature':int(c),'reference':int(j),'alpha':alpha,'control':control,'dmsl_hpa':out[0]-base[0],'dwind_ms':out[1]-base[1],'divergent':bool(not np.isfinite(out).all() or abs(out[0]-base[0])>50)})
   # One fixed seeded same-norm random direction per feature/storm.
   d=(D[j]*std);direction=random.normal(size=384);direction=direction/np.linalg.norm(direction)*np.linalg.norm(d)
   for alpha in (0.,2.):
    timegate();changed=mid[0].copy();changed[0,idx]+=((alpha-1.)*z[:,j,None]*direction[None,:]).astype(np.float32)
    out=score(sB.run(None,{used[0]:changed,used[1]:mid[1]}),pos)
    emit({'sid':r['sid'],'feature':int(j),'reference':int(j),'alpha':alpha,'control':'random_direction','dmsl_hpa':out[0]-base[0],'dwind_ms':out[1]-base[1],'divergent':bool(not np.isfinite(out).all() or abs(out[0]-base[0])>50)})
  log(stage='storm_done',n=ni+1,sid=r['sid'],baseline=base)
 (R/'intervene.done').write_text('ok\n');log(stage='done',storms=len(selected))
except BaseException as e:
 log(stage='error',error=repr(e),traceback=traceback.format_exc());(R/'intervene.done').write_text('error\n');raise
