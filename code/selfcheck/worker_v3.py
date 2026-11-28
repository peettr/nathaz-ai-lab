"""Independent WorldParticle parity and G0 tests; Colab only, versioned output."""
import os,sys,time,json,pathlib,hashlib,subprocess,traceback,math,types
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v3');R.mkdir(exist_ok=True)
O=R/'out';O.mkdir(exist_ok=True)
def log(*x):print(*x,flush=True)
def run(*a):log('RUN',a);subprocess.run(a,check=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def save(name,**kw):
 with (O/name).open('xb') as f:np.savez_compressed(f,**kw)
def stage(name,fn):
 try:
  v=fn();(O/(name+'.json')).write_text(json.dumps(dict(status='ok',result=v),indent=2,default=str));log(name,'OK');return v
 except BaseException as e:
  traceback.print_exc();(O/(name+'.json')).write_text(json.dumps(dict(status='failed',error=repr(e),trace=traceback.format_exc()),indent=2));log(name,'FAILED',repr(e));return None
start=time.monotonic()
try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash;from open3d.ml.torch.ops import radius_search;print("IMPORT_SMOKE_OK",torch.__version__,open3d.__version__,dash.__version__,flush=True)')
 import torch,yaml,open3d
 from huggingface_hub import hf_hub_download
 repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo))
 run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
 assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e'
 sys.path.insert(0,str(repo))
 from trajectory_model import TrajectoryModel
 from TrajDataset import load_npz_sample_by_data
 hf='wclw1021/WorldParticle';val=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/validation.txt',local_dir=str(R/'hf'))
 sid=pathlib.Path(val).read_text().splitlines()[0].strip();assert sid=='66',sid
 sample=hf_hub_download(hf,repo_type='dataset',filename=f'fancy_fluid/dataset/{sid}/{sid}.npz',local_dir=str(R/'hf'))
 wt=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['frame_start']=0;cfg['frame_end']=600
 data=load_npz_sample_by_data('fancy_fluid',sample,frame_start=0,frame_end=600)
 gt=data['positions'].numpy();assert len(gt)==600,gt.shape
 ckpt=torch.load(wt,map_location='cpu',weights_only=True);assert isinstance(ckpt,dict) and isinstance(ckpt['state_dict'],dict)
 feats=data['feats'].numpy();raw=np.load(sample,allow_pickle=False);rawfeats=np.array(raw['feats']);box=data['box'].numpy();bf=data['box_feats'].numpy()
 lo,hi=box.min(0),box.max(0);ctr=(lo+hi)/2;dots=np.einsum('ij,ij->i',bf,ctr-box)
 def distribution(a):
  u,c=np.unique(a,return_counts=True);return dict(shape=list(a.shape),min=float(a.min()),max=float(a.max()),mean=float(a.mean()),std=float(a.std()),zero_fraction=float((a==0).mean()),unique_values=[float(x) for x in u[:20]],unique_counts=[int(x) for x in c[:20]])
 audit=dict(sample=sid,raw_feats=distribution(rawfeats),transformed_feats=distribution(feats),normal_inward_fraction=float((dots>0).mean()),normal_outward_fraction=float((dots<0).mean()),normal_tangent_fraction=float((dots==0).mean()),normal_counts_by_axis={str(j):int(np.count_nonzero(np.abs(bf[:,j])>.5)) for j in range(3)},box_lo=lo.tolist(),box_hi=hi.tolist(),box_count=len(box),weight_sha256=sha(wt),weights_only=True,torch=torch.__version__,open3d=open3d.__version__,gpu=torch.cuda.get_device_name())
 (O/'audit.json').write_text(json.dumps(audit,indent=2));log('AUDIT',audit)
 cfg['resolved_other_feats_channels']=int(feats.shape[-1]);cfg['resolved_obstacle_feats_channels']=int(bf.shape[-1]);cfg['data_folder']=str(R/'hf/fancy_fluid/dataset')
 del ckpt
 def p1():
  # Invoke the repository's actual inference.inference function. Patch only its unsafe checkpoint call.
  import inference as author
  args=types.SimpleNamespace(data_dir=str(R/'hf/fancy_fluid/dataset'),output_dir=str(R/'author'),sample=sid,checkpoint=wt,start=0,end=600,num_steps=599,dt=1)
  orig_load=torch.load
  def safe_load(*a,**kw):
   assert a[0]==wt and kw.get('weights_only',True) is True
   kw['weights_only']=True;return orig_load(*a,**kw)
  torch.load=safe_load
  try:author.inference(args,dict(cfg))
  finally:torch.load=orig_load
  author_path=R/'author/outcomes/npz'/sid/f'{sid}_0_600.npz'
  with np.load(author_path,allow_pickle=False) as a:ap=a['position'].copy()
  assert ap.shape==gt.shape,(ap.shape,gt.shape)
  model=TrajectoryModel(dict(cfg)).cuda().eval()
  ck=orig_load(wt,map_location='cpu',weights_only=True);sd={k.removeprefix('model.'):v for k,v in ck['state_dict'].items() if k.startswith('model.')};missing,extra=model.model.load_state_dict(sd,strict=False);assert not missing and not extra
  del ck,sd
  p=torch.tensor(gt[0],device='cuda')[None];v=data['velocities'][0].cuda()[None]
  f=torch.tensor(feats,device='cuda')[None];b=torch.tensor(box,device='cuda')[None];bn=torch.tensor(bf,device='cuda')[None]
  cp=np.empty_like(gt);cp[0]=gt[0]
  with torch.inference_mode():
   for k in range(1,600):
    with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p.float(),v.float(),f.float(),b.float(),bn.float(),external_force=None)
    cp[k]=p[0].detach().float().cpu().numpy()
    if k%100==0:log('P1',k)
  ae=np.mean((ap[1:]-gt[1:])**2,axis=(1,2));ce=np.mean((cp[1:]-gt[1:])**2,axis=(1,2));de=np.mean((ap[1:]-cp[1:])**2,axis=(1,2))
  save('P1_validation_v3.npz',steps=np.arange(600),truth_10=gt[::10],author_10=ap[::10],custom_10=cp[::10],author_truth_mse=ae,custom_truth_mse=ce,paths_mse=de)
  return {str(k):dict(author_truth_mse=float(ae[k-1]),custom_truth_mse=float(ce[k-1]),paths_mse=float(de[k-1]),max_abs_paths=float(np.max(np.abs(ap[k]-cp[k])))) for k in (100,599)}|{'mean_1_599':dict(author_truth_mse=float(ae.mean()),custom_truth_mse=float(ce.mean()),paths_mse=float(de.mean()))}
 p1result=stage('P1_v3',p1)
 # Independent construction and execution: failure of one must not block the other.
 model=None
 def get_model():
  nonlocal_placeholder=None
  m=TrajectoryModel(dict(cfg)).cuda().eval();ck=torch.load(wt,map_location='cpu',weights_only=True)
  sd={k.removeprefix('model.'):v for k,v in ck['state_dict'].items() if k.startswith('model.')};miss,extra=m.model.load_state_dict(sd,strict=False);assert not miss and not extra;(delvar:=None)
  return m
 def regular(lower,extent,h):
  dx=.07
  grid=[np.arange(lower[j]+dx/2,lower[j]+(h if j==1 else extent[j]),dx,dtype=np.float32) for j in range(3)]
  return np.stack(np.meshgrid(*grid,indexing='ij'),-1).reshape(-1,3)
 def walls(lower,upper,pitch,inward):
  faces=[];norm=[]
  for ax in range(3):
   others=[j for j in range(3) if j!=ax]
   ar=[np.arange(lower[j]+pitch/2,upper[j],pitch,dtype=np.float32) for j in others]
   u,v=np.meshgrid(*ar,indexing='ij')
   for side in (0,1):
    a=np.full((u.size,3),lower[ax] if side==0 else upper[ax],np.float32);a[:,others[0]]=u.ravel();a[:,others[1]]=v.ravel()
    n=np.zeros_like(a);n[:,ax]=(1 if side==0 else -1)*(1 if inward else -1);faces.append(a);norm.append(n)
  return np.concatenate(faces),np.concatenate(norm)
 def g0(name,points,wall,norm,lower,upper):
  model=get_model();n=len(points)
  p=torch.tensor(points,device='cuda')[None];v=torch.zeros_like(p);f=torch.zeros((1,n,1),device='cuda');b=torch.tensor(wall,device='cuda')[None];bn=torch.tensor(norm,device='cuda')[None]
  force=torch.zeros_like(p);force[:,:,1]=-9.81
  rows=[];samples=[];sample_steps=[]
  with torch.inference_mode():
   for step in range(2001):
    if step%50==0 or step==1:
     x=p[0].float().cpu().numpy();vv=v[0].float().cpu().numpy();outside=int(np.count_nonzero(np.any((x<lower)|(x>upper),axis=1)))
     edges=np.linspace(lower[0],upper[0],17);tops=[x[(x[:,0]>=a)&(x[:,0]<z),1].max() for a,z in zip(edges[:-1],edges[1:]) if np.any((x[:,0]>=a)&(x[:,0]<z))]
     rows.append((step,step*.01,outside,float(np.std(tops)) if len(tops)>1 else np.nan,float(.5*.3242*np.sum(vv.astype(np.float64)**2)),len(tops),float(x[:,1].max())))
     if step%500==0:log(name,step,rows[-1])
    if step%10==0:samples.append(p[0].detach().float().cpu().numpy().copy());sample_steps.append(step)
    if step<2000:
     with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p,v,f,b,bn,external_force=force)
  a=np.asarray(rows,dtype=np.float64)
  save(name+'.npz',metric_steps=a[:,0].astype(np.int32),metric_t=a[:,1],outside=a[:,2].astype(np.int32),surface_std=a[:,3],kinetic_energy=a[:,4],nonempty_bins=a[:,5].astype(np.int32),max_y=a[:,6],sample_steps=np.asarray(sample_steps),position=np.asarray(samples,dtype=np.float32),initial_position=points,box=wall,box_feats=norm)
  del model;torch.cuda.empty_cache()
  return dict(particles=n,force_shape=[1,n,3],metrics_0_1_100_500_1000_1500_2000=[r for r in rows if int(r[0]) in (0,1,100,500,1000,1500,2000)],metric_count=len(rows),samples=len(samples))
 def p2():
  pts=regular(lo,hi-lo,.6);return g0('P2_train_container_v3',pts,box,bf,lo,hi)
 p2result=stage('P2_v3',p2)
 def p3():
  lower=np.array([-1.5,0,-.25]);upper=np.array([1.5,1.5,.25]);area=2*((hi-lo)[0]*(hi-lo)[1]+(hi-lo)[0]*(hi-lo)[2]+(hi-lo)[1]*(hi-lo)[2]);pitch=math.sqrt(area/len(box))
  wb,wn=walls(lower,upper,pitch,audit['normal_inward_fraction']>audit['normal_outward_fraction']);pts=regular(lower,upper-lower,.6)
  result=g0('P3_capped_tank_v3',pts,wb,wn,lower,upper);result['boundary_pitch']=pitch;result['boundary_count']=len(wb);return result
 p3result=stage('P3_v3',p3)
 (O/'results_v3.json').write_text(json.dumps(dict(status='ok',p1=p1result,p2=p2result,p3=p3result,audit=audit,elapsed_s=time.monotonic()-start),indent=2))
except BaseException as e:
 traceback.print_exc();(O/'failure_v3.json').write_text(json.dumps(dict(error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-start),indent=2))
finally:
 (O/'done_v3').write_text('worker ended')
