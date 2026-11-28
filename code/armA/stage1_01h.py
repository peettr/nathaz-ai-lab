"""01h diagnostic or fixed-pressure stage 1; GPU-only, immutable 01g gate."""
import argparse, json, time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01h import build
from flow_stage1_01g import gate


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=('diagnostic','fixed_pressure'),required=True)
    p.add_argument('--dtype',choices=('float32','float64'),default='float32')
    p.add_argument('--out',required=True); p.add_argument('--scratch',required=True)
    a=p.parse_args()
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    out=Path(a.out); out.mkdir(parents=True,exist_ok=False)
    scratch=Path(a.scratch);scratch.mkdir(parents=True,exist_ok=False)
    nx,ny,re,seed,tau,step=384,128,3000,26022,256,512
    discard=100352;segment=25600;first=discard+8*segment
    max_steps=200192 if a.mode=='diagnostic' else 503808
    outlet='zero_gradient' if a.mode=='diagnostic' else 'fixed_pressure'
    state,run,nu,control=build(nx,ny,re,a.dtype,'KBC',outlet=outlet)
    from xlb.velocity_set import D2Q9
    from xlb.compute_backend import ComputeBackend
    from xlb.precision_policy import PrecisionPolicy
    precision=PrecisionPolicy.FP64FP64 if a.dtype=='float64' else PrecisionPolicy.FP32FP32
    vs=D2Q9(precision_policy=precision,compute_backend=ComputeBackend.JAX)
    @jax.jit
    def monitors(f):
        rho=jnp.sum(f,axis=0)
        ux=jnp.sum(f*vs.c[0,:,None,None],axis=0)/rho
        return jnp.mean(rho),jnp.mean(ux),jnp.sum(rho[0,:]*ux[0,:]),jnp.sum(rho[-1,:]*ux[-1,:])
    rng=np.random.default_rng(seed);alpha=np.exp(-1/tau);previous=np.zeros(8)
    samples=[];times=[];metrics=[];start=time.perf_counter()
    print(json.dumps(dict(stage='config',mode=a.mode,outlet=outlet,nx=nx,ny=ny,re=re,collision='KBC',seed=seed,noise_ar1_alpha=float(alpha),nominal_inlet_rms_fraction=.1,discard=discard,segment=segment,first_check=first,max_steps=max_steps,dtype=a.dtype,device=str(jax.devices()[0]))),flush=True)
    for stop in range(step,max_steps+1,step):
        white=rng.standard_normal((step,8));noise=np.empty_like(white)
        for i in range(step):
            previous=alpha*previous+np.sqrt(1-alpha*alpha)*white[i]
            noise[i]=previous
        tick=time.perf_counter()
        state,obs=run(state,jnp.asarray(noise,dtype=control.dtype),control)
        block=np.asarray(obs.block_until_ready());times.append(time.perf_counter()-tick)
        if not np.isfinite(block).all():
            np.savetxt(out/'monitor.csv',np.asarray(metrics),delimiter=',',header='step,rho_mean,u_mean,inlet_mass_flux,outlet_mass_flux',comments='')
            print(json.dumps(dict(stage='unstable',steps=stop)),flush=True)
            raise SystemExit(43)
        if stop%2048==0:
            vals=np.asarray(jnp.stack(monitors(state[0])).block_until_ready(),dtype=float)
            if not np.isfinite(vals).all():
                print(json.dumps(dict(stage='unstable_monitor',steps=stop)),flush=True)
                raise SystemExit(43)
            metrics.append([stop,*vals.tolist()])
        if a.mode=='diagnostic':
            continue
        if stop>discard: samples.append(block)
        if stop>=first and (stop-first)%(segment*2)==0:
            series=np.concatenate(samples[-(8*segment//step):])
            result=gate(series)
            print(json.dumps(dict(stage='gate',steps=stop,**result)),flush=True)
            np.save(scratch/f'state_{a.dtype}_{stop}.npy',np.asarray(state[0]))
            np.save(scratch/f'lag_{a.dtype}_{stop}.npy',np.asarray(state[1]))
            if result['qualified']:
                np.save(out/f'state_{a.dtype}.npy',np.asarray(state[0]))
                np.save(out/f'lag_{a.dtype}.npy',np.asarray(state[1]))
                print(json.dumps(dict(stage='spinup_saved',steps=stop,hot_forward_s_per_step=float(np.mean(times[-16:])/step))),flush=True)
                break
    np.savetxt(out/'monitor.csv',np.asarray(metrics),delimiter=',',header='step,rho_mean,u_mean,inlet_mass_flux,outlet_mass_flux',comments='')
    if a.mode=='diagnostic':
        print(json.dumps(dict(stage='diagnostic_complete',steps=max_steps,monitor_count=len(metrics),elapsed_seconds=time.perf_counter()-start)),flush=True)
        return
    if not result['qualified']:
        print(json.dumps(dict(stage='final',qualified=False,steps=max_steps,elapsed_seconds=time.perf_counter()-start)),flush=True)
        raise SystemExit(42)
    post=[]
    for _ in range(256):
        white=rng.standard_normal((step,8));noise=np.empty_like(white)
        for i in range(step):
            previous=alpha*previous+np.sqrt(1-alpha*alpha)*white[i]
            noise[i]=previous
        state,obs=run(state,jnp.asarray(noise,dtype=control.dtype),control)
        post.append(np.asarray(obs.block_until_ready()))
    np.save(scratch/f'post_probe_{a.dtype}.npy',np.concatenate(post))
    print(json.dumps(dict(stage='postspinup',steps=131072,elapsed_seconds=time.perf_counter()-start)),flush=True)
if __name__=='__main__':main()
