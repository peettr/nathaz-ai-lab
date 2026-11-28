"""L26.19-01h bounded author-function long-rollout checks; remote only."""
import sys, time, json, pathlib, subprocess, hashlib, traceback, shutil, types, gc
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v7'); R.mkdir(exist_ok=True); O=R/'out'; O.mkdir(exist_ok=True)
START=time.monotonic(); RATE=2.10; CAP=1.4*3600/RATE; MARGIN=220

def log(*x): print(*x,flush=True)
def write(name,obj): (O/name).write_text(json.dumps(obj,indent=2,default=str))
def run(*args): log('RUN',args); subprocess.run(args,check=True)
def stage(name,fn):
 try:
  ret=fn();write(name+'_v7.json',dict(status='ok',result=ret));log(name,'OK');return ret
 except BaseException as e:
  traceback.print_exc();write(name+'_v7.json',dict(status='failed',error=repr(e),trace=traceback.format_exc()));log(name,'FAILED',repr(e));return None

def remaining(): return CAP-(time.monotonic()-START)-MARGIN
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for x in iter(lambda:f.read(8<<20),b''):h.update(x)
 return h.hexdigest()

try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash,mdtraj;from open3d.ml.torch.ops import radius_search;print("IMPORT_OK",torch.__version__,open3d.__version__,flush=True)')
 import torch,yaml
 from huggingface_hub import hf_hub_download
 repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo));run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e');sys.path.insert(0,str(repo))
 # Retain the original inference function's logic; only safe load substitution, with a second copy for fp32.
 source=(repo/'inference.py').read_text(); assert source.count('torch.load(args.checkpoint, map_location=device)')==1
 safe=source.replace('torch.load(args.checkpoint, map_location=device)','torch.load(args.checkpoint, map_location=device, weights_only=True)')
 assert safe.count('with autocast(dtype=torch.bfloat16):')==1
 (R/'inference_safe_v7.py').write_text(safe)
 fp32=safe.replace('with autocast(dtype=torch.bfloat16):','with autocast(enabled=False):')
 (R/'inference_fp32_v7.py').write_text(fp32)
 import importlib.util
 def import_script(p,name):
  spec=importlib.util.spec_from_file_location(name,p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
 author=import_script(R/'inference_safe_v7.py','author_v7');full32=import_script(R/'inference_fp32_v7.py','fp32_v7')
 sample_path=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename='fancy_fluid/dataset/66/66.npz',local_dir=str(R/'hf'))
 wt=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 ck=torch.load(wt,map_location='cpu',weights_only=True);del ck
 cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['frame_end']=600
 from TrajDataset import load_npz_sample_by_data
 data=load_npz_sample_by_data('fancy_fluid',sample_path,frame_start=0,frame_end=600)
 box=data['box'].numpy(); bounds=(box.min(0),box.max(0)); sample_data=data['positions'].numpy(); n=len(sample_data[0]); mass=float(0.324179202)
 write('setup_v7.json',dict(gpu=torch.cuda.get_device_name(),torch=torch.__version__,weight_sha256=digest(wt),weights_only=True,sample=66,frames=len(sample_data),particles=n,bounds=[x.tolist() for x in bounds],modifications=['safe weights_only=True load only in S1','disabled inner bf16 autocast only in S2']))
 # Original output is ephemeral in VM; extract only metrics and decimated positions before final pull.
 def analyze(tag,out):
  pth=out/'outcomes'/'npz'/'66'/'66_0_600.npz'
  with np.load(pth) as z:
   p=z['position'];v=z['velocity']
  if p.shape[0]!=2001: raise ValueError(('not_2001',p.shape))
  lo,hi=bounds;rows=[];sample_pos=[];sample_steps=[];first=None
  for k in range(2001):
   x=p[k];vel=v[k];inside=np.all((x>=lo)&(x<=hi),axis=1);outside=int((~inside).sum())
   if first is None and outside:first=k
   if k%50==0 or k==1:
    y=x[inside];edges=np.linspace(lo[0],hi[0],17);tops=[]
    for a,b in zip(edges[:-1],edges[1:]):
     bucket=y[(y[:,0]>=a)&(y[:,0]<b)];
     if len(bucket):tops.append(float(bucket[:,1].max()))
    rows.append((k,k*float(cfg['timestep']),outside,float(x[:,1].mean()),float(.5*mass*np.sum(vel.astype(np.float64)**2)),float(np.std(tops)) if len(tops)>1 else np.nan))
   if k%10==0:sample_steps.append(k);sample_pos.append(x.astype(np.float32))
  a=np.asarray(rows,dtype=float)
  with (O/(tag+'_v7.npz')).open('xb') as f:
   np.savez_compressed(f,metric_steps=a[:,0].astype(np.int32),metric_time=a[:,1],outside=a[:,2].astype(np.int32),mean_y=a[:,3],kinetic_energy=a[:,4],surface_std=a[:,5],sample_steps=np.asarray(sample_steps),position=np.asarray(sample_pos,dtype=np.float32))
  result=dict(first_outside_step=first,metric_count=len(rows),sample_count=len(sample_steps),selected=[r for r in rows if int(r[0]) in (0,50,100,500,600,1000,1500,2000)],npz_size=(O/(tag+'_v7.npz')).stat().st_size)
  write(tag+'_summary_v7.json',result);log('RESULT',tag,result);return result
 def run_author(tag,mod):
  out=R/tag;out.mkdir(exist_ok=True)
  args=types.SimpleNamespace(data_dir=str(R/'hf'/'fancy_fluid'/'dataset'),sample='66',checkpoint=str(wt),output_dir=str(out),start=0,end=600,dt=1,num_steps=100)
  t0=time.monotonic();mod.inference(args,dict(cfg));pilot=time.monotonic()-t0
  speed=pilot/100; projection=2000*speed*1.12;left=remaining()
  write(tag+'_gate_v7.json',dict(pilot_100_s=pilot,s_per_step=speed,projected_full_s_12pct_margin=projection,remaining_s=left,elapsed_s=time.monotonic()-START))
  if projection>left:raise RuntimeError(f'{tag} full 2000 step projected {projection:.1f}s > remaining {left:.1f}s')
  # Different output root ensures pilot is never overwritten.
  full=R/(tag+'_full');full.mkdir(exist_ok=True);args.output_dir=str(full);args.num_steps=2000
  t1=time.monotonic();mod.inference(args,dict(cfg));wall=time.monotonic()-t1
  result=analyze(tag,full);result.update(pilot_s=pilot,full_wall_s=wall);return result
 s1=stage('S1',lambda:run_author('S1',author))
 del author;gc.collect();torch.cuda.empty_cache()
 s2=stage('S2',lambda:run_author('S2',full32))
 del full32;gc.collect();torch.cuda.empty_cache()
 # Public repository currently lists checkpoint/config only: no sample under deep_lagrange_dataset.
 def s3():
  paths=[]
  from huggingface_hub import list_repo_tree
  for item in list_repo_tree('wclw1021/WorldParticle',repo_type='dataset',path_in_repo='deep_lagrange_dataset',recursive=True):paths.append(item.path)
  candidates=[x for x in paths if x.endswith(('.npz','.zst'))]
  write('S3_manifest_v7.json',dict(paths=paths,sample_candidates=candidates))
  if remaining()>150:
   deep=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename='deep_lagrange_dataset/checkpoint/final.ckpt',local_dir=str(R/'hf'))
   sha=digest(deep); obj=torch.load(deep,map_location='cpu',weights_only=True)
   write('S3_checkpoint_v7.json',dict(sha256=sha,weights_only=True,keys=list(obj.keys()),config_path='deep_lagrange_dataset/checkpoint/config.yaml'))
   del obj
  else:write('S3_checkpoint_v7.json',dict(status='not_downloaded_budget',remaining_s=remaining()))
  if not candidates: raise FileNotFoundError('HF deep_lagrange_dataset has checkpoint/config but no validation sample; cannot run S3 without inventing input')
  raise RuntimeError('Need inspect sample format and budget before S3')
 stage('S3',s3)
 write('results_v7.json',dict(S1=s1,S2=s2,elapsed_s=time.monotonic()-START,rate_cu_h=RATE))
except BaseException as e:
 traceback.print_exc();write('failure_v7.json',dict(error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-START))
finally:
 write('done_v7',dict(elapsed_s=time.monotonic()-START))
