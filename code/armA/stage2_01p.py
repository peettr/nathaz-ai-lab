"""01p BGK paired random-command AD/FD; fixed qualified state and noise seed."""
import argparse,json,math,time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
import armA_case_01d
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise
ROOT=Path('/groups/kareem/[用户]/L26_22_DIFFLBM_20261114/armA')
STATE=ROOT/'run_01l/bgk_stage1/qualified'
RUN=ROOT/'run_01p/stage2'
NOMINAL=np.r_[np.full(8,.05),np.full(8,.005),[.025,.04]]
WIDTHS=np.r_[np.full(8,.087),np.full(8,.02),np.full(2,.2)]
COMMANDS=np.random.default_rng(26220).uniform(.8*NOMINAL,1.2*NOMINAL,size=(5,18))
BLOCK=40

def safe(v):
    if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [safe(x) for x in v]
    if isinstance(v,(np.floating,float)):
        x=float(v);return x if math.isfinite(x) else ('NaN' if math.isnan(x) else ('+inf' if x>0 else '-inf'))
    if isinstance(v,(np.integer,int)):return int(v)
    if isinstance(v,(np.bool_,bool)):return bool(v)
    return v

def emit(path,**r):
    with path.open('a',buffering=1) as f:f.write(json.dumps(safe(r),sort_keys=True,allow_nan=False)+'\n')

def begin(dtype):
    _,chunk,_,cmd=build(384,128,1000,dtype,'BGK',outlet='fixed_pressure')
    st=(jnp.asarray(np.load(STATE/'state_float32.npy'),dtype=cmd.dtype),jnp.asarray(np.load(STATE/'lag_float32.npy'),dtype=cmd.dtype))
    if dtype=='float64':
        z=correlated_noise(8192,26023,cmd.dtype)
        for i in range(0,8192,512):st,_=chunk(st,z[i:i+512],cmd)
        st[0].block_until_ready()
    return st,chunk,cmd

def fd_prefixes_at(st,chunk,noise,x,marks):
    assert noise.shape[0]%BLOCK==0 and all(t%BLOCK==0 for t in marks)
    zero=jnp.zeros((12,),x.dtype)
    def body(carry,z):
        flow,acc,sq=carry
        flow,y=chunk(flow,z,x)
        acc=acc+jnp.sum(y,axis=0);sq=sq+jnp.sum(y*y,axis=0)
        return (flow,acc,sq),(acc,sq)
    _,(sums,squares)=jax.lax.scan(body,(st,zero,zero),noise.reshape(-1,BLOCK,8))
    idx=np.asarray(marks)//BLOCK-1
    mu=sums[idx]/jnp.asarray(marks,dtype=x.dtype)[:,None]
    sigma=jnp.sqrt(jnp.maximum(squares[idx]/jnp.asarray(marks,dtype=x.dtype)[:,None]-mu*mu,1e-20))
    return jnp.stack((jnp.sum((mu-.023)**2,axis=1),jnp.sum((sigma-.001)**2,axis=1)),axis=1)

def obj(st,chunk,noise,x,T,kind):
    remat=jax.checkpoint(chunk);zero=jnp.zeros((12,),x.dtype)
    def body(carry,z):
        flow,acc,sq=carry
        flow,y=remat(flow,z,x)
        return (flow,acc+jnp.sum(y,axis=0),sq+jnp.sum(y*y,axis=0)),None
    (_,a,s),_=jax.lax.scan(body,(st,zero,zero),noise[:T].reshape(-1,BLOCK,8))
    mu=a/T;sig=jnp.sqrt(jnp.maximum(s/T-mu*mu,1e-20))
    return jnp.sum((mu-.023)**2) if kind=='mean' else jnp.sum((sig-.001)**2)

