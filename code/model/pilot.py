"""50-step formal-geometry WorldParticle timing gate on isolated Colab."""
import json, math, pathlib, sys, time, traceback
import numpy as np
import torch, yaml

ROOT=pathlib.Path('/content/l26_19_wp')
sys.path.insert(0,str(ROOT/'repo'))
from trajectory_model import TrajectoryModel

DT=.01; L=3.; W=.5; MASS=.3242

def geometry(h, inward):
    dx=.07
    x=np.arange(-L/2+dx/2,L/2,dx,dtype=np.float32)
    y=np.arange(dx/2,h,dx,dtype=np.float32)
    z=np.arange(-W/2+dx/2,W/2,dx,dtype=np.float32)
    X,Y,Z=np.meshgrid(x,y,z,indexing='ij')
    pos=np.stack((X,Y,Z),axis=-1).reshape(-1,3)
    # density from actual training specimen, specified at ~1500/m²
    db=1/np.sqrt(1500.)
    faces=[]; normals=[]
    for axis,value,aranges,sign in [
        (0,-L/2,[(1,1.5),(2,W)],1),(0,L/2,[(1,1.5),(2,W)],-1),
        (2,-W/2,[(0,L),(1,1.5)],1),(2,W/2,[(0,L),(1,1.5)],-1),
        (1,0,[(0,L),(2,W)],1)]:
        coords=[]
        for dim,span in aranges:
            start=-span/2 if dim!=1 else 0
            coords.append(np.arange(start+db/2,start+span,db,dtype=np.float32))
        u,v=np.meshgrid(*coords,indexing='ij')
        p=np.full((u.size,3),value,dtype=np.float32)
        p[:,aranges[0][0]]=u.ravel();p[:,aranges[1][0]]=v.ravel()
        n=np.zeros_like(p);n[:,axis]=sign if inward else -sign
        faces.append(p);normals.append(n)
    return pos,np.concatenate(faces),np.concatenate(normals)

def setup(h,b=1):
    info=json.loads((ROOT/'prepare_v2_state.json').read_text())
    if info['status']!='ok': raise RuntimeError('unsafe/incomplete weight preparation')
    audit=json.loads((ROOT/'sample_audit.json').read_text())
    assert audit['inward_fraction']>.9 or audit['outward_fraction']>.9, audit
    inward=audit['inward_fraction']>.9
    p,box,bf=geometry(h,inward)
    cfg=yaml.safe_load((ROOT/'config.yaml').read_text())
    cfg['resolved_other_feats_channels']=1; cfg['resolved_obstacle_feats_channels']=3
    model=TrajectoryModel(cfg).to('cuda').eval()
    ckpt=torch.load(info['weight'],map_location='cpu',weights_only=True)
    state={k.removeprefix('model.'):v for k,v in ckpt['state_dict'].items() if k.startswith('model.')}
    missing,unexpected=model.model.load_state_dict(state,strict=False)
    print('LOAD',len(state),'missing',missing,'unexpected',unexpected,flush=True)
    assert not missing and not unexpected
    del ckpt,state
    torch.cuda.empty_cache()
    pos=torch.tensor(p,device='cuda').repeat(b,1,1)
    vel=torch.zeros_like(pos)
    feats=torch.zeros((b,len(p),1),device='cuda')
    box=torch.tensor(box,device='cuda').repeat(b,1,1)
    bf=torch.tensor(bf,device='cuda').repeat(b,1,1)
    force=torch.zeros_like(pos);force[:,:,1]=-9.81
    return model,pos,vel,feats,box,bf,force,dict(n_fluid=len(p),n_boundary=box.shape[1],h=h,batch=b)

def pilot(h,b):
    model,pos,vel,feats,box,bf,force,meta=setup(h,b)
    ts=[]
    with torch.inference_mode(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
        for step in range(50):
            torch.cuda.synchronize();start=time.monotonic()
            pos,vel=model(pos,vel,feats,box,bf,external_force=force)
            torch.cuda.synchronize();ts.append(time.monotonic()-start)
            if step%10==9: print('PILOT',h,b,step+1,'last10',sum(ts[-10:])/10,flush=True)
    meta.update(s_per_step=sum(ts[5:])/45,elapsed=sum(ts),first_step_s=ts[0],finite=bool(torch.isfinite(pos).all() and torch.isfinite(vel).all()),max_abs=float(pos.abs().max()))
    print('PILOT_DONE',json.dumps(meta),flush=True)
    return meta

try:
    out=[pilot(.3,1),pilot(.3,2),pilot(.6,1),pilot(.6,2)]
    (ROOT/'pilot.json').write_text(json.dumps(dict(status='ok',pilots=out),indent=2))
except BaseException as e:
    (ROOT/'pilot.json').write_text(json.dumps(dict(status='failed',error=repr(e),trace=traceback.format_exc()),indent=2))
    traceback.print_exc();raise
finally:
    (ROOT/'pilot.done').write_text((ROOT/'pilot.json').read_text()[:1500])
