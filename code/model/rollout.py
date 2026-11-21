"""WorldParticle zero-shot tank rollout; only isolated Colab VM output."""
import json, math, pathlib, sys, time, traceback, hashlib
import numpy as np
import torch, yaml
ROOT=pathlib.Path('/content/l26_19_wp'); OUT=ROOT/'rollouts'; OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'repo'))
from trajectory_model import TrajectoryModel
DT=.01; L=3.; W=.5; M=.3242; G=9.81
AUDIT=json.loads((ROOT/'sample_audit.json').read_text()); INWARD=AUDIT['inward_fraction']>.9
assert INWARD or AUDIT['outward_fraction']>.9
STATE=json.loads((ROOT/'prepare_v2_state.json').read_text());assert STATE['status']=='ok'
CFG=yaml.safe_load((ROOT/'config.yaml').read_text());CFG['resolved_other_feats_channels']=1;CFG['resolved_obstacle_feats_channels']=3
T0=time.monotonic()
def geom(h,tilt=False):
    dx=.07; x=np.arange(-L/2+dx/2,L/2,dx,dtype=np.float32);y=np.arange(dx/2,h+.1,dx,dtype=np.float32);z=np.arange(-W/2+dx/2,W/2,dx,dtype=np.float32)
    X,Y,Z=np.meshgrid(x,y,z,indexing='ij')
    mask=Y<(h+(.1*h*X/(L/2) if tilt else 0))
    p=np.stack((X[mask],Y[mask],Z[mask]),axis=-1).astype('float32')
    db=1/np.sqrt(1500.); faces=[]; norms=[]
    for axis,value,axes,sign in [(0,-L/2,[(1,1.5),(2,W)],1),(0,L/2,[(1,1.5),(2,W)],-1),(2,-W/2,[(0,L),(1,1.5)],1),(2,W/2,[(0,L),(1,1.5)],-1),(1,0,[(0,L),(2,W)],1)]:
        coords=[np.arange((-span/2 if dim!=1 else 0)+db/2,(-span/2 if dim!=1 else 0)+span,db,dtype=np.float32) for dim,span in axes]
        a,b=np.meshgrid(*coords,indexing='ij');wall=np.full((a.size,3),value,dtype=np.float32);wall[:,axes[0][0]]=a.ravel();wall[:,axes[1][0]]=b.ravel()
        normal=np.zeros_like(wall);normal[:,axis]=(sign if INWARD else -sign)
        faces.append(wall);norms.append(normal)
    return p,np.concatenate(faces),np.concatenate(norms)
def freq(h):return math.sqrt((math.pi*G/L)*math.tanh(math.pi*h/L))/(2*math.pi)
def cases(h):
    f1=freq(h)
    yield 'G0','G0',0.,0.,2000
    yield 'C1','C1',0.,0.,math.ceil(12/f1/DT)
    for ratio in (.8,.9,.95,1.,1.05,1.1,1.2):yield f'C2_{round(ratio*100):03d}','C2',.015,ratio*f1,math.ceil(15/(ratio*f1)/DT)
    for ratio in (.9,1.,1.1):yield f'C2b_{round(ratio*100):03d}','C2b',.06,ratio*f1,math.ceil(15/(ratio*f1)/DT)
    yield 'AB0','AB0',0.,f1,math.ceil(15/f1/DT)
    yield 'AB1','AB1',.015,f1,math.ceil(15/f1/DT)