def compare(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    na=np.linalg.norm(a);nb=np.linalg.norm(b)
    if not (np.isfinite(a).all() and np.isfinite(b).all() and np.isfinite(na) and np.isfinite(nb) and na>0 and nb>0):
        return {'cos':'NaN','relative_difference':'NaN','ad_norm':safe(float(na)),'fd_norm':safe(float(nb)),'finite':False}
    return {'cos':float(np.dot(a,b)/(na*nb)),'relative_difference':float(np.linalg.norm(a-b)/nb),
            'ad_norm':float(na),'fd_norm':float(nb),'finite':True}

def run_point(i,tm,tv,out):
    windows={'mean':tuple(tm//d for d in (8,4,2,1)), 'var':tuple(tv//d for d in (8,4,2,1))}
    if any(t%BLOCK for ts in windows.values() for t in ts):raise ValueError('all windows must align to block 40')
    st64,chunk64,cmd64=begin('float64');base=COMMANDS[i]
    noise64=correlated_noise(max(tm,tv),26031,cmd64.dtype)
    fd={};times=set(windows['mean']+windows['var']);full=max(times)
    for h in (.01,.005,.0025,.001):
        if h<.005:marks=tuple(sorted(set((tm,tv))))
        else:marks=tuple(sorted(times))
        perturb=h*WIDTHS*np.eye(18)
        inputs=jnp.asarray(np.r_[base+perturb,base-perturb],dtype=cmd64.dtype)
        fun=jax.jit(jax.vmap(lambda x:fd_prefixes_at(st64,chunk64,noise64[:max(marks)],x,marks)))
        t=time.perf_counter();arr=np.asarray(fun(inputs).block_until_ready());elapsed=time.perf_counter()-t
        emit(out,type='fd_batch',point=i,step=h,marks=marks,seconds_including_jit=elapsed,finite=bool(np.isfinite(arr).all()))
        for kind,col in (('mean',0),('var',1)):
            for T in windows[kind]:
                if T in marks:
                    idx=marks.index(T);fd[kind,T,h]=(arr[:18,idx,col]-arr[18:,idx,col])/(2*h*WIDTHS)
        del fun
    ad={}
    for dtype in ('float32','float64'):
        if dtype=='float64':st,chunk,noise=st64,chunk64,noise64
        else:
            st,chunk,_=begin(dtype);noise=correlated_noise(full,26031,jnp.float32)
        for kind,ts in windows.items():
            for T in ts:
                f=jax.jit(jax.grad(lambda x:obj(st,chunk,noise,x,T,kind)))
                t=time.perf_counter();g=np.asarray(f(jnp.asarray(base,dtype=st[0].dtype)).block_until_ready());elapsed=time.perf_counter()-t
                ad[dtype,kind,T]=g
                for h in ((.01,.005,.0025,.001) if T==ts[-1] else (.01,.005)):
                    emit(out,type='result',point=i,command=base.tolist(),noise_seed=26031,dtype=dtype,metric=kind,T=T,
                         fd_step_fraction=h,ad=g.tolist(),fd=fd[kind,T,h].tolist(),seconds_including_jit=elapsed,
                         **compare(g,fd[kind,T,h]))
                del f
    for kind,ts in windows.items():
        for T in ts:
            a,b=fd[kind,T,.01],fd[kind,T,.005]
            emit(out,type='fd_reliability',point=i,metric=kind,T=T,relative_difference=compare(b,a)['relative_difference'],
                 unreliable=bool(not isinstance(compare(b,a)['relative_difference'],(int,float)) or compare(b,a)['relative_difference']>.05))
        fullT=ts[-1];short=ts[0]
        emit(out,type='truncation',point=i,metric=kind,short_window=short,full_window=fullT,
             **compare(ad['float64',kind,short],fd[kind,fullT,.01]))
        seglen=fullT//(2 if kind=='mean' else 8)
        if seglen%BLOCK:raise ValueError('segment length misaligned')
        # Forward common trajectory; stop-gradient each segment's start state.
        st,chunk,_=begin('float64');z=noise64[:fullT];segments=[]
        for start in range(0,fullT,seglen):
            segz=z[start:start+seglen]
            f=jax.jit(jax.grad(lambda x:obj(st,chunk,segz,x,seglen,kind)))
            segments.append(np.asarray(f(jnp.asarray(base,dtype=cmd64.dtype)).block_until_ready()))
            st,_=chunk(st,segz,jnp.asarray(base,dtype=cmd64.dtype));st[0].block_until_ready()
            del f
        avg=np.mean(segments,axis=0)
        for h in (.01,.005,.0025,.001):
            emit(out,type='segment_average',point=i,metric=kind,T=fullT,segment_length=seglen,
                 segment_count=len(segments),segment_objective='each segment mean or sigma across 12 probes versus fixed target; stop gradient at segment initial state; equal-weight gradient average',
                 fd_step_fraction=h,gradient=avg.tolist(),**compare(avg,fd[kind,fullT,h]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--point',type=int,required=True);p.add_argument('--tm',type=int,required=True);p.add_argument('--tv',type=int,required=True);a=p.parse_args()
    if a.point not in range(5) or len(jax.devices())!=1 or jax.devices()[0].platform!='gpu':raise RuntimeError('allocated GPU required')
    RUN.mkdir(parents=True,exist_ok=True);out=RUN/f'point_{a.point}.jsonl'
    if out.exists():raise FileExistsError(out)
    emit(out,type='start',point=a.point,command=COMMANDS[a.point].tolist(),command_seed=26220,noise_seed=26031,T_m=a.tm,T_v=a.tv)
    run_point(a.point,a.tm,a.tv,out)
    emit(out,type='complete',point=a.point)
if __name__=='__main__':main()
