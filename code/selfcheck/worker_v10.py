"""L26.19-01k: bounded fp32 author-path initial-condition comparison on Colab L4."""
import sys,time,json,pathlib,subprocess,traceback,hashlib,types,importlib.util,gc
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v10');R.mkdir(exist_ok=True);O=R/'out';O.mkdir(exist_ok=True)
ALLOC=float(pathlib.Path('/content/allocated_v10.txt').read_text());START=time.monotonic();RATE=2.10;CAP=2.2*3600/RATE;MARGIN=180

def log(*x):print(*x,flush=True)
def write(name,obj):(O/name).write_text(json.dumps(obj,indent=2,default=str))
def run(*a):log('RUN',a);subprocess.run(a,check=True)
def remaining():return CAP-(time.time()-ALLOC)-MARGIN
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
 return h.hexdigest()
def stage(tag,fn):
 try:
  ret=fn();write(tag+'_status_v10.json',dict(status='ok',result=ret));return ret
 except BaseException as e:
  traceback.print_exc();write(tag+'_status_v10.json',dict(status='failed',error=repr(e),trace=traceback.format_exc()));return None
try:
 run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
 run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
 run(sys.executable,'-c','import torch,open3d,dash,mdtraj;from open3d.ml.torch.ops import radius_search;print("IMPORT_OK",torch.__version__,open3d.__version__,flush=True)')
 import torch,yaml
 from huggingface_hub import hf_hub_download
 repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo));run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e');sys.path.insert(0,str(repo))
 from TrajDataset import load_npz_sample_by_data
 hf='wclw1021/WorldParticle';sample=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/66/66.npz',local_dir=str(R/'hf'));wt=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
 ck=torch.load(wt,map_location='cpu',weights_only=True);del ck
 data=load_npz_sample_by_data('fancy_fluid',sample,frame_start=0,frame_end=2)
 box=data['box'].numpy();bn=data['box_feats'].numpy();lo=np.array([-2.,0.,-1.],np.float32);hi=np.array([2.,2.,1.],np.float32)
 onplane=np.any(np.isclose(box,lo[None],atol=1e-5)|np.isclose(box,hi[None],atol=1e-5),axis=1)
 wall=box[onplane];norm=bn[onplane];cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['frame_end']=2
 source=(repo/'inference.py').read_text();assert source.count('torch.load(args.checkpoint, map_location=device)')==1 and source.count('with autocast(dtype=torch.bfloat16):')==1
 source=source.replace('torch.load(args.checkpoint, map_location=device)','torch.load(args.checkpoint, map_location=device, weights_only=True)').replace('with autocast(dtype=torch.bfloat16):','with autocast(enabled=False):')
 (R/'inference_fp32_v10.py').write_text(source);spec=importlib.util.spec_from_file_location('author_fp32_v10',R/'inference_fp32_v10.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
 def make_input(tag,pos,vel,raw):
  path=R/'input'/tag;path.mkdir(parents=True,exist_ok=True)
  np.savez_compressed(path/(tag+'.npz'),position=pos[None],velocity=vel[None],feats=raw,box=wall,box_feats=norm)
  return path
 mass=.324179202;raw_template=np.array([[.026010504,.324179202,1000.]],np.float32)
 xs=np.linspace(-1.96,1.96,57,dtype=np.float32);ys=np.float32(.035)+np.arange(5,dtype=np.float32)*np.float32(.07);zs=np.linspace(-.945,.945,28,dtype=np.float32)
 pos1=np.stack(np.meshgrid(xs,ys,zs,indexing='ij'),axis=-1).reshape(-1,3);vel1=np.zeros_like(pos1)
 distances=np.minimum(pos1-lo,hi-pos1);minimum=float(distances.min());count1=len(pos1)
 setup=dict(gpu=torch.cuda.get_device_name(),torch=torch.__version__,weight_sha256=digest(wt),weights_only=True,wall_count=len(wall),sample=66,T1_count=count1,T1_grid=[len(xs),len(ys),len(zs)],T1_min_wall_distance_m=minimum,T1_initial_y=[float(ys[0]),float(ys[-1])],T1_velocity='zero',T1_feats=0,T2_initial='sample 66 GT[0] position and velocity, loader feats',precision='fp32',external_force=None)
 write('setup_v10.json',setup);log('SETUP',setup)
 if count1!=7980 or minimum<.0349:raise ValueError(('T1 geometry',count1,minimum))
 make_input('T1',pos1,vel1,np.repeat(raw_template,count1,axis=0))
 samplepos=data['positions'].numpy()[0].astype(np.float32);samplevel=data['velocities'].numpy()[0].astype(np.float32);n2=len(samplepos)
 raw2=np.repeat(raw_template,n2,axis=0);make_input('T2',samplepos,samplevel,raw2)
 orig_loader=author.load_npz_sample_by_data
 def controlled_loader(*args,**kwargs):
  d=orig_loader(*args,**kwargs)
  if pathlib.Path(str(args[1])).stem=='T1':d['feats'].zero_()
  elif pathlib.Path(str(args[1])).stem=='T2':d['feats'].fill_(float(data['feats'][0,0]))
  return d
 author.load_npz_sample_by_data=controlled_loader
 setup['T2_count']=n2;setup['T2_feats']=float(data['feats'][0,0]);write('setup_v10.json',setup)
 def args_for(tag,out,steps):return types.SimpleNamespace(data_dir=str(R/'input'),sample=tag,checkpoint=str(wt),output_dir=str(out),start=0,end=2,dt=1,num_steps=steps)
 def inference(tag,label,steps):
  out=R/(tag+'_'+label);out.mkdir(exist_ok=True);t=time.monotonic();author.inference(args_for(tag,out,steps),dict(cfg));return out,time.monotonic()-t
 def extract(tag,out,steps,final=False):
  with np.load(out/'outcomes'/'npz'/tag/(tag+'_0_2.npz')) as z:p=z['position'];v=z['velocity']
  if p.shape!=(steps+1,len(p[0]),3) or v.shape!=p.shape:raise ValueError(('unexpected trajectory',p.shape,v.shape,steps))
  rows=[];samples=[];sample_steps=[];first=None;edges=np.linspace(lo[0],hi[0],17)
  for k,(x,velocity) in enumerate(zip(p,v)):
   inside=np.all((x>=lo)&(x<=hi),axis=1);outside=int((~inside).sum())
   if outside and first is None:first=k
   if k%50==0 or k==1:
    inside_x=x[inside];tops=[]
    for a,b in zip(edges[:-1],edges[1:]):
     group=inside_x[(inside_x[:,0]>=a)&(inside_x[:,0]<b)]
     if len(group):tops.append(float(group[:,1].max()))
    rows.append((k,k*.01,outside,float(x[:,1].mean()),float(.5*mass*np.sum(velocity.astype(np.float64)**2)),float(np.std(tops)) if len(tops)>1 else np.nan))
   if k%10==0:sample_steps.append(k);samples.append(x.astype(np.float32))
  a=np.asarray(rows,float)
  name=tag+'_v10.npz' if final else tag+'_pilot_v10.npz'
  with (O/name).open('xb') as f:np.savez_compressed(f,metric_steps=a[:,0].astype(np.int32),metric_time=a[:,1],outside=a[:,2].astype(np.int32),mean_y=a[:,3],kinetic_energy=a[:,4],surface_std=a[:,5],sample_steps=np.asarray(sample_steps),position=np.asarray(samples,np.float32))
  if final:
   with (O/(tag+'_end_v10.npz')).open('xb') as f:np.savez_compressed(f,position=p[-1],velocity=v[-1],step=steps,time_s=steps*.01,box=wall,box_feats=norm,feats=0. if tag=='T1' else float(data['feats'][0,0]))
  selected=a[np.isin(a[:,0],[0,1,50,100,500,1000,1500,2000,2500,3000])].tolist()
  result=dict(steps=steps,first_outside_step=first,max_outside=int(a[:,2].max()),metric_count=len(a),sample_count=len(samples),selected=selected,finished=final)
  if tag=='T1' and steps>=2000:
   late=a[(a[:,0]>=1500)&(a[:,0]<=2000),5];ten=a[(a[:,0]>=1000)&(a[:,0]<=2000)]
   result.update(surface_std_15_20_mean_m=float(np.nanmean(late)) if np.isfinite(late).any() else None,ke_10_20_max_J=float(ten[:,4].max()),ke_10_20_slope_J_per_s=float(np.polyfit(ten[:,1],ten[:,4],1)[0]),ke_1s_J=float(a[a[:,0]==100,4][0]))
  if tag=='T2' and steps>=3000:
   late=a[(a[:,0]>=2500)&(a[:,0]<=3000),5];twenty=a[(a[:,0]>=2000)&(a[:,0]<=3000)]
   result.update(surface_std_25_30_mean_m=float(np.nanmean(late)) if np.isfinite(late).any() else None,ke_20_30_max_J=float(twenty[:,4].max()),ke_20_30_slope_J_per_s=float(np.polyfit(twenty[:,1],twenty[:,4],1)[0]),ke_20s_J=float(a[a[:,0]==2000,4][0]),mean_y_last5s_m=float(a[(a[:,0]>=2500)&(a[:,0]<=3000),3].mean()))
  write(tag+'_'+label+'_summary_v10.json',result);log('RESULT',tag,label,result);return result
 def run_case(tag,goal):
  pilot,pilot_s=inference(tag,'pilot',100);speed=pilot_s/100;projection=goal*speed*1.1;left=remaining()
  gate=dict(pilot_s=pilot_s,s_per_step=speed,projected_s_10pct=projection,remaining_s=left,goal_steps=goal)
  write(tag+'_gate_v10.json',gate);log('GATE',tag,gate)
  if projection>left:
   extract(tag,pilot,100,False);return dict(status='budget_gate',gate=gate)
  if tag=='T1':
   first,wall_s=inference(tag,'first1000',1000);partial=extract(tag,first,1000,False)
   if partial['first_outside_step'] is not None:return dict(status='stopped_at_1000_outside',wall_s=wall_s,result=extract(tag,first,1000,True))
   if 2000*wall_s/1000*1.1>remaining():return dict(status='budget_stopped_1000',wall_s=wall_s,result=extract(tag,first,1000,True))
   full,wall_s=inference(tag,'full2000',2000);return dict(status='completed',wall_s=wall_s,result=extract(tag,full,2000,True))
  full,wall_s=inference(tag,'full3000',3000);return dict(status='completed',wall_s=wall_s,result=extract(tag,full,3000,True))
 # label used by extract names is bound per stage; no shared output names are reused.
 label='T1';t1=stage('T1',lambda:run_case('T1',1000));gc.collect();torch.cuda.empty_cache()
 label='T2';t2=stage('T2',lambda:run_case('T2',3000))
 write('results_v10.json',dict(T1=t1,T2=t2,elapsed_s=time.monotonic()-START,remaining_s=remaining(),rate_cu_h=RATE))
except BaseException as e:
 traceback.print_exc();write('failure_v10.json',dict(error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-START))
finally:write('done_v10',dict(elapsed_s=time.monotonic()-START))