def out_one(model,depth,h,case,kind,amp,f,n):
    path=OUT/f'{depth}_{case}.npz';assert not path.exists(),f'existing output {path}'
    p,box,bf=geom(h,kind=='C1');count=len(p)
    pos=torch.tensor(p,device='cuda')[None];vel=torch.zeros_like(pos)
    feats=torch.zeros((1,count,1),device='cuda');box=torch.tensor(box,device='cuda')[None];bf=torch.tensor(bf,device='cuda')[None]
    force=torch.zeros_like(pos);force[:,:,1]=-G
    t=np.arange(n+1,dtype=np.float64)*DT
    momentum=np.empty((n+1,3),dtype=np.float64);surface=np.empty((n+1,2),dtype=np.float32);sample_pos=[];sample_v=[];sample_t=[]
    absmax=0.;cross=0;nan=False
    def record(i):
        nonlocal absmax,cross,nan
        xyz=pos[0].detach().float().cpu().numpy();v=vel[0].detach().float().cpu().numpy()
        if not np.isfinite(xyz).all() or not np.isfinite(v).all():nan=True;raise ValueError(f'nonfinite step {i}')
        momentum[i]=M*v.sum(0,dtype=np.float64)
        left=xyz[xyz[:,0]<-L/2+.05,1];right=xyz[xyz[:,0]> L/2-.05,1]
        surface[i,0]=left.max() if len(left) else np.nan
        surface[i,1]=right.max() if len(right) else np.nan
        absmax=max(absmax,float(np.max(np.abs(xyz))))
        cross=max(cross,int(np.count_nonzero((xyz[:,0]<-L/2-.07)|(xyz[:,0]>L/2+.07)|(xyz[:,1]<-.07)|(xyz[:,2]<-W/2-.07)|(xyz[:,2]>W/2+.07))))
        if i%10==0:sample_t.append(t[i]);sample_pos.append(xyz.copy());sample_v.append(v.copy())
    start=time.monotonic()
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        record(0)
        for i in range(1,n+1):
            now=(i-1)*DT
            ax=0. if kind in ('G0','C1','AB0') else (-amp*(2*math.pi*f)**2 if kind=='AB1' else amp*(2*math.pi*f)**2*math.sin(2*math.pi*f*now))
            force[:,:,0]=ax
            pos,vel=model(pos,vel,feats,box,bf,external_force=force)
            record(i)
            if i%500==0:print('CASE_STEP',depth,case,i,n,'wall',round(time.monotonic()-start,1),flush=True)
    torch.cuda.synchronize()
    payload=dict(t=t,P=momentum,surface=surface,surface_left=surface[:,0],surface_right=surface[:,1],sample_t=np.asarray(sample_t),position=np.stack(sample_pos),velocity=np.stack(sample_v),particle_mass=np.float64(M),particle_count=np.int32(count),dt=np.float64(DT),depth=np.float64(h),case=np.array(case),force_convention=np.array('container: (-a_b,-9.81,0); AB1 constant -a_max; C1 initial slope'))
    with path.open('xb') as file:np.savez_compressed(file,**payload)
    result=dict(depth=depth,case=case,steps=n,particles=count,seconds=time.monotonic()-start,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),finite=not nan,cross_wall_margin_0p07_max=cross,surface_nonfinite=int(np.count_nonzero(~np.isfinite(surface))),sample_frames=len(sample_t))
    print('CASE_DONE',json.dumps(result),flush=True)
    with (OUT/'manifest.jsonl').open('a') as file:file.write(json.dumps(result)+'\n')
    return result
try:
    results=[]
    for depth,h in [('H1',.3),('H2',.6)]:
        model=TrajectoryModel(CFG).to('cuda').eval()
        ckpt=torch.load(STATE['weight'],map_location='cpu',weights_only=True)
        state={k.removeprefix('model.'):v for k,v in ckpt['state_dict'].items() if k.startswith('model.')}
        missing,extra=model.model.load_state_dict(state,strict=False);assert not missing and not extra
        del ckpt,state;torch.cuda.empty_cache()
        for case,kind,amp,f,n in cases(h):results.append(out_one(model,depth,h,case,kind,amp,f,n))
        del model;torch.cuda.empty_cache()
    assert len(results)==28
    (OUT/'summary.json').write_text(json.dumps(dict(status='ok',cases=results,elapsed_s=time.monotonic()-T0,torch=torch.__version__,precision='autocast bf16'),indent=2))
except BaseException as e:
    traceback.print_exc()
    (OUT/'summary.json').write_text(json.dumps(dict(status='failed',error=repr(e),trace=traceback.format_exc(),elapsed_s=time.monotonic()-T0),indent=2))
    raise
finally:
    (OUT/'rollout.done').write_text((OUT/'summary.json').read_text()[:3000])
