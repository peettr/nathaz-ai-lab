"""01j fixed-state, paired-noise window scan. GPU allocation only."""
import argparse, json, math, time
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01h import build
from checkpoint_pilot_01i import correlated_noise


def record(**kw):
    print(json.dumps(kw, allow_nan=False, default=str), flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state', required=True); p.add_argument('--lag', required=True)
    p.add_argument('--dtype', choices=['float32','float64'], required=True)
    p.add_argument('--objective', choices=['mean','var'], required=True)
    p.add_argument('--fd', action='store_true')
    args=p.parse_args()
    devices=jax.devices()
    assert len(devices)==1 and devices[0].platform=='gpu', devices
    state0,chunk,_,cmd=build(384,128,3000,args.dtype,'KBC',outlet='fixed_pressure')
    state=(jnp.asarray(np.load(args.state),dtype=cmd.dtype),jnp.asarray(np.load(args.lag),dtype=cmd.dtype))
    if args.dtype=='float64':
        warm=correlated_noise(8192,26023,cmd.dtype)
        for i in range(0,8192,512): state,_=chunk(state,warm[i:i+512],cmd)
        jax.block_until_ready(state[0]);record(stage='precision_warm',steps=8192)
    # Same state and common-random-number noise for every paired evaluation.
    noise=correlated_noise(107520,26024,cmd.dtype)
    record(stage='configuration',dtype=args.dtype,objective=args.objective,gpu=str(devices[0]),
           noise_seed=26024,warm_seed=26023 if args.dtype=='float64' else None,
           inner_block=40,outer_block=840,command=np.asarray(cmd).tolist(),
           fp64_memory_fraction='0.78 (set in launcher)')
    for k in range(7,-1,-1):
        n=107520//(2**k)
        assert n%840==0 and 840%40==0
        segments=noise[:n].reshape(n//840,21,40,8)
        def value(x):
            def inner(carry,z):
                flow,s1,s2=carry
                flow,values=jax.checkpoint(chunk)(flow,z,x)
                return (flow,s1+jnp.sum(values,axis=0),s2+jnp.sum(values*values,axis=0)),None
            def outer(carry,z):
                return jax.lax.scan(inner,carry,z)[0],None
            zero=jnp.zeros((12,),dtype=cmd.dtype)
            (_,s1,s2),_=jax.lax.scan(jax.checkpoint(outer),(state,zero,zero),segments)
            mu=s1/n
            sigma=jnp.sqrt(jnp.maximum(s2/n-mu*mu,1e-20))
            return jnp.sum((mu-.023)**2) if args.objective=='mean' else jnp.sum((sigma-.001)**2)
        jf=jax.jit(value);jg=jax.jit(jax.grad(value))
        try:
            start=time.perf_counter(); y,g=jf(cmd),jg(cmd); g.block_until_ready()
            vec=np.asarray(g,dtype=float); dt=time.perf_counter()-start
            finite=bool(np.isfinite(vec).all())
            record(stage='scan',dtype=args.dtype,objective=args.objective,steps=n,
                   finite=finite,inf_count=int(np.isinf(vec).sum()),nan_count=int(np.isnan(vec).sum()),
                   norm=float(np.linalg.norm(vec)) if finite else None,
                   max_abs=float(np.max(np.abs(vec))) if finite else None,
                   gradient=vec.tolist() if finite else None,elapsed_s=dt,
                   value=float(y),memory=devices[0].memory_stats())
            if args.fd and n<=3360:
                base=np.asarray(cmd,dtype=float); fd=[]
                for fraction in (0.005,0.01):
                    estimates=[]
                    for i in range(18):
                        # Frozen parameter ranges: speeds 0.003..0.09; amplitudes 0..0.02; drag 0..0.2.
                        width=.087 if i<8 else (.02 if i<16 else .2)
                        h=width*fraction; xp=base.copy();xm=base.copy();xp[i]+=h;xm[i]-=h
                        yp=float(jf(jnp.asarray(xp,dtype=cmd.dtype)));ym=float(jf(jnp.asarray(xm,dtype=cmd.dtype)))
                        estimates.append((yp-ym)/(2*h))
                    f=np.array(estimates)
                    cos=float(np.dot(vec,f)/(np.linalg.norm(vec)*np.linalg.norm(f))) if finite and np.linalg.norm(f)>0 else None
                    rel=float(np.linalg.norm(vec-f)/np.linalg.norm(f)) if finite and np.linalg.norm(f)>0 else None
                    record(stage='fd',dtype=args.dtype,objective=args.objective,steps=n,
                           fraction=fraction,cosine=cos,relative_difference=rel,fd=f.tolist(),
                           finite_ad=finite)
                    fd.append(f)
                record(stage='fd_reliability',dtype=args.dtype,objective=args.objective,steps=n,
                       fd_relative_difference=float(np.linalg.norm(fd[0]-fd[1])/np.linalg.norm(fd[1])) if np.linalg.norm(fd[1]) else None)
        except Exception as e:
            record(stage='scan_error',dtype=args.dtype,objective=args.objective,steps=n,error=repr(e))
            raise
        finally:
            del jf,jg
            jax.clear_caches()

if __name__=='__main__':main()
