"""L26.22-01m: frozen BGK five-point paired AD/FD study on allocated A10.
One FP64 batched forward per (point, FD step); all objective/window FD
values come from its prefixes. AD uses separate reverse passes per prefix.
"""
import argparse
import json
import math
import time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
import armA_case_01d  # isolated import-only shim, no Warp computation
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise

TM, TV, BLOCK = 35840, 74240, 40
SEEDS = (26031, 26032, 26033, 26034, 26035)
WIDTHS = np.array([.087]*8 + [.02]*8 + [.2]*2)
ROOT = Path('/groups/kareem/[用户]/L26_22_DIFFLBM_20261114/armA')
STATE = ROOT/'run_01l/bgk_stage1/qualified'
RUN = ROOT/'run_01m/stage2'
WINDOWS = {'mean': (TM//8, TM//4, TM//2, TM), 'var': (TV//8, TV//4, TV//2, TV)}
ALL_T = sorted(set(WINDOWS['mean']+WINDOWS['var']))

def safe(v):
    if isinstance(v, dict): return {k:safe(x) for k,x in v.items()}
    if isinstance(v, (list,tuple,np.ndarray)): return [safe(x) for x in v]
    if isinstance(v, (np.floating,float)):
        v=float(v)
        return v if math.isfinite(v) else ('NaN' if math.isnan(v) else ('+inf' if v>0 else '-inf'))
    if isinstance(v,(np.integer,int)): return int(v)
    if isinstance(v,(np.bool_,bool)): return bool(v)
    return v

def emit(path, item):
    with open(path,'a',buffering=1) as f: f.write(json.dumps(safe(item),allow_nan=False,sort_keys=True)+'\n')

def beginning(dtype):
    _,chunk,_,cmd=build(384,128,1000,dtype,'BGK',outlet='fixed_pressure')
    st=(jnp.asarray(np.load(STATE/'state_float32.npy'),dtype=cmd.dtype),
        jnp.asarray(np.load(STATE/'lag_float32.npy'),dtype=cmd.dtype))
    if dtype=='float64':
        noise=correlated_noise(8192,26023,cmd.dtype)
        for i in range(0,8192,512): st,_=chunk(st,noise[i:i+512],cmd)
        st[0].block_until_ready()
    return st,chunk,cmd

def objective(st,chunk,noise,x,T,kind):
    remat=jax.checkpoint(chunk)
    zero=jnp.zeros((12,),x.dtype)
    def one(carry,z):
        flow,acc,sq=carry
        flow,y=remat(flow,z,x)
        return (flow,acc+jnp.sum(y,axis=0),sq+jnp.sum(y*y,axis=0)),None
    (_,acc,sq),_=jax.lax.scan(one,(st,zero,zero),noise[:T].reshape(T//BLOCK,BLOCK,8))
    mu=acc/T
    var=jnp.sqrt(jnp.maximum(sq/T-mu*mu,1e-20))
    return jnp.sum((mu-.023)**2) if kind=='mean' else jnp.sum((var-.001)**2)

def fd_prefixes(st,chunk,noise,commands):
    # Static-length single batched forward, checkpoint values at every predeclared prefix.
    zero=jnp.zeros((12,),commands.dtype)
    marks=np.array([T//BLOCK-1 for T in ALL_T],dtype=np.int32)
    def one(x):
        def body(carry,z):
            flow,acc,sq=carry
            flow,y=chunk(flow,z,x)
            acc=acc+jnp.sum(y,axis=0); sq=sq+jnp.sum(y*y,axis=0)
            return (flow,acc,sq),(acc,sq)
        (_,_,_), (sums,squares)=jax.lax.scan(body,(st,zero,zero),noise.reshape(TV//BLOCK,BLOCK,8))
        sums=sums[marks]; squares=squares[marks]
        T=jnp.asarray(ALL_T,dtype=x.dtype)[:,None]
        mu=sums/T; sigma=jnp.sqrt(jnp.maximum(squares/T-mu*mu,1e-20))
        return jnp.stack((jnp.sum((mu-.023)**2,axis=1),jnp.sum((sigma-.001)**2,axis=1)),axis=1)
    return jax.jit(jax.vmap(one))(commands)

def compare(ad,fd):
    a=np.asarray(ad,dtype=float); f=np.asarray(fd,dtype=float)
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(f)):
        return {'finite':False,'cos':'NaN','relative_difference':'NaN','ad_norm':float(np.linalg.norm(a)),'fd_norm':float(np.linalg.norm(f))}
    na=float(np.linalg.norm(a)); nf=float(np.linalg.norm(f))
    return {'finite':True,'cos':float(np.dot(a,f)/(na*nf)) if na*nf else 'NaN',
            'relative_difference':float(np.linalg.norm(a-f)/nf) if nf else 'NaN',
            'ad_norm':na,'fd_norm':nf}

def run_point(idx, out):
    seed=SEEDS[idx]
    # Begin every objective and precision at the same qualified state; same noise seed.
    st64,chunk64,cmd64=beginning('float64')
    noise64=correlated_noise(TV,seed,cmd64.dtype)
    base=np.asarray(cmd64)
    fd={}
    for step in ((.01,.005) if idx<2 else (.01,)):
        perturb=step*WIDTHS*np.eye(18)
        inputs=jnp.asarray(np.concatenate((base+perturb,base-perturb)),dtype=cmd64.dtype)
        tic=time.perf_counter()
        vals=np.asarray(fd_prefixes(st64,chunk64,noise64,inputs).block_until_ready())
        seconds=time.perf_counter()-tic
        if vals.shape!=(36,len(ALL_T),2): raise ValueError(vals.shape)
        for kind,col in (('mean',0),('var',1)):
            for T in WINDOWS[kind]:
                j=ALL_T.index(T)
                g=(vals[:18,j,col]-vals[18:,j,col])/(2*step*WIDTHS)
                fd[(kind,T,step)]=g
        emit(out,{'type':'fd_batch','point':idx,'seed':seed,'step':step,'seconds_including_jit':seconds,
                  'finite':bool(np.isfinite(vals).all()),'peak':jax.devices()[0].memory_stats()})
    ad={}
    for dtype in ('float32','float64'):
        if dtype=='float64': st,chunk,cmd,noise=st64,chunk64,cmd64,noise64
        else:
            st,chunk,cmd=beginning(dtype)
            noise=correlated_noise(TV,seed,cmd.dtype)
        for kind in ('mean','var'):
            for T in WINDOWS[kind]:
                fun=jax.jit(jax.grad(lambda x:objective(st,chunk,noise,x,T,kind)))
                tic=time.perf_counter(); grad=np.asarray(fun(cmd).block_until_ready()); elapsed=time.perf_counter()-tic
                ad[(dtype,kind,T)]=grad
                for step in ((.01,.005) if idx<2 else (.01,)):
                    cmp=compare(grad,fd[(kind,T,step)])
                    emit(out,{'type':'result','point':idx,'seed':seed,'dtype':dtype,'metric':kind,'T':T,
                              'fd_step_fraction':step,'ad':grad.tolist(),'fd':fd[(kind,T,step)].tolist(),
                              'seconds_including_jit':elapsed,**cmp})
                del fun
    # Descriptive quantities only; not a gate. Full-window FD is the denominator/reference.
    for kind in ('mean','var'):
        T=TM if kind=='mean' else TV
        g=ad[('float64',kind,T//8)]
        emit(out,{'type':'truncation_proxy','point':idx,'metric':kind,'short_window':T//8,
                  'full_window':T,**compare(g,fd[(kind,T,.01)]),
                  'interpretation':'short-prefix versus full-window FD; not segment-average gradient'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--point',type=int,required=True);a=p.parse_args()
    if a.point not in range(5): raise ValueError(a.point)
    if len(jax.devices())!=1 or jax.devices()[0].platform!='gpu': raise RuntimeError('single allocated GPU required')
    if not (STATE/'state_float32.npy').is_file(): raise FileNotFoundError(STATE)
    RUN.mkdir(parents=True,exist_ok=True)
    out=RUN/f'point_{a.point}.jsonl'
    if out.exists(): raise FileExistsError(out)
    emit(out,{'type':'start','point':a.point,'seed':SEEDS[a.point],'T_m':TM,'T_v':TV,'grid':[384,128],
              'Re_H':1000,'collision':'BGK','source':'1755011 qualified state','precision_warm_steps':8192})
    run_point(a.point,out)
    emit(out,{'type':'complete','point':a.point})
if __name__=='__main__': main()
