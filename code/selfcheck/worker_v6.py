"""Bounded L26.19-01g Colab-only experiment; immutable v6 outputs."""
import sys,time,json,pathlib,subprocess,hashlib,traceback
import numpy as np
R=pathlib.Path('/content/l26_19_selfcheck_v6'); R.mkdir(exist_ok=True); O=R/'out'; O.mkdir(exist_ok=True)
START=time.monotonic(); RATE=2.10; CAP_SECONDS=3600/RATE; MARGIN=180

def log(*args): print(*args,flush=True)
def write(name,obj): (O/name).write_text(json.dumps(obj,indent=2,default=str))
def stage(name,fn):
    try:
        ret=fn();write(name+'_v6.json',dict(status='ok',result=ret));log(name,'OK');return ret
    except BaseException as exc:
        traceback.print_exc();write(name+'_v6.json',dict(status='failed',error=repr(exc),trace=traceback.format_exc()));log(name,'FAILED',repr(exc));return None

def run(*args): log('RUN',args);subprocess.run(args,check=True)
try:
    run(sys.executable,'-m','pip','install','-q','open3d==0.20.0','pytorch-lightning==2.0.2','mdtraj==1.10.3','zstandard==0.25.0','msgpack==1.1.2','einops==0.8.2','pyyaml==6.0.3','huggingface_hub','dash')
    run(sys.executable,'-m','pip','install','-q','torch==2.13.0+cu126','torchvision==0.28.0+cu126','--index-url','https://download.pytorch.org/whl/cu126')
    run(sys.executable,'-c','import torch,open3d,dash;from open3d.ml.torch.ops import radius_search;print("IMPORT_OK",torch.__version__,open3d.__version__,flush=True)')
    import torch,yaml
    from huggingface_hub import hf_hub_download
    repo=R/'repo';run('git','clone','-q','https://github.com/WorldParticle/WorldParticle.git',str(repo));run('git','-C',str(repo),'checkout','-q','b8e37b854f2af3fc9bfd7fc150cfc01cba4a092e')
    sys.path.insert(0,str(repo))
    from trajectory_model import TrajectoryModel
    from TrajDataset import load_npz_sample_by_data
    hf='wclw1021/WorldParticle';sample=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/dataset/66/66.npz',local_dir=str(R/'hf'))
    data=load_npz_sample_by_data('fancy_fluid',sample,frame_start=0,frame_end=600)
    wt=hf_hub_download(hf,repo_type='dataset',filename='fancy_fluid/checkpoint/final.ckpt',local_dir=str(R/'hf'))
    ck=torch.load(wt,map_location='cpu',weights_only=True)
    h=hashlib.sha256()
    with open(wt,'rb') as f:
        for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
    cfg=yaml.safe_load(pathlib.Path('/content/selfcheck_config.yaml').read_text());cfg['resolved_other_feats_channels']=1;cfg['resolved_obstacle_feats_channels']=3
    box=data['box'].numpy();bn=data['box_feats'].numpy();lo,hi=box.min(0),box.max(0);feat=float(data['feats'][0,0]);gt=data['positions'].numpy()
    audit=dict(gpu=torch.cuda.get_device_name(),torch=torch.__version__,sha256=h.hexdigest(),weights_only=True,feats=feat,box_count=len(box),bounds=[lo.tolist(),hi.tolist()],gt_frames=len(gt),rate_cu_h=RATE)
    write('audit_v6.json',audit);log('AUDIT',audit)
    def model_new():
        m=TrajectoryModel(dict(cfg)).cuda().eval();sd={k.removeprefix('model.'):v for k,v in ck['state_dict'].items() if k.startswith('model.')};miss,extra=m.model.load_state_dict(sd,strict=False);log('STATE_KEYS',len(miss),len(extra));return m
    def metrics(step,p,v,rows):
        x=p[0].float().cpu().numpy();vv=v[0].float().cpu().numpy();out=int(np.any((x<lo)|(x>hi),axis=1).sum());edges=np.linspace(lo[0],hi[0],17)
        tops=[x[(x[:,0]>=a)&(x[:,0]<b),1].max() for a,b in zip(edges[:-1],edges[1:]) if np.any((x[:,0]>=a)&(x[:,0]<b))]
        rows.append((step,step*.01,out,float(np.std(tops)) if len(tops)>1 else float('nan'),float(.5*.3242*np.sum(vv.astype(np.float64)**2)),float(x[:,1].mean())))
        if step%100==0:log('METRIC',step,rows[-1])
    def save(name,rows,positions,sample_steps,initial,extra):
        a=np.asarray(rows,dtype=float)
        with (O/(name+'_v6.npz')).open('xb') as f:np.savez_compressed(f,metric_steps=a[:,0].astype(np.int32),metric_t=a[:,1],outside=a[:,2].astype(np.int32),surface_std=a[:,3],kinetic_energy=a[:,4],mean_y=a[:,5],sample_steps=np.asarray(sample_steps),position=np.asarray(positions,dtype=np.float32),initial_position=initial,box=box,box_feats=bn,**extra)
        return dict(particles=len(initial),metric_count=len(rows),samples=len(sample_steps),selected=[r for r in rows if int(r[0]) in (0,100,500,600,1000,1500,2000)])
    def regular7020():
        dx=.07;xs=np.arange(lo[0]+dx/2,hi[0],dx,dtype=np.float32);zs=np.arange(lo[2]+dx/2,hi[2],dx,dtype=np.float32)
        # Five layers. Evenly select exactly 7020 cells; report actual height/count.
        ys=lo[1]+dx/2+dx*np.arange(5,dtype=np.float32)
        g=np.stack(np.meshgrid(xs,ys,zs,indexing='ij'),-1).reshape(-1,3)
        if len(g)<7020:raise ValueError(('insufficient_grid_cells',len(g)))
        indices=np.linspace(0,len(g)-1,7020,dtype=np.int64);return g[indices]
    def R1():
        points=regular7020();n=len(points);model=model_new();p=torch.tensor(points,device='cuda')[None];v=torch.zeros_like(p);f=torch.full((1,n,1),feat,device='cuda');b=torch.tensor(box,device='cuda')[None];bf=torch.tensor(bn,device='cuda')[None];force=torch.zeros_like(p);force[:,:,1]=-9.81
        rows=[];positions=[];ss=[];t0=time.monotonic()
        with torch.inference_mode():
            for step in range(2001):
                if step%50==0 or step==1:metrics(step,p,v,rows)
                if step%10==0:positions.append(p[0].detach().float().cpu().numpy().copy());ss.append(step)
                if step==100:
                    speed=(time.monotonic()-t0)/100;projected=1900*speed;available=CAP_SECONDS-(time.monotonic()-START)-MARGIN
                    write('R1_gate_v6.json',dict(s_per_step=speed,projected_remaining_s=projected,available_s=available,elapsed_s=time.monotonic()-START))
                    log('R1_GATE',speed,projected,available)
                    if projected>available:raise RuntimeError('R1 projection exceeds remaining 1 CU budget')
                if step<2000:
                    with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p,v,f,b,bf,external_force=force)
        result=save('R1_regular7020',rows,positions,ss,points,dict(feat_value=np.float32(feat)))
        result.update(initial_height=[float(points[:,1].min()),float(points[:,1].max())],s_per_step=(time.monotonic()-t0)/2000)
        del model;torch.cuda.empty_cache();return result
    r1=stage('R1',R1)
    def R2():
        n=len(gt[0]);speed=(r1 or {}).get('s_per_step')
        if speed is None:raise RuntimeError('R1 pilot unavailable for R2 cost estimate')
        projected=2000*speed;available=CAP_SECONDS-(time.monotonic()-START)-MARGIN
        write('R2_gate_v6.json',dict(projected_s=projected,available_s=available,R1_s_per_step=speed))
        if projected>available:raise RuntimeError('R2 estimated cost exceeds remaining 1 CU budget')
        model=model_new();p=torch.tensor(gt[0],device='cuda')[None];v=data['velocities'][0].cuda()[None];f=data['feats'].cuda()[None];b=torch.tensor(box,device='cuda')[None];bf=torch.tensor(bn,device='cuda')[None]
        rows=[];positions=[];ss=[];t0=time.monotonic()
        with torch.inference_mode():
            for step in range(2001):
                if step%50==0 or step==1:metrics(step,p,v,rows)
                if step%10==0:positions.append(p[0].detach().float().cpu().numpy().copy());ss.append(step)
                if step==100:
                    rate=(time.monotonic()-t0)/100;left=CAP_SECONDS-(time.monotonic()-START)-MARGIN
                    write('R2_pilot_v6.json',dict(s_per_step=rate,projected_remaining_s=1900*rate,available_s=left))
                    if 1900*rate>left:raise RuntimeError('R2 measured pilot exceeds remaining 1 CU budget')
                if step<2000:
                    with torch.autocast('cuda',dtype=torch.bfloat16):p,v=model(p.float(),v.float(),f.float(),b.float(),bf.float(),external_force=None)
        result=save('R2_author_continuation',rows,positions,ss,gt[0],dict(feat_value=np.float32(feat),truth0=gt[0]))
        for a,b0 in ((600,1000),(1000,1500),(1500,2000)):
            rowa=next(r for r in rows if r[0]==a);rowb=next(r for r in rows if r[0]==b0)
            result[f'trend_{a}_{b0}']=dict(energy_change=rowb[4]-rowa[4],mean_y_change=rowb[5]-rowa[5])
        result['s_per_step']=(time.monotonic()-t0)/2000;return result
    r2=stage('R2',R2)
    write('results_v6.json',dict(R1=r1,R2=r2,elapsed_s=time.monotonic()-START))
except BaseException as exc:
    traceback.print_exc();write('failure_v6.json',dict(error=repr(exc),trace=traceback.format_exc(),elapsed_s=time.monotonic()-START))
finally:
    write('done_v6',dict(elapsed_s=time.monotonic()-START))
