"""BGK Re_H=1000 fixed-pressure paired short-window FP64 AD/FD."""
import argparse, json, math, time
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
import armA_case_01d  # fail-closed shim before XLB imports
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise

def serial(x):
    if isinstance(x,dict): return {k:serial(v) for k,v in x.items()}
    if isinstance(x,(tuple,list,np.ndarray)): return [serial(v) for v in x]
    if isinstance(x,(float,np.floating)):
        f=float(x); return f if math.isfinite(f) else str(f)
    if isinstance(x,(bool,np.bool_)): return bool(x)
    if isinstance(x,(int,np.integer)): return int(x)
    return str(x)
def emit(**kw): print(json.dumps(serial(kw),allow_nan=False),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--state',required=True); ap.add_argument('--lag',required=True)
    ap.add_argument('--max-seconds',type=float,default=1800.)
    a=ap.parse_args()
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    _,chunk,_,cmd=build(384,128,1000,'float64','BGK',outlet='fixed_pressure')
    state=(jnp.asarray(np.load(a.state),dtype=jnp.float64),jnp.asarray(np.load(a.lag),dtype=jnp.float64))
    warm=correlated_noise(8192,26023,jnp.float64)
    for i in range(0,8192,512): state,_=chunk(state,warm[i:i+512],cmd)
    state[0].block_until_ready()
    control=np.asarray(cmd,dtype=np.float64)
    noise=correlated_noise(3360,26024,jnp.float64)
    t0=time.monotonic(); emit(stage='config',gpu=str(jax.devices()[0]),collision='BGK',re=1000,fd_fractions=[.01,.005],warm_steps=8192,seed=26024)
    for steps in (840,1680,3360):
        if time.monotonic()-t0>a.max_seconds: emit(stage='budget_stop',steps=steps); break
        blocks=noise[:steps].reshape(steps//40,40,8)
        def objective(x):
            def one(carry,z):
                flow,acc=carry
                flow,probe=jax.checkpoint(chunk)(flow,z,x)
                return (flow,acc+jnp.sum(probe,axis=0)),None
            (_,acc),_=jax.lax.scan(one,(state,jnp.zeros((12,),dtype=jnp.float64)),blocks)
            return jnp.sum((acc/steps-.023)**2)
        f=jax.jit(objective); grad=jax.jit(jax.grad(objective))
        g=np.asarray(grad(jnp.asarray(control)),dtype=float)
        for fraction in (.01,.005):
            fd=[]
            for i in range(18):
                width=.087 if i<8 else (.02 if i<16 else .2)
                h=fraction*width
                plus=control.copy(); minus=control.copy(); plus[i]+=h; minus[i]-=h
                fd.append((float(f(jnp.asarray(plus)))-float(f(jnp.asarray(minus))))/(2*h))
            fd=np.asarray(fd)
            gn=float(np.linalg.norm(g)); fn=float(np.linalg.norm(fd))
            finite=bool(np.isfinite(g).all() and np.isfinite(fd).all())
            cosine=float(np.dot(g,fd)/(gn*fn)) if finite and gn and fn and np.isfinite(gn*fn) else None
            rel=float(np.linalg.norm(g-fd)/fn) if finite and fn else None
            emit(stage='short_window',steps=steps,fd_fraction=fraction,finite_ad=bool(np.isfinite(g).all()),finite_fd=bool(np.isfinite(fd).all()),ad_norm=gn,fd_norm=fn,cosine=cosine,relative_difference=rel,ad=g,fd=fd,elapsed_s=time.monotonic()-t0)
            if not (finite and cosine is not None and cosine>=.95 and rel<=.10):
                emit(stage='gate_stop',steps=steps,fd_fraction=fraction); return
        del f,grad
        jax.clear_caches()
    emit(stage='done',elapsed_s=time.monotonic()-t0)
if __name__=='__main__': main()
