"""L26.19-01c isolated Colab selfcheck; published checkpoint, one validation case."""
import os,sys,time,json,pathlib,hashlib,subprocess,traceback,math
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck'); R.mkdir(exist_ok=True)
O=R/'out';O.mkdir(exist_ok=True)
def log(*a): print(*a,flush=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def run(*args):log('RUN',args);subprocess.run(args,check=True)
def save(name,**kw):
 p=O/name
 assert not p.exists(),p
 with p.open('xb') as f:np.savez_compressed(f,**kw)
 log('SAVED',p,p.stat().st_size)
tstart=time.monotonic()
try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash; from open3d.ml.torch.ops import radius_search; print("IMPORT_SMOKE_OK",torch.__version__,open3d.__version__,dash.__version__,flush=True)')
 import torch,yaml,open3d
 from huggingface_hub import hf_hub_download
 repo=R/'repo'
 if not repo.exists():run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo))
 run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
 assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e'
 sys.path.insert(0,str(repo))
 from trajectory_model import TrajectoryModel
 from TrajDataset import load_npz_sample_by_data
 try:
  import open3d.ml.torch as ml3d
  from open3d.ml.torch.ops import radius_search
  log('OPEN3D_OK',torch.__version__,open3d.__version__)
 except Exception:traceback.print_exc();raise
 val=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename='fancy_fluid/dataset/validation.txt',local_dir=str(R/'hf'))
 sid=pathlib.Path(val).read_text().splitlines()[0].strip()
 assert sid=='66',sid
 path=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename=f'fancy_fluid/dataset/{sid}/{sid}.npz',local_dir=str(R/'hf'))
 wt=hf_hub_download('wclw1021/WorldParticle',repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['frame_end']=601
 data=load_npz_sample_by_data('fancy_fluid',path,frame_start=0,frame_end=601)
 gt=data['positions'].numpy();assert len(gt)>=601,len(gt)
 ckpt=torch.load(wt,map_location='cpu',weights_only=True)
 assert isinstance(ckpt,dict) and isinstance(ckpt['state_dict'],dict)
 log('SAFE_LOAD',sha(wt),len(ckpt['state_dict']),'SAMPLE',sid,gt.shape)
 feats=data['feats'].numpy();raw=np.load(path,allow_pickle=False)
 rawfeats=np.array(raw['feats']);box=data['box'].numpy();bf=data['box_feats'].numpy()
 lo,hi=box.min(0),box.max(0);ctr=(lo+hi)/2
 dots=np.einsum('ij,ij->i',bf,ctr-box);infrac=float((dots>0).mean());outfrac=float((dots<0).mean())
 log('FEATS',rawfeats.shape,feats.shape,float(np.min(feats)),float(np.max(feats)),float(np.std(feats)),'NORMALS',infrac,outfrac,'BOX',lo,hi)
 cfg['resolved_other_feats_channels']=int(feats.shape[-1]);cfg['resolved_obstacle_feats_channels']=int(bf.shape[-1]);cfg['data_folder']=str(R/'hf/fancy_fluid/dataset')
 model=TrajectoryModel(cfg).cuda().eval()
 sd={k.removeprefix('model.'):v for k,v in ckpt['state_dict'].items() if k.startswith('model.')}
 miss,extra=model.model.load_state_dict(sd,strict=False);assert not miss and not extra,(miss,extra)
 del ckpt,sd
 torch.cuda.empty_cache()
 f=torch.tensor(feats,device='cuda');b=torch.tensor(box,device='cuda');bf_t=torch.tensor(bf,device='cuda')
 pos0=torch.tensor(gt[0],device='cuda');vel0=data['velocities'][0].cuda()
 def rollout(batched):
  pos=pos0.clone();vel=vel0.clone()
  if batched:pos=pos[None];vel=vel[None]
  ff=f[None] if batched else f; bb=b[None] if batched else b; nn=bf_t[None] if batched else bf_t
  rec={0:gt[0].copy()};samp=[];base=time.monotonic()
  with torch.inference_mode():
   for i in range(1,601):
    # Repository inference.py: float32 inputs, torch.cuda.amp.autocast(bf16), external_force=None.
    with torch.autocast('cuda',dtype=torch.bfloat16):
     pos,vel=model(pos.float(),vel.float(),ff.float(),bb.float(),nn.float(),external_force=None)
    if i in (100,600): rec[i]=pos.squeeze(0).detach().float().cpu().numpy().copy()
    if i%10==0:samp.append(pos.squeeze(0).detach().float().cpu().numpy().copy())
    if i%100==0:log('P1_STEP',batched,i,'elapsed',round(time.monotonic()-base,2))
  return rec,np.stack(samp)
 # First path precisely repository's unbatched inference function forward path, second existing rollout.py batched call.
 orig,osamp=rollout(False);bat,bsamp=rollout(True)
 p1={str(k):{'repo_truth_mse':float(np.mean((orig[k]-gt[k])**2)),'rollout_truth_mse':float(np.mean((bat[k]-gt[k])**2)),'paths_mse':float(np.mean((bat[k]-orig[k])**2)),'paths_max_abs':float(np.max(np.abs(bat[k]-orig[k])))} for k in (100,600)}
 save('P1_validation.npz',sample=np.array(sid),steps=np.array([100,600]),gt=gt[[100,600]],repo=np.stack([orig[100],orig[600]]),rollout=np.stack([bat[100],bat[600]]),sample_steps=np.arange(10,601,10),repo_samples=osamp,rollout_samples=bsamp)
 log('P1_DONE',p1)
 # P2 P3: start still water in two boxes, same sampling and zero feature transformation as training data.
 def regular(l,h,w,lower):
  dx=.07
  grid=[np.arange(lower[j]+dx/2,lower[j]+extent-(0 if j!=1 else h+0.001),dx,dtype=np.float32) for j,extent in enumerate((l,h,w))]
  # Explicit y = lower+0.035..lower+h, not meshgrid's x/z bounds altered by height.
  grid=[np.arange(lower[0]+dx/2,lower[0]+l,dx,dtype=np.float32),np.arange(lower[1]+dx/2,lower[1]+h,dx,dtype=np.float32),np.arange(lower[2]+dx/2,lower[2]+w,dx,dtype=np.float32)]
  return np.stack(np.meshgrid(*grid,indexing='ij'),-1).reshape(-1,3)
 def walls(lower,upper,db,inward):
  faces=[];norm=[]
  for axis in range(3):
   other=[j for j in range(3) if j!=axis]
   ar=[np.arange(lower[j]+db/2,upper[j],db,dtype=np.float32) for j in other]
   u,v=np.meshgrid(*ar,indexing='ij')
   for side in (0,1):
    a=np.full((u.size,3),lower[axis] if side==0 else upper[axis],np.float32);a[:,other[0]]=u.ravel();a[:,other[1]]=v.ravel()
    n=np.zeros_like(a);n[:,axis]=(1 if side==0 else -1)*(1 if inward else -1)
    faces.append(a);norm.append(n)
  return np.concatenate(faces),np.concatenate(norm)
 def g0(name,points,wall,norm,lower,upper):
  assert not (O/(name+'.npz')).exists()
  n=len(points);p=torch.tensor(points,device='cuda')[None];v=torch.zeros_like(p);ff=torch.zeros((1,n,1),device='cuda');bb=torch.tensor(wall,device='cuda')[None];nn=torch.tensor(norm,device='cuda')[None]
  force=torch.zeros_like(p);force[:,:,1]=-9.81
  ts=[];metrics=[];samples=[]
  with torch.inference_mode():
   for step in range(2001):
    if step%100==0 or step==1:
     x=p[0].float().cpu().numpy();vv=v[0].float().cpu().numpy()
     outside=int(np.count_nonzero(np.any((x<np.asarray(lower))|(x>np.asarray(upper)),axis=1)))
     # Free-surface dispersion: SD of max y in longitudinal x bins with particles; empty bins omitted.
     edges=np.linspace(lower[0],upper[0],17);top=[x[(x[:,0]>=a)&(x[:,0]<z),1].max() for a,z in zip(edges[:-1],edges[1:]) if np.any((x[:,0]>=a)&(x[:,0]<z))]
     metrics.append((step,step*.01,outside,float(np.std(top)) if len(top)>1 else np.nan,float(.5*.3242*np.sum(vv.astype(np.float64)**2)),len(top),float(x[:,1].max()),float(vv.max())))
     if step%100==0:samples.append(x.copy())
     if step%500==0:log('G0_STEP',name,step,metrics[-1][:5])
    if step<2000:
     with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p,v,ff,bb,nn,external_force=force)
  m=np.asarray(metrics,dtype=np.float64);save(name+'.npz',metric_steps=m[:,0].astype(np.int32),metric_t=m[:,1],outside=m[:,2].astype(np.int32),surface_std=m[:,3],kinetic_energy=m[:,4],nonempty_bins=m[:,5].astype(np.int32),max_y=m[:,6],max_v=m[:,7],sample_t=np.arange(0,2001,100)*.01,position=np.stack(samples).astype(np.float32),initial_position=points,box=wall,box_feats=norm)
  return m[:,[0,2,3,4,5,6]].tolist()
 # Train box dimensions inferred directly, not assume coordinates or normals sign.
 p2=regular(float(hi[0]-lo[0]),.6,float(hi[2]-lo[2]),lo)
 p2m=g0('P2_train_container',p2,box,bf,lo,hi)
 lower=np.array([-1.5,0,-.25]);upper=np.array([1.5,1.5,.25]);area=2*((hi-lo)[0]*(hi-lo)[1]+(hi-lo)[0]*(hi-lo)[2]+(hi-lo)[1]*(hi-lo)[2]);db=math.sqrt(area/len(box))
 wb,wn=walls(lower,upper,db,infrac>outfrac)
 p3=regular(3,.6,.5,lower)
 p3m=g0('P3_capped_tank',p3,wb,wn,lower,upper)
 report=dict(status='ok',sample_id=sid,source='HF wclw1021/WorldParticle fancy_fluid validation first sample',repo_commit='b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e',weight_sha256=sha(wt),weights_only=True,torch=torch.__version__,open3d=open3d.__version__,gpu=torch.cuda.get_device_name(),p1=p1,p2=p2m,p3=p3m,feature_raw_shape=rawfeats.shape,feature_transformed_minmax=[float(feats.min()),float(feats.max())],feature_transformed_std=float(feats.std()),box_inward_fraction=infrac,box_outward_fraction=outfrac,box_count=len(box),tank_boundary_count=len(wb),boundary_pitch=db,external_force_shape=[1,len(p3),3],external_force_repo_none=True,elapsed_s=time.monotonic()-tstart)
 (O/'results.json').write_text(json.dumps(report,indent=2));log('SUCCESS',report['elapsed_s'])
except BaseException as e:
 traceback.print_exc();(O/'failure.json').write_text(json.dumps(dict(error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-tstart),indent=2));raise
finally:
 (O/'done').write_text('worker ended')
