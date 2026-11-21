"""BGK stationary-window / hot-gradient / vectorized FD pilot; GPU only."""
import argparse, json, math, time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
import armA_case_01d  # fail-closed unused-Warp import shim
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise
from steady_windows_01f import windows

def emit(**kw):
    print(json.dumps(kw, allow_nan=False, default=lambda x: x.tolist() if hasattr(x,'tolist') else str(x)), flush=True)

def device_peak(dev):
    stats=dev.memory_stats() or {}
    return {'peak_bytes_in_use':stats.get('peak_bytes_in_use'), 'bytes_in_use':stats.get('bytes_in_use'), 'bytes_limit':stats.get('bytes_limit')}

def initial(root, dtype):
    _,chunk,_,control=build(384,128,1000,dtype,'BGK',outlet='fixed_pressure')
    state=(jnp.asarray(np.load(root/'state_float32.npy'),dtype=control.dtype),jnp.asarray(np.load(root/'lag_float32.npy'),dtype=control.dtype))
    if dtype=='float64':
        noise=correlated_noise(8192,26023,control.dtype)
        for i in range(0,8192,512): state,_=chunk(state,noise[i:i+512],control)
        state[0].block_until_ready()
        emit(stage='precision_warm',dtype=dtype,steps=8192)
    return state,chunk,control

def probe_series(root, n, batch):
    state,chunk,cmd=initial(root,'float32')
    # Qualified state from 1755011, not the transient; one fixed post-state noise realization.
    noise=correlated_noise(n,26025,cmd.dtype)
    obs=[]
    for i in range(0,n,512):
        state,part=chunk(state,noise[i:i+512],cmd)
        obs.append(np.asarray(part.block_until_ready()))
    series=np.concatenate(obs)
    records={}
    for key,T,rows in windows(series,batch=batch,denominator=.05):
        records[key]={'T':T,'last':rows[-1],'row_count':len(rows)}
        emit(stage='windows',metric=key,T=T,last=rows[-1],batch=batch,n=n)
    return records

def measure(root,dtype,metric,T,block):
    state,chunk,cmd=initial(root,dtype)
    # Identical noise for warm/hot evaluations; branch from identical saved state.
    noise=correlated_noise(T,26024,cmd.dtype)
    blocks=[noise[i:min(i+block,T)] for i in range(0,T,block)]
    # Dynamic last block shape would recompile chunk; qualified T must align.
    assert T%block==0
    blocks=noise.reshape((T//block,block,8))
    remat=jax.checkpoint(chunk)
    def objective(x):
        def outer(carry,z):
            flow,total,square=carry
            flow,samples=remat(flow,z,x)
            return (flow,total+jnp.sum(samples,axis=0),square+jnp.sum(samples*samples,axis=0)),None
        zero=jnp.zeros((12,),cmd.dtype)
        (_,total,square),_=jax.lax.scan(outer,(state,zero,zero),blocks)
        mu=total/T
        sigma=jnp.sqrt(jnp.maximum(square/T-mu*mu,1e-20))
        return jnp.sum((mu-.023)**2) if metric=='mean' else jnp.sum((sigma-.001)**2)
    forward=jax.jit(objective); gradient=jax.jit(jax.grad(objective))
    emit(stage='compile_start',dtype=dtype,metric=metric,T=T,block=block)
    forward(cmd).block_until_ready()
    gradient(cmd).block_until_ready()
    dev=jax.devices()[0]
    t=time.perf_counter(); f=forward(cmd).block_until_ready(); fw=time.perf_counter()-t
    t=time.perf_counter(); g=gradient(cmd).block_until_ready(); gw=time.perf_counter()-t
    gg=np.asarray(g)
    peak=device_peak(dev)
    emit(stage='hot',dtype=dtype,metric=metric,T=T,block=block,forward_s=fw,gradient_s=gw,ratio=gw/fw,finite=bool(np.isfinite(gg).all()),norm=float(np.linalg.norm(gg)) if np.isfinite(gg).all() else 'NaN',peak=peak,value=float(f))
    return fw,gw,peak

def small_batch(root):
    state,chunk,cmd=initial(root,'float64')
    T=840; noise=correlated_noise(T,26024,cmd.dtype)
    def two(x):
        acc=jnp.zeros((12,),cmd.dtype); sq=acc
        def one(carry,z):
            st,total,square=carry
            st,probe=chunk(st,z,x)
            return (st,total+jnp.sum(probe,axis=0),square+jnp.sum(probe*probe,axis=0)),None
        (_,total,square),_=jax.lax.scan(one,(state,acc,sq),noise.reshape(T//40,40,8))
        mu=total/T; sigma=jnp.sqrt(jnp.maximum(square/T-mu*mu,1e-20))
        return jnp.stack((jnp.sum((mu-.023)**2),jnp.sum((sigma-.001)**2)))
    x=np.asarray(cmd); plus=[]; minus=[]
    for i in range(18):
        width=.087 if i<8 else (.02 if i<16 else .2)
        p=x.copy();m=x.copy();p[i]+=.01*width;m[i]-=.01*width
        plus.append(p);minus.append(m)
    vec=jnp.asarray(np.asarray(plus+minus))
    batched=jax.jit(jax.vmap(two)); t=time.perf_counter()
    y=batched(vec).block_until_ready(); first=time.perf_counter()-t
    t=time.perf_counter(); y=batched(vec).block_until_ready(); hot=time.perf_counter()-t
    emit(stage='vmap_sample',T=T,outputs=int(y.shape[0]),objectives=2,first_s=first,hot_s=hot,peak=device_peak(jax.devices()[0]),all_finite=bool(np.isfinite(np.asarray(y)).all()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--state-dir',required=True);p.add_argument('--mode',choices=['windows','hot','sample'],required=True)
    p.add_argument('--dtype',choices=['float32','float64']);p.add_argument('--metric',choices=['mean','var']);p.add_argument('--T',type=int);p.add_argument('--n',type=int,default=131072);p.add_argument('--batch',type=int,default=2560);p.add_argument('--block',type=int,default=40)
    a=p.parse_args();assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    root=Path(a.state_dir);assert (root/'state_float32.npy').is_file() and (root/'lag_float32.npy').is_file()
    if a.mode=='windows':probe_series(root,a.n,a.batch)
    elif a.mode=='hot':assert a.dtype and a.metric and a.T;measure(root,a.dtype,a.metric,a.T,a.block)
    else:small_batch(root)
if __name__=='__main__':main()
