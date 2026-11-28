"""BGK fallback at Re_H=1000; frozen 01g/01h pulse/spinup gate."""
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
    p.add_argument('--out',required=True)
    p.add_argument('--scratch',required=True)
    args=p.parse_args()
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    scratch=Path(args.scratch); scratch.mkdir(parents=True,exist_ok=False)
    nx,ny,re,seed,tau,step=384,128,1000,26022,256,512
    discard,segment,max_steps=100352,25600,503808
    first=discard+8*segment
    state,run,nu,control=build(nx,ny,re,'float32','BGK',outlet='fixed_pressure')
    rng=np.random.default_rng(seed); alpha=np.exp(-1/tau); prev=np.zeros(8)
    samples=[]; times=[]; t0=time.perf_counter(); qualified=False
    print(json.dumps(dict(stage='config',nx=nx,ny=ny,re=re,nu=nu,collision='BGK',outlet='fixed_pressure',seed=seed,noise_ar1_alpha=float(alpha),nominal_inlet_rms_fraction=.1,discard=discard,segment=segment,first_check=first,max_steps=max_steps,dtype='float32',device=str(jax.devices()[0]))),flush=True)
    def noise():
        nonlocal prev
        white=rng.standard_normal((step,8)); z=np.empty_like(white)
        for i in range(step):
            prev=alpha*prev+np.sqrt(1-alpha*alpha)*white[i]
            z[i]=prev
        return jnp.asarray(z,dtype=control.dtype)
    for stop in range(step,max_steps+1,step):
        tick=time.perf_counter()
        state,obs=run(state,noise(),control)
        block=np.asarray(obs.block_until_ready()); times.append(time.perf_counter()-tick)
        if not np.isfinite(block).all() or not np.isfinite(np.asarray(state[0][...,::16,::16])).all():
            print(json.dumps(dict(stage='unstable',steps=stop)),flush=True)
            raise SystemExit(43)
        if stop>discard: samples.append(block)
        if stop>=first and (stop-first)%(segment*2)==0:
            series=np.concatenate(samples[-(8*segment//step):])
            result=gate(series)
            print(json.dumps(dict(stage='gate',steps=stop,**result)),flush=True)
            np.save(scratch/f'state_float32_{stop}.npy',np.asarray(state[0]))
            np.save(scratch/f'lag_float32_{stop}.npy',np.asarray(state[1]))
            if result['qualified']:
                qualified=True
                np.save(out/'state_float32.npy',np.asarray(state[0]))
                np.save(out/'lag_float32.npy',np.asarray(state[1]))
                print(json.dumps(dict(stage='spinup_saved',steps=stop,hot_forward_s_per_step=float(np.mean(times[-16:])/step))),flush=True)
                break
    print(json.dumps(dict(stage='final',qualified=qualified,steps=stop,elapsed_seconds=time.perf_counter()-t0,measured_forward_s_per_step=float(np.mean(times[-16:])/step))),flush=True)
    if not qualified: raise SystemExit(42)
    post=[]
    for _ in range(256):
        state,obs=run(state,noise(),control)
        post.append(np.asarray(obs.block_until_ready()))
    np.save(scratch/'post_probe_float32.npy',np.concatenate(post))
    print(json.dumps(dict(stage='postspinup',steps=131072,elapsed_seconds=time.perf_counter()-t0)),flush=True)
if __name__=='__main__': main()
