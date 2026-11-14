"""01f isolated Colab Q2/Q3/Q4, immutable v5 outputs."""
import os,sys,time,json,pathlib,hashlib,subprocess,traceback,math
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v5');R.mkdir(exist_ok=True);O=R/'out';O.mkdir(exist_ok=True)
def log(*x):print(*x,flush=True)
def run(*a):log('RUN',a);subprocess.run(a,check=True)
def stage(name,fn):
 try:
  v=fn();(O/(name+'_v5.json')).write_text(json.dumps({'status':'ok','result':v},indent=2));log(name,'OK');return v
 except BaseException as e:
  traceback.print_exc();(O/(name+'_v5.json')).write_text(json.dumps({'status':'failed','trace':traceback.format_exc()},indent=2));log(name,'FAILED',e);return None
start=time.monotonic()
try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash;from open3d.ml.torch.ops import radius_search;print("IMPORT_SMOKE_OK",torch.__version__,open3d.__version__,dash.__version__,flush=True)')
 import torch,yaml
 from huggingface_hub import hf_hub_download
 repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo))
 run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
 log('COMMIT',subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip())
 sys.path.insert(0,str(repo))
 from TrajDataset import transform_particle_feats_by_data,load_npz_sample_by_data
 from trajectory_model import TrajectoryModel
 hf='wclw1021/WorldParticle'
 sample=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/66/66.npz',local_dir=str(R/'hf'))
 data=load_npz_sample_by_data('fancy_fluid',sample,frame_start=0,frame_end=600)
 featval=float(data['feats'][0,0]);box=data['box'].numpy();bf=data['box_feats'].numpy();lo,hi=box.min(0),box.max(0)
 audit_rows=[]
 try:
  trainfile=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/train.txt',local_dir=str(R/'hf'))
  ids=pathlib.Path(trainfile).read_text().splitlines()[:10]
 except Exception as e:
  log('train.txt unavailable, use validation.txt',repr(e));valfile=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/validation.txt',local_dir=str(R/'hf'));ids=pathlib.Path(valfile).read_text().splitlines()[:10]
 for sid in ids:
  try:
   sid=sid.strip().split('/')[-1].replace('.npz','')
   fp=hf_hub_download(hf,repo_type='dataset',filename=f'fancy_fluid/dataset/{sid}/{sid}.npz',local_dir=str(R/'hf'))
   d=load_npz_sample_by_data('fancy_fluid',fp,frame_start=0,frame_end=600)
   row={'id':sid,'N':int(len(d['feats'])),'feats_min':float(d['feats'].min()),'feats_max':float(d['feats'].max()),'feats_value':float(d['feats'][0,0]),'zero_count':int((d['feats']==0).sum())};audit_rows.append(row);log('AUDIT_SAMPLE',row)
  except Exception as e:log('AUDIT_SAMPLE_FAILED',sid,repr(e));audit_rows.append({'id':sid,'error':repr(e)})
 (O/'sample_table_v5.json').write_text(json.dumps(audit_rows,indent=2))
 wt=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 ck=torch.load(wt,map_location='cpu',weights_only=True);log('CHECKPOINT_TYPE',type(ck).__name__)
 h=hashlib.sha256();
 with open(wt,'rb') as fi:
  for chunk in iter(lambda:fi.read(8<<20),b''):h.update(chunk)
 cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['resolved_other_feats_channels']=1;cfg['resolved_obstacle_feats_channels']=3
 audit={'sample_loader_value':featval,'loader_function':'TrajDataset.load_npz_sample_by_data','weight_sha256':h.hexdigest(),'weights_only':True,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,'box_count':len(box)}
 (O/'audit_v5.json').write_text(json.dumps(audit,indent=2));log('AUDIT',audit)
 def regular(lower,extent,h):
  dx=.07;grid=[np.arange(lower[j]+dx/2,lower[j]+(h if j==1 else extent[j]),dx,dtype=np.float32) for j in range(3)]
  return np.stack(np.meshgrid(*grid,indexing='ij'),-1).reshape(-1,3)
 def walls(lower,upper,pitch,top=True):
  faces=[];norm=[]
  for ax in range(3):
   others=[j for j in range(3) if j!=ax];ar=[np.arange(lower[j]+pitch/2,upper[j],pitch,dtype=np.float32) for j in others];u,v=np.meshgrid(*ar,indexing='ij')
   for side in (0,1):
    if ax==1 and side==1 and not top:continue
    a=np.full((u.size,3),lower[ax] if side==0 else upper[ax],np.float32);a[:,others[0]]=u.ravel();a[:,others[1]]=v.ravel()
    n=np.zeros_like(a);n[:,ax]=(-1 if side==0 else 1);faces.append(a);norm.append(n)
  return np.concatenate(faces),np.concatenate(norm)
 def model_new():
  m=TrajectoryModel(dict(cfg)).cuda().eval();sd={k.removeprefix('model.'):v for k,v in ck['state_dict'].items() if k.startswith('model.')};miss,extra=m.model.load_state_dict(sd,strict=False);log('STATE_KEYS',len(miss),len(extra));return m
 def g0(name,points,wall,norm,lower,upper,steps=2000,feats_value=None):
  model=model_new();n=len(points);p=torch.tensor(points,device='cuda')[None];v=torch.zeros_like(p);f=torch.full((1,n,1),featval if feats_value is None else feats_value,device='cuda');b=torch.tensor(wall,device='cuda')[None];bn=torch.tensor(norm,device='cuda')[None];force=torch.zeros_like(p);force[:,:,1]=-9.81
  rows=[];samples=[];sample_steps=[];edges=np.linspace(lower[0],upper[0],17)
  with torch.inference_mode():
   for step in range(steps+1):
    if step%50==0 or step==1:
     x=p[0].float().cpu().numpy();vv=v[0].float().cpu().numpy();outside=int(np.count_nonzero(np.any((x<lower)|(x>upper),axis=1)))
     tops=[x[(x[:,0]>=a)&(x[:,0]<z),1].max() for a,z in zip(edges[:-1],edges[1:]) if np.any((x[:,0]>=a)&(x[:,0]<z))]
     rows.append((step,step*.01,outside,float(np.std(tops)) if len(tops)>1 else np.nan,float(.5*.3242*np.sum(vv.astype(np.float64)**2)),float(x[:,1].mean()),len(tops)))
     if step%500==0:log(name,step,rows[-1])
    if step%10==0:samples.append(p[0].detach().float().cpu().numpy().copy());sample_steps.append(step)
    if step<steps:
     with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p,v,f,b,bn,external_force=force)
  a=np.asarray(rows,dtype=np.float64)
  with (O/(name+'_v5.npz')).open('xb') as out:np.savez_compressed(out,metric_steps=a[:,0].astype(np.int32),metric_t=a[:,1],outside=a[:,2].astype(np.int32),surface_std=a[:,3],kinetic_energy=a[:,4],mean_y=a[:,5],nonempty_bins=a[:,6].astype(np.int32),sample_steps=np.asarray(sample_steps),position=np.asarray(samples,dtype=np.float32),initial_position=points,box=wall,box_feats=norm,feat_value=np.float32(featval if feats_value is None else feats_value))
  del model;torch.cuda.empty_cache()
  return {'particles':n,'force_shape':[1,n,3],'metric_count':len(rows),'samples':len(samples),'selected':[r for r in rows if int(r[0]) in (0,1,100,500,1000,1500,2000)]}
 def q2():return g0('Q2_train_container',regular(lo,hi-lo,.6),box,bf,lo,hi)
 q2r=stage('Q2',q2)
 def q2z():return g0('Q2z_train_container',regular(lo,hi-lo,.6),box,bf,lo,hi,steps=500,feats_value=0.0)
 q2zr=stage('Q2z',q2z)
 def q3():
  lower=np.array([-1.5,0,-.25]);upper=np.array([1.5,1.5,.25]);area=2*((hi-lo)[0]*(hi-lo)[1]+(hi-lo)[0]*(hi-lo)[2]+(hi-lo)[1]*(hi-lo)[2]);pitch=math.sqrt(area/len(box));wb,wn=walls(lower,upper,pitch)
  return g0('Q3_capped_tank',regular(lower,upper-lower,.6),wb,wn,lower,upper)
 q3r=stage('Q3',q3)
 def q4():
  lower=np.array([-1.5,0,-.25]);upper=np.array([1.5,1.5,.25]);wb,wn=walls(lower,upper,1/math.sqrt(1500),top=False)
  return g0('Q4_open_tank',regular(lower,upper-lower,.6),wb,wn,lower,upper)
 q4r=stage('Q4',q4)
 (O/'results_v5.json').write_text(json.dumps({'status':'ok','Q2':q2r,'Q2z':q2zr,'Q3':q3r,'Q4':q4r,'audit':audit,'elapsed_s':time.monotonic()-start},indent=2))
except BaseException as e:
 traceback.print_exc();(O/'failure_v5.json').write_text(json.dumps({'error':repr(e),'trace':traceback.format_exc(),'elapsed_s':time.monotonic()-start},indent=2))
finally:(O/'done_v5').write_text('worker ended')
