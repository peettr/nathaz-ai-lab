"""L26.19-01j: bounded Colab L4 fp32 native inference in training container."""
import sys,time,json,pathlib,subprocess,traceback,hashlib,types,importlib.util
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v9'); R.mkdir(exist_ok=True); O=R/'out';O.mkdir(exist_ok=True)
START=time.monotonic(); ALLOC=float(pathlib.Path('/content/allocated_v9.txt').read_text()); RATE=2.10; CAP=1.5*3600/RATE; MARGIN=180

def log(*a):print(*a,flush=True)
def save_json(name,obj): (O/name).write_text(json.dumps(obj,indent=2,default=str))
def run(*a):log('RUN',a);subprocess.run(a,check=True)
def remaining():return CAP-(time.time()-ALLOC)-MARGIN
try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash,mdtraj;from open3d.ml.torch.ops import radius_search;print("IMPORT_OK",torch.__version__,open3d.__version__,flush=True)')
 import torch,yaml
 from huggingface_hub import hf_hub_download
 repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo));run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e');sys.path.insert(0,str(repo))
 from TrajDataset import load_npz_sample_by_data
 hf='wclw1021/WorldParticle';sample=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/66/66.npz',local_dir=str(R/'hf'));wt=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 ck=torch.load(wt,map_location='cpu',weights_only=True); del ck
 data=load_npz_sample_by_data('fancy_fluid',sample,frame_start=0,frame_end=2)
 box=data['box'].numpy();bn=data['box_feats'].numpy();lo=np.array([-2.,0.,-1.],np.float32);hi=np.array([2.,2.,1.],np.float32)
 # Outermost planes are identified by coordinates, not normals; retain all their points, remove all interior objects.
 onplane=np.any(np.isclose(box,lo[None],atol=1e-5)|np.isclose(box,hi[None],atol=1e-5),axis=1)
 wall=box[onplane];norm=bn[onplane]
 dx=.07;xs=np.arange(lo[0]+dx/2,hi[0],dx,dtype=np.float32);zs=np.arange(lo[2]+dx/2,hi[2],dx,dtype=np.float32);ys=np.float32(.035)+np.arange(5,dtype=np.float32)*np.float32(.07)
 pos=np.stack(np.meshgrid(xs,ys,zs,indexing='ij'),axis=-1).reshape(-1,3);vel=np.zeros_like(pos);N=len(pos)
 # Raw physical features copied from training sample; original loader transforms them; override its float32 roundoff to prescribed zero.
 raw=np.repeat(np.array([[.026010504,.324179202,1000.]],np.float32),N,axis=0)
 local=R/'input'/'G0';local.mkdir(parents=True,exist_ok=True)
 np.savez_compressed(local/'G0.npz',position=pos[None],velocity=vel[None],feats=raw,box=wall,box_feats=norm)
 orig=load_npz_sample_by_data('fancy_fluid',str(local/'G0.npz'),frame_start=0,frame_end=2)
 assert tuple(orig['positions'].shape)==(1,N,3) and len(wall)>0
 import inference as unused
 source=(repo/'inference.py').read_text();assert source.count('torch.load(args.checkpoint, map_location=device)')==1 and source.count('with autocast(dtype=torch.bfloat16):')==1
 source=source.replace('torch.load(args.checkpoint, map_location=device)','torch.load(args.checkpoint, map_location=device, weights_only=True)').replace('with autocast(dtype=torch.bfloat16):','with autocast(enabled=False):')
 (R/'inference_fp32_v9.py').write_text(source)
 spec=importlib.util.spec_from_file_location('author_fp32_v9',R/'inference_fp32_v9.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
 loader=author.load_npz_sample_by_data
 def zero_feature_loader(*args,**kwargs):
  s=loader(*args,**kwargs);s['feats'].zero_();return s
 author.load_npz_sample_by_data=zero_feature_loader
 cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['frame_end']=2
 sha=hashlib.sha256()
 with open(wt,'rb') as f:
  for chunk in iter(lambda:f.read(8<<20),b''):sha.update(chunk)
 setup=dict(gpu=torch.cuda.get_device_name(),torch=torch.__version__,weight_sha256=sha.hexdigest(),weights_only=True,sample=66,wall_count=len(wall),removed_count=len(box)-len(wall),source_box_count=len(box),wall_coordinate_min=wall.min(0).tolist(),wall_coordinate_max=wall.max(0).tolist(),fluid_count=N,grid_shape=[len(xs),len(ys),len(zs)],initial_y=[float(ys[0]),float(ys[-1])],initial_velocity=0,raw_feats=raw[0].tolist(),loader_feats_before_override=float(orig['feats'][0,0]),feats_used=0.,wall_normals_distribution=[float(np.mean(np.sum(norm*(wall-(lo+hi)/2),axis=1)>0))],precision='fp32 autocast disabled',force='author external_force=None')
 save_json('setup_v9.json',setup);log('SETUP',setup)
 def args_for(out,steps):return types.SimpleNamespace(data_dir=str(R/'input'),sample='G0',checkpoint=str(wt),output_dir=str(out),start=0,end=2,dt=1,num_steps=steps)
 pilot=R/'pilot';pilot.mkdir(exist_ok=True);t=time.monotonic();author.inference(args_for(pilot,100),dict(cfg));t100=time.monotonic()-t
 gate=dict(pilot_100_s=t100,s_per_step=t100/100,projected_full_s=2000*t100/100*1.10,remaining_s=remaining(),elapsed_s=time.monotonic()-START,rate_cu_h=RATE)
 save_json('gate_v9.json',gate);log('GATE',gate)
 if gate['projected_full_s']>gate['remaining_s']:raise RuntimeError('budget gate: projected 2000 steps exceeds remaining 1.5 CU')
 full=R/'full';full.mkdir(exist_ok=True);t=time.monotonic();author.inference(args_for(full,2000),dict(cfg));wall_s=time.monotonic()-t
 with np.load(full/'outcomes'/'npz'/'G0'/'G0_0_2.npz') as z:p=z['position'];v=z['velocity']
 if p.shape!=(2001,N,3) or v.shape!=p.shape:raise ValueError(('unexpected output shape',p.shape,v.shape))
 rows=[];samples=[];steps=[];first=None;edges=np.linspace(lo[0],hi[0],17)
 for k,(x,velocity) in enumerate(zip(p,v)):
  inside=np.all((x>=lo)&(x<=hi),axis=1);outside=int((~inside).sum())
  if outside and first is None:first=k
  if k%50==0 or k==100 or k==1:
   inside_x=x[inside];tops=[]
   for a,b in zip(edges[:-1],edges[1:]):
    group=inside_x[(inside_x[:,0]>=a)&(inside_x[:,0]<b)]
    if len(group):tops.append(float(group[:,1].max()))
   energy=float(.5*.324179202*np.sum(velocity.astype(np.float64)**2))
   rows.append((k,k*.01,outside,float(x[:,1].mean()),energy,float(np.std(tops)) if len(tops)>1 else np.nan,len(tops)))
  if k%10==0:steps.append(k);samples.append(x.astype(np.float32))
 a=np.asarray(rows,float)
 with (O/'G0_v9.npz').open('xb') as f:np.savez_compressed(f,metric_steps=a[:,0].astype(np.int32),metric_time=a[:,1],outside=a[:,2].astype(np.int32),mean_y=a[:,3],kinetic_energy=a[:,4],surface_std=a[:,5],nonempty_bins=a[:,6].astype(np.int32),sample_steps=np.asarray(steps),position=np.asarray(samples,dtype=np.float32),wall=wall,wall_normals=norm,initial_position=pos)
 with (O/'settled_G0_v9.npz').open('xb') as f:np.savez_compressed(f,position=p[-1],velocity=v[-1],step=2000,time_s=20.,box=wall,box_feats=norm,feats=0.)
 late=a[(a[:,0]>=1500)&(a[:,0]<=2000),5];ten=a[(a[:,0]>=1000)&(a[:,0]<=2000)];slope=float(np.polyfit(ten[:,1],ten[:,4],1)[0]);selected=a[np.isin(a[:,0],[0,1,50,100,500,1000,1500,2000])].tolist()
 result=dict(first_outside_step=first,late_surface_std_mean_m=float(np.nanmean(late)) if np.any(np.isfinite(late)) else None,late_defined_count=int(np.isfinite(late).sum()),ke_10_20_max_J=float(ten[:,4].max()),ke_10_20_slope_J_per_s=slope,ke_1s_J=float(a[a[:,0]==100,4][0]),selected=selected,full_wall_s=wall_s,metric_count=len(rows),samples=len(steps),elapsed_s=time.monotonic()-START)
 save_json('results_v9.json',result);log('RESULT',result)
except BaseException as e:
 traceback.print_exc();save_json('failure_v9.json',dict(error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-START))
finally:save_json('done_v9',dict(elapsed_s=time.monotonic()-START))
